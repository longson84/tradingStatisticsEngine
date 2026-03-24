import type { ZoneEntry } from "@/lib/api"
import { fmtPrice, fmtPct, fmtDate } from "@/lib/format"

interface Props {
  entries: ZoneEntry[]
}

function rowStyle(entry: ZoneEntry): React.CSSProperties {
  if (entry.is_active) return { backgroundColor: "rgba(234, 179, 8, 0.18)" }
  return { backgroundColor: "rgba(34, 197, 94, 0.10)" }
}

function rowTextColor(entry: ZoneEntry): string {
  if (entry.is_active) return "text-yellow-600 dark:text-yellow-200"
  return "text-emerald-600 dark:text-emerald-200"
}

export function ZoneEntryTable({ entries }: Props) {
  return (
    <div className="overflow-y-auto max-h-[640px] overflow-x-auto">
      <table className="w-full text-xs tabular-nums border-collapse min-w-[900px]">
        <thead className="sticky top-0 z-10 bg-background">
          <tr className="text-muted-foreground uppercase tracking-wide border-b border-border">
            <th className="py-2 px-2 text-left font-medium w-10">Lv</th>
            <th className="py-2 px-3 text-left font-medium">Start Date</th>
            <th className="py-2 px-2 text-center font-medium">Zone</th>
            <th className="py-2 px-3 text-right font-medium">Entry</th>
            <th className="py-2 px-3 text-right font-medium">Low</th>
            <th className="py-2 px-3 text-left font-medium">Low Date</th>
            <th className="py-2 px-3 text-right font-medium">MAE %</th>
            <th className="py-2 px-2 text-right font-medium">→ Low</th>
            <th className="py-2 px-3 text-left font-medium">Recovery</th>
            <th className="py-2 px-2 text-right font-medium">→ Rec</th>
            <th className="py-2 px-2 text-right font-medium">Children</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => {
            const color = rowTextColor(e)
            return (
              <tr
                key={i}
                style={rowStyle(e)}
                className={`border-b border-border/50 ${color}`}
              >
                {/* Level */}
                <td className="py-1.5 px-2 text-muted-foreground/50 text-center">{e.level}</td>

                {/* Start Date with indentation */}
                <td className="py-1.5 px-3 whitespace-nowrap">
                  <span style={{ paddingLeft: e.level * 14 + "px" }}>
                    {e.level > 0 && (
                      <span className="text-muted-foreground/30 mr-1">└─</span>
                    )}
                    <span className="font-medium">{fmtDate(e.start_date)}</span>
                  </span>
                </td>

                {/* Zone */}
                <td className="py-1.5 px-2 text-center font-bold">{e.zone_pct}%</td>

                {/* Entry price */}
                <td className="py-1.5 px-3 text-right font-medium">{fmtPrice(e.entry_price)}</td>

                {/* Low price */}
                <td className="py-1.5 px-3 text-right">{fmtPrice(e.low_price)}</td>

                {/* Low date */}
                <td className="py-1.5 px-3">{fmtDate(e.low_date)}</td>

                {/* MAE % */}
                <td className="py-1.5 px-3 text-right">{fmtPct(e.mae_pct)}</td>

                {/* → Low */}
                <td className="py-1.5 px-2 text-right text-muted-foreground">{e.days_to_low}</td>

                {/* Recovery date */}
                <td className="py-1.5 px-3">
                  {e.is_active ? (
                    <span className="font-semibold text-yellow-400">active</span>
                  ) : (
                    fmtDate(e.recovery_date)
                  )}
                </td>

                {/* → Rec */}
                <td className="py-1.5 px-2 text-right text-muted-foreground">
                  {e.days_to_recovery != null ? e.days_to_recovery : "—"}
                </td>

                {/* Children */}
                <td className="py-1.5 px-2 text-right text-muted-foreground/70">{e.children_count}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
