"""SQLite + local files. Everything lives under DATA_DIR so one archive is a full backup."""

import json
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi.concurrency import run_in_threadpool

from finchart_api.domain.models import Board, Card, CardPatch, NewCard
from finchart_api.domain.ports import DuplicateCardError, InvalidOrderError, UserData

DB_FILENAME = "finchart.db"
IMAGES_DIRNAME = "images"
SCHEMA_VERSION = 1

_SCHEMA = """
create table if not exists users (
  id            text primary key,
  username      text not null unique,
  password_hash text not null,
  created_at    text not null
);

create table if not exists sessions (
  token_hash  text primary key,
  user_id     text not null references users(id) on delete cascade,
  created_at  text not null,
  expires_at  text not null
);
create index if not exists sessions_user_idx on sessions (user_id);

create table if not exists boards (
  id          text primary key,
  owner_id    text not null references users(id) on delete cascade,
  title       text not null check (length(title) between 1 and 200),
  created_at  text not null
);
create index if not exists boards_owner_created_idx on boards (owner_id, created_at desc);

create table if not exists cards (
  id              text primary key,
  board_id        text not null references boards(id) on delete cascade,
  owner_id        text not null references users(id) on delete cascade,
  position        integer not null check (position >= 0),
  image_path      text not null,
  thumb_path      text not null,
  image_sha256    text not null,
  title           text not null,
  chart_type      text not null,
  period          text,
  takeaways       text not null default '[]',
  interpretation  text not null,
  caveats         text not null default '[]',
  user_note       text,
  model           text not null,
  raw_response    text,
  created_at      text not null,
  unique (owner_id, image_sha256)
);
create index if not exists cards_board_position_idx on cards (board_id, position);

-- One row per completed VLM analysis; survives card deletion so daily quotas hold.
create table if not exists analysis_log (
  owner_id    text not null references users(id) on delete cascade,
  created_at  text not null
);
create index if not exists analysis_log_owner_idx on analysis_log (owner_id, created_at);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.images_dir = data_dir / IMAGES_DIRNAME
        self.path = data_dir / DB_FILENAME
        self._lock = threading.Lock()

    def migrate(self) -> None:
        self.images_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(_SCHEMA)
            conn.execute(f"pragma user_version = {SCHEMA_VERSION}")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        # One writer at a time keeps SQLite simple; the app runs a single worker anyway.
        with self._lock:
            conn = sqlite3.connect(self.path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("pragma foreign_keys = on")
            conn.execute("pragma journal_mode = wal")
            try:
                with conn:
                    yield conn
            finally:
                conn.close()

    async def run(self, fn: Any, *args: Any) -> Any:
        def call() -> Any:
            with self.connect() as conn:
                return fn(conn, *args)

        return await run_in_threadpool(call)


def _board(row: sqlite3.Row) -> Board:
    return Board.model_validate(dict(row))


def _card(row: sqlite3.Row) -> Card:
    data = dict(row)
    data["takeaways"] = json.loads(data["takeaways"])
    data["caveats"] = json.loads(data["caveats"])
    data.pop("raw_response", None)
    return Card.model_validate(data)


class SqliteBoards:
    def __init__(self, db: Database, owner: UUID) -> None:
        self._db, self._owner = db, str(owner)

    async def create(self, title: str) -> Board:
        board_id, created = str(uuid4()), _now()

        def op(conn: sqlite3.Connection) -> Board:
            conn.execute(
                "insert into boards (id, owner_id, title, created_at) values (?, ?, ?, ?)",
                (board_id, self._owner, title, created),
            )
            return Board(
                id=UUID(board_id),
                owner_id=UUID(self._owner),
                title=title,
                created_at=datetime.fromisoformat(created),
            )

        result: Board = await self._db.run(op)
        return result

    async def list_all(self) -> list[Board]:
        def op(conn: sqlite3.Connection) -> list[Board]:
            rows = conn.execute(
                "select * from boards where owner_id = ? order by created_at desc", (self._owner,)
            )
            return [_board(r) for r in rows]

        result: list[Board] = await self._db.run(op)
        return result

    async def get(self, board_id: UUID) -> Board | None:
        def op(conn: sqlite3.Connection) -> Board | None:
            row = conn.execute(
                "select * from boards where id = ? and owner_id = ?", (str(board_id), self._owner)
            ).fetchone()
            return _board(row) if row else None

        result: Board | None = await self._db.run(op)
        return result

    async def rename(self, board_id: UUID, title: str) -> Board | None:
        def op(conn: sqlite3.Connection) -> Board | None:
            row = conn.execute(
                "update boards set title = ? where id = ? and owner_id = ? returning *",
                (title, str(board_id), self._owner),
            ).fetchone()
            return _board(row) if row else None

        result: Board | None = await self._db.run(op)
        return result

    async def delete(self, board_id: UUID) -> bool:
        def op(conn: sqlite3.Connection) -> bool:
            cur = conn.execute(
                "delete from boards where id = ? and owner_id = ?", (str(board_id), self._owner)
            )
            return cur.rowcount > 0

        result: bool = await self._db.run(op)
        return result


class SqliteCards:
    def __init__(self, db: Database, owner: UUID) -> None:
        self._db, self._owner = db, str(owner)

    async def _one(self, sql: str, params: tuple[Any, ...]) -> Card | None:
        def op(conn: sqlite3.Connection) -> Card | None:
            row = conn.execute(sql, params).fetchone()
            return _card(row) if row else None

        result: Card | None = await self._db.run(op)
        return result

    async def find_by_sha(self, sha256: str) -> Card | None:
        return await self._one(
            "select * from cards where owner_id = ? and image_sha256 = ?", (self._owner, sha256)
        )

    async def list_recent(self, limit: int) -> list[Card]:
        def op(conn: sqlite3.Connection) -> list[Card]:
            rows = conn.execute(
                "select * from cards where owner_id = ? order by created_at desc limit ?",
                (self._owner, limit),
            )
            return [_card(r) for r in rows]

        result: list[Card] = await self._db.run(op)
        return result

    async def get(self, card_id: UUID) -> Card | None:
        return await self._one(
            "select * from cards where id = ? and owner_id = ?", (str(card_id), self._owner)
        )

    async def next_position(self, board_id: UUID) -> int:
        def op(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "select coalesce(max(position), -1) + 1 from cards"
                " where board_id = ? and owner_id = ?",
                (str(board_id), self._owner),
            ).fetchone()
            return int(row[0])

        result: int = await self._db.run(op)
        return result

    async def insert(self, card: NewCard) -> Card:
        card_id, created = str(uuid4()), _now()
        if str(card.owner_id) != self._owner:
            raise PermissionError("card owner mismatch")

        def op(conn: sqlite3.Connection) -> Card:
            owns_board = conn.execute(
                "select 1 from boards where id = ? and owner_id = ?",
                (str(card.board_id), self._owner),
            ).fetchone()
            if not owns_board:
                raise PermissionError("board not owned by caller")
            try:
                row = conn.execute(
                    """insert into cards (id, board_id, owner_id, position, image_path,
                         thumb_path, image_sha256, title, chart_type, period, takeaways,
                         interpretation, caveats, model, raw_response, created_at)
                       values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) returning *""",
                    (
                        card_id,
                        str(card.board_id),
                        self._owner,
                        card.position,
                        card.image_path,
                        card.thumb_path,
                        card.image_sha256,
                        card.title,
                        card.chart_type,
                        card.period,
                        json.dumps(card.takeaways, ensure_ascii=False),
                        card.interpretation,
                        json.dumps(card.caveats, ensure_ascii=False),
                        card.model,
                        json.dumps(card.raw_response, ensure_ascii=False),
                        created,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as exc:
                if "image_sha256" in str(exc):
                    raise DuplicateCardError(card.image_sha256) from exc
                raise
            conn.execute(
                "insert into analysis_log (owner_id, created_at) values (?, ?)",
                (self._owner, created),
            )
            return _card(row)

        result: Card = await self._db.run(op)
        return result

    async def list_for_board(self, board_id: UUID) -> list[Card]:
        def op(conn: sqlite3.Connection) -> list[Card]:
            rows = conn.execute(
                "select * from cards where board_id = ? and owner_id = ? order by position",
                (str(board_id), self._owner),
            )
            return [_card(r) for r in rows]

        result: list[Card] = await self._db.run(op)
        return result

    async def update(self, card_id: UUID, patch: CardPatch) -> Card | None:
        fields = patch.model_dump(exclude_unset=True)
        if not fields:
            return await self.get(card_id)
        for key in ("takeaways", "caveats"):
            if key in fields and fields[key] is not None:
                fields[key] = json.dumps(fields[key], ensure_ascii=False)
        assignments = ", ".join(f"{name} = ?" for name in fields)  # names come from CardPatch only
        return await self._one(
            f"update cards set {assignments} where id = ? and owner_id = ? returning *",
            (*fields.values(), str(card_id), self._owner),
        )

    async def delete(self, card_id: UUID) -> Card | None:
        return await self._one(
            "delete from cards where id = ? and owner_id = ? returning *",
            (str(card_id), self._owner),
        )

    async def reorder(self, board_id: UUID, card_ids: Sequence[UUID]) -> None:
        wanted = [str(i) for i in card_ids]

        def op(conn: sqlite3.Connection) -> None:
            current = {
                r[0]
                for r in conn.execute(
                    "select id from cards where board_id = ? and owner_id = ?",
                    (str(board_id), self._owner),
                )
            }
            if len(wanted) != len(current) or set(wanted) != current:
                raise InvalidOrderError("card_ids must list every card of the board exactly once")
            conn.executemany(
                "update cards set position = ? where id = ? and owner_id = ?",
                [(pos, cid, self._owner) for pos, cid in enumerate(wanted)],
            )

        await self._db.run(op)

    async def analyses_since(self, since: datetime) -> int:
        def op(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "select count(*) from analysis_log where owner_id = ? and created_at >= ?",
                (self._owner, since.isoformat()),
            ).fetchone()
            return int(row[0])

        result: int = await self._db.run(op)
        return result


class FileStorage:
    """Images under DATA_DIR/images/<owner>/...; served by the API after an owner check."""

    def __init__(self, root: Path, owner: UUID) -> None:
        self._root, self._owner = root, str(owner)

    def _resolve(self, path: str) -> Path:
        target = (self._root / path).resolve()
        owner_dir = (self._root / self._owner).resolve()
        if owner_dir not in target.parents:
            raise PermissionError(path)
        return target

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        target = self._resolve(path)

        def write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)

        await run_in_threadpool(write)

    async def remove(self, paths: Sequence[str]) -> None:
        targets = [self._resolve(p) for p in paths]

        def unlink() -> None:
            for t in targets:
                t.unlink(missing_ok=True)

        await run_in_threadpool(unlink)

    def url(self, path: str) -> str:
        return f"/api/images/{path}"

    def file_for(self, path: str) -> Path | None:
        try:
            target = self._resolve(path)
        except PermissionError:
            return None
        return target if target.is_file() else None


def sqlite_user_data(db: Database, owner: UUID) -> UserData:
    return UserData(
        owner_id=owner,
        boards=SqliteBoards(db, owner),
        cards=SqliteCards(db, owner),
        storage=FileStorage(db.images_dir, owner),
    )
