import { useHrKpi } from "@/api/governance";
import { GlobalFilters } from "@/components/GlobalFilters";
import { KpiCard } from "@/components/KpiCard";
import { PayrollBySubsidiaryChart } from "@/components/PayrollBySubsidiaryChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { IconArrowDownRight, IconTrend, IconUsers, IconWallet } from "@/components/icons";
import { formatSigned, formatXof, formatInt } from "@/lib/format";
import { useFilters } from "@/store/filters";

function periodLabel(start: string, end: string): string {
  return `${start} → ${end}`;
}

export function HrDashboard() {
  const { year, quarter } = useFilters();
  const { data, isLoading, isError, error } = useHrKpi(year, quarter);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-brand-600">
            Gouvernance RH
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
            Tableau de bord — Ressources humaines
          </h1>
          {data && (
            <p className="mt-1 text-sm text-slate-400">
              Périmètre&nbsp;:{" "}
              <span className="font-medium text-slate-600">
                {data.scope === "GROUP" ? "Groupe (toutes filiales)" : data.scope.join(", ")}
              </span>{" "}
              · Période {periodLabel(data.period.start, data.period.end)}
            </p>
          )}
        </div>
        <GlobalFilters />
      </header>

      {isLoading && <SkeletonGrid />}

      {isError && (
        <Card className="border-rose-200 bg-rose-50">
          <CardContent className="py-6 text-sm text-rose-700">
            Impossible de charger les indicateurs : {(error as Error).message}
          </CardContent>
        </Card>
      )}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              index={0}
              title="Masse salariale (brut)"
              value={formatXof(data.metrics["hr.payroll_mass"].value)}
              hint="Cumul de la période"
              icon={<IconWallet className="h-[18px] w-[18px]" />}
            />
            <KpiCard
              index={1}
              title="Entrées"
              value={formatInt(data.metrics["hr.entries"].value)}
              hint="Embauches sur la période"
              icon={<IconUsers className="h-[18px] w-[18px]" />}
              tone="good"
            />
            <KpiCard
              index={2}
              title="Sorties"
              value={formatInt(data.metrics["hr.exits"].value)}
              hint="Départs sur la période"
              icon={<IconArrowDownRight className="h-[18px] w-[18px]" />}
              tone="bad"
            />
            <KpiCard
              index={3}
              title="Variation nette d'effectif"
              value={formatSigned(data.metrics["hr.net_headcount_change"].value)}
              hint="Entrées − sorties"
              icon={<IconTrend className="h-[18px] w-[18px]" />}
              tone={
                data.metrics["hr.net_headcount_change"].value >= 0 ? "good" : "bad"
              }
            />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-slate-700">
                  Masse salariale par filiale
                </CardTitle>
              </CardHeader>
              <CardContent>
                <PayrollBySubsidiaryChart data={data.payroll_by_subsidiary} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-slate-700">Répartition</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(data.payroll_by_subsidiary)
                  .sort((a, b) => b[1] - a[1])
                  .map(([code, value]) => {
                    const total = Object.values(data.payroll_by_subsidiary).reduce(
                      (s, v) => s + v,
                      0,
                    );
                    const pct = total ? Math.round((value / total) * 100) : 0;
                    return (
                      <div key={code}>
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium text-slate-600">{code}</span>
                          <span className="text-slate-400">{pct}%</span>
                        </div>
                        <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-brand-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="py-10">
            <div className="h-4 w-24 animate-pulse rounded bg-slate-100" />
            <div className="mt-3 h-7 w-32 animate-pulse rounded bg-slate-100" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
