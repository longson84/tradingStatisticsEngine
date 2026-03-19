# Architecture Review — 2026-03-18

## Module Map

```
src/
├── ingestion/          Data fetching + file-based daily cache (yfinance, vnstock, csv)
├── indicators/         Pure functions: MA, Bollinger, Donchian, AHR999, peak
├── factors/            BaseFactor ABC + 3 implementations (ahr999, distance_from_peak, ma_ratio)
│                       Factors wrap indicators and are consumed by rarity analysis
├── strategy/           BaseStrategy ABC + 4 implementations (PriceVsMA, MACrossover, BB, Donchian)
│                       Strategies produce (crossover_series, buy_signals, sell_signals)
├── position/           Trade simulation engine: build_trades, build_equity_curve, get_current_position
├── backtest/           Performance calc, drawdown, monthly/annual stats, chart builders, trade tables
├── analysis/
│   └── rarity/         NP event detection, percentile stats, report generation
├── portfolio/          Portfolio + PositionResult dataclasses ← UNUSED (see issues)
├── shared/             Constants, formatters, BasePack/PackResult base classes, stats utils
└── app/
    ├── data_loader.py          @st.cache_data wrappers; registry-pattern loader
    ├── strategy_compute.py     @st.cache_data wrapper for full backtest computation
    ├── strategy_sidebar_factories.py   Strategy sidebar widgets + sweep config builders
    ├── analysis_sidebar_factories.py   Factor analysis sidebar widgets
    ├── packs/
    │   ├── _renderers.py       Shared Streamlit renderers (used across 3+ packs)
    │   ├── position_pack.py    Single-ticker strategy backtest
    │   ├── batch_pack.py       Multi-ticker strategy backtest
    │   ├── sweep_pack.py       Parameter sweep across one ticker
    │   └── rarity_pack.py      Factor rarity analysis
    └── widgets/
        ├── position_widget.py  Position-specific section renderers
        └── rarity_widget.py    Rarity-specific table/tree renderers

pages/
    1_Factor_Analysis.py
    2_Strategy_Backtest.py
    3_Batch_Backtest.py
    4_Parameter_Sweep.py
```

## Dependency Flow

```
pages → app/packs → app/widgets + app/_renderers
                  → app/strategy_compute → position/ + backtest/ + strategy/
                  → analysis/rarity/     → factors/ + indicators/
                  → app/data_loader      → ingestion/
                        shared/ (constants, fmt, base) ← used by all layers
```

---

## Issues

### 1. `ParameterSweepPack` and `BatchPositionPack` inherit `PositionPack` unnecessarily

Both classes extend `PositionPack` but override everything — `run_computation` and `render_results` both return `pass`. No inherited logic is actually used.

```python
class ParameterSweepPack(PositionPack):  # uses none of PositionPack's methods
class BatchPositionPack(PositionPack):   # same
```

Both should extend `BasePack` directly. The inheritance creates a misleading contract and couples unrelated packs.

**Fix:** Change both to `class ParameterSweepPack(BasePack)` and `class BatchPositionPack(BasePack)`.

---

### 2. `ParameterSweepPack` breaks the `BasePack` interface

`BasePack` defines `run_computation` + `render_results` as the standard entry points. `ParameterSweepPack` replaces them with `run_sweep` + `render_sweep_results`, so the page (`4_Parameter_Sweep.py`) must know it is not a standard pack and call different methods.

This means `ParameterSweepPack` cannot be treated polymorphically as a `BasePack`.

**Options:**
- Align the interface: have `run_computation` accept a list of configs and `render_results` handle the sweep layout.
- Or accept the deviation and document it explicitly.

---

### 3. `sweep_pack._render_variant_expander` duplicates `position_widget`

The trade log section in `_render_variant_expander` (sweep_pack, ~40 lines) manually builds trade rows and applies identical row-styling logic as `position_widget.render_trade_log`. The column set differs slightly (no "B&H at Close"), but the structure is the same.

**Fix:** Extract `build_trade_log_df` to accept an optional `bh_equity` argument (already done), and have sweep use `render_trade_log` from `position_widget`. Or make `render_trade_log` slightly more configurable (max rows, header style).

---

### 4. `portfolio/` module is dead code

`Portfolio` and `PositionResult` have no callers outside their own module — not imported by any pack, page, or app file. The actual results flow through `PackResult` + `compute_ticker_core` dict.

**Fix:** Remove `src/portfolio/` unless there is a planned multi-position feature.

---

### 5. Duplicate `from src.shared.constants import` in `sweep_pack.py`

```python
from src.shared.constants import (COLOR_ACTIVE, DATE_FORMAT_DISPLAY, ...)  # line 9
from src.shared.constants import INITIAL_CAPITAL                            # line 20
```

**Fix:** Merge into a single import block.

---

### 6. `strategy_compute.py` imports Streamlit

`compute_ticker_core` is decorated with `@st.cache_data`, meaning `src/app/strategy_compute.py` depends on `streamlit`. This is acceptable for now given Streamlit is the only UI, but makes the computation layer non-portable to a FastAPI/React migration without extracting the cache decorator.

**Future:** Separate the pure computation function from the cache wrapper — the function can live in `src/backtest/` and the cached version lives in `src/app/`.

---

### 7. `_renderers.py` naming

The `_` prefix conventionally signals a private/internal module, but `_renderers.py` is imported by `position_pack`, `sweep_pack`, `batch_pack`, and `rarity_pack` — it is effectively a public shared module.

**Fix:** Rename to `renderers.py` or move to `src/app/widgets/shared_renderers.py` to match the `widgets/` convention.

---

## Suggested Refactor Priority

| Priority | Item |
|----------|------|
| High | Fix `ParameterSweepPack(PositionPack)` → `BasePack` (issue 1) |
| High | Remove dead `portfolio/` module (issue 4) |
| Medium | Consolidate sweep trade log to reuse `position_widget.render_trade_log` (issue 3) |
| Medium | Rename `_renderers.py` → `renderers.py` or move to widgets (issue 7) |
| Low | Fix duplicate constants import in sweep_pack (issue 5) |
| Low | Decouple `strategy_compute.py` from streamlit (issue 6) |
| Low | Align `ParameterSweepPack` with `BasePack` interface (issue 2) |
