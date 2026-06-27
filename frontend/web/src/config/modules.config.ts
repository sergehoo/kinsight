import type * as React from "react";

import {
  BarChart,
  Bell,
  Briefcase,
  Building,
  Calculator,
  Calendar,
  Cart,
  ChartPie,
  CheckCircle,
  Cog,
  DollarCircle,
  FileText,
  Grid,
  Help,
  Layers,
  Network,
  Receipt,
  Shield,
  Target,
  User,
  Users,
  Wallet,
} from "@/components/overview/icons";
import { canAccess, DOMAIN_PERMISSION, type Permission } from "@/lib/permissions";

export type ModuleIcon = React.ComponentType<React.SVGProps<SVGSVGElement>>;

export interface SidebarItemConfig {
  label: string;
  path: `/${string}`;
  icon: ModuleIcon;
  moduleKey: string;
  requiredPermissions?: Permission[];
  featureFlag?: string;
}

export interface DashboardModuleConfig {
  id: string;
  label: string;
  icon: ModuleIcon;
  basePath: `/dashboard/${string}`;
  group: string;
  requiredPermissions: Permission[];
  sidebarItems: SidebarItemConfig[];
  defaultRoute: `/${string}`;
  featureFlag?: string;
  filters?: string[];
}

const FILTERS_RE = ["Période", "Filiale", "Programme", "Chantier", "Statut"];
const FILTERS_HR = ["Période", "Filiale", "Département", "Site", "Métier"];
const FILTERS_FIN = ["Période", "Filiale", "Centre de coût", "Compte", "Devise"];
const FILTERS_OPS = ["Période", "Filiale", "Site", "Fournisseur", "Statut"];
const FILTERS_COM = ["Période", "Filiale", "Programme", "Commercial", "Canal"];
const FILTERS_RISK = ["Période", "Domaine", "Filiale", "Criticité", "Statut"];

/**
 * Taxonomie de navigation K-Insight : la topbar pilote les 9 grands domaines,
 * la sidebar charge dynamiquement les sous-modules du domaine sélectionné.
 * Ajouter un domaine = ajouter une entrée ici (aucune autre partie de l'app à modifier).
 */
export const dashboardModules: DashboardModuleConfig[] = [
  {
    id: "overview",
    label: "Overview Groupe",
    icon: Grid,
    basePath: "/dashboard/overview-groupe",
    group: "Pilotage",
    requiredPermissions: [DOMAIN_PERMISSION.overview],
    defaultRoute: "/executive",
    featureFlag: "domain_overview",
    filters: ["Période", "Filiale", "Domaine", "Site"],
    sidebarItems: [
      { label: "Vue Exécutive", path: "/executive", icon: Target, moduleKey: "groupe" },
      { label: "Performance Groupe", path: "/performance", icon: BarChart, moduleKey: "group-performance" },
      { label: "Filiales", path: "/filiales", icon: Layers, moduleKey: "group-subsidiaries" },
      { label: "Finances Consolidées", path: "/finances", icon: Wallet, moduleKey: "finance-executive" },
      { label: "Capital Humain Groupe", path: "/capital-humain", icon: Users, moduleKey: "hr-executive" },
      { label: "Immobilier Groupe", path: "/immobilier", icon: Building, moduleKey: "executive" },
      { label: "Opérations Groupe", path: "/operations", icon: Cog, moduleKey: "ops-executive" },
      { label: "Risques Groupe", path: "/risques", icon: Shield, moduleKey: "risk-executive" },
      { label: "Alertes Stratégiques", path: "/alertes", icon: Bell, moduleKey: "alerts" },
      { label: "IA Synthèse CODIR", path: "/ia-codir", icon: CheckCircle, moduleKey: "ai" },
      { label: "Rapports Groupe", path: "/rapports", icon: FileText, moduleKey: "reports" },
    ],
  },
  {
    id: "immobilier",
    label: "Immobilier",
    icon: Building,
    basePath: "/dashboard/immobilier",
    group: "Métiers",
    requiredPermissions: [DOMAIN_PERMISSION.immobilier],
    defaultRoute: "/overview",
    featureFlag: "domain_immobilier",
    filters: FILTERS_RE,
    sidebarItems: [
      { label: "Executive Overview", path: "/overview", icon: Target, moduleKey: "executive" },
      { label: "Portfolio Immobilier", path: "/portfolio", icon: Briefcase, moduleKey: "portfolio" },
      { label: "Gouvernance Foncière", path: "/foncier", icon: Layers, moduleKey: "land" },
      { label: "Programmes Immobiliers", path: "/programmes", icon: Building, moduleKey: "programmes" },
      { label: "Construction", path: "/construction", icon: Building, moduleKey: "construction" },
      { label: "VRD", path: "/vrd", icon: Network, moduleKey: "vrd" },
      { label: "Commercialisation", path: "/commercialisation", icon: Target, moduleKey: "commercialisation" },
      { label: "Gestion Locative", path: "/locatif", icon: Receipt, moduleKey: "rental" },
      { label: "Finance Projet", path: "/finance", icon: Wallet, moduleKey: "finance" },
      { label: "Stocks Chantier", path: "/stocks", icon: Cart, moduleKey: "inventory" },
      { label: "Ressources Chantier", path: "/ressources", icon: Users, moduleKey: "chantier-resources" },
      { label: "Sécurité Chantier", path: "/securite", icon: Shield, moduleKey: "security" },
      { label: "Maintenance", path: "/maintenance", icon: Cog, moduleKey: "maintenance" },
      { label: "Clients", path: "/clients", icon: User, moduleKey: "clients" },
      { label: "Risques Immobiliers", path: "/risques", icon: ChartPie, moduleKey: "risques" },
      { label: "Prévisions IA", path: "/ia", icon: CheckCircle, moduleKey: "ai" },
      { label: "Rapports Immobilier", path: "/rapports", icon: FileText, moduleKey: "reports" },
    ],
  },
  {
    id: "capital-humain",
    label: "Capital Humain",
    icon: Users,
    basePath: "/dashboard/capital-humain",
    group: "Métiers",
    requiredPermissions: [DOMAIN_PERMISSION.capitalHumain],
    defaultRoute: "/overview",
    featureFlag: "domain_hr",
    filters: FILTERS_HR,
    sidebarItems: [
      { label: "Executive HR Overview", path: "/overview", icon: Target, moduleKey: "hr-executive" },
      { label: "Workforce Analytics", path: "/workforce", icon: Users, moduleKey: "hr-workforce" },
      { label: "Organigramme", path: "/organigramme", icon: Network, moduleKey: "hr-organization" },
      { label: "Présence", path: "/presence", icon: CheckCircle, moduleKey: "hr-attendance" },
      { label: "Congés", path: "/conges", icon: Calendar, moduleKey: "hr-leave" },
      { label: "Recrutement", path: "/recrutement", icon: Briefcase, moduleKey: "hr-recruitment" },
      { label: "Onboarding", path: "/onboarding", icon: CheckCircle, moduleKey: "hr-onboarding" },
      { label: "Paie", path: "/paie", icon: Wallet, moduleKey: "hr-payroll", requiredPermissions: ["view_hr_payroll"] },
      { label: "Performance", path: "/performance", icon: BarChart, moduleKey: "hr-performance" },
      { label: "Formation", path: "/formation", icon: FileText, moduleKey: "hr-training" },
      { label: "Compétences", path: "/competences", icon: Grid, moduleKey: "hr-skills" },
      { label: "Carrière", path: "/carriere", icon: CheckCircle, moduleKey: "hr-career" },
      { label: "Engagement", path: "/engagement", icon: User, moduleKey: "hr-experience" },
      { label: "Santé & Sécurité", path: "/sante-securite", icon: Shield, moduleKey: "hr-health-safety" },
      { label: "Conformité RH", path: "/conformite", icon: Receipt, moduleKey: "hr-compliance" },
      { label: "Productivité", path: "/productivite", icon: BarChart, moduleKey: "hr-productivity" },
      { label: "Workforce Planning", path: "/planning", icon: ChartPie, moduleKey: "hr-planning" },
      { label: "IA RH", path: "/ia", icon: CheckCircle, moduleKey: "hr-ai" },
      { label: "Centre d'Alertes RH", path: "/alertes", icon: Bell, moduleKey: "hr-alerts" },
      { label: "Rapports RH", path: "/rapports", icon: FileText, moduleKey: "hr-reports" },
    ],
  },
  {
    id: "finance",
    label: "Finance",
    icon: Wallet,
    basePath: "/dashboard/finance",
    group: "Métiers",
    requiredPermissions: [DOMAIN_PERMISSION.finance],
    defaultRoute: "/overview",
    featureFlag: "domain_finance",
    filters: FILTERS_FIN,
    sidebarItems: [
      { label: "Executive Finance Overview", path: "/overview", icon: Target, moduleKey: "finance-executive" },
      { label: "Trésorerie", path: "/tresorerie", icon: DollarCircle, moduleKey: "finance-treasury" },
      { label: "Encaissements", path: "/encaissements", icon: Receipt, moduleKey: "finance-cash-in" },
      { label: "Décaissements", path: "/decaissements", icon: Receipt, moduleKey: "finance-cash-out" },
      { label: "Budget", path: "/budget", icon: Calculator, moduleKey: "finance-budget" },
      { label: "Comptabilité", path: "/comptabilite", icon: Calculator, moduleKey: "finance-accounting" },
      { label: "Balance", path: "/balance", icon: FileText, moduleKey: "finance-balance" },
      { label: "Grand Livre", path: "/grand-livre", icon: FileText, moduleKey: "finance-ledger" },
      { label: "Factures", path: "/factures", icon: Receipt, moduleKey: "finance-invoices" },
      { label: "Créances", path: "/creances", icon: DollarCircle, moduleKey: "finance-receivables" },
      { label: "Dettes", path: "/dettes", icon: DollarCircle, moduleKey: "finance-payables" },
      { label: "Recouvrement", path: "/recouvrement", icon: Target, moduleKey: "finance-recovery" },
      { label: "Analyse Rentabilité", path: "/rentabilite", icon: ChartPie, moduleKey: "finance-profitability" },
      { label: "Fiscalité", path: "/fiscalite", icon: Calculator, moduleKey: "finance-tax" },
      { label: "Prévisions Financières", path: "/previsions", icon: CheckCircle, moduleKey: "finance-forecast" },
      { label: "Risques Financiers", path: "/risques", icon: Shield, moduleKey: "finance-risks" },
      { label: "Rapports Finance", path: "/rapports", icon: FileText, moduleKey: "finance-reports" },
    ],
  },
  {
    id: "operations",
    label: "Opérations",
    icon: Cog,
    basePath: "/dashboard/operations",
    group: "Métiers",
    requiredPermissions: [DOMAIN_PERMISSION.operations],
    defaultRoute: "/overview",
    featureFlag: "domain_operations",
    filters: FILTERS_OPS,
    sidebarItems: [
      { label: "Executive Operations Overview", path: "/overview", icon: Target, moduleKey: "ops-executive" },
      { label: "Stocks & Logistique", path: "/stocks", icon: Cart, moduleKey: "inventory" },
      { label: "Achats", path: "/achats", icon: Cart, moduleKey: "ops-purchasing" },
      { label: "Approvisionnements", path: "/approvisionnements", icon: Network, moduleKey: "ops-supply" },
      { label: "Inventaires", path: "/inventaires", icon: Grid, moduleKey: "ops-stocktaking" },
      { label: "Flotte", path: "/flotte", icon: Briefcase, moduleKey: "ops-fleet" },
      { label: "Maintenance", path: "/maintenance", icon: Cog, moduleKey: "maintenance" },
      { label: "Projets", path: "/projets", icon: Network, moduleKey: "work-areas" },
      { label: "Équipements", path: "/equipements", icon: Cog, moduleKey: "ops-equipment" },
      { label: "Fournisseurs", path: "/fournisseurs", icon: Briefcase, moduleKey: "ops-suppliers" },
      { label: "Productivité", path: "/productivite", icon: BarChart, moduleKey: "ops-productivity" },
      { label: "Coûts Opérationnels", path: "/couts", icon: Wallet, moduleKey: "ops-costs" },
      { label: "Risques Opérationnels", path: "/risques", icon: ChartPie, moduleKey: "ops-risks" },
      { label: "Rapports Opérations", path: "/rapports", icon: FileText, moduleKey: "ops-reports" },
    ],
  },
  {
    id: "commercial-clients",
    label: "Commercial & Clients",
    icon: Target,
    basePath: "/dashboard/commercial-clients",
    group: "Métiers",
    requiredPermissions: [DOMAIN_PERMISSION.commercial],
    defaultRoute: "/overview",
    featureFlag: "domain_commercial",
    filters: FILTERS_COM,
    sidebarItems: [
      { label: "Executive Commercial Overview", path: "/overview", icon: Target, moduleKey: "com-executive" },
      { label: "CRM", path: "/crm", icon: Network, moduleKey: "com-crm" },
      { label: "Pipeline", path: "/pipeline", icon: BarChart, moduleKey: "com-pipeline" },
      { label: "Prospects", path: "/prospects", icon: Users, moduleKey: "com-prospects" },
      { label: "Clients", path: "/clients", icon: User, moduleKey: "clients" },
      { label: "Ventes", path: "/ventes", icon: Target, moduleKey: "com-sales" },
      { label: "Réservations", path: "/reservations", icon: Calendar, moduleKey: "com-reservations" },
      { label: "Contrats", path: "/contrats", icon: Receipt, moduleKey: "com-contracts" },
      { label: "Réclamations", path: "/reclamations", icon: Bell, moduleKey: "com-complaints" },
      { label: "Satisfaction Client", path: "/satisfaction", icon: CheckCircle, moduleKey: "com-satisfaction" },
      { label: "Fidélisation", path: "/fidelisation", icon: User, moduleKey: "com-loyalty" },
      { label: "Performance Commerciale", path: "/performance", icon: BarChart, moduleKey: "com-performance" },
      { label: "Prévisions Ventes", path: "/previsions", icon: CheckCircle, moduleKey: "com-forecast" },
      { label: "Rapports Commercial", path: "/rapports", icon: FileText, moduleKey: "com-reports" },
    ],
  },
  {
    id: "risques-conformite",
    label: "Risques & Conformité",
    icon: Shield,
    basePath: "/dashboard/risques-conformite",
    group: "Gouvernance",
    requiredPermissions: [DOMAIN_PERMISSION.risque],
    defaultRoute: "/overview",
    featureFlag: "domain_risk",
    filters: FILTERS_RISK,
    sidebarItems: [
      { label: "Executive Risk Overview", path: "/overview", icon: Target, moduleKey: "risk-executive" },
      { label: "Alertes Critiques", path: "/alertes", icon: Bell, moduleKey: "alerts" },
      { label: "Audit", path: "/audit", icon: CheckCircle, moduleKey: "risk-audit" },
      { label: "Conformité", path: "/conformite", icon: Receipt, moduleKey: "risk-compliance" },
      { label: "Sécurité", path: "/securite", icon: Shield, moduleKey: "security" },
      { label: "Contrôle d'Accès", path: "/controle-acces", icon: Shield, moduleKey: "risk-access-control" },
      { label: "Incidents", path: "/incidents", icon: Bell, moduleKey: "risk-incidents" },
      { label: "Documents Critiques", path: "/documents", icon: FileText, moduleKey: "risk-documents" },
      { label: "Risques Juridiques", path: "/juridique", icon: FileText, moduleKey: "risk-legal" },
      { label: "Risques Financiers", path: "/risques-financiers", icon: Wallet, moduleKey: "finance-risks" },
      { label: "Risques Opérationnels", path: "/risques-operationnels", icon: Cog, moduleKey: "ops-risks" },
      { label: "Cartographie des Risques", path: "/cartographie", icon: ChartPie, moduleKey: "risk-mapping" },
      { label: "Rapports Risques", path: "/rapports", icon: FileText, moduleKey: "risk-reports" },
    ],
  },
  {
    id: "ia",
    label: "IA Gouvernance",
    icon: CheckCircle,
    basePath: "/dashboard/ia-gouvernance",
    group: "Gouvernance",
    requiredPermissions: [DOMAIN_PERMISSION.ia],
    defaultRoute: "/groupe",
    featureFlag: "domain_ai",
    filters: ["Période", "Domaine", "Filiale", "Scénario"],
    sidebarItems: [
      { label: "IA Groupe", path: "/groupe", icon: CheckCircle, moduleKey: "ai" },
      { label: "IA Immobilier", path: "/immobilier", icon: Building, moduleKey: "ai" },
      { label: "IA Capital Humain", path: "/capital-humain", icon: Users, moduleKey: "hr-ai" },
      { label: "IA Finance", path: "/finance", icon: Wallet, moduleKey: "finance-forecast" },
      { label: "Alertes IA", path: "/alertes", icon: Bell, moduleKey: "alerts" },
    ],
  },
  {
    id: "rapports",
    label: "Rapports",
    icon: FileText,
    basePath: "/dashboard/rapports",
    group: "Gouvernance",
    requiredPermissions: [DOMAIN_PERMISSION.reports],
    defaultRoute: "/groupe",
    featureFlag: "domain_reports",
    filters: ["Période", "Domaine", "Filiale", "Format"],
    sidebarItems: [
      { label: "Rapports Groupe", path: "/groupe", icon: FileText, moduleKey: "reports" },
      { label: "Rapports Immobilier", path: "/immobilier", icon: Building, moduleKey: "reports" },
      { label: "Rapports Capital Humain", path: "/capital-humain", icon: Users, moduleKey: "hr-reports" },
      { label: "Rapports Finance", path: "/finance", icon: Wallet, moduleKey: "finance-reports" },
      { label: "Rapports Opérations", path: "/operations", icon: Cog, moduleKey: "ops-reports" },
      { label: "Rapports Commercial", path: "/commercial", icon: Target, moduleKey: "com-reports" },
      { label: "Aide & Catalogue", path: "/catalog", icon: Help, moduleKey: "aide" },
    ],
  },
];

export function visibleDashboardModules(permissions: readonly Permission[]) {
  return dashboardModules.filter((module) => canAccess(module.requiredPermissions, [...permissions]));
}

export function visibleSidebarItems(module: DashboardModuleConfig, permissions: readonly Permission[]) {
  return module.sidebarItems.filter((item) => canAccess(item.requiredPermissions, [...permissions]));
}

export function getModuleById(moduleId: string | undefined) {
  return dashboardModules.find((module) => module.id === moduleId);
}

export function getModuleByBaseSlug(slug: string | undefined) {
  if (!slug) return undefined;
  return dashboardModules.find((module) => module.basePath.split("/").at(-1) === slug || module.id === slug);
}

export function getModuleFromPath(pathname: string) {
  return dashboardModules.find((module) => pathname === module.basePath || pathname.startsWith(`${module.basePath}/`));
}

export function getModuleFromLegacyKey(moduleKey: string | undefined) {
  if (!moduleKey) return undefined;
  return dashboardModules.find((module) => module.sidebarItems.some((item) => item.moduleKey === moduleKey));
}

export function getSidebarItemFromPath(module: DashboardModuleConfig, itemSlug: string | undefined) {
  const target = (itemSlug ? `/${itemSlug}` : module.defaultRoute) as `/${string}`;
  return module.sidebarItems.find((item) => item.path === target) ?? module.sidebarItems.find((item) => item.path === module.defaultRoute);
}

export function getSidebarItemFromModuleKey(module: DashboardModuleConfig, moduleKey: string | undefined) {
  return module.sidebarItems.find((item) => item.moduleKey === moduleKey);
}

export function getItemHref(module: DashboardModuleConfig, item: SidebarItemConfig) {
  return `${module.basePath}${item.path}`;
}

export function getDefaultItemHref(module: DashboardModuleConfig, permissions: readonly Permission[]) {
  const visible = visibleSidebarItems(module, permissions);
  const preferred = visible.find((item) => item.path === module.defaultRoute) ?? visible[0];
  return preferred ? getItemHref(module, preferred) : module.basePath;
}
