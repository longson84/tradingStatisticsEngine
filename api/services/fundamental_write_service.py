"""Convert provider frames into normalized point-in-time persistence records."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pandas as pd

from api.fundamental_metrics import (
    FACT_SPECS,
    VALUATION_SPECS,
    calculation_version,
    period_identity,
    snapshot_key,
)
from api.repositories.fundamental_repository import (
    FundamentalFactWriteRecord,
    FundamentalReportWriteRecord,
    FundamentalRepository,
    FundamentalWriteBatch,
    FundamentalWriteResult,
    ProviderValuationWriteRecord,
)


class FundamentalWriteError(ValueError):
    pass


class FundamentalWriteService:
    def __init__(self, repository: FundamentalRepository):
        self._repository = repository

    def store_provider_frame(
        self,
        *,
        instrument_id: int,
        source: str,
        methodology: str,
        fetched_at: datetime,
        frame: pd.DataFrame,
    ) -> FundamentalWriteResult:
        instrument = self._repository.get_instrument(instrument_id)
        if instrument is None:
            raise FundamentalWriteError(f"Unknown instrument: {instrument_id}")
        if frame.empty:
            raise FundamentalWriteError(
                f"No fundamentals returned for instrument {instrument_id} ({instrument.symbol})"
            )
        currency = instrument.currency
        reports: list[FundamentalReportWriteRecord] = []
        for _, row in frame.sort_values("effective_date").iterrows():
            effective = _required_date(row.get("effective_date"), "effective_date")
            period_end = _optional_date(row.get("period_end"))
            period_value = row.get("period")
            period = "" if pd.isna(period_value) else str(period_value).strip()
            fiscal_year, fiscal_quarter, period_type = period_identity(
                period, period_end
            )
            facts = tuple(
                FundamentalFactWriteRecord(
                    metric_code=spec.metric_code,
                    value=value,
                    unit=spec.unit,
                    currency=(
                        currency if spec.unit in {"currency", "per_share"} else None
                    ),
                    period_basis=spec.period_basis,
                    fact_kind=spec.fact_kind,
                    source_field=column,
                    calculation_version=calculation_version(source, methodology),
                )
                for column, spec in FACT_SPECS.items()
                if (value := _optional_decimal(row.get(column))) is not None
            )
            valuations = tuple(
                ProviderValuationWriteRecord(
                    metric_code=metric_code,
                    value=value,
                    unit=unit,
                    currency=currency if unit == "currency" else None,
                )
                for column, (metric_code, unit) in VALUATION_SPECS.items()
                if (value := _optional_decimal(row.get(column))) is not None
            )
            reports.append(FundamentalReportWriteRecord(
                report_key=snapshot_key(effective, period_end, period),
                period_end=period_end,
                period_label=period or None,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                period_type=period_type,
                effective_session_date=effective,
                facts=facts,
                valuations=valuations,
            ))
        return self._repository.upsert_fundamentals(FundamentalWriteBatch(
            instrument_id=instrument_id,
            reporting_currency=currency,
            source=source,
            methodology=methodology,
            fetched_at=fetched_at,
            reports=tuple(reports),
        ))


def _required_date(value: object, field: str):
    result = _optional_date(value)
    if result is None:
        raise FundamentalWriteError(f"Missing or invalid {field}")
    return result


def _optional_date(value: object):
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    parsed = Decimal(str(value))
    return parsed if parsed.is_finite() else None
