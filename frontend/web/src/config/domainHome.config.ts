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
    image: "/assets/%E2%80%94Pngtree%E2%80%94modern%20yellow%20construction%20crane%20for_20885637.png",
    imageSlug: "immobilier-crane",
    imageAlt: "Grue de chantier sur un programme immobilier en construction",
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
    image: "/assets/capital-humain-equipe-stocksnap.jpg",
    imageSlug: "capital-humain-equipe",
    imageWidths: [640, 960],
    imageFocus: "right",
    imageAlt: "Équipe pluridisciplinaire en réunion de travail autour d'une table, ordinateurs et notes",
    imageMode: "cover",
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
    image: "/assets/tree-grows-coin-glass-jar-with-copy-space.jpg",
    imageSlug: "finance-tresorerie",
    imageAlt: "Épargne en croissance, symbole de trésorerie",
    imageMode: "cover",
  },
};

export const domainHeroes: Record<string, DomainHeroSpec> = { ...generatedHeroes, ...photoHeroes };

export function getDomainHero(domainId: string | undefined): DomainHeroSpec | undefined {
  return domainId ? domainHeroes[domainId] : undefined;
}
