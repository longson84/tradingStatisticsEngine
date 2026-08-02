"""Static reusable symbol-list endpoints."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from api.schemas.symbol_list import SymbolListItem, SymbolListResponse, SymbolListSummary, SymbolListsResponse

router = APIRouter(prefix="/symbol-lists", tags=["symbol-lists"])

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "symbol_lists"
_US_COMBINED_LIST_ID = "US_ALL"
_VN_COMBINED_LIST_ID = "VN_ALL"
_US_LIST_FILES = {
    "US100": "us100.json",
    "US2000": "us2000.json",
    "US500": "us500.json",
    "US30": "us30.json",
}
_VN_LIST_FILES = {
    "VN30": "vn30.json",
    "VN100": "vn100.json",
}
_LIST_FILES = {
    **_US_LIST_FILES,
    **_VN_LIST_FILES,
}


def _load_payload(list_id: str) -> dict[str, Any]:
    normalized_id = list_id.upper()
    if normalized_id == _US_COMBINED_LIST_ID:
        return _combined_payload(
            list_files=_US_LIST_FILES,
            list_id=_US_COMBINED_LIST_ID,
            name="Combined US Companies",
            description=(
                "One enriched static list merged from Nasdaq-100, S&P 500, and "
                "Dow Jones snapshots. Sector and industry are filled from the "
                "saved sources when available."
            ),
        )
    if normalized_id == _VN_COMBINED_LIST_ID:
        return _combined_payload(
            list_files=_VN_LIST_FILES,
            list_id=_VN_COMBINED_LIST_ID,
            name="Combined VN Companies",
            description=(
                "One saved Vietnam company list combining VN30 and VN100 "
                "constituents with VNStock company and industry information."
            ),
        )

    file_name = _LIST_FILES.get(normalized_id)
    if file_name is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol list: {list_id!r}")

    path = _DATA_DIR / file_name
    try:
        return _read_static_payload(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Symbol list file not found: {file_name}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid symbol list JSON: {file_name}") from exc


def _load_static_payload(list_id: str) -> dict[str, Any]:
    file_name = _LIST_FILES[list_id]
    path = _DATA_DIR / file_name
    return _read_static_payload(path)


def _read_static_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    symbols_file = payload.get("symbols_file")
    if not symbols_file:
        return payload

    with (path.parent / str(symbols_file)).open(newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            rows.append({key: value or None for key, value in row.items()})
    payload["symbols"] = rows
    return payload


def _combined_payload(
    *,
    list_files: dict[str, str],
    list_id: str,
    name: str,
    description: str,
) -> dict[str, Any]:
    payloads = [_load_static_payload(source_id) for source_id in list_files]
    rows_by_symbol: dict[str, dict[str, Any]] = {}

    for payload in payloads:
        source_id = str(payload["id"])
        source_name = str(payload["name"])

        for row in payload.get("symbols", []):
            key = str(row.get("yfinance_symbol") or row["symbol"])
            existing = rows_by_symbol.get(key)

            if existing is None:
                merged = dict(row)
                merged["source_ids"] = [source_id]
                merged["source_lists"] = [source_name]
                rows_by_symbol[key] = merged
                continue

            existing["source_ids"].append(source_id)
            existing["source_lists"].append(source_name)

            for field in ("sector", "industry", "exchange", "name"):
                if not existing.get(field) and row.get(field):
                    existing[field] = row[field]

            for field, value in row.items():
                if field not in existing or existing[field] is None:
                    existing[field] = value

    sources = []
    for payload in payloads:
        sources.extend(payload.get("sources", []))

    symbols = sorted(rows_by_symbol.values(), key=lambda row: str(row.get("yfinance_symbol") or row["symbol"]))

    return {
        "id": list_id,
        "name": name,
        "description": description,
        "as_of": " / ".join(str(payload["as_of"]) for payload in payloads if payload.get("as_of")) or None,
        "fetched_at": max(str(payload["fetched_at"]) for payload in payloads if payload.get("fetched_at")),
        "sources": sources,
        "symbols": symbols,
        "symbol_count": len(symbols),
    }


def _summary(payload: dict[str, Any]) -> SymbolListSummary:
    return SymbolListSummary(
        id=str(payload["id"]),
        name=str(payload["name"]),
        description=str(payload.get("description", "")),
        symbol_count=int(payload.get("symbol_count", len(payload.get("symbols", [])))),
        as_of=payload.get("as_of"),
        fetched_at=payload.get("fetched_at"),
    )


def _symbol_item(row: dict[str, Any]) -> SymbolListItem:
    base_keys = {"symbol", "yfinance_symbol", "name", "sector", "industry", "exchange"}
    return SymbolListItem(
        symbol=str(row["symbol"]),
        yfinance_symbol=str(row.get("yfinance_symbol") or row["symbol"]),
        name=str(row.get("name") or row["symbol"]),
        sector=row.get("sector"),
        industry=row.get("industry"),
        exchange=row.get("exchange"),
        metadata={k: v for k, v in row.items() if k not in base_keys and v is not None},
    )


@router.get("", response_model=SymbolListsResponse)
def list_symbol_lists() -> SymbolListsResponse:
    return SymbolListsResponse(
        lists=[
            _summary(_load_payload(_US_COMBINED_LIST_ID)),
            *[_summary(_load_payload(list_id)) for list_id in _US_LIST_FILES],
            _summary(_load_payload(_VN_COMBINED_LIST_ID)),
            *[_summary(_load_payload(list_id)) for list_id in _VN_LIST_FILES],
        ]
    )


@router.get("/{list_id}", response_model=SymbolListResponse)
def get_symbol_list(list_id: str) -> SymbolListResponse:
    payload = _load_payload(list_id)
    summary = _summary(payload)
    return SymbolListResponse(
        **summary.model_dump(),
        sources=payload.get("sources", []),
        symbols=[_symbol_item(row) for row in payload.get("symbols", [])],
    )
