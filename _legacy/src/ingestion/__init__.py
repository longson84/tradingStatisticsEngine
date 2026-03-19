"""Data download + disk cache — no Streamlit dependencies."""
from src.ingestion.base import DataIngestor
from src.ingestion.yfinance import YFinanceIngestor
from src.ingestion.vnstock import VnStockIngestor
from src.ingestion.csv import CSVIngestor

__all__ = ["DataIngestor", "YFinanceIngestor", "VnStockIngestor", "CSVIngestor"]
