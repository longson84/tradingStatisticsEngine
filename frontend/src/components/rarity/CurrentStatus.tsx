import type { RarityAnalysisResponse, FactorType } from "@/lib/api"
import { fmtPrice, fmtPct, fmtFactor, fmtDate, fmtOrdinal } from "@/lib/format"

// Per-factor context key definitions: order + label + format
type Fmt = "price" | "pct" | "number" | "date" | "pct_signed"
const FACTOR_CONTEXT: Record<FactorType, Array<{ key: string; label: string; fmt: Fmt }>> = {
  distance_from_peak: [
    { key: "peak_date",           label: "Reference date",              fmt: "date" },
    { key: "peak_price",          label: "Reference value",             fmt: "price" },
    { key: "sessions_from_peak",  label: "Sessions from reference date",fmt: "number" },
    { key: "remaining_sessions",  label: "Remaining valid sessions",    fmt: "number" },
  ],
  moving_average: [
    { key: "ma_value",      label: "MA value",        fmt: "price" },
    { key: "distance_pct",  label: "Distance from MA", fmt: "pct_signed" },
  ],
  bollinger: [
    { key: "upper_band",     label: "Upper band",  fmt: "price" },
    { key: "middle_band",    label: "Middle band", fmt: "price" },
    { key: "lower_band",     label: "Lower band",  fmt: "price" },
    { key: "bandwidth_pct",  label: "Bandwidth",   fmt: "pct" },
  ],
  donchian: [
    { key: "upper_channel",  label: "Upper channel",  fmt: "price" },
    { key: "lower_channel",  label: "Lower channel",  fmt: "price" },
    { key: "channel_width",  label: "Channel width",  fmt: "price" },
  ],
}

function fmtCtxValue(value: unknown, fmt: Fmt): string {
  const n = Number(value)
  switch (fmt) {
    case "price":      return fmtPrice(n)
    case "pct":        return fmtPct(n)
    case "pct_signed": return (n >= 0 ? "+" : "") + fmtPct(n)
    case "number":     return String(Math.round(n))
    case "date":       return fmtDate(String(value))
    default:           return String(value)
  }
}

interface Props {
  data: RarityAnalysisResponse
  factorType: FactorType
}

export function CurrentStatus({ data, factorType }: Props) {
  const ctxConfig = FACTOR_CONTEXT[factorType] ?? []

  // Potential drop calculation
  const potentialLow =
    data.zone_entry_price != null
      ? data.zone_entry_price * (1 - data.max_potential_drop_pct / 100)
      : null
  const dropFromCurrent =
    potentialLow != null && data.current_price > 0
      ? ((data.current_price - potentialLow) / data.current_price) * 100
      : null

  const items: Array<{ label: string; value: string }> = [
    { label: "Current price",   value: fmtPrice(data.current_price) },
    { label: "Current factor value", value: fmtFactor(data.current_value) },
    { label: "Current rarity",  value: fmtOrdinal(data.current_percentile) },
    ...ctxConfig
      .filter(c => data.factor_context[c.key] != null)
      .map(c => ({
        label: c.label,
        value: fmtCtxValue(data.factor_context[c.key], c.fmt),
      })),
  ]

  if (data.current_zone != null && data.zone_entry_date) {
    items.push({
      label: `Entered P${data.current_zone} zone on`,
      value: `${fmtDate(data.zone_entry_date)} at ${fmtPrice(data.zone_entry_price ?? 0)}`,
    })
    items.push({
      label: "Sessions in current zone",
      value: String(data.sessions_in_zone),
    })
  }

  if (potentialLow != null && dropFromCurrent != null) {
    items.push({
      label: "Max potential drop",
      value: `${fmtPrice(potentialLow)}  (~${fmtPct(dropFromCurrent)} from current, Max DD: ${fmtPct(data.max_potential_drop_pct)})`,
    })
  }

  return (
    <ol className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm">
          <span className="text-muted-foreground/50 shrink-0 w-5 text-right">{i + 1}.</span>
          <span className="text-muted-foreground">{item.label}:</span>
          <span className="text-foreground font-medium">{item.value}</span>
        </li>
      ))}
    </ol>
  )
}
