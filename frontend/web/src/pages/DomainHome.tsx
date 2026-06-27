import * as React from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { downloadGroupExport } from "@/api/governance";
import { AppHeader } from "@/components/chrome/AppHeader";
import { BrandFooter } from "@/components/chrome/BrandFooter";
import { SideRail } from "@/components/chrome/SideRail";
import { BLACK, FRAME_BG, ORANGE, glass } from "@/components/chrome/theme";
import { CrossSectionChart } from "@/components/overview/CrossSectionChart";
import { DomainScoreCard } from "@/components/overview/DomainScoreCard";
import { Gauge } from "@/components/overview/Gauge";
import { GroupGovernanceIndex } from "@/components/overview/GroupGovernanceIndex";
import { ArrowUpRight, ChevronDown, Cog, Dots, TriUp } from "@/components/overview/icons";
import { Menu, MenuItem } from "@/components/ui/Menu";
import { getDefaultItemHref, type DashboardModuleConfig } from "@/config/modules.config";
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

function DetailCard({ label, color, highlighted, href, index }: { label: string; color: string; highlighted?: boolean; href: string; index: number }) {
  return (
    <motion.article
      className="relative h-[150px] overflow-hidden rounded-[26px] p-5"
      style={{
        ...glass,
        background: "linear-gradient(135deg,rgba(255,255,255,0.82),rgba(243,248,249,0.56))",
        border: highlighted ? `2.5px solid ${ORANGE}` : glass.border,
        boxShadow: highlighted ? "0 22px 46px rgba(255,135,53,0.12)" : glass.boxShadow,
      }}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4, transition: { duration: 0.22, ease: EASE_OUT } }}
      transition={{ delay: 0.12 + index * 0.08, duration: 0.5, ease: EASE_OUT }}
    >
      <div className="flex items-start justify-between">
        <div className="flex min-w-0 items-center gap-3 pr-2">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[#EEF0F0] text-[#7B8084]">
            <Cog width={18} height={18} />
          </span>
          <span className="truncate text-[15px] font-semibold text-[#16191A]">{label}</span>
        </div>
        <Link to={href} aria-label={`Détails ${label}`} className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white/60 text-[#222] shadow-sm transition-transform hover:-translate-y-0.5">
          <ArrowUpRight width={16} height={16} />
        </Link>
      </div>
      <div className="absolute left-5 top-[72px] text-[11px] font-bold uppercase tracking-[0.1em] text-[#9AA09D]">mart à connecter</div>
      <div className="absolute bottom-5 left-5 text-[34px] font-semibold leading-none text-black">N/D</div>
      <div className="absolute -bottom-4 right-[-38px] h-[110px] w-[176px] opacity-95">
        <Gauge value={8} color={color} />
      </div>
    </motion.article>
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
        <div>
          <h3 className="text-[17px] font-semibold text-black">Signaux & seuils</h3>
          <p className="mt-0.5 text-[11.5px] font-medium text-[#8A8F8E]">Données EDW — lecture seule</p>
        </div>
        <button type="button" aria-label={open ? "Réduire" : "Développer"} onClick={() => setOpen((v) => !v)} className="grid h-9 w-9 place-items-center rounded-full bg-white/60 text-[#222] shadow-sm">
          <ChevronDown width={16} height={16} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .3s ease" }} />
        </button>
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
  const padLeft = sidebarExpanded ? "pl-[88px] md:pl-[296px]" : "pl-[88px] md:pl-[120px]";
  const details = spec.kpis.slice(0, 3);
  const [showFeatured, setShowFeatured] = React.useState(true);

  return (
    <div className="min-h-screen bg-[#B8B7B4] p-3 text-black sm:p-5 lg:p-6">
      <div className="relative mx-auto min-h-[900px] w-full max-w-[1840px] overflow-hidden rounded-[42px] border border-white/70 bg-[#F4F7F2] shadow-[0_34px_100px_rgba(36,38,38,0.22)]">
        <div className={`pointer-events-none absolute inset-0 rounded-[inherit] ${FRAME_BG}`} />

        <AppHeader />
        <SideRail />

        <main className={`relative z-10 pb-12 pr-5 pt-2 transition-[padding] duration-300 ease-out sm:pr-8 lg:pr-[3%] ${padLeft}`}>
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            {/* Colonne principale */}
            <div className="flex min-w-0 flex-col gap-6">
              {/* Zone hero : titre + visuel + carte vedette */}
              <div className="relative min-h-[360px] lg:min-h-[430px]">
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

                <section className="relative z-20 max-w-[460px] pt-4">
                  <p className="text-[12px] font-bold uppercase tracking-[0.18em]" style={{ color: spec.accent }}>{spec.kicker}</p>
                  <h1 className="mt-2 text-[46px] font-semibold leading-[1.02] tracking-tight text-black lg:text-[60px]">{spec.title}</h1>
                  <p className="mt-4 max-w-[400px] text-[15px] font-medium leading-relaxed text-[#777C7D]">{spec.tagline}</p>
                  <Link to={exploreHref} className="mt-6 inline-flex items-center gap-2 rounded-full px-5 py-3 text-[13.5px] font-bold text-white shadow-[0_16px_32px_rgba(0,0,0,0.16)] transition-transform hover:-translate-y-0.5" style={{ background: BLACK }}>
                    Explorer les {module.sidebarItems.length} sous-modules
                    <ArrowUpRight width={16} height={16} />
                  </Link>
                </section>

                {showFeatured ? (
                  <motion.div
                    className="absolute left-1/2 top-[54%] z-30 w-[284px] -translate-x-1/2 rounded-[22px] p-5 text-white lg:left-auto lg:right-2 lg:top-[24%] lg:translate-x-0"
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
                    <div className="mt-5 flex items-end justify-between">
                      <span className="text-[36px] font-semibold leading-none">N/D</span>
                      <div className="flex items-center">
                        {spec.featuredBadges.slice(0, 3).map((initials, i) => (
                          <span key={initials} className="grid h-8 w-8 place-items-center rounded-full border-2 border-white/70 text-[10px] font-bold" style={{ marginLeft: i ? -8 : 0, background: i === 1 ? "#fff" : spec.accent, color: i === 1 ? "#111" : "#fff" }}>
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
                    className="absolute left-1/2 top-[54%] z-30 inline-flex -translate-x-1/2 items-center gap-2 rounded-full px-4 py-2.5 text-[12px] font-bold text-white lg:left-auto lg:right-2 lg:top-[24%] lg:translate-x-0"
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
                <div className="flex items-start justify-between gap-5">
                  <div>
                    <h2 className="text-[16px] font-semibold text-[#202020]">{spec.chartTitle}</h2>
                    <div className="mt-3 flex items-end gap-3">
                      <span className="text-[34px] font-semibold leading-none text-black">N/D</span>
                      <span className="flex items-center gap-1 text-[12px] font-bold text-[#9AA09D]">à connecter</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 pt-2 text-[15px] font-semibold text-[#242424]">
                    <span className="h-2.5 w-[60px] rounded-full" style={{ background: ORANGE }} />
                    {spec.chartUnit}
                  </div>
                </div>
                <div className="mt-4 h-[230px]">
                  <CrossSectionChart accent={ORANGE} />
                </div>
              </motion.section>

              {/* Score de Gouvernance (branché mart, gouverné N/D) :
                  Overview → indice Groupe consolidé ; autres domaines → score du domaine. */}
              {module.id === "overview" ? (
                <GroupGovernanceIndex accent={spec.accent} />
              ) : (
                <DomainScoreCard domainId={module.id} accent={spec.accent} />
              )}
            </div>

            {/* Colonne droite */}
            <aside className="flex flex-col gap-4">
              <div className="mb-1 flex items-center justify-end gap-3">
                <PeriodMenu />
                <ActionsMenu />
              </div>
              {details.map((kpi, i) => (
                <DetailCard key={kpi.label} label={kpi.label} color={kpi.color} highlighted={i === 0} href={exploreHref} index={i} />
              ))}
              <SignalsCard spec={spec} />
            </aside>
          </div>

          <BrandFooter />
        </main>
      </div>
    </div>
  );
}
