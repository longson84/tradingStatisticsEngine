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
2. Resolve business operations by stable `instrument_id`. Venue and Symbol are
   separate descriptive dimensions; equal symbol text may exist on different
   venues without identifying the same instrument.
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
11. Keep economic venue identity separate from observation provenance. A
    Binance order book remains a Binance venue market even when a different
    source later supplies its historical observations.
12. Preserve the actual quote asset. A BTC/USDT close is denominated in USDT
    and must not be labelled USD unless an explicit conversion methodology is
    applied.

## Persistence

PostgreSQL is the canonical application database. SQLAlchemy 2.x provides the
Python persistence boundary, transactions, and connection management. Alembic
is the only supported mechanism for changing the database schema.

The local development database is defined in `compose.yaml` and bound only to
IPv4 loopback at `127.0.0.1:5436`, avoiding the Cloud SQL proxy on `5434` and
preventing `localhost` from resolving to a different IPv6 listener. The
connection is selected through `DATABASE_URL`; committed credentials are
development-only and must not be reused outside a local machine.

PostgreSQL is the sole persisted source for company and Universe business data.
Live Universe adapters validate provider data in memory and synchronize the
database directly; downloaded provider responses and normalized membership
snapshots are not saved as JSON or CSV. All application company and membership
reads use PostgreSQL services. Exact-instrument Price History and market-index
benchmarks read canonical daily bars from PostgreSQL, and refreshes
incrementally upsert the same tables. Price coverage, refresh state, and
fundamentals also use PostgreSQL.

### Canonical company, asset, venue, and instrument schema

- `companies` stores issuer identity and company-level metadata such as display
  name, legal name, sector, and industry. A company can issue multiple
  instruments.
- `company_identifiers` stores stable reconciliation keys such as SEC CIK. Its
  `namespace` and `source` are plain strings; there is intentionally no
  provider catalog foreign key.
- `assets` stores venue-independent economic identity. Equity share classes,
  native crypto assets, fiat currencies, and stablecoins are distinct asset
  types. An asset may exist without an issuing company.
- `asset_issuers` stores the optional effective-dated relationship from an
  asset to a company. Decentralized assets such as BTC have no synthetic issuer
  row.
- `venues` stores the economic location of trading, such as Binance Spot or
  NASDAQ. A venue is not a data-provider registry and remains part of market
  identity even if its API becomes unavailable. Every venue also owns an IANA
  timezone, a `trading_calendar_code` policy string, and a local daily-session
  cutoff. The calendar code is application metadata, not a foreign key to a
  calendar table.
- `instruments` stores venue-specific tradable-product identity: optional
  company, venue, base asset, quote asset, settlement asset, market class,
  current canonical ticker, product type, trading increments, active state,
  and source. Existing equity instruments retain their issuer relationship;
  crypto spot instruments have no company and require venue, base, and quote
  assets. Reference-rate instruments have no company or venue and require base
  and quote assets; they represent a provider observation, not an executable
  market. Market-index instruments also have no company or venue, but unlike a
  reference rate they have no base or quote assets; they represent a calculated
  index level such as SPX or VN30.
- `instrument_symbols` stores canonical, source-specific, and historical
  ticker mappings with optional validity dates. `instruments.ticker` remains
  the denormalized current canonical symbol used by existing price and API
  consumers and must be updated with its current canonical mapping.
- `universes` stores system-managed named current snapshots such as US100,
  US500, US2000, US30, VN30, VNMID, VN100, VNSML, VNALL, and Binance Spot. A
  universe has no market classification; any instrument characteristics needed
  by a consumer come from its current membership.
- `universe_memberships` implements the many-to-many relationship between
  instruments and universes.
- `price_bars` stores canonical daily OHLCV observations once per instrument,
  session, and price basis. A venue-specific crypto bar is canonical for that
  instrument, not a cross-venue composite price for its base asset.
- `price_bar_coverages` stores one derived operational summary per instrument
  and price basis. It accelerates status and refresh planning; it is rebuilt
  from canonical bars and is never an analytical price source.
- `price_refresh_states` stores the latest provider-check outcome per instrument
  and price basis. `attempted_through` is independent from the latest observable
  trade date, so checked no-new-bar sessions are not mislabeled as unattempted.

The initial membership table represents current saved snapshots. It is not
historical membership data. Effective-dated membership will require a later
explicit migration and a source capable of providing reliable membership dates.

### Daily price schema

- `price_bars` stores one canonical daily OHLCV observation per instrument,
  trading date, and price basis.
- `price_basis` distinguishes adjusted, unadjusted, provider-unspecified, and
  calculated index-level observations. Refresh code must use an explicit stable
  value; it must not infer adjustment semantics from the provider name.
- `source` and `fetched_at` preserve the provenance of the currently selected
  canonical observation. A later refresh may replace that observation
  atomically but must not create a duplicate provider copy for the same key.
- `currency` identifies the monetary currency and `price_scale` converts the
  stored quote into one currency unit. For example, a VN quote stored in
  thousands of VND uses `currency = VND` and `price_scale = 1000`. Crypto quote
  assets such as USDT and USDC are stored by their own codes and are not
  silently normalized to USD.
- Provider OHLCV observations use PostgreSQL double precision because upstream
  market data already arrives as floating point and analytical workloads favor
  compact numeric arrays. Exact decimal types remain appropriate for accounting
  and transactional monetary values.
- Weekly and monthly bars are derived from daily observations and are not stored
  as duplicate source data at this stage.
- The one-time universe CSV importer and its source caches were removed after
  database and price-history parity were verified. PostgreSQL
  backups, rather than CSV application caches, are the recovery mechanism for
  canonical price bars.
- Provider rows with non-positive or non-finite prices, inverted high/low, or
  negative/non-finite volume are reported and omitted. The canonical table's
  constraints preserve the same minimum quality boundary for future writers.

### Binance Spot ingestion

- Binance public market-data access is unauthenticated; the application does
  not request or store trading API keys.
- `/api/v3/exchangeInfo` is normalized in memory before a short atomic catalog
  transaction upserts assets, the `BINANCE_SPOT` venue, spot instruments,
  exchange symbol mappings, scalar trading rules, and the current
  `BINANCE_SPOT` instrument universe.
- Missing instruments are retained and marked inactive. A provider outage,
  empty response, duplicate symbol, or malformed identity aborts the catalog
  update rather than replacing the last known-good universe.
- Historical daily bars use checksum-verified monthly files from Binance
  Public Data. REST `/api/v3/klines` fills uncovered archive months and the
  incremental tail. Network downloads occur outside database transactions;
  each validated instrument history is committed separately.
- Binance daily bars use `price_basis = venue_unadjusted`, preserve their
  archive or REST source per observation, and are keyed to the Binance venue
  instrument. They must not be presented as global asset-level reference
  prices.
- The safe operational default synchronizes only the catalog. History loading
  requires an explicit symbol or quote-asset selector and enforces a maximum
  selection size unless the operator deliberately raises it.
- `GET /crypto/markets` is the read projection for the Crypto Instruments UI. It
  pages venue instruments in PostgreSQL, applies search, venue, quote-asset,
  and active-state filters server-side, and returns trading rules plus derived
  price coverage. Venue is an explicit row and filter dimension so Binance Spot
  and a future OKX Spot listing over the same assets remain separate
  instruments. The UI labels rows as spot instruments rather than companies or
  global crypto assets.

### Reference-rate ingestion

- A reference rate is modeled with the same canonical `instruments` table as
  other products, using `instrument_type = reference_rate`. It links canonical
  base and quote assets but has no company and no economic venue.
- `BTC-USD` and `ETH-USD` are the initial reference-rate instruments. BTC or
  ETH is the base asset and USD is the quote asset. They are distinct from
  venue instruments such as Binance BTC/USDT or ETH/USDT: the quote asset,
  price semantics, and identity are different.
- Yahoo Finance is the current observation provider and `yfinance` is the
  software adapter. Provider provenance remains an open string on the symbol,
  instrument, and price observation; changing adapters does not change the
  instrument's canonical identity and does not require a provider table.
- Daily observations use `price_basis = provider_unspecified` because the
  provider contract does not give this application a durable adjusted-versus-
  unadjusted guarantee. They are stored in canonical `price_bars` with USD as
  the quote currency, never as a JSON cache or a venue-specific trade series.
- `GET /reference-rates` is a 50-row server-paginated read projection with
  search, base/quote, and active-state filters. Its explicit null venue is a
  semantic distinction, not missing catalog data.
- The operational sync seeds the registered catalog safely by default.
  Historical network retrieval requires `--history`, can be bounded with an
  explicit `--symbols` list, requests each asset's earliest plausible history
  for a fresh database, and overlaps seven days on incremental refreshes before
  idempotent upsert. Stored coverage begins on the provider's first returned
  observation, which may be later than the requested start.

### Market-index ingestion

- SPX and VN30 are venue-less canonical Instruments with
  `instrument_type = market_index`. The index itself is calculated rather than
  traded, has no issuing Company, and does not receive a synthetic Venue or
  base/quote Asset relationship.
- Canonical symbols are SPX and VN30. Provider mappings live in
  `instrument_symbols`: Yahoo Finance `^GSPC` for SPX and VNStock Data `VN30`
  for VN30. Their acquisition adapters remain application policy rather than a
  Provider table.
- Daily index observations use the normal `price_bars`,
  `price_bar_coverages`, and `price_refresh_states` tables with
  `price_basis = index_level`. Source and fetch provenance remain attached to
  each selected canonical observation.
- Venue-less does not mean continuously traded. SPX follows the US equity
  session policy and VN30 follows the Vietnam equity session policy through
  their registered index routing definitions.
- Price History resolves its relative-strength benchmark from these stored
  canonical Instruments. A missing benchmark leaves relative strength empty;
  it never triggers an implicit provider download during an analytical read.
- `scripts.sync_market_indices` performs explicit incremental or full provider
  refresh. Data Operations can also find SPX or VN30 as exact Instruments and
  uses the same metadata-derived routing and exact-ID write path.

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

## Application layering

The backend dependency direction is:

```text
route -> service -> repository protocol
                    ^
wiring -> SQLAlchemy repository -> database models
```

- Repositories contain persistence queries and return persistence-neutral
  records. They do not implement business rules and never commit transactions.
- Services implement use cases and depend on repository protocols. Service
  modules must not import FastAPI, SQLAlchemy, or concrete database models.
- Routes validate HTTP input, call one service use case, map service errors to
  HTTP responses, and serialize explicit Pydantic response models.
- SQLAlchemy models never cross the API boundary and are never serialized
  directly to the frontend.
- Dependency wiring belongs in `api/deps.py`; routes must not construct engines,
  sessions, repositories, or services.
- Collection queries have deterministic ordering and explicit upper bounds.
- Write use cases define one transaction boundary. A future unit-of-work
  abstraction may expose that boundary to services; repositories still do not
  call `commit`.

The frontend is independent from backend implementation layers. It communicates
only through HTTP clients and generated API contracts. Frontend code must never
depend on repository, service, ORM, or database concepts.

Exact-instrument price-history reads follow the same boundary.
`InstrumentAnalysisService` resolves an instrument's canonical basis and
constructs engine `PriceFrame` objects plus provenance metadata. Only dependency
wiring may instantiate the SQLAlchemy implementation; routes do not access ORM
models or repository implementations.

## End-to-end contracts

FastAPI Pydantic request and response schemas are the canonical HTTP contract.
The checked-in `frontend/openapi.json` and
`frontend/src/lib/generated/api-schema.ts` are generated artifacts; do not edit
them manually.

- Give stable `operation_id` values to endpoints consumed through generated
  operation types.
- Run `pnpm generate:api` whenever a Pydantic schema, route parameter, response,
  or operation ID changes.
- Frontend clients derive request and response types from the generated schema
  instead of declaring parallel interfaces.
- Run `pnpm check:api-types` in validation to regenerate into temporary files
  and detect contract drift independently of the current Git state.
- Runtime parsing may be added at untrusted external boundaries. Within this
  application, generated types provide compile-time alignment while Pydantic
  performs backend runtime validation.

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

### 2026-08-02 — Layered company reads and generated web contracts

Context: moving Companies from static files to PostgreSQL could couple routes or
React components to persistence details, while handwritten Pydantic and
TypeScript interfaces could silently drift.

Decision: separate repository protocols, SQLAlchemy repository implementations,
application services, and FastAPI routes. Use FastAPI OpenAPI as the source for
generated frontend request and response types. Enforce key dependency boundaries
with tests.

Consequences: the UI can change independently from persistence, services can be
tested without FastAPI or SQLAlchemy, and API contract changes become explicit
generated diffs. Contract generation is now part of the validation workflow.

### 2026-08-02 — Complete company read cutover

Context: after the Companies page moved to PostgreSQL, Price History still used
the legacy `/symbol-lists` API and handwritten TypeScript contracts to populate
its ticker selector.

Decision: migrate Price History to the generated `/companies` contract and
remove the legacy symbol-list HTTP routes, schemas, frontend types, and route
tests. Retain the saved symbol-list files and `api/symbol_list_data.py` solely as
inputs to the idempotent PostgreSQL importer.

Consequences: PostgreSQL is the single application read source for company and
universe membership data. Company metadata no longer has two public contracts.
This retained-snapshot recovery approach was later superseded by live audited
Universe synchronization and PostgreSQL backups.

### 2026-08-03 — Canonical daily price-bar storage

Context: market price histories are still stored in overlapping universe CSV
caches. The same ticker can appear in multiple files, and later market-health
and relative-strength calculations need efficient symbol-range and
cross-sectional date reads.

Decision: add canonical `price_bars` keyed by instrument, trading date, and
price basis. Store provider and fetch provenance plus explicit currency and
price scale. Index trading date for cross-sectional work and rely on the unique
key for instrument date-range reads. Preserve daily bars as the source grain;
derive weekly and monthly views when reading.

Consequences: the schema can hold each instrument's daily history once despite
overlapping universes. Existing CSV caches remain the active read source until
a separate, verified importer and repository cutover are implemented.

### 2026-08-03 — Transactional price-cache import

Context: importing overlapping universe files independently could duplicate
bars, silently overwrite newer observations, or commit only part of the market
when a later file is invalid.

Decision: stage each CSV with PostgreSQL `COPY` inside one transaction, validate
it, and upsert by the canonical instrument/date/basis key. Process broader
universes first, update only from a newer manifest, and reject conflicting rows
that claim the same fetch timestamp. Keep the file read path unchanged during
this import stage.

Consequences: the existing 1.3 GB cache can be loaded efficiently and rerun
without rewriting unchanged rows. Invalid provider observations are counted but
do not prevent valid market history from migrating. The files cannot be removed
until refresh writes and application reads have separately moved to PostgreSQL.

### 2026-08-03 — Price-history repository and service boundary

Context: PostgreSQL contains canonical bars, but routes must not query ORM
models directly and market-health needs a bulk path that does not materialize
ORM entities.

Decision: introduce a persistence-neutral price-bar repository protocol with
streaming symbol/universe range queries, a SQLAlchemy projection repository,
and a price-history service that returns `PriceFrame` data with explicit source,
basis, currency, scale, and coverage metadata. Construct the concrete repository
only in `api/deps.py`.

Consequences: the next read cutover can replace CSV calls at the route boundary
without changing analytical code or coupling HTTP/UI code to PostgreSQL. This
stage initially did not change application reads.

### 2026-08-03 — Price History and Market Health read cutover

Context: after canonical price bars and service boundaries were verified, the
two analytical read paths still depended on overlapping universe CSV files.
Loading every historical database row for Market Health would also materialize
far more data than its intended ten-year display requires.

Decision: inject `PriceHistoryService` into the Price History and Market Health
routes. Preserve the public source and price-basis labels. For Market Health,
query ten years plus a rolling-window warm-up, stream rows in ticker order, and
return the ten-year calculated series. The distribution drill-down queries only
the requested date and its warm-up range.

Consequences: these application reads no longer depend on the market-history
CSV files, and UI/analytical code remains independent from persistence.
Benchmark and fundamental files are separate migrations.

### 2026-08-05 — Market Health close-only read path

Context: the five-universe Market Health endpoint loaded 3.82 million full
OHLCV rows into per-symbol dataclasses and `PriceFrame` objects even though the
calculation uses only closing prices. A live all-market request took 76.6
seconds and returned 2.9 MB; US2000 alone materialized 2.72 million rows.

Decision: give Market Health a dedicated persistence-neutral data service and
a SQLAlchemy repository projection that reads only instrument ID, session date,
and close, ordered by instrument ID and date, then pivots directly to the
date-by-symbol matrix consumed by the engine. Latest dates come from canonical
coverage rather than scanning price bars. The Run request carries one or more
selected universes, and the frontend exposes that selection before execution.
Historical response points contain only date, health score, and median distance;
the current point retains the full diagnostic fields. This was the initial
close-only contract before simplifying the indicator below.

Consequences: the identical live all-five request takes 11.9 seconds and returns
583 KB, while US2000 alone takes 6.7 seconds and returns 113 KB. Health score and
median-distance histories match the previous endpoint exactly for every market.
This established the non-persistent Phase 1 optimization baseline.

### 2026-08-05 — Median-only Market Health indicator

Context: the configurable composite score duplicated information that was not
currently needed. The useful market-level signal is the cross-sectional median
of each eligible stock's percentage distance from its trailing 200-session
closing high. The current 10-band stock distribution and drill-down remain
useful diagnostics and must not be removed.

Decision: make `median_distance` the only historical Market Health indicator.
Remove composite coefficients, component breadth histories, composite score,
regime classification, and the composite chart from the engine, HTTP contract,
and frontend. Retain current coverage metadata and all 10 drawdown buckets.
After a stock has begun trading, carry its last observable close across an
exchange session with no trade; do not fill leading pre-listing dates. Apply
the same panel convention to the chart and distribution drill-down so
illiquid constituents do not fail coverage merely because they skipped a
session.

Consequences: the endpoint returns only date and median distance for historical
points, reducing the all-five response from 583 KB to 377 KB. A warm live run
on the current local dataset took 14.6 seconds; database and host load make this
timing variable. Every median observation exactly matched the prior close-only
implementation. A persisted derived series is unnecessary until this remaining
calculation needs materially lower latency.

### 2026-08-08 — Historical context for Market Health

Context: a current cross-sectional median distance is difficult to interpret
without knowing where that same universe normally trades. Raw levels are not
directly comparable across universes, and crash observations make a time-series
mean less representative of a typical session.

Decision: summarize each universe against its own displayed daily
`median_distance` series, using up to ten years of available observations.
Report the time-series median, 25th and 75th
percentiles, observation count, and the empirical midrank percentile of the
latest reading. The percentile is the share strictly below the latest value
plus half the share tied with it. Because a less-negative distance is healthier,
higher ranks are stronger. Classify ranks as exceptionally weak below 10,
weak from 10 to below 25, normal from 25 to below 75, strong from 75 to below
90, and exceptionally strong from 90 through 100. Calculate this context in
the engine and serialize it through the API; the frontend only presents it.

Consequences: Market Health cards show current position relative to a robust
typical value and normal range without assuming a normal distribution. The
classification is descriptive, universe-specific, and not a trading signal.
Render each universe in a separate historical chart. Alongside the daily
cross-sectional `median_distance`, plot trailing 10-year, 5-year, and 1-year
calendar-window medians through each date. Window boundaries are inclusive,
available pre-display history is loaded so early visible points have genuine
trailing context, and no running baseline uses future observations. The latest
10-year value aligns with the historical median on the market card.

### 2026-08-05 — VN size-segment and all-share universes

Context: VN30 and VN100 did not expose the small-cap segment or a broad HOSE
health view. VNStock 4.0.5 declares additional index groups, but live provider
verification showed KBS returning complete constituents more reliably than VCI
for these group listings.

Decision: store VNMID, VNSML, and VNALL as system-managed, single-market
universes alongside VN30 and VN100. KBS is the constituent source and primary
OHLCV source; VCI is the fallback when KBS fails or does not reach the requested
completed session. One synchronized snapshot must preserve the exact set
identities `VN100 = VN30 union VNMID` and `VNALL = VN100 union VNSML`; the
2026-08-05 snapshot contains 30, 70, 100, 215, and 315 members respectively.
All five memberships point to shared canonical VN instruments and price bars.

Market Data refreshes VNALL first and passes successful ticker identities to
the four narrower views, so overlap never causes a second provider download in
the same run. Fundamentals remain stored once per instrument and use the same
reuse convention. Market Health calculates and drills down each membership
independently from PostgreSQL, while Price History selects the narrowest saved
VN membership containing the chosen company.

Consequences: VNAllshare provides broad HOSE market health, and VNMidCap and
VNSmallCap expose size-segment behavior without duplicating stored prices. The
VNStock 4.0.5 community tier currently limits newly requested daily OHLCV to
eight years, so the ten-year Market Health window uses all stored history but
cannot manufacture the two unavailable years for newly added constituents.
The snapshots still represent current membership rather than effective-dated
historical membership, so historical charts retain survivorship bias.

### 2026-08-07 — Provider-aware VN refresh completion

Context: a VN refresh was reported as successful whenever every provider call
returned a non-empty frame and the subprocess exited with code zero. Illiquid
symbols could legitimately have no bar on the expected session, causing the UI
to show the same tickers as stale and redownload them indefinitely. A recent
fetch timestamp could not distinguish a provider check from actual bar coverage.

Decision: VN daily history uses KBS first and VCI as fallback when KBS errors,
returns no rows, or ends before the requested completed session. When both
sources return data, the frame reaching the later session wins, ties prefer KBS,
and overlapping normalized OHLCV values are compared in refresh diagnostics.
Canonical rows retain their selected provider per bar; derived coverage reports
`mixed` when a series contains more than one provider.

Persist the latest per-symbol check in `price_refresh_states`, including the
requested `attempted_through`, provider `returned_through`, outcome (`current`,
`checked_no_new_bar`, or `failed`), selected provider, timestamp, and diagnostic
detail. Incremental planning reuses a successful no-new-bar check for the same
expected session. Market status keeps actual last-trade coverage separate and
reports checked-without-new-bar and provider failures independently. A universe
is operationally checked when every member either has a current bar or a
successful no-new-bar check, with no refresh failures.

Consequences: job completion describes successful checking rather than claiming
every symbol traded. No-new-bar symbols do not loop within the same session,
real failures remain retryable, and downstream analysis still uses canonical
stored bars with explicit row-level provenance. Provider comparison is
diagnostic; it does not manufacture or forward-fill a missing OHLCV bar.

### 2026-08-03 — Incremental PostgreSQL price refresh

Context: after the read cutover, provider refresh jobs still planned from and
rewrote overlapping universe CSV files. This made the old files operationally
necessary and could redownload the same US100/VN30 constituent after a broader
universe had already refreshed it.

Decision: plan incremental refreshes from per-instrument PostgreSQL coverage,
request a seven-calendar-day overlap only for stale symbols, validate provider
rows in the price-refresh service, and upsert with the canonical
instrument/date/basis key. Network calls occur outside transactions; each
universe write is one short transaction. An all-market full refresh processes
US2000, US500, US100, then VNALL before its overlapping VN100, VN30, VNMID, and
VNSML views, carrying successful ticker identities forward to avoid repeated
downloads. VNStock continues to use VCI and its
rate-safe checkpoint between provider calls; benchmark refresh remains a
separate file-backed workflow.

Refresh planning uses the latest completed session for each market. In
particular, a daytime VN refresh before the 15:15 close must target the previous
session rather than redownloading every ticker in pursuit of an incomplete day.
The same convention prevents a Vietnam-daytime refresh from treating a not-yet-
opened US session as missing.

Consequences: price refresh no longer reads or writes universe CSV history and
can resume incrementally from the database. Transient VN download checkpoints
are not canonical data.

### 2026-08-03 — Price storage parity and maintenance cutover

Context: price reads and refresh writes used PostgreSQL, but the Market Data
page still reported and deleted old universe CSV files. A universe-scoped
database delete is unsafe because canonical bars are shared by overlapping
universes such as US100, US500, and US2000.

Decision: derive Market Data coverage, row counts, sources, basis, and refresh
time through a persistence-neutral price-storage service backed by PostgreSQL.
Maintain per-instrument coverage summaries transactionally with price writes so
operational queries do not repeatedly scan millions of daily bars.
Clear operations are market-scoped: clearing any US entry removes all US price
bars, and clearing a VN entry removes all VN price bars. The UI exposes one
explicit clear action per market and names every affected universe before
confirmation. API mutation transactions are owned by the dependency boundary;
repositories never commit. Market Data response types in the frontend are
generated from the OpenAPI contract.

Verification compared representative OHLCV histories and recalculated Market
Health from PostgreSQL against the frozen CSV copies. US100 matched across
1,332 shared output sessions and VN30 across 1,324; the only observed difference
was floating-point noise of approximately 2.1e-14 in one median value.

Consequences: no application price read, refresh, status, or clear path depends
on universe or single-symbol CSV files. Those files and their legacy
loader/import tooling were deleted after verification. Benchmark histories,
fundamental snapshots, and transient VN refresh recovery checkpoints remain
separate file-backed concerns.

### 2026-08-03 — Point-in-time fundamental persistence model

Context: the file-backed fundamental snapshots mix report identity, accounting
facts, derived TTM measures, and sparse provider valuation ratios in one wide
row. Finance analysis must distinguish the period described by a report from
the first market session on which the report could have been known, and must
retain later restatements without rewriting historical knowledge.

Decision: persist report identity and availability in `fundamental_reports` and
normalized numeric metrics in `fundamental_facts`. Every report has a stable
source-specific `report_key`, `period_end`, optional publication timestamp, and
required `effective_session_date`. Facts use exact numeric values with explicit
unit, currency, scale, period basis, provenance kind, and calculation version.
Original and restated reports are separate rows, so an as-known-on-date query
selects only reports whose effective session is not later than the requested
date.

Sparse P/E, P/B, P/S, or EV/EBITDA values explicitly reported by a provider are
stored separately in `provider_valuation_observations` for comparison and audit.
They are not forward-filled as the canonical daily series. Daily valuation is
calculated from the daily PostgreSQL close and the latest eligible point-in-time
fundamental. `fundamental_refresh_runs` durably records provider version, counts,
status, and errors for one universe refresh.

Consequences: the schema supports revisions, new metrics, different currencies,
reported versus derived values, and reproducible calculation versions without
adding daily valuation duplication. This stage adds persistence only; existing
fundamental cache reads and refresh writes remain unchanged until importer and
repository/service parity are separately verified.

### 2026-08-04 — PostgreSQL-first single-company Factor Rarity

Context: Factor Rarity previously accepted a free-form ticker and provider
choice, then downloaded a complete history on every analysis. That bypassed the
canonical company and price-bar models, repeated provider work, and allowed
analysis of symbols absent from the application database.

Decision: the company workflow accepts only a canonical `market` plus `ticker`
identity from the active PostgreSQL instruments. Price retrieval is owned by a
persistence-neutral company price service: it reads the canonical market basis
from PostgreSQL, compares coverage with the latest completed market session,
and refreshes only the selected stale ticker with a seven-day overlap before
running the engine analysis. A provider failure preserves usable stored bars
and is returned as explicit staleness metadata rather than silently replacing
the stored series. US uses adjusted Yahoo bars; VN uses VCI provider bars with
the existing unspecified-adjustment basis. The shared company/ticker selector
is presentation-only and is reused by Price History and Factor Rarity.

The HTTP contract returns market, expected and actual last sessions, refresh
status, warning, source, and price basis. Frontend rarity types are generated
from that OpenAPI contract. The company-only form does not expose AHR999 because
that factor is not part of the US/VN company price model.

Consequences: clicking Analyse normally performs a PostgreSQL read and no
provider request. Missing or stale data causes at most one targeted refresh per
ticker and expected session in the running API process; repeated analyses in
that process reuse the stored result. Exchange-holiday awareness and durable
cross-process refresh-attempt tracking remain future scheduling concerns.

### 2026-08-04 — PostgreSQL-first single-company SMA Strategy

Context: SMA Strategy still accepted a free-form symbol and provider choice and
called the provider-backed generic loader on every run. This gave it different
company identity, freshness, and persistence behavior from Factor Rarity and
Price History.

Decision: `/backtest/analyze` accepts canonical `market` plus `ticker`, rejects
companies absent from PostgreSQL, and obtains its full history through the same
`CompanyPriceService` used by Factor Rarity. The service performs a targeted
refresh only when that selected ticker is stale. Optional analysis dates slice
the returned in-memory `PriceFrame`; they do not create a second storage path or
alter canonical bars. Strategy construction and all performance calculations
remain in the engine. The response carries the same freshness, provider, and
price-basis metadata as Factor Rarity.

The SMA page reuses the shared US/VN company selector and executes analysis as
an explicit mutation per Run click. Its response and nested performance types
come from the generated OpenAPI contract.

Consequences: repeated SMA runs use PostgreSQL instead of redownloading full
history, while a stale symbol causes only one ticker refresh. The generic
multi-symbol portfolio backtest remains provider-configurable; this decision
applies specifically to the single-company analysis endpoint and SMA page.

### 2026-08-04 — Single-market watchlists and stored Predefined Rarity

Context: system universes and user-selected ticker groups are both instrument
collections, but they have different ownership and lifecycle. Treating a
watchlist as a universe would let user edits interfere with provider-managed
constituents and market-data refresh planning. Predefined Rarity also accepted
free-form symbols and downloaded them directly, bypassing canonical companies.

Decision: keep `watchlists` and ordered `watchlist_memberships` separate from
`universes` and `universe_memberships`. Every watchlist has one immutable `US`
or `VN` market. The watchlist service normalizes names and tickers, enforces
case-insensitive name uniqueness per market, resolves every member against an
active instrument in that same market, and owns CRUD behavior through a
persistence-neutral repository. SQLAlchemy construction and transaction
ownership remain in `api/deps.py`. Composite database foreign keys include the
market on both the watchlist and instrument references, so cross-market
membership is rejected even if a write bypasses the service.

Predefined Rarity now accepts only `watchlist_id`. It resolves canonical
members, bulk-reads their market-specific price basis from PostgreSQL, and
reports missing and stale symbols without making provider calls. An empty
watchlist or one with no stored history is rejected explicitly. Watchlist CRUD
and analysis response types are generated from OpenAPI, and the UI provides a
dedicated Watchlists page plus a market-filtered selector on Predefined.

Consequences: universes remain system/provider-managed populations used by
Market Data and Market Health; watchlists remain user-managed analysis inputs.
Both can later satisfy a shared read-only instrument-set interface without
sharing persistence or mutation semantics. Bulk watchlist refresh is a separate
explicit workflow and is not hidden inside Analyse. The explicit Update prices
action lives on the watchlist detail page, while Market Data provides a central
monitor for the latest watchlist refresh jobs. The background worker reads the
watchlist and PostgreSQL coverage in a short transaction, downloads only missing
or stale members outside any database transaction, then bulk-upserts successful
histories in a separate transaction. VN requests remain sequential and paced at
4.1 seconds; US requests use Yahoo Finance. Existing rows survive individual
provider failures, and no universe memberships are created or changed.
Universe refresh planning queries that same canonical coverage directly by
market and ticker, rather than treating coverage as owned by a universe. Thus a
completed watchlist refresh is reused by later incremental US500, US2000,
US100, VNALL, VN100, VN30, VNMID, or VNSML refreshes whenever the ticker and
price basis match.
API-launched price jobs also hold a shared per-market lease: only one US price
refresh and one VN price refresh may run concurrently, preventing overlapping
universes and watchlists from making duplicate provider calls. Fundamentals use
their independent job coordination because they have a different persistence
and freshness lifecycle.

Market Data status must not present the maximum ticker `fetched_at` or maximum
session date as if it represented the whole universe. Price status therefore
reports the expected completed session, the oldest latest-session date across
covered members (`coverage_through`), the newest ticker session, and separate
current, stale, missing, covered, and total-member counts. The maximum write
timestamp is labelled recent activity. Fundamentals likewise distinguish recent
activity from the oldest per-ticker latest fetch. Durable completed refresh runs
exist for fundamentals; adding the equivalent price-refresh-run persistence is
a separate schema change rather than deriving a false completion time.

### 2026-08-03 — Legacy fundamentals import

Context: after the point-in-time schema existed, 2,511 per-instrument CSV and
manifest pairs remained the only populated source for the current Price History
fundamental overlays.

Decision: import every complete cache pair atomically and idempotently. Each
legacy effective-date row becomes a report with a deterministic source key;
the importer does not invent unavailable publication or provider-observation
timestamps. Accounting and derived facts are normalized with exact numeric
values, while market cap and provider ratios become sparse valuation
observations with explicit units. Unknown instruments or malformed identities
abort the transaction. Non-finite individual values are omitted and reported.

The verified import contains 138,866 reports, 274,654 facts, and 18,600 provider
valuation observations for 2,511 instruments. Re-running produced identical
counts. Six non-finite `VN-BVH` revenue values were omitted. Latest FPT and PNJ
facts and valuation observations matched their source caches exactly at the
database's ten-decimal storage precision.

Consequences: PostgreSQL now contains a verified copy of the existing
point-in-time fundamentals, but application reads and provider refresh writes
remain file-backed. The next stage is a persistence-neutral repository and
service; no UI route should query these tables directly.

### 2026-08-03 — Fundamental repository and service boundary

Context: normalized PostgreSQL rows are intentionally different from the wide
per-symbol frame consumed by the existing Price History calculations. Routes
and React components must not depend on SQLAlchemy models or reconstruct that
projection independently.

Decision: `FundamentalRepository` is the persistence-neutral read contract and
`SqlAlchemyFundamentalRepository` is its PostgreSQL implementation. The
`FundamentalService` owns the application projection from reports, facts, and
sparse provider valuations into the existing wide point-in-time frame. Concrete
repository construction lives only in `api/deps.py`. Period labels and provider
methodology are explicit report attributes because they are part of the current
consumer contract and cannot be inferred reliably after import.

The service normalizes market and ticker identity, preserves report-effective
dates, exposes source and methodology metadata, and aggregates universe status.
It does not calculate valuation ratios or contain SQLAlchemy queries. Daily P/E
and P/B remain downstream calculations that combine price bars with the latest
eligible point-in-time facts.

Consequences: service and repository behavior can be tested independently, and
future storage implementations can satisfy the same contract without changing
the UI. Live FPT and PNJ projections were verified against the legacy cache for
all identity and numeric columns. Application routes and refresh writes remain
file-backed until their separate cutover stages; the cache is retained until no
runtime reader or writer depends on it.

### 2026-08-03 — Fundamental read cutover

Context: the repository/service projection matched the imported cache, so
application reads no longer needed to depend on per-symbol CSV files. Keeping
two read implementations would allow Price History and Market Data status to
disagree about the same stored facts.

Decision: Price History obtains point-in-time snapshots and metadata through
`FundamentalService`. Market Data obtains per-universe fundamental coverage from
the same service. Routes depend only on services injected by `api/deps.py`; they
do not import the legacy cache or SQLAlchemy repositories. The existing API
response fields remain stable during this transition, but the former cache-path
field reports `PostgreSQL`, and per-universe file size is zero because shared
normalized rows have no meaningful file-size measure.

Missing fundamentals remain non-fatal for Price History. Database and
programming failures are no longer swallowed as if a company simply lacked
reports. Provider-reported ratios remain sparse comparison values; daily P/E
and P/B continue to be calculated from PostgreSQL prices and eligible facts.

Consequences: Price History and fundamental coverage status now read only from
PostgreSQL. The provider refresh worker still writes the legacy cache during
this intermediate stage, so its database write cutover is the next required
step before the old cache can be removed.

### 2026-08-03 — Fundamental refresh write cutover

Context: after the read cutover, a file-backed refresh would not update the
canonical data read by Price History. It also based cross-universe reuse on JSON
manifests and ignored the requested full-versus-incremental mode.

Decision: the fundamentals worker now obtains universe constituents from the
company repository and uses report `fetched_at` values in PostgreSQL for its
12-hour overlap-reuse window. Provider calls occur outside database
transactions. Each successful symbol is converted by
`FundamentalWriteService` and upserted atomically through
`FundamentalRepository`; existing report keys are reused so refreshed facts do
not duplicate migrated history. Incremental mode reuses recently refreshed
symbols. Full mode bypasses data from before that run while still reusing an
overlapping ticker refreshed earlier in the same ordered all-universe run.

Every universe run is recorded in `fundamental_refresh_runs` with requested,
reused, succeeded, and failed counts plus a bounded error summary. A failure for
one symbol rolls back only that symbol and preserves all previously stored
facts. The API and UI now describe both price and fundamental storage as
PostgreSQL; file-size and cache-directory fields were removed from the typed
contract.

Consequences: application reads and normal refresh writes no longer require
fundamental CSV files. A live FPT VCI refresh upserted 33 reports, 462 facts, and
198 valuation observations while retaining exactly 33 stored reports. The
legacy cache/import utilities may now be removed in a separate cleanup after a
final dependency audit.

### 2026-08-04 — Fundamental cache removal

Context: PostgreSQL parity, read cutover, and refresh-write cutover were all
verified, leaving the one-time CSV importer and cache helpers as dead migration
code. Keeping them would preserve a second, misleading persistence convention
and retain 5,022 migrated files occupying approximately 25 MB.

Decision: provider acquisition and frame normalization live in
`api/fundamental_provider.py`, which performs no filesystem persistence. The
one-time importer, its CLI, cache-only tests, and `api/fundamentals_cache.py`
were removed. The `.cache/fundamentals` directory was permanently deleted only
after the full test suite, production build, API-contract check, refresh-worker
import check, and live FPT/PNJ plus five-universe PostgreSQL reads succeeded.

Consequences: PostgreSQL is the sole fundamental persistence system. Normal
reads and refreshes cannot recreate the deleted CSV directory. Historical data
is retained in normalized reports, facts, and sparse valuation observations;
provider refreshes remain the recovery path for future data acquisition.

### 2026-08-08 — Sponsored VN provider boundary

Context: the application acquired sponsored Vnstock access, but canonical VN
refreshes still import the public `vnstock` package directly. Merely storing the
API key does not activate sponsored methods, and hard-coding package versions or
assuming Unified UI selected KBS versus VCI would create false provenance.

Decision: load project-local environment values through `api.config` without
overwriting process variables, and isolate sponsored/community access behind
typed adapters in `api.providers.vietnam_market`. Sponsored access is preferred
when `vnstock_data` is installed. It must fail explicitly if installed but
authentication fails; community fallback is allowed only when the package is
absent and the caller did not require sponsored access. Sponsored OHLCV uses
the package's explicit VCI `Quote.history` route: Unified UI routes OHLCV to KBS,
whose FPT canary exposed only about ten years and did not preserve canonical VCI
price/volume history. Trading statistics continue through Unified UI, which
explicitly routes that method to VCI. Package versions are discovered at
runtime. A read-only diagnostic validates FPT OHLCV and historical
trading-statistics schemas without logging secrets or writing canonical data.

Consequences: VN price refreshes and application VN price reads use sponsored
VCI through one typed loader, record the runtime package version and explicit
VCI upstream in row provenance, and never silently downgrade. Community KBS/VCI
fallback is opt-in. A strict FPT canary must prove coverage and value parity
before the first sponsored write. Saved-watchlist refreshes use that same
loader and provenance so they cannot overwrite sponsored rows with newer public
KBS fetches. The VN30 relative-strength benchmark also uses sponsored VCI; a
legacy cache is replaced only after every stored overlapping bar passes strict
date and OHLCV parity. Sponsored VN requests default to 30 per minute after the
full VNALL rollout demonstrated that faster pacing amplified upstream timeout
clusters. Fundamental refresh remains a separate provider and persistence path.

### 2026-08-08 — Sponsored VN fundamental cutover

Context: VN fundamental refresh still imported community `vnstock` directly
and called a private VCI report method. The sponsored package's unified
`Finance` wrapper cannot currently support the application's point-in-time
contract: it coerces raw publication dates to `NaN`, while its formatted ratio
method removes the fiscal quarter and therefore cannot represent a missing
quarter faithfully.

Decision: VN fundamentals use a typed sponsored adapter around the explicit
`vnstock_data` VCI financial implementation. Income statements are obtained
through its public raw method, preserving `publicDate`. Ratio acquisition uses
the narrow raw-report hook because that is the only sponsored route retaining
the exact `year`, `quarter`, and `ratioType` fields. Normalization remains in
`api/fundamental_provider.py` and continues to make each report effective on
the day after `publicDate`, preventing same-day and historical look-ahead.

Fundamental persistence uses stable source identity `vci`; package name and
runtime version belong in methodology and `fundamental_refresh_runs`, not in a
report uniqueness key. Migration 0010 relabels existing VN VCI reports and
valuations and moves their fact calculation identity to `legacy-vci`. This
allows sponsored refreshes to update the same report, fact, and valuation rows
instead of duplicating the full history whenever the client package changes.

Consequences: normal VN fundamental refresh requires authenticated sponsored
access and never silently falls back to the community client. Provider-version
upgrades preserve database identity while remaining auditable. The explicit
raw ratio hook is a contained compatibility boundary covered by adapter and
point-in-time normalization tests; it can be removed when the sponsored public
ratio result retains exact fiscal-quarter keys.

### 2026-08-08 — Notebook and legacy VNStock loader retirement

Context: the API and all production VN price workflows already use the
sponsored application adapter `api.providers.VietnamPriceLoader`. The separate
engine `VNStockLoader` still imported public `vnstock`, implemented a different
KBS-to-VCI fallback policy, and had no consumers beyond its own tests and the
now-unneeded exploratory notebooks.

Decision: remove the notebook directory and retire the unused engine
`VNStockLoader` rather than rename or duplicate the sponsored adapter. The
`trading_engine` remains provider-neutral through its `DataLoader` protocol and
`PriceFrame`; VN provider selection and authentication stay in the application
adapter boundary. The external API request token `vnstock` remains a backwards-
compatible logical selector and resolves to sponsored `VietnamPriceLoader`.

Consequences: no engine or production path imports public `vnstock` directly.
There is one canonical VN application loader with explicit sponsored VCI
provenance and end-exclusive engine date semantics. Public-package access is
limited to the deliberately explicit community recovery adapter and is not an
automatic production fallback.

### 2026-08-08 — Reproducible private sponsor installation

Context: `vnstock_data` is distributed through Vnstock's authenticated member
installer rather than the public package index. Its installed distribution
therefore points to a temporary local bundle and cannot be represented safely
in `pyproject.toml` or `uv.lock`. An exact `uv sync` would remove that package
and its private companion dependencies without an application code change.

Decision: the project setup first runs `uv sync --all-groups --inexact`, then
invokes `scripts.setup_vnstock_data`, which downloads the official CLI installer
over HTTPS, supplies the ignored `VNSTOCK_API_KEY`, targets the project `.venv`,
and verifies `vnstock_data >= 3.2.7`. Routine `uv run` commands use `--no-sync`;
dependency changes must go through `pnpm setup`. The public `vnstock` package is
no longer a direct project dependency. It may still be installed transitively
by the sponsor bundle or deliberately used by the explicit community recovery
adapter.

Consequences: a new machine has one documented setup command, secrets and
temporary sponsor paths stay out of Git, and later development commands cannot
silently prune sponsored access. Sponsor updates remain controlled by the
official installer and are recorded dynamically in data provenance rather than
pretended to be reproducible through a stale public lock entry.

The root commands also set `UV_CACHE_DIR=.cache/uv`. This ignored project-local
cache keeps setup and validation independent from home-directory permissions
without making dependency artifacts part of source control.

### 2026-08-08 — Final VN provider compatibility and recovery policy

Context: the provider migration left two identities that serve different
purposes. API clients and saved universe metadata already use the logical token
`vnstock`, while stored price rows carry concrete acquisition provenance such
as `vnstock-data-3.2.7-vci`. Removing the logical token would be an unnecessary
contract break; displaying concrete provenance verbatim would make the UI hard
to interpret.

Decision: retain `vnstock` as the backwards-compatible API selector, resolving
it only to the sponsored `VietnamPriceLoader`. Present concrete stored sources
through a shared UI formatter, including the upstream provider and sponsored
package version where available. Normal VN price and fundamental workflows
require sponsored access. Community KBS then VCI fetching remains available
only through the explicit recovery switch in the market-history refresh script;
it is never an automatic application fallback.

Consequences: external request contracts remain stable, operators can identify
the actual upstream and client version on stored price history, and a sponsor
failure is visible instead of silently changing the data source. Recovery use
is deliberate and its community provenance remains stored on the affected rows.

### 2026-08-09 — Live company-universe provider boundary

Context: PostgreSQL is already the canonical application read source for
companies and current universe membership, but its initial membership import
and the price-refresh symbol selector still depend on checked-in JSON and CSV
snapshots. Those files duplicate relational state and require manual refreshes.

Decision: introduce immutable, normalized universe snapshots and an
application-level provider protocol under `api/providers`. Source adapters
fetch Nasdaq-100, the listed-equity IWM holdings proxy, the S&P 500, the Dow 30,
and the three disjoint Vietnam size segments without writing provider payloads
to disk. VNStock KBS supplies VN30, VNMidCap, and VNSmallCap membership;
`VN100` and `VNALL` are derived in memory to preserve the established set
relationships. Provider-specific symbols are normalized at this boundary,
including US class-share notation used by the price loader. The public VNStock
listing adapter is an explicit universe-metadata input and does not change the
sponsored-only policy for normal VN prices or fundamentals.

Consequences: later synchronization work can validate one persistence-neutral
contract before acquiring database locks. Network and parser failures are
explicit, empty or duplicate normalized membership is rejected, and no new
company-list JSON or CSV is created. The existing static importer and
price-refresh file reader remain temporarily until the transactional writer and
consumer cutover are implemented and verified.

### 2026-08-09 — Canonical issuer, instrument, and symbol identity

Context: the initial `instruments` table mixed issuer metadata with listing
identity. That made two share classes look like two companies, made ticker
renames overwrite identity, and provided no durable place for symbols that
differ between an exchange and a data source.

Decision: add `companies`, `company_identifiers`, and `instrument_symbols`.
Move company name, sector, and industry out of `instruments`; every instrument
now belongs to exactly one company. Retain the current canonical ticker on the
instrument for compatibility and efficient established queries, while symbol
aliases and validity periods live in `instrument_symbols`. Stable issuer IDs
such as SEC CIK reconcile multiple instruments to one company. Source identity
is stored as an open string namespace/provenance value rather than normalized
through a provider table, because adapters and commercial access paths can
change without changing canonical financial identity.

Consequences: GOOG and GOOGL can be distinct tradable instruments of one
Alphabet company, while BRK.B and BRK-B can map to the same instrument in
different namespaces. Existing company-list API contracts remain unchanged but
now join issuer metadata. The migration performs a conservative one-company-
per-instrument legacy backfill; later trusted identifiers may reconcile those
rows without guessing from names alone.

### 2026-08-09 — Separate company catalog and instrument universe views

Context: the former Companies page rendered one row per market ticker, mixing
issuer language with instrument price coverage and universe membership. After
issuer identity became relational, the same company could correctly own more
than one instrument, so that presentation was no longer semantically valid.

Decision: `/instruments` is the canonical frontend view for tradable securities,
price coverage, exchange, and universe membership. `/companies` is a separate
issuer catalog backed by `GET /companies/catalog`; it returns one company row
with nested identifiers and instruments. The established `GET /companies`
instrument contract remains temporarily available to avoid a simultaneous
cross-application API rename. The legacy frontend `/company/lists` URL redirects
to `/instruments` and preserves its query string.

Consequences: company counts and instrument counts are no longer conflated in
the UI. Alphabet can appear once in the company catalog with GOOG and GOOGL,
while both securities remain independent rows in the Instruments page. A later
API cleanup may rename the legacy instrument endpoint after all consumers have
moved without changing either canonical database identity.

### 2026-08-09 — Server-paginated company and instrument catalogs

Context: both catalog pages initially loaded and rendered every matching row.
At roughly three thousand issuers and instruments this was functional, but it
transferred nested identity and membership data unnecessarily and created a
large browser DOM for every visit.

Decision: Companies and Instruments request 50 rows per page with server-side
offset pagination, debounced search, and server-side filters. Each response
includes total matching rows and aggregate facet counts computed independently
from the page slice, so country, sector, and universe controls remain accurate.
Offset pagination is preferred at this scale; cursor pagination is deferred
until catalog size or write frequency makes stable deep offsets a demonstrated
problem. Market Health drill-down retains its full computed-bucket join because
its membership is produced by the analytical result rather than a catalog
filter.

Consequences: normal page payload and rendered-row count are bounded at 50,
filter changes reset to the first page, and search waits 300 milliseconds before
querying. PostgreSQL remains authoritative for filtering and counts; the UI no
longer derives catalog facets from an incomplete client-side page.

### 2026-08-09 — Venue-neutral assets and Binance Spot ingestion

Context: the issuer/instrument schema required every instrument to belong to a
US or Vietnam company and limited quote currencies to three characters. That
could not represent decentralized crypto assets, stablecoin quotes, multiple
venue order books, or spot and derivative products without inventing companies
or treating exchange symbols as permanent asset identity.

Decision: add canonical `assets`, optional effective-dated `asset_issuers`, and
economic `venues`. Generalize instruments so company identity is optional and
spot products require a venue, base asset, and quote asset. Preserve the actual
quote asset and store venue-specific trading increments. Seed legacy equity
assets, issuer links, fiat quote assets, and known exchange venues
deterministically in migration `0012`. Introduce an unauthenticated Binance
Spot adapter, an atomic `BINANCE_SPOT` catalog synchronizer, checksum-verified
monthly archive loading, and REST gap/incremental retrieval. Do not add a
provider foreign key or persist raw provider JSON.

Consequences: BTC exists without a company, Binance BTC/USDT is a distinct spot
instrument denominated in USDT, and future venues can list their own instruments
without symbol collisions. Existing US/VN company and instrument APIs retain
their contracts. Binance supplies venue market data and an active-instrument
universe; it does not become the canonical source for global market-cap ranks,
cross-venue reference prices, token contracts, or crypto fundamentals.

The first frontend projection is a 50-row server-paginated Binance Spot market
catalog at `/crypto`. It exposes base/quote identity, active state, scalar
trading rules, venue identity, and stored daily-history coverage; it does not
imply that Binance is the canonical issuer or the only possible venue for an
asset.

### 2026-08-10 — Venue-less reference-rate instruments

Context: analysis already downloaded Yahoo's `BTC-USD`, while the canonical
crypto model only represented executable venue spot products such as Binance
BTC/USDT. Treating Yahoo as a venue would confuse observation provenance with
economic execution, and treating BTC/USD as a company or JSON dataset would
bypass the canonical asset and price-bar model.

Decision: represent BTC/USD as a venue-less `reference_rate` instrument linking
the canonical BTC and USD assets. Migration `0013` adds the database identity
constraint and seeds the instrument plus its Yahoo Finance symbol. Yahoo
Finance is stored as open-string provenance and `yfinance` remains an adapter,
not a provider or venue entity. Store its daily observations in `price_bars`
with `provider_unspecified` basis and expose a paginated `/reference-rates`
catalog and frontend page.

Consequences: BTC/USD and Binance BTC/USDT can coexist without pretending they
are interchangeable prices. Reference rates reuse the same coverage,
provenance, refresh, and PostgreSQL recovery model as other daily bars, while a
future provider or adapter can be substituted without changing instrument
identity. New reference-rate pairs can use the same model without creating a
new table per data family.

### 2026-08-10 — Register ETH/USD as a reference rate

Context: the reference-rate implementation initially registered only BTC/USD,
but ETH/USD has the same venue-less provider-observation semantics and should
not require a duplicated ingestion path or a new persistence model.

Decision: migration `0014` seeds canonical ETH and the Yahoo `ETH-USD` symbol.
The operational synchronizer now processes a bounded registry containing both
BTC-USD and ETH-USD, with optional symbol selection for targeted backfills.

Consequences: the Reference Rates page discovers ETH/USD automatically through
the existing paginated projection. Both rates share validation, provenance,
coverage, and canonical `price_bars` storage while remaining separate
instruments linked to their respective base assets.

### 2026-08-10 — Instrument-identified Factor Rarity

Context: Factor Rarity still used the legacy company-list projection and sent
`market + ticker`, even after issuer, tradable-product, venue, asset, and symbol
identity had been separated. That compatibility path was ambiguous for multiple
share classes and could not identify venue-specific spot instruments or
venue-less reference rates.

Decision: Factor Rarity now accepts only a positive canonical `instrument_id`.
`GET /instruments` is the server-side discovery boundary for analysis-ready
instruments and can search equities by issuer or symbol, spot instruments by
asset or venue, and reference rates by their asset pair. The selector stores the
ID while symbol, company, venue, base/quote assets, currency, coverage, price
basis, and source remain display or provenance metadata. Discovery defaults to
instruments with canonical PostgreSQL price coverage.

Price resolution reads `price_bars` by the exact instrument ID and canonical
basis: adjusted for US equities, provider-unspecified for VN equities and
reference rates, and venue-unadjusted for spot instruments. Existing targeted
US/VN refresh behavior remains behind the instrument boundary. Crypto spot and
reference-rate series are refreshed by their dedicated ingestion workflows; an
analysis request reports stale stored data explicitly instead of routing those
instruments through an equity provider.

Consequences: GOOG and GOOGL remain separate analyzable instruments of one
Alphabet issuer; Binance and OKX products with similar symbols cannot collide;
and BTC/USD reference-rate analysis does not invent a company or venue. The
engine contract remains unchanged because the API still resolves the selected
instrument into one `PriceFrame` before factor computation.

### 2026-08-10 — Cross-market instrument watchlists and predefined rarity

Context: saved watchlists were created as single-market company groups and
accepted ticker strings. Their memberships already referenced instruments, but
duplicated the watchlist market in each row and constrained every member to the
same market. Predefined Rarity then converted the membership back to
`market + ticker`, losing exact identity for venue-specific crypto instruments,
reference rates, and potentially colliding symbols.

Decision: migration `0015` removes market from `watchlists` and
`watchlist_memberships`. A watchlist is now a globally named, user-managed,
ordered set of active canonical `instrument_id` values. It may contain equities,
venue-specific crypto spot products, and venue-less reference rates together.
Universes remain provider or system-defined sourced collections; watchlists are
personal selections and do not carry source provenance. Predefined Rarity loads
canonical PostgreSQL price bars in bulk by exact instrument IDs and reports
availability, staleness, price basis, and source per instrument.

The existing bulk refresh workflow remains intentionally narrower than the
watchlist model: it is available only when every member is an equity and all
members belong to the same supported US or VN market. Mixed-asset, cross-market,
crypto, and reference-rate watchlists remain analyzable from stored canonical
bars, while their refreshes use the dedicated ingestion workflows for those
instrument types.

Consequences: watchlist membership no longer conflates companies with tradable
products or depends on mutable ticker text. Equal symbols on different venues
remain distinct, ordering is durable, and Predefined Rarity can analyze a mixed
instrument set without merging provenance. Existing duplicate watchlist names
from different markets are preserved during migration by adding their former
market suffix before global name uniqueness is applied.

### 2026-08-10 — Instrument Collections navigation and canonical universe catalog

Context: watchlists remained under the legacy `/company/watchlists` route even
after they became cross-market instrument collections. The only frontend-facing
universe endpoint was `/companies/universes`, which intentionally excluded
crypto and added synthetic `US_ALL` and `VN_ALL` company views. It therefore
could not describe the canonical `universes` table or a venue universe such as
Binance Spot.

Decision: introduce an Instrument Collections surface with separate
`/collections/universes` and `/collections/watchlists` URLs. The former is a
read-only projection of actual persisted universe records, including source,
as-of and synchronization metadata, active and total membership counts,
instrument types, and venues. Its membership table reuses the canonical
instrument discovery endpoint with an exact universe filter and 50-row
server-side pagination. The Watchlists tab retains user-managed ordered
membership. `/company/watchlists` is retired as a product URL and redirects to
the new watchlist collection URL for bookmark compatibility.

Universes and watchlists remain separate persistence models. A universe is a
provider- or system-synchronized collection with provenance and unordered
membership; a watchlist is a user-managed ordered collection and is never
overwritten by universe synchronization. The shared Collection concept exists
only in navigation and selection UI, not as a new polymorphic database table.

Consequences: Binance Spot is visible beside US and Vietnam universes without
inventing a company, while synthetic company catalog filters do not masquerade
as canonical universes. Cross-asset watchlists are no longer placed under
Company Analysis, and future data-coverage screens can select either collection
type while still resolving observations by exact instrument ID.

### 2026-08-10 — Market-neutral system universes

Context: the Universe catalog exposed `US`, `VN`, and `CRYPTO` as one `market`
classification. Those values mixed geography with asset class and made a
display filter look like a first-class domain entity. Universe identity and
membership do not require that classification: a universe is simply a named,
system-managed collection of canonical instruments.

Decision: migration `0016` removes `market` from `universes`. The canonical
Universe API and Collections UI expose the universe name, stable code,
provenance, synchronization metadata, and membership-derived instrument types
and venues, without a market field, filter, or badge. Universe membership is
read-only to application users and is replaced only by ingestion or internal
synchronization workflows. Watchlists remain separately persisted,
user-managed, ordered collections.

Legacy price-refresh, market-health, fundamentals, and company-list workflows
that currently require one operational US or VN scope derive it from the
universe's member instruments. They reject an empty or mixed-scope universe
instead of inferring behaviour from its code or display name. Names are for
people; backend routing must use canonical instrument metadata.

Consequences: new universes can span regions, venues, or asset classes without
schema changes, and `CRYPTO` is no longer presented as comparable to country
codes. Removing or renaming a universe does not alter instrument identity or
provider routing. The `market` compatibility field on instruments remains a
separate migration concern and is not part of Universe identity.

### 2026-08-11 — Instrument-centered Data Operations

Context: the retired Market Data page hardcoded eight US and Vietnam universes,
called each universe a market, inferred routing from code prefixes, and could
not update canonical Binance Spot or reference-rate instruments. It also mixed
collection coverage, update execution, destructive market-wide clearing, and
watchlist job monitoring on one legacy surface.

Decision: replace the product route with `/data-operations` and retain
`/market-data` only as a frontend redirect for bookmarks. Data Operations uses
a preview-first contract: the user selects a Universe, Watchlist, or exact
Instrument plus dataset and mode; the backend resolves current active members
to canonical instrument IDs and returns eligible, current, stale, missing, and
unsupported counts before allowing execution. Updating observations never
mutates collection membership.

Existing proven workers remain behind the new boundary. Supported US/VN
Universe price and fundamental jobs use the established universe refreshers;
homogeneous US- or VN-equity Watchlists use the watchlist price worker; and an
exact-instrument worker dispatches equities, Binance Spot instruments, and
registered Yahoo reference rates to their configured adapters. Fundamental
updates remain Universe-scoped for now. Bulk Binance-universe history is
intentionally unavailable because an unfiltered run would request more than a
thousand instruments; operators must select exact spot instruments.

Both Universe price and fundamental workers resolve their execution set from
the same active PostgreSQL `universe_memberships` projection used by the
preview. Checked-in JSON/CSV symbol snapshots are not an execution input. This
keeps the preview count, provider work, and canonical writes aligned even when
an ingestion workflow replaces current membership.

The legacy `/market-data` HTTP endpoints remain temporarily because Price
History and the established workers still consume their contracts. They are
compatibility adapters, not the product navigation or the canonical new update
boundary. Market-wide destructive clearing is removed from the UI; future
maintenance deletion must be explicitly instrument- and dataset-scoped.

Consequences: collection names no longer control provider routing, overlapping
Universe or Watchlist membership cannot duplicate canonical instrument
identity, and crypto/reference-rate histories are operable from the same UI as
equities. Operation coordination and progress remain in-process and are not a
durable history; canonical observation coverage and provider provenance remain
persisted on the data rows and coverage projections.

Price coverage on this surface is instrument-grained. The
`GET /data-operations/coverage` projection joins each active scope member to its
canonical `price_bar_coverages` and `price_refresh_states` rows. It exposes the
first and last stored sessions, stored observation count, price basis and
source, latest provider-check outcome, and the expected session calculated at
read time. No Universe- or Watchlist-level coverage row is persisted; their
current, stale, missing, checked-no-new-bar, and failed totals are derived from
the resolved member instruments.

`expected_sessions_behind` is a trailing freshness measure, not a claim that
the full historical series has no internal holes. It counts weekday sessions
after the latest stored US/VN equity bar through the expected session and daily
sessions for continuously traded crypto/reference-rate series. The expected
session follows the existing operational market-close calendar. Exchange
holiday-aware calendars and exact internal-gap auditing remain separate future
capabilities and must not be inferred from this field. Price coverage is shown
independently of the selected operation dataset; fundamental report coverage
requires its own point-in-time projection.

### 2026-08-11 — Canonical equity venues

Context: equity instruments originally stored free-text exchange labels and
migration `0012` converted those labels into `LEGACY:{market}:{exchange}` venue
rows. Those identifiers retained the old market shortcut and left equities
whose source snapshot omitted exchange without a venue. They were unsuitable
as the eventual replacement for `instruments.market`.

Decision: migration `0017` seeds canonical equity venues (`NASDAQ`, `NYSE`,
`NYSE_AMERICAN`, `NYSE_ARCA`, `CBOE_BZX`, `IEX`, `HOSE`, `HNX`, and `UPCOM`),
reassigns every trusted legacy exchange label, standardizes the compatibility
exchange value to the stable venue code, and removes unreferenced legacy venue
rows. Company-universe
imports resolve the same registry for future writes and preserve an already
enriched venue when a static membership snapshot has no exchange field.

Current US listing assignments can be refreshed from Nasdaq Trader's
`nasdaqlisted.txt` and `otherlisted.txt` directories with
`pnpm sync:equity-venues`. The adapter fetches both files in memory, excludes
test issues, reconciles current canonical and alias symbols, updates only
unambiguous matches, and persists no downloaded JSON or CSV snapshot. Unknown
or ambiguous symbols remain visible in command output rather than being
assigned to a fabricated catch-all venue. Vietnam assignments currently come
from the trusted HOSE/HNX/UPCOM labels supplied by the universe ingestion
source.

Consequences: venue is now the canonical current listing location for resolved
equities, while issuer country remains on Company and asset class remains on
Instrument. `instruments.market` and the free-text `exchange` column remain
temporary compatibility fields because loaders, calendars, and older
repositories still consume them; this migration does not claim that the legacy
market cutover is complete. Venue trading-calendar/timezone metadata is the
next prerequisite before those consumers can be migrated safely.

### 2026-08-11 — Venue-owned daily-session calendars

Context: expected-session logic still translated the legacy `US` and `VN`
instrument market values into hardcoded timezones and close cutoffs. That
shortcut cannot distinguish venues, cannot represent continuously traded spot
markets, and would block removing `instruments.market`.

Decision: migration `0018` adds mandatory `timezone_name`,
`trading_calendar_code`, and `session_cutoff_time` metadata to every Venue.
Canonical US equity venues use `America/New_York`, `US_EQUITIES`, and 16:15;
HOSE/HNX/UPCOM use `Asia/Ho_Chi_Minh`, `VN_EQUITIES`, and 15:15; Binance Spot
uses `UTC`, `CRYPTO_24_7`, and the midnight daily-bar boundary. All venue
writers reassert this registry so synchronization cannot create an incomplete
venue.

`latest_completed_venue_session()` is the canonical venue-based calculation.
The legacy `latest_completed_session(now, market)` entrypoint now delegates to
the NYSE or HOSE schedule to preserve existing behavior during cutover. The
current equity calendars continue to exclude weekends only; exchange-holiday
support requires a versioned holiday calendar and must not be inferred from the
calendar code. A reference rate remains venue-less, so its provider-defined
observation schedule is not represented by Venue metadata.

Consequences: timezone and daily-session semantics now belong to the economic
venue instead of country/asset-class shorthand. Existing consumers can migrate
from `instrument.market` to `instrument.venue` incrementally without changing
their expected-session results. The legacy market column is still retained
until those consumers have completed that cutover.

### 2026-08-11 — Read-only canonical Venue catalog

Context: venue rows and their schedule metadata were visible only through
database inspection and instrument projections. That made the canonical venue
registry, schedule policy assignments, and current instrument relationships
hard to audit from the application.

Decision: `GET /venues` exposes a read-only PostgreSQL projection of every
Venue, including identity, type, country, timezone, calendar policy code,
session cutoff, status, source, and derived total/active instrument counts. The
Data → Venues UI reads this endpoint and supports local search and filtering;
it does not mutate venue metadata. The Data Model UI explicitly models
`trading_calendar_code` as a string column interpreted by application calendar
logic, alongside `timezone_name` and `session_cutoff_time`.

Consequences: operators can inspect the live canonical registry without SQL,
while venue synchronization remains the only writer. The UI must not imply
that `US_EQUITIES`, `VN_EQUITIES`, or `CRYPTO_24_7` are database entities or
that the current weekend-only equity policies include exchange holidays. A
future persisted holiday/calendar model would require a separate versioned
design and migration rather than silently changing the meaning of these codes.

### 2026-08-11 — Exact instrument identity for observation persistence

Context: the canonical observation tables already referenced `instrument_id`,
but several repository write contracts and refresh workers still accepted
`market + ticker` and resolved an instrument during persistence. That shortcut
is ambiguous when the same symbol exists on multiple venues and allows a
provider result to be attached to a different product than the one selected by
the operation preview.

Decision: price bars, price refresh state, fundamental reports, and provider
valuation observations are now written by exact canonical `instrument_id`.
Coverage and refresh planning are keyed by instrument ID as well. Universe,
Watchlist, exact-instrument, Binance Spot, reference-rate, canary, and
fundamental workers carry the selected ID from their PostgreSQL scope through
to persistence. Single-instrument analysis refresh also delegates by ID.

Legacy API and service entrypoints may temporarily accept `market + ticker` for
backward compatibility, but they resolve that pair exactly once at the service
boundary and continue internally with the ID. An ambiguous pair resolves to no
instrument instead of choosing an arbitrary venue. Provider selection still
uses the compatibility market field during this phase; replacing that routing
with instrument type, venue, and source metadata is the next cutover.

Consequences: equal ticker text on different venues cannot cause observation
writes to cross instruments, overlapping collections remain idempotent by
canonical identity, and per-instrument coverage is aligned with the operation
scope. No database migration is required for this phase because the stored
tables already use instrument foreign keys; the change removes identity loss
from repository contracts and worker orchestration.

### 2026-08-12 — Metadata-driven observation-source routing

Context: exact `instrument_id` persistence removed identity ambiguity, but the
refresh layer still chose a downloader from the compatibility
`instruments.market` value. Market is neither a venue nor a data source, and it
cannot represent one instrument having different identifiers at Yahoo Finance,
VNStock, Binance, or a future provider.

Decision: canonical refresh and analysis paths now load an
`InstrumentRoutingMetadata` projection and resolve an `InstrumentDataRoute`
from the instrument type, canonical Venue code and schedule, catalog source,
and current primary `instrument_symbols`. The route supplies the price adapter,
provider-specific symbol, price basis, currency, storage scale, observation
schedule, full-history boundary, and optional fundamental adapter. Current
adapter policies are US equity venues to Yahoo Finance, Vietnam equity venues
to VNStock Data, Binance Spot instruments to Binance, and venue-less Yahoo
Finance reference rates to Yahoo Finance.

The adapter registry is application code rather than a Provider table. Venue
continues to answer where a product trades; source-specific identifiers remain
rows in `instrument_symbols`; the adapter answers how the application obtains
observations. Missing or unsupported routing metadata is rejected explicitly
instead of falling back to a country-like market value. Stored observations
retain their existing source provenance.

Consequences: Data Operations, exact-instrument refresh, collection refresh,
fundamental refresh, canaries, and on-demand analysis refresh no longer select
providers from `instruments.market`. A collection must resolve to one compatible
adapter for a single refresh job, while its membership remains canonical
instrument IDs. Legacy market-data APIs and compatibility read projections may
still expose `market` until the API/UI retirement phase; they are not the
canonical routing mechanism. No database migration is required for this phase.

### 2026-08-12 — Retire legacy Market Data and remove instrument market columns

Context: metadata-driven routing and exact-instrument observation persistence
made the old `/market-data` API redundant. Its contracts still exposed
`market + ticker`, destructive market-wide clearing, and in-process job state.
The `instruments.market`, `instruments.exchange`, and
`instrument_symbols.market` columns duplicated Company country, Venue identity,
and symbol namespace without representing any independent domain entity.

Decision: remove the legacy Market Data router, schemas, storage service, UI,
and frontend route. Price History remains available through
`GET /instruments/{instrument_id}/history`; SMA and rarity analyses also select
an exact instrument ID. Data Operations is the sole update surface and resolves
Universe, Watchlist, or Instrument scopes to canonical IDs before routing.

Migration `0019` drops `instruments.market`, `instruments.exchange`, and
`instrument_symbols.market`. A venue-specific instrument is unique by
`venue_id + ticker`; a venue-less instrument is unique by ticker. Current
provider symbols are searchable by `namespace + symbol` but are not globally
unique because two venues or instruments may legitimately share provider text.
Company country remains issuer geography, Venue remains trading location, and
the adapter registry remains acquisition behavior. Catalog reads may include an
equity whose venue is unresolved, but refresh routing rejects it until a
canonical venue is assigned.

Universe and Watchlist coverage and refresh status continue to be derived from
their member instruments. No operation-run table or collection-level coverage
row is introduced. Durable history is the exact instrument observation,
coverage, refresh-state, and fundamental refresh evidence already stored in
PostgreSQL.

Consequences: `market` is no longer stored or returned as instrument identity,
equal symbol text can coexist on different venues, and UI filters use Venue or
Company country explicitly. Old `/market-data` clients receive 404 and must
migrate to `/data-operations`, `/instruments`, and exact instrument history.

### 2026-08-12 — Retire Market Health before canonical redesign

Context: the Market Health feature still modeled named Universes as hardcoded
markets, collapsed exact instrument IDs back into ticker-keyed matrices, and
reconstructed historical breadth from current membership. Retaining that
boundary while designing its replacement would preserve ambiguous identity and
survivorship-biased semantics.

Decision: remove Market Health completely before designing a replacement. The
`/market-health` API, schemas, data service, engine calculation and result types,
frontend page, navigation, charts, distribution drill-down, generated contracts,
and dedicated tests are retired. The obsolete Universe-wide price-history and
close-matrix repository paths used only by Market Health are removed as well.
Exact-instrument Price History and canonical price observations remain.

Consequences: `/market/health` and `/market-health/*` no longer exist, and the
Instruments page no longer interprets Market Health query parameters or renders
health-derived columns. No replacement analysis, persistence model, or formula
is implied by this retirement; those will require a separate reviewed design.

### 2026-08-12 — Universe Stats from canonical instrument observations

Context: after retiring Market Health, the required cross-sectional view is a
user-selected comparison of one or more canonical Universes. Restoring the old
market boundary, ticker-keyed matrices, composite health score, or hardcoded
Universe list would conflict with exact instrument identity and metadata-driven
observation routing.

Decision: add Universe Stats as an on-demand analysis over active current
Universe membership. The API resolves each chosen Universe to exact instrument
IDs and each member's canonical price basis, then reads a close-only ten-year
range plus 400 calendar days of warm-up from PostgreSQL. It does not refresh or
persist derived statistics. For every instrument, missing closes after its first
observation are carried forward while leading pre-listing values remain null.

Formula version `universe-distance-v1` uses a fixed 200-session window. For each
eligible instrument and observation date it calculates
`(close / rolling_max(close, 200) - 1) * 100` and
`(close / rolling_min(close, 200) - 1) * 100`, then takes the cross-sectional
median separately for the High 200 and Low 200 charts. A date is published only
when at least 50 percent of the current active membership has a valid 200-session
observation. The response includes eligible count and coverage percentage.

Consequences: the `/universe-stats` UI can compare any selected catalog
Universes without treating them as markets or losing venue-specific identity.
Historical lines intentionally reconstruct today's membership and therefore
retain survivorship bias; the API marks the membership mode as
`current_snapshot` and the UI states this limitation. Point-in-time constituent
statistics require effective-dated Universe membership in a future model.

### 2026-08-12 — New-Low Deep exact-instrument read cutover

Context: New-Low Deep still accepted free-form ticker text plus a user-selected
Yahoo Finance, VNStock, or CSV source and downloaded prices while running the
analysis. That path bypassed canonical instrument identity, could not distinguish
equal symbols on different venues, and allowed the selected provider to change
the price basis independently of PostgreSQL.

Decision: New-Low Deep now identifies one canonical `instrument_id` and reads
that instrument's complete canonical stored price history without refreshing a
provider. The dedicated `POST /events/new-low-deep` contract contains only the
instrument ID and analytical parameters. Its response carries instrument
identity, Venue or venue-less asset identity, currency, price source, canonical
price basis, stored range, expected latest session, row count, and stale status.
The UI uses the shared three-character instrument search across equities, crypto
spot products, and reference rates and displays storage provenance before the
analysis results.

Formula version `new-low-episodes-v1` preserves the existing engine behavior:
a strict trigger is a close below the prior configurable session-window low;
recovery is the first close at or above the pre-trigger close; qualifying quick
recoveries are discarded; and forward-return and maximum-down statistics use
the configured trading-session horizons. The migration changes input identity
and observation access, not the analytical calculation.

Consequences: New-Low Deep no longer accepts a data source, ticker, or arbitrary
date range and cannot silently fetch or mix observations while analyzing. Stale
history remains analyzable but is visibly labeled and must be refreshed through
Data Operations.

### 2026-08-12 — Legacy analysis surface retirement

Context: New-Low Comparison, the SEC Fundamentals page, and Growth Dashboard
still accepted free-form symbols and, where price observations were needed,
selected a provider directly. They bypassed exact canonical instrument identity
and canonical PostgreSQL observation reads. Their legacy contracts also kept a
second analysis path alive beside the migrated pages.

Decision: remove the three frontend routes and navigation entries and retire
`POST /events/new-low-episodes`, `POST /fundamentals/sec`,
`POST /fundamentals/growth`, and `POST /fundamentals/growth/assessment`. New-Low
Deep remains the supported new-low workflow and continues to resolve one exact
`instrument_id`. Canonical fundamental ingestion, normalized PostgreSQL storage,
Data Operations refreshes, and fundamental-derived Price History fields remain
part of the application; only the legacy analytical dashboards and their public
HTTP contracts are retired.

Consequences: no visible analysis page can submit arbitrary symbol text plus a
provider through these retired workflows. Reintroducing multi-instrument new-low
comparison or dedicated fundamental analysis requires a new contract based on
exact instrument IDs or canonical Collections and stored observations.

### 2026-08-13 — Retire symbol/provider analytical API ingress

Context: after the visible analysis pages moved to canonical Instrument,
Watchlist, and Universe identity, five unused public endpoints still accepted
arbitrary `symbol` or `symbols` values plus a caller-selected `data_source`.
They fetched provider data directly during the analytical request and therefore
preserved a second identity and observation path outside canonical PostgreSQL.

Decision: retire `POST /backtest`, `POST /sweep`, `POST /factors/analyze`,
`POST /factors/universe`, and `POST /factors/regime`, together with their request
and response schemas. Remove the FastAPI `fetch_prices` and provider-loader
selection helpers that existed only for those contracts. Keep portfolio,
comparison, factor, regime, and CSV-loader capabilities inside the standalone
`trading_engine` library; retiring an application endpoint does not narrow the
library API. The supported application analysis contracts are now exact
Instrument, Watchlist, or Universe workflows.

Consequences: no registered analysis endpoint accepts provider choice or a
free-form symbol as identity. `POST /backtest/analyze`, Factor Rarity,
Predefined Rarity, Universe Stats, and New-Low Deep remain available. A contract
test enumerates both the retired paths and the canonical request schemas so the
legacy ingress cannot be accidentally restored. Making every remaining analysis
read stored observations without an implicit refresh is a separate subsequent
cutover.

### 2026-08-13 — Stored-only analytical reads

Context: the canonical analysis contracts used exact `instrument_id` values,
but Backtest, Factor Rarity, and Instrument Price History shared an analysis
service method that could download and persist newer equity observations while
serving the read. This made a read request mutate PostgreSQL, treated equities
differently from crypto and reference rates, and obscured whether an analytical
result used the data visible before the request.

Decision: all analysis and price-history reads now load only canonical
PostgreSQL `price_bars` for the instrument's canonical price basis. They compute
the latest expected session from the instrument's Venue or observation schedule
and return freshness metadata without contacting a provider. Stale data remains
analyzable and is clearly labeled in the UI. Provider adapters are instantiated
only by explicit Data Operations jobs and their refresh scripts; downloaded
equity frames are persisted by exact `instrument_id` through the price-write
service.

Consequences: GET and analytical POST requests are deterministic with respect to
the stored observation snapshot and have no price-refresh side effects. Users
must run Data Operations to update stale or missing histories. The response
fields `refreshed` and `refresh_warning` are removed because an analysis can no
longer refresh; `expected_last_session`, `data_last_session`, `is_stale`, source,
and price basis describe the stored input instead. Instrument Price History now
exposes the same expected-session and stale status.

### 2026-08-13 — Precise Company, Instrument, and Universe catalogs

Context: the issuer catalog was exposed at `GET /companies/catalog`, while the
root `GET /companies` path still returned one row per equity Instrument. A
second `GET /companies/universes` compatibility projection manufactured
`US_ALL` and `VN_ALL` identities that were not persisted Universes. This kept
Company and Instrument terminology inverted even after both frontend pages and
the relational model distinguished them.

Decision: `GET /companies` is now the canonical issuer catalog and returns one
Company with nested identifiers and Instruments. `GET /instruments` is the
canonical Instrument catalog and returns issuer classification, Venue, price
coverage, and actual persisted Universe memberships with server-side search,
filters, facets, and 50-row pagination in the UI. `GET /universes` remains the
only Universe catalog. The Instruments UI obtains its Universe controls from
that endpoint, filters the catalog by exact Universe code, and represents all
active equities by omitting the Universe filter. Remove
`GET /companies/catalog`, `GET /companies/universes`, the old Company-list
schemas and service/repository projection, and the synthetic `US_ALL` and
`VN_ALL` values.

Consequences: each catalog URL now names the entity it returns. Alphabet appears
once in Companies while GOOG and GOOGL remain separate Instruments. Universe
controls are metadata-driven and can include any persisted equity Universe
without a frontend code list. “All equities” is a query scope, not a synthetic
membership set, and no database migration is required for this API cutover.

### 2026-08-13 — Live audited Universe synchronization

Context: canonical Company, Asset, Instrument, Symbol, Venue, and Universe
tables existed, and live provider adapters could produce normalized snapshots,
but a clean database still depended on `scripts.import_companies` and the
checked-in symbol-list files. There was no transactional live writer or durable
record of successful and failed membership synchronization attempts.

Decision: `scripts.sync_company_universes` is the supported equity-Universe
bootstrap and maintenance command. It fetches provider data and the Nasdaq
Trader venue directory before opening a write transaction, normalizes and
validates the complete snapshots in memory, and then acquires PostgreSQL
advisory transaction locks. United States Universes lock independently; VN30,
VNMID, VN100, VNSML, and VNALL share one family lock and are always replaced in
one transaction. VN100 must equal VN30 union VNMID, and VNALL must equal VN100
union VNSML.

The writer resolves Instruments from canonical Venue plus a current canonical,
listing, or provider Symbol. It uses stable Company identifiers such as SEC CIK
or VNStock organization code before existing Instrument ownership and never
merges Companies from normalized names alone. Known Companies, equity Assets,
and Instruments are reused; missing canonical rows are created. During the
remaining compatibility period, every write updates both `instruments.ticker`
and current `instrument_symbols` rows. Provider metadata only replaces a value
when it is non-null, and share-class labels do not replace a neutral issuer
name.

Membership replacement, Universe provenance, active-state recalculation, and
one scalar `universe_sync_runs` audit row per Universe commit atomically. The
audit table deliberately has no JSON payload. Empty, malformed, cross-market,
implausibly sized, or unexpectedly high-change snapshots are rejected; the
change threshold can only be bypassed with the explicit `--force` control.
Fetch or validation failure records a failed audit attempt in a separate
transaction and leaves the last known-good membership untouched. Removing
membership never deletes prices, fundamentals, refresh state, or Watchlist
membership. `--dry-run` reports additions, removals, unchanged members, and
metadata changes without writing any application or audit row.

Consequences: `alembic upgrade head` followed by
`python -m scripts.sync_company_universes --all` can populate a clean database
without the legacy importer and without persisting a downloaded JSON, CSV, or
provider response. Provider availability is an operational synchronization
dependency, not an API-startup dependency; synchronization is never run during
application startup. Phase 7 subsequently removed the checked-in symbol-list
files and old importer after every consumer had been cut over.

### 2026-08-13 — Metadata-driven Data Operations execution

Context: Data Operations previewed exact Instrument metadata but execution
still branched by a fixed list of Universe codes. Universe, Watchlist, and
single-Instrument updates delegated to three registries and three workers;
Watchlists had to contain equities from one adapter, Watchlist and exact-
Instrument fundamentals were disabled, and adding a Universe required code.

Decision: one Data Operations planner resolves the selected Universe,
Watchlist, or Instrument into exact active Instrument IDs, derives dataset
capability from each Instrument's Venue, type, Symbol namespace, and source
metadata, and groups eligible Instruments by adapter. One transient job runner
executes those groups and every persistence write remains keyed by exact
`instrument_id`. Universe code and display name have no routing meaning. Mixed
Watchlists can therefore update supported price and fundamental subsets, and a
new persisted Universe requires no worker change. Adapter limits are explicit
operational policy; the Binance Spot price limit defaults to 100 and can be
configured with `DATA_OPERATION_PRICES_BINANCE_SPOT_MAX_INSTRUMENTS`.

The legacy Watchlist refresh endpoints, Watchlist and Universe job registries,
fixed supported-Universe constants, and market-named fundamental/history
workers are retired. `/data-operations/jobs` is the only HTTP launch surface.
Jobs remain process-local progress state and are not durable business history.
Canonical `price_bar_coverages`, `price_refresh_states`, observation provenance,
and fundamental fetch timestamps are the durable per-Instrument operational
state. A failed price acquisition records a failed attempt without erasing
stored bars; a successful check records its attempted and returned sessions.

Consequences: renaming a Universe cannot alter adapter selection, same-symbol
Instruments on different Venues remain independent IDs, and collection coverage
is always derived from member state. The Watchlists page manages membership
only; updates are launched centrally through Data Operations. Fundamentals no
longer create Universe-scoped refresh-run rows when launched through the new
executor, because no persistent Data Operation run-history model is desired.

### 2026-08-13 — Canonical PostgreSQL market-index benchmarks

Context: Price History calculated relative strength from SPX or VN30, but those
two histories were the final analytical observations stored in local CSV files
with JSON manifests. The Universe price command refreshed those files as a side
effect, while normal Data Operations did not. This split provenance, coverage,
and recovery behavior from every other canonical daily series.

Decision: migration `0021` registers SPX and VN30 as venue-less
`market_index` Instruments with provider symbols `^GSPC` and `VN30`. Their
daily levels use canonical `price_bars` with `price_basis = index_level`, normal
coverage and refresh-state rows, and exact Instrument IDs. SPX carries the US
equity observation schedule and VN30 the Vietnam equity schedule without
inventing an execution Venue. Price History reads both from PostgreSQL and
never refreshes during the request.

The one-time `scripts.migrate_legacy_benchmark_cache` command validates cache
identity, row counts, dates, and source metadata before importing the existing
rows and can delete the four source files only after both series commit and
verify. Future acquisition uses `scripts.sync_market_indices` or an exact-
Instrument Data Operation. The Universe price command no longer has a hidden
benchmark side effect, and the runtime cache reader/writer is removed.

Consequences: benchmark observations now share the same identity, provenance,
freshness, and PostgreSQL backup model as equity, crypto, and reference-rate
prices. SPX and VN30 can be refreshed independently, provider failure retains
stored levels, and relative-strength reads are deterministic with respect to
the database snapshot.

### 2026-08-13 — Remove static company and Universe snapshots

Context: live audited Universe synchronization, PostgreSQL-only membership
reads, and exact-Instrument observation workflows had replaced every runtime
use of the checked-in company-list JSON and CSV snapshots. Keeping the old
importer and snapshot-count tests left a second, stale bootstrap path that could
reconstruct different membership and metadata from the supported live sources.

Decision: remove `api/data/symbol_lists`, its JSON/CSV reader, the static
company importer, and its command. A clean database is populated only by
Alembic followed by `scripts.sync_company_universes --all`. Tests use compact
relational fixtures for catalog behavior and mocked provider snapshots for
synchronization behavior; the normal suite never fetches live constituent
data. Provider payloads are validated in memory and are not persisted as
application JSON or CSV artifacts.

Consequences: PostgreSQL is the sole company and Universe business-data store,
and external sources are replaceable synchronization inputs. Recovery uses
database backups and a new validated synchronization rather than checked-in
membership snapshots. Current Universe membership remains a current snapshot
and therefore carries survivorship bias until a separately designed,
effective-dated membership-history source and schema are introduced.
