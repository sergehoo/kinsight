import { create } from "zustand";

/** Nature de la période. Les mêmes valeurs que le backend (`governance/filtres.py`). */
export type ModePeriode = "trimestre" | "annee" | "7j" | "30j" | "90j" | "personnalisee";
export type TypePersonnel = "" | "employee" | "worker";

/** Filtres globaux du cockpit. Une seule source pour tous les écrans : KPI,
 *  courbes, tableaux, alertes, IA et exports lisent CE store, et le convertissent
 *  en paramètres serveur par UNE seule fonction (`parametresFiltres`). */
interface FiltersState {
  periode: ModePeriode;
  year: number;
  quarter: number;
  dateFrom: string;
  dateTo: string;
  subsidiary: string; // "all" | code filiale (KRE, KSH, MYK…)
  site: string;       // "" | code de site Shield
  personnel: TypePersonnel;
  departement: string; // "" | libellé de département Odoo
  setPeriode: (periode: ModePeriode) => void;
  setYear: (year: number) => void;
  setQuarter: (quarter: number) => void;
  setDates: (dateFrom: string, dateTo: string) => void;
  setSubsidiary: (subsidiary: string) => void;
  setSite: (site: string) => void;
  setPersonnel: (personnel: TypePersonnel) => void;
  setDepartement: (departement: string) => void;
  reinitialiserDimensions: () => void;
}

/** Valeur du filiale signifiant « pas de restriction supplémentaire ».
 *
 *  Elle ne veut pas dire « toutes les filiales du Groupe » : le périmètre serveur
 *  borne de toute façon la réponse. Pour un directeur de filiale, « toutes »
 *  signifie donc « tout mon périmètre », qui est sa seule filiale.
 */
export const TOUTES_FILIALES = "all";

/** Le trimestre EN COURS. Le défaut figé à « T1 2026 » présentait le premier
 *  trimestre comme courant en plein quatrième — sur tous les écrans à la fois. */
export function trimestreCourant(d: Date = new Date()): { year: number; quarter: number } {
  return { year: d.getFullYear(), quarter: Math.floor(d.getMonth() / 3) + 1 };
}

/** Années proposées : de la première année de données K-Insight à l'année en
 *  cours. Écrites en dur, elles s'arrêtaient à 2026 pour toujours. */
export const PREMIERE_ANNEE = 2024;
export function anneesDisponibles(d: Date = new Date()): number[] {
  const annees: number[] = [];
  for (let a = PREMIERE_ANNEE; a <= d.getFullYear(); a += 1) annees.push(a);
  return annees;
}

const courant = trimestreCourant();

// L'état INITIAL vient déjà de l'adresse. Lue dans un effet, elle arrivait APRÈS
// les premières requêtes des écrans : chacun chargeait le trimestre par défaut,
// puis recommençait avec la période du lien — double charge et période fausse à
// l'écran pendant un instant.
const depuisUrl: Partial<FiltresLus> = typeof window !== "undefined" ? filtresDeLUrl(window.location.search) : {};

export const useFilters = create<FiltersState>((set) => ({
  periode: "trimestre",
  year: courant.year,
  quarter: courant.quarter,
  dateFrom: "",
  dateTo: "",
  subsidiary: TOUTES_FILIALES,
  site: "",
  personnel: "",
  departement: "",
  ...depuisUrl,
  setPeriode: (periode) => set({ periode }),
  setYear: (year) => set({ year }),
  setQuarter: (quarter) => set({ quarter, periode: "trimestre" }),
  setDates: (dateFrom, dateTo) => set({ dateFrom, dateTo, periode: "personnalisee" }),
  setSubsidiary: (subsidiary) => set({ subsidiary }),
  // Site et type ne se croisent pas dans l'historique : choisir l'un efface l'autre,
  // plutôt que de laisser l'écran afficher un croisement que le serveur refusera.
  setSite: (site) => set({ site, personnel: "" }),
  setPersonnel: (personnel) => set({ personnel, site: "" }),
  setDepartement: (departement) => set({ departement }),
  reinitialiserDimensions: () => set({ site: "", personnel: "", departement: "" }),
}));

type FiltresLus = Pick<FiltersState, "periode" | "year" | "quarter" | "dateFrom" | "dateTo" | "subsidiary"
  | "site" | "personnel" | "departement">;

/** LES paramètres serveur des filtres — une seule conversion pour tous les appels.
 *
 *  Le backend calcule lui-même les bornes de la période (`filtres.py`) : le front
 *  n'envoie que la NATURE et ses paramètres. C'est ce qui supprime l'écart de
 *  convention (borne de fin incluse ici, exclue là-bas) que l'inventaire a relevé. */
export function parametresFiltres(f: FiltresLus): URLSearchParams {
  const q = new URLSearchParams({ periode: f.periode });
  if (f.periode === "trimestre" || f.periode === "annee") q.set("year", String(f.year));
  if (f.periode === "trimestre") q.set("quarter", String(f.quarter));
  if (f.periode === "personnalisee" && f.dateFrom && f.dateTo) {
    q.set("date_from", f.dateFrom);
    q.set("date_to", f.dateTo);
  }
  if (f.subsidiary && f.subsidiary !== TOUTES_FILIALES) q.set("subsidiary", f.subsidiary);
  if (f.site) q.set("site", f.site);
  if (f.personnel) q.set("type", f.personnel);
  if (f.departement) q.set("departement", f.departement);
  return q;
}

/** La veille, en date LOCALE (sans passer par UTC) : borne haute de toute période. */
export function hierIso(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return iso(d);
}

/** Libellé de la période sélectionnée, tel que l'écran l'affiche. */
export function libelleFiltrePeriode(f: Pick<FiltersState, "periode" | "year" | "quarter" | "dateFrom" | "dateTo">): string {
  switch (f.periode) {
    case "7j": return "7 derniers jours";
    case "30j": return "30 derniers jours";
    case "90j": return "90 derniers jours";
    case "annee": return `Année ${f.year}`;
    case "personnalisee":
      return f.dateFrom && f.dateTo ? `${frDate(f.dateFrom)} → ${frDate(f.dateTo)}` : "Période personnalisée";
    default: return `T${f.quarter} ${f.year}`;
  }
}

function frDate(isoDate: string): string {
  const [a, m, j] = isoDate.split("-");
  return `${j}/${m}/${a}`;
}

/* ── Synchronisation avec l'URL ────────────────────────────────────────────────
 *
 * Les filtres vivent AUSSI dans l'adresse : un lien partagé, un rechargement ou
 * un export rouvrent exactement la vue filtrée. Lecture une fois au démarrage,
 * écriture à chaque changement par `replaceState` (pas d'entrée d'historique à
 * chaque clic). Seuls nos paramètres sont touchés. */
const CLES_URL: Record<string, keyof FiltresLus> = {
  periode: "periode", year: "year", quarter: "quarter", date_from: "dateFrom", date_to: "dateTo",
  subsidiary: "subsidiary", site: "site", type: "personnel", departement: "departement",
};

/** Les filtres portés par l'adresse, validés. Pure : ne modifie rien. */
function filtresDeLUrl(search: string): Partial<FiltresLus> {
  const q = new URLSearchParams(search);
  const lu: Partial<FiltresLus> = {};
  const modes: ModePeriode[] = ["trimestre", "annee", "7j", "30j", "90j", "personnalisee"];
  const periode = q.get("periode") as ModePeriode | null;
  if (periode && modes.includes(periode)) lu.periode = periode;
  const annee = Number(q.get("year"));
  if (Number.isInteger(annee) && annee >= PREMIERE_ANNEE && annee <= new Date().getFullYear()) lu.year = annee;
  const t = Number(q.get("quarter"));
  if (Number.isInteger(t) && t >= 1 && t <= 4) lu.quarter = t;
  const dateIso = /^\d{4}-\d{2}-\d{2}$/;
  if (dateIso.test(q.get("date_from") ?? "") && dateIso.test(q.get("date_to") ?? "")) {
    lu.dateFrom = q.get("date_from") as string;
    lu.dateTo = q.get("date_to") as string;
  }
  if (q.get("subsidiary")) lu.subsidiary = q.get("subsidiary") as string;
  if (q.get("site")) lu.site = q.get("site") as string;
  const type = q.get("type");
  if (type === "employee" || type === "worker") lu.personnel = type;
  if (q.get("departement")) lu.departement = q.get("departement") as string;
  if (lu.site && lu.personnel) delete lu.personnel; // le serveur refuserait le croisement
  return lu;
}

export function lireFiltresDepuisUrl(search: string = window.location.search): void {
  const lu = filtresDeLUrl(search);
  if (Object.keys(lu).length) useFilters.setState(lu);
}

export function ecrireFiltresDansUrl(f: FiltresLus): void {
  const url = new URL(window.location.href);
  for (const cle of Object.keys(CLES_URL)) url.searchParams.delete(cle);
  parametresFiltres(f).forEach((valeur, cle) => url.searchParams.set(cle, valeur));
  const suivante = `${url.pathname}${url.search}${url.hash}`;
  if (suivante !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
    window.history.replaceState(window.history.state, "", suivante);
  }
}

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
