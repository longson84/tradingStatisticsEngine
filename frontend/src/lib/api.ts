import type { components, operations } from "@/lib/generated/api-schema"

const BASE = "http://localhost:8000"

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorMessage(err, res.status))
  }
  return res.json()
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorMessage(err, res.status))
  }
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorMessage(err, res.status))
  }
  return res.json()
}

function errorMessage(err: unknown, status: number): string {
  if (err && typeof err === "object" && "detail" in err) {
    const detail = (err as { detail: unknown }).detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail)) {
      return detail.map(item => {
        if (item && typeof item === "object" && "msg" in item) {
          const loc = "loc" in item && Array.isArray((item as { loc?: unknown }).loc)
            ? (item as { loc: unknown[] }).loc.join(".")
            : "request"
          return `${loc}: ${(item as { msg: unknown }).msg}`
        }
        return JSON.stringify(item)
      }).join("; ")
    }
    return JSON.stringify(detail)
  }
  return `HTTP ${status}`
}

export type FactorType = "distance_from_peak" | "distance_from_ma" | "moving_average" | "bollinger" | "donchian" | "ahr999"
export type MaType = "sma" | "ema" | "wma"
export type DataSource = "yfinance" | "vnstock" | "csv"
export type RarityRecoveryMode = "price" | "factor"

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
  bars_elapsed: number | null
  forward_returns: Record<string, number | null>
  is_active: boolean
  is_quick_recovery: boolean
  level: number
  children_count: number
  parent_zone_pct: number | null
  parent_start_date: string | null
}

export interface TimeSeriesPoint {
  date: string
  price: number
  factor: number
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
  time_series: TimeSeriesPoint[]
}

export type PredefinedRarityFactorKey =
  | "distance_ma50"
  | "distance_ma100"
  | "distance_ma150"
  | "distance_ma200"
  | "distance_high_100"
  | "distance_high_150"
  | "distance_high_200"

export interface PredefinedRarityRow {
  symbol: string
  first_date: string
  last_date: string
  observations: number
  reference_price: number
  p50_price: number
  current_price: number
  current_value_pct: number
  current_percentile: number
  percentiles: Record<string, number>
}

export interface PredefinedRarityTable {
  factor_key: PredefinedRarityFactorKey
  factor_name: string
  rows: PredefinedRarityRow[]
}

export interface PredefinedRarityResponse {
  percentile_columns: string[]
  tables: PredefinedRarityTable[]
  errors: string[]
}

export type SymbolListId =
  | "US_ALL"
  | "US100"
  | "US2000"
  | "US500"
  | "US30"
  | "VN_ALL"
  | "VN30"
  | "VN100"

export interface SymbolListSummary {
  id: SymbolListId
  name: string
  description: string
  symbol_count: number
  as_of: string | null
  fetched_at: string | null
}

export interface SymbolListItem {
  symbol: string
  yfinance_symbol: string
  name: string
  sector: string | null
  industry: string | null
  exchange: string | null
  metadata: Record<string, unknown>
}

export interface SymbolListResponse extends SymbolListSummary {
  sources: Array<Record<string, string>>
  symbols: SymbolListItem[]
}

export interface SymbolListsResponse {
  lists: SymbolListSummary[]
}

export type CompanyResponse = components["schemas"]["CompanyResponse"]
export type CompanyListResponse = components["schemas"]["CompanyListResponse"]
export type CompanyUniversesResponse = components["schemas"]["CompanyUniversesResponse"]
export type CompanyUniverseId = CompanyListResponse["id"]
export type CompanyListQuery = NonNullable<
  operations["listCompanies"]["parameters"]["query"]
>

export interface MarketHealthWeights {
  within_10: number
  within_20: number
  within_30: number
  not_below_40: number
}

export interface MarketHealthPoint {
  date: string
  health_score: number
  median_distance: number
  p10_distance: number
  p20_distance: number
  p80_distance: number
  p90_distance: number
  within_10: number
  within_20: number
  within_30: number
  stress_40: number
  coverage_pct: number
  eligible_count: number
  change_5: number | null
  change_20: number | null
  ema_gap: number
}

export interface MarketHealthCache {
  fetched_at: string
  first_date: string
  last_date: string
  symbol_count: number
  source: string
  price_basis: string
}

export interface MarketHealthDistributionBucket {
  label: string
  min_distance: number | null
  max_distance: number | null
  count: number
  percentage: number
  cumulative_percentage: number
}

export interface MarketHealthStockDistance {
  symbol: string
  date: string
  current_price: number
  rolling_high: number
  distance: number
}

export interface MarketHealthDistributionResponse {
  universe: MarketHealthMarket["universe"]
  date: string
  window: number
  min_distance: number | null
  max_distance: number | null
  stocks: MarketHealthStockDistance[]
}

export interface MarketHealthMarket {
  universe: "US500" | "US2000" | "US100" | "VN100" | "VN30"
  universe_size: number
  regime: string
  cache: MarketHealthCache
  current: MarketHealthPoint
  series: MarketHealthPoint[]
  distribution: MarketHealthDistributionBucket[]
}

export interface MarketHealthRunResponse {
  window: number
  minimum_coverage: number
  weights: MarketHealthWeights
  markets: MarketHealthMarket[]
}

export interface MarketDataJob {
  id: string
  market: "US500" | "US2000" | "US100" | "VN100" | "VN30"
  mode: "incremental" | "full"
  dataset: "prices" | "fundamentals"
  status: "queued" | "running" | "completed" | "failed"
  current: number
  total: number
  message: string
  started_at: string | null
  finished_at: string | null
  error: string | null
}

export interface MarketDataCacheStatus {
  universe: "US500" | "US2000" | "US100" | "VN100" | "VN30"
  exists: boolean
  size_bytes: number
  fetched_at: string | null
  first_date: string | null
  last_date: string | null
  symbol_count: number | null
  row_count: number | null
  source: string | null
  price_basis: string | null
  errors: Array<Record<string, string>>
  latest_job: MarketDataJob | null
  fundamentals_exists: boolean
  fundamentals_fetched_at: string | null
  fundamentals_symbol_count: number
  fundamentals_snapshot_count: number
  fundamentals_size_bytes: number
  latest_fundamentals_job: MarketDataJob | null
}

export interface MarketDataStatusResponse {
  cache_directory: string
  fundamentals_cache_directory: string
  markets: MarketDataCacheStatus[]
}

export interface SymbolPricePoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number | null
  eps_ttm: number | null
  shares_outstanding: number | null
  trailing_pe: number | null
  trailing_pb: number | null
  relative_strength: number | null
}

export interface SymbolPriceHistoryResponse {
  symbol: string
  universe: "US500" | "US2000" | "US100" | "VN100" | "VN30"
  source: string
  price_basis: string
  fetched_at: string
  first_date: string
  last_date: string
  row_count: number
  relative_strength_benchmark: "VN30" | "SPX"
  trailing_pe_source: string | null
  trailing_pe_method: string | null
  trailing_pe_fetched_at: string | null
  fundamentals_fields: string[]
  provider_reported_pe: number | null
  provider_reported_pb: number | null
  provider_ratio_effective_date: string | null
  provider_ratio_period: string | null
  shares_growth_pct: number | null
  shares_growth_cagr_pct: number | null
  shares_growth_observed_years: number | null
  shares_growth_start_date: string | null
  shares_growth_full_10y: boolean
  shares_cagr_5y_pct: number | null
  shares_cagr_5y_observed_years: number | null
  shares_cagr_5y_start_date: string | null
  shares_cagr_full_5y: boolean
  prices: SymbolPricePoint[]
}

// ── New Low Episode Analysis ────────────────────────────────────────────────

export interface NewLowCurrentEpisode {
  start_date: string
  start_price: number
  recovery_level: number
  current_date: string
  current_price: number
  current_down_pct: number
  current_return_pct: number
  max_down_pct: number
  sessions_elapsed: number
  ignored_new_lows: number
  low_date: string
  low_price: number
  days_to_low: number
  recovery_needed_pct: number
  max_down_percentile: number
  ignored_lows_percentile: number
  duration_percentile: number
}

export interface NewLowForwardStats {
  horizon: number
  count: number
  return_percentiles: Record<string, number>
  max_down_percentiles: Record<string, number>
}

export interface NewLowEpisode {
  start_date: string
  start_price: number
  recovery_level: number
  recovered: boolean
  recovery_date: string | null
  recovery_sessions: number | null
  ignored_new_lows: number
  low_date: string
  low_price: number
  days_to_low: number
  max_down_pct: number
  forward_returns: Record<string, number | null>
  forward_max_down: Record<string, number | null>
}

export interface NewLowTimeSeriesPoint {
  date: string
  close: number
  is_new_low: boolean
}

export interface NewLowSymbolResult {
  symbol: string
  first_date: string
  last_date: string
  total_bars: number
  latest_price: number
  lookback_sessions: number
  quick_recovery_sessions: number
  raw_new_low_bars: number
  kept_episodes: number
  completed_episodes: number
  active_episodes: number
  quick_ignored_episodes: number
  total_ignored_new_lows: number
  max_down_percentiles: Record<string, number>
  recovery_session_percentiles: Record<string, number>
  ignored_new_low_percentiles: Record<string, number>
  current: NewLowCurrentEpisode | null
  forward_stats: NewLowForwardStats[]
  episodes: NewLowEpisode[]
  time_series: NewLowTimeSeriesPoint[]
}

export interface NewLowEpisodesResponse {
  results: NewLowSymbolResult[]
}

// ── SEC Fundamental Dashboard ───────────────────────────────────────────────

export interface FundamentalRow {
  fiscal_year: number
  filed: string | null
  filing_accepted_at: string | null
  filing_timing: string | null
  reaction_session_date: string | null
  filing_return_pct: number | null
  revenue: number | null
  revenue_yoy_pct: number | null
  gross_profit: number | null
  operating_income: number | null
  operating_income_yoy_pct: number | null
  operating_margin_pct: number | null
  net_income: number | null
  net_income_yoy_pct: number | null
  free_cash_flow: number | null
  free_cash_flow_yoy_pct: number | null
  free_cash_flow_margin_pct: number | null
  capex: number | null
  capex_to_revenue_pct: number | null
  cash_and_short_term_investments: number | null
  debt: number | null
  net_cash: number | null
  debt_to_fcf: number | null
  equity: number | null
  eps_diluted: number | null
  eps_yoy_pct: number | null
  diluted_shares: number | null
}

export interface FundamentalQuarterRow {
  period_end: string
  filed: string | null
  filing_accepted_at: string | null
  filing_timing: string | null
  reaction_session_date: string | null
  filing_return_pct: number | null
  revenue: number | null
  revenue_yoy_pct: number | null
  revenue_qoq_pct: number | null
  operating_income: number | null
  operating_income_yoy_pct: number | null
  operating_margin_pct: number | null
  net_income: number | null
  net_income_yoy_pct: number | null
  free_cash_flow: number | null
  free_cash_flow_yoy_pct: number | null
  free_cash_flow_margin_pct: number | null
  capex: number | null
  capex_to_revenue_pct: number | null
  cash_and_short_term_investments: number | null
  debt: number | null
  net_cash: number | null
  eps_diluted: number | null
  eps_yoy_pct: number | null
  diluted_shares: number | null
}

export interface FundamentalSummary {
  revenue_cagr_pct: number | null
  operating_income_cagr_pct: number | null
  net_income_cagr_pct: number | null
  free_cash_flow_cagr_pct: number | null
  eps_cagr_pct: number | null
  latest_operating_margin_pct: number | null
  latest_fcf_margin_pct: number | null
  latest_capex_to_revenue_pct: number | null
  latest_debt_to_fcf: number | null
  latest_net_cash: number | null
  share_count_change_pct: number | null
}

export interface FundamentalResponse {
  symbol: string
  cik: string
  entity_name: string
  requested_current_year: number
  first_year: number | null
  last_year: number | null
  rows: FundamentalRow[]
  quarter_rows: FundamentalQuarterRow[]
  summary: FundamentalSummary
}

// ── Growth Dashboard ───────────────────────────────────────────────────────

export interface GrowthMetricSnapshot {
  metric: string
  latest_value: number | null
  latest_yoy_pct: number | null
  cagr_3y_pct: number | null
  cagr_5y_pct: number | null
  cagr_10y_pct: number | null
  latest_margin_pct: number | null
}

export interface QuarterlyGrowthSnapshot {
  metric: string
  latest_value: number | null
  latest_yoy_pct: number | null
  previous_yoy_pct: number | null
  average_4q_yoy_pct: number | null
  latest_qoq_pct: number | null
  direction: string | null
}

export interface AnnualGrowthRow {
  fiscal_year: number
  revenue: number | null
  revenue_yoy_pct: number | null
  gross_profit_yoy_pct: number | null
  operating_income_yoy_pct: number | null
  net_income_yoy_pct: number | null
  free_cash_flow_yoy_pct: number | null
  eps_yoy_pct: number | null
  share_count_yoy_pct: number | null
  operating_margin_pct: number | null
  free_cash_flow_margin_pct: number | null
}

export interface QuarterlyGrowthRow {
  period_end: string
  revenue: number | null
  revenue_yoy_pct: number | null
  revenue_qoq_pct: number | null
  operating_income_yoy_pct: number | null
  net_income_yoy_pct: number | null
  free_cash_flow_yoy_pct: number | null
  eps_yoy_pct: number | null
  operating_margin_pct: number | null
  free_cash_flow_margin_pct: number | null
}

export interface GrowthQualitySummary {
  revenue_cagr_5y_pct: number | null
  operating_income_cagr_5y_pct: number | null
  free_cash_flow_cagr_5y_pct: number | null
  eps_cagr_5y_pct: number | null
  latest_operating_margin_pct: number | null
  latest_fcf_margin_pct: number | null
  operating_margin_change_5y_pct: number | null
  fcf_margin_change_5y_pct: number | null
  share_count_change_5y_pct: number | null
}

export interface GrowthAnalysisResponse {
  symbol: string
  cik: string
  entity_name: string
  requested_current_year: number
  first_year: number | null
  last_year: number | null
  annual_metrics: GrowthMetricSnapshot[]
  quarterly_metrics: QuarterlyGrowthSnapshot[]
  annual_rows: AnnualGrowthRow[]
  quarterly_rows: QuarterlyGrowthRow[]
  summary: GrowthQualitySummary
}

export interface GrowthAssessmentResponse {
  provider: string
  model: string
  good_things: string[]
  bad_things: string[]
  risks: string[]
  opportunities: string[]
  investment_considerations: string[]
  disclaimer: string
  prompt: string
}

// ── SMA Strategy Analysis ───────────────────────────────────────────────────

export type StrategyType = "buy_and_hold" | "price_vs_ma"

export interface PerformanceSummary {
  total_return_pct: number
  cagr_pct: number
  sharpe_ratio: number
  max_drawdown_pct: number
  current_drawdown_pct: number
  current_drawdown_days: number
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
  early_returns: Record<string, number | null>
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

export interface UndercutDistributionRow {
  undercuts: number
  trade_count: number
  pct_of_winners: number
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
  mfe_percentiles_losers: DistributionRow[]
  monthly_returns_strategy: Record<string, Record<string, number | null>>
  monthly_returns_bah: Record<string, Record<string, number | null>>
  monthly_stats_by_calendar: MonthlyStatRow[]
  monthly_stats_by_entry_month: MonthlyStatRow[]
  health_by_year: HealthRow[]
  equity_curve_strategy: Record<string, number>
  equity_curve_bah: Record<string, number>
  ticker_prices: Record<string, number>
  undercut_distribution: UndercutDistributionRow[] | null
}

export function smaStrategyAnalysisApi(params: {
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
  recovery_mode?: RarityRecoveryMode
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
    recovery_mode: params.recovery_mode ?? "price",
    data_source: params.data_source ?? "yfinance",
    zones: params.zones,
    date_range: { start: "2000-01-01", end: today },
  })
}

export function predefinedRarityApi(params: {
  symbols: string[]
  data_source?: DataSource
}): Promise<PredefinedRarityResponse> {
  return post("/factors/predefined-rarity", {
    symbols: params.symbols.map(s => s.toUpperCase().trim()).filter(Boolean),
    data_source: params.data_source ?? "yfinance",
  })
}

export function symbolListsApi(): Promise<SymbolListsResponse> {
  return get("/symbol-lists")
}

export function symbolListApi(id: SymbolListId): Promise<SymbolListResponse> {
  return get(`/symbol-lists/${id}`)
}

export function companyUniversesApi(): Promise<CompanyUniversesResponse> {
  return get("/companies/universes")
}

export function companiesApi(
  params: CompanyListQuery = {},
): Promise<CompanyListResponse> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value != null) query.set(key, String(value))
  }
  const suffix = query.size > 0 ? `?${query}` : ""
  return get(`/companies${suffix}`)
}

export function marketHealthRunApi(
  weights: MarketHealthWeights
): Promise<MarketHealthRunResponse> {
  return post("/market-health/run", {
    weights,
    window: 200,
    minimum_coverage: 0.8,
  })
}

export function marketHealthDistributionApi(params: {
  universe: MarketHealthMarket["universe"]
  date: string
  window?: number
  min_distance: number | null
  max_distance: number | null
}): Promise<MarketHealthDistributionResponse> {
  const query = new URLSearchParams({
    date: params.date,
    window: String(params.window ?? 200),
  })
  if (params.min_distance != null) query.set("min_distance", String(params.min_distance))
  if (params.max_distance != null) query.set("max_distance", String(params.max_distance))
  return get(`/market-health/${params.universe}/distribution?${query}`)
}

export function marketDataStatusApi(): Promise<MarketDataStatusResponse> {
  return get("/market-data/status")
}

export function symbolPriceHistoryApi(
  symbol: string,
  universe: SymbolPriceHistoryResponse["universe"]
): Promise<SymbolPriceHistoryResponse> {
  const query = new URLSearchParams({ universe })
  return get(
    `/market-data/symbols/${encodeURIComponent(symbol.toUpperCase().trim())}/history?${query}`
  )
}

export function marketDataRefreshApi(
  market: "US500" | "US2000" | "US100" | "VN100" | "VN30",
  mode: "incremental" | "full",
  dataset: "prices" | "fundamentals" = "prices"
): Promise<MarketDataJob> {
  return post(`/market-data/${market}/refresh?mode=${mode}&dataset=${dataset}`, {})
}

export function marketDataClearApi(
  market: "US500" | "US2000" | "US100" | "VN100" | "VN30"
): Promise<{ universe: string; cleared: boolean }> {
  return del(`/market-data/${market}`)
}

export function newLowEpisodesApi(params: {
  symbols: string[]
  lookback_sessions: number
  quick_recovery_sessions: number
  data_source?: DataSource
  start?: string
  end?: string
  forward_horizons?: number[]
}): Promise<NewLowEpisodesResponse> {
  const today = new Date().toISOString().slice(0, 10)
  return post("/events/new-low-episodes", {
    symbols: params.symbols.map(s => s.toUpperCase().trim()).filter(Boolean),
    lookback_sessions: params.lookback_sessions,
    quick_recovery_sessions: params.quick_recovery_sessions,
    data_source: params.data_source ?? "yfinance",
    forward_horizons: params.forward_horizons ?? [5, 10, 20, 50, 100, 150, 200],
    date_range: { start: params.start ?? "1980-01-01", end: params.end ?? today },
  })
}

export function fundamentalsSecApi(params: {
  symbol: string
  current_year: number
  years?: number
  data_source?: "yfinance" | "vnstock"
}): Promise<FundamentalResponse> {
  return post("/fundamentals/sec", {
    symbol: params.symbol.toUpperCase().trim(),
    current_year: params.current_year,
    years: params.years ?? 20,
    data_source: params.data_source ?? "yfinance",
  })
}

export function growthAnalysisApi(params: {
  symbol: string
  current_year: number
  years?: number
}): Promise<GrowthAnalysisResponse> {
  return post("/fundamentals/growth", {
    symbol: params.symbol.toUpperCase().trim(),
    current_year: params.current_year,
    years: params.years ?? 20,
    data_source: "yfinance",
  })
}

export function growthAssessmentApi(growth: GrowthAnalysisResponse): Promise<GrowthAssessmentResponse> {
  return post("/fundamentals/growth/assessment", { growth })
}
