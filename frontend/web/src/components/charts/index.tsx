/** Graphiques K-Insight pilotés par le contrat KMetric.
 *
 *  Quatre briques manquantes de la mission, bâties sur le socle ECharts existant :
 *  TrendChart (3/6/12 mois), ComparisonChart (réel vs objectif/budget/N-1),
 *  BreakdownChart (répartition filiale/site/catégorie) et FunnelChart (pipeline).
 *  Aucune ne trace quoi que ce soit sans point réel : elles délèguent alors à
 *  EmptyChartState, déjà présent dans le kit.
 */
import * as React from "react";
import type { EChartsOption } from "echarts";

import type { DataState } from "@/components/ui/kit";
import {
  hasRealBreakdown,
  hasRealSeries,
  type KBreakdownItem,
  type KSeriesPoint,
} from "@/lib/kmetric";

import { AXIS_LABEL, BASE_GRID, BASE_TOOLTIP, ChartFrame, SPLIT_LINE, toEchartsValues, useAccent } from "./base";

const GREY = "#B8BEBC";

interface CommonProps {
  state: DataState;
  source?: string;
  height?: number;
  emptyMessage?: string;
  emptyAction?: { label: string; to: string };
}

/* ── TrendChart ────────────────────────────────────────────────────────────── */
export function TrendChart({
  series,
  label,
  unit,
  state,
  source,
  height,
  emptyMessage,
  emptyAction,
}: CommonProps & { series?: KSeriesPoint[]; label: string; unit?: string }) {
  const accent = useAccent();
  const points = series ?? [];
  const option = React.useMemo<EChartsOption>(
    () => ({
      grid: BASE_GRID,
      tooltip: { ...BASE_TOOLTIP, valueFormatter: (v) => (v === null ? "N/D" : `${v}${unit ? ` ${unit}` : ""}`) },
      xAxis: {
        type: "category",
        data: points.map((p) => p.label),
        axisLabel: AXIS_LABEL,
        axisLine: { lineStyle: { color: "rgba(116,124,125,0.22)" } },
        axisTick: { show: false },
      },
      yAxis: { type: "value", axisLabel: AXIS_LABEL, splitLine: SPLIT_LINE },
      series: [
        {
          name: label,
          type: "line",
          smooth: true,
          showSymbol: false,
          // `connectNulls: false` : une donnée manquante laisse un trou visible,
          // au lieu de relier deux points comme si la mesure existait.
          connectNulls: false,
          lineStyle: { width: 3, color: accent },
          areaStyle: { color: accent, opacity: 0.12 },
          itemStyle: { color: accent },
          data: toEchartsValues(points.map((p) => p.value)),
        },
      ],
    }),
    [points, label, unit, accent],
  );

  return (
    <ChartFrame
      hasData={hasRealSeries(series)}
      state={state}
      option={option}
      height={height}
      source={source}
      emptyMessage={emptyMessage}
      emptyAction={emptyAction}
      ariaLabel={`Tendance ${label}`}
    />
  );
}

/* ── ComparisonChart ───────────────────────────────────────────────────────── */
export function ComparisonChart({
  series,
  label,
  compareLabel,
  unit,
  state,
  source,
  height,
  emptyMessage,
  emptyAction,
}: CommonProps & { series?: KSeriesPoint[]; label: string; compareLabel: string; unit?: string }) {
  const accent = useAccent();
  const points = series ?? [];
  const option = React.useMemo<EChartsOption>(
    () => ({
      grid: BASE_GRID,
      legend: { bottom: 0, itemWidth: 14, itemHeight: 8, textStyle: { ...AXIS_LABEL, fontSize: 11 } },
      tooltip: { ...BASE_TOOLTIP, valueFormatter: (v) => (v === null ? "N/D" : `${v}${unit ? ` ${unit}` : ""}`) },
      xAxis: {
        type: "category",
        data: points.map((p) => p.label),
        axisLabel: AXIS_LABEL,
        axisLine: { lineStyle: { color: "rgba(116,124,125,0.22)" } },
        axisTick: { show: false },
      },
      yAxis: { type: "value", axisLabel: AXIS_LABEL, splitLine: SPLIT_LINE },
      series: [
        {
          name: label,
          type: "bar",
          barMaxWidth: 22,
          itemStyle: { color: accent, borderRadius: [6, 6, 0, 0] },
          data: toEchartsValues(points.map((p) => p.value)),
        },
        {
          name: compareLabel,
          type: "bar",
          barMaxWidth: 22,
          itemStyle: { color: GREY, borderRadius: [6, 6, 0, 0], opacity: 0.55 },
          data: toEchartsValues(points.map((p) => p.compare)),
        },
      ],
    }),
    [points, label, compareLabel, unit, accent],
  );

  // Il faut au moins une valeur ET un comparatif : sinon ce n'est pas une comparaison.
  const comparable =
    hasRealSeries(series) && points.some((p) => p.compare !== null && p.compare !== undefined);

  return (
    <ChartFrame
      hasData={comparable}
      state={state}
      option={option}
      height={height}
      source={source}
      emptyMessage={emptyMessage ?? "Comparaison indisponible : il manque la série de référence (objectif, budget ou N-1)."}
      emptyAction={emptyAction}
      ariaLabel={`${label} comparé à ${compareLabel}`}
    />
  );
}

/* ── BreakdownChart ────────────────────────────────────────────────────────── */
export function BreakdownChart({
  items,
  unit,
  state,
  source,
  height,
  emptyMessage,
  emptyAction,
}: CommonProps & { items?: KBreakdownItem[]; unit?: string }) {
  const accent = useAccent();
  // Les entrées sans valeur sont ÉCARTÉES du tracé (pas mises à zéro) : une barre
  // à zéro se lirait comme une mesure nulle, ce qui serait faux.
  const real = (items ?? []).filter((i) => i.value !== null && i.value !== undefined);
  const sorted = [...real].sort((a, b) => (b.value as number) - (a.value as number));

  const option = React.useMemo<EChartsOption>(
    () => ({
      grid: { ...BASE_GRID, left: 8 },
      tooltip: { ...BASE_TOOLTIP, trigger: "item", valueFormatter: (v) => `${v}${unit ? ` ${unit}` : ""}` },
      xAxis: { type: "value", axisLabel: AXIS_LABEL, splitLine: SPLIT_LINE },
      yAxis: {
        type: "category",
        data: sorted.map((i) => i.label).reverse(),
        axisLabel: { ...AXIS_LABEL, width: 110, overflow: "truncate" },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: "bar",
          barMaxWidth: 18,
          itemStyle: { color: accent, borderRadius: [0, 6, 6, 0] },
          data: sorted.map((i) => i.value).reverse(),
        },
      ],
    }),
    [sorted, unit, accent],
  );

  return (
    <ChartFrame
      hasData={hasRealBreakdown(items)}
      state={state}
      option={option}
      height={height}
      source={source}
      emptyMessage={emptyMessage}
      emptyAction={emptyAction}
      ariaLabel="Répartition"
    />
  );
}

/* ── FunnelChart ───────────────────────────────────────────────────────────── */
export function FunnelChart({
  steps,
  unit,
  state,
  source,
  height,
  emptyMessage,
  emptyAction,
}: CommonProps & { steps?: KBreakdownItem[]; unit?: string }) {
  const accent = useAccent();
  const real = (steps ?? []).filter((s) => s.value !== null && s.value !== undefined);

  const option = React.useMemo<EChartsOption>(
    () => ({
      tooltip: { ...BASE_TOOLTIP, trigger: "item", valueFormatter: (v) => `${v}${unit ? ` ${unit}` : ""}` },
      series: [
        {
          type: "funnel",
          left: 12,
          right: 12,
          top: 12,
          bottom: 12,
          minSize: "20%",
          gap: 3,
          label: { position: "inside", color: "#fff", fontWeight: 700, fontSize: 11 },
          itemStyle: { borderColor: "#fff", borderWidth: 2, color: accent },
          data: real.map((s, i) => ({
            name: s.label,
            value: s.value as number,
            // Dégradé d'opacité pour lire l'ordre des étapes sans inventer de couleurs.
            itemStyle: { color: accent, opacity: 1 - i * 0.13 },
          })),
        },
      ],
    }),
    [real, unit, accent],
  );

  return (
    <ChartFrame
      hasData={real.length > 0}
      state={state}
      option={option}
      height={height}
      source={source}
      emptyMessage={emptyMessage}
      emptyAction={emptyAction}
      ariaLabel="Entonnoir de conversion"
    />
  );
}
