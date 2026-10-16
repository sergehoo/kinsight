import { useEffect } from "react";
import { Navigate, useLocation, useParams } from "react-router-dom";

import { ANCIENNES_VUES_RH } from "@/config/sectionsRh";

import {
  getDefaultItemHref,
  getModuleByBaseSlug,
  getSidebarItemFromPath,
  visibleDashboardModules,
  visibleSidebarItems,
} from "@/config/modules.config";
import { getCurrentPermissions } from "@/lib/permissions";
import { useNavigationStore } from "@/state/navigationStore";

import { DashboardLayout } from "./DashboardLayout";
import { PermissionGuard } from "./PermissionGuard";

export function ModuleRouter() {
  const { moduleId, itemId } = useParams();
  const { search } = useLocation();
  const permissions = getCurrentPermissions();
  const module = getModuleByBaseSlug(moduleId);
  const visibleModules = visibleDashboardModules(permissions);
  const { setSelectedModule } = useNavigationStore();

  useEffect(() => {
    if (module) {
      setSelectedModule(module.id);
    }
  }, [module, setSelectedModule]);

  if (!module) {
    const [firstModule] = visibleModules;
    return <Navigate to={firstModule ? getDefaultItemHref(firstModule, permissions) : "/dashboard"} replace />;
  }

  // Anciennes vues du Capital Humain, devenues des onglets : redirection
  // permanente vers la section, filtres conservés.
  const ancienne = module.id === "capital-humain" ? ANCIENNES_VUES_RH[`/${itemId}`] : undefined;
  if (ancienne) {
    const suite = new URLSearchParams(search);
    suite.set("onglet", ancienne.onglet);
    return <Navigate to={`${module.basePath}${ancienne.section}?${suite.toString()}`} replace />;
  }

  const visibleItems = visibleSidebarItems(module, permissions);
  const item = getSidebarItemFromPath(module, itemId);
  if (!item || !visibleItems.some((visibleItem) => visibleItem.path === item.path)) {
    return <Navigate to={getDefaultItemHref(module, permissions)} replace />;
  }

  return (
    <PermissionGuard requiredPermissions={[...module.requiredPermissions, ...(item.requiredPermissions ?? [])]}>
      <DashboardLayout moduleKey={item.moduleKey} />
    </PermissionGuard>
  );
}
