from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from finchart_api.config import Settings, get_settings
from finchart_api.domain.ports import UserData
from finchart_api.http import boards, cards, health
from finchart_api.http.auth import AuthUser, SupabaseJwksVerifier, TokenVerifier
from finchart_api.http.deps import Services, UserDataFactory
from finchart_api.http.ratelimit import RateLimiter
from finchart_api.http.spa import SpaStaticFiles
from finchart_api.infra.supabase import supabase_user_data
from finchart_api.llm.base import VisionProvider
from finchart_api.llm.factory import build_vision_provider


def create_app(
    settings: Settings | None = None,
    *,
    verifier: TokenVerifier | None = None,
    user_data: UserDataFactory | None = None,
    provider: VisionProvider | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    http_client = httpx.AsyncClient(timeout=30)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await http_client.aclose()

    def supabase_factory(user: AuthUser) -> UserData:
        return supabase_user_data(
            http_client, settings.supabase_url, settings.supabase_anon_key, user.token, user.id
        )

    app = FastAPI(
        title="finchart-notes",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.services = Services(
        settings=settings,
        verifier=verifier or SupabaseJwksVerifier(settings.supabase_url),
        user_data=user_data or supabase_factory,
        provider=provider or build_vision_provider(settings),
        rate_limiter=RateLimiter(settings.rate_limit_per_minute),
    )
    for router in (health.router, boards.router, cards.router):
        app.include_router(router, prefix="/api")

    # Mounted last so /api routes take precedence over the SPA catch-all.
    if settings.web_dist_dir and settings.web_dist_dir.is_dir():
        app.mount("/", SpaStaticFiles(settings.web_dist_dir), name="web")

    return app
