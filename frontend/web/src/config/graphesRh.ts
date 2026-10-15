/** Graphiques RÉELS des modules Capital Humain.
 *
 *  Le catalogue `lib/modules.tsx` déclare, par module, des « sections » nées quand
 *  le mart EDW était la source envisagée : chacune rendait un cadre de graphe VIDE
 *  (« Aucune série servie »), avec des emplacements d'axe. Dix-neuf modules, une
 *  quarantaine de graphes décoratifs.
 *
 *  Ce fichier dit, module par module, ce qui se TRACE vraiment — une métrique du
 *  registre canonique (`hr_registry.py`), lue dans l'historique K-Insight sous les
 *  filtres du cockpit — et, pour les sections qu'aucune source ne sert, POURQUOI.
 *  Une section remplacée par un graphe réel est nommée dans `remplace` ; toutes les
 *  autres sont listées « sans source » avec leur motif, sans cadre vide.
 *
 *  Aucun chiffre ni aucune métrique n'est déclaré ici : seulement des identifiants
 *  du registre. Le choix du type suit la donnée (mission §12) : courbe pour une
 *  tendance, barres pour comparer des sites ou des départements, donut pour une
 *  structure, barres empilées pour employés / ouvriers, chaleur pour jours × sites.
 */

export type GrapheRh =
  /** Tendance jour par jour d'une métrique sur la période filtrée. */
  | { type: "courbe"; titre: string; sousTitre: string; metric: string }
  /** Composition jour par jour par type de personnel (`matrice=type`). */
  | { type: "empile-type"; titre: string; sousTitre: string; metric: string }
  /** Jours × sites (`matrice=site`), colorée par les seuils de décision. */
  | { type: "chaleur-sites"; titre: string; sousTitre: string; metric: string }
  /** Comparaison des codes d'une dimension sur la période (`ventilation=`). */
  | { type: "barres"; titre: string; sousTitre: string; metric: string; ventilation: "site" | "departement" }
  /** Structure d'un ensemble ventilé (`ventilation=`). */
  | { type: "donut"; titre: string; sousTitre: string; metric: string; ventilation: "type" | "departement" }
  /** Structure recomposée de stocks distincts (employés / ouvriers déclarés). */
  | { type: "donut-stocks"; titre: string; sousTitre: string; parts: [PartDeStock, PartDeStock] };

interface PartDeStock { metric: string; libelle: string }

export interface GraphesModuleRh {
  graphes: GrapheRh[];
  /** Titres de sections du catalogue que ces graphes remplacent. */
  remplace?: string[];
  /** Motif propre à une section sans source (par titre). */
  motifs?: Record<string, string>;
  /** Motif commun aux autres sections sans source de ce module. */
  motif?: string;
}

export const MOTIF_RH_PAR_DEFAUT = "Aucune série servie par Kaydan Shield ni Odoo pour cette analyse.";

export const PRESENCE_TAUX: GrapheRh = {
  type: "courbe", titre: "Taux de présence", metric: "hr.taux_presence_jour",
  sousTitre: "Présents ÷ attendus, jour par jour — Kaydan Shield",
};
export const PRESENTS_PAR_TYPE: GrapheRh = {
  type: "empile-type", titre: "Présents par jour — employés / ouvriers", metric: "hr.presents_jour",
  sousTitre: "Composition quotidienne des présents — Kaydan Shield",
};
export const CHALEUR_SITES: GrapheRh = {
  type: "chaleur-sites", titre: "Présence jours × sites", metric: "hr.taux_presence_jour",
  sousTitre: "Taux de présence de chaque site, chaque jour — couleur selon les seuils de décision",
};
export const STRUCTURE_DECLAREE: GrapheRh = {
  type: "donut-stocks", titre: "Structure de l'effectif déclaré",
  sousTitre: "Employés et ouvriers déclarés dans Shield — dernière valeur de la période",
  parts: [{ metric: "hr.employes", libelle: "Employés" }, { metric: "hr.ouvriers", libelle: "Ouvriers" }],
};

const SANS_PAIE = "La paie n'est pas lue par K-Insight : ni masse salariale, ni charges, ni primes.";
const SANS_MOUVEMENTS = "Entrées et départs non mesurés : les dates d'embauche et de départ ne sont pas lues dans Odoo.";

export const GRAPHES_RH: Record<string, GraphesModuleRh> = {
  "hr-executive": {
    graphes: [
      {
        type: "courbe", titre: "Effectif déclaré", metric: "hr.effectif_total",
        sousTitre: "Employés + ouvriers déclarés dans Shield, relevé quotidien",
      },
      {
        type: "courbe", titre: "Employés actifs (Odoo)", metric: "hr.employes_actifs_odoo",
        sousTitre: "Fiches employé actives du référentiel Odoo, relevé quotidien",
      },
      PRESENCE_TAUX,
      PRESENTS_PAR_TYPE,
      STRUCTURE_DECLAREE,
    ],
    remplace: ["Evolution effectif", "Evolution absentéisme"],
    motifs: {
      "Evolution turnover": SANS_MOUVEMENTS,
      "Evolution masse salariale": SANS_PAIE,
      "Evolution recrutements": "Les candidatures Odoo ne sont que comptées ; promotions et mobilités ne sont pas lues.",
    },
  },
  "hr-workforce": {
    graphes: [
      STRUCTURE_DECLAREE,
      {
        type: "donut", titre: "Structure par département (Odoo)", metric: "hr.employes_actifs_odoo",
        ventilation: "departement",
        sousTitre: "Employés actifs par département — dernière valeur de la période",
      },
    ],
    motifs: {
      "Pyramide des âges": "Âge, genre et ancienneté ne sont pas lus dans Odoo (données personnelles non importées).",
      "Répartition métiers": "Métiers (hr.job) et directions ne sont pas ventilés ; la structure par département est tracée ci-dessus.",
      "Répartition hiérarchique": "Les niveaux hiérarchiques et les rattachements managériaux ne sont pas lus.",
      "Cartographie effectifs": "Pays, régions et villes ne sont portés ni par Shield ni par le référentiel Odoo lu.",
    },
  },
  "hr-organization": {
    graphes: [
      {
        type: "barres", titre: "Employés actifs par département", metric: "hr.employes_actifs_odoo",
        ventilation: "departement",
        sousTitre: "Comparaison des départements Odoo — dernière valeur de la période",
      },
    ],
    motifs: {
      "Organigramme dynamique": "La hiérarchie (responsables, rattachements) n'est pas lue dans Odoo.",
      "Succession & postes vacants": "Les postes à pourvoir sont comptés (carte ci-dessus) ; la succession n'est tracée nulle part.",
    },
  },
  // La page réelle de présence est `AttendancePage` ; ces graphes servent l'accès
  // direct `/modules/hr-attendance`, qui rend encore le catalogue.
  "hr-attendance": {
    graphes: [PRESENCE_TAUX, CHALEUR_SITES, PRESENTS_PAR_TYPE,
      {
        type: "barres", titre: "Taux de présence par site", metric: "hr.taux_presence_jour", ventilation: "site",
        sousTitre: "Du plus au moins performant sur la période — Kaydan Shield",
      }],
    remplace: ["Heatmap présence", "Evolution journalière", "Top retards & absences"],
  },
  "hr-recruitment": {
    graphes: [],
    motifs: {
      "Funnel de recrutement": "Les étapes des candidatures (hr.applicant) ne sont pas lues : pas d'entonnoir sans étapes réelles.",
      "Délais & coûts": "Ni dates de candidature ni coûts de recrutement ne sont lus.",
    },
  },
  "hr-payroll": { graphes: [], motif: SANS_PAIE },
  "hr-performance": {
    graphes: [],
    motif: "Aucune évaluation ni objectif n'est lu (module d'évaluation Odoo non raccordé) : pas de score, pas de nuage performance × coût.",
  },
  "hr-leave": { graphes: [], motif: "Les congés (hr.leave) ne sont pas encore lus dans Odoo." },
  "hr-training": { graphes: [], motif: "Aucune donnée de formation n'est lue." },
  "hr-skills": { graphes: [], motif: "Aucune donnée de compétences n'est lue." },
  "hr-career": { graphes: [], motif: "Promotions, mobilités et plans de succession ne sont lus nulle part." },
  "hr-experience": { graphes: [], motif: "Aucune enquête d'engagement ni de satisfaction n'est raccordée." },
  "hr-health-safety": {
    graphes: [],
    motif: "Les incidents de sécurité Shield ne sont pas encore rapprochés des effectifs ; EPI et visites médicales ne sont pas lus.",
  },
  "hr-compliance": { graphes: [], motif: "Contrats et échéances (hr.contract) ne sont pas encore lus en détail." },
  "hr-planning": { graphes: [], motif: "Aucune prévision n'est publiée tant que les mouvements d'effectif ne sont pas mesurés." },
  "hr-diversity": { graphes: [], motif: "Genre, âge et nationalité ne sont pas lus (données personnelles non importées)." },
  "hr-ai": { graphes: [], motif: "Les prévisions IA attendent des séries de mouvements et de paie qui ne sont pas lues." },
  "hr-reports": { graphes: [], motif: "Le calendrier des rapports programmés n'est pas encore en place." },
};

/** Les sections du catalogue que rien ne trace, avec leur motif. */
export function sectionsSansSource(
  moduleKey: string,
  sections: { title: string; subtitle: string }[],
): { titre: string; sousTitre: string; motif: string }[] {
  const spec = GRAPHES_RH[moduleKey];
  const remplacees = new Set(spec?.remplace ?? []);
  return sections
    .filter((s) => !remplacees.has(s.title))
    .map((s) => ({
      titre: s.title,
      sousTitre: s.subtitle,
      motif: spec?.motifs?.[s.title] ?? spec?.motif ?? MOTIF_RH_PAR_DEFAUT,
    }));
}
