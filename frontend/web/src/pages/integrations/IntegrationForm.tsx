import * as React from "react";
import { useNavigate, useParams } from "react-router-dom";

import { glass } from "@/components/chrome/theme";
import { IntegrationsShell, StatusBadge } from "@/components/integrations/parts";
import {
  useAddCredential,
  useCreateEndpoint,
  useCreateMapping,
  useCreateSource,
  useDeleteEndpoint,
  useDeleteMapping,
  useEndpoints,
  useErrors,
  useJobs,
  useLogs,
  useMappings,
  useSource,
  useSyncNow,
  useTestConnection,
  useUpdateConnector,
} from "@/lib/integrations";

const SOURCE_TYPES = [
  ["rest", "API REST"], ["graphql", "API GraphQL"], ["webhook", "Webhook"], ["postgres", "PostgreSQL (RO)"],
  ["mysql", "MySQL (RO)"], ["csv", "CSV"], ["excel", "Excel"], ["gsheets", "Google Sheets"], ["airbyte", "Airbyte"],
];
const TARGET_MODULES = [
  ["rh", "Capital Humain"], ["immobilier", "Immobilier"], ["finance", "Finance"], ["stocks", "Stocks & Logistique"],
  ["flotte", "Flotte"], ["securite", "Sécurité"], ["commercial", "Commercial & Clients"], ["risques", "Risques & Conformité"],
  ["groupe", "Groupe"], ["autre", "Autre"],
];
const AUTH_METHODS = [["none", "Aucune"], ["api_key", "Clé API"], ["bearer", "Bearer"], ["basic", "Basic"], ["oauth2", "OAuth2"], ["header", "Header"]];

const field = "h-11 w-full rounded-xl border border-[#DDE2E0] bg-white/80 px-4 text-[14px] text-[#1A1F1F] outline-none focus:border-[#FF8735]";
const labelCls = "mb-1.5 block text-[12px] font-bold uppercase tracking-[0.08em] text-[#8A9291]";
const btnDark = "rounded-full bg-[#0B0B0C] px-5 py-2.5 text-[13px] font-bold text-white disabled:opacity-60";
const btnGhost = "rounded-full border border-[#DDE2E0] bg-white/70 px-4 py-2 text-[12px] font-bold text-[#3A3E3E] hover:bg-white";

function slugify(s: string) {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function CreateForm() {
  const navigate = useNavigate();
  const create = useCreateSource();
  const [name, setName] = React.useState("");
  const [sourceType, setSourceType] = React.useState("rest");
  const [target, setTarget] = React.useState("autre");
  const [frequency, setFrequency] = React.useState("manual");
  const [demo, setDemo] = React.useState(true);
  const [description, setDescription] = React.useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate(
      { name, slug: slugify(name), source_type: sourceType, target_module: target, sync_frequency: frequency, demo_mode: demo, description },
      { onSuccess: (s) => navigate(`/admin/integrations/${s.id}`) },
    );
  };

  return (
    <form onSubmit={submit} className="grid max-w-[760px] gap-5 rounded-[24px] p-7" style={glass}>
      <div>
        <label className={labelCls}>Nom de la plateforme</label>
        <input className={field} value={name} onChange={(e) => setName(e.target.value)} placeholder="K-Shield, K-Express, CRM…" required />
        {name ? <p className="mt-1 text-[11px] text-[#9AA09D]">slug : {slugify(name)}</p> : null}
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label className={labelCls}>Type de source</label>
          <select className={field} value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
            {SOURCE_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Module cible</label>
          <select className={field} value={target} onChange={(e) => setTarget(e.target.value)}>
            {TARGET_MODULES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Fréquence de synchronisation</label>
          <input className={field} value={frequency} onChange={(e) => setFrequency(e.target.value)} placeholder="manual ou cron (ex. 0 */6 * * *)" />
        </div>
        <label className="flex items-center gap-3 self-end pb-1 text-[14px] font-semibold text-[#2C3132]">
          <input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} className="h-4 w-4" />
          Mode démo (dégradé) tant que non connectée
        </label>
      </div>
      <div>
        <label className={labelCls}>Description</label>
        <textarea className="min-h-[80px] w-full rounded-xl border border-[#DDE2E0] bg-white/80 px-4 py-3 text-[14px] outline-none focus:border-[#FF8735]" value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      {create.isError ? <p className="text-[13px] font-semibold text-[#A32D2D]">Échec de création (backend indisponible ou droits insuffisants).</p> : null}
      <div className="flex gap-3">
        <button type="submit" disabled={create.isPending} className="rounded-full bg-[#0B0B0C] px-6 py-3 text-[14px] font-bold text-white disabled:opacity-60">{create.isPending ? "Création…" : "Créer la source"}</button>
        <button type="button" onClick={() => navigate("/admin/integrations")} className="rounded-full border border-[#DDE2E0] bg-white/70 px-6 py-3 text-[14px] font-bold text-[#3A3E3E]">Annuler</button>
      </div>
    </form>
  );
}

function ApiConfigTab({ source }: { source: any }) {
  const updateConnector = useUpdateConnector();
  const addCredential = useAddCredential();
  const test = useTestConnection();
  const sync = useSyncNow();
  const [baseUrl, setBaseUrl] = React.useState(source.connector?.base_url || "");
  const [auth, setAuth] = React.useState(source.connector?.auth_method || "none");
  const [token, setToken] = React.useState("");
  const connectorId = source.connector?.id;
  const cred = source.connector?.credentials?.[0];

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!connectorId) return;
    await updateConnector.mutateAsync({ id: connectorId, patch: { base_url: baseUrl, auth_method: auth } });
    if (token.trim()) {
      await addCredential.mutateAsync({ connector: connectorId, kind: "api_token", label: "Token API", secret: token.trim() });
      setToken("");
    }
  };

  return (
    <form onSubmit={save} className="grid gap-5 rounded-[24px] p-7" style={glass}>
      <div>
        <label className={labelCls}>URL de base</label>
        <input className={field} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.k-shield.io" />
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label className={labelCls}>Authentification</label>
          <select className={field} value={auth} onChange={(e) => setAuth(e.target.value)}>
            {AUTH_METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Token API {cred?.is_set ? <span className="text-[#0F6E56]">· défini ({cred.masked})</span> : null}</label>
          <input className={field} type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder={cred?.is_set ? "•••• (laisser vide pour conserver)" : "Coller le token (chiffré en base)"} />
        </div>
      </div>
      <p className="text-[11px] text-[#9AA09D]">Les secrets sont chiffrés au repos et ne sont jamais réaffichés en clair.</p>
      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={updateConnector.isPending} className={btnDark}>Enregistrer</button>
        <button type="button" onClick={() => test.mutate(source.id)} className={btnGhost}>Tester la connexion</button>
        <button type="button" onClick={() => sync.mutate(source.id)} className="rounded-full bg-[#FF8735] px-5 py-2.5 text-[13px] font-bold text-white">Synchroniser</button>
      </div>
      {test.data ? <p className="text-[13px] font-semibold" style={{ color: test.data.ok ? "#0F6E56" : "#A32D2D" }}>{test.data.message}</p> : null}
      {sync.data ? <p className="text-[13px] font-semibold text-[#185FA5]">Sync : {sync.data.status} — {sync.data.message}</p> : null}
    </form>
  );
}

function EndpointsTab({ connectorId }: { connectorId?: string }) {
  const { data: endpoints } = useEndpoints(connectorId);
  const create = useCreateEndpoint();
  const del = useDeleteEndpoint();
  const [name, setName] = React.useState("");
  const [path, setPath] = React.useState("");
  const [method, setMethod] = React.useState("GET");
  const [incremental, setIncremental] = React.useState(false);
  const [cursor, setCursor] = React.useState("");

  const add = (e: React.FormEvent) => {
    e.preventDefault();
    if (!connectorId || !name) return;
    create.mutate(
      { connector: connectorId, name, path, http_method: method, incremental, cursor_field: cursor },
      { onSuccess: () => { setName(""); setPath(""); setCursor(""); setIncremental(false); } },
    );
  };

  return (
    <div className="grid gap-5">
      <form onSubmit={add} className="grid gap-4 rounded-[24px] p-6 sm:grid-cols-[1fr_1.4fr_auto_auto]" style={glass}>
        <div><label className={labelCls}>Nom</label><input className={field} value={name} onChange={(e) => setName(e.target.value)} placeholder="Employés" required /></div>
        <div><label className={labelCls}>Chemin / table / requête</label><input className={field} value={path} onChange={(e) => setPath(e.target.value)} placeholder="/api/hr/employees" /></div>
        <div><label className={labelCls}>Méthode</label><select className={field} value={method} onChange={(e) => setMethod(e.target.value)}><option>GET</option><option>POST</option></select></div>
        <div className="flex flex-col justify-end gap-2">
          <label className="flex items-center gap-2 text-[12px] font-semibold text-[#2C3132]"><input type="checkbox" checked={incremental} onChange={(e) => setIncremental(e.target.checked)} />Incrémental</label>
          <button type="submit" className={btnDark}>Ajouter</button>
        </div>
        {incremental ? <div className="sm:col-span-4"><label className={labelCls}>Champ curseur</label><input className={field} value={cursor} onChange={(e) => setCursor(e.target.value)} placeholder="updated_at" /></div> : null}
      </form>

      <div className="overflow-hidden rounded-[24px]" style={glass}>
        <table className="w-full border-collapse text-[13.5px]">
          <thead><tr className="text-left text-[11px] font-bold uppercase tracking-[0.1em] text-[#8A9291]"><th className="px-5 py-4">Endpoint</th><th className="px-3 py-4">Chemin</th><th className="px-3 py-4">Méthode</th><th className="px-3 py-4">Incrémental</th><th className="px-5 py-4 text-right">Actions</th></tr></thead>
          <tbody>
            {(endpoints ?? []).map((ep) => (
              <tr key={ep.id} className="border-t border-[#E2E6E2]/80">
                <td className="px-5 py-3.5 font-bold text-[#16191A]">{ep.name}</td>
                <td className="px-3 py-3.5 text-[#52595A]">{ep.path || "—"}</td>
                <td className="px-3 py-3.5 text-[#52595A]">{ep.http_method}</td>
                <td className="px-3 py-3.5 text-[#52595A]">{ep.incremental ? `oui · ${ep.cursor_field || "?"}` : "non"}</td>
                <td className="px-5 py-3.5 text-right"><button type="button" onClick={() => del.mutate(ep.id)} className="rounded-full border border-[#F0C1C1] bg-[#FCEBEB] px-3 py-1.5 text-[12px] font-bold text-[#A32D2D]">Supprimer</button></td>
              </tr>
            ))}
            {endpoints && endpoints.length === 0 ? <tr><td colSpan={5} className="px-5 py-6 text-center text-[13px] text-[#9AA09D]">Aucun endpoint. Ajoutez-en un ci-dessus.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MappingTab({ connectorId }: { connectorId?: string }) {
  const { data: endpoints } = useEndpoints(connectorId);
  const [endpointId, setEndpointId] = React.useState<string>("");
  React.useEffect(() => { if (!endpointId && endpoints && endpoints.length) setEndpointId(endpoints[0].id); }, [endpoints, endpointId]);
  const { data: mappings } = useMappings(endpointId || undefined);
  const create = useCreateMapping();
  const del = useDeleteMapping();
  const [src, setSrc] = React.useState("");
  const [tgt, setTgt] = React.useState("");
  const [table, setTable] = React.useState("");
  const [isKey, setIsKey] = React.useState(false);

  const add = (e: React.FormEvent) => {
    e.preventDefault();
    if (!endpointId || !src || !tgt) return;
    create.mutate({ endpoint: endpointId, source_field: src, target_field: tgt, target_table: table, is_key: isKey }, { onSuccess: () => { setSrc(""); setTgt(""); setTable(""); setIsKey(false); } });
  };

  if (!endpoints || endpoints.length === 0) {
    return <div className="rounded-[24px] px-6 py-8 text-center text-[13px] text-[#777C7D]" style={glass}>Créez d'abord un endpoint dans l'onglet « Endpoints » pour mapper ses champs.</div>;
  }

  return (
    <div className="grid gap-5">
      <div className="flex items-center gap-3 rounded-[20px] px-5 py-3" style={glass}>
        <label className="text-[12px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">Endpoint</label>
        <select className="h-10 rounded-xl border border-[#DDE2E0] bg-white/80 px-3 text-[14px]" value={endpointId} onChange={(e) => setEndpointId(e.target.value)}>
          {endpoints.map((ep) => <option key={ep.id} value={ep.id}>{ep.name}</option>)}
        </select>
      </div>

      <form onSubmit={add} className="grid gap-4 rounded-[24px] p-6 sm:grid-cols-[1fr_1fr_1fr_auto]" style={glass}>
        <div><label className={labelCls}>Champ source</label><input className={field} value={src} onChange={(e) => setSrc(e.target.value)} placeholder="employee_id" required /></div>
        <div><label className={labelCls}>Champ cible</label><input className={field} value={tgt} onChange={(e) => setTgt(e.target.value)} placeholder="employee_key" required /></div>
        <div><label className={labelCls}>Table cible (mart)</label><input className={field} value={table} onChange={(e) => setTable(e.target.value)} placeholder="warehouse.dim_employee" /></div>
        <div className="flex flex-col justify-end gap-2">
          <label className="flex items-center gap-2 text-[12px] font-semibold text-[#2C3132]"><input type="checkbox" checked={isKey} onChange={(e) => setIsKey(e.target.checked)} />Clé</label>
          <button type="submit" className={btnDark}>Mapper</button>
        </div>
      </form>

      <div className="overflow-hidden rounded-[24px]" style={glass}>
        <table className="w-full border-collapse text-[13.5px]">
          <thead><tr className="text-left text-[11px] font-bold uppercase tracking-[0.1em] text-[#8A9291]"><th className="px-5 py-4">Source</th><th className="px-3 py-4">→ Cible</th><th className="px-3 py-4">Table</th><th className="px-3 py-4">Clé</th><th className="px-5 py-4 text-right">Actions</th></tr></thead>
          <tbody>
            {(mappings ?? []).map((m) => (
              <tr key={m.id} className="border-t border-[#E2E6E2]/80">
                <td className="px-5 py-3.5 font-semibold text-[#16191A]">{m.source_field}</td>
                <td className="px-3 py-3.5 text-[#52595A]">{m.target_field}</td>
                <td className="px-3 py-3.5 text-[#9AA09D]">{m.target_table || "—"}</td>
                <td className="px-3 py-3.5 text-[#52595A]">{m.is_key ? "🔑" : ""}</td>
                <td className="px-5 py-3.5 text-right"><button type="button" onClick={() => del.mutate(m.id)} className="rounded-full border border-[#F0C1C1] bg-[#FCEBEB] px-3 py-1.5 text-[12px] font-bold text-[#A32D2D]">Supprimer</button></td>
              </tr>
            ))}
            {mappings && mappings.length === 0 ? <tr><td colSpan={5} className="px-5 py-6 text-center text-[13px] text-[#9AA09D]">Aucun mapping pour cet endpoint.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const LOG_COLOR: Record<string, string> = { info: "#185FA5", warn: "#854F0B", error: "#A32D2D" };

function HistoryTab({ sourceId }: { sourceId: string }) {
  const { data: jobs } = useJobs(sourceId);
  const { data: logs } = useLogs(sourceId);
  const { data: errors } = useErrors(sourceId);
  return (
    <div className="grid gap-5">
      <div className="overflow-hidden rounded-[24px]" style={glass}>
        <div className="px-5 pt-4 text-[15px] font-bold text-[#16191A]">Historique de synchronisation</div>
        <table className="mt-2 w-full border-collapse text-[13px]">
          <thead><tr className="text-left text-[11px] font-bold uppercase tracking-[0.1em] text-[#8A9291]"><th className="px-5 py-3">Déclencheur</th><th className="px-3 py-3">Statut</th><th className="px-3 py-3">Lignes</th><th className="px-3 py-3">Message</th><th className="px-5 py-3 text-right">Date</th></tr></thead>
          <tbody>
            {(jobs ?? []).map((j) => (
              <tr key={j.id} className="border-t border-[#E2E6E2]/80">
                <td className="px-5 py-3 text-[#52595A]">{j.trigger}</td>
                <td className="px-3 py-3 font-bold" style={{ color: j.status === "success" ? "#0F6E56" : j.status === "error" ? "#A32D2D" : "#185FA5" }}>{j.status}</td>
                <td className="px-3 py-3 text-[#52595A]">{j.rows_ingested}</td>
                <td className="px-3 py-3 text-[#777C7D]">{j.message}</td>
                <td className="px-5 py-3 text-right text-[#9AA09D]">{new Date(j.created_at).toLocaleString("fr-FR")}</td>
              </tr>
            ))}
            {jobs && jobs.length === 0 ? <tr><td colSpan={5} className="px-5 py-6 text-center text-[13px] text-[#9AA09D]">Aucune synchronisation.</td></tr> : null}
          </tbody>
        </table>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-[24px] p-5" style={glass}>
          <div className="text-[15px] font-bold text-[#16191A]">Logs</div>
          <ul className="mt-3 grid gap-2">
            {(logs ?? []).slice(0, 20).map((l) => (
              <li key={l.id} className="flex gap-3 text-[12.5px]">
                <span className="font-bold uppercase" style={{ color: LOG_COLOR[l.level] ?? "#52595A" }}>{l.level}</span>
                <span className="min-w-0 flex-1 text-[#52595A]">{l.message}</span>
              </li>
            ))}
            {logs && logs.length === 0 ? <li className="text-[13px] text-[#9AA09D]">Aucun log.</li> : null}
          </ul>
        </div>
        <div className="rounded-[24px] p-5" style={glass}>
          <div className="text-[15px] font-bold text-[#16191A]">Erreurs de liaison</div>
          <ul className="mt-3 grid gap-2">
            {(errors ?? []).slice(0, 20).map((er) => (
              <li key={er.id} className="text-[12.5px] text-[#A32D2D]">{er.code ? `[${er.code}] ` : ""}{er.message}</li>
            ))}
            {errors && errors.length === 0 ? <li className="text-[13px] text-[#9AA09D]">Aucune erreur.</li> : null}
          </ul>
        </div>
      </div>
    </div>
  );
}

const TABS = [["api", "Configuration API"], ["endpoints", "Endpoints"], ["mapping", "Mapping des champs"], ["history", "Historique & logs"]];

function ConfigureForm({ id }: { id: string }) {
  const { data: source } = useSource(id);
  const [tab, setTab] = React.useState("api");
  if (!source) return <p className="text-[14px] text-[#777C7D]">Chargement…</p>;
  const connectorId = source.connector?.id;

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[22px] px-6 py-4" style={glass}>
        <div>
          <div className="text-[18px] font-bold text-[#16191A]">{source.name}</div>
          <div className="text-[12px] text-[#9AA09D]">{source.source_type_label} · {source.target_module_label ?? source.target_module}</div>
        </div>
        <StatusBadge status={source.status} />
      </div>

      <div className="flex flex-wrap gap-1.5 rounded-full p-1.5" style={glass}>
        {TABS.map(([v, l]) => (
          <button key={v} type="button" onClick={() => setTab(v)} className="rounded-full px-4 py-2 text-[13px] font-bold transition-colors" style={tab === v ? { background: "#0B0B0C", color: "#fff" } : { color: "#52595A" }}>{l}</button>
        ))}
      </div>

      {tab === "api" ? <ApiConfigTab source={source} /> : null}
      {tab === "endpoints" ? <EndpointsTab connectorId={connectorId} /> : null}
      {tab === "mapping" ? <MappingTab connectorId={connectorId} /> : null}
      {tab === "history" ? <HistoryTab sourceId={id} /> : null}
    </div>
  );
}

export function IntegrationForm() {
  const { id } = useParams();
  return (
    <IntegrationsShell title={id ? "Configurer la source" : "Ajouter une source"} subtitle={id ? undefined : "Déclarez une plateforme. Vous pourrez la configurer, déclarer ses endpoints et mapper ses champs quand son API sera prête."}>
      {id ? <ConfigureForm id={id} /> : <CreateForm />}
    </IntegrationsShell>
  );
}
