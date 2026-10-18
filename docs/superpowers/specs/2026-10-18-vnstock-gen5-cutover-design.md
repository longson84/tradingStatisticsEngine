# Vnstock Gen 5 Cutover Design

## Objective

Replace the application's Vnstock generation 4 integration with the current
Vnstock generation 5 stack. The completed application must have one active
Vietnam data provider, no generation 4 runtime packages or setup workflow,
and no ambiguous `vnstock_data` routing tokens.

The cutover uses the official `vnstock` 5.1 release line for market and
reference data and the official `vnstock_quant` add-on for financial ratios.
The dependency lock records the exact resolved versions.

## Scope

The migration covers:

- Python dependency resolution and authenticated Vnstock package index setup.
- Vietnam OHLCV and trade-history acquisition.
- Vietnam financial statements and derived ratio acquisition.
- Vietnam equity universe membership and company metadata.
- Instrument and operation routing identifiers.
- Database migration of active Vnstock provider symbols.
- CLI setup, diagnostics, environment variables, documentation, and tests.
- Final replacement of the main `.venv` and removal of `.venv5x`.

It does not add news, MCP, pipeline, or other unrelated Vnstock products.

## Provider Boundary

The canonical active provider identifier is `vnstock`. The application has a
single `VnstockProvider` for market data and a single
`VnstockFundamentalProvider` for fundamental data. Generation-specific names
such as `VnstockDataProvider` and `Vnstock5Provider` are removed.

All Gen 5 calls select their upstream source explicitly. Market and
fundamental calls use VCI where required to preserve the existing series;
index membership uses the supported KBS route. Provider errors are translated
only at application boundaries and retain the original exception as their
cause.

Active routing values, operation adapters, rate-limit configuration, and
instrument-symbol namespaces use `vnstock`. Historical observation provenance
is immutable: an existing value such as `vnstock-data-3.2.7-vci` continues to
describe the package that produced that row.

## Market Data

`VnstockProvider` calls the Gen 5 public API:

- `Market().equity(symbol).ohlcv(..., source="vci")`
- `Market().equity(symbol).trade_history(..., source="vci")`

The normalized OHLCV contract remains unchanged. Persisted prices retain the
existing canonical price scale and price-basis rules. New row provenance uses
`vnstock-<resolved-version>-vci`.

## Fundamental Data and Point-in-Time Safety

Gen 5 financial statements do not expose the exact historical report
publication date used by the generation 4 adapter. The migration must not
invent dates or silently use quarter-end dates, because either choice can
introduce look-ahead bias.

Existing historical fundamental observations remain in the database and are
never relabelled. A Gen 5 refresh fetches normalized quarterly statements and
official `vnstock_quant` ratios, selects the latest complete fiscal period, and
persists one current observation. Its `effective_date` is the calendar day
after the provider request timestamp. This means the application records only
what it can prove was available when acquired.

The observation records its fiscal `period` and `period_end`. Subsequent
refreshes create or merge observations under the existing repository rules.
Historical backfill from Gen 5 is intentionally disabled until an official
public API supplies reliable publication timestamps.

Rows with an incomplete period, missing ratio identity, or an unparseable
request timestamp fail explicitly rather than falling back to an inferred
effective date.

## Universe Data

The universe adapter uses Gen 5 `Reference` APIs:

- `Reference().index.list_by_group(group, source="kbs")` for VN30,
  VNMidCap, and VNSmallCap membership.
- `Reference().equity.list()` for symbol and company names.
- `Reference().equity.list_by_industry(source="vci")` for industry metadata.

VN100 and VNALL remain deterministic composites of the base groups. Snapshot
validation, identifiers, and the domain-level `UniverseSnapshot` contract do
not change.

## Persistence Migration

An Alembic migration changes active `instrument_symbols` rows whose namespace
or source is exactly `vnstock_data` to `vnstock`. The migration is narrow and
reversible. It does not rewrite price-row provider provenance, fundamental
methodology text, operation history, or any other historical audit field.

Application literals accept only `vnstock` after the migration. There is no
runtime alias for `vnstock_data`; stale configuration fails visibly.

## Dependency and Runtime Cleanup

`pyproject.toml` declares the authenticated official package index and pins
compatible release lines for `vnstock` 5.1 and `vnstock_quant`. `uv.lock` is
the source of truth for exact artifacts.

The generation 4 installer workflow and its tests are removed, including the
downloaded-installer setup script. Root commands use normal `uv sync` and a
Gen 5 health check based on the official CLI/status interface. Environment
variables are renamed to `VNSTOCK_REQUESTS_PER_MINUTE` and
`VNSTOCK_MAX_WORKERS`.

After all tests pass in the isolated Gen 5 environment, an exact `uv sync`
updates the project's main `.venv`, pruning generation 4 packages. The
temporary `.venv5x` is then deleted. No API key or account status is written
to the repository or command output.

## Documentation and Historical Evidence

`docs/ARCHITECTURE.md`, `README.md`, `AGENTS.md`, `.env.example`, and package
scripts describe only the active Gen 5 workflow. Dated architecture decisions
and the generation 4 baseline document remain as historical evidence and are
clearly marked superseded; they are not executable instructions.

## Verification

The cutover is accepted only when all of the following hold:

- Unit tests prove Gen 5 market, fundamental, universe, routing, migration,
  error, and point-in-time behavior.
- A live VCI price parity canary succeeds for a bounded symbol/date range.
- A live fundamental canary produces one current observation without inferred
  historical dates.
- A live universe canary returns validated VN30, VNMidCap, and VNSmallCap
  memberships.
- `uv run pytest`, `pnpm lint`, `pnpm type-check`, and `pnpm build` pass.
- `uv pip list` in `.venv` contains the selected Gen 5 packages and none of
  `vnstock_data`, `vnstock_installer`, `vnai`, `vnii`, `vnstock_news`, or
  `vnstock_ta`.
- Repository search finds no executable generation 4 imports, tokens, setup
  commands, or environment-variable names.

## Rollback

Rollback is performed through Git and the Alembic downgrade. Historical data
does not require repair because its provenance is never rewritten. Runtime
rollback requires intentionally reinstalling the old environment from the
recorded baseline; the normal application no longer carries a generation 4
fallback.
