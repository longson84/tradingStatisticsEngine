from datetime import datetime
from typing import Any, Dict

import pandas as pd
import streamlit as st

from src.base import AnalysisPack, AnalysisResult
from src.signal.signals import AHR999Signal, BaseSignal, DistanceFromPeakSignal, MASignal
from src.signal.report import ReportGenerator
from src.signal.visualizer import ChartVisualizer


class SignalAnalysisPack(AnalysisPack):
    @property
    def pack_name(self) -> str:
        return "Signal Analysis"

    def render_sidebar(self) -> Dict[str, Any]:
        st.sidebar.header("Signal Analysis")

        ticker_input = st.sidebar.text_input(
            "Tickers (space-separated):",
            value="BTC-USD",
            key="signal_ticker_input",
            help="e.g. BTC-USD ETH-USD MSFT",
        )
        tickers = [t.strip().upper() for t in ticker_input.split() if t.strip()]

        # Build signal options
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

        # Filter by applicability across all tickers
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
            final_signal = MASignal(ma_type, int(ma_len))
        elif selected_name:
            final_signal = signal_map[selected_name]

        return {"tickers": tickers, "signal": final_signal}

    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> AnalysisResult:
        signal: BaseSignal = config["signal"]

        try:
            signal_series = signal.calculate(df)

            report_gen = ReportGenerator(ticker, signal, df, signal_series)
            report_gen.calculate()
            report_text = report_gen.generate_text_report()

            fig = ChartVisualizer.create_chart(ticker, df, signal_series, signal)
            current_value = signal_series.iloc[-1]
            fig_dist = ChartVisualizer.create_distribution_chart(
                signal_series, current_value, signal.name
            )

            return AnalysisResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=df["Close"],
                signal_series=signal_series,
                data={
                    "report_text": report_text,
                    "fig": fig,
                    "fig_dist": fig_dist,
                    "signal": signal,
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

    def render_results(self, result: AnalysisResult) -> None:
        if result.error:
            st.error(f"❌ [{result.ticker}] {result.error}")
            return

        report_text: str = result.data["report_text"]
        fig = result.data["fig"]
        fig_dist = result.data["fig_dist"]
        signal: BaseSignal = result.data["signal"]

        with st.expander(f"📊 Kết quả phân tích: {result.ticker}", expanded=True):
            st.subheader("📝 Báo cáo phân tích")
            st.markdown(report_text, unsafe_allow_html=True)

            st.divider()

            with st.expander("📊 Xem Phân phối tín hiệu (Distribution)", expanded=True):
                try:
                    st.plotly_chart(fig_dist, width="stretch")
                except TypeError:
                    st.plotly_chart(fig_dist, use_container_width=True)

            with st.expander("📈 Xem Biểu đồ tín hiệu lịch sử", expanded=True):
                try:
                    st.plotly_chart(fig, width="stretch")
                except TypeError:
                    st.plotly_chart(fig, use_container_width=True)

            st.subheader("Tải về kết quả")
            timestamp = datetime.now().strftime("%y%m%d")
            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    label="📥 Tải Báo Cáo (.md)",
                    data=report_text,
                    file_name=f"{timestamp}_{result.ticker}_Report.md",
                    mime="text/markdown",
                    key=f"sig_dl_md_{result.ticker}",
                )

            with col2:
                try:
                    img_bytes = fig.to_image(format="png", width=1200, height=800, scale=2)
                    st.download_button(
                        label="📥 Tải Biểu Đồ (.png)",
                        data=img_bytes,
                        file_name=f"{timestamp}_{result.ticker}_Chart.png",
                        mime="image/png",
                        key=f"sig_dl_png_{result.ticker}",
                    )
                except Exception:
                    html_bytes = fig.to_html()
                    st.download_button(
                        label="📥 Tải Biểu Đồ (.html)",
                        data=html_bytes,
                        file_name=f"{timestamp}_{result.ticker}_Chart.html",
                        mime="text/html",
                        key=f"sig_dl_html_{result.ticker}",
                    )
                    st.caption("⚠️ PNG unavailable — downloading HTML instead.")
