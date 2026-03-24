import type { PerformanceSummary } from "@/lib/api"
import { fmtPct, fmtNum, fmtInt } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

interface Props {
  data: PerformanceSummary
}

export function PerformanceSummaryCard({ data }: Props) {
  const metrics = [
    { label: "Total Return", value: fmtPct(data.total_return_pct), color: colorPct(data.total_return_pct) },
    { label: "CAGR", value: fmtPct(data.cagr_pct), color: colorPct(data.cagr_pct) },
    { label: "Sharpe Ratio", value: fmtNum(data.sharpe_ratio), color: colorPct(data.sharpe_ratio) },
    { label: "Max Drawdown", value: fmtPct(data.max_drawdown_pct), color: "text-red-400" },
    { label: "Win Rate", value: fmtPct(data.win_rate_pct), color: colorPct(data.win_rate_pct - 50) },
    { label: "Avg Win", value: fmtPct(data.avg_win_pct), color: "text-green-400" },
    { label: "Avg Loss", value: fmtPct(data.avg_loss_pct), color: "text-red-400" },
    { label: "Profit Factor", value: data.profit_factor === 999 ? "∞" : fmtNum(data.profit_factor), color: colorPct(data.profit_factor - 1) },
    { label: "Max Consec. Losses", value: fmtInt(data.max_consec_losses), color: "text-foreground" },
    { label: "Avg Holding Days", value: fmtNum(data.avg_holding_days, 1), color: "text-foreground" },
    { label: "Best Trade", value: fmtPct(data.best_trade_pct), color: "text-green-400" },
    { label: "Worst Trade", value: fmtPct(data.worst_trade_pct), color: "text-red-400" },
    { label: "Total Trades", value: fmtInt(data.total_trades), color: "text-foreground" },
    {
      label: "Win Trades",
      value: fmtInt(Math.round(data.total_trades * data.win_rate_pct / 100)),
      color: "text-green-400",
    },
    {
      label: "Loss Trades",
      value: fmtInt(data.total_trades - Math.round(data.total_trades * data.win_rate_pct / 100)),
      color: "text-red-400",
    },
  ]

  return (
    <div>
      <SectionTitle>Performance Summary</SectionTitle>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {metrics.map(m => (
          <div key={m.label} className="bg-card border border-border rounded px-3 py-2">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">{m.label}</div>
            <div className={`text-sm font-semibold tabular-nums ${m.color}`}>{m.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function colorPct(n: number): string {
  return n >= 0 ? "text-green-400" : "text-red-400"
}
