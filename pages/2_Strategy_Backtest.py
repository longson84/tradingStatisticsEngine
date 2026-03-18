import streamlit as st
from src.app.data_loader import load_data
from src.app.packs import PositionPack

st.set_page_config(
    page_title="Strategy Backtest",
    page_icon="🔁",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔁 Strategy Backtest")
st.markdown("MA-based trading strategies with trade-level backtesting, win rate, and performance metrics.")

pack = PositionPack()
config = pack.render_sidebar()

if st.sidebar.button("🚀 Run Backtest", type="primary", key="strat_run_btn") or st.session_state.get(
    "strategy_submitted"
):
    st.session_state["strategy_submitted"] = True

    tickers = config.get("tickers", [])
    strategy = config.get("strategy")

    if not tickers:
        st.error("Please enter at least one ticker.")
    elif not strategy:
        st.error("Please select a strategy.")
    else:
        progress = st.progress(0)
        status = st.empty()

        for i, ticker in enumerate(tickers):
            status.text(f"Processing {ticker} ({i + 1}/{len(tickers)})...")
            df = load_data(ticker, config.get("data_source", "yfinance"), config.get("vnstock_source", "KBS"))
            result = pack.run_computation(ticker, df, config)
            pack.render_results(result)
            progress.progress((i + 1) / len(tickers))

        status.text("Done!")
