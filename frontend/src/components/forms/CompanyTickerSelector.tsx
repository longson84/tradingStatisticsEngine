import { FormLabel, FormSelect } from "@/components/forms/FormSelect"
import type { CompanyResponse, CompanyUniverseId } from "@/lib/api"


export type CompanyMarket = Extract<CompanyUniverseId, "US_ALL" | "VN_ALL">

const COMPANY_MARKET_OPTIONS: Array<{ label: string; value: CompanyMarket }> = [
  { label: "US Companies", value: "US_ALL" },
  { label: "VN Companies", value: "VN_ALL" },
]


export function CompanyTickerSelector({
  market,
  ticker,
  companies,
  total,
  isPending,
  id,
  onMarketChange,
  onTickerChange,
  onSubmit,
}: {
  market: CompanyMarket
  ticker: string
  companies: CompanyResponse[]
  total?: number
  isPending: boolean
  id: string
  onMarketChange: (market: CompanyMarket) => void
  onTickerChange: (ticker: string) => void
  onSubmit?: () => void
}) {
  const normalized = ticker.toUpperCase().trim()
  const valid = companies.some(item => item.ticker.toUpperCase() === normalized)
  return (
    <>
      <div>
        <FormLabel>Company list</FormLabel>
        <FormSelect
          value={market}
          onChange={value => {
            onMarketChange(value)
            onTickerChange("")
          }}
          options={COMPANY_MARKET_OPTIONS}
        />
      </div>
      <div>
        <FormLabel>Ticker</FormLabel>
        <input
          list={id}
          value={ticker}
          onChange={event => onTickerChange(event.target.value.toUpperCase())}
          onKeyDown={event => {
            if (event.key === "Enter" && valid) onSubmit?.()
          }}
          placeholder={isPending ? "Loading tickers…" : "Search ticker or company"}
          className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:border-ring focus:outline-none"
          aria-label="Ticker"
        />
        <datalist id={id}>
          {companies.map(item => (
            <option
              key={`${item.market}-${item.ticker}`}
              value={item.ticker}
              label={`${item.ticker} · ${item.company_name}`}
            />
          ))}
        </datalist>
        <p className="mt-1 text-[10px] text-muted-foreground">
          {total != null
            ? `${total.toLocaleString()} PostgreSQL companies available`
            : "Choose from the PostgreSQL company universe."}
        </p>
      </div>
    </>
  )
}
