/** Colonne KPI RH branchée sur Kaydan Shield (via l'API K-Insight). États gouvernés.
 *
 *  Un KPI n'affiche une valeur QUE si la source l'a réellement renvoyée. Sinon
 *  l'état (`connecting` / `partial` / `disconnected` / `error`) est explicite.
 */
import { MetricCard, StateBadge, type DataState } from "@/components/ui/kit";
import { useShieldHrKpis } from "@/lib/shieldHr";

const SOURCE = "Kaydan Shield";
const SCOPE = "Périmètre Groupe";

/** Ordre d'affichage stable, utilisé aussi pour les squelettes de chargement. */
const PLACEHOLDERS = [
  "Effectif total", "Employés", "Ouvriers", "Présents aujourd'hui",
  "Absents", "Retards", "Taux de présence", "Sites",
];

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-1">{children}</div>;
}

export function ShieldHrKpis() {
  const { data, isLoading, isError, dataUpdatedAt } = useShieldHrKpis();

  if (isLoading) {
    return (
      <Grid>
        {PLACEHOLDERS.map((title) => (
          <MetricCard key={title} title={title} state="connecting" source={SOURCE} scope={SCOPE} />
        ))}
      </Grid>
    );
  }

  if (isError || !data) {
    return (
      <Grid>
        {PLACEHOLDERS.map((title) => (
          <MetricCard key={title} title={title} state="error" source={SOURCE} scope={SCOPE} />
        ))}
      </Grid>
    );
  }

  const source = data.source || SOURCE;
  const updatedAt = data.updated_at ?? (dataUpdatedAt ? new Date(dataUpdatedAt).toISOString() : undefined);

  return (
    <div className="flex flex-col gap-3">
      {/* Bandeau de source : état consolidé de la connexion RH. */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-[16px] bg-white/55 px-3 py-2">
        <span className="truncate text-[11.5px] font-bold text-[#4A4F50]">{source}</span>
        <StateBadge state={data.status as DataState} />
      </div>

      <Grid>
        {data.kpis.map((kpi, index) => (
          <MetricCard
            key={kpi.key}
            title={kpi.title}
            value={kpi.value}
            unit={kpi.unit}
            state={kpi.status}
            source={source}
            updatedAt={kpi.status === "connected" ? updatedAt : undefined}
            scope={SCOPE}
            highlighted={index === 0}
          />
        ))}
      </Grid>
    </div>
  );
}
