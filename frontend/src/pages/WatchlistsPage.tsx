import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ListPlus, RefreshCw, Trash2 } from "lucide-react"

import { Sidebar } from "@/components/Sidebar"
import { FormLabel, FormSelect } from "@/components/forms/FormSelect"
import {
  companiesApi,
  createWatchlistApi,
  deleteWatchlistApi,
  refreshWatchlistPricesApi,
  updateWatchlistApi,
  watchlistApi,
  watchlistsApi,
  watchlistRefreshJobsApi,
  type CompanyResponse,
  type Watchlist,
  type WatchlistRefreshJob,
} from "@/lib/api"


type Market = "US" | "VN"

const MARKET_OPTIONS: Array<{ label: string; value: Market }> = [
  { label: "US Companies", value: "US" },
  { label: "VN Companies", value: "VN" },
]


export function WatchlistsPage() {
  const [market, setMarket] = useState<Market>("US")
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const watchlists = useQuery({
    queryKey: ["watchlists", market],
    queryFn: () => watchlistsApi(market),
  })
  const detail = useQuery({
    queryKey: ["watchlist", selectedId],
    queryFn: () => watchlistApi(selectedId!),
    enabled: selectedId != null,
  })
  const companies = useQuery({
    queryKey: ["companies", `${market}_ALL`],
    queryFn: () => companiesApi({ universe: `${market}_ALL` }),
  })
  const refreshJobs = useQuery({
    queryKey: ["watchlist-refresh-jobs"],
    queryFn: watchlistRefreshJobsApi,
    staleTime: 0,
    refetchInterval: query => query.state.data?.jobs.some(
      job => job.status === "queued" || job.status === "running"
    ) ? 1_500 : false,
  })

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <div className="mb-6 border-b border-border pb-4">
          <h1 className="text-2xl font-bold tracking-tight">Watchlists</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            User-managed company groups. Each watchlist belongs to exactly one market.
          </p>
        </div>

        <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
          <section className="rounded-lg border border-border bg-card p-4">
            <FormLabel>Market</FormLabel>
            <FormSelect
              value={market}
              onChange={value => {
                setMarket(value)
                setSelectedId(null)
              }}
              options={MARKET_OPTIONS}
            />

            <button
              onClick={() => setSelectedId(null)}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <ListPlus size={15} /> New watchlist
            </button>

            <div className="mt-4 space-y-2">
              {watchlists.isPending && (
                <p className="text-xs text-muted-foreground">Loading watchlists…</p>
              )}
              {watchlists.data?.watchlists.map(row => (
                <button
                  key={row.id}
                  onClick={() => setSelectedId(row.id)}
                  className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${selectedId === row.id ? "border-primary bg-primary/10" : "border-border hover:bg-accent"}`}
                >
                  <div className="text-sm font-medium">{row.name}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {row.member_count.toLocaleString()} companies
                  </div>
                </button>
              ))}
              {!watchlists.isPending && watchlists.data?.watchlists.length === 0 && (
                <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
                  No {market} watchlists yet.
                </p>
              )}
            </div>
          </section>

          {selectedId != null && detail.error ? (
            <section className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
              {detail.error.message}
            </section>
          ) : selectedId != null && detail.isPending ? (
            <section className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
              Loading watchlist…
            </section>
          ) : (
            <WatchlistEditor
              key={selectedId != null && detail.data ? detail.data.id : `new-${market}`}
              market={market}
              initial={selectedId != null ? detail.data ?? null : null}
              companies={companies.data?.companies ?? []}
              refreshJob={selectedId == null ? undefined : refreshJobs.data?.jobs.find(
                job => job.watchlist_id === selectedId
              )}
              onSaved={id => setSelectedId(id)}
              onDeleted={() => setSelectedId(null)}
            />
          )}
        </div>
      </main>
    </div>
  )
}


function WatchlistEditor({
  market,
  initial,
  companies,
  refreshJob,
  onSaved,
  onDeleted,
}: {
  market: Market
  initial: Watchlist | null
  companies: CompanyResponse[]
  refreshJob?: WatchlistRefreshJob
  onSaved: (id: number) => void
  onDeleted: () => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(initial?.name ?? "")
  const [description, setDescription] = useState(initial?.description ?? "")
  const [tickers, setTickers] = useState(
    initial?.members.map(member => member.ticker) ?? []
  )
  const [candidate, setCandidate] = useState("")

  const save = useMutation({
    mutationFn: () => initial
      ? updateWatchlistApi(initial.id, { name, description, tickers })
      : createWatchlistApi({ name, market, description, tickers }),
    onSuccess: async saved => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["watchlists", market] }),
        queryClient.invalidateQueries({ queryKey: ["watchlist", saved.id] }),
      ])
      onSaved(saved.id)
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteWatchlistApi(initial!.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["watchlists", market] })
      onDeleted()
    },
  })
  const refresh = useMutation({
    mutationFn: () => refreshWatchlistPricesApi(initial!.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["watchlist-refresh-jobs"] })
    },
  })
  const refreshing = refreshJob?.status === "queued" || refreshJob?.status === "running"

  const companyByTicker = new Map(companies.map(row => [row.ticker, row]))
  const normalizedCandidate = candidate.toUpperCase().trim()
  const canAdd = companyByTicker.has(normalizedCandidate) && !tickers.includes(normalizedCandidate)
  const addCandidate = () => {
    if (!canAdd) return
    setTickers(current => [...current, normalizedCandidate])
    setCandidate("")
  }

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h2 className="text-lg font-semibold">
            {initial ? initial.name : `New ${market} watchlist`}
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Only active {market} companies can be added.
          </p>
        </div>
        {initial && (
          <div className="flex gap-2">
            <button
              onClick={() => refresh.mutate()}
              disabled={refresh.isPending || refreshing || initial.member_count === 0}
              className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
            >
              <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />
              Update prices
            </button>
            <button
              onClick={() => {
                if (window.confirm(`Delete watchlist “${initial.name}”?`)) remove.mutate()
              }}
              disabled={remove.isPending || refreshing}
              className="flex items-center gap-1.5 rounded-md border border-destructive/30 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/5 disabled:opacity-50"
            >
              <Trash2 size={13} /> Delete
            </button>
          </div>
        )}
      </div>

      {refreshJob && (
        <div className="mt-4 rounded-md border border-primary/20 bg-primary/5 p-3 text-xs">
          <div className="flex justify-between gap-3">
            <span className="font-medium">Price refresh · {refreshJob.status}</span>
            <span className="tabular-nums text-muted-foreground">
              {refreshJob.total > 0 ? `${refreshJob.current}/${refreshJob.total}` : refreshJob.status}
            </span>
          </div>
          <p className="mt-1 truncate text-[11px] text-muted-foreground" title={refreshJob.message}>
            {refreshJob.message}
          </p>
          {refreshJob.error && <p className="mt-2 whitespace-pre-wrap text-destructive">{refreshJob.error}</p>}
        </div>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <FormLabel>Name</FormLabel>
          <input
            value={name}
            onChange={event => setName(event.target.value)}
            maxLength={100}
            className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm focus:border-ring focus:outline-none"
          />
        </div>
        <div>
          <FormLabel>Market</FormLabel>
          <div className="rounded border border-input bg-muted/40 px-2 py-1.5 text-sm">
            {market === "US" ? "US Companies" : "VN Companies"}
          </div>
        </div>
      </div>

      <div className="mt-4">
        <FormLabel>Description</FormLabel>
        <input
          value={description}
          onChange={event => setDescription(event.target.value)}
          maxLength={500}
          className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm focus:border-ring focus:outline-none"
        />
      </div>

      <div className="mt-5 border-t border-border pt-4">
        <FormLabel>Add company</FormLabel>
        <div className="flex gap-2">
          <input
            list={`watchlist-${market}-companies`}
            value={candidate}
            onChange={event => setCandidate(event.target.value.toUpperCase())}
            onKeyDown={event => {
              if (event.key === "Enter") addCandidate()
            }}
            placeholder="Search ticker or company"
            className="min-w-0 flex-1 rounded border border-input bg-background px-2 py-1.5 text-sm focus:border-ring focus:outline-none"
          />
          <datalist id={`watchlist-${market}-companies`}>
            {companies.map(company => (
              <option
                key={company.ticker}
                value={company.ticker}
                label={`${company.ticker} · ${company.company_name}`}
              />
            ))}
          </datalist>
          <button
            onClick={addCandidate}
            disabled={!canAdd}
            className="rounded-md bg-secondary px-4 py-1.5 text-sm text-secondary-foreground disabled:opacity-40"
          >
            Add
          </button>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto rounded-md border border-border">
        <div className="grid min-w-[900px] grid-cols-[80px_minmax(0,1fr)_180px_220px_80px] bg-muted/50 px-3 py-2 text-[10px] uppercase tracking-wide text-muted-foreground">
          <span>Ticker</span><span>Company</span><span>Sector</span><span>Industry</span><span />
        </div>
        {tickers.map(ticker => {
          const company = companyByTicker.get(ticker)
          return (
            <div
              key={ticker}
              className="grid min-w-[900px] grid-cols-[80px_minmax(0,1fr)_180px_220px_80px] items-center border-t border-border px-3 py-2 text-sm"
            >
              <span className="font-medium">{ticker}</span>
              <span className="truncate pr-3">{company?.company_name ?? ticker}</span>
              <span className="truncate pr-3 text-xs text-muted-foreground" title={company?.sector ?? undefined}>
                {company?.sector ?? "—"}
              </span>
              <span className="truncate pr-3 text-xs text-muted-foreground" title={company?.industry ?? undefined}>
                {company?.industry ?? "—"}
              </span>
              <button
                onClick={() => setTickers(current => current.filter(item => item !== ticker))}
                className="text-right text-xs text-destructive hover:underline"
              >
                Remove
              </button>
            </div>
          )
        })}
        {tickers.length === 0 && (
          <div className="border-t border-border px-3 py-8 text-center text-xs text-muted-foreground">
            No companies added yet.
          </div>
        )}
      </div>

      {(save.error || remove.error || refresh.error) && (
        <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {(save.error ?? remove.error ?? refresh.error)?.message}
        </div>
      )}

      <div className="mt-5 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {tickers.length.toLocaleString()} companies
        </span>
        <button
          onClick={() => save.mutate()}
          disabled={!name.trim() || save.isPending || refreshing}
          className="rounded-md bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
        >
          {save.isPending ? "Saving…" : initial ? "Save watchlist" : "Create watchlist"}
        </button>
      </div>
    </section>
  )
}
