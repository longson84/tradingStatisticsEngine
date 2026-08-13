import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { InstrumentTable } from "@/components/instrument/InstrumentTable"
import { Pagination } from "@/components/ui/Pagination"
import { Sidebar } from "@/components/Sidebar"
import {
  instrumentsApi,
  universesApi,
} from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"
import { useDebouncedValue } from "@/lib/useDebouncedValue"

const ALL_SECTORS = "ALL"
const PAGE_SIZE = 50
export function InstrumentsPage() {
  const [selectedUniverse, setSelectedUniverse] = useState<string | null>(null)
  const [activeSector, setActiveSector] = useState(ALL_SECTORS)
  const [query, setQuery] = useState("")
  const [offset, setOffset] = useState(0)
  const debouncedQuery = useDebouncedValue(query.trim(), 300)

  const { data: availableUniverses } = useQuery({
    queryKey: ["instrument-universes"],
    queryFn: universesApi,
    retry: false,
  })

  const equityUniverses = useMemo(
    () => (availableUniverses?.universes ?? []).filter(
      universe => universe.instrument_types.includes("common_stock"),
    ),
    [availableUniverses?.universes],
  )
  const activeUniverse = equityUniverses.find(
    universe => universe.code === selectedUniverse,
  ) ?? null

  const { data: list, isFetching, error } = useQuery({
    queryKey: [
      "instrument-list",
      selectedUniverse,
      activeSector,
      debouncedQuery,
      offset,
    ],
    queryFn: () => instrumentsApi({
      scope: "equity",
      universe: selectedUniverse ?? undefined,
      sector: activeSector === ALL_SECTORS ? undefined : activeSector,
      search: debouncedQuery || undefined,
      has_price_history: false,
      offset,
      limit: PAGE_SIZE,
    }),
    placeholderData: previous => previous,
    retry: false,
  })

  const data = list ?? null

  const sectorOptions = useMemo(() => {
    if (!data) return []
    return [
      {
        sector: ALL_SECTORS,
        count: data.facets.sectors.reduce((sum, facet) => sum + facet.count, 0),
      },
      ...data.facets.sectors.map(facet => ({
        sector: facet.value,
        count: facet.count,
      })),
    ]
  }, [data])

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="flex flex-col gap-4 pb-4 border-b border-border">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Instruments</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Canonical tradable equity instruments, optionally filtered by Universe.
              </p>
            </div>
            {data && (
              <div className="text-xs text-muted-foreground text-right">
                <div>{fmtInt(data.total)} instruments</div>
                <div>
                  {activeUniverse
                    ? activeUniverse.as_of
                      ? `As of ${activeUniverse.as_of}`
                      : "Persisted Universe"
                    : "All active equities"}
                </div>
              </div>
            )}
          </div>

          <FilterGroup label="Universe">
            <FilterButton
              active={selectedUniverse === null}
              onClick={() => {
                setSelectedUniverse(null)
                setActiveSector(ALL_SECTORS)
                setOffset(0)
              }}
            >
              All Equities
            </FilterButton>
            {equityUniverses.map(universe => (
                <FilterButton
                  key={universe.code}
                  active={selectedUniverse === universe.code}
                  onClick={() => {
                    setSelectedUniverse(universe.code)
                    setActiveSector(ALL_SECTORS)
                    setOffset(0)
                  }}
                >
                  {universe.name} ({fmtInt(universe.active_instrument_count)})
                </FilterButton>
            ))}
          </FilterGroup>

          {sectorOptions.length > 0 && (
            <FilterGroup label="Sector">
              {sectorOptions.map(option => (
                <FilterButton
                  key={option.sector}
                  active={activeSector === option.sector}
                  onClick={() => {
                    setActiveSector(option.sector)
                    setOffset(0)
                  }}
                >
                  {option.sector === ALL_SECTORS ? "All Sectors" : option.sector} ({fmtInt(option.count)})
                </FilterButton>
              ))}
            </FilterGroup>
          )}
        </div>

        <div className="mt-5 space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-sm font-semibold">
                {activeUniverse ? `${activeUniverse.name} Instruments` : "All Equity Instruments"}
              </h2>
              <p className="text-xs text-muted-foreground mt-1">
                {activeUniverse
                  ? activeUniverse.description
                  : "All active equity instruments; no synthetic all-market Universe is required."}
              </p>
            </div>

            <label className="relative block w-full lg:w-80">
              <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={e => {
                  setQuery(e.target.value)
                  setOffset(0)
                }}
                placeholder="Search ticker, name, sector..."
                className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm text-foreground focus:outline-none focus:border-ring"
              />
            </label>
          </div>

          {isFetching && <LoadingBar />}

          {error && !isFetching && (
            <div className="rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-300">
              {(error as Error).message}
            </div>
          )}

          {data && !isFetching && (
            <InstrumentTable rows={data.instruments} />
          )}
          {data && !isFetching && (
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

function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
        {label}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {children}
      </div>
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
      onClick={onClick}
      className={cn(
        "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground"
      )}
    >
      {children}
    </button>
  )
}

function LoadingBar() {
  return (
    <div className="h-1 bg-muted overflow-hidden rounded-full">
      <div className="h-full w-1/3 bg-primary animate-pulse" />
    </div>
  )
}
