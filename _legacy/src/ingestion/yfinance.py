import os

import pandas as pd
import yfinance as yf

from src.shared.constants import HISTORICAL_DATA_START_DATE
from src.ingestion.base import DataIngestor


class YFinanceIngestor(DataIngestor):
    def __init__(self, ticker: str, start_date: str = HISTORICAL_DATA_START_DATE):
        self.ticker = ticker
        self.start_date = start_date
        self.source_dir = os.path.join(os.getcwd(), "re", "data", "yfinance")
        os.makedirs(self.source_dir, exist_ok=True)

    def get_data(self) -> pd.DataFrame:
        cached = self._check_daily_cache(self.source_dir, self.ticker)
        if cached is not None:
            return cached

        print(f"--- [Ingestor] Downloading {self.ticker} from Yahoo Finance ---")
        df = yf.download(self.ticker, start=self.start_date, progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty:
            raise ValueError(f"No data for {self.ticker}")

        df.index.name = 'Date'
        df = df[['Close', 'Open', 'High', 'Low']].dropna()

        self._save_cache(self.source_dir, self.ticker, df)
        return df
