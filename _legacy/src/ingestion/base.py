import os
import glob
from datetime import datetime
from abc import ABC, abstractmethod

import pandas as pd


class DataIngestor(ABC):
    """Abstract base class for all data sources."""

    @abstractmethod
    def get_data(self) -> pd.DataFrame:
        pass

    @staticmethod
    def _check_daily_cache(source_dir: str, symbol: str) -> pd.DataFrame | None:
        """Check for a cached file from today. Returns DataFrame or None."""
        today_str = datetime.now().strftime("%Y%m%d")
        pattern = os.path.join(source_dir, f"{today_str}*_{symbol}.csv")
        existing_files = glob.glob(pattern)

        if existing_files:
            file_path = sorted(existing_files)[-1]
            print(f"--- [Ingestor] Using cache: {os.path.basename(file_path)} ---")
            try:
                return pd.read_csv(file_path, parse_dates=['Date'], index_col='Date')
            except Exception as e:
                print(f"Cache read error: {e}. Re-fetching...")
        return None

    @staticmethod
    def _save_cache(source_dir: str, symbol: str, df: pd.DataFrame) -> None:
        """Save DataFrame to timestamped CSV cache."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{symbol}.csv"
        file_path = os.path.join(source_dir, filename)
        try:
            df.to_csv(file_path)
            print(f"--- [Ingestor] Saved: {filename} ---")
        except Exception as e:
            print(f"Cache write error: {e}")
