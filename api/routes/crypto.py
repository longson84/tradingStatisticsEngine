"""Read-only crypto instrument catalog endpoints."""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from api.deps import get_crypto_instrument_service
from api.schemas.crypto import (
    CryptoInstrumentFacetCountResponse,
    CryptoInstrumentFacetsResponse,
    CryptoInstrumentResponse,
    CryptoInstrumentListResponse,
    CryptoInstrumentSummaryResponse,
    CryptoVenueFacetResponse,
)
from api.services.crypto_instrument_service import CryptoInstrumentService


router = APIRouter(prefix="/crypto", tags=["crypto"])


@router.get(
    "/instruments",
    response_model=CryptoInstrumentListResponse,
    operation_id="listCryptoInstruments",
)
def list_crypto_instruments(
    service: Annotated[
        CryptoInstrumentService,
        Depends(get_crypto_instrument_service),
    ],
    venue_code: str | None = Query(default=None, max_length=64),
    search: str | None = Query(default=None, max_length=100),
    quote_asset: str | None = Query(default=None, max_length=32),
    status: Literal["active", "inactive", "all"] = Query(default="active"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
) -> CryptoInstrumentListResponse:
    normalized_venue = venue_code.upper().strip() if venue_code else None
    result = service.list_instruments(
        venue_code=normalized_venue,
        search=search,
        quote_asset=quote_asset,
        is_active={"active": True, "inactive": False, "all": None}[status],
        offset=offset,
        limit=limit,
    )
    selected_venue = next(
        (row for row in result.facets.venues if row.code == normalized_venue),
        None,
    ) if normalized_venue else None
    return CryptoInstrumentListResponse(
        venue_code=normalized_venue,
        venue_name=selected_venue.name if selected_venue else None,
        total=result.total,
        offset=offset,
        limit=limit,
        instruments=[
            CryptoInstrumentResponse(
                id=row.id,
                venue_code=row.venue_code,
                venue_name=row.venue_name,
                symbol=row.symbol,
                base_asset=row.base_asset,
                quote_asset=row.quote_asset,
                is_active=row.is_active,
                price_tick_size=_decimal_text(row.price_tick_size),
                quantity_step_size=_decimal_text(row.quantity_step_size),
                minimum_quantity=_decimal_text(row.minimum_quantity),
                minimum_notional=_decimal_text(row.minimum_notional),
                first_session=row.first_date,
                last_session=row.last_date,
                stored_sessions=row.stored_sessions,
                price_source=row.price_source,
            )
            for row in result.rows
        ],
        facets=CryptoInstrumentFacetsResponse(
            venues=[
                CryptoVenueFacetResponse(
                    code=row.code,
                    name=row.name,
                    count=row.count,
                )
                for row in result.facets.venues
            ],
            quote_assets=[
                CryptoInstrumentFacetCountResponse(value=row.value, count=row.count)
                for row in result.facets.quote_assets
            ],
            active_count=result.facets.active_count,
            inactive_count=result.facets.inactive_count,
        ),
        summary=CryptoInstrumentSummaryResponse(
            instrument_count=result.summary.instrument_count,
            active_count=result.summary.active_count,
            inactive_count=result.summary.inactive_count,
            with_history_count=result.summary.with_history_count,
            catalog_fetched_at=result.summary.catalog_fetched_at,
        ),
    )


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f").rstrip("0").rstrip(".") or "0"
