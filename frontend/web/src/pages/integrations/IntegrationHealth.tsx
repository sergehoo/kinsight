import { Link } from "react-router-dom";

import { glass } from "@/components/chrome/theme";
import { IntegrationsError, IntegrationsShell, StatusBadge } from "@/components/integrations/parts";
import { useHealth } from "@/lib/integrations";
import { useRelativeTime } from "@/components/ui/kit";

function Stat({ label, value, color, hint }: {
  label: string; value: number | string | null; color: string; hint?: string;
}) {
  return (
    <div className="rounded-[22px] p-5" style={glass}>
      <div className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#8A9291]">{label}</div>
      {/* `null` n'est pas 0 : une latence inconnue ne doit pas s'afficher « 0 ms ». */}
      <div className="mt-2 text-[34px] font-semibold leading-none" style={{ color }}>
        {value ?? "—"}
      </div>
      {hint ? <div className="mt-1.5 text-[11px] font-medium text-[#9AA09D]">{hint}</div> : null}
    </div>
  );
}

export function IntegrationHealth() {
  const { data, isLoading, isError, error } = useHealth();
  const lastSync = useRelativeTime(data?.last_sync ?? undefined);

  return (
    <IntegrationsShell
      title="Santé des connecteurs"
      subtitle="Vue consolidée de l'état des sources. Le mode dégradé garantit qu'une source non connectée n'interrompt pas la plateforme."
      actions={<Link to="/admin/integrations" className="rounded-full px-4 py-2.5 text-[13px] font-bold text-[#3A3E3E]" style={glass}>Liste des intégrations</Link>}
    >
      {isLoading ? <p className="text-[14px] text-[#777C7D]">Chargement…</p> : null}
      {isError ? <IntegrationsError error={error} /> : null}

      {data ? (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
            <Stat label="Sources" value={data.total} color="#16191A" hint={`${data.active} active(s)`} />
            <Stat label="Connectées" value={data.connected} color="#0F6E56" />
            <Stat label="Partielles" value={data.partial ?? 0} color="#B4820F"
                  hint="au moins une source répond, pas toutes" />
            <Stat label="En erreur" value={data.error} color="#A32D2D" />
            <Stat label="Périmées" value={data.stale ?? 0} color="#8A6D1F"
                  hint={`connectées mais non testées depuis ${data.stale_after_hours ?? 24} h`} />
            <Stat label="Latence moyenne" value={data.avg_latency_ms != null ? `${data.avg_latency_ms} ms` : null}
                  color="#185FA5" hint={data.last_sync ? `dernière sync ${lastSync}` : "aucune sync enregistrée"} />
          </div>

          {data.total === 0 ? (
            <div className="mt-6 rounded-[24px] px-6 py-10 text-center" style={glass}>
              <p className="text-[15px] font-semibold text-[#2C3132]">Aucune source déclarée</p>
              <p className="mx-auto mt-2 max-w-[440px] text-[13px] text-[#777C7D]">
                Les cockpits métier resteront en « non connecté » tant qu'aucune plateforme
                n'est raccordée. C'est le comportement voulu : aucune donnée n'est simulée.
              </p>
              <Link to="/admin/integrations/new"
                className="mt-5 inline-flex rounded-full bg-[#0B0B0C] px-5 py-2.5 text-[13px] font-bold text-white">
                + Ajouter une source
              </Link>
            </div>
          ) : null}

          <div className="mt-6 overflow-hidden rounded-[24px]" style={glass}>
            <table className="w-full border-collapse text-[13.5px]">
              <thead>
                <tr className="text-left text-[11px] font-bold uppercase tracking-[0.1em] text-[#8A9291]">
                  <th className="px-5 py-4">Plateforme</th>
                  <th className="px-3 py-4">Module</th>
                  <th className="px-3 py-4">Statut</th>
                  <th className="px-5 py-4 text-right">Dernière MAJ</th>
                </tr>
              </thead>
              <tbody>
                {data.sources.map((s) => (
                  <tr key={s.id} className="border-t border-[#E2E6E2]/80">
                    <td className="px-5 py-4">
                      <Link to={`/admin/integrations/${s.id}`} className="font-bold text-[#16191A] hover:text-[#FF8735]">{s.name}</Link>
                    </td>
                    <td className="px-3 py-4 text-[#52595A]">{s.target_module_label ?? s.target_module}</td>
                    <td className="px-3 py-4"><StatusBadge status={s.status} /></td>
                    <td className="px-5 py-4 text-right text-[#9AA09D]">{new Date(s.updated_at).toLocaleString("fr-FR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </IntegrationsShell>
  );
}
