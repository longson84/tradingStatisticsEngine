import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, CheckCircle2, Database, RefreshCw, Trash2 } from "lucide-react"
import { Sidebar } from "@/components/Sidebar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  marketDataClearApi,
  marketDataRefreshApi,
  marketDataStatusApi,
  type MarketDataCacheStatus,
} from "@/lib/api"


type Market = "US500" | "US2000" | "US100" | "VN100" | "VN30"


export function MarketDataPage() {
  const queryClient = useQueryClient()
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
  const refresh = useMutation({
    mutationFn: ({ market, mode, dataset }: {
      market: Market
      mode: "incremental" | "full"
      dataset: "prices" | "fundamentals"
    }) => marketDataRefreshApi(market, mode, dataset),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["market-data-status"] }),
  })
  const clear = useMutation({
    mutationFn: marketDataClearApi,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["market-data-status"] }),
  })

  const clearMarket = (market: Market) => {
    const confirmed = window.confirm(
      `Clear the local ${market} price-history cache? Market Health cannot calculate ${market} until you rebuild it.`
    )
    if (confirmed) clear.mutate(market)
  }

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

        <div className="mb-5 rounded-lg border border-border bg-card px-4 py-3 text-xs leading-relaxed text-muted-foreground">
          Market Health&apos;s Run button only reads these local files. Update downloads recent
          sessions and merges them into the cache; Full rebuild requests maximum provider history.
          Fundamentals are retained indefinitely and refresh only when requested here. A failed
          refresh keeps the previous cache unchanged.
        </div>

        {status.isPending && (
          <div className="h-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full w-1/3 animate-pulse bg-primary" />
          </div>
        )}
        {status.error && <ErrorMessage message={status.error.message} />}
        {refresh.error && <ErrorMessage message={refresh.error.message} />}
        {clear.error && <ErrorMessage message={clear.error.message} />}

        <div className="grid gap-5 xl:grid-cols-2">
          {status.data?.markets.map(market => (
            <MarketCacheCard
              key={market.universe}
              market={market}
              mutating={refresh.isPending || clear.isPending}
              onRefresh={(mode, dataset) => refresh.mutate({
                market: market.universe,
                mode,
                dataset,
              })}
              onClear={() => clearMarket(market.universe)}
            />
          ))}
        </div>

        {status.data && (
          <div className="mt-5 rounded-md border border-border bg-muted/30 px-4 py-3 text-[11px] text-muted-foreground">
            Local cache directory: <span className="font-mono">{status.data.cache_directory}</span>
            <br />
            Fundamentals: <span className="font-mono">{status.data.fundamentals_cache_directory}</span>
          </div>
        )}
      </main>
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

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">{market.universe}</h2>
            <Badge variant={market.exists ? "secondary" : "outline"}>
              {market.exists ? "Cached" : "No cache"}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {market.universe.startsWith("US")
              ? "Yahoo Finance · adjusted prices"
              : "VNStock VCI · adjustment unspecified"}
          </p>
        </div>
        {market.exists
          ? <CheckCircle2 size={19} className="text-emerald-500" />
          : <AlertTriangle size={19} className="text-amber-500" />}
      </div>

      <div className="mt-5 grid grid-cols-2 gap-x-5 gap-y-3 text-xs sm:grid-cols-3">
        <Datum label="Latest session" value={market.last_date ?? "—"} />
        <Datum label="First session" value={market.first_date ?? "—"} />
        <Datum label="Fetched" value={formatDateTime(market.fetched_at)} />
        <Datum label="Symbols" value={formatInteger(market.symbol_count)} />
        <Datum label="Rows" value={formatInteger(market.row_count)} />
        <Datum label="File size" value={formatBytes(market.size_bytes)} />
      </div>

      <div className="mt-5 rounded-md border border-border bg-muted/20 p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs font-semibold">Point-in-time fundamentals</div>
          <Badge variant={market.fundamentals_exists ? "secondary" : "outline"}>
            {market.fundamentals_symbol_count}/{market.symbol_count ?? 0} symbols
          </Badge>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
          <Datum label="Fetched" value={formatDateTime(market.fundamentals_fetched_at)} />
          <Datum label="Snapshots" value={market.fundamentals_snapshot_count.toLocaleString()} />
          <Datum label="File size" value={formatBytes(market.fundamentals_size_bytes)} />
        </div>
      </div>

      {market.errors.length > 0 && (
        <p className="mt-3 text-[11px] text-amber-600 dark:text-amber-400">
          {market.errors.length} ticker{market.errors.length === 1 ? "" : "s"} unavailable or kept from older cached history.
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
            <Button
              variant="destructive"
              disabled={mutating || running || !market.exists}
              onClick={onClear}
            >
              <Trash2 /> Clear cache
            </Button>
          </div>
        </details>
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        {market.universe.startsWith("VN")
          ? `VNStock requests run sequentially at about 14 requests/minute; price and fundamental caches shared with ${market.universe === "VN30" ? "VN100" : "VN30"} are reused.`
          : "Yahoo Finance price requests use bounded batches. Fundamentals are stored once per ticker and reused across US2000, US500, and US100."}
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


function formatBytes(value: number): string {
  if (!value) return "—"
  const units = ["B", "KB", "MB", "GB"]
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1)
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}
