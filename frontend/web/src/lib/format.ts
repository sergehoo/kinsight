/** Formatage des montants XOF (entiers, 0 décimale — cohérent avec le backend). */
const xof = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "XOF",
  maximumFractionDigits: 0,
});

export function formatXof(value: number): string {
  return xof.format(value);
}

/** Formatage compact (1,2 M, 3,1 k) pour les axes et badges. */
const compact = new Intl.NumberFormat("fr-FR", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function formatCompact(value: number): string {
  return compact.format(value);
}

export function formatInt(value: number): string {
  return new Intl.NumberFormat("fr-FR").format(value);
}

/** Signe explicite pour les variations (+3 / −2). */
export function formatSigned(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${formatInt(Math.abs(value))}`;
}
