import * as React from "react";
import { motion } from "framer-motion";

import { useHrScore } from "@/api/governance";
import { glass } from "@/components/chrome/theme";
import { Gauge } from "@/components/overview/Gauge";
import { EASE_OUT } from "@/lib/motion";
import { parametresFiltres, useFilters } from "@/store/filters";
import type { HrScoreResponse } from "@/types/governance";

/** Human Capital Score, calculé sur données RÉELLES (`governance/score_rh.py`).
 *
 *  CE QUI A ÉTÉ RETIRÉ, ET POURQUOI.
 *    - « Données EDW — réel » : le score lisait `mart.hr_score`, qu'un jeu de
 *      démonstration seul alimentait.
 *    - Les cartes KRE / KSH / MYK écrites en dur, et le drill-down filiale →
 *      département → équipe → collaborateur dont les libellés (« Direction
 *      Opérations », « Équipe A », « Collaborateur ··· 01 ») étaient inventés.
 *      La présence Shield n'est pas ventilée par filiale : le dire vaut mieux.
 *    - Le repli à neuf dimensions affiché PENDANT le chargement, qui se lisait
 *      comme un résultat.
 *  Le global n'est publié que si les dimensions mesurées couvrent assez du poids
 *  total ; sinon la jauge reste sans aiguille et la raison est écrite dessous. */

const DIM_COLORS: Record<string, string> = {
  effectifs_stabilite: "#416FF4",
  presence_ponctualite: "#2D74E0",
  productivite: "#FF8735",
  recrutement: "#7A5AF8",
  performance: "#42BFA0",
  formation_competences: "#E08A1E",
  engagement_climat: "#8A63D2",
  sante_securite: "#D92B55",
  conformite: "#5B6470",
};
const MONTH_LABELS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jui", "Aoû", "Sep", "Oct", "Nov", "Déc"];
const NOMBRE = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

const fmtScore = (n: number | null | undefined): string => (n == null ? "N/D" : NOMBRE.format(n));
// Largeur de barre : 0 % si N/D (jamais de remplissage fictif — ADR-0007), bornée 0..100.
const barWidth = (n: number | null | undefined): string => (n == null ? "0%" : `${Math.max(0, Math.min(100, n))}%`);

function Dimension({ d, index }: { d: HrScoreResponse["dimensions"][number]; index: number }) {
  const ecart = d.score != null && d.precedent != null ? +(d.score - d.precedent).toFixed(1) : null;
  return (
    <motion.div
      className="grid gap-0.5"
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.1 + index * 0.04, duration: 0.4, ease: EASE_OUT }}
    >
      {/* Deux lignes plutôt qu'une : sur la colonne de l'accueil, un libellé
          de largeur fixe ne laissait plus de place à la barre. */}
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 truncate text-[13px] font-semibold text-[#3C4142]" title={d.label}>{d.label}</span>
        <span className="flex shrink-0 items-baseline gap-2">
          <span className="text-[11px] font-bold text-[#9AA09D]">{d.weight} %</span>
          <span className={`text-[13px] font-extrabold ${d.score == null ? "text-[#A0A6A3]" : "text-[#16191A]"}`}>{fmtScore(d.score)}</span>
        </span>
      </div>
      <span className="relative mt-1 block h-2 overflow-hidden rounded-full bg-[#ECEEF0]">
        <motion.span
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ background: DIM_COLORS[d.key] ?? "#416FF4", opacity: d.score == null ? 0 : 0.92 }}
          initial={{ width: 0 }}
          animate={{ width: barWidth(d.score) }}
          transition={{ duration: 0.9, ease: EASE_OUT }}
        />
      </span>
      {/* Le détail du calcul pour une dimension scorée ; le motif sinon. */}
      <p className="mt-0.5 text-[10.5px] font-medium leading-snug text-[#8C9391]" title={d.formule ?? undefined}>
        {d.score != null && d.entrees
          ? `Présence ${fmtScore(d.entrees.taux_presence)} % · ponctualité ${fmtScore(d.entrees.taux_ponctualite)} % · ${d.entrees.jours_mesures}/${d.entrees.jours} j mesurés`
            + (ecart != null ? ` · ${ecart > 0 ? "+" : ecart < 0 ? "−" : ""}${NOMBRE.format(Math.abs(ecart))} pt vs période préc.` : "")
          : d.motif ?? "Non mesurée."}
      </p>
    </motion.div>
  );
}

export function HumanCapitalScore() {
  const filtres = useFilters();
  const { data, isLoading } = useHrScore(parametresFiltres(filtres).toString());

  const global = data?.global ?? null;
  const dimensions = data?.dimensions ?? [];
  const trend = data?.trend ?? [];
  const mesures = trend.filter((t) => t.score != null);
  const couverture = data?.couverture;

  return (
    <motion.section
      className="rounded-[30px] p-7"
      style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.82),rgba(243,248,249,0.55))" }}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE_OUT }}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#8A9291]">Score de gouvernance RH</p>
          <h3 className="mt-1 text-[22px] font-semibold text-[#151818]">Human Capital Score</h3>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full bg-[#EEF1FB] px-3 py-1.5 text-[11px] font-bold text-[#185FA5]">
          <span className={`h-1.5 w-1.5 rounded-full ${data?.source_state === "connected" ? "bg-[#42BFA0]" : "bg-[#A0A6A3]"}`} />
          {isLoading ? "Calcul…" : `Kaydan Shield + Odoo · ${data?.period?.label ?? ""}`}
        </span>
      </div>

      <div className="mt-5 grid gap-7 2xl:grid-cols-[260px_minmax(0,1fr)]">
        <div className="flex flex-col items-center justify-center rounded-[24px] bg-white/55 p-5">
          <div className="relative h-[120px] w-[210px]">
            {/* La jauge s'anime vers la VRAIE valeur ; sans valeur, pas d'aiguille. */}
            <Gauge value={global} color="#416FF4" />
            <div className="absolute inset-x-0 bottom-1 text-center">
              <div className="text-[34px] font-extrabold leading-none text-[#16191A]">
                {fmtScore(global)}<span className="text-[16px] font-bold text-[#9AA09D]"> /100</span>
              </div>
            </div>
          </div>
          {couverture ? (
            <p className="mt-3 text-center text-[11.5px] font-semibold text-[#586061]">
              {couverture.dimensions_scorees}/{couverture.dimensions} dimensions mesurées · {couverture.poids_couvert} % du poids
            </p>
          ) : null}
          {global == null && data?.motif_global ? (
            <p className="mt-1.5 text-center text-[11px] font-medium leading-snug text-[#8C6D1F]">{data.motif_global}</p>
          ) : null}
        </div>

        <div className="grid content-start gap-3 sm:grid-cols-2">
          {isLoading ? (
            <p className="text-[12.5px] font-medium text-[#8C9391]">Calcul des dimensions…</p>
          ) : dimensions.map((d, i) => <Dimension key={d.key} d={d} index={i} />)}
        </div>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="rounded-[20px] bg-white/55 p-4">
          <div className="mb-3 text-[12px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">
            Présence &amp; ponctualité · 12 mois
          </div>
          <div className="flex h-16 items-end gap-1.5">
            {trend.slice(-12).map((t) => {
              const h = t.score == null ? 18 : Math.max(6, Math.min(100, t.score));
              return (
                <span key={t.month} title={`${t.month.slice(0, 7)} · ${fmtScore(t.score)}`} className="flex-1 rounded-t"
                      style={{ height: `${h}%`, background: t.score == null ? "#DDE2E0" : "#2D74E0", opacity: t.score == null ? 1 : 0.85 }} />
              );
            })}
          </div>
          <div className="mt-1 flex justify-between text-[10px] font-semibold text-[#A0A6A3]">
            {trend.length ? (
              <>
                <span>{MONTH_LABELS[new Date(trend.slice(-12)[0].month).getMonth()] ?? ""}</span>
                <span>{mesures.length ? `${mesures.length} mois mesuré(s)` : "aucun mois mesuré"}</span>
                <span>{MONTH_LABELS[new Date(trend[trend.length - 1].month).getMonth()] ?? ""}</span>
              </>
            ) : null}
          </div>
        </div>
        <div className="rounded-[20px] bg-white/55 p-4">
          <div className="mb-2 text-[12px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">Par filiale</div>
          <p className="text-[12px] font-medium leading-relaxed text-[#697071]">
            {data?.by_subsidiary_motif ?? "Non rattaché : la présence Shield n'est pas ventilée par filiale."}
          </p>
        </div>
      </div>
    </motion.section>
  );
}
