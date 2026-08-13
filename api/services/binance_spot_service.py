"""Binance Spot synchronization use cases over persistence-neutral contracts."""
from __future__ import annotations

from datetime import datetime

from api.providers.binance_spot import BinanceDailyKline, BinanceSpotCatalog
from api.repositories.crypto_instrument_repository import (
    CryptoAssetWrite,
    CryptoInstrumentRepository,
    SpotCatalogSyncResult,
    SpotCatalogWrite,
    SpotInstrumentRecord,
    SpotInstrumentWrite,
    SpotInstrumentListQuery,
    SpotInstrumentListResult,
)
from api.repositories.price_bar_repository import (
    PriceBarRefreshRepository,
    PriceBarWriteRecord,
)
from api.services.price_refresh_service import PriceRefreshWriteResult


BINANCE_SPOT_VENUE = "BINANCE_SPOT"
BINANCE_SPOT_UNIVERSE = "BINANCE_SPOT"
BINANCE_SPOT_SOURCE = "binance_spot_exchange_info"
BINANCE_PRICE_BASIS = "venue_unadjusted"

_STABLECOINS = {
    "BUSD",
    "DAI",
    "FDUSD",
    "TUSD",
    "USDC",
    "USDP",
    "USDT",
}
_FIAT_ASSETS = {
    "ARS",
    "AUD",
    "BRL",
    "EUR",
    "GBP",
    "IDR",
    "JPY",
    "MXN",
    "NGN",
    "PLN",
    "RON",
    "RUB",
    "TRY",
    "UAH",
    "USD",
    "VND",
    "ZAR",
}


class BinanceSpotSyncError(ValueError):
    pass


class BinanceSpotService:
    def __init__(
        self,
        catalog_repository: CryptoInstrumentRepository,
        price_repository: PriceBarRefreshRepository | None = None,
    ) -> None:
        self._catalog_repository = catalog_repository
        self._price_repository = price_repository

    def sync_catalog(self, catalog: BinanceSpotCatalog) -> SpotCatalogSyncResult:
        if catalog.fetched_at.tzinfo is None:
            raise BinanceSpotSyncError(
                "Binance catalog fetched_at must be timezone-aware"
            )
        if not catalog.symbols:
            raise BinanceSpotSyncError("Binance catalog must not be empty")
        symbols: set[str] = set()
        asset_codes: set[str] = set()
        instruments: list[SpotInstrumentWrite] = []
        for row in catalog.symbols:
            if row.symbol in symbols:
                raise BinanceSpotSyncError(
                    f"Binance catalog contains duplicate symbol {row.symbol}"
                )
            if row.base_asset == row.quote_asset:
                raise BinanceSpotSyncError(
                    f"Binance catalog contains a self-quoted market {row.symbol}"
                )
            symbols.add(row.symbol)
            asset_codes.update((row.base_asset, row.quote_asset))
            instruments.append(
                SpotInstrumentWrite(
                    symbol=row.symbol,
                    base_asset=row.base_asset,
                    quote_asset=row.quote_asset,
                    is_active=(
                        row.status == "TRADING" and row.is_spot_trading_allowed
                    ),
                    price_tick_size=row.price_tick_size,
                    quantity_step_size=row.quantity_step_size,
                    minimum_quantity=row.minimum_quantity,
                    minimum_notional=row.minimum_notional,
                )
            )
        assets = tuple(
            CryptoAssetWrite(
                code=code,
                name=code,
                asset_type=_asset_type(code),
            )
            for code in sorted(asset_codes)
        )
        return self._catalog_repository.sync_spot_catalog(SpotCatalogWrite(
            venue_code=BINANCE_SPOT_VENUE,
            venue_name="Binance Spot",
            universe_code=BINANCE_SPOT_UNIVERSE,
            universe_name="Binance Spot",
            source=BINANCE_SPOT_SOURCE,
            fetched_at=catalog.fetched_at,
            assets=assets,
            instruments=tuple(instruments),
        ))

    def list_instruments(
        self,
        *,
        symbols: tuple[str, ...] = (),
        quote_assets: tuple[str, ...] = (),
    ) -> tuple[SpotInstrumentRecord, ...]:
        return self._catalog_repository.list_spot_instruments(
            BINANCE_SPOT_VENUE,
            symbols=tuple(value.upper().strip() for value in symbols),
            quote_assets=tuple(value.upper().strip() for value in quote_assets),
        )

    def list_markets(
        self,
        *,
        search: str | None = None,
        quote_asset: str | None = None,
        is_active: bool | None = True,
        offset: int = 0,
        limit: int = 50,
    ) -> SpotInstrumentListResult:
        return self._catalog_repository.list_spot_catalog(
            SpotInstrumentListQuery(
                venue_code=BINANCE_SPOT_VENUE,
                search=search.strip() if search else None,
                quote_asset=quote_asset.upper().strip() if quote_asset else None,
                is_active=is_active,
                offset=offset,
                limit=limit,
            ),
        )

    def store_history(
        self,
        instrument: SpotInstrumentRecord,
        klines: tuple[BinanceDailyKline, ...],
        *,
        fetched_at: datetime,
    ) -> PriceRefreshWriteResult:
        if self._price_repository is None:
            raise BinanceSpotSyncError(
                "Price repository is required to store history"
            )
        if fetched_at.tzinfo is None:
            raise BinanceSpotSyncError(
                "Binance history fetched_at must be timezone-aware"
            )
        records: list[PriceBarWriteRecord] = []
        seen_dates = set()
        rejected = 0
        for row in klines:
            valid = (
                row.symbol == instrument.symbol
                and row.trading_date not in seen_dates
                and all(
                    value.is_finite() and value > 0
                    for value in (row.open, row.high, row.low, row.close)
                )
                and row.high >= row.low
                and row.volume.is_finite()
                and row.volume >= 0
            )
            seen_dates.add(row.trading_date)
            if not valid:
                rejected += 1
                continue
            records.append(PriceBarWriteRecord(
                instrument_id=instrument.id,
                trading_date=row.trading_date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
                currency=instrument.quote_asset,
                price_scale=1,
                price_basis=BINANCE_PRICE_BASIS,
                source=row.source,
                fetched_at=fetched_at,
            ))
        stored = self._price_repository.upsert_bars(records)
        return PriceRefreshWriteResult(
            input_rows=len(klines),
            rejected_rows=rejected,
            stored_rows=stored,
        )


def _asset_type(code: str) -> str:
    if code in _STABLECOINS:
        return "stablecoin"
    if code in _FIAT_ASSETS:
        return "fiat"
    return "crypto"
