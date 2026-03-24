import { useState } from "react"
import type { TradeRow } from "@/lib/api"
import { fmtDate, fmtPrice, fmtPct, fmtInt } from "@/lib/format"
import { SectionTitle } from "./SectionTitle"

const PAGE_SIZE = 20

interface Props {
  trades: TradeRow[]
  equityStrategy: Record<string, number>
  equityBah: Record<string, number>
}

export function TradeLog({ trades, equityStrategy, equityBah }: Props) {
  const lastStratDate = Object.keys(equityStrategy).sort().at(-1) ?? ""
  const lastBahDate = Object.keys(equityBah).sort().at(-1) ?? ""
  const [page, setPage] = useState(0)
  const sorted = [...trades].reverse()
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)
  const pageSlice = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  if (trades.length === 0) {
    return (
      <div>
        <SectionTitle>Trade Log</SectionTitle>
        <p className="text-sm text-muted-foreground italic">No trades.</p>
      </div>
    )
  }

  return (
    <div>
      <SectionTitle>Trade Log ({trades.length})</SectionTitle>
      <div className="overflow-x-auto">
        <table className="w-full text-xs tabular-nums border-collapse">
          <thead>
            <tr className="border-b border-border text-muted-foreground uppercase tracking-wide">
              <th className="py-2 px-2 text-left font-medium">#</th>
              <th className="py-2 px-2 text-left font-medium">Entry</th>
              <th className="py-2 px-2 text-left font-medium">Exit</th>
              <th className="py-2 px-2 text-right font-medium">Entry Px</th>
              <th className="py-2 px-2 text-right font-medium">Exit Px</th>
              <th className="py-2 px-2 text-right font-medium">Return</th>
              <th className="py-2 px-2 text-right font-medium">Days</th>
              <th className="py-2 px-2 text-right font-medium">MAE</th>
              <th className="py-2 px-2 text-right font-medium">MAE Px</th>
              <th className="py-2 px-2 text-right font-medium">MFE</th>
              <th className="py-2 px-2 text-right font-medium">MFE Px</th>
              <th className="py-2 px-2 text-right font-medium">Retrace</th>
              <th className="py-2 px-2 text-right font-medium">Strat NAV</th>
              <th className="py-2 px-2 text-right font-medium">BaH NAV</th>
            </tr>
          </thead>
          <tbody>
            {pageSlice.map((t, i) => {
              const globalIndex = page * PAGE_SIZE + i
              const isOpen = t.exit_date === null
              const retPct = t.return_pct
              const lookupDate = t.exit_date ?? lastStratDate
              const stratNav = equityStrategy[lookupDate]
              const bahNav = equityBah[t.exit_date ?? lastBahDate]
              const rowBg = isOpen
                ? "bg-yellow-950/20"
                : retPct != null && retPct > 0
                ? "bg-green-950/10"
                : retPct != null && retPct < 0
                ? "bg-red-950/10"
                : ""

              return (
                <tr key={globalIndex} className={`border-b border-border/40 ${rowBg}`}>
                  <td className="py-1.5 px-2 text-muted-foreground">{trades.length - globalIndex}</td>
                  <td className="py-1.5 px-2 text-foreground">{fmtDate(t.entry_date)}</td>
                  <td className="py-1.5 px-2 text-foreground">
                    {isOpen ? <span className="text-yellow-400 font-medium">Open</span> : fmtDate(t.exit_date)}
                  </td>
                  <td className="py-1.5 px-2 text-right text-foreground">{fmtPrice(t.entry_price)}</td>
                  <td className="py-1.5 px-2 text-right text-foreground">{t.exit_price != null ? fmtPrice(t.exit_price) : "—"}</td>
                  <td className={`py-1.5 px-2 text-right font-medium ${retPct != null ? (retPct > 0 ? "text-green-400" : "text-red-400") : "text-muted-foreground"}`}>
                    {retPct != null ? fmtPct(retPct) : "—"}
                  </td>
                  <td className="py-1.5 px-2 text-right text-foreground">{t.holding_days != null ? fmtInt(t.holding_days) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-red-400">{t.mae_pct != null ? fmtPct(t.mae_pct) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-muted-foreground">{t.mae_price != null ? fmtPrice(t.mae_price) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-green-400">{t.mfe_pct != null ? fmtPct(t.mfe_pct) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-muted-foreground">{t.mfe_price != null ? fmtPrice(t.mfe_price) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-muted-foreground">{t.retracement_pct != null ? fmtPct(t.retracement_pct) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-blue-400 font-medium">{stratNav != null ? fmtInt(stratNav) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-muted-foreground">{bahNav != null ? fmtInt(bahNav) : "—"}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 px-1">
          <span className="text-xs text-muted-foreground">
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, trades.length)} of {trades.length}
          </span>
          <div className="flex items-center gap-1">
            <PageBtn onClick={() => setPage(0)} disabled={page === 0} label="«" />
            <PageBtn onClick={() => setPage(p => p - 1)} disabled={page === 0} label="‹" />
            {pageRange(page, totalPages).map(p => (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={[
                  "w-7 h-7 rounded text-xs transition-colors",
                  p === page
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent",
                ].join(" ")}
              >
                {p + 1}
              </button>
            ))}
            <PageBtn onClick={() => setPage(p => p + 1)} disabled={page === totalPages - 1} label="›" />
            <PageBtn onClick={() => setPage(totalPages - 1)} disabled={page === totalPages - 1} label="»" />
          </div>
        </div>
      )}
    </div>
  )
}

function PageBtn({ onClick, disabled, label }: { onClick: () => void; disabled: boolean; label: string }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-7 h-7 rounded text-xs text-muted-foreground hover:text-foreground hover:bg-accent disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
    >
      {label}
    </button>
  )
}

/** Returns a window of up to 5 page indices centred on the current page. */
function pageRange(current: number, total: number): number[] {
  const window = 5
  let start = Math.max(0, current - Math.floor(window / 2))
  const end = Math.min(total, start + window)
  start = Math.max(0, end - window)
  return Array.from({ length: end - start }, (_, i) => start + i)
}
