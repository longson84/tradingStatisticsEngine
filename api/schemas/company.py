"""Public company API contracts generated into frontend TypeScript types."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


MarketCode = Literal["US", "VN"]
CompanyUniverseId = Literal[
    "US_ALL", "US100", "US2000", "US500", "US30",
    "VN_ALL", "VN30", "VN100",
]


class CompanyResponse(BaseModel):
    ticker: str
    company_name: str
    market: MarketCode
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    lists: list[str]


class CompanyUniverseResponse(BaseModel):
    id: CompanyUniverseId
    name: str
    market: MarketCode
    description: str
    company_count: int
    as_of: str | None = None
    fetched_at: datetime | None = None


class CompanyUniversesResponse(BaseModel):
    universes: list[CompanyUniverseResponse]


class CompanyListResponse(BaseModel):
    id: CompanyUniverseId
    name: str
    market: MarketCode
    description: str
    as_of: str | None = None
    fetched_at: datetime | None = None
    total: int
    offset: int
    limit: int
    companies: list[CompanyResponse]
