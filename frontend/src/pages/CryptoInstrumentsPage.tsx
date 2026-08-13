import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { CryptoInstrumentTable } from "@/components/crypto/CryptoInstrumentTable"
import { Sidebar } from "@/components/Sidebar"
import { Pagination } from "@/components/ui/Pagination"
import { cryptoInstrumentsApi } from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"
import { useDebouncedValue } from "@/lib/useDebouncedValue"


const ALL_QUOTES = "ALL"
const ALL_VENUES = "ALL"
const PAGE_SIZE = 50
type InstrumentStatus = "active" | "inactive" | "all"


export function CryptoInstrumentsPage() {
  const [status, setStatus] = useState<InstrumentStatus>("active")
  const [venueCode, setVenueCode] = useState(ALL_VENUES)
  const [quoteAsset, setQuoteAsset] = useState(ALL_QUOTES)
  const [query, setQuery] = useState("")
  const [offset, setOffset] = useState(0)
  const debouncedQuery = useDebouncedValue(query.trim(), 300)
  const instruments = useQuery({
    queryKey: ["crypto-instruments", status, venueCode, quoteAsset, debouncedQuery, offset],
    queryFn: () => cryptoInstrumentsApi({
      status,
      venue_code: venueCode === ALL_VENUES ? undefined : venueCode,
      quote_asset: quoteAsset === ALL_QUOTES ? undefined : quoteAsset,
      search: debouncedQuery || undefined,
      offset,
      limit: PAGE_SIZE,
    }),
    placeholderData: previous => previous,
    refetchOnMount: "always",
    retry: false,
  })
  const data = instruments.data
  const venueOptions = useMemo(() => {
    const options = data?.facets.venues ?? []
    if (
      venueCode === ALL_VENUES
      || options.some(option => option.code === venueCode)
    ) return options
    return [{ code: venueCode, name: venueCode, count: 0 }, ...options]
  }, [data?.facets.venues, venueCode])
  const quoteOptions = useMemo(
    () => data?.facets.quote_assets ?? [],
    [data?.facets.quote_assets],
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <div className="border-b border-border pb-5">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
            <div>
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Spot venues
              </div>
              <h1 className="text-2xl font-bold tracking-tight">Crypto Instruments</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Venue-specific spot instruments, trading rules, and locally stored daily history.
              </p>
            </div>
            <div className="text-right text-xs text-muted-foreground">
              <div>{fmtInt(data?.summary.instrument_count ?? 0)} catalog instruments</div>
              <div>{catalogDate(data?.summary.catalog_fetched_at)}</div>
            </div>
          </div>

          {data && (
            <div className="mt-5 grid overflow-hidden rounded-lg border border-border bg-card sm:grid-cols-2 xl:grid-cols-4">
              <SummaryCell label="All instruments" value={data.summary.instrument_count} />
              <SummaryCell label="Trading now" value={data.summary.active_count} />
              <SummaryCell label="Inactive" value={data.summary.inactive_count} />
              <SummaryCell label="With stored history" value={data.summary.with_history_count} />
            </div>
          )}

          <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_260px_260px]">
            <FilterGroup label="Instrument status">
              <FilterButton
                active={status === "active"}
                onClick={() => changeStatus("active")}
              >
                Trading ({fmtInt(data?.facets.active_count ?? 0)})
              </FilterButton>
              <FilterButton
                active={status === "inactive"}
                onClick={() => changeStatus("inactive")}
              >
                Inactive ({fmtInt(data?.facets.inactive_count ?? 0)})
              </FilterButton>
              <FilterButton
                active={status === "all"}
                onClick={() => changeStatus("all")}
              >
                All
              </FilterButton>
            </FilterGroup>

            <label className="space-y-2">
              <span className="block text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                Venue
              </span>
              <select
                value={venueCode}
                onChange={event => {
                  setVenueCode(event.target.value)
                  setQuoteAsset(ALL_QUOTES)
                  setOffset(0)
                }}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none"
              >
                <option value={ALL_VENUES}>All venues</option>
                {venueOptions.map(option => (
                  <option key={option.code} value={option.code}>
                    {option.name} ({fmtInt(option.count)})
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-2">
              <span className="block text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                Quote asset
              </span>
              <select
                value={quoteAsset}
                onChange={event => {
                  setQuoteAsset(event.target.value)
                  setOffset(0)
                }}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none"
              >
                <option value={ALL_QUOTES}>All quote assets</option>
                {quoteOptions.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.value} ({fmtInt(option.count)})
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="mt-5 space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-sm font-semibold">Spot Instrument Catalog</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Each row is one venue-specific tradable pair—not a company or token issuer.
              </p>
            </div>
            <label className="relative block w-full lg:w-96">
              <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={event => {
                  setQuery(event.target.value)
                  setOffset(0)
                }}
                placeholder="Search BTCUSDT, BTC, USDT..."
                className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
              />
            </label>
          </div>

          {instruments.isFetching && (
            <div className="h-1 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/3 animate-pulse bg-primary" />
            </div>
          )}
          {instruments.error && !instruments.isFetching && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {instruments.error.message}
            </div>
          )}
          {data && !instruments.isFetching && (
            <CryptoInstrumentTable instruments={data.instruments} />
          )}
          {data && !instruments.isFetching && (
            <Pagination
              total={data.total}
              offset={data.offset}
              limit={data.limit}
              onOffsetChange={setOffset}
            />
          )}
        </div>
      </main>
    </div>
  )

  function changeStatus(next: InstrumentStatus) {
    setStatus(next)
    setOffset(0)
  }
}


function SummaryCell({ label, value }: { label: string; value: number }) {
  return (
    <div className="border-border px-4 py-3 sm:border-r last:border-r-0">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{fmtInt(value)}</div>
    </div>
  )
}


function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
        {label}
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  )
}


function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}


function catalogDate(value: string | null | undefined): string {
  if (!value) return "Catalog not synced"
  return `Catalog synced ${new Date(value).toLocaleString()}`
}
