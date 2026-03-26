import type { DistributionRow } from "@/lib/api"
import { fmtPct, fmtInt } from "@/lib/format"

const SATURATE_AT = 20   // ±20% = full intensity

interface Props {
  percentiles: DistributionRow[]
  title?: string
}

export function ReturnDistribution({ percentiles, title = "Return Distribution" }: Props) {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs tabular-nums border-collapse">
          <thead>
            <tr className="border-b border-border text-muted-foreground uppercase tracking-wide">
              <th className="py-2 px-3 text-left font-medium">{title}</th>
              <th className="py-2 px-3 text-right font-medium">Value</th>
              <th className="py-2 px-3 text-right font-medium">Cum. Count</th>
            </tr>
          </thead>
          <tbody>
            {percentiles.length === 0 ? (
              <tr><td colSpan={3} className="py-3 px-3 text-muted-foreground italic">No data</td></tr>
            ) : (
              percentiles.map((r) => {
                const isMedian = r.percentile === 50
                return (
                  <tr
                    key={r.percentile}
                    className={`border-b border-border/40 ${isMedian ? "border-t border-border/60" : ""}`}
                  >
                    <td className={`py-1.5 px-3 ${isMedian ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
                      P{r.percentile}
                      {isMedian && <span className="ml-1.5 text-[9px] text-muted-foreground/60 font-normal uppercase tracking-wider">median</span>}
                    </td>
                    <td
                      className={`py-1.5 px-3 text-right ${isMedian ? "font-bold" : "font-medium"}`}
                      style={heatCell(r.value_pct, SATURATE_AT)}
                    >
                      {fmtPct(r.value_pct)}
                    </td>
                    <td className={`py-1.5 px-3 text-right ${isMedian ? "font-semibold text-foreground" : "text-foreground"}`}>
                      {fmtInt(r.cumulative_count)}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function heatCell(val: number, saturateAt: number): React.CSSProperties {
  if (val === 0) return { color: "#9ca3af" }
  const intensity = Math.min(Math.abs(val) / saturateAt, 1)
  if (val > 0) return {
    color: intensity > 0.4 ? "#15803d" : "#16a34a",
    backgroundColor: `rgba(34, 197, 94, ${0.08 + intensity * 0.38})`,
  }
  return {
    color: intensity > 0.4 ? "#b91c1c" : "#dc2626",
    backgroundColor: `rgba(239, 68, 68, ${0.08 + intensity * 0.38})`,
  }
}
