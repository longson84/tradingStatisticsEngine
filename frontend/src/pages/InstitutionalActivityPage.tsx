import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Landmark } from "lucide-react"

import { Sidebar } from "@/components/Sidebar"
import { USInstitutionalInstrumentSelector } from "@/components/forms/USInstitutionalInstrumentSelector"
import { InstitutionalActivityView } from "@/components/institutional-activity/InstitutionalActivityView"
import {
  instrumentInstitutionalActivityApi,
  instrumentsApi,
  type InstrumentCatalogItem,
} from "@/lib/api"
import { useDebouncedValue } from "@/lib/useDebouncedValue"


export function InstitutionalActivityPage() {
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<InstrumentCatalogItem | null>(null)
  const [applied, setApplied] = useState<InstrumentCatalogItem | null>(null)
  const debounced = useDebouncedValue(search.trim(), 300)
  const instruments = useQuery({
    queryKey: ["us-institutional-instruments", debounced],
    queryFn: () => instrumentsApi({
      scope: "equity", universe: "US3000", search: debounced,
      has_price_history: false, limit: 20,
    }),
    enabled: selected == null && debounced.length >= 3,
  })
  const activity = useQuery({
    queryKey: ["institutional-activity", applied?.id, 8],
    queryFn: () => instrumentInstitutionalActivityApi({
      instrument_id: applied!.id, quarters: 8,
    }),
    enabled: applied != null,
    retry: false,
    staleTime: 0,
  })
  const apply = () => {
    if (!selected) return
    if (applied?.id === selected.id) void activity.refetch()
    else setApplied(selected)
  }
  return <div className="flex min-h-screen bg-background text-foreground">
    <Sidebar />
    <main className="min-w-0 flex-1 overflow-y-auto p-6">
      <header className="mb-6 border-b border-border pb-5">
        <div className="flex items-center gap-2"><Landmark size={21} className="text-primary" /><h1 className="text-2xl font-bold">US Institutional Activity</h1></div>
        <p className="mt-1 text-sm text-muted-foreground">Stored SEC Form 13F holdings and inferred quarter-to-quarter position changes for an exact US common stock.</p>
      </header>
      <section className="mb-5 rounded-xl border border-border bg-card p-5">
        <div className="grid gap-4 lg:grid-cols-[minmax(300px,1fr)_auto] lg:items-end">
          <USInstitutionalInstrumentSelector
            search={search}
            instruments={instruments.data?.instruments ?? []}
            selectedInstrument={selected}
            total={instruments.data?.total}
            isPending={debounced.length >= 3 && instruments.isFetching}
            errorMessage={instruments.error?.message}
            onSearchChange={value => { setSearch(value); setSelected(null); setApplied(null) }}
            onInstrumentChange={instrument => {
              setSelected(instrument)
              if (instrument) setSearch(instrument.symbol)
              setApplied(null)
            }}
            onSubmit={apply}
          />
          <button type="button" disabled={!selected || activity.isFetching} onClick={apply} className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40">View activity</button>
        </div>
      </section>
      {!applied && <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">Choose a tracked US equity, then View activity. This page reads PostgreSQL only.</div>}
      {applied && activity.isFetching && <div role="status" className="rounded-lg border border-border p-6 text-sm text-muted-foreground">Loading stored institutional activity…</div>}
      {applied && activity.error && <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-5 text-sm"><h2 className="font-semibold">Institutional Activity request failed</h2><p className="mt-1 text-muted-foreground">{activity.error.message}</p></div>}
      {applied && activity.data && <InstitutionalActivityView result={activity.data} />}
    </main>
  </div>
}
