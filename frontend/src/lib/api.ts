const BASE = "http://localhost:8000"

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Rarity Analysis ──────────────────────────────────────────────────────────

export interface ZoneStat {
  zone_pct: number
  threshold_value: number
  count: number
  qr_count: number
  qr_pct: number
  count_5y: number
  qr_5y: number
  count_10y: number
  qr_10y: number
  avg_days: number
  mmae_pct: number
  mae_by_percentile: Record<string, number>
  is_current_zone: boolean
}

export interface ZoneEntry {
  zone_pct: number
  start_date: string
  entry_price: number
  entry_factor: number
  low_price: number
  low_date: string
  low_factor: number
  mae_pct: number
  days_to_low: number
  recovery_date: string | null
  days_to_recovery: number | null
  is_active: boolean
  is_quick_recovery: boolean
  level: number
  children_count: number
  parent_zone_pct: number | null
  parent_start_date: string | null
}

export interface RarityAnalysisResponse {
  factor_name: string
  symbol: string
  stats_date: string
  first_date: string
  last_date: string
  total_bars: number
  current_price: number
  current_value: number
  current_percentile: number
  current_zone: number | null
  zone_entry_date: string | null
  zone_entry_price: number | null
  sessions_in_zone: number
  max_potential_drop_pct: number
  factor_context: Record<string, unknown>
  zone_stats: ZoneStat[]
  entries: ZoneEntry[]
}

export type FactorType = "distance_from_peak" | "moving_average" | "bollinger" | "donchian"
export type MaType = "sma" | "ema" | "wma"
export type DataSource = "yfinance" | "vnstock" | "csv"

// ── Strategy Backtest Analysis ────────────────────────────────────────────────

export type StrategyType = "buy_and_hold" | "price_vs_ma"

export interface PerformanceSummary {
  total_return_pct: number
  cagr_pct: number
  sharpe_ratio: number
  max_drawdown_pct: number
  current_drawdown_pct: number
  calmar_ratio: number
  win_rate_pct: number
  avg_win_pct: number
  avg_loss_pct: number
  max_consec_losses: number
  best_trade_pct: number
  worst_trade_pct: number
  total_trades: number
  avg_holding_days: number
  profit_factor: number
  time_in_market_pct: number
}

export interface CurrentPosition {
  entry_date: string
  entry_price: number
  holding_days: number
  unrealized_return_pct: number | null
  mae_pct: number | null
  mfe_pct: number | null
}

export interface TradeRow {
  symbol: string
  direction: string
  entry_date: string
  exit_date: string | null
  entry_price: number
  exit_price: number | null
  return_pct: number | null
  holding_days: number | null
  mae_pct: number | null
  mfe_pct: number | null
  mae_price: number | null
  mfe_price: number | null
  retracement_pct: number | null
}

export interface DistributionRow {
  percentile: number
  value_pct: number
  cumulative_count: number
}


export interface MonthlyStatRow {
  label: string
  count: number
  p5: number | null
  p10: number | null
  p15: number | null
  p20: number | null
  p25: number | null
  p50: number | null
  p75: number | null
  p90: number | null
  p95: number | null
}

export interface HealthRow {
  year: number
  trades: number
  p5: number | null
  p10: number | null
  p15: number | null
  p20: number | null
  p25: number | null
  p50: number | null
  p75: number | null
  p90: number | null
  p95: number | null
}

export interface SingleTickerAnalysis {
  symbol: string
  strategy_label: string
  from_date: string
  to_date: string
  total_bars: number
  current_position: CurrentPosition | null
  strategy: PerformanceSummary
  bah: PerformanceSummary
  trades: TradeRow[]
  return_percentiles: DistributionRow[]
  mae_percentiles_winners: DistributionRow[]
  mfe_percentiles_winners: DistributionRow[]
  monthly_returns_strategy: Record<string, Record<string, number | null>>
  monthly_returns_bah: Record<string, Record<string, number | null>>
  monthly_stats_by_calendar: MonthlyStatRow[]
  monthly_stats_by_entry_month: MonthlyStatRow[]
  health_by_year: HealthRow[]
  equity_curve_strategy: Record<string, number>
  equity_curve_bah: Record<string, number>
}

export function backtestAnalyzeApi(params: {
  symbol: string
  ma_type: MaType
  ma_length: number
  buy_lag: number
  sell_lag: number
  initial_capital: number
  data_source: DataSource
  start?: string
  end?: string
}): Promise<SingleTickerAnalysis> {
  return post("/backtest/analyze", {
    symbol: params.symbol.toUpperCase().trim(),
    strategy: {
      type: "price_vs_ma",
      ma_type: params.ma_type,
      ma_length: params.ma_length,
      buy_lag: params.buy_lag,
      sell_lag: params.sell_lag,
    },
    initial_capital: params.initial_capital,
    data_source: params.data_source,
    start: params.start ?? null,
    end: params.end ?? null,
  })
}

export function rarityAnalysisApi(params: {
  symbol: string
  factor_type: FactorType
  period: number
  ma_type?: MaType
  std_dev?: number
  exit_length?: number
  quick_recovery_days?: number
  data_source?: DataSource
  zones?: number[]
}): Promise<RarityAnalysisResponse> {
  const today = new Date().toISOString().slice(0, 10)
  return post("/factors/rarity", {
    symbol: params.symbol.toUpperCase().trim(),
    factor_type: params.factor_type,
    period: params.period,
    ma_type: params.ma_type ?? "sma",
    std_dev: params.std_dev ?? 2.0,
    quick_recovery_days: params.quick_recovery_days ?? 5,
    data_source: params.data_source ?? "yfinance",
    zones: params.zones,
    date_range: { start: "2000-01-01", end: today },
  })
}
