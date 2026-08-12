import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { InstrumentTable } from "@/components/instrument/InstrumentTable"
import { Pagination } from "@/components/ui/Pagination"
import { Sidebar } from "@/components/Sidebar"
import {
  companiesApi,
  companyUniversesApi,
  type CompanyUniverseId,
} from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"
import { useDebouncedValue } from "@/lib/useDebouncedValue"

const ALL_SECTORS = "ALL"
const ALL_SOURCES = "ALL"
const PAGE_SIZE = 50
const FEATURED_LIST_IDS: CompanyUniverseId[] = ["US_ALL", "VN_ALL"]
const SOURCE_ORDER = [
  "US100", "US500", "US2000", "US30",
  "VNALL", "VN100", "VN30", "VNMID", "VNSML",
]
export function InstrumentsPage() {
  const [selectedListId, setSelectedListId] = useState<CompanyUniverseId>("US_ALL")
  const activeListId = selectedListId
  const [activeSource, setActiveSource] = useState(ALL_SOURCES)
  const [activeSector, setActiveSector] = useState(ALL_SECTORS)
  const [query, setQuery] = useState("")
  const [offset, setOffset] = useState(0)
  const debouncedQuery = useDebouncedValue(query.trim(), 300)
  const requestedUniverse = (
    activeSource === ALL_SOURCES ? activeListId : activeSource
  ) as CompanyUniverseId

  const { data: availableLists } = useQuery({
    queryKey: ["instrument-universes"],
    queryFn: companyUniversesApi,
    retry: false,
  })

  const { data: list, isFetching, error } = useQuery({
    queryKey: [
      "instrument-list",
      requestedUniverse,
      activeSector,
      debouncedQuery,
      offset,
    ],
    queryFn: () => companiesApi({
      universe: requestedUniverse,
      sector: activeSector === ALL_SECTORS ? undefined : activeSector,
      search: debouncedQuery || undefined,
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

  const sourceOptions = useMemo(() => {
    if (!data) return []
    return [
      { id: ALL_SOURCES, label: "All", count: data.facets.all_count },
      ...data.facets.universes
        .map(facet => ({
          id: facet.value,
          label: listBadgeLabel(facet.value),
          count: facet.count,
        }))
        .sort((a, b) => sourceOrder(a.id) - sourceOrder(b.id) || a.id.localeCompare(b.id)),
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
                Tradable US and Vietnam securities in synchronized instrument universes.
              </p>
            </div>
            {data && (
              <div className="text-xs text-muted-foreground text-right">
                <div>{fmtInt(data.total)} instruments</div>
                <div>{data.as_of ? `As of ${data.as_of}` : "Static list"}</div>
              </div>
            )}
          </div>

          <FilterGroup label="Saved list">
            {FEATURED_LIST_IDS.map(listId => {
              const summary = availableLists?.universes.find(item => item.id === listId)
              return (
                <FilterButton
                  key={listId}
                  active={activeListId === listId}
                  onClick={() => {
                    setSelectedListId(listId)
                    setActiveSource(ALL_SOURCES)
                    setActiveSector(ALL_SECTORS)
                    setQuery("")
                    setOffset(0)
                  }}
                >
                  {savedListLabel(listId)}{summary ? ` (${fmtInt(summary.company_count)})` : ""}
                </FilterButton>
              )
            })}
          </FilterGroup>

          {sourceOptions.length > 2 && (
            <FilterGroup label="Index">
              {sourceOptions.map(option => (
                <FilterButton
                  key={option.id}
                  active={activeSource === option.id}
                  onClick={() => {
                    setActiveSource(option.id)
                    setActiveSector(ALL_SECTORS)
                    setOffset(0)
                  }}
                >
                  {option.label} ({fmtInt(option.count)})
                </FilterButton>
              ))}
            </FilterGroup>
          )}

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
                {data ? instrumentListName(data.id) : "Instrument List"}
              </h2>
              <p className="text-xs text-muted-foreground mt-1">
                {data
                  ? instrumentListDescription(data.id)
                  : "Choose a universe to view its instruments."}
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
            <InstrumentTable rows={data.companies} />
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

function sourceOrder(source: string): number {
  const index = SOURCE_ORDER.indexOf(source)
  return index === -1 ? SOURCE_ORDER.length : index
}

function savedListLabel(listId: CompanyUniverseId): string {
  if (listId === "US_ALL") return "US Instruments"
  if (listId === "VN_ALL") return "VN Instruments"
  return listId
}


function instrumentListName(listId: CompanyUniverseId): string {
  if (listId === "US_ALL") return "US Instruments"
  if (listId === "VN_ALL") return "VN Instruments"
  return `${listBadgeLabel(listId)} Instruments`
}


function instrumentListDescription(listId: CompanyUniverseId): string {
  if (listId === "US_ALL") {
    return "All saved US instruments merged without duplicate canonical tickers."
  }
  if (listId === "VN_ALL") {
    return "All saved Vietnam instruments merged without duplicate canonical tickers."
  }
  return `Current instruments in the ${listBadgeLabel(listId)} universe.`
}


function listBadgeLabel(list: string): string {
  if (list === "US100") return "Nasdaq 100"
  if (list === "US500") return "S&P 500"
  if (list === "US2000") return "Russell 2000"
  if (list === "US30") return "Dow Jones"
  if (list === "VNMID") return "VNMidCap"
  if (list === "VNSML") return "VNSmallCap"
  if (list === "VNALL") return "VNAllshare"
  return list
}


function LoadingBar() {
  return (
    <div className="h-1 bg-muted overflow-hidden rounded-full">
      <div className="h-full w-1/3 bg-primary animate-pulse" />
    </div>
  )
}
