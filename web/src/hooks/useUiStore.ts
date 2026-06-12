import { create } from "zustand";

interface UiState {
  selectedCellId: string | null;
  setSelectedCellId: (cellId: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  selectedCellId: null,
  setSelectedCellId: (cellId) => set({ selectedCellId: cellId })
}));
