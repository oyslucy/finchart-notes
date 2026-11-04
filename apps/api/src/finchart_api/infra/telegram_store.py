import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID

from finchart_api.infra.sqlite import Database

LINK_TOKEN_TTL = timedelta(minutes=10)
UPDATE_RETENTION = timedelta(days=7)


class LinkResult(Enum):
    LINKED = "linked"
    INVALID = "invalid"
    EXPIRED = "expired"
    USED = "used"
    TELEGRAM_TAKEN = "telegram_taken"


@dataclass(frozen=True)
class TelegramLink:
    user_id: UUID
    username: str
    telegram_user_id: int
    chat_id: int
    telegram_username: str | None
    default_board_id: UUID | None


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _link(row: sqlite3.Row) -> TelegramLink:
    return TelegramLink(
        user_id=UUID(row["user_id"]),
        username=row["username"],
        telegram_user_id=row["telegram_user_id"],
        chat_id=row["chat_id"],
        telegram_username=row["telegram_username"],
        default_board_id=UUID(row["default_board_id"]) if row["default_board_id"] else None,
    )


_LINK_SELECT = """select l.*, u.username from telegram_links l join users u on u.id = l.user_id"""


class TelegramStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def issue_link_token(self, user_id: UUID) -> tuple[str, datetime]:
        """Returns a one-time token; only its SHA-256 is stored."""
        token = secrets.token_urlsafe(24)
        now = _now()
        expires = now + LINK_TOKEN_TTL

        def op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "delete from telegram_link_tokens where expires_at < ?", (now.isoformat(),)
            )
            conn.execute(
                "insert into telegram_link_tokens (token_hash, user_id, created_at, expires_at)"
                " values (?, ?, ?, ?)",
                (_hash(token), str(user_id), now.isoformat(), expires.isoformat()),
            )

        await self._db.run(op)
        return token, expires

    async def consume_link_token(
        self, token: str, telegram_user_id: int, chat_id: int, telegram_username: str | None
    ) -> LinkResult:
        now = _now().isoformat()

        def op(conn: sqlite3.Connection) -> LinkResult:
            row = conn.execute(
                "select user_id, expires_at, used_at from telegram_link_tokens"
                " where token_hash = ?",
                (_hash(token),),
            ).fetchone()
            if row is None:
                return LinkResult.INVALID
            if row["used_at"]:
                return LinkResult.USED
            if row["expires_at"] < now:
                return LinkResult.EXPIRED
            owner = conn.execute(
                "select user_id from telegram_links where telegram_user_id = ?", (telegram_user_id,)
            ).fetchone()
            if owner and owner["user_id"] != row["user_id"]:
                return LinkResult.TELEGRAM_TAKEN
            conn.execute(
                "update telegram_link_tokens set used_at = ? where token_hash = ?",
                (now, _hash(token)),
            )
            conn.execute(
                """insert into telegram_links
                     (user_id, telegram_user_id, chat_id, telegram_username, created_at)
                   values (?, ?, ?, ?, ?)
                   on conflict(user_id) do update set
                     telegram_user_id = excluded.telegram_user_id,
                     chat_id = excluded.chat_id,
                     telegram_username = excluded.telegram_username""",
                (row["user_id"], telegram_user_id, chat_id, telegram_username, now),
            )
            return LinkResult.LINKED

        result: LinkResult = await self._db.run(op)
        return result

    async def link_for_telegram(self, telegram_user_id: int) -> TelegramLink | None:
        def op(conn: sqlite3.Connection) -> TelegramLink | None:
            row = conn.execute(
                f"{_LINK_SELECT} where l.telegram_user_id = ?", (telegram_user_id,)
            ).fetchone()
            return _link(row) if row else None

        result: TelegramLink | None = await self._db.run(op)
        return result

    async def link_for_user(self, user_id: UUID) -> TelegramLink | None:
        def op(conn: sqlite3.Connection) -> TelegramLink | None:
            row = conn.execute(f"{_LINK_SELECT} where l.user_id = ?", (str(user_id),)).fetchone()
            return _link(row) if row else None

        result: TelegramLink | None = await self._db.run(op)
        return result

    async def unlink_user(self, user_id: UUID) -> bool:
        def op(conn: sqlite3.Connection) -> bool:
            cur = conn.execute("delete from telegram_links where user_id = ?", (str(user_id),))
            return cur.rowcount > 0

        result: bool = await self._db.run(op)
        return result

    async def set_default_board(self, user_id: UUID, board_id: UUID) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "update telegram_links set default_board_id = ? where user_id = ?",
                (str(board_id), str(user_id)),
            )

        await self._db.run(op)

    async def claim_update(self, update_id: int) -> bool:
        """True the first time an update_id is seen; False for Telegram's retries."""
        now = _now()

        def op(conn: sqlite3.Connection) -> bool:
            conn.execute(
                "delete from telegram_updates where received_at < ?",
                ((now - UPDATE_RETENTION).isoformat(),),
            )
            cur = conn.execute(
                "insert or ignore into telegram_updates (update_id, received_at) values (?, ?)",
                (update_id, now.isoformat()),
            )
            return cur.rowcount == 1

        result: bool = await self._db.run(op)
        return result
