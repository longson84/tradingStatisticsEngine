import type { PerformanceSummary } from "@/lib/api"
import { fmtPct, fmtNum, fmtInt } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

interface Props {
  data: PerformanceSummary
}

export function PerformanceSummaryCard({ data }: Props) {
  const winTrades = Math.round(data.total_trades * data.win_rate_pct / 100)
  const lossTrades = data.total_trades - winTrades

  const groups: Array<{ label: string; value: string; color: string }[]> = [
    [
      { label: "Total Return",    value: fmtPct(data.total_return_pct),  color: colorPct(data.total_return_pct) },
      { label: "CAGR",            value: fmtPct(data.cagr_pct),          color: colorPct(data.cagr_pct) },
      { label: "Sharpe Ratio",    value: fmtNum(data.sharpe_ratio),       color: colorPct(data.sharpe_ratio) },
      { label: "Calmar Ratio",    value: fmtNum(data.calmar_ratio),       color: colorPct(data.calmar_ratio) },
      { label: "Profit Factor",   value: data.profit_factor === 999 ? "∞" : fmtNum(data.profit_factor), color: colorPct(data.profit_factor - 1) },
    ],
    [
      { label: "Max Drawdown",    value: fmtPct(data.max_drawdown_pct),   color: "text-red-400" },
      { label: "Curr. Drawdown",  value: fmtPct(data.current_drawdown_pct), color: "text-red-400" },
      { label: "Curr. DD Days",   value: data.current_drawdown_days > 0 ? `${data.current_drawdown_days}d` : "—", color: data.current_drawdown_days > 0 ? "text-red-400" : "text-muted-foreground" },
      { label: "Win Rate",        value: fmtPct(data.win_rate_pct),       color: colorPct(data.win_rate_pct - 50) },
      { label: "Avg Win",         value: fmtPct(data.avg_win_pct),        color: "text-green-400" },
      { label: "Avg Loss",        value: fmtPct(data.avg_loss_pct),       color: "text-red-400" },
    ],
    [
      { label: "Total Trades",    value: fmtInt(data.total_trades),       color: "text-foreground" },
      { label: "Win Trades",      value: fmtInt(winTrades),               color: "text-green-400" },
      { label: "Loss Trades",     value: fmtInt(lossTrades),              color: "text-red-400" },
      { label: "Max Consec. Loss",value: fmtInt(data.max_consec_losses),  color: "text-foreground" },
      { label: "Avg Holding Days",value: fmtNum(data.avg_holding_days, 1), color: "text-foreground" },
    ],
    [
      { label: "Best Trade",      value: fmtPct(data.best_trade_pct),     color: "text-green-400" },
      { label: "Worst Trade",     value: fmtPct(data.worst_trade_pct),    color: "text-red-400" },
      { label: "Time in Market",  value: fmtPct(data.time_in_market_pct), color: "text-foreground" },
    ],
  ]

  const metrics = groups.flat()

  return (
    <div>
      <SectionTitle>Performance Summary</SectionTitle>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {metrics.map(m => (
          <div
            key={m.label}
            className="bg-card border border-border rounded px-3 py-2.5"
            style={{ borderLeft: `3px solid ${accentBorder(m.color)}` }}
          >
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">{m.label}</div>
            <div className={`text-[15px] font-semibold tabular-nums leading-tight ${m.color}`}>{m.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function colorPct(n: number): string {
  return n >= 0 ? "text-green-400" : "text-red-400"
}

function accentBorder(tailwindColor: string): string {
  if (tailwindColor === "text-green-400") return "rgba(34, 197, 94, 0.6)"
  if (tailwindColor === "text-red-400")   return "rgba(239, 68, 68, 0.6)"
  return "rgba(100, 116, 139, 0.25)"  // neutral slate for non-directional metrics
}
