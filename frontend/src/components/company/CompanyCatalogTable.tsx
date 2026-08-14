import type { CompanyCatalogItem } from "@/lib/api"
import { cn } from "@/lib/utils"


export function CompanyCatalogTable({ companies }: { companies: CompanyCatalogItem[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full min-w-[1320px] text-sm">
        <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Company</th>
            <th className="px-3 py-2 text-left font-medium">Legal name</th>
            <th className="px-3 py-2 text-left font-medium">Domicile</th>
            <th className="px-3 py-2 text-left font-medium">Listing countries</th>
            <th className="px-3 py-2 text-left font-medium">Sector</th>
            <th className="px-3 py-2 text-left font-medium">Industry</th>
            <th className="px-3 py-2 text-left font-medium">Instruments</th>
            <th className="px-3 py-2 text-left font-medium">Exchanges</th>
            <th className="px-3 py-2 text-left font-medium">Universes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {companies.map(company => {
            const exchanges = unique(company.instruments.map(row => row.venue_code))
            const universes = unique(company.instruments.flatMap(row => row.universes))
            return (
              <tr key={company.id} className="align-top hover:bg-muted/30">
                <td className="min-w-64 px-3 py-2">
                  <div className="font-semibold">{company.display_name}</div>
                  {company.identifiers.map(identifier => (
                    <div
                      key={`${identifier.namespace}-${identifier.value}`}
                      className="mt-0.5 text-[11px] text-muted-foreground"
                    >
                      {identifierLabel(identifier.namespace)}: {identifier.value}
                    </div>
                  ))}
                </td>
                <td className="min-w-64 px-3 py-2 text-muted-foreground">
                  {company.legal_name ?? "n/a"}
                </td>
                <td className="px-3 py-2 font-medium">
                  {company.domicile_country_code ?? "Unknown"}
                </td>
                <td className="px-3 py-2 font-medium">
                  {company.listing_country_codes.join(", ") || "n/a"}
                </td>
                <td className="px-3 py-2 text-muted-foreground">
                  {company.sector ?? "n/a"}
                </td>
                <td className="min-w-64 px-3 py-2 text-muted-foreground">
                  {company.industry ?? "n/a"}
                </td>
                <td className="min-w-52 px-3 py-2">
                  <div className="flex flex-wrap gap-1.5">
                    {company.instruments.map(instrument => (
                      <span
                        key={instrument.id}
                        title={[
                          instrument.instrument_type.replaceAll("_", " "),
                          instrument.share_class,
                          instrument.currency,
                        ].filter(Boolean).join(" · ")}
                        className={cn(
                          "inline-flex rounded px-1.5 py-0.5 text-[11px] font-semibold",
                          instrument.is_active
                            ? "bg-sky-500/18 text-sky-800 dark:text-sky-200"
                            : "bg-muted text-muted-foreground line-through",
                        )}
                      >
                        {instrument.symbol}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2 text-muted-foreground">
                  {exchanges.join(", ") || "n/a"}
                </td>
                <td className="min-w-48 px-3 py-2">
                  <div className="flex flex-wrap gap-1.5">
                    {universes.map(universe => (
                      <span
                        key={universe}
                        className="inline-flex rounded bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground"
                      >
                        {universeLabel(universe)}
                      </span>
                    ))}
                    {universes.length === 0 && (
                      <span className="text-muted-foreground">n/a</span>
                    )}
                  </div>
                </td>
              </tr>
            )
          })}
          {companies.length === 0 && (
            <tr>
              <td colSpan={9} className="px-3 py-10 text-center text-muted-foreground">
                No companies match the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}


function unique(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value)))).sort()
}


function identifierLabel(namespace: string): string {
  if (namespace === "sec_cik") return "SEC CIK"
  return namespace.replaceAll("_", " ").toUpperCase()
}


function universeLabel(universe: string): string {
  if (universe === "US100") return "Nasdaq 100"
  if (universe === "US500") return "S&P 500"
  if (universe === "US2000") return "Russell 2000"
  if (universe === "US30") return "Dow Jones"
  if (universe === "VNMID") return "VNMidCap"
  if (universe === "VNSML") return "VNSmallCap"
  if (universe === "VNALL") return "VNAllshare"
  return universe
}
