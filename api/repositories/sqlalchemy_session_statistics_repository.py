"""SQLAlchemy persistence for immutable Instrument session statistics."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import (
    Instrument,
    InstrumentSessionStatisticMetric,
    InstrumentSessionStatisticSnapshot,
    Venue,
)
from api.instrument_symbols import canonical_symbol_expression
from api.repositories.session_statistics_repository import (
    SessionStatisticInstrumentRecord,
    SessionStatisticMetricRecord,
    SessionStatisticSnapshotRecord,
    SessionStatisticSnapshotWrite,
)
from api.session_statistics import SESSION_STATISTIC_METRIC_CODES


class SqlAlchemySessionStatisticsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_instrument(
        self, instrument_id: int
    ) -> SessionStatisticInstrumentRecord | None:
        row = self._session.execute(
            select(
                Instrument.id,
                canonical_symbol_expression(),
                Instrument.instrument_type,
                Venue.code.label("venue_code"),
                Instrument.currency,
            )
            .outerjoin(Venue, Venue.id == Instrument.venue_id)
            .where(Instrument.id == instrument_id, Instrument.is_active.is_(True))
        ).one_or_none()
        if row is None:
            return None
        return SessionStatisticInstrumentRecord(
            instrument_id=row.id,
            symbol=row.symbol,
            instrument_type=row.instrument_type,
            venue_code=row.venue_code,
            currency=row.currency,
        )

    def store_snapshot(self, record: SessionStatisticSnapshotWrite) -> int:
        expected = set(SESSION_STATISTIC_METRIC_CODES)
        received = set(record.metrics)
        if received != expected or len(record.metrics) != len(expected):
            raise ValueError("Session statistics must contain exactly 64 metrics")
        if self._session.get(Instrument, record.instrument_id) is None:
            raise ValueError(
                f"Session statistics reference unknown instrument: {record.instrument_id}"
            )
        snapshot = InstrumentSessionStatisticSnapshot(
            instrument_id=record.instrument_id,
            period_start=record.period_start,
            period_end=record.period_end,
            source=record.source,
            schema_version=record.schema_version,
            fetched_at=record.fetched_at,
            metrics=[
                InstrumentSessionStatisticMetric(
                    metric_code=code,
                    value=record.metrics[code],
                )
                for code in SESSION_STATISTIC_METRIC_CODES
            ],
        )
        self._session.add(snapshot)
        self._session.flush()
        return snapshot.id

    def get_latest_snapshot(
        self, instrument_id: int, period_start: date, period_end: date
    ) -> SessionStatisticSnapshotRecord | None:
        snapshot = self._session.scalar(
            select(InstrumentSessionStatisticSnapshot)
            .where(
                InstrumentSessionStatisticSnapshot.instrument_id == instrument_id,
                InstrumentSessionStatisticSnapshot.period_start == period_start,
                InstrumentSessionStatisticSnapshot.period_end == period_end,
            )
            .order_by(
                InstrumentSessionStatisticSnapshot.fetched_at.desc(),
                InstrumentSessionStatisticSnapshot.id.desc(),
            )
            .limit(1)
        )
        if snapshot is None:
            return None
        values = {metric.metric_code: metric.value for metric in snapshot.metrics}
        return SessionStatisticSnapshotRecord(
            snapshot_id=snapshot.id,
            instrument_id=snapshot.instrument_id,
            period_start=snapshot.period_start,
            period_end=snapshot.period_end,
            source=snapshot.source,
            schema_version=snapshot.schema_version,
            fetched_at=snapshot.fetched_at,
            metrics=tuple(
                SessionStatisticMetricRecord(code=code, value=values[code])
                for code in SESSION_STATISTIC_METRIC_CODES
            ),
        )
