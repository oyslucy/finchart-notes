from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SpaStaticFiles(StaticFiles):
    """Serves the web build and falls back to index.html for client-side routes."""

    def __init__(self, directory: Path) -> None:
        super().__init__(directory=directory, html=True)

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)
