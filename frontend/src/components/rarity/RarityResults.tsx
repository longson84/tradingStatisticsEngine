import type { RarityAnalysisResponse, FactorType, ZoneEntry } from "@/lib/api"
import { fmtDate, fmtInt, fmtPct } from "@/lib/format"
import { ZoneStatsTable } from "./ZoneStatsTable"
import { CurrentStatus } from "./CurrentStatus"
import { ZoneEntryTable } from "./ZoneEntryTable"
import { PriceFactorChart } from "./PriceFactorChart"

interface Props {
  data: RarityAnalysisResponse
  factorType: FactorType
}

export function RarityResults({ data, factorType }: Props) {
  const visibleEntryCount = data.entries.filter(e => !e.is_quick_recovery).length
  const currentFactorZone = [...data.zone_stats]
    .sort((a, b) => a.zone_pct - b.zone_pct)
    .find(zone => data.current_value <= zone.threshold_value)?.zone_pct ?? null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 pb-4 border-b border-border">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">{data.symbol}</h2>
          <span className="text-xs font-mono px-2 py-0.5 rounded border border-border bg-muted text-muted-foreground uppercase tracking-wider">
            {data.factor_name}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-4 text-xs text-muted-foreground/60">
          <span>{fmtDate(data.first_date)} – {fmtDate(data.last_date)}</span>
          <span className="tabular-nums">{fmtInt(data.total_bars)} sessions</span>
          <span>as of {fmtDate(data.stats_date)}</span>
        </div>
      </div>

      {/* Current Status */}
      <section>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Current Status</h3>
        <div className="border border-border rounded-lg bg-card px-5 py-4">
          <CurrentStatus data={data} factorType={factorType} />
        </div>
      </section>

      {/* Price and factor chart */}
      <div>
        <PriceFactorChart
          timeSeries={data.time_series}
          zoneStats={data.zone_stats}
          entries={data.entries}
        />
      </div>

      {/* Zone Statistics */}
      <section>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Zone Statistics</h3>
        <div className="border border-border rounded-lg overflow-hidden bg-card">
          <ZoneStatsTable
            stats={data.zone_stats}
            entries={data.entries}
            currentFactorZone={currentFactorZone}
          />
        </div>
      </section>

      {/* Zone Duration Statistics */}
      <section>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Zone Duration Statistics</h3>
        <div className="border border-border rounded-lg overflow-x-auto bg-card">
          <ZoneDurationTable
            entries={data.entries}
            stats={data.zone_stats}
            sessionsInZone={data.sessions_in_zone}
            currentFactorZone={currentFactorZone}
          />
        </div>
      </section>

      {/* Forward Returns by Zone */}
      <section>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Forward Returns by Zone</h3>
        <div className="space-y-4">
          {RETURN_HORIZONS.map(horizon => (
            <div key={horizon}>
              <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                After {horizon} Bars
              </h4>
              <div className="border border-border rounded-lg overflow-x-auto bg-card">
                <ZoneForwardReturnsTable
                  entries={data.entries}
                  zones={data.zone_stats.map(z => z.zone_pct)}
                  horizon={horizon}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Zone Entry History */}
      <section>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Zone Entry History
          <span className="ml-2 text-muted-foreground/50 font-normal normal-case">
            {visibleEntryCount} entries
          </span>
        </h3>
        <div className="border border-border rounded-lg overflow-hidden bg-card">
          <ZoneEntryTable entries={data.entries} />
        </div>
      </section>
    </div>
  )
}

const RETURN_HORIZONS = ["50", "100", "150", "200"]
const RETURN_PERCENTILES = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
const DURATION_PERCENTILES = [5, 10, 15, 20, 25, 50]

function percentile(values: number[], pct: number): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const rank = (pct / 100) * (sorted.length - 1)
  const lo = Math.floor(rank)
  const hi = Math.ceil(rank)
  if (lo === hi) return sorted[lo]
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (rank - lo)
}

function worstTailPercentile(values: number[], pct: number): number | null {
  return percentile(values, 100 - pct)
}

function ZoneForwardReturnsTable({
  entries,
  zones,
  horizon,
}: {
  entries: ZoneEntry[]
  zones: number[]
  horizon: string
}) {
  const rows = zones.map(zone => {
    const zoneEntries = entries.filter(e => e.zone_pct === zone)
    const values = zoneEntries
      .map(e => e.forward_returns[horizon])
      .filter((v): v is number => v != null)
    return {
      zone,
      count: values.length,
      percentiles: Object.fromEntries(
        RETURN_PERCENTILES.map(p => [p, percentile(values, p)])
      ) as Record<number, number | null>,
    }
  })

  return (
    <table className="w-full text-sm min-w-[980px]">
      <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
        <tr>
          <th className="text-left px-3 py-2 font-medium">Zone</th>
          <th className="text-right px-3 py-2 font-medium">N</th>
          {RETURN_PERCENTILES.map(p => (
            <th key={p} className="text-right px-3 py-2 font-medium">Ret P{p}</th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rows.map(row => (
          <tr key={`${row.zone}-${horizon}`} className="hover:bg-muted/30">
            <td className="px-3 py-2 font-semibold text-foreground">P{row.zone}</td>
            <td className="px-3 py-2 text-right tabular-nums">{fmtInt(row.count)}</td>
            {RETURN_PERCENTILES.map(p => (
              <ReturnCell key={p} value={row.percentiles[p]} />
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function durationColor(val: number): string {
  if (val <= 5) return "text-muted-foreground"
  if (val <= 20) return "text-amber-600 dark:text-amber-400"
  if (val <= 60) return "text-orange-600 dark:text-orange-400"
  return "text-red-600 dark:text-red-400"
}

function ZoneDurationTable({
  entries,
  stats,
  sessionsInZone,
  currentFactorZone,
}: {
  entries: ZoneEntry[]
  stats: RarityAnalysisResponse["zone_stats"]
  sessionsInZone: number
  currentFactorZone: number | null
}) {
  const rows = stats.map(stat => {
    const values = entries
      .filter(e =>
        e.zone_pct === stat.zone_pct &&
        !e.is_quick_recovery &&
        e.days_to_recovery != null
      )
      .map(e => e.days_to_recovery as number)
    return {
      stat,
      count: values.length,
      maxDays: values.length ? Math.max(...values) : null,
      percentiles: Object.fromEntries(
        DURATION_PERCENTILES.map(p => [p, worstTailPercentile(values, p)])
      ) as Record<number, number | null>,
    }
  })

  return (
    <table className="w-full text-xs tabular-nums border-collapse min-w-[980px]">
      <thead>
        <tr className="bg-muted text-muted-foreground uppercase tracking-wide border-b-2 border-border">
          <th className="py-2.5 px-3 font-semibold border-r border-border text-left">Zone</th>
          <th className="py-2.5 px-3 font-semibold border-r border-border text-right">Factor</th>
          <th className="py-2.5 px-3 font-semibold border-r border-border text-right">Count</th>
          <th className="py-2.5 px-3 font-semibold border-r border-border text-right">QR</th>
          <th className="py-2.5 px-3 font-semibold border-r border-border text-right">QR %</th>
          <th className="py-2.5 px-3 font-semibold border-r border-border text-center">5Y</th>
          <th className="py-2.5 px-3 font-semibold border-r border-border text-center">10Y</th>
          <th className="py-2.5 px-3 font-semibold border-r border-border text-right">Avg Days</th>
          <th className="py-2.5 px-3 font-semibold border-r border-border text-right">Max Days</th>
          {DURATION_PERCENTILES.map(p => (
            <th
              key={p}
              className="py-2.5 px-3 font-semibold border-r border-border last:border-r-0 text-right"
              title={`Longest ${p}% duration threshold`}
            >
              Days P{p}
            </th>
          ))}
        </tr>
        <tr className="bg-muted/50 border-b border-border">
          <td colSpan={9} />
          <td colSpan={DURATION_PERCENTILES.length} className="py-1 px-3 text-[9px] text-muted-foreground/60 italic text-right">
            longest-tail completed entries, excl. quick recoveries
          </td>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rows.map(({ stat, count, maxDays, percentiles }) => {
          const activeRecovery = stat.is_current_zone
          const factorCurrent = stat.zone_pct === currentFactorZone
          return (
            <tr
              key={stat.zone_pct}
              className="transition-colors hover:bg-muted/30"
              style={
                activeRecovery
                  ? { backgroundColor: "rgba(180, 100, 0, 0.12)" }
                  : factorCurrent
                    ? { backgroundColor: "rgba(14, 165, 233, 0.08)" }
                    : undefined
              }
            >
              <td
                className="py-2 px-3 border-r border-border font-bold"
                style={activeRecovery
                  ? { color: "#b45309", boxShadow: "inset 3px 0 0 #b45309" }
                  : factorCurrent
                    ? { color: "#0369a1", boxShadow: "inset 3px 0 0 #0284c7" }
                    : { color: "#9ca3af" }
                }
              >
                P{stat.zone_pct}
                {factorCurrent && (
                  <span className="ml-1 rounded bg-sky-500/12 px-1 py-0.5 text-[9px] uppercase tracking-wide text-sky-700 dark:text-sky-300">
                    factor
                  </span>
                )}
                {activeRecovery && (
                  <span className="ml-1 rounded bg-amber-500/12 px-1 py-0.5 text-[9px] uppercase tracking-wide text-amber-700 dark:text-amber-300">
                    active
                  </span>
                )}
              </td>
              <td className="py-2 px-3 border-r border-border text-right">
                {fmtPct(stat.threshold_value * 100)}
              </td>
              <td className="py-2 px-3 border-r border-border text-right text-foreground">{fmtInt(count)}</td>
              <td className="py-2 px-3 border-r border-border text-right text-foreground">{fmtInt(stat.qr_count)}</td>
              <td className="py-2 px-3 border-r border-border text-right text-foreground">{fmtPct(stat.qr_pct)}</td>
              <td className="py-2 px-3 border-r border-border text-center text-muted-foreground">
                {fmtInt(stat.count_5y)}/{fmtInt(stat.qr_5y)}
              </td>
              <td className="py-2 px-3 border-r border-border text-center text-muted-foreground">
                {fmtInt(stat.count_10y)}/{fmtInt(stat.qr_10y)}
              </td>
              <td className="py-2 px-3 border-r border-border text-right text-foreground">
                {Math.round(stat.avg_days)}
                {activeRecovery && sessionsInZone > 0 && (
                  <span className="ml-1 text-amber-700 dark:text-amber-400 font-semibold">
                    ({sessionsInZone})
                  </span>
                )}
              </td>
              <td className="py-2 px-3 border-r border-border text-right text-foreground">
                {maxDays != null ? fmtInt(maxDays) : "—"}
              </td>
              {DURATION_PERCENTILES.map(p => {
                const val = percentiles[p]
                return (
                  <td
                    key={p}
                    className={[
                      "py-2 px-3 border-r border-border last:border-r-0 text-right",
                      val != null ? durationColor(val) : "text-muted-foreground/40",
                    ].join(" ")}
                  >
                    {val != null ? fmtInt(val) : "—"}
                  </td>
                )
              })}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function ReturnCell({ value }: { value: number | null }) {
  return (
    <td className="px-3 py-2 text-right tabular-nums">
      {value == null ? (
        <span className="text-muted-foreground/40">—</span>
      ) : (
        <span
          className={[
            "inline-block min-w-20 rounded px-2 py-1",
            value < 0 ? "bg-rose-500/14 text-rose-700 dark:text-rose-300" : "",
            value > 0 ? "bg-emerald-500/14 text-emerald-700 dark:text-emerald-300" : "",
            value === 0 ? "bg-muted/30 text-muted-foreground" : "",
          ].join(" ")}
        >
          {fmtPct(value)}
        </span>
      )}
    </td>
  )
}
