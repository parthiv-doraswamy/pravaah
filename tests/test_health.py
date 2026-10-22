"""Smoke tests for the API's initial health contract."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_endpoint_reports_api_process() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pravaah-api"}


def test_readiness_endpoint_discloses_unconfigured_dependency_checks() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"] == "not_configured"
