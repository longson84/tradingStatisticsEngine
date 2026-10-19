import { Link } from "react-router"

import { Badge } from "@/components/ui/badge"
import type { TradingActivityScannerResponse } from "@/lib/api"
import { fmtDate, fmtNum, fmtPct } from "@/lib/format"


type ScannerItem = TradingActivityScannerResponse["items"][number]
type ScannerStatus = ScannerItem["status"]

const SECTIONS: { status: ScannerStatus; title: string; description: string }[] = [
  { status: "current", title: "Current ranked activity", description: "Usable observations on the latest stored collection session, ranked by turnover intensity." },
  { status: "stale", title: "Stale observations", description: "The newest stored observation predates the collection session and is not ranked." },
  { status: "insufficient_history", title: "Insufficient 20-session history", description: "The observation is current, but fewer than 20 prior stored sessions are available for its anomaly baseline." },
  { status: "unavailable", title: "Unavailable", description: "The instrument is unsupported, has no stored activity, or has invalid inputs." },
]

const REASONS: Record<string, string> = {
  unsupported_instrument: "Trade history is not supported for this instrument.",
  no_stored_activity: "No stored trading activity.",
  insufficient_history: "Fewer than 20 prior stored sessions.",
  invalid_total_value: "Stored total value is invalid.",
  invalid_market_cap: "Stored market capitalization is invalid.",
  non_positive_market_cap: "Stored market capitalization is not positive.",
  invalid_baseline_window: "The prior 20-session window contains invalid observations.",
  zero_baseline_variance: "The prior 20-session window has no variation.",
}

export function TradingActivityScannerResults({ result }: { result: TradingActivityScannerResponse }) {
  return <div className="space-y-5">
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{result.scope_name}</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Latest stored completed session: <strong className="text-foreground">{fmtDate(result.target_session)}</strong>.
            {" "}Calculated from PostgreSQL activity only. No provider calls.
          </p>
        </div>
        <Badge variant="outline">{result.formula_version} · {result.baseline_sessions}-session baseline</Badge>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {SECTIONS.map(section => <div key={section.status} className="rounded-lg border border-border p-3">
          <div className="text-xs text-muted-foreground">{section.title}</div>
          <div className="mt-1 text-xl font-semibold tabular-nums">{result.counts[section.status]}</div>
        </div>)}
      </div>
    </section>

    {SECTIONS.map(section => {
      const items = result.items.filter(item => item.status === section.status)
      return <section key={section.status} className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="font-semibold">{section.title} <span className="text-muted-foreground">({items.length})</span></h2>
          <p className="mt-1 text-xs text-muted-foreground">{section.description}</p>
        </div>
        {items.length === 0
          ? <p className="p-5 text-sm text-muted-foreground">No instruments in this state.</p>
          : <ScannerTable items={items} />}
      </section>
    })}
  </div>
}

function ScannerTable({ items }: { items: ScannerItem[] }) {
  return <div className="overflow-x-auto">
    <table className="w-full whitespace-nowrap text-sm">
      <thead className="bg-muted text-left text-xs text-muted-foreground"><tr>
        <th className="px-4 py-3">Rank</th><th className="px-4 py-3">Instrument</th>
        <th className="px-4 py-3 text-right">Session</th><th className="px-4 py-3 text-right">Turnover intensity</th>
        <th className="px-4 py-3 text-right">20-session baseline</th><th className="px-4 py-3 text-right">Anomaly</th>
        <th className="px-4 py-3">Availability</th>
      </tr></thead>
      <tbody>{items.map(item => <tr key={item.instrument_id} className="border-t border-border">
        <td className="px-4 py-3 tabular-nums">{item.rank ?? "—"}</td>
        <td className="px-4 py-3">
          <Link className="font-semibold text-primary hover:underline" to={`/vietnam-market/trading-activity?instrument_id=${item.instrument_id}&symbol=${encodeURIComponent(item.symbol)}`}>{item.symbol}</Link>
          <div className="text-xs text-muted-foreground">{item.display_name ?? item.venue_code ?? "—"}</div>
        </td>
        <td className="px-4 py-3 text-right tabular-nums">{fmtDate(item.latest_session)}</td>
        <td className="px-4 py-3 text-right tabular-nums">{item.turnover_intensity == null ? "—" : fmtPct(item.turnover_intensity * 100)}</td>
        <td className="px-4 py-3 text-right tabular-nums">{item.baseline == null ? "—" : fmtPct(item.baseline * 100)}</td>
        <td className="px-4 py-3 text-right tabular-nums">{item.anomaly_score == null ? "—" : `${item.anomaly_score >= 0 ? "+" : ""}${fmtNum(item.anomaly_score)}σ`}</td>
        <td className="max-w-sm whitespace-normal px-4 py-3 text-xs text-muted-foreground">{item.unavailable_reason ? REASONS[item.unavailable_reason] : item.status === "stale" ? "Newer collection session exists." : "Available"}</td>
      </tr>)}</tbody>
    </table>
  </div>
}
