"""Telegram bot (application layer). Images go through the same create_card use case as the web."""

import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from finchart_api.domain.cards import BoardNotFoundError, DailyQuotaExceededError, create_card
from finchart_api.domain.models import Board
from finchart_api.domain.ports import UserData
from finchart_api.domain.uploads import (
    ALLOWED_MIME,
    UnsupportedImageError,
    UploadTooLargeError,
    validate_image_upload,
)
from finchart_api.http.ratelimit import RateLimiter
from finchart_api.infra.sqlite import Database, sqlite_user_data
from finchart_api.infra.telegram_api import TelegramApiError, TelegramClient
from finchart_api.infra.telegram_store import LinkResult, TelegramLink, TelegramStore
from finchart_api.llm.base import VisionProvider, VisionProviderError

log = logging.getLogger("finchart.telegram")

INBOX_TITLE = "Inbox"
FILE_TIP = "화질 유지를 위해 사진 대신 파일로 보내세요."
_HASHTAG = re.compile(r"#([^\s#]+)")

LINK_MESSAGES = {
    LinkResult.INVALID: "연결 링크가 올바르지 않습니다. 웹 설정에서 새 링크를 만들어 주세요.",
    LinkResult.EXPIRED: "연결 링크가 만료되었습니다(10분). 웹 설정에서 새 링크를 만들어 주세요.",
    LinkResult.USED: "이미 사용한 연결 링크입니다. 웹 설정에서 새 링크를 만들어 주세요.",
    LinkResult.TELEGRAM_TAKEN: (
        "이 텔레그램 계정은 이미 다른 finchart 계정에 연결되어 있습니다. "
        "그 계정의 웹 설정에서 먼저 연결을 해제해 주세요."
    ),
}


@dataclass(frozen=True)
class IncomingImage:
    file_id: str
    file_size: int | None
    from_photo: bool


@dataclass
class TelegramBot:
    db: Database
    store: TelegramStore
    client: TelegramClient
    provider: VisionProvider
    upload_limiter: RateLimiter
    max_upload_bytes: int
    daily_quota: int
    public_base_url: str

    # --- entry point -----------------------------------------------------------------

    async def process_update(self, update: dict[str, Any]) -> None:
        """Handles one update. Safe to call again with the same update (Telegram retries)."""
        message = update.get("message")
        if not isinstance(message, dict) or message.get("chat", {}).get("type") != "private":
            return
        if not await self.store.claim_update(int(update["update_id"])):
            return
        sender = message.get("from") or {}
        chat_id = int(message["chat"]["id"])
        try:
            await self._dispatch(message, int(sender["id"]), sender.get("username"), chat_id)
        except TelegramApiError as exc:
            log.warning("telegram reply failed: %s", exc)

    async def _dispatch(
        self, message: dict[str, Any], telegram_user_id: int, username: str | None, chat_id: int
    ) -> None:
        command, argument = _command(message.get("text") or "")
        if command == "/start" and argument:
            await self._link(argument, telegram_user_id, username, chat_id)
            return

        link = await self.store.link_for_telegram(telegram_user_id)
        if link is None:
            await self.client.send_message(chat_id, self._not_linked())
            return

        if command == "/unlink":
            await self.store.unlink_user(link.user_id)
            await self.client.send_message(
                chat_id, "연결을 해제했습니다. 다시 쓰려면 웹 설정에서 연결해 주세요."
            )
        elif command == "/board":
            await self._board_command(link, argument, chat_id)
        else:
            image = _incoming_image(message)
            if isinstance(image, IncomingImage):
                await self._analyze(link, image, message.get("caption") or "", chat_id)
            elif isinstance(image, str):
                await self.client.send_message(chat_id, image)
            else:
                await self.client.send_message(chat_id, self._help(link))

    # --- linking -----------------------------------------------------------------------

    async def _link(
        self, token: str, telegram_user_id: int, username: str | None, chat_id: int
    ) -> None:
        result = await self.store.consume_link_token(token, telegram_user_id, chat_id, username)
        if result is not LinkResult.LINKED:
            await self.client.send_message(chat_id, LINK_MESSAGES[result])
            return
        link = await self.store.link_for_telegram(telegram_user_id)
        name = link.username if link else ""
        await self.client.send_message(
            chat_id,
            f"연결되었습니다, {name}님.\n차트 스크린샷을 보내면 분석해서 카드로 저장합니다.\n"
            f"{FILE_TIP}\n\n"
            "캡션에 #보드이름 을 쓰면 그 보드에 저장하고, /board 로 기본 보드를 바꿀 수 있습니다.",
        )

    def _not_linked(self) -> str:
        return (
            "아직 계정이 연결되지 않았습니다. 웹 설정에서 먼저 연결해주세요.\n"
            f"{self.public_base_url}/settings"
        )

    def _help(self, link: TelegramLink) -> str:
        return (
            f"{link.username}님 계정에 연결되어 있습니다.\n\n"
            f"차트 스크린샷을 보내면 분석해서 카드로 저장합니다. {FILE_TIP}\n"
            "• 캡션에 #보드이름 → 그 보드에 저장\n"
            "• /board → 보드 목록, /board 보드이름 → 기본 보드 변경\n"
            "• /unlink → 연결 해제"
        )

    # --- boards ------------------------------------------------------------------------

    async def _board_command(self, link: TelegramLink, name: str, chat_id: int) -> None:
        data = sqlite_user_data(self.db, link.user_id)
        if not name:
            boards = await data.boards.list_all()
            lines = [
                f"{'• ' if b.id == link.default_board_id else '  '}{b.title}" for b in boards
            ] or ["(보드가 없습니다)"]
            await self.client.send_message(
                chat_id,
                "보드 목록 (• 기본 보드)\n"
                + "\n".join(lines)
                + "\n\n/board 보드이름 으로 바꿉니다.",
            )
            return
        board = await _find_or_create_board(data, name)
        await self.store.set_default_board(link.user_id, board.id)
        await self.client.send_message(chat_id, f"이제 기본 보드는 '{board.title}'입니다.")

    async def _target_board(self, link: TelegramLink, data: UserData, caption: str) -> Board:
        tag = _HASHTAG.search(caption)
        if tag:
            return await _find_or_create_board(data, tag.group(1).replace("_", " "))
        if link.default_board_id:
            board = await data.boards.get(link.default_board_id)
            if board:
                return board
        inbox = await _find_or_create_board(data, INBOX_TITLE)
        await self.store.set_default_board(link.user_id, inbox.id)
        return inbox

    # --- analysis ----------------------------------------------------------------------

    async def _analyze(
        self, link: TelegramLink, image: IncomingImage, caption: str, chat_id: int
    ) -> None:
        if not self.upload_limiter.allow(str(link.user_id)):
            await self.client.send_message(
                chat_id, "업로드가 너무 잦습니다. 1분 뒤 다시 보내 주세요."
            )
            return
        if image.file_size and image.file_size > self.max_upload_bytes:
            await self.client.send_message(chat_id, self._too_large())
            return

        pending = await self.client.send_message(chat_id, "분석 중…")
        reply = await self._run_analysis(link, image, caption)
        if image.from_photo:
            reply += f"\n\n팁: {FILE_TIP}"
        await self.client.edit_message_text(chat_id, pending, reply)

    async def _run_analysis(self, link: TelegramLink, image: IncomingImage, caption: str) -> str:
        data = sqlite_user_data(self.db, link.user_id)
        try:
            file = await self.client.get_file(image.file_id)
            content = await self.client.download_file(file.file_path, self.max_upload_bytes)
            validate_image_upload(content, self.max_upload_bytes)
            board = await self._target_board(link, data, caption)
            result = await create_card(
                data, self.provider, board.id, content, daily_quota=self.daily_quota
            )
        except UploadTooLargeError:
            return self._too_large()
        except UnsupportedImageError:
            return "PNG, JPEG, WebP 이미지만 분석할 수 있습니다."
        except DailyQuotaExceededError:
            return "오늘 분석할 수 있는 장수를 모두 썼습니다. 내일 다시 보내 주세요."
        except VisionProviderError:
            return "분석 요청이 몰려 실패했습니다. 잠시 후 다시 보내 주세요."
        except (TelegramApiError, BoardNotFoundError) as exc:
            log.warning("telegram analysis failed: %s", exc)
            return "이미지를 처리하지 못했습니다. 잠시 후 다시 보내 주세요."

        card = result.card
        lines = [card.title, *[f"• {t}" for t in card.takeaways[:3]]]
        if result.duplicate:
            lines.insert(0, "이미 올린 이미지라 기존 분석을 불러왔습니다.\n")
        lines += ["", f"보드: {board.title}", self.card_url(card.board_id, card.id)]
        return "\n".join(lines)

    def card_url(self, board_id: UUID, card_id: UUID) -> str:
        return f"{self.public_base_url}/boards/{board_id}/cards/{card_id}"

    def _too_large(self) -> str:
        return (
            f"이미지가 너무 큽니다. {self.max_upload_bytes // (1024 * 1024)}MB 이하로 보내 주세요."
        )


def _command(text: str) -> tuple[str, str]:
    if not text.startswith("/"):
        return "", ""
    head, _, rest = text.strip().partition(" ")
    return head.split("@", 1)[0].lower(), rest.strip()


def _incoming_image(message: dict[str, Any]) -> IncomingImage | str | None:
    """The largest photo size, or an image document. A string is an error to show."""
    photos = message.get("photo")
    if isinstance(photos, list) and photos:
        best = max(photos, key=lambda p: (p.get("file_size") or 0, p.get("width", 0)))
        return IncomingImage(best["file_id"], best.get("file_size"), from_photo=True)
    document = message.get("document")
    if isinstance(document, dict):
        if document.get("mime_type") not in ALLOWED_MIME:
            return "PNG, JPEG, WebP 이미지 파일만 분석할 수 있습니다."
        return IncomingImage(document["file_id"], document.get("file_size"), from_photo=False)
    return None


async def _find_or_create_board(data: UserData, name: str) -> Board:
    title = name.strip()[:200] or INBOX_TITLE
    for board in await data.boards.list_all():
        if board.title.casefold() == title.casefold():
            return board
    return await data.boards.create(title)
