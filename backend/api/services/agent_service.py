"""Agent chat service: Fred answers free text and runs real searches when needed.

Two paths share the same `chat()` entry point:

1. **LLM tool-calling agent (preferred).** When `LOADSTAR_LLM_ENABLED=true` and an
   `GEMINI_API_KEY` is set, the Gemini API drives the conversation. The model
   has two tools — `search_sites` (real engine search) and
   `explain_site` (cell explanation). The model decides when to call them; the
   server executes the call against the real engine and feeds the result back.
   The model never sees free-form numbers it can echo: every figure in its
   reply must come from a tool result, enforced by the system prompt.

2. **Deterministic regex fallback.** When the LLM is disabled, missing, or
   errors, a keyword-driven parser (preserved verbatim from the original
   service) builds a `SearchRequest`, runs the engine, and returns deterministic
   narration. This is the demo-safe default and keeps the rehearsal alive when
   any external dependency is offline.

The wire contract `AgentChatResponse` is identical across both paths so the
frontend store/map updates without branching.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, cast

from backend.api.core.config import get_settings
from backend.api.services.cache_keys import build_cache_key
from backend.api.services.llm_service import explain_site, extract_response_text
from backend.api.services.site_service import search_site_cells
from backend.engine.contracts import (
    AgentAction,
    AgentChatRequest,
    AgentChatResponse,
    ExplainRequest,
    ExplainSource,
    RankedSite,
    SearchRequest,
    SearchResponse,
    Weights,
)

logger = logging.getLogger("loadstar.agent")

# ISO-2 code to display name for every country in the curated dataset.
_COUNTRY_NAMES: dict[str, str] = {
    "AT": "Austria",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CH": "Switzerland",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IS": "Iceland",
    "IT": "Italy",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
}

# Country names and adjectives mapped to the ISO-2 codes `country_filter` matches.
# Bare two-letter codes are intentionally omitted (a word like "no" must not be
# read as Norway); "uk" is the one safe abbreviation because it is never an
# ordinary English word.
_COUNTRY_ALIASES: dict[str, str] = {
    "austria": "AT",
    "austrian": "AT",
    "belgium": "BE",
    "belgian": "BE",
    "bulgaria": "BG",
    "bulgarian": "BG",
    "switzerland": "CH",
    "swiss": "CH",
    "czechia": "CZ",
    "czech republic": "CZ",
    "czech": "CZ",
    "germany": "DE",
    "german": "DE",
    "denmark": "DK",
    "danish": "DK",
    "estonia": "EE",
    "estonian": "EE",
    "spain": "ES",
    "spanish": "ES",
    "finland": "FI",
    "finnish": "FI",
    "france": "FR",
    "french": "FR",
    "united kingdom": "GB",
    "great britain": "GB",
    "britain": "GB",
    "british": "GB",
    "england": "GB",
    "uk": "GB",
    "greece": "GR",
    "greek": "GR",
    "croatia": "HR",
    "croatian": "HR",
    "hungary": "HU",
    "hungarian": "HU",
    "ireland": "IE",
    "irish": "IE",
    "iceland": "IS",
    "icelandic": "IS",
    "italy": "IT",
    "italian": "IT",
    "lithuania": "LT",
    "lithuanian": "LT",
    "luxembourg": "LU",
    "latvia": "LV",
    "latvian": "LV",
    "netherlands": "NL",
    "dutch": "NL",
    "holland": "NL",
    "norway": "NO",
    "norwegian": "NO",
    "poland": "PL",
    "polish": "PL",
    "portugal": "PT",
    "portuguese": "PT",
    "romania": "RO",
    "romanian": "RO",
    "serbia": "RS",
    "serbian": "RS",
    "sweden": "SE",
    "swedish": "SE",
    "slovenia": "SI",
    "slovenian": "SI",
    "slovakia": "SK",
    "slovak": "SK",
}

_SUPPORTED_COUNTRY_CODES: tuple[str, ...] = tuple(_COUNTRY_NAMES.keys())

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
_SUPPORTED_EMPHASIS_FACTORS: tuple[str, ...] = (
    "price",
    "carbon",
    "grid",
    "connectivity",
    "land",
    "congestion",
)

_WORKLOAD_TERMS = ("training", "inference", "mixed")

_SEARCH_INTENT_TERMS = (
    "build",
    "campus",
    "capacity",
    "candidate",
    "data center",
    "datacenter",
    "details",
    "find",
    "location",
    "recommend",
    "search",
    "show",
    "site",
    "where",
)

_DETAIL_INTENT_TERMS = (
    "detail",
    "explain",
    "risk",
    "tradeoff",
    "why",
)

_HELP_INTENT_TERMS = (
    "help",
    "what can you do",
    "how does this work",
    "how do you work",
)

_THANKS_TERMS = ("thanks", "thank you", "appreciate it")

FRED_INTRO = "Hello, my name is Fred. How can I help you today?"

# LLM tool-calling configuration.
_MAX_TOOL_ITERATIONS = 2
_LLM_TIMEOUT_S = 30.0
_LLM_MAX_OUTPUT_TOKENS = 2048

_FRED_SYSTEM_PROMPT = (
    "You are Fred, a senior data-center siting analyst embedded in the "
    "Loadstar dashboard. You help users decide where to build AI campuses "
    "across Europe, and you explain your reasoning like an expert advisor.\n\n"
    "TOOLS\n"
    "- search_sites: ALWAYS call this when the user asks where to build, for the "
    "cheapest/greenest/biggest site, mentions a country or region, an MW target, "
    "or any comparison across sites. Never state siting numbers from memory.\n"
    "- explain_site: call when the user asks for details, tradeoffs, or risk on a "
    "specific cell and a selected_cell_id is available.\n\n"
    "MULTI-TURN REFINEMENT (critical): when the user sends a short follow-up (a "
    "country name, 'what about Germany?', 'try 100 MW', 'cheaper instead'), treat "
    "it as a REFINEMENT of your most recent search. Reuse the prior power_mw, "
    "workload_type, and emphasis unless the user changes them; only override what "
    "they actually mention. Never silently revert to defaults across turns.\n\n"
    "NUMERIC FAITHFULNESS: every price, carbon intensity, headroom, distance, or "
    "score in your reply MUST come verbatim from a tool result you received this "
    "turn. Never invent or estimate numbers. With no tool result, call "
    "search_sites or ask a clarifying question.\n\n"
    "RESPONSE STYLE: be thorough and genuinely useful, not terse. The chat panel "
    "renders Markdown, so format for fast scanning:\n"
    "- Open with one sentence framing the result (the load, any country filter, "
    "how many candidates ranked).\n"
    "- Then a numbered list of the top candidates (up to 6). For each, a bold "
    "heading like '**1. Lulea, Sweden - 82% match**', followed by indented "
    "bullets that use the tool numbers, for example:\n"
    "  - Carbon: 24 g/kWh\n"
    "  - Price: EUR 42/MWh\n"
    "  - Headroom: 540 MW\n"
    "  - Grid: 6 km to HV substation\n"
    "  - Connectivity: 12 km to fiber\n"
    "  - Why it ranks here: its strongest factors from score_breakdown.\n"
    "- Close with a short recommendation that names the single best pick and its "
    "main tradeoff, then a next step ('Flying the map to Lulea now.').\n"
    "Write complete, informative bullets. Do not pad, but do not be one-line "
    "terse. Write 'EUR' rather than a currency symbol.\n\n"
    "For a single-site question, write a tight, well-structured paragraph or a "
    "short bulleted profile instead of a numbered list.\n"
    "If the user only greets you, thanks you, or asks how the product works, "
    "reply in one or two friendly sentences without calling any tool."
)


_SEARCH_SITES_DECLARATION: dict[str, Any] = {
    "name": "search_sites",
    "description": (
        "Run the live siting engine to rank candidate cells for a "
        "data-center build. Returns, per cell, real price, carbon intensity, "
        "grid headroom, distance to HV substation and to fiber, buildable-land "
        "fraction, and a per-factor score_breakdown. Use those numbers verbatim."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "power_mw": {
                "type": "number",
                "minimum": 1,
                "description": "Target load in megawatts.",
            },
            "workload_type": {
                "type": "string",
                "enum": ["training", "inference", "mixed"],
                "description": "Workload profile that drives the carbon weighting.",
            },
            "top_k": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "How many ranked candidates to return (default 8).",
            },
            "country_filter": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": list(_SUPPORTED_COUNTRY_CODES),
                },
                "description": "Restrict ranking to these ISO-2 country codes.",
            },
            "emphasis": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": list(_SUPPORTED_EMPHASIS_FACTORS),
                },
                "description": (
                    "Factors to emphasize in the composite score. "
                    "Multiplies the default weight before renormalizing."
                ),
            },
        },
        "required": ["power_mw"],
    },
}


_EXPLAIN_SITE_DECLARATION: dict[str, Any] = {
    "name": "explain_site",
    "description": (
        "Generate a detailed explanation of a single candidate cell. Use when "
        "the user asks 'why', 'tradeoffs', 'risks', or 'tell me about this "
        "site' for the currently selected cell."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "cell_id": {
                "type": "string",
                "description": "H3 cell identifier returned by search_sites.",
            },
            "power_mw": {
                "type": "number",
                "minimum": 1,
                "description": "Target load in MW for the explanation.",
            },
            "workload_type": {
                "type": "string",
                "enum": ["training", "inference", "mixed"],
            },
        },
        "required": ["cell_id"],
    },
}


def _parse_country_filter(text: str) -> list[str] | None:
    found: list[str] = []
    for alias, code in _COUNTRY_ALIASES.items():
        if code in found:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", text):
            found.append(code)
    return found or None


def _weights_from_emphasis(factors: list[str]) -> Weights:
    """Build a `Weights` boosting each factor by `_EMPHASIS_MULTIPLIER`.

    Mirrors the regex-driven `_build_weights` used in the deterministic path,
    but takes a structured list of factor names — the LLM tool surface picks
    from `_SUPPORTED_EMPHASIS_FACTORS` so the inputs are validated upstream.
    """

    data = {key: float(value) for key, value in Weights().model_dump().items()}
    for factor in factors:
        if factor not in data:
            continue
        data[factor] *= _EMPHASIS_MULTIPLIER
    total = sum(data.values())
    if total > 0:
        data = {key: value / total for key, value in data.items()}
    return Weights(**data)


def _build_weights(text: str) -> Weights:
    factors: list[str] = []
    for phrases, factor in _EMPHASIS:
        if any(phrase in text for phrase in phrases):
            factors.append(factor)
    return _weights_from_emphasis(factors)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _mentions_power(text: str) -> bool:
    return re.search(r"\d+(?:\.\d+)?\s*mw", text) is not None


def _mentions_emphasis(text: str) -> bool:
    return any(phrase in text for phrases, _ in _EMPHASIS for phrase in phrases)


def _has_siting_constraints(text: str) -> bool:
    return (
        _parse_country_filter(text) is not None
        or _mentions_power(text)
        or _contains_any(text, _WORKLOAD_TERMS)
    )


def _has_search_intent(text: str) -> bool:
    return (
        _has_siting_constraints(text)
        or _mentions_emphasis(text)
        or _contains_any(text, _SEARCH_INTENT_TERMS)
    )


def _is_greeting(text: str) -> bool:
    greeting_pattern = r"\b(hello|hey|hi|good morning|good afternoon|good evening)\b"
    return re.search(greeting_pattern, text) is not None


def _is_selected_detail_question(payload: AgentChatRequest, text: str) -> bool:
    if payload.selected_cell_id is None or _has_siting_constraints(text):
        return False
    return _contains_any(text, _DETAIL_INTENT_TERMS) or "tell me about" in text


def _conversation_message(text: str) -> str:
    if _is_greeting(text) or "who are you" in text or "your name" in text:
        return FRED_INTRO
    if _contains_any(text, _THANKS_TERMS):
        return "You are welcome. I am here when you want to compare sites or adjust the load."
    if _contains_any(text, _HELP_INTENT_TERMS):
        return (
            "Tell me the load in MW, the country or region, and what matters most: "
            "cost, carbon, grid headroom, land, or connectivity."
        )
    return (
        "I can help with live siting searches. Tell me the MW target, the country, "
        "and the priority you want me to optimize."
    )


def _history_block(payload: AgentChatRequest) -> str:
    turns = payload.history[-6:]
    if not turns:
        return "Recent conversation: none."
    lines = [f"{turn.speaker}: {turn.body[:500]}" for turn in turns]
    return "Recent conversation:\n" + "\n".join(lines)


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
            f"Sure, I checked the live siting engine. No candidate cells clear "
            f"the filters for {request.power_mw:.0f} MW"
            f"{_filter_phrase(request)}. Try a lower MW target or a wider country filter."
        )
    site = top.site
    count = len(search.results)
    plural = "s" if count != 1 else ""
    return (
        f"Sure, here is what I found. Found {count} candidate{plural}"
        f"{_filter_phrase(request)}. "
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


async def _try_gemini_chat(
    payload: AgentChatRequest,
    request: SearchRequest,
    search: SearchResponse,
    top: RankedSite | None,
    api_key: str,
    model: str,
) -> str | None:
    """Rephrase the deterministic reply around the engine facts; None on error.

    Used only by the deterministic fallback path. The new tool-calling agent
    (`_run_llm_agent`) drives the LLM directly and does not call this helper.
    """

    prompt = (
        "You are Fred, a data-center siting analyst embedded in a live dashboard. "
        "The engine already ran a real search for the user's question. In ONE short "
        "paragraph (max 80 words), answer using ONLY the facts below; never invent "
        "numbers. Begin naturally with 'Sure' when appropriate. Name the top site, "
        "say briefly why it leads, and mention you are flying the map to it.\n\n"
        f"{_history_block(payload)}\n\n"
        f"User question: {payload.message}\n\n{_facts_block(request, search, top)}"
    )
    try:
        # Lazy import so monkeypatched test paths never load the Gemini client.
        from google import genai
        from google.genai import types

        # `client: Any` because google-genai's `generate_content` signature is
        # partially unknown under pyright strict mode; matches `_run_llm_agent`.
        client: Any = genai.Client(api_key=api_key)
        response: Any = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=300),
            ),
            timeout=_LLM_TIMEOUT_S,
        )
    except Exception as exc:
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


def _build_search_request_from_args(
    payload: AgentChatRequest,
    args: dict[str, Any],
) -> SearchRequest:
    """Convert tool-call args into a SearchRequest, defaulting to payload values."""

    power_raw = args.get("power_mw", payload.power_mw)
    try:
        power_mw = max(float(power_raw), 1.0)
    except (TypeError, ValueError):
        power_mw = max(float(payload.power_mw), 1.0)

    workload = args.get("workload_type", payload.workload_type)
    if workload not in _WORKLOAD_TERMS:
        workload = payload.workload_type

    top_k_raw = args.get("top_k", 8)
    try:
        top_k = min(max(int(top_k_raw), 1), 50)
    except (TypeError, ValueError):
        top_k = 8

    country_filter_raw = args.get("country_filter")
    if isinstance(country_filter_raw, list):
        country_filter_list = cast(list[Any], country_filter_raw)
        country_filter: list[str] | None = [
            code
            for code in country_filter_list
            if isinstance(code, str) and code in _SUPPORTED_COUNTRY_CODES
        ] or None
    else:
        country_filter = None

    emphasis_raw = args.get("emphasis")
    if isinstance(emphasis_raw, list):
        emphasis_list = cast(list[Any], emphasis_raw)
        emphasis = [
            factor
            for factor in emphasis_list
            if isinstance(factor, str) and factor in _SUPPORTED_EMPHASIS_FACTORS
        ]
    else:
        emphasis = []

    return SearchRequest(
        power_mw=power_mw,
        workload_type=workload,
        top_k=top_k,
        weights=_weights_from_emphasis(emphasis),
        country_filter=country_filter,
    )


def _summarize_search_for_tool(
    request: SearchRequest,
    response: SearchResponse,
) -> dict[str, Any]:
    """Compact payload the LLM consumes as the search_sites result.

    Surfaces the top five candidates with the same fields the deterministic
    narration uses. Keeping this small reduces token cost and forces the model
    to lean on the tool result rather than reasoning over the entire response.
    """

    top_results: list[dict[str, Any]] = []
    for ranked in response.results[:8]:
        site = ranked.site
        top_results.append(
            {
                "cell_id": site.cell_id,
                "region_name": site.region_name,
                "country": _COUNTRY_NAMES.get(site.country_code, site.country_code),
                "country_code": site.country_code,
                "composite_score_pct": round(ranked.composite_score * 100, 1),
                "mean_price_eur_mwh": round(site.mean_price_eur_mwh, 1),
                "carbon_intensity_g_kwh": round(site.carbon_intensity_g_kwh, 1),
                "headroom_mw": round(site.headroom_mw, 1),
                "dist_hv_substation_km": round(site.dist_hv_substation_km, 1),
                "dist_fiber_km": round(site.dist_fiber_km, 1),
                "buildable_fraction": round(site.buildable_fraction, 2),
                # Per-factor 0..1 scores so the model can explain *why* a cell
                # ranks where it does (e.g. "leads on carbon and price").
                "score_breakdown": {
                    factor: round(value, 2)
                    for factor, value in ranked.score_breakdown.items()
                },
            }
        )
    payload: dict[str, Any] = {
        "count": len(response.results),
        "applied": {
            "power_mw": request.power_mw,
            "workload_type": request.workload_type,
            "top_k": request.top_k,
            "country_filter": request.country_filter,
        },
        "top_results": top_results,
    }
    return payload


def _thinking_config(types: Any) -> Any:
    """Low-latency thinking config, tolerant of google-genai version drift.

    The configured model only runs in thinking mode, and its default budget is
    slow enough to blow the per-call timeout. "low" keeps the reasoning quality
    while roughly thirding the latency. Returns None when the installed SDK does
    not expose `thinking_level`, so the call still succeeds at the default budget.
    """

    try:
        return types.ThinkingConfig(thinking_level="low")
    except Exception:
        return None


def _build_gemini_contents(payload: AgentChatRequest, types: Any) -> list[Any]:
    """Convert prior history + the new user message into Gemini contents."""

    items: list[Any] = []
    for turn in payload.history[-8:]:
        items.append(
            types.Content(
                role="model" if turn.speaker == "assistant" else "user",
                parts=[types.Part(text=turn.body)],
            )
        )
    items.append(
        types.Content(
            role="user",
            parts=[types.Part(text=payload.message)],
        )
    )
    return items


def _extract_function_calls(response: Any) -> list[dict[str, Any]]:
    """Collect Gemini function calls from a model response.

    Each item is normalized to `{call_id, name, arguments}`. Returns an empty
    list when the model produced only a text answer.
    """

    calls: list[dict[str, Any]] = []
    raw_calls = _safe_getattr(response, "function_calls")
    if isinstance(raw_calls, list):
        for call in cast(list[Any], raw_calls):
            name = _safe_getattr(call, "name")
            if not isinstance(name, str):
                continue
            call_id = _safe_getattr(call, "id")
            args = _safe_getattr(call, "args")
            calls.append(
                {
                    "call_id": call_id if isinstance(call_id, str) else None,
                    "name": name,
                    "arguments": args if isinstance(args, dict) else {},
                }
            )
        return calls

    content = _first_candidate_content(response)
    parts = _safe_getattr(content, "parts")
    if not isinstance(parts, list):
        return []
    for part in cast(list[Any], parts):
        function_call = _safe_getattr(part, "function_call")
        if function_call is None:
            continue
        name = _safe_getattr(function_call, "name")
        if not isinstance(name, str):
            continue
        call_id = _safe_getattr(function_call, "id")
        args = _safe_getattr(function_call, "args")
        calls.append(
            {
                "call_id": call_id if isinstance(call_id, str) else None,
                "name": name,
                "arguments": args if isinstance(args, dict) else {},
            }
        )
    return calls


def _first_candidate_content(response: Any) -> Any:
    candidates = _safe_getattr(response, "candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    return _safe_getattr(candidates[0], "content")


def _safe_getattr(value: Any, name: str) -> Any:
    try:
        return getattr(value, name, None)
    except Exception:
        return None


async def _run_llm_agent(payload: AgentChatRequest) -> AgentChatResponse | None:
    """Drive Fred via Gemini function calling; return None on any error.

    The loop is bounded by `_MAX_TOOL_ITERATIONS` to cap latency. After the cap
    we force a final text reply by calling once more without tools. Any
    exception falls through to the deterministic path.
    """

    settings = get_settings()
    if not (settings.gemini_enabled and settings.gemini_api_key):
        return None

    model = settings.gemini_model
    api_key = settings.gemini_api_key

    last_search_request: SearchRequest | None = None
    last_search_response: SearchResponse | None = None
    tool_iterations = 0

    try:
        # Lazy import keeps the Gemini client out of the deterministic test path.
        from google import genai
        from google.genai import types

        client: Any = genai.Client(api_key=api_key)
        contents = _build_gemini_contents(payload, types)
        tools_enabled = True

        while True:
            config_kwargs: dict[str, Any] = {
                "system_instruction": _FRED_SYSTEM_PROMPT,
                "max_output_tokens": _LLM_MAX_OUTPUT_TOKENS,
                # The configured model is a thinking model. At its default budget
                # a single turn took ~18s, blowing the per-call timeout and
                # forcing the deterministic fallback. "low" keeps the quality but
                # roughly thirds the latency so both tool turns finish in time.
                "thinking_config": _thinking_config(types),
            }
            if tools_enabled:
                config_kwargs["tools"] = [
                    types.Tool(
                        function_declarations=cast(
                            Any,
                            [_SEARCH_SITES_DECLARATION, _EXPLAIN_SITE_DECLARATION],
                        )
                    )
                ]
                config_kwargs["automatic_function_calling"] = (
                    types.AutomaticFunctionCallingConfig(disable=True)
                )

            response: Any = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(**config_kwargs),
                ),
                timeout=_LLM_TIMEOUT_S,
            )
            calls = _extract_function_calls(response)

            if not calls:
                text = extract_response_text(response)
                if not text:
                    logger.warning(
                        "agent.empty_response",
                        extra={"event": "agent.empty_response", "model": model},
                    )
                    return None
                action = _build_action(last_search_request, last_search_response)
                return AgentChatResponse(
                    source="gemini",
                    model=model,
                    message=text,
                    action=action,
                    cache_key=build_cache_key(
                        "agent.chat.llm",
                        payload.message,
                        payload.selected_cell_id,
                        payload.power_mw,
                        payload.workload_type,
                        payload.history,
                        last_search_request,
                    ),
                )

            tool_iterations += 1

            response_content = _first_candidate_content(response)
            if response_content is None:
                logger.warning(
                    "agent.empty_response",
                    extra={"event": "agent.empty_response", "model": model},
                )
                return None
            contents.append(response_content)

            for call in calls:
                tool_output: dict[str, Any]
                if call["name"] == "search_sites":
                    request = _build_search_request_from_args(payload, call["arguments"])
                    try:
                        engine_response = search_site_cells(request)
                    except Exception as exc:
                        tool_output = {"error": type(exc).__name__}
                    else:
                        last_search_request = request
                        last_search_response = engine_response
                        tool_output = _summarize_search_for_tool(request, engine_response)
                elif call["name"] == "explain_site":
                    cell_id = call["arguments"].get("cell_id")
                    if not isinstance(cell_id, str) or not cell_id:
                        tool_output = {"error": "missing_cell_id"}
                    else:
                        explain_request = ExplainRequest(
                            cell_id=cell_id,
                            power_mw=float(
                                call["arguments"].get("power_mw", payload.power_mw)
                            ),
                            workload_type=call["arguments"].get(
                                "workload_type", payload.workload_type
                            )
                            if call["arguments"].get("workload_type") in _WORKLOAD_TERMS
                            else payload.workload_type,
                        )
                        try:
                            explanation = await explain_site(explain_request)
                            tool_output = {"message": explanation.message}
                        except KeyError:
                            tool_output = {"error": "unknown_cell"}
                else:
                    tool_output = {"error": "unknown_tool"}

                function_response_kwargs: dict[str, Any] = {
                    "name": call["name"],
                    "response": tool_output,
                }
                if call["call_id"] is not None:
                    function_response_kwargs["id"] = call["call_id"]
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    **function_response_kwargs
                                )
                            )
                        ],
                    )
                )

            if tool_iterations >= _MAX_TOOL_ITERATIONS:
                # Force a final text reply by removing tools from the next call.
                tools_enabled = False

    except Exception as exc:
        logger.warning(
            "agent.fallback",
            extra={
                "event": "agent.fallback",
                "reason": type(exc).__name__,
                "model": model,
            },
        )
        return None


def _build_action(
    request: SearchRequest | None,
    response: SearchResponse | None,
) -> AgentAction:
    if request is None or response is None:
        return AgentAction(type="none")
    focus_cell_id = response.results[0].site.cell_id if response.results else None
    return AgentAction(
        type="search",
        search=response,
        focus_cell_id=focus_cell_id,
        applied=request,
    )


async def _deterministic_chat(payload: AgentChatRequest) -> AgentChatResponse:
    """Keyword-driven fallback path. Demo-safe; no LLM required."""

    text = payload.message.lower()
    if _is_selected_detail_question(payload, text):
        try:
            explanation = await explain_site(
                ExplainRequest(
                    cell_id=payload.selected_cell_id or "",
                    power_mw=payload.power_mw,
                    workload_type=payload.workload_type,
                )
            )
        except KeyError:
            explanation = None

        if explanation is not None:
            return AgentChatResponse(
                source=explanation.source,
                model=explanation.model,
                message=explanation.message,
                action=AgentAction(type="none"),
                cache_key=build_cache_key(
                    "agent.chat.detail",
                    payload.message,
                    payload.selected_cell_id,
                    payload.power_mw,
                    payload.workload_type,
                    payload.history,
                ),
            )

    if not _has_search_intent(text):
        return AgentChatResponse(
            source="template",
            model=None,
            message=_conversation_message(text),
            action=AgentAction(type="none"),
            cache_key=build_cache_key(
                "agent.chat.conversation",
                payload.message,
                payload.selected_cell_id,
                payload.history,
            ),
        )

    request = _build_search_request(payload)
    search = search_site_cells(request)
    top = search.results[0] if search.results else None
    focus_cell_id = top.site.cell_id if top else None
    cache_key = build_cache_key("agent.chat", request, payload.message, payload.history)

    message = _deterministic_message(request, search, top)
    source: ExplainSource = "template"
    model: str | None = None

    settings = get_settings()
    if settings.gemini_enabled and settings.gemini_api_key:
        live = await _try_gemini_chat(
            payload,
            request,
            search,
            top,
            settings.gemini_api_key,
            settings.gemini_model,
        )
        if live is not None:
            message = live
            source = "gemini"
            model = settings.gemini_model

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


async def chat(payload: AgentChatRequest) -> AgentChatResponse:
    """Return Fred's reply plus any dashboard action the UI should apply.

    Prefers the LLM tool-calling agent when configured; falls back to the
    deterministic regex parser on any error or when the LLM is disabled.
    """

    settings = get_settings()
    if settings.gemini_enabled and settings.gemini_api_key:
        live = await _run_llm_agent(payload)
        if live is not None:
            return live
    return await _deterministic_chat(payload)
