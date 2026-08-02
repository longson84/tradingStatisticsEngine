"""Cross-sectional market health from each stock's distance to its rolling high."""
from __future__ import annotations

from datetime import date
from math import ceil

import numpy as np
import pandas as pd

from trading_engine.types import (
    InsufficientDataError,
    MarketHealthDistributionBucket,
    MarketHealthResult,
    MarketHealthStockDistance,
    MarketHealthWeights,
    PriceFrame,
)


_DISTRIBUTION_BANDS = (
    ("0 to -10%", -10.0, None),
    ("-10 to -20%", -20.0, -10.0),
    ("-20 to -30%", -30.0, -20.0),
    ("-30 to -40%", -40.0, -30.0),
    ("-40 to -50%", -50.0, -40.0),
    ("-50 to -60%", -60.0, -50.0),
    ("-60 to -70%", -70.0, -60.0),
    ("-70 to -80%", -80.0, -70.0),
    ("-80 to -90%", -90.0, -80.0),
    ("-90 to -100%", None, -90.0),
)


def _current_distribution(
    distances: pd.Series,
) -> list[MarketHealthDistributionBucket]:
    values = distances.dropna().astype(float)
    total = len(values)
    buckets: list[MarketHealthDistributionBucket] = []
    cumulative_count = 0
    for label, minimum, maximum in _DISTRIBUTION_BANDS:
        selected = pd.Series(True, index=values.index)
        if minimum is not None:
            selected &= values >= minimum
        if maximum is not None:
            selected &= values < maximum
        count = int(selected.sum())
        cumulative_count += count
        buckets.append(
            MarketHealthDistributionBucket(
                label=label,
                min_distance=minimum,
                max_distance=maximum,
                count=count,
                percentage=count / total * 100.0 if total else 0.0,
                cumulative_percentage=(
                    cumulative_count / total * 100.0 if total else 0.0
                ),
            )
        )
    return buckets


def compute_market_distance_snapshot(
    prices: dict[str, PriceFrame],
    *,
    as_of: date,
    window: int = 200,
    min_distance: float | None = None,
    max_distance: float | None = None,
) -> list[MarketHealthStockDistance]:
    """Return per-symbol trailing-high distances for one exact market session."""
    if window < 2:
        raise ValueError("window must be at least 2")

    timestamp = pd.Timestamp(as_of)
    rows: list[MarketHealthStockDistance] = []
    for symbol, price_frame in prices.items():
        close = price_frame.data["close"].astype(float).sort_index()
        close = close[~close.index.duplicated(keep="last")]
        if timestamp not in close.index:
            continue
        history = close.loc[:timestamp].tail(window)
        if len(history) < window:
            continue
        current_price = float(history.iloc[-1])
        rolling_high = float(history.max())
        distance = (current_price / rolling_high - 1.0) * 100.0
        if min_distance is not None and distance < min_distance:
            continue
        if max_distance is not None and distance >= max_distance:
            continue
        rows.append(
            MarketHealthStockDistance(
                symbol=symbol,
                date=as_of,
                current_price=current_price,
                rolling_high=rolling_high,
                distance=distance,
            )
        )
    return sorted(rows, key=lambda row: row.distance, reverse=True)


def compute_market_health(
    prices: dict[str, PriceFrame],
    *,
    universe: str,
    weights: MarketHealthWeights | None = None,
    window: int = 200,
    minimum_coverage: float = 0.8,
) -> MarketHealthResult:
    """Build a daily equal-weight health series without look-ahead.

    Each stock's daily value is its percentage distance from the highest close
    in the trailing ``window`` sessions. The composite score is a normalized
    weighted average of breadth within 10%, 20%, and 30% of the high plus the
    percentage of stocks that are not more than 40% below the high.
    """
    if not prices:
        raise InsufficientDataError("Market health requires at least one symbol")
    if window < 2:
        raise ValueError("window must be at least 2")
    if not 0 < minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be in (0, 1]")

    resolved_weights = weights or MarketHealthWeights()
    weight_values = np.array(
        [
            resolved_weights.within_10,
            resolved_weights.within_20,
            resolved_weights.within_30,
            resolved_weights.not_below_40,
        ],
        dtype=float,
    )
    if not np.isfinite(weight_values).all() or (weight_values < 0).any():
        raise ValueError("market health weights must be finite and non-negative")
    weight_total = float(weight_values.sum())
    if weight_total <= 0:
        raise ValueError("at least one market health weight must be positive")

    close_by_symbol: dict[str, pd.Series] = {}
    for symbol, price_frame in prices.items():
        close = price_frame.data["close"].astype(float).sort_index()
        close = close[~close.index.duplicated(keep="last")]
        close_by_symbol[symbol] = close

    closes = pd.concat(close_by_symbol, axis=1).sort_index()
    rolling_highs = closes.rolling(window=window, min_periods=window).max()
    distances = (closes / rolling_highs - 1.0) * 100.0

    eligible_count = distances.notna().sum(axis=1)
    required_count = max(1, ceil(len(close_by_symbol) * minimum_coverage))
    distances = distances.loc[eligible_count >= required_count]
    eligible_count = eligible_count.loc[distances.index]
    if distances.empty:
        raise InsufficientDataError(
            f"No dates meet {minimum_coverage:.0%} coverage after a {window}-session warm-up"
        )

    denominator = eligible_count.astype(float)
    within_10 = distances.ge(-10.0).sum(axis=1) / denominator * 100.0
    within_20 = distances.ge(-20.0).sum(axis=1) / denominator * 100.0
    within_30 = distances.ge(-30.0).sum(axis=1) / denominator * 100.0
    stress_40 = distances.le(-40.0).sum(axis=1) / denominator * 100.0
    not_below_40 = 100.0 - stress_40

    health_score = (
        resolved_weights.within_10 * within_10
        + resolved_weights.within_20 * within_20
        + resolved_weights.within_30 * within_30
        + resolved_weights.not_below_40 * not_below_40
    ) / weight_total

    def row_percentile(row: pd.Series, percentile: int) -> float:
        return float(np.percentile(row.dropna().to_numpy(dtype=float), percentile))

    series = pd.DataFrame(
        {
            "health_score": health_score,
            "median_distance": distances.median(axis=1),
            "p10_distance": distances.apply(row_percentile, axis=1, percentile=10),
            "p20_distance": distances.apply(row_percentile, axis=1, percentile=20),
            "p80_distance": distances.apply(row_percentile, axis=1, percentile=80),
            "p90_distance": distances.apply(row_percentile, axis=1, percentile=90),
            "within_10": within_10,
            "within_20": within_20,
            "within_30": within_30,
            "stress_40": stress_40,
            "coverage_pct": eligible_count / len(close_by_symbol) * 100.0,
            "eligible_count": eligible_count,
        }
    )
    series["change_5"] = series["health_score"].diff(5)
    series["change_20"] = series["health_score"].diff(20)
    series["ema_gap"] = (
        series["health_score"].ewm(span=5, adjust=False).mean()
        - series["health_score"].ewm(span=20, adjust=False).mean()
    )
    series.index.name = "date"
    distribution = _current_distribution(distances.loc[series.index[-1]])

    return MarketHealthResult(
        universe=universe,
        universe_size=len(close_by_symbol),
        window=window,
        minimum_coverage=minimum_coverage,
        weights=resolved_weights,
        series=series,
        distribution=distribution,
    )


def classify_market_health(score: float, change_20: float | None) -> str:
    """Map health level and 20-session direction to a concise regime label."""
    if score >= 70:
        level = "strong"
    elif score >= 55:
        level = "healthy"
    elif score >= 40:
        level = "mixed"
    elif score >= 25:
        level = "weak"
    else:
        level = "deeply_weak"

    if change_20 is None or np.isnan(change_20) or abs(change_20) < 3:
        direction = "stable"
    elif change_20 > 0:
        direction = "improving"
    else:
        direction = "deteriorating"
    return f"{level}_{direction}"
