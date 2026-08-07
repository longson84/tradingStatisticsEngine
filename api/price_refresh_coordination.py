"""Coordinate API-launched price refreshes that share canonical market data."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class PriceRefreshLease:
    owner_id: str
    label: str


_active: dict[str, PriceRefreshLease] = {}
_lock = Lock()


def acquire_price_refresh(market: str, owner_id: str, label: str) -> None:
    normalized = _market(market)
    with _lock:
        active = _active.get(normalized)
        if active is not None:
            raise RuntimeError(
                f"A {normalized} price refresh is already running: {active.label}"
            )
        _active[normalized] = PriceRefreshLease(owner_id=owner_id, label=label)


def release_price_refresh(market: str, owner_id: str) -> None:
    normalized = _market(market)
    with _lock:
        active = _active.get(normalized)
        if active is not None and active.owner_id == owner_id:
            _active.pop(normalized, None)


def get_active_price_refresh(market: str) -> PriceRefreshLease | None:
    normalized = _market(market)
    with _lock:
        return _active.get(normalized)


def _market(value: str) -> str:
    normalized = value.upper().strip()
    if normalized not in {"US", "VN"}:
        raise ValueError("Price refresh market must be US or VN")
    return normalized
