from backend.api.core.config import get_settings
from backend.pipeline.access_check import check_earth_engine, check_ember


def test_earth_engine_missing_project_records_downstream_implication(monkeypatch) -> None:
    monkeypatch.delenv("EARTHENGINE_PROJECT", raising=False)
    decision = check_earth_engine()
    assert decision.status == "blocked"
    assert "Issues 9 and 10" in decision.downstream_implication
    assert decision.fallback


def test_ember_missing_hourly_url_records_actual_pull_requirement(monkeypatch) -> None:
    # `check_ember()` reads `EMBER_HOURLY_PRICE_URL` via `get_settings()`. The
    # Settings singleton is cached, so we need to drop it after stripping the
    # env var to force a fresh load that picks up the absence.
    monkeypatch.delenv("EMBER_HOURLY_PRICE_URL", raising=False)
    monkeypatch.delenv("EMBER_API_KEY", raising=False)
    monkeypatch.setenv("LOADSTAR_DISABLE_DOTENV", "1")
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "ember_hourly_price_url", None)
    monkeypatch.setattr(settings, "ember_api_key", None)
    try:
        decision = check_ember()
    finally:
        get_settings.cache_clear()
    assert decision.status == "blocked"
    assert "hourly price" in decision.check
    assert "Issue 6" in decision.downstream_implication
