import streamlit as st
from src.data_loader import load_data
from src.signal.pack import SignalAnalysisPack

st.set_page_config(
    page_title="Signal Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 Signal Analysis")
st.markdown("Rarity zones, percentile analysis, and drawdown statistics for trading signals.")

pack = SignalAnalysisPack()
config = pack.render_sidebar()

if st.sidebar.button("🚀 Analyse", type="primary", key="signal_run_btn") or st.session_state.get(
    "signal_submitted"
):
    st.session_state["signal_submitted"] = True

    tickers = config.get("tickers", [])
    signal = config.get("signal")

    if not tickers:
        st.error("Please enter at least one ticker.")
    elif not signal:
        st.error("Please select a valid signal.")
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
