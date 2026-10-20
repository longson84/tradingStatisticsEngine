"""Explicit SEC archive ingestion into canonical institutional storage."""
from __future__ import annotations

from dataclasses import dataclass

from api.adapters.sec_13f import Sec13FArchive
from api.repositories.institutional_activity_repository import (
    InstitutionalActivityRepository,
    InstitutionalFilingWrite,
    InstitutionalPositionWrite,
)


@dataclass(frozen=True)
class InstitutionalActivityImportResult:
    submissions: int
    positions_seen: int
    positions_added: int
    mapped_positions: int
    unmapped_positions: int
    option_positions: int


class InstitutionalActivityWriteService:
    def __init__(self, repository: InstitutionalActivityRepository) -> None:
        self._repository = repository

    def import_archive(self, archive: Sec13FArchive) -> InstitutionalActivityImportResult:
        filing_ids: dict[str, tuple[int, object]] = {}
        submissions = 0
        for submission in archive.iter_submissions():
            manager_id = self._repository.upsert_manager(submission.manager)
            filing_id = self._repository.add_filing(InstitutionalFilingWrite(
                manager_id=manager_id,
                accession_number=submission.accession_number,
                form_type=submission.form_type,
                report_period=submission.report_period,
                filed_at=submission.filed_at,
                accepted_at=submission.accepted_at,
                amendment_type=submission.amendment_type,
                source_url=submission.source_url,
                source=submission.source,
                fetched_at=submission.fetched_at,
                availability_precision=submission.availability_precision,
            ))
            filing_ids[submission.accession_number] = (filing_id, submission)
            submissions += 1

        writes: list[InstitutionalPositionWrite] = []
        mapped = unmapped = options = 0
        for position in archive.iter_positions():
            filing = filing_ids.get(position.accession_number)
            if filing is None:
                continue
            filing_id, submission = filing
            instrument_id = self._repository.resolve_instrument_id(
                "cusip", position.raw_cusip, submission.report_period
            )
            mapped += instrument_id is not None
            unmapped += instrument_id is None
            options += position.put_call is not None
            writes.append(InstitutionalPositionWrite(
                filing_id=filing_id,
                source_row_number=position.source_row_number,
                instrument_id=instrument_id,
                raw_cusip=position.raw_cusip,
                raw_figi=position.raw_figi,
                issuer_name=position.issuer_name,
                title_of_class=position.title_of_class,
                reported_value=position.reported_value,
                reported_value_unit=position.reported_value_unit,
                shares=position.shares,
                share_type=position.share_type,
                put_call=position.put_call,
                investment_discretion=position.investment_discretion,
                voting_sole=position.voting_sole,
                voting_shared=position.voting_shared,
                voting_none=position.voting_none,
                source="sec-13f",
                fetched_at=submission.fetched_at,
            ))
        added = self._repository.add_positions(writes)
        return InstitutionalActivityImportResult(
            submissions=submissions,
            positions_seen=len(writes),
            positions_added=added,
            mapped_positions=mapped,
            unmapped_positions=unmapped,
            option_positions=options,
        )
