"""Persist normalized participant flows by exact Instrument identity."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pandas as pd

from api.instrument_data_routing import (
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)
from api.repositories.instrument_flow_repository import (
    InstrumentFlowRepository,
    InstrumentFlowWriteRecord,
    ParticipantType,
)
from api.repositories.instrument_routing_repository import InstrumentRoutingRepository
from api.services.instrument_flow_service import (
    InstrumentFlowCapabilityError,
    UnknownFlowInstrumentError,
)


_FLOW_COLUMNS = (
    "symbol", "date", "buy_volume", "buy_value", "sell_volume", "sell_value",
    "net_volume", "net_value",
)


class InstrumentFlowWriteService:
    def __init__(
        self,
        repository: InstrumentFlowRepository,
        routing_repository: InstrumentRoutingRepository,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository

    def store_observations(
        self,
        instrument_id: int,
        participant_type: ParticipantType,
        frame: pd.DataFrame,
        *,
        source: str,
        fetched_at: datetime,
    ) -> int:
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        instrument = self._repository.get_instrument(instrument_id)
        metadata = self._routing_repository.get_instrument_route_metadata(instrument_id)
        if instrument is None or metadata is None:
            raise UnknownFlowInstrumentError(f"Unknown instrument: {instrument_id}")
        try:
            route = resolve_instrument_data_route(metadata)
        except UnsupportedInstrumentRouteError as exc:
            raise InstrumentFlowCapabilityError(
                f"Instrument {instrument_id} does not support foreign_flow"
            ) from exc
        if participant_type != "foreign" or "foreign_flow" not in route.capabilities:
            raise InstrumentFlowCapabilityError(
                f"Instrument {instrument_id} does not support foreign_flow"
            )
        missing = [column for column in _FLOW_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"Flow observations are missing columns: {missing}")
        symbols = {
            str(symbol).upper().strip() for symbol in frame["symbol"].dropna().tolist()
        }
        if symbols != {route.provider_symbol}:
            raise ValueError(
                f"Flow observations for {sorted(symbols)} cannot update instrument "
                f"{instrument_id} ({route.provider_symbol})"
            )
        records = (
            InstrumentFlowWriteRecord(
                instrument_id=instrument_id,
                trading_date=pd.Timestamp(row["date"]).date(),
                participant_type=participant_type,
                buy_volume=Decimal(str(row["buy_volume"])),
                buy_value=Decimal(str(row["buy_value"])),
                sell_volume=Decimal(str(row["sell_volume"])),
                sell_value=Decimal(str(row["sell_value"])),
                net_volume=Decimal(str(row["net_volume"])),
                net_value=Decimal(str(row["net_value"])),
                currency=route.currency,
                source=source,
                fetched_at=fetched_at,
            )
            for _, row in frame.iterrows()
        )
        return self._repository.upsert_observations(records)
