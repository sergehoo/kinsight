/** Registre des métriques attendues par domaine.
 *
 *  Ce fichier DÉCLARE ce que chaque cockpit métier doit afficher — identifiant,
 *  libellé, unité, niveau, formule, source visée — sans jamais porter de valeur.
 *  Toute métrique naît donc `disconnected` et le reste tant qu'un adaptateur ne
 *  l'alimente pas avec une donnée réelle.
 *
 *  Deux effets recherchés :
 *  1. un domaine devient « prêt à brancher » sans qu'on invente ni chiffre ni endpoint ;
 *  2. l'écart entre le cockpit cible et ce qui est réellement alimenté est LISIBLE
 *     à l'écran, au lieu d'être masqué par des données de démonstration.
 *
 *  Convention de clé de domaine : on utilise l'identifiant de `modules.config.ts`
 *  (« capital-humain »), pas la clé sémantique « hr » du catalogue de métriques.
 */
import { declaredMetric, type KMetric } from "@/lib/kmetric";

/** Sources connues. `code` sert d'identifiant machine dans KMetric.source. */
export const SOURCES = {
  shield: { code: "kaydan_shield", label: "Kaydan Shield" },
  odoo: { code: "odoo", label: "Odoo" },
  sap: { code: "sap", label: "SAP" },
  edw: { code: "edw", label: "Mart EDW" },
  interne: { code: "api_interne", label: "API métier interne" },
} as const;

type SourceKey = keyof typeof SOURCES;

interface MetricSpec {
  id: string;
  title: string;
  unit?: string;
  source: SourceKey;
  /** Par défaut « measured ». `formula` est obligatoire dès que c'est un calcul. */
  level?: "measured" | "computed" | "predicted";
  formula?: string;
  drilldown?: string;
}

function build(specs: MetricSpec[]): KMetric[] {
  return specs.map((spec) =>
    declaredMetric({
      id: spec.id,
      title: spec.title,
      unit: spec.unit,
      level: spec.level ?? "measured",
      formula: spec.formula,
      source: SOURCES[spec.source].code,
      sourceLabel: SOURCES[spec.source].label,
      drilldownUrl: spec.drilldown,
    }),
  );
}

/* ── Overview Groupe ───────────────────────────────────────────────────────── */
const OVERVIEW: MetricSpec[] = [
  { id: "groupe.ca_consolide", title: "CA consolidé", unit: "XOF", source: "edw", level: "computed", formula: "somme des CA filiales, retraitée des flux intragroupe" },
  { id: "groupe.tresorerie", title: "Trésorerie", unit: "XOF", source: "edw" },
  { id: "groupe.marge", title: "Marge / EBITDA", unit: "%", source: "edw", level: "computed", formula: "EBITDA ÷ CA consolidé × 100" },
  { id: "groupe.effectif", title: "Effectif Groupe", source: "shield", level: "computed", formula: "employés + ouvriers, toutes filiales" },
  { id: "groupe.patrimoine", title: "Patrimoine", unit: "XOF", source: "edw" },
  { id: "groupe.risque_global", title: "Risque global", unit: "index", source: "edw", level: "computed", formula: "score pondéré des dimensions de risque alimentées" },
  { id: "groupe.budget_realise", title: "Budget vs réalisé", unit: "%", source: "edw", level: "computed", formula: "réalisé ÷ budget × 100" },
];

/* ── Immobilier ────────────────────────────────────────────────────────────── */
const IMMOBILIER: MetricSpec[] = [
  { id: "immo.valeur_patrimoine", title: "Valeur du patrimoine", unit: "XOF", source: "edw" },
  { id: "immo.surface_geree", title: "Surface gérée", unit: "m²", source: "edw" },
  { id: "immo.taux_occupation", title: "Taux d'occupation", unit: "%", source: "edw", level: "computed", formula: "surface occupée ÷ surface gérée × 100" },
  { id: "immo.avancement", title: "Avancement construction", unit: "%", source: "edw" },
  { id: "immo.commercialisation", title: "Taux de commercialisation", unit: "%", source: "edw", level: "computed", formula: "lots réservés ou vendus ÷ lots disponibles × 100" },
  { id: "immo.budget_consomme", title: "Budget consommé", unit: "%", source: "edw", level: "computed", formula: "dépenses engagées ÷ budget projet × 100" },
  { id: "immo.rentabilite", title: "Rentabilité", unit: "%", source: "edw", level: "computed", formula: "résultat net du projet ÷ capitaux investis × 100" },
];

/* ── Capital Humain ────────────────────────────────────────────────────────── */
// Les six premières sont réellement alimentées par le connecteur Shield.
const CAPITAL_HUMAIN: MetricSpec[] = [
  { id: "shield.effectif_total", title: "Effectif total", source: "shield", level: "computed", formula: "employés + ouvriers" },
  { id: "shield.employes", title: "Employés", source: "shield" },
  { id: "shield.ouvriers", title: "Ouvriers", source: "shield" },
  { id: "shield.presents", title: "Présents aujourd'hui", source: "shield" },
  { id: "shield.absents", title: "Absents", source: "shield" },
  { id: "shield.retards", title: "Retards", source: "shield" },
  { id: "shield.taux_presence", title: "Taux de présence", unit: "%", source: "shield", level: "computed", formula: "présents ÷ (présents + absents) × 100" },
  { id: "rh.absenteisme", title: "Taux d'absentéisme", unit: "%", source: "odoo", level: "computed", formula: "jours d'absence ÷ jours travaillés théoriques × 100" },
  { id: "rh.turnover", title: "Turnover", unit: "%", source: "odoo", level: "computed", formula: "départs sur la période ÷ effectif moyen × 100" },
  { id: "hr.masse_salariale", title: "Masse salariale", unit: "XOF", source: "edw" },
  { id: "hr.entrees", title: "Entrées", source: "edw" },
  { id: "hr.sorties", title: "Sorties", source: "edw" },
  { id: "hr.variation_effectif", title: "Variation d'effectif", source: "edw", level: "computed", formula: "entrées − sorties sur la période" },
  { id: "rh.heures_sup", title: "Heures supplémentaires", unit: "h", source: "shield" },
  { id: "rh.conges", title: "Congés en cours", unit: "j", source: "odoo" },
  { id: "rh.recrutements", title: "Recrutements en cours", source: "odoo" },
  { id: "rh.prestataires", title: "Prestataires", source: "odoo" },
];

/* ── Finance ───────────────────────────────────────────────────────────────── */
const FINANCE: MetricSpec[] = [
  { id: "fin.cash", title: "Cash disponible", unit: "XOF", source: "edw" },
  { id: "fin.ca", title: "Chiffre d'affaires", unit: "XOF", source: "edw" },
  { id: "fin.encaissements", title: "Encaissements", unit: "XOF", source: "edw" },
  { id: "fin.decaissements", title: "Décaissements", unit: "XOF", source: "edw" },
  { id: "fin.marge", title: "Marge", unit: "%", source: "edw", level: "computed", formula: "(CA − coûts directs) ÷ CA × 100" },
  { id: "fin.creances", title: "Créances clients", unit: "XOF", source: "edw" },
  { id: "fin.dettes", title: "Dettes fournisseurs", unit: "XOF", source: "edw" },
  { id: "fin.budget", title: "Budget vs réalisé", unit: "%", source: "edw", level: "computed", formula: "réalisé ÷ budget × 100" },
  { id: "fin.resultat", title: "Résultat", unit: "XOF", source: "edw" },
  { id: "fin.dso", title: "DSO", unit: "j", source: "edw", level: "computed", formula: "créances clients ÷ CA TTC × nombre de jours de la période" },
  { id: "fin.dpo", title: "DPO", unit: "j", source: "edw", level: "computed", formula: "dettes fournisseurs ÷ achats TTC × nombre de jours de la période" },
  { id: "fin.cash_flow", title: "Cash-flow", unit: "XOF", source: "edw", level: "computed", formula: "encaissements − décaissements sur la période" },
];

/* ── Opérations & Logistique ───────────────────────────────────────────────── */
const OPERATIONS: MetricSpec[] = [
  { id: "ops.taux_service", title: "Taux de service", unit: "%", source: "edw", level: "computed", formula: "commandes servies complètes ÷ commandes totales × 100" },
  { id: "ops.livraisons_temps", title: "Livraisons à temps", unit: "%", source: "edw", level: "computed", formula: "livraisons dans le délai promis ÷ livraisons totales × 100" },
  { id: "ops.stocks", title: "Valeur des stocks", unit: "XOF", source: "odoo" },
  { id: "ops.ruptures", title: "Ruptures de stock", source: "odoo" },
  { id: "ops.couverture_stock", title: "Couverture de stock", unit: "j", source: "odoo", level: "computed", formula: "stock disponible ÷ consommation moyenne journalière" },
  { id: "ops.delais_fournisseurs", title: "Délai fournisseurs moyen", unit: "j", source: "odoo" },
  { id: "ops.avancement_chantiers", title: "Avancement chantiers", unit: "%", source: "edw" },
  { id: "ops.flotte", title: "Véhicules disponibles", source: "odoo" },
  { id: "ops.maintenance", title: "Interventions en attente", source: "odoo" },
];

/* ── Commercial & Clients ──────────────────────────────────────────────────── */
const COMMERCIAL: MetricSpec[] = [
  { id: "com.pipeline", title: "Pipeline", unit: "XOF", source: "odoo" },
  { id: "com.ca_signe", title: "CA signé", unit: "XOF", source: "odoo" },
  { id: "com.conversion", title: "Taux de conversion", unit: "%", source: "odoo", level: "computed", formula: "opportunités gagnées ÷ opportunités traitées × 100" },
  { id: "com.reservations", title: "Réservations signées", source: "edw" },
  { id: "com.panier_moyen", title: "Panier moyen", unit: "XOF", source: "odoo", level: "computed", formula: "CA signé ÷ nombre de ventes" },
  { id: "com.delai_signature", title: "Délai moyen de signature", unit: "j", source: "odoo", level: "computed", formula: "moyenne des délais entre création et signature de l'opportunité" },
  { id: "com.opportunites", title: "Opportunités ouvertes", source: "odoo" },
  { id: "com.clients_actifs", title: "Clients actifs", source: "odoo" },
];

/* ── Risques & Conformité ──────────────────────────────────────────────────── */
const RISQUES: MetricSpec[] = [
  { id: "risk.exposition", title: "Exposition globale", unit: "index", source: "edw", level: "computed", formula: "moyenne pondérée des risques résiduels par dimension alimentée" },
  { id: "risk.alertes_critiques", title: "Alertes critiques", source: "shield" },
  { id: "risk.incidents", title: "Incidents", source: "edw" },
  { id: "risk.conformite", title: "Taux de conformité", unit: "%", source: "edw", level: "computed", formula: "contrôles conformes ÷ contrôles réalisés × 100" },
  { id: "risk.actions_correctives", title: "Actions correctives", source: "edw" },
  { id: "risk.actions_retard", title: "Actions en retard", source: "edw" },
  { id: "risk.anomalies_acces", title: "Anomalies d'accès", source: "shield" },
];

export const DOMAIN_METRICS: Record<string, MetricSpec[]> = {
  overview: OVERVIEW,
  immobilier: IMMOBILIER,
  "capital-humain": CAPITAL_HUMAIN,
  finance: FINANCE,
  operations: OPERATIONS,
  "commercial-clients": COMMERCIAL,
  "risques-conformite": RISQUES,
};

/** Métriques déclarées d'un domaine, toutes en `disconnected` : c'est le socle
 *  sur lequel un adaptateur vient superposer les valeurs réellement obtenues. */
export function declaredMetricsFor(domainId: string): KMetric[] {
  return build(DOMAIN_METRICS[domainId] ?? []);
}

/** Sources visées par un domaine, dédoublonnées — alimente SourceHealth. */
export function sourcesFor(domainId: string): Array<{ code: string; label: string }> {
  const specs = DOMAIN_METRICS[domainId] ?? [];
  const seen = new Map<string, string>();
  for (const spec of specs) {
    const source = SOURCES[spec.source];
    seen.set(source.code, source.label);
  }
  return [...seen].map(([code, label]) => ({ code, label }));
}

/** Superpose les métriques réellement obtenues sur les métriques déclarées.
 *  Une déclaration non alimentée reste visible en `disconnected` : c'est ce qui
 *  rend l'écart au cockpit cible lisible plutôt que silencieux. */
export function mergeMetrics(domainId: string, live: KMetric[]): KMetric[] {
  const byId = new Map(live.map((m) => [m.id, m]));
  const declared = declaredMetricsFor(domainId);
  const merged = declared.map((d) => byId.get(d.id) ?? d);
  // Métriques servies par une source mais non déclarées : on les conserve en fin
  // de liste plutôt que de les perdre silencieusement.
  const extra = live.filter((m) => !declared.some((d) => d.id === m.id));
  return [...merged, ...extra];
}
