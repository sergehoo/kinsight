import * as React from "react";
import { Link } from "react-router-dom";

import { AnimatedNumber } from "@/components/overview/AnimatedNumber";
import { glass } from "@/components/chrome/theme";

/* ════════════════════════════════════════════════════════════════════════════
   ÉTATS DE DONNÉES GOUVERNÉS
   Vocabulaire unique partagé par tous les domaines et toutes les sources
   (API métier interne, Odoo, Kaydan Shield). Aucune donnée n'est inventée :
   un état non `connected` n'affiche JAMAIS de chiffre métier.
   ════════════════════════════════════════════════════════════════════════════ */
export type DataState =
  | "connected"
  | "connecting"
  | "partial"
  | "disconnected"
  | "error"
  /** Dernière donnée connue, servie par le cache hors ligne. Toujours signalée. */
  | "stale"
  /** Navigateur hors ligne : aucune donnée disponible. */
  | "offline";

/** Alias rétro-compatible : d'anciens appels utilisent success/loading. */
export type MetricStatus = DataState | "success" | "loading";

export function normalizeState(state: MetricStatus | undefined): DataState {
  if (state === "success") return "connected";
  if (state === "loading") return "connecting";
  return state ?? "connected";
}

interface StateMeta {
  label: string;
  color: string;
  bg: string;
  /** Texte affiché à la place d'une valeur métier absente. */
  placeholder: string;
  hint: string;
}

export const STATE_META: Record<DataState, StateMeta> = {
  connected: { label: "Connecté", color: "#1E8A6E", bg: "rgba(66,191,160,0.13)", placeholder: "—", hint: "Données à jour" },
  connecting: { label: "Synchronisation", color: "#E0801E", bg: "rgba(224,128,30,0.12)", placeholder: "…", hint: "Récupération en cours" },
  partial: { label: "Partiel", color: "#B8791C", bg: "rgba(224,168,30,0.14)", placeholder: "—", hint: "Certaines mesures manquent" },
  disconnected: { label: "Non connecté", color: "#7C8384", bg: "rgba(124,131,132,0.12)", placeholder: "N/D", hint: "Source à raccorder" },
  error: { label: "Indisponible", color: "#D92B55", bg: "rgba(217,43,85,0.11)", placeholder: "—", hint: "Source injoignable" },
  stale: { label: "Donnée datée", color: "#8A6D1F", bg: "rgba(214,178,62,0.18)", placeholder: "—", hint: "Dernière donnée connue, hors ligne" },
  offline: { label: "Hors ligne", color: "#5C6370", bg: "rgba(92,99,112,0.12)", placeholder: "N/D", hint: "Réseau indisponible" },
};

/* ── Fraîcheur vivante ─────────────────────────────────────────────────────
   « mis à jour il y a X » qui s'actualise tout seul, sans re-fetch. */
export function formatRelative(iso: string | undefined, now: number): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 10) return "à l'instant";
  if (seconds < 60) return `il y a ${seconds} s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `il y a ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `il y a ${hours} h`;
  return `il y a ${Math.round(hours / 24)} j`;
}

export function useRelativeTime(iso?: string): string {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!iso) return;
    const id = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => window.clearInterval(id);
  }, [iso]);
  return formatRelative(iso, now);
}

/* ── Skeleton ──────────────────────────────────────────────────────────────── */
export function Skeleton({ className = "", rounded = "rounded-lg" }: { className?: string; rounded?: string }) {
  return <span aria-hidden className={`ki-shimmer block ${rounded} ${className}`} />;
}

/* ── StateBadge ────────────────────────────────────────────────────────────── */
export function StateBadge({ state, label, className = "" }: { state: DataState; label?: string; className?: string }) {
  const meta = STATE_META[state];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.06em] ${className}`}
      style={{ background: meta.bg, color: meta.color }}
      title={meta.hint}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${state === "connecting" ? "ki-sync-dot" : ""}`}
        style={{ background: meta.color }}
      />
      {label ?? meta.label}
    </span>
  );
}

/* ── SourceMeta : provenance + fraîcheur ───────────────────────────────────── */
export function SourceMeta({ source, updatedAt, scope }: { source?: string; updatedAt?: string; scope?: string }) {
  const relative = useRelativeTime(updatedAt);
  const parts = [source, relative, scope].filter(Boolean);
  if (!parts.length) return null;
  return (
    <div className="mt-2 flex min-w-0 items-center gap-1.5 text-[10.5px] font-semibold text-[#A0A6A3]">
      <span className="truncate">{parts.join(" · ")}</span>
    </div>
  );
}

/* ── IconButton ────────────────────────────────────────────────────────────
   Bouton rond uniforme (même taille/rayon/hover/focus). Zone tactile ≥44px
   sur mobile ; visuel compact sur desktop. `to` → lien, sinon bouton. */
type IconButtonProps = {
  children: React.ReactNode;
  label: string;
  to?: string;
  onClick?: () => void;
  variant?: "glass" | "ghost" | "dark";
  size?: "sm" | "md";
};
const IB_VARIANT = {
  glass: "text-[#242424]",
  ghost: "bg-white/60 text-[#242424] shadow-sm hover:bg-white/85",
  dark: "text-white",
} as const;
export function IconButton({ children, label, to, onClick, variant = "ghost", size = "md" }: IconButtonProps) {
  const cls =
    `inline-grid min-h-[44px] min-w-[44px] place-items-center rounded-full transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0 ` +
    `ki-accent-ring ${IB_VARIANT[variant]} ` +
    (size === "sm" ? "h-9 w-9 sm:min-h-0 sm:min-w-0" : "h-11 w-11");
  const style = variant === "glass" ? glass : variant === "dark" ? { background: "#16191A" } : undefined;
  if (to) return <Link to={to} aria-label={label} className={cls} style={style}>{children}</Link>;
  return <button type="button" aria-label={label} onClick={onClick} className={cls} style={style}>{children}</button>;
}

/* ── ResponsiveGrid ──────────────────────────────────────────────────────────
   Grille fluide auto-fit (aucune largeur fixe) : les colonnes s'ajustent. */
export function ResponsiveGrid({ min = 240, gap = 16, children, className = "" }: { min?: number; gap?: number; children: React.ReactNode; className?: string }) {
  return (
    <div className={className} style={{ display: "grid", gap, gridTemplateColumns: `repeat(auto-fit, minmax(min(${min}px, 100%), 1fr))` }}>
      {children}
    </div>
  );
}

/* ── MetricCard ──────────────────────────────────────────────────────────────
   Carte KPI fluide et gouvernée : valeur animée si connectée, squelette si en
   cours, message explicite sinon. Ne fabrique jamais un chiffre. */
export interface MetricCardProps {
  title: string;
  value?: string | number | null;
  unit?: string;
  trend?: string;
  trendUp?: boolean;
  comparison?: string;
  source?: string;
  updatedAt?: string;
  scope?: string;
  state?: MetricStatus;
  /** @deprecated utiliser `state` */
  status?: MetricStatus;
  accent?: string;
  highlighted?: boolean;
  href?: string;
  /** Pourquoi cette mesure n'a pas de valeur, dans les mots de l'appelant.
   *
   *  Le message générique ci-dessous suppose une source identifiée qu'il suffit
   *  de raccorder. C'est le cas courant, mais pas le seul : un indicateur dont
   *  AUCUNE source n'existe donne « Aucune source à raccorder », qui se lit comme
   *  une phrase bancale et laisse croire à un branchement oublié. Quand
   *  l'appelant connaît la vraie raison, elle prime. */
  unavailableNote?: string;
}

export function MetricCard(props: MetricCardProps) {
  const {
    title, value, unit, trend, trendUp, comparison,
    source, updatedAt, scope, accent = "var(--domain-accent)", highlighted = false, href,
    unavailableNote,
  } = props;
  const state = normalizeState(props.state ?? props.status);
  const meta = STATE_META[state];
  // `stale` est le seul état non connecté autorisé à afficher un chiffre : c'est
  // une donnée réellement observée, et le badge + le pied de carte le disent.
  const hasValue = (state === "connected" || state === "stale") && value !== null && value !== undefined;

  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 flex-1 truncate text-[12.5px] font-semibold text-[#586061]" title={title}>
          {title}
        </span>
        <StateBadge state={state} />
      </div>

      <div className="mt-2.5 min-h-[38px]">
        {state === "connecting" ? (
          <Skeleton className="h-8 w-2/3" />
        ) : (
          <div className="flex items-end gap-1.5">
            <span className="text-[clamp(24px,5vw,34px)] font-extrabold leading-none text-[#16191A]">
              {hasValue ? <AnimatedNumber value={String(value)} /> : meta.placeholder}
            </span>
            {unit && hasValue ? <span className="pb-0.5 text-[12px] font-bold text-[#9AA09D]">{unit}</span> : null}
          </div>
        )}
      </div>

      {trend && hasValue ? (
        <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2 text-[11.5px] font-bold" style={{ color: trendUp === false ? "#D92B55" : "#1E8A6E" }}>
          <span>{trend}</span>
          {comparison ? <span className="font-medium text-[#9AA09D]">{comparison}</span> : null}
        </div>
      ) : null}

      {!hasValue && state !== "connecting" ? (
        <p className="mt-1.5 text-[11px] font-medium leading-snug text-[#8C9391]">
          {unavailableNote
            ? unavailableNote
            : state === "disconnected"
              ? `${source ?? "Source"} à raccorder — aucune donnée publiée.`
              : state === "error"
                ? "Source injoignable — dernière tentative échouée."
                : state === "offline"
                  ? "Hors ligne — aucune donnée en cache pour cette mesure."
                  : "Mesure absente de la réponse de la source."}
        </p>
      ) : null}

      {state === "stale" ? (
        <p className="mt-1.5 text-[11px] font-semibold leading-snug" style={{ color: STATE_META.stale.color }}>
          Dernière donnée connue — non rafraîchie depuis le retour hors ligne.
        </p>
      ) : null}
      <SourceMeta source={source} updatedAt={updatedAt} scope={scope} />
    </>
  );

  const className =
    "group flex min-w-0 flex-col justify-between overflow-hidden rounded-[22px] p-4 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_24px_48px_rgba(40,44,48,0.13)] sm:p-5";
  const style: React.CSSProperties = {
    ...glass,
    background: "linear-gradient(135deg,rgba(255,255,255,0.86),rgba(243,248,249,0.58))",
    ...(highlighted ? { border: `1.5px solid ${accent}`, transition: "border-color var(--domain-transition)" } : null),
  };

  if (href) {
    return (
      <Link to={href} className={`${className} ki-accent-ring`} style={style}>
        {body}
      </Link>
    );
  }
  return <article className={className} style={style}>{body}</article>;
}

/* ── EmptyChartState : état vide premium pour un graphe non alimenté ───────── */
export function EmptyChartState({
  state = "disconnected",
  source,
  message,
  action,
}: {
  state?: DataState;
  source?: string;
  message?: string;
  action?: { label: string; to: string };
}) {
  const meta = STATE_META[state];
  return (
    <div className="flex h-full min-h-[180px] w-full flex-col items-center justify-center gap-3 rounded-[20px] border border-dashed border-[#D7DDDA] bg-white/40 px-5 py-6 text-center">
      {state === "connecting" ? (
        <div className="flex w-full max-w-[320px] items-end justify-center gap-1.5" aria-hidden>
          {[38, 62, 46, 74, 54, 82, 48].map((h, i) => (
            <Skeleton key={i} className="w-4" rounded="rounded-md" />
          ))}
        </div>
      ) : (
        <span className="ki-accent-bg ki-accent-icon grid h-11 w-11 place-items-center rounded-full">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 3v18h18" />
            <path d="m7 14 3-3 3 3 4-5" />
          </svg>
        </span>
      )}
      <div>
        <div className="text-[13px] font-bold text-[#3C4142]">{meta.label}</div>
        <p className="mt-0.5 max-w-[46ch] text-[11.5px] font-medium leading-snug text-[#8C9391]">
          {message ?? `Aucune série publiée${source ? ` par ${source}` : ""}. Le graphe s'affichera dès le raccordement de la source.`}
        </p>
      </div>
      {action ? (
        <Link
          to={action.to}
          className="rounded-full bg-[#16191A] px-4 py-2 text-[11.5px] font-bold text-white transition-transform hover:-translate-y-0.5"
        >
          {action.label}
        </Link>
      ) : null}
    </div>
  );
}

/* ── SignalCard ──────────────────────────────────────────────────────────────
   Signal responsive. Types : info | success | warning | critical | anomaly. */
export type SignalSeverity = "info" | "success" | "warning" | "critical" | "anomaly";
export interface SignalCardProps {
  severity: SignalSeverity;
  title: string;
  description?: string;
  metric?: string;
  variation?: string;
  entity?: string;
  source?: string;
  detectedAt?: string;
  action?: { label: string; onClick?: () => void };
}
const SEV: Record<SignalSeverity, { c: string; bg: string; l: string }> = {
  info: { c: "#37A0DD", bg: "rgba(55,160,221,0.10)", l: "Info" },
  success: { c: "#1E8A6E", bg: "rgba(66,191,160,0.12)", l: "OK" },
  warning: { c: "#E0801E", bg: "rgba(224,128,30,0.10)", l: "Vigilance" },
  critical: { c: "#D92B55", bg: "rgba(217,43,85,0.10)", l: "Critique" },
  anomaly: { c: "#8A63D2", bg: "rgba(138,99,210,0.12)", l: "Anomalie" },
};
export function SignalCard({ severity, title, description, metric, variation, entity, source, detectedAt, action }: SignalCardProps) {
  const s = SEV[severity] ?? SEV.info;
  const relative = useRelativeTime(detectedAt);
  return (
    <article className="min-w-0 rounded-[14px] bg-white/70 p-3 transition-colors hover:bg-white/90" style={{ borderLeft: `3px solid ${s.c}` }}>
      <div className="flex items-center justify-between gap-2">
        <span className="shrink-0 rounded-full px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wide" style={{ background: s.bg, color: s.c }}>{s.l}</span>
        {relative ? <span className="shrink-0 text-[9.5px] font-semibold text-[#A0A6A3]">{relative}</span> : null}
      </div>
      <div className="mt-1.5 truncate text-[12.5px] font-semibold text-[#16191A]">{title}</div>
      {description ? <div className="mt-0.5 line-clamp-2 text-[11px] font-medium text-[#6B7270]">{description}</div> : null}
      {(metric || variation || entity) ? (
        <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px] font-semibold text-[#586061]">
          {metric ? <span className="rounded-full bg-white/80 px-2 py-0.5">{metric}{variation ? ` ${variation}` : ""}</span> : null}
          {entity ? <span className="rounded-full bg-white/80 px-2 py-0.5">{entity}</span> : null}
          {source ? <span className="rounded-full bg-white/80 px-2 py-0.5">{source}</span> : null}
        </div>
      ) : null}
      {action ? (
        <button type="button" onClick={action.onClick} className="mt-2 text-[11px] font-bold" style={{ color: s.c }}>{action.label} →</button>
      ) : null}
    </article>
  );
}
