import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { ReferenceRateTable } from "@/components/reference-rates/ReferenceRateTable"
import { Sidebar } from "@/components/Sidebar"
import { Pagination } from "@/components/ui/Pagination"
import { referenceRatesApi } from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"
import { useDebouncedValue } from "@/lib/useDebouncedValue"


const ALL_ASSETS = "ALL"
const PAGE_SIZE = 50
type ReferenceRateStatus = "active" | "inactive" | "all"


export function ReferenceRatesPage() {
  const [status, setStatus] = useState<ReferenceRateStatus>("active")
  const [baseAsset, setBaseAsset] = useState(ALL_ASSETS)
  const [quoteAsset, setQuoteAsset] = useState(ALL_ASSETS)
  const [query, setQuery] = useState("")
  const [offset, setOffset] = useState(0)
  const debouncedQuery = useDebouncedValue(query.trim(), 300)
  const rates = useQuery({
    queryKey: ["reference-rates", status, baseAsset, quoteAsset, debouncedQuery, offset],
    queryFn: () => referenceRatesApi({
      status,
      base_asset: baseAsset === ALL_ASSETS ? undefined : baseAsset,
      quote_asset: quoteAsset === ALL_ASSETS ? undefined : quoteAsset,
      search: debouncedQuery || undefined,
      offset,
      limit: PAGE_SIZE,
    }),
    placeholderData: previous => previous,
    refetchOnMount: "always",
    retry: false,
  })
  const data = rates.data
  const baseOptions = useMemo(() => data?.facets.base_assets ?? [], [data])
  const quoteOptions = useMemo(() => data?.facets.quote_assets ?? [], [data])

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <div className="border-b border-border pb-5">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
            <div>
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Venue-less observations
              </div>
              <h1 className="text-2xl font-bold tracking-tight">Reference Rates</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Canonical market observations used for analysis—not executable venue listings.
              </p>
            </div>
            <div className="text-right text-xs text-muted-foreground">
              <div>{fmtInt(data?.summary.instrument_count ?? 0)} reference instruments</div>
              <div>{coverageLabel(data?.summary.earliest_session, data?.summary.latest_session)}</div>
            </div>
          </div>

          {data && (
            <div className="mt-5 grid overflow-hidden rounded-lg border border-border bg-card sm:grid-cols-2 xl:grid-cols-4">
              <SummaryCell label="All rates" value={data.summary.instrument_count} />
              <SummaryCell label="Active" value={data.summary.active_count} />
              <SummaryCell label="Inactive" value={data.summary.inactive_count} />
              <SummaryCell label="With stored history" value={data.summary.with_history_count} />
            </div>
          )}

          <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_260px_260px]">
            <FilterGroup label="Status">
              {(["active", "inactive", "all"] as const).map(value => (
                <FilterButton
                  key={value}
                  active={status === value}
                  onClick={() => {
                    setStatus(value)
                    setOffset(0)
                  }}
                >
                  {value === "active" ? `Active (${fmtInt(data?.facets.active_count ?? 0)})`
                    : value === "inactive" ? `Inactive (${fmtInt(data?.facets.inactive_count ?? 0)})`
                      : "All"}
                </FilterButton>
              ))}
            </FilterGroup>

            <AssetSelect
              label="Base asset"
              value={baseAsset}
              options={baseOptions}
              onChange={value => {
                setBaseAsset(value)
                setOffset(0)
              }}
            />
            <AssetSelect
              label="Quote asset"
              value={quoteAsset}
              options={quoteOptions}
              onChange={value => {
                setQuoteAsset(value)
                setOffset(0)
              }}
            />
          </div>
        </div>

        <div className="mt-5 space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-sm font-semibold">Reference Instrument Catalog</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Each row links canonical base and quote assets; it has a provider, but no venue.
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
                placeholder="Search BTC-USD, ETH-USD, Bitcoin..."
                className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
              />
            </label>
          </div>

          {rates.isFetching && (
            <div className="h-1 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/3 animate-pulse bg-primary" />
            </div>
          )}
          {rates.error && !rates.isFetching && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {rates.error.message}
            </div>
          )}
          {data && !rates.isFetching && <ReferenceRateTable instruments={data.instruments} />}
          {data && !rates.isFetching && (
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
        "rounded-md border px-3 py-1.5 text-xs font-medium capitalize transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}


function AssetSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; count: number }[]
  onChange: (value: string) => void
}) {
  return (
    <label className="space-y-2">
      <span className="block text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
        {label}
      </span>
      <select
        value={value}
        onChange={event => onChange(event.target.value)}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none"
      >
        <option value={ALL_ASSETS}>All assets</option>
        {options.map(option => (
          <option key={option.value} value={option.value}>
            {option.value} ({fmtInt(option.count)})
          </option>
        ))}
      </select>
    </label>
  )
}


function coverageLabel(first: string | null | undefined, last: string | null | undefined) {
  if (!first || !last) return "History not imported"
  return `Stored history ${first} to ${last}`
}
