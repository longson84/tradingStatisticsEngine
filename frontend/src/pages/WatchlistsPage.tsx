import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowDown, ArrowUp, ListPlus, Trash2 } from "lucide-react"

import { AnalysisInstrumentSelector } from "@/components/forms/AnalysisInstrumentSelector"
import { FormLabel } from "@/components/forms/FormSelect"
import {
  createWatchlistApi,
  deleteWatchlistApi,
  instrumentsApi,
  updateWatchlistApi,
  watchlistApi,
  watchlistsApi,
  type InstrumentCatalogItem,
  type InstrumentScope,
  type Watchlist,
} from "@/lib/api"
import { useDebouncedValue } from "@/lib/useDebouncedValue"


interface EditorInstrument {
  id: number
  symbol: string
  instrumentType: string
  companyName?: string | null
  venueName?: string | null
  venueCode?: string | null
  baseAsset?: string | null
  quoteAsset?: string | null
  currency: string
}


export function WatchlistsPanel() {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const watchlists = useQuery({
    queryKey: ["watchlists"],
    queryFn: watchlistsApi,
  })
  const detail = useQuery({
    queryKey: ["watchlist", selectedId],
    queryFn: () => watchlistApi(selectedId!),
    enabled: selectedId != null,
  })
  return (
    <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
      <section className="rounded-lg border border-border bg-card p-4">
        <button
          onClick={() => setSelectedId(null)}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
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
                {row.member_count.toLocaleString()} instruments · {compositionLabel(row)}
              </div>
            </button>
          ))}
          {!watchlists.isPending && watchlists.data?.watchlists.length === 0 && (
            <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
              No watchlists yet.
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
          key={selectedId != null && detail.data ? detail.data.id : "new"}
          initial={selectedId != null ? detail.data ?? null : null}
          onSaved={id => setSelectedId(id)}
          onDeleted={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}


function WatchlistEditor({
  initial,
  onSaved,
  onDeleted,
}: {
  initial: Watchlist | null
  onSaved: (id: number) => void
  onDeleted: () => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(initial?.name ?? "")
  const [description, setDescription] = useState(initial?.description ?? "")
  const [members, setMembers] = useState<EditorInstrument[]>(
    initial?.members.map(member => ({
      id: member.instrument_id,
      symbol: member.symbol,
      instrumentType: member.instrument_type,
      companyName: member.company_name,
      venueName: member.venue_name,
      venueCode: member.venue_code,
      baseAsset: member.base_asset,
      quoteAsset: member.quote_asset,
      currency: member.currency,
    })) ?? []
  )
  const [scope, setScope] = useState<InstrumentScope>("equity")
  const [search, setSearch] = useState("")
  const [candidate, setCandidate] = useState<InstrumentCatalogItem | null>(null)
  const debouncedSearch = useDebouncedValue(search.trim(), 300)
  const canSearch = debouncedSearch.length >= 3
  const instruments = useQuery({
    queryKey: ["watchlist-instrument-search", scope, debouncedSearch],
    queryFn: () => instrumentsApi({
      scope,
      search: debouncedSearch,
      has_price_history: false,
      limit: 25,
    }),
    enabled: canSearch,
  })

  const save = useMutation({
    mutationFn: () => {
      const request = {
        name,
        description,
        instrument_ids: members.map(member => member.id),
      }
      return initial
        ? updateWatchlistApi(initial.id, request)
        : createWatchlistApi(request)
    },
    onSuccess: async saved => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["watchlists"] }),
        queryClient.invalidateQueries({ queryKey: ["watchlist", saved.id] }),
      ])
      onSaved(saved.id)
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteWatchlistApi(initial!.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["watchlists"] })
      onDeleted()
    },
  })
  const canAdd = candidate != null && !members.some(member => member.id === candidate.id)

  const addCandidate = () => {
    if (!candidate || !canAdd) return
    setMembers(current => [...current, fromAnalysisInstrument(candidate)])
    setCandidate(null)
    setSearch("")
  }
  const move = (index: number, offset: -1 | 1) => {
    const target = index + offset
    if (target < 0 || target >= members.length) return
    setMembers(current => {
      const next = [...current]
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h2 className="text-lg font-semibold">{initial ? initial.name : "New watchlist"}</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Add equities, crypto spot instruments, and reference rates by stable instrument identity.
          </p>
        </div>
        {initial && (
          <div className="flex gap-2">
            <button
              onClick={() => {
                if (window.confirm(`Delete watchlist “${initial.name}”?`)) remove.mutate()
              }}
              disabled={remove.isPending}
              className="flex items-center gap-1.5 rounded-md border border-destructive/30 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/5 disabled:opacity-50"
            >
              <Trash2 size={13} /> Delete
            </button>
          </div>
        )}
      </div>

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
          <FormLabel>Description</FormLabel>
          <input
            value={description}
            onChange={event => setDescription(event.target.value)}
            maxLength={500}
            className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm focus:border-ring focus:outline-none"
          />
        </div>
      </div>

      <div className="mt-5 grid gap-3 border-t border-border pt-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="grid gap-3 sm:grid-cols-[180px_minmax(0,1fr)]">
          <AnalysisInstrumentSelector
            scope={scope}
            search={search}
            instruments={instruments.data?.instruments ?? []}
            selectedInstrument={candidate}
            isPending={canSearch && instruments.isFetching}
            onScopeChange={value => {
              setScope(value)
              setSearch("")
              setCandidate(null)
            }}
            onSearchChange={value => {
              setSearch(value)
              setCandidate(null)
            }}
            onInstrumentChange={setCandidate}
            onSubmit={addCandidate}
            helperText="Type at least 3 characters. Active instruments are shown even before price history is loaded."
          />
        </div>
        <button
          onClick={addCandidate}
          disabled={!canAdd}
          className="h-9 rounded-md bg-secondary px-5 text-sm text-secondary-foreground disabled:opacity-40"
        >
          Add instrument
        </button>
      </div>

      <div className="mt-4 overflow-x-auto rounded-md border border-border">
        <div className="grid min-w-[900px] grid-cols-[60px_110px_minmax(0,1fr)_150px_150px_120px] bg-muted/50 px-3 py-2 text-[10px] uppercase tracking-wide text-muted-foreground">
          <span>Order</span><span>Symbol</span><span>Identity</span><span>Type</span><span>Market / Venue</span><span />
        </div>
        {members.map((member, index) => (
          <div
            key={member.id}
            className="grid min-w-[900px] grid-cols-[60px_110px_minmax(0,1fr)_150px_150px_120px] items-center border-t border-border px-3 py-2 text-sm"
          >
            <span className="tabular-nums text-xs text-muted-foreground">{index + 1}</span>
            <span className="font-medium">{member.symbol}</span>
            <span className="truncate pr-3" title={identityLabel(member)}>{identityLabel(member)}</span>
            <span className="text-xs text-muted-foreground">{typeLabel(member)}</span>
            <span className="text-xs text-muted-foreground">
              {member.venueCode ?? "Venue-less"}
            </span>
            <span className="flex justify-end gap-1">
              <button onClick={() => move(index, -1)} disabled={index === 0} aria-label={`Move ${member.symbol} up`} className="rounded p-1 hover:bg-accent disabled:opacity-25"><ArrowUp size={13} /></button>
              <button onClick={() => move(index, 1)} disabled={index === members.length - 1} aria-label={`Move ${member.symbol} down`} className="rounded p-1 hover:bg-accent disabled:opacity-25"><ArrowDown size={13} /></button>
              <button onClick={() => setMembers(current => current.filter(item => item.id !== member.id))} className="ml-1 text-xs text-destructive hover:underline">Remove</button>
            </span>
          </div>
        ))}
        {members.length === 0 && (
          <div className="border-t border-border px-3 py-8 text-center text-xs text-muted-foreground">
            No instruments added yet.
          </div>
        )}
      </div>

      {(save.error || remove.error) && (
        <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {(save.error ?? remove.error)?.message}
        </div>
      )}

      <div className="mt-5 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{members.length.toLocaleString()} instruments</span>
        <button
          onClick={() => save.mutate()}
          disabled={!name.trim() || save.isPending}
          className="rounded-md bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
        >
          {save.isPending ? "Saving…" : initial ? "Save watchlist" : "Create watchlist"}
        </button>
      </div>
    </section>
  )
}


function fromAnalysisInstrument(instrument: InstrumentCatalogItem): EditorInstrument {
  return {
    id: instrument.id,
    symbol: instrument.symbol,
    instrumentType: instrument.instrument_type,
    companyName: instrument.company_name,
    venueName: instrument.venue_name,
    venueCode: instrument.venue_code,
    baseAsset: instrument.base_asset,
    quoteAsset: instrument.quote_asset,
    currency: instrument.currency,
  }
}


function identityLabel(instrument: EditorInstrument): string {
  return instrument.companyName
    ?? (instrument.baseAsset && instrument.quoteAsset
      ? `${instrument.baseAsset}/${instrument.quoteAsset}`
      : instrument.symbol)
}


function typeLabel(instrument: EditorInstrument): string {
  if (instrument.instrumentType === "spot") return "Crypto spot"
  if (instrument.instrumentType === "reference_rate") return "Reference rate"
  return "Equity"
}


function compositionLabel(row: {
  equity_count: number
  crypto_spot_count: number
  reference_rate_count: number
}): string {
  const parts = [
    row.equity_count ? `${row.equity_count} equities` : null,
    row.crypto_spot_count ? `${row.crypto_spot_count} crypto spot` : null,
    row.reference_rate_count ? `${row.reference_rate_count} rates` : null,
  ].filter(Boolean)
  return parts.join(" · ") || "empty"
}
