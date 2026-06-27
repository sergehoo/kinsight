import { Link } from "react-router-dom";

import { glass } from "@/components/chrome/theme";
import { IntegrationsShell, StatusBadge } from "@/components/integrations/parts";
import { useHealth } from "@/lib/integrations";

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-[22px] p-5" style={glass}>
      <div className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#8A9291]">{label}</div>
      <div className="mt-2 text-[34px] font-semibold leading-none" style={{ color }}>{value}</div>
    </div>
  );
}

export function IntegrationHealth() {
  const { data, isLoading, isError } = useHealth();

  return (
    <IntegrationsShell
      title="Santé des connecteurs"
      subtitle="Vue consolidée de l'état des sources. Le mode dégradé garantit qu'une source non connectée n'interrompt pas la plateforme."
      actions={<Link to="/admin/integrations" className="rounded-full px-4 py-2.5 text-[13px] font-bold text-[#3A3E3E]" style={glass}>Liste des intégrations</Link>}
    >
      {isLoading ? <p className="text-[14px] text-[#777C7D]">Chargement…</p> : null}
      {isError ? <p className="rounded-2xl bg-[#FCEBEB] px-5 py-4 text-[14px] font-semibold text-[#A32D2D]">Backend intégrations indisponible.</p> : null}

      {data ? (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Sources" value={data.total} color="#16191A" />
            <Stat label="Actives" value={data.active} color="#185FA5" />
            <Stat label="Connectées" value={data.connected} color="#0F6E56" />
            <Stat label="En erreur" value={data.error} color="#A32D2D" />
          </div>

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
