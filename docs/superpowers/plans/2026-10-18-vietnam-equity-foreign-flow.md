# Vietnam Equity Foreign Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver stored, refreshable Vnstock Gen 5 foreign-investor flow data and a capability-scoped Vietnam Investor Flow page for exact canonical Instruments.

**Architecture:** Vnstock acquisition stays behind a typed API provider, normalized flow observations are persisted in PostgreSQL by exact Instrument ID, and UI reads never call the provider. Eligibility is derived from canonical routing metadata and is enforced independently in discovery, refresh, and read paths.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, Alembic, pandas, pytest, Vnstock 5.1.x, React 19, TypeScript, React Query, lightweight-charts, Vite, pnpm.

**Spec:** `docs/superpowers/specs/2026-10-18-vietnam-equity-flow-design.md`

## Global Constraints

- The first slice implements only the `foreign_flow` capability and exact-Instrument refresh scope.
- Opening Investor Flow reads PostgreSQL only; provider access occurs only in explicit Data Operations.
- Eligibility requires an active `common_stock` with a Company, Venue `HOSE`, `HNX`, or `UPCOM`, and a resolved `vnstock` route.
- Canonical observation identity is `(instrument_id, trading_date, participant_type)`; provider source is provenance, not identity.
- Store provider-reported net values; do not replace them with calculated differences.
- Keep `trading_engine` independent of Vnstock, FastAPI, SQLAlchemy, and frontend code.
- Use `uv` for Python and `pnpm` for JavaScript; do not introduce another package workflow.
- Update Pydantic schemas and generated TypeScript interfaces together.
- Update `docs/ARCHITECTURE.md` in the implementation that establishes the new data boundary.

## Review Focus

- Two Instruments with the same symbol on different Venues must never cross-write or cross-read flow observations; Task 4 pins exact-ID behavior.
- Malformed timestamps, missing fields, non-numeric values, negative gross values, and duplicate dates must normalize deterministically or fail visibly; Task 2 pins each case.
- A client bypassing capability-filtered discovery with a US equity, index, crypto pair, or unknown ID must receive the specified `404`/`422`, not an empty success or fallback; Task 4 pins these responses.
- A provider failure or a second concurrent Vnstock job must retain stored observations and respect the shared adapter lease; Task 5 pins both behaviors.
- Vietnam session cutoffs and date-range edges must produce correct stale state and inclusive filtering, including timezone-aware provider timestamps; Tasks 2 and 4 pin these boundaries.

---

### Task 1: Capability-Derived Instrument Discovery

**Files:**
- Modify: `api/instrument_data_routing.py`
- Modify: `api/repositories/instrument_analysis_repository.py`
- Modify: `api/repositories/sqlalchemy_instrument_analysis_repository.py`
- Modify: `api/services/instrument_analysis_service.py`
- Modify: `api/schemas/instrument.py`
- Modify: `api/routes/instruments.py`
- Modify: `tests/api/test_instrument_data_routing.py`
- Modify: `tests/api/test_instrument_analysis.py`

**Interfaces:**
- Produces: `InstrumentCapability = Literal["foreign_flow"]`.
- Produces: `InstrumentDataRoute.capabilities: frozenset[InstrumentCapability]`.
- Produces: `AnalysisInstrumentQuery.capability: InstrumentCapability | None` and `GET /instruments?capability=foreign_flow`.
- Consumes later: Tasks 4 and 5 check `foreign_flow in route.capabilities`; Task 6 uses the discovery query.

- [ ] **Step 1: Write failing routing and discovery tests**

Add tests named:

- `test_vietnam_common_stock_route_exposes_foreign_flow_capability`
- `test_us_equity_index_spot_and_reference_rate_routes_do_not_expose_foreign_flow`
- `test_foreign_flow_discovery_filters_before_count_and_pagination`
- `test_foreign_flow_discovery_does_not_require_stored_price_history`

Seed more than one page of mixed US/Vietnam Instruments and assert that rows,
`total`, and facets contain only eligible Vietnam common stocks.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_instrument_data_routing.py tests/api/test_instrument_analysis.py -q
```

Expected: FAIL because capability types, route metadata, and query filtering do not exist.

- [ ] **Step 3: Implement capability resolution and pre-pagination filtering**

Add `capabilities=frozenset({"foreign_flow"})` only to the existing VN common-stock route; all other routes receive an empty set. Thread the optional capability from FastAPI through `InstrumentAnalysisService.list_instruments(...)` into `AnalysisInstrumentQuery`. In SQL, apply the same canonical VN eligibility predicates before totals, facets, offset, and limit; reject unknown capability values through the Pydantic literal.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit the capability checkpoint**

```bash
git add api/instrument_data_routing.py api/repositories/instrument_analysis_repository.py api/repositories/sqlalchemy_instrument_analysis_repository.py api/services/instrument_analysis_service.py api/schemas/instrument.py api/routes/instruments.py tests/api/test_instrument_data_routing.py tests/api/test_instrument_analysis.py
git commit -m "feat: expose foreign flow instrument capability"
```

### Task 2: Typed Vnstock Foreign-Flow Adapter

**Files:**
- Modify: `api/providers/vietnam_market.py`
- Modify: `tests/api/test_vietnam_market_provider.py`

**Interfaces:**
- Consumes: existing `VietnamProviderResult`, `VietnamProviderMetadata`, and `provider_source_label(...)`.
- Produces: `VietnamMarketProvider.foreign_flow(symbol: str, start: date, end: date) -> VietnamProviderResult`.
- Produces: `VnstockProvider.foreign_flow(symbol: str, start: date, end: date) -> VietnamProviderResult`.
- Produces: `normalize_foreign_flow_result(result: VietnamProviderResult) -> pd.DataFrame` with columns `symbol`, `date`, `buy_volume`, `buy_value`, `sell_volume`, `sell_value`, `net_volume`, `net_value`, and `provider_source`.

- [ ] **Step 1: Write failing provider and normalization tests**

Add tests named:

- `test_provider_calls_foreign_flow_with_explicit_vci_source`
- `test_foreign_flow_normalization_maps_gen5_columns_and_vietnam_dates`
- `test_foreign_flow_normalization_keeps_provider_net_values_and_last_duplicate`
- `test_foreign_flow_normalization_rejects_missing_or_non_numeric_required_values`
- `test_foreign_flow_normalization_rejects_negative_buy_or_sell_values`

Use a `+07:00` timestamp fixture and assert the stored date remains the Vietnam calendar date. Assert the net values can differ from the locally calculated difference and remain unchanged.

- [ ] **Step 2: Run the focused provider tests and verify they fail**

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_market_provider.py -q
```

Expected: FAIL because `foreign_flow` and its normalizer do not exist.

- [ ] **Step 3: Implement the provider call and strict normalizer**

Call `Market().equity(normalized).foreign_flow(start=..., end=..., source="vci")`. Normalize the seven Gen 5 fields to the produced interface, preserve timezone-local calendar dates before dropping timezone information, coerce numerics, reject any required null/non-numeric value, reject negative gross buy/sell measures, sort ascending, and keep the last duplicate date.

- [ ] **Step 4: Run the focused provider tests and verify they pass**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit the provider checkpoint**

```bash
git add api/providers/vietnam_market.py tests/api/test_vietnam_market_provider.py
git commit -m "feat: adapt Vnstock foreign flow data"
```

### Task 3: Canonical Flow Persistence

**Files:**
- Create: `migrations/versions/0032_instrument_flow_observations.py`
- Modify: `api/db/models.py`
- Create: `api/repositories/instrument_flow_repository.py`
- Create: `api/repositories/sqlalchemy_instrument_flow_repository.py`
- Create: `tests/api/test_instrument_flow_model.py`
- Create: `tests/api/test_instrument_flow_repository.py`
- Create: `tests/test_instrument_flow_migration.py`

**Interfaces:**
- Produces: SQLAlchemy models `InstrumentFlowObservation` and `InstrumentFlowCoverage` with relationships from `Instrument`.
- Produces: `ParticipantType = Literal["foreign", "proprietary"]`.
- Produces: repository records `InstrumentFlowWriteRecord`, `InstrumentFlowRecord`, `InstrumentFlowCoverageRecord`, `FlowInstrumentRecord`, and `InstrumentFlowQuery`.
- Produces: `InstrumentFlowRepository.get_instrument(...)`, `get_coverage(...)`, `iter_observations(...)`, and `upsert_observations(...)`.
- Consumes later: Tasks 4 and 5 use this protocol and SQLAlchemy implementation.

- [ ] **Step 1: Write failing model, migration, and repository tests**

Cover:

- fixed-point round-trip for large VND values and signed nets;
- uniqueness on `(instrument_id, trading_date, participant_type)` while allowing foreign and proprietary rows on the same date;
- database rejection of negative gross buy/sell values and unsupported participant types;
- exact-Instrument inclusive date filtering and ascending order;
- idempotent upsert replacing a corrected date;
- coverage first/last/count/source/fetched-at recomputation in the same transaction;
- rollback leaving both observations and coverage unchanged;
- migration `upgrade()` creates both tables and widens Data Operation and batch-step dataset constraints to include `foreign_flow`; `downgrade()` reverses those changes;
- ORM check constraints for Data Operation runs and batch steps match the migrated database constraint.

- [ ] **Step 2: Run the focused persistence tests and verify they fail**

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_instrument_flow_model.py tests/api/test_instrument_flow_repository.py tests/test_instrument_flow_migration.py -q
```

Expected: FAIL because the models, migration, and repositories do not exist.

- [ ] **Step 3: Implement models, migration, and repository**

Use `Numeric(38, 6)` for all six measures, `String(16)` for participant type and currency, `String(100)` for source, and timezone-aware fetched timestamps. The SQLAlchemy repository supports PostgreSQL and SQLite conflict-upsert dialects, validates referenced Instrument IDs, batches writes, and rebuilds only affected `(instrument_id, participant_type)` coverage rows.

- [ ] **Step 4: Run the focused persistence tests and verify they pass**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit the persistence checkpoint**

```bash
git add migrations/versions/0032_instrument_flow_observations.py api/db/models.py api/repositories/instrument_flow_repository.py api/repositories/sqlalchemy_instrument_flow_repository.py tests/api/test_instrument_flow_model.py tests/api/test_instrument_flow_repository.py tests/test_instrument_flow_migration.py
git commit -m "feat: persist canonical instrument flow observations"
```

### Task 4: Exact-Instrument Flow Services and Read API

**Files:**
- Create: `api/services/instrument_flow_write_service.py`
- Create: `api/services/instrument_flow_service.py`
- Create: `api/schemas/market_flow.py`
- Create: `api/routes/market_flows.py`
- Modify: `api/deps.py`
- Modify: `api/main.py`
- Create: `tests/api/test_instrument_flow_service.py`
- Create: `tests/api/test_market_flows.py`

**Interfaces:**
- Consumes: Task 1 route capability, Task 2 normalized frame, Task 3 repository.
- Produces: `InstrumentFlowWriteService.store_observations(instrument_id: int, participant_type: ParticipantType, frame: pd.DataFrame, *, source: str, fetched_at: datetime) -> int`.
- Produces: `InstrumentFlowService.get_stored_flow(instrument_id: int, participant_type: ParticipantType, *, start: date | None = None, end: date | None = None, now: datetime | None = None) -> InstrumentFlowData`.
- Produces: `GET /instruments/{instrument_id}/market-flows?participant_type=foreign&start=...&end=...`, operation ID `getInstrumentMarketFlows`; the first-slice public query schema accepts only `Literal["foreign"]` even though persistence reserves `proprietary`.
- Consumes later: Task 6 imports the generated response type and calls the endpoint.

- [ ] **Step 1: Write failing write/read service and route tests**

Add tests for:

- exact-ID symbol validation before writing;
- timezone-aware `fetched_at` requirement;
- same symbol on two Venues never cross-writing or cross-reading;
- inclusive start/end filtering and ascending response order;
- expected latest session and stale state around the Vietnam session cutoff;
- unknown Instrument returns `404`;
- known US equity, index, crypto, and reference-rate IDs return capability-specific `422`;
- eligible VN equity with no observations returns storage-specific `422`;
- response exposes source, fetch time, currency, coverage, and provider-reported net values.

- [ ] **Step 2: Run the focused service/API tests and verify they fail**

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_instrument_flow_service.py tests/api/test_market_flows.py -q
```

Expected: FAIL because flow services, schemas, dependency wiring, and route do not exist.

- [ ] **Step 3: Implement write service, read service, schemas, and route**

Both services resolve routing metadata and require `foreign_flow` capability independently of discovery. The writer converts normalized DataFrame values to `Decimal(str(value))` records and delegates one transaction to the repository. The reader uses coverage for metadata, applies the requested date range to observations, and calculates staleness with `latest_completed_venue_session(...)`. The route maps unknown IDs to `404` and capability/storage/range errors to `422` without provider access.

- [ ] **Step 4: Run the focused service/API tests and verify they pass**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit the service/API checkpoint**

```bash
git add api/services/instrument_flow_write_service.py api/services/instrument_flow_service.py api/schemas/market_flow.py api/routes/market_flows.py api/deps.py api/main.py tests/api/test_instrument_flow_service.py tests/api/test_market_flows.py
git commit -m "feat: expose stored foreign flow history"
```

### Task 5: Explicit Foreign-Flow Data Operation

**Files:**
- Create: `scripts/refresh_instrument_flow.py`
- Modify: `scripts/run_data_operation.py`
- Modify: `api/services/data_operation_service.py`
- Modify: `api/repositories/data_operation_repository.py`
- Modify: `api/repositories/sqlalchemy_data_operation_repository.py`
- Modify: `api/schemas/data_operations.py`
- Modify: `api/schemas/batch_operations.py`
- Modify: `api/data_operation_jobs.py`
- Modify: `api/db/models.py`
- Modify: `tests/api/test_data_operations.py`
- Modify: `tests/test_run_data_operation.py`
- Create: `tests/test_refresh_instrument_flow.py`

**Interfaces:**
- Consumes: Tasks 1–4 provider, capability, coverage, and write interfaces.
- Produces: `DataOperationDataset = Literal["prices", "fundamentals", "foreign_flow"]` across API, jobs, and batch contracts.
- Produces: `refresh_instrument_flow(instrument_id: int, mode: str, *, engine: Engine | None = None, provider: VietnamMarketProvider | None = None, now: datetime | None = None) -> str`.
- Produces: exact-Instrument `foreign_flow` planning with adapter key `vnstock` and one provider request per execution.
- Consumes later: Task 6 exposes the dataset in Data Operations.

- [ ] **Step 1: Write failing refresh, planning, runner, and lease tests**

Cover:

- VN equity exact-Instrument preview and plan are runnable;
- US equity and every non-Instrument scope are rejected without partial execution;
- incremental mode overlaps the last seven calendar days and full mode starts at the route history boundary;
- provider failure leaves prior observations and coverage intact;
- successful refresh stores normalized rows and reports the returned-through date;
- `_execute_instrument(...)` dispatches `foreign_flow` to the new refresh function;
- Vnstock rate limiting charges one request;
- `data_operation_jobs` acquires the same `vnstock` lease for prices, fundamentals, and foreign flow and rejects a concurrent conflicting job;
- persisted/restored jobs accept `foreign_flow`.

- [ ] **Step 2: Run the focused operation tests and verify they fail**

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_data_operations.py tests/test_run_data_operation.py tests/test_refresh_instrument_flow.py tests/api/test_price_refresh_coordination.py -q
```

Expected: FAIL because the dataset and refresh path do not exist.

- [ ] **Step 3: Implement exact-Instrument refresh and orchestration**

Add foreign coverage fields to `DataOperationInstrumentRecord` and the SQL projection. For `foreign_flow`, `_dataset_adapter(...)` returns `vnstock` only when the route carries the capability; `_execution(...)` requires `scope_type == "instrument"`. The refresh script always performs an explicit provider request, using a seven-day overlap in incremental mode, `latest_completed_venue_session(...)`, Task 2 normalization, and Task 4 writer. Extend dataset literals, CLI choices, batch schemas, job restore/active-key loops, and the shared adapter lease without changing price/fundamental behavior.

- [ ] **Step 4: Run focused tests and the migration against the development database**

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_data_operations.py tests/test_run_data_operation.py tests/test_refresh_instrument_flow.py tests/api/test_price_refresh_coordination.py -q
UV_CACHE_DIR=.cache/uv uv run alembic upgrade head
```

Expected: tests PASS and Alembic upgrades to `0032`.

- [ ] **Step 5: Commit the Data Operations checkpoint**

```bash
git add scripts/refresh_instrument_flow.py scripts/run_data_operation.py api/services/data_operation_service.py api/repositories/data_operation_repository.py api/repositories/sqlalchemy_data_operation_repository.py api/schemas/data_operations.py api/schemas/batch_operations.py api/data_operation_jobs.py api/db/models.py tests/api/test_data_operations.py tests/test_run_data_operation.py tests/test_refresh_instrument_flow.py tests/api/test_price_refresh_coordination.py
git commit -m "feat: refresh foreign flow through data operations"
```

### Task 6: Investor Flow Frontend and Data Operations Controls

**Files:**
- Modify: `frontend/openapi.json`
- Modify: `frontend/src/lib/generated/api-schema.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/components/market/InvestorFlowChart.tsx`
- Create: `frontend/src/pages/InvestorFlowPage.tsx`
- Modify: `frontend/src/pages/DataOperationsPage.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/format.ts`

**Interfaces:**
- Consumes: Task 1 `listInstruments` capability query, Task 4 `getInstrumentMarketFlows`, and Task 5 `foreign_flow` Data Operation dataset.
- Produces: `instrumentMarketFlowsApi({instrument_id, participant_type, start?, end?})`.
- Produces: route `/vietnam-market/investor-flow` and `Vietnam Market > Investor Flow` navigation entry.
- Produces: reusable `InvestorFlowChart` rendering signed net value plus gross buy/sell value series.

- [ ] **Step 1: Regenerate contracts and confirm TypeScript initially has no UI integration**

```bash
pnpm generate:api
pnpm type-check
```

Expected: generated contracts include the new backend fields; type-check passes before page integration.

- [ ] **Step 2: Implement API wrapper, dedicated selector, and page states**

The page owns local search/selection state rather than the global multi-scope analysis selector. Search with `capability=foreign_flow`, `has_price_history=false`, and `limit=20`. Implement no-selection, no-results, loading, stored-data-missing, stale, API-error, and populated states. The missing-data state links to `/data-operations/single` with explicit instructions to choose the exact Instrument and Foreign flow dataset. Submit inclusive optional start/end dates and display source, fetched time, Venue, currency, first/last date, and row count.

- [ ] **Step 3: Implement chart, summaries, and daily table**

Use lightweight-charts with a signed net-value series and buy/sell supporting series, responsive resize cleanup, and a zero reference line. Add summary cards for latest net value/volume and selected-period cumulative buy, sell, and net values. Render the daily table newest-first without changing API order. Add VND compact-value formatting to `format.ts` and preserve signs.

- [ ] **Step 4: Integrate Data Operations without implying broader support**

Add `Foreign flow` to the dataset control and tracked-session validation. When selected, force or require exact Instrument scope, query the Instrument picker with `capability=foreign_flow`, hide price-only coverage, and show copy explaining that this operation updates stored Vietnam equity flow. Do not expose proprietary, session-statistics, or volume-profile controls yet.

- [ ] **Step 5: Run frontend verification and commit**

```bash
pnpm lint
pnpm type-check
pnpm build
UV_CACHE_DIR=.cache/uv uv run python -m scripts.check_api_types
git add frontend/openapi.json frontend/src/lib/generated/api-schema.ts frontend/src/lib/api.ts frontend/src/components/market/InvestorFlowChart.tsx frontend/src/pages/InvestorFlowPage.tsx frontend/src/pages/DataOperationsPage.tsx frontend/src/components/Sidebar.tsx frontend/src/App.tsx frontend/src/lib/format.ts
git commit -m "feat: add Vietnam investor flow interface"
```

Expected: all four verification commands pass and the commit succeeds.

### Task 7: Architecture Record, Live Smoke Test, and Full Verification

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify if required by observed behavior: files from Tasks 1–6 and their tests

**Interfaces:**
- Consumes: completed foreign-flow slice.
- Produces: canonical architecture decision and final verification evidence.

- [ ] **Step 1: Add the architecture decision**

Record the capability-derived UI policy, exact canonical flow identity, VCI provenance, explicit-refresh/stored-read separation, participant-type extension path, and the deliberate separation of session aggregates and live KBS volume profile.

- [ ] **Step 2: Run the complete automated gates**

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync pytest
pnpm lint
pnpm type-check
pnpm build
UV_CACHE_DIR=.cache/uv uv run python -m scripts.check_api_types
git diff --check
```

Expected: every command passes.

- [ ] **Step 3: Run a bounded live FPT foreign-flow smoke test**

Run an exact-Instrument incremental `foreign_flow` Data Operation for the canonical FPT Instrument, then request its stored market-flow endpoint for a three-session range. Verify that the operation source is VCI/Vnstock 5.1.x, observations are stored under FPT's exact Instrument ID, dates are ordered, and reopening the read endpoint performs no provider request.

- [ ] **Step 4: Verify the feature in the real UI**

Open `/vietnam-market/investor-flow`, search for FPT, verify that unsupported non-Vietnam Instruments are absent, load stored data, inspect source/coverage/stale metadata, chart signs and zero line, summary values, newest-first table, date filtering, and responsive layout. Confirm Data Operations permits Foreign flow only with exact eligible Instruments.

- [ ] **Step 5: Commit documentation and any verification fixes**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: record Vietnam equity flow architecture"
```

If verification required code fixes, include only those reviewed files and their regression tests in this final commit, then rerun Step 2 before claiming completion.
