import { describe, expect, it } from "vitest";

import type { RankedSite, SiteFeature, SupplyMixResponse } from "../../types/api";
import { buildStatCards, STAT_PLACEHOLDER, type StatCard } from "./statCards";

const BASE_SITE: SiteFeature = {
  buildable_fraction: 0.72,
  carbon_intensity_g_kwh: 24,
  cell_id: "851f25d7fffffff",
  congestion_index: 0.22,
  cooling_degree_proxy: 0.18,
  country_code: "SE",
  dc_similarity: 0.81,
  dist_fiber_km: 18.4,
  dist_hv_substation_km: 7.2,
  dist_ixp_km: 710,
  exclusion_flag: false,
  headroom_mw: 540,
  latency_proxy_ms: 14.8,
  latitude: 65.58,
  lightgbm_score: 0.79,
  longitude: 22.15,
  mean_price_eur_mwh: 34,
  price_volatility: 17,
  region_name: "Lulea / Boden",
  resolution: 5,
  shap_values: { headroom_mw: 0.22 },
  solar_cf: 0.1,
  water_dist_km: 3.4,
  wind_cf: 0.42,
};

function rankedSite(overrides: {
  cell_id: string;
  composite_score: number;
  price: number;
  carbon: number;
  headroom: number;
}): RankedSite {
  return {
    site: {
      ...BASE_SITE,
      cell_id: overrides.cell_id,
      mean_price_eur_mwh: overrides.price,
      carbon_intensity_g_kwh: overrides.carbon,
      headroom_mw: overrides.headroom,
    },
    composite_score: overrides.composite_score,
    score_breakdown: {},
    score_contributions: {},
    score_explanations: [],
  };
}

const SUPPLY_MIX: SupplyMixResponse = {
  annual_matched_clean_share: 0.5,
  cache_key: "",
  cell_id: "851f25d7fffffff",
  data_mode: "fixture",
  dispatch_preview: [],
  dispatch_summary: {},
  effective_carbon_g_kwh: 20,
  effective_cost_eur_mwh: 41,
  hourly_24_7_cfe_share: 0.95,
  load_mw: 280,
  load_profile: "flat_24_7",
  optimization_horizon_hours: 24,
  pareto_frontier: [],
  recommended_portfolio: {},
  solver_status: "optimal",
};

function byKey(cards: StatCard[]): Record<string, StatCard> {
  return Object.fromEntries(cards.map((card) => [card.key, card]));
}

describe("buildStatCards", () => {
  it("shows placeholders when there are no results", () => {
    const cards = byKey(buildStatCards([], undefined));
    expect(cards.candidates.value).toBe("0");
    expect(cards["top-score"].value).toBe(STAT_PLACEHOLDER);
    expect(cards.price.value).toBe(STAT_PLACEHOLDER);
    expect(cards["effective-cost"].value).toBe(STAT_PLACEHOLDER);
    expect(cards["cfe-share"].value).toBe(STAT_PLACEHOLDER);
  });

  it("formats the search-derived cards with vs-field deltas", () => {
    const results = [
      rankedSite({ cell_id: "a", composite_score: 0.93, price: 34, carbon: 24, headroom: 540 }),
      rankedSite({ cell_id: "b", composite_score: 0.6, price: 40, carbon: 60, headroom: 300 }),
    ];
    const cards = byKey(buildStatCards(results, undefined));

    expect(cards.candidates.value).toBe("2");
    expect(cards["top-score"].value).toBe("93%");
    expect(cards.price.value).toBe("34 EUR/MWh");
    expect(cards.carbon.value).toBe("24 gCO2/kWh");
    expect(cards.headroom.value).toBe("540 MW");

    // Top carbon (24) is below the field mean (42) — lower is better → positive.
    expect(cards.carbon.delta?.tone).toBe("positive");
    // Top headroom (540) is above the field mean (420) — higher is better → positive.
    expect(cards.headroom.delta?.tone).toBe("positive");
    // Optimizer-derived cards remain placeholders until the optimizer runs.
    expect(cards["effective-cost"].value).toBe(STAT_PLACEHOLDER);
  });

  it("fills the optimizer cards once supply mix is available", () => {
    const results = [
      rankedSite({ cell_id: "a", composite_score: 0.93, price: 34, carbon: 24, headroom: 540 }),
    ];
    const cards = byKey(buildStatCards(results, SUPPLY_MIX));

    expect(cards["effective-cost"].value).toBe("41 EUR/MWh");
    expect(cards["cfe-share"].value).toBe("95%");
    expect(cards["cfe-share"].delta?.tone).toBe("positive");
  });
});
