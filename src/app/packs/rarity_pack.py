"""Rarity analysis pack (was SignalAnalysisPack)."""
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from src.shared.base import AnalysisPack, AnalysisResult
from src.shared.constants import COLOR_ACTIVE, COLOR_GROUP, DATE_FORMAT_DISPLAY
from src.shared.fmt import fmt_pct, fmt_price

from src.signals.base import BaseSignal
from src.signals.ahr999 import AHR999Signal
from src.signals.distance_from_peak import DistanceFromPeakSignal
from src.signals.ma_ratio import MARatioSignal

from src.analysis.rarity.events import EventStatus, NPEvent
from src.analysis.rarity.charts import create_price_signal_chart, create_distribution_chart
from src.analysis.rarity.tables import build_event_tree_df
from src.analysis.rarity.report import ReportGenerator

from src.app.ui import plot_chart, sidebar_data_source, sidebar_ticker_input


class RarityAnalysisPack(AnalysisPack):
    @property
    def pack_name(self) -> str:
        return "Signal Analysis"

    def render_sidebar(self) -> Dict[str, Any]:
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

    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> AnalysisResult:
        indicator: BaseSignal = config["signal"]

        try:
            signal_series = indicator.calculate(df)

            report_gen = ReportGenerator(ticker, indicator, df, signal_series, config["qr_threshold"])
            report_gen.calculate()
            display_report_text = report_gen.generate_display_report()
            stats_df, highlight_p = report_gen.build_stats_df()

            fig = create_price_signal_chart(ticker, df, signal_series, indicator)
            current_value = signal_series.iloc[-1]
            fig_dist = create_distribution_chart(signal_series, current_value, indicator.name)

            return AnalysisResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=df["Close"],
                signal_series=signal_series,
                data={
                    "fig": fig,
                    "fig_dist": fig_dist,
                    "signal": indicator,
                    "np_events": report_gen.np_events,
                    "qr_threshold": report_gen.qr_threshold,
                    "display_report_text": display_report_text,
                    "stats_df": stats_df,
                    "highlight_p": highlight_p,
                },
            )
        except Exception as e:
            return AnalysisResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=df["Close"] if "Close" in df.columns else pd.Series(dtype=float),
                signal_series=pd.Series(dtype=float),
                error=str(e),
            )

    @staticmethod
    def _render_stats_table(stats_df: pd.DataFrame) -> None:
        if stats_df.empty:
            return

        highlight_mask = stats_df["_highlight"].tolist()
        display_df = stats_df.drop(columns=["_highlight"])

        def _row_style(row: pd.Series):
            if highlight_mask[row.name]:
                return [COLOR_ACTIVE] * len(row)
            return [""] * len(row)

        styled = display_df.style.apply(_row_style, axis=1)
        n_rows = len(display_df)
        height = 38 + n_rows * 35

        st.dataframe(styled, hide_index=True, use_container_width=True, height=height)

    @staticmethod
    def _render_event_tree(np_events: List[NPEvent], qr_threshold: int) -> None:
        df = build_event_tree_df(np_events, qr_threshold)
        if df.empty:
            st.info("No significant events (all classified as Quick Recoveries).")
            return

        unrecovered_mask = df["_unrecovered"].tolist()
        level_zero_mask = (df["Lv"] == 0).tolist()
        display_df = df.drop(columns=["_unrecovered"])

        def _row_style(row: pd.Series):
            i = row.name
            if unrecovered_mask[i]:
                return [COLOR_ACTIVE] * len(row)
            if level_zero_mask[i]:
                return [COLOR_GROUP] * len(row)
            return [""] * len(row)

        styled = display_df.style.apply(_row_style, axis=1)
        row_height = 35
        header_height = 38
        height = header_height + min(len(display_df), 20) * row_height

        st.dataframe(
            styled,
            hide_index=True,
            use_container_width=True,
            height=height,
            column_config={
                "Lv":       st.column_config.NumberColumn("Lv"),
                "Start":    st.column_config.TextColumn("Start Date"),
                "Zone":     st.column_config.TextColumn("Zone"),
                "Entry":    st.column_config.TextColumn("Entry"),
                "Low":      st.column_config.TextColumn("Low"),
                "Low Date": st.column_config.TextColumn("Low Date"),
                "MAE %":    st.column_config.TextColumn("MAE %"),
                "→ Low":    st.column_config.NumberColumn("→ Low"),
                "Recovery": st.column_config.TextColumn("Recovery"),
                "→ Rec":    st.column_config.TextColumn("→ Rec"),
                "Children": st.column_config.NumberColumn("Children"),
            },
        )

        n_active = sum(unrecovered_mask)
        n_total = len(display_df)
        n_lv0 = sum(level_zero_mask)
        st.caption(
            f"{n_total} events shown  •  "
            f"🟡 {n_active} active (unrecovered)  •  "
            f"🔵 {n_lv0} top-level (Lv 0)  •  "
            f"QR threshold: ≤ {qr_threshold} days (hidden)"
        )

    def render_results(self, result: AnalysisResult) -> None:
        if result.error:
            st.error(f"❌ [{result.ticker}] {result.error}")
            return

        fig = result.data["fig"]
        fig_dist = result.data["fig_dist"]
        signal: BaseSignal = result.data["signal"]
        np_events: List[NPEvent] = result.data.get("np_events", [])
        qr_threshold: int = result.data.get("qr_threshold", 5)
        display_report_text: str = result.data.get("display_report_text", "")
        stats_df: pd.DataFrame = result.data.get("stats_df", pd.DataFrame())

        with st.expander(f"📊 Kết quả phân tích: {result.ticker}", expanded=True):
            st.subheader("📊 Thống kê các sự kiện NP")
            self._render_stats_table(stats_df)

            st.subheader("📝 Báo cáo phân tích")
            st.markdown(display_report_text, unsafe_allow_html=True)

            st.divider()

            st.subheader("🌳 Event Tree")
            self._render_event_tree(np_events, qr_threshold)

            with st.expander("📊 Xem Phân phối tín hiệu (Distribution)", expanded=True):
                plot_chart(fig_dist)

            with st.expander("📈 Xem Biểu đồ tín hiệu lịch sử", expanded=True):
                plot_chart(fig)

