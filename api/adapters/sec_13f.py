"""Streaming reader for official SEC quarterly Form 13F ZIP archives."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from io import TextIOWrapper
from typing import BinaryIO, Iterator, Mapping
from zipfile import BadZipFile, ZipFile

from api.repositories.institutional_activity_repository import InstitutionalManagerWrite


class Sec13FArchiveError(ValueError):
    """Raised when an official archive row cannot satisfy the canonical contract."""


@dataclass(frozen=True)
class Sec13FSubmission:
    manager: InstitutionalManagerWrite
    accession_number: str
    form_type: str
    report_period: date
    filed_at: date
    accepted_at: datetime
    availability_precision: str
    amendment_type: str | None
    amendment_number: int
    source_url: str
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class Sec13FPosition:
    accession_number: str
    source_row_number: int
    raw_cusip: str
    raw_figi: str | None
    issuer_name: str
    title_of_class: str
    reported_value: Decimal
    reported_value_unit: str
    shares: Decimal
    share_type: str
    put_call: str | None
    investment_discretion: str | None
    voting_sole: Decimal
    voting_shared: Decimal
    voting_none: Decimal


@dataclass(frozen=True)
class Sec13FRejectedPosition:
    accession_number: str | None
    source_row_number: int
    reason: str
    raw_payload: dict[str, str]


class Sec13FArchive:
    """Re-openable, bounded-memory view over SEC SUBMISSION/COVERPAGE/INFOTABLE."""

    def __init__(
        self,
        stream: BinaryIO,
        *,
        fetched_at: datetime,
        acceptance_times: Mapping[str, datetime] | None = None,
    ) -> None:
        if fetched_at.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        self._stream = stream
        self._fetched_at = fetched_at.astimezone(UTC)
        self._acceptance_times = dict(acceptance_times or {})

    @property
    def fetched_at(self) -> datetime:
        return self._fetched_at

    def iter_submissions(self) -> Iterator[Sec13FSubmission]:
        with self._zip() as archive:
            covers = {
                row["ACCESSION_NUMBER"].strip(): row
                for _, row in self._rows(archive, "COVERPAGE.tsv")
            }
            for row_number, row in self._rows(archive, "SUBMISSION.tsv"):
                form_type = row.get("SUBMISSIONTYPE", "").strip().upper()
                if form_type not in {"13F-HR", "13F-HR/A"}:
                    continue
                accession = self._required(row, "ACCESSION_NUMBER", "SUBMISSION", row_number)
                cover = covers.get(accession)
                if cover is None:
                    raise Sec13FArchiveError(
                        f"SUBMISSION row {row_number}: missing COVERPAGE for {accession}"
                    )
                filed_at = self._date(row, "FILING_DATE", "SUBMISSION", row_number)
                accepted_at = self._acceptance_times.get(accession)
                if accepted_at is None:
                    accepted_at = datetime.combine(
                        filed_at + timedelta(days=1), time.min, tzinfo=UTC
                    )
                    precision = "filing_date_conservative"
                else:
                    if accepted_at.utcoffset() is None:
                        raise Sec13FArchiveError(
                            f"Acceptance time for {accession} must be timezone-aware"
                        )
                    accepted_at = accepted_at.astimezone(UTC)
                    precision = "accepted_at"
                cik = self._required(row, "CIK", "SUBMISSION", row_number)
                yield Sec13FSubmission(
                    manager=InstitutionalManagerWrite(
                        sec_cik=cik,
                        legal_name=self._required(
                            cover, "FILINGMANAGER_NAME", "COVERPAGE", row_number
                        ),
                        source="sec-13f",
                    ),
                    accession_number=accession,
                    form_type=form_type,
                    report_period=self._date(
                        row, "PERIODOFREPORT", "SUBMISSION", row_number
                    ),
                    filed_at=filed_at,
                    accepted_at=accepted_at,
                    availability_precision=precision,
                    amendment_type=_amendment_type(cover.get("AMENDMENTTYPE", "")),
                    amendment_number=_optional_non_negative_integer(
                        cover.get("AMENDMENTNO", ""), "COVERPAGE", row_number,
                    ),
                    source_url=_filing_url(cik, accession),
                    source="sec-13f",
                    fetched_at=self._fetched_at,
                )

    def iter_positions(self) -> Iterator[Sec13FPosition]:
        for record in self.iter_position_records():
            if isinstance(record, Sec13FRejectedPosition):
                raise Sec13FArchiveError(record.reason)
            yield record

    def iter_position_records(
        self,
    ) -> Iterator[Sec13FPosition | Sec13FRejectedPosition]:
        with self._zip() as archive:
            filing_dates = {
                self._required(row, "ACCESSION_NUMBER", "SUBMISSION", row_number):
                self._date(row, "FILING_DATE", "SUBMISSION", row_number)
                for row_number, row in self._rows(archive, "SUBMISSION.tsv")
            }
            for row_number, row in self._rows(archive, "INFOTABLE.tsv"):
                try:
                    yield self._parse_position(row, row_number, filing_dates)
                except Sec13FArchiveError as error:
                    yield Sec13FRejectedPosition(
                        accession_number=(row.get("ACCESSION_NUMBER") or "").strip() or None,
                        source_row_number=row_number,
                        reason=str(error),
                        raw_payload={key: value or "" for key, value in row.items()},
                    )

    def _parse_position(
        self,
        row: Mapping[str, str | None],
        row_number: int,
        filing_dates: Mapping[str, date],
    ) -> Sec13FPosition:
        accession = self._required(
            row, "ACCESSION_NUMBER", "INFOTABLE", row_number
        )
        filed_at = filing_dates.get(accession)
        if filed_at is None:
            raise Sec13FArchiveError(
                f"INFOTABLE row {row_number}: missing SUBMISSION for {accession}"
            )
        return Sec13FPosition(
                    accession_number=accession,
                    source_row_number=self._integer(
                        row, "INFOTABLE_SK", "INFOTABLE", row_number
                    ),
                    raw_cusip=self._required(row, "CUSIP", "INFOTABLE", row_number).upper(),
                    raw_figi=(row.get("FIGI") or "").strip().upper() or None,
                    issuer_name=self._required(
                        row, "NAMEOFISSUER", "INFOTABLE", row_number
                    ),
                    title_of_class=self._required(
                        row, "TITLEOFCLASS", "INFOTABLE", row_number
                    ),
                    reported_value=self._decimal(
                        row, "VALUE", "INFOTABLE", row_number, allow_zero=True
                    ),
                    reported_value_unit=(
                        "USD" if filed_at >= date(2023, 1, 3) else "USD_thousands"
                    ),
                    shares=self._decimal(
                        row, "SSHPRNAMT", "INFOTABLE", row_number, allow_zero=False
                    ),
                    share_type=self._required(
                        row, "SSHPRNAMTTYPE", "INFOTABLE", row_number
                    ).upper(),
                    put_call=(row.get("PUTCALL") or "").strip().upper() or None,
                    investment_discretion=(
                        (row.get("INVESTMENTDISCRETION") or "").strip() or None
                    ),
                    voting_sole=self._decimal(
                        row, "VOTING_AUTH_SOLE", "INFOTABLE", row_number, allow_zero=True
                    ),
                    voting_shared=self._decimal(
                        row, "VOTING_AUTH_SHARED", "INFOTABLE", row_number, allow_zero=True
                    ),
                    voting_none=self._decimal(
                        row, "VOTING_AUTH_NONE", "INFOTABLE", row_number, allow_zero=True
                    ),
        )

    def _zip(self) -> ZipFile:
        try:
            self._stream.seek(0)
            return ZipFile(self._stream)
        except (BadZipFile, OSError) as error:
            raise Sec13FArchiveError("Invalid SEC 13F ZIP archive") from error

    @staticmethod
    def _rows(archive: ZipFile, name: str):
        try:
            member = archive.open(name)
        except KeyError as error:
            raise Sec13FArchiveError(f"SEC 13F archive is missing {name}") from error
        with member, TextIOWrapper(member, encoding="utf-8-sig", newline="") as text:
            reader = csv.DictReader(text, delimiter="\t")
            if reader.fieldnames is None:
                raise Sec13FArchiveError(f"{name} has no header")
            for row_number, row in enumerate(reader, start=2):
                yield row_number, row

    @staticmethod
    def _required(row, field: str, table: str, row_number: int) -> str:
        value = (row.get(field) or "").strip()
        if not value:
            raise Sec13FArchiveError(f"{table} row {row_number}: missing {field}")
        return value

    @classmethod
    def _date(cls, row, field: str, table: str, row_number: int) -> date:
        value = cls._required(row, field, table, row_number)
        try:
            return datetime.strptime(value, "%d-%b-%Y").date()
        except ValueError as error:
            raise Sec13FArchiveError(
                f"{table} row {row_number}: invalid {field}"
            ) from error

    @classmethod
    def _integer(cls, row, field: str, table: str, row_number: int) -> int:
        value = cls._required(row, field, table, row_number)
        try:
            parsed = int(value)
        except ValueError as error:
            raise Sec13FArchiveError(
                f"{table} row {row_number}: invalid {field}"
            ) from error
        if parsed <= 0:
            raise Sec13FArchiveError(f"{table} row {row_number}: invalid {field}")
        return parsed

    @classmethod
    def _decimal(
        cls, row, field: str, table: str, row_number: int, *, allow_zero: bool,
    ) -> Decimal:
        value = cls._required(row, field, table, row_number)
        try:
            parsed = Decimal(value)
        except InvalidOperation as error:
            raise Sec13FArchiveError(
                f"{table} row {row_number}: invalid {field}"
            ) from error
        if not parsed.is_finite() or parsed < 0 or (not allow_zero and parsed == 0):
            raise Sec13FArchiveError(f"{table} row {row_number}: invalid {field}")
        return parsed


def _amendment_type(value: str) -> str | None:
    normalized = value.strip().upper()
    if not normalized:
        return None
    if "RESTATEMENT" in normalized:
        return "restatement"
    if "NEW HOLDINGS" in normalized:
        return "new_holdings"
    raise Sec13FArchiveError(f"Unsupported SEC 13F amendment type: {value}")


def _optional_non_negative_integer(
    value: str, table: str, row_number: int,
) -> int:
    normalized = (value or "").strip()
    if not normalized:
        return 0
    try:
        parsed = int(normalized)
    except ValueError as error:
        raise Sec13FArchiveError(
            f"{table} row {row_number}: invalid AMENDMENTNO"
        ) from error
    if parsed < 0:
        raise Sec13FArchiveError(f"{table} row {row_number}: invalid AMENDMENTNO")
    return parsed


def _filing_url(cik: str, accession: str) -> str:
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession.replace('-', '')}/{accession}-index.html"
    )
