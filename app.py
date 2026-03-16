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
| **📈 Signal Analysis** | Analyse signal rarity, percentile zones, and historical drawdown statistics for any ticker. Supports AHR999, Distance-from-Peak (N-day), and MA-ratio signals. |
| **🔁 Strategy Backtest** | Backtest MA-based trading strategies (Price vs MA, MA Crossover) with entry/exit lags. Shows win rate, total return, profit factor, and full trade log. |

---

*Signals* are continuous values computed from price data.
*Strategies* apply rules to signals to generate buy/sell events.
"""
)
