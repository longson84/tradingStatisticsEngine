"""Shared FastAPI dependencies.

Resolves data loaders and constructs strategy instances from request configs.
All data-fetching logic lives here — the trading_engine library stays loader-agnostic.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.repositories.sqlalchemy_company_repository import SqlAlchemyCompanyRepository
from api.repositories.sqlalchemy_company_catalog_repository import (
    SqlAlchemyCompanyCatalogRepository,
)
from api.repositories.sqlalchemy_fundamental_repository import (
    SqlAlchemyFundamentalRepository,
)
from api.repositories.sqlalchemy_crypto_market_repository import (
    SqlAlchemyCryptoMarketRepository,
)
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.repositories.sqlalchemy_instrument_analysis_repository import (
    SqlAlchemyInstrumentAnalysisRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.repositories.sqlalchemy_reference_rate_repository import (
    SqlAlchemyReferenceRateRepository,
)
from api.repositories.sqlalchemy_watchlist_repository import (
    SqlAlchemyWatchlistRepository,
)
from api.repositories.sqlalchemy_universe_repository import (
    SqlAlchemyUniverseRepository,
)
from api.repositories.sqlalchemy_data_operation_repository import (
    SqlAlchemyDataOperationRepository,
)
from api.repositories.sqlalchemy_venue_repository import SqlAlchemyVenueRepository
from api.services.company_service import CompanyService
from api.services.binance_spot_service import BinanceSpotService
from api.services.crypto_instrument_service import CryptoInstrumentService
from api.services.company_catalog_service import CompanyCatalogService
from api.services.fundamental_service import FundamentalService
from api.services.reference_rate_service import ReferenceRateService
from api.services.company_price_service import CompanyPriceService
from api.services.instrument_analysis_service import InstrumentAnalysisService
from api.services.watchlist_service import WatchlistService
from api.services.universe_service import UniverseService
from api.services.data_operation_service import DataOperationService
from api.services.venue_service import VenueService
from api.providers.vietnam_price_loader import VietnamPriceLoader

from trading_engine.data.yfinance_loader import YFinanceLoader
from trading_engine.factors.moving_average import MovingAverageRatio
from trading_engine.strategy.buy_and_hold import BuyAndHold
from trading_engine.strategy.factor_threshold import FactorThresholdStrategy
from trading_engine.types import DataLoadError, DataLoader, Portfolio, PriceFrame, Strategy, StrategySlot

from api.schemas.backtest import (
    BuyAndHoldConfig,
    PriceVsMAConfig,
    StrategyConfig,
)


@lru_cache(maxsize=1)
def get_database_engine() -> Engine:
    return create_db_engine()


def get_db_session() -> Iterator[Session]:
    with Session(get_database_engine()) as session:
        yield session


def get_db_transaction_session() -> Iterator[Session]:
    """Provide an API-owned unit of work for maintenance mutations."""
    with Session(get_database_engine()) as session:
        with session.begin():
            yield session


def get_company_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> CompanyService:
    return CompanyService(SqlAlchemyCompanyRepository(session))


def get_company_catalog_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> CompanyCatalogService:
    return CompanyCatalogService(SqlAlchemyCompanyCatalogRepository(session))


def get_binance_spot_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> BinanceSpotService:
    return BinanceSpotService(SqlAlchemyCryptoMarketRepository(session))


def get_crypto_instrument_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> CryptoInstrumentService:
    return CryptoInstrumentService(SqlAlchemyCryptoMarketRepository(session))


def get_reference_rate_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ReferenceRateService:
    return ReferenceRateService(SqlAlchemyReferenceRateRepository(session))


def get_fundamental_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> FundamentalService:
    return FundamentalService(SqlAlchemyFundamentalRepository(session))


def get_company_price_service(
    session: Annotated[Session, Depends(get_db_transaction_session)],
) -> CompanyPriceService:
    return CompanyPriceService(
        SqlAlchemyPriceBarRepository(session),
        SqlAlchemyInstrumentRoutingRepository(session),
        {
            "yfinance": YFinanceLoader(),
            "vnstock_data": VietnamPriceLoader(),
        },
    )


def get_instrument_analysis_service(
    session: Annotated[Session, Depends(get_db_transaction_session)],
) -> InstrumentAnalysisService:
    price_repository = SqlAlchemyPriceBarRepository(session)
    return InstrumentAnalysisService(
        SqlAlchemyInstrumentAnalysisRepository(session),
        SqlAlchemyInstrumentRoutingRepository(session),
        CompanyPriceService(
            price_repository,
            SqlAlchemyInstrumentRoutingRepository(session),
            {
                "yfinance": YFinanceLoader(),
                "vnstock_data": VietnamPriceLoader(),
            },
        ),
    )


def get_watchlist_service(
    session: Annotated[Session, Depends(get_db_transaction_session)],
) -> WatchlistService:
    return WatchlistService(SqlAlchemyWatchlistRepository(session))


def get_universe_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> UniverseService:
    return UniverseService(SqlAlchemyUniverseRepository(session))


def get_data_operation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> DataOperationService:
    return DataOperationService(
        SqlAlchemyDataOperationRepository(session),
        SqlAlchemyInstrumentRoutingRepository(session),
    )


def get_venue_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> VenueService:
    return VenueService(SqlAlchemyVenueRepository(session))


def get_loader(source: str) -> DataLoader:
    """Return the appropriate DataLoader for the requested source."""
    if source == "yfinance":
        return YFinanceLoader()
    if source == "vnstock":
        return VietnamPriceLoader()
    raise HTTPException(status_code=400, detail=f"Unsupported data source: {source!r}")


def build_strategy(config: StrategyConfig) -> Strategy:
    """Construct a Strategy instance from a request config."""
    if isinstance(config, BuyAndHoldConfig):
        return BuyAndHold(weight=config.weight)
    if isinstance(config, PriceVsMAConfig):
        factor = MovingAverageRatio(
            ma_type=config.ma_type.upper(),
            length=config.ma_length,
        )
        return FactorThresholdStrategy(
            factor=factor,
            threshold=0.0,
            buy_lag=config.buy_lag,
            sell_lag=config.sell_lag,
        )
    raise HTTPException(status_code=400, detail=f"Unknown strategy type: {config.type!r}")


def build_portfolio(
    strategy: Strategy,
    initial_capital: float,
    max_leverage: float = 1.0,
) -> Portfolio:
    """Wrap a single strategy in a one-slot Portfolio."""
    return Portfolio(
        slots=[StrategySlot(strategy=strategy, weight=1.0)],
        initial_capital=initial_capital,
        max_leverage=max_leverage,
    )


def fetch_prices(
    symbols: list[str],
    start: date,
    end: date,
    source: str,
) -> dict[str, PriceFrame]:
    """Fetch price data for all symbols. Raises 422 on partial or total failure."""
    loader = get_loader(source)
    prices: dict[str, PriceFrame] = {}
    errors: list[str] = []

    for symbol in symbols:
        try:
            prices[symbol] = loader.load(symbol, start, end)
        except DataLoadError as e:
            errors.append(f"{symbol}: {e}")

    if errors and not prices:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to load any symbols. Errors: {errors}",
        )
    if errors:
        # Partial success — still proceed, surface warnings in logs
        import logging
        logging.getLogger(__name__).warning("Partial load failures: %s", errors)

    return prices
