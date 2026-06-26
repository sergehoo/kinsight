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

export interface ModuleKpi {
  label: string;
  value: string;
  gauge: number;
  color: string;
  delta: string;
  up: boolean;
  source?: string;
}

export type ModuleKind = "default" | "notifications" | "settings" | "profile" | "help" | "ai";
export type ModuleChartType = "line" | "bar" | "pie" | "funnel" | "gantt" | "heatmap" | "radar";

export interface ModuleChart {
  title: string;
  subtitle: string;
  type: ModuleChartType;
  source: string;
}

export interface ModuleRow {
  title: string;
  detail: string;
  accent: string;
}

export interface ModuleSection {
  title: string;
  subtitle: string;
  source: string;
  chart: ModuleChart;
  rows: ModuleRow[];
}

export interface ModuleDef {
  key: string;
  title: string;
  subtitle: string;
  status: string;
  accent: string;
  icon: React.ReactNode;
  kind: ModuleKind;
  source: string;
  kpis?: ModuleKpi[];
  rows?: ModuleRow[];
  sections?: ModuleSection[];
  home?: boolean;
}

const ICON_SIZE = { width: 30, height: 30 };
const COLORS = ["#416FF4", "#42BFA0", "#D92B55", "#FF8735", "#8A63D2"];
const MART_STATUS = "Mart à connecter — aucune donnée inventée";

function metricKpis(source: string, labels: string[]): ModuleKpi[] {
  return labels.map((label, index) => ({
    label,
    value: "N/D",
    gauge: 8,
    color: COLORS[index % COLORS.length],
    delta: "mart à connecter",
    up: false,
    source,
  }));
}

function rows(items: string[], source: string): ModuleRow[] {
  return items.map((title, index) => ({
    title,
    detail: `${source} · donnée attendue du Data Warehouse`,
    accent: COLORS[index % COLORS.length],
  }));
}

function chart(title: string, subtitle: string, type: ModuleChartType, source: string): ModuleChart {
  return { title, subtitle, type, source };
}

function section(
  title: string,
  subtitle: string,
  source: string,
  chartType: ModuleChartType,
  rowItems: string[],
): ModuleSection {
  return {
    title,
    subtitle,
    source,
    chart: chart(title, subtitle, chartType, source),
    rows: rows(rowItems, source),
  };
}

export const MODULES: Record<string, ModuleDef> = {
  executive: {
    key: "executive",
    title: "Executive Overview",
    subtitle: "Vue DG consolidée : patrimoine, programmes, ventes, cash, ROI et risques.",
    status: MART_STATUS,
    accent: "#FF8735",
    icon: <Target {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_executive_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_executive_kpi", [
      "Valeur totale du patrimoine",
      "Nombre total de programmes",
      "Programmes actifs",
      "Programmes terminés",
      "Programmes en retard",
      "Chiffre d'affaires",
      "Résultat net",
      "Cash disponible",
      "Budget consommé",
      "ROI global",
      "Taux de commercialisation",
      "Taux d'occupation",
      "Valeur des stocks",
      "Valeur foncière",
      "Nombre de clients",
      "Nombre de ventes",
      "Nombre de réservations",
    ]),
    sections: [
      section("Evolution CA", "Tendance mensuelle du chiffre d'affaires", "mart.real_estate_revenue_monthly", "line", ["CA mensuel", "Objectif", "Ecart"]),
      section("Evolution ventes", "Ventes, réservations et annulations", "mart.real_estate_sales_monthly", "bar", ["Ventes", "Réservations", "Annulations"]),
      section("Evolution marge", "Marge brute et résultat net", "mart.real_estate_margin_monthly", "line", ["Marge", "Résultat net", "EBITDA"]),
      section("Evolution cash", "Encaissements, décaissements et cash net", "mart.real_estate_cashflow_monthly", "line", ["Encaissements", "Décaissements", "Cash net"]),
      section("Evolution construction", "Avancement physique consolidé", "mart.real_estate_construction_progress", "bar", ["Gros oeuvre", "VRD", "Finitions"]),
    ],
  },
  portfolio: {
    key: "portfolio",
    title: "Portfolio Immobilier",
    subtitle: "Terrains, programmes, résidences, immeubles, villas, appartements et actifs exploités.",
    status: MART_STATUS,
    accent: "#416FF4",
    icon: <Briefcase {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_portfolio_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_portfolio_kpi", [
      "Nombre d'actifs",
      "Valeur portefeuille",
      "Surface totale",
      "Occupation",
      "Disponibilité",
      "Rentabilité",
      "Répartition géographique",
    ]),
    sections: [
      section("Répartition par typologie", "Terrains, bureaux, villas, appartements et entrepôts", "mart.real_estate_asset_mix", "pie", ["Terrains", "Villas", "Appartements", "Bureaux", "Entrepôts"]),
      section("Répartition géographique", "Pays, ville, commune et quartier", "mart.real_estate_geo_distribution", "heatmap", ["Pays", "Ville", "Commune", "Quartier"]),
    ],
  },
  land: {
    key: "land",
    title: "Gouvernance Foncière",
    subtitle: "Titres fonciers, hypothèques, surfaces disponibles, documents cadastraux et échéances.",
    status: MART_STATUS,
    accent: "#42BFA0",
    icon: <Layers {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_land_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_land_kpi", [
      "Nombre de terrains",
      "Valeur foncière",
      "Titres fonciers",
      "Titres en attente",
      "Hypothèques",
      "Valeur hypothécaire",
      "Surface totale",
      "Surface disponible",
      "Surface exploitée",
      "Surface constructible",
      "Documents cadastraux",
      "Expiration documents",
    ]),
    sections: [
      section("Surfaces foncières", "Exploité, disponible, constructible", "mart.real_estate_land_surface", "bar", ["Surface disponible", "Surface exploitée", "Surface constructible"]),
      section("Documents & échéances", "Titres, cadastre, hypothèques", "mart.real_estate_land_documents", "gantt", ["Titre foncier", "Cadastre", "Hypothèque", "Renouvellement"]),
    ],
  },
  construction: {
    key: "construction",
    title: "Gouvernance Construction",
    subtitle: "Budget, coût réel, retard, qualité, livraison et indice de performance par chantier.",
    status: MART_STATUS,
    accent: "#FF8735",
    icon: <Building {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_construction_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_construction_kpi", [
      "Budget",
      "Coût réel",
      "Coût restant",
      "Avancement",
      "Retard",
      "Qualité",
      "Date livraison",
      "Indice performance",
    ]),
    sections: [
      section("Courbe S", "Planifié vs réalisé", "mart.real_estate_s_curve", "line", ["Planifié", "Réalisé", "Ecart"]),
      section("Burn Rate", "Consommation budgétaire par période", "mart.real_estate_burn_rate", "bar", ["Budget consommé", "Coût restant", "Ecart"]),
      section("Planning Gantt", "Terrassement, fondation, gros œuvre, second œuvre, VRD, finitions, réception", "mart.real_estate_project_schedule", "gantt", ["Terrassement", "Fondation", "Gros œuvre", "Second œuvre", "VRD", "Finitions", "Réception"]),
      section("Evolution Budget", "Budget initial, révisé et réel", "mart.real_estate_budget_evolution", "line", ["Budget initial", "Budget révisé", "Coût réel"]),
    ],
  },
  vrd: {
    key: "vrd",
    title: "VRD",
    subtitle: "Voirie, électricité, drainage, assainissement, télécom, eau potable et espaces verts.",
    status: MART_STATUS,
    accent: "#2BB7A3",
    icon: <Network {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_vrd_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_vrd_kpi", ["Avancement", "Budget", "Qualité", "Retards", "Incidents"]),
    sections: [
      section("Avancement VRD", "Comparatif par lot technique", "mart.real_estate_vrd_progress", "bar", ["Voirie", "Electricité", "Drainage", "Assainissement", "Télécom", "Eau potable", "Espaces verts"]),
      section("Incidents VRD", "Retards, qualité et incidents ouverts", "mart.real_estate_vrd_incidents", "radar", ["Retards", "Qualité", "Incidents", "Budget", "Réception"]),
    ],
  },
  commercialisation: {
    key: "commercialisation",
    title: "Commercialisation",
    subtitle: "Leads, prospects, réservations, contrats, ventes, livraisons et annulations.",
    status: MART_STATUS,
    accent: "#7A5AF8",
    icon: <Target {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_sales_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_sales_kpi", [
      "Leads",
      "Prospects",
      "Réservations",
      "Contrats",
      "Ventes",
      "Livraisons",
      "Annulations",
      "Taux conversion",
      "Lots disponibles",
      "Lots réservés",
      "Lots vendus",
      "Lots livrés",
      "CA commercial",
      "Objectifs commerciaux",
      "Top commerciaux",
    ]),
    sections: [
      section("Pipeline commercial", "Leads vers ventes signées", "mart.real_estate_sales_pipeline", "funnel", ["Leads", "Prospects", "Réservations", "Contrats", "Ventes"]),
      section("Evolution ventes", "Ventes et réservations mensuelles", "mart.real_estate_sales_evolution", "line", ["Réservations", "Ventes", "Annulations"]),
      section("Carte ventes", "Répartition géographique des ventes", "mart.real_estate_sales_map", "heatmap", ["Pays", "Ville", "Commune", "Quartier"]),
    ],
  },
  rental: {
    key: "rental",
    title: "Gestion Locative",
    subtitle: "Biens loués, vacance, loyers, impayés, baux et renouvellements.",
    status: MART_STATUS,
    accent: "#416FF4",
    icon: <Receipt {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_rental_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_rental_kpi", ["Biens loués", "Biens vacants", "Taux occupation", "Loyers", "Impayés", "Baux", "Renouvellements", "Expiration contrats", "Revenus locatifs", "Rentabilité"]),
    sections: [
      section("Occupation locative", "Occupation, vacance et renouvellements", "mart.real_estate_rental_occupancy", "bar", ["Loués", "Vacants", "Renouvellements"]),
      section("Revenus locatifs", "Loyers, impayés et rentabilité", "mart.real_estate_rental_income", "line", ["Loyers", "Impayés", "Rentabilité"]),
    ],
  },
  finance: {
    key: "finance",
    title: "Finances",
    subtitle: "Connexion Odoo Comptabilité : budget, cash flow, charges, produits et résultat.",
    status: MART_STATUS,
    accent: "#42BFA0",
    icon: <Wallet {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_finance_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_finance_kpi", ["Budget", "Budget consommé", "Budget restant", "Encaissements", "Décaissements", "Cash Flow", "Charges", "Produits", "Marge", "EBITDA", "Résultat net", "Résultat opérationnel"]),
    sections: [
      section("Evolution trésorerie", "Cash in, cash out et cash net", "mart.real_estate_treasury_evolution", "line", ["Encaissements", "Décaissements", "Cash net"]),
      section("Répartition dépenses", "Dépenses par nature et centre de coût", "mart.real_estate_expense_distribution", "pie", ["Construction", "Commercial", "Foncier", "Maintenance"]),
      section("Prévisions finance", "Projection cash et marge", "analytics.real_estate_finance_forecast", "line", ["Prévision 30j", "Prévision 60j", "Prévision 90j"]),
    ],
  },
  treasury: {
    key: "treasury",
    title: "Trésorerie",
    subtitle: "Cash disponible, flux entrants/sortants, engagements et projection 90 jours.",
    status: MART_STATUS,
    accent: "#2D74E0",
    icon: <DollarCircle {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_treasury_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_treasury_kpi", ["Cash disponible", "Cash engagé", "Flux entrants", "Flux sortants", "Cash net", "Projection 90 jours"]),
    sections: [
      section("Cash Flow", "Flux de trésorerie opérationnels", "mart.real_estate_cashflow_daily", "line", ["Cash in", "Cash out", "Net"]),
      section("Prévision 90 jours", "Projection ancrée sur l'EDW", "analytics.real_estate_cash_forecast", "line", ["J+30", "J+60", "J+90"]),
    ],
  },
  accounting: {
    key: "accounting",
    title: "Comptabilité",
    subtitle: "Balance, grand livre, journal, créances, dettes, TVA, factures et échéances.",
    status: MART_STATUS,
    accent: "#E08A1E",
    icon: <Calculator {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_accounting_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_accounting_kpi", ["Balance", "Grand Livre", "Journal", "Créances", "Dettes", "TVA", "Factures", "Recouvrements", "Echéances"]),
    sections: [
      section("Créances & dettes", "Aging client/fournisseur", "mart.real_estate_accounting_aging", "bar", ["0-30j", "31-60j", "61-90j", "+90j"]),
      section("TVA & échéances", "TVA collectée, déductible et échéances", "mart.real_estate_tax_schedule", "gantt", ["TVA", "Factures", "Recouvrements", "Echéances"]),
    ],
  },
  inventory: {
    key: "inventory",
    title: "Stocks",
    subtitle: "Connexion Odoo Stock : valeur, rotation, ruptures, consommation, inventaires et matériaux critiques.",
    status: MART_STATUS,
    accent: "#2BB7A3",
    icon: <Cart {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_inventory_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_inventory_kpi", ["Valeur stock", "Rotation", "Ruptures", "Consommation", "Entrées", "Sorties", "Inventaires", "Matériaux critiques", "Equipements", "Outillage"]),
    sections: [
      section("Rotation stock", "Entrées, sorties et consommation", "mart.real_estate_inventory_rotation", "bar", ["Entrées", "Sorties", "Consommation"]),
      section("Matériaux critiques", "Ruptures et seuils minimum", "mart.real_estate_critical_materials", "radar", ["Ciment", "Fer", "Carrelage", "Peinture", "VRD"]),
    ],
  },
  maintenance: {
    key: "maintenance",
    title: "Maintenance",
    subtitle: "Engins, matériels, véhicules, ascenseurs, groupes électrogènes et climatisation.",
    status: MART_STATUS,
    accent: "#5B8DEF",
    icon: <Cog {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_maintenance_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_maintenance_kpi", ["Disponibilité", "Maintenance préventive", "Maintenance corrective", "Temps arrêt", "Coût maintenance"]),
    sections: [
      section("Disponibilité équipements", "Disponibilité par famille d'actif", "mart.real_estate_equipment_availability", "bar", ["Engins", "Véhicules", "Ascenseurs", "Groupes", "Climatisation"]),
      section("Coûts maintenance", "Préventif vs correctif", "mart.real_estate_maintenance_cost", "line", ["Préventif", "Correctif", "Temps arrêt"]),
    ],
  },
  "chantier-resources": {
    key: "chantier-resources",
    title: "Ressources Chantier",
    subtitle: "Connexion RH et K-Shield : présence temps réel, productivité, heures, coût MO et pointage RFID.",
    status: MART_STATUS,
    accent: "#8A63D2",
    icon: <Users {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_site_resources_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_site_resources_kpi", ["Ouvriers présents", "Présence temps réel", "Productivité", "Heures travaillées", "Coût MO", "Sous-traitants", "Répartition métiers", "Pointage RFID"]),
    sections: [
      section("Heatmap présence", "Présence par chantier et plage horaire", "mart.real_estate_presence_heatmap", "heatmap", ["Site", "Métier", "Heure", "Badge RFID"]),
      section("Productivité chantier", "Productivité et temps travaillé", "mart.real_estate_site_productivity", "line", ["Productivité", "Heures", "Coût MO"]),
    ],
  },
  security: {
    key: "security",
    title: "Sécurité",
    subtitle: "Connexion K-Shield : accès sites, incidents, accidents, EPI, alarmes et zones interdites.",
    status: MART_STATUS,
    accent: "#D92B55",
    icon: <Shield {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_security_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_security_kpi", ["Accès sites", "Présence", "Incidents", "Accidents", "EPI", "Alarmes", "Zones interdites", "Alertes RFID"]),
    sections: [
      section("Incidents sécurité", "Incidents, accidents et alarmes", "mart.real_estate_security_incidents", "bar", ["Incidents", "Accidents", "Alarmes", "EPI"]),
      section("Zones & RFID", "Accès et zones interdites", "mart.real_estate_security_access", "heatmap", ["Site", "Zone", "Badge RFID", "Alerte"]),
    ],
  },
  clients: {
    key: "clients",
    title: "Relation Client",
    subtitle: "Connexion CRM : clients, prospects, réclamations, paiements, satisfaction, tickets et SAV.",
    status: MART_STATUS,
    accent: "#7A5AF8",
    icon: <Network {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_customer_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_customer_kpi", ["Clients", "Prospects", "Réclamations", "Paiements", "Satisfaction", "Tickets", "Demandes SAV"]),
    sections: [
      section("Satisfaction & SAV", "Tickets, réclamations et demandes SAV", "mart.real_estate_customer_service", "line", ["Tickets", "Réclamations", "SAV", "Satisfaction"]),
      section("Paiements clients", "Paiements, retards et recouvrements", "mart.real_estate_customer_payments", "bar", ["Paiements", "Retards", "Recouvrements"]),
    ],
  },
  patrimoine: {
    key: "patrimoine",
    title: "Patrimoine",
    subtitle: "Valeur totale, bâtiments, terrains, équipements, évolution valeur et amortissements.",
    status: MART_STATUS,
    accent: "#416FF4",
    icon: <Building {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_asset_value_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_asset_value_kpi", ["Valeur totale patrimoine", "Valeur bâtiments", "Valeur terrains", "Valeur équipements", "Evolution valeur", "Amortissements"]),
    sections: [
      section("Evolution valeur", "Valeur patrimoniale et amortissements", "mart.real_estate_asset_value_evolution", "line", ["Bâtiments", "Terrains", "Equipements", "Amortissements"]),
      section("Composition patrimoine", "Répartition par classe d'actif", "mart.real_estate_asset_composition", "pie", ["Bâtiments", "Terrains", "Equipements"]),
    ],
  },
  risques: {
    key: "risques",
    title: "Gouvernance des Risques",
    subtitle: "Retards, dépassements, cash négatif, stocks critiques, incidents, juridique et alertes.",
    status: MART_STATUS,
    accent: "#D92B55",
    icon: <ChartPie {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_risk_kpi",
    home: true,
    kpis: metricKpis("mart.real_estate_risk_kpi", ["Retards", "Dépassements budget", "Retards paiement", "Retards livraison", "Stocks critiques", "Incidents sécurité", "Cash négatif", "Contrats expirants", "Alertes juridiques"]),
    rows: [
      { title: "Critique", detail: "Risque rouge — donnée issue de mart.real_estate_risk_kpi", accent: "#D92B55" },
      { title: "Important", detail: "Risque orange — donnée issue de mart.real_estate_risk_kpi", accent: "#FF8735" },
      { title: "Moyen", detail: "Risque jaune — donnée issue de mart.real_estate_risk_kpi", accent: "#E8B923" },
      { title: "Normal", detail: "Risque vert — donnée issue de mart.real_estate_risk_kpi", accent: "#42BFA0" },
    ],
    sections: [
      section("Matrice risques", "Criticité par programme et domaine", "mart.real_estate_risk_matrix", "heatmap", ["Programme", "Budget", "Planning", "Cash", "Sécurité"]),
      section("Evolution risques", "Ouvertures et résolutions", "mart.real_estate_risk_evolution", "line", ["Ouverts", "Résolus", "Critiques"]),
    ],
  },
  ai: {
    key: "ai",
    title: "Centre IA",
    subtitle: "Analyse décisionnelle ancrée sur le Data Warehouse : recommandations, simulations, scénarios et prévisions.",
    status: "IA ancrée EDW — aucune donnée inventée",
    accent: "#060606",
    icon: <CheckCircle {...ICON_SIZE} />,
    kind: "ai",
    source: "analytics.real_estate_ai_insights",
    home: true,
    kpis: metricKpis("analytics.real_estate_ai_insights", ["Rentabilité", "Retards", "Ventes", "Trésorerie", "Cash Flow", "Qualité", "Productivité", "Performance commerciale", "Performance RH", "Performance financière"]),
    rows: [
      { title: "Pourquoi les ventes diminuent ?", detail: "Réponse autorisée uniquement si mart.real_estate_sales_kpi est disponible", accent: "#416FF4" },
      { title: "Pourquoi le budget explose ?", detail: "Analyse basée sur mart.real_estate_budget_evolution", accent: "#D92B55" },
      { title: "Quelle sera la trésorerie dans 90 jours ?", detail: "Prévision basée sur analytics.real_estate_cash_forecast", accent: "#42BFA0" },
      { title: "Quels projets doivent être accélérés ?", detail: "Scénario basé sur planning, ventes, cash et risques", accent: "#FF8735" },
    ],
    sections: [
      section("Prévisions IA", "Cash, ventes et retards projetés", "analytics.real_estate_forecasts", "line", ["Cash 90j", "Ventes", "Retards"]),
      section("Priorités IA", "Recommandations classées par impact", "analytics.real_estate_recommendations", "radar", ["Impact", "Urgence", "Cash", "Risque", "ROI"]),
    ],
  },
  alerts: {
    key: "alerts",
    title: "Centre d'Alertes",
    subtitle: "Alertes intelligentes : chantiers, budget, cash, contrats, stock, paiements et ventes.",
    status: MART_STATUS,
    accent: "#FF8735",
    icon: <Bell {...ICON_SIZE} />,
    kind: "notifications",
    source: "mart.real_estate_alerts",
    home: true,
    rows: [
      { title: "Chantier arrêté", detail: "Règle critique — mart.real_estate_alerts", accent: "#D92B55" },
      { title: "Dépassement budget", detail: "Règle critique — mart.real_estate_alerts", accent: "#D92B55" },
      { title: "Cash négatif", detail: "Règle critique — mart.real_estate_alerts", accent: "#D92B55" },
      { title: "Contrat arrivant à échéance", detail: "Règle critique — mart.real_estate_alerts", accent: "#D92B55" },
      { title: "Retard supérieur à 30 jours", detail: "Règle importante — mart.real_estate_alerts", accent: "#FF8735" },
      { title: "Stock critique", detail: "Règle importante — mart.real_estate_alerts", accent: "#FF8735" },
      { title: "Paiement client en retard", detail: "Règle importante — mart.real_estate_alerts", accent: "#FF8735" },
      { title: "Nouvelle vente", detail: "Signal positif — mart.real_estate_alerts", accent: "#42BFA0" },
      { title: "Nouveau programme", detail: "Signal positif — mart.real_estate_alerts", accent: "#42BFA0" },
      { title: "Livraison réalisée", detail: "Signal positif — mart.real_estate_alerts", accent: "#42BFA0" },
    ],
  },
  reports: {
    key: "reports",
    title: "Rapports",
    subtitle: "Rapports DG, investisseurs, DAF, direction technique et direction commerciale.",
    status: MART_STATUS,
    accent: "#5B6470",
    icon: <FileText {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_reporting",
    home: true,
    kpis: metricKpis("mart.real_estate_reporting", ["Rapports générés", "Exports planifiés", "Destinataires", "Validations en attente"]),
    sections: [
      section("Rapports programmés", "Fréquence, périmètre et statut", "mart.real_estate_report_schedule", "gantt", ["DG", "Investisseurs", "DAF", "Technique", "Commercial"]),
    ],
  },
  groupe: {
    key: "groupe",
    title: "Vue groupe",
    subtitle: "Consolidation transverse des filiales du groupe Kaydan.",
    status: MART_STATUS,
    accent: "#8A63D2",
    icon: <Layers {...ICON_SIZE} />,
    kind: "default",
    source: "mart.group_kpi",
    kpis: metricKpis("mart.group_kpi", ["Filiales", "Effectif groupe", "CA consolidé"]),
  },
  timeline: {
    key: "timeline",
    title: "Timeline",
    subtitle: "Jalons, échéances et charge des équipes.",
    status: MART_STATUS,
    accent: "#6366F1",
    icon: <Calendar {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_timeline",
    kpis: metricKpis("mart.real_estate_timeline", ["Jalons à venir", "Tâches en retard", "Charge équipe"]),
  },
  "work-areas": {
    key: "work-areas",
    title: "Zones de travail",
    subtitle: "Sites actifs, occupation et incidents ouverts.",
    status: MART_STATUS,
    accent: "#5B8DEF",
    icon: <Grid {...ICON_SIZE} />,
    kind: "default",
    source: "mart.real_estate_work_area",
    kpis: metricKpis("mart.real_estate_work_area", ["Sites actifs", "Taux d'occupation", "Incidents ouverts"]),
  },
  notifications: {
    key: "notifications",
    title: "Notifications",
    subtitle: "Alertes data, jalons et événements du périmètre.",
    status: "Centre d'alertes",
    accent: "#FF8735",
    icon: <Bell {...ICON_SIZE} />,
    kind: "notifications",
    source: "mart.real_estate_alerts",
    rows: rows(["Mart real_estate_kpi en attente", "Mart finance_kpi en attente", "Règles d'alertes configurées"], "mart.real_estate_alerts"),
  },
  parametres: {
    key: "parametres",
    title: "Paramètres",
    subtitle: "Préférences d'affichage, périmètre et accès.",
    status: "Lecture seule",
    accent: "#5B6470",
    icon: <Cog {...ICON_SIZE} />,
    kind: "settings",
    source: "app.settings",
    rows: [
      { title: "Périmètre par défaut", detail: "Groupe (toutes filiales)", accent: "#416FF4" },
      { title: "Langue", detail: "Français", accent: "#42BFA0" },
      { title: "Thème", detail: "Clair premium", accent: "#FF8735" },
      { title: "Rôle & RBAC", detail: "Lecture seule — données gouvernées", accent: "#8A63D2" },
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
    source: "knowledge.governance",
    rows: [
      { title: "Catalogue de métriques", detail: "Définitions et grains des KPI servis", accent: "#416FF4" },
      { title: "Gouvernance des données", detail: "RBAC, périmètre et lecture seule", accent: "#FF8735" },
      { title: "Ancrage IA", detail: "L'IA répond uniquement à partir des marts/analytics disponibles", accent: "#060606" },
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
    source: "app.profile",
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

export const DASHBOARD_LINKS: DashboardLink[] = [
  { key: "realEstate", title: "Real Estate", subtitle: "Cockpit de gouvernance immobilière", accent: "#FF8735", icon: <Building {...ICON_SIZE} /> },
  { key: "hr", title: "Ressources humaines", subtitle: "Masse salariale, entrées et sorties", accent: "#416FF4", icon: <Users {...ICON_SIZE} /> },
  { key: "finance", title: "Finance", subtitle: "Charges, marges et trésorerie", accent: "#42BFA0", icon: <CheckCircle {...ICON_SIZE} /> },
];
