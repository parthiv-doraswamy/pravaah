"""Smoke tests for API health endpoints with isolated dependency checks."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_endpoint_reports_api_process() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pravaah-api"}


def test_readiness_succeeds_when_database_check_succeeds(monkeypatch) -> None:
    monkeypatch.setattr("app.main.database_is_ready", lambda: True)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "pravaah-api",
        "checks": {"database": "ok"},
    }


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("app.main.database_is_ready", lambda: False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["database"] == "unavailable"
