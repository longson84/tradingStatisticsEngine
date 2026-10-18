# Vietnam Equity Flow Design

## Objective

Add Vnstock Gen 5 market-flow data to Trading Statistics Engine without
implying that every canonical Instrument has the same provider capabilities.
The first independently usable slice is historical foreign-investor flow for
Vietnamese common stocks. The design deliberately leaves a typed extension
path for proprietary flow, session statistics, and current-session volume
profiles.

The application remains library-first and database-backed: opening an analysis
page reads canonical PostgreSQL observations and never performs an implicit
provider request.

## Scope

The first slice includes:

- an explicit `foreign_flow` capability for eligible Vietnam equities;
- a typed Vnstock Gen 5 `Market().equity(symbol).foreign_flow(...)` adapter;
- normalized, point-in-time PostgreSQL persistence by exact Instrument ID;
- exact-instrument foreign-flow refresh through Data Operations;
- a stored foreign-flow API contract;
- a Vietnam Market > Investor Flow UI with a capability-filtered selector;
- provider, repository, service, API, and frontend tests;
- an architecture decision recording the new observation boundary.

The first slice does not implement proprietary flow, session statistics,
volume profile, inferred signals, recommendations, or cross-market
substitutes. It also does not claim support merely because an Instrument uses
VND.

## Product and Navigation Model

Add a `Vietnam Market` navigation section. Its first route is `Investor Flow`.
The page has a dedicated Instrument selector containing only active Vietnamese
common stocks that support the requested capability. It does not expose the
global Equity, Crypto Spot, Reference Rate, or Market Index scope picker.

The completed feature family will be divided as follows:

- **Investor Flow** contains Foreign and Proprietary tabs because both are
  historical daily series with the same six measures.
- **Session Statistics** is a separate page because Vnstock returns one broad
  aggregate record for a requested period rather than a normal daily series.
- **Volume Profile** is a separate current-session page because it is a
  timestamped price-level snapshot obtained from KBS, not historical VCI data.

In the first slice, Investor Flow contains only Foreign flow. The page shows:

- the selected Instrument, Venue, VCI source, stored coverage, and fetch time;
- a date-range control;
- net traded value as the primary signed chart;
- buy and sell values as supporting series;
- volume and value summary cards;
- a daily observations table;
- an empty state that directs the user to update foreign-flow data when no
  stored observations exist;
- a stale-data notice when the final stored date precedes the latest completed
  Venue session.

## Capability and Eligibility Model

Introduce an application-level `InstrumentCapability` literal. The first slice
contains only `foreign_flow`; these additional values are added with their
respective implementations rather than advertised prematurely:

- `proprietary_flow`
- `session_stats`
- `volume_profile`

Capabilities are derived from canonical Instrument routing metadata. The
`foreign_flow` capability is available in the first slice; later slices apply
the same eligibility policy only after their provider, storage, API, and UI
paths exist. Capabilities are not persisted as mutable Instrument flags and
are not inferred in React.
Each implemented capability applies only when all of these conditions hold:

- `instrument_type == "common_stock"`;
- the Instrument has a Company identity;
- the Venue is one of `HOSE`, `HNX`, or `UPCOM`;
- the resolved provider route is the active `vnstock` route;
- the provider symbol can be resolved from canonical routing metadata.

`GET /instruments` gains an optional `capability` filter. Its result rows,
total, and facets must all reflect the eligible set; post-pagination filtering
is not acceptable. The backend remains authoritative. A direct request for an
unsupported Instrument returns a clear capability-unavailable response even
if a client bypasses discovery.

## Provider Boundary and Normalization

Extend the typed Vietnam market provider with:

```python
foreign_flow(symbol, start, end) -> VietnamProviderResult
```

The Gen 5 adapter calls:

```python
Market().equity(symbol).foreign_flow(
    start=start.isoformat(),
    end=end.isoformat(),
    source="vci",
)
```

The normalizer requires exactly the semantic fields represented by the Gen 5
response:

- `time`
- `buy_vol`, `buy_val`
- `sell_vol`, `sell_val`
- `net_vol`, `net_val`

It converts `time` to a Vietnam trading date, converts numeric values without
inventing missing values, sorts ascending, and keeps the final duplicate for a
date. Buy and sell values must be non-negative. Net values remain signed and
are stored as provider-reported observations; the application does not replace
them with calculated differences. Empty or malformed provider results fail
explicitly and retain the original exception as their cause at the adapter
boundary.

Provenance uses the existing stable package/version/upstream label, such as
`vnstock-5.1.0-vci`, plus a timezone-aware application fetch timestamp.

## Canonical Persistence

Migration `0032` adds `instrument_flow_observations` and
`instrument_flow_coverages`.

`instrument_flow_observations` stores:

- exact `instrument_id` foreign key;
- `trading_date`;
- `participant_type`, constrained initially to `foreign` and `proprietary`;
- fixed-point `buy_volume`, `buy_value`, `sell_volume`, `sell_value`,
  `net_volume`, and `net_value`;
- `currency`;
- `source`;
- timezone-aware `fetched_at`;
- normal created/updated audit timestamps.

The canonical unique key is:

```text
(instrument_id, trading_date, participant_type)
```

Source is provenance, not part of identity. Refreshing the same canonical
observation replaces its values and source metadata atomically. Buy and sell
columns have non-negative constraints; net columns are signed. Fixed-point
columns avoid binary rounding for large VND values and retain any
fractional quantities returned by a future compatible source.

`instrument_flow_coverages` stores one row per Instrument and participant type:

- first and last stored date;
- row count;
- latest source and fetch time.

Observation upserts and coverage recomputation occur in the same database
transaction. Deleting an Instrument cascades to both tables. The generic
`DataOperationRun` remains the operational audit; the flow tables do not
duplicate job logs.

## Refresh Workflow

Extend the Data Operations dataset union and database constraint with
`foreign_flow`. In this first slice, foreign-flow refresh supports exact
Instrument scope. Collection-wide refresh can be added after request volume
and provider behavior have been measured; the API must reject unsupported
scope/dataset combinations rather than enqueueing a partial surprise.

The Data Operation planner resolves the Instrument route and capability before
starting a job. An incremental refresh starts with a small overlap of the most
recent stored sessions so upstream corrections can replace canonical rows. A
full refresh requests the provider-supported history boundary through the
latest completed Venue session. Both modes upsert idempotently by the canonical
key.

Foreign-flow work uses the same `vnstock` adapter lease and rate budget as
other Vnstock operations so price, fundamental, and flow jobs cannot
independently oversubscribe the account. Provider failures do not delete or
truncate previously stored observations.

## Read API

Add:

```http
GET /instruments/{instrument_id}/market-flows
    ?participant_type=foreign
    &start=YYYY-MM-DD
    &end=YYYY-MM-DD
```

The response contains:

- Instrument ID, symbol, type, Venue, and currency;
- participant type;
- first/last stored dates, expected latest session, stale status, and row
  count;
- source and fetch timestamp;
- ordered observations containing date and the six flow measures.

The endpoint performs no provider access. Unknown Instruments return `404`.
Known but capability-ineligible Instruments return `422`. Eligible Instruments
without stored observations also return a specific `422`, consistent with the
existing stored-history behavior. Invalid ranges return `422` through request
validation.

The Pydantic contract and generated TypeScript contract are updated together.

## Engine and Application Boundaries

Provider selection, Instrument capability resolution, refresh orchestration,
and persistence remain in `api/`. The initial page is a presentation of stored
market observations and does not introduce a reusable analytical formula, so
no Vnstock import or FastAPI dependency enters `trading_engine`.

If flow-derived factors or strategies are introduced later, their provider-
neutral inputs and calculations will be modeled in `trading_engine` separately
from this acquisition feature. Foreign flow itself is data, not a factor,
signal, strategy, or recommendation.

## Error Handling and User Feedback

The UI distinguishes:

- no Instrument selected;
- no eligible search result;
- eligible Instrument with no stored flow data;
- stale stored data;
- API failure;
- an active or failed Data Operation.

An unsupported Instrument is never silently substituted with another symbol or
Venue. Existing stored observations remain visible when a refresh fails, with
the failed operation reported separately.

## Testing

Backend coverage includes:

- capability derivation for VN common stocks and rejection of US equities,
  indices, crypto, reference rates, missing Companies, and unsupported Venues;
- capability-filtered Instrument totals and pagination;
- provider call arguments, normalized column mapping, timezone-to-date
  handling, malformed/empty frames, and provenance;
- exact-Instrument write protection, idempotent upsert, overlap correction,
  constraints, coverage recomputation, and transaction rollback;
- Data Operation eligibility, unsupported scopes, job persistence, adapter
  lease behavior, incremental/full ranges, and retained data after failures;
- API ordering, decimal serialization, date filtering, stale calculation, and
  `404`/`422` responses;
- Alembic upgrade and downgrade behavior.

Frontend coverage and verification include:

- only `foreign_flow`-capable Instruments appear in search;
- loading, empty, stale, error, and populated states;
- signed net-value presentation and source/fetch metadata;
- `pnpm lint`, `pnpm type-check`, and `pnpm build`.

The full Python suite must continue to prove that `trading_engine` imports no
application framework or Vnstock runtime.

## Extension Sequence

1. **Foreign flow:** implement the complete slice described here.
2. **Proprietary flow:** add the provider method, enable the existing
   `proprietary` participant type, expose the second Investor Flow tab, and
   reuse the same persistence and read API.
3. **Session statistics:** introduce a separate aggregate model and page after
   classifying the 65 returned fields into stable domain groups. Do not force
   the aggregate response into daily flow observations.
4. **Volume profile:** expose a separately timestamped current-session snapshot
   from KBS. Do not imply historical coverage unless an actual historical
   persistence policy is designed later.

## Documentation and Rollback

Update `docs/ARCHITECTURE.md` in the implementation commit with the capability
policy, canonical flow identity, provider/read separation, and exact-Instrument
persistence decision.

Rollback removes the UI/API/provider path and downgrades migration `0032`.
Existing price, fundamental, Instrument, and operation data is unaffected.
