"""Persistence contract for canonical instrument data-routing metadata."""
from __future__ import annotations

from typing import Protocol

from api.instrument_data_routing import InstrumentRoutingMetadata


class InstrumentRoutingRepository(Protocol):
    def find_instrument_route_metadata(
        self, namespace: str, symbol: str
    ) -> InstrumentRoutingMetadata | None: ...

    def get_instrument_route_metadata(
        self, instrument_id: int
    ) -> InstrumentRoutingMetadata | None: ...

    def get_instrument_routes_metadata(
        self, instrument_ids: tuple[int, ...]
    ) -> tuple[InstrumentRoutingMetadata, ...]: ...
