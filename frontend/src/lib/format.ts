/**
 * Unified number / date formatting for the entire app.
 *
 * Rules (as defined by the user):
 *  - Prices:      no decimal, thousand separator          → "70,629"
 *  - Percentages: 2 decimal places + "%"                 → "42.66%"
 *  - Factor vals: shown as % (×100, 2dp, signed)         → "-42.66%"
 *  - Dates:       dd/MM/yy                               → "23/03/26"
 *  - Timestamps:  dd/MM/yy HH:mm in the user's timezone  → "23/03/26 14:05"
 *  - Plain ints:  thousand separator, no decimal         → "4,206"
 */

export function fmtPrice(n: number): string {
  return Math.round(n).toLocaleString("en-US")
}

export function fmtPct(n: number, decimals = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }) + "%"
}

/** Generic decimal number with thousand separator — for Sharpe, profit factor, etc. */
export function fmtNum(n: number, decimals = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/** Factor value multiplied ×100 and shown with sign */
export function fmtFactor(n: number): string {
  return fmtPct(n * 100)
}

/** ISO date string "2026-03-23" → "23/03/26" */
export function fmtDate(d: string | null | undefined): string {
  if (!d) return "—"
  const [year, month, day] = d.split("-")
  return `${day}/${month}/${year.slice(2)}`
}

/** ISO timestamp → local wall time "dd/MM/yy HH:mm" */
export function fmtDateTime(d: string | null | undefined): string {
  if (!d) return "—"
  const value = new Date(d)
  if (Number.isNaN(value.getTime())) return d
  const day = String(value.getDate()).padStart(2, "0")
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const year = String(value.getFullYear()).slice(-2)
  const hour = String(value.getHours()).padStart(2, "0")
  const minute = String(value.getMinutes()).padStart(2, "0")
  return `${day}/${month}/${year} ${hour}:${minute}`
}

export function fmtInt(n: number): string {
  return Math.round(n).toLocaleString("en-US")
}

/** Compact signed market value, preserving direction for flow data. */
export function fmtCompactVnd(n: number): string {
  const absolute = Math.abs(n)
  const units = [
    { threshold: 1e12, suffix: "tn", divisor: 1e12 },
    { threshold: 1e9, suffix: "bn", divisor: 1e9 },
    { threshold: 1e6, suffix: "mn", divisor: 1e6 },
  ]
  const unit = units.find(item => absolute >= item.threshold)
  const formatted = unit
    ? `${(absolute / unit.divisor).toLocaleString("en-US", { maximumFractionDigits: 2 })}${unit.suffix}`
    : Math.round(absolute).toLocaleString("en-US")
  return `${n < 0 ? "−" : n > 0 ? "+" : ""}${formatted} VND`
}

export function fmtOrdinal(n: number): string {
  return n.toFixed(2) + "th"
}

/** Human-readable acquisition provenance stored alongside observations. */
export function fmtProviderSource(source: string | null | undefined): string {
  if (!source) return "Local cache"
  if (source === "yfinance") return "Yahoo Finance"
  if (source === "vci" || source === "vnstock-vci") return "VCI"
  if (source === "kbs" || source === "vnstock-kbs") return "KBS"
  if (source === "mixed" || source.startsWith("database:")) {
    return "Mixed provider history"
  }

  const historicalSponsored = source.match(/^vnstock-data-(.+)-(vci|kbs)$/i)
  if (historicalSponsored) {
    const [, version, upstream] = historicalSponsored
    return `${upstream.toUpperCase()} · vnstock data ${version}`
  }

  const sponsored = source.match(/^vnstock-(.+)-(vci|kbs)$/i)
  if (sponsored) {
    const [, version, upstream] = sponsored
    return `${upstream.toUpperCase()} · vnstock ${version}`
  }

  return source
}
