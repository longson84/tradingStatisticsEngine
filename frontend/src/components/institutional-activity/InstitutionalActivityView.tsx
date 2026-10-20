import { Badge } from "@/components/ui/badge"
import type { InstitutionalActivityResponse } from "@/lib/api"
import { fmtDate, fmtInt, fmtPct } from "@/lib/format"


const ACTION_LABELS: Record<string, string> = {
  new: "New",
  added: "Added",
  unchanged: "Unchanged",
  reduced: "Reduced",
  exited: "Exited",
}


export function InstitutionalActivityView({
  result,
}: {
  result: InstitutionalActivityResponse
}) {
  if (result.status !== "available") {
    return (
      <section role="status" className="rounded-lg border border-dashed border-border p-8 text-center">
        <h2 className="font-semibold">Institutional Activity is not available</h2>
        <p className="mt-2 text-sm text-muted-foreground">{result.message}</p>
      </section>
    )
  }
  const conservative = [...result.changes, ...result.current_holders]
    .some(row => row.availability_precision === "filing_date_conservative")
  return (
    <>
      <section className="mb-5 rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-bold">{result.symbol}</h2>
          {result.venue_code && <Badge variant="outline">{result.venue_code}</Badge>}
          <Badge variant="secondary">SEC Form 13F</Badge>
        </div>
        <p className="mt-2 text-sm">
          Holdings as of <strong>{fmtDate(result.latest_report_period)}</strong>. Filed data available {result.latest_available_at ? new Date(result.latest_available_at).toLocaleString() : "—"}.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Reported position changes compare consecutive quarter-end filings. They are delayed disclosures and inferred changes, not confirmed executions, trade dates, or execution prices.
        </p>
        {conservative && <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">Some filings use conservative next-day availability because the quarterly archive did not contain an exact acceptance timestamp.</p>}
      </section>

      <section className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-label="Reported position changes">
        {(["new", "added", "reduced", "exited", "unchanged"] as const).map(action => (
          <div key={action} className="rounded-lg border border-border bg-card p-4">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{ACTION_LABELS[action]}</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">{fmtInt(result.action_counts[action] ?? 0)}</div>
          </div>
        ))}
      </section>

      <HistoryChart result={result} />

      <section className="mb-5 overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="font-semibold">Reported position changes</h2>
          <p className="text-xs text-muted-foreground">Latest report period compared with the immediately preceding stored period.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[940px] text-sm">
            <thead className="bg-muted/40 text-left text-xs"><tr><th className="px-4 py-2">Manager</th><th>Action</th><th>Previous shares</th><th>Current shares</th><th>Change</th><th>Portfolio date</th><th>Source</th></tr></thead>
            <tbody>{result.changes.map(row => <tr key={row.manager_id} className="border-t border-border">
              <td className="px-4 py-3 font-medium">{row.manager_name}{row.is_curated && <Badge variant="secondary" className="ml-2">Curated manager</Badge>}</td>
              <td>{ACTION_LABELS[row.action] ?? row.action}</td>
              <td className="tabular-nums">{fmtInt(row.previous_shares)}</td>
              <td className="tabular-nums">{fmtInt(row.current_shares)}</td>
              <td className="tabular-nums">{signedInt(row.share_change)}{row.percentage_change == null ? "" : ` (${signedPct(row.percentage_change)})`}</td>
              <td>{fmtDate(row.report_period)}</td>
              <td><a href={row.source_url} target="_blank" rel="noreferrer" className="font-medium text-primary underline">SEC filing</a></td>
            </tr>)}</tbody>
          </table>
        </div>
        {result.changes.length === 0 && <p className="p-6 text-sm text-muted-foreground">Two consecutive stored report periods are required before changes can be classified.</p>}
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3"><h2 className="font-semibold">Current reported holders</h2></div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-sm">
            <thead className="bg-muted/40 text-left text-xs"><tr><th className="px-4 py-2">Manager</th><th>Reported shares</th><th>Portfolio date</th><th>Source</th></tr></thead>
            <tbody>{result.current_holders.map(row => <tr key={row.manager_id} className="border-t border-border">
              <td className="px-4 py-3 font-medium">{row.manager_name}{row.is_curated && <Badge variant="secondary" className="ml-2">Curated manager</Badge>}</td>
              <td className="tabular-nums">{fmtInt(row.shares)}</td>
              <td>{fmtDate(row.report_period)}</td>
              <td><a href={row.source_url} target="_blank" rel="noreferrer" className="font-medium text-primary underline">SEC filing</a></td>
            </tr>)}</tbody>
          </table>
        </div>
      </section>
    </>
  )
}


function HistoryChart({ result }: { result: InstitutionalActivityResponse }) {
  const high = Math.max(...result.history.map(row => row.total_shares), 1)
  const width = Math.max(640, result.history.length * 90 + 80)
  const step = (width - 70) / Math.max(result.history.length, 1)
  return <section className="mb-5 rounded-xl border border-border bg-card p-5">
    <h2 className="font-semibold">Reported shares by quarter</h2>
    <p className="mt-1 text-xs text-muted-foreground">Common-stock positions only; puts and calls are excluded.</p>
    <div className="mt-3 overflow-x-auto"><svg role="img" aria-label="Reported shares by quarter" width={width} height={260}>
      <title>Reported shares by quarter</title>
      {result.history.map((row, index) => {
        const height = row.total_shares / high * 180
        const x = 45 + index * step
        return <g key={row.report_period}>
          <title>{`${row.report_period}: ${fmtInt(row.total_shares)} shares across ${row.holder_count} holders`}</title>
          <rect x={x} y={205 - height} width={Math.max(20, step - 24)} height={height} fill="#2563eb" rx={2} />
          <text x={x} y={225} fontSize={10} fill="currentColor">{fmtDate(row.report_period)}</text>
        </g>
      })}
    </svg></div>
  </section>
}


function signedInt(value: number): string {
  return `${value > 0 ? "+" : ""}${fmtInt(value)}`
}


function signedPct(value: number): string {
  return `${value > 0 ? "+" : ""}${fmtPct(value)}`
}
