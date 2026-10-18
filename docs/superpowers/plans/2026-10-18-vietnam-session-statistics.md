# Vietnam Session Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver stored, explicitly refreshed Vnstock Gen 5 session statistics for one eligible Vietnam equity and one requested period.

**Architecture:** Add a strict 65-field VCI adapter and a closed 64-metric catalog, persist each successful exact-period fetch as an immutable snapshot plus fixed-point metric rows, and expose only the latest matching snapshot through a database-only API. Extend single Data Operations with required period parameters, then add a standalone Session Statistics page and prefilled refresh handoff without exposing this dataset to Batch Operations.

**Tech Stack:** Python 3.12, Vnstock 5.1.x, pandas, FastAPI/Pydantic, SQLAlchemy 2, Alembic, PostgreSQL/SQLite tests, React 19, TypeScript, React Query, Vite, pytest, uv, pnpm.

**Spec:** `docs/superpowers/specs/2026-10-18-vietnam-session-statistics-design.md`

## Global Constraints

- Keep `trading_engine` independent from FastAPI, Vnstock, SQLAlchemy, and React.
- UI reads PostgreSQL only; only an explicit exact-Instrument Data Operation may call Vnstock.
- Support active Company-backed common stocks on HOSE, HNX, and UPCOM only.
- Preserve all 64 provider values as `Numeric(38, 6)`; do not recalculate totals, nets, or averages.
- One-period first: no period comparison, inferred signal, false daily time series, or Batch Operation.
- `session_stats` operations require `period_start`, `period_end`, and `mode="full"`.
- Update `docs/ARCHITECTURE.md` whenever persistence, API, or provenance boundaries ship.
- Use `uv` and `pnpm`; do not introduce another package manager or environment workflow.

## Review Focus

- A two-date VCI response is one aggregate row, not two observations; the provider test must assert one row and the exact requested period.
- A provider schema addition, omission, duplicate row, `NaN`, or infinity must fail before persistence; strict normalizer tests own these cases.
- Re-fetching an exact period must create a later immutable snapshot while reads select the newest fetch; repository tests own ordering and retained history.
- `session_stats` without both dates, with a reversed range, or with incremental mode must return `422` before a job starts; route/schema tests own validation.
- A prefilled Data Operations URL may contain an unknown Instrument or malformed dates; the page must retain safe empty controls and require valid explicit submission.

---

### Task 1: Provider Contract, Metric Catalog, and Capability

**Files:**
- Create: `api/session_statistics.py`
- Modify: `api/providers/vietnam_market.py`
- Modify: `api/instrument_capabilities.py`
- Modify: `api/instrument_data_routing.py`
- Modify: `api/repositories/sqlalchemy_instrument_analysis_repository.py`
- Test: `tests/api/test_vietnam_market_provider.py`
- Test: `tests/api/test_instrument_data_routing.py`
- Test: `tests/api/test_instrument_analysis.py`

**Interfaces:**
- Consumes: existing `VietnamProviderResult`, `VnstockProvider._result(...)`, canonical Instrument routing, and capability-filtered discovery.
- Produces: `SessionStatisticMetricCode`, `SessionStatisticMetricDefinition`, `SESSION_STATISTIC_METRICS`, `SESSION_STATISTIC_SCHEMA_VERSION = 1`, `VnstockProvider.session_stats(symbol: str, start: date, end: date) -> VietnamProviderResult`, and `normalize_session_stats_result(result: VietnamProviderResult) -> dict[SessionStatisticMetricCode, Decimal]`.

- [ ] **Step 1: Write failing provider and catalog tests**

Add tests asserting:

- `session_stats("FPT", date(2026, 10, 15), date(2026, 10, 16))` calls VCI with those ISO dates;
- the catalog contains exactly the 64 observed numeric column names, each once, in the four spec groups with `volume`, `value`, or `count` units;
- normalization returns exact `Decimal` values and excludes `symbol`;
- zero and signed net metrics are accepted;
- zero rows, two rows, wrong symbol, missing/extra columns, duplicate columns, `NaN`, infinity, and non-numeric values raise `ProviderDataError`.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_market_provider.py -q`

Expected: FAIL because the catalog, provider method, and normalizer do not exist.

- [ ] **Step 3: Implement the closed metric catalog and strict provider boundary**

Define the exact 64-code literal and metadata tuple in `api/session_statistics.py`. Implement the provider call and strict one-row normalization without deriving any metric.

- [ ] **Step 4: Write failing capability tests**

Assert `session_stats` is derived for eligible Vietnam common stocks, rejected for other Instruments, and filtered before Instrument totals/pagination.

- [ ] **Step 5: Run capability tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_instrument_data_routing.py tests/api/test_instrument_analysis.py -q`

Expected: FAIL because `session_stats` is not an `InstrumentCapability`.

- [ ] **Step 6: Implement capability routing and discovery**

Add `session_stats` to the literal and to the same VN common-stock routing predicate used by participant flows.

- [ ] **Step 7: Run Task 1 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_market_provider.py tests/api/test_instrument_data_routing.py tests/api/test_instrument_analysis.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add api/session_statistics.py api/providers/vietnam_market.py api/instrument_capabilities.py api/instrument_data_routing.py api/repositories/sqlalchemy_instrument_analysis_repository.py tests/api/test_vietnam_market_provider.py tests/api/test_instrument_data_routing.py tests/api/test_instrument_analysis.py
git commit -m "feat: add session statistics provider contract"
```

### Task 2: Immutable Snapshot Persistence

**Files:**
- Create: `migrations/versions/0034_instrument_session_statistics.py`
- Modify: `api/db/models.py`
- Create: `api/repositories/session_statistics_repository.py`
- Create: `api/repositories/sqlalchemy_session_statistics_repository.py`
- Test: `tests/api/test_session_statistics_model.py`
- Test: `tests/api/test_session_statistics_repository.py`
- Test: `tests/test_session_statistics_migration.py`

**Interfaces:**
- Consumes: Task 1 metric codes and schema version.
- Produces: `SessionStatisticInstrumentRecord`, `SessionStatisticSnapshotWrite`, `SessionStatisticMetricRecord`, `SessionStatisticSnapshotRecord`, protocol `SessionStatisticsRepository`, and SQLAlchemy implementation methods `get_instrument(...)`, `store_snapshot(...)`, and `get_latest_snapshot(instrument_id, period_start, period_end)`.

- [ ] **Step 1: Write failing model and migration tests**

Assert two new tables, Instrument cascade, `period_start <= period_end`, schema version positive, metric-code uniqueness per snapshot, fixed-point signed round trips, and downgrade removal without touching flow tables.

- [ ] **Step 2: Run model/migration tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_session_statistics_model.py tests/test_session_statistics_migration.py -q`

Expected: FAIL because migration `0034` and models do not exist.

- [ ] **Step 3: Add migration `0034` and matching ORM models**

Create `instrument_session_stat_snapshots` and `instrument_session_stat_metrics` exactly as specified. Use an index on `(instrument_id, period_start, period_end, fetched_at)` and a unique constraint on `(snapshot_id, metric_code)`.

- [ ] **Step 4: Write failing repository tests**

Assert one transaction stores exactly 64 metrics, malformed metric sets store nothing, repeated exact-period fetches remain as separate snapshots, newest `fetched_at` wins, other periods remain isolated, and deleting the Instrument cascades.

- [ ] **Step 5: Run repository tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_session_statistics_repository.py -q`

Expected: FAIL because the repository contracts and implementation do not exist.

- [ ] **Step 6: Implement repository contracts and SQLAlchemy persistence**

`store_snapshot(record: SessionStatisticSnapshotWrite) -> int` validates the exact catalog set before inserting. `get_latest_snapshot(...) -> SessionStatisticSnapshotRecord | None` orders by `fetched_at DESC, id DESC` and returns metrics in catalog order.

- [ ] **Step 7: Run Task 2 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_session_statistics_model.py tests/api/test_session_statistics_repository.py tests/test_session_statistics_migration.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add migrations/versions/0034_instrument_session_statistics.py api/db/models.py api/repositories/session_statistics_repository.py api/repositories/sqlalchemy_session_statistics_repository.py tests/api/test_session_statistics_model.py tests/api/test_session_statistics_repository.py tests/test_session_statistics_migration.py
git commit -m "feat: persist session statistics snapshots"
```

### Task 3: Stored Session Statistics Service and Read API

**Files:**
- Create: `api/services/session_statistics_service.py`
- Create: `api/services/session_statistics_write_service.py`
- Create: `api/schemas/session_statistics.py`
- Create: `api/routes/session_statistics.py`
- Modify: `api/deps.py`
- Modify: `api/main.py`
- Test: `tests/api/test_session_statistics_service.py`
- Test: `tests/api/test_session_statistics_route.py`

**Interfaces:**
- Consumes: Task 2 repository contracts and Task 1 capability/catalog.
- Produces: `SessionStatisticsService.get_stored_snapshot(instrument_id: int, period_start: date, period_end: date) -> SessionStatisticsData`, `SessionStatisticsWriteService.store_snapshot(...) -> int`, and `GET /instruments/{instrument_id}/session-statistics?start=...&end=...`.

- [ ] **Step 1: Write failing service tests**

Assert exact-period newest-snapshot reads, catalog-ordered metric metadata, timezone-aware writes, provider-symbol protection, unknown Instrument, unsupported capability, invalid range, and no stored snapshot errors.

- [ ] **Step 2: Run service tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_session_statistics_service.py -q`

Expected: FAIL because services do not exist.

- [ ] **Step 3: Implement thin read/write services**

Keep routing and capability validation in services; keep metric values unchanged and delegate storage/querying to the repository.

- [ ] **Step 4: Write failing route and OpenAPI tests**

Assert required start/end query parameters, Instrument/provenance/schema fields, all ordered metric metadata and values, `404` for unknown Instrument, `422` for unsupported/missing/reversed periods, and no provider dependency in the route.

- [ ] **Step 5: Run route tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_session_statistics_route.py -q`

Expected: FAIL because the route, schemas, and dependency wiring do not exist.

- [ ] **Step 6: Implement schemas, dependency wiring, route, and router registration**

Use `SessionStatisticMetricResponse` and `InstrumentSessionStatisticsResponse`; serialize fixed-point values using the repository's established API numeric convention.

- [ ] **Step 7: Run Task 3 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_session_statistics_service.py tests/api/test_session_statistics_route.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add api/services/session_statistics_service.py api/services/session_statistics_write_service.py api/schemas/session_statistics.py api/routes/session_statistics.py api/deps.py api/main.py tests/api/test_session_statistics_service.py tests/api/test_session_statistics_route.py
git commit -m "feat: expose stored session statistics"
```

### Task 4: Period-Aware Single Data Operations Contract

**Files:**
- Create: `migrations/versions/0035_session_statistics_operations.py`
- Modify: `api/db/models.py`
- Modify: `api/schemas/data_operations.py`
- Modify: `api/routes/data_operations.py`
- Modify: `api/services/data_operation_service.py`
- Modify: `api/data_operation_jobs.py`
- Modify: `api/deps.py`
- Modify: `api/schemas/batch_operations.py`
- Test: `tests/api/test_data_operations.py`
- Create: `tests/api/test_data_operation_jobs.py`
- Test: `tests/api/test_instrument_flow_model.py`
- Test: `tests/test_session_statistics_operation_migration.py`

**Interfaces:**
- Consumes: Task 3 exact-period read capability.
- Produces: single-operation dataset `session_stats`; optional `period_start` and `period_end` on `DataOperationRequest`, `DataOperationJob`, and `DataOperationRun`, conditionally required only for `session_stats` with `mode="full"`; Batch Operations continue to use their existing dataset union without `session_stats`.

- [ ] **Step 1: Write failing request and planning tests**

Assert `session_stats` accepts one exact eligible Instrument only, requires both dates, rejects reversed dates and incremental mode, rejects dates on other datasets, excludes unsupported Instruments, and is absent from Batch Operation schema enums.

- [ ] **Step 2: Run request/planning tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_data_operations.py -q`

Expected: FAIL because the dataset and conditional request validation do not exist.

- [ ] **Step 3: Implement split single/batch dataset types and period validation**

Add `session_stats` only to the single Data Operation union and define a separate `BatchDataOperationDataset` that retains the four existing values. Pass the validated period to planning so an exact-period preview can query `SessionStatisticsRepository` and distinguish existing versus missing snapshots without changing other dataset behavior.

- [ ] **Step 4: Write failing durable-job and migration tests**

Assert period fields round-trip through queued, loaded, history, and subprocess command data; active-job identity still blocks a second session-statistics run for the same Instrument; migration `0035` changes only the run dataset constraint and nullable period columns; downgrade retains proprietary flow.

- [ ] **Step 5: Run job/migration tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_data_operation_jobs.py tests/api/test_instrument_flow_model.py tests/test_session_statistics_operation_migration.py -q`

Expected: FAIL because durable period fields and migration `0035` do not exist.

- [ ] **Step 6: Implement durable period propagation**

Persist `period_start`/`period_end`, include `--period-start`/`--period-end` only when set, and preserve them in API job responses. Do not alter batch-plan tables or batch dataset constraints.

- [ ] **Step 7: Run Task 4 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_data_operations.py tests/api/test_data_operation_jobs.py tests/api/test_instrument_flow_model.py tests/test_session_statistics_operation_migration.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add migrations/versions/0035_session_statistics_operations.py api/db/models.py api/schemas/data_operations.py api/routes/data_operations.py api/services/data_operation_service.py api/data_operation_jobs.py api/deps.py api/schemas/batch_operations.py tests/api/test_data_operations.py tests/api/test_data_operation_jobs.py tests/api/test_instrument_flow_model.py tests/test_session_statistics_operation_migration.py
git commit -m "feat: plan period session statistics operations"
```

### Task 5: Session Statistics Refresh Runner

**Files:**
- Create: `scripts/refresh_instrument_session_statistics.py`
- Modify: `scripts/run_data_operation.py`
- Test: `tests/test_refresh_instrument_session_statistics.py`
- Test: `tests/test_run_data_operation.py`
- Test: `tests/api/test_price_refresh_coordination.py`

**Interfaces:**
- Consumes: Task 1 provider/normalizer, Task 3 write service, and Task 4 CLI period arguments.
- Produces: `refresh_instrument_session_statistics(instrument_id: int, period_start: date, period_end: date, *, engine: Engine | None = None, provider: VietnamMarketProvider | None = None, now: datetime | None = None) -> str` and runner dispatch for `dataset="session_stats"`.

- [ ] **Step 1: Write failing refresh tests**

Assert exact VCI dates, explicit capability enforcement, stable provenance, one immutable 64-metric snapshot, timezone-aware fetch time, retained earlier snapshots on provider/validation failure, and a progress message naming Instrument and period.

- [ ] **Step 2: Run refresh tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/test_refresh_instrument_session_statistics.py -q`

Expected: FAIL because the refresh script does not exist.

- [ ] **Step 3: Implement the refresh transaction**

Resolve exact Instrument metadata before the call, normalize all fields, and commit the snapshot through one transaction-scoped repository/write service.

- [ ] **Step 4: Write failing runner and lease tests**

Assert CLI/parser/dispatcher require and propagate both dates, charge one Vnstock request, and share the existing `vnstock` lease with prices, fundamentals, and participant flows.

- [ ] **Step 5: Run runner tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/test_run_data_operation.py tests/api/test_price_refresh_coordination.py -q`

Expected: FAIL because the runner does not dispatch `session_stats`.

- [ ] **Step 6: Implement runner and shared-lease dispatch**

Reject missing CLI dates before engine work. Pass the exact dates through `_execute_group(...)` and `_execute_instrument(...)` only for `session_stats`.

- [ ] **Step 7: Run Task 5 tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/test_refresh_instrument_session_statistics.py tests/test_run_data_operation.py tests/api/test_price_refresh_coordination.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/refresh_instrument_session_statistics.py scripts/run_data_operation.py tests/test_refresh_instrument_session_statistics.py tests/test_run_data_operation.py tests/api/test_price_refresh_coordination.py
git commit -m "feat: refresh session statistics snapshots"
```

### Task 6: Session Statistics Frontend

**Files:**
- Create: `frontend/src/pages/SessionStatisticsPage.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/openapi.json`
- Modify: `frontend/src/lib/generated/api-schema.ts`

**Interfaces:**
- Consumes: Task 3 read API and generated schemas.
- Produces: `instrumentSessionStatisticsApi({ instrument_id, start, end })`, route `/vietnam-market/session-statistics`, and the standalone one-period UI.

- [ ] **Step 1: Regenerate the API contract and verify the intended types**

Run: `pnpm generate:api`

Expected: generated `session_stats` capability and `InstrumentSessionStatisticsResponse` types appear; Batch Operation types still exclude `session_stats`.

- [ ] **Step 2: Add the typed API wrapper**

Export response/metric types and implement the exact-period GET wrapper in `frontend/src/lib/api.ts`.

- [ ] **Step 3: Build the standalone page**

Use existing Investor Flow selector/date patterns. Render provenance, the six spec summary cards, and all four ordered metric groups. Only Apply performs the stored read; changing controls does not call the provider.

- [ ] **Step 4: Add navigation and route**

Place Session Statistics beneath Investor Flow in the Vietnam Market sidebar section.

- [ ] **Step 5: Verify frontend GREEN**

Run: `pnpm lint && pnpm type-check && pnpm build`

Expected: PASS, with only the existing Vite chunk-size warning allowed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SessionStatisticsPage.tsx frontend/src/lib/api.ts frontend/src/App.tsx frontend/src/components/Sidebar.tsx frontend/openapi.json frontend/src/lib/generated/api-schema.ts
git commit -m "feat: add session statistics interface"
```

### Task 7: Data Operations Period UI and Prefill Handoff

**Files:**
- Modify: `frontend/src/pages/DataOperationsPage.tsx`
- Modify: `frontend/src/pages/SessionStatisticsPage.tsx`
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Consumes: Task 4 period-aware job API and Task 6 selected Instrument/period.
- Produces: query parameters `dataset=session_stats&instrument_id=<id>&symbol=<symbol>&period_start=<date>&period_end=<date>`, safe prefill parsing, period controls, and explicit “Fetch selected period” submission.

- [ ] **Step 1: Implement safe prefill parsing as pure helpers**

Accept the prefill only when dataset, positive integer Instrument ID, symbol, and two ISO dates are all valid and ordered; otherwise retain normal defaults without auto-starting.

- [ ] **Step 2: Add `session_stats` single-operation controls**

Add the dataset option only on the single view, force exact Instrument scope and `mode="full"`, show required date controls, pass dates to preview/start, and explain that each fetch creates a stored snapshot.

- [ ] **Step 3: Link missing snapshots to the prefilled operation**

Construct the query from the current Session Statistics selection. Never encode provider credentials or start the operation from the analysis page.

- [ ] **Step 4: Verify frontend GREEN**

Run: `pnpm lint && pnpm type-check && pnpm build && UV_CACHE_DIR=.cache/uv uv run python -m scripts.check_api_types`

Expected: PASS and generated contracts current.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/DataOperationsPage.tsx frontend/src/pages/SessionStatisticsPage.tsx frontend/src/lib/api.ts
git commit -m "feat: configure session statistics operations"
```

### Task 8: Architecture, Full Verification, and Live Smoke Test

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: durable architecture record and verified release candidate.

- [ ] **Step 1: Update the canonical architecture record**

Document the aggregate-period semantics, 64-code catalog, immutable snapshot identity, latest exact-period read, explicit Data Operations period, shared Vnstock lease, capability policy, and database-only UI boundary.

- [ ] **Step 2: Run migrations on the development database**

Run: `UV_CACHE_DIR=.cache/uv uv run alembic upgrade head`

Expected: upgrades `0033 -> 0034 -> 0035` successfully.

- [ ] **Step 3: Run the full Python suite**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest`

Expected: PASS; report any intentional skips and warnings exactly.

- [ ] **Step 4: Run all frontend and contract gates**

Run: `pnpm lint && pnpm type-check && pnpm build && UV_CACHE_DIR=.cache/uv uv run python -m scripts.check_api_types && git diff --check`

Expected: PASS; only the known Vite chunk-size warning is acceptable.

- [ ] **Step 5: Run one live exact-period smoke test**

Use canonical FPT Instrument ID and `2026-10-15` through `2026-10-16`. Verify the operation completes, one snapshot with 64 metrics is stored, the read API returns source `vnstock-5.1.0-vci`, and a second fetch retains the earlier snapshot while returning the newer one.

- [ ] **Step 6: Perform a whole-feature adversarial review**

Review staged, unstaged, untracked, migration downgrade, generated contracts, provider-read separation, participant-flow regressions, Batch Operation exclusion, and exact-period error states. Fix findings through a fresh TDD cycle and rerun affected gates.

- [ ] **Step 7: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: record session statistics architecture"
```

- [ ] **Step 8: Report integration state**

Show final commit list, clean/dirty status, ahead/behind counts, live-smoke evidence, and clearly distinguish local verification from remote push or deployed-browser validation.
