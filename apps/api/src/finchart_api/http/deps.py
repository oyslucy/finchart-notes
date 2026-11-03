from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from finchart_api.config import Settings
from finchart_api.domain.ports import UserData
from finchart_api.http.auth import AuthUser, TokenError, TokenVerifier, user_from_claims
from finchart_api.http.ratelimit import RateLimiter
from finchart_api.llm.base import VisionProvider

UserDataFactory = Callable[[AuthUser], UserData]


@dataclass
class Services:
    settings: Settings
    verifier: TokenVerifier
    user_data: UserDataFactory
    provider: VisionProvider
    rate_limiter: RateLimiter


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


_bearer = HTTPBearer(auto_error=False)
ServicesDep = Annotated[Services, Depends(get_services)]


async def get_current_user(
    services: ServicesDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = await services.verifier.verify(credentials.credentials)
        user = user_from_claims(claims, credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc
    if user.email not in services.settings.allowed_email_set:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "email not allowed")
    return user


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def get_user_data(services: ServicesDep, user: CurrentUser) -> UserData:
    return services.user_data(user)


UserDataDep = Annotated[UserData, Depends(get_user_data)]
