import type { HealthRow } from "@/lib/api"
import { fmtPct, fmtInt } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

interface Props {
  rows: HealthRow[]
}

export function StrategyHealth({ rows }: Props) {
  if (rows.length === 0) {
    return (
      <div>
        <SectionTitle>Strategy Health Over Time</SectionTitle>
        <p className="text-sm text-muted-foreground italic">No data.</p>
      </div>
    )
  }

  const pCols = Object.keys(rows[0])
    .filter(k => /^p\d+$/.test(k))
    .map(k => Number(k.slice(1)))
    .sort((a, b) => a - b)

  return (
    <div>
      <SectionTitle>Strategy Health Over Time</SectionTitle>
      <div className="overflow-x-auto">
        <table className="w-full text-xs tabular-nums border-collapse">
          <thead>
            <tr className="border-b border-border text-muted-foreground uppercase tracking-wide">
              <th className="py-2 px-3 text-left font-medium">Year</th>
              <th className="py-2 px-3 text-right font-medium">Trades</th>
              {pCols.map(p => (
                <th key={p} className="py-2 px-3 text-right font-medium">P{p}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.year} className="border-b border-border/40">
                <td className="py-2 px-3 font-semibold text-foreground">{r.year}</td>
                <td className="py-2 px-3 text-right text-foreground">{fmtInt(r.trades)}</td>
                {pCols.map(p => (
                  <PctCell key={p} val={r[`p${p}` as keyof HealthRow] as number | null} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function PctCell({ val }: { val: number | null }) {
  if (val == null) return <td className="py-2 px-3 text-right text-muted-foreground/40">—</td>
  const color = val >= 0 ? "text-green-400" : "text-red-400"
  return <td className={`py-2 px-3 text-right ${color}`}>{fmtPct(val)}</td>
}
