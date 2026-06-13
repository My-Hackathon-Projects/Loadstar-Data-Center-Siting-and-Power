"""Server-side text-to-speech adapter for Fred's voice."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from urllib import error, parse, request

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

    return await asyncio.to_thread(
        _post_elevenlabs_speech,
        api_key=settings.elevenlabs_api_key,
        voice_id=settings.elevenlabs_voice_id,
        model=settings.elevenlabs_model,
        output_format=settings.elevenlabs_output_format,
        timeout_seconds=settings.elevenlabs_timeout_seconds,
        text=payload.text,
    )


def _post_elevenlabs_speech(
    *,
    api_key: str,
    voice_id: str,
    model: str,
    output_format: str,
    timeout_seconds: float,
    text: str,
) -> SpeechAudio:
    query = parse.urlencode({"output_format": output_format})
    safe_voice_id = parse.quote(voice_id, safe="")
    url = f"{_ELEVENLABS_BASE_URL}/{safe_voice_id}/stream?{query}"
    body = json.dumps({"text": text, "model_id": model}).encode("utf-8")
    upstream_request = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "xi-api-key": api_key,
        },
        method="POST",
    )

    try:
        with request.urlopen(upstream_request, timeout=timeout_seconds) as response:
            content_type = response.headers.get("content-type", "audio/mpeg")
            return SpeechAudio(content=response.read(), media_type=content_type)
    except error.HTTPError as exc:
        logger.warning(
            "tts.upstream_http_error",
            extra={
                "event": "tts.upstream_http_error",
                "status_code": exc.code,
                "provider": "elevenlabs",
            },
        )
        raise SpeechSynthesisError("ElevenLabs speech synthesis failed.") from exc
    except (OSError, TimeoutError) as exc:
        logger.warning(
            "tts.upstream_request_error",
            extra={
                "event": "tts.upstream_request_error",
                "reason": type(exc).__name__,
                "provider": "elevenlabs",
            },
        )
        raise SpeechSynthesisError("ElevenLabs speech synthesis failed.") from exc
