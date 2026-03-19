# TODOS

Tracked work deferred from code review. Each item includes context so future-you understands the motivation.

---

## TODO-001: Portfolio Page

**What:** Wire `src/portfolio/portfolio.py` to a new Streamlit page (`pages/5_Portfolio.py`).

**Why:** The module is fully scaffolded but no page drives it. Users currently have no way to see aggregated performance across multiple positions.

**Pros:** Completes the natural feature arc of the app (signal → strategy → position → portfolio).

**Cons:** Requires designing the Portfolio sidebar UX and deciding how positions are composed.

**Context:** `portfolio.py` exists as of the `build` branch. The module is unconnected to any page. Start by wiring a minimal sidebar (ticker list + strategy) that creates positions and passes them to `portfolio.py`.

**Depends on:** `build` branch merged to `master`.

---

## TODO-002: Sweep Dispatch Refactor

**What:** Replace the `build_from_sweep_config` / `sweep_label` / `should_skip_sweep_length` string-dispatch if/elif chains with per-strategy `sweep_config` classmethods on `BaseStrategy`.

**Why:** Adding a 5th strategy currently requires updating 6 places: `STRATEGY_REGISTRY`, `SIDEBAR_REGISTRY`, `SWEEP_SIDEBAR_REGISTRY`, plus these 3 dispatch functions. The integrity test catches the first 3 but not the last 3.

**Pros:** Adding a new strategy becomes a single-file change. The integrity test covers the full surface automatically.

**Cons:** Requires adding a `sweep_config` classmethod to `BaseStrategy` and all 4 existing strategy classes. Moderate scope.

**Context:** The integrity test extension (Issue 4 from eng review 2026-03-19) protects against crashes but doesn't eliminate the smell. Tackle when a 5th strategy is added — that's the clearest trigger point.

**Depends on:** `build` branch merged. Issue 4 integrity test extension in place.
