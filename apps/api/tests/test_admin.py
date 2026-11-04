import sqlite3
from pathlib import Path

import pytest
from pydantic import SecretStr

from finchart_api.admin import delete_user
from finchart_api.config import Settings

from .conftest import make_png
from .test_api import Api, board, upload
from .test_telegram import Harness


def test_delete_user_removes_everything_it_owns(tmp_path: Path) -> None:
    api = Api(tmp_path)
    alice, bob = api.user("alice"), api.user("bob")
    upload(alice, board(alice), make_png(1001))
    bob_card = upload(bob, board(bob), make_png(1002)).json()["card"]

    message = delete_user(Settings(_env_file=None, data_dir=tmp_path), "alice")

    assert message == "deleted alice: 1 board(s), 1 card(s)"
    with sqlite3.connect(tmp_path / "finchart.db") as conn:
        tables = ["users", "sessions", "boards", "cards", "analysis_log"]
        remaining = {t: conn.execute(f"select count(*) from {t}").fetchone()[0] for t in tables}
    assert remaining == {"users": 1, "sessions": 1, "boards": 1, "cards": 1, "analysis_log": 1}
    assert alice.get("/api/boards").status_code == 401
    assert bob.get(bob_card["image_url"]).status_code == 200
    owners = {p.name for p in (tmp_path / "images").iterdir()}
    assert len(owners) == 1


def test_delete_user_also_drops_telegram_link(tmp_path: Path) -> None:
    h = Harness(tmp_path, telegram_bot_token=SecretStr("123:token"))
    h.linked_user("alice", tg_user=111)

    delete_user(Settings(_env_file=None, data_dir=tmp_path), "alice")

    h.send(text="hello", tg_user=111)
    assert "먼저 연결해주세요" in h.telegram.sent[-1][1]


def test_delete_unknown_user_fails(tmp_path: Path) -> None:
    Api(tmp_path)
    with pytest.raises(SystemExit):
        delete_user(Settings(_env_file=None, data_dir=tmp_path), "nobody")
