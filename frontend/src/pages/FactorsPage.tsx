import { useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { Sidebar } from "@/components/Sidebar"
import { RarityResults } from "@/components/rarity/RarityResults"
import { rarityAnalysisApi } from "@/lib/api"
import type { FactorType, MaType, DataSource } from "@/lib/api"

// ── Per-factor dynamic param config ──────────────────────────────────────────

interface FactorOption {
  label: string
  value: FactorType
}

const FACTOR_OPTIONS: FactorOption[] = [
  { label: "Distance From Peak", value: "distance_from_peak" },
  { label: "Moving Average",     value: "moving_average" },
  { label: "Bollinger Bands",    value: "bollinger" },
  { label: "Donchian Channel",   value: "donchian" },
]

const DATA_SOURCES: Array<{ label: string; value: DataSource }> = [
  { label: "Yahoo Finance", value: "yfinance" },
  { label: "VN Stock",      value: "vnstock" },
  { label: "CSV",           value: "csv" },
]

const MA_TYPES: Array<{ label: string; value: MaType }> = [
  { label: "SMA", value: "sma" },
  { label: "EMA", value: "ema" },
  { label: "WMA", value: "wma" },
]

// ── Analysis type tabs ────────────────────────────────────────────────────────

type AnalysisType = "rarity"

const ANALYSIS_TABS: Array<{ label: string; value: AnalysisType }> = [
  { label: "Rarity Analysis", value: "rarity" },
]

// ── Small reusable form controls ──────────────────────────────────────────────

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span className="block text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-1">
      {children}
    </span>
  )
}

function FormSelect<T extends string>({
  value,
  onChange,
  options,
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
  value,
  onChange,
  min = 1,
  step = 1,
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

// ── Main page ─────────────────────────────────────────────────────────────────

export function FactorsPage() {
  // Form state
  const [symbol, setSymbol]         = useState("MSFT")
  const [dataSource, setDataSource] = useState<DataSource>("yfinance")
  const [factorType, setFactorType] = useState<FactorType>("distance_from_peak")
  const [period, setPeriod]         = useState(200)
  const [maType, setMaType]         = useState<MaType>("sma")
  const [stdDev, setStdDev]         = useState(2.0)
  const [qrDays, setQrDays]         = useState(5)
  const [activeTab, setActiveTab]   = useState<AnalysisType>("rarity")

  // Frozen params — only updated when user clicks Analyse
  const [frozenParams, setFrozenParams] = useState<Parameters<typeof rarityAnalysisApi>[0] | null>(null)

  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["rarity", frozenParams],
    queryFn: () => rarityAnalysisApi(frozenParams!),
    enabled: frozenParams != null,
    retry: false,
  })

  const handleAnalyse = useCallback(() => {
    setFrozenParams({
      symbol,
      factor_type: factorType,
      period,
      ma_type: maType,
      std_dev: stdDev,
      quick_recovery_days: qrDays,
      data_source: dataSource,
    })
    // If params are unchanged, force refetch
    refetch()
  }, [symbol, factorType, period, maType, stdDev, qrDays, dataSource, refetch])

  const controls = (
    <div className="space-y-4">
      {/* Data Source */}
      <div>
        <Label>Data Source</Label>
        <FormSelect value={dataSource} onChange={setDataSource} options={DATA_SOURCES} />
      </div>

      {/* Ticker */}
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

      {/* Factor */}
      <div>
        <Label>Factor</Label>
        <FormSelect value={factorType} onChange={setFactorType} options={FACTOR_OPTIONS} />
      </div>

      {/* Period (all factors have this) */}
      <div>
        <Label>Period</Label>
        <NumberInput value={period} onChange={setPeriod} min={2} />
      </div>

      {/* MA Type — moving_average only */}
      {factorType === "moving_average" && (
        <div>
          <Label>MA Type</Label>
          <FormSelect value={maType} onChange={setMaType} options={MA_TYPES} />
        </div>
      )}

      {/* Std Dev — bollinger only */}
      {factorType === "bollinger" && (
        <div>
          <Label>Std Deviation</Label>
          <NumberInput value={stdDev} onChange={setStdDev} min={0.5} step={0.5} />
        </div>
      )}

      {/* Quick Recovery Days */}
      <div>
        <Label>Quick Recovery (sessions)</Label>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setQrDays(d => Math.max(1, d - 1))}
            className="w-7 h-7 rounded bg-secondary hover:bg-secondary/80 text-secondary-foreground hover:text-secondary-foreground flex items-center justify-center text-base leading-none transition-colors"
          >
            −
          </button>
          <span className="flex-1 text-center text-sm text-foreground tabular-nums">{qrDays}</span>
          <button
            onClick={() => setQrDays(d => d + 1)}
            className="w-7 h-7 rounded bg-secondary hover:bg-secondary/80 text-secondary-foreground hover:text-secondary-foreground flex items-center justify-center text-base leading-none transition-colors"
          >
            +
          </button>
        </div>
      </div>

      {/* Analyse button */}
      <button
        onClick={handleAnalyse}
        disabled={isFetching || !symbol.trim()}
        className="w-full py-2 rounded bg-destructive hover:bg-destructive/90 disabled:opacity-40 disabled:cursor-not-allowed text-destructive-foreground text-sm font-semibold transition-colors"
      >
        {isFetching ? "Loading…" : "Analyse"}
      </button>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" children={controls} />

      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Analysis type tabs */}
        <div className="border-b border-border px-6 flex gap-1 pt-1">
          {ANALYSIS_TABS.map(tab => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={[
                "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
                activeTab === tab.value
                  ? "border-foreground text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              ].join(" ")}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Loading bar */}
          {isFetching && (
            <div className="mb-4 h-0.5 w-full bg-white/8 rounded overflow-hidden">
              <div className="h-full bg-red-500 animate-pulse w-2/3 rounded" />
            </div>
          )}

          {/* Error */}
          {error && !isFetching && (
            <div className="rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-300">
              {(error as Error).message}
            </div>
          )}

          {/* Empty state */}
          {!data && !isFetching && !error && (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground/40 text-sm">
              Configure the controls and click <span className="text-red-400 font-medium ml-1">Analyse</span>.
            </div>
          )}

          {/* Results */}
          {data && !isFetching && activeTab === "rarity" && (
            <RarityResults data={data} factorType={factorType} />
          )}
        </div>
      </main>
    </div>
  )
}
