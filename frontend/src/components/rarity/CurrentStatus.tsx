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

  const potentialLow =
    data.zone_entry_price != null
      ? data.zone_entry_price * (1 - data.max_potential_drop_pct / 100)
      : null
  const dropFromCurrent =
    potentialLow != null && data.current_price > 0
      ? ((data.current_price - potentialLow) / data.current_price) * 100
      : null

  const inZone = data.current_zone != null && data.zone_entry_date

  const contextItems = ctxConfig
    .filter(c => data.factor_context[c.key] != null)
    .map(c => ({
      label: c.label,
      value: fmtCtxValue(data.factor_context[c.key], c.fmt),
    }))

  return (
    <div className="space-y-4">
      {/* Primary metric tiles */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-border bg-muted/30 px-4 py-3">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Current Price</div>
          <div className="text-xl font-bold tabular-nums text-foreground">{fmtPrice(data.current_price)}</div>
        </div>
        <div className="rounded-lg border border-border bg-muted/30 px-4 py-3">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Factor Value</div>
          <div className="text-xl font-bold tabular-nums text-foreground">{fmtFactor(data.current_value)}</div>
        </div>
        <div className={[
          "rounded-lg border px-4 py-3",
          inZone
            ? "border-amber-400 bg-amber-50 dark:border-amber-600/50 dark:bg-amber-900/20"
            : "border-border bg-muted/30"
        ].join(" ")}>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Rarity</div>
          <div className={[
            "text-xl font-bold tabular-nums",
            inZone ? "text-amber-700 dark:text-amber-400" : "text-foreground"
          ].join(" ")}>{fmtOrdinal(data.current_percentile)}</div>
        </div>
      </div>

      {/* Active zone panel */}
      {inZone && (
        <div className="rounded-lg border border-amber-400 bg-amber-50 dark:border-amber-600/40 dark:bg-amber-900/15 px-4 py-3 grid grid-cols-2 gap-x-8 gap-y-1.5 text-sm">
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">Zone entered</span>
            <span className="font-semibold text-amber-700 dark:text-amber-400 tabular-nums">
              P{data.current_zone} on {fmtDate(data.zone_entry_date!)} at {fmtPrice(data.zone_entry_price ?? 0)}
            </span>
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">Sessions in zone</span>
            <span className="font-semibold text-foreground tabular-nums">{data.sessions_in_zone}</span>
          </div>
        </div>
      )}

      {/* Factor context grid */}
      {contextItems.length > 0 && (
        <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm px-1">
          {contextItems.map((item, i) => (
            <div key={i} className="flex justify-between gap-2 border-b border-border/40 pb-1.5">
              <span className="text-muted-foreground">{item.label}</span>
              <span className="font-medium text-foreground tabular-nums">{item.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Potential drop warning */}
      {potentialLow != null && dropFromCurrent != null && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Max potential drop</span>
          <span className="font-semibold text-red-400 tabular-nums">
            {fmtPrice(potentialLow)} · ~{fmtPct(dropFromCurrent)} from current · Max DD {fmtPct(data.max_potential_drop_pct)}
          </span>
        </div>
      )}
    </div>
  )
}
