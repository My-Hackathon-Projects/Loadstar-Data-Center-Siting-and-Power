import type { MapLayerName } from "../features/map/mapLayers";
import type { OptimizeRequest, SearchRequest } from "../types/api";

export const DEFAULT_ACTIVE_LAYER: MapLayerName = "composite_score";
export const DEFAULT_DEMO_POWER_MW = 280;
export const DEFAULT_LOAD_PROFILE: OptimizeRequest["load_profile"] =
  "flat_24_7";
export const DEFAULT_SEARCH_TOP_K = 8;
export const DEFAULT_WORKLOAD_TYPE: SearchRequest["workload_type"] =
  "training";
