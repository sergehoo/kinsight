import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Link, useLocation, useNavigate } from "react-router-dom";

import {
  getDefaultItemHref,
  getItemHref,
  getModuleById,
  getModuleFromLegacyKey,
  getModuleFromPath,
  getSidebarItemFromModuleKey,
  visibleDashboardModules,
  visibleSidebarItems,
} from "@/config/modules.config";
import { Help, Home, Logout } from "@/components/overview/icons";
import { getCurrentPermissions } from "@/lib/permissions";
import { EASE_OUT } from "@/lib/motion";
import { useNavigationStore } from "@/state/navigationStore";

const PANEL_STYLE = {
  background: "rgba(255,255,255,0.72)",
  border: "1px solid rgba(255,255,255,0.74)",
  boxShadow: "0 22px 52px rgba(40,44,48,0.12)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
} as const;

function Chevrons({ open }: { open: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: open ? "none" : "rotate(180deg)" }}>
      <path d="m15 6-6 6 6 6" />
      <path d="m9 6-6 6 6 6" opacity="0.45" />
    </svg>
  );
}

export function DynamicSidebar() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const permissions = getCurrentPermissions();
  const visibleModules = visibleDashboardModules(permissions);
  const { selectedModuleId, setSelectedModule, sidebarExpanded, toggleSidebar } = useNavigationStore();
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const switcherRef = useRef<HTMLDivElement>(null);

  const legacyKey = pathname.startsWith("/modules/") ? pathname.split("/").at(-1) : undefined;
  const legacyDashboardModule =
    pathname === "/" || pathname === "/d/realEstate"
      ? getModuleById("immobilier")
      : pathname === "/d/hr"
        ? getModuleById("capital-humain")
        : pathname === "/d/finance"
          ? getModuleById("finance")
          : undefined;
  const moduleFromUrl = getModuleFromPath(pathname) ?? getModuleFromLegacyKey(legacyKey) ?? legacyDashboardModule;
  const candidate = moduleFromUrl ?? getModuleById(selectedModuleId);
  // Filet permissions : ne jamais afficher les sous-modules d'un domaine non autorisé.
  const activeModule = candidate && visibleModules.some((module) => module.id === candidate.id) ? candidate : visibleModules[0];
  const sidebarItems = activeModule ? visibleSidebarItems(activeModule, permissions) : [];

  useEffect(() => {
    if (activeModule && selectedModuleId !== activeModule.id) {
      setSelectedModule(activeModule.id);
    }
  }, [activeModule, selectedModuleId, setSelectedModule]);

  useEffect(() => {
    if (!switcherOpen) return;
    const onClick = (event: MouseEvent) => {
      if (switcherRef.current && !switcherRef.current.contains(event.target as Node)) setSwitcherOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [switcherOpen]);

  const expanded = sidebarExpanded;
  const ModuleIcon = activeModule?.icon;

  const switchModule = (moduleId: string) => {
    const next = visibleModules.find((module) => module.id === moduleId);
    if (!next) return;
    setSelectedModule(next.id);
    setSwitcherOpen(false);
    navigate(getDefaultItemHref(next, permissions));
  };

  const logout = () => {
    try {
      localStorage.removeItem("k-insight-token");
    } catch {
      /* stockage indisponible : ignore */
    }
    navigate("/");
  };

  return (
    <aside
      className="absolute left-3 top-[184px] z-30 flex max-h-[calc(100%-212px)] flex-col rounded-[30px] p-3 transition-[width] duration-300 ease-out sm:left-5 lg:left-[2%] lg:top-[205px]"
      style={{ ...PANEL_STYLE, width: expanded ? 264 : 76 }}
      aria-label="Navigation du cockpit"
    >
      {/* En-tête : module actif + sélecteur */}
      <div ref={switcherRef} className="relative shrink-0">
        <button
          type="button"
          onClick={() => (expanded ? setSwitcherOpen((open) => !open) : toggleSidebar())}
          className="flex w-full items-center gap-3 rounded-[20px] p-2 text-left transition-colors hover:bg-white/55"
          aria-haspopup="menu"
          aria-expanded={switcherOpen}
          title={expanded ? "Changer de domaine" : activeModule?.label}
        >
          <span
            className="grid h-12 w-12 shrink-0 place-items-center rounded-[16px] text-white shadow-[0_12px_24px_rgba(0,0,0,0.12)]"
            style={{ background: "#0B0B0C" }}
          >
            {ModuleIcon ? <ModuleIcon width={22} height={22} /> : null}
          </span>
          {expanded ? (
            <span className="min-w-0 flex-1">
              <span className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#9AA09D]">Domaine</span>
              <span className="block truncate text-[15px] font-bold text-[#16191A]">{activeModule?.label}</span>
            </span>
          ) : null}
          {expanded ? (
            <span className="shrink-0 text-[#7C8384]" style={{ transform: switcherOpen ? "rotate(180deg)" : "none", transition: "transform .2s" }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
            </span>
          ) : null}
        </button>

        <AnimatePresence>
          {switcherOpen && expanded ? (
            <motion.div
              role="menu"
              className="absolute left-0 right-0 top-[68px] z-40 max-h-[320px] overflow-y-auto rounded-[22px] p-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              style={PANEL_STYLE}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: EASE_OUT }}
            >
              {visibleModules.map((module) => {
                const Icon = module.icon;
                const active = module.id === activeModule?.id;
                return (
                  <button
                    key={module.id}
                    type="button"
                    role="menuitem"
                    onClick={() => switchModule(module.id)}
                    className="flex w-full items-center gap-3 rounded-[16px] px-3 py-2.5 text-left text-[13.5px] font-semibold transition-colors hover:bg-white/65"
                    style={active ? { background: "#0B0B0C", color: "#fff" } : { color: "#3C4142" }}
                  >
                    <Icon width={18} height={18} />
                    <span className="truncate">{module.label}</span>
                  </button>
                );
              })}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      <div className="my-3 h-px shrink-0 bg-[#DDE2E0]/80" />

      {/* Liste des vues du module */}
      <motion.nav
        key={activeModule?.id ?? "empty"}
        className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto pr-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, ease: EASE_OUT }}
        aria-label={activeModule?.label}
      >
        {activeModule ? (
          <Link
            to={activeModule.basePath}
            title={expanded ? undefined : "Accueil du domaine"}
            aria-current={pathname === activeModule.basePath ? "page" : undefined}
            className={`group flex items-center gap-3 rounded-[16px] transition-colors ${expanded ? "px-3 py-2.5" : "justify-center px-0 py-2.5"}`}
            style={pathname === activeModule.basePath ? { background: "#0B0B0C", color: "#fff" } : { color: "#4A4F50" }}
          >
            <span
              className={`grid h-9 w-9 shrink-0 place-items-center rounded-[12px] transition-colors ${pathname === activeModule.basePath ? "" : "group-hover:bg-white/70"}`}
              style={pathname === activeModule.basePath ? { background: "rgba(255,255,255,0.16)" } : undefined}
            >
              <Home width={19} height={19} />
            </span>
            {expanded ? <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold">Accueil</span> : null}
          </Link>
        ) : null}
        {sidebarItems.map((item) => {
          const href = activeModule ? getItemHref(activeModule, item) : "#";
          const activeFromUrl = activeModule ? pathname === href : false;
          const activeFromLegacy = activeModule ? getSidebarItemFromModuleKey(activeModule, legacyKey)?.moduleKey === item.moduleKey : false;
          const active = activeFromUrl || activeFromLegacy;
          const Icon = item.icon;
          return (
            <Link
              key={`${activeModule?.id}-${item.path}`}
              to={href}
              title={expanded ? undefined : item.label}
              aria-current={active ? "page" : undefined}
              className={`group flex items-center gap-3 rounded-[16px] transition-colors ${expanded ? "px-3 py-2.5" : "justify-center px-0 py-2.5"}`}
              style={active ? { background: "#0B0B0C", color: "#fff" } : { color: "#4A4F50" }}
            >
              <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-[12px] transition-colors ${active ? "" : "group-hover:bg-white/70"}`} style={active ? { background: "rgba(255,255,255,0.16)" } : undefined}>
                <Icon width={19} height={19} />
              </span>
              {expanded ? <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold">{item.label}</span> : null}
              {expanded && active ? <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: activeModule?.icon ? "#FF8735" : "#fff" }} /> : null}
            </Link>
          );
        })}
      </motion.nav>

      <div className="mt-2 flex shrink-0 flex-col gap-1 border-t border-[#DDE2E0]/80 pt-2">
        <Link
          to="/dashboard/rapports/catalog"
          title={expanded ? undefined : "Aide"}
          className={`flex items-center gap-3 rounded-[16px] text-[#4A4F50] transition-colors hover:bg-white/60 ${expanded ? "px-3 py-2.5" : "justify-center py-2.5"}`}
        >
          <span className="grid h-9 w-9 shrink-0 place-items-center"><Help width={19} height={19} /></span>
          {expanded ? <span className="text-[13.5px] font-semibold">Aide & catalogue</span> : null}
        </Link>
        <button
          type="button"
          onClick={logout}
          title={expanded ? undefined : "Déconnexion"}
          className={`flex items-center gap-3 rounded-[16px] text-[#4A4F50] transition-colors hover:bg-white/60 ${expanded ? "px-3 py-2.5" : "justify-center py-2.5"}`}
        >
          <span className="grid h-9 w-9 shrink-0 place-items-center"><Logout width={19} height={19} /></span>
          {expanded ? <span className="text-[13.5px] font-semibold">Déconnexion</span> : null}
        </button>
        <button
          type="button"
          onClick={toggleSidebar}
          className={`mt-1 flex items-center gap-3 rounded-[16px] bg-white/55 text-[#3C4142] transition-colors hover:bg-white/80 ${expanded ? "px-3 py-2" : "justify-center py-2"}`}
          aria-label={expanded ? "Replier la navigation" : "Déplier la navigation"}
        >
          <span className="grid h-7 w-7 shrink-0 place-items-center"><Chevrons open={expanded} /></span>
          {expanded ? <span className="text-[12.5px] font-bold">Replier</span> : null}
        </button>
      </div>
    </aside>
  );
}
