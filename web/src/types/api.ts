export interface SiteFeature {
  cell_id: string;
  country_code: string;
  region_name: string;
  latitude: number;
  longitude: number;
  resolution: number;
  mean_price_eur_mwh: number;
  price_volatility: number;
  carbon_intensity_g_kwh: number;
  congestion_index: number;
  headroom_mw: number;
  dist_hv_substation_km: number;
  dist_fiber_km: number;
  dist_ixp_km: number;
  latency_proxy_ms: number;
  solar_cf: number;
  wind_cf: number;
  water_dist_km: number;
  cooling_degree_proxy: number;
  buildable_fraction: number;
  dc_similarity: number;
  lightgbm_score: number;
  shap_values: Record<string, number>;
  exclusion_flag: boolean;
}

export interface ScaleWarning {
  code: string;
  message: string;
}

export interface RankedSite {
  site: SiteFeature;
  composite_score: number;
  score_breakdown: Record<string, number>;
}

export interface SearchResponse {
  data_mode: "fixture";
  requested_power_mw: number;
  workload_type: string;
  warnings: ScaleWarning[];
  results: RankedSite[];
}

export interface SearchRequest {
  power_mw: number;
  workload_type: "training" | "inference" | "mixed";
  top_k: number;
}

export interface SiteDetailResponse {
  data_mode: "fixture";
  site: SiteFeature;
}

export interface OptimizeRequest {
  cell_id: string;
  load_mw: number;
  load_profile: "flat_24_7" | "spiky_training";
}

export interface ParetoPoint {
  carbon_cap_g_kwh: number | null;
  effective_cost_eur_mwh: number;
  effective_carbon_g_kwh: number;
  grid_share: number;
  wind_ppa_share: number;
  solar_ppa_share: number;
  onsite_solar_share: number;
  battery_shifted_share: number;
}

export interface SupplyMixResponse {
  data_mode: "fixture";
  cell_id: string;
  load_mw: number;
  load_profile: string;
  recommended_portfolio: Record<string, number>;
  effective_cost_eur_mwh: number;
  effective_carbon_g_kwh: number;
  annual_matched_clean_share: number;
  hourly_24_7_cfe_share: number;
  pareto_frontier: ParetoPoint[];
  dispatch_preview: Array<Record<string, number>>;
}
