/** Colonne KPI RH branchée sur Kaydan Shield (via l'API K-Insight). États gouvernés.
 *
 *  Un KPI n'affiche une valeur QUE si la source l'a réellement renvoyée. Hors ligne,
 *  la dernière donnée connue reste lisible mais porte l'état `stale` : jamais présentée
 *  comme fraîche. Sans cache disponible, l'état est `offline` et aucun chiffre n'est
 *  inventé.
 */
import { MetricCard, StateBadge, type DataState } from "@/components/ui/kit";
import { useShieldHrKpis } from "@/lib/shieldHr";
import { useOnlineStatus } from "@/pwa/useNetwork";

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
  const online = useOnlineStatus();

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
    // Hors ligne sans cache : on le dit, plutôt que d'afficher une erreur brute.
    const fallback: DataState = online ? "error" : "offline";
    return (
      <Grid>
        {PLACEHOLDERS.map((title) => (
          <MetricCard key={title} title={title} state={fallback} source={SOURCE} scope={SCOPE} />
        ))}
      </Grid>
    );
  }

  const { payload, stale, cachedAt } = data;
  const source = payload.source || SOURCE;
  const updatedAt =
    (stale ? cachedAt && new Date(cachedAt).toISOString() : payload.updated_at) ??
    (dataUpdatedAt ? new Date(dataUpdatedAt).toISOString() : undefined);

  // Une réponse issue du cache ne peut pas être annoncée « connectée ».
  const stateFor = (kpiStatus: DataState): DataState =>
    stale && kpiStatus === "connected" ? "stale" : kpiStatus;
  const bannerState: DataState = stale ? "stale" : payload.status;

  return (
    <div className="flex flex-col gap-3">
      {/* Bandeau de source : état consolidé de la connexion RH. */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-[16px] bg-white/55 px-3 py-2">
        <span className="truncate text-[11.5px] font-bold text-[#4A4F50]">{source}</span>
        <StateBadge state={bannerState} />
      </div>

      <Grid>
        {payload.kpis.map((kpi, index) => {
          const state = stateFor(kpi.status);
          return (
            <MetricCard
              key={kpi.key}
              title={kpi.title}
              value={kpi.value}
              unit={kpi.unit}
              state={state}
              source={source}
              updatedAt={state === "connected" || state === "stale" ? updatedAt : undefined}
              scope={SCOPE}
              highlighted={index === 0}
            />
          );
        })}
      </Grid>
    </div>
  );
}
