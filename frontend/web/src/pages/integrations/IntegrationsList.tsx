import { Link } from "react-router-dom";

import type { DataSource } from "@/types/integrations";

import { glass } from "@/components/chrome/theme";
import { IntegrationsError, IntegrationsShell, PrimaryLink, StatusBadge } from "@/components/integrations/parts";
import { useSources, useSyncNow, useTestConnection, useToggleActive } from "@/lib/integrations";
import { useRelativeTime } from "@/components/ui/kit";

export function IntegrationsList() {
  const { data: sources, isLoading, isError, error } = useSources();
  const test = useTestConnection();
  const sync = useSyncNow();
  const toggle = useToggleActive();

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
      {isError ? <IntegrationsError error={error} /> : null}

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
                <th className="px-3 py-4">Environnement</th>
                <th className="px-3 py-4">Statut</th>
                <th className="px-3 py-4">Dernier test</th>
                <th className="px-5 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <SourceRow key={s.id} source={s} test={test} sync={sync} toggle={toggle} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </IntegrationsShell>
  );
}

/** Une ligne de source : état, fraîcheur, latence, erreurs récentes, actions.
 *
 *  Le retour de test est affiché À LA LIGNE concernée : un message global
 *  laisserait l'utilisateur deviner quelle source a répondu quoi.
 */
function SourceRow({ source, test, sync, toggle }: {
  source: DataSource;
  test: ReturnType<typeof useTestConnection>;
  sync: ReturnType<typeof useSyncNow>;
  toggle: ReturnType<typeof useToggleActive>;
}) {
  const testedAgo = useRelativeTime(source.last_tested_at ?? undefined);
  const syncedAgo = useRelativeTime(source.last_sync_at ?? undefined);
  const busy = test.isPending && test.variables === source.id;
  const result = test.data && test.variables === source.id ? test.data : null;
  const erreurs = source.recent_errors ?? [];

  return (
    <tr className="border-t border-[#E2E6E2]/80 align-top">
      <td className="px-5 py-4">
        <Link to={`/admin/integrations/${source.id}`} className="font-bold text-[#16191A] hover:text-[#FF8735]">
          {source.name}
        </Link>
        <div className="text-[11px] text-[#9AA09D]">{source.slug}</div>
        {source.base_url ? (
          <div className="mt-0.5 max-w-[240px] truncate text-[11px] text-[#9AA09D]" title={source.base_url}>
            {source.base_url}
          </div>
        ) : null}
      </td>
      <td className="px-3 py-4 text-[#52595A]">{source.source_type_label}</td>
      <td className="px-3 py-4 text-[#52595A]">
        {source.environment_label ?? "—"}
        {source.demo_mode ? <div className="text-[11px] text-[#B4820F]">mode démo</div> : null}
      </td>
      <td className="px-3 py-4">
        <StatusBadge status={source.status} />
        {!source.is_active ? <div className="mt-1 text-[11px] font-semibold text-[#8A8F8E]">désactivée</div> : null}
        {erreurs.length ? (
          <div className="mt-1.5 max-w-[220px] truncate text-[11px] font-semibold text-[#A32D2D]" title={erreurs[0].message}>
            {erreurs.length} erreur{erreurs.length > 1 ? "s" : ""} · {erreurs[0].message}
          </div>
        ) : null}
      </td>
      <td className="px-3 py-4 text-[13px] text-[#52595A]">
        {busy ? (
          <span className="font-semibold text-[#185FA5]">Test en cours…</span>
        ) : source.last_tested_at ? (
          <>
            <div className="font-semibold">{testedAgo}</div>
            {source.last_latency_ms != null ? (
              <div className="text-[11px] text-[#9AA09D]">{source.last_latency_ms} ms</div>
            ) : null}
          </>
        ) : (
          <span className="text-[#9AA09D]">jamais testée</span>
        )}
        <div className="mt-1 text-[11px] text-[#9AA09D]">
          {source.last_sync_at ? `sync ${syncedAgo}` : "aucune sync"}
        </div>
        {result ? (
          <div className={`mt-1 max-w-[220px] text-[11px] font-semibold ${result.ok ? "text-[#0F6E56]" : "text-[#A32D2D]"}`}>
            {result.message}
          </div>
        ) : null}
      </td>
      <td className="px-5 py-4">
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button type="button" disabled={busy} onClick={() => test.mutate(source.id)}
            className="rounded-full border border-[#DDE2E0] bg-white/70 px-3 py-1.5 text-[12px] font-bold text-[#3A3E3E] hover:bg-white disabled:opacity-50">
            {busy ? "Test…" : "Tester"}
          </button>
          <button type="button" disabled={sync.isPending} onClick={() => sync.mutate(source.id)}
            className="rounded-full bg-[#FF8735] px-3 py-1.5 text-[12px] font-bold text-white hover:brightness-95 disabled:opacity-50">
            Synchroniser
          </button>
          <Link to={`/admin/integrations/${source.id}`}
            className="rounded-full border border-[#DDE2E0] bg-white/70 px-3 py-1.5 text-[12px] font-bold text-[#3A3E3E] hover:bg-white">
            Configurer
          </Link>
          <button
            type="button"
            onClick={() => {
              // Désactiver coupe l'alimentation d'un tableau de bord : on confirme.
              const verbe = source.is_active ? "Désactiver" : "Réactiver";
              if (window.confirm(`${verbe} « ${source.name} » ?`)) toggle.mutate(source.id);
            }}
            className="rounded-full border border-[#DDE2E0] bg-white/70 px-3 py-1.5 text-[12px] font-bold text-[#8A4A4A] hover:bg-white"
          >
            {source.is_active ? "Désactiver" : "Réactiver"}
          </button>
        </div>
      </td>
    </tr>
  );
}
