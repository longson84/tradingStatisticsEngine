"""Explicit SEC archive ingestion into canonical institutional storage."""
from __future__ import annotations

from dataclasses import dataclass

from api.adapters.sec_13f import Sec13FArchive, Sec13FRejectedPosition
from api.repositories.institutional_activity_repository import (
    AmbiguousInstrumentIdentifierError,
    InstitutionalActivityRepository,
    InstitutionalFilingWrite,
    InstitutionalPositionWrite,
    InstitutionalPositionRejectionWrite,
)


@dataclass(frozen=True)
class InstitutionalActivityImportResult:
    submissions: int
    positions_seen: int
    positions_added: int
    mapped_positions: int
    unmapped_positions: int
    ambiguous_positions: int
    rejected_positions: int
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
                amendment_number=submission.amendment_number,
                source_url=submission.source_url,
                source=submission.source,
                fetched_at=submission.fetched_at,
                availability_precision=submission.availability_precision,
                is_complete=False,
            ))
            filing_ids[submission.accession_number] = (filing_id, submission)
            submissions += 1

        writes: list[InstitutionalPositionWrite] = []
        rejections: list[InstitutionalPositionRejectionWrite] = []
        incomplete_filing_ids: set[int] = set()
        mapped = unmapped = ambiguous = rejected = options = added = seen = 0
        for position in archive.iter_position_records():
            seen += 1
            if isinstance(position, Sec13FRejectedPosition):
                filing = (
                    filing_ids.get(position.accession_number)
                    if position.accession_number is not None else None
                )
                filing_id = filing[0] if filing is not None else None
                if filing_id is None:
                    incomplete_filing_ids.update(row[0] for row in filing_ids.values())
                else:
                    incomplete_filing_ids.add(filing_id)
                fetched_at = (
                    filing[1].fetched_at if filing is not None else archive.fetched_at
                )
                rejections.append(InstitutionalPositionRejectionWrite(
                    filing_id=filing_id,
                    accession_number=position.accession_number,
                    source_row_number=position.source_row_number,
                    reason=position.reason,
                    raw_payload=position.raw_payload,
                    source="sec-13f",
                    fetched_at=fetched_at,
                ))
                rejected += 1
                if len(rejections) >= 1000:
                    self._repository.add_position_rejections(rejections)
                    rejections.clear()
                continue
            filing = filing_ids.get(position.accession_number)
            if filing is None:
                continue
            filing_id, submission = filing
            try:
                instrument_id = self._repository.resolve_instrument_id(
                    "cusip", position.raw_cusip, submission.report_period
                )
                mapping_status = "mapped" if instrument_id is not None else "unmapped"
            except AmbiguousInstrumentIdentifierError:
                instrument_id = None
                mapping_status = "ambiguous"
                ambiguous += 1
            mapped += instrument_id is not None
            unmapped += mapping_status == "unmapped"
            options += position.put_call is not None
            writes.append(InstitutionalPositionWrite(
                filing_id=filing_id,
                source_row_number=position.source_row_number,
                instrument_id=instrument_id,
                mapping_status=mapping_status,
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
            if len(writes) >= 1000:
                added += self._repository.add_positions(writes)
                writes.clear()
        added += self._repository.add_positions(writes)
        self._repository.add_position_rejections(rejections)
        for filing_id, _ in filing_ids.values():
            self._repository.set_filing_completeness(
                filing_id, filing_id not in incomplete_filing_ids,
            )
        return InstitutionalActivityImportResult(
            submissions=submissions,
            positions_seen=seen,
            positions_added=added,
            mapped_positions=mapped,
            unmapped_positions=unmapped,
            ambiguous_positions=ambiguous,
            rejected_positions=rejected,
            option_positions=options,
        )
