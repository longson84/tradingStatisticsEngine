import streamlit as st
from src.app.data_loader import load_data
from src.app.packs import RarityAnalysisPack

st.set_page_config(
    page_title="Factor Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 Factor Analysis")
st.markdown("Rarity zones, percentile analysis, and drawdown statistics for trading factors.")

pack = RarityAnalysisPack()
config = pack.render_sidebar()

if st.sidebar.button("🚀 Analyse", type="primary", key="factor_run_btn") or st.session_state.get(
    "factor_submitted"
):
    st.session_state["factor_submitted"] = True

    tickers = config.get("tickers", [])
    factor = config.get("factor")

    if not tickers:
        st.error("Please enter at least one ticker.")
    elif not factor:
        st.error("Please select a valid factor.")
    else:
        progress = st.progress(0)
        status = st.empty()

        for i, ticker in enumerate(tickers):
            status.text(f"Processing {ticker} ({i + 1}/{len(tickers)})...")
            df = load_data(ticker, config.get("data_source", "yfinance"))
            result = pack.run_computation(ticker, df, config)
            pack.render_results(result)
            progress.progress((i + 1) / len(tickers))

        status.text("Done!")
