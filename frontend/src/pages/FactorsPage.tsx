import { useState, useCallback } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Sidebar } from "@/components/Sidebar"
import { FormLabel as Label, FormSelect } from "@/components/forms/FormSelect"
import { RarityResults } from "@/components/rarity/RarityResults"
import {
  CompanyTickerSelector,
  type CompanyMarket,
} from "@/components/forms/CompanyTickerSelector"
import { companiesApi, rarityAnalysisApi } from "@/lib/api"
import type { FactorType, MaType, RarityRecoveryMode } from "@/lib/api"

// ── Per-factor dynamic param config ──────────────────────────────────────────

interface FactorOption {
  label: string
  value: FactorType
}

const FACTOR_OPTIONS: FactorOption[] = [
  { label: "Distance From Peak", value: "distance_from_peak" },
  { label: "Distance From MA",   value: "distance_from_ma" },
  { label: "Moving Average",     value: "moving_average" },
  { label: "Bollinger Bands",    value: "bollinger" },
  { label: "Donchian Channel",   value: "donchian" },
]

const MA_TYPES: Array<{ label: string; value: MaType }> = [
  { label: "SMA", value: "sma" },
  { label: "EMA", value: "ema" },
  { label: "WMA", value: "wma" },
]

const RECOVERY_MODES: Array<{ label: string; value: RarityRecoveryMode }> = [
  { label: "Price recovers entry", value: "price" },
  { label: "Factor exits zone", value: "factor" },
]

// ── Analysis type tabs ────────────────────────────────────────────────────────

type AnalysisType = "rarity"

const ANALYSIS_TABS: Array<{ label: string; value: AnalysisType }> = [
  { label: "Rarity Analysis", value: "rarity" },
]

// ── Small reusable form controls ──────────────────────────────────────────────

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
  const [market, setMarket]         = useState<CompanyMarket>("US_ALL")
  const [symbol, setSymbol]         = useState("MSFT")
  const [factorType, setFactorType] = useState<FactorType>("distance_from_peak")
  const [period, setPeriod]         = useState(200)
  const [maType, setMaType]         = useState<MaType>("sma")
  const [stdDev, setStdDev]         = useState(2.0)
  const [recoveryMode, setRecoveryMode] = useState<RarityRecoveryMode>("price")
  const [qrDays, setQrDays]         = useState(5)
  const [activeTab, setActiveTab]   = useState<AnalysisType>("rarity")

  const companies = useQuery({
    queryKey: ["companies", market],
    queryFn: () => companiesApi({ universe: market }),
  })

  const {
    mutate: runAnalysis,
    data,
    error,
    isPending: isFetching,
  } = useMutation({
    mutationFn: rarityAnalysisApi,
  })

  const handleAnalyse = useCallback(() => {
    const valid = companies.data?.companies.some(
      item => item.ticker.toUpperCase() === symbol.toUpperCase().trim()
    )
    if (!valid) return
    runAnalysis({
      market: market === "US_ALL" ? "US" : "VN",
      ticker: symbol.toUpperCase().trim(),
      factor_type: factorType,
      period,
      ma_type: maType,
      std_dev: stdDev,
      quick_recovery_days: qrDays,
      recovery_mode: recoveryMode,
    })
  }, [companies.data, market, symbol, factorType, period, maType, stdDev, recoveryMode, qrDays, runAnalysis])

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
        id="factor-rarity-symbols"
        onMarketChange={setMarket}
        onTickerChange={setSymbol}
        onSubmit={handleAnalyse}
      />

      {/* Factor */}
      <div>
        <Label>Factor</Label>
        <FormSelect value={factorType} onChange={setFactorType} options={FACTOR_OPTIONS} />
      </div>

      <div>
        <Label>Period</Label>
        <NumberInput value={period} onChange={setPeriod} min={2} />
      </div>

      {/* MA Type — MA-based factors only */}
      {(factorType === "moving_average" || factorType === "distance_from_ma") && (
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

      <div>
        <Label>Recovery Mode</Label>
        <FormSelect value={recoveryMode} onChange={setRecoveryMode} options={RECOVERY_MODES} />
      </div>

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
        disabled={isFetching || !selectedCompany}
        className="w-full py-2.5 rounded-md bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed text-primary-foreground text-sm font-semibold transition-colors tracking-wide"
      >
        {isFetching ? "Analysing…" : "Analyse"}
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
            <div className="mb-4 h-0.5 w-full bg-border rounded overflow-hidden relative">
              <div
                className="absolute h-full w-1/3 bg-primary rounded"
                style={{ animation: "progress-slide 1.2s ease-in-out infinite" }}
              />
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
            <div className="flex flex-col items-center justify-center h-64 gap-2">
              <div className="text-muted-foreground/30 text-4xl font-thin tracking-widest">TSE</div>
              <p className="text-muted-foreground/40 text-sm">Configure the controls and click <span className="text-foreground/60 font-medium">Analyse</span></p>
            </div>
          )}

          {/* Results */}
          {data && !isFetching && activeTab === "rarity" && (
            <>
              {(data.refreshed || data.is_stale || data.refresh_warning) && (
                <div className={`mb-4 rounded-md border px-4 py-3 text-xs ${data.is_stale ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300" : "border-border bg-muted/30 text-muted-foreground"}`}>
                  Data through {data.data_last_session}; expected {data.expected_last_session}.
                  {data.refreshed ? " PostgreSQL was refreshed for this ticker." : ""}
                  {data.refresh_warning ? ` ${data.refresh_warning}` : ""}
                </div>
              )}
              <RarityResults data={data} factorType={factorType} />
            </>
          )}
        </div>
      </main>
    </div>
  )
}
