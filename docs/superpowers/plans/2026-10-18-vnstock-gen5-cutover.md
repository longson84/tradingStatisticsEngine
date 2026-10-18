# Vnstock Gen 5 Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Vnstock generation 5 the application's only active Vietnam data integration and remove the generation 4 runtime, code paths, and setup workflow.

**Architecture:** Keep the existing engine and API domain contracts, but replace the provider boundary with canonical `vnstock` adapters. Market and reference data come from `vnstock` 5.1; current point-in-time financial observations come from `vnstock_quant` 0.4 ratios and use acquisition time because Gen 5 does not expose historical publication dates.

**Tech Stack:** Python 3.12, uv, vnstock 5.1.x, vnstock-quant 0.4.x, pandas, FastAPI, SQLAlchemy, Alembic, pytest, React/TypeScript/pnpm.

**Spec:** `docs/superpowers/specs/2026-10-18-vnstock-gen5-cutover-design.md`

## Global Constraints

- The canonical active provider identifier is exactly `vnstock`; no runtime alias accepts `vnstock_data`.
- Preserve historical provenance such as `vnstock-data-3.2.7-vci`; migrate only active routing identity.
- Every Gen 5 provider request names its upstream source explicitly.
- A new Vietnam fundamental observation uses the day after acquisition as `effective_date`; never infer a historical publication date.
- Use `uv` for Python dependencies and `pnpm` for JavaScript dependencies.
- Do not log, commit, or embed the Vnstock API key or a credentialed package-index URL.
- Keep `trading_engine` independent from Vnstock, FastAPI, and frontend runtime code.

## Review Focus

- A Gen 4 `vnstock_data` routing value remaining after migration must fail rather than silently selecting Gen 5; Task 5 tests this.
- A ratio result with no complete fiscal period must fail explicitly rather than create a partially populated snapshot; Task 3 tests this.
- A malformed or timezone-aware acquisition timestamp must produce one deterministic next-day effective date; Task 3 tests this.
- A universe metadata response containing multiple ICB levels per symbol must select level 1 as sector and the deepest available level as industry; Task 4 tests this.
- Package synchronization must not leave any Gen 4 distribution installed alongside Gen 5; Task 6 verifies the installed inventory.

---

### Task 1: Lock the Generation 5 Dependency and Health Workflow

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `scripts/check_vnstock.py`
- Create: `tests/test_check_vnstock.py`
- Modify: `package.json`

**Interfaces:**
- Consumes: the official package index `https://vnstocks.com/api/packages` and locally configured Vnstock credentials.
- Produces: locked `vnstock>=5.1,<5.2`, locked `vnstock-quant>=0.4,<0.5`, and `check_environment() -> VnstockEnvironmentStatus` for setup verification.

- [ ] **Step 1: Write failing health-check tests**

  Add tests proving that `check_environment()` accepts the locked Gen 5 major/minor lines, rejects a non-5.x core, rejects missing `vnstock_quant`, and never includes credentials in its returned text.

- [ ] **Step 2: Verify the health-check tests fail**

  Run: `UV_CACHE_DIR=.cache/uv .venv5x/bin/python -m pytest tests/test_check_vnstock.py -q`

  Expected: FAIL because `scripts.check_vnstock` does not exist.

- [ ] **Step 3: Implement the health check and dependency declarations**

  Add `VnstockEnvironmentStatus` and `check_environment()` in `scripts/check_vnstock.py`. Declare the two compatible dependency lines and the named official uv index without embedded credentials. Replace `check:vnstock`, `setup:vnstock`, and `setup` scripts with Gen 5 commands that use uv and the health check.

- [ ] **Step 4: Resolve and inspect the dependency lock**

  Run the authenticated uv lock/sync flow without printing the credential, then run `uv tree --locked | rg 'vnstock|quant'`.

  Expected: the tree contains only the Gen 5 core and quant lines; no Gen 4 Vnstock package is selected.

- [ ] **Step 5: Verify Task 1**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/test_check_vnstock.py -q && pnpm check:vnstock`

  Expected: all health-check tests pass and the command reports Gen 5 core and quant as available.

- [ ] **Step 6: Commit Task 1**

  Commit only the dependency, lock, health-check, package-script, and test files with message `build: lock vnstock generation 5`.

### Task 2: Replace the Market Provider with the Canonical Gen 5 Adapter

**Files:**
- Modify: `api/providers/vietnam_market.py`
- Modify: `api/providers/vietnam_price_loader.py`
- Modify: `scripts/canary_vnstock_ohlcv.py`
- Rename: `scripts/diagnose_vnstock_data.py` to `scripts/diagnose_vnstock.py`
- Modify: `tests/api/test_vietnam_market_provider.py`
- Modify: `tests/api/test_vietnam_price_loader.py`
- Rename: `tests/test_diagnose_vnstock_data.py` to `tests/test_diagnose_vnstock.py`

**Interfaces:**
- Consumes: `Market().equity(symbol).ohlcv(..., source="vci")` and `trade_history(..., source="vci")`.
- Produces: `VnstockProvider` implementing `VietnamMarketProvider`, with normalized provenance `vnstock-<version>-vci`.

- [ ] **Step 1: Replace parallel-provider tests with canonical-provider tests**

  Tests must assert explicit lowercase `vci`, the Gen 5 version guard, unchanged OHLCV normalization, source-preserving errors, and absence of `VnstockDataProvider`/`Vnstock5Provider` exports.

- [ ] **Step 2: Verify the new tests fail**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_market_provider.py tests/api/test_vietnam_price_loader.py tests/test_diagnose_vnstock.py -q`

  Expected: FAIL because the canonical provider and renamed diagnostic do not exist yet.

- [ ] **Step 3: Implement `VnstockProvider` and update consumers**

  Remove both generation-specific provider classes. Keep the existing protocol, metadata dataclasses, validation, and normalizer. Update the loader, diagnostic, and OHLCV canary to use `VnstockProvider` and the `vnstock` adapter label.

- [ ] **Step 4: Verify Task 2**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_market_provider.py tests/api/test_vietnam_price_loader.py tests/test_diagnose_vnstock.py tests/test_canary_vnstock_ohlcv.py -q`

  Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 2**

  Commit the market-provider, consumer, canary, diagnostic, and test changes with message `refactor: make vnstock 5 the market provider`.

### Task 3: Implement Acquisition-Dated Gen 5 Fundamentals

**Files:**
- Modify: `api/providers/vietnam_fundamentals.py`
- Modify: `api/fundamental_provider.py`
- Modify: `scripts/canary_vnstock_fundamentals.py`
- Modify: `scripts/refresh_instrument_fundamentals.py`
- Modify: `tests/api/test_vietnam_fundamental_provider.py`
- Modify: `tests/api/test_fundamental_provider.py`
- Modify: `tests/test_canary_vnstock_fundamentals.py`

**Interfaces:**
- Consumes: `Dataset.load(symbol, period="quarter", prices=True, notes=False, source="vci")` and `fa.ratios(dataset, period="quarter", profile="vn", format="long")`.
- Produces: `VnstockFundamentalProvider.fetch(symbol) -> VietnamFundamentalResult`, including ratio rows, UTC `acquired_at`, package versions, and explicit VCI source; `_normalize_vn_quant_ratios(result) -> pd.DataFrame` returns at most one current snapshot.

- [ ] **Step 1: Write failing provider and point-in-time tests**

  Add tests for explicit Dataset/ratio parameters, required ratio IDs, latest complete-period selection, ID-to-domain-field mapping, UTC and timezone-aware next-day dating, period-end calculation, incomplete-period rejection, and methodology text naming both resolved package versions.

- [ ] **Step 2: Verify the tests fail for the intended missing behavior**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_fundamental_provider.py tests/api/test_fundamental_provider.py -q`

  Expected: FAIL on the old raw VCI adapter and historical `publicDate` normalizer.

- [ ] **Step 3: Implement the Gen 5 fundamental provider**

  Replace raw/private VCI imports with public `vnstock_quant` APIs. Map quant IDs to the canonical value columns, derive only values whose inputs are present, select one complete latest quarter, and set `effective_date` to the day after `acquired_at`. Raise `ProviderDataError` when no complete period or timestamp exists.

- [ ] **Step 4: Update refresh and canary behavior**

  Change the refresh script and canary to the `vnstock` adapter. The canary validates one current snapshot and optional storage; remove historical parity assumptions that Gen 5 cannot support.

- [ ] **Step 5: Verify Task 3**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_vietnam_fundamental_provider.py tests/api/test_fundamental_provider.py tests/test_canary_vnstock_fundamentals.py -q`

  Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 3**

  Commit the fundamental provider, normalizer, scripts, and tests with message `feat: acquire point-in-time fundamentals with vnstock quant`.

### Task 4: Move Vietnam Universes to Gen 5 Reference APIs

**Files:**
- Modify: `api/providers/vietnam_universes.py`
- Modify: `tests/api/test_universe_providers.py`

**Interfaces:**
- Consumes: the Gen 5 `Reference` index/equity accessors listed in the spec.
- Produces: unchanged `UniverseSnapshot` domain objects sourced as `vnstock-<version>-kbs` and `vnstock-<version>-kbs-derived`.

- [ ] **Step 1: Write failing Gen 5 universe tests**

  Replace the fake generation 4 listing with fake `Reference.index` and `Reference.equity` accessors. Assert explicit KBS/VCI calls, cached base-group requests, composite membership, company names, exchanges, level-1 sectors, deepest-level industries, and Gen 5 provenance.

- [ ] **Step 2: Verify the universe tests fail**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_universe_providers.py -q`

  Expected: FAIL because the provider still imports `vnstock_data.Listing`.

- [ ] **Step 3: Implement the Reference-backed universe adapter**

  Use one lazily constructed `Reference()` instance, `index.list_by_group`, `equity.list_by_exchange`, and `equity.list_by_industry`. Remove the hard-coded industry map and generation 4 organ-code dependency while keeping validation and composite construction unchanged.

- [ ] **Step 4: Verify Task 4**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_universe_providers.py -q`

  Expected: all universe tests pass.

- [ ] **Step 5: Commit Task 4**

  Commit the universe adapter and tests with message `refactor: use vnstock 5 reference universes`.

### Task 5: Migrate Active Routing Identity to `vnstock`

**Files:**
- Create: `migrations/versions/0031_migrate_vnstock_provider_identity.py`
- Create: `tests/test_vnstock_provider_migration.py`
- Modify: `api/instrument_data_routing.py`
- Modify: `api/price_refresh_coordination.py`
- Modify: `api/services/data_operation_service.py`
- Modify: `api/fundamental_provider.py`
- Modify: `scripts/run_data_operation.py`
- Modify: `scripts/refresh_instrument_fundamentals.py`
- Modify: `scripts/canary_vnstock_ohlcv.py`
- Modify: tests under `tests/api/` and `tests/test_run_data_operation.py` that assert adapter values.
- Modify: `.env.example`

**Interfaces:**
- Consumes: the canonical provider classes from Tasks 2-4.
- Produces: routing literals containing `vnstock`, environment variables `VNSTOCK_REQUESTS_PER_MINUTE` and `VNSTOCK_MAX_WORKERS`, and reversible migration `0031`.

- [ ] **Step 1: Write failing routing, environment, and migration tests**

  Update routing/coordination/operation expectations to `vnstock`; assert `vnstock_data` is rejected. Test that migration upgrade changes only exact active namespace/source values and downgrade reverses only those values.

- [ ] **Step 2: Verify the tests fail**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api/test_instrument_data_routing.py tests/api/test_price_refresh_coordination.py tests/api/test_data_operations.py tests/test_run_data_operation.py tests/test_vnstock_provider_migration.py -q`

  Expected: FAIL on old adapter and environment names and the missing migration.

- [ ] **Step 3: Implement the canonical routing and migration**

  Replace executable `vnstock_data` literals with `vnstock`; add migration `0031` after `0030`; rename the two environment variables; keep historical source/methodology fields untouched.

- [ ] **Step 4: Verify Task 5**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest tests/api tests/test_run_data_operation.py tests/test_vnstock_provider_migration.py -q`

  Expected: all API, operation, and migration tests pass.

- [ ] **Step 5: Commit Task 5**

  Commit the migration, routing, configuration, and tests with message `refactor: migrate active provider identity to vnstock`.

### Task 6: Remove Generation 4 Workflow and Complete the Cutover

**Files:**
- Delete: `scripts/setup_vnstock_data.py`
- Delete: `tests/test_setup_vnstock_data.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/vnstock-generation-4-baseline.md`
- Modify: `frontend/src/lib/format.ts`
- Create: `tests/test_no_legacy_vnstock_runtime.py`
- Modify: any remaining executable file found by the generation 4 search.

**Interfaces:**
- Consumes: completed Gen 5 providers, routing, migrations, and dependency lock.
- Produces: one documented setup path, one clean Gen 5 runtime, and no executable generation 4 references.

- [ ] **Step 1: Add or update documentation/static regression assertions**

  Add a focused test or scripted search that permits generation 4 names only inside the dated baseline and superseded architecture history, and fails for executable imports, routing tokens, setup commands, or old environment variables.

- [ ] **Step 2: Verify the static assertion fails**

  Run the new test/search before cleanup.

  Expected: FAIL and list the remaining generation 4 executable references.

- [ ] **Step 3: Remove the old workflow and update active documentation**

  Delete the installer and tests; update setup, diagnostics, frontend labels, architecture, and developer commands. Mark the baseline and dated architecture decision as superseded without deleting historical evidence.

- [ ] **Step 4: Run live bounded canaries**

  Run the Gen 5 price canary for FPT over a short date range, the fundamental canary without writes, and universe fetches for VN30/VNMidCap/VNSmallCap.

  Expected: price data is non-empty and normalized; fundamentals produce exactly one acquisition-dated row; universe counts are non-zero and validated.

- [ ] **Step 5: Run the full repository verification**

  Run: `UV_CACHE_DIR=.cache/uv uv run --no-sync pytest && pnpm lint && pnpm type-check && pnpm build`

  Expected: all pytest tests pass; lint, type-check, and build exit successfully.

- [ ] **Step 6: Replace the main environment and verify installed inventory**

  Run exact `uv sync --all-groups` in the final integrated checkout, remove `.venv5x`, and inspect `uv pip list`.

  Expected: `vnstock 5.1.x` and `vnstock-quant 0.4.x` are present; `vnstock_data`, `vnstock_installer`, `vnai`, `vnii`, `vnstock_news`, and `vnstock_ta` are absent.

- [ ] **Step 7: Verify no executable Gen 4 references remain**

  Run a repository `rg` excluding `.git`, virtual environments, the baseline document, and superseded dated architecture sections.

  Expected: no executable Gen 4 imports, adapter values, setup commands, or old environment-variable names.

- [ ] **Step 8: Commit Task 6**

  Commit cleanup, documentation, frontend label, and verification test changes with message `chore: remove vnstock generation 4 workflow`.
