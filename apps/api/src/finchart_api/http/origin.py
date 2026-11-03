from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_SAFE = {"GET", "HEAD", "OPTIONS"}


class SameOriginMiddleware(BaseHTTPMiddleware):
    """Rejects cross-site state-changing requests; complements SameSite=Lax cookies."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        origin = request.headers.get("origin")
        # Proxies (Caddy, the Vite dev server) may rewrite Host but report the original here.
        hosts = {request.headers.get("host"), request.headers.get("x-forwarded-host")}
        cross_site = origin is not None and urlsplit(origin).netloc not in hosts
        if request.method not in _SAFE and cross_site:
            return JSONResponse({"detail": "cross-origin request blocked"}, status_code=403)
        return await call_next(request)
