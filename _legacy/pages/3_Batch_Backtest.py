import streamlit as st
from src.app.data_loader import load_data
from src.app.packs import BatchPositionPack

st.set_page_config(
    page_title="Batch Backtest",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📦 Batch Backtest")
st.markdown("Run a strategy across multiple symbols and compare results in a single summary table.")

pack = BatchPositionPack()
config = pack.render_sidebar()

tickers = config.get("tickers", [])
strategy = config.get("strategy")
data_source = config.get("data_source", "yfinance")

# Detect data source change → force start new
# Use _used_ suffix to avoid clashing with widget key batch_data_source
stored_ds = st.session_state.get("batch_ds_used")
if stored_ds is not None and stored_ds != data_source:
    st.session_state.pop("batch_results", None)
    st.session_state.pop("batch_strategy_label", None)
    st.session_state.pop("batch_ds_used", None)
    st.info("Data source changed — previous results cleared.")

has_results = bool(st.session_state.get("batch_results"))
using_group = config.get("symbol_group", "— type manually —") != "— type manually —"

# --- Sidebar buttons ---
run_btn = st.sidebar.button("🚀 Run Batch", type="primary", key="batch_run_btn")

new_btn = False
if has_results and not using_group:
    new_btn = st.sidebar.button("🗑 Start New", key="batch_new_btn")

# --- Start New ---
if new_btn:
    st.session_state.pop("batch_results", None)
    st.session_state.pop("batch_strategy_label", None)
    st.session_state.pop("batch_ds_used", None)
    st.rerun()

# --- Helpers ---
def _run_tickers(tickers_to_run):
    if not tickers_to_run:
        return []
    progress = st.progress(0)
    status = st.empty()
    results = []
    for i, ticker in enumerate(tickers_to_run):
        status.text(f"Processing {ticker} ({i + 1}/{len(tickers_to_run)})...")
        df = load_data(ticker, data_source)
        result = pack.run_computation(ticker, df, config)
        results.append(result)
        progress.progress((i + 1) / len(tickers_to_run))
    status.text("Done!")
    return results

# --- Run Batch (adds new tickers; replaces results when using a group) ---
if run_btn:
    if not tickers:
        st.error("Please enter at least one ticker.")
    elif not strategy:
        st.error("Please select a strategy.")
    else:
        if using_group:
            new_results = _run_tickers(tickers)
            st.session_state["batch_results"] = new_results
        else:
            existing = {r.ticker for r in st.session_state.get("batch_results", [])}
            new_tickers = [t for t in tickers if t not in existing]
            if not new_tickers:
                st.info("All entered tickers are already in the results.")
                st.stop()
            added = _run_tickers(new_tickers)
            st.session_state["batch_results"] = st.session_state.get("batch_results", []) + added
        st.session_state["batch_strategy_label"] = strategy.name
        st.session_state["batch_ds_used"] = data_source
        st.rerun()

# --- Render results ---
if st.session_state.get("batch_results"):
    pack.render_batch_results(
        st.session_state["batch_results"],
        strategy_label=st.session_state.get("batch_strategy_label", ""),
    )
