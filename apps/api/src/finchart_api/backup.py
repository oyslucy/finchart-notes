"""Daily backups of DATA_DIR (SQLite + images) to Oracle Object Storage.

Usage: python -m finchart_api.backup {run|schedule|list|restore [NAME|latest]}
"""

import logging
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from finchart_api.infra.sqlite import DB_FILENAME, IMAGES_DIRNAME

PREFIX = "finchart-"
SUFFIX = ".tar.gz"
KEEP = 7
LAST_SUCCESS_FILE = ".last_backup"
# 19:00 UTC is 04:00 in Korea, when nobody is uploading.
RUN_AT_UTC_HOUR = 19

log = logging.getLogger("finchart.backup")


class BackupStore(Protocol):
    def put(self, name: str, source: Path) -> None: ...
    def names(self) -> list[str]: ...
    def delete(self, name: str) -> None: ...
    def fetch(self, name: str, dest: Path) -> None: ...


def archive_name(now: datetime) -> str:
    return f"{PREFIX}{now.strftime('%Y%m%d-%H%M%S')}{SUFFIX}"


def create_archive(data_dir: Path, dest_dir: Path, now: datetime) -> Path:
    """Takes a consistent SQLite snapshot (safe while the app writes) and tars it with images."""
    snapshot = dest_dir / DB_FILENAME
    with sqlite3.connect(data_dir / DB_FILENAME) as src, sqlite3.connect(snapshot) as dst:
        src.backup(dst)
    archive = dest_dir / archive_name(now)
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(snapshot, arcname=DB_FILENAME)
        images = data_dir / IMAGES_DIRNAME
        if images.is_dir():
            tar.add(images, arcname=IMAGES_DIRNAME)
    return archive


def prune(store: BackupStore, keep: int = KEEP) -> list[str]:
    ours = sorted(n for n in store.names() if n.startswith(PREFIX) and n.endswith(SUFFIX))
    stale = ours[:-keep] if keep else ours
    for name in stale:
        store.delete(name)
    return stale


def run_backup(data_dir: Path, store: BackupStore, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    with tempfile.TemporaryDirectory() as tmp:
        archive = create_archive(data_dir, Path(tmp), now)
        store.put(archive.name, archive)
    removed = prune(store)
    (data_dir / LAST_SUCCESS_FILE).write_text(now.isoformat())
    log.info("backup %s uploaded, pruned %d", archive.name, len(removed))
    return archive.name


def last_success(data_dir: Path) -> datetime | None:
    try:
        return datetime.fromisoformat((data_dir / LAST_SUCCESS_FILE).read_text().strip())
    except (OSError, ValueError):
        return None


def restore(data_dir: Path, store: BackupStore, name: str = "latest") -> str:
    """Replaces DATA_DIR contents with a backup. The app must be stopped first."""
    if name == "latest":
        candidates = sorted(n for n in store.names() if n.startswith(PREFIX))
        if not candidates:
            raise SystemExit("no backups found")
        name = candidates[-1]
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / name
        store.fetch(name, archive)
        staging = Path(tmp) / "staging"
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(staging, filter="data")
        if not (staging / DB_FILENAME).is_file():
            raise SystemExit(f"{name} does not contain {DB_FILENAME}")
        _set_aside_current(data_dir)
        for item in staging.iterdir():
            shutil.move(str(item), data_dir / item.name)
    log.info("restored %s", name)
    return name


def _set_aside_current(data_dir: Path) -> None:
    # Keeps the replaced data next to the new one instead of deleting it outright.
    aside = data_dir / f".pre-restore-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    aside.mkdir()
    for item in list(data_dir.iterdir()):
        if item.name.startswith(".pre-restore-"):
            continue
        shutil.move(str(item), aside / item.name)


def seconds_until_next_run(now: datetime) -> float:
    target = now.replace(hour=RUN_AT_UTC_HOUR, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def schedule(
    data_dir: Path, store: BackupStore, sleep: Callable[[float], None] = time.sleep
) -> None:
    while True:
        sleep(seconds_until_next_run(datetime.now(UTC)))
        try:
            run_backup(data_dir, store)
        except Exception:
            log.exception("backup failed; retrying in an hour")
            sleep(3600)
            try:
                run_backup(data_dir, store)
            except Exception:
                log.exception("backup retry failed; next attempt tomorrow")


class OciBackupStore:
    """Oracle Object Storage via instance principals, so no API keys live on the VM."""

    def __init__(self, bucket: str) -> None:
        import oci

        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        self._client = oci.object_storage.ObjectStorageClient(
            config={"region": signer.region}, signer=signer
        )
        self._ns = self._client.get_namespace().data
        self._bucket = bucket

    def put(self, name: str, source: Path) -> None:
        with source.open("rb") as body:
            self._client.put_object(self._ns, self._bucket, name, body)

    def names(self) -> list[str]:
        response = self._client.list_objects(self._ns, self._bucket, prefix=PREFIX)
        return [o.name for o in response.data.objects]

    def delete(self, name: str) -> None:
        self._client.delete_object(self._ns, self._bucket, name)

    def fetch(self, name: str, dest: Path) -> None:
        response = self._client.get_object(self._ns, self._bucket, name)
        with dest.open("wb") as out:
            for chunk in response.data.raw.stream(1024 * 1024, decode_content=False):
                out.write(chunk)


def main(argv: list[str]) -> None:
    from finchart_api.config import get_settings

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    command = argv[0] if argv else "run"
    store = OciBackupStore(settings.backup_bucket)
    if command == "run":
        print(run_backup(settings.data_dir, store))
    elif command == "schedule":
        log.info("next backup in %.0f s", seconds_until_next_run(datetime.now(UTC)))
        schedule(settings.data_dir, store)
    elif command == "list":
        print("\n".join(sorted(store.names())))
    elif command == "restore":
        print(restore(settings.data_dir, store, argv[1] if len(argv) > 1 else "latest"))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
