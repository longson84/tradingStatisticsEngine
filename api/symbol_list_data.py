"""Canonical readers for the saved company-universe snapshots."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data" / "symbol_lists"
US_LIST_FILES = {
    "US100": "us100.json",
    "US2000": "us2000.json",
    "US500": "us500.json",
    "US30": "us30.json",
}
VN_LIST_FILES = {
    "VN30": "vn30.json",
    "VN100": "vn100.json",
}
LIST_FILES = {**US_LIST_FILES, **VN_LIST_FILES}


def load_static_payload(list_id: str) -> dict[str, Any]:
    return read_static_payload(DATA_DIR / LIST_FILES[list_id])


def read_static_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    symbols_file = payload.get("symbols_file")
    if not symbols_file:
        return payload

    with (path.parent / str(symbols_file)).open(newline="") as handle:
        payload["symbols"] = [
            {key: value or None for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    return payload
