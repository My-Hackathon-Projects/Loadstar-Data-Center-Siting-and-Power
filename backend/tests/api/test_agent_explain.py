"""Tests for `/agent/explain`.

Three states matter:
- Disabled: returns the deterministic template.
- Enabled but the Gemini client raises: falls back to the template.
- Enabled and the Gemini client returns text: returns the live response.

Tests patch the Gemini helper so the real module never makes a network call.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.core.config import get_settings
from backend.api.main import app
from backend.api.services import llm_service


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _payload() -> dict[str, object]:
    return {
        "cell_id": "8508c683fffffff",
        "power_mw": 280,
        "workload_type": "training",
    }


def test_agent_explain_returns_template_when_llm_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "false")
    client = TestClient(app)
    response = client.post("/agent/explain", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "template"
    assert body["model"] is None
    assert body["cell_id"] == "8508c683fffffff"
    assert "viability" in body["message"].lower() or "viable" in body["message"].lower()
    assert body["cache_key"].startswith("agent.explain:")


def test_agent_explain_falls_back_when_gemini_raises(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    monkeypatch.setattr(llm_service, "_try_gemini", _try_gemini_raising)

    caplog.set_level("WARNING", logger="loadstar.llm")
    client = TestClient(app)
    response = client.post("/agent/explain", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "template"


async def _try_gemini_raising(*_: Any, **__: Any) -> str | None:
    return None


def test_agent_explain_returns_live_response_when_gemini_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    get_settings.cache_clear()

    async def _fake_call(*_: Any, **__: Any) -> str:
        return "Lulea/Boden looks strong: high headroom, low carbon, abundant wind."

    monkeypatch.setattr(llm_service, "_try_gemini", _fake_call)

    client = TestClient(app)
    response = client.post("/agent/explain", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "gemini"
    assert body["model"] == "gemini-3.1-pro-preview"
    assert body["message"].startswith("Lulea/Boden")


def test_agent_explain_404_on_unknown_cell() -> None:
    client = TestClient(app)
    response = client.post(
        "/agent/explain",
        json={
            "cell_id": "no-such-cell",
            "power_mw": 280,
            "workload_type": "training",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "site_not_found"


def test_extract_response_text_handles_text_attr() -> None:
    @dataclass
    class _Stub:
        text: str

    assert llm_service.extract_response_text(_Stub(text="hi")) == "hi"


def test_extract_response_text_walks_structured_candidates() -> None:
    @dataclass
    class _Part:
        text: str

    @dataclass
    class _Content:
        parts: list[_Part]

    @dataclass
    class _Candidate:
        content: _Content

    @dataclass
    class _Stub:
        candidates: list[_Candidate]
        text: None = None

    payload = _Stub(candidates=[_Candidate(content=_Content(parts=[_Part(text="from-blocks")]))])
    assert llm_service.extract_response_text(payload) == "from-blocks"
