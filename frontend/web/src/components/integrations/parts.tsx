import * as React from "react";
import { Link, useNavigate } from "react-router-dom";

import { AppHeader } from "@/components/chrome/AppHeader";
import { BrandFooter } from "@/components/chrome/BrandFooter";
import { FRAME_BG, glass } from "@/components/chrome/theme";
import { ApiError } from "@/lib/integrations";
import type { SourceStatus } from "@/types/integrations";

const STATUS_STYLE: Record<SourceStatus, { bg: string; fg: string; label: string }> = {
  not_configured: { bg: "#EEF0F0", fg: "#6B7280", label: "Non configurée" },
  configured: { bg: "#E6F1FB", fg: "#185FA5", label: "Configurée" },
  testing: { bg: "#FAEEDA", fg: "#854F0B", label: "En test" },
  connected: { bg: "#E1F5EE", fg: "#0F6E56", label: "Connectée" },
  syncing: { bg: "#E6F1FB", fg: "#185FA5", label: "Synchronisation…" },
  error: { bg: "#FCEBEB", fg: "#A32D2D", label: "Erreur" },
  disabled: { bg: "#F1EFE8", fg: "#5F5E5A", label: "Désactivée" },
};

export function StatusBadge({ status }: { status: SourceStatus }) {
  const s = STATUS_STYLE[status] ?? STATUS_STYLE.not_configured;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-bold" style={{ background: s.bg, color: s.fg }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.fg }} />
      {s.label}
    </span>
  );
}

export function IntegrationsShell({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: React.ReactNode; children: React.ReactNode }) {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen ki-page p-3 text-black sm:p-5 lg:p-6">
      <div className="relative mx-auto min-h-[760px] w-full max-w-[1840px] overflow-hidden rounded-[42px] border border-white/70 bg-[#F4F7F2] shadow-[0_34px_100px_rgba(36,38,38,0.22)]">
        <div className={`pointer-events-none absolute inset-0 rounded-[inherit] ${FRAME_BG}`} />
        <AppHeader />
        <main className="relative z-10 px-7 pb-12 pt-2 sm:px-10 lg:px-12">
          <button type="button" onClick={() => navigate("/")} className="mb-6 inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold text-[#3A3E3E]" style={glass}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6" /></svg>
            Tableau de bord
          </button>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-[12px] font-bold uppercase tracking-[0.18em] text-[#FF8735]">Connecteurs & Intégrations</p>
              <h1 className="mt-1 text-[34px] font-semibold tracking-tight text-black sm:text-[42px]">{title}</h1>
              {subtitle ? <p className="mt-2 max-w-[680px] text-[14px] font-medium text-[#777C7D]">{subtitle}</p> : null}
            </div>
            <div className="flex flex-wrap items-center gap-3">{actions}</div>
          </div>
          <div className="mt-8">{children}</div>
          <BrandFooter />
        </main>
      </div>
    </div>
  );
}

export const integrationsNav = [
  { to: "/admin/integrations", label: "Liste des intégrations" },
  { to: "/admin/integrations/health", label: "Santé des connecteurs" },
  { to: "/admin/integrations/new", label: "Ajouter une source" },
];

export function PrimaryLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link to={to} className="inline-flex items-center gap-2 rounded-full bg-[#0B0B0C] px-5 py-2.5 text-[13px] font-bold text-white shadow-[0_14px_28px_rgba(0,0,0,0.16)] transition-transform hover:-translate-y-0.5">
      {children}
    </Link>
  );
}

/** Diagnostic d'un échec d'appel au control-plane.
 *
 *  Le centre d'intégrations affichait « Backend indisponible — vérifiez l'API »
 *  quelle que soit la cause. Or les trois causes probables appellent trois
 *  gestes différents : un 403 se règle par un droit, un 401 par une reconnexion,
 *  une panne réseau par une vérification du service. Confondre les trois envoie
 *  chercher un problème d'infrastructure là où il manque une permission.
 */
export function IntegrationsError({ error }: { error: unknown }) {
  const status = error instanceof ApiError ? error.status : undefined;
  const corps = (error instanceof ApiError ? error.details : undefined) ?? {};
  // Nos endpoints d'authentification Shield répondent {ok, message, auth} :
  // `message` porte la cause exacte donnée par Shield, et la présence d'`auth`
  // signe une réponse d'authentification Shield. Sans ce marqueur, un 401 « jeton
  // Shield refusé » s'afficherait comme « votre session a expiré, reconnectez-vous »
  // — on renverrait l'opérateur se reconnecter alors que sa session est intacte.
  const messageServeur = typeof corps.message === "string" ? corps.message : null;
  const refusShield = "auth" in corps;
  // `detail` est le message générique de DRF, déjà reformulé au-dessus ; le
  // reproduire tel quel ajouterait une seconde phrase disant la même chose.
  // Seules les erreurs PAR CHAMP (400) valent d'être listées.
  const parChamp = Object.entries(corps).filter(
    ([champ]) => !["detail", "message", "ok", "auth"].includes(champ),
  );
  const details = parChamp.length ? parChamp : null;

  const cases: Record<number, { titre: string; explication: string; geste: string }> = {
    400: {
      titre: "Formulaire refusé par le serveur",
      explication: "Un ou plusieurs champs ne satisfont pas les contraintes du modèle.",
      geste: "Corrigez les champs signalés ci-dessous, puis réessayez.",
    },
    401: {
      titre: "Session expirée",
      explication: "Le serveur ne reconnaît plus votre session.",
      geste: "Reconnectez-vous pour continuer.",
    },
    403: {
      titre: "Accès réservé aux administrateurs d'intégration",
      explication:
        "Votre compte est authentifié, mais le centre de connecteurs exige d'être superutilisateur, " +
        "ou de porter le rôle « Administrateur intégrations » ou « Administrateur / Conseil d'administration ». " +
        "Le libellé « Super Admin » affiché dans l'en-tête ne correspond à aucun de ces rôles.",
      geste: "Demandez l'un de ces rôles à un administrateur, ou connectez-vous avec un compte qui le porte.",
    },
    404: {
      titre: "Endpoint introuvable",
      explication: "Le serveur ne connaît pas cette route. L'URL d'API du build ou le routage du proxy est incorrect.",
      geste: "Vérifiez VITE_API_BASE_URL au build et la règle de proxy sur /api/.",
    },
    409: {
      titre: "Session Shield non renouvelable",
      explication:
        "Le serveur a bien traité la demande, mais Shield a refusé le renouvellement — " +
        "jeton de renouvellement expiré ou révoqué. Le message ci-dessus en donne la cause.",
      geste: "Déposez un couple access + refresh neuf via « Réauthentifier ».",
    },
    429: {
      titre: "Trop de tentatives",
      explication:
        "Shield limite le débit des renouvellements et vient d'être sollicité. " +
        "Insister aggrave la limite au lieu de la lever.",
      geste: "Patientez une minute avant de réessayer.",
    },
    // Un 502 n'est PAS une erreur applicative : il est émis par le proxy, qui n'a
    // pas réussi à joindre le service. Le présenter comme « le backend a échoué à
    // traiter la requête » envoie lire des journaux applicatifs qui ne contiennent
    // rien, alors que le service est simplement absent de l'autre côté du proxy.
    502: {
      titre: "Le proxy n'a pas pu joindre le service",
      explication:
        "Réponse 502 émise par le serveur web, pas par K-Insight : la requête n'est jamais arrivée à " +
        "l'application. Le conteneur backend est arrêté, ou le proxy pointe vers une adresse qui n'existe plus " +
        "(cas classique après un redéploiement).",
      geste: "Vérifiez que le service backend tourne, puis redémarrez le conteneur frontend pour qu'il résolve à nouveau son amont.",
    },
    503: {
      titre: "Service temporairement indisponible",
      explication: "Réponse 503 : le service est en cours de démarrage ou de redéploiement.",
      geste: "Réessayez dans une minute.",
    },
    504: {
      titre: "Délai dépassé côté proxy",
      explication:
        "Réponse 504 : le service a bien été joint mais n'a pas répondu dans le temps imparti. " +
        "L'opération est peut-être allée à son terme côté serveur.",
      geste: "Vérifiez l'état réel avant de réessayer, pour ne pas créer de doublon.",
    },
  };

  const refusDeJeton = {
    titre: "Jeton Shield refusé",
    explication:
      "Kaydan Shield a rejeté le couple présenté. Votre session K-Insight, elle, est intacte : " +
      "il n'y a pas à vous reconnecter.",
    geste: "Obtenez un couple access + refresh neuf dans Shield, puis recollez-le.",
  };
  const known = refusShield && status === 401 ? refusDeJeton : status !== undefined ? cases[status] : undefined;
  const cinqCents = status !== undefined && status >= 500;
  const titre = known?.titre ?? (cinqCents ? "Erreur applicative du backend" : "API inaccessible");
  const explication =
    known?.explication ??
    (cinqCents
      ? `Le serveur a répondu ${status} : la requête est parvenue à l'application, qui a échoué à la traiter.`
      : "Aucune réponse du backend K-Insight. La requête n'a pas abouti (réseau, service arrêté ou proxy).");
  const geste =
    known?.geste ??
    (cinqCents
      ? "Consultez les journaux du service backend : la cause est côté serveur."
      : "Vérifiez que le service backend tourne et que le proxy route bien /api/ vers lui.");

  return (
    <div className="rounded-[20px] border border-[#F0D2D2] bg-[#FCEBEB] px-5 py-4">
      <p className="text-[14px] font-bold text-[#A32D2D]">{titre}</p>
      <p className="mt-1 text-[13px] font-medium leading-relaxed text-[#8C4141]">{explication}</p>
      {/* La phrase du serveur passe avant nos généralités : elle nomme la cause. */}
      {messageServeur ? (
        <p className="mt-1.5 text-[13px] font-semibold leading-relaxed text-[#8C4141]">{messageServeur}</p>
      ) : null}
      {/* Sur un 400, DRF renvoie l'erreur PAR CHAMP : la recopier évite de faire
          deviner lequel pose problème. */}
      {details ? (
        <ul className="mt-2 space-y-0.5">
          {details.map(([champ, messages]) => (
            <li key={champ} className="text-[12.5px] font-semibold text-[#8C4141]">
              <span className="font-bold">{champ}</span> : {(Array.isArray(messages) ? messages : [String(messages)]).join(" ")}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-1.5 text-[12.5px] font-semibold text-[#A32D2D]">{geste}</p>
    </div>
  );
}
