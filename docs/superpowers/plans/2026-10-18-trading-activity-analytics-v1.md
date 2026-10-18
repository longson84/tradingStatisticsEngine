# Trading Activity Analytics v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stored-data-only turnover intensity analytics with a prior-20-session anomaly score and a Trading Activity chart.

**Architecture:** A pure `trading_engine` module owns the versioned formula and next-session factor conversion. The FastAPI service supplies requested rows plus up to 20 earlier stored rows, serializes analysis separately from raw observations, and the React page renders the analytical result without performing calculations or provider calls.

**Tech Stack:** Python 3.12, pandas, FastAPI/Pydantic, SQLAlchemy, pytest, React 19, TypeScript, Vite, lightweight SVG charts.

**Spec:** `docs/superpowers/specs/2026-10-18-trading-activity-analytics-v1-design.md`

## Global Constraints

- Formula identifier: `turnover_intensity_v1`.
- Baseline and population standard deviation use exactly the 20 immediately preceding stored sessions and exclude the current session.
- Derived analytics are not persisted and acquisition never occurs from the read path.
- Returned raw rows remain restricted to the requested date range.
- Any factor or strategy series is shifted by one observed session.
- Preserve the current uncommitted Vietnam picker and responsive Data Operations work.

## Review Focus

- Exactly 20 prior rows versus only 19 must switch anomaly availability at the correct boundary.
- A zero market cap in either the current row or its prior-20 window must not become infinity or a fabricated zero.
- A constant prior window must return a zero-variance reason, not divide by zero.
- Reading a narrow date range must use stored lookback context without leaking those rows into the response activity range.
- Unsupported instruments and missing stored rows must retain their existing explicit errors and must never instantiate a provider.

---

### Task 1: Provider-neutral formula and lagged factor boundary

**Files:**
- Create: `trading_engine/activity/__init__.py`
- Create: `trading_engine/activity/turnover_intensity.py`
- Modify: `trading_engine/types.py`
- Test: `tests/trading_engine/test_turnover_intensity.py`

**Interfaces:**
- Consumes: ordered `TradingActivityObservation` values containing `session`, `total_value`, and `market_cap`.
- Produces: `analyze_turnover_intensity(observations, baseline_sessions=20) -> TurnoverIntensityAnalysis` and `turnover_intensity_factor_series(analysis) -> FactorSeries`.

- [ ] **Step 1: Write failing engine tests**

Cover literal ratios, prior-20 population mean/z-score, the 19/20 boundary,
non-positive and non-finite inputs, invalid prior-window propagation,
zero variance, order/duplicate validation, formula metadata, and a factor series
whose value at session `t` is the raw intensity from session `t-1`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/trading_engine/test_turnover_intensity.py -q`

Expected: FAIL because the activity types/module do not exist.

- [ ] **Step 3: Implement the minimal pure calculation**

Add shared frozen dataclasses and explicit unavailable-reason literals in
`types.py`. Implement strict chronological validation, finite-number guards,
the exact versioned formula, and the one-session-shifted factor conversion.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/trading_engine/test_turnover_intensity.py -q`

Expected: all tests pass.

### Task 2: Stored lookback and API serialization

**Files:**
- Modify: `api/repositories/trade_statistics_repository.py`
- Modify: `api/repositories/sqlalchemy_trade_statistics_repository.py`
- Modify: `api/services/trade_statistics_service.py`
- Modify: `api/schemas/trade_statistics.py`
- Modify: `api/routes/trade_statistics.py`
- Test: `tests/api/test_trade_statistics_repository.py`
- Test: `tests/api/test_trade_statistics_service.py`
- Test: `tests/api/test_trade_statistics_route.py`

**Interfaces:**
- Consumes: Task 1 observations and analysis.
- Produces: top-level `turnover_intensity` metadata/points in `InstrumentTradeStatisticsResponse`; raw `rows` remain unchanged and in requested-range order.

- [ ] **Step 1: Write failing repository, service, and route tests**

Prove descending limited lookback is returned to the service in chronological
order, exactly 20 pre-start rows feed the first requested point, context rows
do not enter `rows`/boundaries/counts, unavailable reasons serialize as null
metrics plus a stable code, existing HTTP errors are unchanged, and the route
dependency graph has no provider.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_trade_statistics_repository.py tests/api/test_trade_statistics_service.py tests/api/test_trade_statistics_route.py -q`

Expected: FAIL because lookback and analytics response fields do not exist.

- [ ] **Step 3: Implement lookback, service mapping, schemas, and route mapping**

Add `list_rows_before(instrument_id, before, limit)`, read exactly 20 earlier
stored rows, analyze context plus requested rows, then serialize only requested
analysis points. Use finite JSON floats for derived ratios and preserve the raw
Decimal-to-number boundary.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_trade_statistics_repository.py tests/api/test_trade_statistics_service.py tests/api/test_trade_statistics_route.py -q`

Expected: all tests pass.

### Task 3: Trading Activity analytics UI

**Files:**
- Create: `frontend/src/components/trading-activity/TurnoverIntensityAnalytics.tsx`
- Create: `frontend/scripts/test-turnover-intensity-analytics.mjs`
- Modify: `frontend/src/pages/TradingActivityPage.tsx`
- Modify: `frontend/src/lib/generated/api-schema.ts`
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: generated `turnover_intensity` response fields from Task 2.
- Produces: latest-value cards, intensity/prior-20 baseline line chart, anomaly chart, and visible unavailable explanations.

- [ ] **Step 1: Regenerate the API client and write a failing rendered-component contract**

Run API generation, then render the real component with available,
insufficient-history, invalid-market-cap, and zero-variance points. Assert chart
roles/labels, latest values, null rendering as `Not available`, and readable
reason copy.

- [ ] **Step 2: Run the frontend contract and verify RED**

Run: `pnpm --dir frontend test:turnover-intensity-analytics`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement and wire the analytics presentation**

Keep analytical calculation out of React. Render the API points using SVG,
retain horizontal scrolling for long periods, and place the section before the
existing raw activity charts/table.

- [ ] **Step 4: Run the frontend contract and verify GREEN**

Run: `pnpm --dir frontend test:turnover-intensity-analytics`

Expected: contract passes.

### Task 4: Architecture contract and complete verification

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: Tasks 1-3 behavior.
- Produces: canonical formula version, stored-lookback, unavailable-state, provider-boundary, and next-session-lag rules.

- [ ] **Step 1: Update the canonical architecture record**

Document `turnover_intensity_v1`, the prior-20 population formula, the context
read boundary, non-persistence, unavailable reasons, and next-session factor/
strategy lag.

- [ ] **Step 2: Run complete validation**

Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest`

Expected: all tests pass.

Run: `pnpm lint && pnpm type-check && pnpm build && pnpm check:api-types`

Expected: all commands pass; the existing Vite chunk-size warning may remain.

- [ ] **Step 3: Review the complete diff**

Run: `git diff --check` and inspect all staged, unstaged, and untracked files,
including the preserved picker/layout work.

Expected: no whitespace errors, unrelated edits, provider calls, or raw-row
contract regressions.
