# Trading Statistics Engine

Architecture and durable data conventions are documented in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Setup

Create an ignored `.env` from `.env.example`, set `VNSTOCK_API_KEY`, then run:

```bash
pnpm setup
```

`uv` resolves the locked dependency graph from PyPI and Vnstock's official
package index. The active integration uses `vnstock` 5.1.x and
`vnstock-quant` 0.4.x; exact artifacts are recorded in `uv.lock`.

Verify the local Gen 5 installation without making a data request:

```bash
pnpm check:vnstock
```

Inspect account and entitlement status with the official CLI:

```bash
.venv/bin/vnstock status
```

Neither the API key nor credentialed package-index URLs are committed.

## Local PostgreSQL

Start PostgreSQL, apply migrations, and synchronize the live equity Universes:

```bash
docker compose up -d postgres
UV_CACHE_DIR=.cache/uv uv run alembic upgrade head
UV_CACHE_DIR=.cache/uv uv run python -m scripts.sync_equity_universes --all
```

Preview provider changes without writing:

```bash
UV_CACHE_DIR=.cache/uv uv run python -m scripts.sync_equity_universes --all --dry-run
```
