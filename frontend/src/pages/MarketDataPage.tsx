import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, CheckCircle2, Database, RefreshCw, Trash2 } from "lucide-react"
import { Sidebar } from "@/components/Sidebar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  marketDataClearApi,
  marketDataJobApi,
  marketDataRefreshApi,
  marketDataStatusApi,
  watchlistRefreshJobsApi,
  type MarketDataCacheStatus,
  type MarketDataJob,
  type WatchlistRefreshJob,
} from "@/lib/api"


type Market = MarketDataCacheStatus["universe"]
type MarketRefreshScope = "full" | "us" | "vn"
type MarketRefreshDataset = "prices" | "fundamentals"

const MARKET_REFRESH_PLANS: Record<MarketRefreshScope, Market[]> = {
  full: ["US2000", "US500", "US100", "VNALL"],
  us: ["US2000", "US500", "US100"],
  vn: ["VNALL"],
}

const MARKET_REFRESH_LABELS: Record<MarketRefreshScope, string> = {
  full: "Full market",
  us: "US market",
  vn: "VN market",
}

const MARKET_DATASET_LABELS: Record<MarketRefreshDataset, string> = {
  prices: "Prices",
  fundamentals: "Fundamentals",
}

interface MarketRefreshProgress {
  scope: MarketRefreshScope
  dataset: MarketRefreshDataset
  market: Market
  step: number
  steps: number
  current: number
  total: number
  message: string
  completed: boolean
}

interface MarketDataActivity {
  market: Market
  timestamp: string
}


export function MarketDataPage() {
  const queryClient = useQueryClient()
  const [marketRefreshProgress, setMarketRefreshProgress] = useState<MarketRefreshProgress | null>(null)
  const status = useQuery({
    queryKey: ["market-data-status"],
    queryFn: marketDataStatusApi,
    staleTime: 0,
    refetchOnMount: true,
    refetchInterval: query => query.state.data?.markets.some(
      market => market.latest_job?.status === "queued"
        || market.latest_job?.status === "running"
        || market.latest_fundamentals_job?.status === "queued"
        || market.latest_fundamentals_job?.status === "running"
    ) ? 1_500 : false,
  })
  const watchlistJobs = useQuery({
    queryKey: ["watchlist-refresh-jobs"],
    queryFn: watchlistRefreshJobsApi,
    staleTime: 0,
    refetchOnMount: true,
    refetchInterval: query => query.state.data?.jobs.some(
      job => job.status === "queued" || job.status === "running"
    ) ? 1_500 : false,
  })
  const refresh = useMutation({
    mutationFn: ({ market, mode, dataset }: {
      market: Market
      mode: "incremental" | "full"
      dataset: "prices" | "fundamentals"
    }) => marketDataRefreshApi(market, mode, dataset),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["market-data-status"] }),
  })
  const marketRefresh = useMutation({
    mutationFn: async ({ scope, dataset }: {
      scope: MarketRefreshScope
      dataset: MarketRefreshDataset
    }) => {
      const plan = MARKET_REFRESH_PLANS[scope]
      for (const [index, market] of plan.entries()) {
        setMarketRefreshProgress({
          scope,
          dataset,
          market,
          step: index + 1,
          steps: plan.length,
          current: 0,
          total: 0,
          message: `Starting ${market}`,
          completed: false,
        })
        const startedJob = await marketDataRefreshApi(market, "incremental", dataset)
        const completedJob = await waitForMarketDataJob(startedJob.id, job => {
          setMarketRefreshProgress({
            scope,
            dataset,
            market,
            step: index + 1,
            steps: plan.length,
            current: job.current,
            total: job.total,
            message: job.message,
            completed: false,
          })
        })
        if (completedJob.status === "failed") {
          throw new Error(
            `${market} ${dataset} update failed: ${completedJob.error ?? completedJob.message}`
          )
        }
        await queryClient.invalidateQueries({ queryKey: ["market-data-status"] })
      }
      const finalMarket = plan[plan.length - 1]
      setMarketRefreshProgress({
        scope,
        dataset,
        market: finalMarket,
        step: plan.length,
        steps: plan.length,
        current: 1,
        total: 1,
        message: `${MARKET_REFRESH_LABELS[scope]} ${dataset} update completed`,
        completed: true,
      })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["market-data-status"] }),
  })
  const clear = useMutation({
    mutationFn: marketDataClearApi,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["market-data-status"] }),
  })

  const clearMarket = (market: Market) => {
    const marketCode = market.startsWith("US") ? "US" : "VN"
    const affected = marketCode === "US"
      ? "US2000, US500, and US100"
      : "VNALL, VN100, VN30, VNMID, and VNSML"
    const confirmed = window.confirm(
      `Clear every stored ${marketCode} price bar? This affects ${affected}. Price History and Market Health will be unavailable for them until rebuilt.`
    )
    if (confirmed) clear.mutate(market)
  }

  const anyMarketJobRunning = status.data?.markets.some(market => (
    market.latest_job?.status === "queued"
      || market.latest_job?.status === "running"
      || market.latest_fundamentals_job?.status === "queued"
      || market.latest_fundamentals_job?.status === "running"
  )) ?? false
  const marketRefreshDisabled = marketRefresh.isPending || refresh.isPending || anyMarketJobRunning
  const latestPriceJob = latestMarketDataJob(status.data?.markets, "prices")
  const latestFundamentalsJob = latestMarketDataJob(status.data?.markets, "fundamentals")
  const latestPriceActivity = latestMarketDataActivity(status.data?.markets, "prices")
  const latestFundamentalsActivity = latestMarketDataActivity(
    status.data?.markets,
    "fundamentals"
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mb-6 border-b border-border pb-4">
          <div className="flex items-center gap-2">
            <Database size={20} className="text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Market Data</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Maintain local price history and point-in-time company fundamentals.
          </p>
        </div>

        <section className="mb-5 rounded-xl border border-primary/20 bg-gradient-to-br from-primary/10 via-card to-card p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <RefreshCw size={18} className="text-primary" />
                <h2 className="text-lg font-semibold">Update markets</h2>
              </div>
              <p className="mt-1 max-w-3xl text-xs leading-relaxed text-muted-foreground">
                Run prices and fundamentals separately. US updates run sequentially in coverage
                order: US2000 → US500 → US100. VN updates run VNALL once because it covers the
                smaller VN universes.
              </p>
            </div>
            <div className="grid gap-3">
              {(["prices", "fundamentals"] as const).map(dataset => (
                <div key={dataset} className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <span className="w-24 text-xs font-semibold">{MARKET_DATASET_LABELS[dataset]}</span>
                  <div className="flex flex-wrap gap-2">
                    {(["full", "us", "vn"] as const).map(scope => {
                      const active = marketRefresh.isPending
                        && marketRefresh.variables?.scope === scope
                        && marketRefresh.variables.dataset === dataset
                      return (
                        <Button
                          key={scope}
                          variant={dataset === "prices" && scope === "full" ? "default" : "outline"}
                          disabled={marketRefreshDisabled}
                          onClick={() => marketRefresh.mutate({ scope, dataset })}
                        >
                          <RefreshCw className={active ? "animate-spin" : ""} />
                          {MARKET_REFRESH_LABELS[scope]}
                        </Button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <LastRunSummary
              label="Last price run"
              job={latestPriceJob}
              activity={latestPriceActivity}
            />
            <LastRunSummary
              label="Last fundamentals run"
              job={latestFundamentalsJob}
              activity={latestFundamentalsActivity}
            />
          </div>
          {marketRefreshProgress && (
            <MarketRefreshProgressView progress={marketRefreshProgress} />
          )}
        </section>

        <div className="mb-5 rounded-lg border border-border bg-card px-4 py-3 text-xs leading-relaxed text-muted-foreground">
          Price History and Market Health read canonical PostgreSQL price bars. Update downloads
          recent sessions and upserts them; Full rebuild requests maximum provider history.
          Fundamental reads and refresh writes use canonical PostgreSQL point-in-time data.
          Incremental refreshes reuse recently updated overlapping symbols; full refreshes bypass
          the reuse window. A failed symbol write leaves its existing database rows unchanged.
        </div>

        {status.isPending && (
          <div className="h-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full w-1/3 animate-pulse bg-primary" />
          </div>
        )}
        {status.error && <ErrorMessage message={status.error.message} />}
        {marketRefresh.error && <ErrorMessage message={marketRefresh.error.message} />}
        {refresh.error && <ErrorMessage message={refresh.error.message} />}
        {clear.error && <ErrorMessage message={clear.error.message} />}

        <div className="grid gap-5 xl:grid-cols-2">
          {status.data?.markets.map(market => (
            <MarketCacheCard
              key={market.universe}
              market={market}
              mutating={marketRefresh.isPending || refresh.isPending || clear.isPending}
              onRefresh={(mode, dataset) => refresh.mutate({
                market: market.universe,
                mode,
                dataset,
              })}
              onClear={() => clearMarket(market.universe)}
            />
          ))}
        </div>

        <section className="mt-5 rounded-lg border border-border bg-card p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Watchlist price refreshes</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Start a targeted refresh from the relevant Watchlist page. Active and latest jobs are monitored here.
              </p>
            </div>
            <Badge variant="outline">
              {watchlistJobs.data?.jobs.length ?? 0} jobs
            </Badge>
          </div>
          {watchlistJobs.error && (
            <div className="mt-4"><ErrorMessage message={watchlistJobs.error.message} /></div>
          )}
          <div className="mt-4 grid gap-3 xl:grid-cols-2">
            {watchlistJobs.data?.jobs.map(job => (
              <WatchlistJobProgress key={job.id} job={job} />
            ))}
          </div>
          {!watchlistJobs.isPending && watchlistJobs.data?.jobs.length === 0 && (
            <div className="mt-4 rounded-md border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
              No watchlist refresh has run since the API started.
            </div>
          )}
        </section>

        {status.data && (
          <div className="mt-5 rounded-md border border-border bg-muted/30 px-4 py-3 text-[11px] text-muted-foreground">
            Price storage: <span className="font-mono">{status.data.price_storage}</span>
            <br />
            Fundamental storage: <span className="font-mono">{status.data.fundamentals_storage}</span>
          </div>
        )}
      </main>
    </div>
  )
}


function MarketRefreshProgressView({ progress }: { progress: MarketRefreshProgress }) {
  const currentStepProgress = progress.total > 0
    ? Math.min(1, progress.current / progress.total)
    : 0
  const totalProgress = progress.completed
    ? 100
    : ((progress.step - 1 + currentStepProgress) / progress.steps) * 100

  return (
    <div className="mt-4 rounded-lg border border-primary/20 bg-background/70 p-3">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-medium">
          {MARKET_DATASET_LABELS[progress.dataset]} · {MARKET_REFRESH_LABELS[progress.scope]} · {progress.completed
            ? "Complete"
            : `Step ${progress.step}/${progress.steps}: ${progress.market}`}
        </span>
        <span className="tabular-nums text-muted-foreground">{Math.round(totalProgress)}%</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-primary transition-[width] duration-300"
          style={{ width: `${totalProgress}%` }}
        />
      </div>
      <p className="mt-2 truncate text-[11px] text-muted-foreground" title={progress.message}>
        {progress.message}
      </p>
    </div>
  )
}


function LastRunSummary({
  label,
  job,
  activity,
}: {
  label: string
  job: MarketDataJob | null
  activity: MarketDataActivity | null
}) {
  return (
    <div className="rounded-md border border-border bg-background/60 px-3 py-2 text-xs">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{label}</span>
        {job && (
          <Badge variant={job.status === "failed" ? "destructive" : "secondary"}>
            {job.status}
          </Badge>
        )}
        {!job && activity && <Badge variant="outline">database activity</Badge>}
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">
        {job
          ? `${job.market} · ${formatDateTime(job.finished_at ?? job.started_at)}`
          : activity
            ? `${activity.market} · ${formatDateTime(activity.timestamp)} · job history unavailable after API restart`
            : "No run or stored activity found."}
      </p>
    </div>
  )
}


function latestMarketDataJob(
  markets: MarketDataCacheStatus[] | undefined,
  dataset: MarketRefreshDataset
): MarketDataJob | null {
  const jobs = markets
    ?.map(market => dataset === "prices" ? market.latest_job : market.latest_fundamentals_job)
    .filter((job): job is MarketDataJob => job != null) ?? []
  return jobs.reduce<MarketDataJob | null>((latest, job) => {
    if (!latest) return job
    const jobTime = Date.parse(job.finished_at ?? job.started_at ?? "") || 0
    const latestTime = Date.parse(latest.finished_at ?? latest.started_at ?? "") || 0
    return jobTime > latestTime ? job : latest
  }, null)
}


function latestMarketDataActivity(
  markets: MarketDataCacheStatus[] | undefined,
  dataset: MarketRefreshDataset
): MarketDataActivity | null {
  return markets?.reduce<MarketDataActivity | null>((latest, market) => {
    const timestamp = dataset === "prices"
      ? market.recent_activity_at
      : market.fundamentals_recent_activity_at
    if (!timestamp) return latest
    if (!latest || Date.parse(timestamp) > Date.parse(latest.timestamp)) {
      return { market: market.universe, timestamp }
    }
    return latest
  }, null) ?? null
}


async function waitForMarketDataJob(
  jobId: string,
  onProgress: (job: Awaited<ReturnType<typeof marketDataJobApi>>) => void
) {
  while (true) {
    await delay(1_500)
    const job = await marketDataJobApi(jobId)
    onProgress(job)
    if (job.status === "completed" || job.status === "failed") return job
  }
}


function delay(milliseconds: number) {
  return new Promise(resolve => window.setTimeout(resolve, milliseconds))
}


function WatchlistJobProgress({ job }: { job: WatchlistRefreshJob }) {
  const progress = job.total > 0 ? Math.min(100, (job.current / job.total) * 100) : 0
  return (
    <div className="rounded-md border border-border bg-muted/20 p-3">
      <div className="flex items-start justify-between gap-3 text-xs">
        <div>
          <span className="font-medium">{job.watchlist_name}</span>
          <span className="ml-2 text-muted-foreground">{job.market}</span>
        </div>
        <Badge variant={job.status === "failed" ? "destructive" : "secondary"}>
          {job.status}
        </Badge>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-primary transition-[width] duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="mt-2 flex justify-between gap-3 text-[11px] text-muted-foreground">
        <span className="truncate" title={job.message}>{job.message}</span>
        <span className="shrink-0 tabular-nums">
          {job.total > 0 ? `${job.current}/${job.total}` : job.status}
        </span>
      </div>
      {job.error && (
        <p className="mt-2 whitespace-pre-wrap text-[11px] text-destructive">{job.error}</p>
      )}
      <p className="mt-2 text-[10px] text-muted-foreground">
        Started {formatDateTime(job.started_at)}
        {job.finished_at ? ` · Finished ${formatDateTime(job.finished_at)}` : ""}
      </p>
    </div>
  )
}


function MarketCacheCard({
  market,
  mutating,
  onRefresh,
  onClear,
}: {
  market: MarketDataCacheStatus
  mutating: boolean
  onRefresh: (
    mode: "incremental" | "full",
    dataset: "prices" | "fundamentals"
  ) => void
  onClear: () => void
}) {
  const job = market.latest_job
  const fundamentalsJob = market.latest_fundamentals_job
  const running = [job, fundamentalsJob].some(
    item => item?.status === "queued" || item?.status === "running"
  )
  const canClearMarket = market.universe === "US2000" || market.universe === "VNALL"
  const marketCode = market.universe.startsWith("US") ? "US" : "VN"
  const errors = market.errors ?? []
  const totalSymbols = market.universe_symbol_count || market.symbol_count || 0
  const fullyCurrent = market.exists
    && totalSymbols > 0
    && market.current_symbol_count + market.checked_no_new_bar_count === totalSymbols
    && market.failed_refresh_symbol_count === 0
  const checkedWithoutBar = market.checked_no_new_bar_count > 0

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">{market.universe}</h2>
            <Badge variant={fullyCurrent ? "secondary" : "outline"}>
              {fullyCurrent
                ? checkedWithoutBar ? "Checked" : "Current"
                : market.exists ? "Partial" : "No cache"}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {market.universe.startsWith("US")
              ? "Yahoo Finance · adjusted prices"
              : "VNStock KBS → VCI fallback · adjustment unspecified"}
          </p>
        </div>
        {fullyCurrent
          ? <CheckCircle2 size={19} className="text-emerald-500" />
          : <AlertTriangle size={19} className="text-amber-500" />}
      </div>

      <div className="mt-5 grid grid-cols-2 gap-x-5 gap-y-3 text-xs sm:grid-cols-3">
        <Datum label="Expected session" value={market.expected_session ?? "—"} />
        <Datum label="Oldest last trade" value={market.coverage_through ?? "—"} />
        <Datum label="Newest ticker session" value={market.last_date ?? "—"} />
        <Datum
          label="Current symbols"
          value={`${market.current_symbol_count.toLocaleString()} / ${totalSymbols.toLocaleString()}`}
        />
        <Datum label="Stale symbols" value={market.stale_symbol_count.toLocaleString()} />
        <Datum
          label="Checked, no new bar"
          value={market.checked_no_new_bar_count.toLocaleString()}
        />
        <Datum
          label="Refresh failures"
          value={market.failed_refresh_symbol_count.toLocaleString()}
        />
        <Datum label="Missing prices" value={market.missing_symbol_count.toLocaleString()} />
        <Datum label="First history" value={market.first_date ?? "—"} />
        <Datum label="Rows" value={formatInteger(market.row_count ?? null)} />
        <Datum
          label="Recent activity"
          value={formatDateTime(market.recent_activity_at ?? null)}
        />
      </div>

      <div className="mt-5 rounded-md border border-border bg-muted/20 p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs font-semibold">Point-in-time fundamentals</div>
          <Badge variant={market.fundamentals_exists ? "secondary" : "outline"}>
            {market.fundamentals_symbol_count}/{totalSymbols} symbols
          </Badge>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
          <Datum
            label="Recent activity"
            value={formatDateTime(market.fundamentals_recent_activity_at ?? null)}
          />
          <Datum
            label="Oldest ticker update"
            value={formatDateTime(market.fundamentals_oldest_fetched_at ?? null)}
          />
          <Datum label="Snapshots" value={(market.fundamentals_snapshot_count ?? 0).toLocaleString()} />
          <Datum label="Storage" value="PostgreSQL" />
        </div>
      </div>

      {errors.length > 0 && (
        <p className="mt-3 text-[11px] text-amber-600 dark:text-amber-400">
          {errors.length} refresh error{errors.length === 1 ? "" : "s"}; existing database rows were retained.
        </p>
      )}

      {job && <JobProgress job={job} />}
      {fundamentalsJob && <JobProgress job={fundamentalsJob} />}

      <div className="mt-5 flex flex-wrap gap-2">
        <Button disabled={mutating || running} onClick={() => onRefresh("incremental", "prices")}>
          <RefreshCw className={running ? "animate-spin" : ""} />
          Update prices
        </Button>
        <Button
          variant="outline"
          disabled={mutating || running}
          onClick={() => onRefresh("incremental", "fundamentals")}
        >
          <RefreshCw className={running ? "animate-spin" : ""} />
          Update fundamentals
        </Button>
        <details className="group relative">
          <summary className="flex h-8 cursor-pointer list-none items-center rounded-lg border border-border px-2.5 text-sm font-medium hover:bg-muted">
            Advanced
          </summary>
          <div className="absolute left-0 top-10 z-10 flex w-48 flex-col gap-2 rounded-lg border border-border bg-popover p-2 shadow-lg">
            <Button
              variant="outline"
              disabled={mutating || running}
              onClick={() => onRefresh("full", "prices")}
            >
              <RefreshCw /> Full rebuild
            </Button>
            {canClearMarket && (
              <Button
                variant="destructive"
                disabled={mutating || running || !market.exists}
                onClick={onClear}
              >
                <Trash2 /> Clear all {marketCode} prices
              </Button>
            )}
          </div>
        </details>
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        {market.universe.startsWith("VN")
          ? "VNStock requests run sequentially at about 14 requests/minute. Canonical ticker data is reused across VNALL, VN100, VN30, VNMID, and VNSML."
          : "Yahoo Finance price requests use bounded batches. Fundamentals are stored once per ticker and reused across US2000, US500, and US100."}
      </p>
      <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground">
        Coverage through is the oldest latest-session date among covered symbols. Recent activity is only the newest ticker write and does not imply complete coverage.
      </p>
    </section>
  )
}


function JobProgress({ job }: { job: NonNullable<MarketDataCacheStatus["latest_job"]> }) {
  const progress = job.total > 0 ? Math.min(100, (job.current / job.total) * 100) : 0
  return (
    <div className="mt-5 rounded-md border border-primary/20 bg-primary/5 p-3">
      <div className="flex justify-between gap-3 text-xs">
        <span className="font-medium capitalize">{job.dataset} · {job.mode} refresh</span>
        <span className="tabular-nums text-muted-foreground">
          {job.total > 0 ? `${job.current}/${job.total}` : job.status}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-primary transition-[width] duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="mt-2 truncate text-[11px] text-muted-foreground" title={job.message}>
        {job.message}
      </p>
      {job.error && (
        <p className="mt-2 whitespace-pre-wrap text-[11px] text-destructive">{job.error}</p>
      )}
    </div>
  )
}


function Datum({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-0.5 font-medium tabular-nums">{value}</div>
    </div>
  )
}


function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {message}
    </div>
  )
}


function formatDateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "—"
}


function formatInteger(value: number | null): string {
  return value == null ? "—" : value.toLocaleString()
}
