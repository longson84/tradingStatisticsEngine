"""Point-in-time trailing P/E calculations."""
from __future__ import annotations

import pandas as pd


def fundamental_growth_over_years(
    snapshots: pd.DataFrame,
    *,
    value_column: str,
    as_of: pd.Timestamp,
    years: int,
) -> dict[str, float | str | bool] | None:
    """Measure total and annualized growth over up to the requested history."""
    if snapshots.empty or value_column not in snapshots.columns or years < 1:
        return None

    values = snapshots[["effective_date", value_column]].copy()
    values["effective_date"] = pd.to_datetime(
        values["effective_date"], errors="coerce"
    ).dt.normalize()
    values[value_column] = pd.to_numeric(values[value_column], errors="coerce")
    values = (
        values.dropna()
        .loc[lambda frame: frame[value_column] > 0]
        .loc[lambda frame: frame["effective_date"] <= pd.Timestamp(as_of).normalize()]
        .sort_values("effective_date")
        .drop_duplicates("effective_date", keep="last")
    )
    if len(values) < 2:
        return None

    end = values.iloc[-1]
    target = pd.Timestamp(as_of).normalize() - pd.DateOffset(years=years)
    old_enough = values.loc[values["effective_date"] <= target]
    full_period = not old_enough.empty
    start = old_enough.iloc[-1] if full_period else values.iloc[0]
    measurement_start = target if full_period else start["effective_date"]
    observed_years = (
        (pd.Timestamp(as_of).normalize() - measurement_start).days / 365.2425
    )
    if observed_years <= 0:
        return None

    start_value = float(start[value_column])
    end_value = float(end[value_column])
    ratio = end_value / start_value
    return {
        "total_growth_pct": (ratio - 1.0) * 100.0,
        "cagr_pct": (ratio ** (1.0 / observed_years) - 1.0) * 100.0,
        "observed_years": observed_years,
        "start_date": measurement_start.date().isoformat(),
        "full_period": full_period,
    }


def point_in_time_fundamental(
    dates: pd.Index,
    snapshots: pd.DataFrame,
    *,
    value_column: str,
    name: str,
) -> pd.Series:
    """Carry each published fundamental forward until the next snapshot."""
    result = pd.Series(index=dates, dtype=float, name=name)
    if len(dates) == 0 or snapshots.empty or value_column not in snapshots.columns:
        return result

    values = snapshots[["effective_date", value_column]].copy()
    values["effective_date"] = pd.to_datetime(
        values["effective_date"], errors="coerce"
    ).dt.normalize()
    values[value_column] = pd.to_numeric(values[value_column], errors="coerce")
    values = (
        values.dropna()
        .sort_values("effective_date")
        .drop_duplicates("effective_date", keep="last")
    )
    if values.empty:
        return result

    price_dates = pd.DataFrame({"date": pd.DatetimeIndex(dates).normalize()})
    aligned = pd.merge_asof(
        price_dates.sort_values("date"),
        values.rename(columns={"effective_date": "date"}),
        on="date",
        direction="backward",
    )
    result.iloc[:] = aligned[value_column].to_numpy()
    return result


def rebase_per_share_value_to_adjusted_prices(
    close: pd.Series,
    snapshots: pd.DataFrame,
    *,
    value_column: str,
    reported_multiple_column: str,
    price_multiplier: float = 1.0,
) -> pd.DataFrame:
    """Put a per-share fundamental onto the chart's adjusted-share basis.

    A provider-reported P/E at period end anchors the conversion, ensuring stock
    splits and stock dividends embedded in adjusted prices do not distort older
    P/E values.
    """
    snapshots = snapshots.copy()
    required = {"period_end", reported_multiple_column}
    if close.empty or not required.issubset(snapshots.columns):
        return snapshots

    series = pd.to_numeric(close, errors="coerce").sort_index()
    for index, row in snapshots.iterrows():
        period_end = pd.to_datetime(row["period_end"], errors="coerce")
        multiple = pd.to_numeric(
            pd.Series([row[reported_multiple_column]]), errors="coerce"
        ).iloc[0]
        if pd.isna(period_end) or pd.isna(multiple) or multiple <= 0:
            continue
        eligible = series[series.index <= period_end]
        if eligible.empty or pd.isna(eligible.iloc[-1]):
            continue
        snapshots.at[index, value_column] = (
            float(eligible.iloc[-1]) * price_multiplier / float(multiple)
        )
    return snapshots


def point_in_time_price_multiple(
    close: pd.Series,
    snapshots: pd.DataFrame,
    *,
    value_column: str,
    name: str,
    price_multiplier: float = 1.0,
) -> pd.Series:
    """Return a daily price multiple using only point-in-time fundamentals."""
    result = pd.Series(index=close.index, dtype=float, name=name)
    if close.empty or snapshots.empty or value_column not in snapshots.columns:
        return result

    aligned = point_in_time_fundamental(
        close.index,
        snapshots.loc[pd.to_numeric(snapshots[value_column], errors="coerce") > 0],
        value_column=value_column,
        name=value_column,
    )
    values = pd.to_numeric(close, errors="coerce").to_numpy() * price_multiplier
    result.iloc[:] = values / aligned.to_numpy()
    result[result <= 0] = float("nan")
    return result


def rebase_eps_to_adjusted_prices(
    close: pd.Series,
    eps_snapshots: pd.DataFrame,
    *,
    price_multiplier: float = 1.0,
) -> pd.DataFrame:
    return rebase_per_share_value_to_adjusted_prices(
        close,
        eps_snapshots,
        value_column="eps_ttm",
        reported_multiple_column="reported_pe",
        price_multiplier=price_multiplier,
    )


def point_in_time_trailing_pe(
    close: pd.Series,
    eps_snapshots: pd.DataFrame,
    *,
    price_multiplier: float = 1.0,
) -> pd.Series:
    return point_in_time_price_multiple(
        close,
        eps_snapshots,
        value_column="eps_ttm",
        name="trailing_pe",
        price_multiplier=price_multiplier,
    )
