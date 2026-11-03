from pathlib import Path

from fastapi.testclient import TestClient

from finchart_api.config import Settings
from finchart_api.main import create_app


def test_health_returns_ok(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(_env_file=None, data_dir=tmp_path)))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "last_backup": None}
