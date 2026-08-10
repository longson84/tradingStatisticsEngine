import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { useSearchParams } from "react-router"
import { InstrumentTable } from "@/components/instrument/InstrumentTable"
import { Pagination } from "@/components/ui/Pagination"
import { Sidebar } from "@/components/Sidebar"
import {
  companiesApi,
  companyUniversesApi,
  marketHealthDistributionApi,
  type CompanyUniverseId,
  type MarketHealthMarket,
  type MarketHealthStockDistance,
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
const HEALTH_UNIVERSES: MarketHealthMarket["universe"][] = [
  "US500", "US2000", "US100",
  "VNALL", "VN100", "VN30", "VNMID", "VNSML",
]

interface HealthDrilldown {
  universe: MarketHealthMarket["universe"]
  date: string
  window: number
  min_distance: number | null
  max_distance: number | null
}

export function InstrumentsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const searchKey = searchParams.toString()
  const drilldown = useMemo(
    () => parseHealthDrilldown(new URLSearchParams(searchKey)),
    [searchKey],
  )
  const [selectedListId, setSelectedListId] = useState<CompanyUniverseId>("US_ALL")
  const activeListId: CompanyUniverseId = drilldown?.universe ?? selectedListId
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
      drilldown,
      offset,
    ],
    queryFn: () => companiesApi({
      universe: requestedUniverse,
      sector: activeSector === ALL_SECTORS ? undefined : activeSector,
      search: debouncedQuery || undefined,
      offset: drilldown ? 0 : offset,
      limit: drilldown ? 5000 : PAGE_SIZE,
    }),
    placeholderData: previous => previous,
    retry: false,
  })

  const health = useQuery({
    queryKey: ["company-health-drilldown", drilldown],
    queryFn: () => marketHealthDistributionApi(drilldown!),
    enabled: drilldown != null,
    retry: false,
  })

  const healthBySymbol = useMemo<Map<string, MarketHealthStockDistance>>(() => new Map(
    health.data?.stocks.map(stock => [stock.symbol, stock]) ?? []
  ), [health.data])

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

  const filteredRows = useMemo(() => {
    if (!data) return []
    const rows = data.companies.filter(row => {
      if (drilldown && !healthBySymbol.has(row.ticker)) return false
      return true
    })
    if (!drilldown) return rows
    return rows.sort((a, b) => (
      healthBySymbol.get(b.ticker)?.distance ?? -Infinity
    ) - (
      healthBySymbol.get(a.ticker)?.distance ?? -Infinity
    ))
  }, [data, drilldown, healthBySymbol])

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="flex flex-col gap-4 pb-4 border-b border-border">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Instruments</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Tradable US and Vietnam securities in the saved market universes.
              </p>
            </div>
            {data && (
              <div className="text-xs text-muted-foreground text-right">
                <div>{fmtInt(drilldown ? healthBySymbol.size : data.total)} instruments</div>
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
                    setSearchParams({})
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
          {drilldown && (
            <div className="flex items-center justify-between gap-4 rounded-lg border border-primary/25 bg-primary/5 px-4 py-3">
              <div>
                <div className="text-sm font-semibold">Market Health drill-down</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {drilldown.universe} · {distanceRangeLabel(drilldown.min_distance, drilldown.max_distance)} · {drilldown.date}
                </div>
              </div>
              <button
                onClick={() => {
                  setSearchParams({})
                  setSelectedListId("US_ALL")
                  setOffset(0)
                }}
                className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-accent"
              >
                Clear drill-down
              </button>
            </div>
          )}
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-sm font-semibold">
                {data ? instrumentListName(data.id) : "Instrument List"}
              </h2>
              <p className="text-xs text-muted-foreground mt-1">
                {data
                  ? instrumentListDescription(data.id)
                  : "Choose a market universe to view its instruments."}
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

          {health.error && (
            <div className="rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-300">
              {health.error.message}
            </div>
          )}

          {data && !isFetching && !health.isFetching && (
            <InstrumentTable
              rows={filteredRows}
              healthBySymbol={drilldown ? healthBySymbol : undefined}
            />
          )}
          {data && !drilldown && !isFetching && (
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


function parseHealthDrilldown(params: URLSearchParams): HealthDrilldown | null {
  const list = params.get("list")
  const date = params.get("date")
  if (!list || !date || !HEALTH_UNIVERSES.includes(list as MarketHealthMarket["universe"])) {
    return null
  }
  const window = Number(params.get("window") ?? 200)
  const min = params.get("min_distance")
  const max = params.get("max_distance")
  return {
    universe: list as MarketHealthMarket["universe"],
    date,
    window: Number.isFinite(window) ? window : 200,
    min_distance: min == null ? null : Number(min),
    max_distance: max == null ? null : Number(max),
  }
}


function distanceRangeLabel(minimum: number | null, maximum: number | null): string {
  if (minimum == null) return `Below ${maximum}%`
  if (maximum == null) return `0% to ${minimum}%`
  return `${maximum}% to ${minimum}%`
}

function LoadingBar() {
  return (
    <div className="h-1 bg-muted overflow-hidden rounded-full">
      <div className="h-full w-1/3 bg-primary animate-pulse" />
    </div>
  )
}
