"""LLM-backed site explanation service with a deterministic template fallback.

When `Settings.gemini_enabled` is true and `Settings.gemini_api_key` is set,
this service calls the Gemini API to generate a one-paragraph explanation of
the selected cell. Any failure (auth, rate-limit, network, unexpected response
shape) falls through to a deterministic template that uses the same site facts.
The response carries a `source` field so the UI can show a small badge
("Live" vs "Deterministic template").

The template path is the demo-safe default: a network blip, an expired API
key, or a regional outage cannot break the rehearsal.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from backend.api.core.config import get_settings
from backend.api.repositories.site_repository import site_repository
from backend.api.services.cache_keys import build_cache_key
from backend.engine.contracts import ExplainRequest, ExplainResponse, SiteFeature

logger = logging.getLogger("loadstar.llm")
_GEMINI_TIMEOUT_S = 30.0
_GEMINI_MAX_OUTPUT_TOKENS = 1024

_PROMPT_TEMPLATE = (
    "You are a senior data-center siting analyst writing for a hackathon judge. In "
    "two short Markdown paragraphs (about 150 words total), explain why the candidate "
    "cell below is or is not a strong fit for a {power_mw:.0f} MW AI {workload_type} "
    "campus. Use **bold** for the cell name and key figures. Reference the headroom, "
    "carbon intensity, mean price, buildable-land share, LightGBM viability, fiber "
    "distance, and congestion, and call out the clearest strength and the clearest "
    "risk. End with a concrete next step the user should take in the Pareto panel.\n\n"
    "Cell: {region_name} ({country_code}, cell_id={cell_id})\n"
    "Headroom: {headroom_mw:.0f} MW\n"
    "Mean price: {mean_price_eur_mwh:.0f} EUR/MWh\n"
    "Carbon intensity: {carbon_intensity_g_kwh:.0f} gCO2/kWh\n"
    "Buildable land share: {buildable_fraction:.2f}\n"
    "LightGBM viability: {lightgbm_score:.2f}\n"
    "Fiber distance: {dist_fiber_km:.1f} km\n"
    "Congestion index: {congestion_index:.2f}\n"
)


def _low_latency_thinking(types: Any) -> Any:
    """Low thinking budget so the call finishes in time; None if unsupported.

    `types: Any` so the construction is not type-checked against a specific
    google-genai stub version (the `thinking_level` field is newer than some
    installed stubs). Mirrors `agent_service._thinking_config`.
    """

    try:
        return types.ThinkingConfig(thinking_level="low")
    except Exception:
        return None


async def explain_site(payload: ExplainRequest) -> ExplainResponse:
    """Return a chat-bubble explanation for the requested cell.

    Tries the Gemini API when `LOADSTAR_LLM_ENABLED=true` and the
    key is set; falls back to the deterministic template on any error.
    """

    site = site_repository.get_site(payload.cell_id)
    if site is None:
        raise KeyError(f"Unknown site cell: {payload.cell_id}")

    cache_key = build_cache_key(
        "agent.explain",
        payload.cell_id,
        round(payload.power_mw, 2),
        payload.workload_type,
    )
    settings = get_settings()
    if settings.gemini_enabled and settings.gemini_api_key:
        live = await _try_gemini(site, payload, settings.gemini_api_key, settings.gemini_model)
        if live is not None:
            return ExplainResponse(
                cell_id=payload.cell_id,
                source="gemini",
                model=settings.gemini_model,
                message=live,
                cache_key=cache_key,
            )
    return ExplainResponse(
        cell_id=payload.cell_id,
        source="template",
        model=None,
        message=_template_message(site, payload),
        cache_key=cache_key,
    )


async def _try_gemini(
    site: SiteFeature,
    payload: ExplainRequest,
    api_key: str,
    model: str,
) -> str | None:
    """Call the Gemini API; return None on any error."""

    prompt = _PROMPT_TEMPLATE.format(
        power_mw=payload.power_mw,
        workload_type=payload.workload_type,
        region_name=site.region_name,
        country_code=site.country_code,
        cell_id=site.cell_id,
        headroom_mw=site.headroom_mw,
        mean_price_eur_mwh=site.mean_price_eur_mwh,
        carbon_intensity_g_kwh=site.carbon_intensity_g_kwh,
        buildable_fraction=site.buildable_fraction,
        lightgbm_score=site.lightgbm_score,
        dist_fiber_km=site.dist_fiber_km,
        congestion_index=site.congestion_index,
    )
    try:
        # Lazy import so test paths that monkey-patch the module don't pay the
        # cost of loading the Gemini client.
        from google import genai
        from google.genai import types

        # `client: Any` because google-genai's `generate_content` signature is
        # partially unknown under pyright strict mode; matches `_run_llm_agent`.
        client: Any = genai.Client(api_key=api_key)
        response: Any = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=_GEMINI_MAX_OUTPUT_TOKENS,
                    thinking_config=_low_latency_thinking(types),
                ),
            ),
            timeout=_GEMINI_TIMEOUT_S,
        )
    except Exception as exc:
        logger.warning(
            "llm.fallback",
            extra={
                "event": "llm.fallback",
                "reason": type(exc).__name__,
                "model": model,
            },
        )
        return None

    text = extract_response_text(response)
    if not text:
        logger.warning(
            "llm.empty_response",
            extra={"event": "llm.empty_response", "model": model},
        )
        return None
    return text


def extract_response_text(response: Any) -> str | None:
    """Pull assistant text out of common SDK response shapes."""

    text = _safe_getattr(response, "text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    candidates = _safe_getattr(response, "candidates")
    if isinstance(candidates, list):
        for candidate in cast(list[Any], candidates):
            content = _safe_getattr(candidate, "content")
            parts = _safe_getattr(content, "parts")
            if not isinstance(parts, list):
                continue
            for part in cast(list[Any], parts):
                part_text = _safe_getattr(part, "text")
                if isinstance(part_text, str) and part_text.strip():
                    return part_text.strip()

    text = _safe_getattr(response, "output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    output = getattr(response, "output", None)
    if isinstance(output, list):
        for item in cast(list[Any], output):
            content = _safe_getattr(item, "content")
            if not isinstance(content, list):
                continue
            for block in cast(list[Any], content):
                block_text = _safe_getattr(block, "text")
                if isinstance(block_text, str) and block_text.strip():
                    return block_text.strip()
    return None


def _safe_getattr(value: Any, name: str) -> Any:
    try:
        return getattr(value, name, None)
    except Exception:
        return None


def _template_message(site: SiteFeature, payload: ExplainRequest) -> str:
    """Deterministic explanation matching the previous frontend template."""

    return (
        f"{site.region_name} is being evaluated for {payload.power_mw:.0f} MW "
        f"{payload.workload_type}. Key facts: {site.headroom_mw:.0f} MW headroom, "
        f"{site.mean_price_eur_mwh:.0f} EUR/MWh, {site.carbon_intensity_g_kwh:.0f} "
        f"gCO2/kWh, {int(site.buildable_fraction * 100)}% buildable land, and "
        f"{int(site.lightgbm_score * 100)}% ML viability. Use the Pareto panel to "
        "inspect cost/carbon tradeoffs for this selected cell."
    )
