import type { MarketHealthDistributionBucket, MarketHealthMarket } from "@/lib/api"


const MARKET_COLORS: Record<MarketHealthMarket["universe"], string> = {
  US500: "#16a34a",
  US2000: "#7c3aed",
  US100: "#2563eb",
  VNALL: "#0f766e",
  VN100: "#dc2626",
  VN30: "#ea580c",
  VNMID: "#d97706",
  VNSML: "#db2777",
}


export function MarketDistanceDistributionChart({
  market,
  onBucketClick,
}: {
  market: MarketHealthMarket
  onBucketClick?: (bucket: MarketHealthDistributionBucket) => void
}) {
  const total = market.distribution.reduce((sum, bucket) => sum + bucket.count, 0)
  const largestBucketPercentage = Math.max(
    ...market.distribution.map(bucket => bucket.percentage),
    0,
  )

  return (
    <section className="min-w-0 rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{market.universe} distribution</h3>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Distance from trailing 200-session high · {market.current.date}
          </p>
        </div>
        <div className="text-right">
          <div className="text-lg font-semibold tabular-nums">{total.toLocaleString()}</div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">stocks</div>
        </div>
      </div>

      <div className="mt-5 space-y-2">
        {market.distribution.map(bucket => (
          <button
            key={bucket.label}
            type="button"
            onClick={() => onBucketClick?.(bucket)}
            className="grid w-full grid-cols-[70px_1fr_82px] items-center gap-2 rounded-sm text-left transition-colors hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <div className="text-[11px] tabular-nums text-muted-foreground">
              {bucket.label}
            </div>
            <div className="h-6 overflow-hidden rounded-sm bg-muted">
              <div
                className="h-full rounded-sm opacity-85 transition-[width] duration-300"
                style={{
                  width: `${largestBucketPercentage > 0
                    ? bucket.percentage / largestBucketPercentage * 100
                    : 0}%`,
                  backgroundColor: MARKET_COLORS[market.universe],
                }}
              />
            </div>
            <div className="text-right tabular-nums">
              <div className="text-[10px] font-semibold leading-none">
                {bucket.count.toLocaleString()} · {bucket.percentage.toFixed(1)}%
              </div>
              <div className="mt-0.5 text-[8px] leading-none text-muted-foreground">
                cum. {bucket.cumulative_percentage.toFixed(1)}%
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="mt-4 border-t border-border pt-3 text-[10px] text-muted-foreground">
        Bar width is relative to this market&apos;s largest band. Labels show actual share and cumulative share.
      </div>
    </section>
  )
}
