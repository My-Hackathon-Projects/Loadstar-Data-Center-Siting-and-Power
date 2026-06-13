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

export interface ScoreExplanation {
  factor: string;
  score: number;
  weight: number;
  contribution: number;
  raw_value: string;
  direction: "lower_is_better" | "higher_is_better" | "composite";
}

export interface RankedSite {
  site: SiteFeature;
  composite_score: number;
  score_breakdown: Record<string, number>;
  score_contributions: Record<string, number>;
  score_explanations: ScoreExplanation[];
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
  carbon_cap_g_kwh?: number | null;
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
  backup_share: number;
  curtailment_share: number;
}

export interface DispatchSummary {
  total_load_mwh: number;
  total_grid_mwh: number;
  total_wind_ppa_mwh: number;
  total_solar_ppa_mwh: number;
  total_onsite_solar_mwh: number;
  total_backup_mwh: number;
  total_battery_charge_mwh: number;
  total_battery_discharge_mwh: number;
  total_curtailment_mwh: number;
  wind_ppa_capacity_mw: number;
  solar_ppa_capacity_mw: number;
  onsite_solar_capacity_mw: number;
  battery_power_capacity_mw: number;
  battery_energy_capacity_mwh: number;
  backup_capacity_mw: number;
  grid_limit_mw: number;
}

export interface DispatchPreviewRow {
  hour: number;
  load_mw: number;
  grid_mw: number;
  wind_ppa_mw: number;
  solar_ppa_mw: number;
  onsite_solar_mw: number;
  battery_charge_mw: number;
  battery_discharge_mw: number;
  battery_soc_mwh: number;
  backup_mw: number;
  curtailment_mw: number;
}

export interface SupplyMixResponse {
  data_mode: "fixture";
  cell_id: string;
  load_mw: number;
  load_profile: string;
  solver_status: string;
  optimization_horizon_hours: number;
  recommended_portfolio: Record<string, number>;
  effective_cost_eur_mwh: number;
  effective_carbon_g_kwh: number;
  annual_matched_clean_share: number;
  hourly_24_7_cfe_share: number;
  pareto_frontier: ParetoPoint[];
  dispatch_summary: DispatchSummary;
  dispatch_preview: DispatchPreviewRow[];
}
