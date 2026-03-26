import { fmtPct } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
const SATURATE_AT = 15  // ±15% = full color intensity

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

  function yearTotal(yearData: Record<string, number | null>): number {
    return Object.values(yearData).reduce<number>((acc, v) => acc + (v ?? 0), 0)
  }

  return (
    <div className="overflow-x-auto">
      <table className="text-xs tabular-nums border-collapse w-full">
        <thead>
          <tr className="border-b border-border text-muted-foreground uppercase tracking-wide text-[10px]">
            <th className="py-2 px-2 text-left font-medium w-12">Year</th>
            <th className="py-2 px-2 text-right font-medium w-14 border-r border-border/60">Total</th>
            {MONTHS.map(m => (
              <th key={m} className="py-2 px-1.5 text-center font-medium w-12">{m}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.map(year => {
            const row = data[year]
            const total = yearTotal(row)
            return (
              <tr key={year} className="border-b border-border/30 hover:bg-accent/10 transition-colors">
                <td className="py-1 px-2 font-semibold text-[11px] text-muted-foreground">{year}</td>
                <td
                  className="py-1 px-2 text-right text-[11px] font-bold border-r border-border/60"
                  style={cellStyle(total)}
                >
                  {fmtPct(total, 1)}
                </td>
                {MONTHS.map(m => {
                  const val = row[m] ?? null
                  return (
                    <td
                      key={m}
                      className="py-1 px-1.5 text-center text-[11px] rounded-[2px]"
                      style={val != null ? cellStyle(val) : { color: "#6b7280" }}
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

      {/* Color legend */}
      <div className="mt-3 flex items-center gap-2 text-[10px] text-muted-foreground">
        <span>−{SATURATE_AT}%</span>
        <div
          className="h-2 w-32 rounded"
          style={{
            background: `linear-gradient(to right,
              rgba(239,68,68,0.55),
              rgba(239,68,68,0.1) 45%,
              rgba(156,163,175,0.15) 50%,
              rgba(34,197,94,0.1) 55%,
              rgba(34,197,94,0.55))`,
          }}
        />
        <span>+{SATURATE_AT}%</span>
      </div>
    </div>
  )
}

function cellStyle(val: number): React.CSSProperties {
  if (val === 0) return { color: "#9ca3af" }
  const intensity = Math.min(Math.abs(val) / SATURATE_AT, 1)
  if (val > 0) {
    return {
      color: intensity > 0.4 ? "#15803d" : "#16a34a",
      backgroundColor: `rgba(34, 197, 94, ${0.1 + intensity * 0.45})`,
    }
  } else {
    return {
      color: intensity > 0.4 ? "#b91c1c" : "#dc2626",
      backgroundColor: `rgba(239, 68, 68, ${0.1 + intensity * 0.45})`,
    }
  }
}
