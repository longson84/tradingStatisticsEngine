"""Persist one downloaded history by exact canonical Instrument identity."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from api.instrument_data_routing import resolve_instrument_data_route
from api.repositories.instrument_routing_repository import InstrumentRoutingRepository
from api.repositories.price_bar_repository import PriceBarRepository, PriceBarWriteRecord
from trading_engine.types import PriceFrame


class InstrumentPriceWriteService:
    def __init__(
        self,
        repository: PriceBarRepository,
        routing_repository: InstrumentRoutingRepository,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository

    def store_history(
        self,
        instrument_id: int,
        prices: PriceFrame,
        *,
        fetched_at: datetime,
    ) -> int:
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        target = self._repository.get_instrument(instrument_id)
        metadata = self._routing_repository.get_instrument_route_metadata(
            instrument_id
        )
        if target is None or metadata is None:
            raise ValueError(f"Unknown instrument: {instrument_id}")
        route = resolve_instrument_data_route(metadata)
        if prices.symbol.upper().strip() != route.provider_symbol:
            raise ValueError(
                f"Price history for {prices.symbol} cannot update instrument "
                f"{instrument_id} ({route.provider_symbol})"
            )
        records = (
            PriceBarWriteRecord(
                instrument_id=instrument_id,
                trading_date=pd.Timestamp(index).date(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=(
                    float(row["volume"])
                    if "volume" in row and not pd.isna(row["volume"])
                    else None
                ),
                currency=route.currency,
                price_scale=route.price_scale,
                price_basis=route.price_basis,
                source=prices.source,
                fetched_at=fetched_at,
            )
            for index, row in prices.data.iterrows()
        )
        return self._repository.upsert_bars(records)
