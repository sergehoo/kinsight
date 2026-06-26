import { create } from "zustand";

const STORAGE_KEY = "k-insight-selected-module";
const DEFAULT_MODULE_ID = "overview";

function readSelectedModule() {
  if (typeof window === "undefined") return DEFAULT_MODULE_ID;
  return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_MODULE_ID;
}

interface NavigationState {
  selectedModuleId: string;
  setSelectedModule: (moduleId: string) => void;
}

export const useNavigationStore = create<NavigationState>((set) => ({
  selectedModuleId: readSelectedModule(),
  setSelectedModule: (moduleId) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, moduleId);
    }
    set({ selectedModuleId: moduleId });
  },
}));
