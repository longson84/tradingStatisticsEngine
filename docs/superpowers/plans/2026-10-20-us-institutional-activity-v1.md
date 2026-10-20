# US Institutional Activity v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an exact-US-equity Institutional Activity page backed by canonical SEC 13F positions and provider-neutral reported-position changes.

**Architecture:** Immutable manager, filing, identifier, and position records live in PostgreSQL. A pure engine function derives changes from effective common-stock positions; an SEC adapter writes through repositories during explicit refreshes, while FastAPI and React only read stored data.

**Tech Stack:** Python 3.12, SQLAlchemy/Alembic, FastAPI/Pydantic, pytest, React 19, TypeScript, Vite.

**Spec:** `docs/superpowers/specs/2026-10-20-us-institutional-activity-v1-design.md`

## Global Constraints

- Never label inferred 13F position changes as executed transactions.
- Preserve portfolio period, accepted time, accession, source URL, and fetch time.
- Resolve positions only through verified Instrument-level CUSIP mappings.
- Keep options separate and exclude them from v1 common-stock activity.
- No provider access from read routes or React.
- Update `docs/ARCHITECTURE.md` with every new canonical boundary and formula.

## Review Focus

- An amended filing must supersede its earlier revision without deleting history or double-counting the manager.
- Missing, ambiguous, or expired CUSIP mappings must remain explicit and must not attach by issuer-name similarity.
- A manager absent in the current effective filing must become `exited`; a newly present manager must become `new`.
- Filed/accepted time, not report period, must control point-in-time availability.
- Put/call rows must never enter common-stock holder totals or changes.

---

### Task 1: Provider-neutral position change calculation

**Files:**
- Create: `trading_engine/institutional/__init__.py`
- Create: `trading_engine/institutional/position_changes.py`
- Modify: `trading_engine/types.py`
- Test: `tests/trading_engine/test_institutional_position_changes.py`

**Interfaces:**
- Consumes: ordered `InstitutionalPositionSnapshot` values keyed by manager, Instrument, and report period.
- Produces: `derive_institutional_position_changes(...) -> tuple[InstitutionalPositionChange, ...]` with version `institutional_position_change_v1`.

- [ ] Write tests for new/add/unchanged/reduce/exit, zero-share rejection, duplicate identity, option exclusion, ordering, and accepted-time availability; run and verify RED.
- [ ] Implement frozen shared types and the minimal pure calculation; run focused tests and verify GREEN.
- [ ] Commit the independently tested engine boundary.

### Task 2: Canonical persistence and repositories

**Files:**
- Create: `migrations/versions/0039_institutional_activity.py`
- Modify: `api/db/models.py`
- Create: `api/repositories/institutional_activity_repository.py`
- Create: `api/repositories/sqlalchemy_institutional_activity_repository.py`
- Test: `tests/test_institutional_activity_migration.py`
- Test: `tests/api/test_institutional_activity_repository.py`

**Interfaces:**
- Consumes: canonical Instrument IDs and Task 1 snapshots.
- Produces: immutable manager/filing/position writes, verified identifier lookup, effective-revision reads, and instrument activity reads.

- [ ] Write migration/model/repository tests and verify RED.
- [ ] Add constrained tables, relationships, indexes, amendment/effective-revision behavior, and repository mappings; verify GREEN.
- [ ] Commit the persistence boundary.

### Task 3: SEC archive adapter and explicit refresh service

**Files:**
- Create: `api/adapters/sec_13f.py`
- Create: `api/services/institutional_activity_write_service.py`
- Create: `scripts/refresh_institutional_activity.py`
- Test: `tests/api/test_sec_13f_adapter.py`
- Test: `tests/api/test_institutional_activity_write_service.py`
- Test: `tests/test_refresh_institutional_activity.py`

**Interfaces:**
- Consumes: an official SEC 13F archive stream and pre-verified CUSIP mappings.
- Produces: validated manager, filing, and immutable source-position writes with counts for mapped, unmapped, skipped-option, and failed rows.

- [ ] Write fixture-driven parser and service tests, including amendments, malformed rows, unmapped CUSIPs, and idempotency; verify RED.
- [ ] Implement streaming ZIP/TSV parsing, validation-before-write, and the explicit CLI refresh; verify GREEN.
- [ ] Commit the acquisition boundary.

### Task 4: Stored-data API

**Files:**
- Create: `api/schemas/institutional_activity.py`
- Create: `api/services/institutional_activity_service.py`
- Create: `api/routes/institutional_activity.py`
- Modify: `api/deps.py`
- Modify: `api/main.py`
- Test: `tests/api/test_institutional_activity_service.py`
- Test: `tests/api/test_institutional_activity_route.py`

**Interfaces:**
- Consumes: Task 2 effective position snapshots and Task 1 calculator.
- Produces: `GET /instruments/{instrument_id}/institutional-activity?quarters=8` with summary, history, changes, holders, provenance, and eligibility/coverage states.

- [ ] Write service and route tests for normal, unsupported, unmapped, no-data, amendment, and point-in-time responses; verify RED.
- [ ] Implement thin schemas/service/route wiring with no provider dependency; verify GREEN.
- [ ] Commit the read API.

### Task 5: US Institutional Activity UI

**Files:**
- Create: `frontend/src/pages/InstitutionalActivityPage.tsx`
- Create: `frontend/src/components/institutional-activity/InstitutionalActivityView.tsx`
- Create: `frontend/scripts/test-institutional-activity.mjs`
- Modify: `frontend/src/lib/api.ts`
- Modify: frontend navigation/router files discovered during implementation
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: Task 4 response and the shared Instrument picker constrained to active US common stocks.
- Produces: freshness/coverage banner, quarterly chart, action summary, latest-change table, current-holder table, filing links, and explicit unavailable states.

- [ ] Write a rendered-component contract and verify RED.
- [ ] Implement and wire the page without analytical calculations or provider calls; verify GREEN.
- [ ] Commit the UI.

### Task 6: Architecture record and complete verification

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: Tasks 1-5.
- Produces: the durable identity, provenance, amendment, point-in-time, and provider-boundary record.

- [ ] Update the canonical architecture record.
- [ ] Run the full pytest suite and frontend lint, type-check, build, and API-type checks.
- [ ] Run `git diff --check`, inspect all changes, and commit the verified documentation/gate result.
