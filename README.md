# Trading Statistics Engine

Architecture and durable data conventions are documented in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Setup

Create an ignored `.env` from `.env.example`, set `VNSTOCK_API_KEY`, then run:

```bash
pnpm setup
```

The setup order is intentional. `uv` installs the public dependency graph with
`--inexact`, then the official Vnstock sponsor installer refreshes its private
bundle in the project `.venv`. Normal project commands use `uv run --no-sync`
so that `vnstock_data` is not removed merely because the private distribution
cannot be represented in the public `uv.lock` file.

Verify the local sponsored installation without making a data request:

```bash
pnpm check:vnstock
```

Force the official installer to fetch the latest entitled sponsor bundle:

```bash
.venv/bin/python -m scripts.setup_vnstock_data --force
```

The installer is downloaded at runtime from the
[official Vnstock member installer](https://vnstocks.com/onboard-member/cai-dat-go-loi/cai-dat-nang-cao).
Neither the API key nor the private temporary package path is committed.

## Local PostgreSQL

Start PostgreSQL, apply migrations, and import the saved company universes:

```bash
docker compose up -d postgres
UV_CACHE_DIR=.cache/uv uv run --no-sync alembic upgrade head
UV_CACHE_DIR=.cache/uv uv run --no-sync python -m scripts.import_companies
```

The importer is idempotent. Verify database parity without writing:

```bash
UV_CACHE_DIR=.cache/uv uv run --no-sync python -m scripts.import_companies --verify-only
```
