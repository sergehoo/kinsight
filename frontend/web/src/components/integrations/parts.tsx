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
  // `detail` est le message générique de DRF, déjà reformulé au-dessus ; le
  // reproduire tel quel ajouterait une seconde phrase disant la même chose.
  // Seules les erreurs PAR CHAMP (400) valent d'être listées.
  const parChamp = Object.entries((error instanceof ApiError ? error.details : undefined) ?? {}).filter(([champ]) => champ !== "detail");
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
  };

  const known = status !== undefined ? cases[status] : undefined;
  const cinqCents = status !== undefined && status >= 500;
  const titre = known?.titre ?? (cinqCents ? "Backend en erreur" : "API inaccessible");
  const explication =
    known?.explication ??
    (cinqCents
      ? `Le serveur a répondu ${status} : la requête est parvenue au backend, qui a échoué à la traiter.`
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
