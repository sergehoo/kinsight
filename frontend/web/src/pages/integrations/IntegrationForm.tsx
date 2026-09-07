import * as React from "react";
import { createPortal } from "react-dom";
import { useNavigate, useParams } from "react-router-dom";

import { glass } from "@/components/chrome/theme";
import type { SessionAuth } from "@/types/integrations";
import { IntegrationsError, IntegrationsShell, StatusBadge } from "@/components/integrations/parts";
import {
  ApiError,
  fetchSourceBySlug,
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
  useReauthenticate,
  useTestConnection,
  useToggleActive,
  useUpdateConnector,
} from "@/lib/integrations";

// Les cinq plateformes visées d'abord ; les formats de fichier restent
// disponibles plus bas, mais ne sont pas ce qu'on branche au quotidien.
const SOURCE_TYPES: Array<[string, string]> = [
  ["kaydan_shield", "Kaydan Shield"],
  ["odoo_hr", "Odoo"],
  ["sap", "SAP"],
  ["edw", "Entrepôt de données (mart)"],
  ["rest", "API REST"],
  ["graphql", "API GraphQL"],
  ["webhook", "Webhook"],
  ["postgres", "PostgreSQL (lecture seule)"],
  ["mysql", "MySQL (lecture seule)"],
  ["airbyte", "Connecteur Airbyte"],
  ["csv", "Fichier CSV"],
  ["excel", "Excel"],
  ["gsheets", "Google Sheets"],
];

const ENVIRONMENTS: Array<[string, string]> = [
  ["production", "Production"],
  ["staging", "Recette"],
  ["sandbox", "Bac à sable"],
];
const TARGET_MODULES = [
  ["rh", "Capital Humain"], ["immobilier", "Immobilier"], ["finance", "Finance"], ["stocks", "Stocks & Logistique"],
  ["flotte", "Flotte"], ["securite", "Sécurité"], ["commercial", "Commercial & Clients"], ["risques", "Risques & Conformité"],
  ["groupe", "Groupe"], ["autre", "Autre"],
];
const AUTH_METHODS = [["none", "Aucune"], ["api_key", "Clé API"], ["bearer", "Bearer"], ["basic", "Basic"], ["oauth2", "OAuth2"], ["header", "Header"]];

/** Ce qu'un type de source implique réellement.
 *
 *  Sans ces réglages, toute source créée repartait en « API REST / Autre » : le
 *  formulaire ne savait rien du type choisi. Les valeurs ci-dessous reprennent
 *  exactement les exigences de `validate_config` côté backend — les afficher ici
 *  évite de découvrir un champ obligatoire seulement au moment du test.
 */
type TypePreset = {
  slug: string;
  module: string;
  auth: string;
  urlPlaceholder: string;
  requiresUrl: boolean;
  requiresDatabase: boolean;
  credentialKind: string;
  credentialLabel: string;
  note: string;
};

const PRESET_PAR_DEFAUT: TypePreset = {
  slug: "",
  module: "autre",
  auth: "none",
  urlPlaceholder: "https://…",
  requiresUrl: false,
  requiresDatabase: false,
  credentialKind: "api_token",
  credentialLabel: "Token API",
  note: "",
};

const TYPE_PRESETS: Record<string, Partial<TypePreset>> = {
  kaydan_shield: {
    slug: "kaydan-shield",
    module: "rh",
    auth: "bearer",
    urlPlaceholder: "https://api.kaydanshield.com/api/v1",
    requiresUrl: true,
    credentialKind: "api_token",
    credentialLabel: "Token API Shield (Bearer)",
    note:
      "Connecteur dédié — Shield alimente Capital Humain, Risques & Conformité et la vue Groupe. " +
      "Le code doit rester « kaydan-shield » : c'est par lui que le connecteur retrouve la source.",
  },
  odoo_hr: {
    slug: "odoo-hr",
    module: "rh",
    auth: "api_key",
    urlPlaceholder: "https://odoo.kaydan.tech",
    requiresUrl: true,
    requiresDatabase: true,
    credentialKind: "api_key",
    credentialLabel: "Clé API Odoo",
    note: "Odoo exige aussi le nom de la base de données : le test échouera sans lui.",
  },
  sap: {
    module: "finance",
    auth: "basic",
    urlPlaceholder: "https://sap.kaydan.tech",
    requiresUrl: true,
    credentialKind: "password",
    credentialLabel: "Mot de passe du compte de service",
    note: "",
  },
  edw: {
    module: "groupe",
    auth: "none",
    note:
      "Le mart est lu directement par le gateway en lecture seule (ADR-0004) : " +
      "ni URL ni secret à saisir ici.",
  },
  rest: { module: "autre", auth: "bearer", urlPlaceholder: "https://api.exemple.com", requiresUrl: true, note: "" },
  graphql: { module: "autre", auth: "bearer", urlPlaceholder: "https://api.exemple.com/graphql", requiresUrl: true, note: "" },
  webhook: { module: "autre", auth: "none", note: "La source pousse ses événements : aucune URL sortante à déclarer." },
};

function presetPour(type: string): TypePreset {
  return { ...PRESET_PAR_DEFAUT, ...(TYPE_PRESETS[type] ?? {}) };
}

const field = "h-11 w-full rounded-xl border border-[#DDE2E0] bg-white/80 px-4 text-[14px] text-[#1A1F1F] outline-none focus:border-[#FF8735]";
const labelCls = "mb-1.5 block text-[12px] font-bold uppercase tracking-[0.08em] text-[#8A9291]";
const btnDark = "rounded-full bg-[#0B0B0C] px-5 py-2.5 text-[13px] font-bold text-white disabled:opacity-60";
const btnGhost = "rounded-full border border-[#DDE2E0] bg-white/70 px-4 py-2 text-[12px] font-bold text-[#3A3E3E] hover:bg-white";

function slugify(s: string) {
  return s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

const ETAPES = ["Source", "Connexion", "Validation"];

function Stepper({ etape, onAller }: { etape: number; onAller: (n: number) => void }) {
  return (
    <ol className="flex flex-wrap items-center gap-2" aria-label="Étapes de création">
      {ETAPES.map((titre, i) => {
        const n = i + 1;
        const actif = n === etape;
        const passe = n < etape;
        return (
          <li key={titre} className="flex items-center gap-2">
            <button
              type="button"
              // On ne peut revenir qu'en arrière : avancer sans valider l'étape
              // courante produirait une source incomplète.
              onClick={() => (passe ? onAller(n) : undefined)}
              disabled={!passe}
              aria-current={actif ? "step" : undefined}
              className="flex items-center gap-2 rounded-full px-3.5 py-2 text-[13px] font-bold transition-colors disabled:cursor-default"
              style={actif ? { background: "#0B0B0C", color: "#fff" } : { color: passe ? "#0F6E56" : "#9AA09D" }}
            >
              <span
                className="grid h-5 w-5 place-items-center rounded-full text-[11px] font-bold"
                style={actif ? { background: "#FF8735", color: "#fff" } : { background: passe ? "#E1F5EE" : "#EEF0F0", color: passe ? "#0F6E56" : "#9AA09D" }}
              >
                {passe ? "✓" : n}
              </span>
              {titre}
            </button>
            {n < ETAPES.length ? <span className="h-px w-6 bg-[#DDE2E0]" aria-hidden /> : null}
          </li>
        );
      })}
    </ol>
  );
}

type Verdict = { ok: boolean; message: string; status: string; latency_ms?: number | null };

/** Où la chaîne s'est arrêtée. Sans cette information, un échec du test Shield
 *  s'affichait « Backend en erreur » alors que le backend avait parfaitement
 *  répondu et que la source était bel et bien créée. */
type Etape = "creation" | "connecteur" | "secret" | "test";

const LIBELLE_ETAPE: Record<Etape, { titre: string; acquis: string }> = {
  creation: { titre: "Échec de la création de la source", acquis: "" },
  connecteur: { titre: "Échec de la configuration du connecteur", acquis: "Source créée" },
  secret: { titre: "Échec de l'enregistrement du secret", acquis: "Source créée · connecteur configuré" },
  test: { titre: "Échec du test de connexion", acquis: "Source créée · connecteur configuré · secret enregistré" },
};

/** « Échec du test Kaydan Shield » situe la panne mieux que « test de connexion ». */
function titreEtape(etape: Etape, typeLabel: string) {
  const base = LIBELLE_ETAPE[etape];
  const titre = etape === "test" ? `Échec du test ${typeLabel}` : base.titre;
  return base.acquis ? `${base.acquis} · ${titre}` : titre;
};

/** Un échec dont on ne sait pas s'il a atteint le serveur : la requête est
 *  peut-être passée, seule la réponse manque. C'est le cas d'un 502 émis par le
 *  proxy et de toute coupure réseau. */
function estAmbigu(error: unknown) {
  if (!(error instanceof ApiError)) return true; // pas de réponse du tout
  return error.status === 502 || error.status === 503 || error.status === 504;
}

function CreateForm() {
  const navigate = useNavigate();
  const create = useCreateSource();
  const updateConnector = useUpdateConnector();
  const addCredential = useAddCredential();
  const test = useTestConnection();

  // Étape 1 — identité de la source.
  const [name, setName] = React.useState("");
  const [code, setCode] = React.useState("kaydan-shield");
  const [codeTouche, setCodeTouche] = React.useState(false);
  const [sourceType, setSourceType] = React.useState("kaydan_shield");
  const [environment, setEnvironment] = React.useState("production");
  const [target, setTarget] = React.useState("rh");
  const [description, setDescription] = React.useState("");

  // Étape 2 — connexion.
  const [baseUrl, setBaseUrl] = React.useState("");
  const [auth, setAuth] = React.useState("bearer");
  const [secret, setSecret] = React.useState("");
  const [database, setDatabase] = React.useState("");
  const [frequency, setFrequency] = React.useState("manual");
  // Le mode démo est un mode DÉGRADÉ : il laisse une source non connectée se
  // comporter comme si elle l'était. Il doit rester une décision explicite,
  // jamais un défaut — sinon un écran affiche des chiffres que personne n'a mesurés.
  const [demo, setDemo] = React.useState(false);

  // Étape 3 — création puis test réel.
  const [etape, setEtape] = React.useState(1);
  const [sourceCreee, setSourceCreee] = React.useState<{ id: string; connectorId?: string } | null>(null);
  const [enCours, setEnCours] = React.useState(false);
  const [echec, setEchec] = React.useState<{ etape: Etape; erreur: unknown } | null>(null);
  const [creationAmbigue, setCreationAmbigue] = React.useState(false);
  // Une source portant déjà ce code : on la propose à l'ouverture plutôt que de
  // laisser l'utilisateur devant un « corrigez les champs » sans issue.
  const [sourceHomonyme, setSourceHomonyme] = React.useState<{ id: string; name: string } | null>(null);
  const [verdict, setVerdict] = React.useState<Verdict | null>(null);

  const preset = presetPour(sourceType);
  const shield = sourceType === "kaydan_shield";

  const changerType = (valeur: string) => {
    const p = presetPour(valeur);
    setSourceType(valeur);
    setTarget(p.module);
    setAuth(p.auth);
    // Le code suit le type tant que l'utilisateur ne l'a pas écrit lui-même.
    if (!codeTouche) setCode(p.slug || slugify(name));
  };

  const codeFinal = code.trim() || preset.slug || slugify(name);
  const etape1Ok = name.trim().length > 0 && codeFinal.length > 0;
  const etape2Ok = (!preset.requiresUrl || baseUrl.trim().length > 0) && (!preset.requiresDatabase || database.trim().length > 0);

  /** Crée la source, configure le connecteur, dépose le secret, puis teste.
   *
   *  Si une étape échoue après la création, la source déjà créée est conservée
   *  (`sourceCreee`) : réessayer ne doit pas produire un doublon ni buter sur un
   *  code déjà pris.
   */
  const creerEtTester = async () => {
    setEnCours(true);
    setEchec(null);
    setVerdict(null);
    setSourceHomonyme(null);
    let etape: Etape = "creation";
    try {
      let cible = sourceCreee;
      if (!cible) {
        let source: { id: string; connector?: { id: string } };
        try {
          source = await create.mutateAsync({
            name: name.trim(),
            slug: codeFinal,
            source_type: sourceType,
            environment,
            target_module: target,
            sync_frequency: frequency.trim() || "manual",
            demo_mode: demo,
            description,
          });
        } catch (e) {
          // Rattrapage du cas ambigu : un essai précédent s'est peut-être écrit
          // côté serveur sans que la réponse revienne. Le code est alors « déjà
          // pris »… par nous. On reprend cette source au lieu d'échouer, et sans
          // jamais créer de doublon.
          const conflitDeCode =
            e instanceof ApiError && e.status === 400 && Boolean(e.details && "slug" in e.details);
          if (!(conflitDeCode && creationAmbigue)) {
            if (estAmbigu(e)) setCreationAmbigue(true);
            // Code déjà pris sur un premier essai : ce n'est pas notre orpheline,
            // c'est une source qui existe. La nommer et l'offrir à l'ouverture vaut
            // mieux que « corrigez les champs signalés » — d'autant que le
            // connecteur Shield résout SA source par ce code exact, donc la bonne
            // action est presque toujours de modifier celle-là.
            if (conflitDeCode) {
              const existante = await fetchSourceBySlug(codeFinal).catch(() => undefined);
              if (existante) setSourceHomonyme({ id: existante.id, name: existante.name });
            }
            throw e;
          }
          const existante = await fetchSourceBySlug(codeFinal);
          if (!existante) throw e;
          source = existante;
        }
        cible = { id: source.id, connectorId: source.connector?.id };
        setSourceCreee(cible);
        setCreationAmbigue(false);
      }

      if (cible.connectorId) {
        etape = "connecteur";
        const config: Record<string, unknown> = {};
        if (preset.requiresDatabase && database.trim()) config.database = database.trim();
        await updateConnector.mutateAsync({
          id: cible.connectorId,
          patch: { base_url: baseUrl.trim(), auth_method: auth, config },
        });
        if (secret.trim()) {
          etape = "secret";
          await addCredential.mutateAsync({
            connector: cible.connectorId,
            kind: preset.credentialKind,
            label: preset.credentialLabel,
            secret: secret.trim(),
          });
          // Le secret ne survit pas à son envoi : ni state, ni storage, ni log.
          setSecret("");
        }
      }

      etape = "test";
      setVerdict(await test.mutateAsync(cible.id));
    } catch (e) {
      setEchec({ etape, erreur: e });
    } finally {
      setEnCours(false);
    }
  };

  /** Revenir en arrière EFFACE le verdict et l'erreur.
   *
   *  Sinon l'écran ment deux fois : le bandeau « Backend en erreur » reste
   *  affiché sous les champs des étapes 1 et 2, et un verdict obtenu avec
   *  l'ancienne URL continue de décrire une configuration qu'on vient de
   *  modifier. La source déjà créée, elle, est conservée : le réessai la reprend.
   */
  const allerA = (n: number) => {
    setEtape(n);
    setEchec(null);
    setVerdict(null);
  };

  const suivant = (e: React.FormEvent) => {
    e.preventDefault();
    if (etape === 1 && etape1Ok) setEtape(2);
    else if (etape === 2 && etape2Ok) setEtape(3);
  };

  return (
    <div className="grid max-w-[820px] gap-5">
      <div className="rounded-[20px] px-5 py-4" style={glass}>
        <Stepper etape={etape} onAller={allerA} />
      </div>

      <form onSubmit={suivant} className="grid gap-5 rounded-[24px] p-7" style={glass}>
        {etape === 1 ? (
          <>
            <div>
              <label className={labelCls} htmlFor="src-nom">Nom de la plateforme</label>
              <input id="src-nom" className={field} value={name} onChange={(e) => setName(e.target.value)} placeholder="Kaydan Shield, Odoo RH, CRM…" required autoFocus />
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label className={labelCls} htmlFor="src-type">Type de source</label>
                <select id="src-type" className={field} value={sourceType} onChange={(e) => changerType(e.target.value)}>
                  {SOURCE_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
                {preset.note ? <p className="mt-1.5 text-[11.5px] leading-relaxed text-[#6E7A78]">{preset.note}</p> : null}
              </div>
              <div>
                <label className={labelCls} htmlFor="src-code">Code</label>
                <input
                  id="src-code"
                  className={field}
                  value={code}
                  onChange={(e) => { setCodeTouche(true); setCode(slugify(e.target.value)); }}
                  placeholder={preset.slug || slugify(name) || "ma-source"}
                />
                <p className="mt-1 text-[11px] text-[#9AA09D]">
                  {shield ? "Le connecteur Shield attend exactement « kaydan-shield »." : "Identifiant technique, non modifiable ensuite."}
                </p>
              </div>
              <div>
                <label className={labelCls} htmlFor="src-env">Environnement</label>
                <select id="src-env" className={field} value={environment} onChange={(e) => setEnvironment(e.target.value)}>
                  {ENVIRONMENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className={labelCls} htmlFor="src-module">Module cible</label>
                <select id="src-module" className={field} value={target} onChange={(e) => setTarget(e.target.value)}>
                  {TARGET_MODULES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className={labelCls} htmlFor="src-desc">Description</label>
              <textarea id="src-desc" className="min-h-[80px] w-full rounded-xl border border-[#DDE2E0] bg-white/80 px-4 py-3 text-[14px] outline-none focus:border-[#FF8735]" value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </>
        ) : null}

        {etape === 2 ? (
          <>
            {preset.requiresUrl ? (
              <div>
                <label className={labelCls} htmlFor="cnx-url">URL de base</label>
                <input id="cnx-url" className={field} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder={preset.urlPlaceholder} required />
              </div>
            ) : (
              <p className="rounded-[16px] border border-[#DDE6E2] bg-white/60 px-4 py-3 text-[13px] text-[#52595A]">
                Ce type de source n'appelle aucune URL sortante. {preset.note}
              </p>
            )}
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label className={labelCls} htmlFor="cnx-auth">Authentification</label>
                <select id="cnx-auth" className={field} value={auth} onChange={(e) => setAuth(e.target.value)}>
                  {AUTH_METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className={labelCls} htmlFor="cnx-secret">{preset.credentialLabel}</label>
                <input
                  id="cnx-secret"
                  className={field}
                  type="password"
                  autoComplete="new-password"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  placeholder={auth === "none" ? "Aucun secret requis" : "Collez le secret (chiffré en base)"}
                  disabled={auth === "none"}
                />
              </div>
              {preset.requiresDatabase ? (
                <div>
                  <label className={labelCls} htmlFor="cnx-db">Base de données</label>
                  <input id="cnx-db" className={field} value={database} onChange={(e) => setDatabase(e.target.value)} placeholder="kaydan_prod" required />
                </div>
              ) : null}
              <div>
                <label className={labelCls} htmlFor="cnx-freq">Fréquence de synchronisation</label>
                <input id="cnx-freq" className={field} value={frequency} onChange={(e) => setFrequency(e.target.value)} placeholder="manual ou cron (ex. 0 */6 * * *)" />
              </div>
            </div>
            <p className="text-[11.5px] leading-relaxed text-[#6E7A78]">
              Le secret part directement au backend, y est chiffré au repos et n'est jamais renvoyé en clair.
              Il n'est stocké ni dans le navigateur, ni dans les journaux, ni dans le cache de l'application.
            </p>
            <label className="flex items-start gap-3 rounded-[16px] border border-[#EFE3CE] bg-[#FDF6EA] px-4 py-3 text-[13px] font-semibold text-[#6B4E1E]">
              <input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} className="mt-0.5 h-4 w-4" />
              <span>
                Activer le mode démo (dégradé)
                <span className="mt-0.5 block font-medium text-[#8A6E36]">
                  Désactivé par défaut. Tant qu'il est désactivé, une source non connectée reste « déconnectée »
                  et n'affiche aucune donnée simulée.
                </span>
              </span>
            </label>
          </>
        ) : null}

        {etape === 3 ? (
          <>
            <dl className="grid gap-x-6 gap-y-3 rounded-[18px] border border-[#E2E6E2] bg-white/60 px-5 py-4 text-[13.5px] sm:grid-cols-2">
              {[
                ["Nom", name],
                ["Code", codeFinal],
                ["Type", SOURCE_TYPES.find(([v]) => v === sourceType)?.[1] ?? sourceType],
                ["Environnement", ENVIRONMENTS.find(([v]) => v === environment)?.[1] ?? environment],
                ["Module cible", TARGET_MODULES.find(([v]) => v === target)?.[1] ?? target],
                ["URL de base", baseUrl || "—"],
                ["Authentification", AUTH_METHODS.find(([v]) => v === auth)?.[1] ?? auth],
                ["Secret fourni", secret.trim() ? "oui (masqué)" : "non"],
                ["Mode démo", demo ? "activé" : "désactivé"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 border-b border-[#EDF0EE] pb-2 last:border-0">
                  <dt className="text-[#8A9291]">{k}</dt>
                  <dd className="text-right font-semibold text-[#16191A]">{v}</dd>
                </div>
              ))}
            </dl>

            {verdict ? (
              <div
                className="rounded-[18px] border px-5 py-4"
                style={verdict.ok
                  ? { borderColor: "#BEE6D8", background: "#E1F5EE" }
                  : { borderColor: "#F0D2D2", background: "#FCEBEB" }}
              >
                <p className="text-[14px] font-bold" style={{ color: verdict.ok ? "#0F6E56" : "#A32D2D" }}>
                  {verdict.ok ? "Connexion établie" : "Connexion refusée"}
                  {verdict.latency_ms != null ? ` · ${verdict.latency_ms} ms` : ""}
                </p>
                <p className="mt-1 text-[13px] font-medium leading-relaxed" style={{ color: verdict.ok ? "#2C6354" : "#8C4141" }}>
                  {verdict.message}
                </p>
                {!verdict.ok ? (
                  <p className="mt-1.5 text-[12.5px] font-semibold text-[#8C4141]">
                    La source est enregistrée mais reste déconnectée : aucune donnée ne sera affichée tant que
                    le test n'aboutit pas. Corrigez la connexion puis relancez le test depuis sa fiche.
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="text-[13px] leading-relaxed text-[#52595A]">
                La source va être créée, son connecteur configuré, puis la connexion réellement testée
                depuis le serveur. Le verdict s'affiche ici avant l'ouverture de la fiche.
              </p>
            )}

            {sourceCreee && !verdict ? (
              <p className="text-[12.5px] font-semibold text-[#854F0B]">
                La source a été créée ; l'étape suivante a échoué. Réessayer reprendra là où ça s'est arrêté,
                sans créer de doublon.
              </p>
            ) : null}
          </>
        ) : null}

        {echec ? (
          <div className="grid gap-2">
            <div className="rounded-[18px] border border-[#EFE3CE] bg-[#FDF6EA] px-5 py-3">
              <p className="text-[13.5px] font-bold text-[#6B4E1E]">
                {titreEtape(echec.etape, SOURCE_TYPES.find(([v]) => v === sourceType)?.[1] ?? "de connexion")}
              </p>
              {echec.etape !== "creation" ? (
                <p className="mt-0.5 text-[12.5px] font-medium text-[#8A6E36]">
                  Les étapes précédentes ont abouti : la source existe et reste consultable. Seule celle-ci a échoué.
                </p>
              ) : null}
            </div>
            <IntegrationsError error={echec.erreur} />
            {sourceHomonyme ? (
              <div className="rounded-[18px] border border-[#DDE6E2] bg-white/70 px-5 py-3">
                <p className="text-[13px] font-semibold text-[#2C3132]">
                  Le code « {codeFinal} » est déjà porté par la source «&nbsp;{sourceHomonyme.name}&nbsp;».
                </p>
                <p className="mt-0.5 text-[12.5px] font-medium text-[#6E7A78]">
                  {shield
                    ? "Le connecteur Shield résout sa source par ce code : c'est cette fiche qu'il faut corriger, pas une seconde source."
                    : "Modifiez cette source, ou choisissez un autre code."}
                </p>
                <button
                  type="button"
                  onClick={() => navigate(`/admin/integrations/${sourceHomonyme.id}`)}
                  className={btnGhost + " mt-2"}
                >
                  Ouvrir «&nbsp;{sourceHomonyme.name}&nbsp;»
                </button>
              </div>
            ) : null}
            {sourceCreee ? (
              <button
                type="button"
                onClick={() => navigate(`/admin/integrations/${sourceCreee.id}`)}
                className={btnGhost + " justify-self-start"}
              >
                Ouvrir la fiche de la source
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-3">
          {etape > 1 ? (
            <button type="button" onClick={() => allerA(etape - 1)} className={btnGhost}>Retour</button>
          ) : null}
          {etape < 3 ? (
            <button type="submit" disabled={etape === 1 ? !etape1Ok : !etape2Ok} className="rounded-full bg-[#0B0B0C] px-6 py-3 text-[14px] font-bold text-white disabled:opacity-40">
              Continuer
            </button>
          ) : verdict ? (
            <button type="button" onClick={() => navigate(`/admin/integrations/${sourceCreee?.id}`)} className="rounded-full bg-[#0B0B0C] px-6 py-3 text-[14px] font-bold text-white">
              Ouvrir la fiche de la source
            </button>
          ) : (
            <button type="button" onClick={creerEtTester} disabled={enCours} className="rounded-full bg-[#0B0B0C] px-6 py-3 text-[14px] font-bold text-white disabled:opacity-60">
              {enCours ? "Création et test…" : sourceCreee ? "Réessayer" : "Créer et tester la connexion"}
            </button>
          )}
          <button type="button" onClick={() => navigate("/admin/integrations")} className="rounded-full border border-[#DDE2E0] bg-white/70 px-6 py-3 text-[14px] font-bold text-[#3A3E3E]">
            {verdict ? "Fermer" : "Annuler"}
          </button>
        </div>
      </form>
    </div>
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


/** Ce que la fiche dit de la session Shield.
 *
 *  Le point de la mission : ne JAMAIS réclamer un collage manuel de jeton quand le
 *  renouvellement automatique suffit. Un access expiré avec un refresh vivant est
 *  annoncé « connecté », parce que le prochain appel le renouvellera de lui-même ;
 *  « réauthentification requise » est réservé au cas où le refresh ne peut plus rien.
 */
function badgeDeSession(auth: SessionAuth | null | undefined, statutSource: string) {
  if (!auth) return null;
  if (auth.etat === "auth_required") {
    return { texte: "Réauthentification requise", fond: "#FCEBEB", couleur: "#A32D2D" };
  }
  if (statutSource === "error") {
    return { texte: "Erreur réseau", fond: "#FAEEDA", couleur: "#854F0B" };
  }
  return { texte: "Connecté", fond: "#E1F5EE", couleur: "#0F6E56" };
}

function dateCourte(valeur: string | null | undefined) {
  return valeur ? new Date(valeur).toLocaleString("fr-FR") : "—";
}

/** Les causes techniques du backend, dites en français.
 *
 *  Afficher `refresh_refuse` tel quel à un DRH ne lui apprend rien et ne lui dit
 *  pas quoi faire. La cause brute reste utile côté journaux ; l'écran, lui, doit
 *  nommer le geste.
 */
const CAUSES: Record<string, string> = {
  refresh_refuse: "le jeton de renouvellement a été refusé par Shield (expiré ou révoqué)",
  refresh_absent: "aucun jeton de renouvellement n'était enregistré",
  quota_refresh: "Shield a limité le débit des renouvellements",
  base_absente: "l'URL de base du connecteur est vide",
  certificats_invalides: "le certificat TLS de Shield n'a pas pu être vérifié depuis le serveur",
  access_absent_de_la_reponse: "Shield a répondu sans jeton d'accès",
  reponse_illisible: "la réponse de Shield était illisible",
};

function causeLisible(cause: string) {
  if (CAUSES[cause]) return CAUSES[cause];
  if (cause.startsWith("reseau_")) return "Shield était injoignable depuis le serveur";
  if (cause.startsWith("http_")) return `Shield a répondu ${cause.slice(5)}`;
  return cause;
}

/** Pourquoi le renouvellement automatique ne joue pas — et ce n'est pas la même
 *  chose de n'avoir aucun jeton de renouvellement et d'en avoir un que Shield
 *  refuse : le premier n'a jamais été déposé, le second doit être remplacé. */
function raisonSansRenouvellement(auth: SessionAuth) {
  if (!auth.refresh_present) {
    return "Renouvellement automatique inactif : sans jeton de renouvellement, la session expirera sans recours.";
  }
  if (auth.cause_dernier_echec === "refresh_refuse") {
    return "Renouvellement automatique interrompu : le jeton de renouvellement enregistré est refusé par Shield. Il faut recoller un couple neuf.";
  }
  return "Renouvellement automatique indisponible pour le moment — voir la cause ci-dessous.";
}

function SessionShield({ auth, statutSource }: { auth: SessionAuth; statutSource: string }) {
  const badge = badgeDeSession(auth, statutSource);
  // « Valide jusqu'au 22:57 » à 23:05 se lit comme une session vivante alors
  // qu'elle est morte : la même date doit changer de phrase quand elle passe.
  const depasse = Boolean(auth.expire_le) && new Date(auth.expire_le as string) <= new Date();
  const expire = !auth.expiration_connue
    ? "Échéance de session inconnue — la source tranchera au prochain appel"
    : depasse
      ? `Session expirée depuis le ${dateCourte(auth.expire_le)}`
      : `Session valide jusqu'au ${dateCourte(auth.expire_le)}`;

  return (
    <div className="grid gap-2 rounded-[18px] border border-[#DDE6E2] bg-white/60 px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">
          Session Kaydan Shield
        </p>
        {badge ? (
          <span className="rounded-full px-3 py-1 text-[12px] font-bold"
                style={{ background: badge.fond, color: badge.couleur }}>
            {badge.texte}
          </span>
        ) : null}
      </div>

      <p className="text-[13.5px] font-semibold text-[#2C3132]">{expire}</p>

      <p className="text-[12.5px] font-medium" style={{ color: auth.renouvellement_automatique ? "#0F6E56" : "#854F0B" }}>
        {auth.renouvellement_automatique
          ? "Renouvellement automatique actif — aucun jeton à recoller à l'expiration."
          : raisonSansRenouvellement(auth)}
      </p>

      <dl className="grid gap-x-6 gap-y-1 text-[12.5px] sm:grid-cols-2">
        <div className="flex justify-between gap-3">
          <dt className="text-[#8A9291]">Dernière authentification</dt>
          <dd className="font-semibold text-[#2C3132]">{dateCourte(auth.derniere_authentification)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-[#8A9291]">Jeton de renouvellement</dt>
          <dd className="font-semibold text-[#2C3132]">{auth.refresh_present ? "enregistré" : "absent"}</dd>
        </div>
      </dl>

      {auth.cause_dernier_echec ? (
        <p className="text-[12.5px] font-semibold text-[#A32D2D]">
          Dernier échec d'authentification ({dateCourte(auth.dernier_echec)}) : {causeLisible(auth.cause_dernier_echec)}.
        </p>
      ) : null}
    </div>
  );
}

/** Dépôt d'un couple de jetons.
 *
 *  Les deux champs sont de type `password` et jamais préremplis ; leur valeur ne
 *  vit que dans l'état de ce composant, et disparaît à la fermeture. Rien n'est
 *  écrit en `localStorage`, `sessionStorage` ni dans le cache de l'application —
 *  un jeton copié dans le navigateur y survivrait à toutes les rotations.
 */
function ModaleReauth({ sourceId, onFerme, onSucces }: {
  sourceId: string;
  onFerme: () => void;
  onSucces: (message: string) => void;
}) {
  const reauth = useReauthenticate();
  const [acces, setAcces] = React.useState("");
  const [refresh, setRefresh] = React.useState("");

  const oublier = () => {
    setAcces("");
    setRefresh("");
  };

  const fermer = () => {
    oublier();
    onFerme();
  };

  const complet = acces.trim().length > 0 && refresh.trim().length > 0;

  const envoyer = (e: React.FormEvent) => {
    e.preventDefault();
    if (!complet) return;
    reauth.mutate(
      { sourceId, access: acces.trim(), refresh: refresh.trim() },
      {
        onSuccess: (r) => {
          // Le secret quitte la mémoire dès que le backend l'a chiffré.
          oublier();
          onSucces(r.message || "Session déposée.");
          onFerme();
        },
      },
    );
  };

  // La fiche source porte `backdrop-filter: blur(18px)` : ce filtre fait d'elle un
  // bloc conteneur, si bien qu'un `position: fixed` posé à l'intérieur se cale sur
  // la carte au lieu de la fenêtre. La boîte de dialogue s'ouvrait alors dans le
  // flux de la carte, hors de l'écran, et paraissait ne pas s'ouvrir du tout. Le
  // portail la sort de cette hiérarchie : le voile couvre à nouveau la page.
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
         role="dialog" aria-modal="true" aria-label="Réauthentifier Kaydan Shield">
      <form onSubmit={envoyer} className="grid w-full max-w-[560px] gap-4 rounded-[24px] bg-[#F7F9F6] p-7 shadow-[0_30px_80px_rgba(0,0,0,0.3)]">
        <div>
          <h2 className="text-[19px] font-bold text-[#16191A]">Réauthentifier Kaydan Shield</h2>
          <p className="mt-1 text-[13px] font-medium leading-relaxed text-[#6E7A78]">
            Collez le couple obtenu auprès de Shield. Les deux jetons sont nécessaires :
            un jeton d'accès seul redonnerait une session qui expire sans recours — exactement
            ce que le renouvellement automatique évite.
          </p>
        </div>

        <div>
          <label className={labelCls} htmlFor="reauth-access">Jeton d'accès (access)</label>
          <input id="reauth-access" className={field} type="password" autoComplete="off"
                 value={acces} onChange={(e) => setAcces(e.target.value)} required autoFocus
                 placeholder="Collez le jeton d'accès" />
        </div>
        <div>
          <label className={labelCls} htmlFor="reauth-refresh">Jeton de renouvellement (refresh)</label>
          <input id="reauth-refresh" className={field} type="password" autoComplete="off"
                 value={refresh} onChange={(e) => setRefresh(e.target.value)} required
                 placeholder="Collez le jeton de renouvellement" />
        </div>

        <p className="text-[11.5px] leading-relaxed text-[#6E7A78]">
          Les jetons partent directement au backend, y sont chiffrés au repos et ne sont jamais
          réaffichés. Ils ne sont écrits ni dans le navigateur, ni dans les journaux, ni dans le
          cache de l'application.
        </p>

        {reauth.isError ? <IntegrationsError error={reauth.error} /> : null}
        {reauth.data && !reauth.data.ok ? (
          <p className="text-[12.5px] font-semibold text-[#A32D2D]">{reauth.data.message}</p>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <button type="submit" disabled={!complet || reauth.isPending}
                  className="rounded-full bg-[#0B0B0C] px-6 py-3 text-[14px] font-bold text-white disabled:opacity-40">
            {reauth.isPending ? "Dépôt en cours…" : "Déposer la session"}
          </button>
          <button type="button" onClick={fermer}
                  className="rounded-full border border-[#DDE2E0] bg-white/70 px-6 py-3 text-[14px] font-bold text-[#3A3E3E]">
            Annuler
          </button>
        </div>
      </form>
    </div>,
    document.body,
  );
}

function ConfigureForm({ id }: { id: string }) {
  const { data: source, isLoading, isError, error } = useSource(id);
  const test = useTestConnection();
  const toggle = useToggleActive();
  const reauthAuto = useReauthenticate();
  const [tab, setTab] = React.useState("api");
  const [modaleOuverte, setModaleOuverte] = React.useState(false);
  const [avis, setAvis] = React.useState<string | null>(null);

  if (isError) return <IntegrationsError error={error} />;
  if (isLoading || !source) return <p className="text-[14px] text-[#777C7D]">Chargement…</p>;

  const connectorId = source.connector?.id;
  const connector = source.connector;
  const creds = connector?.credentials ?? [];
  const dernierTest = connector?.last_tested_at ? new Date(connector.last_tested_at).toLocaleString("fr-FR") : "jamais testée";
  const latence = connector?.last_latency_ms;
  const auth = connector?.session_auth ?? null;
  // `auth_required` est le SEUL cas où l'on réclame une intervention : partout
  // ailleurs le renouvellement automatique s'en charge.
  const reauthNecessaire = auth?.etat === "auth_required";

  return (
    <div className="grid gap-5">
      <div className="grid gap-4 rounded-[22px] px-6 py-5" style={glass}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[18px] font-bold text-[#16191A]">{source.name}</div>
            <div className="text-[12px] text-[#9AA09D]">
              {source.source_type_label} · {source.target_module_label ?? source.target_module}
              {source.environment_label ? ` · ${source.environment_label}` : ""} · code « {source.slug} »
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={source.status} />
            {/* Le mode démo se voit : une source dégradée ne doit pas passer pour une source connectée. */}
            {source.demo_mode ? (
              <span className="rounded-full bg-[#FDF6EA] px-3 py-1 text-[12px] font-bold text-[#854F0B]">Mode démo</span>
            ) : null}
          </div>
        </div>

        <dl className="grid gap-x-6 gap-y-2 text-[13px] sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">Dernière vérification</dt><dd className="font-semibold text-[#2C3132]">{dernierTest}</dd></div>
          <div><dt className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">Latence</dt><dd className="font-semibold text-[#2C3132]">{latence != null ? `${latence} ms` : "—"}</dd></div>
          <div><dt className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">URL de base</dt><dd className="truncate font-semibold text-[#2C3132]">{connector?.base_url || "—"}</dd></div>
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">Secrets</dt>
            <dd className="font-semibold text-[#2C3132]">
              {/* Seul le masque circule : le clair ne quitte jamais le backend. */}
              {creds.length ? creds.map((c) => `${c.label || c.kind} · ${c.masked}`).join(", ") : "aucun"}
            </dd>
          </div>
        </dl>

        {connector?.last_test_message ? (
          <p className="text-[12.5px] font-semibold" style={{ color: connector.last_test_ok ? "#0F6E56" : "#A32D2D" }}>
            {connector.last_test_message}
          </p>
        ) : null}

        {auth ? <SessionShield auth={auth} statutSource={source.status} /> : null}

        <div className="flex flex-wrap items-center gap-2">
          {/* Quand la session est morte, réauthentifier passe en action principale :
              tester la connexion ne ferait que reconfirmer le refus. */}
          {reauthNecessaire ? (
            <button type="button" onClick={() => { setAvis(null); setModaleOuverte(true); }}
                    className="rounded-full bg-[#0B0B0C] px-5 py-2.5 text-[13px] font-bold text-white">
              Réauthentifier
            </button>
          ) : null}
          <button type="button" onClick={() => test.mutate(source.id)} disabled={test.isPending} className={btnGhost}>
            {test.isPending ? "Test en cours…" : "Tester la connexion"}
          </button>
          {/* Offert quand le renouvellement peut encore aboutir — pas seulement
              quand un refresh existe. Un refresh que Shield a déjà refusé ne
              reviendra pas : proposer de le rejouer ferait consommer le quota de
              renouvellement pour reconfirmer un refus. */}
          {auth?.renouvellement_automatique ? (
            <button type="button" onClick={() => {
              // L'avis de la tentative précédente ne doit pas survivre à la
              // suivante : « Session rétablie » affiché au-dessus d'un refus
              // laisserait croire aux deux à la fois.
              setAvis(null);
              reauthAuto.mutate({ sourceId: source.id }, { onSuccess: (r) => setAvis(r.message) });
            }} disabled={reauthAuto.isPending} className={btnGhost}>
              {reauthAuto.isPending ? "Renouvellement…" : "Renouveler la session"}
            </button>
          ) : null}
          {auth && !reauthNecessaire ? (
            <button type="button" onClick={() => { setAvis(null); setModaleOuverte(true); }} className={btnGhost}>
              Réauthentifier
            </button>
          ) : null}
          <button type="button" onClick={() => toggle.mutate(source.id)} disabled={toggle.isPending} className={btnGhost}>
            {source.is_active ? "Désactiver" : "Activer"}
          </button>
        </div>

        {avis ? (
          <p className="text-[12.5px] font-semibold text-[#0F6E56]">{avis}</p>
        ) : null}
        {reauthAuto.data && !reauthAuto.data.ok ? (
          <p className="text-[12.5px] font-semibold text-[#A32D2D]">{reauthAuto.data.message}</p>
        ) : null}
        {reauthAuto.isError ? <IntegrationsError error={reauthAuto.error} /> : null}
        {test.isError ? <IntegrationsError error={test.error} /> : null}

        {modaleOuverte ? (
          <ModaleReauth
            sourceId={source.id}
            onFerme={() => setModaleOuverte(false)}
            onSucces={(message) => setAvis(message)}
          />
        ) : null}
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
