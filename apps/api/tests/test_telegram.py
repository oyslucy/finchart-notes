import io
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from finchart_api.config import Settings
from finchart_api.infra.telegram_api import TelegramFile
from finchart_api.main import create_app

from .conftest import FakeProvider, make_png

SECRET = "webhook-secret"
PASSWORD = "correct-horse-1"


class FakeTelegram:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.edits: list[tuple[int, int, str]] = []
        self.files: dict[str, bytes] = {}

    async def send_message(self, chat_id: int, text: str) -> int:
        self.sent.append((chat_id, text))
        return len(self.sent)

    async def edit_message_text(self, chat_id: int, message_id: int, text: str) -> None:
        self.edits.append((chat_id, message_id, text))

    async def get_file(self, file_id: str) -> TelegramFile:
        return TelegramFile(file_path=file_id, file_size=len(self.files[file_id]))

    async def download_file(self, file_path: str, max_bytes: int) -> bytes:
        return self.files[file_path][: max_bytes + 1]

    def texts(self) -> list[str]:
        return [t for _, t in self.sent] + [t for *_, t in self.edits]


class Harness:
    def __init__(self, data_dir: Path, **overrides: Any) -> None:
        options: dict[str, Any] = {
            "telegram_bot_token": SecretStr("123:token"),
            "telegram_bot_username": "TestBot",
            "telegram_webhook_secret": SecretStr(SECRET),
            "max_upload_bytes": 10 * 1024 * 1024,
            **overrides,
        }
        self.telegram = FakeTelegram()
        self.provider = FakeProvider()
        self.app = create_app(
            Settings(_env_file=None, data_dir=data_dir, **options),
            provider=self.provider,
            telegram_client=self.telegram,
        )
        self.bot_client = TestClient(self.app)
        self.next_update = 1

    def user(self, username: str) -> TestClient:
        client = TestClient(self.app)
        r = client.post("/api/auth/signup", json={"username": username, "password": PASSWORD})
        assert r.status_code == 201
        return client

    def link_token(self, web: TestClient) -> str:
        r = web.post("/api/telegram/link-token")
        assert r.status_code == 200
        url = urlparse(r.json()["url"])
        assert url.netloc == "t.me" and url.path == "/TestBot"
        token: str = parse_qs(url.query)["start"][0]
        return token

    def send(self, update_id: int | None = None, secret: str | None = SECRET, **message: Any):  # type: ignore[no-untyped-def]
        if update_id is None:
            update_id = self.next_update
            self.next_update += 1
        tg_user = message.pop("tg_user", 111)
        chat_type = message.pop("chat_type", "private")
        body = {
            "update_id": update_id,
            "message": {
                "message_id": update_id,
                "from": {"id": tg_user, "username": f"tg{tg_user}"},
                "chat": {"id": tg_user, "type": chat_type},
                **message,
            },
        }
        headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret else {}
        return self.bot_client.post("/api/telegram/webhook", json=body, headers=headers)

    def linked_user(self, username: str = "alice", tg_user: int = 111) -> TestClient:
        web = self.user(username)
        self.send(text=f"/start {self.link_token(web)}", tg_user=tg_user)
        return web

    def document(self, data: bytes, file_id: str = "doc1", **extra: Any):  # type: ignore[no-untyped-def]
        self.telegram.files[file_id] = data
        doc = {"file_id": file_id, "file_size": len(data), "mime_type": "image/png"}
        return self.send(document=doc, **extra)


@pytest.fixture
def h(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


# --- webhook security ---


def test_webhook_rejects_missing_or_wrong_secret(h: Harness) -> None:
    assert h.send(secret=None, text="hi").status_code == 403
    assert h.send(secret="nope", text="hi").status_code == 403
    assert h.telegram.sent == []


def test_webhook_answers_ok_for_valid_secret(h: Harness) -> None:
    r = h.send(text="hi")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_group_chats_are_ignored(h: Harness) -> None:
    h.linked_user()
    h.telegram.sent.clear()
    h.send(text="hi", chat_type="group")
    assert h.telegram.sent == []


# --- linking ---


def test_link_flow_connects_account(h: Harness) -> None:
    web = h.user("alice")
    assert web.get("/api/telegram/status").json()["linked"] is False

    h.send(text=f"/start {h.link_token(web)}")

    status = web.get("/api/telegram/status").json()
    assert status == {
        "enabled": True,
        "linked": True,
        "telegram_username": "tg111",
        "bot_username": "TestBot",
    }
    assert "연결되었습니다, alice님" in h.telegram.sent[-1][1]
    assert "파일로 보내세요" in h.telegram.sent[-1][1]


def test_link_token_is_single_use(h: Harness) -> None:
    web = h.user("alice")
    token = h.link_token(web)
    h.send(text=f"/start {token}", tg_user=111)
    h.send(text=f"/start {token}", tg_user=222)

    assert "이미 사용한 연결 링크" in h.telegram.sent[-1][1]


def test_forged_token_is_rejected(h: Harness) -> None:
    h.user("alice")
    h.send(text="/start forged-token-value")
    assert "올바르지 않습니다" in h.telegram.sent[-1][1]


def test_expired_token_is_rejected(h: Harness) -> None:
    web = h.user("alice")
    token = h.link_token(web)
    with h.app.state.services.db.connect() as conn:
        conn.execute("update telegram_link_tokens set expires_at = '2000-01-01T00:00:00+00:00'")

    h.send(text=f"/start {token}")

    assert "만료" in h.telegram.sent[-1][1]
    assert web.get("/api/telegram/status").json()["linked"] is False


def test_only_token_hash_is_stored(h: Harness) -> None:
    token = h.link_token(h.user("alice"))
    with h.app.state.services.db.connect() as conn:
        stored = [r[0] for r in conn.execute("select token_hash from telegram_link_tokens")]
    assert token not in stored and len(stored[0]) == 64


def test_telegram_account_cannot_link_to_two_users(h: Harness) -> None:
    h.linked_user("alice", tg_user=111)
    bob = h.user("bob")

    h.send(text=f"/start {h.link_token(bob)}", tg_user=111)

    assert "이미 다른 finchart 계정" in h.telegram.sent[-1][1]
    assert bob.get("/api/telegram/status").json()["linked"] is False


def test_link_token_requires_login_and_configuration(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    assert TestClient(h.app).post("/api/telegram/link-token").status_code == 401

    disabled = Harness(tmp_path / "off", telegram_bot_token=SecretStr(""))
    web = disabled.user("alice")
    assert web.post("/api/telegram/link-token").status_code == 503
    assert web.get("/api/telegram/status").json()["enabled"] is False


def test_unlink_from_web_and_bot(h: Harness) -> None:
    web = h.linked_user()
    assert web.delete("/api/telegram/link").status_code == 204
    assert web.get("/api/telegram/status").json()["linked"] is False

    h.linked_user("bob", tg_user=333)
    h.send(text="/unlink", tg_user=333)
    h.send(text="hello", tg_user=333)
    assert "먼저 연결해주세요" in h.telegram.sent[-1][1]


# --- unlinked users ---


def test_unlinked_user_gets_only_link_prompt(h: Harness) -> None:
    h.telegram.files["p1"] = make_png()
    h.send(photo=[{"file_id": "p1", "file_size": 100, "width": 10}])

    assert len(h.telegram.sent) == 1
    assert "웹 설정에서 먼저 연결해주세요" in h.telegram.sent[0][1]
    assert h.provider.calls == 0 and h.telegram.edits == []


# --- analysis ---


def test_document_is_analyzed_into_inbox(h: Harness) -> None:
    web = h.linked_user()

    h.document(make_png())

    assert h.telegram.sent[-1][1] == "분석 중…"
    reply = h.telegram.edits[-1][2]
    assert "KOSPI 일봉" in reply and "보드: Inbox" in reply
    assert "/boards/" in reply and "/cards/" in reply
    assert [b["title"] for b in web.get("/api/boards").json()] == ["Inbox"]
    assert "팁" not in reply


def test_photo_uses_largest_size_and_suggests_files(h: Harness) -> None:
    h.linked_user()
    h.telegram.files["small"] = b"tiny"
    h.telegram.files["large"] = make_png()

    h.send(
        photo=[
            {"file_id": "small", "file_size": 4, "width": 90},
            {"file_id": "large", "file_size": 9000, "width": 1280},
        ]
    )

    reply = h.telegram.edits[-1][2]
    assert "KOSPI 일봉" in reply and "파일로 보내세요" in reply


def test_duplicate_update_is_processed_once(h: Harness) -> None:
    h.linked_user()
    h.telegram.files["doc1"] = make_png()
    doc = {"file_id": "doc1", "file_size": 10, "mime_type": "image/png"}

    h.send(update_id=500, document=doc)
    h.send(update_id=500, document=doc)

    assert h.provider.calls == 1
    assert len(h.telegram.edits) == 1


def test_same_image_twice_reuses_analysis(h: Harness) -> None:
    web = h.linked_user()
    image = make_png()
    h.document(image, file_id="a")
    h.document(image, file_id="b")

    assert h.provider.calls == 1
    assert "기존 분석을 불러왔습니다" in h.telegram.edits[-1][2]
    board_id = web.get("/api/boards").json()[0]["id"]
    assert len(web.get(f"/api/boards/{board_id}/cards").json()) == 1


def test_caption_hashtag_picks_board(h: Harness) -> None:
    web = h.linked_user()
    h.document(make_png(), caption="삼성 실적 #반도체_업황")

    assert "보드: 반도체 업황" in h.telegram.edits[-1][2]
    assert [b["title"] for b in web.get("/api/boards").json()] == ["반도체 업황"]


def test_board_command_changes_default(h: Harness) -> None:
    web = h.linked_user()
    h.send(text="/board 매크로")
    h.document(make_png())

    assert "기본 보드는 '매크로'" in h.telegram.sent[-2][1]
    assert "보드: 매크로" in h.telegram.edits[-1][2]
    h.send(text="/board")
    assert "• 매크로" in h.telegram.sent[-1][1]
    assert [b["title"] for b in web.get("/api/boards").json()] == ["매크로"]


def test_non_image_document_is_rejected(h: Harness) -> None:
    h.linked_user()
    h.send(document={"file_id": "x", "file_size": 10, "mime_type": "application/pdf"})
    assert "이미지 파일만" in h.telegram.sent[-1][1]
    assert h.provider.calls == 0


def test_unsupported_bytes_are_rejected_after_download(h: Harness) -> None:
    h.linked_user()
    buf = io.BytesIO()
    Image.new("RGB", (50, 50)).save(buf, format="GIF")
    h.document(buf.getvalue())
    assert "PNG, JPEG, WebP" in h.telegram.edits[-1][2]
    assert h.provider.calls == 0


def test_oversized_file_is_rejected(tmp_path: Path) -> None:
    h = Harness(tmp_path, max_upload_bytes=1000)
    h.linked_user()
    h.document(make_png())
    assert "너무 큽니다" in h.telegram.texts()[-1]
    assert h.provider.calls == 0


def test_rate_limit_is_shared_with_web(tmp_path: Path) -> None:
    h = Harness(tmp_path, rate_limit_per_minute=1)
    web = h.linked_user()
    board_id = web.post("/api/boards", json={"title": "웹"}).json()["id"]
    web.post(
        f"/api/boards/{board_id}/cards", files={"image": ("a.png", make_png(1100), "image/png")}
    )

    h.document(make_png())

    assert "너무 잦습니다" in h.telegram.sent[-1][1]


def test_daily_quota_message(tmp_path: Path) -> None:
    h = Harness(tmp_path, daily_analyses_per_user=1)
    h.linked_user()
    h.document(make_png(1001), file_id="a")
    h.document(make_png(1002), file_id="b")
    assert "오늘 분석할 수 있는 장수" in h.telegram.edits[-1][2]
