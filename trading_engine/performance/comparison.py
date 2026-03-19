"""Comparison framework — unified batch/sweep/multi-strategy runner.

run_comparison() takes N BacktestConfigs + pre-fetched prices,
runs each one, and collects results + errors. Partial failure:
individual config failures are collected, not raised.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from trading_engine.types import (
    BacktestConfig,
    ComparisonReport,
    ConfigError,
    Portfolio,
    PortfolioResult,
    PriceFrame,
)
from trading_engine.portfolio.simulation import run_portfolio


def run_comparison(
    configs: list[BacktestConfig],
    prices: dict[str, PriceFrame],
    max_workers: int = 1,
) -> ComparisonReport:
    """Run N backtest configurations and collect results.

    Args:
        configs: List of backtest configurations to run.
        prices: Pre-fetched price data (caller is responsible for fetching).
        max_workers: Number of parallel workers (1 = sequential).

    Returns:
        ComparisonReport with results + errors. Never raises for individual
        config failures — those are collected in errors.

    Raises:
        ValueError: If configs list is empty.
    """
    if not configs:
        raise ValueError("No configs provided to run_comparison")

    results: list[PortfolioResult] = []
    successful_configs: list[BacktestConfig] = []
    errors: list[tuple[BacktestConfig, Exception]] = []

    if max_workers <= 1:
        for config in configs:
            result, error = _run_single(config, prices)
            if error is not None:
                errors.append((config, error))
            else:
                results.append(result)
                successful_configs.append(config)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_run_single, config, prices): config
                for config in configs
            }
            for future in as_completed(futures):
                config = futures[future]
                result, error = future.result()
                if error is not None:
                    errors.append((config, error))
                else:
                    results.append(result)
                    successful_configs.append(config)

    return ComparisonReport(
        results=results,
        configs=successful_configs,
        errors=errors,
    )


def _run_single(
    config: BacktestConfig,
    prices: dict[str, PriceFrame],
) -> tuple[PortfolioResult | None, Exception | None]:
    """Run a single backtest config. Returns (result, None) or (None, error)."""
    try:
        # Filter prices to the config's date range and symbols
        filtered: dict[str, PriceFrame] = {}
        for symbol in config.symbols:
            if symbol not in prices:
                raise ConfigError(f"No price data for symbol: {symbol}")

            pf = prices[symbol]
            mask = (pf.data.index >= str(config.start)) & (
                pf.data.index <= str(config.end)
            )
            filtered_data = pf.data.loc[mask]

            if filtered_data.empty:
                raise ConfigError(
                    f"No data for {symbol} in range {config.start} to {config.end}"
                )

            filtered[symbol] = PriceFrame(
                symbol=symbol, data=filtered_data, source=pf.source
            )

        portfolio = Portfolio(
            initial_capital=1000.0,
            strategy=config.strategy,
        )
        result = run_portfolio(portfolio, filtered)
        return result, None

    except Exception as e:
        return None, e
