import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from finchart_api.config import Settings, get_settings
from finchart_api.http import auth, boards, cards, health, images, telegram
from finchart_api.http.deps import Services
from finchart_api.http.origin import SameOriginMiddleware
from finchart_api.http.ratelimit import RateLimiter
from finchart_api.http.spa import SpaStaticFiles
from finchart_api.infra.accounts import Accounts
from finchart_api.infra.sqlite import Database
from finchart_api.infra.telegram_api import HttpTelegramClient, TelegramClient
from finchart_api.infra.telegram_store import TelegramStore
from finchart_api.llm.base import VisionProvider
from finchart_api.llm.factory import build_vision_provider
from finchart_api.telegram.bot import TelegramBot
from finchart_api.telegram.polling import run_polling


def create_app(
    settings: Settings | None = None,
    *,
    provider: VisionProvider | None = None,
    telegram_client: TelegramClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    db = Database(settings.data_dir)
    db.migrate()
    provider = provider or build_vision_provider(settings)
    upload_limiter = RateLimiter(settings.rate_limit_per_minute)
    telegram_store = TelegramStore(db)

    http_client: HttpTelegramClient | None = None
    bot: TelegramBot | None = None
    if settings.telegram_enabled:
        if telegram_client is None:
            http_client = HttpTelegramClient(settings.telegram_bot_token.get_secret_value())
            telegram_client = http_client
        bot = TelegramBot(
            db=db,
            store=telegram_store,
            client=telegram_client,
            provider=provider,
            upload_limiter=upload_limiter,  # shared with the web, so limits are per user
            max_upload_bytes=settings.max_upload_bytes,
            daily_quota=settings.daily_analyses_per_user,
            public_base_url=settings.public_base_url.rstrip("/"),
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        poller = None
        if bot and http_client and settings.telegram_mode == "polling":
            poller = asyncio.create_task(run_polling(bot, http_client))
        yield
        if poller:
            poller.cancel()
            with suppress(asyncio.CancelledError):
                await poller
        if http_client:
            await http_client.aclose()

    app = FastAPI(
        title="finchart-notes",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(SameOriginMiddleware)
    app.state.services = Services(
        settings=settings,
        db=db,
        accounts=Accounts(db),
        provider=provider,
        upload_limiter=upload_limiter,
        login_limiter=RateLimiter(settings.login_attempts_per_minute),
        signup_limiter=RateLimiter(settings.signups_per_ip_per_hour, window_s=3600),
        telegram_store=telegram_store,
        telegram=bot,
    )
    routers = (health.router, auth.router, boards.router, cards.router, images.router)
    for router in (*routers, telegram.router):
        app.include_router(router, prefix="/api")

    # Mounted last so /api routes take precedence over the SPA catch-all.
    if settings.web_dist_dir and settings.web_dist_dir.is_dir():
        app.mount("/", SpaStaticFiles(settings.web_dist_dir), name="web")

    return app
