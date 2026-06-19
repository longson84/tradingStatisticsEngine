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
  const lastBahDate   = Object.keys(equityBah).sort().at(-1) ?? ""
  const [page, setPage] = useState(0)
  const sorted     = [...trades].reverse()
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)
  const pageSlice  = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

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

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs tabular-nums border-collapse [&_td]:border-r [&_td]:border-border [&_th]:border-r [&_th]:border-border">
          <thead>
            {/* Group header */}
            <tr className="bg-muted/40 border-b border-border text-[9px] uppercase tracking-widest text-muted-foreground/70">
              <th colSpan={3} className="py-1.5 px-3 text-left font-semibold">Trade</th>
              <th colSpan={4} className="py-1.5 px-3 text-left font-semibold border-l border-border">Execution</th>
              <th colSpan={5} className="py-1.5 px-3 text-left font-semibold border-l border-border">Risk Metrics</th>
              <th colSpan={2} className="py-1.5 px-3 text-left font-semibold border-l border-border">Equity</th>
            </tr>
            {/* Column header */}
            <tr className="bg-card border-b border-border text-muted-foreground uppercase tracking-wide">
              <th className="py-2 px-2 text-left font-medium w-8">#</th>
              <th className="py-2 px-2 text-left font-medium">Entry</th>
              <th className="py-2 px-2 text-left font-medium">Exit</th>
              <th className="py-2 px-2 text-right font-medium border-l border-border">Entry Px</th>
              <th className="py-2 px-2 text-right font-medium">Exit Px</th>
              <th className="py-2 px-2 text-right font-medium">Return</th>
              <th className="py-2 px-2 text-right font-medium">Days</th>
              <th className="py-2 px-2 text-right font-medium border-l border-border">MAE</th>
              <th className="py-2 px-2 text-right font-medium">MAE Px</th>
              <th className="py-2 px-2 text-right font-medium">MFE</th>
              <th className="py-2 px-2 text-right font-medium">MFE Px</th>
              <th className="py-2 px-2 text-right font-medium">Retrace</th>
              <th className="py-2 px-2 text-right font-medium border-l border-border">Strat NAV</th>
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
              const bahNav   = equityBah[t.exit_date ?? lastBahDate]

              // Left-border stripe color
              const stripe = isOpen
                ? "rgba(234,179,8,0.7)"
                : retPct != null && retPct > 0
                ? "rgba(34,197,94,0.6)"
                : retPct != null && retPct < 0
                ? "rgba(239,68,68,0.55)"
                : "transparent"

              return (
                <tr
                  key={globalIndex}
                  className="border-b border-border hover:bg-blue-500/20 transition-colors group"
                >
                  {/* # — carries the colored left stripe */}
                  <td
                    className="py-1.5 px-2 text-muted-foreground/60 font-mono text-[10px]"
                    style={{ borderLeft: `3px solid ${stripe}` }}
                  >
                    {trades.length - globalIndex}
                  </td>

                  <td className="py-1.5 px-2 text-foreground">{fmtDate(t.entry_date)}</td>
                  <td className="py-1.5 px-2">
                    {isOpen
                      ? <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm bg-yellow-500/15 text-yellow-500 font-semibold text-[10px]">● Open</span>
                      : <span className="text-muted-foreground">{fmtDate(t.exit_date)}</span>
                    }
                  </td>

                  <td className="py-1.5 px-2 text-right text-foreground border-l border-border/30">{fmtPrice(t.entry_price)}</td>
                  <td className="py-1.5 px-2 text-right text-foreground">{t.exit_price != null ? fmtPrice(t.exit_price) : "—"}</td>

                  {/* Return — pill badge */}
                  <td className="py-1.5 px-2 text-right">
                    {retPct != null ? (
                      <span
                        className="inline-block px-1.5 py-0.5 rounded-sm text-[11px] font-bold"
                        style={{
                          color:           retPct > 0 ? "#15803d" : "#b91c1c",
                          backgroundColor: retPct > 0 ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.12)",
                        }}
                      >
                        {fmtPct(retPct)}
                      </span>
                    ) : <span className="text-muted-foreground">—</span>}
                  </td>

                  <td className="py-1.5 px-2 text-right text-muted-foreground">{t.holding_days != null ? fmtInt(t.holding_days) : "—"}</td>

                  <td className="py-1.5 px-2 text-right text-red-400 border-l border-border/30">{t.mae_pct != null ? fmtPct(t.mae_pct) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-muted-foreground">{t.mae_price != null ? fmtPrice(t.mae_price) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-green-500">{t.mfe_pct != null ? fmtPct(t.mfe_pct) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-muted-foreground">{t.mfe_price != null ? fmtPrice(t.mfe_price) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-muted-foreground">{t.retracement_pct != null ? fmtPct(t.retracement_pct) : "—"}</td>

                  <td className="py-1.5 px-2 text-right font-semibold text-blue-500 border-l border-border/30">{stratNav != null ? fmtInt(stratNav) : "—"}</td>
                  <td className="py-1.5 px-2 text-right text-muted-foreground">{bahNav != null ? fmtInt(bahNav) : "—"}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
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

function pageRange(current: number, total: number): number[] {
  const window = 5
  let start = Math.max(0, current - Math.floor(window / 2))
  const end = Math.min(total, start + window)
  start = Math.max(0, end - window)
  return Array.from({ length: end - start }, (_, i) => start + i)
}
