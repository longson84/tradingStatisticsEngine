import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { Sidebar } from "@/components/Sidebar"
import { venuesApi, type Venue } from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"


const ALL = "ALL"


export function VenuesPage() {
  const [query, setQuery] = useState("")
  const [venueType, setVenueType] = useState(ALL)
  const [calendarCode, setCalendarCode] = useState(ALL)
  const venues = useQuery({
    queryKey: ["venues"],
    queryFn: venuesApi,
    refetchOnMount: "always",
    retry: false,
  })
  const rows = useMemo(() => venues.data?.venues ?? [], [venues.data])
  const types = useMemo(
    () => [...new Set(rows.map(row => row.venue_type))].sort(),
    [rows],
  )
  const calendars = useMemo(
    () => [...new Set(rows.map(row => row.trading_calendar_code))].sort(),
    [rows],
  )
  const filteredRows = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase()
    return rows.filter(row => (
      (venueType === ALL || row.venue_type === venueType)
      && (calendarCode === ALL || row.trading_calendar_code === calendarCode)
      && (
        !needle
        || row.code.toLocaleLowerCase().includes(needle)
        || row.name.toLocaleLowerCase().includes(needle)
        || row.country_code?.toLocaleLowerCase().includes(needle)
      )
    ))
  }, [calendarCode, query, rows, venueType])
  const activeVenues = rows.filter(row => row.is_active).length
  const activeInstruments = rows.reduce(
    (total, row) => total + row.active_instrument_count,
    0,
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
          <header className="border-b border-border pb-5">
            <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
              <div>
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Trading locations
                </div>
                <h1 className="text-2xl font-bold tracking-tight">Venues</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Economic trading locations and the schedule metadata used to determine completed daily sessions.
                </p>
              </div>
              <div className="text-right text-xs text-muted-foreground">
                <div>{fmtInt(venues.data?.total ?? 0)} canonical venues</div>
                <div>Read-only PostgreSQL catalog</div>
              </div>
            </div>

            <div className="mt-5 grid overflow-hidden rounded-lg border border-border bg-card sm:grid-cols-2 xl:grid-cols-4">
              <SummaryCell label="Venues" value={rows.length} />
              <SummaryCell label="Active venues" value={activeVenues} />
              <SummaryCell label="Venue types" value={types.length} />
              <SummaryCell label="Active instruments" value={activeInstruments} />
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <FilterSelect label="Venue type" value={venueType} values={types} onChange={setVenueType} />
              <FilterSelect label="Calendar" value={calendarCode} values={calendars} onChange={setCalendarCode} />
            </div>
          </header>

          <section className="mt-5 space-y-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-sm font-semibold">Venue Catalog</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Instrument counts are derived from current canonical instrument relationships.
                </p>
              </div>
              <label className="relative block w-full lg:w-96">
                <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={query}
                  onChange={event => setQuery(event.target.value)}
                  placeholder="Search code, name, country..."
                  className="w-full rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm focus:border-ring focus:outline-none"
                />
              </label>
            </div>

            {venues.isFetching && (
              <div className="h-1 overflow-hidden rounded-full bg-muted">
                <div className="h-full w-1/3 animate-pulse bg-primary" />
              </div>
            )}
            {venues.error && !venues.isFetching && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {venues.error.message}
              </div>
            )}
            {!venues.isFetching && !venues.error && (
              <VenueTable rows={filteredRows} />
            )}
          </section>
      </main>
    </div>
  )
}


function SummaryCell({ label, value }: { label: string; value: number }) {
  return (
    <div className="border-border px-4 py-3 sm:border-r last:border-r-0">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{fmtInt(value)}</div>
    </div>
  )
}


function FilterSelect({
  label,
  value,
  values,
  onChange,
}: {
  label: string
  value: string
  values: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="space-y-2">
      <span className="block text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">{label}</span>
      <select
        value={value}
        onChange={event => onChange(event.target.value)}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none"
      >
        <option value={ALL}>All</option>
        {values.map(option => <option key={option} value={option}>{humanize(option)}</option>)}
      </select>
    </label>
  )
}


function VenueTable({ rows }: { rows: Venue[] }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border px-6 py-12 text-center text-sm text-muted-foreground">
        No venues match these filters.
      </div>
    )
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="w-full min-w-[1120px] text-left text-sm">
        <thead className="bg-muted/50 text-[10px] uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-4 py-3 font-semibold">Venue</th>
            <th className="px-4 py-3 font-semibold">Type</th>
            <th className="px-4 py-3 font-semibold">Country</th>
            <th className="px-4 py-3 font-semibold">Timezone</th>
            <th className="px-4 py-3 font-semibold">Calendar</th>
            <th className="px-4 py-3 font-semibold">Cutoff</th>
            <th className="px-4 py-3 text-right font-semibold">Instruments</th>
            <th className="px-4 py-3 font-semibold">Source</th>
            <th className="px-4 py-3 font-semibold">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map(row => (
            <tr key={row.id} className="hover:bg-muted/25">
              <td className="px-4 py-3">
                <div className="font-semibold">{row.name}</div>
                <code className="mt-1 block text-[11px] text-muted-foreground">{row.code}</code>
              </td>
              <td className="px-4 py-3 text-muted-foreground">{humanize(row.venue_type)}</td>
              <td className="px-4 py-3 text-muted-foreground">{row.country_code ?? "Global"}</td>
              <td className="px-4 py-3 font-mono text-xs">{row.timezone_name}</td>
              <td className="px-4 py-3"><code className="text-xs">{row.trading_calendar_code}</code></td>
              <td className="px-4 py-3 font-mono text-xs">{formatTime(row.session_cutoff_time)}</td>
              <td className="px-4 py-3 text-right tabular-nums">
                <div className="font-medium">{fmtInt(row.active_instrument_count)} active</div>
                <div className="mt-1 text-xs text-muted-foreground">{fmtInt(row.instrument_count)} total</div>
              </td>
              <td className="px-4 py-3 text-xs text-muted-foreground">{row.source}</td>
              <td className="px-4 py-3">
                <span className={cn(
                  "inline-flex rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide",
                  row.is_active ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-muted text-muted-foreground",
                )}>
                  {row.is_active ? "Active" : "Inactive"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


function formatTime(value: string) {
  return value.slice(0, 5)
}


function humanize(value: string) {
  return value.replaceAll("_", " ").toLocaleLowerCase().replace(/\b\w/g, character => character.toLocaleUpperCase())
}
