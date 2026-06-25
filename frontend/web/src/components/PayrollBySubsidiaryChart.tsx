import ReactECharts from "echarts-for-react";

import { formatCompact, formatXof } from "@/lib/format";

interface Props {
  data: Record<string, number>;
}

const SUBSIDIARY_LABELS: Record<string, string> = {
  KRE: "K-Express",
  KSH: "K-Shield",
  MYK: "MyKaydan",
};

export function PayrollBySubsidiaryChart({ data }: Props) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const categories = entries.map(([code]) => SUBSIDIARY_LABELS[code] ?? code);
  const values = entries.map(([, v]) => v);

  const option = {
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (v: number) => formatXof(v),
    },
    xAxis: {
      type: "category",
      data: categories,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#e2e8f0" } },
      axisLabel: { color: "#475569" },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#eef2f7" } },
      axisLabel: { color: "#94a3b8", formatter: (v: number) => formatCompact(v) },
    },
    series: [
      {
        type: "bar",
        data: values,
        barWidth: "46%",
        itemStyle: {
          borderRadius: [8, 8, 0, 0],
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "#6366f1" },
              { offset: 1, color: "#4338ca" },
            ],
          },
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 320 }} notMerge lazyUpdate />;
}
