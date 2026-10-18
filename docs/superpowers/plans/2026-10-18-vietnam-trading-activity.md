# Vietnam Daily Trading Activity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver stored, explicitly refreshed Vnstock Gen 5 daily trading activity for one eligible Vietnam equity and one requested date range without changing canonical OHLCV storage.

**Architecture:** Add a strict VCI `trade_history` normalizer and a provider-neutral persistence contract for daily activity rows keyed by exact Instrument and session. Expose stored ranges through a database-only API, extend single Data Operations with exact dates, and add a standalone Trading Activity page while leaving `price_bars`, `PriceFrame`, and Batch Operations unchanged.

**Tech Stack:** Python 3.12, Vnstock 5.1.x, pandas, FastAPI/Pydantic, SQLAlchemy 2, Alembic, PostgreSQL/SQLite tests, React 19, TypeScript, React Query, Vite, pytest, uv, pnpm.

**Spec:** `docs/superpowers/specs/2026-10-18-vietnam-trading-activity-design.md`

## Global Constraints

- Keep `price_bars` and `trading_engine.types.PriceFrame` unchanged.
- Keep `trading_engine` independent from Vnstock, FastAPI, SQLAlchemy, and React.
- Store only provider-reported daily activity fields; do not store duplicate raw or adjusted price columns in the new table.
- UI reads PostgreSQL only; only an explicit exact-Instrument Data Operation may call Vnstock.
- Support active Company-backed common stocks on HOSE, HNX, and UPCOM only.
- `trade_history` operations require `period_start`, `period_end`, and `mode="full"` and remain absent from Batch Operations.
- Preserve fixed-point provider values, signed net volume, source, schema version, and timezone-aware fetch time.
- Do not call VCI buy/sell classifications investor inflow, foreign flow, proprietary flow, or recommendations.
- Do not add factors or strategy behavior in this slice; future use of end-of-session activity must lag to a later tradable session.
- Update `docs/ARCHITECTURE.md` in the same change as the persistence, API, provenance, and point-in-time boundaries.

## Review Focus

- A requested range may be only partly stored; the API and UI must report actual stored first/last dates and must not claim complete coverage.
- VCI may return duplicate or out-of-range sessions; normalization must reject the entire response before any row is persisted.
- A delayed refresh with an older `fetched_at` must not overwrite newer canonical rows.
- A valid weekend/holiday-only request may return no provider rows; refresh failure must preserve stored history and the read API must distinguish “no stored rows” from unsupported Instrument.
- Large monetary values and fractional averages must round-trip through fixed-point storage and API serialization without becoming formatted strings or silently truncated integers.

---

### Task 1: Provider Contract, Normalizer, and Capability

**Files:**
- Create: `api/trade_statistics.py`
- Modify: `api/providers/vietnam_market.py`
- Modify: `api/instrument_capabilities.py`
- Modify: `api/instrument_data_routing.py`
- Modify: `api/repositories/sqlalchemy_instrument_analysis_repository.py`
- Test: `tests/api/test_vietnam_market_provider.py`
- Test: `tests/api/test_instrument_data_routing.py`
- Test: `tests/api/test_instrument_analysis.py`

**Interfaces:**
- Consumes: existing `VietnamProviderResult`, `VnstockProvider.trade_history(...)`, canonical Instrument routing, and capability-filtered discovery.
- Produces: `TRADE_STATISTIC_SCHEMA_VERSION = 1`, `TRADE_HISTORY_PROVIDER_COLUMNS`, `TRADE_STATISTIC_STORAGE_COLUMNS`, `normalize_trade_history_result(result: VietnamProviderResult) -> pd.DataFrame`, and `InstrumentCapability` value `"trade_history"`.

- [ ] **Step 1: Write failing strict provider-contract tests**

Expand `_trade_history()` to the observed 39-column response and add tests asserting:

- `trade_history("FPT", start, end)` sends exact ISO dates, `resolution="1D"`, and `source="vci"`;
- normalization returns ascending unique `trading_date` rows with exactly the approved persisted columns;
- the normalizer accepts zero gross values and signed `total_net_trade_volume`;
- missing/extra/duplicate columns, duplicate dates, dates outside the requested period, invalid dates, `NaN`, infinity, negative gross values, and inconsistent `matched + deal != total` volume/value raise `ProviderDataError`;
- typed Vnstock failures retain safe `code` and `action` context without including credentials;
- empty responses continue to fail at the provider boundary.

- [ ] **Step 2: Run provider tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_market_provider.py -q`

Expected: FAIL because the catalog and normalizer do not exist.

- [ ] **Step 3: Implement the closed contract and normalizer**

Define the 39 provider columns and persisted activity columns in `api/trade_statistics.py`. Implement `normalize_trade_history_result(...)` in `api/providers/vietnam_market.py` using `Decimal(str(value))`, timezone-safe date extraction, exact range validation against result metadata, stable ascending order, and no derived analytics. Translate typed Vnstock failures into the existing provider exception boundary while retaining only safe error code/action context.

- [ ] **Step 4: Write failing capability tests**

Assert `trade_history` is derived only for eligible VN common stocks, direct unsupported routes omit it, and `GET /instruments?capability=trade_history` filters before totals and pagination.

- [ ] **Step 5: Run capability tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_instrument_data_routing.py tests/api/test_instrument_analysis.py -q`

Expected: FAIL because `trade_history` is not an Instrument capability.

- [ ] **Step 6: Implement capability routing and discovery**

Add `trade_history` to the same VN common-stock capability predicate as participant flows and session statistics, then include it in the repository capability filter.

- [ ] **Step 7: Run Task 1 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_market_provider.py tests/api/test_instrument_data_routing.py tests/api/test_instrument_analysis.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add api/trade_statistics.py api/providers/vietnam_market.py api/instrument_capabilities.py api/instrument_data_routing.py api/repositories/sqlalchemy_instrument_analysis_repository.py tests/api/test_vietnam_market_provider.py tests/api/test_instrument_data_routing.py tests/api/test_instrument_analysis.py
git commit -m "feat: add daily trade statistics provider contract"
```

### Task 2: Canonical Daily Trade-Statistics Persistence

**Files:**
- Create: `migrations/versions/0037_instrument_daily_trade_statistics.py`
- Modify: `api/db/models.py`
- Create: `api/repositories/trade_statistics_repository.py`
- Create: `api/repositories/sqlalchemy_trade_statistics_repository.py`
- Create: `tests/api/test_trade_statistics_model.py`
- Create: `tests/api/test_trade_statistics_repository.py`
- Create: `tests/test_trade_statistics_migration.py`

**Interfaces:**
- Consumes: Task 1 schema version and persisted-column contract.
- Produces: `TradeStatisticInstrumentRecord`, `DailyTradeStatisticWriteRecord`, `DailyTradeStatisticRecord`, protocol `TradeStatisticsRepository`, and SQLAlchemy methods `get_instrument(...)`, `upsert_rows(records)`, and `list_rows(instrument_id, start, end)`.

- [ ] **Step 1: Write failing model and migration tests**

Assert migration `0037` creates `instrument_daily_trade_statistics` with:

- Instrument cascade;
- unique `(instrument_id, trading_date)` identity;
- positive schema version;
- non-negative gross values/counts and signed net volume;
- `Numeric(38, 6)` fixed-point columns;
- source and timezone-aware fetch provenance;
- downgrade removal without touching price, flow, or session-statistics tables.

- [ ] **Step 2: Run model/migration tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_trade_statistics_model.py tests/test_trade_statistics_migration.py -q`

Expected: FAIL because migration `0037` and the ORM model do not exist.

- [ ] **Step 3: Add migration and matching ORM model**

Create one wide daily table with the spec's exact stored fields. Add an Instrument relationship with `cascade="all, delete-orphan"`; do not add columns or relationships to `PriceBar`.

- [ ] **Step 4: Write failing repository tests**

Assert:

- one transaction upserts all normalized rows;
- exact date-range reads are ascending and isolated from other Instruments/ranges;
- later `fetched_at` updates a row while older input cannot overwrite it;
- large values and fractional averages round-trip exactly as `Decimal`;
- an unknown Instrument stores nothing;
- malformed record sets roll back atomically;
- deleting an Instrument cascades.

- [ ] **Step 5: Run repository tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_trade_statistics_repository.py -q`

Expected: FAIL because repository contracts and implementation do not exist.

- [ ] **Step 6: Implement repository contracts and canonical upserts**

`upsert_rows(records: Iterable[DailyTradeStatisticWriteRecord]) -> int` rejects mixed Instruments, duplicate dates, invalid schemas, or empty identity fields before writing. Use PostgreSQL/SQLite conflict updates guarded by `excluded.fetched_at >= stored.fetched_at`.

- [ ] **Step 7: Run Task 2 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_trade_statistics_model.py tests/api/test_trade_statistics_repository.py tests/test_trade_statistics_migration.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add migrations/versions/0037_instrument_daily_trade_statistics.py api/db/models.py api/repositories/trade_statistics_repository.py api/repositories/sqlalchemy_trade_statistics_repository.py tests/api/test_trade_statistics_model.py tests/api/test_trade_statistics_repository.py tests/test_trade_statistics_migration.py
git commit -m "feat: persist daily trade statistics"
```

### Task 3: Stored Range Service and Read API

**Files:**
- Create: `api/services/trade_statistics_service.py`
- Create: `api/services/trade_statistics_write_service.py`
- Create: `api/schemas/trade_statistics.py`
- Create: `api/routes/trade_statistics.py`
- Modify: `api/deps.py`
- Modify: `api/main.py`
- Create: `tests/api/test_trade_statistics_service.py`
- Create: `tests/api/test_trade_statistics_route.py`

**Interfaces:**
- Consumes: Task 2 repository records and Task 1 capability/schema contract.
- Produces: `TradeStatisticsService.get_stored_range(instrument_id: int, start: date, end: date) -> TradeStatisticsData`, `TradeStatisticsWriteService.store_rows(instrument_id: int, symbol: str, rows: pd.DataFrame, *, source: str, fetched_at: datetime) -> int`, and `GET /instruments/{instrument_id}/trade-statistics?start=...&end=...`.

- [ ] **Step 1: Write failing service tests**

Assert exact-range ordered reads, actual first/last stored sessions, partial coverage, provider-symbol protection on writes, timezone-aware fetch validation, unknown Instrument, unsupported capability, reversed range, and no-stored-row errors. Assert service reads never instantiate or call a provider.

- [ ] **Step 2: Run service tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_trade_statistics_service.py -q`

Expected: FAIL because the read/write services do not exist.

- [ ] **Step 3: Implement thin read/write services**

Keep route/capability validation in services and database work in the repository. Return requested range plus actual stored first/last dates; do not claim complete session coverage or derive analytics.

- [ ] **Step 4: Write failing route and OpenAPI tests**

Assert required dates, Instrument metadata, requested and stored ranges, stable row order, source/schema/fetch provenance, exact numeric serialization, `404` unknown Instrument, and specific `422` unsupported/reversed/no-data responses. Assert the route dependency graph contains no provider.

- [ ] **Step 5: Run route tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_trade_statistics_route.py -q`

Expected: FAIL because schemas, route, and dependency wiring do not exist.

- [ ] **Step 6: Implement schemas, dependency wiring, and route registration**

Add `DailyTradeStatisticResponse` and `InstrumentTradeStatisticsResponse`. Follow the repository's established numeric API convention while preserving large integer and fractional values in tests.

- [ ] **Step 7: Run Task 3 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_trade_statistics_service.py tests/api/test_trade_statistics_route.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add api/services/trade_statistics_service.py api/services/trade_statistics_write_service.py api/schemas/trade_statistics.py api/routes/trade_statistics.py api/deps.py api/main.py tests/api/test_trade_statistics_service.py tests/api/test_trade_statistics_route.py
git commit -m "feat: expose stored daily trade statistics"
```

### Task 4: Exact-Period Single Data Operations Contract

**Files:**
- Create: `migrations/versions/0038_trade_history_operations.py`
- Modify: `api/db/models.py`
- Modify: `api/schemas/data_operations.py`
- Modify: `api/routes/data_operations.py`
- Modify: `api/services/data_operation_service.py`
- Modify: `api/data_operation_jobs.py`
- Modify: `api/deps.py`
- Modify: `api/schemas/batch_operations.py`
- Test: `tests/api/test_data_operations.py`
- Test: `tests/api/test_data_operation_jobs.py`
- Test: `tests/api/test_instrument_flow_model.py`
- Create: `tests/test_trade_history_operation_migration.py`

**Interfaces:**
- Consumes: Task 3 exact-range repository/service behavior.
- Produces: single-operation dataset `"trade_history"`; shared exact-period validation for `session_stats` and `trade_history`; persisted job dates and CLI flags already modeled by `DataOperationRun`; Batch Operations continue to exclude both datasets.

- [ ] **Step 1: Write failing request and planning tests**

Assert `trade_history`:

- requires exact Instrument scope, both dates, ordered dates, and full mode;
- rejects period dates for non-exact datasets;
- resolves only capability-eligible Instruments;
- previews current rows using the exact requested range without claiming session completeness;
- remains absent from Batch Operation schema enums;
- does not weaken existing `session_stats` validation.

- [ ] **Step 2: Run request/planning tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_data_operations.py -q`

Expected: FAIL because `trade_history` is not a dataset and period validation recognizes only session statistics.

- [ ] **Step 3: Implement exact-period dataset validation and planning**

Introduce one shared exact-period dataset predicate used by Pydantic validation, preview routing, and execution rules. Keep `BatchDataOperationDataset` unchanged. Inject `TradeStatisticsRepository` into `DataOperationService` for exact-range preview counts.

- [ ] **Step 4: Write failing durable-job and migration tests**

Assert period fields round-trip through queued, loaded, history, and subprocess command records for `trade_history`; active-job identity blocks a second run for the same Instrument/dataset; migration `0038` adds only the run dataset value and downgrade retains `session_stats` and proprietary flow.

- [ ] **Step 5: Run job/migration tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_data_operation_jobs.py tests/api/test_instrument_flow_model.py tests/test_trade_history_operation_migration.py -q`

Expected: FAIL because durable dataset constraints do not include `trade_history`.

- [ ] **Step 6: Implement dataset propagation and migration `0038`**

Reuse existing `period_start`/`period_end` columns and subprocess flags. Extend only the single-run dataset constraint and types; do not alter batch-plan tables or batch-step constraints.

- [ ] **Step 7: Run Task 4 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_data_operations.py tests/api/test_data_operation_jobs.py tests/api/test_instrument_flow_model.py tests/test_trade_history_operation_migration.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add migrations/versions/0038_trade_history_operations.py api/db/models.py api/schemas/data_operations.py api/routes/data_operations.py api/services/data_operation_service.py api/data_operation_jobs.py api/deps.py api/schemas/batch_operations.py tests/api/test_data_operations.py tests/api/test_data_operation_jobs.py tests/api/test_instrument_flow_model.py tests/test_trade_history_operation_migration.py
git commit -m "feat: plan exact-period trade history operations"
```

### Task 5: Explicit Trade-History Refresh Runner

**Files:**
- Create: `scripts/refresh_instrument_trade_statistics.py`
- Modify: `scripts/run_data_operation.py`
- Create: `tests/test_refresh_instrument_trade_statistics.py`
- Test: `tests/test_run_data_operation.py`
- Test: `tests/api/test_price_refresh_coordination.py`

**Interfaces:**
- Consumes: Task 1 provider normalizer, Task 2 repository, Task 3 write service, and Task 4 exact-period job arguments.
- Produces: `refresh_instrument_trade_statistics(instrument_id: int, period_start: date, period_end: date, *, engine: Engine | None = None, provider: VietnamMarketProvider | None = None, now: datetime | None = None) -> str` and runner dispatch for `dataset="trade_history"`.

- [ ] **Step 1: Write failing refresh tests**

Assert the refresh:

- resolves exact Instrument capability and provider symbol before Vnstock work;
- makes one explicit VCI request for the requested period;
- normalizes then atomically upserts every returned row with one stable source and fetch time;
- returns requested range, actual returned first/last sessions, and row count;
- preserves earlier rows when provider validation or persistence fails;
- rejects naive `now` values.

- [ ] **Step 2: Run refresh tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/test_refresh_instrument_trade_statistics.py -q`

Expected: FAIL because the refresh script does not exist.

- [ ] **Step 3: Implement the refresh script**

Use two short database scopes around the provider call, matching existing refresh scripts. Do not call or write `PriceBarRepository`.

- [ ] **Step 4: Write failing runner tests**

Assert CLI/parser/dispatcher require ordered dates and full mode before database work, pass exact dates to the refresh, charge one Vnstock request, and share the existing Vnstock start-rate limiter.

- [ ] **Step 5: Run runner/coordination tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/test_run_data_operation.py tests/api/test_price_refresh_coordination.py -q`

Expected: FAIL because the runner does not dispatch `trade_history`.

- [ ] **Step 6: Implement runner dispatch**

Extend the exact-period dispatch path shared with session statistics and call `refresh_instrument_trade_statistics(...)` only for `trade_history`.

- [ ] **Step 7: Run Task 5 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/test_refresh_instrument_trade_statistics.py tests/test_run_data_operation.py tests/api/test_price_refresh_coordination.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/refresh_instrument_trade_statistics.py scripts/run_data_operation.py tests/test_refresh_instrument_trade_statistics.py tests/test_run_data_operation.py tests/api/test_price_refresh_coordination.py
git commit -m "feat: refresh daily trade statistics"
```

### Task 6: Trading Activity Interface and Refresh Handoff

**Files:**
- Modify: `frontend/openapi.json`
- Modify: `frontend/src/lib/generated/api-schema.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/pages/TradingActivityPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/pages/DataOperationsPage.tsx`

**Interfaces:**
- Consumes: Task 3 API response and Task 4 Data Operations request contract.
- Produces: route `/vietnam-market/trading-activity`, capability-filtered Instrument discovery, stored exact-range rendering, and safe prefill `dataset=trade_history&instrument_id=<id>&symbol=<symbol>&period_start=<date>&period_end=<date>`.

- [ ] **Step 1: Regenerate API contracts and verify generated types**

Run: `pnpm generate:api`

Expected: generated types include `trade_history`, `InstrumentTradeStatisticsResponse`, actual stored range fields, and daily activity rows; Batch Operation types still exclude `trade_history` and `session_stats`.

- [ ] **Step 2: Add typed API helpers**

Add exported aliases and `instrumentTradeStatisticsApi({instrument_id, start, end})`. Extend single Data Operation request/query types without hand-writing generated response shapes.

- [ ] **Step 3: Implement the standalone Trading Activity page**

Follow the existing Investor Flow and Session Statistics selector patterns. Implement explicit Apply, database-only queries, requested/actual coverage provenance, summary cards, matched/deal stacked daily chart, net-volume chart, detailed table, and distinct no-selection/loading/no-data/partial/unsupported/error states.

Keep chart transformations in React but do not introduce reusable analytical formulas. Label buy/sell/net values as VCI classifications.

- [ ] **Step 4: Add route and navigation**

Place Trading Activity below Session Statistics in the Vietnam Market sidebar and register `/vietnam-market/trading-activity`.

- [ ] **Step 5: Add safe Data Operations prefill and controls**

Extend prefill parsing to accept only positive Instrument IDs, non-empty symbols, real ISO dates that parse and round-trip, and ordered periods. For `trade_history`, force Instrument scope and full mode, show exact-period fields, use “Fetch selected period” copy, and never auto-submit.

- [ ] **Step 6: Run frontend gates**

Run:

```bash
pnpm lint
pnpm type-check
pnpm build
pnpm check:api-types
```

Expected: all commands PASS. Vite's existing chunk-size warning is allowed; new lint, type, build, or API drift errors are not.

- [ ] **Step 7: Commit**

```bash
git add frontend/openapi.json frontend/src/lib/generated/api-schema.ts frontend/src/lib/api.ts frontend/src/pages/TradingActivityPage.tsx frontend/src/App.tsx frontend/src/components/Sidebar.tsx frontend/src/pages/DataOperationsPage.tsx
git commit -m "feat: add Vietnam trading activity interface"
```

### Task 7: Architecture Record, Live Smoke, and Full Verification

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Test: all affected backend and frontend gates

**Interfaces:**
- Consumes: Tasks 1–6 completed implementation.
- Produces: durable architecture decision, verified migration/runtime behavior, and final release evidence.

- [ ] **Step 1: Update the canonical architecture record**

Record:

- why daily activity remains outside `price_bars` and `PriceFrame`;
- exact Instrument/session identity and fixed-point/provenance rules;
- provider validation and canonical newer-fetch upsert behavior;
- explicit exact-range refresh versus database-only reads;
- Batch Operations exclusion;
- VCI classification labels;
- future provider-neutral analytics and mandatory next-session timing.

- [ ] **Step 2: Run focused backend suites**

Run:

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_market_provider.py tests/api/test_instrument_data_routing.py tests/api/test_instrument_analysis.py tests/api/test_trade_statistics_model.py tests/api/test_trade_statistics_repository.py tests/api/test_trade_statistics_service.py tests/api/test_trade_statistics_route.py tests/api/test_data_operations.py tests/api/test_data_operation_jobs.py tests/test_trade_statistics_migration.py tests/test_trade_history_operation_migration.py tests/test_refresh_instrument_trade_statistics.py tests/test_run_data_operation.py tests/api/test_price_refresh_coordination.py -q
```

Expected: PASS.

- [ ] **Step 3: Apply migrations and run one live exact-period smoke**

Apply migrations through `0038`, select one canonical eligible Instrument, and execute one short completed-session `trade_history` range through `scripts.run_data_operation`. Verify stored row count, first/last dates, stable source, and database-only API response. Do not print credentials or claim provider behavior beyond the observed range.

- [ ] **Step 4: Run complete verification**

Run:

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync pytest -q
pnpm lint
pnpm type-check
pnpm build
pnpm check:api-types
git diff --check
```

Expected: all commands PASS; skipped tests and existing non-blocking warnings are reported exactly.

- [ ] **Step 5: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: record daily trading activity architecture"
```
