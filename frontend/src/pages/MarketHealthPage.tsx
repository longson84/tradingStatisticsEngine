import { useMutation } from "@tanstack/react-query"
import { Activity, Play } from "lucide-react"
import { useState } from "react"
import { MarketHealthChart } from "@/components/market/MarketHealthChart"
import { MarketDistanceDistributionChart } from "@/components/market/MarketDistanceDistributionChart"
import { MarketHealthDrilldownDrawer } from "@/components/market/MarketHealthDrilldownDrawer"
import { Sidebar } from "@/components/Sidebar"
import {
  marketHealthRunApi,
  type MarketHealthMarket,
  type MarketHealthDistributionBucket,
  type MarketHealthWeights,
} from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"


const DEFAULT_WEIGHTS: MarketHealthWeights = {
  within_10: 0.35,
  within_20: 0.30,
  within_30: 0.20,
  not_below_40: 0.15,
}

type Market = MarketHealthMarket["universe"]
const MARKET_OPTIONS: Market[] = ["US500", "US2000", "US100", "VN100", "VN30"]


export function MarketHealthPage() {
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS)
  const [selectedMarkets, setSelectedMarkets] = useState<Market[]>(MARKET_OPTIONS)
  const [drilldown, setDrilldown] = useState<{
    market: MarketHealthMarket
    bucket: MarketHealthDistributionBucket
  } | null>(null)
  const run = useMutation({
    mutationFn: () => marketHealthRunApi(weights),
  })
  const weightTotal = Object.values(weights).reduce((sum, value) => sum + value, 0)
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
            Health coefficients
          </h2>
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
            Coefficients are normalized by their total when you run.
          </p>
        </div>

        <CoefficientInput
          label="Within 10%"
          value={weights.within_10}
          onChange={value => setWeights(current => ({ ...current, within_10: value }))}
        />
        <CoefficientInput
          label="Within 20%"
          value={weights.within_20}
          onChange={value => setWeights(current => ({ ...current, within_20: value }))}
        />
        <CoefficientInput
          label="Within 30%"
          value={weights.within_30}
          onChange={value => setWeights(current => ({ ...current, within_30: value }))}
        />
        <CoefficientInput
          label="Not below 40%"
          value={weights.not_below_40}
          onChange={value => setWeights(current => ({ ...current, not_below_40: value }))}
        />

        <div className="text-[11px] text-muted-foreground">
          Coefficient total: {weightTotal.toFixed(2)}
        </div>
        <button
          onClick={() => run.mutate()}
          disabled={run.isPending || weightTotal <= 0}
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
            Equal-weight breadth based on each stock&apos;s distance from its trailing 200-session high.
          </p>
        </div>

        {!run.data && !run.isPending && !run.error && (
          <div className="rounded-lg border border-dashed border-border bg-card px-6 py-16 text-center">
            <h2 className="text-sm font-semibold">Ready to calculate from cached history</h2>
            <p className="mx-auto mt-2 max-w-xl text-xs leading-relaxed text-muted-foreground">
              Adjust the coefficients and click Run. The indicator reads the five selected US and
              Vietnam universe caches only; it does not query Yahoo Finance or VNStock.
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
                  Choose any combination of the five markets. Calculations remain unchanged.
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
            <div className={cn(
              "grid gap-4",
              visibleMarkets.length === 2 && "grid-cols-2",
              visibleMarkets.length === 3 && "grid-cols-3",
              visibleMarkets.length === 4 && "grid-cols-4",
              visibleMarkets.length === 5 && "grid-cols-5",
            )}>
              {visibleMarkets.map(market => (
                <MarketDistanceDistributionChart
                  key={market.universe}
                  market={market}
                  onBucketClick={bucket => setDrilldown({ market, bucket })}
                />
              ))}
            </div>
            <MarketHealthChart markets={visibleMarkets} />
            <MarketHealthChart markets={visibleMarkets} metric="median_distance" />
            <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 px-4 py-3 text-xs text-muted-foreground">
              US500, US2000, and US100 use yfinance auto-adjusted prices. VN100 and VN30 use VCI
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


function CoefficientInput({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (value: number) => void
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium">{label}</span>
      <input
        type="number"
        min="0"
        step="0.05"
        value={value}
        onChange={event => onChange(Math.max(0, Number(event.target.value) || 0))}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm tabular-nums focus:border-ring focus:outline-none"
      />
    </label>
  )
}


function MarketSummary({ market }: { market: MarketHealthMarket }) {
  const current = market.current
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold">{market.universe}</h2>
          <p className="mt-1 text-xs capitalize text-muted-foreground">
            {market.regime.replaceAll("_", " ")}
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold tabular-nums">
            {current.health_score.toFixed(1)}
          </div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Health
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Within 10%" value={`${current.within_10.toFixed(1)}%`} />
        <Metric label="Within 20%" value={`${current.within_20.toFixed(1)}%`} />
        <Metric label="Within 30%" value={`${current.within_30.toFixed(1)}%`} />
        <Metric label="Below 40%" value={`${current.stress_40.toFixed(1)}%`} />
        <Metric label="Median distance" value={`${current.median_distance.toFixed(1)}%`} />
        <Metric
          label="20-session change"
          value={current.change_20 == null ? "n/a" : current.change_20.toFixed(1)}
        />
        <Metric
          label="Coverage"
          value={`${fmtInt(current.eligible_count)}/${fmtInt(market.universe_size)}`}
        />
        <Metric label="Latest session" value={current.date} />
      </div>

      <div className="mt-4 border-t border-border pt-3 text-[11px] text-muted-foreground">
        Cached through {market.cache.last_date} · {market.cache.source} · fetched{" "}
        {new Date(market.cache.fetched_at).toLocaleString()}
      </div>
    </section>
  )
}


function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold tabular-nums">{value}</div>
    </div>
  )
}
