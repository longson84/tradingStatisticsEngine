import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Activity, Search } from "lucide-react"
import { Link } from "react-router"

import { Sidebar } from "@/components/Sidebar"
import { Badge } from "@/components/ui/badge"
import {
  instrumentsApi,
  instrumentTradeStatisticsApi,
  type DailyTradeStatistic,
  type InstrumentCatalogItem,
} from "@/lib/api"
import { fmtCompactVnd, fmtDate, fmtInt, fmtNum, fmtPct, fmtProviderSource } from "@/lib/format"
import { useDebouncedValue } from "@/lib/useDebouncedValue"

type AppliedPeriod = { instrument: InstrumentCatalogItem; start: string; end: string }
type NumericField = {
  [Key in keyof DailyTradeStatistic]: DailyTradeStatistic[Key] extends number ? Key : never
}[keyof DailyTradeStatistic]

const ACTIVITY_COLUMNS: { key: NumericField; label: string; format?: "value" | "average" }[] = [
  { key: "matched_volume", label: "Matched volume" },
  { key: "matched_value", label: "Matched value", format: "value" },
  { key: "deal_volume", label: "Negotiated-deal volume" },
  { key: "deal_value", label: "Negotiated-deal value", format: "value" },
  { key: "total_volume", label: "Total volume" },
  { key: "total_value", label: "Total value", format: "value" },
  { key: "market_cap", label: "Market capitalization", format: "value" },
  { key: "total_shares", label: "Total shares" },
  { key: "total_buy_trade", label: "VCI buy trade count" },
  { key: "total_buy_trade_volume", label: "VCI buy trade volume" },
  { key: "total_sell_trade", label: "VCI sell trade count" },
  { key: "total_sell_trade_volume", label: "VCI sell trade volume" },
  { key: "total_net_trade_volume", label: "VCI net trade volume" },
  { key: "total_buy_unmatched_volume", label: "VCI buy unmatched volume" },
  { key: "total_sell_unmatched_volume", label: "VCI sell unmatched volume" },
  { key: "average_buy_trade_volume", label: "VCI average buy trade volume", format: "average" },
  { key: "average_sell_trade_volume", label: "VCI average sell trade volume", format: "average" },
]

export function TradingActivityPage() {
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<InstrumentCatalogItem | null>(null)
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")
  const [request, setRequest] = useState<AppliedPeriod | null>(null)
  const debounced = useDebouncedValue(search.trim(), 300)
  const instruments = useQuery({
    queryKey: ["trading-activity-instruments", debounced],
    queryFn: () => instrumentsApi({
      search: debounced, capability: "trade_history", has_price_history: false, limit: 20,
    }),
    enabled: selected == null && debounced.length >= 3,
  })
  const activity = useQuery({
    queryKey: ["instrument-trade-statistics", request?.instrument.id, request?.start, request?.end],
    queryFn: () => instrumentTradeStatisticsApi({
      instrument_id: request!.instrument.id, start: request!.start, end: request!.end,
    }),
    enabled: request != null,
    retry: false,
  })
  const rows = activity.data?.rows ?? []
  const latest = rows.at(-1)
  const fetchTimes = [...new Set(rows.map(row => row.fetched_at))]
    .sort((left, right) => new Date(left).getTime() - new Date(right).getTime())
  // These totals and shares only present the stored rows for the applied period.
  const totals = rows.reduce((sum, row) => ({
    volume: sum.volume + row.total_volume,
    value: sum.value + row.total_value,
    matched: sum.matched + row.matched_volume,
    deal: sum.deal + row.deal_volume,
  }), { volume: 0, value: 0, matched: 0, deal: 0 })
  const missing = activity.error?.message.includes("No stored")
  const unsupported = activity.error?.message.includes("does not support trade_history")
  const data = request && !activity.isFetching && !activity.isError ? activity.data : undefined
  const partial = data && (data.first_date !== data.requested_start || data.last_date !== data.requested_end)
  const operationQuery = request ? new URLSearchParams({
    dataset: "trade_history", instrument_id: String(request.instrument.id),
    symbol: request.instrument.symbol, period_start: request.start, period_end: request.end,
  }).toString() : ""
  const refreshLink = <Link className="font-semibold text-primary underline" to={`/data-operations/single?${operationQuery}`}>Fetch this exact period in Data Operations</Link>

  const apply = () => {
    if (!selected || !start || !end || start > end) return
    if (request?.instrument.id === selected.id && request.start === start && request.end === end) {
      void activity.refetch()
    } else {
      setRequest({ instrument: selected, start, end })
    }
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <header className="mb-6 border-b border-border pb-5">
          <div className="flex items-center gap-2"><Activity size={21} className="text-primary" /><h1 className="text-2xl font-bold">Vietnam Trading Activity</h1></div>
          <p className="mt-1 text-sm text-muted-foreground">Stored daily VCI trading activity for one eligible Vietnam equity and one selected period. Apply reads the database; provider fetches require a separate Data Operations submission.</p>
        </header>

        <section className="mb-5 rounded-xl border border-border bg-card p-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(260px,1fr)_180px_180px_auto] lg:items-end">
            <div className="relative">
              <label htmlFor="activity-instrument" className="mb-1 block text-xs font-medium">Instrument</label>
              <Search className="pointer-events-none absolute bottom-2.5 left-3 text-muted-foreground" size={15} />
              <input id="activity-instrument" value={search} onChange={event => { setSearch(event.target.value); setSelected(null); setRequest(null) }} placeholder="Search FPT, VNM, ACB…" className="w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm" />
              {debounced.length >= 3 && !selected && <div className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-md border border-border bg-popover shadow-lg">
                {instruments.isFetching && <p className="p-3 text-xs text-muted-foreground">Searching eligible Instruments…</p>}
                {instruments.error && <p role="alert" className="p-3 text-xs text-destructive">Instrument search failed: {instruments.error.message}</p>}
                {!instruments.isFetching && !instruments.error && instruments.data?.instruments.length === 0 && <p className="p-3 text-xs text-muted-foreground">No eligible Vietnam equities found. Trading activity supports active Company-backed common stocks on HOSE, HNX, and UPCOM with VCI routing.</p>}
                {instruments.data?.instruments.map(item => <button key={item.id} onClick={() => { setSelected(item); setSearch(item.symbol); setRequest(null) }} className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-accent"><span className="font-medium">{item.symbol}</span><span className="text-xs text-muted-foreground">{item.venue_code}</span></button>)}
              </div>}
            </div>
            <DateInput label="Start date" value={start} onChange={value => { setStart(value); setRequest(null) }} />
            <DateInput label="End date" value={end} onChange={value => { setEnd(value); setRequest(null) }} />
            <button disabled={!selected || !start || !end || start > end || activity.isFetching} onClick={apply} className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40">Apply period</button>
          </div>
          {start && end && start > end && <p role="alert" className="mt-3 text-xs text-destructive">Start date must be on or before end date.</p>}
        </section>

        {!request && <EmptyState text="Choose an eligible Instrument and both dates, then Apply to read stored daily activity." />}
        {request && activity.isFetching && <div role="status" className="rounded-lg border border-border p-6 text-sm text-muted-foreground">Loading stored trading activity…</div>}
        {request && !activity.isFetching && activity.error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <h2 className="font-semibold">{missing ? "No stored activity for this period" : unsupported ? "Unsupported Instrument" : "Trading activity request failed"}</h2>
          <p className="mt-1 text-muted-foreground">{activity.error.message}</p>
          {!unsupported && <p className="mt-3">{refreshLink}. Review and submit the prefilled operation to access the provider.</p>}
        </div>}
        {data && <>
          <div className="mb-4 flex flex-wrap items-center gap-2"><h2 className="text-xl font-bold">{data.symbol}</h2><Badge variant="outline">{data.venue_code}</Badge><Badge variant="secondary">Stored daily VCI activity</Badge></div>
          <section className="mb-5 space-y-2 rounded-lg border border-border bg-card p-4 text-sm">
            <p>Requested: {fmtDate(data.requested_start)}–{fmtDate(data.requested_end)}. Stored: {fmtDate(data.first_date)}–{fmtDate(data.last_date)} · {fmtInt(data.row_count)} rows · {data.currency}.</p>
            <p className="text-xs text-muted-foreground">Sources: {[...new Set(rows.map(row => fmtProviderSource(row.source)))].join(", ")}. Schema versions: {[...new Set(rows.map(row => row.schema_version))].join(", ")}. Fetch timestamps and source are shown per row below.</p>
            {fetchTimes.length > 0 && <p className="text-xs text-muted-foreground">Fetched: {new Date(fetchTimes[0]).toLocaleString()}{fetchTimes.length > 1 ? `–${new Date(fetchTimes.at(-1)!).toLocaleString()}` : ""}. Stored boundaries do not establish completeness of sessions inside the range.</p>}
            <p className="text-xs">{refreshLink}. Opening this link only prefills settings.</p>
          </section>
          {partial && <div role="status" className="mb-5 rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm">Partial stored range: stored boundaries differ from the requested dates. Weekends and holidays may account for boundary differences. Only available rows are shown; completeness of sessions inside this range has not been verified.</div>}
          <p className="mb-4 text-xs text-muted-foreground">Buy, sell, net, unmatched, and average trade-size fields are VCI trade classifications.</p>
          {rows.length === 0 ? <EmptyState text="No daily activity rows were returned for this period." /> : <>
            <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <Datum label="Period total value" value={fmtCompactVnd(totals.value)} />
              <Datum label="Period total volume" value={fmtInt(totals.volume)} />
              <Datum label="Matched share of period volume" value={totals.volume > 0 ? fmtPct(totals.matched / totals.volume * 100) : "—"} />
              <Datum label="Negotiated-deal share of period volume" value={totals.volume > 0 ? fmtPct(totals.deal / totals.volume * 100) : "—"} />
              <Datum label={`Latest market capitalization · ${fmtDate(latest?.trading_date)}`} value={latest ? fmtCompactVnd(latest.market_cap) : "—"} />
              <Datum label={`Latest VCI net trade volume · ${fmtDate(latest?.trading_date)}`} value={latest ? fmtInt(latest.total_net_trade_volume) : "—"} />
            </div>
            <ActivityChart rows={rows} kind="stacked" />
            <ActivityChart rows={rows} kind="net" />
            <DailyTable rows={rows} />
          </>}
        </>}
      </main>
    </div>
  )
}

function DateInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="text-xs font-medium">{label}<input required type="date" value={value} onChange={event => onChange(event.target.value)} className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm" /></label>
}

function Datum({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border bg-card p-4"><div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div><div className="mt-1 font-semibold tabular-nums">{value}</div></div>
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">{text}</div>
}

function ActivityChart({ rows, kind }: { rows: DailyTradeStatistic[]; kind: "stacked" | "net" }) {
  // Scale and stack only for display; retain the provider's daily values.
  const stacked = kind === "stacked"
  const values = rows.map(row => stacked ? row.matched_volume + row.deal_volume : row.total_net_trade_volume)
  const high = Math.max(0, ...values) || 1
  const low = Math.min(0, ...values)
  const width = Math.max(720, rows.length * 24 + 90)
  const y = (value: number) => 20 + (high - value) / (high - low) * 220
  const step = (width - 90) / rows.length
  const title = stacked ? "Daily matched and negotiated-deal volume" : "Daily VCI net trade volume"

  return <section className="mb-5 rounded-xl border border-border bg-card p-5">
    <h2 className="font-semibold">{title}</h2>
    <p className="mt-1 text-xs text-muted-foreground">{stacked ? "Blue: matched · Amber: negotiated-deal. Stacked bars show stored volume per session." : "VCI trade classification. Green: positive · Red: negative. The horizontal line marks zero."} Hover a bar for values; the table contains every session.</p>
    <div className="mt-3 overflow-x-auto">
      <svg role="img" aria-label={title} width={width} height={285} className="text-muted-foreground">
        <title>{title}</title>
        {[high, ...(low < 0 ? [0, low] : [0])].map(value => <g key={value}>
          <line x1={75} x2={width - 15} y1={y(value)} y2={y(value)} stroke="currentColor" opacity={0.25} />
          <text x={68} y={y(value) + 4} textAnchor="end" fill="currentColor" fontSize={10}>{fmtInt(value)}</text>
        </g>)}
        {rows.map((row, index) => {
          const x = 78 + index * step
          const barWidth = Math.max(1, step - 5)
          return <g key={row.trading_date}>
            <title>{`${row.trading_date}: ${stacked ? `matched ${fmtInt(row.matched_volume)}, negotiated-deal ${fmtInt(row.deal_volume)}` : `VCI net trade volume ${fmtInt(row.total_net_trade_volume)}`}`}</title>
            {stacked ? <>
              <rect x={x} y={y(row.matched_volume)} width={barWidth} height={y(0) - y(row.matched_volume)} fill="#2563eb" />
              <rect x={x} y={y(row.matched_volume + row.deal_volume)} width={barWidth} height={y(row.matched_volume) - y(row.matched_volume + row.deal_volume)} fill="#d97706" />
            </> : <rect x={x} y={y(Math.max(0, row.total_net_trade_volume))} width={barWidth} height={Math.max(1, Math.abs(y(row.total_net_trade_volume) - y(0)))} fill={row.total_net_trade_volume >= 0 ? "#16a34a" : "#dc2626"} />}
            {index % Math.max(1, Math.ceil(rows.length / 10)) === 0 && <text x={x} y={265} fontSize={10} fill="currentColor">{fmtDate(row.trading_date)}</text>}
          </g>
        })}
      </svg>
    </div>
  </section>
}

function DailyTable({ rows }: { rows: DailyTradeStatistic[] }) {
  return <section className="overflow-hidden rounded-xl border border-border bg-card">
    <h2 className="border-b border-border px-4 py-3 font-semibold">Stored daily activity and provenance</h2>
    <div className="max-h-[640px] overflow-auto">
      <table className="w-full whitespace-nowrap text-right text-xs">
        <thead className="sticky top-0 bg-muted text-muted-foreground"><tr>
          <th scope="col" className="px-4 py-3 text-left">Session</th>
          {ACTIVITY_COLUMNS.map(column => <th scope="col" key={column.key} className="px-4 py-3">{column.label}</th>)}
          <th scope="col" className="px-4 py-3">Source</th><th scope="col" className="px-4 py-3">Schema</th><th scope="col" className="px-4 py-3">Fetched at</th>
        </tr></thead>
        <tbody>{[...rows].reverse().map(row => <tr key={row.trading_date} className="border-t border-border">
          <th scope="row" className="px-4 py-3 text-left font-medium">{fmtDate(row.trading_date)}</th>
          {ACTIVITY_COLUMNS.map(column => <td key={column.key} className="px-4 py-3 tabular-nums">{column.format === "value" ? fmtCompactVnd(row[column.key]) : column.format === "average" ? fmtNum(row[column.key]) : fmtInt(row[column.key])}</td>)}
          <td className="px-4 py-3">{fmtProviderSource(row.source)}</td><td className="px-4 py-3">v{row.schema_version}</td><td className="px-4 py-3"><time dateTime={row.fetched_at}>{new Date(row.fetched_at).toLocaleString()}</time></td>
        </tr>)}</tbody>
      </table>
    </div>
  </section>
}
