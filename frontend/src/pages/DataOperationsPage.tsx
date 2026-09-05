import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { NavLink, useNavigate } from "react-router"
import {
  CheckCircle2,
  DatabaseZap,
  History,
  ListChecks,
  ListTree,
  RefreshCw,
  Search,
  TriangleAlert,
} from "lucide-react"

import { Sidebar } from "@/components/Sidebar"
import { BatchOperationsPanel } from "@/components/data-operations/BatchOperationsPanel"
import { useSearchableSelectKeyboard } from "@/components/forms/useSearchableSelectKeyboard"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  activeDataOperationJobApi,
  batchOperationRunsApi,
  dataOperationJobApi,
  dataOperationHistoryApi,
  dataOperationPriceCoverageApi,
  dataOperationPreviewApi,
  instrumentsApi,
  startDataOperationApi,
  universesApi,
  watchlistsApi,
  type BatchOperationRun,
  type InstrumentCatalogItem,
  type DataOperationDataset,
  type DataOperationJob,
  type DataOperationMode,
  type DataOperationScopeType,
  type InstrumentPriceCoverage,
} from "@/lib/api"
import { cn } from "@/lib/utils"
import { useDebouncedValue } from "@/lib/useDebouncedValue"


type SingleOperationScopeType = Exclude<DataOperationScopeType, "category">

const SCOPE_OPTIONS: Array<{
  value: SingleOperationScopeType
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
const TRACKED_OPERATION_KEY = "tse.data-operation.current"

interface TrackedOperation {
  jobId: string
  scopeType: SingleOperationScopeType
  scopeId: string
  dataset: DataOperationDataset
  mode: DataOperationMode
}


export function DataOperationsPage({ view }: { view: "single" | "batch" }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [restoredOperation] = useState(readTrackedOperation)
  const [scopeType, setScopeType] = useState<SingleOperationScopeType>(
    restoredOperation?.scopeType ?? "universe",
  )
  const [scopeId, setScopeId] = useState(restoredOperation?.scopeId ?? "")
  const [dataset, setDataset] = useState<DataOperationDataset>(
    restoredOperation?.dataset ?? "prices",
  )
  const [mode, setMode] = useState<DataOperationMode>(
    restoredOperation?.mode ?? "incremental",
  )
  const [instrumentSearch, setInstrumentSearch] = useState("")
  const [selectedInstrument, setSelectedInstrument] = useState<InstrumentCatalogItem | null>(null)
  const [startedJob, setStartedJob] = useState<DataOperationJob | null>(null)
  const [trackedJobId, setTrackedJobId] = useState(restoredOperation?.jobId ?? "")
  const [coverageOffset, setCoverageOffset] = useState(0)
  const [coverageSearch, setCoverageSearch] = useState("")
  const debouncedCoverageSearch = useDebouncedValue(coverageSearch.trim(), 300)

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
    queryKey: [
      "data-operation-price-coverage",
      scopeType,
      scopeId,
      coverageOffset,
      debouncedCoverageSearch,
    ],
    queryFn: () => dataOperationPriceCoverageApi({
      scope_type: scopeType,
      scope_id: scopeId,
      offset: coverageOffset,
      limit: COVERAGE_PAGE_SIZE,
      search: debouncedCoverageSearch,
    }),
    enabled: scopeId.length > 0 && dataset === "prices",
  })
  const start = useMutation({
    mutationFn: startDataOperationApi,
    onSuccess: job => {
      if (!isSingleOperationScope(job.scope_type)) return
      setStartedJob(job)
      setTrackedJobId(job.id)
      writeTrackedOperation({
        jobId: job.id,
        scopeType: job.scope_type,
        scopeId: job.scope_id,
        dataset: job.dataset,
        mode: job.mode,
      })
      queryClient.setQueryData(
        ["active-data-operation-job", job.scope_type, job.scope_id, job.dataset],
        job,
      )
      void queryClient.invalidateQueries({ queryKey: ["data-operation-history"] })
    },
  })
  const job = useQuery({
    queryKey: ["data-operation-job", trackedJobId],
    queryFn: () => dataOperationJobApi(trackedJobId),
    enabled: trackedJobId.length > 0,
    initialData: startedJob?.id === trackedJobId ? startedJob : undefined,
    refetchInterval: query => {
      const status = query.state.data?.status
      return status === "queued" || status === "running" ? 1_000 : false
    },
    refetchIntervalInBackground: true,
  })
  const trackedJob = job.data ?? (startedJob?.id === trackedJobId ? startedJob : null)
  const activeScopeJob = useQuery({
    queryKey: ["active-data-operation-job", scopeType, scopeId, dataset],
    queryFn: () => activeDataOperationJobApi({
      scope_type: scopeType,
      scope_id: scopeId,
      dataset,
    }),
    enabled: scopeId.length > 0,
    refetchInterval: query => runningStatus(query.state.data?.status) ? 1_000 : 5_000,
    refetchIntervalInBackground: true,
  })
  const operationRunning = runningStatus(activeScopeJob.data?.status)
    || runningStatus(trackedJob?.status)
  const history = useQuery({
    queryKey: ["data-operation-history"],
    queryFn: () => dataOperationHistoryApi(100),
    refetchInterval: operationRunning ? 2_000 : false,
    refetchIntervalInBackground: true,
  })
  const batchHistory = useQuery({
    queryKey: ["batch-operation-runs", 100],
    queryFn: () => batchOperationRunsApi(100),
    enabled: view === "single",
    refetchInterval: operationRunning ? 2_000 : false,
    refetchIntervalInBackground: true,
  })
  const batchByJobId = new Map(
    (batchHistory.data?.runs ?? []).flatMap(batchRun => (
      batchRun.jobs.map(batchJob => [batchJob.id, batchRun] as const)
    )),
  )
  const latestMatchingJob = history.data?.runs.find(run => (
    run.scope_type === scopeType
    && run.scope_id === scopeId
    && run.dataset === dataset
  )) ?? null
  const activeJob = activeScopeJob.data ?? trackedJob ?? latestMatchingJob

  useEffect(() => {
    const detected = activeScopeJob.data
    if (!detected || !runningStatus(detected.status) || !isSingleOperationScope(detected.scope_type)) return
    writeTrackedOperation({
      jobId: detected.id,
      scopeType: detected.scope_type,
      scopeId: detected.scope_id,
      dataset: detected.dataset,
      mode: detected.mode,
    })
  }, [activeScopeJob.data])

  useEffect(() => {
    if (activeJob?.status === "completed") {
      void queryClient.invalidateQueries({ queryKey: ["data-operation-price-coverage"] })
    }
    if (activeJob?.status === "completed" || activeJob?.status === "failed") {
      void queryClient.invalidateQueries({ queryKey: ["data-operation-history"] })
    }
  }, [activeJob?.id, activeJob?.status, queryClient])

  const chooseScope = (value: SingleOperationScopeType) => {
    setScopeType(value)
    setScopeId("")
    setInstrumentSearch("")
    setSelectedInstrument(null)
    setStartedJob(null)
    setCoverageOffset(0)
    setCoverageSearch("")
  }
  const run = () => {
    if (!preview.data?.can_run) return
    start.mutate({ scope_type: scopeType, scope_id: scopeId, dataset, mode })
  }
  const running = operationRunning
  const checkingActiveJob = scopeId.length > 0
    && activeScopeJob.data === undefined
    && activeScopeJob.isFetching
  const reuseRun = (run: DataOperationJob) => {
    if (run.scope_type === "category") {
      void navigate("/data-operations/batch")
      return
    }
    setScopeType(run.scope_type)
    setScopeId(run.scope_id)
    setDataset(run.dataset)
    setMode(run.mode)
    setStartedJob(null)
    setCoverageOffset(0)
    if (run.scope_type === "instrument") {
      setInstrumentSearch(run.scope_name)
      setSelectedInstrument(null)
    } else {
      setInstrumentSearch("")
      setSelectedInstrument(null)
    }
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

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

        <div className="mb-5 flex gap-1 border-b border-border">
          <NavLink
            to="/data-operations/single"
            className={cn("border-b-2 px-4 py-2 text-sm font-medium", view === "single" ? "border-primary text-foreground" : "border-transparent text-muted-foreground")}
          >
            Single operation
          </NavLink>
          <NavLink
            to="/data-operations/batch"
            className={cn("border-b-2 px-4 py-2 text-sm font-medium", view === "batch" ? "border-primary text-foreground" : "border-transparent text-muted-foreground")}
          >
            Batch plans
          </NavLink>
        </div>

        {view === "batch" && <BatchOperationsPanel />}
        {view === "single" && <>

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
                disabled={!preview.data?.can_run || start.isPending || running || checkingActiveJob}
              >
                <RefreshCw className={start.isPending || running ? "animate-spin" : ""} />
                {checkingActiveJob
                  ? "Checking active job…"
                  : running
                    ? "Update in progress"
                    : mode === "full" ? "Build full history" : "Update data"}
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

        <RunHistory
          runs={history.data?.runs ?? []}
          batchByJobId={batchByJobId}
          loading={history.isFetching || batchHistory.isFetching}
          originLoading={batchHistory.isPending}
          error={history.error?.message}
          onReuse={reuseRun}
        />

        {dataset === "prices" && (
          <InstrumentCoverageTable
            coverage={coverage.data}
            loading={coverage.isFetching}
            error={coverage.error?.message}
            offset={coverageOffset}
            onOffsetChange={setCoverageOffset}
            search={coverageSearch}
            onSearchChange={value => {
              setCoverageSearch(value)
              setCoverageOffset(0)
            }}
          />
        )}
        </>}

      </main>
    </div>
  )
}


function RunHistory({
  runs,
  batchByJobId,
  loading,
  originLoading,
  error,
  onReuse,
}: {
  runs: DataOperationJob[]
  batchByJobId: Map<string, BatchOperationRun>
  loading: boolean
  originLoading: boolean
  error: string | undefined
  onReuse: (run: DataOperationJob) => void
}) {
  return (
    <section className="mt-5 rounded-xl border border-border bg-card">
      <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <div className="flex items-center gap-2">
            <History size={17} className="text-primary" />
            <h2 className="text-base font-semibold">Run history</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            The last 100 operations and their outcomes are retained in PostgreSQL.
          </p>
        </div>
        {loading && <RefreshCw size={15} className="animate-spin text-muted-foreground" />}
      </div>
      {error && <div className="px-5 pb-5"><ErrorMessage message={error} /></div>}
      {!error && !loading && runs.length === 0 && (
        <div className="px-5 py-10 text-center text-sm text-muted-foreground">
          No data operations have been run yet.
        </div>
      )}
      {runs.length > 0 && (
        <div className="max-h-[620px] overflow-auto">
          <table className="w-full min-w-[980px] text-left text-xs">
            <thead className="sticky top-0 z-10 bg-muted text-[10px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-semibold">Started</th>
                <th className="px-4 py-3 font-semibold">Scope</th>
                <th className="px-4 py-3 font-semibold">Operation</th>
                <th className="px-4 py-3 font-semibold">Origin</th>
                <th className="px-4 py-3 font-semibold">Result</th>
                <th className="px-4 py-3 font-semibold">Duration</th>
                <th className="px-4 py-3 font-semibold">Details</th>
                <th className="px-4 py-3 text-right font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {runs.map(run => (
                <tr key={run.id} className="align-top hover:bg-muted/20">
                  <td className="whitespace-nowrap px-4 py-3 tabular-nums">
                    {formatTimestamp(run.started_at ?? run.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-semibold">{run.scope_name}</div>
                    <div className="mt-0.5 text-[10px] capitalize text-muted-foreground">
                      {run.scope_type} · {run.scope_id}
                    </div>
                  </td>
                  <td className="px-4 py-3 capitalize">
                    <div>{run.dataset} · {run.mode}</div>
                    <div className="mt-0.5 text-[10px] text-muted-foreground">
                      {run.adapter_keys.join(", ")}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {originLoading ? (
                      <span className="text-muted-foreground">Checking…</span>
                    ) : batchByJobId.has(run.id) ? (
                      <div>
                        <Badge variant="outline">Batch</Badge>
                        <div className="mt-1 max-w-[180px] truncate text-[10px] text-muted-foreground">
                          {batchByJobId.get(run.id)?.plan_name}
                        </div>
                      </div>
                    ) : <Badge variant="secondary">Single</Badge>}
                  </td>
                  <td className="px-4 py-3">
                    <RunStatus run={run} />
                    <div className="mt-1 tabular-nums text-muted-foreground">
                      {run.succeeded.toLocaleString()} succeeded
                      {run.failed > 0 ? ` · ${run.failed.toLocaleString()} failed` : ""}
                      {` · ${run.current.toLocaleString()}/${run.total.toLocaleString()}`}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 tabular-nums">
                    {formatDuration(run.started_at, run.finished_at)}
                  </td>
                  <td className="max-w-[340px] px-4 py-3">
                    <div className="line-clamp-2 text-muted-foreground">{run.error ?? run.message}</div>
                    {run.output.length > 0 && (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-primary">Output</summary>
                        <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 text-[10px] leading-4">
                          {run.output.join("\n")}
                        </pre>
                      </details>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="outline" size="sm" onClick={() => onReuse(run)}>
                      {run.scope_type === "category" ? "Open batches" : "Use settings"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}


function RunStatus({ run }: { run: DataOperationJob }) {
  const variant = run.status === "failed"
    ? "destructive"
    : run.status === "completed"
      ? "secondary"
      : "outline"
  return <Badge variant={variant} className="capitalize">{run.status}</Badge>
}


function runningStatus(status: DataOperationJob["status"] | undefined) {
  return status === "queued" || status === "running"
}


function isSingleOperationScope(value: DataOperationScopeType): value is SingleOperationScopeType {
  return value === "universe" || value === "watchlist" || value === "instrument"
}


function formatTimestamp(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "—"
}


function formatDuration(startedAt: string | null, finishedAt: string | null) {
  if (!startedAt) return "—"
  const milliseconds = (finishedAt ? new Date(finishedAt) : new Date()).getTime()
    - new Date(startedAt).getTime()
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return "—"
  const seconds = Math.floor(milliseconds / 1_000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return `${minutes}m ${remainder}s`
}


function InstrumentCoverageTable({
  coverage,
  loading,
  error,
  offset,
  onOffsetChange,
  search,
  onSearchChange,
}: {
  coverage: Awaited<ReturnType<typeof dataOperationPriceCoverageApi>> | undefined
  loading: boolean
  error: string | undefined
  offset: number
  onOffsetChange: (offset: number) => void
  search: string
  onSearchChange: (value: string) => void
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
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
        <label className="relative block w-full max-w-md">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={event => onSearchChange(event.target.value)}
            placeholder="Search by symbol"
            aria-label="Search price coverage by symbol"
            className="h-9 w-full rounded-md border border-input bg-background pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
          />
        </label>
        {coverage && search.trim() && (
          <span className="text-xs text-muted-foreground">
            {coverage.total.toLocaleString()} matching instrument{coverage.total === 1 ? "" : "s"}
          </span>
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
              {search.trim()
                ? "No instruments match this symbol."
                : "This scope has no active instruments."}
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


function readTrackedOperation(): TrackedOperation | null {
  try {
    const raw = window.sessionStorage.getItem(TRACKED_OPERATION_KEY)
    if (!raw) return null
    const value = JSON.parse(raw) as Partial<TrackedOperation>
    if (
      typeof value.jobId !== "string"
      || !value.jobId
      || !(["universe", "watchlist", "instrument"] as readonly string[]).includes(
        value.scopeType ?? "",
      )
      || typeof value.scopeId !== "string"
      || !(["prices", "fundamentals"] as const).includes(
        value.dataset as DataOperationDataset,
      )
      || !(["incremental", "full"] as const).includes(
        value.mode as DataOperationMode,
      )
    ) {
      window.sessionStorage.removeItem(TRACKED_OPERATION_KEY)
      return null
    }
    return value as TrackedOperation
  } catch {
    window.sessionStorage.removeItem(TRACKED_OPERATION_KEY)
    return null
  }
}


function writeTrackedOperation(value: TrackedOperation): void {
  try {
    window.sessionStorage.setItem(TRACKED_OPERATION_KEY, JSON.stringify(value))
  } catch {
    // PostgreSQL history still retains the job when browser storage is unavailable.
  }
}
