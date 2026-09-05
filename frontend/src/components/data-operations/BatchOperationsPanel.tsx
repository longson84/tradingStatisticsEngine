import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ChevronDown, ChevronRight, GripVertical, ListPlus, Play, Plus, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  batchOperationPlansApi,
  batchOperationRunApi,
  batchOperationRunsApi,
  createBatchOperationPlanApi,
  deleteBatchOperationPlanApi,
  startBatchOperationRunApi,
  updateBatchOperationPlanApi,
  universesApi,
  watchlistsApi,
  type BatchOperationPlan,
  type BatchOperationStepRequest,
  type BatchOperationRun,
} from "@/lib/api"


const CATEGORY_OPTIONS = [
  ["equity", "All active equities"],
  ["reference_rate", "All active reference rates"],
  ["crypto_spot", "All active crypto spot instruments"],
  ["market_index", "All active market indices"],
] as const

const DEFAULT_STEP: BatchOperationStepRequest = {
  target_type: "category",
  target_id: "equity",
  dataset: "prices",
  mode: "incremental",
}
const TRACKED_BATCH_RUN_KEY = "tse.data-operation.batch-run"


export function BatchOperationsPanel() {
  const [selectedId, setSelectedId] = useState<number | "new" | null>(null)
  const plans = useQuery({ queryKey: ["batch-operation-plans"], queryFn: batchOperationPlansApi })
  const selected = selectedId === "new"
    ? null
    : plans.data?.plans.find(plan => plan.id === selectedId) ?? null

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[310px_minmax(0,1fr)]">
      <section className="rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">Saved plans</h2>
          <Button size="sm" variant="outline" onClick={() => setSelectedId("new")}>
            <Plus size={14} /> New
          </Button>
        </div>
        <div className="space-y-1 p-2">
          {plans.data?.plans.map(plan => (
            <button
              key={plan.id}
              type="button"
              onClick={() => setSelectedId(plan.id)}
              className={`w-full rounded-md border px-3 py-2 text-left ${selectedId === plan.id ? "border-primary bg-primary/10" : "border-transparent hover:bg-accent"}`}
            >
              <span className="block text-sm font-medium">{plan.name}</span>
              <span className="mt-0.5 block text-[11px] text-muted-foreground">
                {plan.steps.length} step{plan.steps.length === 1 ? "" : "s"}
              </span>
            </button>
          ))}
          {!plans.isPending && plans.data?.plans.length === 0 && selectedId !== "new" && (
            <div className="px-3 py-8 text-center text-xs text-muted-foreground">
              Create your first reusable batch plan.
            </div>
          )}
        </div>
      </section>

      {selectedId === "new" ? (
        <BatchPlanEditor key="new" plan={null} onSaved={plan => setSelectedId(plan.id)} />
      ) : selected ? (
        <BatchPlanEditor
          key={selected.id}
          plan={selected}
          onSaved={plan => setSelectedId(plan.id)}
          onDeleted={() => setSelectedId(null)}
        />
      ) : (
        <section className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
          Choose a saved plan or create a new one.
        </section>
      )}
      </div>
      <BatchRunHistory />
    </div>
  )
}


function BatchPlanEditor({
  plan,
  onSaved,
  onDeleted,
}: {
  plan: BatchOperationPlan | null
  onSaved: (plan: BatchOperationPlan) => void
  onDeleted?: () => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(plan?.name ?? "")
  const [description, setDescription] = useState(plan?.description ?? "")
  const [steps, setSteps] = useState<BatchOperationStepRequest[]>(
    plan?.steps.map(step => ({
      target_type: step.target_type,
      target_id: step.target_id,
      dataset: step.dataset,
      mode: step.mode,
    })) ?? [{ ...DEFAULT_STEP }],
  )
  const [startedRun, setStartedRun] = useState<BatchOperationRun | null>(null)
  const [trackedRunId, setTrackedRunId] = useState(() => (
    window.sessionStorage.getItem(TRACKED_BATCH_RUN_KEY) ?? ""
  ))
  const universes = useQuery({ queryKey: ["universes"], queryFn: universesApi })
  const watchlists = useQuery({ queryKey: ["watchlists"], queryFn: watchlistsApi })
  const save = useMutation({
    mutationFn: () => {
      const request = { name, description, steps }
      return plan
        ? updateBatchOperationPlanApi(plan.id, request)
        : createBatchOperationPlanApi(request)
    },
    onSuccess: async saved => {
      await queryClient.invalidateQueries({ queryKey: ["batch-operation-plans"] })
      onSaved(saved)
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteBatchOperationPlanApi(plan!.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["batch-operation-plans"] })
      onDeleted?.()
    },
  })
  const start = useMutation({
    mutationFn: () => startBatchOperationRunApi(plan!.id),
    onSuccess: run => {
      setStartedRun(run)
      setTrackedRunId(run.id)
      window.sessionStorage.setItem(TRACKED_BATCH_RUN_KEY, run.id)
      void queryClient.invalidateQueries({ queryKey: ["batch-operation-runs"] })
    },
  })
  const run = useQuery({
    queryKey: ["batch-operation-run", trackedRunId],
    queryFn: () => batchOperationRunApi(trackedRunId),
    enabled: trackedRunId.length > 0,
    initialData: startedRun?.id === trackedRunId ? startedRun : undefined,
    refetchInterval: query => {
      const status = query.state.data?.status
      return status === "queued" || status === "running" ? 1_000 : false
    },
    refetchIntervalInBackground: true,
  })

  useEffect(() => {
    if (run.data && (run.data.status === "completed" || run.data.status === "failed")) {
      void queryClient.invalidateQueries({ queryKey: ["batch-operation-runs"] })
    }
  }, [queryClient, run.data])

  const updateStep = (index: number, patch: Partial<BatchOperationStepRequest>) => {
    setSteps(current => current.map((step, position) => (
      position === index ? { ...step, ...patch } : step
    )))
  }

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div>
          <h2 className="text-lg font-semibold">{plan ? plan.name : "New batch plan"}</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Targets resolve from current PostgreSQL metadata each time the batch runs.
          </p>
        </div>
        <div className="flex gap-2">
          {plan && (
            <Button variant="outline" onClick={() => remove.mutate()} disabled={remove.isPending}>
              <Trash2 size={14} /> Delete
            </Button>
          )}
          <Button onClick={() => save.mutate()} disabled={!name.trim() || steps.length === 0 || save.isPending}>
            {save.isPending ? "Saving…" : plan ? "Save changes" : "Create plan"}
          </Button>
          {plan && (
            <Button onClick={() => start.mutate()} disabled={start.isPending || run.data?.status === "queued" || run.data?.status === "running"}>
              <Play size={14} /> {start.isPending ? "Starting…" : "Run batch"}
            </Button>
          )}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Name
          <input value={name} onChange={event => setName(event.target.value)} maxLength={100} className="mt-1 block h-9 w-full rounded-md border border-input bg-background px-3 text-sm normal-case" />
        </label>
        <label className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Description
          <input value={description} onChange={event => setDescription(event.target.value)} maxLength={500} className="mt-1 block h-9 w-full rounded-md border border-input bg-background px-3 text-sm normal-case" />
        </label>
      </div>

      <div className="mt-5 overflow-x-auto rounded-lg border border-border">
        <div className="grid min-w-[850px] grid-cols-[44px_160px_minmax(220px,1fr)_130px_130px_44px] bg-muted/50 px-3 py-2 text-[10px] uppercase tracking-wide text-muted-foreground">
          <span>#</span><span>Target type</span><span>Dynamic target</span><span>Dataset</span><span>Mode</span><span />
        </div>
        {steps.map((step, index) => (
          <div key={index} className="grid min-w-[850px] grid-cols-[44px_160px_minmax(220px,1fr)_130px_130px_44px] items-center gap-0 border-t border-border px-3 py-2 text-xs">
            <span className="flex items-center gap-1 text-muted-foreground"><GripVertical size={13} />{index + 1}</span>
            <select value={step.target_type} onChange={event => updateStep(index, { target_type: event.target.value as BatchOperationStepRequest["target_type"], target_id: defaultTarget(event.target.value) })} className="mr-2 h-8 rounded border border-input bg-background px-2">
              <option value="category">Instrument category</option>
              <option value="universe">Universe</option>
              <option value="watchlist">Watchlist</option>
            </select>
            <select value={step.target_id} onChange={event => updateStep(index, { target_id: event.target.value })} className="mr-2 h-8 rounded border border-input bg-background px-2">
              {step.target_type === "category" && CATEGORY_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              {step.target_type === "universe" && <option value="">Choose a universe…</option>}
              {step.target_type === "universe" && universes.data?.universes.map(row => <option key={row.id} value={row.code}>{row.name}</option>)}
              {step.target_type === "watchlist" && <option value="">Choose a watchlist…</option>}
              {step.target_type === "watchlist" && watchlists.data?.watchlists.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
            <select value={step.dataset} onChange={event => updateStep(index, { dataset: event.target.value as BatchOperationStepRequest["dataset"] })} className="mr-2 h-8 rounded border border-input bg-background px-2"><option value="prices">Prices</option><option value="fundamentals">Fundamentals</option></select>
            <select value={step.mode} onChange={event => updateStep(index, { mode: event.target.value as BatchOperationStepRequest["mode"] })} className="mr-2 h-8 rounded border border-input bg-background px-2"><option value="incremental">Incremental</option><option value="full">Full history</option></select>
            <button type="button" onClick={() => setSteps(current => current.filter((_, position) => position !== index))} aria-label={`Remove step ${index + 1}`} className="rounded p-1 text-destructive hover:bg-destructive/10"><Trash2 size={14} /></button>
          </div>
        ))}
      </div>
      <Button variant="outline" className="mt-3" onClick={() => setSteps(current => [...current, { ...DEFAULT_STEP }])}>
        <Plus size={14} /> Add step
      </Button>

      {(save.error || remove.error || start.error) && (
        <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {(save.error ?? remove.error ?? start.error)?.message}
        </div>
      )}
      {run.data && <BatchRunProgress run={run.data} />}
    </section>
  )
}


function BatchRunProgress({
  run,
  title = "Current batch run",
}: {
  run: BatchOperationRun
  title?: string
}) {
  return (
    <div className="mt-5 border-t border-border pt-4">
      <div className="flex items-center justify-between gap-3">
        <div><h3 className="text-sm font-semibold">{title}</h3><p className="mt-1 text-xs text-muted-foreground">Step {run.current_step} of {run.total_steps}</p></div>
        <Badge variant={run.status === "failed" ? "destructive" : run.status === "completed" ? "secondary" : "outline"}>{run.status}</Badge>
      </div>
      <div className="mt-3 divide-y divide-border">
        {run.jobs.map(job => {
          const progress = job.total ? Math.min(100, job.current / job.total * 100) : 0
          return (
            <div key={job.id} className="grid gap-2 py-3 text-xs md:grid-cols-[minmax(180px,1fr)_140px_100px] md:items-center">
              <div>
                <div className="font-medium">{job.scope_name}</div>
                <div className="mt-0.5 text-[10px] capitalize text-muted-foreground">{job.dataset} · {job.mode}</div>
                <div className="mt-1 h-1.5 overflow-hidden rounded bg-muted"><div className="h-full bg-primary" style={{ width: `${progress}%` }} /></div>
                {(job.error || job.output.length > 0) && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-primary">Result details</summary>
                    {job.error && <div className="mt-2 whitespace-pre-wrap text-destructive">{job.error}</div>}
                    {job.output.length > 0 && <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 text-[10px] leading-4">{job.output.join("\n")}</pre>}
                  </details>
                )}
              </div>
              <span className="text-muted-foreground">{job.adapter_keys.join(", ")}</span>
              <span className="text-right tabular-nums">{job.succeeded} succeeded{job.failed > 0 ? ` · ${job.failed} failed` : ""}<br />{job.current}/{job.total} · {job.status}</span>
            </div>
          )
        })}
      </div>
      {run.error && <div className="mt-2 whitespace-pre-wrap text-xs text-destructive">{run.error}</div>}
    </div>
  )
}


function BatchRunHistory() {
  const [openRunId, setOpenRunId] = useState<string | null>(null)
  const runs = useQuery({ queryKey: ["batch-operation-runs"], queryFn: () => batchOperationRunsApi(20) })
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2"><ListPlus size={17} className="text-primary" /><h2 className="text-base font-semibold">Batch run history</h2></div>
      <div className="mt-4 divide-y divide-border">
        {runs.data?.runs.map(run => {
          const open = openRunId === run.id
          return (
            <div key={run.id} className="py-3 text-xs">
              <button
                type="button"
                aria-expanded={open}
                onClick={() => setOpenRunId(current => current === run.id ? null : run.id)}
                className="flex w-full items-center justify-between gap-3 rounded-md p-2 text-left hover:bg-muted/40"
              >
                <div className="flex min-w-0 items-center gap-2">
                  {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                  <div><div className="font-medium">{run.plan_name}</div><div className="mt-0.5 text-muted-foreground">{new Date(run.created_at).toLocaleString()} · {run.current_step}/{run.total_steps} steps · {run.jobs.length} sessions</div></div>
                </div>
                <Badge variant={run.status === "failed" ? "destructive" : run.status === "completed" ? "secondary" : "outline"}>{run.status}</Badge>
              </button>
              {open && <BatchRunProgress run={run} title="Batch run details" />}
            </div>
          )
        })}
        {!runs.isPending && runs.data?.runs.length === 0 && <p className="py-8 text-center text-xs text-muted-foreground">No batch runs yet.</p>}
      </div>
    </section>
  )
}


function defaultTarget(targetType: string): string {
  if (targetType === "category") return "equity"
  return ""
}
