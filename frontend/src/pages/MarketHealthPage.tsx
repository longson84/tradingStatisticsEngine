import { useMutation } from "@tanstack/react-query"
import { Activity, Play } from "lucide-react"
import { useState } from "react"
import { MarketHealthChart } from "@/components/market/MarketHealthChart"
import { MarketDistanceDistributionChart } from "@/components/market/MarketDistanceDistributionChart"
import { MarketHealthDrilldownDrawer } from "@/components/market/MarketHealthDrilldownDrawer"
import { Sidebar } from "@/components/Sidebar"
import { Badge } from "@/components/ui/badge"
import {
  marketHealthRunApi,
  type MarketHealthMarket,
  type MarketHealthDistributionBucket,
} from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"


type Market = MarketHealthMarket["universe"]
const MARKET_OPTIONS: Market[] = [
  "US500", "US2000", "US100",
  "VNALL", "VN100", "VN30", "VNMID", "VNSML",
]


export function MarketHealthPage() {
  const [selectedMarkets, setSelectedMarkets] = useState<Market[]>(MARKET_OPTIONS)
  const [drilldown, setDrilldown] = useState<{
    market: MarketHealthMarket
    bucket: MarketHealthDistributionBucket
  } | null>(null)
  const run = useMutation({
    mutationFn: () => marketHealthRunApi(selectedMarkets),
  })
  const visibleMarkets = run.data?.markets.filter(
    market => selectedMarkets.includes(market.universe)
  ) ?? []
  const toggleMarket = (market: Market) => {
    setSelectedMarkets(current => {
      if (current.includes(market)) {
        return current.length === 1 ? current : current.filter(item => item !== market)
      }
      return MARKET_OPTIONS.filter(item => current.includes(item) || item === market)
    })
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Median distance
          </h2>
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
            Median stock distance from its trailing 200-session closing high.
          </p>
        </div>
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Markets to calculate
          </h2>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {MARKET_OPTIONS.map(market => (
              <button
                key={market}
                type="button"
                onClick={() => toggleMarket(market)}
                aria-pressed={selectedMarkets.includes(market)}
                className={cn(
                  "rounded border px-2 py-1 text-[11px] font-medium transition-colors",
                  selectedMarkets.includes(market)
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border text-muted-foreground hover:bg-accent"
                )}
              >
                {market}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={() => run.mutate()}
          disabled={run.isPending}
          className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Play size={14} />
          {run.isPending ? "Running…" : "Run"}
        </button>
      </Sidebar>

      <main className="flex-1 overflow-y-auto p-6">
        <div className="mb-6 border-b border-border pb-4">
          <div className="flex items-center gap-2">
            <Activity size={20} className="text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Market Health</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Median stock distance from the trailing 200-session high, with current drawdown distributions.
          </p>
        </div>

        {!run.data && !run.isPending && !run.error && (
          <div className="rounded-lg border border-dashed border-border bg-card px-6 py-16 text-center">
            <h2 className="text-sm font-semibold">Ready to calculate from saved history</h2>
            <p className="mx-auto mt-2 max-w-xl text-xs leading-relaxed text-muted-foreground">
              Select markets and click Run. The indicator reads saved local histories and does not
              query Yahoo Finance or VNStock.
            </p>
          </div>
        )}

        {run.isPending && (
          <div className="h-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full w-1/3 animate-pulse bg-primary" />
          </div>
        )}

        {run.error && (
          <div className="rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-300">
            {run.error.message}
          </div>
        )}

        {run.data && (
          <div className="space-y-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold">Displayed markets</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Change the selection and click Run to calculate only those markets.
                </p>
              </div>
              <div className="flex flex-wrap rounded-md border border-border bg-card p-1">
                {MARKET_OPTIONS.map(market => (
                  <button
                    key={market}
                    onClick={() => toggleMarket(market)}
                    aria-pressed={selectedMarkets.includes(market)}
                    className={cn(
                      "rounded px-3 py-1.5 text-xs font-medium transition-colors",
                      selectedMarkets.includes(market)
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground"
                    )}
                  >
                    {market}
                  </button>
                ))}
              </div>
            </div>

            <div className={cn(
              "grid gap-4",
              visibleMarkets.length > 1 && "xl:grid-cols-2"
            )}>
              {visibleMarkets.map(market => (
                <MarketSummary key={market.universe} market={market} />
              ))}
            </div>
            <div className="overflow-x-auto pb-2">
              <div
                className="grid gap-4"
                style={{
                  gridTemplateColumns: `repeat(${visibleMarkets.length}, minmax(300px, 1fr))`,
                  minWidth: `${visibleMarkets.length * 300}px`,
                }}
              >
                {visibleMarkets.map(market => (
                  <MarketDistanceDistributionChart
                    key={market.universe}
                    market={market}
                    onBucketClick={bucket => setDrilldown({ market, bucket })}
                  />
                ))}
              </div>
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              {visibleMarkets.map(market => (
                <MarketHealthChart key={market.universe} market={market} />
              ))}
            </div>
            <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 px-4 py-3 text-xs text-muted-foreground">
              US500, US2000, and US100 use yfinance auto-adjusted prices. All VN universes use VCI
              provider prices; VNStock does not document or expose a corporate-action adjustment
              setting, so individual distance values should be interpreted with that limitation.
              Historical breadth uses today&apos;s saved index membership and should not be treated as
              a survivorship-bias-free backtest.
            </div>
          </div>
        )}
      </main>
      {drilldown && (
        <MarketHealthDrilldownDrawer
          market={drilldown.market}
          bucket={drilldown.bucket}
          onClose={() => setDrilldown(null)}
        />
      )}
    </div>
  )
}


function MarketSummary({ market }: { market: MarketHealthMarket }) {
  const current = market.current
  const context = market.historical_context
  const differenceFromMedian = current.median_distance - context.median_distance
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">{market.universe}</h2>
            <Badge variant="outline" className={regimeClassName(context.regime)}>
              {context.regime}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Distance from trailing 200-session high
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold tabular-nums">
            {current.median_distance.toFixed(1)}%
          </div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Median distance
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Metric label="Historical median (up to 10Y)" value={`${context.median_distance.toFixed(1)}%`} />
        <Metric
          label="Versus historical median"
          value={`${differenceFromMedian >= 0 ? "+" : ""}${differenceFromMedian.toFixed(1)} pp`}
        />
        <Metric label="Historical percentile (up to 10Y)" value={`${context.current_percentile.toFixed(0)}th`} />
        <Metric
          label="Normal range (25th–75th)"
          value={`${context.q25_distance.toFixed(1)}% to ${context.q75_distance.toFixed(1)}%`}
        />
        <Metric
          label="Coverage"
          value={`${fmtInt(current.eligible_count)}/${fmtInt(market.universe_size)}`}
        />
        <Metric label="Coverage rate" value={`${current.coverage_pct.toFixed(1)}%`} />
        <Metric label="Latest session" value={current.date} />
      </div>

      <div className="mt-4">
        <div className="relative h-2 rounded-full bg-gradient-to-r from-red-500 via-amber-400 to-emerald-500">
          <span
            className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-foreground shadow"
            style={{ left: `${Math.min(100, Math.max(0, context.current_percentile))}%` }}
          />
        </div>
        <div className="mt-1 flex justify-between text-[9px] uppercase tracking-wide text-muted-foreground">
          <span>Historically weak</span>
          <span>Typical</span>
          <span>Historically strong</span>
        </div>
      </div>

      <div className="mt-4 border-t border-border pt-3 text-[11px] text-muted-foreground">
        Cached through {market.cache.last_date} · {market.cache.source} · fetched{" "}
        {new Date(market.cache.fetched_at).toLocaleString()} · context based on{" "}
        {fmtInt(context.observation_count)} sessions
      </div>
    </section>
  )
}


function regimeClassName(regime: MarketHealthMarket["historical_context"]["regime"]): string {
  if (regime === "Exceptionally strong" || regime === "Strong") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
  }
  if (regime === "Exceptionally weak" || regime === "Weak") {
    return "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300"
  }
  return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
}


function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold tabular-nums">{value}</div>
    </div>
  )
}
