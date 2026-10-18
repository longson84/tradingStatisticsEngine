from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from api.instrument_data_routing import InstrumentRoutingMetadata, ProviderSymbol
from api.repositories.session_statistics_repository import (
    SessionStatisticInstrumentRecord,
    SessionStatisticMetricRecord,
    SessionStatisticSnapshotRecord,
)
from api.services.session_statistics_service import (
    SessionStatisticsCapabilityError,
    SessionStatisticsService,
    SessionStatisticsUnavailableError,
    UnknownSessionStatisticsInstrumentError,
)
from api.services.session_statistics_write_service import (
    SessionStatisticsWriteService,
)
from api.session_statistics import SESSION_STATISTIC_METRIC_CODES
from api.venue_calendars import venue_calendar


class Repository:
    def __init__(self):
        self.instrument = SessionStatisticInstrumentRecord(
            1, "FPT", "common_stock", "HOSE", "VND"
        )
        self.snapshot = None

    def get_instrument(self, instrument_id):
        return self.instrument if instrument_id == 1 else None

    def store_snapshot(self, record):
        self.snapshot = record
        return 7

    def get_latest_snapshot(self, instrument_id, period_start, period_end):
        return self.snapshot


class Routing:
    def __init__(self, *, venue="HOSE"):
        schedule = venue_calendar(venue) if venue in {"HOSE", "HNX", "UPCOM"} else None
        self.row = InstrumentRoutingMetadata(
            instrument_id=1,
            canonical_symbol="FPT",
            instrument_type="common_stock",
            company_id=1,
            venue_code=venue,
            currency="VND",
            catalog_source="test",
            provider_symbols=(ProviderSymbol("listing", "FPT"),),
            timezone_name=schedule.timezone_name if schedule else None,
            trading_calendar_code=schedule.trading_calendar_code if schedule else None,
            session_cutoff_time=schedule.session_cutoff_time if schedule else None,
        )

    def get_instrument_route_metadata(self, instrument_id):
        return self.row if instrument_id == 1 else None


def _values():
    return {
        code: Decimal(index)
        for index, code in enumerate(SESSION_STATISTIC_METRIC_CODES, 1)
    }


def test_write_and_read_services_preserve_exact_period_metrics_and_metadata():
    repository = Repository()
    routing = Routing()
    writer = SessionStatisticsWriteService(repository, routing)
    fetched_at = datetime(2026, 10, 18, tzinfo=UTC)
    snapshot_id = writer.store_snapshot(
        1,
        "FPT",
        date(2026, 10, 15),
        date(2026, 10, 16),
        _values(),
        source="vnstock-5.1.0-vci",
        fetched_at=fetched_at,
    )
    assert snapshot_id == 7
    stored = repository.snapshot
    repository.snapshot = SessionStatisticSnapshotRecord(
        snapshot_id=7,
        instrument_id=1,
        period_start=stored.period_start,
        period_end=stored.period_end,
        source=stored.source,
        schema_version=stored.schema_version,
        fetched_at=stored.fetched_at,
        metrics=tuple(
            SessionStatisticMetricRecord(code=code, value=stored.metrics[code])
            for code in SESSION_STATISTIC_METRIC_CODES
        ),
    )

    result = SessionStatisticsService(repository, routing).get_stored_snapshot(
        1, date(2026, 10, 15), date(2026, 10, 16)
    )

    assert result.snapshot.snapshot_id == 7
    assert result.metrics[0].definition.code == "average_match_volume"
    assert result.metrics[0].value == Decimal(1)
    assert len(result.metrics) == 64


def test_write_service_rejects_naive_time_and_wrong_provider_symbol():
    service = SessionStatisticsWriteService(Repository(), Routing())
    with pytest.raises(ValueError, match="timezone-aware"):
        service.store_snapshot(
            1, "FPT", date(2026, 10, 15), date(2026, 10, 16), _values(),
            source="test", fetched_at=datetime(2026, 10, 18),
        )
    with pytest.raises(ValueError, match="cannot update"):
        service.store_snapshot(
            1, "VNM", date(2026, 10, 15), date(2026, 10, 16), _values(),
            source="test", fetched_at=datetime(2026, 10, 18, tzinfo=UTC),
        )


def test_read_service_distinguishes_invalid_unknown_unsupported_and_missing():
    repository = Repository()
    with pytest.raises(ValueError, match="on or before"):
        SessionStatisticsService(repository, Routing()).get_stored_snapshot(
            1, date(2026, 10, 17), date(2026, 10, 16)
        )
    with pytest.raises(UnknownSessionStatisticsInstrumentError):
        SessionStatisticsService(repository, Routing()).get_stored_snapshot(
            2, date(2026, 10, 15), date(2026, 10, 16)
        )
    with pytest.raises(SessionStatisticsCapabilityError):
        SessionStatisticsService(repository, Routing(venue="NASDAQ")).get_stored_snapshot(
            1, date(2026, 10, 15), date(2026, 10, 16)
        )
    with pytest.raises(SessionStatisticsUnavailableError):
        SessionStatisticsService(repository, Routing()).get_stored_snapshot(
            1, date(2026, 10, 15), date(2026, 10, 16)
        )
