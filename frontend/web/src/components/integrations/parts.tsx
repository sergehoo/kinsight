import * as React from "react";
import { Link, useNavigate } from "react-router-dom";

import { AppHeader } from "@/components/chrome/AppHeader";
import { BrandFooter } from "@/components/chrome/BrandFooter";
import { FRAME_BG, glass } from "@/components/chrome/theme";
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
    <div className="min-h-screen bg-[#B8B7B4] p-3 text-black sm:p-5 lg:p-6">
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
