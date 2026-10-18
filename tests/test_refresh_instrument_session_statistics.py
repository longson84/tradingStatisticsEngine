from datetime import UTC, date, datetime

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, InstrumentSessionStatisticSnapshot, Venue
from api.providers.vietnam_market import VietnamProviderMetadata, VietnamProviderResult
from api.session_statistics import SESSION_STATISTIC_METRIC_CODES
from scripts.refresh_instrument_session_statistics import (
    refresh_instrument_session_statistics,
)


class Provider:
    def __init__(self):
        self.calls = []

    def session_stats(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        return VietnamProviderResult(
            frame=pd.DataFrame({
                "symbol": [symbol],
                **{code: [index] for index, code in enumerate(
                    SESSION_STATISTIC_METRIC_CODES, 1
                )},
            }),
            metadata=VietnamProviderMetadata(
                package="vnstock", package_version="5.1.0", access_mode="sponsored",
                upstream_source="VCI", method="session_stats", symbol=symbol,
                requested_start=start, requested_end=end,
            ),
        )


def _database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        company = Company(display_name="FPT", domicile_country_code="VN", source="test")
        venue = Venue(
            code="HOSE", name="HOSE", venue_type="exchange", country_code="VN",
            timezone_name="Asia/Ho_Chi_Minh", trading_calendar_code="VN_EQUITIES",
            session_cutoff_time=datetime.strptime("15:15", "%H:%M").time(), source="test",
        )
        session.add(Instrument(
            id=1, company=company, venue=venue, symbol="FPT", currency="VND",
            is_active=True, source="test",
        ))
    return engine


def test_refresh_stores_immutable_exact_period_snapshot_with_provenance():
    engine = _database()
    provider = Provider()
    fetched_at = datetime(2026, 10, 18, 8, tzinfo=UTC)
    detail = refresh_instrument_session_statistics(
        1, date(2026, 10, 15), date(2026, 10, 16),
        engine=engine, provider=provider, now=fetched_at,
    )
    refresh_instrument_session_statistics(
        1, date(2026, 10, 15), date(2026, 10, 16),
        engine=engine, provider=provider, now=fetched_at.replace(minute=1),
    )

    assert provider.calls == [
        ("FPT", date(2026, 10, 15), date(2026, 10, 16)),
        ("FPT", date(2026, 10, 15), date(2026, 10, 16)),
    ]
    assert detail == "updated FPT session statistics for 2026-10-15 through 2026-10-16"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(
            InstrumentSessionStatisticSnapshot
        )) == 2
        row = session.scalar(select(InstrumentSessionStatisticSnapshot))
        assert row is not None
        assert row.source == "vnstock-5.1.0-vci"
        assert len(row.metrics) == 64
