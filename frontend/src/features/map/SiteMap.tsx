import { FlyToInterpolator, type Layer, type PickingInfo } from "@deck.gl/core";
import { PathStyleExtension } from "@deck.gl/extensions";
import { GeoJsonLayer } from "@deck.gl/layers";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import DeckGL from "@deck.gl/react";
import type { Feature, Geometry } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";
import MapGL from "react-map-gl/maplibre";

import { useSearchRequest } from "../../hooks/useSearchRequest";
import { useUiStore } from "../../hooks/useUiStore";
import { useLayer, useSearchSites, useSiteDetail } from "../../lib/queries";
import { COLOR, MAP_RGB } from "../../styles/tokens";
import { darkBasemapStyle } from "./darkBasemap";
import {
  buildLayerCells,
  formatLayerValue,
  layerFillColor,
  layerOption,
  type LayerCell,
} from "./mapLayers";
import {
  type GridFeatureProperties,
  type GridGeoJson,
  useGridData,
} from "./useGridData";

const MAP_STYLE = darkBasemapStyle();

interface MapViewState {
  latitude: number;
  longitude: number;
  zoom: number;
  pitch: number;
  minZoom: number;
  maxZoom: number;
  transitionDuration?: number;
  transitionInterpolator?: FlyToInterpolator;
}

const INITIAL_VIEW_STATE: MapViewState = {
  latitude: 57.4,
  longitude: 8.5,
  maxZoom: 8,
  minZoom: 2.4,
  pitch: 0,
  zoom: 3.15,
};

const SELECTED_LINE: [number, number, number, number] = [...MAP_RGB.accent, 255];
const UNSELECTED_LINE: [number, number, number, number] = [...MAP_RGB.white, 60];
const HIGHLIGHT: [number, number, number, number] = [...MAP_RGB.highlight, 90];

// Voltage-tier styling. Both tiers reuse `MAP_RGB.white` so the grid reads as
// a deeper version of the unselected hex stroke instead of inventing a new
// hue. Width and alpha encode the tier; the EHV backbone reads thicker and
// brighter, the 220-380 kV layer thinner and dimmer.
const GRID_EHV_WIDTH_PX = 2.0;
const GRID_HV_WIDTH_PX = 1.0;
const GRID_EHV_ALPHA = 217; // ~0.85
const GRID_HV_ALPHA = 140; // ~0.55
const GRID_BUS_ALPHA = 130; // ~0.51
const ZERO_RGBA: [number, number, number, number] = [0, 0, 0, 0];

function isLine(
  feature: Feature<Geometry, GridFeatureProperties>,
): boolean {
  return feature.properties.kind === "line";
}

function isBus(
  feature: Feature<Geometry, GridFeatureProperties>,
): boolean {
  return feature.properties.kind === "bus";
}

interface FilteredGrid {
  type: "FeatureCollection";
  features: Feature<Geometry, GridFeatureProperties>[];
}

/**
 * Resolve the active LOD for the grid overlay. `auto` follows the zoom
 * heuristic; `backbone` and `all` pin to a fixed tier regardless of zoom.
 */
function resolveGridLod(
  mode: "auto" | "backbone" | "all",
  zoom: number,
): { showHv: boolean; showLowDegreeBuses: boolean } {
  if (mode === "backbone") {
    return { showHv: false, showLowDegreeBuses: false };
  }
  if (mode === "all") {
    return { showHv: true, showLowDegreeBuses: true };
  }
  return {
    showHv: zoom >= 4,
    showLowDegreeBuses: zoom >= 5,
  };
}

function filterGrid(
  grid: GridGeoJson | null | undefined,
  lod: { showHv: boolean; showLowDegreeBuses: boolean },
): FilteredGrid | null {
  if (!grid) {
    return null;
  }
  const features = grid.features.filter((feature) => {
    const props = feature.properties;
    if (props.kind === "line") {
      if (!lod.showHv && props.voltage_tier !== "ehv") {
        return false;
      }
      return true;
    }
    if (props.kind === "bus") {
      if (!lod.showHv) {
        // At wide zoom, only show backbone substations; sub-380 kV nodes
        // would just be noise.
        if (props.voltage_kv < 380) {
          return false;
        }
        if (props.degree < 2) {
          return false;
        }
      } else if (!lod.showLowDegreeBuses && props.degree < 2) {
        return false;
      }
      return true;
    }
    return false;
  });
  return { type: "FeatureCollection", features };
}

function gridLineColor(
  feature: Feature<Geometry, GridFeatureProperties>,
): [number, number, number, number] {
  if (!isLine(feature)) {
    return ZERO_RGBA;
  }
  const props = feature.properties as GridLineProperties;
  const alpha = props.voltage_tier === "ehv" ? GRID_EHV_ALPHA : GRID_HV_ALPHA;
  return [...MAP_RGB.white, alpha] as [number, number, number, number];
}

function gridLineWidth(
  feature: Feature<Geometry, GridFeatureProperties>,
): number {
  if (!isLine(feature)) {
    return 0;
  }
  const props = feature.properties as GridLineProperties;
  return props.voltage_tier === "ehv" ? GRID_EHV_WIDTH_PX : GRID_HV_WIDTH_PX;
}

function gridDashArray(
  feature: Feature<Geometry, GridFeatureProperties>,
): [number, number] {
  if (!isLine(feature)) {
    return [0, 0];
  }
  const props = feature.properties as GridLineProperties;
  return props.is_hvdc ? [4, 3] : [0, 0];
}

function gridBusRadius(
  feature: Feature<Geometry, GridFeatureProperties>,
): number {
  if (!isBus(feature)) {
    return 0;
  }
  const props = feature.properties as GridBusProperties;
  // Encode connectivity as a square-root curve so high-degree hubs stand out
  // without dominating the canvas.
  return Math.max(1.5, Math.min(4.0, 1.0 + Math.sqrt(props.degree)));
}

function gridBusFill(
  feature: Feature<Geometry, GridFeatureProperties>,
): [number, number, number, number] {
  if (!isBus(feature)) {
    return ZERO_RGBA;
  }
  return [...MAP_RGB.white, GRID_BUS_ALPHA] as [number, number, number, number];
}

// Local re-exports of the property variants for the helper closures above.
type GridBusProperties = Extract<GridFeatureProperties, { kind: "bus" }>;
type GridLineProperties = Extract<GridFeatureProperties, { kind: "line" }>;

export function SiteMap() {
  const activeLayer = useUiStore((state) => state.activeLayer);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const showGrid = useUiStore((state) => state.showGrid);
  const gridMode = useUiStore((state) => state.gridMode);
  const searchQuery = useSearchSites(useSearchRequest());
  const layerQuery = useLayer(activeLayer);
  const gridQuery = useGridData(showGrid);
  const selectedSiteQuery = useSiteDetail(selectedCellId);
  const rankedResults = useMemo(
    () => searchQuery.data?.results ?? [],
    [searchQuery.data?.results],
  );
  const cells = useMemo(
    () => buildLayerCells(activeLayer, layerQuery.data, rankedResults),
    [activeLayer, layerQuery.data, rankedResults],
  );
  const cellCoords = useMemo(() => {
    const map = new Map<string, [number, number]>();
    for (const cell of cells) {
      map.set(cell.cellId, [cell.longitude, cell.latitude]);
    }
    return map;
  }, [cells]);
  const activeLayerOption = layerOption(activeLayer);

  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW_STATE);
  // Reuse one interpolator instance so re-renders do not restart the transition.
  const flyTo = useRef(new FlyToInterpolator({ speed: 1.3 }));

  // Fly to the selected cell (e.g. Fred's top candidate) whenever it changes.
  useEffect(() => {
    if (!selectedCellId) {
      return;
    }
    const coords = cellCoords.get(selectedCellId);
    if (!coords) {
      return;
    }
    setViewState((current) => ({
      ...current,
      longitude: coords[0],
      latitude: coords[1],
      zoom: Math.max(current.zoom, 4.6),
      transitionDuration: 1500,
      transitionInterpolator: flyTo.current,
    }));
  }, [selectedCellId, cellCoords]);

  const filteredGrid = useMemo(() => {
    if (!showGrid) {
      return null;
    }
    return filterGrid(gridQuery.data, resolveGridLod(gridMode, viewState.zoom));
  }, [showGrid, gridQuery.data, gridMode, viewState.zoom]);

  const deckLayers = useMemo<Layer[]>(() => {
    const layers: Layer[] = [];
    if (filteredGrid) {
      // PathStyleExtension augments GeoJsonLayer with `getDashArray` and
      // `dashJustified`, but those keys are not declared on the base props
      // type. Cast through `unknown` so the call site stays type-safe up
      // to the extension boundary without leaking `any`.
      const gridProps = {
        id: "transmission-grid",
        data: filteredGrid,
        pickable: true,
        stroked: true,
        filled: true,
        pointType: "circle",
        lineWidthUnits: "pixels",
        lineWidthMinPixels: 0.75,
        pointRadiusUnits: "pixels",
        pointRadiusMinPixels: 1.5,
        getLineColor: gridLineColor,
        getLineWidth: gridLineWidth,
        getPointRadius: gridBusRadius,
        getFillColor: gridBusFill,
        extensions: [new PathStyleExtension({ dash: true })],
        getDashArray: gridDashArray,
        dashJustified: true,
        updateTriggers: {
          getDashArray: filteredGrid.features.length,
        },
      } as unknown as ConstructorParameters<typeof GeoJsonLayer<GridFeatureProperties>>[0];
      layers.push(new GeoJsonLayer<GridFeatureProperties>(gridProps));
    }
    layers.push(
      new H3HexagonLayer<LayerCell>({
        autoHighlight: true,
        coverage: 0.82,
        data: cells,
        extruded: false,
        getFillColor: (cell) =>
          layerFillColor(activeLayer, cell.value, cell.isRanked),
        getHexagon: (cell) => cell.hexagon,
        getLineColor: (cell) =>
          cell.cellId === selectedCellId ? SELECTED_LINE : UNSELECTED_LINE,
        getLineWidth: (cell) => (cell.cellId === selectedCellId ? 3 : 1),
        highlightColor: HIGHLIGHT,
        id: `h3-${activeLayer}`,
        lineWidthMinPixels: 1,
        pickable: true,
        stroked: true,
        updateTriggers: {
          getLineColor: selectedCellId,
          getLineWidth: selectedCellId,
        },
        onClick: (info: PickingInfo<LayerCell>) => {
          if (info.object) {
            setSelectedCellId(info.object.cellId);
          }
        },
      }),
    );
    return layers;
  }, [filteredGrid, activeLayer, cells, selectedCellId, setSelectedCellId]);

  const selectedSiteContext = useMemo(() => {
    const site = selectedSiteQuery.data?.site;
    if (!site) {
      return null;
    }
    if (site.nearest_substation_kv == null || site.nearest_substation_distance_km == null) {
      return null;
    }
    return {
      kv: site.nearest_substation_kv,
      distanceKm: site.nearest_substation_distance_km,
      capacityMva: site.nearest_substation_capacity_mva ?? null,
    };
  }, [selectedSiteQuery.data?.site]);

  return (
    <section className="relative h-[60vh] min-h-[420px] overflow-hidden rounded-2xl border border-subtle bg-void lg:h-full">
      <DeckGL
        controller
        getTooltip={(info: PickingInfo) => buildTooltip(info, activeLayer, activeLayerOption.label, selectedSiteContext)}
        layers={deckLayers}
        onViewStateChange={({ viewState: next }) =>
          setViewState(next as MapViewState)
        }
        viewState={viewState}
      >
        <MapGL
          attributionControl={false}
          interactive={false}
          mapStyle={MAP_STYLE}
          reuseMaps
        />
      </DeckGL>

      <div className="pointer-events-none absolute right-3 top-3 z-10 flex justify-end">
        <div className="pointer-events-auto w-full max-w-xs rounded-xl border border-subtle bg-panel p-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium text-primary">
              {activeLayerOption.label}
            </span>
            <span className="text-xs text-dim">
              {searchQuery.data?.results.length ?? 0} ranked
            </span>
          </div>
          <div
            className="mt-2 h-2 rounded-full"
            style={{
              backgroundImage: `linear-gradient(to right, ${COLOR.rampLow}, ${COLOR.rampMid}, ${COLOR.rampHigh})`,
            }}
          />
          <div className="mt-1 flex justify-between text-xs text-dim">
            <span>Weaker</span>
            <span>Stronger</span>
          </div>
          {showGrid ? (
            <div className="mt-3 border-t border-subtle pt-2 text-[11px] text-dim">
              <div className="flex items-center justify-between gap-2">
                <span>HV grid (PyPSA-Eur)</span>
                <span>capacity, not flow</span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <span className="inline-block h-[2px] w-5 bg-white/85" />
                <span>EHV {"≥"} 380 kV</span>
                <span className="inline-block h-[1px] w-5 bg-white/55" />
                <span>HV 220-380</span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <span className="inline-block h-[2px] w-5 [background-image:linear-gradient(to_right,white_2px,transparent_2px,transparent_5px,white_5px,white_7px)] [background-size:7px_2px] opacity-80" />
                <span>HVDC link (dashed)</span>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {searchQuery.isLoading || layerQuery.isLoading ? (
        <div className="absolute inset-x-3 bottom-3 z-10 rounded-lg border border-subtle bg-panel p-3 text-sm text-dim">
          Loading map layers...
        </div>
      ) : null}
      {searchQuery.isError || layerQuery.isError ? (
        <div className="absolute inset-x-3 bottom-3 z-10 rounded-lg border border-danger bg-panel p-3 text-sm text-danger">
          Map data could not be loaded.
        </div>
      ) : null}
    </section>
  );
}

interface SubstationContext {
  kv: number;
  distanceKm: number;
  capacityMva: number | null;
}

function buildTooltip(
  info: PickingInfo,
  activeLayer: string,
  activeLayerLabel: string,
  selectedSite: SubstationContext | null,
): string | null {
  const obj = info.object as
    | (Feature<Geometry, GridFeatureProperties> & { properties: GridFeatureProperties })
    | LayerCell
    | undefined;
  if (!obj) {
    return null;
  }
  if ("properties" in obj && obj.properties && "kind" in obj.properties) {
    const props = obj.properties;
    if (props.kind === "bus") {
      return [
        `${props.bus_id} (${props.country})`,
        `${Math.round(props.voltage_kv)} kV  deg ${props.degree}`,
        `Connected: ${Math.round(props.connected_capacity_mva)} MVA`,
      ].join("\n");
    }
    if (props.kind === "line") {
      const head = `${props.is_hvdc ? "HVDC " : ""}${Math.round(props.voltage_kv)} kV line`;
      const detail = `${Math.round(props.capacity_mva)} MVA  ${props.length_km.toFixed(0)} km`;
      const xb = props.is_cross_border
        ? `\n${props.country0} <-> ${props.country1}`
        : "";
      return `${head}\n${detail}${xb}`;
    }
  }
  // Hex tooltip path: existing behaviour, optionally extended with the
  // selected site's nearest substation when the hovered cell IS the
  // selected one (the only cell for which we know the substation).
  const cell = obj as LayerCell;
  const baseLines = [
    `${cell.regionName} (${cell.countryCode})`,
    `${activeLayerLabel}: ${formatLayerValue(activeLayer as never, cell.value)}`,
  ];
  if (cell.score !== null) {
    baseLines.push(
      `Score: ${formatLayerValue("composite_score" as never, cell.score)}`,
    );
  }
  if (selectedSite && cell.score !== null) {
    baseLines.push(
      `Nearest substation: ${Math.round(selectedSite.kv)} kV at ${selectedSite.distanceKm.toFixed(1)} km`,
    );
  }
  return baseLines.join("\n");
}
