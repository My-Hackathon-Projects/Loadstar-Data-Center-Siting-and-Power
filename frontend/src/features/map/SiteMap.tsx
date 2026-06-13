import { FlyToInterpolator, type PickingInfo } from "@deck.gl/core";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import DeckGL from "@deck.gl/react";
import { useEffect, useMemo, useRef, useState } from "react";
import MapGL from "react-map-gl/maplibre";

import { useSearchRequest } from "../../hooks/useSearchRequest";
import { useUiStore } from "../../hooks/useUiStore";
import { useLayer, useSearchSites } from "../../lib/queries";
import { COLOR, MAP_RGB } from "../../styles/tokens";
import { darkBasemapStyle } from "./darkBasemap";
import {
  buildLayerCells,
  formatLayerValue,
  layerFillColor,
  layerOption,
  type LayerCell,
} from "./mapLayers";

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

export function SiteMap() {
  const activeLayer = useUiStore((state) => state.activeLayer);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const searchQuery = useSearchSites(useSearchRequest());
  const layerQuery = useLayer(activeLayer);
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

  const deckLayers = useMemo(
    () => [
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
    ],
    [activeLayer, cells, selectedCellId, setSelectedCellId],
  );

  return (
    <section className="relative h-full min-h-[420px] overflow-hidden rounded-2xl border border-subtle bg-void">
      <DeckGL
        controller
        getTooltip={({ object }: PickingInfo<LayerCell>) =>
          object
            ? `${object.regionName} (${object.countryCode})\n${activeLayerOption.label}: ${formatLayerValue(
                activeLayer,
                object.value,
              )}${object.score === null ? "" : `\nScore: ${formatLayerValue("composite_score", object.score)}`}`
            : null
        }
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
