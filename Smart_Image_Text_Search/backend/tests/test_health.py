from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_health_checks_database(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "test")
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
