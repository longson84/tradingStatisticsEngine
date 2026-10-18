from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, InstrumentFlowCoverage, Venue
from api.providers.vietnam_market import VietnamProviderMetadata, VietnamProviderResult
from scripts.refresh_instrument_flow import refresh_instrument_flow


class Provider:
    def __init__(self):
        self.calls = []

    def foreign_flow(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        return VietnamProviderResult(
            frame=pd.DataFrame({
                "time": ["2026-10-15T15:00:00+07:00"],
                "buy_vol": [100], "buy_val": [1000],
                "sell_vol": [40], "sell_val": [300],
                "net_vol": [60], "net_val": [123],
            }),
            metadata=VietnamProviderMetadata(
                package="vnstock", package_version="5.1.0", access_mode="sponsored",
                upstream_source="VCI", method="foreign_flow", symbol=symbol,
                requested_start=start, requested_end=end,
            ),
        )

    def proprietary_flow(self, symbol, start, end):
        self.calls.append((symbol, start, end, "proprietary"))
        result = self.foreign_flow(symbol, start, end)
        return VietnamProviderResult(
            frame=result.frame.assign(net_val=77),
            metadata=VietnamProviderMetadata(
                **{**result.metadata.__dict__, "method": "proprietary_flow"}
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


def test_incremental_refresh_uses_seven_day_overlap_and_stores_provider_net():
    engine = _database()
    provider = Provider()
    now = datetime(2026, 10, 16, 9, tzinfo=UTC)
    detail = refresh_instrument_flow(1, "incremental", engine=engine, provider=provider, now=now)
    assert provider.calls == [("FPT", date(2000, 1, 1), date(2026, 10, 16))]
    assert "through 2026-10-15" in detail
    with Session(engine) as session:
        coverage = session.scalar(select(InstrumentFlowCoverage))
        assert coverage is not None
        assert coverage.last_date == date(2026, 10, 15)

    refresh_instrument_flow(1, "incremental", engine=engine, provider=provider, now=now)
    assert provider.calls[-1][1] == date(2026, 10, 8)


def test_provider_failure_preserves_existing_flow():
    engine = _database()
    provider = Provider()
    now = datetime(2026, 10, 16, 9, tzinfo=UTC)
    refresh_instrument_flow(1, "full", engine=engine, provider=provider, now=now)

    class Failure:
        def foreign_flow(self, symbol, start, end):
            raise RuntimeError("provider down")

    try:
        refresh_instrument_flow(1, "incremental", engine=engine, provider=Failure(), now=now)
    except RuntimeError:
        pass
    with Session(engine) as session:
        coverage = session.scalar(select(InstrumentFlowCoverage))
        assert coverage is not None
        assert coverage.row_count == 1


def test_proprietary_refresh_uses_independent_coverage_and_participant_identity():
    engine = _database()
    provider = Provider()
    now = datetime(2026, 10, 16, 9, tzinfo=UTC)
    refresh_instrument_flow(
        1, "full", participant_type="foreign", engine=engine, provider=provider, now=now
    )

    detail = refresh_instrument_flow(
        1,
        "incremental",
        participant_type="proprietary",
        engine=engine,
        provider=provider,
        now=now,
    )

    proprietary_call = next(call for call in provider.calls if len(call) == 4)
    assert proprietary_call == (
        "FPT", date(2000, 1, 1), date(2026, 10, 16), "proprietary"
    )
    assert "proprietary flow through 2026-10-15" in detail
    with Session(engine) as session:
        coverages = session.scalars(
            select(InstrumentFlowCoverage).order_by(
                InstrumentFlowCoverage.participant_type
            )
        ).all()
        assert [(row.participant_type, row.row_count) for row in coverages] == [
            ("foreign", 1), ("proprietary", 1),
        ]
