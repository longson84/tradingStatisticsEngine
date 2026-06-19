import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Sidebar } from "@/components/Sidebar"
import {
  newLowEpisodesApi,
  type DataSource,
  type NewLowSymbolResult,
} from "@/lib/api"
import { fmtDate, fmtInt, fmtPct, fmtPrice } from "@/lib/format"

const DATA_SOURCES: Array<{ label: string; value: DataSource }> = [
  { label: "Yahoo Finance", value: "yfinance" },
  { label: "VN Stock", value: "vnstock" },
  { label: "CSV", value: "csv" },
]

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span className="block text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-1">
      {children}
    </span>
  )
}

function FormSelect<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T
  onChange: (v: T) => void
  options: Array<{ label: string; value: T }>
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value as T)}
      className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground focus:outline-none focus:border-ring"
    >
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

function NumberInput({
  value,
  onChange,
  min = 0,
}: {
  value: number
  onChange: (v: number) => void
  min?: number
}) {
  return (
    <input
      type="number"
      value={value}
      min={min}
      onChange={e => onChange(Number(e.target.value))}
      className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground focus:outline-none focus:border-ring"
    />
  )
}

function parseSymbols(value: string) {
  return value
    .split(/[\s,]+/)
    .map(s => s.trim().toUpperCase())
    .filter(Boolean)
}

export function NewLowComparisonPage() {
  const [symbolsText, setSymbolsText] = useState("BTC-USD, MSFT, MCD, ADBE, DPZ")
  const [dataSource, setDataSource] = useState<DataSource>("yfinance")
  const [lookback, setLookback] = useState(50)
  const [quickRecovery, setQuickRecovery] = useState(2)
  const [runId, setRunId] = useState(0)
  const [params, setParams] = useState<Parameters<typeof newLowEpisodesApi>[0] | null>(null)

  const symbols = useMemo(() => parseSymbols(symbolsText), [symbolsText])

  const { data, isFetching, error } = useQuery({
    queryKey: ["new-low-comparison", params, runId],
    queryFn: () => newLowEpisodesApi(params!),
    enabled: params != null,
    retry: false,
  })

  const controls = (
    <div className="space-y-4">
      <div>
        <Label>Data Source</Label>
        <FormSelect value={dataSource} onChange={setDataSource} options={DATA_SOURCES} />
      </div>

      <div>
        <Label>Symbols</Label>
        <textarea
          value={symbolsText}
          onChange={e => setSymbolsText(e.target.value.toUpperCase())}
          rows={4}
          className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground uppercase resize-none focus:outline-none focus:border-ring"
        />
      </div>

      <div>
        <Label>Lowest Lookback</Label>
        <NumberInput value={lookback} onChange={setLookback} min={2} />
      </div>

      <div>
        <Label>Ignore Recovery ≤</Label>
        <NumberInput value={quickRecovery} onChange={setQuickRecovery} min={0} />
      </div>

      <button
        onClick={() => {
          setParams({
            symbols,
            lookback_sessions: lookback,
            quick_recovery_sessions: quickRecovery,
            data_source: dataSource,
          })
          setRunId(id => id + 1)
        }}
        disabled={isFetching || symbols.length === 0}
        className="w-full py-2.5 rounded-md bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed text-primary-foreground text-sm font-semibold transition-colors tracking-wide"
      >
        {isFetching ? "Analysing..." : "Analyse"}
      </button>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" children={controls} />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="flex items-end justify-between gap-4 pb-4 border-b border-border">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">New-Low Comparison</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Current episode location versus historical {params?.lookback_sessions ?? lookback}-session low episodes.
            </p>
          </div>
          {data?.results[0] && (
            <div className="text-xs text-muted-foreground text-right">
              <div>as of {fmtDate(data.results[0].last_date)}</div>
              <div>{fmtInt(data.results.length)} symbols</div>
            </div>
          )}
        </div>

        {isFetching && <LoadingBar />}

        {error && !isFetching && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-300">
            {(error as Error).message}
          </div>
        )}

        {!data && !isFetching && !error && (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground/50">
            Configure the symbols and run the comparison.
          </div>
        )}

        {data && !isFetching && (
          <div className="mt-5 space-y-5">
            <section>
              <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Further Downside</h2>
              <div className="border border-border rounded-lg overflow-x-auto bg-card">
                <CurrentDownsideTable rows={data.results} />
              </div>
            </section>

            <section className="grid grid-cols-1 xl:grid-cols-2 gap-5">
              <div>
                <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Recovery Duration</h2>
                <div className="border border-border rounded-lg overflow-x-auto bg-card">
                  <SmallStatsTable rows={data.results} type="duration" />
                </div>
              </div>
              <div>
                <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Ignored New Lows
                </h2>
                <div className="border border-border rounded-lg overflow-x-auto bg-card">
                  <SmallStatsTable rows={data.results} type="ignored" />
                </div>
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}

function CurrentDownsideTable({ rows }: { rows: NewLowSymbolResult[] }) {
  return (
    <table className="w-full text-sm min-w-[980px]">
      <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
        <tr>
          <th className="text-left px-3 py-2 font-medium">Symbol</th>
          <th className="text-right px-3 py-2 font-medium">Start</th>
          <th className="text-right px-3 py-2 font-medium">Start Px</th>
          <th className="text-right px-3 py-2 font-medium">Current Px</th>
          <th className="text-right px-3 py-2 font-medium">Current Down</th>
          <th className="text-right px-3 py-2 font-medium">Max Down</th>
          <th className="text-right px-3 py-2 font-medium">Sessions</th>
          <th className="text-right px-3 py-2 font-medium">P75</th>
          <th className="text-right px-3 py-2 font-medium">P90</th>
          <th className="text-right px-3 py-2 font-medium">P95</th>
          <th className="text-right px-3 py-2 font-medium">Worst</th>
          <th className="text-right px-3 py-2 font-medium">Pctl</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rows.map(row => {
          const c = row.current
          return (
            <tr key={row.symbol} className="hover:bg-muted/30">
              <td className="px-3 py-2 font-medium">{row.symbol}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtDate(c?.start_date)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{c ? fmtPrice(c.start_price) : "n/a"}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(row.latest_price)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{c ? fmtPct(c.current_down_pct) : "n/a"}</td>
              <td className="px-3 py-2 text-right tabular-nums">{c ? fmtPct(c.max_down_pct) : "n/a"}</td>
              <td className="px-3 py-2 text-right tabular-nums">{c ? fmtInt(c.sessions_elapsed) : "n/a"}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtPct(row.max_down_percentiles["75"])}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtPct(row.max_down_percentiles["90"])}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtPct(row.max_down_percentiles["95"])}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtPct(row.max_down_percentiles["100"])}</td>
              <td className="px-3 py-2 text-right tabular-nums">{c ? fmtPct(c.max_down_percentile, 1) : "n/a"}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function SmallStatsTable({ rows, type }: { rows: NewLowSymbolResult[]; type: "duration" | "ignored" }) {
  return (
    <table className="w-full text-sm min-w-[620px]">
      <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
        <tr>
          <th className="text-left px-3 py-2 font-medium">Symbol</th>
          <th className="text-right px-3 py-2 font-medium">Current</th>
          <th className="text-right px-3 py-2 font-medium">P75</th>
          <th className="text-right px-3 py-2 font-medium">P90</th>
          <th className="text-right px-3 py-2 font-medium">P95</th>
          <th className="text-right px-3 py-2 font-medium">Worst</th>
          <th className="text-right px-3 py-2 font-medium">Pctl</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rows.map(row => {
          const c = row.current
          const percentiles = type === "duration" ? row.recovery_session_percentiles : row.ignored_new_low_percentiles
          const current = type === "duration" ? c?.sessions_elapsed : c?.ignored_new_lows
          const percentile = type === "duration" ? c?.duration_percentile : c?.ignored_lows_percentile
          return (
            <tr key={row.symbol} className="hover:bg-muted/30">
              <td className="px-3 py-2 font-medium">{row.symbol}</td>
              <td className="px-3 py-2 text-right tabular-nums">{current != null ? fmtInt(current) : "n/a"}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtInt(percentiles["75"])}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtInt(percentiles["90"])}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtInt(percentiles["95"])}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtInt(percentiles["100"])}</td>
              <td className="px-3 py-2 text-right tabular-nums">{percentile != null ? fmtPct(percentile, 1) : "n/a"}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function LoadingBar() {
  return (
    <div className="mt-4 h-0.5 w-full bg-border rounded overflow-hidden relative">
      <div
        className="absolute h-full w-1/3 bg-primary rounded"
        style={{ animation: "progress-slide 1.2s ease-in-out infinite" }}
      />
    </div>
  )
}
