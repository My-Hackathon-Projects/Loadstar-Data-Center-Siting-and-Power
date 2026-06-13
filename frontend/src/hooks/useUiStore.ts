import { create } from "zustand";

import type { MapLayerName } from "../features/map/mapLayers";
import type { OptimizeRequest, SearchRequest } from "../types/api";

type WorkloadType = SearchRequest["workload_type"];
type LoadProfile = OptimizeRequest["load_profile"];

interface UiState {
  /** Cell currently focused in the detail and optimizer panels. */
  selectedCellId: string | null;
  /** Cells currently pinned in the comparison panel. */
  comparisonCellIds: string[];
  /** Active map layer shown in the H3 overlay. */
  activeLayer: MapLayerName;
  /** Search-form state shared by SearchPanel and SiteMap. */
  powerMw: number;
  workloadType: WorkloadType;
  topK: number;
  /** Optimizer-form state. */
  loadProfile: LoadProfile;
  clearComparison: () => void;
  setActiveLayer: (layerName: MapLayerName) => void;
  setSelectedCellId: (cellId: string | null) => void;
  setSearchParams: (
    next: Partial<{
      powerMw: number;
      workloadType: WorkloadType;
      topK: number;
      loadProfile: LoadProfile;
    }>,
  ) => void;
  toggleComparisonCell: (cellId: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  selectedCellId: null,
  comparisonCellIds: [],
  activeLayer: "composite_score",
  powerMw: 280,
  workloadType: "training",
  topK: 8,
  loadProfile: "flat_24_7",
  clearComparison: () => set({ comparisonCellIds: [] }),
  setActiveLayer: (layerName) => set({ activeLayer: layerName }),
  setSelectedCellId: (cellId) => set({ selectedCellId: cellId }),
  setSearchParams: (next) => set(next),
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
