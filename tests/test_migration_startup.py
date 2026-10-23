"""Production startup migration behavior."""

from fastapi.testclient import TestClient

import app.main as main_module


def test_production_startup_applies_pending_migrations(monkeypatch):
    """Run Alembic to head before serving production traffic."""
    upgrade = []
    monkeypatch.setattr(main_module.settings, "app_env", "production")
    monkeypatch.setattr(
        main_module.command,
        "upgrade",
        lambda config, revision: upgrade.append((config, revision)),
    )

    with TestClient(main_module.app):
        pass

    assert len(upgrade) == 1
    assert upgrade[0][1] == "head"


def test_nonproduction_startup_does_not_run_migrations(monkeypatch):
    """Keep local/test startup independent of an external database."""
    upgrade = []
    monkeypatch.setattr(main_module.settings, "app_env", "development")
    monkeypatch.setattr(
        main_module.command,
        "upgrade",
        lambda config, revision: upgrade.append((config, revision)),
    )

    with TestClient(main_module.app):
        pass

    assert upgrade == []
