import streamlit as st

st.set_page_config(
    page_title="Trading Statistics Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Trading Statistics Engine")
st.markdown(
    """
Welcome! Use the navigation on the left to choose a tool:

### Pages

| Page | Description |
|------|-------------|
| **📈 Factor Analysis** | Analyse factor rarity, percentile zones, and historical drawdown statistics for any ticker. Supports AHR999, Distance-from-Peak (N-day), and MA-ratio factors. |
| **🔁 Strategy Backtest** | Backtest trading strategies (Price vs MA, MA Crossover, Bollinger Bands, Donchian Breakout) with entry/exit lags. Shows win rate, total return, and full trade log. |
| **📦 Batch Backtest** | Run a strategy across multiple symbols and compare results in a single summary table. |
| **🔬 Parameter Sweep** | Sweep a single parameter (MA length) across a ticker and compare results side-by-side. |

---

*Factors* are continuous values computed from price data.
*Strategies* apply rules to factors to generate buy/sell events.
"""
)
