"""Persist explicitly downloaded equity histories by canonical instrument ID."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from api.instrument_data_routing import (
    InstrumentDataRoute,
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)
from api.repositories.instrument_routing_repository import (
    InstrumentRoutingRepository,
)
from api.repositories.price_bar_repository import (
    PriceBarRepository,
    PriceBarWriteRecord,
    PriceInstrumentRecord,
)
from trading_engine.types import PriceFrame


class UnknownCompanyError(ValueError):
    pass


class CompanyPriceService:
    def __init__(
        self,
        repository: PriceBarRepository,
        routing_repository: InstrumentRoutingRepository,
    ):
        self._repository = repository
        self._routing_repository = routing_repository

    def store_downloaded_histories(
        self,
        prices: dict[int, PriceFrame],
        *,
        fetched_at: datetime,
    ) -> int:
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        targets: dict[int, PriceInstrumentRecord] = {}
        routes: dict[int, InstrumentDataRoute] = {}
        for instrument_id, frame in prices.items():
            target = self._repository.get_instrument(instrument_id)
            if target is None:
                raise ValueError(f"Unknown equity instrument: {instrument_id}")
            route = self._route(instrument_id)
            if route.fundamental_adapter is None:
                raise ValueError(f"Unsupported equity instrument: {instrument_id}")
            if frame.symbol.upper().strip() != route.provider_symbol:
                raise ValueError(
                    f"Price history for {frame.symbol} cannot update instrument "
                    f"{instrument_id} ({route.provider_symbol})"
                )
            targets[instrument_id] = target
            routes[instrument_id] = route
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
                source=frame.source,
                fetched_at=fetched_at,
            )
            for instrument_id, frame in prices.items()
            for target in (targets[instrument_id],)
            for route in (routes[instrument_id],)
            for index, row in frame.data.iterrows()
        )
        return self._repository.upsert_bars(records)

    def _route(self, instrument_id: int) -> InstrumentDataRoute:
        metadata = self._routing_repository.get_instrument_route_metadata(
            instrument_id
        )
        if metadata is None:
            raise UnknownCompanyError(f"Unknown instrument: {instrument_id}")
        try:
            return resolve_instrument_data_route(metadata)
        except UnsupportedInstrumentRouteError as exc:
            raise UnknownCompanyError(str(exc)) from exc
