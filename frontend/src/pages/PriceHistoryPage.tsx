import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ChartNoAxesCombined } from "lucide-react"
import { FormLabel } from "@/components/forms/FormSelect"
import { AnalysisInstrumentSelector } from "@/components/forms/AnalysisInstrumentSelector"
import { Sidebar } from "@/components/Sidebar"
import {
  SymbolPriceHistoryChart,
  type PriceHistoryCursorSnapshot,
} from "@/components/market/SymbolPriceHistoryChart"
import { Badge } from "@/components/ui/badge"
import {
  instrumentPriceHistoryApi,
  instrumentsApi,
  type InstrumentCatalogItem,
  type InstrumentPriceHistoryResponse,
  type InstrumentScope,
} from "@/lib/api"
import { fmtProviderSource } from "@/lib/format"
import { parseIndicatorLengths } from "@/lib/moving-averages"
import { useDebouncedValue } from "@/lib/useDebouncedValue"


export function PriceHistoryPage() {
  const [scope, setScope] = useState<InstrumentScope>("equity")
  const [search, setSearch] = useState("")
  const [instrument, setInstrument] = useState<InstrumentCatalogItem | null>(null)
  const [smaInput, setSmaInput] = useState("")
  const [emaInput, setEmaInput] = useState("")
  const [cursorSnapshot, setCursorSnapshot] = useState<PriceHistoryCursorSnapshot | null>(null)
  const [selection, setSelection] = useState({
    instrument: null as InstrumentCatalogItem | null,
    smaLengths: [] as number[],
    emaLengths: [] as number[],
  })

  const debouncedSearch = useDebouncedValue(search.trim(), 300)
  const instruments = useQuery({
    queryKey: ["price-history-instruments", scope, debouncedSearch],
    queryFn: () => instrumentsApi({ scope, search: debouncedSearch, limit: 20 }),
    enabled: debouncedSearch.length >= 3,
  })
  const history = useQuery({
    queryKey: ["instrument-price-history", selection.instrument?.id],
    queryFn: () => instrumentPriceHistoryApi(selection.instrument!.id),
    enabled: selection.instrument != null,
    retry: false,
  })

  const prices = history.data?.prices ?? []
  const first = prices[0]
  const latest = prices[prices.length - 1]
  const highest = prices.length > 0 ? Math.max(...prices.map(point => point.close)) : null
  const lowest = prices.length > 0 ? Math.min(...prices.map(point => point.close)) : null
  const latestEpsTtm = [...prices].reverse().find(point => point.eps_ttm != null)?.eps_ttm ?? null
  const latestTrailingPe = [...prices].reverse().find(point => point.trailing_pe != null)?.trailing_pe ?? null
  const latestTrailingPb = [...prices].reverse().find(point => point.trailing_pb != null)?.trailing_pb ?? null
  const isVietnam = history.data?.currency === "VND"
  const isEquity = history.data?.instrument_type === "common_stock"

  const viewHistory = () => {
    if (!instrument) return
    setCursorSnapshot(null)
    setSelection({
      instrument,
      smaLengths: parseIndicatorLengths(smaInput),
      emaLengths: parseIndicatorLengths(emaInput),
    })
  }

  const controls = (
    <div className="space-y-4">
      <AnalysisInstrumentSelector
        scope={scope}
        search={search}
        instruments={instruments.data?.instruments ?? []}
        selectedInstrument={instrument}
        total={instruments.data?.total}
        isPending={instruments.isFetching}
        onScopeChange={value => {
          setScope(value)
          setSearch("")
          setInstrument(null)
        }}
        onSearchChange={value => {
          setSearch(value)
          setInstrument(null)
        }}
        onInstrumentChange={setInstrument}
        onSubmit={viewHistory}
      />

      <div>
        <FormLabel>SMA lengths</FormLabel>
        <input
          value={smaInput}
          onChange={event => setSmaInput(event.target.value)}
          placeholder="50, 150, 200"
          inputMode="numeric"
          className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:border-ring focus:outline-none"
          aria-label="SMA lengths"
        />
      </div>

      <div>
        <FormLabel>EMA lengths</FormLabel>
        <input
          value={emaInput}
          onChange={event => setEmaInput(event.target.value)}
          placeholder="34, 89"
          inputMode="numeric"
          className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:border-ring focus:outline-none"
          aria-label="EMA lengths"
        />
        <p className="mt-1 text-[10px] text-muted-foreground">
          Separate multiple lengths with commas. Blank means no price overlay.
        </p>
      </div>

      <button
        onClick={viewHistory}
        disabled={!instrument || history.isFetching}
        className="w-full rounded-md bg-primary py-2.5 text-sm font-semibold tracking-wide text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {history.isFetching ? "Loading…" : "View history"}
      </button>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" children={controls} />
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <div className="mb-6 border-b border-border pb-4">
          <div className="flex items-center gap-2">
            <ChartNoAxesCombined size={20} className="text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">
              {history.data?.symbol ?? selection.instrument?.symbol ?? "Instrument"} Price History
            </h1>
            <Badge variant="secondary">{fmtProviderSource(history.data?.source)}</Badge>
            {history.data?.venue_code && <Badge variant="outline">{history.data.venue_code}</Badge>}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Maximum daily price history available in PostgreSQL for the selected instrument.
          </p>
        </div>

        {history.isFetching && (
          <div className="h-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full w-1/3 animate-pulse bg-primary" />
          </div>
        )}
        {history.error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            {history.error.message}
          </div>
        )}

        {history.data?.is_stale && (
          <div className="mb-5 rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-700 dark:text-amber-300">
            Stored data ends at {history.data.last_date}; expected {history.data.expected_last_session}. Update this instrument through Data Operations to load newer observations.
          </div>
        )}

        {history.data && first && latest && (
          <>
            <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6">
              <Datum label="First session" value={history.data.first_date} />
              <Datum label="Latest session" value={history.data.last_date} />
              <Datum label="Sessions" value={history.data.row_count.toLocaleString()} />
              <Datum label="Latest close" value={formatPrice(latest.close)} />
              <Datum label="Close range" value={`${formatPrice(lowest)} – ${formatPrice(highest)}`} />
              {isEquity && (
                <>
                  <Datum label="EPS TTM" value={formatPerShareValue(latestEpsTtm, isVietnam)} />
                  <Datum
                    label={shareGrowthLabel(history.data)}
                    value={formatPercent(history.data.shares_growth_pct)}
                    detail={shareGrowthDetail(history.data)}
                  />
                  <Datum
                    label={shareCagr5yLabel(history.data)}
                    value={formatPercent(history.data.shares_cagr_5y_pct)}
                    detail={shareCagr5yDetail(history.data)}
                  />
                  <Datum label="Calculated P/E" value={formatMultiple(latestTrailingPe)} />
                  <Datum label="Calculated P/B" value={formatMultiple(latestTrailingPb)} />
                  {history.data.provider_reported_pe != null && (
                    <Datum
                      label="VCI reported P/E"
                      value={formatMultiple(history.data.provider_reported_pe)}
                      detail={providerRatioDetail(history.data)}
                    />
                  )}
                  {history.data.provider_reported_pb != null && (
                    <Datum
                      label="VCI reported P/B"
                      value={formatMultiple(history.data.provider_reported_pb)}
                      detail={providerRatioDetail(history.data)}
                    />
                  )}
                </>
              )}
            </div>

            <CursorMetricCards
              snapshot={cursorSnapshot}
              smaLengths={selection.smaLengths}
              emaLengths={selection.emaLengths}
              showFundamentals={isEquity}
              showRelativeStrength={history.data.relative_strength_benchmark != null}
            />

            <section className="rounded-lg border border-border bg-card p-5">
              <SymbolPriceHistoryChart
                key={history.data.instrument_id}
                symbol={history.data.symbol}
                instrumentType={history.data.instrument_type}
                relativeStrengthBenchmark={history.data.relative_strength_benchmark}
                prices={prices}
                smaLengths={selection.smaLengths}
                emaLengths={selection.emaLengths}
                onCursorSnapshotChange={setCursorSnapshot}
              />
            </section>

            <p className="mt-4 text-[11px] leading-relaxed text-muted-foreground">
              {historyFootnote(history.data)}
            </p>
          </>
        )}
      </main>
    </div>
  )
}


function Datum({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-md border border-border bg-card px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold tabular-nums">{value}</div>
      {detail && <div className="mt-1 text-[10px] text-muted-foreground">{detail}</div>}
    </div>
  )
}


function CursorMetricCards({
  snapshot,
  smaLengths,
  emaLengths,
  showFundamentals,
  showRelativeStrength,
}: {
  snapshot: PriceHistoryCursorSnapshot | null
  smaLengths: number[]
  emaLengths: number[]
  showFundamentals: boolean
  showRelativeStrength: boolean
}) {
  const selectedIndicators = [
    ...smaLengths.map(length => `SMA ${length}`),
    ...emaLengths.map(length => `EMA ${length}`),
  ]
  const indicatorValues = new Map(
    snapshot?.indicators.map(indicator => [indicator.label, indicator.value]) ?? [],
  )
  const cards = [
    { label: "Session", value: snapshot?.date ?? "Move cursor over chart" },
    { label: "Open", value: formatExactValue(snapshot?.open ?? null) },
    { label: "High", value: formatExactValue(snapshot?.high ?? null) },
    { label: "Low", value: formatExactValue(snapshot?.low ?? null) },
    { label: "Close", value: formatExactValue(snapshot?.close ?? null) },
    { label: "Volume", value: formatExactValue(snapshot?.volume ?? null, 0) },
    { label: "Volume MA20", value: formatExactValue(snapshot?.volumeMa20 ?? null, 0) },
    ...(showRelativeStrength
      ? [{ label: "Relative strength", value: formatExactValue(snapshot?.relativeStrength ?? null) }]
      : []),
    ...selectedIndicators.map(label => ({
      label,
      value: formatExactValue(indicatorValues.get(label) ?? null),
    })),
    ...(showFundamentals ? [
      { label: "P/E", value: formatExactValue(snapshot?.trailingPe ?? null) },
      { label: "P/B", value: formatExactValue(snapshot?.trailingPb ?? null) },
      { label: "EPS TTM", value: formatExactValue(snapshot?.epsTtm ?? null) },
      {
        label: "Outstanding shares",
        value: formatExactValue(snapshot?.sharesOutstanding ?? null, 0),
      },
    ] : []),
  ]

  return (
    <div className="mb-5 grid gap-3 sm:grid-cols-2 md:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-8">
      {cards.map(card => <Datum key={card.label} label={card.label} value={card.value} />)}
    </div>
  )
}


function providerRatioDetail(history: InstrumentPriceHistoryResponse): string {
  return [history.provider_ratio_period, history.provider_ratio_effective_date]
    .filter(Boolean)
    .join(" · ")
}


function historyFootnote(history: InstrumentPriceHistoryResponse): string {
  if (history.instrument_type === "market_index") {
    return "This is a calculated index-level series, not a traded venue instrument. It has no company fundamentals and is not compared with another benchmark."
  }
  if (history.instrument_type === "spot") {
    return "These are venue-specific, unadjusted spot observations for the selected base/quote instrument. Company fundamentals and an equity benchmark do not apply."
  }
  if (history.instrument_type === "reference_rate") {
    return "These are provider-defined reference observations without an execution venue. Company fundamentals and an equity benchmark do not apply."
  }
  const fundamentals = history.trailing_pe_method
    ? `Fundamentals: ${history.trailing_pe_method}. Stored history changes only through Data Operations. `
    : "Fundamentals are not stored for this instrument. Update them through Data Operations to display P/E and P/B. "
  const adjustment = history.currency === "VND"
    ? "VCI does not expose an adjustment switch or adjusted-close column. The chart shows the stored provider closing series; its corporate-action adjustment methodology is unspecified."
    : "Yahoo Finance history is stored with auto-adjustment enabled, so historical OHLC values reflect splits and distributions according to Yahoo Finance's adjustment data."
  return fundamentals + adjustment
}


function formatPrice(value: number | null): string {
  return value == null ? "—" : value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}


function formatExactValue(value: number | null, decimals = 2): string {
  if (value == null) return "—"
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}


function formatMultiple(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(2)}x`
}


function formatPerShareValue(value: number | null, isVietnam: boolean): string {
  if (value == null) return "—"
  const formatted = value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return isVietnam ? `${formatted} VND` : `$${formatted}`
}


function shareGrowthLabel(history: InstrumentPriceHistoryResponse): string {
  if (history.shares_growth_full_10y) return "10Y share growth"
  if (history.shares_growth_observed_years != null) {
    return `${history.shares_growth_observed_years.toFixed(1)}Y share growth`
  }
  return "10Y share growth"
}


function shareGrowthDetail(history: InstrumentPriceHistoryResponse): string {
  if (history.shares_growth_cagr_pct == null || history.shares_growth_start_date == null) {
    return "Insufficient share history"
  }
  const suffix = history.shares_growth_full_10y ? "" : " · available history"
  return `${formatPercent(history.shares_growth_cagr_pct)} CAGR · since ${history.shares_growth_start_date}${suffix}`
}


function shareCagr5yLabel(history: InstrumentPriceHistoryResponse): string {
  if (history.shares_cagr_full_5y) return "5Y share CAGR"
  if (history.shares_cagr_5y_observed_years != null) {
    return `${history.shares_cagr_5y_observed_years.toFixed(1)}Y share CAGR`
  }
  return "5Y share CAGR"
}


function shareCagr5yDetail(history: InstrumentPriceHistoryResponse): string {
  if (history.shares_cagr_5y_start_date == null) return "Insufficient share history"
  const suffix = history.shares_cagr_full_5y ? "" : " · available history"
  return `Since ${history.shares_cagr_5y_start_date}${suffix}`
}


function formatPercent(value: number | null): string {
  if (value == null) return "—"
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`
}
