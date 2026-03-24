import type { SingleTickerAnalysis } from "@/lib/api"
import { fmtDate, fmtInt } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

interface Props {
  data: SingleTickerAnalysis
}

export function TimeFrame({ data }: Props) {
  return (
    <div>
      <SectionTitle>Statistical Time Frame</SectionTitle>
      <div className="grid grid-cols-4 gap-3">
        <Stat label="Symbol" value={data.symbol} />
        <Stat label="From" value={fmtDate(data.from_date)} />
        <Stat label="To" value={fmtDate(data.to_date)} />
        <Stat label="Total Bars" value={fmtInt(data.total_bars)} />
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-card border border-border rounded px-3 py-2">
      <div className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">{label}</div>
      <div className="text-sm font-semibold text-foreground tabular-nums">{value}</div>
    </div>
  )
}
