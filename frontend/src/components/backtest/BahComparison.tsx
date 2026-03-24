import type { PerformanceSummary } from "@/lib/api"
import { fmtPct, fmtNum } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

interface Props {
  strategy: PerformanceSummary
  bah: PerformanceSummary
}

interface Row {
  label: string
  strat: string
  bah: string
  ratio: string | null
  stratColor?: string
  bahColor?: string
  ratioColor?: string
}

export function BahComparison({ strategy, bah }: Props) {
  const rows: Row[] = [
    {
      label: "Total Return",
      strat: fmtPct(strategy.total_return_pct),
      bah: fmtPct(bah.total_return_pct),
      ratio: safeRatio(strategy.total_return_pct, bah.total_return_pct),
      stratColor: colorPct(strategy.total_return_pct),
      bahColor: colorPct(bah.total_return_pct),
      ratioColor: colorRatio(strategy.total_return_pct, bah.total_return_pct, false),
    },
    {
      label: "CAGR",
      strat: fmtPct(strategy.cagr_pct),
      bah: fmtPct(bah.cagr_pct),
      ratio: safeRatio(strategy.cagr_pct, bah.cagr_pct),
      stratColor: colorPct(strategy.cagr_pct),
      bahColor: colorPct(bah.cagr_pct),
      ratioColor: colorRatio(strategy.cagr_pct, bah.cagr_pct, false),
    },
    {
      label: "Max Drawdown",
      strat: fmtPct(strategy.max_drawdown_pct),
      bah: fmtPct(bah.max_drawdown_pct),
      ratio: safeRatio(strategy.max_drawdown_pct, bah.max_drawdown_pct),
      stratColor: "text-red-400",
      bahColor: "text-red-400",
      ratioColor: colorRatio(strategy.max_drawdown_pct, bah.max_drawdown_pct, true),
    },
    {
      label: "Current Drawdown",
      strat: fmtPct(strategy.current_drawdown_pct),
      bah: fmtPct(bah.current_drawdown_pct),
      ratio: safeRatio(strategy.current_drawdown_pct, bah.current_drawdown_pct),
      stratColor: "text-red-400",
      bahColor: "text-red-400",
      ratioColor: colorRatio(strategy.current_drawdown_pct, bah.current_drawdown_pct, true),
    },
    {
      label: "Calmar Ratio",
      strat: fmtNum(strategy.calmar_ratio),
      bah: fmtNum(bah.calmar_ratio),
      ratio: safeRatio(strategy.calmar_ratio, bah.calmar_ratio),
      stratColor: colorPct(strategy.calmar_ratio),
      bahColor: colorPct(bah.calmar_ratio),
      ratioColor: colorRatio(strategy.calmar_ratio, bah.calmar_ratio, false),
    },
    {
      label: "Time in Market",
      strat: fmtPct(strategy.time_in_market_pct),
      bah: fmtPct(bah.time_in_market_pct),
      ratio: null,
    },
  ]

  return (
    <div>
      <SectionTitle>Strategy vs Buy &amp; Hold</SectionTitle>
      <div className="overflow-x-auto">
        <table className="w-full text-xs tabular-nums border-collapse">
          <thead>
            <tr className="border-b border-border text-muted-foreground uppercase tracking-wide">
              <th className="py-2 px-3 text-left font-medium w-44">Metric</th>
              <th className="py-2 px-3 text-right font-medium">Strategy</th>
              <th className="py-2 px-3 text-right font-medium">Buy &amp; Hold</th>
              <th className="py-2 px-3 text-right font-medium">S ÷ BaH</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.label} className={`border-b border-border/40 ${i % 2 === 0 ? "" : "bg-card/50"}`}>
                <td className="py-2 px-3 text-muted-foreground">{r.label}</td>
                <td className={`py-2 px-3 text-right font-medium ${r.stratColor ?? "text-foreground"}`}>{r.strat}</td>
                <td className={`py-2 px-3 text-right ${r.bahColor ?? "text-foreground"}`}>{r.bah}</td>
                <td className={`py-2 px-3 text-right font-medium ${r.ratioColor ?? "text-foreground"}`}>
                  {r.ratio ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function colorPct(n: number): string {
  return n >= 0 ? "text-green-400" : "text-red-400"
}

/** lowerIsBetter=true for Max DD: ratio <1 means strategy had less drawdown → green */
function colorRatio(a: number, b: number, lowerIsBetter: boolean): string {
  if (b === 0) return "text-muted-foreground"
  const r = a / b
  const good = lowerIsBetter ? r < 1 : r > 1
  return good ? "text-green-400" : "text-red-400"
}

function safeRatio(a: number, b: number): string | null {
  if (b === 0) return null
  return fmtNum(a / b) + "x"
}
