import { useQuery } from "@tanstack/react-query"
import { ExternalLink, Search, X } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { InstrumentTable, type InstrumentRow } from "@/components/instrument/InstrumentTable"
import {
  companiesApi,
  marketHealthDistributionApi,
  type MarketHealthDistributionBucket,
  type MarketHealthMarket,
} from "@/lib/api"


export function MarketHealthDrilldownDrawer({
  market,
  bucket,
  onClose,
}: {
  market: MarketHealthMarket
  bucket: MarketHealthDistributionBucket
  onClose: () => void
}) {
  const [query, setQuery] = useState("")
  const params = {
    universe: market.universe,
    date: market.current.date,
    window: 200,
    min_distance: bucket.min_distance,
    max_distance: bucket.max_distance,
  }
  const distribution = useQuery({
    queryKey: ["market-health-drilldown", params],
    queryFn: () => marketHealthDistributionApi(params),
    retry: false,
  })
  const instruments = useQuery({
    queryKey: ["market-health-instrument-list", market.universe],
    queryFn: () => companiesApi({ universe: market.universe }),
    retry: false,
  })
  const instrumentBySymbol = useMemo(() => new Map(
    instruments.data?.companies.map(instrument => [instrument.ticker, instrument]) ?? []
  ), [instruments.data])
  const healthBySymbol = useMemo(() => new Map(
    distribution.data?.stocks.map(stock => [stock.symbol, stock]) ?? []
  ), [distribution.data])
  const rows = useMemo<InstrumentRow[]>(() => {
    const needle = query.trim().toLowerCase()
    return (distribution.data?.stocks ?? []).flatMap(stock => {
      const instrument = instrumentBySymbol.get(stock.symbol)
      const row: InstrumentRow = instrument
        ? instrument
        : {
            ticker: stock.symbol,
            company_name: stock.symbol,
            market: market.universe.startsWith("VN") ? "VN" : "US",
            sector: null,
            industry: null,
            exchange: null,
            lists: [market.universe],
            first_session: null,
            last_session: null,
            stored_sessions: 0,
          }
      if (!needle) return [row]
      const searchable = [row.ticker, row.company_name, row.sector, row.industry]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
      return searchable.includes(needle) ? [row] : []
    })
  }, [instrumentBySymbol, distribution.data?.stocks, market.universe, query])
  const instrumentsUrl = buildInstrumentsUrl(params)

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", closeOnEscape)
    return () => window.removeEventListener("keydown", closeOnEscape)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/35 p-4"
      role="presentation"
      onMouseDown={event => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label={`${market.universe} ${bucket.label} stocks`}
        className="flex h-full w-[min(1100px,calc(100vw-2rem))] flex-col overflow-hidden rounded-xl border border-border bg-background shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">{market.universe} · {bucket.label}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {market.current.date} · {bucket.count.toLocaleString()} stocks · {bucket.percentage.toFixed(1)}% of eligible stocks
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close drill-down"
            className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X size={18} />
          </button>
        </header>

        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
          <label className="relative block w-full max-w-sm">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Search ticker, company, sector..."
              className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
            />
          </label>
          <a
            href={instrumentsUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground"
          >
            Open in Instruments <ExternalLink size={13} />
          </a>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {(distribution.isFetching || instruments.isFetching) && (
            <div className="h-1 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/3 animate-pulse bg-primary" />
            </div>
          )}
          {(distribution.error || instruments.error) && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {(distribution.error ?? instruments.error)?.message}
            </div>
          )}
          {distribution.data && instruments.data && (
            <InstrumentTable rows={rows} healthBySymbol={healthBySymbol} />
          )}
        </div>
      </section>
    </div>
  )
}


function buildInstrumentsUrl(params: {
  universe: MarketHealthMarket["universe"]
  date: string
  window: number
  min_distance: number | null
  max_distance: number | null
}): string {
  const query = new URLSearchParams({
    list: params.universe,
    date: params.date,
    window: String(params.window),
  })
  if (params.min_distance != null) query.set("min_distance", String(params.min_distance))
  if (params.max_distance != null) query.set("max_distance", String(params.max_distance))
  return `/instruments?${query}`
}
