# Trading Activity Analytics v1 Design

## Goal

Turn stored Vietnam daily trading activity into a provider-neutral liquidity
signal without making any new Vnstock request.

## Formula contract

The formula identifier is `turnover_intensity_v1`.

- `turnover_intensity[t] = total_value[t] / market_cap[t]`.
- The baseline is the arithmetic mean of the 20 stored session observations
  immediately preceding `t`; the current session is never included.
- The anomaly score is `(turnover_intensity[t] - baseline[t]) /
  population_standard_deviation(prior_20_intensities)`.
- The first possible anomaly is therefore the 21st stored session.
- A non-positive or non-finite market capitalization makes the current
  intensity unavailable. Invalid total value is also unavailable.
- Fewer than 20 prior stored sessions, an invalid observation within that
  prior window, or zero prior-window variance makes the anomaly unavailable
  with a machine-readable reason. A valid current intensity remains visible
  even when its anomaly is unavailable.
- Stored-session windows do not claim exchange-calendar completeness.

## Boundaries

- The calculation belongs in `trading_engine`, with its shared dataclasses in
  `trading_engine/types.py`; FastAPI only maps stored records into and out of
  that calculation.
- The existing PostgreSQL activity rows remain canonical. There is no schema
  migration and no persisted derived value.
- A requested range may use at most 20 earlier stored rows as calculation
  context. Context rows are not returned as requested activity rows.
- The existing unsupported-Instrument and missing-storage errors remain
  explicit. The UI additionally renders per-session analytical unavailability
  instead of silently substituting zero.
- A factor or strategy representation must shift the intensity by one observed
  session. Same-session use is not exposed.

## UI

The Trading Activity page adds an analytics section beside the existing stored
activity presentation. It shows the latest available intensity and anomaly,
an intensity/baseline chart, an anomaly chart, and readable unavailable states.
The original raw activity charts, table, provenance, and Data Operations link
remain intact.

