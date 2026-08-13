# Database-Only Company Universe Migration

## Objective

Make PostgreSQL the only persisted source for company and universe business
data. External providers remain synchronization inputs, but provider responses
and normalized symbol lists are not saved as JSON or CSV.

Build and configuration artifacts such as `package.json`, TypeScript configs,
and the generated `frontend/openapi.json` remain outside this migration because
they are not stored market data.

## Target Architecture

```text
External providers
        |
        v
Provider adapters
        |
        v
Validate and normalize in memory
        |
        v
Transactional universe sync
        |
        v
PostgreSQL
        |
        +--> Companies API
        +--> Price refresh
        +--> Fundamentals refresh
        +--> Market Health
```

The normalized relational tables are the canonical model:

- `companies`: one canonical issuer, independent of its listings.
- `company_identifiers`: stable issuer reconciliation keys such as SEC CIK.
- `instruments`: one tradable security issued by a company.
- `instrument_symbols`: canonical, source-specific, and historical ticker
  mappings. Namespace and source are strings, not provider foreign keys.
- `universes`: one system-managed company universe.
- `universe_memberships`: the current many-to-many membership set.

No additional company-list or provider-catalog table is required.

```text
Company 1 ── * Instrument 1 ── * InstrumentSymbol
   |
   └── * CompanyIdentifier
```

Examples represented by this model:

- Alphabet: one company identified by SEC CIK `1652044`, with separate `GOOG`
  and `GOOGL` instruments.
- Berkshire Hathaway Class B: one instrument with listing symbol `BRK.B` and
  Yahoo symbol `BRK-B` in separate namespaces.
- Core Natural Resources: one instrument can retain expired `CEIX` and current
  `CNR` listing-symbol rows with validity dates.

## Phase 1: Define the Provider Boundary

Add an application-level provider protocol under `api/providers/`, independent
of FastAPI routes and `trading_engine`.

Normalized provider values:

```text
UniverseSnapshot
- code
- name
- market
- description
- effective_date
- fetched_at
- source
- constituents

UniverseConstituent
- canonical_ticker
- company_name
- sector
- industry
- exchange
```

Implement replaceable source adapters:

| Universe | Initial source |
| --- | --- |
| US100 | Nasdaq constituent API |
| US2000 | iShares IWM holdings proxy |
| US500 | Current S&P 500 source |
| US30 | Current Dow 30 source |
| VN30, VNMID, VNSML | VNStock KBS listing API |
| VN100 | Derived from `VN30 union VNMID` |
| VNALL | Derived from `VN100 union VNSML` |

Deriving the composite Vietnam universes guarantees their set relationships and
avoids redundant provider calls.

Symbol normalization must explicitly handle provider-specific class-share
notation versus the canonical ticker used by price loaders. Vietnam symbols
remain normalized uppercase tickers.

## Phase 2: Strengthen Relational Persistence

Status: issuer/instrument/symbol identity implemented in migration `0011`.
Company metadata is no longer stored on instruments, stable identifiers can
reconcile multiple share classes, and historical/source-specific symbols have
a relational home. Existing API reads now join the company table. The static
bootstrap importer populates this model only as a temporary bridge until Phase
7 removes it.

Keep `companies`, `company_identifiers`, `instruments`, `instrument_symbols`,
`universes`, and `universe_memberships`. Add the synchronization audit table in
a later Alembic migration rather than modifying applied migrations.

Add a relational `universe_sync_runs` audit table with scalar columns:

```text
id
universe_code
source
status
started_at
finished_at
effective_date
received_count
added_count
removed_count
unchanged_count
error
```

Do not add a JSON or JSONB provider-payload column.

Consider replacing the arbitrary `universes.as_of` string with a proper date
while preserving the API's ISO date-string contract.

Extend a persistence-neutral repository boundary with operations to:

- List current universe tickers.
- Read current universe metadata and membership.
- Atomically replace a universe membership set.
- Record synchronization runs.

## Phase 3: Implement Safe Synchronization

Status: complete in Phase 4 of the canonical-model migration. Live snapshots
are validated before persistence, Universe or VN-family advisory locks protect
transactional replacement, and failures retain last-known-good membership.

Create a `UniverseSyncService` that coordinates providers and persistence.

For each synchronization:

1. Fetch external data before opening a database transaction.
2. Normalize symbols and metadata in memory.
3. Reject empty, duplicate, malformed, or cross-market results.
4. Check expected counts, set relationships, and membership-change thresholds.
5. Acquire a PostgreSQL lock for the universe or related universe family.
6. Recheck current database state after acquiring the lock.
7. Upsert instruments without overwriting useful metadata with null values.
8. Replace current universe memberships.
9. Update universe source and fetch provenance.
10. Recalculate instrument active state.
11. Commit the complete change atomically.

Required invariants:

- A failed fetch never changes existing membership.
- A suspiciously large change requires an explicit `--force` override.
- The five Vietnam universes update as one atomic family.
- Removing a company from a universe never deletes its prices, fundamentals,
  or watchlist membership.
- An instrument becomes inactive only when it belongs to no current system
  universe.
- Null provider metadata never overwrites existing non-null metadata.
- No network request runs while a database transaction or write lock is held.

## Phase 4: Replace the Bootstrap Command

Status: complete. `scripts.sync_company_universes` is now the supported live
bootstrap with `--all`, `--market`, `--universe`, `--dry-run`, `--force`, and
`--database-url`. The legacy importer remains only for the final file-layer
retirement phase and is no longer documented as the setup path.

Replace:

```bash
python -m scripts.import_companies
```

with:

```bash
python -m scripts.sync_company_universes --all
```

Supported controls should include:

```text
--market us|vn
--universe US500
--dry-run
--force
--database-url
```

`--dry-run` reports additions, removals, metadata changes, and validation
warnings without writing.

A clean installation becomes:

```bash
alembic upgrade head
python -m scripts.sync_company_universes --all
```

Do not synchronize during API startup. The application must continue using the
last known-good database state when an external constituent source is down.

## Phase 5: Cut Every Consumer Over to PostgreSQL

Current status:

- Company API reads PostgreSQL: complete.
- Fundamentals refresh reads PostgreSQL: complete.
- Price refresh reads JSON/CSV: must be migrated.

Replace the `_symbols()` file read in `scripts/refresh_market_history.py` with a
repository query against current `universe_memberships`. Price and fundamentals
refreshes must use the same database membership source and ordering rules.

Universe synchronization remains a separate operation so a listing-provider
failure does not prevent refreshing prices for the last known-good membership.

## Phase 6: Test the Migration

Add unit coverage for:

- Every provider parser using small mocked responses.
- Symbol normalization, including class-share notation.
- Duplicate and malformed constituent rejection.
- Composite Vietnam universe derivation.
- Metadata precedence.
- Large-change rejection and the explicit force override.

Add PostgreSQL integration coverage for:

- Idempotent synchronization.
- Transactional membership replacement.
- Failed synchronization preserving the previous state.
- Concurrent synchronization locking and lock-time rechecks.
- Membership removal without deleting prices, fundamentals, or watchlists.
- Correct instrument active-state recalculation.
- Price refresh obtaining symbols only from PostgreSQL.

Replace JSON-dependent tests in:

- `tests/api/test_company_import.py`
- `tests/api/test_companies.py`
- `tests/test_refresh_market_history.py`

The normal test suite must mock provider calls and require no live network.

## Phase 7: Remove the File-Backed Layer

After database parity and consumer-cutover validation, delete:

- `api/data/symbol_lists/*.json`
- `api/data/symbol_lists/us2000_symbols.csv`
- `api/symbol_list_data.py`
- `api/db/company_import.py`
- `scripts/import_companies.py`

Remove related imports, snapshot-count assertions, setup instructions, and
obsolete architecture statements.

Update `docs/ARCHITECTURE.md` in the same change to declare:

- PostgreSQL is the sole company and universe store.
- External providers are synchronization inputs, not application read sources.
- Company and universe snapshots are not persisted as JSON or CSV.
- Current membership remains subject to survivorship bias until a separate
  effective-dated membership-history design is implemented.

## Completion Criteria

The migration is complete when:

- A clean database can be populated solely through the live synchronization
  command.
- All nine universes exist with validated memberships.
- Company, price, and fundamentals workflows read memberships only from
  PostgreSQL.
- Provider failure leaves the previous database state intact.
- No production code references `api/data/symbol_lists` or
  `api.symbol_list_data`.
- No company or universe business data is stored in JSON or CSV.
- Python tests, frontend validation, API contract drift checks, and the
  production build pass.

## Delivery Sequence

Deliver the migration in four reviewable changes:

1. Provider protocol, normalized types, adapters, and parser tests.
2. PostgreSQL identity model (complete), writer, audit migration,
   synchronization service, and CLI.
3. Price-refresh consumer cutover and database integration tests.
4. Static-file deletion, obsolete-code removal, and documentation cleanup.

## Crypto Spot Extension

Status: Binance Spot foundation implemented in migration `0012` and
`scripts.sync_binance_spot`.

- Crypto catalog and price data is normalized directly into PostgreSQL; no
  Binance response is persisted as JSON or CSV.
- `assets`, `asset_issuers`, and `venues` separate economic identity from
  companies, trading products, symbols, and observation sources.
- `BINANCE_SPOT` is a venue and current instrument universe. BTC and other
  decentralized assets do not receive synthetic company rows.
- Monthly public-data archives are verified in memory with SHA-256 checksums;
  REST fills archive gaps and the incremental tail.
- Venue bars retain their true quote asset and `venue_unadjusted` basis. An
  asset-level cross-venue reference price remains a separate future design.
