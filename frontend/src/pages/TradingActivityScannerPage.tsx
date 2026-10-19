import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ScanSearch } from "lucide-react"

import { Sidebar } from "@/components/Sidebar"
import { TradingActivityScannerResults } from "@/components/trading-activity/TradingActivityScannerResults"
import {
  tradingActivityScannerApi,
  universesApi,
  watchlistsApi,
  type TradingActivityScannerScopeType,
} from "@/lib/api"


export function TradingActivityScannerPage() {
  const [scopeType, setScopeType] = useState<TradingActivityScannerScopeType>("universe")
  const [scopeId, setScopeId] = useState("")
  const universes = useQuery({ queryKey: ["universes"], queryFn: universesApi })
  const watchlists = useQuery({ queryKey: ["watchlists"], queryFn: watchlistsApi })
  const options = useMemo(() => scopeType === "universe"
    ? (universes.data?.universes ?? [])
      .filter(universe => universe.venue_codes.some(code => ["HOSE", "HNX", "UPCOM"].includes(code)))
      .map(universe => ({ id: universe.code, label: `${universe.name} (${universe.active_instrument_count})` }))
    : (watchlists.data?.watchlists ?? [])
      .map(watchlist => ({ id: String(watchlist.id), label: `${watchlist.name} (${watchlist.member_count})` })),
  [scopeType, universes.data, watchlists.data])

  const activeScopeId = options.some(option => option.id === scopeId)
    ? scopeId
    : options[0]?.id ?? ""

  const scan = useQuery({
    queryKey: ["trading-activity-scanner", scopeType, activeScopeId],
    queryFn: () => tradingActivityScannerApi({ scope_type: scopeType, scope_id: activeScopeId }),
    enabled: activeScopeId.length > 0,
    // A return from Data Operations or collection editing must reread PostgreSQL.
    staleTime: 0,
    refetchOnMount: "always",
    retry: false,
  })

  return <div className="flex min-h-screen bg-background text-foreground">
    <Sidebar />
    <main className="min-w-0 flex-1 overflow-y-auto p-6">
      <header className="mb-6 border-b border-border pb-5">
        <div className="flex items-center gap-2"><ScanSearch size={21} className="text-primary" /><h1 className="text-2xl font-bold">Trading Activity Scanner</h1></div>
        <p className="mt-1 text-sm text-muted-foreground">Rank stored Vietnam equity turnover intensity across a Universe or Watchlist. This analysis reads PostgreSQL only and never fetches Vnstock data.</p>
      </header>

      <section className="mb-5 rounded-xl border border-border bg-card p-5">
        <div className="grid gap-4 md:grid-cols-[220px_minmax(280px,1fr)]">
          <label className="text-xs font-medium">Collection type
            <select value={scopeType} onChange={event => { setScopeType(event.target.value as TradingActivityScannerScopeType); setScopeId("") }} className="mt-1 block h-10 w-full rounded-md border border-input bg-background px-3 text-sm">
              <option value="universe">Universe</option><option value="watchlist">Watchlist</option>
            </select>
          </label>
          <label className="text-xs font-medium">{scopeType === "universe" ? "Universe" : "Watchlist"}
            <select value={activeScopeId} onChange={event => setScopeId(event.target.value)} disabled={options.length === 0} className="mt-1 block h-10 w-full rounded-md border border-input bg-background px-3 text-sm disabled:opacity-50">
              {options.length === 0 && <option value="">No collection available</option>}
              {options.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
            </select>
          </label>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">These native selectors support Up/Down arrow-key selection. Mixed watchlists remain visible; unsupported members are separated as unavailable.</p>
      </section>

      {activeScopeId && scan.isFetching && <div role="status" className="rounded-lg border border-border p-6 text-sm text-muted-foreground">Scanning stored trading activity…</div>}
      {scan.error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm"><h2 className="font-semibold">Scanner request failed</h2><p className="mt-1 text-muted-foreground">{scan.error.message}</p></div>}
      {scan.data && !scan.isFetching && <TradingActivityScannerResults result={scan.data} />}
      {!activeScopeId && !scan.isFetching && <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">Choose a collection with at least one member.</div>}
    </main>
  </div>
}
