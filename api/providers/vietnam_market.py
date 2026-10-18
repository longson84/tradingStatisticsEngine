"""Typed adapter for authenticated sponsored Vietnam market data."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from importlib import import_module, metadata
from typing import Literal, Protocol

import pandas as pd

from api.config import load_env_file
from api.session_statistics import (
    SESSION_STATISTIC_METRIC_CODES,
    SessionStatisticMetricCode,
)
from api.trade_statistics import (
    TRADE_HISTORY_PROVIDER_COLUMNS,
    TRADE_STATISTIC_STORAGE_COLUMNS,
)


AccessMode = Literal["sponsored"]
InstrumentKind = Literal["equity", "index"]


class ProviderUnavailableError(RuntimeError):
    """Raised when the selected provider package cannot be loaded."""


class ProviderDataError(RuntimeError):
    """Raised when a provider returns no usable data for a request."""


@dataclass(frozen=True)
class VietnamProviderMetadata:
    package: str
    package_version: str
    access_mode: AccessMode
    upstream_source: str
    method: str
    symbol: str
    requested_start: date
    requested_end: date


@dataclass(frozen=True)
class VietnamProviderResult:
    frame: pd.DataFrame
    metadata: VietnamProviderMetadata


class VietnamMarketProvider(Protocol):
    def ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        interval: str = "1D",
        instrument_kind: InstrumentKind = "equity",
    ) -> VietnamProviderResult: ...

    def trade_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult: ...

    def foreign_flow(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult: ...

    def proprietary_flow(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult: ...

    def session_stats(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult: ...


class VnstockProvider:
    """Vnstock generation 5 adapter using explicit VCI market routes."""

    package = "vnstock"
    access_mode: AccessMode = "sponsored"
    source = "VCI"

    def __init__(self) -> None:
        load_env_file()
        self.package_version = _package_version(self.package)
        if not self.package_version.startswith("5.1."):
            raise ProviderUnavailableError(
                "VnstockProvider requires vnstock 5.1.x in its runtime"
            )

    def ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        interval: str = "1D",
        instrument_kind: InstrumentKind = "equity",
    ) -> VietnamProviderResult:
        normalized = _request(symbol, start, end)
        market = self._market()
        instrument = (
            market.index(normalized)
            if instrument_kind == "index"
            else market.equity(normalized)
        )
        frame = instrument.ohlcv(
            start=start.isoformat(),
            end=end.isoformat(),
            interval=interval,
            source=self.source.lower(),
        )
        return self._result(frame, normalized, start, end, "ohlcv")

    def trade_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult:
        from vnstock.core.exceptions import VnstockError

        normalized = _request(symbol, start, end)
        try:
            frame = self._market().equity(normalized).trade_history(
                start=start.isoformat(),
                end=end.isoformat(),
                resolution="1D",
                source=self.source.lower(),
            )
        except VnstockError as exc:
            # Raw messages can contain credentials or request URLs. Expose only
            # stable codes and action text without credential-bearing content.
            context = []
            code = getattr(exc, "code", None)
            if isinstance(code, str) and re.fullmatch(r"VNSTOCK_[A-Z0-9_]+", code):
                context.append(f"code={code}")
            action = getattr(exc, "action", None)
            if (
                isinstance(action, str)
                and action.strip()
                and len(action) <= 500
                and not re.search(
                    r"https?://|api[_ -]?key|token|secret|credential|password|"
                    r"authorization|bearer|[\x00-\x1f]",
                    action,
                    flags=re.IGNORECASE,
                )
            ):
                context.append(f"action={action.strip()}")
            suffix = f" ({'; '.join(context)})" if context else ""
            raise ProviderDataError(
                f"trade_history request failed for {normalized}{suffix}"
            ) from None
        return self._result(frame, normalized, start, end, "trade_history")

    def foreign_flow(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult:
        normalized = _request(symbol, start, end)
        frame = self._market().equity(normalized).foreign_flow(
            start=start.isoformat(),
            end=end.isoformat(),
            source=self.source.lower(),
        )
        return self._result(frame, normalized, start, end, "foreign_flow")

    def proprietary_flow(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult:
        normalized = _request(symbol, start, end)
        frame = self._market().equity(normalized).proprietary_flow(
            start=start.isoformat(),
            end=end.isoformat(),
            source=self.source.lower(),
        )
        return self._result(frame, normalized, start, end, "proprietary_flow")

    def session_stats(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult:
        normalized = _request(symbol, start, end)
        frame = self._market().equity(normalized).session_stats(
            start=start.isoformat(),
            end=end.isoformat(),
            source=self.source.lower(),
        )
        return self._result(frame, normalized, start, end, "session_stats")

    def _market(self):
        try:
            module = import_module(self.package)
            market_factory = module.Market
        except (ImportError, AttributeError) as exc:
            raise ProviderUnavailableError(
                "vnstock generation 5 could not be loaded"
            ) from exc
        return market_factory()

    def _result(
        self,
        frame: pd.DataFrame | None,
        symbol: str,
        start: date,
        end: date,
        method: str,
    ) -> VietnamProviderResult:
        clean = _require_frame(frame, symbol, method)
        return VietnamProviderResult(
            frame=clean,
            metadata=VietnamProviderMetadata(
                package=self.package,
                package_version=self.package_version,
                access_mode=self.access_mode,
                upstream_source=self.source,
                method=method,
                symbol=symbol,
                requested_start=start,
                requested_end=end,
            ),
        )


def provider_source_label(metadata: VietnamProviderMetadata) -> str:
    """Build stable row provenance without claiming an unknown upstream."""
    package = metadata.package.replace("_", "-").lower()
    upstream = metadata.upstream_source.replace("_", "-").lower()
    return f"{package}-{metadata.package_version}-{upstream}"


def normalize_ohlcv_result(result: VietnamProviderResult) -> pd.DataFrame:
    """Normalize a provider OHLCV result for canonical price persistence."""
    frame = result.frame.copy()
    frame.columns = [str(column).lower() for column in frame.columns]
    if "time" in frame.columns:
        frame = frame.rename(columns={"time": "date"})
    elif "date" not in frame.columns:
        raise ProviderDataError(
            f"ohlcv data for {result.metadata.symbol} is missing a date column"
        )
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ProviderDataError(
            f"ohlcv data for {result.metadata.symbol} is missing columns: "
            f"{sorted(missing)}"
        )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ("open", "high", "low", "close", "volume"):
        if column not in frame:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["symbol"] = result.metadata.symbol
    frame["provider_source"] = provider_source_label(result.metadata)
    return (
        frame[[
            "symbol", "date", "open", "high", "low", "close", "volume",
            "provider_source",
        ]]
        .dropna(subset=["date", "open", "high", "low", "close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def normalize_foreign_flow_result(result: VietnamProviderResult) -> pd.DataFrame:
    """Normalize Gen 5 foreign-investor flow without deriving provider values."""
    return _normalize_participant_flow_result(result, "foreign_flow")


def normalize_trade_history_result(result: VietnamProviderResult) -> pd.DataFrame:
    """Validate the whole daily provider response before projecting activity."""
    frame = _require_frame(result.frame, result.metadata.symbol, "trade_history")
    prefix = f"trade_history data for {result.metadata.symbol}"
    columns = tuple(frame.columns)
    if len(columns) != len(set(columns)):
        raise ProviderDataError(f"{prefix} has duplicate columns")
    if columns != TRADE_HISTORY_PROVIDER_COLUMNS:
        raise ProviderDataError(f"{prefix} must contain the exact supported schema")
    if result.metadata.requested_start > result.metadata.requested_end:
        raise ProviderDataError(f"{prefix} has an invalid requested period")

    numeric_columns = tuple(
        column for column in TRADE_HISTORY_PROVIDER_COLUMNS
        if column not in {"trading_date", "end_trading_date", "price_change_value"}
    )
    gross_columns = tuple(
        column for column in TRADE_STATISTIC_STORAGE_COLUMNS
        if column != "total_net_trade_volume"
    )
    for column in numeric_columns:
        try:
            values = [Decimal(str(value)) for value in frame[column]]
        except (InvalidOperation, ValueError) as exc:
            raise ProviderDataError(f"{prefix} contains invalid numeric values") from exc
        if any(not value.is_finite() for value in values):
            raise ProviderDataError(f"{prefix} contains invalid numeric values")
        if column in gross_columns and any(value < 0 for value in values):
            raise ProviderDataError(f"{prefix} gross values must be non-negative")
        frame[column] = values

    dates = [_trade_history_date(value, prefix) for value in frame["trading_date"]]
    end_dates = [
        _trade_history_date(value, prefix) for value in frame["end_trading_date"]
    ]
    if len(dates) != len(set(dates)):
        raise ProviderDataError(f"{prefix} has duplicate trading dates")
    if dates != end_dates:
        raise ProviderDataError(f"{prefix} has inconsistent end trading dates")
    if any(
        day < result.metadata.requested_start or day > result.metadata.requested_end
        for day in dates
    ):
        raise ProviderDataError(f"{prefix} contains dates outside the requested period")
    for value in frame["price_change_value"]:
        if not isinstance(value, str) or re.fullmatch(
            r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?\s+"
            r"\([+-]?\d+(?:\.\d+)?%\)", value.strip()
        ) is None:
            raise ProviderDataError(f"{prefix} contains invalid price-change display values")
    for unit in ("volume", "value"):
        for amounts in zip(
            frame[f"matched_{unit}"], frame[f"deal_{unit}"], frame[f"total_{unit}"],
        ):
            matched, deal, total = amounts
            with localcontext() as context:
                # Decimal's default 28 digits would round valid wide DB values.
                context.prec = max(
                    1,
                    max(value.adjusted() for value in amounts)
                    - min(value.as_tuple().exponent for value in amounts) + 2,
                )
                if matched + deal != total:
                    raise ProviderDataError(f"{prefix} contains inconsistent total {unit}")

    frame["symbol"] = result.metadata.symbol
    frame["trading_date"] = dates
    frame["provider_source"] = provider_source_label(result.metadata)
    return (
        frame[["symbol", "trading_date", *TRADE_STATISTIC_STORAGE_COLUMNS, "provider_source"]]
        .sort_values("trading_date", kind="stable")
        .reset_index(drop=True)
    )


def _trade_history_date(value: object, prefix: str) -> date:
    try:
        # Timestamps expressed in UTC must still identify the Vietnam session.
        # Naive provider dates already refer to that venue's local calendar.
        if not isinstance(value, (str, date)):
            raise ValueError("unsupported date type")
        stamp = pd.Timestamp(value)
        if pd.isna(stamp):
            raise ValueError("missing date")
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert("Asia/Ho_Chi_Minh")
        return stamp.date()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProviderDataError(f"{prefix} contains invalid trading dates") from exc


def normalize_proprietary_flow_result(result: VietnamProviderResult) -> pd.DataFrame:
    """Normalize Gen 5 proprietary-trading flow without deriving net values."""
    return _normalize_participant_flow_result(result, "proprietary_flow")


def normalize_session_stats_result(
    result: VietnamProviderResult,
) -> dict[SessionStatisticMetricCode, Decimal]:
    """Validate one complete VCI aggregate and preserve provider values."""
    frame = result.frame.copy()
    columns = [str(column).lower() for column in frame.columns]
    expected = ("symbol", *SESSION_STATISTIC_METRIC_CODES)
    if len(columns) != len(set(columns)):
        raise ProviderDataError(
            f"session_stats data for {result.metadata.symbol} has duplicate columns"
        )
    if len(frame) != 1 or tuple(columns) != expected:
        raise ProviderDataError(
            f"session_stats data for {result.metadata.symbol} must contain one "
            "row with the exact supported schema"
        )
    frame.columns = columns
    symbol = str(frame.iloc[0]["symbol"]).upper().strip()
    if symbol != result.metadata.symbol:
        raise ProviderDataError(
            f"session_stats data for {result.metadata.symbol} returned symbol {symbol}"
        )
    values: dict[SessionStatisticMetricCode, Decimal] = {}
    for code in SESSION_STATISTIC_METRIC_CODES:
        try:
            value = Decimal(str(frame.iloc[0][code]))
        except (InvalidOperation, ValueError) as exc:
            raise ProviderDataError(
                f"session_stats data for {result.metadata.symbol} contains invalid values"
            ) from exc
        if not value.is_finite():
            raise ProviderDataError(
                f"session_stats data for {result.metadata.symbol} contains invalid values"
            )
        values[code] = value
    return values


def _normalize_participant_flow_result(
    result: VietnamProviderResult,
    dataset: str,
) -> pd.DataFrame:
    frame = result.frame.copy()
    frame.columns = [str(column).lower() for column in frame.columns]
    required = {
        "time", "buy_vol", "buy_val", "sell_vol", "sell_val", "net_vol",
        "net_val",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ProviderDataError(
            f"{dataset} data for {result.metadata.symbol} is missing columns: "
            f"{sorted(missing)}"
        )

    dates = pd.to_datetime(frame["time"], errors="coerce")
    numeric_columns = (
        "buy_vol", "buy_val", "sell_vol", "sell_val", "net_vol", "net_val",
    )
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if dates.isna().any() or frame[list(numeric_columns)].isna().any().any():
        raise ProviderDataError(
            f"{dataset} data for {result.metadata.symbol} contains invalid values"
        )
    gross_columns = ("buy_vol", "buy_val", "sell_vol", "sell_val")
    if (frame[list(gross_columns)] < 0).any().any():
        raise ProviderDataError(
            f"{dataset} gross values for {result.metadata.symbol} must be non-negative"
        )

    frame["date"] = dates.dt.date
    frame["symbol"] = result.metadata.symbol
    frame["provider_source"] = provider_source_label(result.metadata)
    frame = frame.rename(columns={
        "buy_vol": "buy_volume",
        "buy_val": "buy_value",
        "sell_vol": "sell_volume",
        "sell_val": "sell_value",
        "net_vol": "net_volume",
        "net_val": "net_value",
    })
    return (
        frame[[
            "symbol", "date", "buy_volume", "buy_value", "sell_volume",
            "sell_value", "net_volume", "net_value", "provider_source",
        ]]
        .sort_values("date", kind="stable")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def _request(symbol: str, start: date, end: date) -> str:
    normalized = symbol.upper().strip()
    if not normalized:
        raise ValueError("Vietnam market symbol must not be empty")
    if start > end:
        raise ValueError("Vietnam market start date must not be after end date")
    return normalized


def _require_frame(
    frame: pd.DataFrame | None,
    symbol: str,
    method: str,
) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise ProviderDataError(f"{method} returned no data for {symbol}")
    return frame.copy()


def _package_version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "unknown"
