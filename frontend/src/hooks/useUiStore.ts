import { create } from "zustand";

import type { OptimizeRequest, SearchRequest } from "../types/api";

type WorkloadType = SearchRequest["workload_type"];
type LoadProfile = OptimizeRequest["load_profile"];

interface UiState {
  /** Cell currently focused in the detail and optimizer panels. */
  selectedCellId: string | null;
  /** Search-form state shared by SearchPanel and SiteMap. */
  powerMw: number;
  workloadType: WorkloadType;
  topK: number;
  /** Optimizer-form state. */
  loadProfile: LoadProfile;
  setSelectedCellId: (cellId: string) => void;
  setSearchParams: (
    next: Partial<{
      powerMw: number;
      workloadType: WorkloadType;
      topK: number;
      loadProfile: LoadProfile;
    }>
  ) => void;
}

export const useUiStore = create<UiState>((set) => ({
  selectedCellId: null,
  powerMw: 280,
  workloadType: "training",
  topK: 8,
  loadProfile: "flat_24_7",
  setSelectedCellId: (cellId) => set({ selectedCellId: cellId }),
  setSearchParams: (next) => set(next)
}));
