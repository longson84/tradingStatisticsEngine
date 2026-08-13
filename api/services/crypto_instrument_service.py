"""Venue-neutral crypto instrument catalog use cases."""
from __future__ import annotations

from api.repositories.crypto_instrument_repository import (
    CryptoInstrumentRepository,
    SpotInstrumentListQuery,
    SpotInstrumentListResult,
)


class CryptoInstrumentService:
    def __init__(self, repository: CryptoInstrumentRepository) -> None:
        self._repository = repository

    def list_instruments(
        self,
        *,
        venue_code: str | None = None,
        search: str | None = None,
        quote_asset: str | None = None,
        is_active: bool | None = True,
        offset: int = 0,
        limit: int = 50,
    ) -> SpotInstrumentListResult:
        return self._repository.list_spot_catalog(SpotInstrumentListQuery(
            venue_code=venue_code.upper().strip() if venue_code else None,
            search=search.strip() if search else None,
            quote_asset=quote_asset.upper().strip() if quote_asset else None,
            is_active=is_active,
            offset=offset,
            limit=limit,
        ))
