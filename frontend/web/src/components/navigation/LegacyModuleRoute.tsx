import { Navigate, useLocation, useParams } from "react-router-dom";

import { visibleDashboardModules, visibleSidebarItems } from "@/config/modules.config";
import { getCurrentPermissions } from "@/lib/permissions";
import { ModulePage } from "@/pages/ModulePage";

/** `/modules/:key` — l'ancienne adresse d'un module.
 *
 *  Pour le Capital Humain, elle rendait `ModulePage` SANS les garde-fous de la
 *  route canonique : aucun contrôle de permission côté écran (le serveur
 *  refusait les données, mais la page s'ouvrait), et `/modules/hr-attendance`
 *  affichait le catalogue au lieu de la vraie page Présence. Elle redirige
 *  désormais vers `/dashboard/capital-humain/<vue>`, filtres conservés — ou vers
 *  l'accueil si le rôle ne voit pas ce module. Les autres domaines sont
 *  inchangés. */
export function LegacyModuleRoute() {
  const { key } = useParams();
  const { search } = useLocation();
  if (!key?.startsWith("hr-")) return <ModulePage />;

  const permissions = getCurrentPermissions();
  for (const module of visibleDashboardModules(permissions)) {
    const item = visibleSidebarItems(module, permissions).find((i) => i.moduleKey === key);
    // Le domaine Capital Humain d'abord : la même clé figure aussi dans la Vue Groupe.
    if (item && module.id === "capital-humain") return <Navigate to={`${module.basePath}${item.path}${search}`} replace />;
  }
  return <Navigate to="/dashboard" replace />;
}
