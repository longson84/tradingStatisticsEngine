import os
from datetime import datetime

import pandas as pd

from src.ingestion.base import DataIngestor

VNSTOCK_START_DATE = '2000-01-01'


class VnStockIngestor(DataIngestor):
    def __init__(self, symbol: str, vnstock_source: str = 'KBS'):
        self.symbol = symbol.upper()
        self.vnstock_source = vnstock_source
        self.source_dir = os.path.join(os.getcwd(), "re", "data", f"vnstock_{vnstock_source.lower()}")
        os.makedirs(self.source_dir, exist_ok=True)

    def get_data(self) -> pd.DataFrame:
        cached = self._check_daily_cache(self.source_dir, self.symbol)
        if cached is not None:
            return cached

        from vnstock import Quote
        end_date = datetime.now().strftime('%Y-%m-%d')
        fallback = 'VCI' if self.vnstock_source == 'KBS' else 'KBS'
        sources_to_try = [self.vnstock_source, fallback]

        raw = None
        for source in sources_to_try:
            print(f"--- [VnStockIngestor] Fetching {self.symbol} from vnstock ({source}) ---")
            try:
                q = Quote(symbol=self.symbol, source=source)
                raw = q.history(start=VNSTOCK_START_DATE, end=end_date, interval='1D')
                if raw is not None and not raw.empty:
                    print(f"--- [VnStockIngestor] Success with source: {source} ---")
                    break
                print(f"--- [VnStockIngestor] Empty response from {source}, trying fallback ---")
            except Exception as e:
                print(f"--- [VnStockIngestor] {source} failed ({e}), trying fallback ---")

        if raw is None or raw.empty:
            raise ValueError(f"No data for {self.symbol} from any vnstock source (tried: {sources_to_try})")

        raw['time'] = pd.to_datetime(raw['time']).dt.normalize()
        raw = raw.set_index('time')
        raw.index.name = 'Date'
        raw = raw.rename(columns={'close': 'Close', 'open': 'Open', 'high': 'High', 'low': 'Low'})
        df = raw[['Close', 'Open', 'High', 'Low']].dropna()

        self._save_cache(self.source_dir, self.symbol, df)
        return df
