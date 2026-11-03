"""In-memory stand-ins for Supabase that mimic RLS by filtering on the caller's id."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import jwt

from finchart_api.domain.models import Board, Card, CardPatch, NewCard
from finchart_api.domain.ports import DuplicateCardError, InvalidOrderError, UserData
from finchart_api.http.auth import AuthUser, TokenError

TEST_SECRET = "test-secret-at-least-32-bytes-long!!"


def make_token(user_id: UUID, email: str) -> str:
    claims = {"sub": str(user_id), "email": email, "aud": "authenticated"}
    return jwt.encode(claims, TEST_SECRET, algorithm="HS256")


class HmacVerifier:
    async def verify(self, token: str) -> dict[str, Any]:
        try:
            claims: dict[str, Any] = jwt.decode(
                token, TEST_SECRET, algorithms=["HS256"], audience="authenticated"
            )
        except jwt.PyJWTError as exc:
            raise TokenError(str(exc)) from exc
        return claims


class Store:
    def __init__(self) -> None:
        self.boards: dict[UUID, Board] = {}
        self.cards: dict[UUID, Card] = {}
        self.objects: dict[str, bytes] = {}


class FakeBoards:
    def __init__(self, store: Store, owner: UUID) -> None:
        self._s, self._owner = store, owner

    async def create(self, title: str) -> Board:
        board = Board(id=uuid4(), owner_id=self._owner, title=title, created_at=datetime.now(UTC))
        self._s.boards[board.id] = board
        return board

    async def list_all(self) -> list[Board]:
        return [b for b in self._s.boards.values() if b.owner_id == self._owner]

    async def get(self, board_id: UUID) -> Board | None:
        board = self._s.boards.get(board_id)
        return board if board and board.owner_id == self._owner else None

    async def rename(self, board_id: UUID, title: str) -> Board | None:
        board = await self.get(board_id)
        if board is None:
            return None
        self._s.boards[board_id] = board.model_copy(update={"title": title})
        return self._s.boards[board_id]

    async def delete(self, board_id: UUID) -> bool:
        if await self.get(board_id) is None:
            return False
        del self._s.boards[board_id]
        for card_id in [c.id for c in self._s.cards.values() if c.board_id == board_id]:
            del self._s.cards[card_id]
        return True


class FakeCards:
    def __init__(self, store: Store, owner: UUID) -> None:
        self._s, self._owner = store, owner

    def _mine(self) -> list[Card]:
        return [c for c in self._s.cards.values() if c.owner_id == self._owner]

    async def find_by_sha(self, sha256: str) -> Card | None:
        return next((c for c in self._mine() if c.image_sha256 == sha256), None)

    async def next_position(self, board_id: UUID) -> int:
        positions = [c.position for c in self._mine() if c.board_id == board_id]
        return max(positions, default=-1) + 1

    async def insert(self, card: NewCard) -> Card:
        if await self.find_by_sha(card.image_sha256):
            raise DuplicateCardError(card.image_sha256)
        stored = Card(
            id=uuid4(),
            user_note=None,
            created_at=datetime.now(UTC),
            **card.model_dump(exclude={"raw_response"}),
        )
        self._s.cards[stored.id] = stored
        return stored

    async def list_for_board(self, board_id: UUID) -> list[Card]:
        return sorted((c for c in self._mine() if c.board_id == board_id), key=lambda c: c.position)

    async def get(self, card_id: UUID) -> Card | None:
        card = self._s.cards.get(card_id)
        return card if card and card.owner_id == self._owner else None

    async def update(self, card_id: UUID, patch: CardPatch) -> Card | None:
        card = await self.get(card_id)
        if card is None:
            return None
        self._s.cards[card_id] = card.model_copy(update=patch.model_dump(exclude_unset=True))
        return self._s.cards[card_id]

    async def delete(self, card_id: UUID) -> Card | None:
        card = await self.get(card_id)
        if card is not None:
            del self._s.cards[card_id]
        return card

    async def reorder(self, board_id: UUID, card_ids: Sequence[UUID]) -> None:
        current = {c.id for c in await self.list_for_board(board_id)}
        if len(card_ids) != len(current) or set(card_ids) != current:
            raise InvalidOrderError("card_ids must list every card of the board exactly once")
        for position, card_id in enumerate(card_ids):
            self._s.cards[card_id] = self._s.cards[card_id].model_copy(
                update={"position": position}
            )


class FakeStorage:
    def __init__(self, store: Store, owner: UUID) -> None:
        self._s, self._owner = store, owner

    def _check(self, path: str) -> None:
        if not path.startswith(f"{self._owner}/"):
            raise PermissionError(path)

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        self._check(path)
        self._s.objects[path] = data

    async def remove(self, paths: Sequence[str]) -> None:
        for path in paths:
            self._check(path)
            self._s.objects.pop(path, None)

    async def signed_urls(self, paths: Sequence[str], expires_in: int) -> dict[str, str]:
        return {p: f"https://signed.test/{p}?ttl={expires_in}" for p in paths}


def fake_user_data(store: Store) -> Any:
    def factory(user: AuthUser) -> UserData:
        return UserData(
            owner_id=user.id,
            boards=FakeBoards(store, user.id),
            cards=FakeCards(store, user.id),
            storage=FakeStorage(store, user.id),
        )

    return factory
