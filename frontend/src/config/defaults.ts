import type { MapLayerName } from "../features/map/mapLayers";
import type { OptimizeRequest, SearchRequest, Weights } from "../types/api";

export const DEFAULT_ACTIVE_LAYER: MapLayerName = "composite_score";
export const DEFAULT_DEMO_POWER_MW = 280;
export const DEFAULT_LOAD_PROFILE: OptimizeRequest["load_profile"] = "flat_24_7";
export const DEFAULT_SEARCH_TOP_K = 8;
export const DEFAULT_WORKLOAD_TYPE: SearchRequest["workload_type"] = "training";

/**
 * Scoring weights exposed as sliders in the specifications bar. Mirrors the
 * Pydantic `Weights` defaults in `engine.contracts`; the search endpoint accepts
 * these as an optional field, so adjusting them is within the existing contract.
 */
export const DEFAULT_WEIGHTS: Weights = {
  carbon: 0.24,
  congestion: 0.18,
  connectivity: 0.1,
  grid: 0.14,
  land: 0.08,
  ml: 0.08,
  price: 0.18,
};

/** Order and human labels for the weight sliders. */
export const WEIGHT_FACTORS: ReadonlyArray<{
  key: keyof Weights;
  label: string;
}> = [
  { key: "carbon", label: "carbon" },
  { key: "price", label: "price" },
  { key: "congestion", label: "congestion" },
  { key: "grid", label: "grid" },
  { key: "connectivity", label: "connectivity" },
  { key: "land", label: "land" },
  { key: "ml", label: "ml viability" },
];

/**
 * Country filter options exposed in the specifications bar. Covers every market
 * in the served dataset (`backend/engine/data/europe_sites.json`); keep in sync
 * when the dataset's country set changes. Sorted by display label.
 */
export const COUNTRY_FILTER_OPTIONS: ReadonlyArray<{
  code: string;
  label: string;
}> = [
  { code: "AT", label: "Austria" },
  { code: "BE", label: "Belgium" },
  { code: "BG", label: "Bulgaria" },
  { code: "HR", label: "Croatia" },
  { code: "CZ", label: "Czechia" },
  { code: "DK", label: "Denmark" },
  { code: "EE", label: "Estonia" },
  { code: "FI", label: "Finland" },
  { code: "FR", label: "France" },
  { code: "DE", label: "Germany" },
  { code: "GR", label: "Greece" },
  { code: "HU", label: "Hungary" },
  { code: "IS", label: "Iceland" },
  { code: "IE", label: "Ireland" },
  { code: "IT", label: "Italy" },
  { code: "LV", label: "Latvia" },
  { code: "LT", label: "Lithuania" },
  { code: "LU", label: "Luxembourg" },
  { code: "NL", label: "Netherlands" },
  { code: "NO", label: "Norway" },
  { code: "PL", label: "Poland" },
  { code: "PT", label: "Portugal" },
  { code: "RO", label: "Romania" },
  { code: "RS", label: "Serbia" },
  { code: "SK", label: "Slovakia" },
  { code: "SI", label: "Slovenia" },
  { code: "ES", label: "Spain" },
  { code: "SE", label: "Sweden" },
  { code: "CH", label: "Switzerland" },
  { code: "GB", label: "United Kingdom" },
];

/**
 * Workload-type options exposed in SearchPanel. The Pydantic Literal in
 * `engine.contracts.SearchRequest.workload_type` enforces the allowed values
 * server-side; this list is the matching client menu.
 */
export const WORKLOAD_TYPE_OPTIONS: ReadonlyArray<{
  value: SearchRequest["workload_type"];
  label: string;
}> = [
  { value: "training", label: "Training" },
  { value: "inference", label: "Inference" },
  { value: "mixed", label: "Mixed" }
];

/**
 * Result-count options exposed in SearchPanel. The API caps `top_k` at 50
 * (validator on `engine.contracts.SearchRequest.top_k`); these are the
 * sensible demo presets.
 */
export const SEARCH_TOP_K_OPTIONS: readonly number[] = [5, 8, 10] as const;

/**
 * Load-profile options exposed in OptimizerPanel. Mirrors the Pydantic
 * Literal in `engine.contracts.OptimizeRequest.load_profile`.
 */
export const LOAD_PROFILE_OPTIONS: ReadonlyArray<{
  value: OptimizeRequest["load_profile"];
  label: string;
}> = [
  { value: "flat_24_7", label: "Flat 24/7" },
  { value: "spiky_training", label: "Spiky training" }
];
