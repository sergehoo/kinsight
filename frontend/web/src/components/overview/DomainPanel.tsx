/** Colonne cockpit d'un domaine : KPI, sources, classement, aide à la décision.
 *
 *  Un SEUL composant sert les 7 domaines. Il superpose les métriques réellement
 *  obtenues sur les métriques DÉCLARÉES du registre : un KPI attendu mais non
 *  alimenté reste donc visible en « non connecté » au lieu de disparaître. C'est
 *  volontaire — l'écart entre le cockpit cible et ce qui est branché doit se voir.
 */
import * as React from "react";

import { MetricCard, StateBadge, type DataState } from "@/components/ui/kit";
import { NoInsights, RankingCard, SourceHealth, type SourceHealthItem } from "@/components/ui/insight";
import { mergeMetrics, sourcesFor } from "@/config/domainMetrics";
import { effectiveStatus, type KMetric } from "@/lib/kmetric";
import { useOnlineStatus } from "@/pwa/useNetwork";
import { useShieldHrKpis } from "@/lib/shieldHr";
import { useHrKpi } from "@/api/governance";
import { shieldKpisToMetrics } from "@/lib/adapters/shield";
import { hrMartMetrics, payrollBreakdown } from "@/lib/adapters/governance";
import { useFilters } from "@/store/filters";

/** Nombre de KPI mis en avant dans la colonne ; le reste est replié. */
const VISIBLE = 6;

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-1">{children}</div>;
}

/** Métriques vivantes d'un domaine. Seul Capital Humain dispose aujourd'hui de
 *  sources réellement branchées (Shield + mart RH) ; les autres domaines n'ont
 *  aucun mart alimenté et restent donc sur leurs métriques déclarées. */
function useDomainMetrics(domainId: string): {
  metrics: KMetric[];
  breakdown: ReturnType<typeof payrollBreakdown>;
  breakdownState: DataState;
  loading: boolean;
  shieldState: DataState;
  martState: DataState;
} {
  const isHr = domainId === "capital-humain";
  const { year, quarter } = useFilters();
  const shield = useShieldHrKpis();
  const hrKpi = useHrKpi(year, quarter);

  const live = React.useMemo(() => {
    if (!isHr) return [];
    return [...shieldKpisToMetrics(shield.data), ...hrMartMetrics(hrKpi.data, `T${quarter} ${year}`)];
  }, [isHr, shield.data, hrKpi.data, quarter, year]);

  const breakdown = React.useMemo(() => (isHr ? payrollBreakdown(hrKpi.data) : []), [isHr, hrKpi.data]);

  const shieldState: DataState = shield.isLoading
    ? "connecting"
    : shield.isError || !shield.data
      ? "error"
      : shield.data.stale
        ? "stale"
        : shield.data.payload.status;

  // Le mart peut répondre 200 tout en signalant qu'il n'a rien à publier
  // (`available: false`) ou qu'il est injoignable (`source_state: "error"`).
  // Se fier au seul succès HTTP afficherait « connecté » sur une source en panne.
  const martState: DataState = !isHr
    ? "disconnected"
    : hrKpi.isLoading
      ? "connecting"
      : hrKpi.isError || !hrKpi.data
        ? "error"
        : hrKpi.data.source_state === "error"
          ? "error"
          : hrKpi.data.available === false
            ? "disconnected"
            : "connected";

  return {
    metrics: mergeMetrics(domainId, live),
    breakdown,
    breakdownState: breakdown.length ? "connected" : martState === "connecting" ? "connecting" : "disconnected",
    loading: isHr && (shield.isLoading || hrKpi.isLoading),
    shieldState,
    martState,
  };
}

export function DomainPanel({ domainId }: { domainId: string }) {
  const online = useOnlineStatus();
  const [expanded, setExpanded] = React.useState(false);
  const { metrics, breakdown, breakdownState, shieldState, martState } = useDomainMetrics(domainId);

  const shown = expanded ? metrics : metrics.slice(0, VISIBLE);
  const hidden = metrics.length - shown.length;
  const connectedCount = metrics.filter((m) => m.status === "connected" || m.status === "stale").length;

  // L'état de chaque source déclarée par le domaine, avec l'état réel quand on l'a.
  const sources: SourceHealthItem[] = sourcesFor(domainId).map((source) => {
    if (source.code === "kaydan_shield") {
      return { code: source.code, label: source.label, state: shieldState, detail: "Effectifs, présence, sites" };
    }
    if (source.code === "edw") {
      return {
        code: source.code,
        label: source.label,
        state: martState,
        detail: domainId === "capital-humain" ? "Masse salariale, mouvements" : "Aucun mart alimenté pour ce domaine",
      };
    }
    return { code: source.code, label: source.label, state: "disconnected", detail: "Connecteur non branché" };
  });

  return (
    <div className="flex flex-col gap-4">
      {/* Bandeau de couverture : combien de KPI du cockpit cible sont alimentés. */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-[16px] bg-white/55 px-3 py-2">
        <span className="truncate text-[11.5px] font-bold text-[#4A4F50]">
          {connectedCount}/{metrics.length} indicateurs alimentés
        </span>
        <StateBadge
          state={connectedCount === 0 ? "disconnected" : connectedCount === metrics.length ? "connected" : "partial"}
        />
      </div>

      <Grid>
        {shown.map((metric, index) => (
          <MetricCard
            key={metric.id}
            title={metric.title}
            value={metric.value}
            unit={metric.unit}
            state={effectiveStatus(metric, { online })}
            source={metric.sourceLabel}
            updatedAt={metric.updatedAt}
            scope={metric.period}
            highlighted={index === 0}
            href={metric.drilldownUrl}
          />
        ))}
      </Grid>

      {hidden > 0 || expanded ? (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="ki-accent-ring self-start rounded-full bg-white/60 px-3.5 py-2 text-[11.5px] font-bold text-[#3C4142] transition-colors hover:bg-white/85"
        >
          {expanded ? "Réduire" : `Voir les ${hidden} autres indicateurs`}
        </button>
      ) : null}

      {/* Ventilation réelle : masse salariale par filiale (seule servie à ce jour). */}
      {breakdown.length ? (
        <RankingCard
          title="Masse salariale par filiale"
          items={breakdown}
          unit="XOF"
          state={breakdownState}
          source="Mart EDW"
        />
      ) : null}

      <SourceHealth sources={sources} />

      <NoInsights
        reason={
          connectedCount === 0
            ? "Aucune source de ce domaine n'est raccordée : il n'y a pas encore de constat à formuler."
            : "Les sources branchées ne fournissent pas encore d'historique comparable (objectif, budget ou N-1)."
        }
      />
    </div>
  );
}
