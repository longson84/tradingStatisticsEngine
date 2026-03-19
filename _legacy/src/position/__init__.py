"""Single-position simulation: signals → trades + equity. No Streamlit."""
from src.position.trade import Trade
from src.position.engine import build_trades, build_equity_curve
from src.position.current import CurrentPosition, get_current_position

__all__ = [
    "Trade",
    "build_trades",
    "build_equity_curve",
    "CurrentPosition",
    "get_current_position",
]
