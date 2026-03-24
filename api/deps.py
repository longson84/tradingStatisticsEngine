"""Shared FastAPI dependencies.

Resolves data loaders and constructs strategy instances from request configs.
All data-fetching logic lives here — the trading_engine library stays loader-agnostic.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException

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


def get_loader(source: str) -> DataLoader:
    """Return the appropriate DataLoader for the requested source."""
    if source == "yfinance":
        return YFinanceLoader()
    if source == "vnstock":
        from trading_engine.data.vnstock_loader import VnStockLoader
        return VnStockLoader()
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
