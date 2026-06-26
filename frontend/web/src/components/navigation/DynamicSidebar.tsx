import { useEffect } from "react";
import { motion } from "framer-motion";
import { useLocation, useNavigate } from "react-router-dom";

import {
  getItemHref,
  getModuleById,
  getModuleFromLegacyKey,
  getModuleFromPath,
  getSidebarItemFromModuleKey,
  visibleDashboardModules,
  visibleSidebarItems,
} from "@/config/modules.config";
import { Help, Logout } from "@/components/overview/icons";
import { getCurrentPermissions } from "@/lib/permissions";
import { EASE_OUT } from "@/lib/motion";
import { useNavigationStore } from "@/state/navigationStore";

import { CircleButton } from "../chrome/CircleButton";

export function DynamicSidebar() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const permissions = getCurrentPermissions();
  const visibleModules = visibleDashboardModules(permissions);
  const { selectedModuleId, setSelectedModule } = useNavigationStore();
  const legacyKey = pathname.startsWith("/modules/") ? pathname.split("/").at(-1) : undefined;
  const moduleFromUrl = getModuleFromPath(pathname) ?? getModuleFromLegacyKey(legacyKey);
  const activeModule = moduleFromUrl ?? getModuleById(selectedModuleId) ?? visibleModules[0];
  const sidebarItems = activeModule ? visibleSidebarItems(activeModule, permissions) : [];

  useEffect(() => {
    if (activeModule && selectedModuleId !== activeModule.id) {
      setSelectedModule(activeModule.id);
    }
  }, [activeModule, selectedModuleId, setSelectedModule]);

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
      className="absolute left-3 top-[184px] z-30 flex max-h-[calc(100%-212px)] w-[72px] flex-col rounded-full px-2 py-4 sm:left-5 lg:left-[2.2%] lg:top-[205px]"
      style={{
        background: "rgba(255,255,255,0.66)",
        border: "1px solid rgba(255,255,255,0.72)",
        boxShadow: "0 18px 42px rgba(40,44,48,0.08)",
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
      }}
    >
      <motion.div
        key={activeModule?.id ?? "empty"}
        className="flex min-h-0 flex-1 flex-col items-center gap-3 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        style={{ scrollbarWidth: "none" }}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.32, ease: EASE_OUT }}
      >
        {sidebarItems.map((item) => {
          const activeFromDashboardUrl = activeModule ? pathname === getItemHref(activeModule, item) : false;
          const activeFromLegacyUrl = activeModule ? getSidebarItemFromModuleKey(activeModule, legacyKey)?.moduleKey === item.moduleKey : false;
          const Icon = item.icon;
          return (
            <CircleButton
              key={`${activeModule?.id}-${item.path}`}
              label={item.label}
              to={activeModule ? getItemHref(activeModule, item) : undefined}
              active={activeFromDashboardUrl || activeFromLegacyUrl}
            >
              <Icon width={20} height={20} />
            </CircleButton>
          );
        })}
      </motion.div>

      <div className="mt-3 flex shrink-0 flex-col items-center gap-3 border-t border-[#DDE2E0]/80 pt-3">
        <CircleButton label="Aide" to="/dashboard/reports/catalog" active={pathname === "/dashboard/reports/catalog"}>
          <Help width={20} height={20} />
        </CircleButton>
        <CircleButton label="Deconnexion" onClick={logout}>
          <Logout width={20} height={20} />
        </CircleButton>
      </div>
    </aside>
  );
}
