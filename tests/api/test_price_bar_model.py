from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, PriceBar


def _instrument() -> Instrument:
    return Instrument(
        company=Company(
            display_name="FPT Corporation",
            domicile_country_code="VN",
            sector="Information Technology",
            industry="Công nghệ và thông tin",
            source="test",
        ),
        symbol="FPT",
        currency="VND",
        source="test",
    )


def _price_bar(instrument_id: int, **overrides: object) -> PriceBar:
    values: dict[str, object] = {
        "instrument_id": instrument_id,
        "trading_date": date(2026, 7, 31),
        "open": 101.5,
        "high": 104.0,
        "low": 100.0,
        "close": 103.25,
        "volume": 2_345_678.0,
        "currency": "VND",
        "price_scale": 1_000,
        "price_basis": "adjusted",
        "source": "VCI",
        "fetched_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return PriceBar(**values)  # type: ignore[arg-type]


def test_price_bar_round_trip_preserves_basis_provenance_and_units():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        session.add(_price_bar(instrument.id))
        session.commit()

        stored = session.scalar(select(PriceBar))
        assert stored is not None
        assert stored.instrument.symbol == "FPT"
        assert stored.trading_date == date(2026, 7, 31)
        assert stored.close == 103.25
        assert stored.volume == 2_345_678.0
        assert stored.currency == "VND"
        assert stored.price_scale == 1_000
        assert stored.price_basis == "adjusted"
        assert stored.source == "VCI"


def test_price_bar_rejects_duplicate_instrument_date_and_basis():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        session.add_all([
            _price_bar(instrument.id),
            _price_bar(instrument.id, source="KBS"),
        ])

        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    ("overrides", "constraint_name"),
    [
        ({"close": 0.0}, "ck_price_bars_close_positive"),
        ({"high": 99.0, "low": 100.0}, "ck_price_bars_high_gte_low"),
        ({"volume": -1.0}, "ck_price_bars_volume"),
        ({"price_scale": 0}, "ck_price_bars_price_scale"),
    ],
)
def test_price_bar_rejects_invalid_market_observations(
    overrides: dict[str, object], constraint_name: str
):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        session.add(_price_bar(instrument.id, **overrides))

        with pytest.raises(IntegrityError) as exc_info:
            session.commit()
        assert constraint_name in str(exc_info.value)
