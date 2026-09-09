import { generatedHeroes } from "./domainHeroes.generated";

export interface HeroKpi {
  label: string;
  color: string;
}

/** Spec d'une page d'accueil hero de domaine. Valeurs toujours gouvernées (N/D). */
export interface DomainHeroSpec {
  id: string;
  title: string;
  kicker: string;
  tagline: string;
  accent: string;
  featuredTitle: string;
  featuredSubtitle: string;
  featuredBadges: string[];
  /** La mesure RÉELLE que la carte vedette doit afficher, quand il en existe une.
   *
   *  Sans ce descripteur la carte affiche « N/D » et « Mart EDW à raccorder » —
   *  ce qui était codé en dur pour TOUS les domaines, y compris ceux dont une
   *  source vivante servait déjà le même chiffre à deux centimètres de là. La
   *  clé est celle du KPI servi par le backend, jamais un identifiant parallèle :
   *  deux identités pour une mesure, c'est deux versions qui divergent. */
  featuredMetric?: { source: "shield-hr"; key: string };
  kpis: HeroKpi[];
  chartTitle: string;
  chartUnit: string;
  alertLabels: string[];
  image?: string;
  imageMode?: "contain" | "cover";
  illustrationSvg?: string;
  /** Base des variantes optimisées dans /assets/opt (sans largeur ni extension). */
  imageSlug?: string;
  /** Description réelle du visuel ; vide si purement décoratif. */
  imageAlt?: string;
  /** Largeurs réellement générées dans /assets/opt pour ce visuel. */
  imageWidths?: number[];
  /** Ancrage du recadrage : « right » garde le sujet visible côté droit. */
  imageFocus?: "center" | "right" | "left";
}

/** Domaines disposant d'une vraie photo (assets existants). */
const photoHeroes: Record<string, DomainHeroSpec> = {
  immobilier: {
    id: "immobilier",
    title: "Immobilier",
    kicker: "Gouvernance immobilière",
    tagline: "Programmes, construction, ventes et patrimoine consolidés du Groupe.",
    accent: "#FF8735",
    featuredTitle: "Résidence Komatsu",
    featuredSubtitle: "Programme phare · avancement",
    featuredBadges: ["KO", "AD"],
    kpis: [
      { label: "Avancement construction", color: "#FF8735" },
      { label: "Taux de commercialisation", color: "#416FF4" },
      { label: "Budget consommé", color: "#E08A1E" },
      { label: "Stock restant", color: "#42BFA0" },
    ],
    chartTitle: "Évolution des ventes & avancement",
    chartUnit: "%",
    alertLabels: ["Chantier arrêté", "Dépassement budget", "Retard livraison", "Stock critique", "Nouvelle vente"],
    image: "/assets/construction.png",
    imageSlug: "immobilier-chantier",
    imageWidths: [640, 1024],
    imageAlt:
      "Maquette d'immeuble en construction, structure et échafaudages apparents, surmontée d'une grue à tour",
    imageMode: "contain",
  },
  "capital-humain": {
    id: "capital-humain",
    title: "Capital Humain",
    kicker: "Gouvernance RH",
    tagline: "Effectifs, présence, masse salariale et performance du Groupe.",
    accent: "#416FF4",
    featuredTitle: "Effectif Groupe",
    featuredSubtitle: "Consolidé multi-filiales",
    featuredBadges: ["RH", "DG"],
    // `effectif_total` est la MÊME clé que celle de la grille de KPI : la carte
    // vedette affichait « N/D · Mart EDW à raccorder » pendant que la carte
    // voisine affichait 722 depuis Shield. Un seul chiffre, une seule source.
    featuredMetric: { source: "shield-hr", key: "effectif_total" },
    kpis: [
      { label: "Effectif total", color: "#416FF4" },
      { label: "Turnover", color: "#D92B55" },
      { label: "Masse salariale", color: "#E08A1E" },
      { label: "Taux de présence", color: "#42BFA0" },
    ],
    chartTitle: "Évolution de l'effectif",
    chartUnit: "pers.",
    alertLabels: ["Turnover élevé", "Contrat à échéance", "Effectif critique", "Absentéisme", "Recrutement"],
    image: "/assets/capitalhumain.png",
    imageSlug: "capital-humain-collaboratrice",
    imageWidths: [640, 1024],
    // `imageFocus` retiré avec `cover` : l'ancrage du recadrage n'a de sens que
    // pour un visuel qui remplit le cadre. Un sujet détouré, lui, se contient.
    imageAlt: "Collaboratrice souriante en tenue professionnelle, tenant une tablette numérique",
    imageMode: "contain",
  },
  finance: {
    id: "finance",
    title: "Finance",
    kicker: "Gouvernance financière",
    tagline: "Trésorerie, budget, rentabilité et risques financiers consolidés.",
    accent: "#42BFA0",
    featuredTitle: "Trésorerie nette",
    featuredSubtitle: "Position consolidée Groupe",
    featuredBadges: ["DAF", "DG"],
    kpis: [
      { label: "Cash disponible", color: "#42BFA0" },
      { label: "Budget consommé", color: "#E08A1E" },
      { label: "Marge", color: "#416FF4" },
      { label: "EBITDA", color: "#8A63D2" },
    ],
    chartTitle: "Évolution de la trésorerie",
    chartUnit: "XOF",
    alertLabels: ["Cash négatif", "Dépassement budget", "Créance en retard", "Échéance fiscale", "Encaissement"],
    image: "/assets/finance.png",
    imageSlug: "finance-croissance",
    imageWidths: [640, 1024],
    imageAlt: "Piles de pièces de monnaie surmontées d'une jeune pousse verte, image d'un capital qui croît",
    imageMode: "contain",
  },

  /** IA Décisionnelle — on ne redéfinit QUE le visuel.
   *
   *  Le reste de la spec (titre, accroche, KPI, libellés d'alerte) vient du
   *  fichier généré, qui porte la mention « ne pas éditer à la main » : le
   *  recopier ici en ferait une seconde version, et les deux divergeraient à la
   *  première régénération. On étend, on ne duplique pas.
   *
   *  `illustrationSvg` reste dans la spec sans être rendu : `DomainHome` donne la
   *  priorité à `image` et ne retombe sur le SVG qu'en son absence. Le garder
   *  coûte quelques octets et préserve le repli si le visuel venait à disparaître.
   */
  ia: {
    ...generatedHeroes.ia,
    image: "/assets/AI.png",
    imageSlug: "ia-copilote",
    // 640 et 1024 UNIQUEMENT : la source fait 1229 px de côté, une variante 1600
    // serait un agrandissement — et `HeroImage` avertit qu'une largeur déclarée
    // mais non générée provoque un 404 puis un repli sur l'original de 1,6 Mo.
    imageWidths: [640, 1024],
    imageAlt:
      "Tête robotique de profil, coque blanche entrouverte laissant voir des rouages et des circuits lumineux",
    // Sujet détouré sur fond transparent : `contain` conserve la silhouette,
    // là où `cover` la recadrerait dans un cadre presque carré.
    imageMode: "contain",
  },

  /* Les quatre domaines ci-dessous n'avaient qu'une illustration SVG générée. On
     leur donne un visuel SANS recopier leur spec : `...generatedHeroes.<id>`
     conserve titre, accroche, KPI et libellés d'alerte du fichier généré, qui
     porte la mention « ne pas éditer à la main ». Tous ces PNG sont détourés sur
     fond transparent, d'où `contain` partout : `cover` les recadrerait et
     poserait un cadre arrondi autour du sujet. */

  overview: {
    ...generatedHeroes.overview,
    image: "/assets/vision.png",
    imageSlug: "overview-cible",
    imageWidths: [640, 1024],
    imageAlt: "Cible de fléchettes vue de trois quarts, une fléchette plantée en plein centre",
    imageMode: "contain",
  },

  operations: {
    ...generatedHeroes.operations,
    image: "/assets/logistique.png",
    imageSlug: "operations-logistique",
    // 640 et 900 : la source ne fait que 900 px de large, contre 1229 pour les
    // autres. Déclarer 1024 ici demanderait un fichier qui n'existe pas.
    imageWidths: [640, 900],
    imageAlt:
      "Montage logistique : avion de ligne, globe terrestre, porte-conteneurs, camion et utilitaire",
    imageMode: "contain",
  },

  "commercial-clients": {
    ...generatedHeroes["commercial-clients"],
    image: "/assets/commercial.png",
    imageSlug: "commercial-equipe",
    imageWidths: [640, 1024],
    imageAlt: "Deux commerciaux en costume, souriants, l'un présentant de la main, l'autre bras croisés",
    imageMode: "contain",
  },

  "risques-conformite": {
    ...generatedHeroes["risques-conformite"],
    image: "/assets/risk.png",
    imageSlug: "risques-balance",
    imageWidths: [640, 1024],
    imageAlt:
      "Balance à deux plateaux en équilibre : pièces de monnaie d'un côté, le mot « Risk » en rouge de l'autre",
    imageMode: "contain",
  },
};

export const domainHeroes: Record<string, DomainHeroSpec> = { ...generatedHeroes, ...photoHeroes };

export function getDomainHero(domainId: string | undefined): DomainHeroSpec | undefined {
  return domainId ? domainHeroes[domainId] : undefined;
}
