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

from finchart_api.domain.analysis import ChartAnalysis
from finchart_api.domain.articles import (
    Article,
    ArticleData,
    ArticleTranslation,
    DuplicateArticleError,
    FailureCode,
)
from finchart_api.domain.models import Board, Card, CardPatch, NewCard
from finchart_api.domain.ports import DuplicateCardError, InvalidOrderError, UserData

DB_FILENAME = "finchart.db"
IMAGES_DIRNAME = "images"
# Each entry upgrades the schema by one version; never edit an entry once released.
_MIGRATIONS: list[str] = [
    "alter table cards add column pinned_at text",
    """create table telegram_links (
         user_id           text primary key references users(id) on delete cascade,
         telegram_user_id  integer not null unique,
         chat_id           integer not null,
         telegram_username text,
         default_board_id  text references boards(id) on delete set null,
         created_at        text not null
       )""",
    """create table telegram_link_tokens (
         token_hash  text primary key,
         user_id     text not null references users(id) on delete cascade,
         created_at  text not null,
         expires_at  text not null,
         used_at     text
       )""",
    # Telegram retries deliveries; remembering update_ids makes the webhook idempotent.
    """create table telegram_updates (
         update_id    integer primary key,
         received_at  text not null
       )""",
    """create table articles (
         id          text primary key,
         owner_id    text not null references users(id) on delete cascade,
         filename    text not null,
         pdf_path    text not null,
         pdf_sha256  text not null,
         page_count  integer not null,
         status      text not null check (status in ('pending', 'done', 'failed')),
         error       text,
         language    text,
         title       text,
         title_ko    text,
         source      text,
         published   text,
         summary     text not null default '[]',
         paragraphs  text not null default '[]',
         model       text,
         created_at  text not null,
         unique (owner_id, pdf_sha256)
       )""",
    "create index articles_owner_created_idx on articles (owner_id, created_at desc)",
    # One row per translation attempt; kept after deletion so the daily quota holds.
    """create table translation_log (
         owner_id    text not null references users(id) on delete cascade,
         created_at  text not null
       )""",
    "create index translation_log_owner_idx on translation_log (owner_id, created_at)",
]
SCHEMA_VERSION = 1 + len(_MIGRATIONS)
# Pinned cards first (most recently pinned on top), then the user's order.
_BOARD_ORDER = "(pinned_at is null), pinned_at desc, position"
_RECENT_ORDER = "(pinned_at is null), pinned_at desc, created_at desc"

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
            version = conn.execute("pragma user_version").fetchone()[0] or 1
            for statement in _MIGRATIONS[version - 1 :]:
                conn.execute(statement)
            conn.execute(f"pragma user_version = {SCHEMA_VERSION}")
            # Translations run in-process; any still pending died with the previous process.
            conn.execute(
                "update articles set status = 'failed', error = 'interrupted'"
                " where status = 'pending'"
            )

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
                f"select * from cards where owner_id = ? order by {_RECENT_ORDER} limit ?",
                (self._owner, limit),
            )
            return [_card(r) for r in rows]

        result: list[Card] = await self._db.run(op)
        return result

    async def search(self, query: str, limit: int) -> list[Card]:
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        columns = ["c.title", "c.interpretation", "c.takeaways", "c.caveats", "c.period"]
        columns += ["coalesce(c.user_note, '')", "b.title"]
        where = " or ".join(f"{col} like ? escape '\\'" for col in columns)

        def op(conn: sqlite3.Connection) -> list[Card]:
            rows = conn.execute(
                f"""select c.* from cards c join boards b on b.id = c.board_id
                    where c.owner_id = ? and ({where})
                    order by (c.pinned_at is null), c.pinned_at desc, c.created_at desc
                    limit ?""",
                (self._owner, *[pattern] * len(columns), limit),
            )
            return [_card(r) for r in rows]

        result: list[Card] = await self._db.run(op)
        return result

    async def get(self, card_id: UUID) -> Card | None:
        return await self._one(
            "select * from cards where id = ? and owner_id = ?", (str(card_id), self._owner)
        )

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
            if conn.execute(
                "select 1 from cards where owner_id = ? and image_sha256 = ?",
                (self._owner, card.image_sha256),
            ).fetchone():
                raise DuplicateCardError(card.image_sha256)
            # Make room so the new card lands exactly at card.position (0 = front).
            conn.execute(
                "update cards set position = position + 1"
                " where board_id = ? and owner_id = ? and position >= ?",
                (str(card.board_id), self._owner, card.position),
            )
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
                f"select * from cards where board_id = ? and owner_id = ? order by {_BOARD_ORDER}",
                (str(board_id), self._owner),
            )
            return [_card(r) for r in rows]

        result: list[Card] = await self._db.run(op)
        return result

    async def update(self, card_id: UUID, patch: CardPatch) -> Card | None:
        fields = patch.model_dump(exclude_unset=True)
        if "pinned" in fields:
            fields["pinned_at"] = _now() if fields.pop("pinned") else None
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

    async def move(self, card_id: UUID, board_id: UUID) -> Card | None:
        """Moves a card to the front of another board owned by the same user."""

        def op(conn: sqlite3.Connection) -> Card | None:
            owns_board = conn.execute(
                "select 1 from boards where id = ? and owner_id = ?", (str(board_id), self._owner)
            ).fetchone()
            card = conn.execute(
                "select board_id from cards where id = ? and owner_id = ?",
                (str(card_id), self._owner),
            ).fetchone()
            if not owns_board or not card:
                return None
            if card["board_id"] != str(board_id):
                conn.execute(
                    "update cards set position = position + 1 where board_id = ? and owner_id = ?",
                    (str(board_id), self._owner),
                )
                conn.execute(
                    "update cards set board_id = ?, position = 0 where id = ? and owner_id = ?",
                    (str(board_id), str(card_id), self._owner),
                )
            row = conn.execute("select * from cards where id = ?", (str(card_id),)).fetchone()
            return _card(row)

        result: Card | None = await self._db.run(op)
        return result

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

    async def replace_analysis(
        self, card_id: UUID, analysis: ChartAnalysis, model: str, raw: dict[str, object]
    ) -> Card | None:
        """Overwrites the model's text (not the user's note) and logs the analysis for the quota."""

        def op(conn: sqlite3.Connection) -> Card | None:
            row = conn.execute(
                """update cards set title = ?, chart_type = ?, period = ?, takeaways = ?,
                     interpretation = ?, caveats = ?, model = ?, raw_response = ?
                   where id = ? and owner_id = ? returning *""",
                (
                    analysis.title,
                    analysis.chart_type,
                    analysis.period,
                    json.dumps(analysis.takeaways, ensure_ascii=False),
                    analysis.interpretation,
                    json.dumps(analysis.caveats, ensure_ascii=False),
                    model,
                    json.dumps(raw, ensure_ascii=False),
                    str(card_id),
                    self._owner,
                ),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "insert into analysis_log (owner_id, created_at) values (?, ?)",
                (self._owner, _now()),
            )
            return _card(row)

        result: Card | None = await self._db.run(op)
        return result

    async def analyses_since(self, since: datetime) -> int:
        def op(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "select count(*) from analysis_log where owner_id = ? and created_at >= ?",
                (self._owner, since.isoformat()),
            ).fetchone()
            return int(row[0])

        result: int = await self._db.run(op)
        return result


def _article(row: sqlite3.Row) -> Article:
    data = dict(row)
    data["summary"] = json.loads(data["summary"])
    data["paragraphs"] = json.loads(data["paragraphs"])
    return Article.model_validate(data)


class SqliteArticles:
    def __init__(self, db: Database, owner: UUID) -> None:
        self._db, self._owner = db, str(owner)

    async def _one(self, sql: str, params: tuple[Any, ...]) -> Article | None:
        def op(conn: sqlite3.Connection) -> Article | None:
            row = conn.execute(sql, params).fetchone()
            return _article(row) if row else None

        result: Article | None = await self._db.run(op)
        return result

    async def insert_pending(
        self, filename: str, pdf_path: str, sha256: str, page_count: int
    ) -> Article:
        def op(conn: sqlite3.Connection) -> Article:
            now = _now()
            try:
                row = conn.execute(
                    """insert into articles (id, owner_id, filename, pdf_path, pdf_sha256,
                         page_count, status, created_at)
                       values (?, ?, ?, ?, ?, ?, 'pending', ?) returning *""",
                    (str(uuid4()), self._owner, filename, pdf_path, sha256, page_count, now),
                ).fetchone()
            except sqlite3.IntegrityError as exc:
                raise DuplicateArticleError(sha256) from exc
            _log_translation(conn, self._owner, now)
            return _article(row)

        result: Article = await self._db.run(op)
        return result

    async def find_by_sha(self, sha256: str) -> Article | None:
        return await self._one(
            "select * from articles where owner_id = ? and pdf_sha256 = ?", (self._owner, sha256)
        )

    async def get(self, article_id: UUID) -> Article | None:
        return await self._one(
            "select * from articles where id = ? and owner_id = ?", (str(article_id), self._owner)
        )

    async def list(self, query: str, limit: int) -> list[Article]:
        like = f"%{query}%"

        def op(conn: sqlite3.Connection) -> list[Article]:
            rows = conn.execute(
                """select * from articles where owner_id = ?
                     and (? = '' or title like ? or title_ko like ? or source like ?
                          or filename like ? or summary like ? or paragraphs like ?)
                   order by created_at desc limit ?""",
                (self._owner, query, like, like, like, like, like, like, limit),
            )
            return [_article(r) for r in rows]

        result: list[Article] = await self._db.run(op)
        return result

    async def restart(self, article_id: UUID) -> Article | None:
        def op(conn: sqlite3.Connection) -> Article | None:
            row = conn.execute(
                """update articles set status = 'pending', error = null
                   where id = ? and owner_id = ? and status = 'failed' returning *""",
                (str(article_id), self._owner),
            ).fetchone()
            if row is None:
                return None
            _log_translation(conn, self._owner, _now())
            return _article(row)

        result: Article | None = await self._db.run(op)
        return result

    async def complete(
        self, article_id: UUID, translation: ArticleTranslation, model: str
    ) -> Article | None:
        t = translation
        return await self._one(
            """update articles set status = 'done', error = null, language = ?, title = ?,
                 title_ko = ?, source = ?, published = ?, summary = ?, paragraphs = ?, model = ?
               where id = ? and owner_id = ? returning *""",
            (
                t.language,
                t.title,
                t.title_ko,
                t.source,
                t.published,
                json.dumps(t.summary, ensure_ascii=False),
                json.dumps([p.model_dump() for p in t.paragraphs], ensure_ascii=False),
                model,
                str(article_id),
                self._owner,
            ),
        )

    async def fail(self, article_id: UUID, code: FailureCode) -> Article | None:
        return await self._one(
            "update articles set status = 'failed', error = ? where id = ? and owner_id = ?"
            " returning *",
            (code, str(article_id), self._owner),
        )

    async def delete(self, article_id: UUID) -> Article | None:
        return await self._one(
            "delete from articles where id = ? and owner_id = ? returning *",
            (str(article_id), self._owner),
        )

    async def translations_since(self, since: datetime) -> int:
        def op(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "select count(*) from translation_log where owner_id = ? and created_at >= ?",
                (self._owner, since.isoformat()),
            ).fetchone()
            return int(row[0])

        result: int = await self._db.run(op)
        return result


def _log_translation(conn: sqlite3.Connection, owner: str, at: str) -> None:
    conn.execute("insert into translation_log (owner_id, created_at) values (?, ?)", (owner, at))


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

    async def read(self, path: str) -> bytes | None:
        file = self.file_for(path)
        return None if file is None else await run_in_threadpool(file.read_bytes)

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


def sqlite_article_data(db: Database, owner: UUID) -> ArticleData:
    return ArticleData(
        owner_id=owner,
        articles=SqliteArticles(db, owner),
        files=FileStorage(db.images_dir, owner),
    )
