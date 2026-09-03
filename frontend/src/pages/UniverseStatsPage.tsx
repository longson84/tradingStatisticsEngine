import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowDown, ArrowUp, ArrowUpDown, BarChart3, Check, ListPlus, Search } from "lucide-react"

import { Sidebar } from "@/components/Sidebar"
import { UniverseStatsChart } from "@/components/universe-stats/UniverseStatsChart"
import {
  universeStatsApi,
  universesApi,
  createWatchlistApi,
  updateWatchlistApi,
  watchlistApi,
  watchlistsApi,
  type UniverseStatsResult,
} from "@/lib/api"
import { cn } from "@/lib/utils"
import { AnalysisPanel } from "@/components/analysis/AnalysisPanel"
import { usePersistedAnalysis } from "@/lib/use-persisted-analysis"


type UniverseStatsView = "breadth" | "member-performance"


export function UniverseStatsPage({ view }: { view: UniverseStatsView }) {
  const isMemberPerformance = view === "member-performance"
  const [search, setSearch] = useState("")
  const [selectedCodes, setSelectedCodes] = useState<string[]>([])
  const universes = useQuery({ queryKey: ["universes"], queryFn: universesApi })
  const stats = usePersistedAnalysis({
    storageKey: `universe-stats.${view}`,
    mutationFn: universeStatsApi,
  })
  const visibleUniverses = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    return universes.data?.universes.filter(universe => (
      !query || [universe.code, universe.name, universe.description]
        .some(value => value.toLocaleLowerCase().includes(query))
    )) ?? []
  }, [search, universes.data])

  const toggleUniverse = (code: string) => {
    setSelectedCodes(current => current.includes(code)
      ? []
      : isMemberPerformance
        ? [code]
        : [...current, code])
    stats.reset()
  }

  const controls = (
    <div className="space-y-4">
      <div>
        <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          {isMemberPerformance ? "Universe" : "Universes"}
        </label>
        <label className="relative block">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={event => setSearch(event.target.value)}
            placeholder="Search universes"
            className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
          />
        </label>
      </div>

      <div className="max-h-[45vh] space-y-1.5 overflow-y-auto pr-1">
        {universes.isPending && <p className="text-xs text-muted-foreground">Loading universes…</p>}
        {universes.error && <p className="text-xs text-destructive">{universes.error.message}</p>}
        {visibleUniverses.map(universe => {
          const selected = selectedCodes.includes(universe.code)
          return (
            <button
              key={universe.code}
              type="button"
              onClick={() => toggleUniverse(universe.code)}
              aria-pressed={selected}
              className={cn(
                "flex w-full items-start gap-2 rounded-md border px-2.5 py-2 text-left transition-colors",
                selected ? "border-primary bg-primary/10" : "border-border hover:bg-accent",
              )}
            >
              <span className={cn(
                "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                selected ? "border-primary bg-primary text-primary-foreground" : "border-input",
              )}>
                {selected && <Check size={11} />}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-xs font-medium">{universe.name}</span>
                <span className="block text-[10px] text-muted-foreground">
                  {universe.code} · {universe.active_instrument_count.toLocaleString()} instruments
                </span>
              </span>
            </button>
          )
        })}
      </div>

      <button
        type="button"
        onClick={() => stats.mutate({ universe_codes: selectedCodes })}
        disabled={selectedCodes.length === 0 || stats.isPending}
        className="w-full rounded-md bg-primary py-2.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {stats.isPending
          ? "Building statistics…"
          : isMemberPerformance
            ? "View member performance"
            : `Build breadth${selectedCodes.length ? ` (${selectedCodes.length})` : ""}`}
      </button>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <AnalysisPanel label={isMemberPerformance ? "Universe selection" : "Universe comparison"}>{controls}</AnalysisPanel>
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <header className="border-b border-border pb-5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Universe Stats
          </div>
          <h1 className="text-2xl font-bold tracking-tight">
            {isMemberPerformance ? "Member Performance" : "Breadth Analysis"}
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            {isMemberPerformance
              ? "Compare current returns and distance from the 200-session closing high for every member."
              : "Compare the median member distance from trailing 200-session closing highs and lows."}
          </p>
        </header>

        {stats.isPending && (
          <div className="mt-5 h-1 overflow-hidden rounded bg-muted">
            <div className="h-full w-1/3 animate-pulse bg-primary" />
          </div>
        )}
        {stats.error && (
          <div className="mt-5 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {stats.error.message}
          </div>
        )}
        {!stats.data && !stats.isPending && !stats.error && (
          <UniverseStatsEmptyState memberPerformance={isMemberPerformance} />
        )}
        {stats.data && !isMemberPerformance && (
          <UniverseStatsResults
            results={stats.data.results}
            errors={stats.data.errors}
            minimumCoverage={stats.data.minimum_coverage_pct}
            historyYears={stats.data.history_years}
          />
        )}
        {stats.data && isMemberPerformance && (
          <MemberPerformanceResults results={stats.data.results} errors={stats.data.errors} />
        )}
      </main>
    </div>
  )
}


function UniverseStatsEmptyState({ memberPerformance }: { memberPerformance: boolean }) {
  return (
    <div className="mt-6 flex min-h-72 flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card px-6 text-center">
      <BarChart3 size={28} className="text-muted-foreground/40" />
      <h2 className="mt-3 text-sm font-semibold">
        {memberPerformance ? "Choose one Universe" : "Choose one or more Universes"}
      </h2>
      <p className="mt-1 max-w-md text-xs leading-5 text-muted-foreground">
        The charts are calculated on demand from canonical PostgreSQL price observations.
      </p>
    </div>
  )
}


function UniverseStatsResults({
  results,
  errors,
  minimumCoverage,
  historyYears,
}: {
  results: UniverseStatsResult[]
  errors: Array<{ universe_code: string; message: string }>
  minimumCoverage: number
  historyYears: number
}) {
  return (
    <div className="mt-6 space-y-5">
      <div className="rounded-lg border border-border bg-card px-4 py-3 text-xs leading-5 text-muted-foreground">
        Historical values use today&apos;s Universe membership (current snapshot), not point-in-time constituents.
        A date is shown when at least {minimumCoverage.toFixed(0)}% of current members have a valid 200-session observation.
        The chart displays up to {historyYears} years.
      </div>

      {errors.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
          {errors.map(error => (
            <div key={error.universe_code}>
              <span className="font-semibold">{error.universe_code}:</span> {error.message}
            </div>
          ))}
        </div>
      )}

      {results.length > 0 && (
        <>
          <CombinedMetricPanel results={results} />
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {results.map(result => <UniverseSummary key={result.universe_code} result={result} />)}
          </div>
        </>
      )}
      {results.length === 0 && errors.length > 0 && (
        <div className="rounded-lg border border-dashed border-border bg-card p-8 text-center text-sm text-muted-foreground">
          None of the selected Universes has enough canonical price history to build the statistic.
        </div>
      )}
    </div>
  )
}


interface InstrumentReturnRow {
  instrumentId: number
  symbol: string
  displayName: string
  universeCodes: string[]
  lastDate: string
  latestClose: number
  return1w: number | null
  return1m: number | null
  return3m: number | null
  distanceFromHigh200d: number | null
  high200dDate: string | null
}


function MemberPerformanceResults({
  results,
  errors,
}: {
  results: UniverseStatsResult[]
  errors: Array<{ universe_code: string; message: string }>
}) {
  return (
    <div className="mt-6 space-y-5">
      {errors.map(error => (
        <div key={error.universe_code} className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
          <span className="font-semibold">{error.universe_code}:</span> {error.message}
        </div>
      ))}
      {results.length > 0 && <InstrumentReturnsTable results={results} />}
    </div>
  )
}


type ReturnSortKey = "return1w" | "return1m" | "return3m" | "distanceFromHigh200d"


function InstrumentReturnsTable({ results }: { results: UniverseStatsResult[] }) {
  const queryClient = useQueryClient()
  const [sortKey, setSortKey] = useState<ReturnSortKey>("return1w")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc")
  const [instrumentSearch, setInstrumentSearch] = useState("")
  const [selectedInstrumentIds, setSelectedInstrumentIds] = useState<Set<number>>(new Set())
  const [watchlistId, setWatchlistId] = useState("")
  const [newWatchlistName, setNewWatchlistName] = useState("")
  const watchlists = useQuery({ queryKey: ["watchlists"], queryFn: watchlistsApi })
  const allRows = useMemo(() => {
    const byInstrument = new Map<number, InstrumentReturnRow>()
    for (const result of results) {
      for (const instrument of result.instruments) {
        const existing = byInstrument.get(instrument.instrument_id)
        if (existing) {
          if (!existing.universeCodes.includes(result.universe_code)) {
            existing.universeCodes.push(result.universe_code)
          }
          continue
        }
        byInstrument.set(instrument.instrument_id, {
          instrumentId: instrument.instrument_id,
          symbol: instrument.symbol,
          displayName: instrument.display_name,
          universeCodes: [result.universe_code],
          lastDate: instrument.last_date,
          latestClose: instrument.latest_close,
          return1w: instrument.return_1w,
          return1m: instrument.return_1m,
          return3m: instrument.return_3m,
          distanceFromHigh200d: instrument.distance_from_high_200d,
          high200dDate: instrument.high_200d_date,
        })
      }
    }
    return [...byInstrument.values()].sort((left, right) => {
      const leftValue = left[sortKey]
      const rightValue = right[sortKey]
      if (leftValue == null && rightValue == null) return left.symbol.localeCompare(right.symbol)
      if (leftValue == null) return 1
      if (rightValue == null) return -1
      const comparison = leftValue - rightValue
      return comparison === 0
        ? left.symbol.localeCompare(right.symbol)
        : sortDirection === "asc" ? comparison : -comparison
    })
  }, [results, sortDirection, sortKey])
  const rows = useMemo(() => {
    const query = instrumentSearch.trim().toLocaleLowerCase()
    if (!query) return allRows
    return allRows.filter(row => (
      row.symbol.toLocaleLowerCase().includes(query)
      || row.displayName.toLocaleLowerCase().includes(query)
    ))
  }, [allRows, instrumentSearch])
  const selectedRows = allRows.filter(row => selectedInstrumentIds.has(row.instrumentId))
  const allVisibleSelected = rows.length > 0
    && rows.every(row => selectedInstrumentIds.has(row.instrumentId))
  const addToWatchlist = useMutation({
    mutationFn: async (destination: { watchlistId: number } | { name: string }) => {
      if ("name" in destination) {
        const created = await createWatchlistApi({
          name: destination.name,
          description: "",
          instrument_ids: selectedRows.map(row => row.instrumentId),
        })
        return {
          added: selectedRows.length,
          alreadyPresent: 0,
          name: created.name,
          watchlistId: created.id,
        }
      }
      const targetId = destination.watchlistId
      const watchlist = await queryClient.fetchQuery({
        queryKey: ["watchlist", targetId],
        queryFn: () => watchlistApi(targetId),
        staleTime: 0,
      })
      const existingIds = new Set(watchlist.members.map(member => member.instrument_id))
      const additions = selectedRows
        .map(row => row.instrumentId)
        .filter(instrumentId => !existingIds.has(instrumentId))
      if (additions.length > 0) {
        await updateWatchlistApi(targetId, {
          name: watchlist.name,
          description: watchlist.description,
          instrument_ids: [
            ...watchlist.members.map(member => member.instrument_id),
            ...additions,
          ],
        })
      }
      return {
        added: additions.length,
        alreadyPresent: selectedRows.length - additions.length,
        name: watchlist.name,
        watchlistId: watchlist.id,
      }
    },
    onSuccess: async result => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["watchlists"] }),
        queryClient.invalidateQueries({ queryKey: ["watchlist", result.watchlistId] }),
      ])
      setWatchlistId(String(result.watchlistId))
      setNewWatchlistName("")
      setSelectedInstrumentIds(new Set())
    },
  })

  const changeSort = (key: ReturnSortKey) => {
    if (key === sortKey) {
      setSortDirection(direction => direction === "desc" ? "asc" : "desc")
      return
    }
    setSortKey(key)
    setSortDirection("desc")
  }
  const toggleInstrument = (instrumentId: number) => {
    setSelectedInstrumentIds(current => {
      const next = new Set(current)
      if (next.has(instrumentId)) next.delete(instrumentId)
      else next.add(instrumentId)
      return next
    })
    addToWatchlist.reset()
  }
  const toggleAll = () => {
    setSelectedInstrumentIds(current => {
      const next = new Set(current)
      if (allVisibleSelected) {
        for (const row of rows) next.delete(row.instrumentId)
      } else {
        for (const row of rows) next.add(row.instrumentId)
      }
      return next
    })
    addToWatchlist.reset()
  }

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex flex-col justify-between gap-3 border-b border-border px-5 py-4 xl:flex-row xl:items-end">
        <div>
          <h2 className="text-base font-semibold">Instrument returns</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Latest close-to-close returns over 5, 21, and 63 trading sessions.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-xs text-muted-foreground">
            {selectedRows.length > 0
              ? `${selectedRows.length.toLocaleString()} of ${rows.length.toLocaleString()} selected`
              : `${rows.length.toLocaleString()} instruments`}
          </span>
          <select
            value={watchlistId}
            onChange={event => {
              setWatchlistId(event.target.value)
              if (event.target.value !== "new") setNewWatchlistName("")
              addToWatchlist.reset()
            }}
            className="h-9 min-w-48 rounded-md border border-input bg-background px-3 text-xs"
            aria-label="Destination watchlist"
          >
            <option value="">Choose watchlist…</option>
            <option value="new">＋ Create new watchlist…</option>
            {watchlists.data?.watchlists.map(watchlist => (
              <option key={watchlist.id} value={watchlist.id}>
                {watchlist.name} ({watchlist.member_count.toLocaleString()})
              </option>
            ))}
          </select>
          {watchlistId === "new" && (
            <input
              value={newWatchlistName}
              onChange={event => {
                setNewWatchlistName(event.target.value)
                addToWatchlist.reset()
              }}
              onKeyDown={event => {
                if (
                  event.key === "Enter"
                  && selectedRows.length > 0
                  && newWatchlistName.trim()
                  && !addToWatchlist.isPending
                ) {
                  addToWatchlist.mutate({ name: newWatchlistName.trim() })
                }
              }}
              maxLength={100}
              placeholder="New watchlist name"
              aria-label="New watchlist name"
              className="h-9 min-w-56 rounded-md border border-input bg-background px-3 text-xs focus:border-ring focus:outline-none"
              autoFocus
            />
          )}
          <button
            type="button"
            onClick={() => addToWatchlist.mutate(
              watchlistId === "new"
                ? { name: newWatchlistName.trim() }
                : { watchlistId: Number(watchlistId) },
            )}
            disabled={
              selectedRows.length === 0
              || !watchlistId
              || (watchlistId === "new" && !newWatchlistName.trim())
              || addToWatchlist.isPending
            }
            className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ListPlus size={14} />
            {addToWatchlist.isPending
              ? watchlistId === "new" ? "Creating…" : "Adding…"
              : watchlistId === "new" ? "Create and add" : "Add to watchlist"}
          </button>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
        <label className="relative block w-full max-w-md">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={instrumentSearch}
            onChange={event => setInstrumentSearch(event.target.value)}
            placeholder="Search by symbol or instrument name"
            className="h-9 w-full rounded-md border border-input bg-background pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
          />
        </label>
        <span className="text-xs text-muted-foreground">
          Showing {rows.length.toLocaleString()} of {allRows.length.toLocaleString()}
        </span>
      </div>
      {watchlists.data?.watchlists.length === 0 && (
        <div className="border-b border-border bg-amber-500/10 px-5 py-2 text-xs">
          No watchlists yet. Choose “Create new watchlist…” above to create one from your selection.
        </div>
      )}
      {addToWatchlist.isSuccess && (
        <div className="border-b border-border bg-emerald-500/10 px-5 py-2 text-xs text-emerald-700 dark:text-emerald-300">
          Added {addToWatchlist.data.added.toLocaleString()} instrument{addToWatchlist.data.added === 1 ? "" : "s"} to {addToWatchlist.data.name}.
          {addToWatchlist.data.alreadyPresent > 0
            ? ` ${addToWatchlist.data.alreadyPresent.toLocaleString()} already present.`
            : ""}
        </div>
      )}
      {addToWatchlist.error && (
        <div className="border-b border-destructive/30 bg-destructive/10 px-5 py-2 text-xs text-destructive">
          {addToWatchlist.error.message}
        </div>
      )}
      <div className="max-h-[70vh] overflow-auto">
        <table className="w-full min-w-[1040px] text-sm">
          <thead className="sticky top-0 z-10 bg-muted/95 text-[10px] uppercase tracking-wide text-muted-foreground backdrop-blur">
            <tr>
              <th className="w-10 px-3 py-2 text-center font-medium">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={toggleAll}
                  aria-label={allVisibleSelected ? "Clear visible instruments" : "Select visible instruments"}
                  className="size-4 rounded border-input accent-primary"
                />
              </th>
              <th className="px-4 py-2 text-left font-medium">Symbol</th>
              <th className="px-4 py-2 text-left font-medium">Instrument name</th>
              <th className="px-4 py-2 text-left font-medium">Universe</th>
              <th className="px-4 py-2 text-left font-medium">As of</th>
              <th className="px-4 py-2 text-right font-medium">Latest close</th>
              <ReturnSortHeader label="1W" sortKey="return1w" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <ReturnSortHeader label="1M" sortKey="return1m" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <ReturnSortHeader label="3M" sortKey="return3m" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <ReturnSortHeader
                label="From high 200D"
                sortKey="distanceFromHigh200d"
                activeKey={sortKey}
                direction={sortDirection}
                onSort={changeSort}
              />
              <th className="px-4 py-2 text-left font-medium">Highest high on date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map(row => (
              <tr
                key={row.instrumentId}
                className={cn(
                  "hover:bg-muted/30",
                  selectedInstrumentIds.has(row.instrumentId) && "bg-primary/5",
                )}
              >
                <td className="px-3 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={selectedInstrumentIds.has(row.instrumentId)}
                    onChange={() => toggleInstrument(row.instrumentId)}
                    aria-label={`Select ${row.symbol}`}
                    className="size-4 rounded border-input accent-primary"
                  />
                </td>
                <td className="px-4 py-2 font-semibold">{row.symbol}</td>
                <td className="max-w-72 truncate px-4 py-2" title={row.displayName}>
                  {row.displayName}
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground">
                  {[...row.universeCodes].sort().join(", ")}
                </td>
                <td className="px-4 py-2 tabular-nums text-muted-foreground">{row.lastDate}</td>
                <td className="px-4 py-2 text-right tabular-nums">{formatClose(row.latestClose)}</td>
                <ReturnCell value={row.return1w} />
                <ReturnCell value={row.return1m} />
                <ReturnCell value={row.return3m} />
                <ReturnCell value={row.distanceFromHigh200d} />
                <td className="px-4 py-2 tabular-nums text-muted-foreground">{row.high200dDate ?? "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={11} className="px-5 py-10 text-center text-sm text-muted-foreground">
                  No instruments match this search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}


function ReturnSortHeader({
  label,
  sortKey,
  activeKey,
  direction,
  onSort,
}: {
  label: string
  sortKey: ReturnSortKey
  activeKey: ReturnSortKey
  direction: "asc" | "desc"
  onSort: (key: ReturnSortKey) => void
}) {
  const active = sortKey === activeKey
  const Icon = !active ? ArrowUpDown : direction === "asc" ? ArrowUp : ArrowDown
  return (
    <th
      className="px-4 py-2 text-right font-medium"
      aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className="ml-auto flex items-center gap-1 hover:text-foreground"
      >
        {label}
        <Icon size={12} />
      </button>
    </th>
  )
}


function ReturnCell({ value }: { value: number | null }) {
  return (
    <td className={cn(
      "px-4 py-2 text-right font-medium tabular-nums",
      value != null && value > 0 && "text-emerald-600 dark:text-emerald-400",
      value != null && value < 0 && "text-red-600 dark:text-red-400",
    )}>
      {value == null ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`}
    </td>
  )
}


function formatClose(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 })
}


function CombinedMetricPanel({ results }: { results: UniverseStatsResult[] }) {
  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="flex flex-col justify-between gap-3 border-b border-border pb-4 lg:flex-row lg:items-start">
        <div>
          <h2 className="text-base font-semibold">200-session Universe distances</h2>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground">
            The High 200 and Low 200 metrics share one time scale. Move the cursor in either pane to inspect the same date across both.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
          {results.map((result, index) => {
            const latest = result.points[result.points.length - 1]
            return (
              <span key={result.universe_code} className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ background: chartColor(index) }} />
                <span className="font-medium">{result.universe_code}</span>
                <span className="text-muted-foreground">High</span>
                <span className="font-semibold tabular-nums">{latest.median_distance_from_high.toFixed(1)}%</span>
                <span className="text-muted-foreground">Low</span>
                <span className="font-semibold tabular-nums">{latest.median_distance_from_low.toFixed(1)}%</span>
              </span>
            )
          })}
        </div>
      </div>
      <div className="pt-4">
        <UniverseStatsChart results={results} />
      </div>
    </section>
  )
}


function UniverseSummary({ result }: { result: UniverseStatsResult }) {
  const latest = result.points[result.points.length - 1]
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{result.universe_name}</h3>
          <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">{result.universe_code}</p>
        </div>
        <div className="text-right text-xs tabular-nums">
          <div>{latest.eligible_count.toLocaleString()} eligible</div>
          <div className="text-muted-foreground">{latest.coverage_pct.toFixed(1)}% coverage</div>
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-3 text-xs">
        <SummaryDatum label="Members" value={result.member_count.toLocaleString()} />
        <SummaryDatum label="With history" value={result.instruments_with_history.toLocaleString()} />
        <SummaryDatum label="First chart date" value={result.first_date} />
        <SummaryDatum label="Latest chart date" value={result.last_date} />
      </dl>
    </section>
  )
}


function SummaryDatum({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium tabular-nums">{value}</dd>
    </div>
  )
}


function chartColor(index: number): string {
  return ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#ca8a04", "#db2777", "#4f46e5", "#0f766e"][index % 10]
}
