/**
 * Unified number / date formatting for the entire app.
 *
 * Rules (as defined by the user):
 *  - Prices:      no decimal, thousand separator          → "70,629"
 *  - Percentages: 2 decimal places + "%"                 → "42.66%"
 *  - Factor vals: shown as % (×100, 2dp, signed)         → "-42.66%"
 *  - Dates:       dd/MM/yy                               → "23/03/26"
 *  - Plain ints:  thousand separator, no decimal         → "4,206"
 */

export function fmtPrice(n: number): string {
  return Math.round(n).toLocaleString("en-US")
}

export function fmtPct(n: number): string {
  return n.toFixed(2) + "%"
}

/** Factor value multiplied ×100 and shown with sign */
export function fmtFactor(n: number): string {
  return (n * 100).toFixed(2) + "%"
}

/** Absolute factor value ×100 (for "distance" style display) */
export function fmtFactorAbs(n: number): string {
  return Math.abs(n * 100).toFixed(2) + "%"
}

/** ISO date string "2026-03-23" → "23/03/26" */
export function fmtDate(d: string | null | undefined): string {
  if (!d) return "—"
  const [year, month, day] = d.split("-")
  return `${day}/${month}/${year.slice(2)}`
}

export function fmtInt(n: number): string {
  return Math.round(n).toLocaleString("en-US")
}

export function fmtOrdinal(n: number): string {
  return n.toFixed(2) + "th"
}
