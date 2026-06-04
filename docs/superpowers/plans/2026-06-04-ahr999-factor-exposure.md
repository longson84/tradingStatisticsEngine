# AHR999 Factor Exposure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing AHR999 factor selectable in the Factors page Rarity Analysis for all tickers.

**Architecture:** AHR999 already computes correctly in `trading_engine/factors/ahr999.py` and is unit-tested. The factor is currently orphaned — not registered in the API factory and not listed in the frontend. This plan wires it through both layers with no symbol restriction. AHR999 is parameter-free, so the frontend hides the Period input when it is selected.

**Tech Stack:** Python (FastAPI, pytest, uv), React + TypeScript (Vite, pnpm).

---

## File Structure

- `api/routes/factors.py` — MODIFY: register `ahr999` in `_build_factor()`.
- `tests/api/__init__.py` — CREATE: package marker for API-layer tests.
- `tests/api/test_factors_route.py` — CREATE: unit test for the factory mapping.
- `frontend/src/lib/api.ts` — MODIFY: add `"ahr999"` to the `FactorType` union.
- `frontend/src/pages/FactorsPage.tsx` — MODIFY: add AHR999 to `FACTOR_OPTIONS`; hide Period when AHR999 is selected.

---

### Task 1: Register AHR999 in the API factor factory

**Files:**
- Create: `tests/api/__init__.py`
- Create: `tests/api/test_factors_route.py`
- Modify: `api/routes/factors.py` (imports + `_build_factor`)

- [ ] **Step 1: Create the test package marker**

Create `tests/api/__init__.py` with a single line:

```python
"""API-layer tests."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/api/test_factors_route.py`:

```python
"""Tests for api/routes/factors.py factory wiring."""
from __future__ import annotations

import pytest

from api.routes.factors import _build_factor
from trading_engine.factors import (
    AHR999,
    BollingerBands,
    DonchianChannel,
    DistanceFromPeak,
    MovingAverageRatio,
)


class TestBuildFactor:
    def test_ahr999_is_registered(self):
        factor = _build_factor("ahr999", 200, "sma")
        assert isinstance(factor, AHR999)

    def test_existing_factors_unaffected(self):
        assert isinstance(_build_factor("moving_average", 50, "ema"), MovingAverageRatio)
        assert isinstance(_build_factor("bollinger", 20, "sma", 2.0), BollingerBands)
        assert isinstance(_build_factor("donchian", 20, "sma"), DonchianChannel)
        assert isinstance(_build_factor("distance_from_peak", 200, "sma"), DistanceFromPeak)

    def test_unknown_factor_still_rejected(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _build_factor("nonsense", 10, "sma")
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/api/test_factors_route.py -v`
Expected: `test_ahr999_is_registered` FAILS — `_build_factor` raises `HTTPException` ("Unknown factor type: 'ahr999'"). The other two tests PASS.

- [ ] **Step 4: Add the AHR999 import**

In `api/routes/factors.py`, with the other factor imports (after the `from trading_engine.factors.moving_average import MovingAverageRatio` line), add:

```python
from trading_engine.factors.ahr999 import AHR999
```

- [ ] **Step 5: Register AHR999 in `_build_factor`**

In `api/routes/factors.py`, inside `_build_factor`, add the branch immediately before the final `raise HTTPException(...)` line:

```python
    if factor_type == "ahr999":
        return AHR999()
```

The full function now ends:

```python
    if factor_type == "distance_from_peak":
        return DistanceFromPeak(window=period)
    if factor_type == "ahr999":
        return AHR999()
    raise HTTPException(status_code=400, detail=f"Unknown factor type: {factor_type!r}")
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/api/test_factors_route.py -v`
Expected: all three tests PASS.

- [ ] **Step 7: Run the full backend suite to check for regressions**

Run: `uv run pytest tests/ -q`
Expected: all tests pass (no existing tests broken).

- [ ] **Step 8: Commit**

```bash
git add api/routes/factors.py tests/api/__init__.py tests/api/test_factors_route.py
git commit -m "feat(api): register AHR999 in factor factory"
```

---

### Task 2: Expose AHR999 in the frontend Factors page

**Files:**
- Modify: `frontend/src/lib/api.ts` (the `FactorType` union)
- Modify: `frontend/src/pages/FactorsPage.tsx` (`FACTOR_OPTIONS` + Period visibility)

- [ ] **Step 1: Add `ahr999` to the `FactorType` union**

In `frontend/src/lib/api.ts`, change the `FactorType` line to:

```ts
export type FactorType = "distance_from_peak" | "moving_average" | "bollinger" | "donchian" | "ahr999"
```

- [ ] **Step 2: Add AHR999 to the factor dropdown**

In `frontend/src/pages/FactorsPage.tsx`, add the AHR999 entry to `FACTOR_OPTIONS`:

```ts
const FACTOR_OPTIONS: FactorOption[] = [
  { label: "Distance From Peak", value: "distance_from_peak" },
  { label: "Moving Average",     value: "moving_average" },
  { label: "Bollinger Bands",    value: "bollinger" },
  { label: "Donchian Channel",   value: "donchian" },
  { label: "AHR999",             value: "ahr999" },
]
```

- [ ] **Step 3: Hide the Period input when AHR999 is selected**

In `frontend/src/pages/FactorsPage.tsx`, the Period control is currently always rendered:

```tsx
      {/* Period (all factors have this) */}
      <div>
        <Label>Period</Label>
        <NumberInput value={period} onChange={setPeriod} min={2} />
      </div>
```

Wrap it so it is hidden for AHR999 (which ignores Period). Replace the block above with:

```tsx
      {/* Period — all factors except AHR999 (which is parameter-free) */}
      {factorType !== "ahr999" && (
        <div>
          <Label>Period</Label>
          <NumberInput value={period} onChange={setPeriod} min={2} />
        </div>
      )}
```

The request still sends the existing `period` state value; the backend ignores it for AHR999, so no further request changes are needed. (MA Type and Std Dev are already conditional on `moving_average` / `bollinger`, so they stay hidden for AHR999 automatically.)

- [ ] **Step 4: Type-check the frontend**

Run: `cd frontend && pnpm tsc --noEmit`
Expected: no type errors. (If `tsc` is not a direct script, use `cd frontend && pnpm exec tsc --noEmit`.)

- [ ] **Step 5: Manual verification in the running app**

Start the frontend dev server (and backend) and confirm:
1. AHR999 appears in the **Factor** dropdown for any ticker (e.g. `MSFT` and `BTC-USD`).
2. Selecting **AHR999** hides the Period / MA Type / Std Dev inputs.
3. With ticker `BTC-USD`, factor `AHR999`, clicking **Analyse** returns and renders Rarity Analysis results without error.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/pages/FactorsPage.tsx
git commit -m "feat(frontend): expose AHR999 factor in Factors page"
```

---

## Self-Review Notes

- **Spec coverage:** Backend factory registration (Task 1) ✓; `FactorType` union (Task 2 Step 1) ✓; `FACTOR_OPTIONS` always-visible entry (Task 2 Step 2) ✓; hide parameter inputs for parameter-free AHR999 (Task 2 Step 3) ✓; no symbol restriction (no guard added anywhere) ✓; scope limited to `/factors/rarity` + Rarity Analysis tab ✓.
- **Placeholder scan:** none — all steps contain concrete code/commands.
- **Type consistency:** `_build_factor("ahr999", ...)` returns `AHR999` (matches `trading_engine.factors.AHR999` export); `FactorType` string `"ahr999"` matches the backend `factor_type` branch and the `FACTOR_OPTIONS` value.
