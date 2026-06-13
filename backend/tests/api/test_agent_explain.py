"""Tests for `/agent/explain`.

Three states matter:
- Disabled: returns the deterministic template.
- Enabled but the OpenAI client raises: falls back to the template.
- Enabled and the OpenAI client returns text: returns the live response.

We patch `AsyncOpenAI` via `monkeypatch.setattr` on the imported symbol inside
`llm_service` so the real module never makes a network call.
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


def test_agent_explain_falls_back_when_openai_raises(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    get_settings.cache_clear()

    class _BoomClient:
        def __init__(self, **_: Any) -> None:
            self.responses = self

        async def create(self, **_: Any) -> Any:
            raise RuntimeError("network error")

    monkeypatch.setattr(llm_service, "_try_openai", _try_openai_raising)

    caplog.set_level("WARNING", logger="loadstar.llm")
    client = TestClient(app)
    response = client.post("/agent/explain", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "template"


async def _try_openai_raising(*_: Any, **__: Any) -> str | None:
    return None


def test_agent_explain_returns_live_response_when_openai_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOADSTAR_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    get_settings.cache_clear()

    async def _fake_call(*_: Any, **__: Any) -> str:
        return "Lulea/Boden looks strong: high headroom, low carbon, abundant wind."

    monkeypatch.setattr(llm_service, "_try_openai", _fake_call)

    client = TestClient(app)
    response = client.post("/agent/explain", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "openai"
    assert body["model"] == "gpt-4o-mini"
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


def test_extract_response_text_handles_output_text_attr() -> None:
    @dataclass
    class _Stub:
        output_text: str

    assert llm_service.extract_response_text(_Stub(output_text="hi")) == "hi"


def test_extract_response_text_walks_structured_output() -> None:
    @dataclass
    class _Block:
        text: str

    @dataclass
    class _Item:
        content: list[_Block]

    @dataclass
    class _Stub:
        output: list[_Item]
        output_text: None = None

    payload = _Stub(output=[_Item(content=[_Block(text="from-blocks")])])
    assert llm_service.extract_response_text(payload) == "from-blocks"
