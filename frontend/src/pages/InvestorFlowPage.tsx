import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Activity, Search } from "lucide-react"
import { Link } from "react-router"

import { Sidebar } from "@/components/Sidebar"
import { InvestorFlowChart } from "@/components/market/InvestorFlowChart"
import { Badge } from "@/components/ui/badge"
import {
  instrumentMarketFlowsApi,
  instrumentsApi,
  type InstrumentCatalogItem,
} from "@/lib/api"
import { fmtCompactVnd, fmtDate, fmtInt, fmtProviderSource } from "@/lib/format"
import { useDebouncedValue } from "@/lib/useDebouncedValue"


export function InvestorFlowPage() {
  const [participant, setParticipant] = useState<"foreign" | "proprietary">("foreign")
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<InstrumentCatalogItem | null>(null)
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")
  const [range, setRange] = useState({ start: "", end: "" })
  const debounced = useDebouncedValue(search.trim(), 300)
  const instruments = useQuery({
    queryKey: ["participant-flow-instruments", participant, debounced],
    queryFn: () => instrumentsApi({
      search: debounced,
      capability: participant === "foreign" ? "foreign_flow" : "proprietary_flow",
      has_price_history: false,
      limit: 20,
    }),
    enabled: debounced.length >= 3,
  })
  const flow = useQuery({
    queryKey: ["instrument-participant-flow", selected?.id, participant, range.start, range.end],
    queryFn: () => instrumentMarketFlowsApi({
      instrument_id: selected!.id,
      participant_type: participant,
      start: range.start || undefined,
      end: range.end || undefined,
    }),
    enabled: selected != null,
    retry: false,
  })
  const observations = flow.data?.observations ?? []
  const latest = observations.at(-1)
  const totals = observations.reduce(
    (sum, row) => ({
      buy: sum.buy + row.buy_value,
      sell: sum.sell + row.sell_value,
      net: sum.net + row.net_value,
    }),
    { buy: 0, sell: 0, net: 0 },
  )
  const missingStoredData = flow.error?.message.includes("No stored")

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <header className="mb-6 border-b border-border pb-5">
          <div className="flex items-center gap-2">
            <Activity size={21} className="text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Vietnam Investor Flow</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Stored daily foreign-investor and proprietary-trading activity for eligible Vietnam equities.
          </p>
        </header>

        <section className="mb-5 rounded-xl border border-border bg-card p-5">
          <div className="mb-4 flex gap-1 border-b border-border">
            {([
              ["foreign", "Foreign investors"],
              ["proprietary", "Proprietary trading"],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setParticipant(value)}
                className={`border-b-2 px-4 py-2 text-sm font-medium ${
                  participant === value
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(260px,1fr)_180px_180px_auto] lg:items-end">
            <div className="relative">
              <label className="mb-1 block text-xs font-medium">Instrument</label>
              <Search className="pointer-events-none absolute bottom-2.5 left-3 text-muted-foreground" size={15} />
              <input
                value={search}
                onChange={event => { setSearch(event.target.value); setSelected(null) }}
                placeholder="Search FPT, VNM, ACB…"
                className="w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm"
              />
              {debounced.length >= 3 && selected == null && (
                <div className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-md border border-border bg-popover shadow-lg">
                  {instruments.isFetching && <div className="p-3 text-xs text-muted-foreground">Searching…</div>}
                  {!instruments.isFetching && instruments.data?.instruments.length === 0 && (
                    <div className="p-3 text-xs text-muted-foreground">No eligible Vietnam equities found.</div>
                  )}
                  {instruments.data?.instruments.map(item => (
                    <button
                      key={item.id}
                      onClick={() => { setSelected(item); setSearch(item.symbol) }}
                      className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                    >
                      <span className="font-medium">{item.symbol}</span>
                      <span className="text-xs text-muted-foreground">{item.venue_code}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <DateInput label="Start date" value={start} onChange={setStart} />
            <DateInput label="End date" value={end} onChange={setEnd} />
            <button
              disabled={!selected || flow.isFetching}
              onClick={() => setRange({ start, end })}
              className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40"
            >
              Apply range
            </button>
          </div>
        </section>

        {!selected && (
          <EmptyState text={`Choose a Vietnam-listed equity to inspect its stored ${participant === "foreign" ? "foreign-investor" : "proprietary-trading"} flow.`} />
        )}
        {flow.isFetching && <div className="h-1 animate-pulse rounded bg-primary/50" />}
        {flow.error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <div>{flow.error.message}</div>
            {missingStoredData && (
              <Link className="mt-2 inline-block font-semibold underline" to="/data-operations/single">
                Open Data Operations and select this exact Instrument with {participant === "foreign" ? "Foreign flow" : "Proprietary flow"}.
              </Link>
            )}
          </div>
        )}
        {flow.data?.is_stale && (
          <div className="mb-5 rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-700 dark:text-amber-300">
            Stored data ends {flow.data.last_date}; expected {flow.data.expected_last_session}. Refresh this exact instrument in Data Operations.
          </div>
        )}
        {flow.data && (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-bold">{flow.data.symbol}</h2>
              <Badge variant="outline">
                {participant === "foreign" ? "Foreign investors" : "Proprietary trading"}
              </Badge>
              <Badge variant="outline">{flow.data.venue_code}</Badge>
              <Badge variant="secondary">{fmtProviderSource(flow.data.source)}</Badge>
              <span className="text-xs text-muted-foreground">
                {fmtDate(flow.data.first_date)}–{fmtDate(flow.data.last_date)} · {flow.data.row_count.toLocaleString()} stored rows · fetched {new Date(flow.data.fetched_at).toLocaleString()}
              </span>
            </div>
            {observations.length === 0 ? (
              <EmptyState text="No observations fall inside the selected date range." />
            ) : (
              <>
                <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <Datum label="Latest net value" value={fmtCompactVnd(latest?.net_value ?? 0)} />
                  <Datum label="Latest net volume" value={fmtInt(latest?.net_volume ?? 0)} />
                  <Datum label="Period buy" value={fmtCompactVnd(totals.buy)} />
                  <Datum label="Period sell" value={fmtCompactVnd(totals.sell)} />
                  <Datum label="Period net" value={fmtCompactVnd(totals.net)} />
                </div>
                <section className="rounded-xl border border-border bg-card p-5">
                  <InvestorFlowChart observations={observations} />
                </section>
                <DailyTable observations={[...observations].reverse()} />
              </>
            )}
          </>
        )}
      </main>
    </div>
  )
}

function DateInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="text-xs font-medium">{label}<input type="date" value={value} onChange={event => onChange(event.target.value)} className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm" /></label>
}

function Datum({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border bg-card p-4"><div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div><div className="mt-1 font-semibold tabular-nums">{value}</div></div>
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">{text}</div>
}

function DailyTable({ observations }: { observations: Awaited<ReturnType<typeof instrumentMarketFlowsApi>>["observations"] }) {
  return <section className="mt-5 overflow-hidden rounded-xl border border-border bg-card"><div className="border-b border-border px-4 py-3 font-semibold">Daily observations</div><div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-muted/40 text-left text-xs text-muted-foreground"><tr><th className="px-4 py-3">Date</th><th>Buy value</th><th>Sell value</th><th>Net value</th><th>Net volume</th></tr></thead><tbody>{observations.map(row => <tr key={row.date} className="border-t border-border"><td className="px-4 py-3">{fmtDate(row.date)}</td><td>{fmtCompactVnd(row.buy_value)}</td><td>{fmtCompactVnd(row.sell_value)}</td><td>{fmtCompactVnd(row.net_value)}</td><td>{fmtInt(row.net_volume)}</td></tr>)}</tbody></table></div></section>
}
