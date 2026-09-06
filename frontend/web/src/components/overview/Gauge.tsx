import * as React from "react";

import { useAnimatedValue } from "@/lib/motion";

interface GaugeProps {
  /** 0..100, ou null = donnée indisponible (N/D, gouverné — ADR-0007). */
  value: number | null;
  color: string;
  track?: string;
  /** Libellé lu par les lecteurs d'écran ; le SVG reste décoratif sans lui. */
  label?: string;
}

/* ── Zones de lecture ──────────────────────────────────────────────────────── */
export interface ScoreZone {
  key: "faible" | "moyen" | "bon" | "excellent";
  label: string;
  from: number;
  to: number;
}

export const SCORE_ZONES: ScoreZone[] = [
  { key: "faible", label: "Faible", from: 0, to: 40 },
  { key: "moyen", label: "Moyen", from: 40, to: 60 },
  { key: "bon", label: "Bon", from: 60, to: 80 },
  { key: "excellent", label: "Excellent", from: 80, to: 100 },
];

/** Zone d'appartenance d'un score. `null` reste `null` : aucune zone n'est
 *  attribuée à une donnée absente, sans quoi « Faible » se lirait comme un
 *  jugement porté sur une mesure qui n'existe pas. */
export function scoreZone(value: number | null | undefined): ScoreZone | null {
  if (value === null || value === undefined) return null;
  const clamped = Math.max(0, Math.min(100, value));
  return SCORE_ZONES.find((zone) => clamped >= zone.from && clamped <= zone.to) ?? null;
}

/* ── Géométrie du demi-cadran ──────────────────────────────────────────────── */
const CX = 100;
const CY = 104;
const R_BAND = 78; // rayon des bandes de zone
const VIEWBOX = "0 0 200 120";

/** 0 → 180° (extrême gauche), 50 → 90° (vertical), 100 → 0° (extrême droite). */
function angleOf(value: number): number {
  return 180 - value * 1.8;
}

function pointAt(value: number, radius: number): [number, number] {
  const rad = (angleOf(value) * Math.PI) / 180;
  return [CX + radius * Math.cos(rad), CY - radius * Math.sin(rad)];
}

/** Arc de `from` à `to` sur le demi-cadran (sens horaire à l'écran). */
function arcPath(from: number, to: number, radius: number): string {
  const [x1, y1] = pointAt(from, radius);
  const [x2, y2] = pointAt(to, radius);
  return `M ${x1} ${y1} A ${radius} ${radius} 0 0 1 ${x2} ${y2}`;
}

/**
 * Compteur de gouvernance — demi-cadran 0 → 100 façon tableau de bord.
 *
 * L'aiguille est interpolée par `useAnimatedValue` : elle BALAIE de l'ancienne à
 * la nouvelle valeur au lieu de sauter, et `prefers-reduced-motion` la fait
 * atteindre sa position sans transition.
 *
 * `value === null` → aucune aiguille, aucun chiffre, zones en gris neutre : une
 * donnée non branchée ne doit jamais ressembler à un score de 0 (ADR-0007).
 */
export function Gauge({ value, color, track = "#ECEEF0", label }: GaugeProps) {
  const isNA = value == null;
  const target = isNA ? 0 : Math.max(0, Math.min(100, value));
  // 0,7 s : dans la fourchette 500–900 ms, courbe ease-out partagée par le cockpit.
  const animated = useAnimatedValue(target, 0.7);
  const shown = isNA ? 0 : animated;

  const uid = React.useId().replace(/:/g, "");
  const needleId = `${uid}-needle`;
  const activeZone = scoreZone(isNA ? null : target);

  // Graduations : majeures chiffrées, mineures tous les 10 pour la lisibilité.
  const majors = [0, 25, 50, 75, 100];
  const minors = [10, 20, 30, 40, 60, 70, 80, 90];

  const needleAngle = shown * 1.8 - 90; // -90° à gauche, 0° en haut, +90° à droite

  return (
    <svg
      viewBox={VIEWBOX}
      className="h-full w-full"
      role={label ? "img" : undefined}
      aria-label={label ? `${label} : ${isNA ? "non disponible" : `${Math.round(target)} sur 100`}` : undefined}
      aria-hidden={label ? undefined : true}
    >
      <defs>
        <linearGradient id={needleId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#2A2F31" />
          <stop offset="100%" stopColor="#0E1112" />
        </linearGradient>
      </defs>

      {/* Piste de fond */}
      <path d={arcPath(0, 100, R_BAND)} fill="none" stroke={track} strokeWidth={13} strokeLinecap="round" />

      {/* Zones : grises par défaut, seule celle qui contient la valeur prend
          l'accent du domaine. Un dégradé arc-en-ciel ferait « chart générique ». */}
      {SCORE_ZONES.map((zone, index) => {
        const isActive = activeZone?.key === zone.key;
        // 0,8 point de retrait entre bandes : la séparation se voit sans trou.
        const from = index === 0 ? 0 : zone.from + 0.8;
        const to = index === SCORE_ZONES.length - 1 ? 100 : zone.to - 0.8;
        return (
          <path
            key={zone.key}
            d={arcPath(from, to, R_BAND)}
            fill="none"
            stroke={isActive ? color : "#CBD1CE"}
            strokeWidth={isActive ? 13 : 9}
            strokeLinecap="butt"
            opacity={isActive ? 0.95 : 0.34 + index * 0.07}
            style={{ transition: "stroke 420ms ease-out, opacity 420ms ease-out, stroke-width 420ms ease-out" }}
          />
        );
      })}

      {/* Graduations */}
      {minors.map((tick) => {
        const [x1, y1] = pointAt(tick, 64);
        const [x2, y2] = pointAt(tick, 69);
        return <line key={`m${tick}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#B9C0BD" strokeWidth={1} opacity={0.5} />;
      })}
      {majors.map((tick) => {
        const [x1, y1] = pointAt(tick, 61);
        const [x2, y2] = pointAt(tick, 69);
        const [tx, ty] = pointAt(tick, 52);
        return (
          <g key={`M${tick}`}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#9AA19E" strokeWidth={1.6} strokeLinecap="round" />
            <text
              x={tx}
              y={ty}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="8.5"
              fontWeight="700"
              fill="#A8AEAB"
            >
              {tick}
            </text>
          </g>
        );
      })}

      {/* Aiguille — masquée tant qu'aucune valeur réelle n'est servie. */}
      {!isNA ? (
        <g transform={`rotate(${needleAngle} ${CX} ${CY})`}>
          <path
            d={`M ${CX - 4.2} ${CY} Q ${CX} ${CY + 3} ${CX + 4.2} ${CY} L ${CX + 1.15} ${CY - 60} Q ${CX} ${CY - 66} ${CX - 1.15} ${CY - 60} Z`}
            fill={`url(#${needleId})`}
          />
        </g>
      ) : null}

      {/* Pivot central : plein quand l'aiguille est là, évidé sinon. */}
      <circle cx={CX} cy={CY} r="7.5" fill="#fff" stroke={isNA ? "#D6DBD8" : color} strokeWidth="2.6" />
      {!isNA ? <circle cx={CX} cy={CY} r="2.8" fill="#16191A" /> : null}
    </svg>
  );
}
