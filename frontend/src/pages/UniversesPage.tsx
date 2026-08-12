import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Database, Search } from "lucide-react"

import { Pagination } from "@/components/ui/Pagination"
import { Badge } from "@/components/ui/badge"
import {
  instrumentsApi,
  universesApi,
  type AnalysisInstrument,
} from "@/lib/api"
import { fmtProviderSource } from "@/lib/format"
import { useDebouncedValue } from "@/lib/useDebouncedValue"
import { cn } from "@/lib/utils"


const PAGE_SIZE = 50


export function UniversesPanel() {
  const [universeSearch, setUniverseSearch] = useState("")
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [memberSearch, setMemberSearch] = useState("")
  const [offset, setOffset] = useState(0)
  const debouncedMemberSearch = useDebouncedValue(memberSearch.trim(), 300)
  const universes = useQuery({
    queryKey: ["universes"],
    queryFn: universesApi,
  })
  const filteredUniverses = useMemo(() => {
    const query = universeSearch.trim().toLocaleLowerCase()
    return universes.data?.universes.filter(universe => (
      !query || [universe.code, universe.name, universe.description]
        .some(value => value.toLocaleLowerCase().includes(query)))
    ) ?? []
  }, [universeSearch, universes.data])
  const selected = universes.data?.universes.find(
    universe => universe.code === selectedCode
  ) ?? null
  const members = useQuery({
    queryKey: ["universe-instruments", selectedCode, debouncedMemberSearch, offset],
    queryFn: () => instrumentsApi({
      universe: selectedCode!,
      search: debouncedMemberSearch || undefined,
      has_price_history: false,
      offset,
      limit: PAGE_SIZE,
    }),
    enabled: selectedCode != null,
    placeholderData: previous => previous,
  })

  return (
    <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
      <section className="rounded-lg border border-border bg-card p-4">
        <label className="relative block">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={universeSearch}
            onChange={event => setUniverseSearch(event.target.value)}
            placeholder="Search universes"
            className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
          />
        </label>

        <div className="mt-4 space-y-2">
          {universes.isPending && <p className="text-xs text-muted-foreground">Loading universes…</p>}
          {universes.error && <p className="text-xs text-destructive">{universes.error.message}</p>}
          {filteredUniverses.map(universe => (
            <button
              key={universe.id}
              onClick={() => {
                setSelectedCode(universe.code)
                setMemberSearch("")
                setOffset(0)
              }}
              className={cn(
                "w-full rounded-md border px-3 py-2 text-left transition-colors",
                selectedCode === universe.code
                  ? "border-primary bg-primary/10"
                  : "border-border hover:bg-accent",
              )}
            >
              <div className="text-sm font-medium">{universe.name}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {universe.code} · {universe.active_instrument_count.toLocaleString()} active instruments
              </div>
            </button>
          ))}
          {!universes.isPending && filteredUniverses.length === 0 && (
            <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
              No universes match these filters.
            </p>
          )}
        </div>
      </section>

      {!selected ? (
        <section className="flex min-h-72 items-center justify-center rounded-lg border border-dashed border-border bg-card p-8 text-center text-sm text-muted-foreground">
          Choose a universe to inspect its synchronized instrument membership.
        </section>
      ) : (
        <section className="min-w-0 rounded-lg border border-border bg-card p-5">
          <div className="flex flex-col justify-between gap-4 border-b border-border pb-4 lg:flex-row lg:items-start">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold">{selected.name}</h2>
                <Badge variant="secondary">Synchronized universe</Badge>
              </div>
              <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground">
                {selected.description || "Provider or system-defined instrument membership."}
              </p>
            </div>
            <div className="text-right text-xs text-muted-foreground">
              <div>{selected.active_instrument_count.toLocaleString()} active / {selected.instrument_count.toLocaleString()} total</div>
              <div>{selected.as_of ? `As of ${selected.as_of}` : "No as-of label"}</div>
            </div>
          </div>

          <div className="mt-4 grid gap-3 text-xs sm:grid-cols-2 xl:grid-cols-4">
            <UniverseDatum label="Code" value={selected.code} />
            <UniverseDatum label="Source" value={fmtProviderSource(selected.source)} />
            <UniverseDatum label="Instrument types" value={selected.instrument_types.map(typeLabel).join(", ") || "—"} />
            <UniverseDatum label="Venues" value={selected.venue_codes.join(", ") || "Not venue-specific"} />
            <UniverseDatum label="Last synchronized" value={formatDateTime(selected.fetched_at)} />
          </div>

          <div className="mt-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h3 className="text-sm font-semibold">Active instruments</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                Membership is synchronized from the universe source and cannot be edited here.
              </p>
            </div>
            <label className="relative block w-full lg:w-80">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={memberSearch}
                onChange={event => {
                  setMemberSearch(event.target.value)
                  setOffset(0)
                }}
                placeholder="Search instruments"
                className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
              />
            </label>
          </div>

          {members.isFetching && <div className="mt-4 h-1 overflow-hidden rounded bg-muted"><div className="h-full w-1/3 animate-pulse bg-primary" /></div>}
          {members.error && <p className="mt-4 text-sm text-destructive">{members.error.message}</p>}
          {members.data && (
            <>
              <div className="mt-4 overflow-x-auto rounded-md border border-border">
                <table className="w-full min-w-[900px] text-sm">
                  <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Symbol</th>
                      <th className="px-3 py-2 text-left font-medium">Identity</th>
                      <th className="px-3 py-2 text-left font-medium">Type</th>
                      <th className="px-3 py-2 text-left font-medium">Venue</th>
                      <th className="px-3 py-2 text-left font-medium">Currency</th>
                      <th className="px-3 py-2 text-right font-medium">Stored sessions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {members.data.instruments.map(instrument => (
                      <UniverseInstrumentRow key={instrument.id} instrument={instrument} />
                    ))}
                  </tbody>
                </table>
                {members.data.instruments.length === 0 && (
                  <div className="px-4 py-8 text-center text-xs text-muted-foreground">No active instruments match this search.</div>
                )}
              </div>
              <Pagination
                total={members.data.total}
                offset={members.data.offset}
                limit={members.data.limit}
                onOffsetChange={setOffset}
              />
            </>
          )}
        </section>
      )}
    </div>
  )
}


function UniverseInstrumentRow({ instrument }: { instrument: AnalysisInstrument }) {
  const identity = instrument.company_name
    ?? (instrument.base_asset && instrument.quote_asset
      ? `${instrument.base_asset}/${instrument.quote_asset}`
      : instrument.symbol)
  return (
    <tr className="hover:bg-muted/30">
      <td className="px-3 py-2 font-medium">{instrument.symbol}</td>
      <td className="px-3 py-2">{identity}</td>
      <td className="px-3 py-2 text-xs text-muted-foreground">{typeLabel(instrument.instrument_type)}</td>
      <td className="px-3 py-2 text-xs text-muted-foreground">
        {instrument.venue_code ?? "Not venue-specific"}
      </td>
      <td className="px-3 py-2 text-xs text-muted-foreground">{instrument.currency}</td>
      <td className="px-3 py-2 text-right tabular-nums">{instrument.stored_sessions.toLocaleString()}</td>
    </tr>
  )
}


function UniverseDatum({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 flex items-center gap-1.5 font-medium">
        {label === "Source" && <Database size={12} />}
        {value}
      </div>
    </div>
  )
}


function typeLabel(value: string): string {
  if (value === "spot") return "Crypto spot"
  if (value === "reference_rate") return "Reference rate"
  if (value === "common_stock") return "Common stock"
  return value.replaceAll("_", " ")
}


function formatDateTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : "—"
}
