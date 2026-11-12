"""Telegram bot (application layer). Images go through the same create_card use case as the web."""

import base64
import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from finchart_api.domain.articles import Article, Translator, submit_article, translate_article
from finchart_api.domain.cards import BoardNotFoundError, DailyQuotaExceededError, create_card
from finchart_api.domain.models import Board
from finchart_api.domain.ports import UserData
from finchart_api.domain.uploads import (
    ALLOWED_MIME,
    TooManyPagesError,
    UnsupportedImageError,
    UnsupportedPdfError,
    UploadTooLargeError,
    validate_image_upload,
    validate_pdf_upload,
)
from finchart_api.http.ratelimit import RateLimiter
from finchart_api.infra.sqlite import Database, sqlite_article_data, sqlite_user_data
from finchart_api.infra.telegram_api import Keyboard, TelegramApiError, TelegramClient
from finchart_api.infra.telegram_store import LinkResult, TelegramLink, TelegramStore
from finchart_api.llm.base import VisionProvider, VisionProviderError

log = logging.getLogger("finchart.telegram")

INBOX_TITLE = "Inbox"
MAX_BOARD_BUTTONS = 8
BOARD_LINE = "보드: "
MOVE_HINT = "다른 보드에 저장하려면 아래에서 고르세요."
FILE_TIP = "화질 유지를 위해 사진 대신 파일로 보내세요."
PDF_MIME = frozenset({"application/pdf", "application/x-pdf"})
TRANSLATE_FAILED = {
    "too_long": "기사가 너무 길어 번역하지 못했습니다. 페이지를 나눠 보내 주세요.",
    "unreadable": "PDF를 읽지 못했습니다. 텍스트가 있는 PDF인지 확인해 주세요.",
    "failed": "번역에 실패했습니다. 잠시 후 웹의 뉴스 탭에서 다시 시도해 주세요.",
    "interrupted": "번역이 중단되었습니다. 웹의 뉴스 탭에서 다시 시도해 주세요.",
}
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
class IncomingPdf:
    file_id: str
    file_size: int | None
    filename: str


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
    # News PDFs; translator is None while the API key is not configured.
    translator: Translator | None = None
    daily_translations: int = 10
    max_pdf_bytes: int = 20 * 1024 * 1024
    max_pdf_pages: int = 30

    # --- entry point -----------------------------------------------------------------

    async def process_update(self, update: dict[str, Any]) -> None:
        """Handles one update. Safe to call again with the same update (Telegram retries)."""
        callback = update.get("callback_query")
        if isinstance(callback, dict):
            if await self.store.claim_update(int(update["update_id"])):
                try:
                    await self._callback(callback)
                except TelegramApiError as exc:
                    log.warning("telegram callback failed: %s", exc)
            return
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
        elif pdf := _incoming_pdf(message):
            await self._translate(link, pdf, chat_id)
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
            "• 뉴스 PDF → 원문과 한국어 번역으로 정리 (웹의 뉴스 탭)\n"
            "• /board → 보드 목록, /board 보드이름 → 기본 보드 변경\n"
            "• /unlink → 연결 해제"
        )

    # --- boards ------------------------------------------------------------------------

    async def _board_command(self, link: TelegramLink, name: str, chat_id: int) -> None:
        data = sqlite_user_data(self.db, link.user_id)
        if not name:
            boards = await data.boards.list_all()
            text, keyboard = _default_board_menu(boards, link.default_board_id)
            await self.client.send_message(chat_id, text, keyboard)
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
        reply, keyboard = await self._run_analysis(link, image, caption)
        if image.from_photo:
            reply += f"\n\n팁: {FILE_TIP}"
        await self.client.edit_message_text(chat_id, pending, reply, keyboard)

    async def _run_analysis(
        self, link: TelegramLink, image: IncomingImage, caption: str
    ) -> tuple[str, Keyboard | None]:
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
            return self._too_large(), None
        except UnsupportedImageError:
            return "PNG, JPEG, WebP 이미지만 분석할 수 있습니다.", None
        except DailyQuotaExceededError:
            return "오늘 분석할 수 있는 장수를 모두 썼습니다. 내일 다시 보내 주세요.", None
        except VisionProviderError:
            return "분석 요청이 몰려 실패했습니다. 잠시 후 다시 보내 주세요.", None
        except (TelegramApiError, BoardNotFoundError) as exc:
            log.warning("telegram analysis failed: %s", exc)
            return "이미지를 처리하지 못했습니다. 잠시 후 다시 보내 주세요.", None

        card = result.card
        # A duplicate may live on another board; report where it actually is.
        current = await data.boards.get(card.board_id) or board
        lines = [card.title, *[f"• {t}" for t in card.takeaways[:3]]]
        if result.duplicate:
            lines.insert(0, "이미 올린 이미지라 기존 분석을 불러왔습니다.\n")
        lines += ["", f"{BOARD_LINE}{current.title}", self.card_url(card.board_id, card.id)]
        keyboard = _move_keyboard(card.id, await data.boards.list_all(), current.id)
        if keyboard:
            lines.append(f"\n{MOVE_HINT}")
        return "\n".join(lines), keyboard or None

    # --- news PDFs ----------------------------------------------------------------------

    async def _translate(self, link: TelegramLink, pdf: IncomingPdf, chat_id: int) -> None:
        if self.translator is None:
            await self.client.send_message(chat_id, "뉴스 번역 기능이 아직 꺼져 있습니다.")
            return
        if not self.upload_limiter.allow(str(link.user_id)):
            await self.client.send_message(
                chat_id, "업로드가 너무 잦습니다. 1분 뒤 다시 보내 주세요."
            )
            return
        if pdf.file_size and pdf.file_size > self.max_pdf_bytes:
            await self.client.send_message(chat_id, self._pdf_too_large())
            return
        pending = await self.client.send_message(chat_id, "기사를 번역하고 있습니다… (1~2분)")
        reply = await self._run_translation(link, pdf, self.translator)
        await self.client.edit_message_text(chat_id, pending, reply)

    async def _run_translation(
        self, link: TelegramLink, pdf: IncomingPdf, translator: Translator
    ) -> str:
        data = sqlite_article_data(self.db, link.user_id)
        try:
            file = await self.client.get_file(pdf.file_id)
            content = await self.client.download_file(file.file_path, self.max_pdf_bytes)
            pages = validate_pdf_upload(content, self.max_pdf_bytes, self.max_pdf_pages)
            submission = await submit_article(
                data, content, pdf.filename, pages, self.daily_translations
            )
        except UploadTooLargeError:
            return self._pdf_too_large()
        except UnsupportedPdfError:
            return "PDF를 열 수 없습니다. 암호가 걸려 있지 않은 PDF로 보내 주세요."
        except TooManyPagesError as exc:
            return f"{exc.pages}쪽짜리 PDF입니다. {exc.limit}쪽 이하로 보내 주세요."
        except DailyQuotaExceededError:
            return "오늘 번역할 수 있는 횟수를 모두 썼습니다. 내일 다시 보내 주세요."
        except TelegramApiError as exc:
            log.warning("telegram pdf download failed: %s", exc)
            return "파일을 받지 못했습니다. 잠시 후 다시 보내 주세요."

        article: Article | None = submission.article
        if not submission.duplicate:
            article = await translate_article(data, translator, submission.article.id)
        if article is None:
            return "기사를 찾을 수 없습니다."
        if article.status == "failed":
            return TRANSLATE_FAILED[article.error or "failed"]
        if article.status == "pending":
            return f"이미 번역 중인 기사입니다.\n{self.article_url(article.id)}"
        lines = [article.title_ko or article.title or article.filename]
        lines += [f"• {s}" for s in article.summary]
        if submission.duplicate:
            lines.insert(0, "이미 번역한 기사라 기존 결과를 불러왔습니다.\n")
        lines += ["", f"원문과 번역 보기: {self.article_url(article.id)}"]
        return "\n".join(lines)

    def article_url(self, article_id: UUID) -> str:
        return f"{self.public_base_url}/news/{article_id}"

    def _pdf_too_large(self) -> str:
        return f"PDF가 너무 큽니다. {self.max_pdf_bytes // (1024 * 1024)}MB 이하로 보내 주세요."

    # --- inline buttons --------------------------------------------------------------

    async def _callback(self, callback: dict[str, Any]) -> None:
        callback_id = str(callback["id"])
        link = await self.store.link_for_telegram(int(callback["from"]["id"]))
        message = callback.get("message") or {}
        if link is None or not message:
            await self.client.answer_callback_query(callback_id, "웹 설정에서 먼저 연결해주세요.")
            return
        chat_id, message_id = int(message["chat"]["id"]), int(message["message_id"])
        action, *ids = str(callback.get("data", "")).split(":")
        try:
            uuids = [_decode_id(i) for i in ids]
        except ValueError:
            uuids = []
        data = sqlite_user_data(self.db, link.user_id)

        if action == "m" and len(uuids) == 2:
            await self._move_from_button(data, uuids[0], uuids[1], message, callback_id)
        elif action == "d" and len(uuids) == 1:
            board = await data.boards.get(uuids[0])
            if board is None:
                await self.client.answer_callback_query(callback_id, "보드를 찾을 수 없습니다.")
                return
            await self.store.set_default_board(link.user_id, board.id)
            text, keyboard = _default_board_menu(await data.boards.list_all(), board.id)
            await self.client.edit_message_text(chat_id, message_id, text, keyboard)
            await self.client.answer_callback_query(callback_id, f"기본 보드: {board.title}")
        else:
            await self.client.answer_callback_query(callback_id, "알 수 없는 요청입니다.")

    async def _move_from_button(
        self,
        data: UserData,
        card_id: UUID,
        board_id: UUID,
        message: dict[str, Any],
        callback_id: str,
    ) -> None:
        card = await data.cards.move(card_id, board_id)
        board = await data.boards.get(board_id) if card else None
        if card is None or board is None:
            await self.client.answer_callback_query(callback_id, "카드나 보드를 찾을 수 없습니다.")
            return
        text = _rewrite_location(
            str(message.get("text", "")), board.title, self.card_url(board.id, card.id)
        )
        keyboard = _move_keyboard(card.id, await data.boards.list_all(), board.id)
        await self.client.edit_message_text(
            int(message["chat"]["id"]), int(message["message_id"]), text, keyboard
        )
        await self.client.answer_callback_query(callback_id, f"'{board.title}'(으)로 옮겼습니다.")

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


def _incoming_pdf(message: dict[str, Any]) -> IncomingPdf | None:
    document = message.get("document")
    if not isinstance(document, dict) or document.get("mime_type") not in PDF_MIME:
        return None
    return IncomingPdf(
        document["file_id"], document.get("file_size"), str(document.get("file_name") or "")
    )


def _incoming_image(message: dict[str, Any]) -> IncomingImage | str | None:
    """The largest photo size, or an image document. A string is an error to show."""
    photos = message.get("photo")
    if isinstance(photos, list) and photos:
        best = max(photos, key=lambda p: (p.get("file_size") or 0, p.get("width", 0)))
        return IncomingImage(best["file_id"], best.get("file_size"), from_photo=True)
    document = message.get("document")
    if isinstance(document, dict):
        if document.get("mime_type") not in ALLOWED_MIME:
            return "차트는 PNG, JPEG, WebP 이미지로, 뉴스는 PDF로 보내 주세요."
        return IncomingImage(document["file_id"], document.get("file_size"), from_photo=False)
    return None


async def _find_or_create_board(data: UserData, name: str) -> Board:
    title = name.strip()[:200] or INBOX_TITLE
    for board in await data.boards.list_all():
        if board.title.casefold() == title.casefold():
            return board
    return await data.boards.create(title)


def _encode_id(value: UUID) -> str:
    # callback_data is capped at 64 bytes, so UUIDs travel as 22-char base64.
    return base64.urlsafe_b64encode(value.bytes).decode().rstrip("=")


def _decode_id(value: str) -> UUID:
    try:
        return UUID(bytes=base64.urlsafe_b64decode(value + "=="))
    except (ValueError, TypeError) as exc:
        raise ValueError(value) from exc


def _rows(buttons: list[dict[str, str]], per_row: int = 2) -> Keyboard:
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def _move_keyboard(card_id: UUID, boards: list[Board], current: UUID) -> Keyboard:
    others = [b for b in boards if b.id != current][:MAX_BOARD_BUTTONS]
    return _rows(
        [
            {"text": b.title[:30], "callback_data": f"m:{_encode_id(card_id)}:{_encode_id(b.id)}"}
            for b in others
        ]
    )


def _default_board_menu(boards: list[Board], default: UUID | None) -> tuple[str, Keyboard]:
    if not boards:
        return "보드가 없습니다. /board 보드이름 으로 만들 수 있습니다.", []
    current = next((b.title for b in boards if b.id == default), None)
    text = (
        f"기본 보드: {current or '없음 (Inbox에 저장)'}\n"
        "아래에서 고르거나 /board 새이름 으로 새 보드를 만들 수 있습니다."
    )
    buttons = [
        {
            "text": ("✓ " if b.id == default else "") + b.title[:30],
            "callback_data": f"d:{_encode_id(b.id)}",
        }
        for b in boards[: MAX_BOARD_BUTTONS * 2]
    ]
    return text, _rows(buttons)


def _rewrite_location(text: str, board_title: str, url: str) -> str:
    """Updates the board line and card link of an earlier analysis reply after a move."""
    out = []
    for line in text.split("\n"):
        if line.startswith(BOARD_LINE):
            line = f"{BOARD_LINE}{board_title}"
        elif "/boards/" in line and "/cards/" in line:
            line = url
        out.append(line)
    return "\n".join(out)
