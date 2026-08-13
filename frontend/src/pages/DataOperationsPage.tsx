import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  CheckCircle2,
  DatabaseZap,
  ListChecks,
  ListTree,
  RefreshCw,
  Search,
  TriangleAlert,
} from "lucide-react"

import { Sidebar } from "@/components/Sidebar"
import { useSearchableSelectKeyboard } from "@/components/forms/useSearchableSelectKeyboard"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  dataOperationJobApi,
  dataOperationPriceCoverageApi,
  dataOperationPreviewApi,
  instrumentsApi,
  startDataOperationApi,
  universesApi,
  watchlistsApi,
  type InstrumentCatalogItem,
  type DataOperationDataset,
  type DataOperationJob,
  type DataOperationMode,
  type DataOperationScopeType,
  type InstrumentPriceCoverage,
} from "@/lib/api"
import { cn } from "@/lib/utils"


const SCOPE_OPTIONS: Array<{
  value: DataOperationScopeType
  label: string
  detail: string
  icon: typeof ListTree
}> = [
  {
    value: "universe",
    label: "Universe",
    detail: "System-managed membership",
    icon: ListTree,
  },
  {
    value: "watchlist",
    label: "Watchlist",
    detail: "Personal ordered selection",
    icon: ListChecks,
  },
  {
    value: "instrument",
    label: "Instrument",
    detail: "One exact canonical instrument",
    icon: DatabaseZap,
  },
]

const COVERAGE_PAGE_SIZE = 50


export function DataOperationsPage() {
  const queryClient = useQueryClient()
  const [scopeType, setScopeType] = useState<DataOperationScopeType>("universe")
  const [scopeId, setScopeId] = useState("")
  const [dataset, setDataset] = useState<DataOperationDataset>("prices")
  const [mode, setMode] = useState<DataOperationMode>("incremental")
  const [instrumentSearch, setInstrumentSearch] = useState("")
  const [selectedInstrument, setSelectedInstrument] = useState<InstrumentCatalogItem | null>(null)
  const [startedJob, setStartedJob] = useState<DataOperationJob | null>(null)
  const [coverageOffset, setCoverageOffset] = useState(0)

  const universes = useQuery({ queryKey: ["universes"], queryFn: universesApi })
  const watchlists = useQuery({ queryKey: ["watchlists"], queryFn: watchlistsApi })
  const normalizedSearch = instrumentSearch.trim()
  const instruments = useQuery({
    queryKey: ["data-operation-instruments", normalizedSearch],
    queryFn: () => instrumentsApi({
      search: normalizedSearch,
      has_price_history: false,
      limit: 20,
    }),
    enabled: scopeType === "instrument" && normalizedSearch.length >= 3,
  })
  const preview = useQuery({
    queryKey: ["data-operation-preview", scopeType, scopeId, dataset],
    queryFn: () => dataOperationPreviewApi({ scope_type: scopeType, scope_id: scopeId, dataset }),
    enabled: scopeId.length > 0,
  })
  const coverage = useQuery({
    queryKey: ["data-operation-price-coverage", scopeType, scopeId, coverageOffset],
    queryFn: () => dataOperationPriceCoverageApi({
      scope_type: scopeType,
      scope_id: scopeId,
      offset: coverageOffset,
      limit: COVERAGE_PAGE_SIZE,
    }),
    enabled: scopeId.length > 0 && dataset === "prices",
  })
  const start = useMutation({
    mutationFn: startDataOperationApi,
    onSuccess: job => setStartedJob(job),
  })
  const job = useQuery({
    queryKey: ["data-operation-job", startedJob?.id],
    queryFn: () => dataOperationJobApi(startedJob!.id),
    enabled: startedJob != null,
    initialData: startedJob ?? undefined,
    refetchInterval: query => {
      const status = query.state.data?.status
      return status === "queued" || status === "running" ? 1_000 : false
    },
  })
  const activeJob = job.data ?? startedJob

  useEffect(() => {
    if (activeJob?.status === "completed") {
      void queryClient.invalidateQueries({ queryKey: ["data-operation-price-coverage"] })
    }
  }, [activeJob?.id, activeJob?.status, queryClient])

  const chooseScope = (value: DataOperationScopeType) => {
    setScopeType(value)
    setScopeId("")
    setInstrumentSearch("")
    setSelectedInstrument(null)
    setStartedJob(null)
    setCoverageOffset(0)
  }
  const run = () => {
    if (!preview.data?.can_run) return
    start.mutate({ scope_type: scopeType, scope_id: scopeId, dataset, mode })
  }
  const running = activeJob?.status === "queued" || activeJob?.status === "running"

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <header className="mb-6 border-b border-border pb-5">
          <div className="flex items-center gap-2">
            <DatabaseZap size={21} className="text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Data Operations</h1>
          </div>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Preview coverage and update canonical PostgreSQL observations by collection or exact instrument.
          </p>
        </header>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
          <section className="rounded-xl border border-border bg-card p-5">
            <SectionLabel number="1" title="Choose the scope" />
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {SCOPE_OPTIONS.map(option => {
                const Icon = option.icon
                return (
                  <button
                    key={option.value}
                    onClick={() => chooseScope(option.value)}
                    className={cn(
                      "rounded-lg border p-3 text-left transition-colors",
                      scopeType === option.value
                        ? "border-primary bg-primary/10"
                        : "border-border hover:bg-accent",
                    )}
                  >
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <Icon size={15} /> {option.label}
                    </div>
                    <div className="mt-1 text-[11px] text-muted-foreground">{option.detail}</div>
                  </button>
                )
              })}
            </div>

            <div className="mt-4">
              {scopeType === "universe" && (
                <select
                  value={scopeId}
                  onChange={event => {
                    setScopeId(event.target.value)
                    setStartedJob(null)
                    setCoverageOffset(0)
                  }}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Choose a universe…</option>
                  {universes.data?.universes.map(universe => (
                    <option key={universe.id} value={universe.code}>
                      {universe.name} ({universe.active_instrument_count.toLocaleString()})
                    </option>
                  ))}
                </select>
              )}
              {scopeType === "watchlist" && (
                <select
                  value={scopeId}
                  onChange={event => {
                    setScopeId(event.target.value)
                    setStartedJob(null)
                    setCoverageOffset(0)
                  }}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Choose a watchlist…</option>
                  {watchlists.data?.watchlists.map(watchlist => (
                    <option key={watchlist.id} value={watchlist.id}>
                      {watchlist.name} ({watchlist.member_count.toLocaleString()})
                    </option>
                  ))}
                </select>
              )}
              {scopeType === "instrument" && (
                <InstrumentPicker
                  search={instrumentSearch}
                  onSearch={value => {
                    setInstrumentSearch(value)
                    setSelectedInstrument(null)
                    setScopeId("")
                    setStartedJob(null)
                    setCoverageOffset(0)
                  }}
                  selected={selectedInstrument}
                  instruments={instruments.data?.instruments ?? []}
                  loading={instruments.isFetching}
                  onSelect={instrument => {
                    setSelectedInstrument(instrument)
                    setInstrumentSearch(instrument.symbol)
                    setScopeId(String(instrument.id))
                    setCoverageOffset(0)
                  }}
                />
              )}
            </div>

            <SectionLabel number="2" title="Choose the operation" className="mt-7" />
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <ChoiceGroup
                label="Dataset"
                options={[
                  ["prices", "Prices"],
                  ["fundamentals", "Fundamentals"],
                ]}
                value={dataset}
                onChange={value => {
                  setDataset(value as DataOperationDataset)
                  setStartedJob(null)
                }}
              />
              <ChoiceGroup
                label="Mode"
                options={[
                  ["incremental", "Incremental"],
                  ["full", "Full history"],
                ]}
                value={mode}
                onChange={value => setMode(value as DataOperationMode)}
              />
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Button
                onClick={run}
                disabled={!preview.data?.can_run || start.isPending || running}
              >
                <RefreshCw className={start.isPending || running ? "animate-spin" : ""} />
                {mode === "full" ? "Build full history" : "Update data"}
              </Button>
              <span className="text-[11px] text-muted-foreground">
                Existing observations are upserted; failed downloads do not erase stored rows.
              </span>
            </div>
            {start.error && <ErrorMessage message={start.error.message} />}
          </section>

          <div className="space-y-5">
            <PreviewPanel preview={preview.data} loading={preview.isFetching} error={preview.error?.message} />
            {activeJob && <JobPanel job={activeJob} />}
          </div>
        </div>

        <section className="mt-5 rounded-lg border border-border bg-muted/20 px-4 py-3 text-xs leading-5 text-muted-foreground">
          Universe membership is read-only here. A data update resolves the current members, groups them by
          metadata-derived adapter, and updates observations by exact instrument ID; it never edits the
          Universe or Watchlist itself. Adapter-specific bulk limits protect provider capacity.
        </section>

        {dataset === "prices" && (
          <InstrumentCoverageTable
            coverage={coverage.data}
            loading={coverage.isFetching}
            error={coverage.error?.message}
            offset={coverageOffset}
            onOffsetChange={setCoverageOffset}
          />
        )}

      </main>
    </div>
  )
}


function InstrumentCoverageTable({
  coverage,
  loading,
  error,
  offset,
  onOffsetChange,
}: {
  coverage: Awaited<ReturnType<typeof dataOperationPriceCoverageApi>> | undefined
  loading: boolean
  error: string | undefined
  offset: number
  onOffsetChange: (offset: number) => void
}) {
  if (!coverage && !loading && !error) return null
  const first = coverage && coverage.total > 0 ? offset + 1 : 0
  const last = coverage ? Math.min(offset + coverage.instruments.length, coverage.total) : 0
  return (
    <section className="mt-5 rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <h2 className="text-base font-semibold">Instrument price coverage</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Stored and expected sessions are tracked per canonical instrument; collection totals are derived.
          </p>
        </div>
        {coverage && (
          <div className="flex flex-wrap gap-2">
            <CoverageCount label="Current" value={coverage.current_count} tone="current" />
            <CoverageCount label="Stale" value={coverage.stale_count} tone="stale" />
            <CoverageCount label="Missing" value={coverage.missing_count} tone="missing" />
            <CoverageCount label="No new bar" value={coverage.checked_no_new_bar_count} />
            <CoverageCount label="Failed checks" value={coverage.failed_count} tone="missing" />
          </div>
        )}
      </div>
      {loading && !coverage && <div className="m-5 h-1 animate-pulse rounded bg-primary/40" />}
      {error && <div className="px-5 pb-5"><ErrorMessage message={error} /></div>}
      {coverage && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1180px] text-left text-xs">
              <thead className="bg-muted/40 text-[10px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-semibold">Instrument</th>
                  <th className="px-4 py-3 font-semibold">First stored</th>
                  <th className="px-4 py-3 font-semibold">Last stored</th>
                  <th className="px-4 py-3 font-semibold">Expected</th>
                  <th className="px-4 py-3 text-right font-semibold">Sessions</th>
                  <th className="px-4 py-3 text-right font-semibold">Behind</th>
                  <th className="px-4 py-3 font-semibold">Coverage</th>
                  <th className="px-4 py-3 font-semibold">Last provider check</th>
                  <th className="px-4 py-3 font-semibold">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {coverage.instruments.map(row => <InstrumentCoverageRow key={row.instrument_id} row={row} />)}
              </tbody>
            </table>
          </div>
          {coverage.instruments.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-muted-foreground">
              This scope has no active instruments.
            </div>
          )}
          <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-3">
            <div className="text-xs text-muted-foreground">
              Showing {first.toLocaleString()}–{last.toLocaleString()} of {coverage.total.toLocaleString()}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0 || loading}
                onClick={() => onOffsetChange(Math.max(0, offset - COVERAGE_PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + COVERAGE_PAGE_SIZE >= coverage.total || loading}
                onClick={() => onOffsetChange(offset + COVERAGE_PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </section>
  )
}


function InstrumentCoverageRow({ row }: { row: InstrumentPriceCoverage }) {
  return (
    <tr className="hover:bg-muted/20">
      <td className="px-4 py-3">
        <div className="font-semibold">{row.symbol}</div>
        <div className="mt-0.5 text-[10px] text-muted-foreground">
          {[row.venue_code, formatInstrumentType(row.instrument_type)].filter(Boolean).join(" · ")}
        </div>
      </td>
      <td className="px-4 py-3 tabular-nums">{formatDate(row.first_stored_session)}</td>
      <td className="px-4 py-3 tabular-nums">{formatDate(row.last_stored_session)}</td>
      <td className="px-4 py-3 tabular-nums">{formatDate(row.expected_session)}</td>
      <td className="px-4 py-3 text-right tabular-nums">{row.stored_sessions.toLocaleString()}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        {row.expected_sessions_behind == null ? "—" : row.expected_sessions_behind.toLocaleString()}
      </td>
      <td className="px-4 py-3"><CoverageStatus status={row.coverage_status} /></td>
      <td className="px-4 py-3">
        <div className="capitalize">{formatRefreshOutcome(row.refresh_outcome)}</div>
        <div className="mt-0.5 text-[10px] text-muted-foreground">
          {row.last_checked_at ? new Date(row.last_checked_at).toLocaleString() : "Never checked"}
        </div>
      </td>
      <td className="px-4 py-3">
        <div>{row.coverage_source ?? "—"}</div>
        <div className="mt-0.5 text-[10px] text-muted-foreground">{row.price_basis}</div>
      </td>
    </tr>
  )
}


function CoverageStatus({ status }: { status: InstrumentPriceCoverage["coverage_status"] }) {
  return (
    <Badge variant={status === "current" ? "secondary" : status === "missing" ? "destructive" : "outline"}>
      {status[0].toUpperCase() + status.slice(1)}
    </Badge>
  )
}


function CoverageCount({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone?: InstrumentPriceCoverage["coverage_status"]
}) {
  return (
    <Badge variant={tone === "missing" ? "destructive" : tone === "current" ? "secondary" : "outline"}>
      {label} {value.toLocaleString()}
    </Badge>
  )
}


function formatDate(value: string | null | undefined) {
  return value ?? "—"
}


function formatInstrumentType(value: string) {
  return value.replaceAll("_", " ")
}


function formatRefreshOutcome(value: InstrumentPriceCoverage["refresh_outcome"]) {
  if (value == null) return "Not checked"
  return value.replaceAll("_", " ")
}


function InstrumentPicker({
  search,
  onSearch,
  selected,
  instruments,
  loading,
  onSelect,
}: {
  search: string
  onSearch: (value: string) => void
  selected: InstrumentCatalogItem | null
  instruments: InstrumentCatalogItem[]
  loading: boolean
  onSelect: (instrument: InstrumentCatalogItem) => void
}) {
  const showResults = search.trim().length >= 3 && selected == null
  const keyboard = useSearchableSelectKeyboard({
    items: instruments,
    open: showResults,
    resetKey: search,
    onSelect,
  })
  return (
    <div className="relative">
      <Search size={14} className="absolute left-3 top-3 text-muted-foreground" />
      <input
        value={search}
        onChange={event => onSearch(event.target.value)}
        onFocus={keyboard.onFocus}
        onKeyDown={keyboard.onKeyDown}
        placeholder="Type at least 3 characters"
        className="w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm"
        aria-label="Instrument"
        role="combobox"
        aria-autocomplete="list"
        aria-controls={keyboard.listboxId}
        aria-activedescendant={keyboard.activeOptionId}
        aria-expanded={keyboard.isOpen}
      />
      {keyboard.isOpen && (
        <div
          id={keyboard.listboxId}
          role="listbox"
          aria-label="Instrument results"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-border bg-popover p-1 shadow-xl"
        >
          {loading && <div className="px-3 py-2 text-xs text-muted-foreground">Searching…</div>}
          {!loading && instruments.map((instrument, index) => (
            <button
              key={instrument.id}
              id={keyboard.optionId(index)}
              ref={keyboard.optionRef(index)}
              type="button"
              role="option"
              aria-selected={keyboard.activeIndex === index}
              onClick={() => onSelect(instrument)}
              onMouseEnter={() => keyboard.setActiveIndex(index)}
              className={cn(
                "w-full rounded px-3 py-2 text-left hover:bg-accent",
                keyboard.activeIndex === index && "bg-accent",
              )}
            >
              <div className="text-sm font-medium">{instrument.symbol}</div>
              <div className="text-[11px] text-muted-foreground">
                {instrument.company_name
                  ?? [instrument.base_asset, instrument.quote_asset].filter(Boolean).join("/")}
                {instrument.venue_name ? ` · ${instrument.venue_name}` : ""}
              </div>
            </button>
          ))}
          {!loading && instruments.length === 0 && (
            <div className="px-3 py-2 text-xs text-muted-foreground">No instruments found.</div>
          )}
        </div>
      )}
    </div>
  )
}


function PreviewPanel({
  preview,
  loading,
  error,
}: {
  preview: Awaited<ReturnType<typeof dataOperationPreviewApi>> | undefined
  loading: boolean
  error: string | undefined
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Coverage preview</h2>
        {preview && (
          <Badge variant={preview.can_run ? "secondary" : "outline"}>
            {preview.can_run ? "Ready" : "Unavailable"}
          </Badge>
        )}
      </div>
      {!preview && !loading && !error && (
        <p className="mt-4 text-sm text-muted-foreground">Choose a scope to inspect its current coverage.</p>
      )}
      {loading && <div className="mt-4 h-1 animate-pulse rounded bg-primary/40" />}
      {error && <ErrorMessage message={error} />}
      {preview && (
        <>
          <div className="mt-3">
            <div className="text-sm font-medium">{preview.scope_name}</div>
            <div className="mt-1 text-xs text-muted-foreground">{preview.message}</div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
            <Datum label="Instruments" value={preview.instrument_count} />
            <Datum label="Eligible" value={preview.eligible_count} />
            <Datum label="Current" value={preview.current_count} />
            <Datum label="Stale" value={preview.stale_count} />
            <Datum label="Missing" value={preview.missing_count} />
            <Datum label="Unsupported" value={preview.unsupported_count} />
          </div>
        </>
      )}
    </section>
  )
}


function JobPanel({ job }: { job: DataOperationJob }) {
  const progress = job.total > 0 ? Math.min(100, (job.current / job.total) * 100) : 0
  const terminal = job.status === "completed" || job.status === "failed"
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Latest operation</h2>
        <Badge variant={job.status === "completed" ? "secondary" : "outline"}>{job.status}</Badge>
      </div>
      <div className="mt-3 flex items-start gap-2">
        {job.status === "failed"
          ? <TriangleAlert size={17} className="mt-0.5 text-destructive" />
          : terminal
            ? <CheckCircle2 size={17} className="mt-0.5 text-emerald-500" />
            : <RefreshCw size={17} className="mt-0.5 animate-spin text-primary" />}
        <div className="min-w-0">
          <div className="text-sm font-medium">{job.scope_name}</div>
          <div className="mt-1 break-words text-xs text-muted-foreground">{job.message}</div>
        </div>
      </div>
      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
      </div>
      <div className="mt-2 text-right text-[11px] tabular-nums text-muted-foreground">
        {job.total > 0 ? `${job.current}/${job.total}` : job.status}
      </div>
      {job.error && <ErrorMessage message={job.error} />}
    </section>
  )
}


function ChoiceGroup({
  label,
  options,
  value,
  onChange,
  disabledValues = [],
}: {
  label: string
  options: string[][]
  value: string
  onChange: (value: string) => void
  disabledValues?: string[]
}) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 flex gap-2">
        {options.map(([option, text]) => (
          <button
            key={option}
            disabled={disabledValues.includes(option)}
            onClick={() => onChange(option)}
            className={cn(
              "rounded-md border px-3 py-2 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-40",
              value === option ? "border-primary bg-primary text-primary-foreground" : "border-border",
            )}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  )
}


function SectionLabel({ number, title, className }: { number: string; title: string; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="flex size-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">{number}</span>
      <h2 className="text-sm font-semibold">{title}</h2>
    </div>
  )
}


function Datum({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-base font-semibold tabular-nums">{value.toLocaleString()}</div>
    </div>
  )
}


function ErrorMessage({ message }: { message: string }) {
  return <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">{message}</div>
}
