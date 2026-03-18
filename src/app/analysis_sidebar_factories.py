"""Analysis sidebar factories — one function per analysis pack."""
from typing import Any, Dict

import streamlit as st

from src.factors.ahr999 import AHR999Factor
from src.factors.distance_from_peak import DistanceFromPeakFactor
from src.factors.ma_ratio import MARatioFactor
from src.app.ui import sidebar_data_source, sidebar_ticker_input


def rarity_analysis_sidebar() -> Dict[str, Any]:
    """Render the rarity analysis sidebar and return the config dict."""
    st.sidebar.header("Factor Analysis")

    data_source = sidebar_data_source("factor")
    tickers = sidebar_ticker_input(data_source, "factor", multi=True)

    base_factors = [
        DistanceFromPeakFactor(200),
        DistanceFromPeakFactor(150),
        DistanceFromPeakFactor(100),
        DistanceFromPeakFactor(50),
        AHR999Factor(),
    ]
    factor_map: Dict[str, Any] = {f.name: f for f in base_factors}
    factor_map["Khoảng cách từ đỉnh (Tùy chỉnh)"] = "CUSTOM_DIST"
    factor_map["MA vs Price (Tùy chỉnh)"] = "CUSTOM_MA"

    available_names = []
    if tickers:
        for name, f_obj in factor_map.items():
            if f_obj in ("CUSTOM_DIST", "CUSTOM_MA"):
                available_names.append(name)
                continue
            if all(f_obj.is_applicable(t) for t in tickers):
                available_names.append(name)
    else:
        available_names = list(factor_map.keys())

    selected_name = st.sidebar.selectbox(
        "Factor:",
        options=available_names,
        index=0 if available_names else None,
        key="factor_selector",
    )

    final_factor: Any = None
    if selected_name and factor_map[selected_name] == "CUSTOM_DIST":
        window = st.sidebar.number_input(
            "Window (days):", min_value=10, value=200, step=10, key="factor_custom_window"
        )
        final_factor = DistanceFromPeakFactor(int(window))
    elif selected_name and factor_map[selected_name] == "CUSTOM_MA":
        col1, col2 = st.sidebar.columns(2)
        ma_type = col1.selectbox("MA Type:", ["SMA", "EMA", "WMA"], key="factor_ma_type")
        ma_len = col2.number_input("Length:", min_value=2, value=200, step=1, key="factor_ma_len")
        final_factor = MARatioFactor(ma_type, int(ma_len))
    elif selected_name:
        final_factor = factor_map[selected_name]

    st.sidebar.divider()
    qr_threshold = int(st.sidebar.number_input(
        "Quick Recovery (days):",
        min_value=2,
        value=5,
        step=1,
        help="Events that recover within this many trading days are classified as Quick Recoveries and excluded from MAE statistics.",
        key="factor_qr_threshold",
    ))

    return {
        "tickers": tickers,
        "factor": final_factor,
        "qr_threshold": qr_threshold,
        "data_source": data_source,
        "vnstock_source": "KBS",
    }
