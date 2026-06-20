# AGENTS.md

## Communication

When the user asks to see output or results, show the requested output first. Do not automatically debug, refactor, or fix failures unless the user asks for that next step.

When the user describes context or something they already did, do not jump straight into code changes. Ask before taking action unless the request clearly asks for implementation.

## Project Snapshot

Trading Statistics Engine is now a library-first full-stack app:

- `trading_engine/`: standalone Python 3.12 trading and analysis library.
- `api/`: FastAPI adapter over the engine.
- `frontend/`: React 19 + TypeScript + Vite UI.
- `tests/`: pytest coverage for the engine and API.
- `notebooks/`: exploratory notebooks that should consume the engine, not own core logic.

Use `uv` for Python dependencies and `pnpm` for JavaScript dependencies. Do not introduce npm, yarn, pipenv, Poetry, or ad hoc virtualenv workflows.

## Core Architecture

Keep `trading_engine` independent from application frameworks. It must work from notebooks, scripts, tests, and FastAPI without importing FastAPI, React/frontend code, Streamlit, or UI/runtime-specific dependencies.

The engine follows this domain flow:

1. Data: `DataLoader` -> `PriceFrame`
2. Factors: `Factor.compute(...)` -> `FactorSeries`
3. Factor analysis: time-series, cross-sectional, regime, rarity, and event analysis
4. Strategy: strategy inputs -> weight matrix and trades
5. Portfolio: portfolio simulation over strategy weights
6. Performance: metrics, drawdowns, monthly/annual returns, trade analytics

Shared dataclasses, protocols, and domain exceptions belong in `trading_engine/types.py`. Reuse those types instead of creating parallel request, response, or analysis models inside feature modules.

## Domain Rules

Do not conflate factors, signals, strategies, and portfolios.

- A factor derives a series from prices.
- Analysis explains factor behavior or market state.
- A strategy produces target weights, not just buy/sell booleans.
- A portfolio simulates capital over those weights.
- Performance modules summarize portfolio/trade outcomes.

Strategy output is a time-by-symbol weight matrix with values in `[-1, 1]`. Long/short direction should remain explicit on trades; do not infer every trade behavior only from weight signs.

Avoid look-ahead bias. If strategy or factor logic uses future bars, shifted negative windows, or same-bar execution assumptions, add or update diagnostics/tests in `trading_engine/diagnostics`.

## Backend Guidance

FastAPI code in `api/` should stay thin:

- Request/response validation belongs in `api/schemas/`.
- Data source selection, strategy construction, and app-level dependency wiring belong in `api/deps.py`.
- Route handlers should translate API inputs into engine calls and serialize engine outputs.
- Core calculations belong in `trading_engine/`, not in route handlers.

When changing API contracts, update both Pydantic schemas and the matching TypeScript interfaces in `frontend/src/lib/api.ts`.

## Frontend Guidance

The frontend is React + TypeScript + Vite with React Query and lightweight charts. Prefer existing local patterns in:

- `frontend/src/lib/api.ts` for API calls and shared response types.
- `frontend/src/lib/format.ts` for display formatting.
- `frontend/src/components/ui/` for reusable primitives.
- Feature folders such as `components/backtest/` and `components/rarity/` for domain-specific presentation.

Keep trading calculations out of React components. Components may transform data for charts/tables, but analytical logic that should be tested or reused belongs in the Python engine/API.

## Commands

Install dependencies:

```bash
pnpm install
uv sync
```

Run both services:

```bash
pnpm dev
```

Run services separately:

```bash
pnpm dev:backend
pnpm dev:frontend
```

Validate changes:

```bash
uv run pytest
pnpm lint
pnpm type-check
pnpm build
```

Use the root `package.json` scripts as the source of truth for ports and dev commands. `frontend/src/lib/api.ts` currently targets `http://localhost:8000`.

## Testing Expectations

For engine changes, add or update pytest coverage under `tests/trading_engine/`.

For API changes, add or update tests under `tests/api/` and verify serialization details such as date keys, optional fields, and error responses.

For frontend changes, run at least `pnpm lint` and `pnpm type-check`; use `pnpm build` when the change affects routes, API types, charts, or shared UI primitives.

The test suite intentionally guards against Streamlit imports inside `trading_engine/`. Preserve that boundary.

## Code Style

Prefer small pure functions, dataclasses, protocols, and explicit conversion boundaries. Reuse existing helpers before adding new ones.

Keep naming domain-specific and precise: `factor`, `strategy`, `portfolio`, `trade`, `weight`, `regime`, and `performance` have distinct meanings in this repo.

Do not add broad abstractions unless they remove real duplication or clarify a domain boundary that already exists in the code.
