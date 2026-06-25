import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { useGovernanceOverview } from "@/api/governance";
import { AnimatedNumber } from "@/components/overview/AnimatedNumber";
import { Gauge } from "@/components/overview/Gauge";
import { SalesHistogram } from "@/components/overview/SalesHistogram";
import { ArrowUpRight, ChevronDown, Cog, Dots, TriDown, TriUp } from "@/components/overview/icons";
import { AppHeader } from "@/components/chrome/AppHeader";
import { SideRail } from "@/components/chrome/SideRail";
import { BLACK, FRAME_BG, ORANGE, glass } from "@/components/chrome/theme";
import { Menu, MenuItem } from "@/components/ui/Menu";
import { EASE_OUT } from "@/lib/motion";
import { useFilters } from "@/store/filters";
import type { DashboardKey, DashboardMetricCard, DashboardSummary } from "@/types/governance";

type DetailMetric = DashboardMetricCard;

const DASHBOARD_KEYS: DashboardKey[] = ["realEstate", "hr", "finance"];
/** Module métier ouvert depuis les flèches « détails » de chaque dashboard. */
const DETAIL_MODULE: Record<DashboardKey, string> = {
  realEstate: "construction",
  hr: "groupe",
  finance: "accounting",
};

interface DashboardModel extends DashboardSummary {
  imageSrc: string;
  imageMode: "contain" | "cover";
}

const DASHBOARD_IMAGES: Record<DashboardKey, Pick<DashboardModel, "imageSrc" | "imageMode">> = {
  realEstate: {
    imageSrc: "/assets/%E2%80%94Pngtree%E2%80%94modern%20yellow%20construction%20crane%20for_20885637.png",
    imageMode: "contain",
  },
  hr: {
    imageSrc: "/assets/african-man-holding-ipad.jpg",
    imageMode: "cover",
  },
  finance: {
    imageSrc: "/assets/tree-grows-coin-glass-jar-with-copy-space.jpg",
    imageMode: "cover",
  },
};

function emptyDashboard(key: DashboardKey, year: number, quarter: number, status: string): DashboardModel {
  const title =
    key === "realEstate" ? "Pilotage Real Estate" : key === "finance" ? "Pilotage Finance" : "Pilotage RH";
  const source =
    key === "realEstate" ? "mart.real_estate_kpi" : key === "finance" ? "mart.finance_kpi" : "mart.hr_kpi";
  return {
    key,
    title,
    subtitle: "Connexion au backend en cours. Les donnees affichees ici viennent exclusivement de l'API governance.",
    status,
    available: false,
    source,
    imageHint: key === "realEstate" ? "real_estate" : key,
    overlayTitle: "Backend",
    overlaySubtitle: source,
    overlayValue: "--",
    overlayBadges: ["API"],
    periodLabel: `T${quarter} ${year}`,
    chartTitle: "Donnees backend",
    chartValue: "--",
    chartDelta: "API indisponible",
    chartDeltaUp: false,
    chartUnit: key === "realEstate" ? "%" : "XOF",
    chartData: {},
    chartEmptyLabel: "Aucune donnee backend disponible",
    cards: [
      { label: "API", context: "Governance", value: "--", delta: "indisponible", up: false, gauge: 8, color: "#416FF4", highlighted: true },
      { label: "Source", context: source, value: "--", delta: "backend", up: false, gauge: 8, color: "#42BFA0" },
      { label: "Audit", context: "RBAC", value: "--", delta: "read", up: false, gauge: 8, color: "#D92B55" },
    ],
    controlTitle: "Controle donnees",
    controlSubtitle: source,
    alertTop: [["API", "--"], ["Source", source], ["Etat", "KO"], ["RBAC", "--"], ["Mode", "read"]],
    alertBottom: [["Backend", "--"], ["EDW", "--"], ["Mart", "--"], ["Audit", "--"], ["Prod", "--"]],
    ...DASHBOARD_IMAGES[key],
  };
}

function withPresentation(summary: DashboardSummary): DashboardModel {
  return { ...summary, ...DASHBOARD_IMAGES[summary.key] };
}

function Delta({ value, up }: { value: string; up: boolean }) {
  return (
    <span
      className="inline-flex max-w-[150px] items-center gap-2 truncate text-[15px] font-semibold"
      style={{ color: up ? "#202526" : "#C43252" }}
    >
      {value}
      {up ? <TriUp width={13} height={13} /> : <TriDown width={13} height={13} />}
    </span>
  );
}

function DetailCard({
  label,
  context,
  value,
  delta,
  up,
  gauge,
  color,
  highlighted,
  detailHref,
  index = 0,
}: DetailMetric & { detailHref: string; index?: number }) {
  const isMissingValue = value.trim() === "--" || value.trim() === "-";
  const displayValue = isMissingValue ? "N/D" : value;

  return (
    <motion.article
      className="relative h-[192px] overflow-hidden rounded-[28px] p-6"
      style={{
        ...glass,
        background: "linear-gradient(135deg,rgba(255,255,255,0.76),rgba(243,248,249,0.56))",
        border: highlighted ? `3px solid ${ORANGE}` : glass.border,
        boxShadow: highlighted
          ? "0 22px 46px rgba(255,135,53,0.12), 0 18px 42px rgba(40,44,48,0.08)"
          : glass.boxShadow,
      }}
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -5, transition: { duration: 0.25, ease: EASE_OUT } }}
      transition={{ delay: 0.1 + index * 0.1, duration: 0.6, ease: EASE_OUT }}
    >
      <div className="flex items-start justify-between">
        <div className="flex min-w-0 items-center gap-4 pr-2">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[#EEF0F0] text-[#7B8084] shadow-[inset_0_1px_0_rgba(255,255,255,0.78)]">
            <Cog width={20} height={20} />
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-[21px] font-semibold leading-tight tracking-normal text-[#151515]">{label}</h2>
            <p className="mt-1 text-[12px] font-medium text-[#7C8282]">{context}</p>
          </div>
        </div>
        <Link
          to={detailHref}
          aria-label={`Détails ${label}`}
          title={`Détails ${label}`}
          className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white/60 text-[#222] shadow-sm transition-transform hover:-translate-y-0.5"
        >
          <ArrowUpRight width={18} height={18} />
        </Link>
      </div>

      <div className="absolute left-6 top-[88px] z-10">
        <Delta value={delta} up={up} />
      </div>

      <div className="absolute bottom-7 left-6 z-10 max-w-[160px]">
        <AnimatedNumber
          value={displayValue}
          className={isMissingValue ? "text-[34px] font-semibold leading-none tracking-normal text-black" : "text-[42px] font-semibold leading-none tracking-normal text-black"}
        />
      </div>

      <div className="absolute -bottom-[18px] right-[-34px] h-[132px] w-[212px] opacity-95">
        <Gauge value={gauge} color={color} />
      </div>
    </motion.article>
  );
}

function AlertsPanel({
  title,
  subtitle,
  top,
  bottom,
}: {
  title: string;
  subtitle: string;
  top: Array<[string, string]>;
  bottom: Array<[string, string]>;
}) {
  const [expanded, setExpanded] = React.useState(true);
  return (
    <motion.article
      className="rounded-[28px] p-7"
      style={glass}
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.45, duration: 0.6, ease: EASE_OUT }}
    >
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-[24px] font-semibold text-black">{title}</h2>
          <p className="mt-1 text-[13px] font-medium text-[#848988]">{subtitle}</p>
        </div>
        <button
          type="button"
          aria-label={expanded ? "Réduire" : "Développer"}
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
          className="grid h-10 w-10 place-items-center rounded-full bg-white/60 text-[#222] shadow-sm"
        >
          <ChevronDown width={18} height={18} style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform .3s ease" }} />
        </button>
      </div>
      <div className="mt-10 grid grid-cols-5 gap-3">
        {top.map(([label, value], index) => (
          <div key={label} className="text-center">
            <div className="truncate text-[12px] font-semibold text-[#2E3131]">{label}</div>
            <div className="mt-1 truncate text-[11px] font-medium text-[#7C8282]">{value}</div>
            <motion.div
              className="mt-3 h-[3px] origin-left rounded-full"
              style={{ background: index < 2 ? "#C51F4D" : index < 4 ? ORANGE : "#F2B389" }}
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ delay: 0.6 + index * 0.05, duration: 0.5, ease: EASE_OUT }}
            />
          </div>
        ))}
      </div>
      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            key="bottom"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <div className="mt-9 grid grid-cols-5 gap-3">
              {bottom.map(([label, value], index) => (
                <div key={label} className="text-center">
                  <div className="truncate text-[12px] font-medium text-[#3D4140]">{label}</div>
                  <div className="mt-1 truncate text-[11px] text-[#858A89]">{value}</div>
                  <motion.div
                    className="mt-3 h-[3px] origin-left rounded-full bg-[#C9BE54]"
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ delay: 0.85 + index * 0.05, duration: 0.5, ease: EASE_OUT }}
                  />
                </div>
              ))}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.article>
  );
}

function ProgramOverlay({
  title,
  subtitle,
  value,
  badges,
  loading,
  detailHref,
}: {
  title: string;
  subtitle: string;
  value: string;
  badges: string[];
  loading: boolean;
  detailHref: string;
}) {
  return (
    <div
      className="absolute left-1/2 top-1/2 z-30 w-[300px] -translate-x-1/2 -translate-y-1/2 rounded-[24px] p-5 text-white shadow-[0_28px_66px_rgba(9,12,15,0.34)]"
      style={{
        background: "rgba(15,18,21,0.66)",
        border: "1px solid rgba(255,255,255,0.36)",
        backdropFilter: "blur(22px) saturate(1.16)",
        WebkitBackdropFilter: "blur(22px) saturate(1.16)",
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[23px] font-semibold leading-tight">{title}</h2>
          <p className="mt-1 text-[13px] font-medium text-white/72">{subtitle}</p>
        </div>
        <Link
          to={detailHref}
          aria-label="Ouvrir le programme"
          className="grid h-11 w-11 place-items-center rounded-full border border-white/30 bg-white/10 transition-transform hover:-translate-y-0.5"
        >
          <ArrowUpRight width={18} height={18} />
        </Link>
      </div>
      <div className="mt-7 flex items-end justify-between gap-4">
        <AnimatedNumber value={loading ? "--" : value} className="text-[42px] font-semibold leading-none" />
        <div className="flex items-center">
          {badges.slice(0, 3).map((initials, index) => (
            <span
              key={initials}
              className="grid h-9 w-9 place-items-center rounded-full border-2 border-white/70 text-[10px] font-bold"
              style={{
                marginLeft: index ? -8 : 0,
                background: index === 0 ? "#F3B33E" : index === 1 ? "#FFFFFF" : ORANGE,
                color: index === 1 ? "#111" : "#fff",
              }}
            >
              {initials}
            </span>
          ))}
          <span className="-ml-2 grid h-9 w-9 place-items-center rounded-full border-2 border-white/70 bg-white/65 text-[12px] font-bold text-[#333]">
            {loading ? "..." : `+${Math.max(0, badges.length - 2)}`}
          </span>
        </div>
      </div>
    </div>
  );
}

function ChartPanel({
  title,
  value,
  delta,
  deltaUp,
  unit,
  data,
  emptyLabel,
  loading,
}: {
  title: string;
  value: string;
  delta: string;
  deltaUp: boolean;
  unit: string;
  data: Record<string, number>;
  emptyLabel: string;
  loading: boolean;
}) {
  return (
    <motion.section
      className="rounded-[34px] px-7 pb-5 pt-5"
      style={{ ...glass, background: "rgba(246,248,246,0.60)" }}
      initial={{ opacity: 0, y: 26 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.18, duration: 0.7, ease: EASE_OUT }}
    >
      <div className="flex items-start justify-between gap-5">
        <div>
          <h2 className="text-[17px] font-semibold text-[#202020]">{title}</h2>
          <div className="mt-4 flex items-end gap-4">
            <AnimatedNumber value={loading ? "--" : value} className="text-[38px] font-semibold leading-none text-black" />
            <Delta value={delta} up={deltaUp} />
          </div>
        </div>
        <div className="flex items-center gap-4 pt-11 text-[17px] font-semibold text-[#242424]">
          <span className="h-3 w-[76px] rounded-full" style={{ background: ORANGE }} />
          {unit}
        </div>
      </div>
      <div className="mt-5 h-[250px]">
        <SalesHistogram data={data} emptyLabel={emptyLabel} loading={loading} />
      </div>
    </motion.section>
  );
}

function PeriodMenu({ label }: { label: string }) {
  const { year, quarter, setYear, setQuarter } = useFilters();
  const years = [2024, 2025, 2026];
  const quarters = [1, 2, 3, 4];
  return (
    <Menu
      align="right"
      width={250}
      trigger={({ open, toggle }) => (
        <button
          type="button"
          onClick={toggle}
          aria-haspopup="menu"
          aria-expanded={open}
          className="flex h-14 items-center gap-4 rounded-full px-7 text-[16px] font-medium text-[#222]"
          style={glass}
        >
          {label}
          <ChevronDown width={16} height={16} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .25s ease" }} />
        </button>
      )}
    >
      {() => (
        <div className="p-1">
          <div className="px-2 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-[#8A908D]">Trimestre</div>
          <div className="mb-2 grid grid-cols-4 gap-1.5">
            {quarters.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setQuarter(q)}
                className="rounded-xl py-2 text-[14px] font-semibold transition-colors"
                style={q === quarter ? { background: ORANGE, color: "#fff" } : { background: "rgba(255,255,255,0.6)", color: "#2A2D2D" }}
              >
                T{q}
              </button>
            ))}
          </div>
          <div className="px-2 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-[#8A908D]">Année</div>
          <div className="grid grid-cols-3 gap-1.5">
            {years.map((y) => (
              <button
                key={y}
                type="button"
                onClick={() => setYear(y)}
                className="rounded-xl py-2 text-[14px] font-semibold transition-colors"
                style={y === year ? { background: BLACK, color: "#fff" } : { background: "rgba(255,255,255,0.6)", color: "#2A2D2D" }}
              >
                {y}
              </button>
            ))}
          </div>
        </div>
      )}
    </Menu>
  );
}

function ActionsMenu({ onRefresh }: { onRefresh: () => void }) {
  const toggleFullscreen = () => {
    if (typeof document === "undefined") return;
    if (document.fullscreenElement) {
      document.exitFullscreen?.();
    } else {
      document.documentElement.requestFullscreen?.();
    }
  };
  return (
    <Menu
      align="right"
      width={210}
      trigger={({ open, toggle }) => (
        <button
          type="button"
          aria-label="Plus d'options"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={toggle}
          className="grid h-14 w-14 place-items-center rounded-full text-[#242424]"
          style={glass}
        >
          <Dots width={22} height={22} />
        </button>
      )}
    >
      {(close) => (
        <>
          <MenuItem onClick={() => { onRefresh(); close(); }}>Rafraîchir les données</MenuItem>
          <MenuItem onClick={() => { toggleFullscreen(); close(); }}>Plein écran</MenuItem>
          <MenuItem onClick={close}>Exporter (bientôt)</MenuItem>
        </>
      )}
    </Menu>
  );
}

function RightPanel({
  period,
  cards,
  controlTitle,
  controlSubtitle,
  alertTop,
  alertBottom,
  detailHref,
  onRefresh,
}: {
  period: string;
  cards: DetailMetric[];
  controlTitle: string;
  controlSubtitle: string;
  alertTop: Array<[string, string]>;
  alertBottom: Array<[string, string]>;
  detailHref: string;
  onRefresh: () => void;
}) {
  return (
    <aside className="flex flex-col gap-4">
      <div className="mb-8 flex justify-end gap-3">
        <PeriodMenu label={period} />
        <ActionsMenu onRefresh={onRefresh} />
      </div>

      {cards.map((card, index) => (
        <DetailCard key={card.label} index={index} detailHref={detailHref} {...card} />
      ))}
      <AlertsPanel title={controlTitle} subtitle={controlSubtitle} top={alertTop} bottom={alertBottom} />
    </aside>
  );
}

export function GovernanceOverview() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { dashboard } = useParams();
  const activeDashboard: DashboardKey = DASHBOARD_KEYS.includes(dashboard as DashboardKey)
    ? (dashboard as DashboardKey)
    : "realEstate";

  // URL invalide (/d/inconnu) → on revient au dashboard par défaut.
  React.useEffect(() => {
    if (dashboard && !DASHBOARD_KEYS.includes(dashboard as DashboardKey)) {
      navigate("/", { replace: true });
    }
  }, [dashboard, navigate]);

  const { year, quarter } = useFilters();
  const { data, isLoading, isError, error } = useGovernanceOverview(year, quarter);
  const model = data?.dashboards[activeDashboard]
    ? withPresentation(data.dashboards[activeDashboard])
    : emptyDashboard(activeDashboard, year, quarter, isError ? (error as Error).message : "Chargement API governance");
  const apiStatus = model.status;
  const modelLoading = isLoading && !data;
  const detailHref = `/modules/${DETAIL_MODULE[activeDashboard]}`;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["governance-overview"] });

  return (
    <div className="min-h-screen bg-[#B8B7B4] p-3 text-black sm:p-5 lg:p-6">
      <div className="relative mx-auto min-h-[1040px] w-full max-w-[1840px] overflow-hidden rounded-[42px] border border-white/70 bg-[#F4F7F2] shadow-[0_34px_100px_rgba(36,38,38,0.22)] lg:h-[calc(100vh-3rem)] lg:min-h-[900px]">
        <div className={`pointer-events-none absolute inset-0 rounded-[inherit] ${FRAME_BG}`} />

        <AppHeader />
        <SideRail />

        <main className="relative z-10 grid gap-6 pb-8 pl-24 pr-5 lg:absolute lg:inset-0 lg:block lg:px-0 lg:pb-0">
          <section className="relative z-20 mt-8 max-w-[500px] sm:ml-[8%] lg:absolute lg:left-[7.8%] lg:top-[13%] lg:ml-0 lg:w-[34%]">
            <h1 className="text-[48px] font-medium leading-[1.03] tracking-normal text-black sm:text-[60px] lg:text-[68px]">
              {model.title}
            </h1>
            <p className="mt-7 max-w-[360px] text-[16px] font-medium leading-6 text-[#777C7D]">{model.subtitle}</p>
            <p className="mt-4 inline-flex rounded-full bg-white/70 px-4 py-2 text-[12px] font-semibold text-[#6D7372] shadow-sm">
              {apiStatus}
            </p>
          </section>

          <div className="relative z-10 mt-4 h-[500px] overflow-hidden lg:absolute lg:left-[17%] lg:top-[5.8%] lg:mt-0 lg:h-[64%] lg:w-[68%] lg:overflow-visible">
            <img
              src={model.imageSrc}
              alt=""
              className={
                model.imageMode === "contain"
                  ? "pointer-events-none h-full w-full scale-[1.08] object-contain opacity-100 drop-shadow-[0_34px_46px_rgba(32,34,34,0.16)]"
                  : "pointer-events-none h-full w-full rounded-[34px] object-cover opacity-[0.92] shadow-[0_34px_70px_rgba(32,34,34,0.18)]"
              }
            />
            {model.imageMode === "cover" ? (
              <div className="pointer-events-none absolute inset-0 rounded-[34px] bg-gradient-to-r from-[#F4F7F2]/85 via-[#F4F7F2]/20 to-[#F4F7F2]/55" />
            ) : null}
            <ProgramOverlay
              title={model.overlayTitle}
              subtitle={model.overlaySubtitle}
              value={model.overlayValue}
              badges={model.overlayBadges}
              loading={modelLoading}
              detailHref={detailHref}
            />
            <div className="pointer-events-none absolute inset-y-0 left-0 w-[16%] bg-gradient-to-r from-[#F4F7F2] via-[#F4F7F2]/80 to-transparent" />
            <div className="pointer-events-none absolute inset-x-[10%] bottom-0 h-20 rounded-full bg-black/20 blur-3xl" />
          </div>

          <div className="relative z-20 lg:absolute lg:bottom-[4.8%] lg:left-[7.8%] lg:right-[390px]">
            <ChartPanel
              title={model.chartTitle}
              value={model.chartValue}
              delta={model.chartDelta}
              deltaUp={model.chartDeltaUp}
              unit={model.chartUnit}
              data={model.chartData}
              emptyLabel={model.chartEmptyLabel}
              loading={modelLoading}
            />
          </div>

          <div className="relative z-20 lg:absolute lg:right-[2.8%] lg:top-[16.8%] lg:w-[330px]">
            <RightPanel
              period={model.periodLabel}
              cards={model.cards}
              controlTitle={model.controlTitle}
              controlSubtitle={model.controlSubtitle}
              alertTop={model.alertTop}
              alertBottom={model.alertBottom}
              detailHref={detailHref}
              onRefresh={refresh}
            />
          </div>
        </main>
      </div>
    </div>
  );
}
