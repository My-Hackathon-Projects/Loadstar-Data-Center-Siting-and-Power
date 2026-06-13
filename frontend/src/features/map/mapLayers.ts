import type { LayerResponse, RankedSite } from "../../types/api";

type LayerDirection = "higher_is_better" | "lower_is_better";

interface MapLayerOption {
  name: string;
  label: string;
  shortLabel: string;
  unit: string;
  direction: LayerDirection;
  domain: readonly [number, number];
}

export const MAP_LAYER_OPTIONS = [
  {
    name: "composite_score",
    label: "Score",
    shortLabel: "Score",
    unit: "",
    direction: "higher_is_better",
    domain: [0, 1],
  },
  {
    name: "mean_price_eur_mwh",
    label: "Price",
    shortLabel: "EUR/MWh",
    unit: "EUR/MWh",
    direction: "lower_is_better",
    domain: [30, 110],
  },
  {
    name: "carbon_intensity_g_kwh",
    label: "Carbon",
    shortLabel: "gCO2/kWh",
    unit: "gCO2/kWh",
    direction: "lower_is_better",
    domain: [20, 430],
  },
  {
    name: "congestion_index",
    label: "Congestion",
    shortLabel: "Cong.",
    unit: "",
    direction: "lower_is_better",
    domain: [0, 1],
  },
  {
    name: "headroom_mw",
    label: "Headroom",
    shortLabel: "MW",
    unit: "MW",
    direction: "higher_is_better",
    domain: [100, 600],
  },
  {
    name: "buildable_fraction",
    label: "Buildable Land",
    shortLabel: "Land",
    unit: "",
    direction: "higher_is_better",
    domain: [0, 1],
  },
] as const satisfies readonly MapLayerOption[];

export type MapLayerName = (typeof MAP_LAYER_OPTIONS)[number]["name"];

export interface LayerCell {
  cellId: string;
  countryCode: string;
  hexagon: string;
  isRanked: boolean;
  latitude: number;
  longitude: number;
  regionName: string;
  score: number | null;
  value: number;
}

export function layerOption(
  layerName: MapLayerName,
): (typeof MAP_LAYER_OPTIONS)[number] {
  return (
    MAP_LAYER_OPTIONS.find((option) => option.name === layerName) ??
    MAP_LAYER_OPTIONS[0]
  );
}

export function buildLayerCells(
  layerName: MapLayerName,
  layer: LayerResponse | undefined,
  rankedSites: RankedSite[],
): LayerCell[] {
  const rankedByCell = new Map(
    rankedSites.map((result) => [result.site.cell_id, result.composite_score]),
  );

  if (!layer) {
    return rankedSites.map((result) => ({
      cellId: result.site.cell_id,
      countryCode: result.site.country_code,
      hexagon: result.site.cell_id,
      isRanked: true,
      latitude: result.site.latitude,
      longitude: result.site.longitude,
      regionName: result.site.region_name,
      score: result.composite_score,
      value: valueForRankedSite(layerName, result),
    }));
  }

  return layer.features.map((feature) => {
    const score = rankedByCell.get(feature.properties.cell_id) ?? null;
    return {
      cellId: feature.properties.cell_id,
      countryCode: feature.properties.country_code,
      hexagon: feature.properties.cell_id,
      isRanked: score !== null,
      latitude: feature.properties.latitude,
      longitude: feature.properties.longitude,
      regionName: feature.properties.region_name,
      score,
      value:
        layerName === "composite_score" && score !== null
          ? score
          : feature.properties.layer_value,
    };
  });
}

export function layerFillColor(
  layerName: MapLayerName,
  value: number,
  isRanked: boolean,
): [number, number, number, number] {
  const option = layerOption(layerName);
  const normalized = normalizeValue(value, option.domain, option.direction);
  const low = [224, 88, 64] as const;
  const mid = [241, 178, 74] as const;
  const high = [23, 126, 118] as const;
  const color =
    normalized < 0.5
      ? interpolateColor(low, mid, normalized / 0.5)
      : interpolateColor(mid, high, (normalized - 0.5) / 0.5);
  return [color[0], color[1], color[2], isRanked ? 210 : 86];
}

export function formatLayerValue(
  layerName: MapLayerName,
  value: number,
): string {
  const option = layerOption(layerName);
  if (layerName === "composite_score" || layerName === "buildable_fraction") {
    return `${Math.round(value * 100)}%`;
  }
  if (layerName === "congestion_index") {
    return value.toFixed(2);
  }
  return `${Math.round(value)} ${option.unit}`;
}

function valueForRankedSite(
  layerName: MapLayerName,
  result: RankedSite,
): number {
  if (layerName === "composite_score") {
    return result.composite_score;
  }
  return Number(result.site[layerName]);
}

function normalizeValue(
  value: number,
  [low, high]: readonly [number, number],
  direction: LayerDirection,
): number {
  if (high <= low) {
    return 1;
  }
  const bounded = Math.min(Math.max(value, low), high);
  const normalized = (bounded - low) / (high - low);
  return direction === "higher_is_better" ? normalized : 1 - normalized;
}

function interpolateColor(
  start: readonly [number, number, number],
  end: readonly [number, number, number],
  ratio: number,
): [number, number, number] {
  const boundedRatio = Math.min(Math.max(ratio, 0), 1);
  return [
    Math.round(start[0] + (end[0] - start[0]) * boundedRatio),
    Math.round(start[1] + (end[1] - start[1]) * boundedRatio),
    Math.round(start[2] + (end[2] - start[2]) * boundedRatio),
  ];
}
