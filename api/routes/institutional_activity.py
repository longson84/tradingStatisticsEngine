"""Database-only US Institutional Activity endpoint."""
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.deps import get_institutional_activity_service
from api.schemas.institutional_activity import (
    InstitutionalActivityChangeResponse,
    InstitutionalActivityHistoryResponse,
    InstitutionalActivityHolderResponse,
    InstitutionalActivityResponse,
)
from api.services.institutional_activity_service import InstitutionalActivityService


router = APIRouter(prefix="/instruments", tags=["instruments"])


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


@router.get(
    "/{instrument_id}/institutional-activity",
    response_model=InstitutionalActivityResponse,
    operation_id="getInstrumentInstitutionalActivity",
)
def get_instrument_institutional_activity(
    instrument_id: int,
    service: Annotated[
        InstitutionalActivityService, Depends(get_institutional_activity_service),
    ],
    quarters: int = Query(8, ge=1, le=20),
) -> InstitutionalActivityResponse:
    result = service.get_activity(instrument_id, quarters)
    return InstitutionalActivityResponse(
        status=result.status, message=result.message,
        instrument_id=result.instrument_id, symbol=result.symbol,
        instrument_type=result.instrument_type, venue_code=result.venue_code,
        formula_version=result.formula_version,
        latest_report_period=result.latest_report_period,
        latest_available_at=result.latest_available_at,
        action_counts=result.action_counts,
        history=[InstitutionalActivityHistoryResponse(
            report_period=row.report_period, holder_count=row.holder_count,
            total_shares=_number(row.total_shares),
        ) for row in result.history],
        changes=[InstitutionalActivityChangeResponse(
            manager_id=row.manager_id, manager_name=row.manager_name,
            is_curated=row.is_curated, action=row.action,
            previous_shares=_number(row.previous_shares),
            current_shares=_number(row.current_shares),
            share_change=_number(row.share_change),
            percentage_change=(
                None if row.percentage_change is None else _number(row.percentage_change)
            ),
            report_period=row.report_period, available_at=row.available_at,
            availability_precision=row.availability_precision,
            source_url=row.source_url,
        ) for row in result.changes],
        current_holders=[InstitutionalActivityHolderResponse(
            manager_id=row.manager_id, manager_name=row.manager_name,
            is_curated=row.is_curated, shares=_number(row.shares),
            report_period=row.report_period, available_at=row.available_at,
            availability_precision=row.availability_precision,
            source_url=row.source_url,
        ) for row in result.current_holders],
    )
