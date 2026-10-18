# Vietnam Daily Trading Activity Design

## Objective

Add Vnstock Gen 5 `trade_history` as a stored daily trading-activity dataset
for eligible Vietnam equities. Preserve the existing provider-neutral OHLCV
model, expose the new activity fields through a database-only API, and present
them on a standalone Trading Activity page for one Instrument and one selected
date range.

The first slice stores and presents provider-reported activity. It does not
turn the new fields into trading recommendations, strategies, or portfolio
weights.

## Confirmed Provider Contract

The installed Vnstock 5.1.0 runtime exposes:

```python
Market().equity(symbol).trade_history(
    start="YYYY-MM-DD",
    end="YYYY-MM-DD",
    resolution="1D",
    source="vci",
)
```

VCI returns one row per trading session with 39 fields. The response combines
four different concerns:

- session identity and company scale;
- ordinary and adjusted daily price fields;
- matched, negotiated-deal, and total volume/value;
- provider-classified buy, sell, net, unmatched, and average trade-size data.

The provider boundary requires the exact supported schema, unique session
dates, finite numeric values, ordered requested-range membership, non-negative
gross volume/value/count fields, and consistent arithmetic where VCI defines a
direct total. It accepts signed price changes and net trade volume. A malformed
row causes the whole fetch to fail before persistence.

`price_change_value` is a formatted provider display string and
`end_trading_date` duplicates session identity. They are validated but not
persisted as analytical values.

## Domain and Storage Boundary

Keep `price_bars` unchanged. It remains the canonical provider-neutral OHLCV
store keyed by Instrument, trading date, and price basis and continues to feed
`PriceFrame`, factors, strategies, portfolios, and performance analysis.

Add one primary application table:

```text
instrument_daily_trade_statistics
```

Its identity is `(instrument_id, trading_date)`. A later successful refresh
may replace the canonical row only when its `fetched_at` is not older than the
stored row. The row records:

- `instrument_id`, `trading_date`, `source`, `schema_version`, `fetched_at`;
- `market_cap`, `total_shares`;
- `matched_volume`, `matched_value`, `deal_volume`, `deal_value`;
- `total_volume`, `total_value`;
- `total_buy_trade`, `total_buy_trade_volume`;
- `total_sell_trade`, `total_sell_trade_volume`;
- `total_net_trade_volume`;
- `total_buy_unmatched_volume`, `total_sell_unmatched_volume`;
- `average_buy_trade_volume`, `average_sell_trade_volume`.

Monetary values, volumes, counts, and averages use fixed-point database types
wide enough to preserve provider values. Gross values and counts are
non-negative; net trade volume may be signed. Deleting an Instrument cascades
to its daily activity rows.

The normalizer validates the duplicated raw and adjusted price fields but does
not copy them into the activity table. Ordinary OHLCV remains authoritative in
`price_bars`. Adjusted VCI price history is a separate future decision and may
only enter `price_bars` under an explicit confirmed `price_basis`.

The first slice does not add a coverage table. Exact-range reads and refreshes
query the primary table directly; `DataOperationRun` remains the operational
audit. A coverage projection can be added later if measured batch or catalog
queries justify it.

## Capability and Eligibility

Add `trade_history` to `InstrumentCapability` only when provider, persistence,
API, Data Operations, and UI paths ship together. Eligibility requires:

- an active Company-backed `common_stock` Instrument;
- Venue `HOSE`, `HNX`, or `UPCOM`;
- the resolved `vnstock` adapter;
- a canonical VCI provider symbol.

`GET /instruments?capability=trade_history` filters before totals and
pagination. Direct requests for unsupported Instruments return an explicit
capability error rather than an empty successful response.

## Refresh Workflow

Add `trade_history` to single Data Operations only. The first slice requires:

- exact Instrument scope;
- explicit `period_start` and `period_end`;
- `period_start <= period_end`;
- `mode="full"`, meaning replace/upsert the requested range from one complete
  provider response, not rebuild all available history.

Batch Operations do not expose `trade_history` initially. This limits request
volume until range sizes and provider cost are measured.

The operation resolves capability before acquiring the shared Vnstock adapter
lease, performs one VCI request, validates every returned row, and writes all
rows in one transaction. Provider or validation failure preserves all
previously stored rows. The refresh result reports the requested period, the
returned first and last sessions, and the stored row count.

The operation uses the same durable period fields already introduced for
session statistics. Request validation changes from “dates only for
`session_stats`” to “dates only for exact-period datasets,” with both
`session_stats` and `trade_history` requiring them.

## Read API

Add:

```http
GET /instruments/{instrument_id}/trade-statistics
    ?start=YYYY-MM-DD
    &end=YYYY-MM-DD
```

The route reads PostgreSQL only. It returns Instrument identity, requested
range, stored coverage within that range, row provenance, and daily activity
rows ordered ascending by trading date.

Unknown Instruments return `404`. Unsupported Instruments and reversed ranges
return `422`. An eligible range with no stored rows returns a specific `422`
that the UI can distinguish from other API failures. Partial stored coverage
is returned honestly with its actual first/last stored dates; the API does not
manufacture missing sessions or call Vnstock to fill them.

Pydantic response schemas and generated TypeScript contracts change together.

## User Interface

Add `Vietnam Market > Trading Activity` as a standalone route. It contains:

- a `trade_history`-capability-filtered Instrument selector;
- required start/end date inputs and an explicit Apply action;
- stored-range and source/fetch-time provenance;
- summary cards for total value, total volume, matched share, negotiated-deal
  share, latest market capitalization, and latest net trade volume;
- a stacked daily chart for matched and negotiated-deal volume;
- a daily net-trade-volume chart;
- a daily table containing the stored activity fields;
- distinct no-selection, loading, no-data, partial-coverage, unsupported, and
  API-error states;
- a safe link that prefills the exact Instrument and requested period in
  single Data Operations.

Opening the page, changing the Instrument, or changing dates never calls
Vnstock. Apply reads stored data only. The Data Operations submission remains
the sole explicit provider-access action.

Matched/deal shares shown in summary cards are presentation ratios calculated
from stored provider totals. The UI must label buy/sell/net fields as VCI trade
classifications; it must not describe them as foreign flow, proprietary flow,
capital inflow, or investment recommendations.

## Analytical Extension Path

This slice does not add trading factors. A later provider-neutral engine change
may accept daily trade-statistics inputs and derive versioned measures such as:

- turnover value divided by market capitalization;
- volume divided by shares outstanding;
- negotiated-deal share;
- net-trade imbalance;
- average trade-size imbalance;
- rolling liquidity or activity anomalies.

Those formulas belong in `trading_engine`, not FastAPI routes or React. Any
strategy using end-of-session activity must lag the values to the next
tradable session or declare an independently justified execution convention.
Same-close use is prohibited by default and must be covered by look-ahead
diagnostics and tests.

## Error Handling and Provenance

The adapter catches typed Vnstock errors and preserves their safe code/action
context without exposing credentials. Empty provider responses, duplicate
sessions, schema drift, invalid dates, non-finite values, and invalid gross
values fail the refresh atomically.

Every stored row records a stable source label such as
`vnstock-5.1.0-vci` and a timezone-aware fetch time. The UI identifies the
provider source and never implies that Vnstock itself owns or improves the
third-party data.

## Testing and Verification

Backend tests cover:

- exact VCI arguments and the complete 39-field response contract;
- strict malformed-schema, duplicate-session, invalid-range, non-finite, and
  signed-versus-gross validation;
- capability derivation and pre-pagination filtering;
- fixed-point persistence, canonical upsert ordering, transaction rollback,
  date-range isolation, and Instrument cascade behavior;
- exact-Instrument Data Operations validation, durable period propagation,
  shared Vnstock lease use, and Batch Operations exclusion;
- database-only API behavior, ordered serialization, partial coverage, and
  `404`/`422` responses;
- migration upgrade and downgrade isolation.

Frontend verification covers generated API contracts, capability-filtered
selection, explicit stored reads, charts/tables, provenance, partial/no-data
states, and safe Data Operations prefill.

Required gates are full `pytest`, `pnpm lint`, `pnpm type-check`, `pnpm build`,
API-contract drift checking, migration upgrade/downgrade tests, and
`git diff --check`.

## Rollback

Rollback removes the Trading Activity route, API, capability, provider
normalizer, Data Operations dataset, and daily statistics table. It leaves
canonical OHLCV, participant flows, session-statistics snapshots,
fundamentals, Instruments, and unrelated Data Operation history intact.
