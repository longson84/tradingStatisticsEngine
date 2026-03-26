import type { MonthlyStatRow } from "@/lib/api"
import { fmtPct } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

const SATURATE_AT = 10

interface Props {
  byCalendar: MonthlyStatRow[]
  byEntryMonth: MonthlyStatRow[]
}

export function MonthlyStats({ byCalendar, byEntryMonth }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>Monthly Stats — Daily Returns by Calendar Month</SectionTitle>
        <StatsTable rows={byCalendar} />
      </div>
      <div>
        <SectionTitle>Monthly Stats — Trade Returns by Entry Month</SectionTitle>
        <StatsTable rows={byEntryMonth} />
      </div>
    </div>
  )
}

function StatsTable({ rows }: { rows: MonthlyStatRow[] }) {
  const pCols = rows.length > 0
    ? Object.keys(rows[0])
        .filter(k => /^p\d+$/.test(k))
        .map(k => Number(k.slice(1)))
        .sort((a, b) => a - b)
    : []

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs tabular-nums border-collapse">
        <thead>
          <tr className="border-b border-border text-muted-foreground uppercase tracking-wide">
            <th className="py-2 px-3 text-left font-medium">Month</th>
            <th className="py-2 px-3 text-right font-medium">Count</th>
            {pCols.map(p => (
              <th
                key={p}
                className={`py-2 px-3 text-right font-medium ${p === 50 ? "text-foreground" : ""}`}
              >
                P{p}{p === 50 && <span className="ml-0.5 text-[8px] opacity-50">med</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className={`border-b border-border/40 ${r.count === 0 ? "opacity-40" : ""}`}>
              <td className="py-1.5 px-3 font-medium text-foreground">{r.label}</td>
              <td className="py-1.5 px-3 text-right text-muted-foreground">{r.count}</td>
              {pCols.map(p => (
                <PctCell
                  key={p}
                  val={r[`p${p}` as keyof MonthlyStatRow] as number | null}
                  isMedian={p === 50}
                />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PctCell({ val, isMedian }: { val: number | null; isMedian?: boolean }) {
  if (val == null) {
    return <td className="py-1.5 px-3 text-right text-muted-foreground/40">—</td>
  }
  return (
    <td
      className={`py-1.5 px-3 text-right ${isMedian ? "font-semibold" : ""}`}
      style={heatCell(val, SATURATE_AT)}
    >
      {fmtPct(val)}
    </td>
  )
}

function heatCell(val: number, saturateAt: number): React.CSSProperties {
  if (val === 0) return { color: "#9ca3af" }
  const intensity = Math.min(Math.abs(val) / saturateAt, 1)
  if (val > 0) return {
    color: intensity > 0.4 ? "#15803d" : "#16a34a",
    backgroundColor: `rgba(34, 197, 94, ${0.07 + intensity * 0.35})`,
  }
  return {
    color: intensity > 0.4 ? "#b91c1c" : "#dc2626",
    backgroundColor: `rgba(239, 68, 68, ${0.07 + intensity * 0.35})`,
  }
}
