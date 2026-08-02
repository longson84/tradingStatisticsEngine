# Trading Statistics Engine

Architecture and durable data conventions are documented in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Local PostgreSQL

Start PostgreSQL, apply migrations, and import the saved company universes:

```bash
docker compose up -d postgres
uv run alembic upgrade head
uv run python -m scripts.import_companies
```

The importer is idempotent. Verify database parity without writing:

```bash
uv run python -m scripts.import_companies --verify-only
```
