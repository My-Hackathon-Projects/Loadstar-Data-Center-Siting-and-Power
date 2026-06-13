import type { PickingInfo } from "@deck.gl/core";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import DeckGL from "@deck.gl/react";
import type { StyleSpecification } from "maplibre-gl";
import { useMemo } from "react";
import Map from "react-map-gl/maplibre";

import { useUiStore } from "../../hooks/useUiStore";
import { useLayer, useSearchSites } from "../../lib/queries";
import { LayerControls } from "./LayerControls";
import {
  buildLayerCells,
  formatLayerValue,
  layerFillColor,
  layerOption,
  type LayerCell,
} from "./mapLayers";

const MAP_STYLE: StyleSpecification = {
  layers: [
    {
      id: "background",
      paint: {
        "background-color": "#eef5f8",
      },
      type: "background",
    },
  ],
  sources: {},
  version: 8,
};

const INITIAL_VIEW_STATE = {
  latitude: 57.4,
  longitude: 8.5,
  maxZoom: 8,
  minZoom: 2.4,
  pitch: 0,
  zoom: 3.15,
};

export function SiteMap() {
  const activeLayer = useUiStore((state) => state.activeLayer);
  const powerMw = useUiStore((state) => state.powerMw);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const topK = useUiStore((state) => state.topK);
  const workloadType = useUiStore((state) => state.workloadType);
  const searchQuery = useSearchSites({
    power_mw: powerMw,
    top_k: topK,
    workload_type: workloadType,
  });
  const layerQuery = useLayer(activeLayer);
  const rankedResults = useMemo(
    () => searchQuery.data?.results ?? [],
    [searchQuery.data?.results],
  );
  const cells = useMemo(
    () => buildLayerCells(activeLayer, layerQuery.data, rankedResults),
    [activeLayer, layerQuery.data, rankedResults],
  );
  const activeLayerOption = layerOption(activeLayer);
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
          cell.cellId === selectedCellId
            ? [14, 116, 144, 255]
            : [255, 255, 255, 170],
        getLineWidth: (cell) => (cell.cellId === selectedCellId ? 3 : 1),
        highlightColor: [17, 94, 89, 90],
        id: `h3-${activeLayer}`,
        lineWidthMinPixels: 1,
        pickable: true,
        stroked: true,
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
    <section className="relative min-h-[520px] overflow-hidden rounded-lg border border-slate-200 bg-slate-100 lg:min-h-[680px]">
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
        initialViewState={INITIAL_VIEW_STATE}
        layers={deckLayers}
      >
        <Map
          attributionControl={false}
          initialViewState={INITIAL_VIEW_STATE}
          interactive={false}
          mapStyle={MAP_STYLE}
          reuseMaps
        />
      </DeckGL>

      <div className="pointer-events-none absolute inset-x-3 top-3 z-10 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="pointer-events-auto rounded-lg border border-slate-200 bg-white/95 p-3 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-normal text-slate-500">
            Map Layer
          </p>
          <div className="mt-2">
            <LayerControls />
          </div>
        </div>
        <div className="pointer-events-auto w-full max-w-xs rounded-lg border border-slate-200 bg-white/95 p-3 text-sm shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium text-slate-900">
              {activeLayerOption.label}
            </span>
            <span className="text-xs text-slate-500">
              {searchQuery.data?.results.length ?? 0} ranked
            </span>
          </div>
          <div className="mt-2 h-2 rounded-full bg-gradient-to-r from-[#e05840] via-[#f1b24a] to-[#177e76]" />
          <div className="mt-1 flex justify-between text-xs text-slate-500">
            <span>Weaker</span>
            <span>Stronger</span>
          </div>
        </div>
      </div>

      {searchQuery.isLoading || layerQuery.isLoading ? (
        <div className="absolute inset-x-3 bottom-3 z-10 rounded-md border border-slate-200 bg-white/95 p-3 text-sm text-slate-600 shadow-sm">
          Loading map layers...
        </div>
      ) : null}
      {searchQuery.isError || layerQuery.isError ? (
        <div className="absolute inset-x-3 bottom-3 z-10 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800 shadow-sm">
          Map data could not be loaded.
        </div>
      ) : null}
    </section>
  );
}
