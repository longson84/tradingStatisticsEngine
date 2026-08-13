"""Shared FastAPI dependencies.

Constructs application services and strategy instances while keeping the
trading_engine library independent from FastAPI and persistence frameworks.
"""
from __future__ import annotations

from functools import lru_cache
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.repositories.sqlalchemy_company_catalog_repository import (
    SqlAlchemyCompanyCatalogRepository,
)
from api.repositories.sqlalchemy_fundamental_repository import (
    SqlAlchemyFundamentalRepository,
)
from api.repositories.sqlalchemy_crypto_instrument_repository import (
    SqlAlchemyCryptoInstrumentRepository,
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
from api.repositories.sqlalchemy_universe_stats_repository import (
    SqlAlchemyUniverseStatsRepository,
)
from api.services.crypto_instrument_service import CryptoInstrumentService
from api.services.company_catalog_service import CompanyCatalogService
from api.services.fundamental_service import FundamentalService
from api.services.reference_rate_service import ReferenceRateService
from api.services.instrument_analysis_service import InstrumentAnalysisService
from api.services.watchlist_service import WatchlistService
from api.services.universe_service import UniverseService
from api.services.data_operation_service import DataOperationService
from api.services.venue_service import VenueService
from api.services.universe_stats_service import UniverseStatsService
from api.services.new_low_analysis_service import NewLowAnalysisService
from trading_engine.factors.moving_average import MovingAverageRatio
from trading_engine.strategy.buy_and_hold import BuyAndHold
from trading_engine.strategy.factor_threshold import FactorThresholdStrategy
from trading_engine.types import Strategy

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


def get_company_catalog_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> CompanyCatalogService:
    return CompanyCatalogService(SqlAlchemyCompanyCatalogRepository(session))


def get_crypto_instrument_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> CryptoInstrumentService:
    return CryptoInstrumentService(SqlAlchemyCryptoInstrumentRepository(session))


def get_reference_rate_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ReferenceRateService:
    return ReferenceRateService(SqlAlchemyReferenceRateRepository(session))


def get_fundamental_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> FundamentalService:
    return FundamentalService(SqlAlchemyFundamentalRepository(session))


def get_instrument_analysis_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> InstrumentAnalysisService:
    return InstrumentAnalysisService(
        SqlAlchemyInstrumentAnalysisRepository(session),
        SqlAlchemyInstrumentRoutingRepository(session),
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


def get_universe_stats_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> UniverseStatsService:
    return UniverseStatsService(
        SqlAlchemyDataOperationRepository(session),
        SqlAlchemyUniverseStatsRepository(session),
    )


def get_new_low_analysis_service(
    instrument_service: Annotated[
        InstrumentAnalysisService, Depends(get_instrument_analysis_service)
    ],
) -> NewLowAnalysisService:
    return NewLowAnalysisService(instrument_service)


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
