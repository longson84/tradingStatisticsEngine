import { useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { Sidebar } from "@/components/Sidebar"
import { StrategyAnalysisResults } from "@/components/backtest/StrategyAnalysisResults"
import { AnalysisInstrumentSelector } from "@/components/forms/AnalysisInstrumentSelector"
import { FormLabel as Label } from "@/components/forms/FormSelect"
import { instrumentsApi, smaStrategyAnalysisApi } from "@/lib/api"
import type { MaType } from "@/lib/api"
import { useDebouncedValue } from "@/lib/useDebouncedValue"
import { AnalysisPanel } from "@/components/analysis/AnalysisPanel"
import { useAnalysisContext } from "@/lib/use-analysis-context"
import { usePersistedAnalysis } from "@/lib/use-persisted-analysis"

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
  const {
    scope,
    search,
    instrument,
    changeScope: setScope,
    changeSearch: setSearch,
    setInstrument,
  } = useAnalysisContext()
  const maType: MaType = "sma"
  const [maLength, setMaLength]           = useState(50)
  const [buyLag, setBuyLag]               = useState(0)
  const [sellLag, setSellLag]             = useState(2)
  const [initialCapital, setInitialCapital] = useState(10_000)
  const [fromDate, setFromDate]           = useState("")

  const [resultSellLag, setResultSellLag] = useState(sellLag)

  const debouncedSearch = useDebouncedValue(search.trim(), 300)
  const instruments = useQuery({
    queryKey: ["sma-instruments", scope, debouncedSearch],
    queryFn: () => instrumentsApi({ scope, search: debouncedSearch, limit: 20 }),
    enabled: debouncedSearch.length >= 3,
  })
  const {
    mutate: runAnalysis,
    data,
    isPending: isFetching,
    error,
  } = usePersistedAnalysis({
    storageKey: "sma-strategy",
    mutationFn: smaStrategyAnalysisApi,
  })

  const handleRun = useCallback(() => {
    if (!instrument) return
    setResultSellLag(sellLag)
    runAnalysis({
      instrument_id: instrument.id,
      ma_type: maType,
      ma_length: maLength,
      buy_lag: buyLag,
      sell_lag: sellLag,
      initial_capital: initialCapital,
      start: fromDate.trim() || undefined,
    })
  }, [instrument, maLength, buyLag, sellLag, initialCapital, fromDate, runAnalysis])

  const controls = (
    <div className="space-y-4">
      <AnalysisInstrumentSelector
        scope={scope}
        search={search}
        instruments={instruments.data?.instruments ?? []}
        selectedInstrument={instrument}
        total={instruments.data?.total}
        isPending={instruments.isFetching}
        onScopeChange={value => {
          setScope(value)
          setSearch("")
          setInstrument(null)
        }}
        onSearchChange={value => {
          setSearch(value)
          setInstrument(null)
        }}
        onInstrumentChange={setInstrument}
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
        disabled={isFetching || !instrument}
        className="w-full py-2 rounded bg-destructive hover:bg-destructive/90 disabled:opacity-40 disabled:cursor-not-allowed text-destructive-foreground text-sm font-semibold transition-colors"
      >
        {isFetching ? "Running…" : "Run Analysis"}
      </button>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <AnalysisPanel>{controls}</AnalysisPanel>

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
            {data.is_stale && (
              <div className="mb-4 rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-700 dark:text-amber-300">
                Stored data ends at {data.data_last_session}; expected {data.expected_last_session}. Update this instrument through Data Operations before treating the analysis as current.
              </div>
            )}
            <StrategyAnalysisResults data={data} sellLag={resultSellLag} />
          </>
        )}
      </main>
    </div>
  )
}
