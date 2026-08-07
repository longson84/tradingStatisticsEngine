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

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
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

export type FactorType = components["schemas"]["RarityRequest"]["factor_type"]
export type MaType = components["schemas"]["RarityRequest"]["ma_type"]
export type DataSource = "yfinance" | "vnstock" | "csv"
export type RarityRecoveryMode = components["schemas"]["RarityRequest"]["recovery_mode"]

// ── Rarity Analysis ──────────────────────────────────────────────────────────

export type ZoneStat = components["schemas"]["ZoneStatsSchema"]
export type ZoneEntry = components["schemas"]["ZoneEntrySchema"]
export type TimeSeriesPoint = components["schemas"]["TimeSeriesPoint"]
export type RarityAnalysisResponse = components["schemas"]["RarityAnalysisResponse"]

export type PredefinedRarityFactorKey = components["schemas"]["PredefinedRarityTable"]["factor_key"]
export type PredefinedRarityRow = components["schemas"]["PredefinedRarityRow"]
export type PredefinedRarityTable = components["schemas"]["PredefinedRarityTable"]
export type PredefinedRarityResponse = components["schemas"]["PredefinedRarityResponse"]

export type CompanyResponse = components["schemas"]["CompanyResponse"]
export type CompanyListResponse = components["schemas"]["CompanyListResponse"]
export type CompanyUniversesResponse = components["schemas"]["CompanyUniversesResponse"]
export type CompanyUniverseId = CompanyListResponse["id"]
export type CompanyListQuery = NonNullable<
  operations["listCompanies"]["parameters"]["query"]
>
export type WatchlistSummary = components["schemas"]["WatchlistSummaryResponse"]
export type Watchlist = components["schemas"]["WatchlistResponse"]
export type WatchlistListResponse = components["schemas"]["WatchlistListResponse"]
export type WatchlistCreateRequest = components["schemas"]["WatchlistCreateRequest"]
export type WatchlistUpdateRequest = components["schemas"]["WatchlistUpdateRequest"]
export type WatchlistDeleteResponse = components["schemas"]["WatchlistDeleteResponse"]
export type WatchlistRefreshJob = components["schemas"]["WatchlistRefreshJobResponse"]
export type WatchlistRefreshJobsResponse = components["schemas"]["WatchlistRefreshJobsResponse"]

export interface MarketHealthPoint {
  date: string
  median_distance: number
  coverage_pct: number
  eligible_count: number
}

export interface MarketHealthSeriesPoint {
  date: string
  median_distance: number
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
  universe: "US500" | "US2000" | "US100" | "VNALL" | "VN100" | "VN30" | "VNMID" | "VNSML"
  universe_size: number
  cache: MarketHealthCache
  current: MarketHealthPoint
  series: MarketHealthSeriesPoint[]
  distribution: MarketHealthDistributionBucket[]
}

export interface MarketHealthRunResponse {
  window: number
  minimum_coverage: number
  markets: MarketHealthMarket[]
}

export type MarketDataJob = components["schemas"]["MarketDataJobResponse"]
export type MarketDataCacheStatus = components["schemas"]["MarketDataCacheStatus"]
export type MarketDataStatusResponse = components["schemas"]["MarketDataStatusResponse"]
export type MarketDataClearResponse = components["schemas"]["MarketDataClearResponse"]

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
  universe: MarketDataCacheStatus["universe"]
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
export type PerformanceSummary = components["schemas"]["PerformanceSummaryResponse"]
export type CurrentPosition = components["schemas"]["CurrentPositionResponse"]
export type TradeRow = components["schemas"]["TradeRowResponse"]
export type DistributionRow = components["schemas"]["DistributionRowResponse"]
export type MonthlyStatRow = components["schemas"]["MonthlyStatRowResponse"]
export type HealthRow = components["schemas"]["HealthRowResponse"]
export type UndercutDistributionRow = components["schemas"]["UndercutDistributionRowResponse"]
export type SingleTickerAnalysis = components["schemas"]["SingleTickerAnalysisResponse"]

export function smaStrategyAnalysisApi(params: {
  market: "US" | "VN"
  ticker: string
  ma_type: MaType
  ma_length: number
  buy_lag: number
  sell_lag: number
  initial_capital: number
  start?: string
  end?: string
}): Promise<SingleTickerAnalysis> {
  return post("/backtest/analyze", {
    market: params.market,
    ticker: params.ticker.toUpperCase().trim(),
    strategy: {
      type: "price_vs_ma",
      ma_type: params.ma_type,
      ma_length: params.ma_length,
      buy_lag: params.buy_lag,
      sell_lag: params.sell_lag,
    },
    initial_capital: params.initial_capital,
    start: params.start ?? null,
    end: params.end ?? null,
  })
}

export function rarityAnalysisApi(params: {
  market: "US" | "VN"
  ticker: string
  factor_type: FactorType
  period: number
  ma_type?: MaType
  std_dev?: number
  exit_length?: number
  quick_recovery_days?: number
  recovery_mode?: RarityRecoveryMode
  zones?: number[]
}): Promise<RarityAnalysisResponse> {
  return post("/factors/rarity", {
    market: params.market,
    ticker: params.ticker.toUpperCase().trim(),
    factor_type: params.factor_type,
    period: params.period,
    ma_type: params.ma_type ?? "sma",
    std_dev: params.std_dev ?? 2.0,
    quick_recovery_days: params.quick_recovery_days ?? 5,
    recovery_mode: params.recovery_mode ?? "price",
    zones: params.zones,
  })
}

export function predefinedRarityApi(params: {
  watchlist_id: number
}): Promise<PredefinedRarityResponse> {
  return post("/factors/predefined-rarity", {
    watchlist_id: params.watchlist_id,
  })
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

export function watchlistsApi(market?: "US" | "VN"): Promise<WatchlistListResponse> {
  const suffix = market ? `?market=${market}` : ""
  return get(`/watchlists${suffix}`)
}

export function watchlistApi(id: number): Promise<Watchlist> {
  return get(`/watchlists/${id}`)
}

export function createWatchlistApi(request: WatchlistCreateRequest): Promise<Watchlist> {
  return post("/watchlists", request)
}

export function updateWatchlistApi(
  id: number,
  request: WatchlistUpdateRequest,
): Promise<Watchlist> {
  return put(`/watchlists/${id}`, request)
}

export function deleteWatchlistApi(id: number): Promise<WatchlistDeleteResponse> {
  return del(`/watchlists/${id}`)
}

export function refreshWatchlistPricesApi(id: number): Promise<WatchlistRefreshJob> {
  return post(`/watchlists/${id}/refresh`, {})
}

export function watchlistRefreshJobsApi(): Promise<WatchlistRefreshJobsResponse> {
  return get("/watchlists/refresh-jobs")
}

export function marketHealthRunApi(
  universes: MarketHealthMarket["universe"][],
): Promise<MarketHealthRunResponse> {
  return post("/market-health/run", {
    universes,
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
  market: MarketDataCacheStatus["universe"],
  mode: "incremental" | "full",
  dataset: "prices" | "fundamentals" = "prices"
): Promise<MarketDataJob> {
  return post(`/market-data/${market}/refresh?mode=${mode}&dataset=${dataset}`, {})
}

export function marketDataClearApi(
  market: MarketDataCacheStatus["universe"]
): Promise<MarketDataClearResponse> {
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
