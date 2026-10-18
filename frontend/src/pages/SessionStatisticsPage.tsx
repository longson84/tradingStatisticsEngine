import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { BarChart3, Search } from "lucide-react"
import { Link } from "react-router"

import { Sidebar } from "@/components/Sidebar"
import { Badge } from "@/components/ui/badge"
import {
  instrumentSessionStatisticsApi,
  instrumentsApi,
  type InstrumentCatalogItem,
  type SessionStatisticMetric,
} from "@/lib/api"
import { fmtCompactVnd, fmtInt, fmtProviderSource } from "@/lib/format"
import { useDebouncedValue } from "@/lib/useDebouncedValue"

const GROUPS = [
  ["market_activity", "Market activity"],
  ["foreign_activity", "Foreign activity"],
  ["trade_direction", "Trade direction"],
  ["order_imbalance", "Order imbalance and trade size"],
] as const

const SUMMARY_CODES = [
  "total_volume", "total_value", "total_match_volume", "total_deal_volume",
  "fr_net_value_total", "total_net_trade_volume",
] as const

export function SessionStatisticsPage() {
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<InstrumentCatalogItem | null>(null)
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")
  const [request, setRequest] = useState<{ id: number; start: string; end: string } | null>(null)
  const debounced = useDebouncedValue(search.trim(), 300)
  const instruments = useQuery({
    queryKey: ["session-statistics-instruments", debounced],
    queryFn: () => instrumentsApi({
      search: debounced,
      capability: "session_stats",
      has_price_history: false,
      limit: 20,
    }),
    enabled: debounced.length >= 3,
  })
  const stats = useQuery({
    queryKey: ["instrument-session-statistics", request],
    queryFn: () => instrumentSessionStatisticsApi({
      instrument_id: request!.id, start: request!.start, end: request!.end,
    }),
    enabled: request != null,
    retry: false,
  })
  const metrics = new Map(stats.data?.metrics.map(metric => [metric.code, metric]))
  const missing = stats.error?.message.includes("No stored")
  const operationQuery = selected && request
    ? new URLSearchParams({
        dataset: "session_stats", instrument_id: String(selected.id),
        symbol: selected.symbol, period_start: request.start, period_end: request.end,
      }).toString()
    : ""

  return <div className="flex min-h-screen bg-background text-foreground">
    <Sidebar />
    <main className="min-w-0 flex-1 overflow-y-auto p-6">
      <header className="mb-6 border-b border-border pb-5">
        <div className="flex items-center gap-2"><BarChart3 size={21} className="text-primary" /><h1 className="text-2xl font-bold">Vietnam Session Statistics</h1></div>
        <p className="mt-1 text-sm text-muted-foreground">One stored VCI aggregate for one Vietnam equity and one selected period.</p>
      </header>
      <section className="mb-5 rounded-xl border border-border bg-card p-5">
        <div className="grid gap-4 lg:grid-cols-[minmax(260px,1fr)_180px_180px_auto] lg:items-end">
          <div className="relative">
            <label className="mb-1 block text-xs font-medium">Instrument</label>
            <Search className="pointer-events-none absolute bottom-2.5 left-3 text-muted-foreground" size={15} />
            <input value={search} onChange={event => { setSearch(event.target.value); setSelected(null); setRequest(null) }} placeholder="Search FPT, VNM, ACB…" className="w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm" />
            {debounced.length >= 3 && selected == null && <div className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-md border border-border bg-popover shadow-lg">
              {instruments.isFetching && <div className="p-3 text-xs text-muted-foreground">Searching…</div>}
              {instruments.data?.instruments.map(item => <button key={item.id} onClick={() => { setSelected(item); setSearch(item.symbol); setRequest(null) }} className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-accent"><span className="font-medium">{item.symbol}</span><span className="text-xs text-muted-foreground">{item.venue_code}</span></button>)}
            </div>}
          </div>
          <DateInput label="Start date" value={start} onChange={value => { setStart(value); setRequest(null) }} />
          <DateInput label="End date" value={end} onChange={value => { setEnd(value); setRequest(null) }} />
          <button disabled={!selected || !start || !end || start > end || stats.isFetching} onClick={() => setRequest({ id: selected!.id, start, end })} className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40">Apply period</button>
        </div>
      </section>
      {!request && <EmptyState text="Choose an eligible Vietnam equity and one period." />}
      {stats.isFetching && <div className="h-1 animate-pulse rounded bg-primary/50" />}
      {stats.error && <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"><div>{stats.error.message}</div>{missing && <Link className="mt-2 inline-block font-semibold underline" to={`/data-operations/single?${operationQuery}`}>Fetch this exact period in Data Operations.</Link>}</div>}
      {stats.data && <>
        <div className="mb-4 flex flex-wrap items-center gap-2"><h2 className="text-xl font-bold">{stats.data.symbol}</h2><Badge variant="outline">{stats.data.venue_code}</Badge><Badge variant="secondary">{fmtProviderSource(stats.data.source)}</Badge><span className="text-xs text-muted-foreground">{stats.data.period_start}–{stats.data.period_end} · schema v{stats.data.schema_version} · fetched {new Date(stats.data.fetched_at).toLocaleString()}</span></div>
        <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">{SUMMARY_CODES.map(code => { const metric = metrics.get(code); return metric ? <Datum key={code} metric={metric} /> : null })}</div>
        <div className="grid gap-5 xl:grid-cols-2">{GROUPS.map(([group, title]) => <MetricGroup key={group} title={title} metrics={stats.data.metrics.filter(metric => metric.group === group)} />)}</div>
      </>}
    </main>
  </div>
}

function DateInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) { return <label className="text-xs font-medium">{label}<input type="date" value={value} onChange={event => onChange(event.target.value)} className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm" /></label> }
function formatMetric(metric: SessionStatisticMetric) { return metric.unit === "value" ? fmtCompactVnd(metric.value) : fmtInt(metric.value) }
function Datum({ metric }: { metric: SessionStatisticMetric }) { return <div className="rounded-lg border border-border bg-card p-4"><div className="text-[10px] uppercase tracking-wider text-muted-foreground">{metric.label}</div><div className="mt-1 font-semibold tabular-nums">{formatMetric(metric)}</div></div> }
function MetricGroup({ title, metrics }: { title: string; metrics: SessionStatisticMetric[] }) { return <section className="overflow-hidden rounded-xl border border-border bg-card"><h2 className="border-b border-border px-4 py-3 font-semibold">{title}</h2><div className="divide-y divide-border">{metrics.map(metric => <div key={metric.code} className="flex items-center justify-between gap-4 px-4 py-2 text-sm"><span className="text-muted-foreground">{metric.label}</span><span className="font-medium tabular-nums">{formatMetric(metric)}</span></div>)}</div></section> }
function EmptyState({ text }: { text: string }) { return <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">{text}</div> }
