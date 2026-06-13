"""LLM-backed site explanation service with a deterministic template fallback.

When `Settings.openai_enabled` is true and `Settings.openai_api_key` is set,
this service calls the OpenAI Responses API to generate a one-paragraph
explanation of the selected cell. Any failure (auth, rate-limit, network,
unexpected response shape) falls through to a deterministic template that uses
the same site facts. The response carries a `source` field so the UI can show
a small badge ("Live" vs "Deterministic template").

The template path is the demo-safe default: a network blip, an expired API
key, or a regional outage cannot break the rehearsal.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from backend.api.core.config import get_settings
from backend.api.repositories.site_repository import site_repository
from backend.api.services.cache_keys import build_cache_key
from backend.engine.contracts import ExplainRequest, ExplainResponse, SiteFeature

logger = logging.getLogger("loadstar.llm")

_PROMPT_TEMPLATE = (
    "You are a senior data-center siting analyst. In ONE paragraph (max 110 words), "
    "explain to a hackathon judge why the candidate cell below is or is not a strong "
    "fit for a {power_mw:.0f} MW AI {workload_type} campus. Reference the headroom, "
    "carbon intensity, mean price, buildable-land share, and the LightGBM viability "
    "score. End with a concrete next step the user should take in the Pareto panel.\n\n"
    "Cell: {region_name} ({country_code}, cell_id={cell_id})\n"
    "Headroom: {headroom_mw:.0f} MW\n"
    "Mean price: {mean_price_eur_mwh:.0f} EUR/MWh\n"
    "Carbon intensity: {carbon_intensity_g_kwh:.0f} gCO2/kWh\n"
    "Buildable land share: {buildable_fraction:.2f}\n"
    "LightGBM viability: {lightgbm_score:.2f}\n"
    "Fiber distance: {dist_fiber_km:.1f} km\n"
    "Congestion index: {congestion_index:.2f}\n"
)


async def explain_site(payload: ExplainRequest) -> ExplainResponse:
    """Return a chat-bubble explanation for the requested cell.

    Tries the OpenAI Responses API when `LOADSTAR_LLM_ENABLED=true` and the
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
    if settings.openai_enabled and settings.openai_api_key:
        live = await _try_openai(site, payload, settings.openai_api_key, settings.openai_model)
        if live is not None:
            return ExplainResponse(
                cell_id=payload.cell_id,
                source="openai",
                model=settings.openai_model,
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


async def _try_openai(
    site: SiteFeature,
    payload: ExplainRequest,
    api_key: str,
    model: str,
) -> str | None:
    """Call the OpenAI Responses API; return None on any error."""

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
        # cost of loading the OpenAI client.
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        response: Any = await client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=300,
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
    """Pull the assistant message out of the Responses API payload.

    The 1.x SDK exposes a convenience `output_text` attribute; we still walk
    the structured payload as a fallback in case the SDK surface evolves.
    """

    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    output = getattr(response, "output", None)
    if isinstance(output, list):
        # Pyright cannot narrow the element type from `Any`-rooted attribute
        # access; cast so the loop bodies are typed.
        for item in cast(list[Any], output):
            content = getattr(item, "content", None)
            if not isinstance(content, list):
                continue
            for block in cast(list[Any], content):
                block_text = getattr(block, "text", None)
                if isinstance(block_text, str) and block_text.strip():
                    return block_text.strip()
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
