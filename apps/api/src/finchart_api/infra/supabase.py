from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx

from finchart_api.domain.models import Board, Card, CardPatch, NewCard
from finchart_api.domain.ports import DuplicateCardError, InvalidOrderError, UserData

BUCKET = "charts"
_CARD_COLUMNS = (
    "id,board_id,owner_id,position,image_path,thumb_path,image_sha256,title,chart_type,"
    "period,takeaways,interpretation,caveats,user_note,model,created_at"
)


class SupabaseError(RuntimeError):
    pass


class _Rest:
    """PostgREST and Storage calls made with the end user's JWT so RLS applies."""

    def __init__(self, http: httpx.AsyncClient, base_url: str, anon_key: str, token: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._headers = {"apikey": anon_key, "Authorization": f"Bearer {token}"}

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        response = await self._http.request(
            method,
            f"{self._base}{path}",
            params=params,
            json=json,
            content=content,
            headers={**self._headers, **(headers or {})},
        )
        if response.status_code >= 400:
            _raise_for(response)
        return response


def _raise_for(response: httpx.Response) -> None:
    body: dict[str, Any] = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            body = parsed
    except ValueError:
        pass
    if body.get("code") == "23505":
        raise DuplicateCardError(body.get("message"))
    if body.get("code") == "22023":
        raise InvalidOrderError(body.get("message"))
    raise SupabaseError(f"{response.status_code}: {response.text[:300]}")


_RETURN_ONE = {"Prefer": "return=representation", "Accept": "application/vnd.pgrst.object+json"}


class SupabaseBoards:
    def __init__(self, rest: _Rest) -> None:
        self._rest = rest

    async def create(self, title: str) -> Board:
        r = await self._rest.request(
            "POST", "/rest/v1/boards", json={"title": title}, headers=_RETURN_ONE
        )
        return Board.model_validate(r.json())

    async def list_all(self) -> list[Board]:
        r = await self._rest.request(
            "GET", "/rest/v1/boards", params={"select": "*", "order": "created_at.desc"}
        )
        return [Board.model_validate(row) for row in r.json()]

    async def get(self, board_id: UUID) -> Board | None:
        rows = await self._select({"id": f"eq.{board_id}"})
        return rows[0] if rows else None

    async def rename(self, board_id: UUID, title: str) -> Board | None:
        r = await self._rest.request(
            "PATCH",
            "/rest/v1/boards",
            params={"id": f"eq.{board_id}"},
            json={"title": title},
            headers={"Prefer": "return=representation"},
        )
        rows = r.json()
        return Board.model_validate(rows[0]) if rows else None

    async def delete(self, board_id: UUID) -> bool:
        r = await self._rest.request(
            "DELETE",
            "/rest/v1/boards",
            params={"id": f"eq.{board_id}"},
            headers={"Prefer": "return=representation"},
        )
        return bool(r.json())

    async def _select(self, filters: dict[str, str]) -> list[Board]:
        r = await self._rest.request("GET", "/rest/v1/boards", params={"select": "*", **filters})
        return [Board.model_validate(row) for row in r.json()]


class SupabaseCards:
    def __init__(self, rest: _Rest) -> None:
        self._rest = rest

    async def find_by_sha(self, sha256: str) -> Card | None:
        rows = await self._select({"image_sha256": f"eq.{sha256}"})
        return rows[0] if rows else None

    async def next_position(self, board_id: UUID) -> int:
        r = await self._rest.request(
            "GET",
            "/rest/v1/cards",
            params={
                "select": "position",
                "board_id": f"eq.{board_id}",
                "order": "position.desc",
                "limit": "1",
            },
        )
        rows = r.json()
        return int(rows[0]["position"]) + 1 if rows else 0

    async def insert(self, card: NewCard) -> Card:
        r = await self._rest.request(
            "POST",
            "/rest/v1/cards",
            params={"select": _CARD_COLUMNS},
            json=card.model_dump(mode="json"),
            headers=_RETURN_ONE,
        )
        return Card.model_validate(r.json())

    async def list_for_board(self, board_id: UUID) -> list[Card]:
        return await self._select({"board_id": f"eq.{board_id}", "order": "position.asc"})

    async def get(self, card_id: UUID) -> Card | None:
        rows = await self._select({"id": f"eq.{card_id}"})
        return rows[0] if rows else None

    async def update(self, card_id: UUID, patch: CardPatch) -> Card | None:
        r = await self._rest.request(
            "PATCH",
            "/rest/v1/cards",
            params={"id": f"eq.{card_id}", "select": _CARD_COLUMNS},
            json=patch.model_dump(mode="json", exclude_unset=True),
            headers={"Prefer": "return=representation"},
        )
        rows = r.json()
        return Card.model_validate(rows[0]) if rows else None

    async def delete(self, card_id: UUID) -> Card | None:
        r = await self._rest.request(
            "DELETE",
            "/rest/v1/cards",
            params={"id": f"eq.{card_id}", "select": _CARD_COLUMNS},
            headers={"Prefer": "return=representation"},
        )
        rows = r.json()
        return Card.model_validate(rows[0]) if rows else None

    async def reorder(self, board_id: UUID, card_ids: Sequence[UUID]) -> None:
        await self._rest.request(
            "POST",
            "/rest/v1/rpc/reorder_cards",
            json={"p_board_id": str(board_id), "p_card_ids": [str(i) for i in card_ids]},
        )

    async def _select(self, filters: dict[str, str]) -> list[Card]:
        r = await self._rest.request(
            "GET", "/rest/v1/cards", params={"select": _CARD_COLUMNS, **filters}
        )
        return [Card.model_validate(row) for row in r.json()]


class SupabaseStorage:
    def __init__(self, rest: _Rest, base_url: str) -> None:
        self._rest = rest
        self._public_base = f"{base_url.rstrip('/')}/storage/v1"

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        await self._rest.request(
            "POST",
            f"/storage/v1/object/{BUCKET}/{path}",
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )

    async def remove(self, paths: Sequence[str]) -> None:
        await self._rest.request(
            "DELETE", f"/storage/v1/object/{BUCKET}", json={"prefixes": list(paths)}
        )

    async def signed_urls(self, paths: Sequence[str], expires_in: int) -> dict[str, str]:
        if not paths:
            return {}
        r = await self._rest.request(
            "POST",
            f"/storage/v1/object/sign/{BUCKET}",
            json={"expiresIn": expires_in, "paths": list(paths)},
        )
        return {
            item["path"]: f"{self._public_base}{item['signedURL']}"
            for item in r.json()
            if item.get("signedURL")
        }


def supabase_user_data(
    http: httpx.AsyncClient, base_url: str, anon_key: str, token: str, owner_id: UUID
) -> UserData:
    rest = _Rest(http, base_url, anon_key, token)
    return UserData(
        owner_id=owner_id,
        boards=SupabaseBoards(rest),
        cards=SupabaseCards(rest),
        storage=SupabaseStorage(rest, base_url),
    )
