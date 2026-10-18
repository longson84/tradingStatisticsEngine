"""Canonical daily trading activity with fetch-time-guarded upserts."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from api.db.models import Instrument, InstrumentDailyTradeStatistic, Venue
from api.instrument_symbols import canonical_symbol_expression
from api.repositories.trade_statistics_repository import (
    DailyTradeStatisticRecord,
    DailyTradeStatisticWriteRecord,
    TradeStatisticInstrumentRecord,
)
from api.trade_statistics import (
    TRADE_STATISTIC_SCHEMA_VERSION,
    TRADE_STATISTIC_STORAGE_COLUMNS,
)


_WRITE_BATCH_SIZE = 1_000
_AVERAGE_COLUMNS = frozenset({"average_buy_trade_volume", "average_sell_trade_volume"})


class SqlAlchemyTradeStatisticsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_instrument(self, instrument_id: int) -> TradeStatisticInstrumentRecord | None:
        row = self._session.execute(
            select(
                Instrument.id, canonical_symbol_expression(),
                Instrument.instrument_type, Venue.code.label("venue_code"),
                Instrument.currency,
            )
            .outerjoin(Venue, Venue.id == Instrument.venue_id)
            .where(Instrument.id == instrument_id, Instrument.is_active.is_(True))
        ).one_or_none()
        if row is None:
            return None
        return TradeStatisticInstrumentRecord(
            instrument_id=row.id, symbol=row.symbol,
            instrument_type=row.instrument_type, venue_code=row.venue_code,
            currency=row.currency,
        )

    def upsert_rows(self, records: Iterable[DailyTradeStatisticWriteRecord]) -> int:
        """Validate the whole batch, then write in the caller's transaction."""
        values = tuple(records)
        if not values:
            return 0
        # Materialize and validate every row before querying or issuing any write.
        rows = [self._write_values(record) for record in values]
        instrument_ids = {record.instrument_id for record in values}
        if len(instrument_ids) != 1:
            raise ValueError("Daily trade statistics must reference one instrument")
        if len({record.trading_date for record in values}) != len(values):
            raise ValueError("Daily trade statistics contain duplicate trading dates")
        instrument_id = values[0].instrument_id
        if self._session.get(Instrument, instrument_id) is None:
            raise ValueError(f"Daily trade statistics reference unknown instrument: {instrument_id}")
        dialect = self._session.get_bind().dialect.name
        if dialect == "postgresql":
            insert_factory = postgresql_insert
        elif dialect == "sqlite":
            insert_factory = sqlite_insert
        else:
            raise ValueError(f"Unsupported daily trade statistics write dialect: {dialect}")
        affected = 0
        for start in range(0, len(rows), _WRITE_BATCH_SIZE):
            statement = insert_factory(InstrumentDailyTradeStatistic).values(
                rows[start:start + _WRITE_BATCH_SIZE]
            )
            statement = statement.on_conflict_do_update(
                index_elements=(
                    InstrumentDailyTradeStatistic.instrument_id,
                    InstrumentDailyTradeStatistic.trading_date,
                ),
                set_={name: getattr(statement.excluded, name) for name in (
                    "source", "schema_version", "fetched_at", *TRADE_STATISTIC_STORAGE_COLUMNS,
                )},
                where=statement.excluded.fetched_at >= InstrumentDailyTradeStatistic.fetched_at,
            ).returning(InstrumentDailyTradeStatistic.id)
            result = self._session.execute(statement)
            affected += len(result.scalars().all())
        return affected

    @staticmethod
    def _write_values(record: DailyTradeStatisticWriteRecord) -> dict[str, object]:
        if type(record.instrument_id) is not int or record.instrument_id <= 0:
            raise ValueError("Daily trade statistics require a positive instrument id")
        if type(record.trading_date) is not date:
            raise ValueError("Daily trade statistics require a trading date")
        if not isinstance(record.source, str) or not record.source.strip() or len(record.source) > 100:
            raise ValueError("Daily trade statistics require a source of at most 100 characters")
        if type(record.schema_version) is not int or record.schema_version != TRADE_STATISTIC_SCHEMA_VERSION:
            raise ValueError("Unsupported daily trade statistics schema version")
        if not isinstance(record.fetched_at, datetime) or record.fetched_at.utcoffset() is None:
            raise ValueError("Daily trade statistics require a timezone-aware fetched_at")
        result = {
            "instrument_id": record.instrument_id, "trading_date": record.trading_date,
            "source": record.source, "schema_version": record.schema_version,
            "fetched_at": record.fetched_at.astimezone(UTC),
        }
        for name in TRADE_STATISTIC_STORAGE_COLUMNS:
            value = getattr(record, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError(f"Daily trade statistics {name} must be a finite Decimal")
            if name != "total_net_trade_volume" and value < 0:
                raise ValueError(f"Daily trade statistics {name} must be non-negative")
            scale = 18 if name in _AVERAGE_COLUMNS else 6
            if value.copy_abs() >= Decimal(10) ** (38 - scale):
                raise ValueError(f"Daily trade statistics {name} exceeds Numeric(38, {scale})")
            # Do not let the process-wide Decimal precision round large values.
            with localcontext() as context:
                # One guard digit also permits rejecting a value whose rounding
                # would exceed the fixed-point integer capacity without InvalidOperation.
                context.prec = 39
                if value.quantize(Decimal(1).scaleb(-scale)) != value:
                    raise ValueError(f"Daily trade statistics {name} exceeds {scale} decimal places")
            result[name] = value
        return result

    def list_rows(
        self, instrument_id: int, start: date, end: date,
    ) -> tuple[DailyTradeStatisticRecord, ...]:
        rows = self._session.scalars(
            select(InstrumentDailyTradeStatistic)
            .where(
                InstrumentDailyTradeStatistic.instrument_id == instrument_id,
                InstrumentDailyTradeStatistic.trading_date >= start,
                InstrumentDailyTradeStatistic.trading_date <= end,
            )
            .order_by(InstrumentDailyTradeStatistic.trading_date)
            .execution_options(populate_existing=True)
        )
        return tuple(DailyTradeStatisticRecord(
            instrument_id=row.instrument_id, trading_date=row.trading_date,
            source=row.source, schema_version=row.schema_version,
            fetched_at=(row.fetched_at.replace(tzinfo=UTC)
                        if row.fetched_at.tzinfo is None else row.fetched_at.astimezone(UTC)),
            **{name: getattr(row, name) for name in TRADE_STATISTIC_STORAGE_COLUMNS},
        ) for row in rows)
