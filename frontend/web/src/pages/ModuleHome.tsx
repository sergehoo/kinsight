import { useEffect } from "react";
import { Navigate, useParams } from "react-router-dom";

import { getDefaultItemHref, getModuleByBaseSlug, visibleDashboardModules } from "@/config/modules.config";
import { getDomainHero } from "@/config/domainHome.config";
import { canAccess, getCurrentPermissions } from "@/lib/permissions";
import { useNavigationStore } from "@/state/navigationStore";

import { DomainHome } from "./DomainHome";

/** Page d'accueil hero d'un domaine (/dashboard/:moduleId). */
export function ModuleHome() {
  const { moduleId } = useParams();
  const permissions = getCurrentPermissions();
  const module = getModuleByBaseSlug(moduleId);
  const { setSelectedModule } = useNavigationStore();

  useEffect(() => {
    if (module) setSelectedModule(module.id);
  }, [module, setSelectedModule]);

  if (!module || !canAccess(module.requiredPermissions, permissions)) {
    const [first] = visibleDashboardModules(permissions);
    return <Navigate to={first ? first.basePath : "/dashboard"} replace />;
  }

  const spec = getDomainHero(module.id);
  if (!spec) {
    // Domaine sans page d'accueil dédiée → ouvrir directement son premier sous-module.
    return <Navigate to={getDefaultItemHref(module, permissions)} replace />;
  }

  return <DomainHome spec={spec} module={module} />;
}
