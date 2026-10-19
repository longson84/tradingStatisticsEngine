# Collection Participant Flow Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow Universe and Watchlist refreshes for stored foreign-flow and proprietary-flow daily observations while preserving exact-Instrument support.

**Architecture:** Reuse the existing metadata planner and per-Instrument Vnstock execution pipeline. Collection membership resolves to eligible Vietnam equities, runs through the shared Vnstock lease/rate limiter with bounded concurrency and retries, and records progress/failures per Instrument; no provider or persistence model changes are required.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, React 19, TypeScript, React Query, pnpm.

**Spec:** `docs/ARCHITECTURE.md` — Vietnam participant-flow persistence and Data Operations boundaries, extended by the approved 2026-10-19 requirement in this plan.

## Global Constraints

- Support `universe`, `watchlist`, and exact `instrument` scopes for `foreign_flow` and `proprietary_flow`.
- Continue rejecting the unbounded `category` scope and all unsupported instruments.
- Keep `session_stats` exact-Instrument-only and preserve all existing period rules.
- Use current collection membership, stable Instrument IDs, the shared Vnstock lease, rate limiter, bounded workers, per-Instrument progress, and failure isolation.
- Default each flow collection to at most 100 eligible Instruments; retain the existing environment override convention.
- Retry a failed flow Instrument once by default, cap total attempts at three, and reserve the request limiter for every attempt.
- Do not add provider calls to read/preview paths or change canonical flow persistence.

## Review Focus

- Mixed-market Watchlists must skip unsupported members while updating eligible Vietnam equities.
- Category flow requests must be rejected before starting a job.
- Oversized eligible collections must fail planning rather than partially execute.
- A retry must consume another rate-limit reservation and must not erase previously stored rows.
- UI dataset changes must not force Universe/Watchlist selection back to one Instrument; Session Statistics still must.

---

### Task 1: Collection-aware flow planning

**Files:**
- Modify: `api/services/data_operation_service.py`
- Modify: `api/schemas/data_operations.py`
- Modify: `tests/api/test_data_operations.py`

**Interfaces:**
- Consumes: current `DataOperationService.plan/preview` and route capabilities.
- Produces: collection plans with one `vnstock` work group of eligible Instrument IDs; explicit category and configured-limit rejection.

- [ ] Write failing planner and request-validation tests for Universe/Watchlist acceptance, unsupported-member counts, category rejection, and the 100-Instrument default limit.
- [ ] Run the focused tests and confirm failures reflect the exact-Instrument restriction.
- [ ] Change `_execution`, `_bulk_limit`, and request validation only as required by those tests.
- [ ] Run `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_data_operations.py -q` and confirm it passes.
- [ ] Commit as `feat: plan collection flow refreshes`.

### Task 2: Bounded flow retries in the existing runner

**Files:**
- Modify: `scripts/run_data_operation.py`
- Modify: `tests/test_run_data_operation.py`

**Interfaces:**
- Consumes: Task 1 collection plans and the existing `_execute_paid_instrument` limiter boundary.
- Produces: two-attempt default for both participant-flow datasets, environment override capped at three, one limiter reservation per attempt.

- [ ] Write failing tests for a successful second attempt, final failure, per-attempt limiter reservation, and the hard cap.
- [ ] Run the focused tests and confirm flow datasets currently stop after one attempt.
- [ ] Add the smallest dataset-specific attempt policy without changing trade-history behavior.
- [ ] Run `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/test_run_data_operation.py -q` and confirm it passes.
- [ ] Commit as `feat: retry collection flow refreshes`.

### Task 3: Expose collection flow refresh in Data Operations

**Files:**
- Modify: `frontend/src/components/data-operations/dataOperationRules.ts`
- Modify: `frontend/src/pages/DataOperationsPage.tsx`
- Modify: `frontend/src/components/data-operations/BatchOperationsPanel.tsx`
- Modify: `frontend/scripts/test-trading-activity-batch-refresh.mjs`
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: Task 1 API behavior and generated `DataOperationDataset` types.
- Produces: Universe/Watchlist selection for both flow datasets in Single Operation and saved Batch Plans; Session Statistics remains exact-only.

- [ ] Update the UI rules contract first so flow datasets accept Universe/Watchlist while category and Session Statistics remain blocked.
- [ ] Run the UI contract and confirm it fails under the old exact-Instrument rule.
- [ ] Update Single Operation copy/scope behavior and add both flow options to saved Batch Plans.
- [ ] Record the collection flow acquisition decision in `docs/ARCHITECTURE.md`.
- [ ] Run the UI contract, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Run the complete Python suite and API contract drift check.
- [ ] Commit as `feat: expose collection flow refreshes`.
