import streamlit as st
from src.data_loader import load_data
from src.strategy.sweep_pack import ParameterSweepPack

st.set_page_config(
    page_title="Parameter Sweep",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔬 Parameter Sweep")
st.markdown("Sweep a single parameter (MA length) across a ticker and compare results side-by-side.")

pack = ParameterSweepPack()
config = pack.render_sidebar()

ticker = config.get("ticker", "")
data_source = config.get("data_source", "yfinance")

# Detect data source change → clear previous results
stored_ds = st.session_state.get("sweep_ds_used")
if stored_ds is not None and stored_ds != data_source:
    st.session_state.pop("sweep_results", None)
    st.session_state.pop("sweep_skipped", None)
    st.session_state.pop("sweep_config", None)
    st.session_state.pop("sweep_ds_used", None)
    st.info("Data source changed — previous results cleared.")

has_results = bool(st.session_state.get("sweep_results"))

# --- Sidebar buttons ---
run_btn = st.sidebar.button("🚀 Run Sweep", type="primary", key="sweep_run_btn")

new_btn = False
if has_results:
    new_btn = st.sidebar.button("🗑 Start New", key="sweep_new_btn")

# --- Start New ---
if new_btn:
    st.session_state.pop("sweep_results", None)
    st.session_state.pop("sweep_skipped", None)
    st.session_state.pop("sweep_config", None)
    st.session_state.pop("sweep_ds_used", None)
    st.rerun()

# --- Run Sweep ---
if run_btn:
    if not ticker:
        st.error("Please enter a ticker.")
    elif not config.get("sweep_lengths"):
        st.error("Sweep range produced no lengths. Check Min/Max/Step.")
    else:
        progress = st.progress(0)
        status = st.empty()

        status.text(f"Loading data for {ticker}...")
        df = load_data(ticker, data_source, "KBS")
        progress.progress(0.1)

        status.text(f"Running sweep ({len(config['sweep_lengths'])} variants)...")
        results, skipped = pack.run_sweep(df, config)
        progress.progress(1.0)
        status.text("Done!")

        st.session_state["sweep_results"] = results
        st.session_state["sweep_skipped"] = skipped
        st.session_state["sweep_config"] = config
        st.session_state["sweep_ds_used"] = data_source
        st.rerun()

# --- Render results ---
if st.session_state.get("sweep_results"):
    pack.render_sweep_results(
        st.session_state["sweep_results"],
        st.session_state["sweep_config"],
        st.session_state.get("sweep_skipped", []),
    )
