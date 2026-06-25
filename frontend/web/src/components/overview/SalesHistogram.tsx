import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";

import { formatCompact } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";

interface SalesHistogramProps {
  data?: Record<string, number>;
  emptyLabel?: string;
  loading?: boolean;
}

const BAR_COUNT = 46;
/** Fenêtre centrale « active » (mise en avant orange), façon coupe 2D de la référence. */
const ACTIVE_FROM = 0.3;
const ACTIVE_TO = 0.64;

const ACTIVE_BAR = "linear-gradient(180deg,#FF7A24 0%,#FF9B4A 52%,rgba(255,168,96,0.10) 100%)";
const ACTIVE_BAR_SOFT = "linear-gradient(180deg,#FF9B52 0%,#FFC08B 56%,rgba(255,200,150,0.10) 100%)";
const MUTED_BAR = "linear-gradient(180deg,rgba(201,210,203,0.92),rgba(236,240,236,0.28))";

const FALLBACK: Array<[string, number]> = [
  ["KRE", 54],
  ["KSH", 44],
  ["MYK", 31],
  ["Autres", 25],
];

const SHARE_COLORS = ["#FF7A24", "#FF9B52", "#FFD2AD"];

/** Générateur pseudo-aléatoire déterministe (LCG) : même donnée => même vague. */
function makeRng(seed: number) {
  let state = (seed % 2147483647) + 1;
  return () => {
    state = (state * 48271) % 2147483647;
    return (state - 1) / 2147483646;
  };
}

/** Construit une vague de `BAR_COUNT` barres, ensemencée par les données. */
function buildSpectrum(values: Array<[string, number]>): number[] {
  const seed =
    values.reduce((acc, [label, value], index) => acc + value * (index + 3) + label.charCodeAt(0), 17) || 17;
  const rng = makeRng(Math.round(seed));
  const bars: number[] = [];
  for (let i = 0; i < BAR_COUNT; i += 1) {
    const t = i / (BAR_COUNT - 1);
    const envelope =
      0.92 * Math.exp(-(((t - 0.4) / 0.2) ** 2)) +
      0.55 * Math.exp(-(((t - 0.74) / 0.13) ** 2)) +
      0.1;
    const jitter = 0.72 + rng() * 0.55;
    bars.push(Math.max(0.06, envelope * jitter));
  }
  const max = Math.max(...bars);
  return bars.map((value) => value / max);
}

function GridLines() {
  return (
    <div className="pointer-events-none absolute inset-x-6 bottom-12 top-6">
      {[0, 1, 2, 3].map((line) => (
        <span
          key={line}
          className="absolute left-0 h-px w-full bg-gradient-to-r from-transparent via-white/80 to-transparent"
          style={{ top: `${line * 30}%` }}
        />
      ))}
    </div>
  );
}

export function SalesHistogram({ data, emptyLabel = "Aucune donnee disponible", loading }: SalesHistogramProps) {
  const reduce = useReducedMotion();

  const rows = data
    ? Object.entries(data)
        .filter(([, value]) => Number.isFinite(value) && value > 0)
        .sort((a, b) => b[1] - a[1])
    : [];
  const isEmpty = !loading && rows.length === 0;
  const hasData = rows.length > 0 && !loading;
  const values = loading || rows.length === 0 ? FALLBACK : rows.slice(0, 8);
  const max = Math.max(...values.map(([, value]) => value), 1);
  const total = values.reduce((sum, [, value]) => sum + value, 0);

  const spectrum = React.useMemo(() => buildSpectrum(values), [values]);
  const activeStart = Math.round(BAR_COUNT * ACTIVE_FROM);
  const activeEnd = Math.round(BAR_COUNT * ACTIVE_TO);

  // Pic de la fenêtre active : sert au badge flottant + ancre les marqueurs.
  const peakIndex = spectrum.reduce(
    (best, value, index) =>
      index >= activeStart && index <= activeEnd && value > spectrum[best] ? index : best,
    activeStart,
  );
  const peakLeft = ((peakIndex + 0.5) / BAR_COUNT) * 100;
  const railStart = (activeStart / BAR_COUNT) * 100;
  const railEnd = ((activeEnd + 1) / BAR_COUNT) * 100;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        className="relative min-h-[150px] flex-1 overflow-hidden rounded-[26px] border border-white/65 px-5 pb-3 pt-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.78),0_16px_34px_rgba(51,56,55,0.06)]"
        style={{ background: "linear-gradient(180deg,rgba(255,255,255,0.52),rgba(255,255,255,0.18))" }}
      >
        <GridLines />
        <div className="pointer-events-none absolute inset-x-6 bottom-11 h-px bg-[#BEC7C1]/55" />

        {/* Halo de la zone active */}
        <div
          className="pointer-events-none absolute bottom-11 top-6 rounded-[20px]"
          style={{
            left: `calc(1.25rem + ${railStart}% )`,
            width: `${railEnd - railStart}%`,
            background: "radial-gradient(120% 100% at 50% 100%,rgba(255,126,45,0.16),transparent 70%)",
          }}
        />

        {isEmpty ? (
          <div className="absolute inset-0 grid place-items-center">
            <span className="max-w-[78%] truncate rounded-full border border-white/70 bg-white/82 px-4 py-2 text-center text-[12px] font-semibold text-[#6F7673] shadow-[0_10px_24px_rgba(42,46,45,0.08)]">
              {emptyLabel}
            </span>
          </div>
        ) : (
          <>
            {!loading ? (
              <motion.span
                className="absolute z-10 -translate-x-1/2 rounded-full bg-white/88 px-2.5 py-1 text-[10px] font-bold text-[#5D6562] shadow-[0_6px_16px_rgba(255,126,45,0.18)]"
                style={{ left: `${peakLeft}%`, top: "0.5rem" }}
                initial={reduce ? false : { opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5, duration: 0.5, ease: EASE_OUT }}
              >
                {formatCompact(max)}
              </motion.span>
            ) : null}

            <div className="absolute inset-x-5 bottom-3 top-7 flex items-end justify-center gap-[3px]">
              {spectrum.map((height, index) => {
                const active = index >= activeStart && index <= activeEnd;
                const background = active ? (height > 0.6 ? ACTIVE_BAR : ACTIVE_BAR_SOFT) : MUTED_BAR;
                const heightPct = Math.max(6, height * 100);
                return (
                  <motion.span
                    key={index}
                    className="relative w-full max-w-[16px] flex-1 origin-bottom rounded-t-[6px] transition-[height] duration-700 ease-out"
                    style={{
                      height: `${heightPct}%`,
                      background,
                      boxShadow: active
                        ? "0 12px 22px rgba(255,126,45,0.22),inset 0 1px 0 rgba(255,255,255,0.5)"
                        : "inset 0 1px 0 rgba(255,255,255,0.7)",
                    }}
                    initial={reduce ? false : { scaleY: 0, opacity: 0 }}
                    animate={{ scaleY: 1, opacity: 1 }}
                    transition={{ delay: index * 0.012, duration: 0.6, ease: EASE_OUT }}
                  />
                );
              })}
            </div>

            <div className="absolute inset-x-6 bottom-3 flex justify-between text-[10px] font-semibold text-[#9AA09D]">
              {ticks.map((fraction) => (
                <span key={fraction}>{loading ? "--" : formatCompact(max * fraction)}</span>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3 text-[12px] font-medium text-[#777C7D]">
        {values.slice(0, 3).map(([label, value], index) => {
          const pct = total ? Math.round((value / total) * 100) : 0;
          return (
            <div
              key={`share-${label}`}
              className="overflow-hidden rounded-full border border-white/65 bg-white/62 shadow-[inset_0_1px_0_rgba(255,255,255,0.72)]"
            >
              <div className="flex items-center justify-between px-3 py-2">
                <span className="truncate pr-2 font-semibold text-[#262929]">{label}</span>
                <span>{loading || !hasData ? "--" : `${pct}%`}</span>
              </div>
              <motion.span
                className="block h-0.5 rounded-full"
                style={{ background: SHARE_COLORS[Math.min(index, SHARE_COLORS.length - 1)] }}
                initial={reduce ? false : { width: 0 }}
                animate={{ width: loading || !hasData ? "24%" : `${Math.max(12, pct)}%` }}
                transition={{ delay: 0.25 + index * 0.08, duration: 0.7, ease: EASE_OUT }}
              />
            </div>
          );
        })}
      </div>

      <div className="relative mt-4 h-16">
        <div className="absolute inset-x-0 top-1/2 h-14 -translate-y-1/2 rounded-full bg-[#E0E2DF] shadow-[inset_0_3px_8px_rgba(30,32,32,0.07)]" />
        <motion.div
          className="absolute top-1/2 h-14 -translate-y-1/2 rounded-full"
          style={{
            background:
              "linear-gradient(90deg,rgba(255,126,45,0.18),#FF8735 18%,#FF8A3C 82%,rgba(255,126,45,0.16))",
            boxShadow: "0 0 34px 10px rgba(255,126,45,0.30)",
          }}
          initial={reduce ? false : { left: `${(railStart + railEnd) / 2}%`, width: 0, opacity: 0 }}
          animate={{ left: `${railStart}%`, width: `${railEnd - railStart}%`, opacity: 1 }}
          transition={{ delay: 0.35, duration: 0.8, ease: EASE_OUT }}
        />
        <motion.span
          className="absolute top-1/2 h-12 w-px -translate-y-1/2 bg-[#C51F4D]"
          style={{ left: `${railStart}%` }}
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7, duration: 0.4 }}
        />
        <motion.span
          className="absolute top-1/2 h-12 w-px -translate-y-1/2 bg-[#C51F4D]"
          style={{ left: `${Math.min(96, railEnd)}%` }}
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.78, duration: 0.4 }}
        />
        <div className="absolute inset-x-8 top-1/2 flex -translate-y-1/2 justify-between text-[11px] font-semibold text-[#8D918F]">
          <span>0</span>
          <span>{loading || !hasData ? "--" : formatCompact(max)}</span>
        </div>
      </div>
    </div>
  );
}
