"""Reference-rate catalog and canonical daily-history use cases."""
from __future__ import annotations

from datetime import datetime
import math

from api.repositories.price_bar_repository import (
    PriceBarRefreshRepository,
    PriceBarWriteRecord,
)
from api.repositories.reference_rate_repository import (
    ReferenceRateInstrumentRecord,
    ReferenceRateListQuery,
    ReferenceRateListResult,
    ReferenceRateRepository,
    ReferenceRateWrite,
    REFERENCE_RATE_PRICE_BASIS,
)
from api.services.price_refresh_service import PriceRefreshWriteResult
from trading_engine.types import PriceFrame


YAHOO_FINANCE_SOURCE = "yahoo_finance"
YAHOO_REFERENCE_RATES = (
    ReferenceRateWrite(
        symbol="BTC-USD",
        base_asset="BTC",
        base_asset_name="Bitcoin",
        base_asset_type="crypto",
        quote_asset="USD",
        quote_asset_name="United States Dollar",
        quote_asset_type="fiat",
        source=YAHOO_FINANCE_SOURCE,
    ),
    ReferenceRateWrite(
        symbol="ETH-USD",
        base_asset="ETH",
        base_asset_name="Ethereum",
        base_asset_type="crypto",
        quote_asset="USD",
        quote_asset_name="United States Dollar",
        quote_asset_type="fiat",
        source=YAHOO_FINANCE_SOURCE,
    ),
)


class ReferenceRateSyncError(ValueError):
    pass


class ReferenceRateService:
    def __init__(
        self,
        catalog_repository: ReferenceRateRepository,
        price_repository: PriceBarRefreshRepository | None = None,
    ) -> None:
        self._catalog_repository = catalog_repository
        self._price_repository = price_repository

    def sync_catalog(
        self, symbols: tuple[str, ...] | None = None
    ) -> tuple[ReferenceRateInstrumentRecord, ...]:
        definitions = {row.symbol: row for row in YAHOO_REFERENCE_RATES}
        requested = (
            tuple(definitions)
            if symbols is None
            else tuple(dict.fromkeys(symbol.upper().strip() for symbol in symbols))
        )
        unknown = sorted(set(requested) - set(definitions))
        if unknown:
            raise ReferenceRateSyncError(
                f"Unsupported Yahoo Finance reference-rate symbols: {unknown}"
            )
        return tuple(
            self._catalog_repository.upsert_reference_rate(definitions[symbol])
            for symbol in requested
        )

    def get_instrument(self, symbol: str) -> ReferenceRateInstrumentRecord | None:
        return self._catalog_repository.get_reference_rate(symbol)

    def list_reference_rates(
        self,
        *,
        search: str | None = None,
        base_asset: str | None = None,
        quote_asset: str | None = None,
        is_active: bool | None = True,
        offset: int = 0,
        limit: int = 50,
    ) -> ReferenceRateListResult:
        return self._catalog_repository.list_reference_rates(
            ReferenceRateListQuery(
                search=search.strip() if search else None,
                base_asset=base_asset.upper().strip() if base_asset else None,
                quote_asset=quote_asset.upper().strip() if quote_asset else None,
                is_active=is_active,
                offset=offset,
                limit=limit,
            )
        )

    def store_history(
        self,
        instrument: ReferenceRateInstrumentRecord,
        prices: PriceFrame,
        *,
        fetched_at: datetime,
    ) -> PriceRefreshWriteResult:
        if self._price_repository is None:
            raise ReferenceRateSyncError(
                "Price repository is required to store reference-rate history"
            )
        if fetched_at.tzinfo is None:
            raise ReferenceRateSyncError(
                "Reference-rate history fetched_at must be timezone-aware"
            )
        if prices.symbol.upper() != instrument.symbol.upper():
            raise ReferenceRateSyncError(
                f"Price history for {prices.symbol} cannot update {instrument.symbol}"
            )

        records: list[PriceBarWriteRecord] = []
        seen_dates = set()
        rejected = 0
        for index, row in prices.data.iterrows():
            trading_date = index.date() if hasattr(index, "date") else index
            volume = row.get("volume")
            volume_value = None if volume is None else float(volume)
            values = tuple(float(row[column]) for column in ("open", "high", "low", "close"))
            valid = (
                trading_date not in seen_dates
                and all(math.isfinite(value) and value > 0 for value in values)
                and values[1] >= values[2]
                and (
                    volume_value is None
                    or (math.isfinite(volume_value) and volume_value >= 0)
                )
            )
            seen_dates.add(trading_date)
            if not valid:
                rejected += 1
                continue
            records.append(PriceBarWriteRecord(
                instrument_id=instrument.id,
                trading_date=trading_date,
                open=values[0],
                high=values[1],
                low=values[2],
                close=values[3],
                volume=volume_value,
                currency=instrument.quote_asset,
                price_scale=1,
                price_basis=REFERENCE_RATE_PRICE_BASIS,
                source=YAHOO_FINANCE_SOURCE,
                fetched_at=fetched_at,
            ))
        stored = self._price_repository.upsert_bars(records)
        return PriceRefreshWriteResult(
            input_rows=len(prices.data),
            rejected_rows=rejected,
            stored_rows=stored,
        )
