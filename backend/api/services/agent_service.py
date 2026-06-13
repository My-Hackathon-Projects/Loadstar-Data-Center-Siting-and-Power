"""Agent chat service: Fred runs a real site search from a free-text ask.

The deterministic intent parser is the demo-safe default. It always builds a real
`SearchRequest` and runs the existing engine search, so the dashboard reacts to
every message even with no API key. When OpenAI is configured the live model only
rephrases the reply around the real, engine-computed numbers (numeric
faithfulness: the engine decides, the model narrates). Any LLM error falls back to
the deterministic narration, exactly like `llm_service`.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.api.core.config import get_settings
from backend.api.services.cache_keys import build_cache_key
from backend.api.services.llm_service import extract_response_text
from backend.api.services.site_service import search_site_cells
from backend.engine.contracts import (
    AgentAction,
    AgentChatRequest,
    AgentChatResponse,
    ExplainSource,
    RankedSite,
    SearchRequest,
    SearchResponse,
    Weights,
)

logger = logging.getLogger("loadstar.agent")

# Country names/adjectives mapped to the ISO-2 codes `country_filter` matches.
# Bare two-letter codes are intentionally omitted; words like "no" must not be
# read as Norway.
_COUNTRY_ALIASES: dict[str, str] = {
    "sweden": "SE",
    "swedish": "SE",
    "germany": "DE",
    "german": "DE",
    "ireland": "IE",
    "irish": "IE",
    "norway": "NO",
    "norwegian": "NO",
    "finland": "FI",
    "finnish": "FI",
    "denmark": "DK",
    "danish": "DK",
    "france": "FR",
    "french": "FR",
    "netherlands": "NL",
    "dutch": "NL",
    "holland": "NL",
}

_COUNTRY_NAMES: dict[str, str] = {
    "SE": "Sweden",
    "DE": "Germany",
    "IE": "Ireland",
    "NO": "Norway",
    "FI": "Finland",
    "DK": "Denmark",
    "FR": "France",
    "NL": "Netherlands",
}

# Phrase groups mapped to the scoring factor they emphasize. The factor's default
# weight is multiplied so the ranking leans that way without changing the engine.
_EMPHASIS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "cheapest",
            "cheap",
            "lowest price",
            "low price",
            "lowest cost",
            "low cost",
            "affordable",
            "price",
        ),
        "price",
    ),
    (
        (
            "greenest",
            "green",
            "cleanest",
            "clean",
            "lowest carbon",
            "low carbon",
            "carbon",
            "emission",
        ),
        "carbon",
    ),
    (("headroom", "capacity", "biggest", "largest", "most power", "grid"), "grid"),
    (("connectivity", "fiber", "fibre", "latency", "network", "ixp"), "connectivity"),
    (("buildable", "land"), "land"),
    (("uncongested", "congestion", "congested"), "congestion"),
)

_EMPHASIS_MULTIPLIER = 3.0


def _parse_country_filter(text: str) -> list[str] | None:
    found: list[str] = []
    for alias, code in _COUNTRY_ALIASES.items():
        if code in found:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", text):
            found.append(code)
    return found or None


def _build_weights(text: str) -> Weights:
    data = {key: float(value) for key, value in Weights().model_dump().items()}
    for phrases, factor in _EMPHASIS:
        if any(phrase in text for phrase in phrases):
            data[factor] *= _EMPHASIS_MULTIPLIER
    # Renormalize so the weights still sum to 1. This preserves the relative
    # emphasis (and therefore the ranking) while keeping the composite score in
    # the 0..1 range the UI renders as a percentage.
    total = sum(data.values())
    if total > 0:
        data = {key: value / total for key, value in data.items()}
    return Weights(**data)


def _build_search_request(payload: AgentChatRequest) -> SearchRequest:
    text = payload.message.lower()

    power_mw = payload.power_mw
    mw_match = re.search(r"(\d+(?:\.\d+)?)\s*mw", text)
    if mw_match:
        power_mw = max(float(mw_match.group(1)), 1.0)

    top_k = 8
    top_k_match = re.search(r"top\s+(\d+)|(\d+)\s+sites?", text)
    if top_k_match:
        raw = next(group for group in top_k_match.groups() if group)
        top_k = min(max(int(raw), 1), 50)

    workload = payload.workload_type
    if "inference" in text:
        workload = "inference"
    elif "mixed" in text:
        workload = "mixed"
    elif "training" in text:
        workload = "training"

    return SearchRequest(
        power_mw=power_mw,
        workload_type=workload,
        top_k=top_k,
        weights=_build_weights(text),
        country_filter=_parse_country_filter(text),
    )


def _filter_phrase(request: SearchRequest) -> str:
    if not request.country_filter:
        return ""
    names = [_COUNTRY_NAMES.get(code, code) for code in request.country_filter]
    return f" in {' / '.join(names)}"


def _deterministic_message(
    request: SearchRequest,
    search: SearchResponse,
    top: RankedSite | None,
) -> str:
    if top is None:
        return (
            f"No candidate cells clear the filters for {request.power_mw:.0f} MW"
            f"{_filter_phrase(request)}. Try a lower MW target or a wider country filter."
        )
    site = top.site
    count = len(search.results)
    plural = "s" if count != 1 else ""
    return (
        f"Found {count} candidate{plural}{_filter_phrase(request)}. "
        f"Top pick: {site.region_name} ({site.country_code}) at "
        f"{top.composite_score * 100:.0f}% score, {site.mean_price_eur_mwh:.0f} EUR/MWh, "
        f"{site.carbon_intensity_g_kwh:.0f} gCO2/kWh, {site.headroom_mw:.0f} MW headroom. "
        "Flying the map there now."
    )


def _facts_block(
    request: SearchRequest,
    search: SearchResponse,
    top: RankedSite | None,
) -> str:
    if top is None:
        return (
            f"Engine result: no candidates clear {request.power_mw:.0f} MW"
            f"{_filter_phrase(request)}."
        )
    site = top.site
    return (
        f"Engine result: {len(search.results)} candidates{_filter_phrase(request)}.\n"
        f"Top site: {site.region_name} ({site.country_code})\n"
        f"Composite score: {top.composite_score * 100:.0f}%\n"
        f"Mean price: {site.mean_price_eur_mwh:.0f} EUR/MWh\n"
        f"Carbon intensity: {site.carbon_intensity_g_kwh:.0f} gCO2/kWh\n"
        f"Headroom: {site.headroom_mw:.0f} MW\n"
    )


async def _try_openai_chat(
    payload: AgentChatRequest,
    request: SearchRequest,
    search: SearchResponse,
    top: RankedSite | None,
    api_key: str,
    model: str,
) -> str | None:
    """Rephrase the reply around the engine facts; return None on any error."""

    prompt = (
        "You are Fred, a data-center siting analyst embedded in a live dashboard. "
        "The engine already ran a real search for the user's question. In ONE short "
        "paragraph (max 70 words), answer using ONLY the facts below; never invent "
        "numbers. Name the top site, say briefly why it leads, and mention you are "
        "flying the map to it.\n\n"
        f"User question: {payload.message}\n\n{_facts_block(request, search, top)}"
    )
    try:
        # Lazy import so monkeypatched test paths never load the OpenAI client.
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        response: Any = await client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=300,
        )
    except Exception as exc:  # noqa: BLE001 - logged, fall back to deterministic text.
        logger.warning(
            "agent.fallback",
            extra={
                "event": "agent.fallback",
                "reason": type(exc).__name__,
                "model": model,
            },
        )
        return None
    return extract_response_text(response)


async def chat(payload: AgentChatRequest) -> AgentChatResponse:
    """Run an agent-driven search and return the reply plus a dashboard action."""

    request = _build_search_request(payload)
    search = search_site_cells(request)
    top = search.results[0] if search.results else None
    focus_cell_id = top.site.cell_id if top else None
    cache_key = build_cache_key("agent.chat", request, payload.message)

    message = _deterministic_message(request, search, top)
    source: ExplainSource = "template"
    model: str | None = None

    settings = get_settings()
    if settings.openai_enabled and settings.openai_api_key:
        live = await _try_openai_chat(
            payload,
            request,
            search,
            top,
            settings.openai_api_key,
            settings.openai_model,
        )
        if live is not None:
            message = live
            source = "openai"
            model = settings.openai_model

    return AgentChatResponse(
        source=source,
        model=model,
        message=message,
        action=AgentAction(
            type="search",
            search=search,
            focus_cell_id=focus_cell_id,
            applied=request,
        ),
        cache_key=cache_key,
    )
