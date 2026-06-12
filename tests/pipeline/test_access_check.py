from pipeline.access_check import check_earth_engine, check_ember


def test_earth_engine_missing_project_records_downstream_implication(monkeypatch) -> None:
    monkeypatch.delenv("EARTHENGINE_PROJECT", raising=False)
    decision = check_earth_engine()
    assert decision.status == "blocked"
    assert "Issues 9 and 10" in decision.downstream_implication
    assert decision.fallback


def test_ember_missing_hourly_url_records_actual_pull_requirement(monkeypatch) -> None:
    monkeypatch.delenv("EMBER_HOURLY_PRICE_URL", raising=False)
    decision = check_ember()
    assert decision.status == "blocked"
    assert "hourly price" in decision.check
    assert "Issue 6" in decision.downstream_implication
