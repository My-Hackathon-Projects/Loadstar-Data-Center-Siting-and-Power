import { describe, expect, it } from "vitest";

import type { LayerResponse, RankedSite, SiteFeature } from "../../types/api";
import {
  MAP_LAYER_OPTIONS,
  buildLayerCells,
  formatLayerValue,
  layerFillColor,
} from "./mapLayers";

const site: SiteFeature = {
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
  latitude: 65.5848,
  lightgbm_score: 0.79,
  longitude: 22.1547,
  mean_price_eur_mwh: 34,
  price_volatility: 17,
  region_name: "Lulea / Boden",
  resolution: 5,
  shap_values: { headroom_mw: 0.22 },
  solar_cf: 0.1,
  water_dist_km: 3.4,
  wind_cf: 0.42,
};

const rankedSite: RankedSite = {
  composite_score: 0.8214,
  score_breakdown: {},
  score_contributions: {},
  score_explanations: [],
  site,
};

const layer: LayerResponse = {
  cache_key: "layers:headroom_mw",
  features: [
    {
      geometry: { coordinates: [site.longitude, site.latitude], type: "Point" },
      properties: {
        ...site,
        layer_name: "headroom_mw",
        layer_value: 540,
      },
      type: "Feature",
    },
  ],
  type: "FeatureCollection",
};

describe("map layer helpers", () => {
  it("keeps the map layer option set aligned with the demo controls", () => {
    expect(MAP_LAYER_OPTIONS.map((option) => option.name)).toEqual([
      "composite_score",
      "mean_price_eur_mwh",
      "carbon_intensity_g_kwh",
      "congestion_index",
      "headroom_mw",
      "buildable_fraction",
    ]);
  });

  it("builds H3 layer cells from GeoJSON layers and search rankings", () => {
    const [cell] = buildLayerCells("headroom_mw", layer, [rankedSite]);

    expect(cell).toMatchObject({
      cellId: site.cell_id,
      hexagon: site.cell_id,
      isRanked: true,
      regionName: site.region_name,
      score: rankedSite.composite_score,
      value: 540,
    });
  });

  it("falls back to ranked search rows before the layer request resolves", () => {
    const [cell] = buildLayerCells("composite_score", undefined, [rankedSite]);

    expect(cell.value).toBe(0.8214);
    expect(cell.isRanked).toBe(true);
  });

  it("returns stable RGBA colors and display values", () => {
    expect(layerFillColor("carbon_intensity_g_kwh", 24, true)).toHaveLength(4);
    expect(layerFillColor("carbon_intensity_g_kwh", 24, true)[3]).toBe(210);
    expect(formatLayerValue("buildable_fraction", 0.72)).toBe("72%");
    expect(formatLayerValue("mean_price_eur_mwh", 34)).toBe("34 EUR/MWh");
  });
});
