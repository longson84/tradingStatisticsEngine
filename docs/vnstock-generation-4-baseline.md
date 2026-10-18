# Vnstock Generation 4 Comparison Baseline

> Superseded on 2026-10-18 by the generation 5 cutover. This document is
> retained only as migration evidence; none of its commands are active setup
> instructions.

Captured on 2026-10-18 before creating the isolated generation 5 environment.
The project `.venv` remains the executable comparison baseline and must not be
updated during generation 5 parity work.

## Runtime

- Python: 3.12.12
- `vnstock`: 4.0.5
- `vnstock_data`: 3.2.7
- `vnai`: 2.5.6
- `vnii`: 0.2.5
- `vnstock_installer`: 3.1.2
- `vnstock_news`: 2.2.2
- `vnstock_ta`: 1.0.6
- `vnstock_ezchart`: 1.0.2

The private sponsor packages were installed from temporary local bundle paths,
so their original `pip freeze` references are intentionally not recorded as
reproducible dependency locations. Package names and runtime versions above are
the comparison identity.

## Verification

The existing read-only project check reported:

```text
vnstock_data: installed=True version=3.2.7 supported=True api_key_configured=True
```

## Isolated generation 5 environment

Generation 5 is installed separately in the ignored project environment
`.venv5x` for parity work. It currently contains `vnstock` 5.1.0 on Python
3.12.12. The Vnstock CLI recognizes the registered account as Silver; no
generation 5 add-on libraries were installed during baseline setup.

Recreate the isolated environment without modifying `.venv`:

```bash
UV_CACHE_DIR=.cache/uv uv venv .venv5x --python .venv/bin/python
UV_CACHE_DIR=.cache/uv uv pip install --python .venv5x/bin/python \
  --extra-index-url https://vnstocks.com/api/packages 'vnstock>=5.1,<5.2'
```

The installed core reported these available add-ons through
`vnstock install --list`: `vnstock-bt`, `vnstock-news`, `vnstock-mcp`, and
`vnstock-quant`. Listing them did not install them.

## First price-parity canary

Both adapters fetched FPT daily VCI OHLCV for 2026-10-01 through 2026-10-18.
After normalizing dates and selecting `date`, `open`, `high`, `low`, `close`,
and `volume`, both results contained 12 rows from 2026-10-01 through
2026-10-16 and produced this SHA-256 digest:

```text
315d50a8acf96b86f509462483520c890cfdfbed3f58462658e008310b8d29b3
```

This proves parity for that bounded window only; it does not establish
long-history, corporate-action, fundamental, or Universe parity.
