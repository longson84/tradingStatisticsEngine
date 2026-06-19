import { useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { Sidebar } from "@/components/Sidebar"
import { StrategyAnalysisResults } from "@/components/backtest/StrategyAnalysisResults"
import { smaStrategyAnalysisApi } from "@/lib/api"
import type { MaType, DataSource } from "@/lib/api"

const DATA_SOURCES: Array<{ label: string; value: DataSource }> = [
  { label: "Yahoo Finance", value: "yfinance" },
  { label: "VN Stock",      value: "vnstock" },
]

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span className="block text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-1">
      {children}
    </span>
  )
}

function FormSelect<T extends string>({
  value, onChange, options,
}: {
  value: T
  onChange: (v: T) => void
  options: Array<{ label: string; value: T }>
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value as T)}
      className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground focus:outline-none focus:border-ring"
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

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

type FrozenParams = Parameters<typeof smaStrategyAnalysisApi>[0]

export function SmaStrategyPage() {
  const [symbol, setSymbol]               = useState("MSFT")
  const [dataSource, setDataSource]       = useState<DataSource>("yfinance")
  const maType: MaType = "sma"
  const [maLength, setMaLength]           = useState(50)
  const [buyLag, setBuyLag]               = useState(0)
  const [sellLag, setSellLag]             = useState(0)
  const [initialCapital, setInitialCapital] = useState(10_000)
  const [fromDate, setFromDate]           = useState("")

  const [frozenParams, setFrozenParams] = useState<FrozenParams | null>(null)

  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["sma-strategy-analysis", frozenParams],
    queryFn: () => smaStrategyAnalysisApi(frozenParams!),
    enabled: frozenParams != null,
    retry: false,
  })

  const handleRun = useCallback(() => {
    setFrozenParams({
      symbol,
      ma_type: maType,
      ma_length: maLength,
      buy_lag: buyLag,
      sell_lag: sellLag,
      initial_capital: initialCapital,
      data_source: dataSource,
      start: fromDate.trim() || undefined,
    })
    refetch()
  }, [symbol, maLength, buyLag, sellLag, initialCapital, dataSource, fromDate, refetch])

  const controls = (
    <div className="space-y-4">
      <div>
        <Label>Data Source</Label>
        <FormSelect value={dataSource} onChange={setDataSource} options={DATA_SOURCES} />
      </div>

      <div>
        <Label>Ticker</Label>
        <input
          type="text"
          value={symbol}
          onChange={e => setSymbol(e.target.value.toUpperCase())}
          placeholder="e.g. MSFT"
          className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground uppercase placeholder:normal-case placeholder:text-muted-foreground focus:outline-none focus:border-ring"
        />
      </div>

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
        disabled={isFetching || !symbol.trim()}
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
          <StrategyAnalysisResults data={data} sellLag={frozenParams?.sell_lag ?? sellLag} />
        )}
      </main>
    </div>
  )
}
