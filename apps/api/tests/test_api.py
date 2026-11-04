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
        options: dict[str, object] = {"allowed_usernames": "alice, bob", **overrides}
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


def test_reorder_changes_listing_order(api: Api) -> None:
    alice = api.user("alice")
    board_id = board(alice)
    ids = [upload(alice, board_id, png(i)).json()["card"]["id"] for i in range(3)]

    r = alice.put(f"/api/boards/{board_id}/order", json={"card_ids": ids[::-1]})
    listed = alice.get(f"/api/boards/{board_id}/cards").json()

    assert r.status_code == 204
    assert [c["id"] for c in listed] == ids[::-1]
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
