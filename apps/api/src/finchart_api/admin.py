"""Operator commands.

Usage:
    python -m finchart_api.admin add-default-boards <username>
    python -m finchart_api.admin delete-user <username>
"""

import asyncio
import shutil
import sys
from uuid import UUID

from finchart_api.config import Settings, get_settings
from finchart_api.domain.boards import add_default_boards
from finchart_api.infra.sqlite import Database, SqliteBoards


def _user_id(db: Database, username: str) -> UUID:
    with db.connect() as conn:
        row = conn.execute("select id from users where username = ?", (username,)).fetchone()
    if row is None:
        raise SystemExit(f"no such user: {username}")
    return UUID(row["id"])


async def _add_default_boards(settings: Settings, username: str) -> str:
    db = Database(settings.data_dir)
    db.migrate()
    created = await add_default_boards(
        SqliteBoards(db, _user_id(db, username)), settings.default_board_names
    )
    return f"created {len(created)} board(s): {', '.join(b.title for b in created) or '-'}"


def delete_user(settings: Settings, username: str) -> str:
    """Removes the account and everything it owns. Foreign keys cascade sessions, boards,
    cards, quota rows and Telegram links; image files are removed from disk."""
    db = Database(settings.data_dir)
    db.migrate()
    user_id = _user_id(db, username)
    with db.connect() as conn:
        boards = conn.execute("select count(*) from boards where owner_id = ?", (str(user_id),))
        cards = conn.execute("select count(*) from cards where owner_id = ?", (str(user_id),))
        counts = (boards.fetchone()[0], cards.fetchone()[0])
        conn.execute("delete from users where id = ?", (str(user_id),))
    shutil.rmtree(db.images_dir / str(user_id), ignore_errors=True)
    return f"deleted {username}: {counts[0]} board(s), {counts[1]} card(s)"


def main(argv: list[str]) -> None:
    settings = get_settings()
    if len(argv) == 2 and argv[0] == "add-default-boards":
        print(asyncio.run(_add_default_boards(settings, argv[1])))
    elif len(argv) == 2 and argv[0] == "delete-user":
        print(delete_user(settings, argv[1]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
