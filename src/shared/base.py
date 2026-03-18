from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import pandas as pd


@dataclass
class PackResult:
    ticker: str
    pack_name: str
    price_series: pd.Series
    signal_series: Optional[pd.Series] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class BasePack(ABC):
    @property
    @abstractmethod
    def pack_name(self) -> str: ...

    @abstractmethod
    def render_sidebar(self) -> Dict[str, Any]:
        """Streamlit widgets → plain config dict. MAY use Streamlit."""
        ...

    @abstractmethod
    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> PackResult:
        """Pure computation. MUST NOT import or call Streamlit."""
        ...

    @abstractmethod
    def render_results(self, result: PackResult) -> None:
        """Streamlit rendering. MAY use Streamlit."""
        ...
