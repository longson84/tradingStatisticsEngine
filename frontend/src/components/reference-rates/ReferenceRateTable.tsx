import type { ReferenceRateInstrument } from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"


export function ReferenceRateTable({
  instruments,
}: {
  instruments: ReferenceRateInstrument[]
}) {
  if (instruments.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card px-6 py-12 text-center">
        <div className="text-sm font-medium">No reference rates found</div>
        <p className="mt-1 text-xs text-muted-foreground">
          Try another search, base asset, quote asset, or status.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full min-w-[980px] text-sm">
        <thead className="border-b border-border bg-muted/40 text-left text-[10px] uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-2.5 font-medium">Instrument</th>
            <th className="px-3 py-2.5 font-medium">Base asset</th>
            <th className="px-3 py-2.5 font-medium">Quote asset</th>
            <th className="px-3 py-2.5 font-medium">Provider</th>
            <th className="px-3 py-2.5 font-medium">Price basis</th>
            <th className="px-3 py-2.5 font-medium">Stored history</th>
            <th className="px-3 py-2.5 text-right font-medium">Sessions</th>
            <th className="px-3 py-2.5 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {instruments.map(instrument => (
            <tr key={instrument.id} className="hover:bg-muted/25">
              <td className="px-3 py-3">
                <div className="font-semibold text-foreground">{instrument.symbol}</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  Reference rate
                </div>
              </td>
              <td className="px-3 py-3">
                <div className="font-medium">{instrument.base_asset}</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  {instrument.base_asset_name}
                </div>
              </td>
              <td className="px-3 py-3">
                <div className="font-medium">{instrument.quote_asset}</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  {instrument.quote_asset_name}
                </div>
              </td>
              <td className="px-3 py-3">
                <div className="font-medium">{sourceLabel(instrument.catalog_source)}</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  yfinance adapter
                </div>
              </td>
              <td className="px-3 py-3 font-mono text-xs">
                {instrument.price_basis.replaceAll("_", " ")}
              </td>
              <td className="px-3 py-3">
                {instrument.first_session && instrument.last_session ? (
                  <>
                    <div className="text-xs text-foreground">
                      {instrument.first_session} → {instrument.last_session}
                    </div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">
                      {sourceLabel(instrument.price_source)}
                    </div>
                  </>
                ) : (
                  <span className="text-xs text-muted-foreground">Not imported</span>
                )}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">
                {fmtInt(instrument.stored_sessions)}
              </td>
              <td className="px-3 py-3">
                <span className={cn(
                  "inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                  instrument.is_active
                    ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                    : "border-border bg-muted text-muted-foreground",
                )}>
                  {instrument.is_active ? "Active" : "Inactive"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


function sourceLabel(source: string | null | undefined): string {
  if (source === "yahoo_finance") return "Yahoo Finance"
  return source ?? "—"
}
