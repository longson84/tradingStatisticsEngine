import { useState } from "react"
import type { SingleTickerAnalysis } from "@/lib/api"
import { fmtDate, fmtPct, fmtNum } from "@/lib/format"
import { TimeFrame } from "./TimeFrame"
import { EquityChart } from "./EquityChart"
import { CurrentPositionCard } from "./CurrentPositionCard"
import { PerformanceSummaryCard } from "./PerformanceSummary"
import { BahComparison } from "./BahComparison"
import { TradeLog } from "./TradeLog"
import { MaeScatter } from "./MaeScatter"
import { MaeMfeScatter } from "./MaeMfeScatter"
import { ReturnVsDuration } from "./ReturnVsDuration"
import { MfeRetracementScatter } from "./MfeRetracementScatter"
import { ReturnDistribution } from "./ReturnDistribution"
import { MonthlyReturns } from "./MonthlyReturns"
import { MonthlyStats } from "./MonthlyStats"
import { StrategyHealth } from "./StrategyHealth"
import { DrawdownPeriods } from "./DrawdownPeriods"
import { DrawdownDepthAnalysis } from "./DrawdownDepthAnalysis"
import { DrawdownDurationAnalysis } from "./DrawdownDurationAnalysis"
import { RollingReturn } from "./RollingReturn"
import { AnnualReturns } from "./AnnualReturns"
import { EarlyTradeBehavior } from "./EarlyTradeBehavior"
import { SellLagBelowMA } from "./SellLagBelowMA"

interface Props {
  data: SingleTickerAnalysis
  sellLag: number
}

export function StrategyAnalysisResults({ data, sellLag }: Props) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="space-y-8">
      {/* Collapsible header */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <button
          onClick={() => setCollapsed(c => !c)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-accent/30 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-foreground">{data.strategy_label}</span>
            <span className="text-xs text-muted-foreground">
              {fmtDate(data.from_date)} → {fmtDate(data.to_date)}
            </span>
            <span className="text-xs text-muted-foreground">
              {data.strategy.total_trades} trades
            </span>
            <span className={`text-xs font-semibold ${data.strategy.total_return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
              {data.strategy.total_return_pct >= 0 ? "+" : ""}
              {fmtPct(data.strategy.total_return_pct)}
            </span>
          </div>
          <span className="text-muted-foreground text-xs">{collapsed ? "▼" : "▲"}</span>
        </button>

        {!collapsed && (
          <div className="px-4 py-2 border-t border-border bg-background/30 text-xs text-muted-foreground flex gap-6">
            <span>CAGR: <span className={data.strategy.cagr_pct >= 0 ? "text-green-400 font-medium" : "text-red-400 font-medium"}>{fmtPct(data.strategy.cagr_pct)}</span></span>
            <span>Sharpe: <span className="text-foreground font-medium">{fmtNum(data.strategy.sharpe_ratio)}</span></span>
            <span>Max DD: <span className="text-red-400 font-medium">{fmtPct(data.strategy.max_drawdown_pct)}</span></span>
            <span>Win Rate: <span className="text-foreground font-medium">{fmtPct(data.strategy.win_rate_pct, 1)}</span></span>
          </div>
        )}
      </div>

      <EquityChart
        strategyLabel={data.strategy_label}
        equityStrategy={data.equity_curve_strategy}
        equityBah={data.equity_curve_bah}
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <RollingReturn equityStrategy={data.equity_curve_strategy} equityBah={data.equity_curve_bah} />
        <AnnualReturns equityStrategy={data.equity_curve_strategy} equityBah={data.equity_curve_bah} strategyLabel={data.strategy_label} />
      </div>

      <TimeFrame data={data} />
      <CurrentPositionCard position={data.current_position} />
      <PerformanceSummaryCard data={data.strategy} />

      <SellLagBelowMA data={data.undercut_distribution} sellLag={sellLag} />

      <BahComparison strategy={data.strategy} bah={data.bah} />
      <DrawdownPeriods equityStrategy={data.equity_curve_strategy} tickerPrices={data.ticker_prices} label="Strategy" />
      <DrawdownPeriods equityStrategy={data.equity_curve_bah} tickerPrices={data.ticker_prices} label="Buy &amp; Hold" />
      <DrawdownDepthAnalysis
        equityStrategy={data.equity_curve_strategy}
        equityBah={data.equity_curve_bah}
        strategyLabel={data.strategy_label}
        currentDepthPct={data.strategy.current_drawdown_pct}
      />

      <DrawdownDurationAnalysis
        equityStrategy={data.equity_curve_strategy}
        equityBah={data.equity_curve_bah}
        strategyLabel={data.strategy_label}
        currentDurationDays={data.strategy.current_drawdown_days}
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        <ReturnDistribution
          percentiles={data.return_percentiles}
          title="RETURN DIST — All Trades"
        />
        <ReturnDistribution
          percentiles={data.mae_percentiles_winners}
          title="MAE DIST — Winning Trades"
        />
        <ReturnDistribution
          percentiles={data.mfe_percentiles_winners}
          title="MFE DIST — Winning Trades"
        />
        <ReturnDistribution
          percentiles={data.mfe_percentiles_losers}
          title="MFE DIST — Losing Trades"
        />
      </div>

      <EarlyTradeBehavior trades={data.trades} />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <MaeScatter trades={data.trades} />
        <MaeMfeScatter trades={data.trades} />
        <ReturnVsDuration trades={data.trades} />
        <MfeRetracementScatter trades={data.trades} />
      </div>

      <TradeLog
        trades={data.trades}
        equityStrategy={data.equity_curve_strategy}
        equityBah={data.equity_curve_bah}
      />
      <MonthlyReturns strategyData={data.monthly_returns_strategy} bahData={data.monthly_returns_bah} />
      <MonthlyStats byCalendar={data.monthly_stats_by_calendar} byEntryMonth={data.monthly_stats_by_entry_month} />
      <StrategyHealth rows={data.health_by_year} />
    </div>
  )
}
