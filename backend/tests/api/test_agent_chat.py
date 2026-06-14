"""Tests for `/agent/chat` (agent-driven search).

Two paths share the same endpoint and contract:

* **Deterministic** — keyword-driven regex parser, used when the LLM is
  disabled or fails. Covered by the original tests below.
* **LLM tool-calling** — Gemini API with `search_sites` and
  `explain_site` tools. Covered by the new tests at the bottom that
  monkeypatch ``_run_llm_agent``; they intentionally do not exercise the
  Gemini SDK transport.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.core.config import get_settings
from backend.api.main import app
from backend.api.services import agent_service
from backend.api.services.site_service import search_site_cells
from backend.engine.contracts import (
    AgentAction,
    AgentChatRequest,
    AgentChatResponse,
    SearchRequest,
)


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
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "false")
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
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "false")
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


def test_chat_energy_manager_prompt_runs_germany_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "false")
    client = TestClient(app)

    body = _post(
        client,
        "I am the energy manager and want to build a data center for 280 MW in Germany.",
    )
    action = body["action"]

    assert action["type"] == "search"
    assert action["applied"]["power_mw"] == 280
    assert action["applied"]["country_filter"] == ["DE"]
    assert "Sure" in body["message"]


def test_chat_greeting_waits_without_dashboard_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "false")
    client = TestClient(app)

    body = _post(client, "hello fred")

    assert body["source"] == "template"
    assert body["message"] == "Hello, my name is Fred. How can I help you today?"
    assert body["action"]["type"] == "none"
    assert body["action"]["search"] is None
    assert body["action"]["applied"] is None


def test_chat_detail_follow_up_explains_selected_site(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "false")
    client = TestClient(app)
    first_search = _post(client, "find sites in Sweden")
    selected_cell_id = first_search["action"]["focus_cell_id"]
    selected_region = first_search["action"]["search"]["results"][0]["site"]["region_name"]

    body = _post(client, "show me the details", selected_cell_id=selected_cell_id)

    assert body["source"] == "template"
    assert body["action"]["type"] == "none"
    assert selected_region in body["message"]


def test_chat_mw_override_can_empty_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "false")
    client = TestClient(app)

    body = _post(client, "need a 99999 MW campus")
    action = body["action"]

    assert action["applied"]["power_mw"] == 99999
    assert action["search"]["results"] == []
    assert action["focus_cell_id"] is None
    assert "No candidate" in body["message"]


def test_chat_uses_live_response_when_gemini_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    get_settings.cache_clear()

    async def _fake_call(*_: Any, **__: Any) -> str:
        return "Lulea/Boden leads on carbon and headroom. Flying you there."

    monkeypatch.setattr(agent_service, "_try_gemini_chat", _fake_call)

    # Force the deterministic path so this test exercises the rephraser, not
    # the new tool-calling agent. The rephraser is the contract this test
    # was written for.
    async def _no_llm_agent(_: AgentChatRequest) -> AgentChatResponse | None:
        return None

    monkeypatch.setattr(agent_service, "_run_llm_agent", _no_llm_agent)

    client = TestClient(app)
    body = _post(client, "cheapest site in Sweden")

    assert body["source"] == "gemini"
    assert body["model"] == "gemini-3.1-pro-preview"
    assert body["message"].startswith("Lulea/Boden")
    # The action still carries the real engine search, not the narration.
    assert body["action"]["type"] == "search"
    assert body["action"]["search"]["results"]


def test_chat_falls_back_to_template_when_gemini_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    async def _raises(*_: Any, **__: Any) -> str | None:
        return None

    monkeypatch.setattr(agent_service, "_try_gemini_chat", _raises)

    # Force the LLM tool-calling agent to bow out so the deterministic path
    # runs (and exercises the fall-through `_try_gemini_chat` rephraser).
    async def _no_llm_agent(_: AgentChatRequest) -> AgentChatResponse | None:
        return None

    monkeypatch.setattr(agent_service, "_run_llm_agent", _no_llm_agent)

    client = TestClient(app)
    body = _post(client, "find sites in Germany")

    assert body["source"] == "template"
    assert body["action"]["applied"]["country_filter"] == ["DE"]


# --- LLM tool-calling agent path -------------------------------------------------


def _enable_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    get_settings.cache_clear()


def test_chat_llm_path_used_when_enabled_and_no_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A no-tool-call LLM reply skips the deterministic search entirely."""

    _enable_llm_env(monkeypatch)

    async def _llm(_: AgentChatRequest) -> AgentChatResponse | None:
        return AgentChatResponse(
            source="gemini",
            model="gemini-3.1-pro-preview",
            message="Hello! Tell me an MW target and a country and I will go.",
            action=AgentAction(type="none"),
            cache_key="agent.chat.llm:greet",
        )

    monkeypatch.setattr(agent_service, "_run_llm_agent", _llm)

    client = TestClient(app)
    body = _post(client, "hi fred")

    assert body["source"] == "gemini"
    assert body["model"] == "gemini-3.1-pro-preview"
    assert body["action"]["type"] == "none"
    assert body["action"]["search"] is None


def test_chat_llm_path_invokes_search_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the LLM returns a search action it must reach the dashboard."""

    _enable_llm_env(monkeypatch)

    request = SearchRequest(
        power_mw=280,
        workload_type="training",
        top_k=8,
        country_filter=["SE"],
    )
    engine_response = search_site_cells(request)
    assert engine_response.results, "fixture should rank at least one Swedish site"
    focus_cell_id = engine_response.results[0].site.cell_id

    async def _llm(_: AgentChatRequest) -> AgentChatResponse | None:
        return AgentChatResponse(
            source="gemini",
            model="gemini-3.1-pro-preview",
            message="Sure, Lulea/Boden leads. Flying the map there now.",
            action=AgentAction(
                type="search",
                search=engine_response,
                focus_cell_id=focus_cell_id,
                applied=request,
            ),
            cache_key="agent.chat.llm:se",
        )

    monkeypatch.setattr(agent_service, "_run_llm_agent", _llm)

    client = TestClient(app)
    body = _post(client, "cheapest 280 MW site in Sweden")

    assert body["source"] == "gemini"
    assert body["action"]["type"] == "search"
    assert body["action"]["focus_cell_id"] == focus_cell_id
    assert body["action"]["applied"]["country_filter"] == ["SE"]
    assert body["action"]["search"]["results"]


def test_chat_llm_path_falls_back_when_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM bowing out (network/auth/etc.) must not break the deterministic flow."""

    _enable_llm_env(monkeypatch)

    async def _llm(_: AgentChatRequest) -> AgentChatResponse | None:
        return None

    async def _no_rephrase(*_: Any, **__: Any) -> str | None:
        return None

    monkeypatch.setattr(agent_service, "_run_llm_agent", _llm)
    monkeypatch.setattr(agent_service, "_try_gemini_chat", _no_rephrase)

    client = TestClient(app)
    body = _post(client, "find sites in Germany")

    assert body["source"] == "template"
    assert body["action"]["type"] == "search"
    assert body["action"]["applied"]["country_filter"] == ["DE"]
    assert "Germany" in body["message"]


def test_chat_llm_path_forwards_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The history list must reach `_run_llm_agent` so multi-turn context works."""

    _enable_llm_env(monkeypatch)

    captured: dict[str, Any] = {}

    async def _llm(payload: AgentChatRequest) -> AgentChatResponse | None:
        captured["history"] = [(turn.speaker, turn.body) for turn in payload.history]
        captured["message"] = payload.message
        return AgentChatResponse(
            source="gemini",
            model="gemini-3.1-pro-preview",
            message="Got it.",
            action=AgentAction(type="none"),
            cache_key="agent.chat.llm:hist",
        )

    monkeypatch.setattr(agent_service, "_run_llm_agent", _llm)

    client = TestClient(app)
    history = [
        {"speaker": "user", "body": "we are looking at Sweden"},
        {"speaker": "assistant", "body": "Sure, Lulea is leading."},
    ]
    response = client.post(
        "/agent/chat",
        json={
            "message": "what about Germany?",
            "power_mw": 280,
            "workload_type": "training",
            "history": history,
        },
    )
    assert response.status_code == 200, response.text

    assert captured["message"] == "what about Germany?"
    assert captured["history"] == [
        ("user", "we are looking at Sweden"),
        ("assistant", "Sure, Lulea is leading."),
    ]
