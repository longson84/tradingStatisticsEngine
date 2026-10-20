from datetime import UTC, date, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from api.adapters.sec_13f import Sec13FArchive, Sec13FArchiveError


def archive_bytes(*, shares: str = "227917810") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "SUBMISSION.tsv",
            "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n"
            "0001067983-26-000001\t14-AUG-2026\t13F-HR\t0001067983\t30-JUN-2026\n",
        )
        archive.writestr(
            "COVERPAGE.tsv",
            "ACCESSION_NUMBER\tFILINGMANAGER_NAME\tISAMENDMENT\tAMENDMENTTYPE\n"
            "0001067983-26-000001\tBerkshire Hathaway Inc\t\t\n",
        )
        archive.writestr(
            "INFOTABLE.tsv",
            "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tFIGI\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL\tINVESTMENTDISCRETION\tVOTING_AUTH_SOLE\tVOTING_AUTH_SHARED\tVOTING_AUTH_NONE\n"
            f"0001067983-26-000001\t1\tAPPLE INC\tCOM\t037833100\tBBG000B9XRY4\t47410000\t{shares}\tSH\t\tSOLE\t{shares}\t0\t0\n",
        )
    return buffer.getvalue()


def test_archive_parses_official_submission_cover_and_information_tables() -> None:
    fetched_at = datetime(2026, 9, 14, 3, tzinfo=UTC)
    accepted_at = datetime(2026, 8, 14, 16, 30, tzinfo=UTC)
    source = Sec13FArchive(
        BytesIO(archive_bytes()),
        fetched_at=fetched_at,
        acceptance_times={"0001067983-26-000001": accepted_at},
    )

    submission, = source.iter_submissions()
    assert submission.manager.sec_cik == "0001067983"
    assert submission.manager.legal_name == "Berkshire Hathaway Inc"
    assert submission.accession_number == "0001067983-26-000001"
    assert submission.report_period == date(2026, 6, 30)
    assert submission.accepted_at == accepted_at
    assert submission.availability_precision == "accepted_at"

    position, = source.iter_positions()
    assert position.accession_number == submission.accession_number
    assert position.raw_cusip == "037833100"
    assert position.raw_figi == "BBG000B9XRY4"
    assert position.reported_value == 47410000
    assert position.reported_value_unit == "USD_thousands"
    assert position.shares == 227917810
    assert position.put_call is None


def test_archive_uses_conservative_next_day_availability_without_acceptance_time() -> None:
    source = Sec13FArchive(
        BytesIO(archive_bytes()),
        fetched_at=datetime(2026, 9, 14, 3, tzinfo=UTC),
    )

    submission, = source.iter_submissions()

    assert submission.accepted_at == datetime(2026, 8, 15, tzinfo=UTC)
    assert submission.availability_precision == "filing_date_conservative"


def test_archive_rejects_non_positive_shares_with_source_context() -> None:
    source = Sec13FArchive(
        BytesIO(archive_bytes(shares="0")),
        fetched_at=datetime(2026, 9, 14, 3, tzinfo=UTC),
    )

    with pytest.raises(Sec13FArchiveError, match="INFOTABLE row 2.*SSHPRNAMT"):
        tuple(source.iter_positions())
