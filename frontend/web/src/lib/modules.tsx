import type * as React from "react";

import {
  Bell,
  Briefcase,
  Building,
  Calculator,
  Calendar,
  Cart,
  ChartPie,
  CheckCircle,
  Cog,
  Grid,
  Help,
  Layers,
  Network,
  Shield,
  Target,
  User,
  Users,
} from "@/components/overview/icons";

export interface ModuleKpi {
  label: string;
  value: string;
  gauge: number;
  color: string;
  delta: string;
  up: boolean;
}

export type ModuleKind = "default" | "notifications" | "settings" | "profile" | "help";

export interface ModuleRow {
  title: string;
  detail: string;
  accent: string;
}

export interface ModuleDef {
  key: string;
  title: string;
  subtitle: string;
  status: string;
  accent: string;
  icon: React.ReactNode;
  kind: ModuleKind;
  kpis?: ModuleKpi[];
  rows?: ModuleRow[];
  /** Affiché dans la grille d'accueil des modules. */
  home?: boolean;
}

const GAUGE_COLORS = ["#416FF4", "#42BFA0", "#D92B55"];
const ICON_SIZE = { width: 30, height: 30 };

function kpis(items: Array<[string, string, number]>): ModuleKpi[] {
  return items.map(([label, value, gauge], index) => ({
    label,
    value,
    gauge,
    color: GAUGE_COLORS[index % GAUGE_COLORS.length],
    delta: "démo",
    up: index !== 2,
  }));
}

const DEMO_STATUS = "Module en préparation — données de démonstration";

export const MODULES: Record<string, ModuleDef> = {
  executive: {
    key: "executive",
    title: "Exécutif",
    subtitle: "Synthèse groupe et pilotage stratégique multi-filiales.",
    status: DEMO_STATUS,
    accent: "#416FF4",
    icon: <Target {...ICON_SIZE} />,
    kind: "default",
    home: true,
    kpis: kpis([
      ["Chiffre d'affaires groupe", "12.4M XOF", 72],
      ["Marge consolidée", "18.6%", 58],
      ["Trésorerie nette", "4.1M XOF", 41],
    ]),
  },
  crm: {
    key: "crm",
    title: "CRM & Ventes",
    subtitle: "Pipeline commercial, conversion et acquisition clients.",
    status: DEMO_STATUS,
    accent: "#7A5AF8",
    icon: <Network {...ICON_SIZE} />,
    kind: "default",
    home: true,
    kpis: kpis([
      ["Pipeline pondéré", "8.9M XOF", 64],
      ["Taux de conversion", "23%", 47],
      ["Affaires à risque", "6", 31],
    ]),
  },
  inventory: {
    key: "inventory",
    title: "Stocks & Achats",
    subtitle: "Valorisation des stocks, ruptures et rotation.",
    status: DEMO_STATUS,
    accent: "#2BB7A3",
    icon: <Cart {...ICON_SIZE} />,
    kind: "default",
    home: true,
    kpis: kpis([
      ["Valeur du stock", "3.2M XOF", 55],
      ["Rotation", "5.4x", 61],
      ["Taux de rupture", "2.1%", 22],
    ]),
  },
  accounting: {
    key: "accounting",
    title: "Comptabilité",
    subtitle: "Résultat, charges et délais de règlement.",
    status: DEMO_STATUS,
    accent: "#E08A1E",
    icon: <Calculator {...ICON_SIZE} />,
    kind: "default",
    home: true,
    kpis: kpis([
      ["Résultat net", "2.3M XOF", 60],
      ["DSO clients", "38 j", 44],
      ["Charges d'exploitation", "7.8M XOF", 52],
    ]),
  },
  kexpress: {
    key: "kexpress",
    title: "K-Express Logistique",
    subtitle: "Livraisons, coûts de course et disponibilité de la flotte.",
    status: DEMO_STATUS,
    accent: "#2D74E0",
    icon: <Grid {...ICON_SIZE} />,
    kind: "default",
    home: true,
    kpis: kpis([
      ["Livraisons à l'heure", "94%", 78],
      ["Flotte active", "27", 66],
      ["Coût par course", "4 200 XOF", 38],
    ]),
  },
  construction: {
    key: "construction",
    title: "Construction",
    subtitle: "Avancement des chantiers, budgets et sécurité.",
    status: DEMO_STATUS,
    accent: "#FF8735",
    icon: <Building {...ICON_SIZE} />,
    kind: "default",
    home: true,
    kpis: kpis([
      ["Avancement chantiers", "61%", 61],
      ["Budget consommé", "57%", 57],
      ["Taux de fréquence (TF)", "1.8", 28],
    ]),
  },
  governance: {
    key: "governance",
    title: "Gouvernance & Catalogue",
    subtitle: "Métriques cataloguées, RBAC et fraîcheur des marts.",
    status: DEMO_STATUS,
    accent: "#42BFA0",
    icon: <Shield {...ICON_SIZE} />,
    kind: "default",
    home: true,
    kpis: kpis([
      ["Métriques cataloguées", "42", 70],
      ["Couverture RBAC", "100%", 100],
      ["Fraîcheur des marts", "OK", 88],
    ]),
  },
  groupe: {
    key: "groupe",
    title: "Vue groupe",
    subtitle: "Consolidation transverse des filiales du groupe Kaydan.",
    status: DEMO_STATUS,
    accent: "#8A63D2",
    icon: <Layers {...ICON_SIZE} />,
    kind: "default",
    kpis: kpis([
      ["Filiales", "6", 60],
      ["Effectif groupe", "248", 64],
      ["CA consolidé", "12.4M XOF", 72],
    ]),
  },
  risques: {
    key: "risques",
    title: "Risques",
    subtitle: "Cartographie des risques, criticité et plans d'action.",
    status: DEMO_STATUS,
    accent: "#D92B55",
    icon: <ChartPie {...ICON_SIZE} />,
    kind: "default",
    kpis: kpis([
      ["Risques ouverts", "14", 47],
      ["Criticité moyenne", "Moyenne", 52],
      ["Plans d'action", "9", 63],
    ]),
  },
  timeline: {
    key: "timeline",
    title: "Timeline",
    subtitle: "Jalons, échéances et charge des équipes.",
    status: DEMO_STATUS,
    accent: "#6366F1",
    icon: <Calendar {...ICON_SIZE} />,
    kind: "default",
    kpis: kpis([
      ["Jalons à venir", "7", 58],
      ["Tâches en retard", "3", 26],
      ["Charge équipe", "82%", 82],
    ]),
  },
  "work-areas": {
    key: "work-areas",
    title: "Zones de travail",
    subtitle: "Sites actifs, occupation et incidents ouverts.",
    status: DEMO_STATUS,
    accent: "#5B8DEF",
    icon: <Grid {...ICON_SIZE} />,
    kind: "default",
    kpis: kpis([
      ["Sites actifs", "9", 64],
      ["Taux d'occupation", "76%", 76],
      ["Incidents ouverts", "4", 29],
    ]),
  },
  portefeuille: {
    key: "portefeuille",
    title: "Portefeuille",
    subtitle: "Projets actifs, valeur et rendement du portefeuille.",
    status: DEMO_STATUS,
    accent: "#416FF4",
    icon: <Briefcase {...ICON_SIZE} />,
    kind: "default",
    kpis: kpis([
      ["Projets actifs", "18", 67],
      ["Valeur portefeuille", "21.5M XOF", 74],
      ["ROI moyen", "14%", 52],
    ]),
  },
  notifications: {
    key: "notifications",
    title: "Notifications",
    subtitle: "Alertes data, jalons et événements du périmètre.",
    status: "3 non lues",
    accent: "#FF8735",
    icon: <Bell {...ICON_SIZE} />,
    kind: "notifications",
    rows: [
      { title: "Mart hr_kpi rafraîchi", detail: "Il y a 12 min — données RH à jour", accent: "#42BFA0" },
      { title: "Seuil masse salariale dépassé (KRE)", detail: "Il y a 1 h — variation +4,2 %", accent: "#D92B55" },
      { title: "Nouveau rapport trimestriel disponible", detail: "Il y a 3 h — T1 2026", accent: "#416FF4" },
      { title: "Mart real_estate_kpi en attente", detail: "Hier — matérialisation requise", accent: "#FF8735" },
    ],
  },
  parametres: {
    key: "parametres",
    title: "Paramètres",
    subtitle: "Préférences d'affichage, périmètre et accès.",
    status: "Lecture seule",
    accent: "#5B6470",
    icon: <Cog {...ICON_SIZE} />,
    kind: "settings",
    rows: [
      { title: "Périmètre par défaut", detail: "Groupe (toutes filiales)", accent: "#416FF4" },
      { title: "Langue", detail: "Français", accent: "#42BFA0" },
      { title: "Thème", detail: "Clair", accent: "#FF8735" },
      { title: "Rôle & RBAC", detail: "Lecteur — données en lecture seule", accent: "#8A63D2" },
    ],
  },
  aide: {
    key: "aide",
    title: "Aide & Support",
    subtitle: "Documentation, catalogue de métriques et contact.",
    status: "Centre d'aide",
    accent: "#2BB7A3",
    icon: <Help {...ICON_SIZE} />,
    kind: "help",
    rows: [
      { title: "Catalogue de métriques", detail: "Définitions et grains des KPI servis", accent: "#416FF4" },
      { title: "Guide de démarrage", detail: "Naviguer entre dashboards et filtres", accent: "#42BFA0" },
      { title: "Gouvernance des données", detail: "RBAC, périmètre et lecture seule", accent: "#FF8735" },
      { title: "Contacter le support", detail: "support@kaydangroupe.com", accent: "#D92B55" },
    ],
  },
  profil: {
    key: "profil",
    title: "Mon profil",
    subtitle: "Compte, périmètre d'accès et préférences.",
    status: "Connecté",
    accent: "#2D74E0",
    icon: <User {...ICON_SIZE} />,
    kind: "profile",
    rows: [
      { title: "Rôle", detail: "Analyste pilotage groupe", accent: "#416FF4" },
      { title: "Périmètre", detail: "Groupe Kaydan — toutes filiales", accent: "#42BFA0" },
      { title: "Accès", detail: "Lecture seule (gouvernance)", accent: "#FF8735" },
    ],
  },
};

export const HOME_MODULE_KEYS = Object.values(MODULES)
  .filter((module) => module.home)
  .map((module) => module.key);

export function getModule(key: string | undefined): ModuleDef | undefined {
  return key ? MODULES[key] : undefined;
}

export interface DashboardLink {
  key: "realEstate" | "hr" | "finance";
  title: string;
  subtitle: string;
  accent: string;
  icon: React.ReactNode;
}

/** Les 3 dashboards réellement servis par le backend governance. */
export const DASHBOARD_LINKS: DashboardLink[] = [
  { key: "realEstate", title: "Real Estate", subtitle: "Pilotage des programmes immobiliers", accent: "#FF8735", icon: <Building {...ICON_SIZE} /> },
  { key: "hr", title: "Ressources humaines", subtitle: "Masse salariale, entrées et sorties", accent: "#416FF4", icon: <Users {...ICON_SIZE} /> },
  { key: "finance", title: "Finance", subtitle: "Charges, marges et trésorerie", accent: "#42BFA0", icon: <CheckCircle {...ICON_SIZE} /> },
];
