"""Analysis sidebar factories — one function per analysis pack."""
from typing import Any, Dict

import streamlit as st

from src.signals.ahr999 import AHR999Signal
from src.signals.distance_from_peak import DistanceFromPeakSignal
from src.signals.ma_ratio import MARatioSignal
from src.app.ui import sidebar_data_source, sidebar_ticker_input


def rarity_analysis_sidebar() -> Dict[str, Any]:
    """Render the rarity analysis sidebar and return the config dict."""
    st.sidebar.header("Signal Analysis")

    data_source = sidebar_data_source("signal")
    tickers = sidebar_ticker_input(data_source, "signal", multi=True)

    base_signals = [
        DistanceFromPeakSignal(200),
        DistanceFromPeakSignal(150),
        DistanceFromPeakSignal(100),
        DistanceFromPeakSignal(50),
        AHR999Signal(),
    ]
    signal_map: Dict[str, Any] = {s.name: s for s in base_signals}
    signal_map["Khoảng cách từ đỉnh (Tùy chỉnh)"] = "CUSTOM_DIST"
    signal_map["MA vs Price (Tùy chỉnh)"] = "CUSTOM_MA"

    available_names = []
    if tickers:
        for name, s_obj in signal_map.items():
            if s_obj in ("CUSTOM_DIST", "CUSTOM_MA"):
                available_names.append(name)
                continue
            if all(s_obj.is_applicable(t) for t in tickers):
                available_names.append(name)
    else:
        available_names = list(signal_map.keys())

    selected_name = st.sidebar.selectbox(
        "Signal:",
        options=available_names,
        index=0 if available_names else None,
        key="signal_selector",
    )

    final_signal: Any = None
    if selected_name and signal_map[selected_name] == "CUSTOM_DIST":
        window = st.sidebar.number_input(
            "Window (days):", min_value=10, value=200, step=10, key="signal_custom_window"
        )
        final_signal = DistanceFromPeakSignal(int(window))
    elif selected_name and signal_map[selected_name] == "CUSTOM_MA":
        col1, col2 = st.sidebar.columns(2)
        ma_type = col1.selectbox("MA Type:", ["SMA", "EMA", "WMA"], key="signal_ma_type")
        ma_len = col2.number_input("Length:", min_value=2, value=200, step=1, key="signal_ma_len")
        final_signal = MARatioSignal(ma_type, int(ma_len))
    elif selected_name:
        final_signal = signal_map[selected_name]

    st.sidebar.divider()
    qr_threshold = int(st.sidebar.number_input(
        "Quick Recovery (days):",
        min_value=2,
        value=5,
        step=1,
        help="Events that recover within this many trading days are classified as Quick Recoveries and excluded from MAE statistics.",
        key="signal_qr_threshold",
    ))

    return {
        "tickers": tickers,
        "signal": final_signal,
        "qr_threshold": qr_threshold,
        "data_source": data_source,
        "vnstock_source": "KBS",
    }
