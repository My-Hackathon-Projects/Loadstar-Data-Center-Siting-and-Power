"""Agent / LLM endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.api.routers.errors import key_error_message, not_found
from backend.api.services.agent_service import chat as agent_chat
from backend.api.services.llm_service import explain_site
from backend.api.services.tts_service import (
    SpeechConfigurationError,
    SpeechSynthesisError,
    synthesize_fred_speech,
)
from backend.engine.contracts import (
    AgentChatRequest,
    AgentChatResponse,
    ApiErrorDetail,
    ApiErrorResponse,
    ExplainRequest,
    ExplainResponse,
    FredSpeechRequest,
)

router = APIRouter(prefix="/agent", tags=["agent"])
_AGENT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {404: {"model": ApiErrorResponse}}
_SPEECH_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"content": {"audio/mpeg": {}}},
    502: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}


@router.post(
    "/explain",
    response_model=ExplainResponse,
    responses=_AGENT_ERROR_RESPONSES,
)
async def explain(request: ExplainRequest) -> ExplainResponse:
    """Explain a selected site for the chat panel; falls back to a template."""

    try:
        return await explain_site(request)
    except KeyError as exc:
        raise not_found(key_error_message(exc), code="site_not_found") from exc


@router.post("/chat", response_model=AgentChatResponse)
async def chat(request: AgentChatRequest) -> AgentChatResponse:
    """Run an agent-driven site search for the chat panel and return a dashboard action."""

    return await agent_chat(request)


@router.post("/speech", response_class=Response, responses=_SPEECH_RESPONSES)
async def speech(request: FredSpeechRequest) -> Response:
    """Generate Fred's spoken audio with the configured ElevenLabs voice."""

    try:
        audio = await synthesize_fred_speech(request)
    except SpeechConfigurationError as exc:
        raise _speech_error(
            "Fred voice is not configured.",
            code="speech_not_configured",
            status_code=503,
        ) from exc
    except SpeechSynthesisError as exc:
        raise _speech_error(
            "Fred voice synthesis failed.",
            code="speech_provider_failed",
            status_code=502,
        ) from exc
    return Response(content=audio.content, media_type=audio.media_type)


def _speech_error(message: str, *, code: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ApiErrorDetail(code=code, message=message).model_dump(),
    )
