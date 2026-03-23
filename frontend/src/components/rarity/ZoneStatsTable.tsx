import type { ZoneStat } from "@/lib/api"
import { fmtPct, fmtFactor } from "@/lib/format"

interface Props {
  stats: ZoneStat[]
}

const MAE_COLS = ["98", "95", "90", "85", "80"]

export function ZoneStatsTable({ stats }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs tabular-nums border-collapse">
        <thead>
          <tr className="text-white/40 uppercase tracking-wide border-b border-white/10">
            <th className="py-2 px-3 text-left font-medium">PCT</th>
            <th className="py-2 px-3 text-right font-medium">Factor</th>
            <th className="py-2 px-3 text-right font-medium">Count</th>
            <th className="py-2 px-3 text-right font-medium">QR</th>
            <th className="py-2 px-3 text-right font-medium">QR %</th>
            <th className="py-2 px-3 text-center font-medium">5Y</th>
            <th className="py-2 px-3 text-center font-medium">10Y</th>
            <th className="py-2 px-3 text-right font-medium">Days</th>
            <th className="py-2 px-3 text-right font-medium">MMAE %</th>
            {MAE_COLS.map(p => (
              <th key={p} className="py-2 px-3 text-right font-medium">MAE-{p}%</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {stats.map(row => {
            const isCurrentZone = row.is_current_zone
            return (
              <tr
                key={row.zone_pct}
                className="border-b border-white/5 transition-colors"
                style={isCurrentZone ? { backgroundColor: "rgba(234, 179, 8, 0.25)" } : undefined}
              >
                <td className="py-2 px-3 font-bold" style={isCurrentZone ? { color: "#fbbf24" } : { color: "#9ca3af" }}>
                  {row.zone_pct}%
                </td>
                <td className="py-2 px-3 text-right" style={isCurrentZone ? { color: "#fde68a", fontWeight: 700 } : {}}>
                  {fmtFactor(row.threshold_value)}
                </td>
                <td className="py-2 px-3 text-right text-white/80">{row.count}</td>
                <td className="py-2 px-3 text-right text-white/80">{row.qr_count}</td>
                <td className="py-2 px-3 text-right text-white/80">{fmtPct(row.qr_pct)}</td>
                <td className="py-2 px-3 text-center text-white/70">{row.count_5y}/{row.qr_5y}</td>
                <td className="py-2 px-3 text-center text-white/70">{row.count_10y}/{row.qr_10y}</td>
                <td className="py-2 px-3 text-right text-white/80">{Math.round(row.avg_days)}</td>
                <td className="py-2 px-3 text-right text-white/80">{fmtPct(row.mmae_pct)}</td>
                {MAE_COLS.map(p => (
                  <td key={p} className="py-2 px-3 text-right text-white/70">
                    {fmtPct(row.mae_by_percentile[p] ?? 0)}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
