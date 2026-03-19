"""Pure statistical utilities — no domain logic, no I/O."""
import numpy as np
import pandas as pd

from src.shared.constants import CALCULATE_PERCENTILES


def calculate_factor_percentiles(factor_series: pd.Series, percentiles=CALCULATE_PERCENTILES) -> pd.DataFrame:
    """Return a DataFrame of factor threshold values at each percentile."""
    clean = factor_series.dropna()
    return pd.DataFrame([
        {"Percentile": p, "Threshold": np.percentile(clean, p)}
        for p in percentiles
    ])
