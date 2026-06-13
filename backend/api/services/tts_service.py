"""Server-side text-to-speech adapter for Fred's voice.

Uses ``httpx`` instead of ``urllib`` because the latter relies on the system
Python's SSL truststore, which is empty on the python.org macOS installer and
fails every HTTPS call with ``URLError([SSL: CERTIFICATE_VERIFY_FAILED])``.
``httpx`` ships with ``certifi``'s CA bundle by default, so the request works
out of the box on any platform without an "Install Certificates" step.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from backend.api.core.config import get_settings
from backend.engine.contracts import FredSpeechRequest

logger = logging.getLogger("loadstar.tts")

_ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"


@dataclass(frozen=True)
class SpeechAudio:
    """Generated audio bytes plus the response media type."""

    content: bytes
    media_type: str


class SpeechConfigurationError(RuntimeError):
    """Raised when required text-to-speech configuration is missing."""


class SpeechSynthesisError(RuntimeError):
    """Raised when the upstream text-to-speech provider fails."""


async def synthesize_fred_speech(payload: FredSpeechRequest) -> SpeechAudio:
    """Generate Fred's speech with ElevenLabs, keeping credentials server-side."""

    settings = get_settings()
    if not settings.elevenlabs_api_key or not settings.elevenlabs_voice_id:
        raise SpeechConfigurationError("ElevenLabs voice is not configured.")

    safe_voice_id = quote(settings.elevenlabs_voice_id, safe="")
    url = f"{_ELEVENLABS_BASE_URL}/{safe_voice_id}/stream"
    headers = {
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
        "xi-api-key": settings.elevenlabs_api_key,
    }
    body = {"text": payload.text, "model_id": settings.elevenlabs_model}
    params = {"output_format": settings.elevenlabs_output_format}

    try:
        async with httpx.AsyncClient(timeout=settings.elevenlabs_timeout_seconds) as client:
            response = await client.post(url, json=body, headers=headers, params=params)
    except httpx.HTTPError as exc:
        logger.warning(
            "tts.upstream_request_error",
            extra={
                "event": "tts.upstream_request_error",
                "reason": type(exc).__name__,
                "provider": "elevenlabs",
            },
        )
        raise SpeechSynthesisError("ElevenLabs speech synthesis failed.") from exc

    if response.status_code >= 400:
        # Surface the upstream failure body in the structured log so 402
        # ("paid plan required"), 401 (bad key), and 422 (bad voice id) are
        # diagnosable without re-running the request by hand. The body is
        # truncated and the api key never leaves the request headers.
        body_preview: str
        try:
            body_preview = response.text[:500]
        except Exception:
            body_preview = "<unreadable>"
        logger.warning(
            "tts.upstream_http_error",
            extra={
                "event": "tts.upstream_http_error",
                "status_code": response.status_code,
                "provider": "elevenlabs",
                "body_preview": body_preview,
            },
        )
        raise SpeechSynthesisError("ElevenLabs speech synthesis failed.")

    media_type = response.headers.get("content-type", "audio/mpeg")
    return SpeechAudio(content=response.content, media_type=media_type)
