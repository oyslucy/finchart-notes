from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from finchart_api.domain.cards import BoardNotFoundError, create_card, delete_card
from finchart_api.domain.models import Card, CardPatch
from finchart_api.domain.ports import InvalidOrderError, UserData
from finchart_api.http.deps import CurrentUser, ServicesDep, UserDataDep
from finchart_api.http.schemas import CardCreateOut, CardOut, OrderIn
from finchart_api.imaging import InvalidImageError, detect_mime
from finchart_api.llm.base import VisionProviderError

router = APIRouter(tags=["cards"])

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
SIGNED_URL_TTL_S = 3600


async def _with_urls(data: UserData, cards: list[Card]) -> list[CardOut]:
    paths = [p for c in cards for p in (c.image_path, c.thumb_path)]
    urls = await data.storage.signed_urls(paths, SIGNED_URL_TTL_S)
    return [CardOut.from_card(c, urls) for c in cards]


async def _read_image(upload: UploadFile, max_bytes: int) -> bytes:
    if upload.content_type not in ALLOWED_MIME:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "only png, jpeg, webp")
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "image too large")
    try:
        if detect_mime(data) not in ALLOWED_MIME:
            raise InvalidImageError("unsupported")
    except InvalidImageError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "not a valid image") from exc
    return data


@router.post("/boards/{board_id}/cards", status_code=status.HTTP_201_CREATED)
async def upload_card(
    board_id: UUID,
    image: Annotated[UploadFile, File()],
    user: CurrentUser,
    services: ServicesDep,
    data: UserDataDep,
    response: Response,
) -> CardCreateOut:
    if not services.rate_limiter.allow(str(user.id)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many uploads, retry shortly")
    image_bytes = await _read_image(image, services.settings.max_upload_bytes)
    try:
        result = await create_card(data, services.provider, board_id, image_bytes)
    except BoardNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "board not found") from exc
    except VisionProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "analysis failed, retry later") from exc
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    [card] = await _with_urls(data, [result.card])
    return CardCreateOut(card=card, duplicate=result.duplicate)


@router.get("/boards/{board_id}/cards")
async def list_cards(board_id: UUID, data: UserDataDep) -> list[CardOut]:
    if await data.boards.get(board_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "board not found")
    return await _with_urls(data, await data.cards.list_for_board(board_id))


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
    [out] = await _with_urls(data, [card])
    return out


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_card(card_id: UUID, data: UserDataDep) -> Response:
    if not await delete_card(data, card_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
