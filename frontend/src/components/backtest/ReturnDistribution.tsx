import type { DistributionRow } from "@/lib/api"
import { fmtPct, fmtInt } from "@/lib/format"

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
              percentiles.map((r) => (
                <tr key={r.percentile} className="border-b border-border/40">
                  <td className="py-1.5 px-3 text-muted-foreground">P{r.percentile}</td>
                  <td className={`py-1.5 px-3 text-right font-medium ${r.value_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {fmtPct(r.value_pct)}
                  </td>
                  <td className="py-1.5 px-3 text-right text-foreground">{fmtInt(r.cumulative_count)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
