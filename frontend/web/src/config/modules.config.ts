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
import { canAccess, type Permission } from "@/lib/permissions";

export type ModuleIcon = React.ComponentType<React.SVGProps<SVGSVGElement>>;

export interface SidebarItemConfig {
  label: string;
  path: `/${string}`;
  icon: ModuleIcon;
  moduleKey: string;
  requiredPermissions?: Permission[];
}

export interface DashboardModuleConfig {
  id: string;
  label: string;
  icon: ModuleIcon;
  basePath: `/dashboard/${string}`;
  requiredPermissions: Permission[];
  sidebarItems: SidebarItemConfig[];
  filters?: string[];
}

export const dashboardModules: DashboardModuleConfig[] = [
  {
    id: "overview",
    label: "Overview Groupe",
    icon: ChartPie,
    basePath: "/dashboard/overview",
    requiredPermissions: ["view_group_overview"],
    filters: ["Période", "Filiale", "Département", "Site"],
    sidebarItems: [
      { label: "Vue Groupe", path: "/overview", icon: Layers, moduleKey: "groupe" },
      { label: "Executive Real Estate", path: "/real-estate", icon: Building, moduleKey: "executive" },
      { label: "Executive HR", path: "/hr", icon: Users, moduleKey: "hr-executive" },
      { label: "Executive Finance", path: "/finance", icon: Wallet, moduleKey: "finance-executive" },
      { label: "Alertes Groupe", path: "/alerts", icon: Bell, moduleKey: "notifications" },
      { label: "Rapports Groupe", path: "/reports", icon: FileText, moduleKey: "reports" },
    ],
  },
  {
    id: "real_estate",
    label: "Real Estate",
    icon: Building,
    basePath: "/dashboard/real-estate",
    requiredPermissions: ["view_real_estate_dashboard"],
    filters: ["Période", "Filiale", "Programme", "Chantier", "Statut"],
    sidebarItems: [
      { label: "Executive Overview", path: "/overview", icon: Target, moduleKey: "executive" },
      { label: "Portfolio Immobilier", path: "/portfolio", icon: Briefcase, moduleKey: "portfolio" },
      { label: "Gouvernance Foncière", path: "/land", icon: Layers, moduleKey: "land" },
      { label: "Construction", path: "/construction", icon: Building, moduleKey: "construction" },
      { label: "VRD", path: "/vrd", icon: Network, moduleKey: "vrd" },
      { label: "Commercialisation", path: "/sales", icon: Target, moduleKey: "commercialisation" },
      { label: "Gestion Locative", path: "/rental", icon: Receipt, moduleKey: "rental" },
      { label: "Finance Projet", path: "/finance", icon: Wallet, moduleKey: "finance" },
      { label: "Stocks Chantier", path: "/inventory", icon: Cart, moduleKey: "inventory" },
      { label: "Ressources Chantier", path: "/resources", icon: Users, moduleKey: "chantier-resources" },
      { label: "Sécurité Chantier", path: "/security", icon: Shield, moduleKey: "security" },
      { label: "Maintenance", path: "/maintenance", icon: Cog, moduleKey: "maintenance" },
      { label: "Clients", path: "/clients", icon: User, moduleKey: "clients" },
      { label: "Risques", path: "/risks", icon: ChartPie, moduleKey: "risques" },
      { label: "Prévisions IA", path: "/ai-forecast", icon: CheckCircle, moduleKey: "ai" },
      { label: "Rapports Real Estate", path: "/reports", icon: FileText, moduleKey: "reports" },
    ],
  },
  {
    id: "hr",
    label: "Ressources Humaines",
    icon: Users,
    basePath: "/dashboard/hr",
    requiredPermissions: ["view_hr_dashboard"],
    filters: ["Période", "Filiale", "Département", "Site", "Métier"],
    sidebarItems: [
      { label: "Executive HR Overview", path: "/overview", icon: Target, moduleKey: "hr-executive" },
      { label: "Workforce", path: "/workforce", icon: Users, moduleKey: "hr-workforce" },
      { label: "Organisation", path: "/organization", icon: Network, moduleKey: "hr-organization" },
      { label: "Présence", path: "/attendance", icon: CheckCircle, moduleKey: "hr-attendance" },
      { label: "Congés", path: "/leaves", icon: Calendar, moduleKey: "hr-leave" },
      { label: "Recrutement", path: "/recruitment", icon: Briefcase, moduleKey: "hr-recruitment" },
      { label: "Paie", path: "/payroll", icon: Wallet, moduleKey: "hr-payroll" },
      { label: "Performance", path: "/performance", icon: BarChart, moduleKey: "hr-performance" },
      { label: "Formation", path: "/training", icon: FileText, moduleKey: "hr-training" },
      { label: "Compétences", path: "/skills", icon: Grid, moduleKey: "hr-skills" },
      { label: "Carrière", path: "/career", icon: CheckCircle, moduleKey: "hr-career" },
      { label: "Expérience Employé", path: "/experience", icon: User, moduleKey: "hr-experience" },
      { label: "Santé & Sécurité", path: "/health-safety", icon: Shield, moduleKey: "hr-health-safety" },
      { label: "Conformité", path: "/compliance", icon: Receipt, moduleKey: "hr-compliance" },
      { label: "Workforce Planning", path: "/planning", icon: ChartPie, moduleKey: "hr-planning" },
      { label: "IA RH", path: "/ai-insights", icon: CheckCircle, moduleKey: "hr-ai" },
      { label: "Rapports RH", path: "/reports", icon: FileText, moduleKey: "hr-reports" },
    ],
  },
  {
    id: "finance",
    label: "Finance & Comptabilité",
    icon: Wallet,
    basePath: "/dashboard/finance",
    requiredPermissions: ["view_finance_dashboard"],
    filters: ["Période", "Filiale", "Centre de coût", "Compte", "Devise"],
    sidebarItems: [
      { label: "Executive Finance Overview", path: "/overview", icon: Target, moduleKey: "finance-executive" },
      { label: "Trésorerie", path: "/treasury", icon: DollarCircle, moduleKey: "finance-treasury" },
      { label: "Encaissements", path: "/cash-in", icon: Receipt, moduleKey: "finance-cash-in" },
      { label: "Décaissements", path: "/cash-out", icon: Receipt, moduleKey: "finance-cash-out" },
      { label: "Budget", path: "/budget", icon: Calculator, moduleKey: "finance-budget" },
      { label: "Comptabilité", path: "/accounting", icon: Calculator, moduleKey: "finance-accounting" },
      { label: "Balance", path: "/balance", icon: FileText, moduleKey: "finance-balance" },
      { label: "Grand Livre", path: "/ledger", icon: FileText, moduleKey: "finance-ledger" },
      { label: "Factures", path: "/invoices", icon: Receipt, moduleKey: "finance-invoices" },
      { label: "Créances", path: "/receivables", icon: DollarCircle, moduleKey: "finance-receivables" },
      { label: "Dettes", path: "/payables", icon: DollarCircle, moduleKey: "finance-payables" },
      { label: "Recouvrement", path: "/recovery", icon: Target, moduleKey: "finance-recovery" },
      { label: "Analyse Rentabilité", path: "/profitability", icon: ChartPie, moduleKey: "finance-profitability" },
      { label: "Prévisions", path: "/forecast", icon: CheckCircle, moduleKey: "finance-forecast" },
      { label: "Risques Financiers", path: "/risks", icon: Shield, moduleKey: "finance-risks" },
      { label: "Rapports Finance", path: "/reports", icon: FileText, moduleKey: "finance-reports" },
    ],
  },
  {
    id: "commercial",
    label: "Commercial",
    icon: Target,
    basePath: "/dashboard/commercial",
    requiredPermissions: ["view_commercial_dashboard"],
    filters: ["Période", "Filiale", "Programme", "Commercial", "Canal"],
    sidebarItems: [
      { label: "Vue Commerciale", path: "/overview", icon: Target, moduleKey: "commercialisation" },
      { label: "Pipeline", path: "/pipeline", icon: BarChart, moduleKey: "commercialisation" },
      { label: "Clients", path: "/clients", icon: User, moduleKey: "clients" },
      { label: "Prévisions IA", path: "/forecast", icon: CheckCircle, moduleKey: "ai" },
      { label: "Rapports Commercial", path: "/reports", icon: FileText, moduleKey: "reports" },
    ],
  },
  {
    id: "inventory",
    label: "Stocks & Logistique",
    icon: Cart,
    basePath: "/dashboard/inventory",
    requiredPermissions: ["view_inventory_dashboard"],
    filters: ["Période", "Filiale", "Site", "Magasin", "Famille article"],
    sidebarItems: [
      { label: "Stocks", path: "/overview", icon: Cart, moduleKey: "inventory" },
      { label: "Matériaux critiques", path: "/critical", icon: Shield, moduleKey: "inventory" },
      { label: "Prévisions", path: "/forecast", icon: CheckCircle, moduleKey: "ai" },
      { label: "Rapports Stocks", path: "/reports", icon: FileText, moduleKey: "reports" },
    ],
  },
  {
    id: "security",
    label: "Sécurité",
    icon: Shield,
    basePath: "/dashboard/security",
    requiredPermissions: ["view_security_dashboard"],
    filters: ["Période", "Filiale", "Site", "Zone", "Criticité"],
    sidebarItems: [
      { label: "Sécurité Groupe", path: "/overview", icon: Shield, moduleKey: "security" },
      { label: "Incidents", path: "/incidents", icon: Bell, moduleKey: "security" },
      { label: "Risques", path: "/risks", icon: ChartPie, moduleKey: "risques" },
      { label: "Alertes", path: "/alerts", icon: Bell, moduleKey: "alerts" },
      { label: "Rapports Sécurité", path: "/reports", icon: FileText, moduleKey: "reports" },
    ],
  },
  {
    id: "fleet",
    label: "Flotte",
    icon: Briefcase,
    basePath: "/dashboard/fleet",
    requiredPermissions: ["view_fleet_dashboard"],
    filters: ["Période", "Filiale", "Site", "Type véhicule", "Statut"],
    sidebarItems: [
      { label: "Vue Flotte", path: "/overview", icon: Briefcase, moduleKey: "maintenance" },
      { label: "Maintenance Flotte", path: "/maintenance", icon: Cog, moduleKey: "maintenance" },
      { label: "Coûts Flotte", path: "/costs", icon: Wallet, moduleKey: "finance" },
      { label: "Rapports Flotte", path: "/reports", icon: FileText, moduleKey: "reports" },
    ],
  },
  {
    id: "projects",
    label: "Projets",
    icon: Network,
    basePath: "/dashboard/projects",
    requiredPermissions: ["view_projects_dashboard"],
    filters: ["Période", "Filiale", "Projet", "Chef projet", "Statut"],
    sidebarItems: [
      { label: "Vue Projets", path: "/overview", icon: Network, moduleKey: "work-areas" },
      { label: "Planning", path: "/timeline", icon: Calendar, moduleKey: "timeline" },
      { label: "Construction", path: "/construction", icon: Building, moduleKey: "construction" },
      { label: "Risques Projets", path: "/risks", icon: ChartPie, moduleKey: "risques" },
      { label: "Rapports Projets", path: "/reports", icon: FileText, moduleKey: "reports" },
    ],
  },
  {
    id: "ai",
    label: "IA Gouvernance",
    icon: CheckCircle,
    basePath: "/dashboard/ai",
    requiredPermissions: ["view_ai_governance"],
    filters: ["Période", "Domaine", "Filiale", "Scénario"],
    sidebarItems: [
      { label: "IA Groupe", path: "/overview", icon: CheckCircle, moduleKey: "ai" },
      { label: "IA RH", path: "/hr", icon: Users, moduleKey: "hr-ai" },
      { label: "IA Finance", path: "/finance", icon: Wallet, moduleKey: "finance-forecast" },
      { label: "Alertes IA", path: "/alerts", icon: Bell, moduleKey: "alerts" },
    ],
  },
  {
    id: "reports",
    label: "Rapports",
    icon: FileText,
    basePath: "/dashboard/reports",
    requiredPermissions: ["view_reports"],
    filters: ["Période", "Domaine", "Filiale", "Format"],
    sidebarItems: [
      { label: "Rapports Groupe", path: "/overview", icon: FileText, moduleKey: "reports" },
      { label: "Rapports RH", path: "/hr", icon: Users, moduleKey: "hr-reports" },
      { label: "Rapports Finance", path: "/finance", icon: Wallet, moduleKey: "finance-reports" },
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
  const target = itemSlug ? `/${itemSlug}` : "/overview";
  return module.sidebarItems.find((item) => item.path === target);
}

export function getSidebarItemFromModuleKey(module: DashboardModuleConfig, moduleKey: string | undefined) {
  return module.sidebarItems.find((item) => item.moduleKey === moduleKey);
}

export function getItemHref(module: DashboardModuleConfig, item: SidebarItemConfig) {
  return `${module.basePath}${item.path}`;
}

export function getDefaultItemHref(module: DashboardModuleConfig, permissions: readonly Permission[]) {
  const [firstItem] = visibleSidebarItems(module, permissions);
  return firstItem ? getItemHref(module, firstItem) : module.basePath;
}
