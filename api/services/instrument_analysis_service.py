"""Instrument discovery and canonical price resolution for analysis workflows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from api.instrument_data_routing import (
    UnsupportedInstrumentRouteError,
    instrument_observation_schedule,
    resolve_instrument_data_route,
)
from api.market_sessions import latest_completed_venue_session
from api.repositories.instrument_analysis_repository import (
    AnalysisInstrumentListResult,
    AnalysisInstrumentPriceBarRecord,
    AnalysisInstrumentQuery,
    AnalysisInstrumentRecord,
    InstrumentAnalysisRepository,
)
from api.repositories.instrument_routing_repository import (
    InstrumentRoutingRepository,
)
from api.services.company_price_service import (
    CompanyPriceService,
    CompanyPriceUnavailableError,
    UnknownCompanyError,
)
from trading_engine.types import PriceFrame


class UnknownInstrumentError(ValueError):
    pass


class InstrumentPriceUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class InstrumentPriceData:
    instrument: AnalysisInstrumentRecord
    prices: PriceFrame
    expected_last_session: date
    data_last_session: date
    refreshed: bool
    is_stale: bool
    refresh_warning: str | None
    price_source: str
    price_basis: str
    fetched_at: datetime


@dataclass(frozen=True)
class StoredInstrumentPriceSet:
    instruments: dict[int, AnalysisInstrumentRecord]
    prices: dict[int, PriceFrame]
    expected_last_sessions: dict[int, date]
    data_last_sessions: dict[int, date]
    price_sources: dict[int, str]
    missing_instrument_ids: tuple[int, ...]
    stale_instrument_ids: tuple[int, ...]


class InstrumentAnalysisService:
    def __init__(
        self,
        repository: InstrumentAnalysisRepository,
        routing_repository: InstrumentRoutingRepository,
        company_price_service: CompanyPriceService | None = None,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository
        self._company_price_service = company_price_service

    def list_instruments(
        self,
        *,
        scope: str | None = None,
        universe: str | None = None,
        search: str | None = None,
        has_price_history: bool = True,
        offset: int = 0,
        limit: int = 20,
    ) -> AnalysisInstrumentListResult:
        return self._repository.list_instruments(AnalysisInstrumentQuery(
            scope=scope,
            universe=universe.upper().strip() if universe else None,
            search=search.strip() if search else None,
            has_price_history=has_price_history,
            offset=offset,
            limit=limit,
        ))

    def get_current_history(
        self,
        instrument_id: int,
        *,
        now: datetime | None = None,
    ) -> InstrumentPriceData:
        instrument = self._repository.get_instrument(instrument_id)
        if instrument is None:
            raise UnknownInstrumentError(f"Unknown instrument: {instrument_id}")

        current = now or datetime.now(UTC)
        metadata = self._metadata(instrument_id)
        try:
            route = resolve_instrument_data_route(metadata)
        except UnsupportedInstrumentRouteError:
            route = None
        refreshed = False
        warning: str | None = None
        if (
            route is not None
            and route.fundamental_adapter is not None
            and self._company_price_service
        ):
            try:
                stored = self._company_price_service.get_current_instrument_history(
                    instrument.id,
                    now=current,
                )
            except UnknownCompanyError as exc:
                raise UnknownInstrumentError(
                    f"Unknown instrument: {instrument_id}"
                ) from exc
            except CompanyPriceUnavailableError as exc:
                raise InstrumentPriceUnavailableError(str(exc)) from exc
            refreshed = stored.refreshed
            warning = stored.refresh_warning
            instrument = self._repository.get_instrument(instrument_id) or instrument

        records = tuple(self._repository.iter_price_bars(
            instrument.id,
            instrument.price_basis,
        ))
        if not records:
            raise InstrumentPriceUnavailableError(
                f"No stored price history for instrument {instrument.id} ({instrument.symbol})"
            )

        frame = pd.DataFrame(
            {
                "open": [row.open for row in records],
                "high": [row.high for row in records],
                "low": [row.low for row in records],
                "close": [row.close for row in records],
                "volume": [row.volume for row in records],
            },
            index=pd.DatetimeIndex(
                [row.trading_date for row in records], name="date"
            ),
        )
        last_date = records[-1].trading_date
        expected = latest_completed_venue_session(
            current, instrument_observation_schedule(metadata)
        )
        if (route is None or route.fundamental_adapter is None) and last_date < expected:
            warning = warning or (
                "Stored history is stale; refresh it through the instrument's "
                "configured ingestion workflow."
            )
        return InstrumentPriceData(
            instrument=instrument,
            prices=PriceFrame(
                symbol=instrument.symbol,
                data=frame,
                source=records[-1].source,
            ),
            expected_last_session=expected,
            data_last_session=last_date,
            refreshed=refreshed,
            is_stale=last_date < expected,
            refresh_warning=warning,
            price_source=records[-1].source,
            price_basis=instrument.price_basis,
            fetched_at=max(row.fetched_at for row in records),
        )

    def get_stored_histories(
        self,
        instrument_ids: list[int] | tuple[int, ...],
        *,
        now: datetime | None = None,
    ) -> StoredInstrumentPriceSet:
        """Load canonical stored bars for exact instruments without refreshing."""
        ordered_ids = tuple(dict.fromkeys(instrument_ids))
        instruments = {
            instrument.id: instrument
            for instrument in self._repository.get_instruments(ordered_ids)
        }
        routing_metadata = self._routing_repository.get_instrument_routes_metadata(
            tuple(instruments)
        )
        metadata_by_id = {row.instrument_id: row for row in routing_metadata}
        records_by_id: dict[int, list[AnalysisInstrumentPriceBarRecord]] = {
            value: [] for value in ordered_ids
        }
        for record in self._repository.iter_instrument_set_price_bars(ordered_ids):
            records_by_id.setdefault(record.instrument_id, []).append(record)

        current = now or datetime.now(UTC)
        prices: dict[int, PriceFrame] = {}
        expected: dict[int, date] = {}
        actual: dict[int, date] = {}
        sources: dict[int, str] = {}
        missing: list[int] = []
        stale: list[int] = []
        for instrument_id in ordered_ids:
            instrument = instruments.get(instrument_id)
            records = records_by_id.get(instrument_id, [])
            if instrument is None or not records:
                missing.append(instrument_id)
                continue
            frame = pd.DataFrame(
                {
                    "open": [row.open for row in records],
                    "high": [row.high for row in records],
                    "low": [row.low for row in records],
                    "close": [row.close for row in records],
                    "volume": [row.volume for row in records],
                },
                index=pd.DatetimeIndex(
                    [row.trading_date for row in records], name="date"
                ),
            )
            metadata = metadata_by_id.get(instrument_id)
            if metadata is None:
                missing.append(instrument_id)
                continue
            expected_date = latest_completed_venue_session(
                current, instrument_observation_schedule(metadata)
            )
            last_date = records[-1].trading_date
            prices[instrument_id] = PriceFrame(
                symbol=instrument.symbol,
                data=frame,
                source=records[-1].source,
            )
            expected[instrument_id] = expected_date
            actual[instrument_id] = last_date
            sources[instrument_id] = records[-1].source
            if last_date < expected_date:
                stale.append(instrument_id)

        return StoredInstrumentPriceSet(
            instruments=instruments,
            prices=prices,
            expected_last_sessions=expected,
            data_last_sessions=actual,
            price_sources=sources,
            missing_instrument_ids=tuple(missing),
            stale_instrument_ids=tuple(stale),
        )

    def _metadata(self, instrument_id: int):
        metadata = self._routing_repository.get_instrument_route_metadata(
            instrument_id
        )
        if metadata is None:
            raise UnknownInstrumentError(f"Unknown instrument: {instrument_id}")
        return metadata
