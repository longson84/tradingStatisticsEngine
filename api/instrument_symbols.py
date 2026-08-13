"""Authoritative current canonical Instrument symbol helpers."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.sql.elements import ColumnElement

from api.db.models import Instrument, InstrumentSymbol


CANONICAL_SYMBOL_NAMESPACE = "canonical"


def canonical_symbol_expression() -> ColumnElement[str]:
    """Return the current canonical symbol correlated to Instrument."""
    return (
        select(InstrumentSymbol.symbol)
        .where(
            InstrumentSymbol.instrument_id == Instrument.id,
            InstrumentSymbol.namespace == CANONICAL_SYMBOL_NAMESPACE,
            InstrumentSymbol.valid_to.is_(None),
            InstrumentSymbol.is_primary.is_(True),
        )
        .correlate(Instrument)
        .scalar_subquery()
        .label("ticker")
    )


def canonical_symbol_exists(symbol: str | ColumnElement[str]) -> ColumnElement[bool]:
    """Return an EXISTS predicate for a current canonical symbol."""
    return (
        select(InstrumentSymbol.id)
        .where(
            InstrumentSymbol.instrument_id == Instrument.id,
            InstrumentSymbol.namespace == CANONICAL_SYMBOL_NAMESPACE,
            InstrumentSymbol.symbol == symbol,
            InstrumentSymbol.valid_to.is_(None),
            InstrumentSymbol.is_primary.is_(True),
        )
        .correlate(Instrument)
        .exists()
    )


def canonical_symbol(instrument: Instrument) -> str:
    """Read the exactly one current canonical symbol from a loaded Instrument."""
    values = {
        row.symbol
        for row in instrument.symbols
        if row.namespace == CANONICAL_SYMBOL_NAMESPACE
        and row.valid_to is None
        and row.is_primary
    }
    if len(values) != 1:
        raise ValueError(
            f"Instrument {instrument.id!r} has {len(values)} current canonical symbols"
        )
    return next(iter(values))


def new_instrument(
    canonical_symbol_value: str,
    *,
    source: str,
    **values: Any,
) -> Instrument:
    """Construct an Instrument with its required initial canonical symbol."""
    instrument = Instrument(source=source, **values)
    instrument.symbols.append(InstrumentSymbol(
        namespace=CANONICAL_SYMBOL_NAMESPACE,
        symbol=canonical_symbol_value.upper().strip(),
        is_primary=True,
        source=source,
    ))
    return instrument
