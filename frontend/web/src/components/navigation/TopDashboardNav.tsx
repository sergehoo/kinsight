import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  getDefaultItemHref,
  getModuleFromLegacyKey,
  getModuleFromPath,
  visibleDashboardModules,
} from "@/config/modules.config";
import { getCurrentPermissions } from "@/lib/permissions";
import { useNavigationStore } from "@/state/navigationStore";

import { BLACK, glass } from "../chrome/theme";

export function TopDashboardNav() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const permissions = getCurrentPermissions();
  const visibleModules = visibleDashboardModules(permissions);
  const { selectedModuleId, setSelectedModule } = useNavigationStore();
  const legacyKey = pathname.startsWith("/modules/") ? pathname.split("/").at(-1) : undefined;
  const urlModule = getModuleFromPath(pathname) ?? getModuleFromLegacyKey(legacyKey);
  const activeModule = urlModule ?? visibleModules.find((module) => module.id === selectedModuleId) ?? visibleModules[0];

  useEffect(() => {
    if (urlModule && urlModule.id !== selectedModuleId) {
      setSelectedModule(urlModule.id);
    }
  }, [selectedModuleId, setSelectedModule, urlModule]);

  const selectModule = (moduleId: string) => {
    const nextModule = visibleModules.find((module) => module.id === moduleId);
    if (!nextModule) return;
    setSelectedModule(nextModule.id);
    navigate(getDefaultItemHref(nextModule, permissions));
  };

  return (
    <div className="w-full">
      <select
        className="h-12 w-full rounded-full border border-white/70 bg-white/76 px-5 text-[14px] font-bold text-[#1B1E1F] shadow-[0_16px_34px_rgba(40,44,48,0.08)] outline-none backdrop-blur-2xl md:hidden"
        value={activeModule?.id ?? ""}
        onChange={(event) => selectModule(event.target.value)}
        aria-label="Choisir un dashboard métier"
      >
        {visibleModules.map((module) => (
          <option key={module.id} value={module.id}>
            {module.label}
          </option>
        ))}
      </select>

      <nav
        className="hidden max-w-full items-center gap-1 overflow-x-auto rounded-full px-2 py-1.5 [scrollbar-width:none] md:flex [&::-webkit-scrollbar]:hidden"
        style={glass}
        aria-label="Dashboards métiers"
      >
        {visibleModules.map((module) => {
          const active = activeModule?.id === module.id;
          const Icon = module.icon;
          return (
            <button
              key={module.id}
              type="button"
              onClick={() => selectModule(module.id)}
              className="flex h-11 shrink-0 items-center gap-2 rounded-full px-5 text-[14px] font-semibold transition-transform hover:-translate-y-0.5"
              style={active ? { background: BLACK, color: "#fff", boxShadow: "0 18px 32px rgba(0,0,0,0.18)" } : { color: "#222" }}
              aria-current={active ? "page" : undefined}
            >
              <Icon width={17} height={17} />
              <span className="whitespace-nowrap">{module.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
