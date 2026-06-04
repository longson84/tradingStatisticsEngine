# Expose the AHR999 factor in the Factors page

**Date:** 2026-06-04
**Branch:** restructure
**Status:** Approved (pending spec review)

## Problem

The `AHR999` factor — Bitcoin's accumulation index — already exists and computes
correctly in `trading_engine/factors/ahr999.py`, but it is **orphaned** on the
`restructure` branch:

- It is not registered in the API's `_build_factor()` factory
  (`api/routes/factors.py`), so no endpoint can build it.
- It is not in the frontend `FactorType` union (`frontend/src/lib/api.ts`).
- It is not in the `FACTOR_OPTIONS` dropdown (`frontend/src/pages/FactorsPage.tsx`).

On the older `master` / `build` branches the factor was wired up (as `AHR999Signal`
/ `AHR999Factor`) and gated to BTC-USD via an `is_applicable(ticker)` method.

## Goal

Make AHR999 selectable in the Factors page **Rarity Analysis** for **all
tickers**, with no symbol restriction. AHR999 is only *meaningful* for Bitcoin,
but the user is trusted to know that — the same way the engine's own docstring
already states: *"will compute on any symbol but results only make sense for
Bitcoin."* No `is_applicable` gate is reintroduced.

This intentionally **reverses** the old branches' BTC-only restriction: AHR999 is
always shown and always computed.

## Scope

- In scope: the `/factors/rarity` endpoint and the Factors page Rarity Analysis
  tab (the only analysis the UI currently exposes).
- Out of scope: `/factors/analyze`, `/factors/universe`, `/factors/regime`
  (universe/regime are cross-sectional and meaningless for a single-asset factor).

## Design

### Backend — `api/routes/factors.py`

Register AHR999 in the factor factory. AHR999 is **parameter-free** — it ignores
`period`, `ma_type`, and `std_dev` (fixed 200-day MA + genesis-date valuation
model), so the branch takes no parameters:

```python
from trading_engine.factors.ahr999 import AHR999

def _build_factor(factor_type, period, ma_type, std_dev=2.0):
    ...
    if factor_type == "ahr999":
        return AHR999()
    ...
```

No applicability guard is added. The existing `FactorComputeError` path already
returns a `422` when there are fewer than 200 bars.

### Frontend — `frontend/src/lib/api.ts`

Add `"ahr999"` to the `FactorType` union:

```ts
export type FactorType =
  "distance_from_peak" | "moving_average" | "bollinger" | "donchian" | "ahr999"
```

### Frontend — `frontend/src/pages/FactorsPage.tsx`

1. Add AHR999 to the dropdown, always visible (no filtering):

   ```ts
   const FACTOR_OPTIONS: FactorOption[] = [
     { label: "Distance From Peak", value: "distance_from_peak" },
     { label: "Moving Average",     value: "moving_average" },
     { label: "Bollinger Bands",    value: "bollinger" },
     { label: "Donchian Channel",   value: "donchian" },
     { label: "AHR999",             value: "ahr999" },
   ]
   ```

2. Hide the parameter inputs when AHR999 is selected. AHR999 ignores all of
   Period / MA Type / Std Dev, so the **Period** block is wrapped in
   `factorType !== "ahr999"` (MA Type and Std Dev are already conditional on
   their own factor types). The request continues to send the existing `period`
   value, which the backend ignores for AHR999.

## Data flow

User selects any ticker → picks AHR999 in the Factor dropdown (param inputs hide)
→ clicks Analyse → `rarityAnalysisApi({ factor_type: "ahr999", symbol, ... })`
→ `POST /factors/rarity` builds `AHR999()`, computes the series, runs the existing
zone-rarity analysis → existing `RarityResults` component renders it unchanged.

## Error handling

- Fewer than 200 bars of data → `FactorComputeError` → `422` (already handled).
- No new error paths introduced (no restriction guard).

## Testing

- **Backend** (`tests/trading_engine/test_factors.py` or the API test module):
  `/factors/rarity` with `factor_type: "ahr999"` returns `200` for a symbol with
  ≥200 bars; existing factor types remain unaffected.
- **Frontend** (manual): AHR999 appears in the dropdown for any ticker;
  selecting it hides Period/MA/Std inputs; Analyse returns and renders rarity
  results.

## Out of scope / non-goals

- No `is_applicable` / symbol-restriction mechanism (deliberately dropped).
- No changes to the AHR999 computation itself.
- No new analysis tabs or factor parameters.
