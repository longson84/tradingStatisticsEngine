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

export type CompanyCatalogItem = components["schemas"]["CompanyCatalogItemResponse"]
export type CompanyCatalogResponse = components["schemas"]["CompanyCatalogResponse"]
export type CompanyCatalogQuery = NonNullable<
  operations["listCompanies"]["parameters"]["query"]
>
export type CryptoInstrument = components["schemas"]["CryptoInstrumentResponse"]
export type CryptoInstrumentListResponse = components["schemas"]["CryptoInstrumentListResponse"]
export type CryptoInstrumentQuery = NonNullable<
  operations["listCryptoInstruments"]["parameters"]["query"]
>
export type ReferenceRateInstrument = components["schemas"]["ReferenceRateInstrumentResponse"]
export type ReferenceRateListResponse = components["schemas"]["ReferenceRateListResponse"]
export type ReferenceRateQuery = NonNullable<
  operations["listReferenceRates"]["parameters"]["query"]
>
export type Venue = components["schemas"]["VenueResponse"]
export type VenueListResponse = components["schemas"]["VenueListResponse"]
export type InstrumentCatalogItem = components["schemas"]["InstrumentCatalogItemResponse"]
export type UniverseCatalog = components["schemas"]["UniverseCatalogResponse"]
export type UniverseListResponse = components["schemas"]["UniverseListResponse"]
export type UniverseSyncRun = components["schemas"]["UniverseSyncRunResponse"]
export type UniverseSyncRunPage = components["schemas"]["UniverseSyncRunPageResponse"]
export type UniverseStatsRequest = components["schemas"]["UniverseStatsRequest"]
export type UniverseStatsResponse = components["schemas"]["UniverseStatsResponse"]
export type UniverseStatsResult = components["schemas"]["UniverseStatsResultResponse"]
export type DataOperationRequest = components["schemas"]["DataOperationRequest"]
export type DataOperationPreview = components["schemas"]["DataOperationPreviewResponse"]
export type DataOperationJob = components["schemas"]["DataOperationJobResponse"]
export type InstrumentPriceCoverage = components["schemas"]["InstrumentPriceCoverageResponse"]
export type InstrumentPriceCoveragePage = components["schemas"]["InstrumentPriceCoveragePageResponse"]
export type DataOperationScopeType = DataOperationRequest["scope_type"]
export type DataOperationDataset = NonNullable<DataOperationRequest["dataset"]>
export type DataOperationMode = NonNullable<DataOperationRequest["mode"]>
export type InstrumentCatalogResponse = components["schemas"]["InstrumentCatalogResponse"]
export type InstrumentCatalogQuery = NonNullable<
  operations["listInstruments"]["parameters"]["query"]
>
export type InstrumentScope = NonNullable<InstrumentCatalogQuery["scope"]>
export type WatchlistSummary = components["schemas"]["WatchlistSummaryResponse"]
export type Watchlist = components["schemas"]["WatchlistResponse"]
export type WatchlistListResponse = components["schemas"]["WatchlistListResponse"]
export type WatchlistCreateRequest = components["schemas"]["WatchlistCreateRequest"]
export type WatchlistUpdateRequest = components["schemas"]["WatchlistUpdateRequest"]
export type WatchlistDeleteResponse = components["schemas"]["WatchlistDeleteResponse"]

export type InstrumentPricePoint = components["schemas"]["InstrumentPricePointResponse"]
export type InstrumentPriceHistoryResponse = components["schemas"]["InstrumentPriceHistoryResponse"]

// ── New Low Episode Analysis ────────────────────────────────────────────────

export type NewLowCurrentEpisode = components["schemas"]["NewLowCurrentEpisodeSchema"]
export type NewLowEpisode = components["schemas"]["NewLowEpisodeSchema"]
export type NewLowSymbolResult = components["schemas"]["NewLowSymbolResultSchema"]

export type NewLowDeepRequest = components["schemas"]["NewLowDeepRequest"]
export type NewLowDeepResponse = components["schemas"]["NewLowDeepResponse"]

// ── SMA Strategy Analysis ───────────────────────────────────────────────────

export type PerformanceSummary = components["schemas"]["PerformanceSummaryResponse"]
export type CurrentPosition = components["schemas"]["CurrentPositionResponse"]
export type TradeRow = components["schemas"]["TradeRowResponse"]
export type DistributionRow = components["schemas"]["DistributionRowResponse"]
export type MonthlyStatRow = components["schemas"]["MonthlyStatRowResponse"]
export type HealthRow = components["schemas"]["HealthRowResponse"]
export type UndercutDistributionRow = components["schemas"]["UndercutDistributionRowResponse"]
export type SingleInstrumentAnalysis = components["schemas"]["SingleInstrumentAnalysisResponse"]

export function smaStrategyAnalysisApi(params: {
  instrument_id: number
  ma_type: MaType
  ma_length: number
  buy_lag: number
  sell_lag: number
  initial_capital: number
  start?: string
  end?: string
}): Promise<SingleInstrumentAnalysis> {
  return post("/backtest/analyze", {
    instrument_id: params.instrument_id,
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
  instrument_id: number
  factor_type: FactorType
  period: number
  ma_type?: MaType
  std_dev?: number
  quick_recovery_days?: number
  recovery_mode?: RarityRecoveryMode
  zones?: number[]
}): Promise<RarityAnalysisResponse> {
  return post("/factors/rarity", {
    instrument_id: params.instrument_id,
    factor_type: params.factor_type,
    period: params.period,
    ma_type: params.ma_type ?? "sma",
    std_dev: params.std_dev ?? 2.0,
    quick_recovery_days: params.quick_recovery_days ?? 5,
    recovery_mode: params.recovery_mode ?? "price",
    zones: params.zones,
  })
}

export function instrumentsApi(
  params: InstrumentCatalogQuery = {},
): Promise<InstrumentCatalogResponse> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value != null) query.set(key, String(value))
  }
  const suffix = query.size > 0 ? `?${query}` : ""
  return get(`/instruments${suffix}`)
}

export function universesApi(): Promise<UniverseListResponse> {
  return get("/universes")
}

export function universeSyncRunsApi(
  universeId: number,
  params: { offset?: number; limit?: number } = {},
): Promise<UniverseSyncRunPage> {
  const query = new URLSearchParams()
  if (params.offset != null) query.set("offset", String(params.offset))
  if (params.limit != null) query.set("limit", String(params.limit))
  const suffix = query.size > 0 ? `?${query}` : ""
  return get(`/universes/${universeId}/sync-runs${suffix}`)
}

export function universeStatsApi(
  params: UniverseStatsRequest,
): Promise<UniverseStatsResponse> {
  return post("/universe-stats/run", params)
}

export function predefinedRarityApi(params: {
  watchlist_id: number
}): Promise<PredefinedRarityResponse> {
  return post("/factors/predefined-rarity", {
    watchlist_id: params.watchlist_id,
  })
}

export function companiesApi(
  params: CompanyCatalogQuery = {},
): Promise<CompanyCatalogResponse> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value != null) query.set(key, String(value))
  }
  const suffix = query.size > 0 ? `?${query}` : ""
  return get(`/companies${suffix}`)
}

export function cryptoInstrumentsApi(
  params: CryptoInstrumentQuery = {},
): Promise<CryptoInstrumentListResponse> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value != null) query.set(key, String(value))
  }
  const suffix = query.size > 0 ? `?${query}` : ""
  return get(`/crypto/instruments${suffix}`)
}

export function referenceRatesApi(
  params: ReferenceRateQuery = {},
): Promise<ReferenceRateListResponse> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value != null) query.set(key, String(value))
  }
  const suffix = query.size > 0 ? `?${query}` : ""
  return get(`/reference-rates${suffix}`)
}

export function venuesApi(): Promise<VenueListResponse> {
  return get("/venues")
}

export function watchlistsApi(): Promise<WatchlistListResponse> {
  return get("/watchlists")
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

export function dataOperationPreviewApi(params: {
  scope_type: DataOperationScopeType
  scope_id: string
  dataset: DataOperationDataset
}): Promise<DataOperationPreview> {
  const query = new URLSearchParams(params)
  return get(`/data-operations/preview?${query}`)
}

export function dataOperationPriceCoverageApi(params: {
  scope_type: DataOperationScopeType
  scope_id: string
  offset?: number
  limit?: number
}): Promise<InstrumentPriceCoveragePage> {
  const query = new URLSearchParams({
    scope_type: params.scope_type,
    scope_id: params.scope_id,
    offset: String(params.offset ?? 0),
    limit: String(params.limit ?? 50),
  })
  return get(`/data-operations/coverage?${query}`)
}

export function startDataOperationApi(
  request: DataOperationRequest,
): Promise<DataOperationJob> {
  return post("/data-operations/jobs", request)
}

export function dataOperationJobApi(jobId: string): Promise<DataOperationJob> {
  return get(`/data-operations/jobs/${encodeURIComponent(jobId)}`)
}

export function instrumentPriceHistoryApi(
  instrumentId: number,
): Promise<InstrumentPriceHistoryResponse> {
  return get(`/instruments/${instrumentId}/history`)
}

export function newLowDeepApi(
  params: NewLowDeepRequest,
): Promise<NewLowDeepResponse> {
  return post("/events/new-low-deep", params)
}
