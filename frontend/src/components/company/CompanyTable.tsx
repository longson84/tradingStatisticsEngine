import type { CompanyResponse, MarketHealthStockDistance } from "@/lib/api"
import { cn } from "@/lib/utils"


export type CompanyRow = CompanyResponse


export function CompanyTable({
  rows,
  healthBySymbol,
}: {
  rows: CompanyRow[]
  healthBySymbol?: Map<string, MarketHealthStockDistance>
}) {
  const showHealth = healthBySymbol != null
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full min-w-[980px] text-sm">
        <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Ticker</th>
            <th className="px-3 py-2 text-left font-medium">Company</th>
            <th className="px-3 py-2 text-left font-medium">Sector</th>
            <th className="px-3 py-2 text-left font-medium">Industry</th>
            <th className="px-3 py-2 text-left font-medium">Exchange</th>
            {showHealth && <th className="px-3 py-2 text-right font-medium">Price</th>}
            {showHealth && <th className="px-3 py-2 text-right font-medium">200D High</th>}
            {showHealth && <th className="px-3 py-2 text-right font-medium">Distance</th>}
            <th className="px-3 py-2 text-left font-medium">List</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map(row => {
            const health = healthBySymbol?.get(row.ticker)
            return (
              <tr key={`${row.market}-${row.ticker}`} className="hover:bg-muted/30">
                <td className="px-3 py-2 font-semibold tabular-nums">{row.ticker}</td>
                <td className="min-w-72 px-3 py-2">{row.company_name}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.sector ?? "n/a"}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.industry ?? "n/a"}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.exchange ?? "n/a"}</td>
                {showHealth && (
                  <td className="px-3 py-2 text-right tabular-nums">
                    {health ? health.current_price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "n/a"}
                  </td>
                )}
                {showHealth && (
                  <td className="px-3 py-2 text-right tabular-nums">
                    {health ? health.rolling_high.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "n/a"}
                  </td>
                )}
                {showHealth && (
                  <td className="px-3 py-2 text-right font-semibold tabular-nums">
                    {health ? `${health.distance.toFixed(2)}%` : "n/a"}
                  </td>
                )}
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1.5">
                    {row.lists.map(list => (
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
            )
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={showHealth ? 9 : 6} className="px-3 py-10 text-center text-muted-foreground">
                No companies match the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}


function listBadgeLabel(list: string): string {
  if (list === "US100") return "Nasdaq 100"
  if (list === "US500") return "S&P 500"
  if (list === "US2000") return "Russell 2000"
  if (list === "US30") return "Dow Jones"
  return list
}


function listBadgeTone(list: string): string {
  if (list === "US100") return "bg-sky-500/18 text-sky-800 dark:text-sky-200"
  if (list === "US500") return "bg-emerald-500/18 text-emerald-800 dark:text-emerald-200"
  if (list === "US2000") return "bg-purple-500/18 text-purple-800 dark:text-purple-200"
  if (list === "US30") return "bg-amber-500/22 text-amber-900 dark:text-amber-200"
  if (list === "VN30") return "bg-red-500/18 text-red-800 dark:text-red-200"
  if (list === "VN100") return "bg-violet-500/18 text-violet-800 dark:text-violet-200"
  return "bg-muted text-muted-foreground"
}
