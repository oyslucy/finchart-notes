import hashlib
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from finchart_api.infra.sqlite import Database

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
SESSION_TTL = timedelta(days=30)

_hasher = PasswordHasher()
# Verifying against a real hash for unknown users keeps login timing uniform.
_DUMMY_HASH = _hasher.hash("timing-equalizer")


class AccountError(ValueError):
    pass


class UsernameTakenError(AccountError):
    pass


@dataclass(frozen=True)
class Account:
    id: UUID
    username: str


def normalize_username(raw: str) -> str:
    return raw.strip().lower()


def validate_credentials(username: str, password: str) -> None:
    if not USERNAME_RE.fullmatch(username):
        raise AccountError("username must be 3-20 chars of a-z, 0-9, _")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise AccountError(f"password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} chars")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Accounts:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, username: str, password: str) -> Account:
        validate_credentials(username, password)
        account = Account(id=uuid4(), username=username)
        password_hash = _hasher.hash(password)

        def op(conn: sqlite3.Connection) -> None:
            try:
                conn.execute(
                    "insert into users (id, username, password_hash, created_at)"
                    " values (?, ?, ?, ?)",
                    (str(account.id), username, password_hash, datetime.now(UTC).isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise UsernameTakenError(username) from exc

        await self._db.run(op)
        return account

    async def authenticate(self, username: str, password: str) -> Account | None:
        def op(conn: sqlite3.Connection) -> sqlite3.Row | None:
            row: sqlite3.Row | None = conn.execute(
                "select id, username, password_hash from users where username = ?", (username,)
            ).fetchone()
            return row

        row = await self._db.run(op)
        try:
            _hasher.verify(row["password_hash"] if row else _DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            return None
        return Account(id=UUID(row["id"]), username=row["username"]) if row else None

    async def start_session(self, account: Account) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)

        def op(conn: sqlite3.Connection) -> None:
            conn.execute("delete from sessions where expires_at < ?", (now.isoformat(),))
            conn.execute(
                "insert into sessions (token_hash, user_id, created_at, expires_at)"
                " values (?, ?, ?, ?)",
                (
                    _token_hash(token),
                    str(account.id),
                    now.isoformat(),
                    (now + SESSION_TTL).isoformat(),
                ),
            )

        await self._db.run(op)
        return token

    async def account_for_session(self, token: str) -> Account | None:
        def op(conn: sqlite3.Connection) -> sqlite3.Row | None:
            row: sqlite3.Row | None = conn.execute(
                """select u.id, u.username from sessions s join users u on u.id = s.user_id
                   where s.token_hash = ? and s.expires_at > ?""",
                (_token_hash(token), datetime.now(UTC).isoformat()),
            ).fetchone()
            return row

        row = await self._db.run(op)
        return Account(id=UUID(row["id"]), username=row["username"]) if row else None

    async def end_session(self, token: str) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute("delete from sessions where token_hash = ?", (_token_hash(token),))

        await self._db.run(op)
