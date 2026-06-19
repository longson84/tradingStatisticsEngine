"""Rich single-ticker strategy analytics — all computation lives here.

Entry point: run_single_ticker_analysis()
Returns a SingleTickerAnalysis dataclass that the API route serialises to JSON.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from trading_engine import run_portfolio
from trading_engine.strategy.buy_and_hold import BuyAndHold
from trading_engine.strategy.factor_threshold import FactorThresholdStrategy
from trading_engine.types import Portfolio, PortfolioResult, PriceFrame, Strategy, StrategySlot, Trade


# =============================================================================
# Output dataclasses
# =============================================================================

@dataclass
class PerformanceSummary:
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    current_drawdown_pct: float
    current_drawdown_days: int
    calmar_ratio: float
    win_rate_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    max_consec_losses: int
    best_trade_pct: float
    worst_trade_pct: float
    total_trades: int
    avg_holding_days: float
    profit_factor: float
    time_in_market_pct: float


@dataclass
class CurrentPosition:
    entry_date: str
    entry_price: float
    holding_days: int
    unrealized_return_pct: float | None
    mae_pct: float | None
    mfe_pct: float | None


EARLY_BARS: list[int] = [2, 5, 10]


@dataclass
class TradeRow:
    symbol: str
    direction: str
    entry_date: str
    exit_date: str | None
    entry_price: float
    exit_price: float | None
    return_pct: float | None
    holding_days: int | None
    mae_pct: float | None
    mfe_pct: float | None
    mae_price: float | None
    mfe_price: float | None
    retracement_pct: float | None
    early_returns: dict[str, float | None] = field(default_factory=dict)


@dataclass
class DistributionRow:
    percentile: int
    value_pct: float
    cumulative_count: int



STAT_PERCENTILES: list[int] = [5, 10, 15, 20, 25, 50, 75, 90, 95]
DIST_PERCENTILES: list[int] = [5, 10, 15, 20, 25, 50, 75, 90, 95, 98, 100]


@dataclass
class MonthlyStatRow:
    label: str
    count: int
    p5: float | None
    p10: float | None
    p15: float | None
    p20: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p90: float | None
    p95: float | None


@dataclass
class HealthRow:
    year: int
    trades: int
    p5: float | None
    p10: float | None
    p15: float | None
    p20: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p90: float | None
    p95: float | None


@dataclass
class UndercutDistributionRow:
    """One row in the undercut distribution.

    Counts how many winning trades had exactly `undercuts` temporary
    dips below MA that recovered (without triggering the exit countdown).
    """

    undercuts: int
    trade_count: int
    pct_of_winners: float


@dataclass
class SingleTickerAnalysis:
    symbol: str
    strategy_label: str
    from_date: str
    to_date: str
    total_bars: int
    current_position: CurrentPosition | None
    strategy: PerformanceSummary
    bah: PerformanceSummary
    trades: list[TradeRow]
    return_percentiles: list[DistributionRow]
    mae_percentiles_winners: list[DistributionRow]
    mfe_percentiles_winners: list[DistributionRow]
    mfe_percentiles_losers: list[DistributionRow]
    monthly_returns_strategy: dict[str, dict[str, float | None]]
    monthly_returns_bah: dict[str, dict[str, float | None]]
    monthly_stats_by_calendar: list[MonthlyStatRow]
    monthly_stats_by_entry_month: list[MonthlyStatRow]
    health_by_year: list[HealthRow]
    equity_curve_strategy: dict[str, float]
    equity_curve_bah: dict[str, float]
    ticker_prices: dict[str, float]
    undercut_distribution: list[UndercutDistributionRow] | None = None


# =============================================================================
# Main entry point
# =============================================================================

def run_single_ticker_analysis(
    strategy: Strategy,
    symbol: str,
    prices: dict[str, PriceFrame],
    initial_capital: float = 10_000.0,
    strategy_label: str = "Strategy",
) -> SingleTickerAnalysis:
    """Run a full single-ticker backtest and return rich analytics.

    Runs both the supplied strategy and a Buy-and-Hold benchmark so the caller
    gets comparison data in one call.
    """
    portfolio = Portfolio(
        slots=[StrategySlot(strategy=strategy, weight=1.0)],
        initial_capital=initial_capital,
    )
    result = run_portfolio(portfolio=portfolio, prices=prices)

    bah_portfolio = Portfolio(
        slots=[StrategySlot(strategy=BuyAndHold(weight=1.0), weight=1.0)],
        initial_capital=initial_capital,
    )
    bah_result = run_portfolio(portfolio=bah_portfolio, prices=prices)

    equity = result.equity_curve
    price_frame = prices[symbol]

    from_date = str(equity.index[0].date()) if not equity.empty else ""
    to_date = str(equity.index[-1].date()) if not equity.empty else ""
    total_bars = len(equity)

    open_trades = [t for t in result.trades if t.exit_date is None]
    closed_trades = [t for t in result.trades if t.exit_date is not None]

    # Current open position for this symbol (most recent)
    current_position: CurrentPosition | None = None
    symbol_open = [t for t in open_trades if t.symbol == symbol]
    if symbol_open:
        t = symbol_open[-1]
        last_price = float(price_frame.data["close"].iloc[-1])
        unrealized = (last_price / t.entry_price - 1) * 100 if t.entry_price > 0 else None
        current_position = CurrentPosition(
            entry_date=str(t.entry_date),
            entry_price=t.entry_price,
            holding_days=t.holding_days or 0,
            unrealized_return_pct=unrealized,
            mae_pct=t.mae_pct,
            mfe_pct=t.mfe_pct,
        )

    bah_closed = [t for t in bah_result.trades if t.exit_date is not None]

    returns = [t.return_pct for t in closed_trades if t.return_pct is not None]
    winners = [t for t in closed_trades if t.return_pct is not None and t.return_pct > 0]
    losers  = [t for t in closed_trades if t.return_pct is not None and t.return_pct <= 0]
    winner_maes = [t.mae_pct for t in winners if t.mae_pct is not None]
    winner_mfes = [t.mfe_pct for t in winners if t.mfe_pct is not None]
    loser_mfes  = [t.mfe_pct for t in losers  if t.mfe_pct is not None]

    undercut_distribution = _compute_undercut_distribution(strategy, winners, price_frame)

    return SingleTickerAnalysis(
        symbol=symbol,
        strategy_label=strategy_label,
        from_date=from_date,
        to_date=to_date,
        total_bars=total_bars,
        current_position=current_position,
        strategy=_compute_performance_summary(result, closed_trades),
        bah=_compute_performance_summary(bah_result, bah_closed),
        trades=_compute_trade_rows(result.trades, price_frame),
        return_percentiles=_compute_percentile_table(returns),
        mae_percentiles_winners=_compute_percentile_table(winner_maes),
        mfe_percentiles_winners=_compute_percentile_table(winner_mfes),
        mfe_percentiles_losers=_compute_percentile_table(loser_mfes),
        monthly_returns_strategy=_compute_monthly_heatmap(result.equity_curve),
        monthly_returns_bah=_compute_monthly_heatmap(bah_result.equity_curve),
        monthly_stats_by_calendar=_compute_monthly_stats_by_calendar(result.equity_curve),
        monthly_stats_by_entry_month=_compute_monthly_stats_by_entry(closed_trades),
        health_by_year=_compute_health_by_year(closed_trades, result.equity_curve),
        equity_curve_strategy={str(ts.date()): float(v) for ts, v in result.equity_curve.items()},
        equity_curve_bah={str(ts.date()): float(v) for ts, v in bah_result.equity_curve.items()},
        ticker_prices={str(ts.date()): float(v) for ts, v in price_frame.data["close"].items()},
        undercut_distribution=undercut_distribution,
    )


# =============================================================================
# Undercut distribution — temporary dips below MA during winning trades
# =============================================================================


def _compute_undercut_distribution(
    strategy: Strategy,
    winners: list[Trade],
    price_frame: PriceFrame,
) -> list[UndercutDistributionRow] | None:
    """Count how many temporary "undercut" events each winning trade had.

    An *undercut* is a run of consecutive bars where close <= MA that
    recovers (close returns above MA) without lasting long enough to
    trigger the exit (i.e. run length < sell_lag + 1).

    The terminal run that reaches the exit bar (should be exactly
    sell_lag + 1 bars) is the exit trigger itself — not an undercut.

    Returns a distribution: for each distinct undercut count, how many
    winning trades had exactly that number of undercuts.
    Returns None when not applicable (non-MA strategy or sell_lag == 0).
    """
    if not isinstance(strategy, FactorThresholdStrategy):
        return None
    if strategy.sell_lag <= 0:
        return None

    factor = strategy.factor
    if not (hasattr(factor, "ma_type") and hasattr(factor, "length")):
        return None

    from trading_engine.factors.moving_average import compute_ma

    sell_lag = strategy.sell_lag
    max_run_for_undercut = sell_lag  # runs of 1..sell_lag bars are undercuts
    close = price_frame.data["close"]
    ma = compute_ma(close, factor.ma_type, factor.length)

    # Build date→integer-position lookup
    date_to_idx: dict[Any, int] = {ts: i for i, ts in enumerate(close.index)}

    trade_undercuts: list[int] = []  # one entry per winning trade

    for t in winners:
        if t.exit_date is None:
            continue
        entry_ts = pd.Timestamp(str(t.entry_date))
        exit_ts = pd.Timestamp(str(t.exit_date))
        entry_idx = date_to_idx.get(entry_ts)
        exit_idx = date_to_idx.get(exit_ts)
        if entry_idx is None or exit_idx is None or entry_idx >= exit_idx:
            continue

        undercuts = 0
        i = entry_idx
        while i <= exit_idx:
            close_val = float(close.iloc[i])
            ma_val = float(ma.iloc[i])
            if pd.isna(ma_val) or close_val > ma_val:
                i += 1
                continue

            # Start of a below-MA run
            run_start = i
            while i <= exit_idx:
                c = float(close.iloc[i])
                m = float(ma.iloc[i])
                if pd.isna(m) or c > m:
                    break
                i += 1
            run_length = i - run_start

            if i > exit_idx:
                # Run reached the exit bar — this is the exit trigger.
                # The final exit countdown needs sell_lag + 1 consecutive
                # below-MA bars, so the terminal run at exit should have
                # that length.  Do NOT count it as an undercut.
                pass
            else:
                # Run ended with a recovery (close > MA at position i).
                if run_length <= max_run_for_undercut:
                    undercuts += 1
            # i now points at the recovery bar — loop continues from there

        trade_undercuts.append(undercuts)

    if not trade_undercuts:
        return []

    # Build distribution
    from collections import Counter
    counter = Counter(trade_undercuts)
    total = len(trade_undercuts)
    result: list[UndercutDistributionRow] = []
    for count in sorted(counter.keys()):
        cnt = counter[count]
        result.append(UndercutDistributionRow(
            undercuts=count,
            trade_count=cnt,
            pct_of_winners=round(cnt / total * 100, 2),
        ))

    return result


# =============================================================================
# Performance summary
# =============================================================================

def _compute_performance_summary(result: PortfolioResult, closed_trades: list[Trade]) -> PerformanceSummary:
    equity = result.equity_curve
    if equity.empty or len(equity) < 2:
        return _empty_summary()

    total_return_pct = float((equity.iloc[-1] / equity.iloc[0] - 1) * 100)
    cagr = _cagr(equity)
    sharpe = _sharpe(equity)
    max_dd = _max_drawdown(equity)
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0.0
    cum_max = equity.cummax()
    peak = float(cum_max.iloc[-1])
    current_dd = float((equity.iloc[-1] / peak - 1) * 100) if peak > 0 else 0.0
    if current_dd < 0.0:
        at_peak = equity[equity >= peak - 1e-9]
        current_dd_days = int((equity.index[-1] - at_peak.index[-1]).days) if not at_peak.empty else 0
    else:
        current_dd_days = 0
    time_in_market = _time_in_market(result.trades, equity)

    returns = [t.return_pct for t in closed_trades if t.return_pct is not None]
    if not returns:
        return PerformanceSummary(
            total_return_pct=total_return_pct,
            cagr_pct=cagr,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            current_drawdown_pct=current_dd,
            current_drawdown_days=current_dd_days,
            calmar_ratio=calmar,
            win_rate_pct=0.0,
            avg_win_pct=0.0,
            avg_loss_pct=0.0,
            max_consec_losses=0,
            best_trade_pct=0.0,
            worst_trade_pct=0.0,
            total_trades=0,
            avg_holding_days=0.0,
            profit_factor=0.0,
            time_in_market_pct=time_in_market,
        )

    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    win_rate = len(wins) / len(returns) * 100
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0

    max_consec = 0
    consec = 0
    for r in returns:
        if r <= 0:
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0

    sum_wins = sum(abs(r) for r in wins)
    sum_losses = sum(abs(r) for r in losses)
    profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else 999.0

    holding_days = [t.holding_days for t in closed_trades if t.holding_days is not None]
    avg_holding = float(np.mean(holding_days)) if holding_days else 0.0

    return PerformanceSummary(
        total_return_pct=total_return_pct,
        cagr_pct=cagr,
        sharpe_ratio=sharpe,
        max_drawdown_pct=max_dd,
        current_drawdown_pct=current_dd,
        current_drawdown_days=current_dd_days,
        calmar_ratio=calmar,
        win_rate_pct=win_rate,
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        max_consec_losses=max_consec,
        best_trade_pct=max(returns),
        worst_trade_pct=min(returns),
        total_trades=len(returns),
        avg_holding_days=avg_holding,
        profit_factor=min(profit_factor, 999.0),
        time_in_market_pct=time_in_market,
    )


def _empty_summary() -> PerformanceSummary:
    return PerformanceSummary(
        total_return_pct=0.0, cagr_pct=0.0, sharpe_ratio=0.0,
        max_drawdown_pct=0.0, current_drawdown_pct=0.0, current_drawdown_days=0, calmar_ratio=0.0, win_rate_pct=0.0,
        avg_win_pct=0.0, avg_loss_pct=0.0, max_consec_losses=0,
        best_trade_pct=0.0, worst_trade_pct=0.0, total_trades=0,
        avg_holding_days=0.0, profit_factor=0.0, time_in_market_pct=0.0,
    )


def _time_in_market(trades: list[Trade], equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    in_market = 0
    for t in trades:
        entry = pd.Timestamp(str(t.entry_date))
        exit_ = pd.Timestamp(str(t.exit_date)) if t.exit_date else equity.index[-1]
        in_market += int(((equity.index >= entry) & (equity.index <= exit_)).sum())
    return in_market / len(equity) * 100


# =============================================================================
# Trade rows
# =============================================================================

def _compute_trade_rows(trades: list[Trade], price_frame: PriceFrame) -> list[TradeRow]:
    close = price_frame.data["close"]
    # Build date→integer-position lookup for O(1) early-bar lookups
    date_to_idx: dict[Any, int] = {ts: i for i, ts in enumerate(close.index)}

    rows = []
    for t in trades:
        mae_price = t.entry_price * (1 + t.mae_pct / 100) if t.mae_pct is not None else None
        mfe_price = t.entry_price * (1 + t.mfe_pct / 100) if t.mfe_pct is not None else None
        retracement: float | None = None
        if t.mfe_pct is not None and t.return_pct is not None and t.return_pct > 0 and t.mfe_pct != 0:
            retracement = (t.mfe_pct - t.return_pct) / abs(t.mfe_pct) * 100

        # Early-bar min returns — lowest return within first N bars while still open
        early_returns: dict[str, float | None] = {}
        if t.exit_date is not None and t.entry_price > 0:
            entry_ts = pd.Timestamp(str(t.entry_date))
            exit_ts  = pd.Timestamp(str(t.exit_date))
            entry_idx = date_to_idx.get(entry_ts)
            exit_idx  = date_to_idx.get(exit_ts)
            for n in EARLY_BARS:
                key = str(n)
                # Bars from entry+1 up to min(entry+n, exit-1) — must have at least 1 bar open
                if entry_idx is not None and exit_idx is not None and entry_idx + 1 < exit_idx:
                    end_bar = min(entry_idx + n, exit_idx - 1)
                    window = close.iloc[entry_idx + 1 : end_bar + 1]
                    min_price = float(window.min())
                    early_returns[key] = (min_price / t.entry_price - 1) * 100
                else:
                    early_returns[key] = None

        rows.append(TradeRow(
            symbol=t.symbol,
            direction=t.direction,
            entry_date=str(t.entry_date),
            exit_date=str(t.exit_date) if t.exit_date is not None else None,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            return_pct=t.return_pct,
            holding_days=t.holding_days,
            mae_pct=t.mae_pct,
            mfe_pct=t.mfe_pct,
            mae_price=mae_price,
            mfe_price=mfe_price,
            retracement_pct=retracement,
            early_returns=early_returns,
        ))
    return rows


# =============================================================================
# Return distribution
# =============================================================================

def _compute_percentile_table(values: list[float]) -> list[DistributionRow]:
    if not values:
        return []
    arr = np.array(values)
    sorted_vals = sorted(values)
    rows = []
    for pct in DIST_PERCENTILES:
        val = float(np.percentile(arr, pct))
        cumulative = sum(1 for v in sorted_vals if v <= val)
        rows.append(DistributionRow(percentile=pct, value_pct=val, cumulative_count=cumulative))
    return rows


# =============================================================================
# Monthly returns heatmap
# =============================================================================

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _compute_monthly_heatmap(equity: pd.Series) -> dict[str, dict[str, float | None]]:
    if equity.empty:
        return {}
    monthly = equity.resample("ME").last()
    monthly_returns = monthly.pct_change() * 100
    result: dict[str, dict[str, float | None]] = {}
    for ts, ret in monthly_returns.items():
        year = str(ts.year)
        month = _MONTH_NAMES[ts.month - 1]
        if year not in result:
            result[year] = {m: None for m in _MONTH_NAMES}
        if not np.isnan(ret):
            result[year][month] = float(ret)
    return result


# =============================================================================
# Monthly stats tables
# =============================================================================

def _make_stat_row(label: str, values: list[float]) -> MonthlyStatRow:
    if not values:
        return MonthlyStatRow(label=label, count=0, **{f"p{p}": None for p in STAT_PERCENTILES})
    arr = np.array(values)
    return MonthlyStatRow(
        label=label,
        count=len(arr),
        **{f"p{p}": float(np.percentile(arr, p)) for p in STAT_PERCENTILES},
    )


def _compute_monthly_stats_by_calendar(equity: pd.Series) -> list[MonthlyStatRow]:
    """P10-P90 of daily returns grouped by calendar month."""
    if equity.empty:
        return [_make_stat_row(m, []) for m in _MONTH_NAMES]
    daily_returns = equity.pct_change().dropna() * 100
    rows = []
    for i, name in enumerate(_MONTH_NAMES, 1):
        month_vals = daily_returns[daily_returns.index.month == i].tolist()
        rows.append(_make_stat_row(name, month_vals))
    return rows


def _compute_monthly_stats_by_entry(trades: list[Trade]) -> list[MonthlyStatRow]:
    """P10-P90 of trade returns grouped by the entry month."""
    by_month: dict[int, list[float]] = defaultdict(list)
    for t in trades:
        if t.return_pct is not None:
            entry_ts = pd.Timestamp(str(t.entry_date))
            by_month[entry_ts.month].append(t.return_pct)
    rows = []
    for i, name in enumerate(_MONTH_NAMES, 1):
        rows.append(_make_stat_row(name, by_month.get(i, [])))
    return rows


# =============================================================================
# Year-by-year health
# =============================================================================

def _compute_health_by_year(trades: list[Trade], equity: pd.Series) -> list[HealthRow]:
    by_year: dict[int, list[Trade]] = defaultdict(list)
    for t in trades:
        entry_ts = pd.Timestamp(str(t.entry_date))
        by_year[entry_ts.year].append(t)

    rows = []
    for year in sorted(by_year.keys()):
        year_trades = by_year[year]
        returns = [t.return_pct for t in year_trades if t.return_pct is not None]

        arr = np.array(returns)
        has_data = len(arr) >= 2
        rows.append(HealthRow(
            year=year,
            trades=len(returns),
            **{f"p{p}": float(np.percentile(arr, p)) if has_data else None for p in STAT_PERCENTILES},
        ))
    return rows


# =============================================================================
# Equity helpers
# =============================================================================

def _cagr(equity: pd.Series) -> float:
    if equity.iloc[0] <= 0:
        return 0.0
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    total = equity.iloc[-1] / equity.iloc[0]
    return float((total ** (365.25 / days) - 1) * 100)


def _sharpe(equity: pd.Series, risk_free: float = 0.0) -> float:
    daily = equity.pct_change().dropna()
    if daily.empty or daily.std() == 0:
        return 0.0
    excess = daily - risk_free / 252
    return float(excess.mean() / excess.std() * np.sqrt(252))


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min() * 100)
