import * as React from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { downloadGroupExport } from "@/api/governance";
import { AppHeader } from "@/components/chrome/AppHeader";
import { BrandFooter } from "@/components/chrome/BrandFooter";
import { SideRail } from "@/components/chrome/SideRail";
import { BLACK, FRAME_BG, ORANGE, glass } from "@/components/chrome/theme";
import { DomainScoreCard } from "@/components/overview/DomainScoreCard";
import { GroupGovernanceIndex } from "@/components/overview/GroupGovernanceIndex";
import { ShieldHrKpis } from "@/components/overview/ShieldHrKpis";
import { ArrowUpRight, ChevronDown, Dots } from "@/components/overview/icons";
import { EmptyChartState, IconButton, MetricCard, StateBadge, type DataState } from "@/components/ui/kit";
import { Menu, MenuItem } from "@/components/ui/Menu";
import { getDefaultItemHref, type DashboardModuleConfig } from "@/config/modules.config";
import { getDomainAccent } from "@/config/domainTheme";
import { useDomainTheme } from "@/lib/useDomainTheme";
import type { DomainHeroSpec } from "@/config/domainHome.config";
import { getCurrentPermissions } from "@/lib/permissions";
import { EASE_OUT } from "@/lib/motion";
import { useFilters } from "@/store/filters";
import { useNavigationStore } from "@/state/navigationStore";

const CHIP_COLORS = ["#D92B55", "#E8703F", "#EF9F27", "#7FB933", "#42BFA0", "#37A0DD", "#5B8DEF", "#8A63D2"];

function PeriodMenu() {
  const { year, quarter, setYear, setQuarter } = useFilters();
  const years = [2024, 2025, 2026];
  const quarters = [1, 2, 3, 4];
  return (
    <Menu
      align="right"
      width={240}
      trigger={({ open, toggle }) => (
        <button
          type="button"
          onClick={toggle}
          aria-haspopup="menu"
          aria-expanded={open}
          className="flex h-12 items-center gap-3 rounded-full px-5 text-[14px] font-bold text-[#222]"
          style={glass}
        >
          T{quarter} {year}
          <ChevronDown width={15} height={15} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .25s ease" }} />
        </button>
      )}
    >
      {() => (
        <div className="p-1">
          <div className="px-2 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-[#8A908D]">Trimestre</div>
          <div className="mb-2 grid grid-cols-4 gap-1.5">
            {quarters.map((q) => (
              <button key={q} type="button" onClick={() => setQuarter(q)} className="rounded-xl py-2 text-[13px] font-semibold" style={q === quarter ? { background: ORANGE, color: "#fff" } : { background: "rgba(255,255,255,0.6)", color: "#2A2D2D" }}>
                T{q}
              </button>
            ))}
          </div>
          <div className="px-2 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-[#8A908D]">Année</div>
          <div className="grid grid-cols-3 gap-1.5">
            {years.map((y) => (
              <button key={y} type="button" onClick={() => setYear(y)} className="rounded-xl py-2 text-[13px] font-semibold" style={y === year ? { background: BLACK, color: "#fff" } : { background: "rgba(255,255,255,0.6)", color: "#2A2D2D" }}>
                {y}
              </button>
            ))}
          </div>
        </div>
      )}
    </Menu>
  );
}

function ActionsMenu() {
  const { year, quarter, subsidiary } = useFilters();
  const [busy, setBusy] = React.useState(false);
  const fullscreen = () => {
    if (typeof document === "undefined") return;
    if (document.fullscreenElement) document.exitFullscreen?.();
    else document.documentElement.requestFullscreen?.();
  };
  const exportAs = async (ext: "xlsx" | "pdf") => {
    setBusy(true);
    try {
      await downloadGroupExport(ext, year, quarter, subsidiary);
    } catch {
      /* l'échec réseau reste silencieux ici ; l'API journalise l'accès */
    } finally {
      setBusy(false);
    }
  };
  return (
    <Menu
      align="right"
      width={230}
      trigger={({ open, toggle }) => (
        <button type="button" aria-label="Plus d'options" aria-haspopup="menu" aria-expanded={open} onClick={toggle} className="grid h-12 w-12 place-items-center rounded-full text-[#242424]" style={glass}>
          <Dots width={20} height={20} />
        </button>
      )}
    >
      {(close) => (
        <>
          <MenuItem onClick={() => { fullscreen(); close(); }}>Plein écran</MenuItem>
          <MenuItem onClick={() => { exportAs("xlsx"); close(); }}>{busy ? "Export…" : "Exporter (Excel)"}</MenuItem>
          <MenuItem onClick={() => { exportAs("pdf"); close(); }}>Exporter (PDF)</MenuItem>
          <MenuItem onClick={close}>Programmer un rapport (bientôt)</MenuItem>
        </>
      )}
    </Menu>
  );
}

function SignalsCard({ spec }: { spec: DomainHeroSpec }) {
  const [open, setOpen] = React.useState(true);
  return (
    <motion.article
      className="rounded-[26px] p-5"
      style={glass}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4, duration: 0.5, ease: EASE_OUT }}
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[17px] font-semibold text-black">Signaux &amp; seuils</h3>
            <StateBadge state="disconnected" />
          </div>
          <p className="mt-0.5 text-[11.5px] font-medium text-[#8A8F8E]">
            {spec.alertLabels.length} seuils déclarés · aucun encore alimenté
          </p>
        </div>
        <IconButton label={open ? "Réduire" : "Développer"} onClick={() => setOpen((v) => !v)} variant="ghost" size="sm">
          <ChevronDown width={16} height={16} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .3s ease" }} />
        </IconButton>
      </div>
      {open ? (
        <div className="mt-4 grid grid-cols-2 gap-2">
          {spec.alertLabels.map((label, i) => (
            <div key={label} className="rounded-[12px] bg-white/60 px-2.5 pb-2 pt-1.5" style={{ borderTop: `2.5px solid ${CHIP_COLORS[i % CHIP_COLORS.length]}` }}>
              <div className="truncate text-[11.5px] font-semibold text-[#3C4142]">{label}</div>
              <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#A0A6A3]">N/D</div>
            </div>
          ))}
        </div>
      ) : null}
    </motion.article>
  );
}

export function DomainHome({ spec, module }: { spec: DomainHeroSpec; module: DashboardModuleConfig }) {
  const sidebarExpanded = useNavigationStore((state) => state.sidebarExpanded);
  const permissions = getCurrentPermissions();
  const exploreHref = getDefaultItemHref(module, permissions);
  // Décalage sidebar appliqué à partir de md seulement (rail masqué en mobile).
  const padLeft = sidebarExpanded ? "md:pl-[296px]" : "md:pl-[120px]";
  const details = spec.kpis.slice(0, 3);
  const [showFeatured, setShowFeatured] = React.useState(true);
  // Aucune série temporelle n'est encore publiée par le mart, quel que soit le
  // domaine : on l'assume explicitement plutôt que d'afficher un graphe décoratif.
  const chartState: DataState = "disconnected";
  const chartSource = "Mart EDW";
  // Pose les tokens --domain-* sur <html> : header, rail et panneaux flottants
  // partagent le même accent, la transition étant gérée en CSS.
  useDomainTheme(module.id);
  // Les attributs SVG (stopColor…) ne résolvent pas var() : couleur concrète,
  // mais issue de la MÊME source que les tokens.
  const accentHex = getDomainAccent(module.id).accent;

  // Fond de page clair + halo teinté par le domaine (plus de gris « désactivé »).
  // Marge nulle en mobile, respirante à partir de sm.
  return (
    <div className="ki-page relative min-h-screen p-0 text-black sm:p-3 md:p-4 lg:p-6">
      <div className="ki-domain-glow pointer-events-none fixed inset-0 z-0" aria-hidden />
      <div className="relative z-10 mx-auto min-h-[560px] w-full max-w-[1840px] overflow-hidden rounded-none border-white/70 bg-[#F4F7F2] shadow-[0_18px_60px_rgba(36,38,38,0.10)] sm:rounded-[28px] sm:border sm:shadow-[0_30px_90px_rgba(36,38,38,0.13)] lg:min-h-[860px] lg:rounded-[42px] 2xl:max-w-[2160px]">
        <div className={`pointer-events-none absolute inset-0 rounded-[inherit] ${FRAME_BG}`} />
        {/* Halo métier à l'intérieur du cadre : anime le hero au changement de domaine. */}
        <div className="ki-domain-glow pointer-events-none absolute inset-0 rounded-[inherit]" aria-hidden />

        <AppHeader />
        <SideRail />

        {/* pb-28 en mobile : dégage le bouton Copilot flottant (fixed bottom-6 h-14),
            qui recouvrait le bas du contenu sur petits écrans. */}
        <main className={`relative z-10 pb-28 pl-4 pr-4 pt-2 transition-[padding] duration-300 ease-out sm:pb-10 sm:pl-5 sm:pr-8 lg:pr-[3%] ${padLeft}`}>
          {/* `key` = domaine : au changement de domaine le bloc se remonte, donc les
              animations d'entrée rejouent → transition douce au lieu d'un saut sec. */}
          <motion.div
            key={module.id}
            className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.42, ease: EASE_OUT }}
          >
            {/* Colonne principale */}
            <div className="flex min-w-0 flex-col gap-6">
              {/* Zone hero : titre + visuel + carte vedette */}
              <div className="relative min-h-[200px] lg:min-h-[430px]">
                <div className="absolute right-0 top-0 hidden h-full w-[64%] lg:block">
                  {spec.image ? (
                    <img
                      src={spec.image}
                      alt=""
                      className={spec.imageMode === "cover" ? "h-full w-full rounded-[28px] object-cover opacity-[0.94]" : "h-full w-full scale-[1.05] object-contain drop-shadow-[0_30px_44px_rgba(32,34,34,0.16)]"}
                    />
                  ) : spec.illustrationSvg ? (
                    <div className="grid h-full w-full place-items-center opacity-[0.82]" dangerouslySetInnerHTML={{ __html: spec.illustrationSvg }} />
                  ) : null}
                  <div className="pointer-events-none absolute inset-y-0 left-0 w-[28%] bg-gradient-to-r from-[#F4F7F2] to-transparent" />
                </div>

                {/* Sur lg+, le texte s'arrête AVANT la carte vedette : elle ne peut
                    plus recouvrir le titre ni la description (z-30 sur z-20). */}
                <section className="relative z-20 max-w-[460px] pt-4 lg:max-w-[min(460px,calc(100%-320px))]">
                  <p className="ki-accent-text text-[11px] font-bold uppercase tracking-[0.18em] sm:text-[12px]">{spec.kicker}</p>
                  <h1 className="mt-2 text-[clamp(28px,7vw,60px)] font-semibold leading-[1.03] tracking-tight text-black">{spec.title}</h1>
                  <p className="mt-3 max-w-[400px] text-[14px] font-medium leading-relaxed text-[#777C7D] sm:mt-4 sm:text-[15px]">{spec.tagline}</p>
                  <Link to={exploreHref} className="mt-5 inline-flex items-center gap-2 rounded-full px-5 py-3 text-[13px] font-bold text-white shadow-[0_16px_32px_rgba(0,0,0,0.16)] transition-transform hover:-translate-y-0.5 sm:mt-6 sm:text-[13.5px]" style={{ background: BLACK }}>
                    Explorer les {module.sidebarItems.length} sous-modules
                    <ArrowUpRight width={16} height={16} />
                  </Link>
                </section>

                {showFeatured ? (
                  <motion.div
                    className="relative z-30 mt-6 w-full max-w-[320px] rounded-[22px] p-5 text-white lg:absolute lg:right-2 lg:top-[24%] lg:mt-0 lg:w-[284px]"
                    style={{ background: "rgba(18,21,24,0.62)", border: "1px solid rgba(255,255,255,0.34)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", boxShadow: "0 26px 60px rgba(9,12,15,0.32)" }}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, ease: EASE_OUT }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="truncate text-[18px] font-semibold leading-tight">{spec.featuredTitle}</h2>
                        <p className="mt-1 truncate text-[12px] font-medium text-white/70">{spec.featuredSubtitle}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <Link to={exploreHref} aria-label="Ouvrir" className="grid h-9 w-9 place-items-center rounded-full border border-white/30 bg-white/10 transition-colors hover:bg-white/20">
                          <ArrowUpRight width={15} height={15} />
                        </Link>
                        <button type="button" onClick={() => setShowFeatured(false)} aria-label="Fermer le résumé" className="grid h-9 w-9 place-items-center rounded-full border border-white/30 bg-white/10 transition-colors hover:bg-white/20">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
                        </button>
                      </div>
                    </div>
                    <div className="mt-5 flex items-end justify-between gap-3">
                      <div className="min-w-0">
                        <span className="block text-[36px] font-semibold leading-none">N/D</span>
                        <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-[0.06em] text-white/75">
                          <span className="h-1.5 w-1.5 rounded-full bg-white/60" />
                          {chartSource} à raccorder
                        </span>
                      </div>
                      <div className="flex items-center">
                        {spec.featuredBadges.slice(0, 3).map((initials, i) => (
                          <span key={initials} className="grid h-8 w-8 place-items-center rounded-full border-2 border-white/70 text-[10px] font-bold" style={{ marginLeft: i ? -8 : 0, background: i === 1 ? "#fff" : accentHex, color: i === 1 ? "#111" : "#fff" }}>
                            {initials}
                          </span>
                        ))}
                        <span className="-ml-2 grid h-8 w-8 place-items-center rounded-full border-2 border-white/70 bg-white/65 text-[11px] font-bold text-[#333]">+3</span>
                      </div>
                    </div>
                  </motion.div>
                ) : (
                  <motion.button
                    type="button"
                    onClick={() => setShowFeatured(true)}
                    aria-label="Afficher le résumé du programme"
                    className="relative z-30 mt-4 inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-bold text-white lg:absolute lg:right-2 lg:top-[24%] lg:mt-0"
                    style={{ background: "rgba(18,21,24,0.62)", border: "1px solid rgba(255,255,255,0.34)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", boxShadow: "0 18px 40px rgba(9,12,15,0.28)" }}
                    initial={{ opacity: 0, scale: 0.92 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3, ease: EASE_OUT }}
                  >
                    <ArrowUpRight width={14} height={14} />
                    Résumé
                  </motion.button>
                )}
              </div>

              {/* Graphe de coupe + slider */}
              <motion.section
                className="rounded-[32px] px-6 pb-5 pt-5"
                style={{ ...glass, background: "rgba(246,248,246,0.6)" }}
                initial={{ opacity: 0, y: 22 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.18, duration: 0.6, ease: EASE_OUT }}
              >
                <div className="flex flex-wrap items-start justify-between gap-3 sm:gap-5">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-[16px] font-semibold text-[#202020]">{spec.chartTitle}</h2>
                      <StateBadge state={chartState} />
                    </div>
                    <p className="mt-1 text-[11.5px] font-medium text-[#8C9391]">
                      Série {spec.chartUnit} · périmètre Groupe consolidé
                    </p>
                  </div>
                  <div className="flex items-center gap-3 pt-1 text-[14px] font-semibold text-[#242424]">
                    <span className="ki-accent-fill h-2.5 w-[60px] rounded-full" />
                    {spec.chartUnit}
                  </div>
                </div>
                <div className="mt-4 min-h-[230px]">
                  <EmptyChartState
                    state={chartState}
                    source={chartSource}
                    action={{ label: "Configurer la source", to: "/admin/integrations" }}
                  />
                </div>
              </motion.section>

              {/* Score de Gouvernance (branché mart, gouverné N/D) :
                  Overview → indice Groupe consolidé ; autres domaines → score du domaine. */}
              {module.id === "overview" ? (
                <GroupGovernanceIndex accent={accentHex} />
              ) : (
                <DomainScoreCard domainId={module.id} accent={accentHex} />
              )}
            </div>

            {/* Colonne droite (KPI + signaux) — grille fluide : 2-up tablette, empilé desktop */}
            <aside className="flex flex-col gap-4">
              <div className="mb-1 flex flex-wrap items-center justify-end gap-2 sm:gap-3">
                <PeriodMenu />
                <ActionsMenu />
              </div>
              {module.id === "capital-humain" ? (
                <ShieldHrKpis />
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-1">
                  {details.map((kpi, i) => (
                    <MetricCard
                      key={kpi.label}
                      title={kpi.label}
                      state="disconnected"
                      source={chartSource}
                      scope="Groupe consolidé"
                      highlighted={i === 0}
                      href={exploreHref}
                    />
                  ))}
                </div>
              )}
              <SignalsCard spec={spec} />
            </aside>
          </motion.div>

          <BrandFooter />
        </main>
      </div>
    </div>
  );
}
