"""Read stored daily activity for an exact requested range without provider access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from api.instrument_data_routing import (
    InstrumentDataRoute,
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)
from api.repositories.instrument_routing_repository import InstrumentRoutingRepository
from api.repositories.trade_statistics_repository import (
    DailyTradeStatisticRecord,
    TradeStatisticInstrumentRecord,
    TradeStatisticsRepository,
)


class UnknownTradeStatisticsInstrumentError(ValueError):
    pass


class TradeStatisticsCapabilityError(ValueError):
    pass


class TradeStatisticsUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class TradeStatisticsData:
    instrument: TradeStatisticInstrumentRecord
    requested_start: date
    requested_end: date
    first_date: date
    last_date: date
    rows: tuple[DailyTradeStatisticRecord, ...]


def resolve_trade_statistics_instrument(
    repository: TradeStatisticsRepository,
    routing_repository: InstrumentRoutingRepository,
    instrument_id: int,
) -> tuple[TradeStatisticInstrumentRecord, InstrumentDataRoute]:
    """Share canonical identity and capability validation across read/write paths."""
    instrument = repository.get_instrument(instrument_id)
    metadata = routing_repository.get_instrument_route_metadata(instrument_id)
    if instrument is None or metadata is None:
        raise UnknownTradeStatisticsInstrumentError(f"Unknown instrument: {instrument_id}")
    try:
        route = resolve_instrument_data_route(metadata)
    except UnsupportedInstrumentRouteError as exc:
        raise TradeStatisticsCapabilityError(
            f"Instrument {instrument_id} does not support trade_history"
        ) from exc
    if "trade_history" not in route.capabilities:
        raise TradeStatisticsCapabilityError(
            f"Instrument {instrument_id} does not support trade_history"
        )
    return instrument, route


class TradeStatisticsService:
    def __init__(
        self,
        repository: TradeStatisticsRepository,
        routing_repository: InstrumentRoutingRepository,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository

    def get_stored_range(
        self, instrument_id: int, start: date, end: date,
    ) -> TradeStatisticsData:
        if start > end:
            raise ValueError("start date must be on or before end date")
        instrument, _ = resolve_trade_statistics_instrument(
            self._repository, self._routing_repository, instrument_id,
        )
        rows = self._repository.list_rows(instrument_id, start, end)
        if not rows:
            raise TradeStatisticsUnavailableError(
                f"No stored daily trade statistics for instrument {instrument_id} "
                f"from {start} through {end}"
            )
        return TradeStatisticsData(
            instrument=instrument, requested_start=start, requested_end=end,
            first_date=rows[0].trading_date, last_date=rows[-1].trading_date,
            rows=rows,
        )
