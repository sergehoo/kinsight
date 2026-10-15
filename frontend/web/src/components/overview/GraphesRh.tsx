/** Graphiques réels d'un module Capital Humain, et ce que rien ne trace.
 *
 *  Chaque graphe lit l'historique K-Insight (`/governance/hr/history/`) sous les
 *  filtres du cockpit — période, site, type, département, filiale — et le
 *  périmètre serveur. Le serveur décide de ce qui est servi ; quand il ne sert
 *  pas, il dit pourquoi (`reason`, `matrice_motif`, `ventilation_motif`) et ce
 *  motif est affiché tel quel. Aucun graphe ne se trace sans point réel, aucune
 *  case vide n'est mise à zéro (ADR-0007).
 */
import * as React from "react";
import { motion } from "framer-motion";
import type { UseQueryResult } from "@tanstack/react-query";

import { useHrHistory, type HrHistory } from "@/api/governance";
import {
  BreakdownChart,
  DonutChart,
  HeatmapChart,
  StackedBarChart,
  TrendChart,
  type Palier,
} from "@/components/charts";
import { glass } from "@/components/chrome/theme";
import type { DataState } from "@/components/ui/kit";
import { GRAPHES_RH, sectionsSansSource, type GrapheRh } from "@/config/graphesRh";
import type { KBreakdownItem, KSeriesPoint } from "@/lib/kmetric";
import { EASE_OUT } from "@/lib/motion";
import { parametresFiltres, useFilters } from "@/store/filters";

const LIBELLE_SOURCE: Record<string, string> = { shield: "Kaydan Shield", odoo: "Odoo RH" };

export function jourCourt(iso: string): string {
  const [, m, j] = iso.split("-");
  return `${j}/${m}`;
}

function arrondi(v: number | null | undefined): number | null {
  return v === null || v === undefined ? null : Math.round(v * 10) / 10;
}

/** Un 403 n'est pas une panne : l'utilisateur n'a pas le droit, et on le dit. */
function estRefus(erreur: unknown): boolean {
  return erreur instanceof Error && /Erreur API 403/.test(erreur.message);
}

export function etatHistorique(q: UseQueryResult<HrHistory>, aDesDonnees: boolean): DataState {
  if (q.isLoading) return "connecting";
  if (q.isError) return estRefus(q.error) ? "disconnected" : "error";
  return aDesDonnees ? "connected" : "disconnected";
}

/** Le motif d'un graphe vide, du plus précis au plus général. */
export function motifHistorique(q: UseQueryResult<HrHistory>, propre?: string | null): string {
  if (q.isError) {
    return estRefus(q.error) ? "Accès non autorisé pour votre rôle." : "Historique momentanément indisponible.";
  }
  const d = q.data;
  if (!d) return "Chargement de l'historique…";
  if (d.reason) return d.reason;
  if (propre) return propre;
  return d.historique_depuis
    ? `Aucune journée mesurée sur la période ; l'historique commence le ${jourCourt(d.historique_depuis)}.`
    : "Historique en cours de constitution : aucune journée encore collectée.";
}

/** Paliers de décision tirés des seuils PUBLIÉS par le backend avec la mesure. */
export function paliersPresence(seuils?: HrHistory["seuils"]): Palier[] | undefined {
  if (!seuils) return undefined;
  const { presence_critique: c, presence_surveillance: s } = seuils;
  return [
    { max: c, label: `Critique < ${c} %`, color: "#E9798F" },
    { min: c, max: s, label: `Surveillance ${c}–${s} %`, color: "#F2C46D" },
    { min: s, label: `Normal ≥ ${s} %`, color: "#5FC3A1" },
  ];
}

/* ── Un graphe par type ──────────────────────────────────────────────────── */

function Courbe({ g, parametres }: { g: Extract<GrapheRh, { type: "courbe" }>; parametres: string }) {
  const q = useHrHistory(g.metric, parametres, "compare=aucune");
  const points: KSeriesPoint[] = (q.data?.points ?? []).map((p) => ({ label: jourCourt(p.date), value: arrondi(p.value) }));
  const reels = points.some((p) => p.value !== null);
  return (
    <TrendChart series={points} label={g.titre} unit={q.data?.format === "pct" ? "%" : undefined}
                state={etatHistorique(q, reels)} source={LIBELLE_SOURCE[q.data?.source ?? ""]}
                emptyMessage={motifHistorique(q)} />
  );
}

function EmpileType({ g, parametres }: { g: Extract<GrapheRh, { type: "empile-type" }>; parametres: string }) {
  const q = useHrHistory(g.metric, parametres, "compare=aucune&matrice=type");
  const m = q.data?.matrice;
  const series = (m?.lignes ?? []).map((l, i) => ({
    name: l.libelle || l.code,
    values: (m?.valeurs[i] ?? []).map(arrondi),
  }));
  const reels = series.some((s) => s.values.some((v) => v !== null));
  return (
    <StackedBarChart categories={(m?.jours ?? []).map(jourCourt)} series={series}
                     state={etatHistorique(q, reels)} source={LIBELLE_SOURCE[q.data?.source ?? ""]}
                     emptyMessage={motifHistorique(q, q.data?.matrice_motif
                       ?? (m && !m.lignes.length ? "Aucune ventilation employés / ouvriers historisée sur la période." : null))} />
  );
}

function ChaleurSites({ g, parametres }: { g: Extract<GrapheRh, { type: "chaleur-sites" }>; parametres: string }) {
  const q = useHrHistory(g.metric, parametres, "compare=aucune&matrice=site");
  const m = q.data?.matrice;
  const valeurs = (m?.valeurs ?? []).map((ligne) => ligne.map(arrondi));
  const reels = valeurs.some((l) => l.some((v) => v !== null));
  return (
    <HeatmapChart lignes={(m?.lignes ?? []).map((l) => l.libelle || l.code)} colonnes={(m?.jours ?? []).map(jourCourt)}
                  valeurs={valeurs} unit="%" paliers={paliersPresence(q.data?.seuils)}
                  state={etatHistorique(q, reels)} source={LIBELLE_SOURCE[q.data?.source ?? ""]}
                  emptyMessage={motifHistorique(q, q.data?.matrice_motif
                    ?? (m && !m.lignes.length ? "Aucun site mesuré sur la période." : null))} />
  );
}

function ventilee(q: UseQueryResult<HrHistory>): KBreakdownItem[] {
  return (q.data?.ventilation ?? []).map((l) => ({ key: l.code, label: l.libelle || l.code, value: arrondi(l.value) }));
}

const NOM_VENTILATION: Record<string, string> = { site: "site", type: "type de personnel", departement: "département" };

/** Ventilation servie mais vide : la métrique existe, la maille n'a rien mesuré. */
function motifVentilation(q: UseQueryResult<HrHistory>, dimension: string): string {
  const vide = Array.isArray(q.data?.ventilation) && !q.data?.ventilation?.length;
  return motifHistorique(q, q.data?.ventilation_motif
    ?? (vide ? `Aucun ${NOM_VENTILATION[dimension] ?? dimension} mesuré sur la période.` : null));
}

function Barres({ g, parametres }: { g: Extract<GrapheRh, { type: "barres" }>; parametres: string }) {
  const q = useHrHistory(g.metric, parametres, `compare=aucune&ventilation=${g.ventilation}`);
  const items = ventilee(q);
  return (
    <BreakdownChart items={items} unit={q.data?.format === "pct" ? "%" : undefined}
                    state={etatHistorique(q, items.some((i) => i.value !== null))}
                    source={LIBELLE_SOURCE[q.data?.source ?? ""]}
                    emptyMessage={motifVentilation(q, g.ventilation)} />
  );
}

function Donut({ g, parametres }: { g: Extract<GrapheRh, { type: "donut" }>; parametres: string }) {
  const q = useHrHistory(g.metric, parametres, `compare=aucune&ventilation=${g.ventilation}`);
  const items = ventilee(q);
  return (
    <DonutChart items={items} state={etatHistorique(q, items.some((i) => i.value !== null))}
                source={LIBELLE_SOURCE[q.data?.source ?? ""]} height={260}
                emptyMessage={motifVentilation(q, g.ventilation)} />
  );
}

/** Structure recomposée de stocks distincts. Une part inconnue rend la structure
 *  INCOMPLÈTE : un donut à une seule part afficherait « 100 % employés ». */
function DonutStocks({ g, parametres }: { g: Extract<GrapheRh, { type: "donut-stocks" }>; parametres: string }) {
  const [a, b] = g.parts;
  const qa = useHrHistory(a.metric, parametres, "compare=aucune");
  const qb = useHrHistory(b.metric, parametres, "compare=aucune");
  const parts = [{ part: a, q: qa }, { part: b, q: qb }];
  const items: KBreakdownItem[] = parts.map(({ part, q }) => ({
    key: part.metric, label: part.libelle, value: arrondi(q.data?.valeur?.value),
  }));
  const manquante = parts.find(({ q }) => q.data?.valeur?.value === null || q.data?.valeur?.value === undefined);
  const complet = !manquante && items.every((i) => i.value !== null);
  const chargement = qa.isLoading || qb.isLoading;
  const enErreur = parts.find(({ q }) => q.isError);
  const motif = enErreur ? motifHistorique(enErreur.q)
    : manquante ? (manquante.q.data?.reason
      ?? `Structure incomplète : ${manquante.part.libelle.toLowerCase()} non mesurés sur la période.`)
      : undefined;
  return (
    <DonutChart items={complet ? items : []} height={260}
                state={chargement ? "connecting" : enErreur ? etatHistorique(enErreur.q, false) : complet ? "connected" : "disconnected"}
                source={LIBELLE_SOURCE[qa.data?.source ?? ""]} emptyMessage={motif} />
  );
}

function Graphe({ g, parametres }: { g: GrapheRh; parametres: string }) {
  switch (g.type) {
    case "courbe": return <Courbe g={g} parametres={parametres} />;
    case "empile-type": return <EmpileType g={g} parametres={parametres} />;
    case "chaleur-sites": return <ChaleurSites g={g} parametres={parametres} />;
    case "barres": return <Barres g={g} parametres={parametres} />;
    case "donut": return <Donut g={g} parametres={parametres} />;
    case "donut-stocks": return <DonutStocks g={g} parametres={parametres} />;
  }
}

/** Un graphe dans sa carte : titre, sous-titre, tracé ou motif. */
export function CarteGraphe({ g, parametres, index = 0, large }: {
  g: GrapheRh;
  parametres: string;
  index?: number;
  /** Sur deux colonnes ; par défaut, la seule carte de chaleur (une case par jour). */
  large?: boolean;
}) {
  return (
    <motion.article
      className={`min-w-0 rounded-[28px] p-5 ${large ?? g.type === "chaleur-sites" ? "xl:col-span-2" : ""}`}
      style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.8),rgba(242,247,247,0.56))" }}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 + index * 0.04, duration: 0.45, ease: EASE_OUT }}
    >
      <h3 className="text-[16px] font-semibold text-[#151818]">{g.titre}</h3>
      <p className="mb-3 mt-0.5 text-[12px] font-semibold text-[#7C8384]">{g.sousTitre}</p>
      <Graphe g={g} parametres={parametres} />
    </motion.article>
  );
}

/* ── Le bloc d'un module ─────────────────────────────────────────────────── */

export function GraphesRh({ moduleKey, sections }: {
  moduleKey: string;
  sections: { title: string; subtitle: string }[];
}) {
  const filtres = useFilters();
  const parametres = parametresFiltres(filtres).toString();
  const graphes = GRAPHES_RH[moduleKey]?.graphes ?? [];
  const sansSource = sectionsSansSource(moduleKey, sections);

  return (
    <div className="space-y-6">
      {graphes.length ? (
        <div className="grid gap-5 xl:grid-cols-2">
          {graphes.map((g, i) => (
            <CarteGraphe key={`${g.type}-${g.titre}`} g={g} parametres={parametres} index={i} />
          ))}
        </div>
      ) : null}

      {sansSource.length ? (
        <section className="rounded-[26px] p-5" style={{ ...glass, background: "rgba(255,255,255,0.5)" }}>
          <h3 className="text-[12px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">
            Analyses sans source — non tracées
          </h3>
          <p className="mt-1 text-[12px] font-medium text-[#8C9391]">
            Aucun graphe n&apos;est dessiné sans série réelle : chaque analyse attendue dit ce qui lui manque.
          </p>
          <ul className="mt-3 grid gap-2.5 md:grid-cols-2">
            {sansSource.map((s) => (
              <li key={s.titre} className="rounded-[18px] bg-white/60 px-4 py-3">
                <div className="text-[13.5px] font-semibold text-[#1B1D1D]">{s.titre}</div>
                <div className="text-[11.5px] font-semibold text-[#9AA09D]">{s.sousTitre}</div>
                <p className="mt-1 text-[11.5px] font-medium leading-snug text-[#8A6E36]">{s.motif}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
