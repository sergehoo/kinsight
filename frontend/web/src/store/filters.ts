import { create } from "zustand";

/** Filtres globaux du tableau de bord (période + filiale). */
interface FiltersState {
  year: number;
  quarter: number;
  subsidiary: string; // "all" | code filiale (KRE, KSH, MYK…)
  setYear: (year: number) => void;
  setQuarter: (quarter: number) => void;
  setSubsidiary: (subsidiary: string) => void;
}

/** Valeur du filiale signifiant « pas de restriction supplémentaire ».
 *
 *  Elle ne veut pas dire « toutes les filiales du Groupe » : le périmètre serveur
 *  borne de toute façon la réponse. Pour un directeur de filiale, « toutes »
 *  signifie donc « tout mon périmètre », qui est sa seule filiale.
 */
export const TOUTES_FILIALES = "all";

export const useFilters = create<FiltersState>((set) => ({
  year: 2026,
  quarter: 1,
  subsidiary: TOUTES_FILIALES,
  setYear: (year) => set({ year }),
  setQuarter: (quarter) => set({ quarter }),
  setSubsidiary: (subsidiary) => set({ subsidiary }),
}));

/* ── Période → vraies bornes ───────────────────────────────────────────────── */

/** Les deux bornes ISO d'un trimestre civil.
 *
 *  Le sélecteur « T2 2025 » ne produisait AUCUNE date : aucune requête ne portait
 *  de période, et le filtre paraissait agir sans agir. Cette fonction est le
 *  chaînon manquant — un seul endroit calcule les bornes, pour que deux écrans ne
 *  puissent pas diverger sur ce que « T2 » veut dire.
 *
 *  Le dernier jour est calculé par `new Date(année, mois, 0)` : le jour 0 du mois
 *  suivant est le dernier du mois courant, ce qui donne 30, 31 ou 29 sans table
 *  de correspondance ni cas particulier pour les années bissextiles.
 */
export function bornesDuTrimestre(year: number, quarter: number): { dateFrom: string; dateTo: string } {
  const trimestre = Math.min(4, Math.max(1, Math.trunc(quarter)));
  const moisDebut = (trimestre - 1) * 3;
  const debut = new Date(year, moisDebut, 1);
  const fin = new Date(year, moisDebut + 3, 0);
  return { dateFrom: iso(debut), dateTo: iso(fin) };
}

/** Date locale au format ISO, SANS passer par UTC.
 *
 *  `toISOString()` convertit en UTC : à Abidjan (UTC+0) c'est sans effet, mais
 *  depuis un fuseau négatif le 1er avril devient le 31 mars, et la période
 *  demandée glisse d'un jour sans que personne ne le voie.
 */
function iso(d: Date): string {
  const mois = String(d.getMonth() + 1).padStart(2, "0");
  const jour = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mois}-${jour}`;
}

/** Le libellé de période affiché, aligné sur les bornes réellement envoyées. */
export function libellePeriode(year: number, quarter: number): string {
  return `T${quarter} ${year}`;
}

/** Vrai si le trimestre choisi est celui en cours (ou dans le futur).
 *
 *  Utile pour dire à l'écran que la période s'arrête aujourd'hui : le trimestre
 *  courant n'est pas terminé, et le serveur ramène sa borne haute à aujourd'hui.
 */
export function trimestreEnCoursOuFutur(year: number, quarter: number): boolean {
  const maintenant = new Date();
  const trimestreCourant = Math.floor(maintenant.getMonth() / 3) + 1;
  return year > maintenant.getFullYear()
    || (year === maintenant.getFullYear() && quarter >= trimestreCourant);
}
