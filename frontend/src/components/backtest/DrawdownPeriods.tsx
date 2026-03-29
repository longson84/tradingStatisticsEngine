import { SectionTitle } from "./SectionTitle"
import { fmtDate, fmtPct, fmtInt, fmtPrice } from "@/lib/format"

const DD_MIN_THRESHOLD = 5   // minimum depth % to count as a drawdown period

interface Props {
  equityStrategy: Record<string, number>
  tickerPrices: Record<string, number>
  label?: string
}

interface Period {
  startDate: string
  startPx: number | null
  troughDate: string
  troughPx: number | null
  recoveryDate: string | null
  recoveryPx: number | null
  depthPct: number
  daysToTrough: number
  recoveryDays: number | null
  totalDays: number | null
}

function daysBetween(d1: string, d2: string): number {
  return Math.round((Date.parse(d2) - Date.parse(d1)) / 86_400_000)
}

function computeDrawdowns(
  curve: Record<string, number>,
  tickerPrices: Record<string, number>,
  top = 10
): Period[] {
  const sorted = Object.entries(curve).sort(([a], [b]) => a.localeCompare(b))
  if (sorted.length < 2) return []

  const periods: Period[] = []
  let peak = sorted[0][1]
  let inDD = false
  let startDate = ""
  let startPeak = peak
  let troughVal = Infinity
  let troughDate = ""

  for (const [date, val] of sorted) {
    if (val >= peak) {
      if (inDD) {
        periods.push({
          startDate,
          startPx:     tickerPrices[startDate]    ?? null,
          troughDate,
          troughPx:    tickerPrices[troughDate]   ?? null,
          recoveryDate: date,
          recoveryPx:  tickerPrices[date]         ?? null,
          depthPct: (troughVal / startPeak - 1) * 100,
          daysToTrough: daysBetween(startDate, troughDate),
          recoveryDays: daysBetween(troughDate, date),
          totalDays: daysBetween(startDate, date),
        })
        inDD = false
      }
      peak = val
    } else {
      if (!inDD) {
        inDD = true
        startDate = date
        startPeak = peak
        troughVal = val
        troughDate = date
      } else if (val < troughVal) {
        troughVal = val
        troughDate = date
      }
    }
  }

  if (inDD) {
    periods.push({
      startDate,
      startPx:     tickerPrices[startDate]  ?? null,
      troughDate,
      troughPx:    tickerPrices[troughDate] ?? null,
      recoveryDate: null,
      recoveryPx:  null,
      depthPct: (troughVal / startPeak - 1) * 100,
      daysToTrough: daysBetween(startDate, troughDate),
      recoveryDays: null,
      totalDays: null,
    })
  }

  return periods
    .filter(p => p.depthPct < -DD_MIN_THRESHOLD)
    .sort((a, b) => a.depthPct - b.depthPct)
    .slice(0, top)
    .sort((a, b) => b.startDate.localeCompare(a.startDate))
}

function stripeColor(pct: number): string {
  if (pct < -30) return "rgba(239,68,68,0.75)"
  if (pct < -15) return "rgba(239,68,68,0.50)"
  return "rgba(249,115,22,0.50)"
}

export function DrawdownPeriods({ equityStrategy, tickerPrices, label = "Strategy" }: Props) {
  const periods = computeDrawdowns(equityStrategy, tickerPrices)

  return (
    <div>
      <SectionTitle>Top Drawdown Periods — {label}</SectionTitle>
      {periods.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">No drawdown data.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-xs tabular-nums border-collapse [&_td]:border-r [&_td]:border-border [&_th]:border-r [&_th]:border-border">
            <thead>
              {/* Group header */}
              <tr className="bg-muted/40 border-b border-border text-[9px] uppercase tracking-widest text-muted-foreground/70">
                <th colSpan={7} className="py-1.5 px-3 text-left font-semibold">Period</th>
                <th colSpan={4} className="py-1.5 px-3 text-left font-semibold border-l border-border">Depth &amp; Duration</th>
                <th colSpan={1} className="py-1.5 px-3 text-left font-semibold border-l border-border">Status</th>
              </tr>
              {/* Column header */}
              <tr className="bg-card border-b border-border text-muted-foreground uppercase tracking-wide">
                <th className="py-2 px-3 text-left font-medium w-8">#</th>
                <th className="py-2 px-3 text-left font-medium">Start</th>
                <th className="py-2 px-3 text-right font-medium">Start Px</th>
                <th className="py-2 px-3 text-left font-medium">Trough</th>
                <th className="py-2 px-3 text-right font-medium">Trough Px</th>
                <th className="py-2 px-3 text-left font-medium">Recovery</th>
                <th className="py-2 px-3 text-right font-medium">Recovery Px</th>
                <th className="py-2 px-3 text-right font-medium border-l border-border">Depth</th>
                <th className="py-2 px-3 text-right font-medium">To Trough (d)</th>
                <th className="py-2 px-3 text-right font-medium">To Recovery (d)</th>
                <th className="py-2 px-3 text-right font-medium">Total (d)</th>
                <th className="py-2 px-3 text-left font-medium border-l border-border">Status</th>
              </tr>
            </thead>
            <tbody>
              {periods.map((p, idx) => (
                <tr
                  key={p.startDate}
                  className={`border-b border-border hover:bg-blue-500/20 transition-colors ${idx % 2 === 1 ? "bg-card/40" : ""}`}
                >
                  <td
                    className="py-1.5 px-3 text-muted-foreground/60 font-mono text-[10px]"
                    style={{ borderLeft: `3px solid ${stripeColor(p.depthPct)}` }}
                  >
                    {idx + 1}
                  </td>

                  <td className="py-1.5 px-3 text-foreground">{fmtDate(p.startDate)}</td>
                  <td className="py-1.5 px-3 text-right text-muted-foreground">{p.startPx != null ? fmtPrice(p.startPx) : "—"}</td>

                  <td className="py-1.5 px-3 text-foreground">{fmtDate(p.troughDate)}</td>
                  <td className="py-1.5 px-3 text-right text-red-400">{p.troughPx != null ? fmtPrice(p.troughPx) : "—"}</td>

                  <td className="py-1.5 px-3 text-muted-foreground">{fmtDate(p.recoveryDate)}</td>
                  <td className="py-1.5 px-3 text-right text-muted-foreground">{p.recoveryPx != null ? fmtPrice(p.recoveryPx) : "—"}</td>

                  <td className="py-1.5 px-3 text-right border-l border-border/30">
                    <span
                      className="inline-block px-1.5 py-0.5 rounded-sm text-[11px] font-bold"
                      style={{
                        color:           "#b91c1c",
                        backgroundColor: `rgba(239,68,68,${p.depthPct < -30 ? 0.18 : p.depthPct < -15 ? 0.12 : 0.08})`,
                      }}
                    >
                      {fmtPct(p.depthPct)}
                    </span>
                  </td>
                  <td className="py-1.5 px-3 text-right text-muted-foreground">{fmtInt(p.daysToTrough)}</td>
                  <td className="py-1.5 px-3 text-right text-muted-foreground">{p.recoveryDays != null ? fmtInt(p.recoveryDays) : "—"}</td>
                  <td className="py-1.5 px-3 text-right text-muted-foreground">{p.totalDays != null ? fmtInt(p.totalDays) : "—"}</td>

                  <td className="py-1.5 px-3 border-l border-border/30">
                    {p.recoveryDate == null
                      ? <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm bg-yellow-500/15 text-yellow-500 font-semibold text-[10px]">● Ongoing</span>
                      : <span className="text-green-500 text-[10px] font-medium">✓ Recovered</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
