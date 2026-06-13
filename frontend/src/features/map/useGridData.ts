import { useQuery } from "@tanstack/react-query";
import type { Feature, Geometry } from "geojson";

import { API_BASE_URL } from "../../config/env";

/**
 * Per-feature properties for the static transmission grid GeoJSON, written
 * by `python3 -m backend.pipeline.pypsa_network`. The frontend only ever
 * reads these properties; nothing in the SPA computes voltage tiers at
 * render time.
 */
export type GridBusProperties = {
  kind: "bus";
  bus_id: string;
  voltage_kv: number;
  country: string;
  degree: number;
  connected_capacity_mva: number;
};

export type GridLineProperties = {
  kind: "line";
  line_id: string;
  voltage_kv: number;
  voltage_tier: "ehv" | "hv";
  capacity_mva: number;
  length_km: number;
  is_hvdc: boolean;
  is_cross_border: boolean;
  country0: string;
  country1: string;
};

export type GridFeatureProperties = GridBusProperties | GridLineProperties;

export interface GridGeoJson {
  type: "FeatureCollection";
  metadata: {
    artifact_version: string;
    source: string;
    bus_count: number;
    line_count: number;
    min_voltage_kv: number;
    ehv_threshold_kv: number;
  };
  features: Feature<Geometry, GridFeatureProperties>[];
}

// Served as `.json` rather than `.geojson` so the Vite dev-proxy bypass
// (which only matches `.json`) and the production FastAPI static-layer
// route (which only handles `*.json`) both serve it without a special
// case. Content is still a GeoJSON FeatureCollection -- deck.gl does
// not care about the URL extension.
const GRID_GEOJSON_PATH = "/layers/transmission_grid.json";

async function fetchGridGeoJson(): Promise<GridGeoJson | null> {
  const url = `${API_BASE_URL}${GRID_GEOJSON_PATH}`;
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      // 404 means the build pipeline has not produced the artifact yet --
      // the SPA must still render without the overlay. Caller treats null
      // as "grid feature absent", not an error worth surfacing to the UI.
      return null;
    }
    return (await response.json()) as GridGeoJson;
  } catch {
    return null;
  }
}

/**
 * Fetch the static PyPSA-Eur HV transmission grid GeoJSON. The hook stays
 * idle (no network) until `enabled` flips true (typically when the user
 * toggles the grid overlay on); the result is cached for the session via
 * react-query so toggling off and back on does not re-download.
 */
export function useGridData(enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: ["layers", "transmission_grid"],
    queryFn: fetchGridGeoJson,
    staleTime: 60 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });
}
