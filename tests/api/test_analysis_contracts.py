from __future__ import annotations

from api.main import app


RETIRED_ANALYSIS_PATHS = {
    "/backtest",
    "/sweep",
    "/factors/analyze",
    "/factors/universe",
    "/factors/regime",
}

CANONICAL_ANALYSIS_PATHS = {
    "/backtest/analyze",
    "/factors/rarity",
    "/factors/predefined-rarity",
    "/universe-stats/run",
    "/events/new-low-deep",
}


def test_legacy_symbol_and_provider_analysis_paths_are_not_registered():
    paths = set(app.openapi()["paths"])

    assert RETIRED_ANALYSIS_PATHS.isdisjoint(paths)
    assert CANONICAL_ANALYSIS_PATHS <= paths


def test_canonical_analysis_requests_do_not_accept_symbol_or_data_source_identity():
    schema = app.openapi()

    for path in CANONICAL_ANALYSIS_PATHS:
        operation = schema["paths"][path]["post"]
        request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        reference = request_schema["$ref"].rsplit("/", 1)[-1]
        properties = schema["components"]["schemas"][reference]["properties"]

        assert "symbol" not in properties, path
        assert "symbols" not in properties, path
        assert "data_source" not in properties, path


def test_single_instrument_analysis_responses_do_not_claim_implicit_refresh():
    schema = app.openapi()["components"]["schemas"]

    for name in ("SingleInstrumentAnalysisResponse", "RarityAnalysisResponse"):
        properties = schema[name]["properties"]
        assert "refreshed" not in properties, name
        assert "refresh_warning" not in properties, name
        assert {
            "expected_last_session",
            "data_last_session",
            "is_stale",
            "price_source",
            "price_basis",
        } <= properties.keys(), name

    history = schema["InstrumentPriceHistoryResponse"]["properties"]
    assert {"expected_last_session", "is_stale"} <= history.keys()
    assert {"trailing_pe_source", "trailing_pe_fetched_at"} <= history.keys()
    assert "fundamentals_fields" not in history
    assert {"price_basis", "fetched_at"}.isdisjoint(history)


def test_openapi_has_no_legacy_company_or_market_identity_contracts():
    schema = app.openapi()
    paths = set(schema["paths"])

    assert {
        "/company/lists",
        "/company/watchlists",
        "/company/price-history",
        "/build/venues",
    }.isdisjoint(paths)
    assert "/crypto/markets" not in paths
    assert "/instruments/crypto-spot" in paths
    assert "/crypto/instruments" not in paths
    assert "SingleTickerAnalysisResponse" not in schema["components"]["schemas"]

    response = schema["components"]["schemas"]["SingleInstrumentAnalysisResponse"]
    assert "instrument_prices" in response["properties"]
    assert "ticker_prices" not in response["properties"]
