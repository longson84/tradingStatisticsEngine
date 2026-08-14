import { useMemo, useState } from "react"
import { ArrowUpDown } from "lucide-react"
import type { InstrumentCatalogItem } from "@/lib/api"
import { cn } from "@/lib/utils"


type InstrumentRow = InstrumentCatalogItem
type CoverageSortKey = "first_session" | "last_session" | "stored_sessions"
type SortDirection = "asc" | "desc"


export function InstrumentTable({ rows }: { rows: InstrumentRow[] }) {
  const [coverageSort, setCoverageSort] = useState<{
    key: CoverageSortKey
    direction: SortDirection
  } | null>(null)
  const displayRows = useMemo(() => {
    if (!coverageSort) return rows
    return [...rows].sort((left, right) => {
      const leftValue = left[coverageSort.key]
      const rightValue = right[coverageSort.key]
      if (leftValue == null && rightValue == null) {
        return left.symbol.localeCompare(right.symbol)
      }
      if (leftValue == null) return 1
      if (rightValue == null) return -1
      const comparison = typeof leftValue === "number"
        ? leftValue - Number(rightValue)
        : String(leftValue).localeCompare(String(rightValue))
      return coverageSort.direction === "asc" ? comparison : -comparison
    })
  }, [coverageSort, rows])

  function toggleCoverageSort(key: CoverageSortKey) {
    setCoverageSort(current => ({
      key,
      direction: current?.key === key && current.direction === "asc" ? "desc" : "asc",
    }))
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full min-w-[1240px] text-sm">
        <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Symbol</th>
            <th className="px-3 py-2 text-left font-medium">Issuer</th>
            <th className="px-3 py-2 text-left font-medium">Sector</th>
            <th className="px-3 py-2 text-left font-medium">Industry</th>
            <th className="px-3 py-2 text-left font-medium">Venue</th>
            <SortableCoverageHeader
              label="First session"
              active={coverageSort?.key === "first_session"}
              direction={coverageSort?.key === "first_session" ? coverageSort.direction : null}
              onClick={() => toggleCoverageSort("first_session")}
            />
            <SortableCoverageHeader
              label="Last session"
              active={coverageSort?.key === "last_session"}
              direction={coverageSort?.key === "last_session" ? coverageSort.direction : null}
              onClick={() => toggleCoverageSort("last_session")}
            />
            <SortableCoverageHeader
              label="Sessions"
              active={coverageSort?.key === "stored_sessions"}
              direction={coverageSort?.key === "stored_sessions" ? coverageSort.direction : null}
              onClick={() => toggleCoverageSort("stored_sessions")}
            />
            <th className="px-3 py-2 text-left font-medium">Universe</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {displayRows.map(row => (
              <tr key={row.id} className="hover:bg-muted/30">
                <td className="px-3 py-2 font-semibold tabular-nums">{row.symbol}</td>
                <td className="min-w-72 px-3 py-2">{row.company_name ?? "n/a"}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.sector ?? "n/a"}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.industry ?? "n/a"}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.venue_code ?? "n/a"}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {row.first_session ?? "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {row.last_session ?? "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {row.stored_sessions.toLocaleString()}
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1.5">
                    {row.universes.map(list => (
                      <span
                        key={list}
                        className={cn(
                          "inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold",
                          listBadgeTone(list)
                        )}
                      >
                        {listBadgeLabel(list)}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
          ))}
          {displayRows.length === 0 && (
            <tr>
              <td colSpan={9} className="px-3 py-10 text-center text-muted-foreground">
                No instruments match the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}


function SortableCoverageHeader({
  label,
  active,
  direction,
  onClick,
}: {
  label: string
  active: boolean
  direction: SortDirection | null
  onClick: () => void
}) {
  return (
    <th
      className="px-3 py-2 text-right font-medium"
      aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={onClick}
        className="ml-auto inline-flex items-center gap-1 hover:text-foreground"
      >
        {label}
        <ArrowUpDown size={12} aria-hidden="true" />
      </button>
    </th>
  )
}


function listBadgeLabel(list: string): string {
  if (list === "US100") return "Nasdaq 100"
  if (list === "US500") return "S&P 500"
  if (list === "US2000") return "Russell 2000"
  if (list === "US30") return "Dow Jones"
  if (list === "VNMID") return "VNMidCap"
  if (list === "VNSML") return "VNSmallCap"
  if (list === "VNALL") return "VNAllshare"
  return list
}


function listBadgeTone(list: string): string {
  if (list === "US100") return "bg-sky-500/18 text-sky-800 dark:text-sky-200"
  if (list === "US500") return "bg-emerald-500/18 text-emerald-800 dark:text-emerald-200"
  if (list === "US2000") return "bg-purple-500/18 text-purple-800 dark:text-purple-200"
  if (list === "US30") return "bg-amber-500/22 text-amber-900 dark:text-amber-200"
  if (list === "VN30") return "bg-red-500/18 text-red-800 dark:text-red-200"
  if (list === "VN100") return "bg-violet-500/18 text-violet-800 dark:text-violet-200"
  if (list === "VNMID") return "bg-amber-500/18 text-amber-900 dark:text-amber-200"
  if (list === "VNSML") return "bg-pink-500/18 text-pink-800 dark:text-pink-200"
  if (list === "VNALL") return "bg-teal-500/18 text-teal-800 dark:text-teal-200"
  return "bg-muted text-muted-foreground"
}
