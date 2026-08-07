import { useState, useCallback } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Sidebar } from "@/components/Sidebar"
import { StrategyAnalysisResults } from "@/components/backtest/StrategyAnalysisResults"
import {
  CompanyTickerSelector,
  type CompanyMarket,
} from "@/components/forms/CompanyTickerSelector"
import { FormLabel as Label } from "@/components/forms/FormSelect"
import { companiesApi, smaStrategyAnalysisApi } from "@/lib/api"
import type { MaType } from "@/lib/api"

function NumberInput({
  value, onChange, min = 0, step = 1,
}: {
  value: number
  onChange: (v: number) => void
  min?: number
  step?: number
}) {
  return (
    <input
      type="number"
      value={value}
      min={min}
      step={step}
      onChange={e => onChange(Number(e.target.value))}
      className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground focus:outline-none focus:border-ring"
    />
  )
}

export function SmaStrategyPage() {
  const [market, setMarket]               = useState<CompanyMarket>("US_ALL")
  const [symbol, setSymbol]               = useState("MSFT")
  const maType: MaType = "sma"
  const [maLength, setMaLength]           = useState(50)
  const [buyLag, setBuyLag]               = useState(0)
  const [sellLag, setSellLag]             = useState(2)
  const [initialCapital, setInitialCapital] = useState(10_000)
  const [fromDate, setFromDate]           = useState("")

  const [resultSellLag, setResultSellLag] = useState(sellLag)

  const companies = useQuery({
    queryKey: ["companies", market],
    queryFn: () => companiesApi({ universe: market }),
  })
  const {
    mutate: runAnalysis,
    data,
    isPending: isFetching,
    error,
  } = useMutation({
    mutationFn: smaStrategyAnalysisApi,
  })

  const handleRun = useCallback(() => {
    const valid = companies.data?.companies.some(
      item => item.ticker.toUpperCase() === symbol.toUpperCase().trim()
    )
    if (!valid) return
    setResultSellLag(sellLag)
    runAnalysis({
      market: market === "US_ALL" ? "US" : "VN",
      ticker: symbol.toUpperCase().trim(),
      ma_type: maType,
      ma_length: maLength,
      buy_lag: buyLag,
      sell_lag: sellLag,
      initial_capital: initialCapital,
      start: fromDate.trim() || undefined,
    })
  }, [companies.data, market, symbol, maLength, buyLag, sellLag, initialCapital, fromDate, runAnalysis])

  const selectedCompany = companies.data?.companies.some(
    item => item.ticker.toUpperCase() === symbol.toUpperCase().trim()
  ) ?? false

  const controls = (
    <div className="space-y-4">
      <CompanyTickerSelector
        market={market}
        ticker={symbol}
        companies={companies.data?.companies ?? []}
        total={companies.data?.total}
        isPending={companies.isPending}
        id="sma-strategy-symbols"
        onMarketChange={setMarket}
        onTickerChange={setSymbol}
        onSubmit={handleRun}
      />

      <div className="border-t border-border pt-4">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
          SMA Strategy
        </div>

        <div className="space-y-3">
          <div>
            <Label>SMA Length</Label>
            <NumberInput value={maLength} onChange={setMaLength} min={2} />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label>Buy Lag</Label>
              <NumberInput value={buyLag} onChange={setBuyLag} min={0} />
            </div>
            <div>
              <Label>Sell Lag</Label>
              <NumberInput value={sellLag} onChange={setSellLag} min={0} />
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-border pt-4 space-y-3">
        <div>
          <Label>Initial Capital</Label>
          <NumberInput value={initialCapital} onChange={setInitialCapital} min={100} step={1000} />
        </div>

        <div>
          <Label>From Date (optional)</Label>
          <input
            type="date"
            value={fromDate}
            onChange={e => setFromDate(e.target.value)}
            className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground focus:outline-none focus:border-ring"
          />
        </div>
      </div>

      <button
        onClick={handleRun}
        disabled={isFetching || !selectedCompany}
        className="w-full py-2 rounded bg-destructive hover:bg-destructive/90 disabled:opacity-40 disabled:cursor-not-allowed text-destructive-foreground text-sm font-semibold transition-colors"
      >
        {isFetching ? "Running…" : "Run Analysis"}
      </button>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" children={controls} />

      <main className="flex-1 overflow-y-auto p-6">
        <div className="mb-5 border-b border-border pb-4">
          <h1 className="text-2xl font-bold tracking-tight">SMA Strategy Analysis</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Single-symbol strategy analysis for price versus simple moving average.
          </p>
        </div>

        {isFetching && (
          <div className="mb-6 h-0.5 w-full bg-white/8 rounded overflow-hidden">
            <div className="h-full bg-red-500 animate-pulse w-2/3 rounded" />
          </div>
        )}

        {error && !isFetching && (
          <div className="rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-300">
            {(error as Error).message}
          </div>
        )}

        {!data && !isFetching && !error && (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground/40 text-sm">
            Configure the strategy and click{" "}
            <span className="text-red-400 font-medium ml-1">Run Analysis</span>.
          </div>
        )}

        {data && !isFetching && (
          <>
            {(data.refreshed || data.is_stale || data.refresh_warning) && (
              <div className={`mb-4 rounded-md border px-4 py-3 text-xs ${data.is_stale ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300" : "border-border bg-muted/30 text-muted-foreground"}`}>
                Data through {data.data_last_session}; expected {data.expected_last_session}.
                {data.refreshed ? " PostgreSQL was refreshed for this ticker." : ""}
                {data.refresh_warning ? ` ${data.refresh_warning}` : ""}
              </div>
            )}
            <StrategyAnalysisResults data={data} sellLag={resultSellLag} />
          </>
        )}
      </main>
    </div>
  )
}
