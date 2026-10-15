import * as React from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { motion } from "framer-motion";
import { Navigate, useParams } from "react-router-dom";

import { PageShell } from "@/components/chrome/PageShell";
import { glass } from "@/components/chrome/theme";
import { AnimatedNumber } from "@/components/overview/AnimatedNumber";
import { Gauge } from "@/components/overview/Gauge";
import { AiQueryBox } from "@/components/overview/AiQueryBox";
import { AlertsPanel } from "@/components/overview/AlertsPanel";
import { GraphesRh } from "@/components/overview/GraphesRh";
import { HumanCapitalScore } from "@/components/overview/HumanCapitalScore";
import { ArrowUpRight, CheckCircle, TriDown, TriUp } from "@/components/overview/icons";
import { EASE_OUT } from "@/lib/motion";
import { useModuleData } from "@/api/governance";
import { formatInt, formatXof } from "@/lib/format";
import { parametresFiltres, useFilters } from "@/store/filters";
import {
  getModule,
  type ModuleChart,
  type ModuleDef,
  type ModuleKpi,
  type ModuleRow,
  type ModuleSection,
  estModuleRh,
  RH_SOURCES,
} from "@/lib/modules";
import type { ModuleDataValue } from "@/types/governance";
import { ecartAffiche } from "@/lib/ecarts";

const EMPTY_TEXT = "En attente Data Warehouse";
const AXIS_LABEL_STYLE = { color: "#8A9291", fontSize: 11, fontWeight: 700 };
const GRID_LINE_STYLE = { color: "rgba(116,124,125,0.13)" };

function isUnavailable(value: string) {
  return value === "N/D" || value === "--" || value === "-";
}

/** Nombre d'emplacements d'axe, SANS les nommer.
 *
 *  La version précédente rendait des libellés : « Jan…Aout » pour une série,
 *  « Zone A…E » pour une carte de chaleur, « Phase 1…4 » pour un Gantt. Aucun de
 *  ces noms ne venait d'une source — ils affirmaient une granularité mensuelle,
 *  un découpage en zones ou un découpage en phases que le mart, muet, n'a jamais
 *  déclarés. Un axe nommé est une donnée : on garde donc la place, pas le nom.
 */
function chartSlots(chart: ModuleChart) {
  if (chart.type === "heatmap") return 5;
  if (chart.type === "gantt" || chart.type === "funnel") return 4;
  return 8;
}

function emptyLabels(chart: ModuleChart) {
  return Array.from({ length: chartSlots(chart) }, () => "");
}

function emptyGraphic(source: string): NonNullable<EChartsOption["graphic"]> {
  return [
    {
      type: "group",
      left: "center",
      top: "middle",
      children: [
        {
          type: "rect",
          shape: { x: -154, y: -32, width: 308, height: 64, r: 22 },
          style: {
            fill: "rgba(255,255,255,0.72)",
            stroke: "rgba(255,255,255,0.82)",
            shadowBlur: 18,
            shadowColor: "rgba(45,52,56,0.08)",
          },
        },
        {
          type: "text",
          left: -118,
          top: -16,
          style: {
            // Un graphe RH n'attend plus le Data Warehouse : il attend une série
            // que ni Shield ni Odoo ne servent encore pour cette vue.
            text: source === RH_SOURCES ? "Aucune série servie" : EMPTY_TEXT,
            fill: "#222829",
            font: "700 13px Manrope, sans-serif",
          },
        },
        {
          type: "text",
          left: -118,
          top: 6,
          style: {
            text: source,
            fill: "#7B8484",
            font: "600 11px Manrope, sans-serif",
          },
        },
      ],
    },
  ];
}

function commonChartOption(chart: ModuleChart, accent: string): EChartsOption {
  const labels = emptyLabels(chart);
  const base: EChartsOption = {
    animation: true,
    animationDuration: 700,
    animationEasing: "cubicOut",
    backgroundColor: "transparent",
    color: [accent, "#42BFA0", "#D92B55", "#5B6470"],
    grid: { left: 20, right: 18, top: 24, bottom: 28, containLabel: true },
    tooltip: {
      show: true,
      trigger: "axis",
      backgroundColor: "rgba(255,255,255,0.92)",
      borderColor: "rgba(255,255,255,0.85)",
      textStyle: { color: "#1D2222", fontFamily: "Manrope" },
      extraCssText: "box-shadow:0 18px 40px rgba(31,35,38,.12);border-radius:14px;",
      formatter: () => (chart.source === RH_SOURCES ? "Aucune série servie par Shield ni Odoo." : "Aucune donnée servie par le mart."),
    },
    graphic: emptyGraphic(chart.source),
  };

  if (chart.type === "pie") {
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: "item" },
      series: [
        {
          type: "pie",
          radius: ["58%", "78%"],
          center: ["50%", "55%"],
          avoidLabelOverlap: true,
          stillShowZeroSum: false,
          emptyCircleStyle: {
            color: "rgba(255,255,255,0.34)",
            borderColor: "rgba(226,230,230,0.9)",
            borderWidth: 24,
          },
          label: { show: false },
          labelLine: { show: false },
          data: [],
        },
      ],
    };
  }

  if (chart.type === "heatmap") {
    return {
      ...base,
      grid: { left: 58, right: 20, top: 18, bottom: 34 },
      xAxis: { type: "category", data: labels, axisLine: { show: false }, axisTick: { show: false }, axisLabel: AXIS_LABEL_STYLE },
      yAxis: {
        type: "category",
        // Ces quatre dimensions étaient nommées sans qu'aucune source ne les déclare.
        data: ["", "", "", ""],
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: AXIS_LABEL_STYLE,
      },
      visualMap: { show: false, min: 0, max: 100 },
      series: [{ type: "heatmap", data: [], itemStyle: { borderRadius: 9, borderWidth: 5, borderColor: "rgba(255,255,255,0.78)" } }],
    };
  }

  if (chart.type === "radar") {
    return {
      ...base,
      radar: {
        radius: "64%",
        center: ["50%", "54%"],
        splitNumber: 4,
        axisName: AXIS_LABEL_STYLE,
        axisLine: { lineStyle: GRID_LINE_STYLE },
        splitLine: { lineStyle: GRID_LINE_STYLE },
        splitArea: { areaStyle: { color: ["rgba(255,255,255,0.2)", "rgba(255,255,255,0.42)"] } },
        indicator: labels.slice(0, 5).map((name) => ({ name, max: 100 })),
      },
      series: [
        {
          type: "radar",
          // `0` traçait un polygone : un radar entièrement au minimum se lit comme
          // un score nul, pas comme une absence de mesure. `null` ne trace rien.
          data: [{ name: "EDW", value: labels.slice(0, 5).map(() => null) }],
          areaStyle: { color: accent, opacity: 0.06 },
          lineStyle: { color: accent, opacity: 0.18, width: 2 },
          symbolSize: 0,
        },
      ],
    };
  }

  if (chart.type === "funnel") {
    return {
      ...base,
      series: [
        {
          type: "funnel",
          left: "12%",
          top: 24,
          width: "76%",
          height: "76%",
          minSize: "28%",
          maxSize: "92%",
          sort: "descending",
          gap: 8,
          label: { show: false },
          itemStyle: { borderRadius: 14, borderColor: "rgba(255,255,255,0.78)", borderWidth: 3 },
          data: [],
        },
      ],
    };
  }

  const asGantt = chart.type === "gantt";
  return {
    ...base,
    xAxis: {
      type: "category",
      // « S1…S6 » annonçait un découpage hebdomadaire qu'aucune source ne porte.
      data: asGantt ? ["", "", "", "", "", ""] : labels,
      boundaryGap: chart.type === "bar" || asGantt,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: AXIS_LABEL_STYLE,
    },
    // Sans donnée, ni l'échelle ni l'unité ne sont connues : imposer 0 → 100 avec
    // un suffixe « % » affirmait que l'indicateur est un pourcentage et qu'il est
    // borné, ce qui est faux pour une masse salariale ou un effectif.
    yAxis: {
      type: "value",
      splitLine: { lineStyle: GRID_LINE_STYLE },
      axisLabel: { ...AXIS_LABEL_STYLE, show: false },
    },
    series: [
      {
        type: chart.type === "bar" || asGantt ? "bar" : "line",
        data: labels.map(() => null),
        smooth: true,
        symbolSize: 7,
        barWidth: asGantt ? 16 : 14,
        itemStyle: {
          borderRadius: asGantt ? 9 : [10, 10, 4, 4],
          color: accent,
          opacity: 0.36,
        },
        lineStyle: { color: accent, width: 3 },
        areaStyle: chart.type === "line" ? { color: accent, opacity: 0.08 } : undefined,
      },
    ],
  };
}

function valeurAffichee(real: ModuleDataValue | undefined): string | null {
  // `null` reste `null` : formater une absence donnait « 0 F CFA » et un ton vert.
  if (!real || real.value === null || real.value === undefined) return null;
  if (real.format === "currency") return formatXof(real.value);
  if (real.format === "pct") return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(real.value)} %`;
  if (real.format === "int") return formatInt(real.value);
  return String(real.value);
}

/** La provenance DITE : la source réelle, et « aujourd'hui » pour une mesure live.
 *  Remplace le « Donnée EDW » écrit en dur, qui s'affichait quelle que soit la source. */
function provenance(real: ModuleDataValue): string {
  const source = real.source_label || "Source";
  // Le chiffre principal est celui de la PÉRIODE quand elle existe : dire
  // « aujourd'hui » à côté contredirait le libellé de période. « Aujourd'hui »
  // n'appartient qu'à la pastille live.
  if (real.periode?.libelle) return `${source} · ${real.periode.libelle}`;
  return real.instant ? `${source} · aujourd'hui` : source;
}

function KpiCard({ kpi, index, values }: { kpi: ModuleKpi; index: number; values?: Record<string, ModuleDataValue> }) {
  const real = values?.[kpi.label];
  const realValue = valeurAffichee(real);
  const live = real?.aujourd_hui ? valeurAffichee({ ...real, value: real.aujourd_hui.value }) : null;
  const ecart = real ? ecartAffiche(real.metric_id, real.precedente ?? undefined) : null;
  // Une carte résolue par le registre mais sans valeur porte un MOTIF : on le
  // montre à la place du « mart à connecter » générique.
  const motif = real && realValue === null ? real.reason || "Aucune donnée servie." : null;
  const unavailable = !realValue && (Boolean(motif) || isUnavailable(kpi.value));
  return (
    <motion.article
      className="relative h-[168px] overflow-hidden rounded-[30px] p-5"
      style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.82),rgba(242,247,247,0.58))" }}
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -5, transition: { duration: 0.25, ease: EASE_OUT } }}
      transition={{ delay: 0.08 + index * 0.035, duration: 0.5, ease: EASE_OUT }}
    >
      <span className="absolute right-5 top-5 h-2.5 w-2.5 rounded-full" style={{ background: kpi.color }} />
      <h3 className="max-w-[190px] text-[15px] font-semibold leading-tight text-[#1A1C1C]">{kpi.label}</h3>
      <span
        className="absolute left-5 top-[64px] inline-flex items-center gap-1.5 text-[12px] font-bold"
        style={{ color: realValue ? "#1F9E75" : unavailable ? "#C43252" : kpi.up ? "#202526" : "#C43252" }}
      >
        {realValue && real ? provenance(real) : motif ? "Non disponible" : kpi.delta}
        {realValue || unavailable ? null : kpi.up ? <TriUp width={10} height={10} /> : <TriDown width={10} height={10} />}
      </span>
      {/* Avec un motif, le « N/D » se fait plus petit : le motif EST l'information
          utile de la carte, et à 32 px le chiffre absent le recouvrait. */}
      <AnimatedNumber
        value={realValue ?? (motif ? "N/D" : kpi.value)}
        className={`absolute bottom-8 left-5 font-semibold leading-none text-black ${motif ? "text-[22px]" : "text-[32px]"}`}
      />
      {motif ? (
        <p className="absolute left-5 right-[92px] top-[82px] line-clamp-2 text-[11px] font-medium leading-[1.25] text-[#8A6E36]" title={motif}>
          {motif}
        </p>
      ) : ecart ? (
        <p className="absolute left-5 top-[84px] text-[11px] font-bold" style={{ color: ecart.favorable ? "#1F9E75" : "#C43252" }}>
          {ecart.texte}
        </p>
      ) : null}
      {/* La mesure du jour, live, à part de la période : elle ne suit pas le
          filtre de période et le dit. */}
      {real?.aujourd_hui ? (
        <span className="absolute bottom-[38px] right-5 rounded-full bg-white/80 px-2 py-0.5 text-[10.5px] font-bold text-[#4A5352]"
              title={real.aujourd_hui.reason || "Mesure live du jour"}>
          Aujourd&apos;hui · {live ?? "N/D"}
        </span>
      ) : null}
      {real?.metric_id || kpi.source ? (
        <span className="absolute bottom-3 left-5 max-w-[165px] truncate text-[10px] font-bold uppercase tracking-[0.12em] text-[#8A9291]"
              title={real?.definition || undefined}>
          {real?.metric_id || kpi.source}
        </span>
      ) : null}
      <div className="absolute -bottom-[24px] right-[-46px] h-[126px] w-[204px]" style={{ opacity: unavailable ? 0.5 : 0.95 }}>
        <Gauge value={kpi.gauge} color={kpi.color} />
      </div>
    </motion.article>
  );
}

function RowList({ rows, showArrow, compact = false }: { rows: ModuleRow[]; showArrow?: boolean; compact?: boolean }) {
  return (
    <div className={compact ? "grid gap-2.5" : "grid gap-3"}>
      {rows.map((row, index) => (
        <motion.div
          key={`${row.title}-${index}`}
          className={`flex items-center gap-4 rounded-[22px] ${compact ? "px-4 py-3" : "px-5 py-4"}`}
          style={{ ...glass, background: "rgba(255,255,255,0.58)" }}
          initial={{ opacity: 0, x: -14 }}
          animate={{ opacity: 1, x: 0 }}
          whileHover={{ x: 4, transition: { duration: 0.2, ease: EASE_OUT } }}
          transition={{ delay: 0.08 + index * 0.04, duration: 0.42, ease: EASE_OUT }}
        >
          <span className="h-10 w-1.5 shrink-0 rounded-full" style={{ background: row.accent }} />
          <div className="min-w-0 flex-1">
            <div className="truncate text-[15px] font-semibold text-[#1B1D1D]">{row.title}</div>
            <div className="truncate text-[12px] font-semibold text-[#7C8282]">{row.detail}</div>
          </div>
          {showArrow ? (
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white/65 text-[#222]">
              <ArrowUpRight width={16} height={16} />
            </span>
          ) : null}
        </motion.div>
      ))}
    </div>
  );
}

function ChartCard({ chart, accent, index }: { chart: ModuleChart; accent: string; index: number }) {
  const option = React.useMemo(() => commonChartOption(chart, accent), [chart, accent]);
  return (
    <motion.article
      className="relative min-h-[338px] overflow-hidden rounded-[32px] p-6"
      style={{
        ...glass,
        background:
          "linear-gradient(135deg,rgba(255,255,255,0.78),rgba(241,247,247,0.58)), radial-gradient(circle at 86% 10%, rgba(255,135,53,0.12), transparent 34%)",
      }}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.16 + index * 0.04, duration: 0.52, ease: EASE_OUT }}
    >
      <div className="mb-3 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="truncate text-[18px] font-semibold text-[#151818]">{chart.title}</h3>
          <p className="mt-1 line-clamp-2 text-[12px] font-semibold text-[#7C8384]">{chart.subtitle}</p>
        </div>
        <span className="shrink-0 rounded-full bg-white/70 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[#707879]">
          {chart.type}
        </span>
      </div>
      <div className="h-[230px] rounded-[26px] bg-white/25 p-1">
        <ReactECharts
          option={option}
          notMerge
          lazyUpdate
          opts={{ renderer: "svg" }}
          style={{ height: "100%", width: "100%" }}
        />
      </div>
      <div className="mt-4 flex items-center justify-between gap-4">
        <span className="min-w-0 truncate text-[11px] font-bold uppercase tracking-[0.14em] text-[#7C8384]">{chart.source}</span>
        <span className="inline-flex shrink-0 items-center gap-2 rounded-full bg-[#FFF4EC] px-3 py-1 text-[11px] font-bold text-[#D86922]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#FF8735]" />
          Lecture seule
        </span>
      </div>
    </motion.article>
  );
}

function AnalyticsSection({ section, accent, index }: { section: ModuleSection; accent: string; index: number }) {
  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
      <ChartCard chart={section.chart} accent={accent} index={index} />
      <motion.aside
        className="min-h-[338px] rounded-[32px] p-6"
        style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.72),rgba(244,248,248,0.52))" }}
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.18 + index * 0.04, duration: 0.52, ease: EASE_OUT }}
      >
        <div className="mb-5">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#8B9394]">{section.source}</p>
          <h3 className="mt-2 text-[20px] font-semibold leading-tight text-[#171A1A]">{section.title}</h3>
          <p className="mt-2 text-[13px] font-semibold leading-relaxed text-[#7C8384]">{section.subtitle}</p>
        </div>
        <RowList rows={section.rows} compact />
      </motion.aside>
    </section>
  );
}

function DataContract({ module }: { module: ModuleDef }) {
  return (
    <motion.div
      className="rounded-[26px] px-6 py-5"
      style={{ ...glass, background: "rgba(255,255,255,0.54)" }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.35, duration: 0.5 }}
    >
      <div className="flex flex-wrap items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-full bg-[#E8F5EF] text-[#1E9B69]">
          <CheckCircle width={18} height={18} />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-[15px] font-semibold text-[#171A1A]">Contrat de données gouverné</h3>
          {estModuleRh(module) ? (
            <p className="mt-1 text-[13px] font-medium leading-relaxed text-[#697071]">
              Aucune donnée chiffrée n'est inventée. Les cartes sont alimentées par{" "}
              <span className="font-bold text-[#252A2B]">Kaydan Shield</span> et{" "}
              <span className="font-bold text-[#252A2B]">Odoo RH</span>, avec leur provenance ; une mesure
              « aujourd'hui » est live et ne suit pas le filtre de période. Une carte sans source affiche N/D et
              dit pourquoi.
            </p>
          ) : (
            <p className="mt-1 text-[13px] font-medium leading-relaxed text-[#697071]">
              Aucune donnée chiffrée n'est inventée. Les KPI, graphiques et analyses s'activent uniquement quand la
              source <span className="font-bold text-[#252A2B]">{module.source}</span> est matérialisée dans le Data Warehouse.
            </p>
          )}
        </div>
      </div>
    </motion.div>
  );
}

/* `HrGovernanceControls` a été RETIRÉ.
 *
 *  Le bloc affichait, sur les 19 modules dont la clé commence par « hr- », une
 *  barre de recherche « Collaborateur, matricule, métier » en `readOnly value=""`
 *  — on ne pouvait même pas y taper —, six puces de regroupement
 *  (Groupe/Filiale/Département/Site/Métier/Période) sans le moindre gestionnaire,
 *  et trois boutons d'export PDF / Excel / PowerPoint qui n'appelaient rien.
 *  `grep -c onClick` sur ce fichier rendait 0.
 *
 *  Un contrôle qui ne fait rien est une affirmation fausse sur ce que l'écran
 *  sait faire : même registre qu'un chiffre inventé, et plus coûteux, parce qu'un
 *  utilisateur clique, ne voit rien se produire et conclut que l'outil est cassé.
 *
 *  Ce qui EST filtrable l'est ailleurs et réellement : Période et Filiale, par
 *  `GlobalDashboardFilters`, relié au store lu par la requête. Les exports PDF et
 *  Excel ont bien des générateurs (`apps/governance/exports.py`) mais aucun
 *  endpoint pour cette page : c'est un lot à part. PowerPoint n'a d'implémentation
 *  à aucun niveau — ni endpoint, ni générateur, ni dépendance déclarée.
 *
 *  La recherche nominative, elle, ne revient pas sans décision préalable : c'est
 *  une donnée à caractère personnel sur la présence d'individus identifiés, et
 *  qui peut chercher qui se tranche avant de l'implémenter.
 */

function AiGuardrail({ module }: { module: ModuleDef }) {
  if (module.kind !== "ai") return null;
  return (
    <motion.div
      className="rounded-[30px] p-6"
      style={{ ...glass, background: "linear-gradient(135deg,rgba(10,10,10,0.86),rgba(35,38,39,0.74))", color: "#fff" }}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.25, duration: 0.48, ease: EASE_OUT }}
    >
      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-white/58">Principe IA</p>
      <h3 className="mt-2 text-[22px] font-semibold">Ancrage strict sur le Data Warehouse</h3>
      <p className="mt-2 max-w-[820px] text-[14px] font-medium leading-relaxed text-white/68">
        Le centre IA ne génère pas de diagnostic tant que les marts et vues analytiques déclarés ne sont pas disponibles.
        Les recommandations, simulations et prévisions doivent rester traçables jusqu'à leur source.
      </p>
    </motion.div>
  );
}

function ModuleBody({ module, values }: { module: ModuleDef; values?: Record<string, ModuleDataValue> }) {
  const hasKpis = Boolean(module.kpis?.length);
  const isAlerts = module.key === "alerts" || module.key === "hr-alerts";
  const isAi = module.kind === "ai";
  const rowsOnly = !hasKpis && module.rows?.length && !isAi && !isAlerts;

  if (rowsOnly) {
    return <RowList rows={module.rows ?? []} showArrow={module.kind === "notifications" || module.kind === "help"} />;
  }

  return (
    <div className="space-y-8">
      <DataContract module={module} />
      {module.key === "hr-executive" ? <HumanCapitalScore /> : null}
      {isAlerts ? <AlertsPanel /> : null}
      <AiGuardrail module={module} />
      {isAi ? <AiQueryBox /> : null}

      {hasKpis ? (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-5">
          {(module.kpis ?? []).map((kpi, index) => (
            <KpiCard key={`${kpi.label}-${index}`} kpi={kpi} index={index} values={values} />
          ))}
        </div>
      ) : null}

      {module.rows?.length ? (
        <div className="grid gap-5 xl:grid-cols-2">
          <RowList rows={module.rows} showArrow={module.kind === "notifications" || module.kind === "help"} />
        </div>
      ) : null}

      {/* Capital Humain : les graphes RÉELS du module, lus dans l'historique sous
          les filtres, et la liste motivée de ce que rien ne trace — plus aucun
          cadre de graphe vide. Les autres domaines gardent le catalogue. */}
      {estModuleRh(module) ? (
        <GraphesRh moduleKey={module.key} sections={module.sections ?? []} />
      ) : module.sections?.length ? (
        <div className="grid gap-6">
          {module.sections.map((section, index) => (
            <AnalyticsSection key={`${section.title}-${index}`} section={section} accent={module.accent} index={index} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

interface ModulePageProps {
  moduleKey?: string;
}

export function ModulePage({ moduleKey }: ModulePageProps = {}) {
  const { key } = useParams();
  const resolvedKey = moduleKey ?? key;
  const filtres = useFilters();
  // UNE conversion des filtres en paramètres serveur, partagée par tous les appels.
  const parametres = parametresFiltres(filtres).toString();
  const { data: moduleData } = useModuleData(resolvedKey, parametres);
  const module = getModule(resolvedKey);
  if (!module) {
    return <Navigate to="/dashboard" replace />;
  }
  return (
    <PageShell
      title={module.title}
      subtitle={module.subtitle}
      status={module.status}
      icon={module.icon}
      accent={module.accent}
    >
      <ModuleBody module={module} values={moduleData?.values} />
    </PageShell>
  );
}
