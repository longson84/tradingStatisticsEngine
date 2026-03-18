"""@st.cache_data wrappers around ingestion."""
import streamlit as st
from src.ingestion import YFinanceIngestor, VnStockIngestor


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

"""
TODO: 
- the load_data does not need to know about vnstock_source, it should be passed to the ingestor
- the load_data just needs to know about the data source
"""
def load_data(ticker: str, data_source: str = "yfinance", vnstock_source: str = "KBS"):
    if data_source == "vnstock":
        return _load_vnstock(ticker, vnstock_source)
    return _load_yfinance(ticker)
