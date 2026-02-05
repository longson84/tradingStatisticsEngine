import pandas as pd
import yfinance as yf
from abc import ABC, abstractmethod

class DataIngestor(ABC):
    """Lớp trừu tượng cho mọi nguồn dữ liệu."""
    
    @abstractmethod
    def get_data(self) -> pd.DataFrame:
        pass

class YFinanceIngestor(DataIngestor):
    def __init__(self, ticker: str, start_date: str = "2015-01-01"):
        self.ticker = ticker
        self.start_date = start_date

    def get_data(self) -> pd.DataFrame:
        print(f"--- [Ingestor] Đang tải dữ liệu {self.ticker} từ Yahoo Finance ---")
        df = yf.download(self.ticker, start=self.start_date, progress=False)
        
        # Chuẩn hóa MultiIndex (Fix lỗi yfinance mới)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            raise ValueError(f"Không có dữ liệu cho {self.ticker}")
            
        # Chuẩn hóa tên cột để thống nhất hệ thống (bắt buộc phải có Date và Close)
        df.index.name = 'Date'
        return df[['Close', 'Open', 'High', 'Low']].dropna()

class CSVIngestor(DataIngestor):
    """Dành cho việc mở rộng sau này: Đọc từ file CSV local"""
    def __init__(self, filepath: str):
        self.filepath = filepath

    def get_data(self) -> pd.DataFrame:
        print(f"--- [Ingestor] Đang đọc file CSV: {self.filepath} ---")
        df = pd.read_csv(self.filepath, parse_dates=['Date'], index_col='Date')
        return df