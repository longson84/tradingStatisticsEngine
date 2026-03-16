import streamlit as st
from src.ingestor import YFinanceIngestor


@st.cache_data(ttl=3600)
def load_data(ticker: str):
    return YFinanceIngestor(ticker).get_data()
