from __future__ import annotations

from datetime import date
import json

import pandas as pd
import pytest

from api.providers.universe import (
    UniverseProviderRegistry,
    UniverseProviderDataError,
    make_constituent,
    normalize_ticker,
    validated_constituents,
)
from api.providers.universe_catalog import create_universe_provider_registry
from api.providers.us_universes import (
    IsharesRussell2000UniverseProvider,
    Nasdaq100UniverseProvider,
    WikipediaUSIndexProvider,
)
from api.providers.vietnam_universes import VnstockUniverseProvider


def test_normalize_ticker_uses_price_loader_class_share_notation():
    assert normalize_ticker(" brk.b ", "US") == "BRK-B"
    assert normalize_ticker("fpt", "VN") == "FPT"

    with pytest.raises(UniverseProviderDataError, match="Invalid VN"):
        normalize_ticker("VN 30", "VN")


def test_validated_constituents_rejects_normalized_duplicates():
    values = [
        make_constituent(ticker="BRK.B", market="US"),
        make_constituent(ticker="BRK-B", market="US"),
    ]

    with pytest.raises(UniverseProviderDataError, match="duplicate tickers"):
        validated_constituents(values, universe="US500")


def test_default_registry_has_one_provider_for_every_system_universe():
    registry = create_universe_provider_registry()

    assert registry.supported_universes == {
        "US100", "US2000", "US500", "US30",
        "VN30", "VNMID", "VN100", "VNSML", "VNALL",
    }


def test_registry_rejects_duplicate_provider_ownership():
    provider = Nasdaq100UniverseProvider(lambda url, params: b"{}")

    with pytest.raises(ValueError, match="Multiple providers configured for US100"):
        UniverseProviderRegistry((provider, provider))


def test_nasdaq_provider_parses_current_quote_list_shape():
    payload = {
        "data": {
            "date": "Aug 8, 2026",
            "data": {
                "rows": [
                    {
                        "symbol": "AAPL",
                        "companyName": "Apple Inc. Common Stock",
                        "sector": "Technology",
                    },
                    {
                        "symbol": "GOOG",
                        "companyName": "Alphabet Inc. Class C",
                        "sector": "Technology",
                    },
                ],
            },
        }
    }
    provider = Nasdaq100UniverseProvider(
        lambda url, params: json.dumps(payload).encode()
    )

    snapshot = provider.fetch("us100")

    assert snapshot.code == "US100"
    assert snapshot.effective_date == date(2026, 8, 8)
    assert snapshot.source == "nasdaq-quote-list"
    assert [row.canonical_ticker for row in snapshot.constituents] == [
        "AAPL", "GOOG",
    ]
    assert snapshot.constituents[0].exchange == "NASDAQ"


def test_ishares_provider_filters_non_equities_and_normalizes_known_classes():
    csv_text = """Fund Holdings as of,"Aug 7, 2026"
Inception Date,"May 22, 2000"
Ticker,Name,Sector,Asset Class,Exchange
MOGA,MOOG INC CLASS A,Industrials,Equity,NYSE
USD,USD CASH,Cash and/or Derivatives,Cash,-
XTSLA,BLK CASH FUND,Cash and/or Derivatives,Money Market,-
ADRO,CHINOOK THERAPEUTICS CVR,Health Care,Equity,NO MARKET (E.G. UNLISTED)
FOLD,AMICUS THERAPEUTICS INC,Health Care,Equity,NASDAQ
"""
    provider = IsharesRussell2000UniverseProvider(
        lambda url, params: csv_text.encode()
    )

    snapshot = provider.fetch("US2000")

    assert snapshot.effective_date == date(2026, 8, 7)
    assert [row.canonical_ticker for row in snapshot.constituents] == [
        "FOLD", "MOG-A",
    ]


def test_ishares_provider_rejects_product_page_fallback():
    provider = IsharesRussell2000UniverseProvider(
        lambda url, params: b"<!DOCTYPE html><html></html>"
    )

    with pytest.raises(UniverseProviderDataError, match="instead of holdings CSV"):
        provider.fetch("US2000")


@pytest.mark.parametrize(
    ("code", "html", "expected"),
    [
        (
            "US500",
            """<table><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th>
            <th>GICS Sub-Industry</th></tr><tr><td>BRK.B</td>
            <td>Berkshire Hathaway</td><td>Financials</td>
            <td>Multi-Sector Holdings</td></tr></table>""",
            "BRK-B",
        ),
        (
            "US30",
            """<table><tr><th>Company</th><th>Exchange</th><th>Symbol</th>
            <th>Industry</th></tr><tr><td>Apple</td><td>NASDAQ</td>
            <td>AAPL</td><td>Information technology</td></tr></table>""",
            "AAPL",
        ),
    ],
)
def test_wikipedia_provider_selects_the_named_constituent_table(
    code: str, html: str, expected: str
):
    provider = WikipediaUSIndexProvider(
        lambda url, params: html.encode()
    )

    snapshot = provider.fetch(code)

    assert [row.canonical_ticker for row in snapshot.constituents] == [expected]


class _FakeListing:
    def __init__(self) -> None:
        self.group_calls: list[str] = []
        self.metadata_calls = 0

    def symbols_by_group(self, group: str) -> pd.Series:
        self.group_calls.append(group)
        values = {
            "VN30": ["ACB", "FPT"],
            "VNMidCap": ["ANV"],
            "VNSmallCap": ["AAA", "AAM"],
        }
        return pd.Series(values[group], name="symbol")

    def all_symbols(self) -> pd.DataFrame:
        self.metadata_calls += 1
        return pd.DataFrame({
            "symbol": ["ACB", "FPT", "ANV", "AAA", "AAM"],
            "organ_name": ["ACB", "FPT Corporation", "ANV", "AAA", "AAM"],
        })

    def symbols_by_industries(self) -> pd.DataFrame:
        return pd.DataFrame({
            "symbol": ["ACB", "FPT"],
            "industry_code": [11, 6],
            "industry_name": ["Ngân hàng", "Công nghệ và thông tin"],
        })


def test_vnstock_provider_derives_composite_universes_and_caches_source_calls():
    listing = _FakeListing()
    provider = VnstockUniverseProvider(lambda: listing)

    vn100 = provider.fetch("VN100")
    vnall = provider.fetch("VNALL")
    vn30 = provider.fetch("VN30")

    assert {row.canonical_ticker for row in vn100.constituents} == {
        "ACB", "ANV", "FPT",
    }
    assert {row.canonical_ticker for row in vnall.constituents} == {
        "AAA", "AAM", "ACB", "ANV", "FPT",
    }
    assert {row.canonical_ticker for row in vn30.constituents} <= {
        row.canonical_ticker for row in vn100.constituents
    }
    assert listing.group_calls == ["VN30", "VNMidCap", "VNSmallCap"]
    assert listing.metadata_calls == 1
    fpt = next(row for row in vnall.constituents if row.canonical_ticker == "FPT")
    assert fpt.sector == "Information Technology"
    assert fpt.industry == "Công nghệ và thông tin"
