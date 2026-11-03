import shutil
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finchart_api.backup import (
    archive_name,
    last_success,
    prune,
    restore,
    run_backup,
    seconds_until_next_run,
)
from finchart_api.config import Settings
from finchart_api.infra.sqlite import Database
from finchart_api.main import create_app


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, name: str, source: Path) -> None:
        self.objects[name] = source.read_bytes()

    def names(self) -> list[str]:
        return list(self.objects)

    def delete(self, name: str) -> None:
        del self.objects[name]

    def fetch(self, name: str, dest: Path) -> None:
        dest.write_bytes(self.objects[name])


def seed(data_dir: Path) -> None:
    db = Database(data_dir)
    db.migrate()
    with db.connect() as conn:
        conn.execute(
            "insert into users (id, username, password_hash, created_at)"
            " values ('u1', 'alice', 'h', 'now')"
        )
    image = data_dir / "images" / "u1" / "abc.webp"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"RIFFimage")


def usernames(data_dir: Path) -> list[str]:
    with sqlite3.connect(data_dir / "finchart.db") as conn:
        return [r[0] for r in conn.execute("select username from users")]


def test_backup_then_restore_round_trips(tmp_path: Path) -> None:
    data, store = tmp_path / "data", MemoryStore()
    seed(data)

    name = run_backup(data, store, now=datetime(2026, 11, 4, 19, tzinfo=UTC))
    shutil.rmtree(data / "images")
    (data / "finchart.db").unlink()
    data.joinpath("stray.txt").write_text("replaced data")
    restored = restore(data, store)

    assert restored == name == "finchart-20261104-190000.tar.gz"
    assert usernames(data) == ["alice"]
    assert (data / "images" / "u1" / "abc.webp").read_bytes() == b"RIFFimage"
    aside = next(data.glob(".pre-restore-*"))
    assert (aside / "stray.txt").read_text() == "replaced data"


def test_backup_records_last_success(tmp_path: Path) -> None:
    seed(tmp_path)
    when = datetime(2026, 11, 4, 19, tzinfo=UTC)

    run_backup(tmp_path, MemoryStore(), now=when)

    assert last_success(tmp_path) == when


def test_prune_keeps_seven_newest(tmp_path: Path) -> None:
    store = MemoryStore()
    start = datetime(2026, 11, 1, tzinfo=UTC)
    names = [archive_name(start + timedelta(days=i)) for i in range(10)]
    for name in names:
        store.objects[name] = b""
    store.objects["unrelated.txt"] = b""

    removed = prune(store)

    assert removed == names[:3]
    assert sorted(store.names()) == sorted([*names[3:], "unrelated.txt"])


def test_restore_specific_backup(tmp_path: Path) -> None:
    data, store = tmp_path / "data", MemoryStore()
    seed(data)
    first = run_backup(data, store, now=datetime(2026, 11, 3, tzinfo=UTC))
    with sqlite3.connect(data / "finchart.db") as conn:
        conn.execute("update users set username = 'changed'")
    run_backup(data, store, now=datetime(2026, 11, 4, tzinfo=UTC))

    restore(data, store, first)

    assert usernames(data) == ["alice"]


def test_restore_without_backups_fails(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        restore(tmp_path, MemoryStore())


@pytest.mark.parametrize(
    ("now", "expected_hours"),
    [
        (datetime(2026, 11, 4, 18, 0, tzinfo=UTC), 1),
        (datetime(2026, 11, 4, 19, 0, tzinfo=UTC), 24),
        (datetime(2026, 11, 4, 20, 0, tzinfo=UTC), 23),
    ],
)
def test_next_run_is_19_utc(now: datetime, expected_hours: int) -> None:
    assert seconds_until_next_run(now) == expected_hours * 3600


def test_health_reports_last_backup(tmp_path: Path) -> None:
    seed(tmp_path)
    run_backup(tmp_path, MemoryStore(), now=datetime(2026, 11, 4, 19, tzinfo=UTC))
    client = TestClient(create_app(Settings(_env_file=None, data_dir=tmp_path)))

    assert client.get("/api/health").json() == {
        "status": "ok",
        "last_backup": "2026-11-04T19:00:00Z",
    }
