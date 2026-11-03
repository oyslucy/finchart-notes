from pathlib import Path

from fastapi.testclient import TestClient

from finchart_api.config import Settings
from finchart_api.main import create_app


def _client(tmp_path: Path) -> TestClient:
    (tmp_path / "index.html").write_text("<html>spa</html>")
    return TestClient(create_app(Settings(_env_file=None, web_dist_dir=tmp_path)))


def test_client_route_falls_back_to_index(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/boards/123")

    assert response.status_code == 200
    assert "spa" in response.text


def test_unknown_api_route_stays_404(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/nope")

    assert response.status_code == 404
