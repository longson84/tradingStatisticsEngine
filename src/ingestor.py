import pandas as pd
import yfinance as yf
import os
import glob
from datetime import datetime
from abc import ABC, abstractmethod

class DataIngestor(ABC):
    """Lớp trừu tượng cho mọi nguồn dữ liệu."""
    
    @abstractmethod
    def get_data(self) -> pd.DataFrame:
        pass

class YFinanceIngestor(DataIngestor):
    def __init__(self, ticker: str, start_date: str = "1990-01-01"):
        self.ticker = ticker
        self.start_date = start_date
        # Tạo folder data riêng cho source này trong folder re/data
        self.source_dir = os.path.join(os.getcwd(), "re", "data", "yfinance")
        os.makedirs(self.source_dir, exist_ok=True)

    def get_data(self) -> pd.DataFrame:
        # 1. Kiểm tra cache trong ngày
        today_str = datetime.now().strftime("%Y%m%d")
        # Pattern: YYYYMMDD*_{ticker}.csv (để match với timestamp bắt đầu bằng ngày hôm nay)
        pattern = os.path.join(self.source_dir, f"{today_str}*_{self.ticker}.csv")
        existing_files = glob.glob(pattern)
        
        if existing_files:
            # Lấy file đầu tiên tìm thấy (hoặc file mới nhất nếu muốn kỹ hơn)
            file_path = sorted(existing_files)[-1] # Lấy cái mới nhất
            print(f"--- [Ingestor] Sử dụng dữ liệu cache: {os.path.basename(file_path)} ---")
            try:
                df = pd.read_csv(file_path, parse_dates=['Date'], index_col='Date')
                return df
            except Exception as e:
                print(f"Lỗi đọc cache: {e}. Tiến hành tải lại...")

        # 2. Nếu chưa có hoặc lỗi, tải mới
        print(f"--- [Ingestor] Đang tải dữ liệu {self.ticker} từ Yahoo Finance ---")
        df = yf.download(self.ticker, start=self.start_date, progress=False)
        
        # Chuẩn hóa MultiIndex (Fix lỗi yfinance mới)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            raise ValueError(f"Không có dữ liệu cho {self.ticker}")
            
        # Chuẩn hóa tên cột để thống nhất hệ thống (bắt buộc phải có Date và Close)
        df.index.name = 'Date'
        df = df[['Close', 'Open', 'High', 'Low']].dropna()
        
        # 3. Lưu cache
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{self.ticker}.csv"
        file_path = os.path.join(self.source_dir, filename)
        
        try:
            df.to_csv(file_path)
            print(f"--- [Ingestor] Đã lưu dữ liệu: {filename} ---")
        except Exception as e:
            print(f"Không thể lưu cache: {e}")
            
        return df

class CSVIngestor(DataIngestor):
    """Dành cho việc mở rộng sau này: Đọc từ file CSV local"""
    def __init__(self, filepath: str):
        self.filepath = filepath

    def get_data(self) -> pd.DataFrame:
        print(f"--- [Ingestor] Đang đọc file CSV: {self.filepath} ---")
        df = pd.read_csv(self.filepath, parse_dates=['Date'], index_col='Date')
        return df
