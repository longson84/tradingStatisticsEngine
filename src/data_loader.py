import streamlit as st
from src.ingestor import YFinanceIngestor, VnStockIngestor


@st.cache_data(ttl=3600)
def _load_yfinance(ticker: str):
    return YFinanceIngestor(ticker).get_data()


@st.cache_data(ttl=3600)
def _load_vnstock(ticker: str, vnstock_source: str):
    return VnStockIngestor(ticker, vnstock_source).get_data()


@st.cache_data(ttl=3600)
def load_vnstock_group(group: str) -> list:
    from vnstock.explorer.vci.listing import Listing
    return Listing().symbols_by_group(group=group).tolist()


def load_data(ticker: str, data_source: str = "yfinance", vnstock_source: str = "KBS"):
    if data_source == "vnstock":
        return _load_vnstock(ticker, vnstock_source)
    return _load_yfinance(ticker)
