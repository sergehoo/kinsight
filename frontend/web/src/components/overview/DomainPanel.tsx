/** Colonne cockpit d'un domaine : KPI, sources, classement, aide à la décision.
 *
 *  Un SEUL composant sert les 7 domaines. Il superpose les métriques réellement
 *  obtenues sur les métriques DÉCLARÉES du registre : un KPI attendu mais non
 *  alimenté reste donc visible en « non connecté » au lieu de disparaître. C'est
 *  volontaire — l'écart entre le cockpit cible et ce qui est branché doit se voir.
 */
import * as React from "react";

import { MetricCard, StateBadge, type DataState } from "@/components/ui/kit";
import {
  DecisionInsightCard,
  NoInsights,
  RankingCard,
  SourceHealth,
  type SourceHealthItem,
} from "@/components/ui/insight";
import { BreakdownChart, TrendChart } from "@/components/charts";
import { glass } from "@/components/chrome/theme";
import { mergeMetrics, sourcesFor } from "@/config/domainMetrics";
import { effectiveStatus, type KMetric } from "@/lib/kmetric";
import { useOnlineStatus } from "@/pwa/useNetwork";
import {
  SERIES_WINDOWS,
  useShieldAttendanceSeries,
  useShieldHrKpis,
  useShieldOverview,
  useShieldSecurity,
  type SeriesWindow,
} from "@/lib/shieldHr";
import { useHrKpi } from "@/api/governance";
import {
  shieldAttendanceRateBreakdown,
  shieldBreakdownStatus,
  shieldInsights,
  shieldKpisToMetrics,
  shieldPayloadToMetrics,
  shieldPresenceBreakdown,
  shieldPresenceByKind,
  shieldSeriesInsights,
  shieldSeriesPoints,
} from "@/lib/adapters/shield";
import { hrMartMetrics, payrollBreakdown } from "@/lib/adapters/governance";
import { useFilters } from "@/store/filters";

/** Nombre de KPI mis en avant dans la colonne ; le reste est replié. */
const VISIBLE = 6;
const PANEL_STYLE = {
  ...glass,
  background: "linear-gradient(135deg,rgba(255,255,255,0.86),rgba(243,248,249,0.58))",
};

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-1">{children}</div>;
}

/** Métriques vivantes d'un domaine. Seul Capital Humain dispose aujourd'hui de
 *  sources réellement branchées (Shield + mart RH) ; les autres domaines n'ont
 *  aucun mart alimenté et restent donc sur leurs métriques déclarées. */
function useDomainMetrics(domainId: string, seriesWindow: SeriesWindow) {
  const isHr = domainId === "capital-humain";
  const isRisk = domainId === "risques-conformite";
  const isOverview = domainId === "overview";
  const { year, quarter } = useFilters();

  // Shield alimente trois cockpits avec trois jeux d'indicateurs distincts ;
  // chaque requête n'est activée que sur le domaine concerné.
  const shield = useShieldHrKpis();
  const security = useShieldSecurity();
  const overview = useShieldOverview();
  const hrKpi = useHrKpi(year, quarter);
  const series = useShieldAttendanceSeries(seriesWindow);

  const shieldQuery = isRisk ? security : isOverview ? overview : shield;

  const live = React.useMemo(() => {
    if (isHr) return [...shieldKpisToMetrics(shield.data), ...hrMartMetrics(hrKpi.data, `T${quarter} ${year}`)];
    if (isRisk) return shieldPayloadToMetrics(security.data, "risk", "/dashboard/risques-conformite/alertes-critiques");
    if (isOverview) return shieldPayloadToMetrics(overview.data, "groupe");
    return [];
  }, [isHr, isRisk, isOverview, shield.data, security.data, overview.data, hrKpi.data, quarter, year]);

  const breakdown = React.useMemo(() => (isHr ? payrollBreakdown(hrKpi.data) : []), [isHr, hrKpi.data]);

  const shieldState: DataState = shieldQuery.isLoading
    ? "connecting"
    : shieldQuery.isError || !shieldQuery.data
      ? "error"
      : shieldQuery.data.stale
        ? "stale"
        : shieldQuery.data.payload.status;

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
    breakdownState: (breakdown.length
      ? "connected"
      : martState === "connecting"
        ? "connecting"
        : "disconnected") as DataState,
    loading: isHr && (shield.isLoading || hrKpi.isLoading),
    shieldState,
    martState,
    // Répartitions et constats issus de Shield, disponibles sur le domaine RH.
    presenceBySite: isHr ? shieldPresenceBreakdown(shield.data) : [],
    attendanceRateBySite: isHr ? shieldAttendanceRateBreakdown(shield.data) : [],
    siteState: isHr ? shieldBreakdownStatus(shield.data) : ("disconnected" as DataState),
    siteNote: isHr ? shield.data?.payload.by_site?.detail : undefined,
    insights: [...shieldInsights(shieldQuery.data), ...(isHr ? shieldSeriesInsights(series.data) : [])],
    // Série de présence : uniquement sur Capital Humain, où elle a un sens.
    seriesPoints: isHr ? shieldSeriesPoints(series.data) : [],
    seriesState: (isHr
      ? series.isLoading
        ? "connecting"
        : series.isError || !series.data
          ? "error"
          : series.data.stale
            ? "stale"
            : series.data.payload.status
      : "disconnected") as DataState,
    seriesMeasured: series.data?.payload.measured_days,
    seriesTotal: series.data?.payload.points.length,
    presenceByKind: isHr ? shieldPresenceByKind(shield.data) : [],
    kindState: (shield.data?.payload.by_kind?.status ?? "disconnected") as DataState,
  };
}

export function DomainPanel({ domainId }: { domainId: string }) {
  const online = useOnlineStatus();
  const [expanded, setExpanded] = React.useState(false);
  const [seriesWindow, setSeriesWindow] = React.useState<SeriesWindow>(30);
  const {
    metrics, breakdown, breakdownState, shieldState, martState,
    presenceBySite, attendanceRateBySite, siteState, siteNote, insights,
    seriesPoints, seriesState, seriesMeasured, seriesTotal, presenceByKind, kindState,
  } = useDomainMetrics(domainId, seriesWindow);

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

      {/* Tendance du taux de présence, mesurée jour par jour. */}
      {seriesPoints.length ? (
        <article className="rounded-[22px] p-4 sm:p-5" style={{ ...PANEL_STYLE }}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[12.5px] font-semibold text-[#586061]">Taux de présence</span>
            <div className="flex items-center gap-2">
              <div className="flex gap-1">
                {SERIES_WINDOWS.map((w) => (
                  <button
                    key={w}
                    type="button"
                    onClick={() => setSeriesWindow(w)}
                    className={`ki-accent-ring rounded-full px-2.5 py-1 text-[10.5px] font-bold transition-colors ${
                      w === seriesWindow ? "bg-[#16191A] text-white" : "bg-white/70 text-[#586061] hover:bg-white"
                    }`}
                  >
                    {w} j
                  </button>
                ))}
              </div>
              <StateBadge state={seriesState} />
            </div>
          </div>
          <div className="mt-3">
            <TrendChart series={seriesPoints} label="Taux de présence" unit="%" state={seriesState} source="Kaydan Shield" height={190} />
          </div>
          {typeof seriesMeasured === "number" && seriesMeasured !== seriesTotal ? (
            <p className="mt-2 text-[10.5px] font-medium text-[#9AA09D]">
              {seriesMeasured}/{seriesTotal} jours mesurés — les jours manquants laissent un trou dans la courbe.
            </p>
          ) : null}
        </article>
      ) : null}

      {/* Présents du jour : employés vs ouvriers (filtre `holder_kind`). */}
      {presenceByKind.some((i) => i.value !== null) ? (
        <RankingCard
          title="Présents aujourd'hui par catégorie"
          items={presenceByKind}
          state={kindState}
          source="Kaydan Shield"
          max={2}
        />
      ) : null}

      {/* Présence par site : mesurée site par site via /attendance/days/. */}
      {presenceBySite.length ? (
        <article className="rounded-[22px] p-4 sm:p-5" style={{ ...PANEL_STYLE }}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[12.5px] font-semibold text-[#586061]">Présents par site</span>
            <StateBadge state={siteState} />
          </div>
          <div className="mt-3">
            <BreakdownChart items={presenceBySite} state={siteState} source="Kaydan Shield" height={200} />
          </div>
          {siteNote ? (
            <p className="mt-2 text-[10.5px] font-medium leading-snug text-[#9AA09D]">{siteNote}</p>
          ) : null}
        </article>
      ) : null}

      {attendanceRateBySite.some((i) => i.value !== null) ? (
        <RankingCard
          title="Taux de présence par site"
          items={attendanceRateBySite}
          unit="%"
          state={siteState}
          source="Kaydan Shield"
        />
      ) : null}

      <SourceHealth sources={sources} />

      {insights.length ? (
        insights.map((insight) => <DecisionInsightCard key={insight.id} insight={insight} />)
      ) : (
        <NoInsights
          reason={
            connectedCount === 0
              ? "Aucune source de ce domaine n'est raccordée : il n'y a pas encore de constat à formuler."
              : "Les mesures disponibles ne franchissent aucun seuil d'alerte : rien à signaler."
          }
        />
      )}
    </div>
  );
}
