from fastapi import FastAPI

from finchart_api.config import Settings, get_settings
from finchart_api.http import auth, boards, cards, health, images
from finchart_api.http.deps import Services
from finchart_api.http.origin import SameOriginMiddleware
from finchart_api.http.ratelimit import RateLimiter
from finchart_api.http.spa import SpaStaticFiles
from finchart_api.infra.accounts import Accounts
from finchart_api.infra.sqlite import Database
from finchart_api.llm.base import VisionProvider
from finchart_api.llm.factory import build_vision_provider


def create_app(
    settings: Settings | None = None, *, provider: VisionProvider | None = None
) -> FastAPI:
    settings = settings or get_settings()
    db = Database(settings.data_dir)
    db.migrate()

    app = FastAPI(title="finchart-notes", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(SameOriginMiddleware)
    app.state.services = Services(
        settings=settings,
        db=db,
        accounts=Accounts(db),
        provider=provider or build_vision_provider(settings),
        upload_limiter=RateLimiter(settings.rate_limit_per_minute),
        login_limiter=RateLimiter(settings.login_attempts_per_minute),
    )
    for router in (health.router, auth.router, boards.router, cards.router, images.router):
        app.include_router(router, prefix="/api")

    # Mounted last so /api routes take precedence over the SPA catch-all.
    if settings.web_dist_dir and settings.web_dist_dir.is_dir():
        app.mount("/", SpaStaticFiles(settings.web_dist_dir), name="web")

    return app
