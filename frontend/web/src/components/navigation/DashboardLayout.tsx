import type * as React from "react";

import { AttendancePage } from "@/pages/AttendancePage";
import { ModulePage } from "@/pages/ModulePage";

interface DashboardLayoutProps {
  moduleKey: string;
}

/** Les modules qui ont une PAGE RÉELLE, branchée sur une source vivante.
 *
 *  `ModulePage` rend le catalogue de présentation de `lib/modules.tsx` : des
 *  libellés attendus, sans valeur, adossés à des tables de mart déclarées. C'est
 *  le bon rendu tant qu'une source manque, et le mauvais dès qu'une source
 *  existe — il continuerait d'afficher « N/D » à côté d'un endpoint qui répond.
 *
 *  Ce registre est le point de bascule, et le seul : la résolution de module, la
 *  visibilité des entrées de menu et le contrôle de permissions restent dans
 *  `ModuleRouter`, inchangés. Brancher un module de plus tiendra en une ligne.
 */
const PAGES_REELLES: Record<string, React.ComponentType> = {
  // Présence : servie par Kaydan Shield (`/integrations/shield/hr-kpi/` et
  // `/attendance-series/`). La table `mart.hr_attendance_kpi` que le catalogue
  // déclarait n'existe nulle part dans le dépôt.
  "hr-attendance": AttendancePage,
};

export function DashboardLayout({ moduleKey }: DashboardLayoutProps) {
  const PageReelle = PAGES_REELLES[moduleKey];
  return PageReelle ? <PageReelle /> : <ModulePage moduleKey={moduleKey} />;
}
