/**
 * API client for the Trading Engine FastAPI backend.
 * All types mirror the Pydantic schemas in api/schemas/.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export type Direction = "long" | "short";
export type MaType = "sma" | "ema" | "wma";
export type DataSource = "yfinance" | "vnstock" | "csv";
export type FactorType =
  | "moving_average"
  | "bollinger"
  | "donchian"
  | "distance_from_peak";

export interface DateRange {
  start: string; // ISO date "YYYY-MM-DD"
  end: string;
}

export interface WeightEvent {
  date: string;
  weight: number;
  price: number;
}

export interface Trade {
  symbol: string;
  direction: Direction;
  entry_date: string;
  entry_price: number;
  entry_weight: number;
  exit_date: string | null;
  exit_price: number | null;
  weight_history: WeightEvent[];
  return_pct: number | null;
  holding_days: number | null;
  mae_pct: number | null;
  mfe_pct: number | null;
}

// ---------------------------------------------------------------------------
// Strategy configs
// ---------------------------------------------------------------------------

export interface BuyAndHoldConfig {
  type: "buy_and_hold";
  weight?: number;
}

export interface MACrossoverConfig {
  type: "ma_crossover";
  fast_period?: number;
  slow_period?: number;
  ma_type?: MaType;
}

export type StrategyConfig = BuyAndHoldConfig | MACrossoverConfig;

// ---------------------------------------------------------------------------
// Backtest
// ---------------------------------------------------------------------------

export interface BacktestRequest {
  symbols: string[];
  date_range: DateRange;
  strategy: StrategyConfig;
  initial_capital?: number;
  max_leverage?: number;
  data_source?: DataSource;
}

export interface PortfolioResultResponse {
  equity_curve: Record<string, number>; // ISO date → NAV
  trades: Trade[];
  weights: Record<string, Record<string, number>>; // symbol → date → weight
  total_return_pct: number;
  final_nav: number;
}

// ---------------------------------------------------------------------------
// Sweep
// ---------------------------------------------------------------------------

export interface SweepRequest {
  symbols: string[];
  date_range: DateRange;
  strategies: StrategyConfig[];
  initial_capital?: number;
  max_leverage?: number;
  data_source?: DataSource;
  max_workers?: number;
}

export interface SweepResultItem {
  strategy_type: string;
  equity_curve: Record<string, number>;
  total_return_pct: number;
  final_nav: number;
  trade_count: number;
}

export interface SweepErrorItem {
  strategy_type: string;
  error: string;
}

export interface SweepResponse {
  results: SweepResultItem[];
  errors: SweepErrorItem[];
}

// ---------------------------------------------------------------------------
// Factors
// ---------------------------------------------------------------------------

export interface FactorRequest {
  symbol: string;
  date_range: DateRange;
  factor_type: FactorType;
  period?: number;
  ma_type?: MaType;
  std_dev?: number;
  data_source?: DataSource;
}

export interface FactorAnalysisResponse {
  factor_name: string;
  current_value: number;
  current_percentile: number;
  history_length_days: number;
  percentiles: Record<string, number>; // "p10", "p25", etc.
}

export interface CrossSectionalRequest {
  symbols: string[];
  date_range: DateRange;
  factor_type: FactorType;
  period?: number;
  ma_type?: MaType;
  threshold?: number;
  data_source?: DataSource;
}

export interface CrossSectionalResponse {
  factor_name: string;
  universe: string[];
  breadth: Record<string, number>;
  pct_above: Record<string, number>;
  universe_median: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const api = {
  backtest: (req: BacktestRequest) =>
    post<PortfolioResultResponse>("/backtest", req),

  sweep: (req: SweepRequest) => post<SweepResponse>("/sweep", req),

  analyzeFactor: (req: FactorRequest) =>
    post<FactorAnalysisResponse>("/factors/analyze", req),

  analyzeUniverse: (req: CrossSectionalRequest) =>
    post<CrossSectionalResponse>("/factors/universe", req),
};
