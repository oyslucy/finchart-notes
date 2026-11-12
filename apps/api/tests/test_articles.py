import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from finchart_api.config import Settings
from finchart_api.domain.articles import TranslatorError
from finchart_api.infra.sqlite import Database, SqliteArticles
from finchart_api.llm.claude_api import ClaudeTranslator
from finchart_api.main import create_app

from .conftest import FakeProvider, FakeTranslator, make_pdf, make_translation

PASSWORD = "correct-horse-1"


class News:
    def __init__(self, data_dir: Path, translator: FakeTranslator | None = None, **overrides: Any):
        options: dict[str, Any] = {"default_boards": "", **overrides}
        settings = Settings(_env_file=None, data_dir=data_dir, **options)
        self.translator = translator if translator is not None else FakeTranslator()
        self.app = create_app(settings, provider=FakeProvider(), translator=self.translator)
        self.data_dir = data_dir

    def user(self, username: str) -> TestClient:
        client = TestClient(self.app)
        r = client.post("/api/auth/signup", json={"username": username, "password": PASSWORD})
        assert r.status_code == 201, r.text
        return client


def upload(client: TestClient, data: bytes, name: str = "fed.pdf", mime: str = "application/pdf"):  # type: ignore[no-untyped-def]
    return client.post("/api/articles", files={"pdf": (name, data, mime)})


@pytest.fixture
def news(tmp_path: Path) -> News:
    return News(tmp_path)


def test_upload_translates_in_background(news: News) -> None:
    alice = news.user("alice")

    r = upload(alice, make_pdf(2))

    assert r.status_code == 202
    submitted = r.json()["article"]
    assert submitted["status"] == "pending" and submitted["page_count"] == 2
    # TestClient runs background tasks before returning, so the article is done now
    article = alice.get(f"/api/articles/{submitted['id']}").json()
    assert article["status"] == "done"
    assert article["title_ko"] == "연준, 금리 동결" and article["source"] == "Reuters"
    assert [p["original"] for p in article["paragraphs"]] == ["The Fed held rates.", "Outlook"]
    assert article["paragraphs"][1]["kind"] == "heading"


def test_same_pdf_reuses_translation(news: News) -> None:
    alice = news.user("alice")
    pdf = make_pdf()
    first = upload(alice, pdf).json()["article"]

    again = upload(alice, pdf)

    assert again.status_code == 200 and again.json()["duplicate"] is True
    assert again.json()["article"]["id"] == first["id"]
    assert news.translator.calls == 1


def test_translation_disabled_without_key(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path, default_boards="")
    app = create_app(settings, provider=FakeProvider())
    alice = TestClient(app)
    alice.post("/api/auth/signup", json={"username": "alice", "password": PASSWORD})

    r = upload(alice, make_pdf())

    assert r.status_code == 503 and r.json()["detail"] == "translation_disabled"


def test_rejects_non_pdf_and_spoofed_pdf(news: News) -> None:
    alice = news.user("alice")
    assert upload(alice, b"hello", mime="text/plain").status_code == 415
    spoofed = upload(alice, b"not really a pdf")
    assert spoofed.status_code == 415 and spoofed.json()["detail"] == "unreadable_pdf"


def test_rejects_too_many_pages(tmp_path: Path) -> None:
    news = News(tmp_path, max_pdf_pages=2)
    r = upload(news.user("alice"), make_pdf(3))
    assert r.status_code == 422 and r.json()["detail"] == "too_many_pages"


def test_daily_translation_quota(tmp_path: Path) -> None:
    news = News(tmp_path, daily_translations_per_user=1)
    alice = news.user("alice")
    assert alice.get("/api/articles/quota").json()["remaining"] == 1
    first = upload(alice, make_pdf(1)).json()["article"]["id"]
    alice.delete(f"/api/articles/{first}")

    blocked = upload(alice, make_pdf(2))

    assert blocked.status_code == 429 and blocked.json()["detail"] == "daily_quota"
    assert alice.get("/api/articles/quota").json()["remaining"] == 0
    # Chart analyses keep their own quota
    assert alice.get("/api/quota").json()["used"] == 0


def test_failure_is_recorded_and_retry_translates(news: News) -> None:
    alice = news.user("alice")
    news.translator.error = TranslatorError("too_long")
    article_id = upload(alice, make_pdf()).json()["article"]["id"]
    failed = alice.get(f"/api/articles/{article_id}").json()
    assert failed["status"] == "failed" and failed["error"] == "too_long"

    news.translator.error = None
    r = alice.post(f"/api/articles/{article_id}/retry")

    assert r.status_code == 202
    assert alice.get(f"/api/articles/{article_id}").json()["status"] == "done"
    assert alice.get("/api/articles/quota").json()["used"] == 2


def test_retry_of_finished_article_does_nothing(news: News) -> None:
    alice = news.user("alice")
    article_id = upload(alice, make_pdf()).json()["article"]["id"]

    alice.post(f"/api/articles/{article_id}/retry")

    assert news.translator.calls == 1


def test_other_users_cannot_read_article_or_pdf(news: News) -> None:
    alice, bob = news.user("alice"), news.user("bob")
    article_id = upload(alice, make_pdf()).json()["article"]["id"]

    assert bob.get(f"/api/articles/{article_id}").status_code == 404
    assert bob.get(f"/api/articles/{article_id}/pdf").status_code == 404
    assert bob.delete(f"/api/articles/{article_id}").status_code == 404
    assert bob.get("/api/articles").json() == []


def test_pdf_is_served_inline(news: News) -> None:
    alice = news.user("alice")
    pdf = make_pdf()
    article = upload(alice, pdf, name="fed minutes.pdf").json()["article"]

    r = alice.get(article["pdf_url"])

    assert r.status_code == 200 and r.content == pdf
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")


def test_delete_removes_pdf_file(news: News) -> None:
    alice = news.user("alice")
    article_id = upload(alice, make_pdf()).json()["article"]["id"]
    assert list(news.data_dir.rglob("*.pdf"))

    assert alice.delete(f"/api/articles/{article_id}").status_code == 204

    assert not list(news.data_dir.rglob("*.pdf"))
    assert alice.get(f"/api/articles/{article_id}").status_code == 404


def test_list_is_newest_first_and_searchable(news: News) -> None:
    alice = news.user("alice")
    upload(alice, make_pdf(1), name="first.pdf")
    news.translator.translation = make_translation("Oil jumps").model_copy(
        update={"title_ko": "유가 급등"}
    )
    upload(alice, make_pdf(2), name="second.pdf")

    listed = alice.get("/api/articles").json()
    found = alice.get("/api/articles", params={"q": "유가"}).json()

    assert [a["filename"] for a in listed] == ["second.pdf", "first.pdf"]
    assert "paragraphs" not in listed[0]
    assert [a["title_ko"] for a in found] == ["유가 급등"]


async def test_restart_marks_unfinished_translations_interrupted(tmp_path: Path) -> None:
    news = News(tmp_path)
    alice = news.user("alice")
    me = alice.get("/api/auth/me").json()
    db = Database(tmp_path)
    with db.connect() as conn:
        owner = UUID(conn.execute("select id from users").fetchone()[0])

    await SqliteArticles(db, owner).insert_pending("a.pdf", "x/a.pdf", "abc", 1)

    restarted = News(tmp_path)
    alice = TestClient(restarted.app)
    alice.post("/api/auth/login", json={"username": me["username"], "password": PASSWORD})
    [article] = alice.get("/api/articles").json()
    assert article["status"] == "failed" and article["error"] == "interrupted"


# --- the Claude client, with the SDK stubbed out ---


class _Stream:
    def __init__(self, message: Any) -> None:
        self.message = message

    async def __aenter__(self) -> "_Stream":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get_final_message(self) -> Any:
        return self.message


def _client(text: str, stop_reason: str = "end_turn") -> Any:
    message = SimpleNamespace(
        model="claude-haiku-4-5-20251001",
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
    )
    calls: list[dict[str, Any]] = []

    def stream(**kwargs: Any) -> _Stream:
        calls.append(kwargs)
        return _Stream(message)

    return SimpleNamespace(messages=SimpleNamespace(stream=stream), calls=calls)


async def test_claude_translator_sends_pdf_and_parses_json() -> None:
    client = _client(make_translation().model_dump_json())
    translator = ClaudeTranslator(api_key="k", model="claude-haiku-4-5-20251001", client=client)

    result = await translator.translate(make_pdf())

    assert result.translation.title_ko == "연준, 금리 동결"
    [call] = client.calls
    document = call["messages"][0]["content"][0]
    assert document["type"] == "document"
    assert document["source"]["media_type"] == "application/pdf"
    assert call["output_config"]["format"]["type"] == "json_schema"


async def test_claude_translator_reports_truncation_and_bad_json() -> None:
    truncated = ClaudeTranslator(api_key="k", model="m", client=_client('{"title":', "max_tokens"))
    garbled = ClaudeTranslator(api_key="k", model="m", client=_client(json.dumps({"x": 1})))

    with pytest.raises(TranslatorError) as too_long:
        await truncated.translate(make_pdf())
    with pytest.raises(TranslatorError) as failed:
        await garbled.translate(make_pdf())

    assert too_long.value.code == "too_long"
    assert failed.value.code == "failed"
