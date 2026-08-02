# Trading Statistics Engine Architecture

This is the canonical record for the application's architecture, data rules,
and durable engineering conventions. `AGENTS.md` explains how contributors
work; this document records what the system is and why important decisions were
made.

## Update contract

Update this document in the same change whenever work alters any of the
following:

- A boundary between `trading_engine`, `api`, persistence, and `frontend`.
- A canonical data model, identifier, relationship, or ownership rule.
- Point-in-time, adjustment, provenance, or reproducibility semantics.
- A provider, persistence technology, cache lifecycle, or refresh workflow.
- A formula whose saved results must remain reproducible.
- A project-wide convention that future features must follow.

Routine bug fixes, styling changes, and endpoint additions that follow existing
rules do not need an architecture entry. Add decisions to the dated decision
log; revise the main sections when the current architecture itself changes.

## System boundaries

- `trading_engine/` is the framework-independent analytical library. It must
  not import FastAPI, SQLAlchemy, frontend code, or runtime-specific services.
- `api/` owns application orchestration, provider selection, persistence,
  refresh jobs, request validation, and serialization.
- `frontend/` owns interaction and presentation. Reusable financial or
  statistical calculations do not belong in React components.
- `scripts/` contains explicit operational entry points. Scripts call API-layer
  persistence and engine functions rather than duplicating their logic.

## Data principles

1. Use stable internal instrument IDs. Ticker text is searchable and displayed,
   but it is not a permanent identity.
2. Identify instruments by market as well as ticker. The same ticker text can
   exist in more than one market.
3. Represent universe membership relationally. Never store a single `list`
   string on an instrument because one instrument may belong to many universes.
4. Preserve missing data as `NULL`; missing financial values are not zero.
5. Store provider provenance, fetch time, price basis, and formula version with
   datasets whose interpretation depends on them.
6. Separate provider observations from reproducible derived calculations.
7. Use trading-session `DATE` values for daily bars and timezone-aware UTC
   timestamps for publication, fetch, and operational events.
8. Point-in-time analysis may only use information available as of that date.
   `period_end` and `effective_date` are distinct concepts.
9. Current-constituent historical analysis has survivorship bias and must be
   labelled as such until effective-dated membership history is available.
10. Refreshes must validate staged data and commit atomically so readers never
    observe a partially updated dataset.

## Persistence

PostgreSQL is the canonical application database. SQLAlchemy 2.x provides the
Python persistence boundary, transactions, and connection management. Alembic
is the only supported mechanism for changing the database schema.

The local development database is defined in `compose.yaml` and published on
port 5434 to avoid other local PostgreSQL projects. The connection is selected
through `DATABASE_URL`; committed credentials are development-only and must not
be reused outside a local machine.

CSV and JSON snapshots remain valid ingestion inputs during migration. They are
not removed until database row counts, key coverage, and application behavior
have been verified. Existing read paths remain file-backed until their separate
migration is complete.

### Initial company schema

- `instruments` stores market, canonical ticker, company name, sector,
  industry, exchange, active state, and source.
- `universes` stores the named current snapshots such as US100, US500, US2000,
  US30, VN30, and VN100.
- `universe_memberships` implements the many-to-many relationship between
  instruments and universes.

The initial membership table represents current saved snapshots. It is not
historical membership data. Effective-dated membership will require a later
explicit migration and a source capable of providing reliable membership dates.

## Database conventions

- Models live in `api/db/models.py`; session and engine construction live in
  `api/db/session.py`.
- Route handlers do not construct engines or own SQL transactions.
- A database mutation is one explicit transaction. On failure it rolls back.
- Schema changes require an Alembic migration and a model update in the same
  change.
- Migrations must be reviewable and deterministic. Do not call external APIs or
  depend on mutable files from an Alembic migration.
- Importers and refreshers must be idempotent and provide verification counts.
- Application code must not create production tables with `metadata.create_all`;
  that helper is reserved for isolated tests. Deployed schemas use Alembic.
- PostgreSQL-specific extensions are added only when a demonstrated workload
  requires them. TimescaleDB is not part of the initial architecture.

## Decision log

### 2026-08-02 — PostgreSQL persistence foundation

Context: company lists, overlapping universes, long price histories,
fundamentals, benchmarks, and derived market indicators were being coordinated
through independent CSV and JSON caches. Relative-strength ranking will add a
large date-by-symbol derived dataset.

Decision: adopt PostgreSQL as the canonical application store, SQLAlchemy 2.x
as the Python persistence layer, and Alembic for schema evolution. Begin with
company instruments and current universe memberships. Do not switch existing
read paths until imported data has verified parity.

Consequences: overlapping list membership no longer requires duplicated company
records in the database. PostgreSQL becomes a local runtime dependency. File
caches remain temporarily during an incremental migration.
