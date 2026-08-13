from __future__ import annotations

from datetime import UTC, datetime
import json

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Instrument,
    InstrumentSymbol,
    PriceBar,
    PriceBarCoverage,
    PriceRefreshState,
)
from scripts.migrate_legacy_benchmark_cache import (
    migrate_legacy_benchmark_cache,
)


def test_legacy_benchmark_cache_migrates_to_exact_index_instruments(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        for code, currency, namespace, provider_symbol in (
            ("SPX", "USD", "yfinance", "^GSPC"),
            ("VN30", "VND", "vnstock_data", "VN30"),
        ):
            instrument = Instrument(
                ticker=code,
                instrument_type="market_index",
                currency=currency,
                is_active=True,
                source="system",
            )
            session.add(instrument)
            session.flush()
            session.add(InstrumentSymbol(
                instrument=instrument,
                namespace=namespace,
                symbol=provider_symbol,
                is_primary=True,
                source="test",
            ))
    fetched_at = datetime(2026, 8, 11, 10, tzinfo=UTC).isoformat()
    for code, close, source in (
        ("SPX", 7700.0, "yfinance"),
        ("VN30", 1900.0, "vnstock-data-3.2.7-vci"),
    ):
        pd.DataFrame([{
            "date": "2026-08-11",
            "open": close - 5,
            "high": close + 5,
            "low": close - 10,
            "close": close,
            "volume": 1000,
        }]).to_csv(tmp_path / f"{code.lower()}.csv", index=False)
        (tmp_path / f"{code.lower()}.json").write_text(json.dumps({
            "benchmark": code,
            "fetched_at": fetched_at,
            "row_count": 1,
            "source": source,
        }))

    results = migrate_legacy_benchmark_cache(engine, tmp_path)

    assert [(row.code, row.row_count) for row in results] == [
        ("SPX", 1), ("VN30", 1)
    ]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PriceBar)) == 2
        assert session.scalar(select(func.count()).select_from(PriceBarCoverage)) == 2
        assert session.scalar(select(func.count()).select_from(PriceRefreshState)) == 2
        bars = tuple(session.scalars(select(PriceBar).order_by(PriceBar.currency)))
    assert {bar.price_basis for bar in bars} == {"index_level"}
    assert {bar.instrument_id for bar in bars} == {
        result.instrument_id for result in results
    }
