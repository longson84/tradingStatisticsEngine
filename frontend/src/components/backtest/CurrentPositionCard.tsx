import type { CurrentPosition } from "@/lib/api"
import { fmtDate, fmtPrice, fmtPct, fmtInt } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

interface Props {
  position: CurrentPosition | null
}

export function CurrentPositionCard({ position }: Props) {
  return (
    <div>
      <SectionTitle>Current Position</SectionTitle>
      {!position ? (
        <div className="text-sm text-muted-foreground italic">No open position</div>
      ) : (
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
          <Stat label="Entry Date" value={fmtDate(position.entry_date)} />
          <Stat label="Entry Price" value={fmtPrice(position.entry_price)} />
          <Stat label="Holding Days" value={fmtInt(position.holding_days)} />
          <Stat
            label="Unrealized P&L"
            value={position.unrealized_return_pct != null ? fmtPct(position.unrealized_return_pct) : "—"}
            color={position.unrealized_return_pct != null
              ? position.unrealized_return_pct >= 0 ? "text-green-400" : "text-red-400"
              : ""}
          />
          <Stat
            label="MAE"
            value={position.mae_pct != null ? fmtPct(position.mae_pct) : "—"}
            color="text-red-400"
          />
          <Stat
            label="MFE"
            value={position.mfe_pct != null ? fmtPct(position.mfe_pct) : "—"}
            color="text-green-400"
          />
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, color = "text-foreground" }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-card border border-border rounded px-3 py-2">
      <div className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${color}`}>{value}</div>
    </div>
  )
}
