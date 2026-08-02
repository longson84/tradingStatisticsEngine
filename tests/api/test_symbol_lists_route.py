"""Tests for static symbol-list endpoints."""
from __future__ import annotations

from api.routes.symbol_lists import get_symbol_list, list_symbol_lists


def test_lists_include_static_presets():
    result = list_symbol_lists()

    assert [item.id for item in result.lists] == [
        "US_ALL",
        "US100",
        "US2000",
        "US500",
        "US30",
        "VN_ALL",
        "VN30",
        "VN100",
    ]
    assert result.lists[0].symbol_count > 503
    assert result.lists[1].symbol_count == 103
    assert result.lists[2].symbol_count == 1954
    assert result.lists[3].symbol_count == 503
    assert result.lists[4].symbol_count == 30
    assert result.lists[5].symbol_count == 100
    assert result.lists[6].symbol_count == 30
    assert result.lists[7].symbol_count == 100


def test_get_symbol_list_returns_yfinance_symbols_and_metadata():
    result = get_symbol_list("US30")

    assert result.id == "US30"
    assert len(result.symbols) == 30
    assert result.symbols[0].symbol == "MMM"
    assert result.symbols[0].yfinance_symbol == "MMM"
    assert result.symbols[0].sector == "Industrials"
    assert result.symbols[0].metadata["index_weight"] == 1.85


def test_combined_symbol_list_enriches_overlapping_rows():
    result = get_symbol_list("US_ALL")
    rows = {row.yfinance_symbol: row for row in result.symbols}

    assert result.id == "US_ALL"
    assert rows["AAPL"].sector == "Information Technology"
    assert rows["AAPL"].industry == "Technology Hardware, Storage & Peripherals"
    assert rows["AAPL"].metadata["market_cap"] == 4631217093920
    assert rows["AAPL"].metadata["source_lists"] == [
        "Nasdaq-100",
        "S&P 500",
        "Dow Jones Industrial Average",
    ]


def test_vietnam_symbol_lists_include_saved_company_and_industry_data():
    vn30 = get_symbol_list("VN30")
    vn100 = get_symbol_list("VN100")
    vn30_rows = {row.symbol: row for row in vn30.symbols}
    vn100_rows = {row.symbol: row for row in vn100.symbols}

    assert len(vn30.symbols) == 30
    assert len(vn100.symbols) == 100
    assert set(vn30_rows).issubset(vn100_rows)
    assert vn100_rows["FPT"].name == "FPT Corporation"
    assert vn100_rows["FPT"].sector == "Information Technology"
    assert vn100_rows["FPT"].industry == "Công nghệ và thông tin"
    assert vn100_rows["FPT"].exchange == "HOSE"
    assert vn100_rows["FPT"].metadata["local_name"] == "CTCP FPT"
    assert vn100_rows["FPT"].metadata["industry_code"] == 6
    assert vn100_rows["FPT"].metadata["data_source"] == "vnstock"


def test_combined_vietnam_list_tracks_vn30_and_vn100_membership():
    result = get_symbol_list("VN_ALL")
    rows = {row.symbol: row for row in result.symbols}

    assert result.id == "VN_ALL"
    assert len(result.symbols) == 100
    assert rows["FPT"].metadata["source_lists"] == ["VN30 Index", "VN100 Index"]
    assert rows["ANV"].metadata["source_lists"] == ["VN100 Index"]
