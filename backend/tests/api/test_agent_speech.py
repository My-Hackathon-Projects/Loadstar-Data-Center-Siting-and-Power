"""Tests for `/agent/speech` (Fred text-to-speech)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.core.config import get_settings
from backend.api.main import app
from backend.api.services import tts_service


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_speech_requires_elevenlabs_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "")
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.post("/agent/speech", json={"text": "Hello."})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "speech_not_configured"


def test_speech_uses_configured_elevenlabs_voice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.setenv("ELEVEBLABS_VOICE_ID", "fred-voice")
    monkeypatch.setenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    get_settings.cache_clear()
    calls: list[dict[str, Any]] = []

    def fake_post(**kwargs: Any) -> tts_service.SpeechAudio:
        calls.append(kwargs)
        return tts_service.SpeechAudio(content=b"audio-bytes", media_type="audio/mpeg")

    monkeypatch.setattr(tts_service, "_post_elevenlabs_speech", fake_post)

    client = TestClient(app)
    response = client.post("/agent/speech", json={"text": "Hello, Fred."})

    assert response.status_code == 200
    assert response.content == b"audio-bytes"
    assert response.headers["content-type"] == "audio/mpeg"
    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["voice_id"] == "fred-voice"
    assert calls[0]["text"] == "Hello, Fred."
