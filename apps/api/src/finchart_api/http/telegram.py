import hmac
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

from finchart_api.http.deps import CurrentAccount, ServicesDep

router = APIRouter(prefix="/telegram", tags=["telegram"])


class LinkTokenOut(BaseModel):
    url: str
    expires_at: datetime


class TelegramStatus(BaseModel):
    enabled: bool
    linked: bool
    telegram_username: str | None = None
    bot_username: str | None = None


def _require_enabled(services: ServicesDep) -> None:
    if services.telegram is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "telegram is not configured")


@router.post("/link-token")
async def create_link_token(account: CurrentAccount, services: ServicesDep) -> LinkTokenOut:
    _require_enabled(services)
    token, expires = await services.telegram_store.issue_link_token(account.id)
    bot = services.settings.telegram_bot_username
    return LinkTokenOut(url=f"https://t.me/{bot}?start={token}", expires_at=expires)


@router.get("/status")
async def telegram_status(account: CurrentAccount, services: ServicesDep) -> TelegramStatus:
    if services.telegram is None:
        return TelegramStatus(enabled=False, linked=False)
    link = await services.telegram_store.link_for_user(account.id)
    return TelegramStatus(
        enabled=True,
        linked=link is not None,
        telegram_username=link.telegram_username if link else None,
        bot_username=services.settings.telegram_bot_username,
    )


@router.delete("/link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink(account: CurrentAccount, services: ServicesDep) -> Response:
    await services.telegram_store.unlink_user(account.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/webhook")
async def webhook(
    request: Request,
    background: BackgroundTasks,
    services: ServicesDep,
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict[str, bool]:
    expected = services.settings.telegram_webhook_secret.get_secret_value()
    if not expected or not secret or not hmac.compare_digest(secret, expected):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bad secret")
    if services.telegram is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "telegram is not configured")
    update: Any = await request.json()
    if isinstance(update, dict) and "update_id" in update:
        # Answer immediately; Telegram retries slow webhooks, and analysis takes seconds.
        background.add_task(services.telegram.process_update, update)
    return {"ok": True}
