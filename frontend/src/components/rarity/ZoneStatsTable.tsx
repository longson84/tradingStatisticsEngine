import type { ZoneStat } from "@/lib/api"
import { fmtPct, fmtFactor } from "@/lib/format"

interface Props {
  stats: ZoneStat[]
}

const MAE_COLS = ["98", "95", "90", "85", "80"]

/** Heat-map color — darker -600 variants read clearly on light backgrounds */
function maeColor(val: number): string {
  if (val <= 2)  return "text-muted-foreground"
  if (val <= 5)  return "text-yellow-600 dark:text-yellow-400"
  if (val <= 10) return "text-amber-600 dark:text-amber-400"
  if (val <= 20) return "text-orange-600 dark:text-orange-400"
  return "text-red-600 dark:text-red-400"
}

const TH = "py-2.5 px-3 font-semibold border-r border-border last:border-r-0"
const TD = "py-2 px-3 border-r border-border last:border-r-0"

export function ZoneStatsTable({ stats }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs tabular-nums border-collapse">
        <thead>
          <tr className="bg-muted text-muted-foreground uppercase tracking-wide border-b-2 border-border">
            <th className={`${TH} text-left`}>Zone</th>
            <th className={`${TH} text-right`}>Factor</th>
            <th className={`${TH} text-right`}>Count</th>
            <th className={`${TH} text-right`}>QR</th>
            <th className={`${TH} text-right`}>QR %</th>
            <th className={`${TH} text-center`}>5Y</th>
            <th className={`${TH} text-center`}>10Y</th>
            <th className={`${TH} text-right`}>Avg Days</th>
            <th className={`${TH} text-right`}>MMAE %</th>
            {/* Separator */}
            <th className="py-2.5 px-0 w-px bg-border/60 border-r border-border" />
            {MAE_COLS.map(p => (
              <th key={p} className={`${TH} text-right`}>MAE-{p}%</th>
            ))}
          </tr>
          <tr className="bg-muted/50 border-b border-border">
            <td colSpan={9} />
            <td className="px-0 bg-border/40" />
            <td colSpan={MAE_COLS.length} className="py-1 px-3 text-[9px] text-muted-foreground/60 italic text-right">
              excl. quick recoveries
            </td>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {stats.map(row => {
            const cur = row.is_current_zone
            return (
              <tr
                key={row.zone_pct}
                className="transition-colors hover:bg-muted/30"
                style={cur ? { backgroundColor: "rgba(180, 100, 0, 0.12)" } : undefined}
              >
                <td
                  className={`${TD} font-bold`}
                  style={cur
                    ? { color: "#b45309", boxShadow: "inset 3px 0 0 #b45309" }
                    : { color: "#9ca3af" }
                  }
                >
                  P{row.zone_pct}
                </td>
                <td className={`${TD} text-right`} style={cur ? { color: "#92400e", fontWeight: 700 } : {}}>
                  {fmtFactor(row.threshold_value)}
                </td>
                <td className={`${TD} text-right text-foreground`}>{row.count}</td>
                <td className={`${TD} text-right text-foreground`}>{row.qr_count}</td>
                <td className={`${TD} text-right text-foreground`}>{fmtPct(row.qr_pct)}</td>
                <td className={`${TD} text-center text-muted-foreground`}>{row.count_5y}/{row.qr_5y}</td>
                <td className={`${TD} text-center text-muted-foreground`}>{row.count_10y}/{row.qr_10y}</td>
                <td className={`${TD} text-right text-foreground`}>{Math.round(row.avg_days)}</td>
                <td className={`${TD} text-right font-semibold ${maeColor(row.mmae_pct)}`}>
                  {fmtPct(row.mmae_pct)}
                </td>
                {/* Separator */}
                <td className="px-0 bg-border/40" />
                {MAE_COLS.map(p => {
                  const val = row.mae_by_percentile[p] ?? 0
                  return (
                    <td key={p} className={`${TD} text-right ${maeColor(val)}`}>
                      {fmtPct(val)}
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
