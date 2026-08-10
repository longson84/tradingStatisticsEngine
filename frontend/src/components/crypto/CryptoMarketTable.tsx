import type { CryptoMarketInstrument } from "@/lib/api"
import { fmtInt } from "@/lib/format"
import { cn } from "@/lib/utils"


export function CryptoMarketTable({
  instruments,
}: {
  instruments: CryptoMarketInstrument[]
}) {
  if (instruments.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card px-6 py-12 text-center">
        <div className="text-sm font-medium">No spot markets found</div>
        <p className="mt-1 text-xs text-muted-foreground">
          Try another search, venue, quote asset, or market status.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full min-w-[1240px] text-sm">
        <thead className="border-b border-border bg-muted/40 text-left text-[10px] uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-2.5 font-medium">Instrument</th>
            <th className="px-3 py-2.5 font-medium">Venue</th>
            <th className="px-3 py-2.5 font-medium">Base asset</th>
            <th className="px-3 py-2.5 font-medium">Quote asset</th>
            <th className="px-3 py-2.5 font-medium">Status</th>
            <th className="px-3 py-2.5 text-right font-medium">Tick size</th>
            <th className="px-3 py-2.5 text-right font-medium">Step size</th>
            <th className="px-3 py-2.5 text-right font-medium">Min notional</th>
            <th className="px-3 py-2.5 font-medium">Stored history</th>
            <th className="px-3 py-2.5 text-right font-medium">Sessions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {instruments.map(instrument => (
            <tr key={instrument.id} className="hover:bg-muted/25">
              <td className="px-3 py-3">
                <div className="font-semibold text-foreground">{instrument.symbol}</div>
              </td>
              <td className="px-3 py-3">
                <div className="font-medium">{instrument.venue_name}</div>
              </td>
              <td className="px-3 py-3 font-medium">{instrument.base_asset}</td>
              <td className="px-3 py-3 font-medium">{instrument.quote_asset}</td>
              <td className="px-3 py-3">
                <span className={cn(
                  "inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                  instrument.is_active
                    ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                    : "border-border bg-muted text-muted-foreground",
                )}>
                  {instrument.is_active ? "Trading" : "Inactive"}
                </span>
              </td>
              <td className="px-3 py-3 text-right font-mono text-xs tabular-nums">
                {formatRule(instrument.price_tick_size)}
              </td>
              <td className="px-3 py-3 text-right font-mono text-xs tabular-nums">
                {formatRule(instrument.quantity_step_size)}
              </td>
              <td className="px-3 py-3 text-right font-mono text-xs tabular-nums">
                {formatRule(instrument.minimum_notional)}
                {instrument.minimum_notional ? ` ${instrument.quote_asset}` : ""}
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


function formatRule(value: string | null | undefined): string {
  if (!value) return "—"
  if (value.length <= 14) return value
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric.toExponential(4) : value
}


function sourceLabel(source: string | null | undefined): string {
  if (source === "binance_public_data") return "Binance public archive"
  if (source === "binance_spot_rest") return "Binance Spot REST"
  return source ?? "Stored daily bars"
}
