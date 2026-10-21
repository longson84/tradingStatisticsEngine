import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { BarChart3 } from "lucide-react"
import { Link } from "react-router"

import { Sidebar } from "@/components/Sidebar"
import { VietnamInstrumentSelector } from "@/components/forms/VietnamInstrumentSelector"
import { Badge } from "@/components/ui/badge"
import {
  instrumentSessionStatisticsApi,
  instrumentsApi,
  type InstrumentCatalogItem,
  type SessionStatisticMetric,
} from "@/lib/api"
import { fmtCompactVnd, fmtDate, fmtDateTime, fmtInt, fmtProviderSource } from "@/lib/format"
import { useDebouncedValue } from "@/lib/useDebouncedValue"

const GROUPS = [
  ["market_activity", "Market activity"],
  ["foreign_activity", "Foreign activity"],
  ["trade_direction", "Trade direction"],
  ["order_imbalance", "Order imbalance and trade size"],
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
      scope: "equity",
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
  const totalVolume = metrics.get("total_volume")?.value ?? 0
  const summary = stats.data ? [
    ["Total volume", fmtInt(totalVolume)],
    ["Total value", fmtCompactVnd(metrics.get("total_value")?.value ?? 0)],
    ["Matched share", formatPercent(metrics.get("total_match_volume")?.value, totalVolume)],
    ["Deal share", formatPercent(metrics.get("total_deal_volume")?.value, totalVolume)],
    ["Foreign net value", fmtCompactVnd(metrics.get("fr_net_value_total")?.value ?? 0)],
    ["Net trade volume", fmtInt(metrics.get("total_net_trade_volume")?.value ?? 0)],
    ["Average buy size", fmtInt(metrics.get("average_buy_volume_per_trade")?.value ?? 0)],
    ["Average sell size", fmtInt(metrics.get("average_sell_volume_per_trade")?.value ?? 0)],
  ] as const : []
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
          <VietnamInstrumentSelector
            search={search}
            instruments={instruments.data?.instruments ?? []}
            selectedInstrument={selected}
            total={instruments.data?.total}
            isPending={debounced.length >= 3 && instruments.isFetching}
            errorMessage={instruments.error?.message}
            emptyMessage="No eligible Vietnam equity matches this search."
            onSearchChange={value => {
              setSearch(value)
              setRequest(null)
            }}
            onInstrumentChange={instrument => {
              setSelected(instrument)
              if (instrument) setSearch(instrument.symbol)
              setRequest(null)
            }}
            onSubmit={() => {
              if (selected && start && end && start <= end) {
                setRequest({ id: selected.id, start, end })
              }
            }}
          />
          <DateInput label="Start date" value={start} onChange={value => { setStart(value); setRequest(null) }} />
          <DateInput label="End date" value={end} onChange={value => { setEnd(value); setRequest(null) }} />
          <button disabled={!selected || !start || !end || start > end || stats.isFetching} onClick={() => setRequest({ id: selected!.id, start, end })} className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40">Apply period</button>
        </div>
      </section>
      {!request && <EmptyState text="Choose an eligible Vietnam equity and one period." />}
      {stats.isFetching && <div className="h-1 animate-pulse rounded bg-primary/50" />}
      {stats.error && <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"><div>{stats.error.message}</div>{missing && <Link className="mt-2 inline-block font-semibold underline" to={`/data-operations/single?${operationQuery}`}>Fetch this exact period in Data Operations.</Link>}</div>}
      {stats.data && <>
        <div className="mb-4 flex flex-wrap items-center gap-2"><h2 className="text-xl font-bold">{stats.data.symbol}</h2><Badge variant="outline">{stats.data.venue_code}</Badge><Badge variant="secondary">{fmtProviderSource(stats.data.source)}</Badge><span className="text-xs text-muted-foreground">{fmtDate(stats.data.period_start)}–{fmtDate(stats.data.period_end)} · schema v{stats.data.schema_version} · fetched {fmtDateTime(stats.data.fetched_at)}</span></div>
        <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{summary.map(([label, value]) => <Datum key={label} label={label} value={value} />)}</div>
        <div className="grid gap-5 xl:grid-cols-2">{GROUPS.map(([group, title]) => <MetricGroup key={group} title={title} metrics={stats.data.metrics.filter(metric => metric.group === group)} />)}</div>
      </>}
    </main>
  </div>
}

function DateInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) { return <label className="text-xs font-medium">{label}<input type="date" value={value} onChange={event => onChange(event.target.value)} className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm" /></label> }
function formatMetric(metric: SessionStatisticMetric) { return metric.unit === "value" ? fmtCompactVnd(metric.value) : fmtInt(metric.value) }
function formatPercent(value: number | undefined, total: number) { return total > 0 && value != null ? `${((value / total) * 100).toFixed(1)}%` : "—" }
function Datum({ label, value }: { label: string; value: string }) { return <div className="rounded-lg border border-border bg-card p-4"><div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div><div className="mt-1 font-semibold tabular-nums">{value}</div></div> }
function MetricGroup({ title, metrics }: { title: string; metrics: SessionStatisticMetric[] }) { return <section className="overflow-hidden rounded-xl border border-border bg-card"><h2 className="border-b border-border px-4 py-3 font-semibold">{title}</h2><div className="divide-y divide-border">{metrics.map(metric => <div key={metric.code} className="flex items-center justify-between gap-4 px-4 py-2 text-sm"><span className="text-muted-foreground">{metric.label}</span><span className="font-medium tabular-nums">{formatMetric(metric)}</span></div>)}</div></section> }
function EmptyState({ text }: { text: string }) { return <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">{text}</div> }
