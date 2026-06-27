import * as React from "react";

import { useAnimatedValue } from "@/lib/motion";

interface GaugeProps {
  value: number | null; // 0..100, ou null = donnée indisponible (N/D, gouverné — ADR-0007)
  color: string;
  track?: string;
}

/** Mini jauge demi-cercle (arc), façon référence. L'aiguille et l'arc balaient de 0 vers la valeur.
 *  `value === null` → état « indisponible » : piste vide, ni arc coloré ni aiguille ni chiffre
 *  (on n'affiche jamais un faux « 0 % » quand la donnée n'est pas branchée). */
export function Gauge({ value, color, track = "#ECEEF0" }: GaugeProps) {
  const isNA = value == null;
  const target = isNA ? 0 : Math.max(0, Math.min(100, value));
  const pct = useAnimatedValue(target, 1.3);
  const gradientId = React.useId().replace(/:/g, "");
  const glowId = `${gradientId}-glow`;
  const centerX = 104;
  const centerY = 102;
  const radius = 82;
  const arcPath = `M ${centerX - radius} ${centerY} A ${radius} ${radius} 0 0 1 ${centerX + radius} ${centerY}`;
  const needleRotation = (pct - 50) * 1.8;
  // Position du chiffre : sur l'axe de l'aiguille, juste au-delà de sa pointe.
  const labelAngle = (180 - pct * 1.8) * (Math.PI / 180);
  const labelX = Math.max(40, Math.min(150, centerX + 66 * Math.cos(labelAngle)));
  const labelY = Math.max(28, Math.min(92, centerY - 66 * Math.sin(labelAngle)));
  const wedgeLeftAngle = (180 - Math.max(0, pct - 14) * 1.8) * (Math.PI / 180);
  const wedgeRightAngle = (180 - Math.min(100, pct + 12) * 1.8) * (Math.PI / 180);
  const wedge = {
    leftX: centerX + 74 * Math.cos(wedgeLeftAngle),
    leftY: centerY - 74 * Math.sin(wedgeLeftAngle),
    rightX: centerX + 74 * Math.cos(wedgeRightAngle),
    rightY: centerY - 74 * Math.sin(wedgeRightAngle),
  };
  const ticks = [0, 25, 50, 75, 100].map((tick) => {
    const angle = (180 - tick * 1.8) * (Math.PI / 180);
    return {
      tick,
      x1: centerX + 68 * Math.cos(angle),
      y1: centerY - 68 * Math.sin(angle),
      x2: centerX + 78 * Math.cos(angle),
      y2: centerY - 78 * Math.sin(angle),
    };
  });

  return (
    <svg viewBox="0 0 190 118" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id={gradientId} x1="20" x2="188" y1="102" y2="102" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={color} stopOpacity="0.78" />
          <stop offset="64%" stopColor={color} />
          <stop offset="100%" stopColor={color} stopOpacity="0.88" />
        </linearGradient>
        <filter id={glowId} x="-35%" y="-45%" width="170%" height="190%">
          <feGaussianBlur stdDeviation="2.4" result="blur" />
          <feColorMatrix
            in="blur"
            type="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 .35 0"
            result="glow"
          />
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <path
        d={`M ${centerX} ${centerY} L ${wedge.leftX} ${wedge.leftY} Q ${centerX + 34} ${centerY - 76} ${wedge.rightX} ${wedge.rightY} Z`}
        fill={color}
        opacity="0.18"
      />
      <path
        d={`M ${centerX - 78} ${centerY} A 78 78 0 0 1 ${centerX + 78} ${centerY} L ${centerX + 54} ${centerY} A 54 54 0 0 0 ${centerX - 54} ${centerY} Z`}
        fill={color}
        opacity="0.055"
      />
      {ticks.map(({ tick, x1, y1, x2, y2 }) => (
        <line
          key={tick}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke="#C9CFCC"
          strokeLinecap="round"
          strokeWidth={tick === 50 ? 1.4 : 1}
          opacity={tick === 50 ? 0.76 : 0.48}
        />
      ))}
      <path
        d={arcPath}
        fill="none"
        stroke={track}
        strokeWidth={18}
        strokeLinecap="round"
      />
      {!isNA && (
        <>
          <path
            d={arcPath}
            fill="none"
            stroke={color}
            strokeWidth={20}
            strokeLinecap="round"
            pathLength={100}
            strokeDasharray={`${pct} 100`}
            opacity="0.16"
          />
          <path
            d={arcPath}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={18}
            strokeLinecap="round"
            pathLength={100}
            strokeDasharray={`${pct} 100`}
            filter={`url(#${glowId})`}
          />
          <g transform={`rotate(${needleRotation} ${centerX} ${centerY})`}>
            <line x1={centerX} y1={centerY} x2={centerX} y2="48" stroke="#202526" strokeLinecap="round" strokeWidth="3" opacity="0.30" />
            <circle cx={centerX} cy={centerY} r="8" fill="#fff" stroke="#D6DBD8" strokeWidth="2.4" />
          </g>
          {/* Lecture chiffrée alignée sur l'aiguille, sans pastille ni contour. */}
          <text
            x={labelX}
            y={labelY}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="13"
            fontWeight="800"
            fill="#1F2426"
            style={{ letterSpacing: "-0.3px" }}
          >
            {Math.round(pct)}%
          </text>
        </>
      )}
    </svg>
  );
}
