import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { BarChart3, Check, Search } from "lucide-react"

import { Sidebar } from "@/components/Sidebar"
import { UniverseStatsChart } from "@/components/universe-stats/UniverseStatsChart"
import {
  universeStatsApi,
  universesApi,
  type UniverseStatsResult,
} from "@/lib/api"
import { cn } from "@/lib/utils"
import { AnalysisPanel } from "@/components/analysis/AnalysisPanel"


export function UniverseStatsPage() {
  const [search, setSearch] = useState("")
  const [selectedCodes, setSelectedCodes] = useState<string[]>([])
  const universes = useQuery({ queryKey: ["universes"], queryFn: universesApi })
  const stats = useMutation({ mutationFn: universeStatsApi })
  const visibleUniverses = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    return universes.data?.universes.filter(universe => (
      !query || [universe.code, universe.name, universe.description]
        .some(value => value.toLocaleLowerCase().includes(query))
    )) ?? []
  }, [search, universes.data])

  const toggleUniverse = (code: string) => {
    setSelectedCodes(current => current.includes(code)
      ? current.filter(value => value !== code)
      : [...current, code])
    stats.reset()
  }

  const controls = (
    <div className="space-y-4">
      <div>
        <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Universes
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
        {stats.isPending ? "Building statistics…" : `Build stats${selectedCodes.length ? ` (${selectedCodes.length})` : ""}`}
      </button>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <AnalysisPanel label="Universe selection">{controls}</AnalysisPanel>
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <header className="border-b border-border pb-5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Cross-sectional analysis
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Universe Stats</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Compare the median member distance from trailing 200-session closing highs and lows.
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
        {!stats.data && !stats.isPending && !stats.error && <UniverseStatsEmptyState />}
        {stats.data && (
          <UniverseStatsResults
            results={stats.data.results}
            errors={stats.data.errors}
            minimumCoverage={stats.data.minimum_coverage_pct}
            historyYears={stats.data.history_years}
          />
        )}
      </main>
    </div>
  )
}


function UniverseStatsEmptyState() {
  return (
    <div className="mt-6 flex min-h-72 flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card px-6 text-center">
      <BarChart3 size={28} className="text-muted-foreground/40" />
      <h2 className="mt-3 text-sm font-semibold">Choose one or more Universes</h2>
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
