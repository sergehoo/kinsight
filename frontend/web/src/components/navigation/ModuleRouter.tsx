import { useEffect } from "react";
import { Navigate, useParams } from "react-router-dom";

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
