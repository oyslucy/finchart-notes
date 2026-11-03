from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import jwt
from fastapi.concurrency import run_in_threadpool


class TokenError(Exception):
    pass


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    email: str
    token: str


class SupabaseJwksVerifier:
    """Verifies Supabase access tokens signed with the project's asymmetric keys."""

    def __init__(self, supabase_url: str) -> None:
        self._issuer = f"{supabase_url.rstrip('/')}/auth/v1"
        self._jwks: jwt.PyJWKClient | None = None

    def _client(self) -> jwt.PyJWKClient:
        if self._jwks is None:
            if not self._issuer.startswith("https://"):
                raise TokenError("SUPABASE_URL is not configured")
            self._jwks = jwt.PyJWKClient(f"{self._issuer}/.well-known/jwks.json", cache_keys=True)
        return self._jwks

    async def verify(self, token: str) -> dict[str, Any]:
        jwks = self._client()
        try:
            # The JWKS fetch is blocking and cached, so it runs off the event loop.
            key = await run_in_threadpool(jwks.get_signing_key_from_jwt, token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
                issuer=self._issuer,
            )
        except jwt.PyJWTError as exc:
            raise TokenError(str(exc)) from exc
        return claims


def user_from_claims(claims: dict[str, Any], token: str) -> AuthUser:
    try:
        return AuthUser(
            id=UUID(str(claims["sub"])), email=str(claims["email"]).lower(), token=token
        )
    except (KeyError, ValueError) as exc:
        raise TokenError("token is missing sub or email") from exc
