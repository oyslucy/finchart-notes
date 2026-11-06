import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from finchart_api.domain.cards import (
    BoardNotFoundError,
    CardNotFoundError,
    DailyQuotaExceededError,
    create_card,
    daily_usage,
    delete_card,
    reanalyze_card,
)
from finchart_api.domain.models import Card, CardPatch
from finchart_api.domain.ports import InvalidOrderError, UserData
from finchart_api.domain.uploads import (
    UnsupportedImageError,
    UploadTooLargeError,
    check_declared_mime,
    validate_image_upload,
)
from finchart_api.http.deps import CurrentAccount, ServicesDep, UserDataDep
from finchart_api.http.schemas import (
    CardCreateOut,
    CardOut,
    MoveIn,
    OrderIn,
    QuotaOut,
    RecentCardOut,
)
from finchart_api.llm.base import VisionProviderError

router = APIRouter(tags=["cards"])
logger = logging.getLogger("uvicorn.error")


def _with_urls(data: UserData, cards: list[Card]) -> list[CardOut]:
    return [CardOut.from_card(c, data.storage.url) for c in cards]


async def _read_image(upload: UploadFile, max_bytes: int) -> bytes:
    try:
        check_declared_mime(upload.content_type)
        data = await upload.read(max_bytes + 1)
        validate_image_upload(data, max_bytes)
    except UploadTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "image too large") from exc
    except UnsupportedImageError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "only png, jpeg, webp") from exc
    return data


def _check_rate(services: ServicesDep, account: CurrentAccount) -> None:
    if not services.upload_limiter.allow(str(account.id)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many uploads, retry shortly")


def _quota_exceeded() -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS, "daily_quota", headers={"X-Limit": "daily"}
    )


def _analysis_failed() -> HTTPException:
    return HTTPException(status.HTTP_502_BAD_GATEWAY, "analysis failed, retry later")


@router.get("/quota")
async def get_quota(services: ServicesDep, data: UserDataDep) -> QuotaOut:
    usage = await daily_usage(data, services.settings.daily_analyses_per_user)
    return QuotaOut(
        limit=usage.limit, used=usage.used, remaining=usage.remaining, resets_at=usage.resets_at
    )


@router.post("/boards/{board_id}/cards", status_code=status.HTTP_201_CREATED)
async def upload_card(
    board_id: UUID,
    image: Annotated[UploadFile, File()],
    account: CurrentAccount,
    services: ServicesDep,
    data: UserDataDep,
    response: Response,
) -> CardCreateOut:
    _check_rate(services, account)
    image_bytes = await _read_image(image, services.settings.max_upload_bytes)
    try:
        result = await create_card(
            data,
            services.provider,
            board_id,
            image_bytes,
            daily_quota=services.settings.daily_analyses_per_user,
        )
    except BoardNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "board not found") from exc
    except DailyQuotaExceededError as exc:
        raise _quota_exceeded() from exc
    except VisionProviderError as exc:
        logger.warning("analysis failed for board %s: %r (cause: %r)", board_id, exc, exc.__cause__)
        raise _analysis_failed() from exc
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    [card] = _with_urls(data, [result.card])
    return CardCreateOut(card=card, duplicate=result.duplicate)


RECENT_LIMIT = 200


@router.get("/cards")
async def list_recent_cards(data: UserDataDep, q: str = "") -> list[RecentCardOut]:
    """Recent cards across boards; with `q`, a keyword search over text and board titles."""
    titles = {b.id: b.title for b in await data.boards.list_all()}
    query = q.strip()[:100]
    cards = (
        await data.cards.search(query, RECENT_LIMIT)
        if query
        else await data.cards.list_recent(RECENT_LIMIT)
    )
    return [
        RecentCardOut(**out.model_dump(), board_title=titles.get(card.board_id, ""))
        for card, out in zip(cards, _with_urls(data, cards), strict=True)
    ]


@router.get("/boards/{board_id}/cards")
async def list_cards(board_id: UUID, data: UserDataDep) -> list[CardOut]:
    if await data.boards.get(board_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "board not found")
    return _with_urls(data, await data.cards.list_for_board(board_id))


@router.put("/boards/{board_id}/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_cards(board_id: UUID, body: OrderIn, data: UserDataDep) -> Response:
    if await data.boards.get(board_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "board not found")
    try:
        await data.cards.reorder(board_id, body.card_ids)
    except InvalidOrderError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/cards/{card_id}")
async def update_card(card_id: UUID, body: CardPatch, data: UserDataDep) -> CardOut:
    card = await data.cards.update(card_id, body)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card not found")
    [out] = _with_urls(data, [card])
    return out


@router.post("/cards/{card_id}/move")
async def move_card(card_id: UUID, body: MoveIn, data: UserDataDep) -> CardOut:
    card = await data.cards.move(card_id, body.board_id)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card or board not found")
    [out] = _with_urls(data, [card])
    return out


@router.post("/cards/{card_id}/reanalyze")
async def reanalyze(
    card_id: UUID, account: CurrentAccount, services: ServicesDep, data: UserDataDep
) -> CardOut:
    _check_rate(services, account)
    try:
        card = await reanalyze_card(
            data, services.provider, card_id, services.settings.daily_analyses_per_user
        )
    except CardNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card not found") from exc
    except DailyQuotaExceededError as exc:
        raise _quota_exceeded() from exc
    except VisionProviderError as exc:
        logger.warning("reanalysis failed for card %s: %r (cause: %r)", card_id, exc, exc.__cause__)
        raise _analysis_failed() from exc
    [out] = _with_urls(data, [card])
    return out


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_card(card_id: UUID, data: UserDataDep) -> Response:
    if not await delete_card(data, card_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
