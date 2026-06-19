import type { UndercutDistributionRow } from "@/lib/api"
import { fmtInt, fmtPct } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

interface Props {
  data: UndercutDistributionRow[] | null
  sellLag: number
}

/** Colour the undercut-0 row green (clean trades) and others amber. */
function pctColor(undercuts: number): string {
  if (undercuts === 0) return "text-green-400"
  return "text-amber-400"
}

export function SellLagBelowMA({ data, sellLag }: Props) {
  if (!data || data.length === 0) return null

  const totalWinners = data.reduce((sum, r) => sum + r.trade_count, 0)

  return (
    <div>
      <SectionTitle>
        Undercut Distribution — Winning Trades (sell_lag = {sellLag})
      </SectionTitle>
      <p className="text-xs text-muted-foreground mb-3">
        Counts how many <em>temporary</em> dips below the MA each winning
        trade survived before exiting. An undercut is a run of close&nbsp;≤&nbsp;MA
        that recovers in ≤&nbsp;{sellLag}&nbsp;bars — too short to trigger the
        exit countdown. The exit itself is not counted.
      </p>
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-accent/30 text-muted-foreground">
              <th className="px-3 py-2 text-left font-medium">Undercuts</th>
              <th className="px-3 py-2 text-right font-medium">Trades</th>
              <th className="px-3 py-2 text-right font-medium">% of Winners</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr
                key={row.undercuts}
                className="border-b border-border/50 hover:bg-accent/10 transition-colors"
              >
                <td className="px-3 py-2 font-mono text-foreground">
                  {row.undercuts === 0 ? "0 (never)" : row.undercuts}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-foreground">
                  {fmtInt(row.trade_count)}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">
                  <span className={pctColor(row.undercuts)}>
                    {fmtPct(row.pct_of_winners)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-border bg-accent/10 text-muted-foreground">
              <td className="px-3 py-2 font-medium">Total winners</td>
              <td className="px-3 py-2 text-right font-mono tabular-nums">
                {fmtInt(totalWinners)}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}
