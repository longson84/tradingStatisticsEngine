import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Link } from "react-router"
import { ChevronDown, ChevronRight } from "lucide-react"
import { Sidebar } from "@/components/Sidebar"
import { FormLabel as Label } from "@/components/forms/FormSelect"
import {
  predefinedRarityApi,
  watchlistsApi,
  type PredefinedRarityFactorKey,
  type PredefinedRarityResponse,
  type PredefinedRarityRow,
} from "@/lib/api"
import { fmtDate, fmtInt, fmtPct, fmtPrice } from "@/lib/format"
import { cn } from "@/lib/utils"

export function PredefinedFactorsRarityPage() {
  const [watchlistId, setWatchlistId] = useState("")
  const watchlists = useQuery({
    queryKey: ["watchlists"],
    queryFn: watchlistsApi,
  })
  const {
    mutate: runAnalysis,
    data,
    isPending: isFetching,
    error,
  } = useMutation({
    mutationFn: predefinedRarityApi,
  })
  const selectedWatchlist = watchlists.data?.watchlists.find(
    row => String(row.id) === watchlistId
  )

  const controls = (
    <div className="space-y-4">
      <div>
        <Label>Watchlist</Label>
        <select
          value={watchlistId}
          onChange={event => setWatchlistId(event.target.value)}
          className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:border-ring focus:outline-none"
        >
          <option value="">Select a watchlist</option>
          {watchlists.data?.watchlists.map(row => (
            <option key={row.id} value={row.id}>
              {row.name} ({row.member_count})
            </option>
          ))}
        </select>
        {selectedWatchlist && (
          <p className="mt-1 text-[10px] text-muted-foreground">
            {selectedWatchlist.member_count.toLocaleString()} canonical instruments
          </p>
        )}
        {!watchlists.isPending && watchlists.data?.watchlists.length === 0 && (
          <p className="mt-2 text-xs text-muted-foreground">
            No watchlists. <Link to="/collections/watchlists" className="text-primary hover:underline">Create one</Link>.
          </p>
        )}
      </div>

      <button
        onClick={() => {
          runAnalysis({ watchlist_id: Number(watchlistId) })
        }}
        disabled={isFetching || !selectedWatchlist || selectedWatchlist.member_count === 0}
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
            <h1 className="text-2xl font-bold tracking-tight">Predefined</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Fixed percentile tables for MA distance and 200-day high distance.
            </p>
          </div>
          {data && (
            <div className="text-xs text-muted-foreground text-right">
              <div>{data.watchlist_name}</div>
              <div>{fmtInt(data.available_instruments)} / {fmtInt(data.requested_instruments)} instruments with stored history</div>
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
            Choose a saved watchlist and run the analysis.
          </div>
        )}

        {data && !isFetching && (
          <div className="mt-5 space-y-6">
            {(data.errors?.length ?? 0) > 0 && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 px-4 py-3 text-sm text-amber-200">
                {data.errors?.join("; ")}
              </div>
            )}

            <SummarySection data={data} />

            {data.tables.map(table => (
              <PredefinedFactorSection key={table.factor_key} data={data} table={table} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

type SummaryP50FactorKey =
  | "distance_ma50"
  | "distance_ma100"
  | "distance_ma150"
  | "distance_ma200"
  | "distance_high_100"
  | "distance_high_150"
  | "distance_high_200"

interface SummaryRow {
  instrumentId: number
  symbol: string
  identity: string
  currentPrice: number
  p50Prices: number[]
  factorP50Prices: Partial<Record<SummaryP50FactorKey, number>>
  toP50Values: number[]
  factorToP50Values: Partial<Record<SummaryP50FactorKey, number>>
  percentiles: Partial<Record<PredefinedRarityFactorKey, number>>
}

function SummarySection({ data }: { data: PredefinedRarityResponse }) {
  const rows = buildSummaryRows(data)

  return (
    <section className="space-y-3">
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Summary
      </h2>
      <div className="border border-border rounded-lg overflow-x-auto bg-card">
        <table className="w-full text-sm min-w-[1320px]">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-left px-3 py-2 font-medium">Symbol</th>
              <th className="text-right px-3 py-2 font-medium">Cur Price</th>
              <th className="text-right px-3 py-2 font-medium">P50 Price Range</th>
              <th className="text-right px-3 py-2 font-medium">To P50 Range</th>
              {data.tables.map(table => (
                <th key={table.factor_key} className="text-right px-3 py-2 font-medium">
                  {factorShortLabel(table.factor_key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map(row => (
              <tr key={row.instrumentId} className="hover:bg-muted/30">
                <td className="px-3 py-2 font-medium">
                  <div>{row.symbol}</div>
                  <div className="text-[10px] font-normal text-muted-foreground">{row.identity}</div>
                </td>
                <td className="px-3 py-2 text-right tabular-nums font-medium">{fmtPrice(row.currentPrice)}</td>
                <td className="px-3 py-2 text-right tabular-nums font-medium">
                  <P50PriceRangeCell row={row} />
                </td>
                <td className="px-3 py-2 text-right tabular-nums font-medium">
                  <ToP50RangeCell row={row} />
                </td>
                {data.tables.map(table => {
                  const percentile = row.percentiles[table.factor_key]

                  return (
                    <td key={table.factor_key} className="px-3 py-2 text-right tabular-nums">
                      {percentile == null ? (
                        <span className="text-muted-foreground">n/a</span>
                      ) : (
                        <span className={cn(
                          "inline-flex min-w-[4.25rem] justify-center rounded px-2 py-1 text-xs font-bold",
                          percentileTone(percentile)
                        )}>
                          {fmtPct(percentile, 1)}
                        </span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <P50DotLegend />
    </section>
  )
}

function P50PriceRangeCell({ row }: { row: SummaryRow }) {
  const { min, max } = minMax(row.p50Prices)
  if (min == null || max == null) return <span className="text-muted-foreground">n/a</span>

  const p50Points = summaryP50Points(row)
  const pointValues = p50Points.map(point => point.value).filter((value): value is number => value != null && Number.isFinite(value))
  const domainMin = Math.min(min, row.currentPrice, ...pointValues)
  const domainMax = Math.max(max, row.currentPrice, ...pointValues)
  const span = domainMax - domainMin
  const rangeLeft = span > 0 ? ((min - domainMin) / span) * 100 : 0
  const rangeWidth = span > 0 ? ((max - min) / span) * 100 : 100
  const currentLeft = span > 0 ? ((row.currentPrice - domainMin) / span) * 100 : 50
  const relation =
    row.currentPrice < min ? "below" :
    row.currentPrice > max ? "above" :
    "inside"

  return (
    <div className="min-w-44">
      <div className="flex items-center justify-end gap-2">
        <span>{fmtPriceRange(row.p50Prices)}</span>
        <span className={cn(
          "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
          relation === "below" && "bg-emerald-500 text-emerald-950",
          relation === "inside" && "bg-sky-400 text-sky-950",
          relation === "above" && "bg-red-600 text-white"
        )}>
          {relation}
        </span>
      </div>
      <div className="relative mt-2 h-4">
        <div className="absolute inset-x-0 top-1.5 h-1.5 rounded bg-muted" />
        <div
          className="absolute top-1 h-2.5 rounded bg-sky-500/75"
          style={{ left: `${rangeLeft}%`, width: `${rangeWidth}%` }}
        />
        <div
          className="absolute top-0 h-4 w-0.5 -translate-x-1/2 bg-foreground"
          style={{ left: `${currentLeft}%` }}
        />
        {p50Points.map(point => {
          if (point.value == null || !Number.isFinite(point.value)) return null
          const left = span > 0 ? ((point.value - domainMin) / span) * 100 : 50

          return (
            <span
              key={point.key}
              title={`${point.legendLabel} ${fmtPrice(point.value)}`}
              className={cn(
                "absolute top-0.5 size-3 -translate-x-1/2 rounded-full border-2 border-background shadow-sm",
                point.tone
              )}
              style={{ left: `${left}%` }}
            />
          )
        })}
      </div>
    </div>
  )
}

function P50DotLegend() {
  return (
    <div className="flex flex-wrap items-center gap-3 px-1 text-[11px] font-medium text-muted-foreground">
      {p50PointDefinitions.map(point => (
        <span key={point.key} className="inline-flex items-center gap-1.5">
          <span className={cn("size-2.5 rounded-full", point.tone)} />
          {point.legendLabel}
        </span>
      ))}
      <span className="inline-flex items-center gap-1.5">
        <span className="h-3.5 w-0.5 bg-foreground" />
        Current price
      </span>
    </div>
  )
}

const p50PointDefinitions = [
  { key: "distance_ma50", label: "50", legendLabel: "MA50 P50", tone: "bg-sky-500" },
  { key: "distance_ma100", label: "100", legendLabel: "MA100 P50", tone: "bg-violet-500" },
  { key: "distance_ma150", label: "150", legendLabel: "MA150 P50", tone: "bg-fuchsia-500" },
  { key: "distance_ma200", label: "200", legendLabel: "MA200 P50", tone: "bg-amber-500" },
  { key: "distance_high_100", label: "High100", legendLabel: "Highest 100D P50", tone: "bg-lime-500" },
  { key: "distance_high_150", label: "High150", legendLabel: "Highest 150D P50", tone: "bg-orange-500" },
  { key: "distance_high_200", label: "High200", legendLabel: "Highest 200D P50", tone: "bg-rose-500" },
] as const

function summaryP50Points(row: SummaryRow) {
  return [
    ...p50PointDefinitions.map(point => ({
      ...point,
      value: row.factorP50Prices[point.key],
    })),
  ]
}

function summaryToP50Points(row: SummaryRow) {
  return [
    ...p50PointDefinitions.map(point => ({
      ...point,
      value: row.factorToP50Values[point.key],
    })),
  ]
}

function ToP50RangeCell({ row }: { row: SummaryRow }) {
  const points = summaryToP50Points(row)
  const values = points.map(point => point.value).filter((value): value is number => value != null && Number.isFinite(value))
  const { min, max } = minMax(values)
  if (min == null || max == null) return <span className="text-muted-foreground">n/a</span>

  const maxAbs = Math.max(Math.abs(min), Math.abs(max), 0.01)
  const negativeWidth = min < 0 ? (Math.abs(min) / maxAbs) * 50 : 0
  const positiveWidth = max > 0 ? (max / maxAbs) * 50 : 0

  return (
    <div className="min-w-64">
      <div className="relative h-9">
        <div className="absolute inset-x-0 bottom-1.5 h-1.5 rounded bg-muted" />
        <div className="absolute left-1/2 bottom-0 h-4 w-px bg-border" />
        {negativeWidth > 0 && (
          <div
            className="absolute bottom-1 h-2.5 rounded-l bg-red-600/80"
            style={{ left: `${50 - negativeWidth}%`, width: `${negativeWidth}%` }}
          />
        )}
        {positiveWidth > 0 && (
          <div
            className="absolute bottom-1 h-2.5 rounded-r bg-emerald-500/80"
            style={{ left: "50%", width: `${positiveWidth}%` }}
          />
        )}
        {points.map(point => {
          if (point.value == null || !Number.isFinite(point.value)) return null
          const left = 50 + (point.value / maxAbs) * 50
          const isRangeEnd = Math.abs(point.value - min) < 0.0001 || Math.abs(point.value - max) < 0.0001

          return (
            <div
              key={point.key}
              title={`${point.legendLabel} to P50 ${fmtSignedPct(point.value)}`}
              className="absolute top-0 h-full w-0"
              style={{ left: `${left}%` }}
            >
              {isRangeEnd && (
                <div className={cn(
                  "absolute left-1/2 top-0 -translate-x-1/2 whitespace-nowrap text-[10px] font-bold leading-none tabular-nums",
                  point.value < 0 ? "text-red-600 dark:text-red-300" : "text-emerald-700 dark:text-emerald-300"
                )}>
                  {fmtSignedPct(point.value)}
                </div>
              )}
              <span className={cn(
                "absolute bottom-[3px] left-1/2 block size-3 -translate-x-1/2 rounded-full border-2 border-background shadow-sm",
                point.tone
              )} />
            </div>
          )
        })}
      </div>
    </div>
  )
}

function buildSummaryRows(data: PredefinedRarityResponse): SummaryRow[] {
  const byInstrument = new Map<number, SummaryRow>()
  const statusById = new Map(data.instruments.map(status => [status.instrument_id, status]))

  for (const table of data.tables) {
    for (const row of table.rows) {
      const status = statusById.get(row.instrument_id)
      const current = byInstrument.get(row.instrument_id) ?? {
        instrumentId: row.instrument_id,
        symbol: row.symbol,
        identity: instrumentIdentity(status),
        currentPrice: row.current_price,
        p50Prices: [],
        factorP50Prices: {},
        toP50Values: [],
        factorToP50Values: {},
        percentiles: {},
      }

      current.currentPrice = row.current_price
      current.p50Prices.push(row.p50_price)
      if (isSummaryP50FactorKey(table.factor_key)) {
        current.factorP50Prices[table.factor_key] = row.p50_price
        current.factorToP50Values[table.factor_key] = returnToMedianPct(row)
      }
      current.toP50Values.push(returnToMedianPct(row))
      current.percentiles[table.factor_key] = row.current_percentile
      byInstrument.set(row.instrument_id, current)
    }
  }

  return [...byInstrument.values()]
}

function instrumentIdentity(
  status: PredefinedRarityResponse["instruments"][number] | undefined,
): string {
  if (!status) return "Canonical instrument"
  const economicIdentity = status.company_name
    ?? (status.base_asset && status.quote_asset
      ? `${status.base_asset}/${status.quote_asset}`
      : status.instrument_type)
  const location = status.venue_name ?? status.venue_code
  return [economicIdentity, location, status.currency]
    .filter(Boolean)
    .join(" · ")
}

function isSummaryP50FactorKey(factorKey: PredefinedRarityFactorKey): factorKey is SummaryP50FactorKey {
  return factorKey === "distance_ma50" ||
    factorKey === "distance_ma100" ||
    factorKey === "distance_ma150" ||
    factorKey === "distance_ma200" ||
    factorKey === "distance_high_100" ||
    factorKey === "distance_high_150" ||
    factorKey === "distance_high_200"
}

function factorShortLabel(factorKey: PredefinedRarityFactorKey) {
  const labels: Record<PredefinedRarityFactorKey, string> = {
    distance_ma50: "MA50 PCTL",
    distance_ma100: "MA100 PCTL",
    distance_ma150: "MA150 PCTL",
    distance_ma200: "MA200 PCTL",
    distance_high_100: "High100 PCTL",
    distance_high_150: "High150 PCTL",
    distance_high_200: "High200 PCTL",
  }
  return labels[factorKey]
}

function fmtPriceRange(values: number[]) {
  const { min, max } = minMax(values)
  if (min == null || max == null) return "n/a"
  if (Math.round(min) === Math.round(max)) return fmtPrice(min)
  return `${fmtPrice(min)} - ${fmtPrice(max)}`
}

function minMax(values: number[]) {
  const finite = values.filter(Number.isFinite)
  if (!finite.length) return { min: null, max: null }
  return { min: Math.min(...finite), max: Math.max(...finite) }
}

function PredefinedFactorSection({
  data,
  table,
}: {
  data: PredefinedRarityResponse
  table: PredefinedRarityResponse["tables"][number]
}) {
  const [chartsOpen, setChartsOpen] = useState(true)

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {table.factor_name}
        </h2>
        <button
          onClick={() => setChartsOpen(open => !open)}
          className="inline-flex items-center gap-1.5 rounded border border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          {chartsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          Charts
        </button>
      </div>
      <div className="border border-border rounded-lg overflow-x-auto bg-card">
        <PredefinedRarityTable data={data} rows={table.rows} />
      </div>
      {chartsOpen && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {table.rows.map(row => (
            <FactorPercentileCard key={`${table.factor_key}-${row.instrument_id}`} row={row} />
          ))}
        </div>
      )}
    </section>
  )
}

function PredefinedRarityTable({
  data,
  rows,
}: {
  data: PredefinedRarityResponse
  rows: PredefinedRarityRow[]
}) {
  return (
    <table className="w-full text-sm min-w-[1180px]">
      <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
        <tr>
          <th className="text-left px-3 py-2 font-medium">Symbol</th>
          <th className="text-right px-3 py-2 font-medium">Ref Price</th>
          <th className="text-right px-3 py-2 font-medium">P50 Price</th>
          <th className="text-right px-3 py-2 font-medium">Cur Price</th>
          <th className="text-right px-3 py-2 font-medium">To P50</th>
          <th className="text-right px-3 py-2 font-medium">Cur</th>
          <th className="text-right px-3 py-2 font-medium">Cur PCTL</th>
          {data.percentile_columns.map(col => (
            <th key={col} className="text-right px-3 py-2 font-medium">{col.toUpperCase()}</th>
          ))}
          <th className="text-right px-3 py-2 font-medium">Start</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rows.map(row => {
          const currentColumn = nearestPercentileColumn(data.percentile_columns, row.current_percentile)

          return (
            <tr key={row.instrument_id} className="hover:bg-muted/30">
              <td className="px-3 py-2 font-medium">
                <div>{row.symbol}</div>
                <div className="text-[10px] font-normal text-muted-foreground">
                  {instrumentIdentity(data.instruments.find(status => status.instrument_id === row.instrument_id))}
                </div>
              </td>
              <td className="px-3 py-2 text-right tabular-nums font-medium">{fmtPrice(row.reference_price)}</td>
              <td className="px-3 py-2 text-right tabular-nums font-medium">{fmtPrice(row.p50_price)}</td>
              <td className="px-3 py-2 text-right tabular-nums font-medium">{fmtPrice(row.current_price)}</td>
              <ReturnToMedianCell value={returnToMedianPct(row)} />
              <td className="px-3 py-2 text-right tabular-nums font-medium">
                {fmtSignedPct(row.current_value_pct)}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                <span className={cn(
                  "inline-flex min-w-[4.25rem] justify-center rounded px-2 py-1 text-xs font-bold",
                  percentileTone(row.current_percentile)
                )}>
                  {fmtPct(row.current_percentile, 1)}
                </span>
              </td>
              {data.percentile_columns.map(col => {
                const isCurrent = col === currentColumn

                return (
                  <td
                    key={col}
                    className={cn(
                      "px-3 py-2 text-right tabular-nums",
                      isCurrent && percentileTone(row.current_percentile)
                    )}
                  >
                    {fmtSignedPct(row.percentiles[col])}
                  </td>
                )
              })}
              <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{fmtDate(row.first_date)}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function ReturnToMedianCell({ value }: { value: number }) {
  return (
    <td className="px-3 py-2 text-right tabular-nums font-medium">
      <span className={cn(
        "inline-flex min-w-[4.25rem] justify-center rounded px-2 py-1 text-xs font-bold",
        value > 0 ? "bg-emerald-500 text-emerald-950" : "",
        value < 0 ? "bg-red-600 text-white" : "",
        value === 0 ? "bg-zinc-500 text-white" : ""
      )}>
        {fmtSignedPct(value)}
      </span>
    </td>
  )
}

function returnToMedianPct(row: PredefinedRarityRow) {
  const currentFactor = row.current_value_pct / 100
  const medianFactor = row.percentiles.p50 / 100
  return ((1 + medianFactor) / (1 + currentFactor) - 1) * 100
}

function FactorPercentileCard({ row }: { row: PredefinedRarityRow }) {
  const markerLeft = Math.max(0, Math.min(100, row.current_percentile))
  const thresholds = [
    ["P5", row.percentiles.p5],
    ["P25", row.percentiles.p25],
    ["P50", row.percentiles.p50],
    ["P75", row.percentiles.p75],
    ["P95", row.percentiles.p95],
  ] as const

  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">{row.symbol}</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wide">current versus historical thresholds</div>
        </div>
        <div className="text-right">
          <div className="text-sm font-semibold tabular-nums">{fmtSignedPct(row.current_value_pct)}</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wide">{fmtPct(row.current_percentile, 1)} pct</div>
        </div>
      </div>

      <div className="px-4 pt-5 pb-4">
        <div className="relative h-20">
          <div className="absolute inset-x-0 top-7 h-5 rounded overflow-hidden border border-border flex">
            {DECILE_BANDS.map(band => (
              <div key={band.label} className={cn("h-full", band.className)} style={{ width: "10%" }} />
            ))}
          </div>
          <div
            className="absolute top-0 bottom-4 w-0.5 -translate-x-1/2 bg-blue-500 shadow-[0_0_0_2px_rgba(59,130,246,0.18)]"
            style={{ left: `${markerLeft}%` }}
          >
            <div className="absolute -top-1 left-1/2 -translate-x-1/2 text-[9px] font-semibold text-blue-500 whitespace-nowrap rounded bg-card px-1">
              current
            </div>
          </div>
        </div>

        <div className="mt-2 grid grid-cols-5 gap-2 text-[10px] text-muted-foreground tabular-nums">
          {thresholds.map(([label, value]) => (
            <div key={label} className="rounded border border-border/70 bg-muted/20 px-2 py-1">
              <div className="uppercase tracking-wide">{label}</div>
              <div className="text-foreground">{fmtSignedPct(value)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const DECILE_BANDS = [
  { label: "0-10", className: "bg-emerald-700" },
  { label: "11-20", className: "bg-emerald-500" },
  { label: "21-30", className: "bg-teal-400" },
  { label: "31-40", className: "bg-cyan-400" },
  { label: "41-50", className: "bg-sky-400" },
  { label: "51-60", className: "bg-blue-500" },
  { label: "61-70", className: "bg-violet-500" },
  { label: "71-80", className: "bg-yellow-400" },
  { label: "81-90", className: "bg-orange-500" },
  { label: "91-100", className: "bg-red-600" },
]

function nearestPercentileColumn(columns: string[], percentile: number) {
  return columns.reduce((nearest, col) => {
    const currentDistance = Math.abs(percentileFromColumn(col) - percentile)
    const nearestDistance = Math.abs(percentileFromColumn(nearest) - percentile)
    return currentDistance < nearestDistance ? col : nearest
  }, columns[0])
}

function percentileFromColumn(column: string) {
  return Number(column.replace("p", ""))
}

function percentileTone(percentile: number) {
  if (percentile <= 10) return "bg-emerald-700 text-white"
  if (percentile <= 20) return "bg-emerald-500 text-emerald-950"
  if (percentile <= 30) return "bg-teal-400 text-teal-950"
  if (percentile <= 40) return "bg-cyan-400 text-cyan-950"
  if (percentile <= 50) return "bg-sky-400 text-sky-950"
  if (percentile <= 60) return "bg-blue-500 text-white"
  if (percentile <= 70) return "bg-violet-500 text-white"
  if (percentile <= 80) return "bg-yellow-400 text-yellow-950"
  if (percentile <= 90) return "bg-orange-500 text-orange-950"
  return "bg-red-600 text-white"
}

function fmtSignedPct(value: number) {
  const sign = value > 0 ? "+" : ""
  return sign + fmtPct(value)
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
