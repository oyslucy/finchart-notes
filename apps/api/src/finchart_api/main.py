from fastapi import FastAPI

from finchart_api.config import Settings, get_settings
from finchart_api.http import health
from finchart_api.http.spa import SpaStaticFiles


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="finchart-notes", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.include_router(health.router, prefix="/api")

    # Mounted last so /api routes take precedence over the SPA catch-all.
    if settings.web_dist_dir and settings.web_dist_dir.is_dir():
        app.mount("/", SpaStaticFiles(settings.web_dist_dir), name="web")

    return app
