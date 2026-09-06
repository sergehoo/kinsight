/** Socle commun des graphiques K-Insight.
 *
 *  ECharts est déjà la librairie du projet (echarts + echarts-for-react) : on ne
 *  vient pas en ajouter une seconde. Ce module factorise le thème d'axes, le
 *  conteneur et surtout la RÈGLE : sans point réel, on ne trace rien — on rend
 *  l'état vide gouverné. Aucune série décorative, jamais (ADR-0007).
 *
 *  Le style global `.echarts-for-react { width: 100% !important }` impose que la
 *  largeur vienne du parent : le conteneur ci-dessous ne fixe donc qu'une hauteur.
 */
import * as React from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

import { EmptyChartState, type DataState } from "@/components/ui/kit";

export const AXIS_LABEL = { color: "#8A9291", fontSize: 11, fontWeight: 700 } as const;
export const SPLIT_LINE = { lineStyle: { color: "rgba(116,124,125,0.13)" } } as const;

/** Couleur d'accent du domaine actif, lue depuis les tokens CSS.
 *  ECharts peint dans un canvas : `var(--domain-accent)` n'y est pas résolu, il
 *  faut donc la valeur calculée. */
export function useAccent(): string {
  const [accent, setAccent] = React.useState("#FF8735");
  React.useEffect(() => {
    const read = () =>
      getComputedStyle(document.documentElement).getPropertyValue("--domain-accent").trim() || "#FF8735";
    setAccent(read());
    // Le token change au changement de domaine : on resynchronise après la transition.
    const id = window.setTimeout(() => setAccent(read()), 400);
    return () => window.clearTimeout(id);
  });
  return accent;
}

export const BASE_GRID = { left: 8, right: 12, top: 24, bottom: 4, containLabel: true } as const;

export const BASE_TOOLTIP = {
  trigger: "axis" as const,
  backgroundColor: "rgba(255,255,255,0.96)",
  borderColor: "rgba(255,255,255,0.9)",
  textStyle: { color: "#16191A", fontSize: 12, fontWeight: 600 },
  extraCssText: "border-radius:14px;box-shadow:0 18px 42px rgba(40,44,48,0.14);",
};

interface ChartFrameProps {
  /** false → on rend l'état vide gouverné plutôt qu'un graphe sans données. */
  hasData: boolean;
  state: DataState;
  option: EChartsOption;
  height?: number;
  source?: string;
  emptyMessage?: string;
  emptyAction?: { label: string; to: string };
  ariaLabel: string;
}

export function ChartFrame({
  hasData,
  state,
  option,
  height = 230,
  source,
  emptyMessage,
  emptyAction,
  ariaLabel,
}: ChartFrameProps) {
  if (!hasData) {
    return (
      <div style={{ minHeight: height }}>
        <EmptyChartState state={state} source={source} message={emptyMessage} action={emptyAction} />
      </div>
    );
  }
  return (
    <div style={{ height }} role="img" aria-label={ariaLabel}>
      <ReactECharts
        option={option}
        style={{ height: "100%" }}
        opts={{ renderer: "svg" }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}

/** Les valeurs absentes doivent créer un TROU dans la courbe, pas un zéro.
 *  ECharts interrompt la ligne sur `null`, ce qui est exactement le comportement
 *  voulu : une donnée manquante ne doit pas ressembler à une chute à zéro. */
export function toEchartsValues(values: Array<number | null | undefined>): Array<number | null> {
  return values.map((v) => (v === null || v === undefined ? null : v));
}
