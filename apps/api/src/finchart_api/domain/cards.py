from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from finchart_api.domain.models import Card, NewCard
from finchart_api.domain.pipeline import analyze_screenshot
from finchart_api.domain.ports import DuplicateCardError, UserData
from finchart_api.imaging import sha256_hex
from finchart_api.llm.base import VisionProvider


class BoardNotFoundError(LookupError):
    pass


class CardNotFoundError(LookupError):
    pass


class DailyQuotaExceededError(Exception):
    pass


@dataclass(frozen=True)
class DailyUsage:
    limit: int
    used: int
    resets_at: datetime

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


def start_of_day() -> datetime:
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


async def daily_usage(data: UserData, daily_quota: int) -> DailyUsage:
    start = start_of_day()
    used = await data.cards.analyses_since(start)
    return DailyUsage(limit=daily_quota, used=used, resets_at=start + timedelta(days=1))


async def _ensure_quota(data: UserData, daily_quota: int) -> None:
    if (await daily_usage(data, daily_quota)).remaining <= 0:
        raise DailyQuotaExceededError(daily_quota)


@dataclass(frozen=True)
class CardCreation:
    card: Card
    duplicate: bool


async def create_card(
    data: UserData,
    provider: VisionProvider,
    board_id: UUID,
    image_bytes: bytes,
    daily_quota: int,
) -> CardCreation:
    if await data.boards.get(board_id) is None:
        raise BoardNotFoundError(board_id)

    existing = await data.cards.find_by_sha(sha256_hex(image_bytes))
    if existing is not None:
        return CardCreation(card=existing, duplicate=True)

    await _ensure_quota(data, daily_quota)
    analyzed = await analyze_screenshot(image_bytes, provider)
    image_path = f"{data.owner_id}/{analyzed.sha256}.webp"
    thumb_path = f"{data.owner_id}/{analyzed.sha256}_thumb.webp"
    await data.storage.upload(image_path, analyzed.images.image, "image/webp")
    await data.storage.upload(thumb_path, analyzed.images.thumb, "image/webp")

    analysis = analyzed.vision.analysis
    new_card = NewCard(
        board_id=board_id,
        owner_id=data.owner_id,
        # Newest first: the latest upload is what the user wants to read next.
        position=0,
        image_path=image_path,
        thumb_path=thumb_path,
        image_sha256=analyzed.sha256,
        title=analysis.title,
        chart_type=analysis.chart_type,
        period=analysis.period,
        takeaways=analysis.takeaways,
        interpretation=analysis.interpretation,
        caveats=analysis.caveats,
        model=analyzed.vision.model,
        raw_response=analyzed.vision.raw,
    )
    try:
        return CardCreation(card=await data.cards.insert(new_card), duplicate=False)
    except DuplicateCardError:
        # A concurrent upload of the same image won the race; reuse its card.
        winner = await data.cards.find_by_sha(analyzed.sha256)
        if winner is None:
            raise
        return CardCreation(card=winner, duplicate=True)


async def reanalyze_card(
    data: UserData, provider: VisionProvider, card_id: UUID, daily_quota: int
) -> Card:
    """Asks the model again about the stored crop; the image and the user's note stay as they are.

    Only the crop is kept, so its bbox is ignored rather than cropping a second time.
    """
    card = await data.cards.get(card_id)
    image = None if card is None else await data.storage.read(card.image_path)
    if card is None or image is None:
        raise CardNotFoundError(card_id)
    await _ensure_quota(data, daily_quota)
    vision = await provider.analyze(image)
    updated = await data.cards.replace_analysis(card_id, vision.analysis, vision.model, vision.raw)
    if updated is None:
        raise CardNotFoundError(card_id)
    return updated


async def delete_card(data: UserData, card_id: UUID) -> bool:
    card = await data.cards.delete(card_id)
    if card is None:
        return False
    await data.storage.remove([card.image_path, card.thumb_path])
    return True


async def delete_board(data: UserData, board_id: UUID) -> bool:
    cards = await data.cards.list_for_board(board_id)
    if not await data.boards.delete(board_id):
        return False
    paths = [p for card in cards for p in (card.image_path, card.thumb_path)]
    if paths:
        await data.storage.remove(paths)
    return True
