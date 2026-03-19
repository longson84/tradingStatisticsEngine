from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


@dataclass
class PackResult:
    ticker: str
    pack_name: str
    price_series: pd.Series
    factor_series: Optional[pd.Series] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class BasePack(ABC):
    """Root abstract base for all packs.

    Pack hierarchy:
        BasePack
        ├── BaseAnalysisPack   — factor analysis packs (RarityAnalysisPack, …)
        └── BaseStrategyPack   — position-based packs (PositionPack, BatchPositionPack)
            BaseSweepPack      — parameter sweep packs (ParameterSweepPack)
    """

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


class BaseAnalysisPack(BasePack):
    """Base for factor analysis packs.

    Subclasses implement the standard BasePack contract:
    render_sidebar / run_computation / render_results.
    """


class BaseSweepPack(BasePack):
    """Base for parameter sweep packs.

    Sweep packs do not use the single-ticker run_computation / render_results
    flow. Those methods raise NotImplementedError to make accidental calls
    loud. The actual contract is run_sweep + render_sweep_results.
    """

    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> PackResult:
        raise NotImplementedError(
            f"{type(self).__name__} is a sweep pack. Use run_sweep() instead of run_computation()."
        )

    def render_results(self, result: PackResult) -> None:
        raise NotImplementedError(
            f"{type(self).__name__} is a sweep pack. Use render_sweep_results() instead of render_results()."
        )

    @abstractmethod
    def run_sweep(
        self, df: pd.DataFrame, config: Dict
    ) -> Tuple[List[Tuple[int, str, Dict]], List[int]]:
        """Run computation across all sweep lengths. Returns (results, skipped)."""
        ...

    @abstractmethod
    def render_sweep_results(
        self,
        sweep_results: List[Tuple[int, str, Dict]],
        config: Dict,
        skipped: List[int],
    ) -> None:
        """Streamlit rendering for the full sweep output."""
        ...
