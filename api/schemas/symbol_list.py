"""Schemas for static reusable symbol lists."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SymbolListSummary(BaseModel):
    id: str
    name: str
    description: str
    symbol_count: int
    as_of: str | None = None
    fetched_at: str | None = None


class SymbolListItem(BaseModel):
    symbol: str
    yfinance_symbol: str
    name: str
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SymbolListResponse(SymbolListSummary):
    sources: list[dict[str, str]]
    symbols: list[SymbolListItem]


class SymbolListsResponse(BaseModel):
    lists: list[SymbolListSummary]
