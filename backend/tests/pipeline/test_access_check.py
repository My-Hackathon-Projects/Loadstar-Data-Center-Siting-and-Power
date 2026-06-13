"""Access-check decisions for the pipeline's external sources."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.api.core.config import get_settings
from backend.pipeline import access_check
from backend.pipeline.access_check import check_earth_engine, check_ember


def test_earth_engine_missing_project_records_downstream_implication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EARTHENGINE_PROJECT", raising=False)
    decision = check_earth_engine()
    assert decision.status == "blocked"
    assert "Issues 9 and 10" in decision.downstream_implication
    assert decision.fallback


def _isolate_ember_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the Ember-related env so each test starts from the same baseline."""

    monkeypatch.delenv("EMBER_HOURLY_PRICE_URL", raising=False)
    monkeypatch.delenv("EMBER_API_KEY", raising=False)
    monkeypatch.setenv("LOADSTAR_DISABLE_DOTENV", "1")
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "ember_hourly_price_url", None)
    monkeypatch.setattr(settings, "ember_api_key", None)


def test_ember_local_csv_db_is_preferred_when_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`check_ember()` reports `ok` when ember/dataset/ember_prices.db exists.

    The local CSV ledger (built by `python3 ember/ingest.py`) is the live
    Ember source today, so the access check must surface it as the
    preferred path rather than complaining about the unused HTTP endpoint.
    """

    _isolate_ember_env(monkeypatch)
    fake_db = tmp_path / "ember" / "dataset" / "ember_prices.db"
    fake_db.parent.mkdir(parents=True)
    fake_db.write_bytes(b"sqlite-stub")

    fake_root = tmp_path / "fake_repo_root" / "backend" / "pipeline" / "access_check.py"
    fake_root.parent.mkdir(parents=True)
    monkeypatch.setattr(access_check, "__file__", str(fake_root))
    real_db = tmp_path / "fake_repo_root" / "ember" / "dataset" / "ember_prices.db"
    real_db.parent.mkdir(parents=True)
    real_db.write_bytes(b"sqlite-stub")

    try:
        decision = check_ember()
    finally:
        get_settings.cache_clear()

    assert decision.status == "ok"
    assert "Local Ember CSV ledger" in decision.check
    assert "hourly_price" in decision.downstream_implication


def test_ember_blocked_when_neither_local_db_nor_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """No local DB and no URL ⇒ blocked, with a clear next-step instruction."""

    _isolate_ember_env(monkeypatch)
    # Point the access-check module at a sandbox that has no ember/ folder so
    # the real on-disk DB does not leak in and the test runs hermetically.
    fake_root = tmp_path / "fake_repo_root" / "backend" / "pipeline" / "access_check.py"
    fake_root.parent.mkdir(parents=True)
    monkeypatch.setattr(access_check, "__file__", str(fake_root))

    try:
        decision = check_ember()
    finally:
        get_settings.cache_clear()

    assert decision.status == "blocked"
    assert "ember/ingest.py" in (decision.fallback or "")
    assert "hourly_price" in decision.downstream_implication
