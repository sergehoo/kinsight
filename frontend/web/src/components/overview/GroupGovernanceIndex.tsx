import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { useGroupScore } from "@/api/governance";
import { glass } from "@/components/chrome/theme";
import { Gauge } from "@/components/overview/Gauge";
import { ArrowUpRight } from "@/components/overview/icons";
import { EASE_OUT } from "@/lib/motion";
import { useFilters } from "@/store/filters";
import type { GroupScoreResponse } from "@/types/governance";

// Lien vers la page d'accueil de chaque domaine consolidé.
const DOMAIN_HREF: Record<string, string> = {
  immobilier: "/dashboard/immobilier",
  finance: "/dashboard/finance",
  "commercial-clients": "/dashboard/commercial-clients",
  "capital-humain": "/dashboard/capital-humain",
  operations: "/dashboard/operations",
  "risques-conformite": "/dashboard/risques-conformite",
};
const DOMAIN_COLOR: Record<string, string> = {
  immobilier: "#FF8735",
  finance: "#42BFA0",
  "commercial-clients": "#416FF4",
  "capital-humain": "#7A5AF8",
  operations: "#37A0DD",
  "risques-conformite": "#D92B55",
};
const fmt = (n: number | null | undefined): string => (n == null ? "N/D" : n.toFixed(1));
// Largeur de barre : 0 % si N/D (jamais de remplissage fictif — ADR-0007), bornée 0..100.
const barWidth = (n: number | null): string => (n == null ? "0%" : `${Math.max(0, Math.min(100, n))}%`);

function trendInfo(trend: GroupScoreResponse["trend"]) {
  const pts = trend.filter((t) => t.score != null).map((t) => t.score as number);
  if (pts.length < 2) return { arrow: "→", label: null as string | null };
  const delta = +(pts[pts.length - 1] - pts[pts.length - 2]).toFixed(1);
  return { arrow: delta > 0.05 ? "↑" : delta < -0.05 ? "↓" : "→", label: `${delta > 0 ? "+" : ""}${delta} pts` };
}

/** Indice de Gouvernance Groupe consolidé — carte d'accueil du domaine Overview. */
export function GroupGovernanceIndex({ accent = "#416FF4" }: { accent?: string }) {
  const { year, quarter, subsidiary } = useFilters();
  const { data, isLoading } = useGroupScore(year, quarter, subsidiary);

  const available = Boolean(data?.available);
  const score = data?.global ?? null;
  const domains = data?.domains ?? [];
  const bySub = data?.by_subsidiary ?? [];
  const { arrow, label } = trendInfo(data?.trend ?? []);

  return (
    <motion.section
      className="rounded-[32px] px-6 pb-6 pt-5"
      style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.86),rgba(243,248,249,0.55))" }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.55, ease: EASE_OUT }}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#8A9291]">Gouvernance consolidée</p>
          <h2 className="mt-1 text-[18px] font-semibold text-[#151818]">Indice de Gouvernance Groupe</h2>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full bg-[#EEF1FB] px-3 py-1.5 text-[11px] font-bold text-[#185FA5]">
          <span className={`h-1.5 w-1.5 rounded-full ${available ? "bg-[#42BFA0]" : "bg-[#416FF4]"}`} />
          {isLoading ? "Chargement…" : available ? "Données EDW — réel" : "Données EDW — gouverné"}
        </span>
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        {/* Jauge consolidée */}
        <div className="flex flex-col items-center justify-center rounded-[22px] bg-white/55 p-4">
          <div className="relative h-[108px] w-[190px]">
            <Gauge value={score} color={accent} />
            <div className="absolute inset-x-0 bottom-1 text-center">
              <div className="text-[30px] font-extrabold leading-none text-[#16191A]">{fmt(score)}<span className="text-[14px] font-bold text-[#9AA09D]"> /100</span></div>
            </div>
          </div>
          <div className="mt-1 flex items-center gap-2 text-[12px] font-semibold text-[#8A9291]">
            <span className="grid h-5 w-5 place-items-center rounded-full bg-[#EEF0F0]">{arrow}</span>
            {available && label ? `Tendance ${arrow} ${label}` : "Tendance · à connecter"}
          </div>
        </div>

        {/* Contribution par domaine (cliquable) */}
        <div className="grid content-start gap-2">
          {domains.map((d) => (
            <Link
              key={d.domain}
              to={DOMAIN_HREF[d.domain] ?? "#"}
              className="group flex items-center gap-3 rounded-xl px-2 py-1 transition-colors hover:bg-white/60"
              title={`Ouvrir ${d.label}`}
            >
              <span className="w-[180px] shrink-0 truncate text-[12.5px] font-semibold text-[#3C4142]">{d.label}</span>
              <span className="w-9 shrink-0 text-right text-[11px] font-bold text-[#9AA09D]">{d.weight}%</span>
              <span className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-[#ECEEF0]">
                <span
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{ background: DOMAIN_COLOR[d.domain] ?? accent, width: barWidth(d.score), opacity: d.score == null ? 0 : 0.9 }}
                />
              </span>
              <span className={`w-11 shrink-0 text-right text-[12px] font-bold ${d.score == null ? "text-[#A0A6A3]" : "text-[#16191A]"}`}>{fmt(d.score)}</span>
              <ArrowUpRight width={13} height={13} className="shrink-0 text-[#C7CCC9] transition-colors group-hover:text-[#416FF4]" />
            </Link>
          ))}
        </div>
      </div>

      {/* Par filiale — indice renormalisé sur les domaines disponibles de chaque filiale (gouverné). */}
      <div className="mt-5 mb-1.5 text-[11px] font-semibold text-[#9AA09D]">
        Par filiale — indice renormalisé sur les domaines disponibles de chaque filiale
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {(bySub.length ? bySub : [{ code: "KRE", score: null }, { code: "KSH", score: null }, { code: "MYK", score: null }]).map((s) => (
          <div key={s.code} className="rounded-xl bg-white/65 px-4 py-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-[#8A9291]">{s.code}</span>
              <span className={`text-[15px] font-extrabold ${s.score == null ? "text-[#A0A6A3]" : "text-[#16191A]"}`}>{fmt(s.score)}</span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[#ECEEF0]">
              <span className="block h-full rounded-full" style={{ background: accent, width: barWidth(s.score), opacity: s.score == null ? 0 : 0.9 }} />
            </div>
          </div>
        ))}
      </div>
    </motion.section>
  );
}
