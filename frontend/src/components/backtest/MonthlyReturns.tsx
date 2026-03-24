import { fmtPct } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

interface Props {
  strategyData: Record<string, Record<string, number | null>>
  bahData: Record<string, Record<string, number | null>>
}

export function MonthlyReturns({ strategyData, bahData }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>Monthly Returns — Strategy</SectionTitle>
        <HeatmapTable data={strategyData} />
      </div>
      <div>
        <SectionTitle>Monthly Returns — Buy &amp; Hold</SectionTitle>
        <HeatmapTable data={bahData} />
      </div>
    </div>
  )
}

function HeatmapTable({ data }: { data: Record<string, Record<string, number | null>> }) {
  const years = Object.keys(data).sort((a, b) => Number(b) - Number(a))

  if (years.length === 0) {
    return <p className="text-sm text-muted-foreground italic">No data.</p>
  }

  // Compute year totals
  function yearTotal(yearData: Record<string, number | null>): number {
    return Object.values(yearData).reduce<number>((acc, v) => acc + (v ?? 0), 0)
  }

  return (
    <div className="overflow-x-auto">
      <table className="text-xs tabular-nums border-collapse">
        <thead>
          <tr className="border-b border-border text-muted-foreground uppercase tracking-wide">
            <th className="py-2 px-2 text-left font-medium w-14">Year</th>
            <th className="py-2 px-2 text-right font-medium w-16">Total</th>
            {MONTHS.map(m => (
              <th key={m} className="py-2 px-2 text-right font-medium w-14">{m}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.map(year => {
            const row = data[year]
            const total = yearTotal(row)
            return (
              <tr key={year} className="border-b border-border/40">
                <td className="py-1.5 px-2 font-semibold text-muted-foreground">{year}</td>
                <td
                  className="py-1.5 px-2 text-right font-semibold text-[11px]"
                  style={cellStyle(total)}
                >
                  {fmtPct(total, 1)}
                </td>
                {MONTHS.map(m => {
                  const val = row[m] ?? null
                  return (
                    <td
                      key={m}
                      className="py-1.5 px-2 text-right text-[11px]"
                      style={val != null ? { ...cellStyle(val) } : { color: "#4b5563" }}
                    >
                      {val != null ? fmtPct(val, 1) : "—"}
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

function cellStyle(val: number): React.CSSProperties {
  if (val === 0) return { color: "#9ca3af" }
  const intensity = Math.min(Math.abs(val) / 10, 1)  // saturate at ±10%
  if (val > 0) {
    const g = Math.round(100 + intensity * 100)
    return { color: `rgb(74, ${g + 34}, 74)`, backgroundColor: `rgba(34, ${g}, 34, 0.25)` }
  } else {
    const r = Math.round(180 + intensity * 60)
    return { color: `rgb(${r}, 74, 74)`, backgroundColor: `rgba(${r}, 34, 34, 0.25)` }
  }
}
