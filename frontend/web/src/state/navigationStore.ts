import { create } from "zustand";

const STORAGE_KEY = "k-insight-selected-module";
const SIDEBAR_KEY = "k-insight-sidebar-expanded";
const DEFAULT_MODULE_ID = "overview";

function readSelectedModule() {
  if (typeof window === "undefined") return DEFAULT_MODULE_ID;
  return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_MODULE_ID;
}

function readSidebarExpanded() {
  if (typeof window === "undefined") return true;
  // Étendu par défaut : meilleure découvrabilité (navigation libellée).
  return window.localStorage.getItem(SIDEBAR_KEY) !== "0";
}

interface NavigationState {
  selectedModuleId: string;
  sidebarExpanded: boolean;
  setSelectedModule: (moduleId: string) => void;
  setSidebarExpanded: (expanded: boolean) => void;
  toggleSidebar: () => void;
}

export const useNavigationStore = create<NavigationState>((set, get) => ({
  selectedModuleId: readSelectedModule(),
  sidebarExpanded: readSidebarExpanded(),
  setSelectedModule: (moduleId) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, moduleId);
    }
    set({ selectedModuleId: moduleId });
  },
  setSidebarExpanded: (expanded) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SIDEBAR_KEY, expanded ? "1" : "0");
    }
    set({ sidebarExpanded: expanded });
  },
  toggleSidebar: () => get().setSidebarExpanded(!get().sidebarExpanded),
}));
