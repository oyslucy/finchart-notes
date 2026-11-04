"""Operator commands. Usage: python -m finchart_api.admin add-default-boards <username>"""

import asyncio
import sys
from uuid import UUID

from finchart_api.config import get_settings
from finchart_api.domain.boards import add_default_boards
from finchart_api.infra.sqlite import Database, SqliteBoards


async def _add_default_boards(username: str) -> None:
    settings = get_settings()
    db = Database(settings.data_dir)
    db.migrate()
    with db.connect() as conn:
        row = conn.execute("select id from users where username = ?", (username,)).fetchone()
    if row is None:
        raise SystemExit(f"no such user: {username}")
    created = await add_default_boards(
        SqliteBoards(db, UUID(row["id"])), settings.default_board_names
    )
    print(f"created {len(created)} board(s): {', '.join(b.title for b in created) or '-'}")


def main(argv: list[str]) -> None:
    if len(argv) == 2 and argv[0] == "add-default-boards":
        asyncio.run(_add_default_boards(argv[1]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
