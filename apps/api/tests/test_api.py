import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from finchart_api.config import Settings
from finchart_api.main import create_app

from .conftest import FakeProvider, make_png

PASSWORD = "correct-horse-1"


class Api:
    """One app over a temp data dir; each user gets their own cookie-carrying client."""

    def __init__(self, data_dir: Path, **overrides: object) -> None:
        # Starter boards are off by default so tests start from an empty account.
        options: dict[str, object] = {
            "allowed_usernames": "alice, bob",
            "default_boards": "",
            **overrides,
        }
        settings = Settings(_env_file=None, data_dir=data_dir, **options)  # type: ignore[arg-type]
        self.provider = FakeProvider()
        self.app = create_app(settings, provider=self.provider)
        self.data_dir = data_dir

    def client(self) -> TestClient:
        return TestClient(self.app)

    def user(self, username: str) -> TestClient:
        client = self.client()
        r = client.post("/api/auth/signup", json={"username": username, "password": PASSWORD})
        assert r.status_code == 201, r.text
        return client


def board(client: TestClient, title: str = "보드") -> str:
    r = client.post("/api/boards", json={"title": title})
    assert r.status_code == 201
    board_id: str = r.json()["id"]
    return board_id


def upload(client: TestClient, board_id: str, data: bytes, mime: str = "image/png"):  # type: ignore[no-untyped-def]
    return client.post(f"/api/boards/{board_id}/cards", files={"image": ("chart.png", data, mime)})


def png(seed: int) -> bytes:
    return make_png(1000 + seed, 800)


@pytest.fixture
def api(tmp_path: Path) -> Api:
    return Api(tmp_path)


# --- auth ---


def test_requests_without_session_are_401(api: Api) -> None:
    assert api.client().get("/api/boards").status_code == 401
    assert api.client().get("/api/auth/me").status_code == 401


def test_signup_signs_in(api: Api) -> None:
    alice = api.user("alice")
    assert alice.get("/api/auth/me").json() == {"username": "alice"}


def test_signup_rejects_unlisted_username(api: Api) -> None:
    r = api.client().post("/api/auth/signup", json={"username": "mallory", "password": PASSWORD})
    assert r.status_code == 403


def test_signup_rejects_taken_username(api: Api) -> None:
    api.user("alice")
    r = api.client().post("/api/auth/signup", json={"username": "Alice", "password": PASSWORD})
    assert r.status_code == 409


def test_signup_validates_password_length(api: Api) -> None:
    r = api.client().post("/api/auth/signup", json={"username": "alice", "password": "short"})
    assert r.status_code == 422


def test_login_and_logout(api: Api) -> None:
    api.user("alice")
    client = api.client()

    bad = client.post("/api/auth/login", json={"username": "alice", "password": "wrong-password"})
    good = client.post("/api/auth/login", json={"username": "ALICE", "password": PASSWORD})
    me = client.get("/api/auth/me")
    out = client.post("/api/auth/logout")
    after = client.get("/api/auth/me")

    assert bad.status_code == 401
    assert good.status_code == 200 and me.status_code == 200
    assert out.status_code == 204
    assert after.status_code == 401


def test_session_cookie_is_httponly(api: Api) -> None:
    r = api.client().post("/api/auth/signup", json={"username": "alice", "password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_removed_from_allow_list_loses_access(tmp_path: Path) -> None:
    alice = Api(tmp_path).user("alice")
    restricted = Api(tmp_path, allowed_usernames="bob")
    client = restricted.client()
    client.cookies.update(alice.cookies)

    assert client.get("/api/boards").status_code == 403


def test_login_is_rate_limited(tmp_path: Path) -> None:
    api = Api(tmp_path, login_attempts_per_minute=3)
    api.user("alice")
    client = api.client()

    codes = [
        client.post(
            "/api/auth/login", json={"username": "alice", "password": "nope-nope"}
        ).status_code
        for _ in range(4)
    ]

    assert codes == [401, 401, 401, 429]


def test_same_origin_post_via_proxy_is_allowed(api: Api) -> None:
    alice = api.user("alice")
    r = alice.post(
        "/api/boards",
        json={"title": "x"},
        headers={"Origin": "http://localhost:5173", "X-Forwarded-Host": "localhost:5173"},
    )
    assert r.status_code == 201


def test_cross_origin_post_is_blocked(api: Api) -> None:
    alice = api.user("alice")
    r = alice.post("/api/boards", json={"title": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


# --- isolation ---


def test_users_only_see_their_own_boards(api: Api) -> None:
    alice, bob = api.user("alice"), api.user("bob")
    board(alice, "앨리스")
    board(bob, "밥")

    assert [b["title"] for b in bob.get("/api/boards").json()] == ["밥"]


def test_other_users_board_is_not_found(api: Api) -> None:
    alice, bob = api.user("alice"), api.user("bob")
    board_id = board(alice)

    assert bob.patch(f"/api/boards/{board_id}", json={"title": "x"}).status_code == 404
    assert bob.delete(f"/api/boards/{board_id}").status_code == 404
    assert bob.get(f"/api/boards/{board_id}/cards").status_code == 404
    assert upload(bob, board_id, png(1)).status_code == 404


def test_other_users_card_and_image_are_not_found(api: Api) -> None:
    alice, bob = api.user("alice"), api.user("bob")
    card = upload(alice, board(alice), png(1)).json()["card"]

    assert bob.patch(f"/api/cards/{card['id']}", json={"user_note": "x"}).status_code == 404
    assert bob.delete(f"/api/cards/{card['id']}").status_code == 404
    assert bob.get(card["image_url"]).status_code == 404
    assert api.client().get(card["image_url"]).status_code == 401
    assert alice.get(card["image_url"]).status_code == 200


def test_image_path_traversal_is_rejected(api: Api) -> None:
    alice = api.user("alice")
    assert alice.get("/api/images/../finchart.db").status_code == 404
    assert alice.get("/api/images/%2e%2e/finchart.db").status_code == 404


def test_same_image_from_two_users_is_not_shared(api: Api) -> None:
    alice, bob = api.user("alice"), api.user("bob")
    first = upload(alice, board(alice), png(1)).json()
    second = upload(bob, board(bob), png(1)).json()

    assert not first["duplicate"] and not second["duplicate"]
    assert first["card"]["id"] != second["card"]["id"]


# --- cards ---


def test_upload_creates_card_and_serves_image(api: Api) -> None:
    alice = api.user("alice")
    r = upload(alice, board(alice), png(1))

    assert r.status_code == 201
    card = r.json()["card"]
    assert card["title"] == "KOSPI 일봉" and card["position"] == 0
    image = alice.get(card["image_url"])
    assert image.status_code == 200 and image.content[:4] == b"RIFF"
    assert "immutable" in image.headers["cache-control"]


def test_duplicate_hash_reuses_existing_analysis(api: Api) -> None:
    alice = api.user("alice")
    board_id = board(alice)
    first = upload(alice, board_id, png(1))
    second = upload(alice, board_id, png(1))

    assert second.status_code == 200 and second.json()["duplicate"] is True
    assert second.json()["card"]["id"] == first.json()["card"]["id"]
    assert api.provider.calls == 1


def test_new_cards_are_placed_first(api: Api) -> None:
    alice = api.user("alice")
    board_id = board(alice)
    ids = [upload(alice, board_id, png(i)).json()["card"]["id"] for i in range(3)]

    listed = alice.get(f"/api/boards/{board_id}/cards").json()

    assert [c["id"] for c in listed] == ids[::-1]
    assert [c["position"] for c in listed] == [0, 1, 2]


def test_reorder_changes_listing_order(api: Api) -> None:
    alice = api.user("alice")
    board_id = board(alice)
    ids = [upload(alice, board_id, png(i)).json()["card"]["id"] for i in range(3)]
    wanted = [ids[1], ids[0], ids[2]]

    r = alice.put(f"/api/boards/{board_id}/order", json={"card_ids": wanted})
    listed = alice.get(f"/api/boards/{board_id}/cards").json()

    assert r.status_code == 204
    assert [c["id"] for c in listed] == wanted
    assert [c["position"] for c in listed] == [0, 1, 2]


def test_reorder_rejects_incomplete_or_duplicated_list(api: Api) -> None:
    alice = api.user("alice")
    board_id = board(alice)
    ids = [upload(alice, board_id, png(i)).json()["card"]["id"] for i in range(2)]

    short = alice.put(f"/api/boards/{board_id}/order", json={"card_ids": ids[:1]})
    doubled = alice.put(f"/api/boards/{board_id}/order", json={"card_ids": [ids[0], ids[0]]})

    assert short.status_code == 400 and doubled.status_code == 400


def test_patch_updates_note_only(api: Api) -> None:
    alice = api.user("alice")
    card = upload(alice, board(alice), png(1)).json()["card"]

    r = alice.patch(f"/api/cards/{card['id']}", json={"user_note": "메모"})

    assert r.json()["user_note"] == "메모"
    assert r.json()["title"] == card["title"]


def test_delete_card_removes_image_files(api: Api) -> None:
    alice = api.user("alice")
    card_id = upload(alice, board(alice), png(1)).json()["card"]["id"]

    assert alice.delete(f"/api/cards/{card_id}").status_code == 204
    assert list((api.data_dir / "images").rglob("*.webp")) == []


def test_delete_board_removes_cards_and_files(api: Api) -> None:
    alice = api.user("alice")
    board_id = board(alice)
    upload(alice, board_id, png(1))

    assert alice.delete(f"/api/boards/{board_id}").status_code == 204
    assert alice.get(f"/api/boards/{board_id}/cards").status_code == 404
    assert list((api.data_dir / "images").rglob("*.webp")) == []


def test_data_survives_app_restart(tmp_path: Path) -> None:
    alice = Api(tmp_path).user("alice")
    board(alice, "남는 보드")

    restarted = Api(tmp_path).client()
    restarted.cookies.update(alice.cookies)

    assert [b["title"] for b in restarted.get("/api/boards").json()] == ["남는 보드"]


# --- limits ---


def test_rejects_non_image_mime(api: Api) -> None:
    alice = api.user("alice")
    assert upload(alice, board(alice), b"hello", mime="text/plain").status_code == 415


def test_rejects_spoofed_image(api: Api) -> None:
    alice = api.user("alice")
    assert upload(alice, board(alice), b"not really a png").status_code == 415


def test_rejects_unsupported_format_even_with_image_mime(api: Api) -> None:
    alice = api.user("alice")
    buf = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buf, format="GIF")
    assert upload(alice, board(alice), buf.getvalue()).status_code == 415


def test_rejects_oversized_upload(tmp_path: Path) -> None:
    alice = Api(tmp_path, max_upload_bytes=1000).user("alice")
    assert upload(alice, board(alice), png(1)).status_code == 413


def test_upload_rate_limit_is_per_user(tmp_path: Path) -> None:
    api = Api(tmp_path, rate_limit_per_minute=2)
    alice, bob = api.user("alice"), api.user("bob")
    board_id = board(alice)

    codes = [upload(alice, board_id, png(i)).status_code for i in range(3)]

    assert codes == [201, 201, 429]
    assert upload(bob, board(bob), png(9)).status_code == 201


# --- open signup and quotas ---


def test_empty_allow_list_means_open_signup(tmp_path: Path) -> None:
    api = Api(tmp_path, allowed_usernames="")
    anyone = api.user("random_person")
    assert anyone.get("/api/boards").status_code == 200


def test_signups_are_limited_per_ip(tmp_path: Path) -> None:
    api = Api(tmp_path, allowed_usernames="", signups_per_ip_per_hour=2)
    client = api.client()

    codes = [
        client.post(
            "/api/auth/signup", json={"username": f"user{i}", "password": PASSWORD}
        ).status_code
        for i in range(3)
    ]

    assert codes == [201, 201, 429]


def test_daily_analysis_quota_survives_card_deletion(tmp_path: Path) -> None:
    api = Api(tmp_path, daily_analyses_per_user=2)
    alice = api.user("alice")
    board_id = board(alice)
    first = upload(alice, board_id, png(1)).json()["card"]["id"]
    upload(alice, board_id, png(2))
    alice.delete(f"/api/cards/{first}")

    blocked = upload(alice, board_id, png(3))
    duplicate = upload(alice, board_id, png(2))

    assert blocked.status_code == 429 and blocked.json()["detail"] == "daily_quota"
    assert duplicate.status_code == 200 and duplicate.json()["duplicate"] is True
    bob = api.user("bob")
    assert upload(bob, board(bob), png(3)).status_code == 201


def test_recent_cards_span_boards_newest_first(api: Api) -> None:
    alice, bob = api.user("alice"), api.user("bob")
    first = upload(alice, board(alice, "매크로"), png(1)).json()["card"]["id"]
    second = upload(alice, board(alice, "반도체"), png(2)).json()["card"]["id"]
    upload(bob, board(bob), png(3))

    recent = alice.get("/api/cards").json()

    assert [c["id"] for c in recent] == [second, first]
    assert [c["board_title"] for c in recent] == ["반도체", "매크로"]
    assert recent[0]["thumb_url"].endswith("_thumb.webp")


# --- pinning, editing, search ---


def test_pinned_cards_come_first_on_board_and_home(api: Api) -> None:
    alice = api.user("alice")
    board_id = board(alice)
    ids = [upload(alice, board_id, png(i)).json()["card"]["id"] for i in range(3)]
    oldest = ids[0]

    pinned = alice.patch(f"/api/cards/{oldest}", json={"pinned": True})
    on_board = [c["id"] for c in alice.get(f"/api/boards/{board_id}/cards").json()]
    on_home = [c["id"] for c in alice.get("/api/cards").json()]

    assert pinned.json()["pinned"] is True
    assert on_board[0] == oldest and on_home[0] == oldest

    alice.patch(f"/api/cards/{oldest}", json={"pinned": False})
    assert [c["id"] for c in alice.get(f"/api/boards/{board_id}/cards").json()] == ids[::-1]


def test_card_text_can_be_edited(api: Api) -> None:
    alice = api.user("alice")
    card = upload(alice, board(alice), png(1)).json()["card"]

    r = alice.patch(
        f"/api/cards/{card['id']}",
        json={"title": "새 제목", "takeaways": ["하나", "둘"], "caveats": [], "period": None},
    )

    body = r.json()
    assert (body["title"], body["takeaways"], body["caveats"], body["period"]) == (
        "새 제목",
        ["하나", "둘"],
        [],
        None,
    )
    assert body["interpretation"] == card["interpretation"]


def test_card_edit_validates_limits(api: Api) -> None:
    alice = api.user("alice")
    card = upload(alice, board(alice), png(1)).json()["card"]

    too_many = alice.patch(f"/api/cards/{card['id']}", json={"takeaways": ["a", "b", "c", "d"]})
    empty_title = alice.patch(f"/api/cards/{card['id']}", json={"title": ""})

    assert too_many.status_code == 422 and empty_title.status_code == 422


def test_search_matches_text_note_and_board_title(api: Api) -> None:
    alice, bob = api.user("alice"), api.user("bob")
    macro = board(alice, "매크로 메모")
    first = upload(alice, macro, png(1)).json()["card"]["id"]
    second = upload(alice, board(alice, "반도체"), png(2)).json()["card"]["id"]
    alice.patch(f"/api/cards/{second}", json={"user_note": "HBM 수요 확인"})
    upload(bob, board(bob, "매크로"), png(3))

    def ids(q: str) -> list[str]:
        return [c["id"] for c in alice.get("/api/cards", params={"q": q}).json()]

    assert ids("hbm") == [second]
    assert ids("매크로") == [first]
    assert set(ids("KOSPI")) == {first, second}
    assert ids("없는단어") == []
    assert ids("%") == []


def test_existing_database_is_migrated(tmp_path: Path) -> None:
    import sqlite3

    from finchart_api.infra.sqlite import SCHEMA_VERSION

    with sqlite3.connect(tmp_path / "finchart.db") as conn:
        conn.executescript(
            """create table cards (id text primary key, board_id text, owner_id text,
                 position integer, image_path text, thumb_path text, image_sha256 text,
                 title text, chart_type text, period text, takeaways text,
                 interpretation text, caveats text, user_note text, model text,
                 raw_response text, created_at text);
               pragma user_version = 1;"""
        )

    alice = Api(tmp_path).user("alice")

    with sqlite3.connect(tmp_path / "finchart.db") as conn:
        columns = [r[1] for r in conn.execute("pragma table_info(cards)")]
        version = conn.execute("pragma user_version").fetchone()[0]
    assert "pinned_at" in columns and version == SCHEMA_VERSION
    assert alice.get("/api/boards").status_code == 200


def test_move_card_to_another_board(api: Api) -> None:
    alice, bob = api.user("alice"), api.user("bob")
    source, target = board(alice, "원래"), board(alice, "옮길 곳")
    existing = upload(alice, target, png(1)).json()["card"]["id"]
    card_id = upload(alice, source, png(2)).json()["card"]["id"]

    moved = alice.post(f"/api/cards/{card_id}/move", json={"board_id": target})

    assert moved.status_code == 200 and moved.json()["board_id"] == target
    listed = [c["id"] for c in alice.get(f"/api/boards/{target}/cards").json()]
    assert listed == [card_id, existing]
    assert alice.get(f"/api/boards/{source}/cards").json() == []
    bobs_board = board(bob)
    assert (
        alice.post(f"/api/cards/{card_id}/move", json={"board_id": bobs_board}).status_code == 404
    )
    assert bob.post(f"/api/cards/{card_id}/move", json={"board_id": bobs_board}).status_code == 404


def test_signup_creates_default_boards_in_order(tmp_path: Path) -> None:
    alice = Api(tmp_path, default_boards="반도체,IT,2차전지,바이오,금융").user("alice")
    titles = [b["title"] for b in alice.get("/api/boards").json()]
    assert titles == ["반도체", "IT", "2차전지", "바이오", "금융"]


async def test_add_default_boards_skips_existing(tmp_path: Path) -> None:
    from uuid import uuid4

    from finchart_api.domain.boards import add_default_boards
    from finchart_api.infra.sqlite import Database, SqliteBoards

    db = Database(tmp_path)
    db.migrate()
    owner = uuid4()
    with db.connect() as conn:
        conn.execute(
            "insert into users (id, username, password_hash, created_at)"
            " values (?, 'u', 'h', 'now')",
            (str(owner),),
        )
    boards = SqliteBoards(db, owner)
    await boards.create("it")

    created = await add_default_boards(boards, ["반도체", "IT", "금융"])

    assert sorted(b.title for b in created) == ["금융", "반도체"]
    assert len(await boards.list_all()) == 3
