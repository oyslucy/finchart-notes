from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from finchart_api.config import Settings
from finchart_api.domain.ports import UserData
from finchart_api.http.ratelimit import RateLimiter
from finchart_api.infra.accounts import Account, Accounts
from finchart_api.infra.sqlite import Database, sqlite_user_data
from finchart_api.llm.base import VisionProvider

SESSION_COOKIE = "finchart_session"


@dataclass
class Services:
    settings: Settings
    db: Database
    accounts: Accounts
    provider: VisionProvider
    upload_limiter: RateLimiter
    login_limiter: RateLimiter


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDep = Annotated[Services, Depends(get_services)]


async def get_current_account(request: Request, services: ServicesDep) -> Account:
    token = request.cookies.get(SESSION_COOKIE)
    account = await services.accounts.account_for_session(token) if token else None
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    if account.username not in services.settings.allowed_username_set:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account not allowed")
    return account


CurrentAccount = Annotated[Account, Depends(get_current_account)]


def get_user_data(services: ServicesDep, account: CurrentAccount) -> UserData:
    return sqlite_user_data(services.db, account.id)


UserDataDep = Annotated[UserData, Depends(get_user_data)]
