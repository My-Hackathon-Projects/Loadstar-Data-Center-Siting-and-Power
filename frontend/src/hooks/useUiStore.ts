import { create } from "zustand";

import {
  DEFAULT_ACTIVE_LAYER,
  DEFAULT_DEMO_POWER_MW,
  DEFAULT_LOAD_PROFILE,
  DEFAULT_SEARCH_TOP_K,
  DEFAULT_WEIGHTS,
  DEFAULT_WORKLOAD_TYPE,
} from "../config/defaults";
import type { MapLayerName } from "../features/map/mapLayers";
import type { OptimizeRequest, SearchRequest, Weights } from "../types/api";

type WorkloadType = SearchRequest["workload_type"];
type LoadProfile = OptimizeRequest["load_profile"];

/**
 * Grid overlay LOD selector. `auto` lets the zoom level decide which voltage
 * tiers render; `backbone` pins to >= 380 kV; `all` shows every line in the
 * GeoJSON file (>= 220 kV after the build-time filter).
 */
export type GridMode = "auto" | "backbone" | "all";

interface UiState {
  /** Cell currently focused in the detail and optimizer panels. */
  selectedCellId: string | null;
  /** Cells currently pinned in the comparison panel. */
  comparisonCellIds: string[];
  /** Active map layer shown in the H3 overlay. */
  activeLayer: MapLayerName;
  /** Whether the transmission-grid overlay is rendered. Default off. */
  showGrid: boolean;
  /** LOD mode for the grid overlay. */
  gridMode: GridMode;
  /** Search-form state shared by SearchPanel and SiteMap. */
  powerMw: number;
  workloadType: WorkloadType;
  topK: number;
  /** Scoring weights (optional `SearchRequest.weights`), driven by the sliders. */
  weights: Weights;
  /** Active country filter (optional `SearchRequest.country_filter`). */
  countryFilter: string[];
  /** Optimizer-form state. */
  loadProfile: LoadProfile;
  clearComparison: () => void;
  setActiveLayer: (layerName: MapLayerName) => void;
  setSelectedCellId: (cellId: string | null) => void;
  setShowGrid: (show: boolean) => void;
  setGridMode: (mode: GridMode) => void;
  setSearchParams: (
    next: Partial<{
      powerMw: number;
      workloadType: WorkloadType;
      topK: number;
      loadProfile: LoadProfile;
      weights: Weights;
      countryFilter: string[];
    }>,
  ) => void;
  setWeight: (factor: keyof Weights, value: number) => void;
  toggleCountryFilter: (code: string) => void;
  toggleComparisonCell: (cellId: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  selectedCellId: null,
  comparisonCellIds: [],
  activeLayer: DEFAULT_ACTIVE_LAYER,
  showGrid: false,
  gridMode: "auto",
  powerMw: DEFAULT_DEMO_POWER_MW,
  workloadType: DEFAULT_WORKLOAD_TYPE,
  topK: DEFAULT_SEARCH_TOP_K,
  weights: DEFAULT_WEIGHTS,
  countryFilter: [],
  loadProfile: DEFAULT_LOAD_PROFILE,
  clearComparison: () => set({ comparisonCellIds: [] }),
  setActiveLayer: (layerName) => set({ activeLayer: layerName }),
  setSelectedCellId: (cellId) => set({ selectedCellId: cellId }),
  setShowGrid: (show) => set({ showGrid: show }),
  setGridMode: (mode) => set({ gridMode: mode }),
  setSearchParams: (next) => set(next),
  setWeight: (factor, value) =>
    set((state) => ({ weights: { ...state.weights, [factor]: value } })),
  toggleCountryFilter: (code) =>
    set((state) => ({
      countryFilter: state.countryFilter.includes(code)
        ? state.countryFilter.filter((existing) => existing !== code)
        : [...state.countryFilter, code],
    })),
  toggleComparisonCell: (cellId) =>
    set((state) => {
      if (state.comparisonCellIds.includes(cellId)) {
        return {
          comparisonCellIds: state.comparisonCellIds.filter(
            (existing) => existing !== cellId,
          ),
        };
      }
      return {
        comparisonCellIds: [...state.comparisonCellIds, cellId].slice(-5),
      };
    }),
}));
