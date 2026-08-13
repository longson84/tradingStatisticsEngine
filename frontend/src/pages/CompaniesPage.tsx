import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { CompanyCatalogTable } from "@/components/company/CompanyCatalogTable"
import { Pagination } from "@/components/ui/Pagination"
import { Sidebar } from "@/components/Sidebar"
import { companiesApi } from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"
import { useDebouncedValue } from "@/lib/useDebouncedValue"

const ALL_COUNTRIES = "ALL"
const ALL_SECTORS = "ALL"
const PAGE_SIZE = 50


export function CompaniesPage() {
  const [country, setCountry] = useState(ALL_COUNTRIES)
  const [sector, setSector] = useState(ALL_SECTORS)
  const [query, setQuery] = useState("")
  const [offset, setOffset] = useState(0)
  const debouncedQuery = useDebouncedValue(query.trim(), 300)
  const catalog = useQuery({
    queryKey: ["company-catalog", country, sector, debouncedQuery, offset],
    queryFn: () => companiesApi({
      country: country === ALL_COUNTRIES ? undefined : country as "US" | "VN",
      sector: sector === ALL_SECTORS ? undefined : sector,
      search: debouncedQuery || undefined,
      offset,
      limit: PAGE_SIZE,
    }),
    placeholderData: previous => previous,
    refetchOnMount: "always",
    retry: false,
  })
  const companies = useMemo(
    () => catalog.data?.companies ?? [],
    [catalog.data?.companies],
  )

  const countryOptions = useMemo(() => {
    const facets = catalog.data?.facets.countries ?? []
    return [
      {
        value: ALL_COUNTRIES,
        label: "All Companies",
        count: facets.reduce((sum, facet) => sum + facet.count, 0),
      },
      ...facets.map(facet => ({
        value: facet.value,
        label: facet.value === "US" ? "US Companies" : "VN Companies",
        count: facet.count,
      })),
    ]
  }, [catalog.data?.facets.countries])

  const sectorOptions = useMemo(() => {
    const facets = catalog.data?.facets.sectors ?? []
    return [
      {
        value: ALL_SECTORS,
        count: facets.reduce((sum, facet) => sum + facet.count, 0),
      },
      ...facets,
    ]
  }, [catalog.data?.facets.sectors])

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="flex flex-col gap-4 border-b border-border pb-4">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Companies</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Canonical issuers grouped independently from their tradable instruments.
              </p>
            </div>
            <div className="text-right text-xs text-muted-foreground">
              <div>{countLabel(catalog.data?.total ?? 0, "company", "companies")}</div>
              <div>50 companies per page</div>
            </div>
          </div>

          <FilterGroup label="Country">
            {countryOptions.map(option => (
              <FilterButton
                key={option.value}
                active={country === option.value}
                onClick={() => {
                  setCountry(option.value)
                  setSector(ALL_SECTORS)
                  setOffset(0)
                }}
              >
                {option.label} ({fmtInt(option.count)})
              </FilterButton>
            ))}
          </FilterGroup>

          {sectorOptions.length > 1 && (
            <FilterGroup label="Sector">
              {sectorOptions.map(option => (
                <FilterButton
                  key={option.value}
                  active={sector === option.value}
                  onClick={() => {
                    setSector(option.value)
                    setOffset(0)
                  }}
                >
                  {option.value === ALL_SECTORS ? "All Sectors" : option.value}
                  {` (${fmtInt(option.count)})`}
                </FilterButton>
              ))}
            </FilterGroup>
          )}
        </div>

        <div className="mt-5 space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-sm font-semibold">Company Catalog</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                One row per issuer; instruments, exchanges, and universe memberships are grouped.
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
                placeholder="Search company, symbol, sector, identifier..."
                className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
              />
            </label>
          </div>

          {catalog.isFetching && (
            <div className="h-1 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/3 animate-pulse bg-primary" />
            </div>
          )}
          {catalog.error && !catalog.isFetching && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {catalog.error.message}
            </div>
          )}
          {catalog.data && !catalog.isFetching && (
            <CompanyCatalogTable companies={companies} />
          )}
          {catalog.data && !catalog.isFetching && (
            <Pagination
              total={catalog.data.total}
              offset={catalog.data.offset}
              limit={catalog.data.limit}
              onOffsetChange={setOffset}
            />
          )}
        </div>
      </main>
    </div>
  )
}


function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
        {label}
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}


function countLabel(count: number, singular: string, plural: string): string {
  return `${fmtInt(count)} ${count === 1 ? singular : plural}`
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
