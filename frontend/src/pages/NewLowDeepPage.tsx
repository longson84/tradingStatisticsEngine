import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  LineStyle,
} from "lightweight-charts"
import { Sidebar } from "@/components/Sidebar"
import {
  newLowEpisodesApi,
  type DataSource,
  type NewLowCurrentEpisode,
  type NewLowEpisode,
  type NewLowSymbolResult,
  type NewLowTimeSeriesPoint,
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

export function NewLowDeepPage() {
  const [symbol, setSymbol] = useState("MSFT")
  const [dataSource, setDataSource] = useState<DataSource>("yfinance")
  const [lookback, setLookback] = useState(50)
  const [quickRecovery, setQuickRecovery] = useState(2)
  const [runId, setRunId] = useState(0)
  const [params, setParams] = useState<Parameters<typeof newLowEpisodesApi>[0] | null>(null)

  const { data, isFetching, error } = useQuery({
    queryKey: ["new-low-deep", params, runId],
    queryFn: () => newLowEpisodesApi(params!),
    enabled: params != null,
    retry: false,
  })

  const result = data?.results[0]

  const controls = (
    <div className="space-y-4">
      <div>
        <Label>Data Source</Label>
        <FormSelect value={dataSource} onChange={setDataSource} options={DATA_SOURCES} />
      </div>

      <div>
        <Label>Symbol</Label>
        <input
          value={symbol}
          onChange={e => setSymbol(e.target.value.toUpperCase())}
          className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground uppercase focus:outline-none focus:border-ring"
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
            symbols: [symbol],
            lookback_sessions: lookback,
            quick_recovery_sessions: quickRecovery,
            data_source: dataSource,
          })
          setRunId(id => id + 1)
        }}
        disabled={isFetching || !symbol.trim()}
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
            <h1 className="text-2xl font-bold tracking-tight">New-Low Deep Analysis</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Single-symbol episode chart, forward outcomes, and historical log.
            </p>
          </div>
          {result && (
            <div className="text-xs text-muted-foreground text-right">
              <div>{result.symbol}</div>
              <div>{fmtDate(result.first_date)} - {fmtDate(result.last_date)}</div>
            </div>
          )}
        </div>

        {isFetching && <LoadingBar />}

        {error && !isFetching && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-300">
            {(error as Error).message}
          </div>
        )}

        {!result && !isFetching && !error && (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground/50">
            Configure a symbol and run the deep analysis.
          </div>
        )}

        {result && !isFetching && (
          <div className="mt-5 space-y-6">
            <CurrentStrip result={result} />
            <NewLowPriceChart result={result} />
            <EpisodeDistributionCharts result={result} />

            <section className="space-y-5">
              <div>
                <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Forward Returns</h2>
                <div className="border border-border rounded-lg overflow-hidden bg-card">
                  <ForwardStatsTable result={result} />
                </div>
              </div>
              <div>
                <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Episode Distribution</h2>
                <div className="border border-border rounded-lg overflow-hidden bg-card">
                  <DistributionTable result={result} />
                </div>
              </div>
            </section>

            <section>
              <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Episode History</h2>
              <div className="border border-border rounded-lg overflow-x-auto bg-card">
                <EpisodeTable episodes={result.episodes} current={result.current} />
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}

function CurrentStrip({ result }: { result: NewLowSymbolResult }) {
  const c = result.current
  const episodeCells = [
    ["State", c ? "Active" : "Inactive"],
    ["Start", fmtDate(c?.start_date)],
    ["Start Price", c ? fmtPrice(c.start_price) : "n/a"],
    ["Current Price", fmtPrice(result.latest_price)],
    ["Current Down", c ? fmtPct(c.current_down_pct) : "n/a"],
    ["Max Down", c ? fmtPct(c.max_down_pct) : "n/a"],
    ["Sessions", c ? fmtInt(c.sessions_elapsed) : "n/a"],
    ["Need Recover", c ? fmtPct(c.recovery_needed_pct) : "n/a"],
  ]
  const countCells = [
    ["Episodes", fmtInt(result.kept_episodes)],
    ["Raw Lows", fmtInt(result.raw_new_low_bars)],
    ["Ignored Lows", fmtInt(result.total_ignored_new_lows)],
    ["Quick Ignored", fmtInt(result.quick_ignored_episodes)],
  ]
  const worstCases = c
    ? [...result.episodes]
        .sort((a, b) => b.max_down_pct - a.max_down_pct)
        .slice(0, 10)
        .map(e => {
          const isActive = !e.recovered && e.start_date === c.start_date
          const shouldProject = e.recovered && e.max_down_pct > c.max_down_pct
          const projectedPrice = shouldProject
            ? c.start_price * (1 - e.max_down_pct / 100)
            : null
          return {
            episode: e,
            isActive,
            projectedPrice,
            downFromHere: projectedPrice != null
              ? ((c.current_price - projectedPrice) / c.current_price) * 100
              : null,
          }
        })
    : []

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-px border border-border rounded-lg overflow-hidden bg-border">
        {episodeCells.map(([label, value]) => (
          <div key={label} className="bg-card px-3 py-3 min-h-16">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className="mt-1 text-sm font-semibold tabular-nums">{value}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px border border-border rounded-lg overflow-hidden bg-border max-w-3xl">
        {countCells.map(([label, value]) => (
          <div key={label} className="bg-card px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className="mt-1 text-sm font-semibold tabular-nums">{value}</div>
          </div>
        ))}
      </div>
      {c && (
        <div className="border border-red-500/30 rounded-lg overflow-hidden bg-card max-w-6xl">
          <div className="px-3 py-2 border-b border-red-500/20 bg-red-500/8">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Top 10 Worst Episodes</div>
          </div>
          {worstCases.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="bg-red-500/8 text-[10px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Case</th>
                  <th className="text-right px-3 py-2 font-medium">Started</th>
                  <th className="text-right px-3 py-2 font-medium">Recovered</th>
                  <th className="text-right px-3 py-2 font-medium">Sessions</th>
                  <th className="text-right px-3 py-2 font-medium">Max Down</th>
                  <th className="text-right px-3 py-2 font-medium">From</th>
                  <th className="text-right px-3 py-2 font-medium">To</th>
                  <th className="text-right px-3 py-2 font-medium">This-Time Price</th>
                  <th className="text-right px-3 py-2 font-medium">Additional Down</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {worstCases.map((row, i) => (
                  <tr
                    key={`${row.episode.start_date}-${row.episode.max_down_pct}`}
                    className={row.isActive ? "bg-blue-500/12 hover:bg-blue-500/18" : "hover:bg-red-500/5"}
                  >
                    <td className="px-3 py-2 font-medium">
                      #{i + 1}
                      {row.isActive && (
                        <span className="ml-2 rounded bg-blue-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-blue-700 dark:text-blue-300">
                          active
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.episode.start_date)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.isActive ? "active" : fmtDate(row.episode.recovery_date)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {row.episode.recovery_sessions != null
                        ? fmtInt(row.episode.recovery_sessions)
                        : row.isActive
                          ? `${fmtInt(c.sessions_elapsed)} (active)`
                          : "n/a"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-red-700 dark:text-red-300">{fmtPct(row.episode.max_down_pct)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(row.episode.start_price)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(row.episode.low_price)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-red-700 dark:text-red-300">
                      {row.projectedPrice != null ? fmtPrice(row.projectedPrice) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-red-700 dark:text-red-300">
                      {row.downFromHere != null ? fmtPct(row.downFromHere) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="px-3 py-3 text-sm text-muted-foreground">
              Current active episode is already at or beyond every completed historical max-down case.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function NewLowPriceChart({ result }: { result: NewLowSymbolResult }) {
  const ref = useRef<HTMLDivElement>(null)

  const currentNewLowDates = useMemo(() => {
    const c = result.current
    if (!c) return new Set<string>()
    return new Set(
      result.time_series
        .filter(p => p.is_new_low && p.date >= c.start_date && p.date <= c.current_date)
        .map(p => p.date)
    )
  }, [result])

  useEffect(() => {
    if (!ref.current || result.time_series.length < 2) return

    const isDark = document.documentElement.classList.contains("dark")
    const chartBackground = isDark ? "#262626" : "#ffffff"
    const gridColor = isDark ? "#3f3f46" : "#e5e7eb"
    const textColor = isDark ? "#a1a1aa" : "#6b7280"
    const borderColor = isDark ? "#52525b" : "#d4d4d8"

    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 380,
      layout: {
        background: { type: ColorType.Solid, color: chartBackground },
        textColor,
        fontFamily: "inherit",
      },
      grid: {
        vertLines: { color: gridColor },
        horzLines: { color: gridColor },
      },
      crosshair: {
        vertLine: { color: textColor },
        horzLine: { color: textColor },
      },
      rightPriceScale: { borderColor },
      timeScale: { borderColor },
    })

    const priceSeries = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 2,
      priceLineVisible: false,
    })
    priceSeries.setData(result.time_series.map(p => ({ time: p.date as any, value: p.close })))

    const c = result.current
    if (c) {
      chart.addSeries(LineSeries, {
        color: "rgba(34,197,94,0.75)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: true,
        title: "Recovery",
      }).setData([
        { time: c.start_date as any, value: c.recovery_level },
        { time: c.current_date as any, value: c.recovery_level },
      ])

      createSeriesMarkers(priceSeries, [
        {
          time: c.start_date as any,
          position: "aboveBar" as const,
          color: "#f97316",
          shape: "arrowDown" as const,
          text: "Start",
        },
        {
          time: c.low_date as any,
          position: "belowBar" as const,
          color: "#dc2626",
          shape: "arrowUp" as const,
          text: "Low",
        },
        ...result.time_series
          .filter(p => currentNewLowDates.has(p.date) && p.date !== c.start_date)
          .map(p => ({
            time: p.date as any,
            position: "belowBar" as const,
            color: "rgba(220,38,38,0.65)",
            shape: "circle" as const,
            size: 1,
          })),
      ].sort((a, b) => (a.time < b.time ? -1 : 1)))
    } else {
      createSeriesMarkers(priceSeries, result.episodes.slice(-20).map(e => ({
        time: e.start_date as any,
        position: "belowBar" as const,
        color: "#f97316",
        shape: "circle" as const,
        size: 1,
      })))
    }

    chart.timeScale().fitContent()

    const resizeObserver = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width
      if (width && width > 0) {
        chart.applyOptions({ width })
        chart.timeScale().fitContent()
      }
    })
    resizeObserver.observe(ref.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
    }
  }, [currentNewLowDates, result])

  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Price Episode</h2>
      <div className="border border-border rounded-lg bg-card overflow-hidden">
        <div className="px-4 py-2 border-b border-border text-[10px] text-muted-foreground flex gap-4">
          <span>Price</span>
          <span>Recovery line</span>
          <span>Ignored new lows</span>
        </div>
        <div ref={ref} className="h-[380px] bg-card" />
      </div>
    </section>
  )
}

function ForwardStatsTable({ result }: { result: NewLowSymbolResult }) {
  return (
    <table className="w-full text-sm">
      <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
        <tr>
          <th className="text-right px-3 py-2 font-medium">Horizon</th>
          <th className="text-right px-3 py-2 font-medium">N</th>
          <th className="text-right px-3 py-2 font-medium">Ret P5</th>
          <th className="text-right px-3 py-2 font-medium">Ret P10</th>
          <th className="text-right px-3 py-2 font-medium">Ret P15</th>
          <th className="text-right px-3 py-2 font-medium">Ret P20</th>
          <th className="text-right px-3 py-2 font-medium">Ret P25</th>
          <th className="text-right px-3 py-2 font-medium">Ret P50</th>
          <th className="text-right px-3 py-2 font-medium">Ret P75</th>
          <th className="text-right px-3 py-2 font-medium">Ret P80</th>
          <th className="text-right px-3 py-2 font-medium">Ret P90</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {result.forward_stats.map(row => (
          <tr key={row.horizon} className="hover:bg-muted/30">
            <td className="px-3 py-2 text-right tabular-nums">{fmtInt(row.horizon)}</td>
            <td className="px-3 py-2 text-right tabular-nums">{fmtInt(row.count)}</td>
            <ReturnCell value={row.return_percentiles["5"]} />
            <ReturnCell value={row.return_percentiles["10"]} />
            <ReturnCell value={row.return_percentiles["15"]} />
            <ReturnCell value={row.return_percentiles["20"]} />
            <ReturnCell value={row.return_percentiles["25"]} />
            <ReturnCell value={row.return_percentiles["50"]} />
            <ReturnCell value={row.return_percentiles["75"]} />
            <ReturnCell value={row.return_percentiles["80"]} />
            <ReturnCell value={row.return_percentiles["90"]} />
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ReturnCell({ value }: { value: number }) {
  return (
    <td className="px-3 py-2 text-right tabular-nums">
      <span
        className={[
          "inline-block min-w-20 rounded px-2 py-1",
          value < 0 ? "bg-rose-500/14 text-rose-700 dark:text-rose-300" : "",
          value > 0 ? "bg-emerald-500/14 text-emerald-700 dark:text-emerald-300" : "",
          value === 0 ? "bg-muted/30 text-muted-foreground" : "",
        ].join(" ")}
      >
        {fmtPct(value)}
      </span>
    </td>
  )
}

function DistributionTable({ result }: { result: NewLowSymbolResult }) {
  const c = result.current
  return (
    <table className="w-full text-sm min-w-[620px]">
      <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
        <tr>
          <th className="text-left px-3 py-2 font-medium">Metric</th>
          <th className="text-right px-3 py-2 font-medium">Current</th>
          <th className="text-right px-3 py-2 font-medium">P50</th>
          <th className="text-right px-3 py-2 font-medium">P75</th>
          <th className="text-right px-3 py-2 font-medium">P90</th>
          <th className="text-right px-3 py-2 font-medium">P95</th>
          <th className="text-right px-3 py-2 font-medium">Worst</th>
          <th className="text-right px-3 py-2 font-medium">Pctl</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        <MetricRow
          label="Max Down"
          current={c?.max_down_pct}
          currentSecondary={c?.current_down_pct}
          p={result.max_down_percentiles}
          percentile={c?.max_down_percentile}
          percent
        />
        <MetricRow
          label="Recovery Sessions"
          current={c?.sessions_elapsed}
          p={result.recovery_session_percentiles}
          percentile={c?.duration_percentile}
        />
        <MetricRow
          label="Ignored New Lows"
          current={c?.ignored_new_lows}
          p={result.ignored_new_low_percentiles}
          percentile={c?.ignored_lows_percentile}
        />
      </tbody>
    </table>
  )
}

function EpisodeDistributionCharts({ result }: { result: NewLowSymbolResult }) {
  const c = result.current

  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Percentile Position</h2>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <PercentileCard
          title="Max Down"
          current={c?.max_down_pct}
          percentile={c?.max_down_percentile}
          thresholds={result.max_down_percentiles}
          format={fmtPct}
        />
        <PercentileCard
          title="Recovery Sessions"
          current={c?.sessions_elapsed}
          percentile={c?.duration_percentile}
          thresholds={result.recovery_session_percentiles}
          format={fmtInt}
        />
        <PercentileCard
          title="Ignored New Lows"
          current={c?.ignored_new_lows}
          percentile={c?.ignored_lows_percentile}
          thresholds={result.ignored_new_low_percentiles}
          format={fmtInt}
        />
      </div>
    </section>
  )
}

function PercentileCard({
  title,
  current,
  percentile,
  thresholds,
  format,
}: {
  title: string
  current: number | undefined
  percentile: number | undefined
  thresholds: Record<string, number>
  format: (n: number) => string
}) {
  const markerLeft = percentile == null ? null : Math.max(0, Math.min(100, percentile))
  const p50 = thresholds["50"]
  const p75 = thresholds["75"]
  const p90 = thresholds["90"]
  const p95 = thresholds["95"]
  const worst = thresholds["100"]

  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">{title}</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wide">current versus historical thresholds</div>
        </div>
        <div className="text-right">
          <div className="text-sm font-semibold tabular-nums">{current != null ? format(current) : "n/a"}</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wide">{percentile != null ? `${fmtPct(percentile, 1)} pct` : "inactive"}</div>
        </div>
      </div>

      <div className="px-4 pt-5 pb-4">
        <div className="relative h-20">
          <div className="absolute inset-x-0 top-7 h-5 rounded overflow-hidden border border-border flex">
            <div className="h-full bg-emerald-500/35" style={{ width: "75%" }} />
            <div className="h-full bg-amber-500/45" style={{ width: "15%" }} />
            <div className="h-full bg-orange-500/55" style={{ width: "5%" }} />
            <div className="h-full bg-red-500/60" style={{ width: "5%" }} />
          </div>
          {markerLeft != null && (
            <div
              className="absolute top-0 bottom-4 w-0.5 bg-blue-500 shadow-[0_0_0_2px_rgba(59,130,246,0.18)]"
              style={{ left: `${markerLeft}%` }}
            >
              <div className="absolute -top-1 left-1/2 -translate-x-1/2 text-[9px] font-semibold text-blue-500 whitespace-nowrap rounded bg-card px-1">
                current
              </div>
            </div>
          )}
        </div>

        <div className="mt-2 grid grid-cols-5 gap-2 text-[10px] text-muted-foreground tabular-nums">
          <div className="rounded border border-border/70 bg-muted/20 px-2 py-1">
            <div className="uppercase tracking-wide">P50</div>
            <div className="text-foreground">{format(p50)}</div>
          </div>
          <div className="rounded border border-border/70 bg-muted/20 px-2 py-1">
            <div className="uppercase tracking-wide">P75</div>
            <div className="text-foreground">{format(p75)}</div>
          </div>
          <div className="rounded border border-border/70 bg-muted/20 px-2 py-1">
            <div className="uppercase tracking-wide">P90</div>
            <div className="text-foreground">{format(p90)}</div>
          </div>
          <div className="rounded border border-border/70 bg-muted/20 px-2 py-1">
            <div className="uppercase tracking-wide">P95</div>
            <div className="text-foreground">{format(p95)}</div>
          </div>
          <div className="rounded border border-border/70 bg-muted/20 px-2 py-1">
            <div className="uppercase tracking-wide">Worst</div>
            <div className="text-foreground">{format(worst)}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricRow({
  label,
  current,
  currentSecondary,
  p,
  percentile,
  percent = false,
}: {
  label: string
  current: number | undefined
  currentSecondary?: number
  p: Record<string, number>
  percentile: number | undefined
  percent?: boolean
}) {
  const fmt = percent ? fmtPct : fmtInt
  return (
    <tr className="hover:bg-muted/30">
      <td className="px-3 py-2 font-medium">{label}</td>
      <td className="px-3 py-2 text-right tabular-nums">
        {current != null
          ? currentSecondary != null
            ? `${fmt(current)} (${fmt(currentSecondary)})`
            : fmt(current)
          : "n/a"}
      </td>
      <td className="px-3 py-2 text-right tabular-nums">{fmt(p["50"])}</td>
      <td className="px-3 py-2 text-right tabular-nums">{fmt(p["75"])}</td>
      <td className="px-3 py-2 text-right tabular-nums">{fmt(p["90"])}</td>
      <td className="px-3 py-2 text-right tabular-nums">{fmt(p["95"])}</td>
      <td className="px-3 py-2 text-right tabular-nums">{fmt(p["100"])}</td>
      <td className="px-3 py-2 text-right tabular-nums">{percentile != null ? fmtPct(percentile, 1) : "n/a"}</td>
    </tr>
  )
}

function EpisodeTable({
  episodes,
  current,
}: {
  episodes: NewLowEpisode[]
  current: NewLowCurrentEpisode | null
}) {
  const displayEpisodes = [...episodes].sort((a, b) => b.start_date.localeCompare(a.start_date))
  const years = Array.from(new Set(displayEpisodes.map(e => e.start_date.slice(0, 4))))
  const yearTone = new Map(years.map((year, i) => [year, i % 6]))

  return (
    <table className="w-full text-sm min-w-[900px]">
      <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
        <tr>
          <th className="text-right px-3 py-2 font-medium">Start</th>
          <th className="text-right px-3 py-2 font-medium">End Date</th>
          <th className="text-right px-3 py-2 font-medium">Start Px</th>
          <th className="text-right px-3 py-2 font-medium">Low Px</th>
          <th className="text-right px-3 py-2 font-medium">Max Down</th>
          <th className="text-right px-3 py-2 font-medium">Recovery</th>
          <th className="text-right px-3 py-2 font-medium">Sessions</th>
          <th className="text-right px-3 py-2 font-medium">Ignored</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {displayEpisodes.map(e => {
          const tone = yearTone.get(e.start_date.slice(0, 4)) ?? 0
          return (
          <tr
            key={`${e.start_date}-${e.start_price}`}
            className={[
              "hover:bg-muted/40",
              tone === 0 ? "bg-sky-500/12 border-l-4 border-l-sky-500/70" : "",
              tone === 1 ? "bg-emerald-500/12 border-l-4 border-l-emerald-500/70" : "",
              tone === 2 ? "bg-amber-500/14 border-l-4 border-l-amber-500/75" : "",
              tone === 3 ? "bg-violet-500/12 border-l-4 border-l-violet-500/70" : "",
              tone === 4 ? "bg-rose-500/12 border-l-4 border-l-rose-500/70" : "",
              tone === 5 ? "bg-cyan-500/12 border-l-4 border-l-cyan-500/70" : "",
            ].join(" ")}
          >
            <td className="px-3 py-2 text-right tabular-nums">{fmtDate(e.start_date)}</td>
            <td className="px-3 py-2 text-right tabular-nums">{fmtDate(e.low_date)}</td>
            <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(e.start_price)}</td>
            <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(e.low_price)}</td>
            <td className="px-3 py-2 text-right tabular-nums">{fmtPct(e.max_down_pct)}</td>
            <td className="px-3 py-2 text-right tabular-nums">{fmtDate(e.recovery_date)}</td>
            <td className="px-3 py-2 text-right tabular-nums">
              {e.recovery_sessions != null
                ? fmtInt(e.recovery_sessions)
                : current?.start_date === e.start_date
                  ? `${fmtInt(current.sessions_elapsed)} (active)`
                  : "active"}
            </td>
            <td className="px-3 py-2 text-right tabular-nums">{fmtInt(e.ignored_new_lows)}</td>
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
