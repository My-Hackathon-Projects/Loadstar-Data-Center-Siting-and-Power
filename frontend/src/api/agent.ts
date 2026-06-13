import { DEFAULT_SEARCH_TOP_K } from "../config/defaults";
import { getSiteLocal, searchSitesLocal } from "../lib/siteEngine";
import type {
  AgentChatRequest,
  AgentChatResponse,
  ExplainRequest,
  ExplainResponse,
  SearchRequest,
} from "../types/api";
import { requestJson } from "./client";
import { isApiReachable } from "./dataSource";
import { loadSites } from "./staticData";

/**
 * Fred and the per-site explanation are LLM-backed on the live API. On the
 * static deployment there is no LLM, so we degrade deterministically:
 *  - chat still runs the real (in-browser) engine search and drives the map,
 *    with a message that conversational AI needs the live engine;
 *  - explain returns a transparent template built from the site's own metrics.
 */

const STATIC_CHAT_NOTE =
  "I cannot chat live on this static deployment, but here are the strongest " +
  "sites for your target. Use the controls on the left to refine by country, " +
  "price, or carbon.";

/** POST `/agent/explain` and return the LLM-or-template explanation payload. */
export async function explainSite(payload: ExplainRequest): Promise<ExplainResponse> {
  if (await isApiReachable()) {
    return requestJson<ExplainResponse>("/agent/explain", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  const { site } = getSiteLocal(payload.cell_id, await loadSites());
  const message =
    `${site.region_name} (${site.country_code}) offers ` +
    `${Math.round(site.carbon_intensity_g_kwh)} gCO2/kWh grid carbon, ` +
    `${Math.round(site.mean_price_eur_mwh)} EUR/MWh wholesale power, and ` +
    `${Math.round(site.headroom_mw)} MW of grid headroom. ` +
    `Land viability scores ${Math.round(site.lightgbm_score * 100)}%. ` +
    "Connect the live engine for a full narrative and supply-mix optimization.";
  return {
    source: "template",
    model: null,
    cell_id: payload.cell_id,
    message,
    cache_key: "",
  };
}

/** POST `/agent/chat`: Fred runs a real search and returns a dashboard action. */
export async function chatAgent(payload: AgentChatRequest): Promise<AgentChatResponse> {
  if (await isApiReachable()) {
    return requestJson<AgentChatResponse>("/agent/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  const request: SearchRequest = {
    power_mw: payload.power_mw,
    workload_type: payload.workload_type,
    top_k: DEFAULT_SEARCH_TOP_K,
  };
  const search = searchSitesLocal(request, await loadSites());
  const focus = search.results[0]?.site.cell_id ?? null;
  return {
    source: "template",
    model: null,
    message: STATIC_CHAT_NOTE,
    action: {
      type: search.results.length > 0 ? "search" : "none",
      search,
      focus_cell_id: focus,
      applied: request,
    },
    cache_key: "",
  };
}
