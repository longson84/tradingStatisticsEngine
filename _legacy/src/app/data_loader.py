"""@st.cache_data wrappers around ingestion."""
import streamlit as st
from src.ingestion import YFinanceIngestor, VnStockIngestor


@st.cache_data(ttl=3600)
def _load_yfinance(ticker: str):
    return YFinanceIngestor(ticker).get_data()


@st.cache_data(ttl=3600)
def _load_vnstock(ticker: str):
    return VnStockIngestor(ticker).get_data()


@st.cache_data(ttl=3600)
def load_vnstock_group(group: str) -> list:
    from vnstock.explorer.vci.listing import Listing
    return Listing().symbols_by_group(group=group).tolist()


_LOADERS = {
    "yfinance": _load_yfinance,
    "vnstock": _load_vnstock,
}


def load_data(ticker: str, data_source: str = "yfinance"):
    loader = _LOADERS.get(data_source)
    if loader is None:
        raise ValueError(f"Unknown data source: {data_source!r}")
    return loader(ticker)
