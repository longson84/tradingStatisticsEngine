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

export function fmtInt(n: number): string {
  return Math.round(n).toLocaleString("en-US")
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

  const sponsored = source.match(/^vnstock-data-(.+)-(vci|kbs)$/i)
  if (sponsored) {
    const [, version, upstream] = sponsored
    return `${upstream.toUpperCase()} · vnstock_data ${version}`
  }

  return source
}
