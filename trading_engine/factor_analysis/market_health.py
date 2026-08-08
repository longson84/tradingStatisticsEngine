"""Cross-sectional market health from each stock's distance to its rolling high."""
from __future__ import annotations

from datetime import date
from math import ceil

import pandas as pd
from pandas.api.indexers import VariableOffsetWindowIndexer

from trading_engine.types import (
    InsufficientDataError,
    MarketHealthDistributionBucket,
    MarketHealthHistoricalContext,
    MarketHealthResult,
    MarketHealthStockDistance,
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


def summarize_market_health_history(
    median_distances: pd.Series,
) -> MarketHealthHistoricalContext:
    """Place the latest median-distance reading in its empirical history."""
    values = median_distances.dropna().astype(float)
    if values.empty:
        raise InsufficientDataError(
            "Historical Market Health context requires at least one observation"
        )

    current = float(values.iloc[-1])
    below = int((values < current).sum())
    equal = int((values == current).sum())
    current_percentile = (below + equal / 2.0) / len(values) * 100.0
    if current_percentile >= 90.0:
        regime = "Exceptionally strong"
    elif current_percentile >= 75.0:
        regime = "Strong"
    elif current_percentile >= 25.0:
        regime = "Normal"
    elif current_percentile >= 10.0:
        regime = "Weak"
    else:
        regime = "Exceptionally weak"

    return MarketHealthHistoricalContext(
        observation_count=len(values),
        median_distance=float(values.median()),
        q25_distance=float(values.quantile(0.25)),
        q75_distance=float(values.quantile(0.75)),
        current_percentile=current_percentile,
        regime=regime,
    )


def compute_market_health_running_medians(
    median_distances: pd.Series,
) -> pd.DataFrame:
    """Return trailing 10Y, 5Y, and 1Y medians without look-ahead."""
    values = median_distances.astype(float)
    if not isinstance(values.index, pd.DatetimeIndex):
        raise ValueError("Running Market Health medians require a DatetimeIndex")

    medians: dict[str, pd.Series] = {}
    for years in (10, 5, 1):
        window = VariableOffsetWindowIndexer(
            index=values.index,
            offset=pd.DateOffset(years=years),
        )
        medians[f"running_median_{years}y"] = values.rolling(
            window=window,
            min_periods=1,
            closed="both",
        ).median()
    return pd.DataFrame(medians, index=values.index)


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
    close_by_symbol: dict[str, pd.Series] = {}
    for symbol, price_frame in prices.items():
        close = price_frame.data["close"].astype(float).sort_index()
        close = close[~close.index.duplicated(keep="last")]
        close_by_symbol[symbol] = close

    closes = pd.concat(close_by_symbol, axis=1).sort_index().loc[:timestamp]
    closes = closes.loc[~closes.index.duplicated(keep="last")].ffill()
    if timestamp not in closes.index:
        return []

    rows: list[MarketHealthStockDistance] = []
    for symbol in closes.columns:
        history = closes[symbol].tail(window)
        if len(history) < window or history.isna().any():
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
    window: int = 200,
    minimum_coverage: float = 0.8,
) -> MarketHealthResult:
    """Build the daily median distance from trailing highs without look-ahead."""
    if not prices:
        raise InsufficientDataError("Market health requires at least one symbol")
    close_by_symbol: dict[str, pd.Series] = {}
    for symbol, price_frame in prices.items():
        close = price_frame.data["close"].astype(float).sort_index()
        close = close[~close.index.duplicated(keep="last")]
        close_by_symbol[symbol] = close

    closes = pd.concat(close_by_symbol, axis=1).sort_index()
    return compute_market_health_from_closes(
        closes,
        universe=universe,
        window=window,
        minimum_coverage=minimum_coverage,
    )


def compute_market_health_from_closes(
    closes: pd.DataFrame,
    *,
    universe: str,
    window: int = 200,
    minimum_coverage: float = 0.8,
) -> MarketHealthResult:
    """Build Market Health directly from a date-by-symbol close matrix."""
    if closes.empty or len(closes.columns) == 0:
        raise InsufficientDataError("Market health requires at least one symbol")
    if window < 2:
        raise ValueError("window must be at least 2")
    if not 0 < minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be in (0, 1]")

    closes = closes.astype(float).sort_index()
    closes = closes.loc[~closes.index.duplicated(keep="last")]
    # A missing row after listing normally means that the stock did not trade
    # on that exchange session. Its last observable close remains the current
    # market value; leading pre-listing gaps intentionally stay missing.
    closes = closes.ffill()
    rolling_highs = closes.rolling(window=window, min_periods=window).max()
    distances = (closes / rolling_highs - 1.0) * 100.0

    eligible_count = distances.notna().sum(axis=1)
    required_count = max(1, ceil(len(closes.columns) * minimum_coverage))
    distances = distances.loc[eligible_count >= required_count]
    eligible_count = eligible_count.loc[distances.index]
    if distances.empty:
        raise InsufficientDataError(
            f"No dates meet {minimum_coverage:.0%} coverage after a {window}-session warm-up"
        )

    series = pd.DataFrame(
        {
            "median_distance": distances.median(axis=1),
            "coverage_pct": eligible_count / len(closes.columns) * 100.0,
            "eligible_count": eligible_count,
        }
    )
    series.index.name = "date"
    distribution = _current_distribution(distances.loc[series.index[-1]])

    return MarketHealthResult(
        universe=universe,
        universe_size=len(closes.columns),
        window=window,
        minimum_coverage=minimum_coverage,
        series=series,
        distribution=distribution,
    )
