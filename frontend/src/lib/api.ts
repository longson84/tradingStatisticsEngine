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
