import pandas as pd

from src.ingestion.base import DataIngestor


class CSVIngestor(DataIngestor):
    """Read from a local CSV file."""

    def __init__(self, filepath: str):
        self.filepath = filepath

    def get_data(self) -> pd.DataFrame:
        print(f"--- [Ingestor] Reading CSV: {self.filepath} ---")
        df = pd.read_csv(self.filepath, parse_dates=['Date'], index_col='Date')
        return df
