"""Tests for `/agent/chat` (agent-driven search).

The deterministic intent parser is the demo-safe default: every message runs a
real engine search and returns a dashboard action. When OpenAI is enabled the
model only rephrases the reply; any error falls back to the deterministic text.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.core.config import get_settings
from backend.api.main import app
from backend.api.services import agent_service


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _post(client: TestClient, message: str, **overrides: object) -> dict[str, Any]:
    payload: dict[str, object] = {
        "message": message,
        "power_mw": 280,
        "workload_type": "training",
    }
    payload.update(overrides)
    response = client.post("/agent/chat", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_runs_real_search_and_returns_focus_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOADSTAR_LLM_ENABLED", raising=False)
    client = TestClient(app)

    body = _post(client, "where are the best sites for training?")

    assert body["source"] == "template"
    assert body["model"] is None
    assert body["cache_key"].startswith("agent.chat:")

    action = body["action"]
    assert action["type"] == "search"
    results = action["search"]["results"]
    assert results, "expected at least one ranked candidate"
    assert action["focus_cell_id"] == results[0]["site"]["cell_id"]
    assert "Flying the map" in body["message"]


def test_chat_country_filter_narrows_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOADSTAR_LLM_ENABLED", raising=False)
    client = TestClient(app)

    body = _post(client, "find the cheapest site in Sweden")
    action = body["action"]

    assert action["applied"]["country_filter"] == ["SE"]
    # "cheapest" emphasizes the price weight above its default.
    assert action["applied"]["weights"]["price"] > 0.18
    results = action["search"]["results"]
    assert results
    assert all(item["site"]["country_code"] == "SE" for item in results)
    assert "Sweden" in body["message"]


def test_chat_mw_override_can_empty_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOADSTAR_LLM_ENABLED", raising=False)
    client = TestClient(app)

    body = _post(client, "need a 99999 MW campus")
    action = body["action"]

    assert action["applied"]["power_mw"] == 99999
    assert action["search"]["results"] == []
    assert action["focus_cell_id"] is None
    assert "No candidate" in body["message"]


def test_chat_uses_live_response_when_openai_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    get_settings.cache_clear()

    async def _fake_call(*_: Any, **__: Any) -> str:
        return "Lulea/Boden leads on carbon and headroom. Flying you there."

    monkeypatch.setattr(agent_service, "_try_openai_chat", _fake_call)

    client = TestClient(app)
    body = _post(client, "cheapest site in Sweden")

    assert body["source"] == "openai"
    assert body["model"] == "gpt-4o-mini"
    assert body["message"].startswith("Lulea/Boden")
    # The action still carries the real engine search, not the narration.
    assert body["action"]["type"] == "search"
    assert body["action"]["search"]["results"]


def test_chat_falls_back_to_template_when_openai_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    get_settings.cache_clear()

    async def _raises(*_: Any, **__: Any) -> str | None:
        return None

    monkeypatch.setattr(agent_service, "_try_openai_chat", _raises)

    client = TestClient(app)
    body = _post(client, "find sites in Germany")

    assert body["source"] == "template"
    assert body["action"]["applied"]["country_filter"] == ["DE"]
