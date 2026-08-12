"""Coordinate API-launched price refreshes that share one acquisition adapter."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class PriceRefreshLease:
    owner_id: str
    label: str


_active: dict[str, PriceRefreshLease] = {}
_lock = Lock()


def acquire_price_refresh(adapter: str, owner_id: str, label: str) -> None:
    normalized = _adapter(adapter)
    with _lock:
        active = _active.get(normalized)
        if active is not None:
            raise RuntimeError(
                f"A {normalized} price refresh is already running: {active.label}"
            )
        _active[normalized] = PriceRefreshLease(owner_id=owner_id, label=label)


def release_price_refresh(adapter: str, owner_id: str) -> None:
    normalized = _adapter(adapter)
    with _lock:
        active = _active.get(normalized)
        if active is not None and active.owner_id == owner_id:
            _active.pop(normalized, None)


def get_active_price_refresh(adapter: str) -> PriceRefreshLease | None:
    normalized = _adapter(adapter)
    with _lock:
        return _active.get(normalized)


def _adapter(value: str) -> str:
    normalized = value.lower().strip()
    if normalized not in {"yfinance", "vnstock_data", "binance_spot"}:
        raise ValueError(f"Unsupported price refresh adapter: {value}")
    return normalized
