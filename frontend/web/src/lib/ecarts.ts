/** L'écart d'une métrique à une période de référence, dit de la même façon partout.
 *
 *  En points pour un taux (un écart de pourcentages n'est pas un pourcentage),
 *  en valeur et en % pour un volume ; coloré selon que la HAUSSE est favorable
 *  ou non pour CETTE métrique. Rien quand l'une des deux valeurs manque : un
 *  écart contre une période non mesurée n'existe pas. */

/** Métriques dont la hausse est une dégradation. Sans cette liste, « +12 absents »
 *  s'affichait en vert, comme un progrès. */
export const HAUSSE_DEFAVORABLE = new Set([
  "hr.absents_jour", "hr.retards_jour", "hr.taux_absence_jour",
  "hr.absenteisme_mensuel", "hr.turnover", "hr.sorties", "hr.heures_supplementaires",
]);

export interface Ecart {
  value?: number | null;
  ecart: number | null;
  ecart_pct?: number | null;
  unite_ecart?: "pts" | "abs" | null;
}

export function ecartAffiche(metricId: string | undefined, c: Ecart | undefined, reference = "période préc."):
  { texte: string; favorable: boolean } | null {
  if (!c || c.ecart === null || c.ecart === undefined) return null;
  if (c.ecart === 0) return { texte: `stable vs ${reference}`, favorable: true };
  const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
  const signe = c.ecart > 0 ? "+" : "−";
  const abs = nombre.format(Math.abs(c.ecart));
  const pct = c.ecart_pct !== null && c.ecart_pct !== undefined
    ? ` (${signe}${nombre.format(Math.abs(c.ecart_pct))} %)` : "";
  const texte = c.unite_ecart === "pts"
    ? `${signe}${abs} pt${Math.abs(c.ecart) >= 2 ? "s" : ""} vs ${reference}`
    : `${signe}${abs}${pct} vs ${reference}`;
  const defavorable = HAUSSE_DEFAVORABLE.has(metricId ?? "");
  return { texte, favorable: defavorable ? c.ecart < 0 : c.ecart > 0 };
}
