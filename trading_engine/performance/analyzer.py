"""Performance analysis — pure functions over PortfolioResult."""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading_engine.types import (
    PerformanceReport,
    PortfolioResult,
    Trade,
    TradeDistribution,
)


def analyze_performance(result: PortfolioResult) -> PerformanceReport:
    """Compute a full performance report from a portfolio simulation result.

    All metrics are computed from the equity curve and trade list.
    Handles the edge case of 0 trades gracefully (all metrics = 0).
    """
    equity = result.equity_curve
    trades = result.trades

    if equity.empty or len(equity) < 2:
        return _empty_report()

    # Core metrics from equity curve
    total_return_pct = float((equity.iloc[-1] / equity.iloc[0] - 1) * 100)
    cagr = _compute_cagr(equity)
    sharpe = _compute_sharpe(equity)
    max_dd = _compute_max_drawdown(equity)

    # Trade-level metrics
    closed_trades = [t for t in trades if t.exit_date is not None]

    if not closed_trades:
        return PerformanceReport(
            total_return_pct=total_return_pct,
            cagr=cagr,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            win_rate=0.0,
            avg_return_per_trade=0.0,
            avg_holding_days=0.0,
            monthly_returns=pd.DataFrame(),
            annual_returns=pd.Series(dtype=float),
            trade_distribution=_empty_distribution(),
        )

    returns = [t.return_pct for t in closed_trades if t.return_pct is not None]
    wins = [r for r in returns if r > 0]
    win_rate = len(wins) / len(returns) * 100 if returns else 0.0
    avg_return = float(np.mean(returns)) if returns else 0.0

    holding_days = [t.holding_days for t in closed_trades if t.holding_days is not None]
    avg_holding = float(np.mean(holding_days)) if holding_days else 0.0

    monthly = _compute_monthly_returns(equity)
    annual = _compute_annual_returns(equity)
    distribution = _compute_distribution(closed_trades)

    return PerformanceReport(
        total_return_pct=total_return_pct,
        cagr=cagr,
        sharpe_ratio=sharpe,
        max_drawdown_pct=max_dd,
        win_rate=win_rate,
        avg_return_per_trade=avg_return,
        avg_holding_days=avg_holding,
        monthly_returns=monthly,
        annual_returns=annual,
        trade_distribution=distribution,
    )


def _compute_cagr(equity: pd.Series) -> float:
    """Compound annual growth rate."""
    if equity.iloc[0] <= 0:
        return 0.0
    total_return = equity.iloc[-1] / equity.iloc[0]
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    years = days / 365.25
    return float((total_return ** (1 / years) - 1) * 100)


def _compute_sharpe(equity: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Annualized Sharpe ratio from daily returns."""
    daily_returns = equity.pct_change().dropna()
    if daily_returns.empty or daily_returns.std() == 0:
        return 0.0
    excess = daily_returns - risk_free_rate / 252
    return float(excess.mean() / excess.std() * np.sqrt(252))


def _compute_max_drawdown(equity: pd.Series) -> float:
    """Maximum drawdown as a percentage."""
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    return float(drawdown.min() * 100)


def _compute_monthly_returns(equity: pd.Series) -> pd.DataFrame:
    """Monthly return matrix (year x month) for heatmap display."""
    monthly = equity.resample("ME").last().pct_change() * 100
    if monthly.empty:
        return pd.DataFrame()

    df = pd.DataFrame({
        "year": monthly.index.year,
        "month": monthly.index.month,
        "return": monthly.values,
    })
    pivot = df.pivot_table(index="year", columns="month", values="return")
    pivot.columns = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ][:len(pivot.columns)]
    return pivot


def _compute_annual_returns(equity: pd.Series) -> pd.Series:
    """Annual returns."""
    annual = equity.resample("YE").last().pct_change() * 100
    annual.index = annual.index.year
    return annual.dropna()


def _compute_distribution(trades: list[Trade]) -> TradeDistribution:
    """Compute return/MAE/MFE distribution buckets."""
    returns = [t.return_pct for t in trades if t.return_pct is not None]
    maes = [t.mae_pct for t in trades if t.mae_pct is not None]
    mfes = [t.mfe_pct for t in trades if t.mfe_pct is not None]

    return_buckets = _bucket(returns, [
        ("< -20%", float("-inf"), -20),
        ("-20 to -10%", -20, -10),
        ("-10 to -5%", -10, -5),
        ("-5 to 0%", -5, 0),
        ("0 to 5%", 0, 5),
        ("5 to 10%", 5, 10),
        ("10 to 20%", 10, 20),
        ("> 20%", 20, float("inf")),
    ])

    mae_buckets = _bucket(maes, [
        ("0 to -5%", -5, 0),
        ("-5 to -10%", -10, -5),
        ("-10 to -20%", -20, -10),
        ("< -20%", float("-inf"), -20),
    ])

    mfe_buckets = _bucket(mfes, [
        ("0 to 5%", 0, 5),
        ("5 to 10%", 5, 10),
        ("10 to 20%", 10, 20),
        ("> 20%", 20, float("inf")),
    ])

    return TradeDistribution(
        return_buckets=return_buckets,
        mae_buckets=mae_buckets,
        mfe_buckets=mfe_buckets,
    )


def _bucket(
    values: list[float],
    buckets: list[tuple[str, float, float]],
) -> dict[str, int]:
    """Count values falling into each bucket."""
    result = {label: 0 for label, _, _ in buckets}
    for v in values:
        for label, lo, hi in buckets:
            if lo <= v < hi:
                result[label] += 1
                break
    return result


def _empty_distribution() -> TradeDistribution:
    return TradeDistribution(
        return_buckets={}, mae_buckets={}, mfe_buckets={}
    )


def _empty_report() -> PerformanceReport:
    return PerformanceReport(
        total_return_pct=0.0,
        cagr=0.0,
        sharpe_ratio=0.0,
        max_drawdown_pct=0.0,
        win_rate=0.0,
        avg_return_per_trade=0.0,
        avg_holding_days=0.0,
        monthly_returns=pd.DataFrame(),
        annual_returns=pd.Series(dtype=float),
        trade_distribution=_empty_distribution(),
    )
