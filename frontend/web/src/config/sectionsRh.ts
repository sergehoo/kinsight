/** Sections du Capital Humain : 20 liens de barre latérale regroupés en 8 entrées.
 *
 *  Chaque section rassemble des modules existants en ONGLETS : aucune page n'est
 *  recréée, chaque onglet rend la page (et les données, et la RBAC) de son module.
 *  Les anciennes adresses (`/dashboard/capital-humain/presence`…) redirigent vers
 *  leur section et leur onglet : aucun lien partagé ni aucun lien interne ne casse.
 *
 *  Droits : un onglet suit la permission de son module (paie, carrière,
 *  performance renforcées ; pages affectées d'un Assistant RH). Une section n'est
 *  proposée que si au moins un de ses onglets l'est.
 */
import { canAccess, type Permission } from "@/lib/permissions";

export interface OngletRh {
  cle: string;
  libelle: string;
  /** Module rendu par l'onglet — et dont la permission gouverne l'onglet. */
  moduleKey: string;
  /** Composant propre (structure des effectifs Shield) au lieu de la page du module. */
  composant?: "structure";
  requiredPermissions?: Permission[];
}

export interface SectionRh {
  key: string;
  path: `/${string}`;
  titre: string;
  sousTitre: string;
  onglets: OngletRh[];
}

export const SECTIONS_RH: SectionRh[] = [
  {
    key: "hr-section-effectifs", path: "/effectifs", titre: "Effectifs & Organisation",
    sousTitre: "Structure des effectifs Kaydan Shield (contrats, départements, postes, sociétés), organisation et planification.",
    onglets: [
      { cle: "structure", libelle: "Structure des effectifs", moduleKey: "hr-workforce", composant: "structure" },
      { cle: "hr-workforce", libelle: "Workforce Analytics", moduleKey: "hr-workforce" },
      { cle: "hr-organization", libelle: "Organigramme", moduleKey: "hr-organization" },
      { cle: "hr-planning", libelle: "Workforce Planning", moduleKey: "hr-planning" },
    ],
  },
  {
    key: "hr-section-temps", path: "/temps-presence", titre: "Temps & Présence",
    sousTitre: "Pointages Kaydan Shield sur la période et aujourd'hui, congés.",
    onglets: [
      { cle: "hr-attendance", libelle: "Présence", moduleKey: "hr-attendance" },
      { cle: "hr-leave", libelle: "Congés", moduleKey: "hr-leave" },
    ],
  },
  {
    key: "hr-section-recrutement", path: "/recrutement-integration", titre: "Recrutement & Intégration",
    sousTitre: "Postes à pourvoir, candidatures et intégration des nouveaux collaborateurs.",
    onglets: [
      { cle: "hr-recruitment", libelle: "Recrutement", moduleKey: "hr-recruitment" },
      { cle: "hr-onboarding", libelle: "Onboarding", moduleKey: "hr-onboarding" },
    ],
  },
  {
    key: "hr-section-talents", path: "/talents", titre: "Performance & Talents",
    sousTitre: "Performance, formation, compétences et carrières.",
    onglets: [
      { cle: "hr-performance", libelle: "Performance", moduleKey: "hr-performance", requiredPermissions: ["view_hr_performance"] },
      { cle: "hr-training", libelle: "Formation", moduleKey: "hr-training" },
      { cle: "hr-skills", libelle: "Compétences", moduleKey: "hr-skills" },
      { cle: "hr-career", libelle: "Carrière", moduleKey: "hr-career", requiredPermissions: ["view_hr_career"] },
    ],
  },
  {
    key: "hr-section-conformite", path: "/engagement-conformite", titre: "Engagement & Conformité",
    sousTitre: "Engagement, santé & sécurité, conformité RH et productivité.",
    onglets: [
      { cle: "hr-experience", libelle: "Engagement", moduleKey: "hr-experience" },
      { cle: "hr-health-safety", libelle: "Santé & Sécurité", moduleKey: "hr-health-safety" },
      { cle: "hr-compliance", libelle: "Conformité RH", moduleKey: "hr-compliance" },
      { cle: "hr-productivity", libelle: "Productivité", moduleKey: "hr-productivity" },
    ],
  },
  {
    key: "hr-section-intelligence", path: "/intelligence", titre: "Intelligence RH",
    sousTitre: "Aide à la décision, signaux et seuils, rapports et exports programmés.",
    onglets: [
      { cle: "hr-ai", libelle: "IA RH", moduleKey: "hr-ai" },
      { cle: "hr-alerts", libelle: "Centre d'alertes", moduleKey: "hr-alerts" },
      { cle: "hr-reports", libelle: "Rapports", moduleKey: "hr-reports" },
    ],
  },
];

/** Anciennes vues → section + onglet (redirections permanentes). */
export const ANCIENNES_VUES_RH: Record<string, { section: string; onglet: string }> = Object.fromEntries(
  ([
    ["/workforce", "hr-workforce"], ["/organigramme", "hr-organization"], ["/planning", "hr-planning"],
    ["/presence", "hr-attendance"], ["/conges", "hr-leave"],
    ["/recrutement", "hr-recruitment"], ["/onboarding", "hr-onboarding"],
    ["/performance", "hr-performance"], ["/formation", "hr-training"], ["/competences", "hr-skills"], ["/carriere", "hr-career"],
    ["/engagement", "hr-experience"], ["/sante-securite", "hr-health-safety"], ["/conformite", "hr-compliance"],
    ["/productivite", "hr-productivity"],
    ["/ia", "hr-ai"], ["/alertes", "hr-alerts"], ["/rapports", "hr-reports"],
  ] as const).map(([chemin, onglet]) => [chemin, { section: sectionDuModule(onglet)!.path, onglet }]),
);

export function sectionParCle(cle: string | undefined): SectionRh | undefined {
  return SECTIONS_RH.find((s) => s.key === cle);
}

export function sectionDuModule(moduleKey: string): SectionRh | undefined {
  return SECTIONS_RH.find((s) => s.onglets.some((o) => o.moduleKey === moduleKey && !o.composant));
}

/** Un onglet est visible si son module l'est : permission renforcée, et pour un
 *  Assistant RH, module affecté (`hr_module:<clé>` servi par /auth/me). */
export function ongletVisible(o: OngletRh, permissions: readonly Permission[], role: string): boolean {
  if (!canAccess(o.requiredPermissions, [...permissions])) return false;
  if (role === "ASSISTANT_RH") return permissions.includes(`hr_module:${o.moduleKey}`);
  return true;
}

export function ongletsVisibles(section: SectionRh, permissions: readonly Permission[], role: string): OngletRh[] {
  return section.onglets.filter((o) => ongletVisible(o, permissions, role));
}
