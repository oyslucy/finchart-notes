from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from finchart_api.domain.models import Card, NewCard
from finchart_api.domain.pipeline import analyze_screenshot
from finchart_api.domain.ports import DuplicateCardError, UserData
from finchart_api.imaging import sha256_hex
from finchart_api.llm.base import VisionProvider


class BoardNotFoundError(LookupError):
    pass


class DailyQuotaExceededError(Exception):
    pass


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

    start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    if await data.cards.analyses_since(start_of_day) >= daily_quota:
        raise DailyQuotaExceededError(daily_quota)

    analyzed = await analyze_screenshot(image_bytes, provider)
    image_path = f"{data.owner_id}/{analyzed.sha256}.webp"
    thumb_path = f"{data.owner_id}/{analyzed.sha256}_thumb.webp"
    await data.storage.upload(image_path, analyzed.images.image, "image/webp")
    await data.storage.upload(thumb_path, analyzed.images.thumb, "image/webp")

    analysis = analyzed.vision.analysis
    new_card = NewCard(
        board_id=board_id,
        owner_id=data.owner_id,
        position=await data.cards.next_position(board_id),
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
