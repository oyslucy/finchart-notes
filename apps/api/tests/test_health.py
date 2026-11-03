from fastapi.testclient import TestClient

from finchart_api.config import Settings
from finchart_api.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
