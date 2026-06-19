import type { RarityAnalysisResponse, FactorType, ZoneStat } from "@/lib/api"
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
  distance_from_ma: [
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
  ahr999: [],
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

function numberCtx(ctx: Record<string, unknown>, key: string): number | null {
  const value = Number(ctx[key])
  return Number.isFinite(value) ? value : null
}

function triggerPriceForZone(
  zone: ZoneStat,
  data: RarityAnalysisResponse,
  factorType: FactorType,
): number | null {
  const threshold = zone.threshold_value
  if (factorType === "distance_from_peak") {
    const peakPrice = numberCtx(data.factor_context, "peak_price")
    return peakPrice != null ? peakPrice * (1 + threshold) : null
  }
  if (factorType === "moving_average" || factorType === "distance_from_ma") {
    const maValue = numberCtx(data.factor_context, "ma_value")
    return maValue != null ? maValue * (1 + threshold) : null
  }
  if (factorType === "bollinger") {
    const upper = numberCtx(data.factor_context, "upper_band")
    const lower = numberCtx(data.factor_context, "lower_band")
    return upper != null && lower != null
      ? lower + threshold * (upper - lower)
      : null
  }
  if (factorType === "donchian") {
    const lower = numberCtx(data.factor_context, "lower_channel")
    const width = numberCtx(data.factor_context, "channel_width")
    return lower != null && width != null
      ? lower + threshold * width
      : null
  }
  return null
}

interface Props {
  data: RarityAnalysisResponse
  factorType: FactorType
}

export function CurrentStatus({ data, factorType }: Props) {
  const ctxConfig = FACTOR_CONTEXT[factorType] ?? []

  const inZone = data.current_zone != null && data.zone_entry_date
  const currentFactorZone = [...data.zone_stats]
    .sort((a, b) => a.zone_pct - b.zone_pct)
    .find(zone => data.current_value <= zone.threshold_value)?.zone_pct ?? null
  const activeEntry = inZone
    ? data.entries.find(e =>
        e.is_active &&
        e.zone_pct === data.current_zone &&
        e.start_date === data.zone_entry_date
      )
    : null
  const worstCases = inZone
    ? [
        ...data.entries.filter(e =>
          e.zone_pct === data.current_zone &&
          !e.is_active &&
          !e.is_quick_recovery
        ),
        ...(activeEntry && !activeEntry.is_quick_recovery ? [activeEntry] : []),
      ]
        .sort((a, b) => b.mae_pct - a.mae_pct)
        .slice(0, 10)
        .map(e => {
          const isActive = activeEntry != null && e.is_active && e.start_date === activeEntry.start_date
          const projectedPrice = data.zone_entry_price != null && e.mae_pct > (activeEntry?.mae_pct ?? 0)
            ? data.zone_entry_price * (1 - e.mae_pct / 100)
            : null
          const additionalDown = projectedPrice != null && projectedPrice < data.current_price
            ? ((data.current_price - projectedPrice) / data.current_price) * 100
            : null
          return { entry: e, isActive, projectedPrice, additionalDown }
        })
    : []
  const inactiveTriggerPrices = !inZone
    ? data.zone_stats
        .map(zone => {
          const triggerPrice = triggerPriceForZone(zone, data, factorType)
          const downFromCurrent = triggerPrice != null && triggerPrice < data.current_price
            ? ((data.current_price - triggerPrice) / data.current_price) * 100
            : null
          return { zone, triggerPrice, downFromCurrent }
        })
        .filter(row => row.triggerPrice != null)
    : []

  const contextItems = ctxConfig
    .filter(c => data.factor_context[c.key] != null)
    .map(c => ({
      label: c.label,
      value: fmtCtxValue(data.factor_context[c.key], c.fmt),
    }))

  return (
    <div className="space-y-4">
      {/* Primary metric tiles */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
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
          currentFactorZone != null
            ? "border-sky-400 bg-sky-50 dark:border-sky-600/50 dark:bg-sky-900/20"
            : "border-border bg-muted/30"
        ].join(" ")}>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Factor Percentile</div>
          <div className={[
            "text-xl font-bold tabular-nums",
            currentFactorZone != null ? "text-sky-700 dark:text-sky-400" : "text-foreground"
          ].join(" ")}>{fmtOrdinal(data.current_percentile)}</div>
        </div>
        <div className={[
          "rounded-lg border px-4 py-3",
          currentFactorZone != null
            ? "border-sky-400 bg-sky-50 dark:border-sky-600/50 dark:bg-sky-900/20"
            : "border-border bg-muted/30"
        ].join(" ")}>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Current Factor Zone</div>
          <div className={[
            "text-xl font-bold tabular-nums",
            currentFactorZone != null ? "text-sky-700 dark:text-sky-400" : "text-foreground"
          ].join(" ")}>
            {currentFactorZone != null ? `P${currentFactorZone}` : "None"}
          </div>
        </div>
      </div>

      {/* Active zone panel */}
      {inZone && (
        <div className="rounded-lg border border-amber-400 bg-amber-50 dark:border-amber-600/40 dark:bg-amber-900/15 px-4 py-3 grid grid-cols-2 gap-x-8 gap-y-1.5 text-sm">
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">Active recovery zone</span>
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

      {!inZone && inactiveTriggerPrices.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="px-3 py-2 border-b border-border bg-muted/40">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Zone trigger prices
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[560px]">
              <thead className="bg-muted/40 text-[10px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Zone</th>
                  <th className="text-right px-3 py-2 font-medium">Factor</th>
                  <th className="text-right px-3 py-2 font-medium">Price To Reach</th>
                  <th className="text-right px-3 py-2 font-medium">Down From Current</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {inactiveTriggerPrices.map(row => (
                  <tr key={row.zone.zone_pct} className="hover:bg-muted/30">
                    <td className="px-3 py-2 font-semibold text-foreground">P{row.zone.zone_pct}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtFactor(row.zone.threshold_value)}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-semibold">
                      {fmtPrice(row.triggerPrice!)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-red-700 dark:text-red-300">
                      {row.downFromCurrent != null ? fmtPct(row.downFromCurrent) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Historical worst cases for the active zone */}
      {inZone && worstCases.length > 0 && (
        <div className="rounded-lg border border-red-500/30 overflow-hidden">
          <div className="px-3 py-2 border-b border-red-500/20 bg-red-500/8">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Top 10 Worst P{data.current_zone} Cases
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[920px]">
              <thead className="bg-red-500/8 text-[10px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Case</th>
                  <th className="text-right px-3 py-2 font-medium">Started</th>
                  <th className="text-right px-3 py-2 font-medium">Recovered</th>
                  <th className="text-right px-3 py-2 font-medium">Sessions</th>
                  <th className="text-right px-3 py-2 font-medium">Max Down</th>
                  <th className="text-right px-3 py-2 font-medium">From</th>
                  <th className="text-right px-3 py-2 font-medium">To</th>
                  <th className="text-right px-3 py-2 font-medium">This-Time Price</th>
                  <th className="text-right px-3 py-2 font-medium">Additional Down</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {worstCases.map((row, i) => (
                  <tr
                    key={`${row.entry.zone_pct}-${row.entry.start_date}-${row.entry.mae_pct}`}
                    className={row.isActive ? "bg-blue-500/12 hover:bg-blue-500/18" : "hover:bg-red-500/5"}
                  >
                    <td className="px-3 py-2 font-medium">
                      #{i + 1}
                      {row.isActive && (
                        <span className="ml-2 rounded bg-blue-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-blue-700 dark:text-blue-300">
                          active
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.entry.start_date)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {row.entry.is_active ? "active" : fmtDate(row.entry.recovery_date)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {row.entry.is_active
                        ? `${row.entry.bars_elapsed ?? data.sessions_in_zone} (active)`
                        : row.entry.days_to_recovery ?? "n/a"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-red-700 dark:text-red-300">
                      {fmtPct(row.entry.mae_pct)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(row.entry.entry_price)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(row.entry.low_price)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-red-700 dark:text-red-300">
                      {row.projectedPrice != null ? fmtPrice(row.projectedPrice) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-red-700 dark:text-red-300">
                      {row.additionalDown != null ? fmtPct(row.additionalDown) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
