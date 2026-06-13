"""Agent / LLM endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.api.routers.errors import key_error_message, not_found
from backend.api.services.agent_service import chat as agent_chat
from backend.api.services.llm_service import explain_site
from backend.engine.contracts import (
    AgentChatRequest,
    AgentChatResponse,
    ApiErrorResponse,
    ExplainRequest,
    ExplainResponse,
)

router = APIRouter(prefix="/agent", tags=["agent"])
_AGENT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {404: {"model": ApiErrorResponse}}


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
