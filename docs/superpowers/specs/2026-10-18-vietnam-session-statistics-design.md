# Vietnam Session Statistics Design

## Objective

Add Vnstock Gen 5 `session_stats` as a standalone, database-backed view for
one eligible Vietnam equity and one requested period. The feature presents
provider aggregates without treating them as daily observations, factors,
signals, strategies, or recommendations.

The UI reads stored snapshots only. Provider access remains an explicit user
operation and never occurs merely because the page opens, the Instrument
changes, or the date range changes.

## Confirmed Provider Semantics

For VCI, `Market().equity(symbol).session_stats(start=..., end=...,
source="vci")` returns one row with 65 columns: `symbol` plus 64 numeric
metrics. The row summarizes the entire requested period. A two-session request
returns totals across both sessions and period averages; it does not return one
row per session.

The adapter therefore records the exact requested start and end dates as part
of snapshot identity and provenance. It must not manufacture a trading date or
write this response into participant-flow observations.

## Capability and Eligibility

Add `session_stats` to `InstrumentCapability` only when its complete provider,
storage, API, Data Operations, and UI paths ship. Eligibility matches the
implemented VCI participant-flow policy:

- `instrument_type == "common_stock"`;
- a canonical Company identity exists;
- Venue is `HOSE`, `HNX`, or `UPCOM`;
- the resolved provider adapter is `vnstock`;
- a canonical provider symbol is available.

`GET /instruments?capability=session_stats` performs this filtering before
counting and pagination. Direct unsupported requests return an explicit
capability error.

## Metric Contract and Groups

The normalizer requires all 65 currently observed fields and rejects missing,
duplicate, non-numeric, non-finite, or unexpected rows. It preserves
provider-reported values instead of recalculating totals, nets, or averages.
All numeric values use fixed-point persistence.

The 64 metrics are presented in four stable domain groups while retaining the
provider field name as the metric code:

1. **Market activity**
   - matched, negotiated-deal, and total volume/value;
   - corresponding period averages.
2. **Foreign activity**
   - total, matched, and negotiated-deal buy/sell/net volume and value;
   - corresponding period averages.
3. **Trade direction**
   - total buy/sell/net trade volume;
   - buy/sell trade counts;
   - corresponding period averages.
4. **Order imbalance and trade size**
   - unmatched buy/sell volume and averages;
   - average buy and sell volume per trade.

Group, label, unit (`volume`, `value`, or `count`), and display order are
application metadata keyed by a closed metric-code literal. React does not
infer metric meaning from string prefixes.

## Canonical Persistence

Add two application tables:

- `instrument_session_stat_snapshots`: exact Instrument ID, requested start
  and end dates, source, schema version, and timezone-aware fetch timestamp;
- `instrument_session_stat_metrics`: snapshot ID, metric code, and
  `Numeric(38, 6)` value.

Each successful fetch creates an immutable snapshot. The unique snapshot key
includes Instrument, requested period, source, and fetch timestamp. Metric
identity is `(snapshot_id, metric_code)`. Snapshot creation and all 64 metric
inserts occur in one transaction; a malformed or incomplete response stores
nothing. Deleting an Instrument cascades to its snapshots and metrics.

Retaining snapshots makes upstream revisions observable. The read API returns
the latest successfully fetched snapshot for the exact requested period. Data
Operation history remains the operational audit and is not duplicated in the
snapshot payload.

## Explicit Refresh Workflow

Add `session_stats` as an exact-Instrument Data Operations dataset. Unlike
daily-series datasets, it requires `period_start` and `period_end`; both are
validated dates and `period_start <= period_end`.

The single-operation request, persisted run, job command, and CLI receive the
requested period explicitly. Existing dataset contracts remain unchanged and
do not acquire implicit date-range defaults. Batch
Operations do not expose `session_stats` in this first slice because the
period is an interactive exact-Instrument input and provider request volume has
not yet been measured.

The operation resolves capability before reserving the shared `vnstock`
adapter lease. It performs one VCI request, validates the complete response,
and commits one immutable snapshot. A provider or validation failure retains
all earlier snapshots.

The Session Statistics page links to a prefilled single Data Operation carrying
the Instrument and selected period. Data Operations displays the period fields
only for `session_stats` and starts no work until the user explicitly submits.

## Read API

Add:

```http
GET /instruments/{instrument_id}/session-statistics
    ?start=YYYY-MM-DD
    &end=YYYY-MM-DD
```

Both dates are required and identify one exact requested period. The response
contains Instrument identity, requested period, source, schema version, fetch
time, and the 64 metrics with code, group, label, unit, order, and numeric
value. It returns the newest stored snapshot for that exact period and performs
no provider access.

Unknown Instruments return `404`; capability-ineligible Instruments, invalid
ranges, and eligible periods without a stored snapshot return specific `422`
responses. The Pydantic and generated TypeScript contracts change together.

## User Interface

Add `Vietnam Market > Session Statistics` as a separate route. The page has:

- a `session_stats`-capability-filtered Instrument selector;
- required start and end dates for one period;
- an explicit Apply action that reads the matching stored snapshot;
- summary cards for total volume/value, matched/deal shares, foreign net
  value, net trade volume, and average trade sizes;
- four grouped metric tables containing all provider fields;
- source, requested period, schema version, and fetch-time provenance;
- distinct no-selection, no-snapshot, unsupported, loading, and API-error
  states;
- a link to prefill the exact Instrument and period in Data Operations when no
  snapshot exists.

The first version does not compare periods, chart a false time series, derive
signals, or silently substitute another Instrument or date range.

## Boundaries and Error Handling

Provider selection, refresh orchestration, persistence, and presentation
metadata remain in `api/`. No Vnstock or FastAPI dependency enters
`trading_engine`. If reusable analytics are later derived from session
statistics, they receive provider-neutral inputs through a separate engine
boundary.

Existing snapshots remain readable after failed refreshes. Unexpected provider
columns are rejected deliberately so an upstream schema change cannot be
silently mislabelled in the UI. Adding a supported provider metric requires a
schema-version and metric-catalog change with tests.

## Testing and Verification

Backend tests cover:

- explicit VCI provider arguments and the one-row 65-column contract;
- all four metric groups, units, ordering, and strict malformed-data failures;
- capability derivation and pre-pagination Instrument filtering;
- immutable snapshots, fixed-point values, exact-period lookup, latest-fetch
  selection, transactional rollback, and cascade behavior;
- required Data Operation period parameters, exact-Instrument restriction,
  persisted period propagation, shared Vnstock lease, and retained snapshots
  after failures;
- API ordering, serialization, `404`/`422` behavior, and absence of provider
  calls on reads;
- Alembic upgrade and downgrade constraints.

Frontend verification covers the generated API contract, capability-filtered
search, exact-period requests, grouped rendering, provenance, empty/error
states, and Data Operations prefill. Required gates are full `pytest`,
`pnpm lint`, `pnpm type-check`, `pnpm build`, API-contract drift checking, and
`git diff --check`.

## Rollback

Rollback removes the Session Statistics route, API, provider method, Data
Operations dataset, and the two session-statistics tables. Participant-flow,
price, fundamental, Instrument, and unrelated operation data remain intact.
