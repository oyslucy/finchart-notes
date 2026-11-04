from collections.abc import Sequence

from finchart_api.domain.models import Board
from finchart_api.domain.ports import BoardRepository


async def add_default_boards(boards: BoardRepository, names: Sequence[str]) -> list[Board]:
    """Creates any missing starter boards. Boards list newest first, so create in reverse
    to show them in the configured order."""
    existing = {b.title.casefold() for b in await boards.list_all()}
    created = []
    for name in reversed(names):
        if name.casefold() not in existing:
            created.append(await boards.create(name))
    return created
