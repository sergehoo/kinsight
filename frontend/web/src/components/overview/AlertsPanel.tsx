import { motion } from "framer-motion";

import { useAlerts } from "@/api/governance";
import { glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";
import { useFilters } from "@/store/filters";
import type { GovernanceAlert } from "@/types/governance";

const SEV = {
  critical: { label: "Critique", color: "#D92B55", bg: "rgba(217,43,85,0.10)" },
  warning: { label: "Vigilance", color: "#E0801E", bg: "rgba(224,128,30,0.10)" },
  info: { label: "Info", color: "#37A0DD", bg: "rgba(55,160,221,0.10)" },
} as const;

function SeverityChip({ severity, n }: { severity: keyof typeof SEV; n: number }) {
  const s = SEV[severity];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-bold" style={{ background: s.bg, color: s.color }}>
      <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
      {n} {s.label}
    </span>
  );
}

function AlertRow({ a }: { a: GovernanceAlert }) {
  const s = SEV[a.severity] ?? SEV.info;
  const sense = a.kind === "trend" ? `chute ${a.value} pts (seuil ≥ ${a.threshold})` : `score ${a.value} (seuil < ${a.threshold})`;
  return (
    <div className="flex items-center gap-3 rounded-xl bg-white/70 px-4 py-3" style={{ borderLeft: `3px solid ${s.color}` }}>
      <span className="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide" style={{ background: s.bg, color: s.color }}>{s.label}</span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-semibold text-[#16191A]">{a.label}</div>
        <div className="truncate text-[11.5px] font-medium text-[#8A9291]">{a.scope} · {sense}</div>
      </div>
      <span className="shrink-0 font-mono text-[10px] text-[#A0A6A3]">{a.source}</span>
    </div>
  );
}

export function AlertsPanel() {
  const { year, quarter, subsidiary } = useFilters();
  const { data, isLoading, isError, error } = useAlerts(year, quarter, subsidiary);
  // Trois situations distinctes, trois messages : un refus de droit, une panne et
  // une absence de données ne se lisent pas de la même façon — les confondre
  // faisait passer un 403 pour « pas encore de données ».
  const refus = isError && error instanceof Error && /Erreur API 403/.test(error.message);

  const counts = data?.counts ?? { critical: 0, warning: 0, info: 0 };
  const alerts = data?.alerts ?? [];

  return (
    <motion.section
      className="rounded-[30px] p-6"
      style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.84),rgba(243,248,249,0.55))" }}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE_OUT }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#8A9291]">Pilotage par exception</p>
          <h3 className="mt-1 text-[20px] font-semibold text-[#151818]">Centre d'alertes</h3>
        </div>
        <div className="flex items-center gap-2">
          <SeverityChip severity="critical" n={counts.critical} />
          <SeverityChip severity="warning" n={counts.warning} />
          <SeverityChip severity="info" n={counts.info} />
        </div>
      </div>

      <div className="mt-4 grid gap-2">
        {isLoading ? (
          <div className="rounded-xl bg-white/60 px-4 py-6 text-center text-[13px] font-semibold text-[#8A9291]">Chargement…</div>
        ) : isError ? (
          <div className="rounded-xl bg-white/60 px-4 py-6 text-center text-[12.5px] font-semibold text-[#8A6E36]">
            {refus
              ? "Accès non autorisé : le centre d'alertes Groupe relève de la vue d'ensemble, que votre rôle ne couvre pas."
              : "Alertes momentanément indisponibles — aucune alerte n'est déduite d'une erreur."}
          </div>
        ) : alerts.length ? (
          alerts.map((a, i) => <AlertRow key={`${a.source}-${i}`} a={a} />)
        ) : data?.available ? (
          <div className="rounded-xl bg-white/60 px-4 py-6 text-center text-[13px] font-semibold text-[#42BFA0]">
            Aucune alerte — tous les indicateurs disponibles sont au-dessus des seuils.
          </div>
        ) : (
          <div className="rounded-xl bg-white/60 px-4 py-6 text-center text-[12px] font-semibold text-[#9AA09D]">
            Aucun score de gouvernance disponible sur la période : aucune alerte n'est évaluée (aucune alerte inventée).
          </div>
        )}
      </div>
      <p className="mt-3 text-[11px] font-medium text-[#A0A6A3]">
        Seuils évalués sur les scores de gouvernance réels · proposition à valider par la direction.
      </p>
    </motion.section>
  );
}
