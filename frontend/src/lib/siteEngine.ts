/**
 * Client-side port of the backend ranking engine
 * (`backend/engine/scoring.py` + `normalization.py`).
 *
 * The deployed SPA is a static site with no API origin, so the read path
 * (search, detail, compare) runs in the browser against the committed
 * `public/data/sites.json` dataset. This module is the single source of that
 * logic on the client.
 *
 * It is kept in lockstep with the Python engine by a golden test
 * (`siteEngine.test.ts`) that re-derives the composite-score map layer and
 * asserts it matches the committed `public/layers/composite_score.json` the
 * backend generated. Change the Python scoring and this must move with it.
 */

import { DEFAULT_WEIGHTS } from "../config/defaults";
import type {
  CompareRequest,
  CompareResponse,
  RankedSite,
  ScaleWarning,
  ScoreExplanation,
  SearchRequest,
  SearchResponse,
  SiteDetailResponse,
  SiteFeature,
  Weights,
} from "../types/api";

// Mirrors backend.engine.assumptions.scale_bands. Update both together.
const SMALL_MW_THRESHOLD = 20;
const LARGE_MW_THRESHOLD = 700;
const SMALL_WARNING = "Below roughly 20 MW, headroom rarely binds in this model.";
const LARGE_WARNING =
  "Above roughly 700 MW, a single connection point is unrealistic; " +
  "use multi-connection campus planning.";

// Mirrors backend.engine.normalization defaults.
const LOWER_PERCENTILE = 5;
const UPPER_PERCENTILE = 95;

type Direction = "lower_is_better" | "higher_is_better" | "composite";

const clamp01 = (value: number): number => Math.min(Math.max(value, 0), 1);

/** Linearly interpolated percentile over finite values; matches numpy-free Python. */
function percentile(values: number[], pct: number): number {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (sorted.length === 0) {
    throw new Error("Cannot compute percentile of an empty finite sequence.");
  }
  if (sorted.length === 1) {
    return sorted[0];
  }
  const position = ((sorted.length - 1) * pct) / 100;
  const lowerIndex = Math.floor(position);
  const upperIndex = Math.min(lowerIndex + 1, sorted.length - 1);
  const fraction = position - lowerIndex;
  return sorted[lowerIndex] + (sorted[upperIndex] - sorted[lowerIndex]) * fraction;
}

interface ClippingBounds {
  lower: number;
  upper: number;
}

function percentileBounds(values: number[]): ClippingBounds {
  return {
    lower: percentile(values, LOWER_PERCENTILE),
    upper: percentile(values, UPPER_PERCENTILE),
  };
}

function normalizeValue(value: number, bounds: ClippingBounds, lowerIsBetter: boolean): number {
  if (!Number.isFinite(value)) {
    return 0; // missing_score
  }
  if (bounds.upper === bounds.lower) {
    return 1; // degenerate_score
  }
  const clipped = Math.min(Math.max(value, bounds.lower), bounds.upper);
  const normalized = (clipped - bounds.lower) / (bounds.upper - bounds.lower);
  return clamp01(lowerIsBetter ? 1 - normalized : normalized);
}

/** Banker's rounding to N decimals to match Python's round(). */
function roundTo(value: number, digits: number): number {
  const factor = 10 ** digits;
  const scaled = value * factor;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  const epsilon = 1e-9;
  let rounded: number;
  if (Math.abs(diff - 0.5) < epsilon) {
    rounded = floor % 2 === 0 ? floor : floor + 1;
  } else {
    rounded = Math.round(scaled);
  }
  return rounded / factor;
}

type FieldName = keyof Pick<
  SiteFeature,
  | "mean_price_eur_mwh"
  | "carbon_intensity_g_kwh"
  | "congestion_index"
  | "headroom_mw"
  | "dist_hv_substation_km"
  | "dist_fiber_km"
  | "dist_ixp_km"
  | "latency_proxy_ms"
  | "buildable_fraction"
  | "dc_similarity"
  | "lightgbm_score"
>;

function fieldScore(
  site: SiteFeature,
  candidates: SiteFeature[],
  field: FieldName,
  lowerIsBetter: boolean,
): number {
  const bounds = percentileBounds(candidates.map((candidate) => candidate[field]));
  return normalizeValue(site[field], bounds, lowerIsBetter);
}

const average = (values: number[]): number =>
  values.reduce((sum, value) => sum + value, 0) / values.length;

interface ScoreFactor {
  name: keyof Weights;
  direction: Direction;
  score: (site: SiteFeature, candidates: SiteFeature[]) => number;
  rawValue: (site: SiteFeature) => string;
}

const pct0 = (value: number): string => `${Math.round(value * 100)}%`;

// Factor order is part of the contract (drives the explanations list).
const SCORE_FACTORS: ScoreFactor[] = [
  {
    name: "price",
    direction: "lower_is_better",
    score: (site, candidates) => fieldScore(site, candidates, "mean_price_eur_mwh", true),
    rawValue: (site) => `${Math.round(site.mean_price_eur_mwh)} EUR/MWh`,
  },
  {
    name: "carbon",
    direction: "lower_is_better",
    score: (site, candidates) => fieldScore(site, candidates, "carbon_intensity_g_kwh", true),
    rawValue: (site) => `${Math.round(site.carbon_intensity_g_kwh)} gCO2/kWh`,
  },
  {
    name: "congestion",
    direction: "lower_is_better",
    score: (site, candidates) => fieldScore(site, candidates, "congestion_index", true),
    rawValue: (site) => `${site.congestion_index.toFixed(2)} congestion index`,
  },
  {
    name: "grid",
    direction: "lower_is_better",
    score: (site, candidates) => fieldScore(site, candidates, "dist_hv_substation_km", true),
    rawValue: (site) => `${site.dist_hv_substation_km.toFixed(1)} km to HV substation`,
  },
  {
    name: "connectivity",
    direction: "composite",
    score: (site, candidates) =>
      average([
        fieldScore(site, candidates, "dist_fiber_km", true),
        fieldScore(site, candidates, "dist_ixp_km", true),
        fieldScore(site, candidates, "latency_proxy_ms", true),
      ]),
    rawValue: (site) =>
      `${site.dist_fiber_km.toFixed(1)} km fiber / ` +
      `${site.dist_ixp_km.toFixed(1)} km IXP / ${site.latency_proxy_ms.toFixed(1)} ms`,
  },
  {
    name: "land",
    direction: "composite",
    score: (site, candidates) =>
      average([
        fieldScore(site, candidates, "buildable_fraction", false),
        fieldScore(site, candidates, "dc_similarity", false),
      ]),
    rawValue: (site) =>
      `${pct0(site.buildable_fraction)} buildable / ${pct0(site.dc_similarity)} data-center similarity`,
  },
  {
    name: "ml",
    direction: "higher_is_better",
    score: (site, candidates) => fieldScore(site, candidates, "lightgbm_score", false),
    rawValue: (site) => `${pct0(site.lightgbm_score)} ML viability`,
  },
];

function resolveWeights(request: SearchRequest): Weights {
  return request.weights ?? DEFAULT_WEIGHTS;
}

function scaleWarnings(powerMw: number): ScaleWarning[] {
  const warnings: ScaleWarning[] = [];
  if (powerMw < SMALL_MW_THRESHOLD) {
    warnings.push({ code: "small_load", message: SMALL_WARNING });
  }
  if (powerMw > LARGE_MW_THRESHOLD) {
    warnings.push({ code: "large_load", message: LARGE_WARNING });
  }
  return warnings;
}

export function eligibleSites(request: SearchRequest, sites: SiteFeature[]): SiteFeature[] {
  const countries = new Set((request.country_filter ?? []).map((code) => code.toUpperCase()));
  return sites.filter(
    (site) =>
      !site.exclusion_flag &&
      site.headroom_mw >= request.power_mw &&
      (countries.size === 0 || countries.has(site.country_code)),
  );
}

function scoreSite(
  site: SiteFeature,
  candidates: SiteFeature[],
  weights: Weights,
): RankedSite {
  const breakdown: Record<string, number> = {};
  const contributions: Record<string, number> = {};
  const explanations: ScoreExplanation[] = [];

  for (const factor of SCORE_FACTORS) {
    const score = roundTo(factor.score(site, candidates), 4);
    const weight = weights[factor.name];
    const contribution = roundTo(score * weight, 4);
    breakdown[factor.name] = score;
    contributions[factor.name] = contribution;
    explanations.push({
      factor: factor.name,
      score,
      weight,
      contribution,
      raw_value: factor.rawValue(site),
      direction: factor.direction,
    });
  }

  const composite = roundTo(
    Object.values(contributions).reduce((sum, value) => sum + value, 0),
    4,
  );
  return {
    site,
    composite_score: composite,
    score_breakdown: breakdown,
    score_contributions: contributions,
    score_explanations: explanations,
  };
}

/** Every eligible site ranked best-first, ignoring top_k (mirrors rank_sites). */
export function rankSites(request: SearchRequest, sites: SiteFeature[]): RankedSite[] {
  const candidates = eligibleSites(request, sites);
  const weights = resolveWeights(request);
  return candidates
    .map((site) => scoreSite(site, candidates, weights))
    .sort(
      (left, right) =>
        right.composite_score - left.composite_score ||
        left.site.mean_price_eur_mwh - right.site.mean_price_eur_mwh ||
        left.site.cell_id.localeCompare(right.site.cell_id),
    );
}

export function searchSitesLocal(request: SearchRequest, sites: SiteFeature[]): SearchResponse {
  const ranked = rankSites(request, sites);
  const topK = request.top_k ?? 10;
  return {
    data_mode: "fixture",
    cache_key: "",
    requested_power_mw: request.power_mw,
    workload_type: request.workload_type ?? "training",
    warnings: scaleWarnings(request.power_mw),
    results: ranked.slice(0, topK),
  };
}

export function getSiteLocal(cellId: string, sites: SiteFeature[]): SiteDetailResponse {
  const site = sites.find((candidate) => candidate.cell_id === cellId);
  if (!site) {
    throw new Error(`Unknown site cell: ${cellId}`);
  }
  return { data_mode: "fixture", cache_key: "", site };
}

export function compareSitesLocal(
  request: CompareRequest,
  sites: SiteFeature[],
): CompareResponse {
  const byId = new Map(sites.map((site) => [site.cell_id, site]));
  const selected = request.cell_ids.map((cellId) => {
    const site = byId.get(cellId);
    if (!site) {
      throw new Error(`Unknown site cell: ${cellId}`);
    }
    return site;
  });
  return { data_mode: "fixture", cache_key: "", sites: selected };
}
