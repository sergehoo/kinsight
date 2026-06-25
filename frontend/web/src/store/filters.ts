import { create } from "zustand";

/** Filtres globaux du tableau de bord (multi-filiales / période). */
interface FiltersState {
  year: number;
  quarter: number;
  setYear: (year: number) => void;
  setQuarter: (quarter: number) => void;
}

export const useFilters = create<FiltersState>((set) => ({
  year: 2026,
  quarter: 1,
  setYear: (year) => set({ year }),
  setQuarter: (quarter) => set({ quarter }),
}));
