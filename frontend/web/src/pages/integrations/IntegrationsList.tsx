import { Link } from "react-router-dom";

import { glass } from "@/components/chrome/theme";
import { IntegrationsShell, PrimaryLink, StatusBadge } from "@/components/integrations/parts";
import { useSources, useSyncNow, useTestConnection } from "@/lib/integrations";

export function IntegrationsList() {
  const { data: sources, isLoading, isError } = useSources();
  const test = useTestConnection();
  const sync = useSyncNow();

  return (
    <IntegrationsShell
      title="Liste des intégrations"
      subtitle="Ajoutez et configurez les plateformes sources (K-Shield, K-Express, CRM, Odoo…) sans toucher au code. Une source non connectée n'empêche jamais la plateforme de fonctionner."
      actions={
        <>
          <Link to="/admin/integrations/health" className="rounded-full px-4 py-2.5 text-[13px] font-bold text-[#3A3E3E]" style={glass}>Santé des connecteurs</Link>
          <PrimaryLink to="/admin/integrations/new">+ Ajouter une source</PrimaryLink>
        </>
      }
    >
      {isLoading ? <p className="text-[14px] text-[#777C7D]">Chargement…</p> : null}
      {isError ? <p className="rounded-2xl bg-[#FCEBEB] px-5 py-4 text-[14px] font-semibold text-[#A32D2D]">Backend intégrations indisponible — vérifiez l'API.</p> : null}

      {sources && sources.length === 0 ? (
        <div className="rounded-[24px] px-6 py-10 text-center" style={glass}>
          <p className="text-[15px] font-semibold text-[#2C3132]">Aucune source configurée</p>
          <p className="mx-auto mt-2 max-w-[420px] text-[13px] text-[#777C7D]">Commencez par ajouter une plateforme. Vous pourrez la configurer puis tester la connexion quand son API sera prête.</p>
          <div className="mt-5 flex justify-center"><PrimaryLink to="/admin/integrations/new">+ Ajouter une source</PrimaryLink></div>
        </div>
      ) : null}

      {sources && sources.length > 0 ? (
        <div className="overflow-hidden rounded-[24px]" style={glass}>
          <table className="w-full border-collapse text-[13.5px]">
            <thead>
              <tr className="text-left text-[11px] font-bold uppercase tracking-[0.1em] text-[#8A9291]">
                <th className="px-5 py-4">Plateforme</th>
                <th className="px-3 py-4">Type</th>
                <th className="px-3 py-4">Module cible</th>
                <th className="px-3 py-4">Statut</th>
                <th className="px-3 py-4">Fréquence</th>
                <th className="px-5 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id} className="border-t border-[#E2E6E2]/80">
                  <td className="px-5 py-4">
                    <Link to={`/admin/integrations/${s.id}`} className="font-bold text-[#16191A] hover:text-[#FF8735]">{s.name}</Link>
                    <div className="text-[11px] text-[#9AA09D]">{s.slug}</div>
                  </td>
                  <td className="px-3 py-4 text-[#52595A]">{s.source_type_label}</td>
                  <td className="px-3 py-4 text-[#52595A]">{s.target_module_label ?? s.target_module}</td>
                  <td className="px-3 py-4"><StatusBadge status={s.status} /></td>
                  <td className="px-3 py-4 text-[#52595A]">{s.sync_frequency}{s.demo_mode ? " · démo" : ""}</td>
                  <td className="px-5 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <button type="button" onClick={() => test.mutate(s.id)} className="rounded-full border border-[#DDE2E0] bg-white/70 px-3 py-1.5 text-[12px] font-bold text-[#3A3E3E] hover:bg-white">Tester</button>
                      <button type="button" onClick={() => sync.mutate(s.id)} className="rounded-full bg-[#FF8735] px-3 py-1.5 text-[12px] font-bold text-white hover:brightness-95">Synchroniser</button>
                      <Link to={`/admin/integrations/${s.id}`} className="rounded-full border border-[#DDE2E0] bg-white/70 px-3 py-1.5 text-[12px] font-bold text-[#3A3E3E] hover:bg-white">Configurer</Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </IntegrationsShell>
  );
}
