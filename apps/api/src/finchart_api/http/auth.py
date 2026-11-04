from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from finchart_api.http.deps import SESSION_COOKIE, CurrentAccount, ServicesDep
from finchart_api.infra.accounts import (
    SESSION_TTL,
    Account,
    AccountError,
    UsernameTakenError,
    normalize_username,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str
    password: str


class Me(BaseModel):
    username: str


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _client_key(request: Request, username: str) -> str:
    return f"{_client_ip(request)}:{username}"


async def _sign_in(response: Response, services: ServicesDep, account: Account) -> Me:
    token = await services.accounts.start_session(account)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=services.settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    return Me(username=account.username)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    body: Credentials, request: Request, response: Response, services: ServicesDep
) -> Me:
    username = normalize_username(body.username)
    if not services.settings.is_username_allowed(username):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "username not allowed")
    if not services.signup_limiter.allow(_client_ip(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many signups")
    try:
        account = await services.accounts.create(username, body.password)
    except UsernameTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "username taken") from exc
    except AccountError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await _sign_in(response, services, account)


@router.post("/login")
async def login(
    body: Credentials, request: Request, response: Response, services: ServicesDep
) -> Me:
    username = normalize_username(body.username)
    if not services.login_limiter.allow(_client_key(request, username)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many attempts")
    account = await services.accounts.authenticate(username, body.password)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not services.settings.is_username_allowed(account.username):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account not allowed")
    return await _sign_in(response, services, account)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, services: ServicesDep) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await services.accounts.end_session(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me")
async def me(account: CurrentAccount) -> Me:
    return Me(username=account.username)
