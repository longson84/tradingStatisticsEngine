import type { ZoneEntry } from "@/lib/api"
import { fmtPrice, fmtPct, fmtDate } from "@/lib/format"

interface Props {
  entries: ZoneEntry[]
}

function rowBg(entry: ZoneEntry): React.CSSProperties {
  if (entry.is_active) return { backgroundColor: "rgba(180, 100, 0, 0.10)" }
  return {}
}

/** Badge: light-mode-friendly dark text on tinted bg + dark mode version */
function zoneBadgeClass(pct: number): string {
  if (pct <= 5)  return "bg-red-100 text-red-700 border-red-300 dark:bg-red-500/15 dark:text-red-400 dark:border-red-500/30"
  if (pct <= 10) return "bg-orange-100 text-orange-700 border-orange-300 dark:bg-orange-500/15 dark:text-orange-400 dark:border-orange-500/30"
  if (pct <= 15) return "bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-500/15 dark:text-amber-500 dark:border-amber-500/30"
  return "bg-yellow-100 text-yellow-700 border-yellow-300 dark:bg-yellow-500/15 dark:text-yellow-600 dark:border-yellow-500/30"
}

function maeColor(val: number): string {
  if (val <= 2)  return "text-muted-foreground"
  if (val <= 5)  return "text-yellow-600 dark:text-yellow-400"
  if (val <= 10) return "text-amber-600 dark:text-amber-400"
  if (val <= 20) return "text-orange-600 dark:text-orange-400"
  return "text-red-600 dark:text-red-400"
}

function fwdColor(val: number): string {
  if (val > 20)  return "text-emerald-700 dark:text-emerald-400 font-semibold"
  if (val > 10)  return "text-emerald-600 dark:text-emerald-500"
  if (val > 2)   return "text-green-600 dark:text-green-500"
  if (val >= 0)  return "text-muted-foreground"
  if (val >= -5) return "text-orange-600 dark:text-orange-400"
  if (val >= -10) return "text-red-500 dark:text-red-400"
  return "text-red-700 dark:text-red-500 font-semibold"
}

const FWD_BARS = ["20", "50", "100", "150", "200"]

const TH = "py-2.5 px-3 font-semibold border-r border-border last:border-r-0"
const TD = "py-2 px-3 border-r border-border last:border-r-0"

function entryKey(entry: Pick<ZoneEntry, "zone_pct" | "start_date">): string {
  return `${entry.zone_pct}|${entry.start_date}`
}

export function ZoneEntryTable({ entries }: Props) {
  const visibleEntries = entries.filter(e => !e.is_quick_recovery)
  const allByKey = new Map(entries.map(e => [entryKey(e), e]))
  const visibleKeys = new Set(visibleEntries.map(entryKey))

  function visibleLevel(entry: ZoneEntry): number {
    let level = 0
    let current: ZoneEntry | undefined = entry
    const seen = new Set<string>()
    while (current?.parent_zone_pct != null && current.parent_start_date != null) {
      const parentKey = `${current.parent_zone_pct}|${current.parent_start_date}`
      if (seen.has(parentKey)) break
      seen.add(parentKey)
      const parent = allByKey.get(parentKey)
      if (!parent) break
      if (visibleKeys.has(parentKey)) level += 1
      current = parent
    }
    return level
  }

  function visibleChildrenCount(entry: ZoneEntry): number {
    const targetKey = entryKey(entry)
    return visibleEntries.filter(candidate => {
      let current: ZoneEntry | undefined = candidate
      const seen = new Set<string>()
      while (current?.parent_zone_pct != null && current.parent_start_date != null) {
        const parentKey = `${current.parent_zone_pct}|${current.parent_start_date}`
        if (parentKey === targetKey) return true
        if (seen.has(parentKey)) return false
        seen.add(parentKey)
        current = allByKey.get(parentKey)
      }
      return false
    }).length
  }

  return (
    <div className="overflow-y-auto max-h-[640px] overflow-x-auto">
      <table className="w-full text-xs tabular-nums border-collapse min-w-[1260px]">
        <thead className="sticky top-0 z-10">
          <tr className="bg-muted text-muted-foreground uppercase tracking-wide border-b-2 border-border">
            <th className={`${TH} text-left`}>Start Date</th>
            <th className={`${TH} text-center`}>Zone</th>
            <th className={`${TH} text-right`}>Entry</th>
            <th className={`${TH} text-right`}>Low</th>
            <th className={`${TH} text-left`}>Low Date</th>
            <th className={`${TH} text-right`}>MAE %</th>
            <th className={`${TH} text-right`}>Bars To Low</th>
            <th className={`${TH} text-left`}>Recover</th>
            <th className={`${TH} text-right`}>Bars To Rec</th>
            <th className={`${TH} text-right border-l-2 border-border`}>+20b</th>
            <th className={`${TH} text-right`}>+50b</th>
            <th className={`${TH} text-right`}>+100b</th>
            <th className={`${TH} text-right`}>+150b</th>
            <th className={`${TH} text-right`}>+200b</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {visibleEntries.map((e, i) => {
            const level = visibleLevel(e)
            const childrenCount = visibleChildrenCount(e)
            return (
              <tr
                key={`${entryKey(e)}-${i}`}
                style={rowBg(e)}
                className="hover:bg-muted/20 transition-colors"
              >
                {/* Start Date with indentation */}
                <td className={`${TD} whitespace-nowrap`}>
                  <span style={{ paddingLeft: level * 16 + "px" }}>
                    {level > 0 && (
                      <span className="text-muted-foreground/50 mr-1.5">└</span>
                    )}
                    <span className="font-medium text-foreground">{fmtDate(e.start_date)}</span>
                    {childrenCount > 0 && (
                      <span className="ml-1 text-muted-foreground">({childrenCount})</span>
                    )}
                  </span>
                </td>

                {/* Zone badge */}
                <td className={`${TD} text-center`}>
                  <span className={`inline-block px-1.5 py-0.5 rounded border text-[10px] font-bold tracking-wide ${zoneBadgeClass(e.zone_pct)}`}>
                    P{e.zone_pct}
                  </span>
                </td>

              <td className={`${TD} text-right font-medium text-foreground`}>{fmtPrice(e.entry_price)}</td>
              <td className={`${TD} text-right text-foreground/80`}>{fmtPrice(e.low_price)}</td>
              <td className={`${TD} text-muted-foreground`}>{fmtDate(e.low_date)}</td>

              <td className={`${TD} text-right font-semibold ${maeColor(e.mae_pct)}`}>
                {fmtPct(e.mae_pct)}
              </td>

              <td className={`${TD} text-right text-muted-foreground`}>{e.days_to_low}</td>

              {/* Recovery pill */}
              <td className={TD}>
                {e.is_active ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 border border-amber-300 text-amber-700 dark:bg-amber-500/15 dark:border-amber-500/30 dark:text-amber-400 text-[10px] font-semibold tracking-wide">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse inline-block" />
                    Active
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/25 dark:text-emerald-500 text-[10px] font-semibold tracking-wide">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                    {fmtDate(e.recovery_date)}
                  </span>
                )}
              </td>

              <td className={`${TD} text-right`}>
                {e.is_active
                  ? <span className="text-amber-600 dark:text-amber-400 font-medium">{e.bars_elapsed} <span className="text-muted-foreground font-normal">(not recovered)</span></span>
                  : <span className="text-muted-foreground">{e.days_to_recovery}</span>
                }
              </td>

                {/* Forward return columns */}
                {FWD_BARS.map((b, idx) => {
                  const val = e.forward_returns?.[b]
                  return (
                    <td
                      key={b}
                      className={`${TD} text-right ${idx === 0 ? "border-l-2 border-border" : ""} ${val != null ? fwdColor(val) : "text-muted-foreground/40"}`}
                    >
                      {val != null ? (val >= 0 ? "+" : "") + val.toFixed(1) + "%" : "—"}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
