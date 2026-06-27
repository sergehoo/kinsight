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
  kpis: HeroKpi[];
  chartTitle: string;
  chartUnit: string;
  alertLabels: string[];
  image?: string;
  imageMode?: "contain" | "cover";
  illustrationSvg?: string;
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
    kpis: [
      { label: "Effectif total", color: "#416FF4" },
      { label: "Turnover", color: "#D92B55" },
      { label: "Masse salariale", color: "#E08A1E" },
      { label: "Taux de présence", color: "#42BFA0" },
    ],
    chartTitle: "Évolution de l'effectif",
    chartUnit: "pers.",
    alertLabels: ["Turnover élevé", "Contrat à échéance", "Effectif critique", "Absentéisme", "Recrutement"],
    image: "/assets/businesswoman-holding-folder-smiling-camera.jpg",
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
    imageMode: "cover",
  },
};

export const domainHeroes: Record<string, DomainHeroSpec> = { ...generatedHeroes, ...photoHeroes };

export function getDomainHero(domainId: string | undefined): DomainHeroSpec | undefined {
  return domainId ? domainHeroes[domainId] : undefined;
}
