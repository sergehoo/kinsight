import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  getModuleById,
  getModuleFromLegacyKey,
  getModuleFromPath,
  visibleDashboardModules,
  type DashboardModuleConfig,
} from "@/config/modules.config";
import { getCurrentPermissions } from "@/lib/permissions";
import { useNavigationStore } from "@/state/navigationStore";

import { BLACK, glass } from "../chrome/theme";

const GROUP_ORDER = ["Pilotage", "Métiers", "Gouvernance"];

function groupModules(modules: DashboardModuleConfig[]) {
  const groups = new Map<string, DashboardModuleConfig[]>();
  for (const module of modules) {
    const list = groups.get(module.group) ?? [];
    list.push(module);
    groups.set(module.group, list);
  }
  const ordered = GROUP_ORDER.filter((group) => groups.has(group));
  for (const group of groups.keys()) if (!ordered.includes(group)) ordered.push(group);
  return ordered.map((group) => ({ group, modules: groups.get(group) ?? [] }));
}

export function TopDashboardNav() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const permissions = getCurrentPermissions();
  const visibleModules = visibleDashboardModules(permissions);
  const { selectedModuleId, setSelectedModule } = useNavigationStore();
  const legacyKey = pathname.startsWith("/modules/") ? pathname.split("/").at(-1) : undefined;
  const legacyDashboardModule =
    pathname === "/" || pathname === "/d/realEstate"
      ? getModuleById("immobilier")
      : pathname === "/d/hr"
        ? getModuleById("capital-humain")
        : pathname === "/d/finance"
          ? getModuleById("finance")
          : undefined;
  const urlModule = getModuleFromPath(pathname) ?? getModuleFromLegacyKey(legacyKey) ?? legacyDashboardModule;
  const candidate = urlModule ?? visibleModules.find((module) => module.id === selectedModuleId);
  const activeModule =
    candidate && visibleModules.some((module) => module.id === candidate.id) ? candidate : visibleModules[0];

  useEffect(() => {
    if (urlModule && urlModule.id !== selectedModuleId) {
      setSelectedModule(urlModule.id);
    }
  }, [selectedModuleId, setSelectedModule, urlModule]);

  const selectModule = (moduleId: string) => {
    const nextModule = visibleModules.find((module) => module.id === moduleId);
    if (!nextModule) return;
    setSelectedModule(nextModule.id);
    navigate(nextModule.basePath);
  };

  const grouped = groupModules(visibleModules);

  return (
    <div className="w-full">
      <select
        className="h-12 w-full rounded-full border border-white/70 bg-white/76 px-5 text-[14px] font-bold text-[#1B1E1F] shadow-[0_16px_34px_rgba(40,44,48,0.08)] outline-none backdrop-blur-2xl md:hidden"
        value={activeModule?.id ?? ""}
        onChange={(event) => selectModule(event.target.value)}
        aria-label="Choisir un domaine analytique"
      >
        {grouped.map(({ group, modules }) => (
          <optgroup key={group} label={group}>
            {modules.map((module) => (
              <option key={module.id} value={module.id}>
                {module.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      <nav
        className="hidden max-w-full items-center gap-1 overflow-x-auto rounded-full px-2 py-1.5 [scrollbar-width:none] md:flex [&::-webkit-scrollbar]:hidden"
        style={glass}
        aria-label="Dashboards métiers"
      >
        {grouped.map(({ group, modules }, groupIndex) => (
          <div key={group} className="flex shrink-0 items-center gap-1" role="group" aria-label={group}>
            {groupIndex > 0 ? <span className="mx-1 h-7 w-px shrink-0 rounded-full bg-[#DCE0DE]" aria-hidden /> : null}
            {modules.map((module) => {
              const active = activeModule?.id === module.id;
              const Icon = module.icon;
              return (
                <button
                  key={module.id}
                  type="button"
                  onClick={() => selectModule(module.id)}
                  className="flex h-11 shrink-0 items-center gap-2 rounded-full px-4 text-[13.5px] font-semibold transition-transform hover:-translate-y-0.5"
                  style={active ? { background: BLACK, color: "#fff", boxShadow: "0 18px 32px rgba(0,0,0,0.18)" } : { color: "#222" }}
                  aria-current={active ? "page" : undefined}
                  title={`${group} · ${module.label}`}
                >
                  <Icon width={16} height={16} />
                  <span className="whitespace-nowrap">{module.label}</span>
                </button>
              );
            })}
          </div>
        ))}
      </nav>
    </div>
  );
}
