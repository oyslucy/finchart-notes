"""Minimal Telegram Bot API client. The bot token is part of every URL, so errors and
logs must never include request URLs."""

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

API_BASE = "https://api.telegram.org"
# httpx logs full request URLs (which contain the token) at INFO; keep it quiet.
logging.getLogger("httpx").setLevel(logging.WARNING)


class TelegramApiError(RuntimeError):
    def __init__(self, method: str, status: int, description: str = "") -> None:
        super().__init__(f"telegram {method} failed ({status}) {description}".strip())
        self.method = method
        self.status = status


@dataclass(frozen=True)
class TelegramFile:
    file_path: str
    file_size: int | None


class TelegramClient(Protocol):
    async def send_message(self, chat_id: int, text: str) -> int: ...
    async def edit_message_text(self, chat_id: int, message_id: int, text: str) -> None: ...
    async def get_file(self, file_id: str) -> TelegramFile: ...
    async def download_file(self, file_path: str, max_bytes: int) -> bytes: ...


class HttpTelegramClient:
    def __init__(self, token: str, http: httpx.AsyncClient | None = None) -> None:
        self._token = token
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(30, read=60))

    async def call(self, method: str, **params: Any) -> Any:
        try:
            response = await self._http.post(f"{API_BASE}/bot{self._token}/{method}", json=params)
        except httpx.HTTPError as exc:
            raise TelegramApiError(method, 0, type(exc).__name__) from None
        body = (
            response.json()
            if response.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        if response.status_code != 200 or not body.get("ok"):
            raise TelegramApiError(method, response.status_code, str(body.get("description", "")))
        return body["result"]

    async def send_message(self, chat_id: int, text: str) -> int:
        result = await self.call(
            "sendMessage", chat_id=chat_id, text=text, link_preview_options={"is_disabled": True}
        )
        return int(result["message_id"])

    async def edit_message_text(self, chat_id: int, message_id: int, text: str) -> None:
        await self.call(
            "editMessageText",
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            link_preview_options={"is_disabled": True},
        )

    async def get_file(self, file_id: str) -> TelegramFile:
        result = await self.call("getFile", file_id=file_id)
        return TelegramFile(file_path=result["file_path"], file_size=result.get("file_size"))

    async def download_file(self, file_path: str, max_bytes: int) -> bytes:
        url = f"{API_BASE}/file/bot{self._token}/{file_path}"
        chunks: list[bytes] = []
        size = 0
        try:
            async with self._http.stream("GET", url) as response:
                if response.status_code != 200:
                    raise TelegramApiError("downloadFile", response.status_code)
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        # Stop reading early; the caller reports "too large".
                        return b"".join(chunks) + chunk
                    chunks.append(chunk)
        except httpx.HTTPError as exc:
            raise TelegramApiError("downloadFile", 0, type(exc).__name__) from None
        return b"".join(chunks)

    async def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            params["offset"] = offset
        result: list[dict[str, Any]] = await self.call("getUpdates", **params)
        return result

    async def aclose(self) -> None:
        await self._http.aclose()
