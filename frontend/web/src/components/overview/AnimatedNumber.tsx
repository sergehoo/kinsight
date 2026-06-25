import * as React from "react";

import { useAnimatedValue } from "@/lib/motion";

interface AnimatedNumberProps {
  /** Valeur formatée à animer, ex. "96.5%", "+2.4%", "3.1M XOF", "N/D". */
  value: string;
  duration?: number;
  className?: string;
}

interface Parsed {
  prefix: string;
  suffix: string;
  target: number;
  decimals: number;
  decimalSep: string;
  groupSep: string | null;
}

// Espaces de regroupement de milliers : espace simple, insécable, insécable étroit.
const GROUP_SPACES = "\\u0020\\u00a0\\u202f";
// Premier nombre rencontré : signe éventuel, chiffres, séparateurs de milliers et décimale.
const NUMBER_RE = new RegExp(`-?\\d[\\d${GROUP_SPACES}.,]*\\d|-?\\d`);
const SPACE_RE = new RegExp(`[${GROUP_SPACES}]`, "g");
const ONE_SPACE_RE = new RegExp(`[${GROUP_SPACES}]`);

function parseValue(value: string): Parsed | null {
  const match = value.match(NUMBER_RE);
  if (!match) return null;

  const raw = match[0];
  const start = match.index ?? 0;
  const prefix = value.slice(0, start);
  const suffix = value.slice(start + raw.length);

  // Partie décimale = dernier séparateur suivi uniquement de chiffres en fin de nombre.
  const decimalMatch = raw.match(/([.,])(\d+)$/);
  const decimalSep = decimalMatch ? decimalMatch[1] : ".";
  const decimals = decimalMatch ? decimalMatch[2].length : 0;

  let cleaned = raw.replace(SPACE_RE, "");
  if (decimalMatch) {
    cleaned = decimalSep === "," ? cleaned.replace(/\./g, "").replace(",", ".") : cleaned.replace(/,/g, "");
  } else {
    cleaned = cleaned.replace(/[.,]/g, "");
  }

  const target = Number.parseFloat(cleaned);
  if (!Number.isFinite(target)) return null;

  const groupMatch = raw.match(ONE_SPACE_RE);
  return { prefix, suffix, target, decimals, decimalSep, groupSep: groupMatch ? groupMatch[0] : null };
}

function render(n: number, parsed: Parsed): string {
  const fixed = Math.abs(n).toFixed(parsed.decimals);
  const [intPartRaw, fracPart] = fixed.split(".");
  const intPart = parsed.groupSep
    ? intPartRaw.replace(/\B(?=(\d{3})+(?!\d))/g, parsed.groupSep)
    : intPartRaw;
  const body = fracPart ? `${intPart}${parsed.decimalSep}${fracPart}` : intPart;
  const sign = n < 0 ? "-" : "";
  return `${parsed.prefix}${sign}${body}${parsed.suffix}`;
}

/** Compteur animé : anime la partie numérique d'une valeur formatée en conservant son habillage. */
export function AnimatedNumber({ value, duration, className }: AnimatedNumberProps) {
  const parsed = React.useMemo(() => parseValue(value), [value]);
  const animated = useAnimatedValue(parsed?.target ?? 0, duration);

  if (!parsed) {
    return <span className={className}>{value}</span>;
  }
  return (
    <span className={className} aria-label={value}>
      {render(animated, parsed)}
    </span>
  );
}
