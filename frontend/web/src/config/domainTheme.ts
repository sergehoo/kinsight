/** Accent métier par domaine — source unique des tokens `--domain-*`.
 *
 *  Aucune couleur d'accent ne doit être écrite en dur dans un composant : tout
 *  passe par les variables CSS posées ici. L'orange Kaydan reste la couleur de
 *  marque (logo, CTA principaux) et n'est pas remplacé par l'accent métier.
 *
 *  `ink` est une déclinaison assombrie du même ton, réservée au TEXTE : les
 *  accents saturés (ambre, teal, vert…) ne passent pas le contraste AA 4.5:1
 *  sur fond clair. `accent` reste utilisé pour les aplats, bordures, halos,
 *  icônes et courbes, où le seuil 4.5:1 ne s'applique pas.
 */

export interface DomainAccent {
  /** Aplats, bordures, halos, icônes, courbes. */
  accent: string;
  /** Déclinaison AA-safe pour le texte sur fond clair (≥ 4.5:1). */
  ink: string;
}

const FALLBACK: DomainAccent = { accent: "#FF8735", ink: "#B4470D" };

export const DOMAIN_ACCENTS: Record<string, DomainAccent> = {
  overview: { accent: "#3B82F6", ink: "#1D4ED8" },
  immobilier: { accent: "#F59E0B", ink: "#B45309" },
  "capital-humain": { accent: "#14B8A6", ink: "#0F766E" },
  finance: { accent: "#10B981", ink: "#047857" },
  operations: { accent: "#F97316", ink: "#C2410C" },
  "commercial-clients": { accent: "#8B5CF6", ink: "#6D28D9" },
  "risques-conformite": { accent: "#E11D48", ink: "#BE123C" },
  // Domaines transverses : on retombe sur la couleur de marque.
  ia: FALLBACK,
  rapports: FALLBACK,
};

export function getDomainAccent(moduleId: string | undefined): DomainAccent {
  return (moduleId && DOMAIN_ACCENTS[moduleId]) || FALLBACK;
}

/** `#RRGGBB` + alpha → `rgb(r g b / a)`. */
function withAlpha(hex: string, alpha: number): string {
  const clean = hex.replace("#", "");
  const r = Number.parseInt(clean.slice(0, 2), 16);
  const g = Number.parseInt(clean.slice(2, 4), 16);
  const b = Number.parseInt(clean.slice(4, 6), 16);
  return `rgb(${r} ${g} ${b} / ${alpha})`;
}

/** Jeu de tokens `--domain-*` correspondant à un domaine. */
export function domainTokens(moduleId: string | undefined): Record<string, string> {
  const { accent, ink } = getDomainAccent(moduleId);
  return {
    "--domain-accent": accent,
    "--domain-ink": ink,
    "--domain-soft": withAlpha(accent, 0.12),
    "--domain-glow": withAlpha(accent, 0.16),
    "--domain-ring": withAlpha(accent, 0.45),
  };
}
