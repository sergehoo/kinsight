import { create } from "zustand";

/** Filtres globaux du tableau de bord (période + multi-filiales). */
interface FiltersState {
  year: number;
  quarter: number;
  subsidiary: string; // "all" | code filiale (KRE, KSH, MYK…)
  setYear: (year: number) => void;
  setQuarter: (quarter: number) => void;
  setSubsidiary: (subsidiary: string) => void;
}

export const SUBSIDIARIES: { code: string; label: string }[] = [
  { code: "all", label: "Toutes les filiales" },
  { code: "KRE", label: "K-Express" },
  { code: "KSH", label: "K-Shield" },
  { code: "MYK", label: "MyKaydan" },
];

export const useFilters = create<FiltersState>((set) => ({
  year: 2026,
  quarter: 1,
  subsidiary: "all",
  setYear: (year) => set({ year }),
  setQuarter: (quarter) => set({ quarter }),
  setSubsidiary: (subsidiary) => set({ subsidiary }),
}));
