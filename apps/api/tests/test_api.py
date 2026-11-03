import io
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from finchart_api.config import Settings
from finchart_api.main import create_app

from .conftest import FakeProvider, make_png
from .fakes import HmacVerifier, Store, fake_user_data, make_token

ALICE = (uuid4(), "alice@example.com")
BOB = (uuid4(), "bob@example.com")


class Api:
    def __init__(self, rate_limit: int = 100, max_upload: int = 10 * 1024 * 1024) -> None:
        self.store = Store()
        self.provider = FakeProvider()
        settings = Settings(
            _env_file=None,
            allowed_emails="alice@example.com, BOB@example.com",
            rate_limit_per_minute=rate_limit,
            max_upload_bytes=max_upload,
        )
        app = create_app(
            settings,
            verifier=HmacVerifier(),
            user_data=fake_user_data(self.store),
            provider=self.provider,
        )
        self.client = TestClient(app)

    @staticmethod
    def auth(user: tuple[UUID, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(*user)}"}

    def board(self, user: tuple[UUID, str], title: str = "보드") -> str:
        r = self.client.post("/api/boards", json={"title": title}, headers=self.auth(user))
        assert r.status_code == 201
        board_id: str = r.json()["id"]
        return board_id

    def upload(self, user: tuple[UUID, str], board_id: str, data: bytes, mime: str = "image/png"):  # type: ignore[no-untyped-def]
        return self.client.post(
            f"/api/boards/{board_id}/cards",
            files={"image": ("chart.png", data, mime)},
            headers=self.auth(user),
        )


@pytest.fixture
def api() -> Api:
    return Api()


def png(seed: int) -> bytes:
    return make_png(1000 + seed, 800)


# --- auth ---


def test_missing_token_is_401(api: Api) -> None:
    assert api.client.get("/api/boards").status_code == 401


def test_garbage_token_is_401(api: Api) -> None:
    r = api.client.get("/api/boards", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_email_not_in_allow_list_is_403(api: Api) -> None:
    r = api.client.get("/api/boards", headers=api.auth((uuid4(), "mallory@example.com")))
    assert r.status_code == 403


def test_allow_list_is_case_insensitive(api: Api) -> None:
    r = api.client.get("/api/boards", headers=api.auth((BOB[0], "Bob@Example.com")))
    assert r.status_code == 200


def test_empty_allow_list_denies_everyone() -> None:
    app = create_app(
        Settings(_env_file=None),
        verifier=HmacVerifier(),
        user_data=fake_user_data(Store()),
        provider=FakeProvider(),
    )
    r = TestClient(app).get("/api/boards", headers=Api.auth(ALICE))
    assert r.status_code == 403


# --- isolation ---


def test_users_only_see_their_own_boards(api: Api) -> None:
    api.board(ALICE, "앨리스")
    api.board(BOB, "밥")

    titles = [b["title"] for b in api.client.get("/api/boards", headers=api.auth(BOB)).json()]

    assert titles == ["밥"]


def test_other_users_board_is_not_found(api: Api) -> None:
    board_id = api.board(ALICE)
    bob = api.auth(BOB)

    assert (
        api.client.patch(f"/api/boards/{board_id}", json={"title": "x"}, headers=bob).status_code
        == 404
    )
    assert api.client.delete(f"/api/boards/{board_id}", headers=bob).status_code == 404
    assert api.client.get(f"/api/boards/{board_id}/cards", headers=bob).status_code == 404
    assert api.upload(BOB, board_id, png(1)).status_code == 404


def test_other_users_card_is_not_found(api: Api) -> None:
    card_id = api.upload(ALICE, api.board(ALICE), png(1)).json()["card"]["id"]
    bob = api.auth(BOB)

    assert (
        api.client.patch(f"/api/cards/{card_id}", json={"user_note": "x"}, headers=bob).status_code
        == 404
    )
    assert api.client.delete(f"/api/cards/{card_id}", headers=bob).status_code == 404


def test_same_image_from_two_users_is_not_shared(api: Api) -> None:
    image = png(1)
    first = api.upload(ALICE, api.board(ALICE), image)
    second = api.upload(BOB, api.board(BOB), image)

    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is False
    assert first.json()["card"]["id"] != second.json()["card"]["id"]


# --- cards ---


def test_upload_creates_card_with_signed_urls(api: Api) -> None:
    r = api.upload(ALICE, api.board(ALICE), png(1))

    assert r.status_code == 201
    card = r.json()["card"]
    assert card["title"] == "KOSPI 일봉"
    assert card["position"] == 0
    assert card["image_url"].startswith("https://signed.test/")
    assert len(api.store.objects) == 2


def test_duplicate_hash_reuses_existing_analysis(api: Api) -> None:
    board_id = api.board(ALICE)
    first = api.upload(ALICE, board_id, png(1))
    second = api.upload(ALICE, board_id, png(1))

    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["card"]["id"] == first.json()["card"]["id"]
    assert api.provider.calls == 1


def test_reorder_changes_listing_order(api: Api) -> None:
    board_id = api.board(ALICE)
    ids = [api.upload(ALICE, board_id, png(i)).json()["card"]["id"] for i in range(3)]

    r = api.client.put(
        f"/api/boards/{board_id}/order", json={"card_ids": ids[::-1]}, headers=api.auth(ALICE)
    )
    listed = api.client.get(f"/api/boards/{board_id}/cards", headers=api.auth(ALICE)).json()

    assert r.status_code == 204
    assert [c["id"] for c in listed] == ids[::-1]
    assert [c["position"] for c in listed] == [0, 1, 2]


def test_reorder_rejects_incomplete_list(api: Api) -> None:
    board_id = api.board(ALICE)
    ids = [api.upload(ALICE, board_id, png(i)).json()["card"]["id"] for i in range(2)]

    r = api.client.put(
        f"/api/boards/{board_id}/order", json={"card_ids": ids[:1]}, headers=api.auth(ALICE)
    )

    assert r.status_code == 400


def test_patch_updates_note_only(api: Api) -> None:
    card = api.upload(ALICE, api.board(ALICE), png(1)).json()["card"]

    r = api.client.patch(
        f"/api/cards/{card['id']}", json={"user_note": "메모"}, headers=api.auth(ALICE)
    )

    assert r.json()["user_note"] == "메모"
    assert r.json()["title"] == card["title"]


def test_delete_card_removes_storage_objects(api: Api) -> None:
    card_id = api.upload(ALICE, api.board(ALICE), png(1)).json()["card"]["id"]

    assert api.client.delete(f"/api/cards/{card_id}", headers=api.auth(ALICE)).status_code == 204
    assert api.store.objects == {}


def test_delete_board_removes_cards_and_objects(api: Api) -> None:
    board_id = api.board(ALICE)
    api.upload(ALICE, board_id, png(1))

    assert api.client.delete(f"/api/boards/{board_id}", headers=api.auth(ALICE)).status_code == 204
    assert api.store.cards == {} and api.store.objects == {}


# --- limits ---


def test_rejects_non_image_mime(api: Api) -> None:
    r = api.upload(ALICE, api.board(ALICE), b"hello", mime="text/plain")
    assert r.status_code == 415


def test_rejects_spoofed_image(api: Api) -> None:
    r = api.upload(ALICE, api.board(ALICE), b"not really a png")
    assert r.status_code == 415


def test_rejects_unsupported_format_even_with_image_mime(api: Api) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buf, format="GIF")
    r = api.upload(ALICE, api.board(ALICE), buf.getvalue())
    assert r.status_code == 415


def test_rejects_oversized_upload() -> None:
    api = Api(max_upload=1000)
    r = api.upload(ALICE, api.board(ALICE), png(1))
    assert r.status_code == 413


def test_rate_limit_per_user() -> None:
    api = Api(rate_limit=2)
    board_id = api.board(ALICE)

    codes = [api.upload(ALICE, board_id, png(i)).status_code for i in range(3)]
    bob_code = api.upload(BOB, api.board(BOB), png(9)).status_code

    assert codes == [201, 201, 429]
    assert bob_code == 201


def test_username_allow_list() -> None:
    domain = "users.finchart-notes.duckdns.org"
    app = create_app(
        Settings(_env_file=None, allowed_usernames="Lucy"),
        verifier=HmacVerifier(),
        user_data=fake_user_data(Store()),
        provider=FakeProvider(),
    )
    client = TestClient(app)

    allowed = client.get("/api/boards", headers=Api.auth((uuid4(), f"lucy@{domain}")))
    other = client.get("/api/boards", headers=Api.auth((uuid4(), f"mallory@{domain}")))
    wrong_domain = client.get("/api/boards", headers=Api.auth((uuid4(), "lucy@example.com")))

    assert allowed.status_code == 200
    assert other.status_code == 403
    assert wrong_domain.status_code == 403


def test_unconfigured_supabase_rejects_tokens_but_health_works() -> None:
    client = TestClient(create_app(Settings(_env_file=None, allowed_emails="alice@example.com")))

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/boards", headers=Api.auth(ALICE)).status_code == 401
