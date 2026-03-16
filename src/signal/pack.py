from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from src.base import AnalysisPack, AnalysisResult
from src.signal.analytics import NPEvent
from src.constants import COLOR_ACTIVE, COLOR_GROUP, DATE_FORMAT_DISPLAY, fmt_price, fmt_pct
from src.signal.signals import AHR999Signal, BaseSignal, DistanceFromPeakSignal, MASignal
from src.signal.report import ReportGenerator
from src.signal.visualizer import ChartVisualizer


class SignalAnalysisPack(AnalysisPack):
    @property
    def pack_name(self) -> str:
        return "Signal Analysis"

    def render_sidebar(self) -> Dict[str, Any]:
        st.sidebar.header("Signal Analysis")

        data_source = st.sidebar.selectbox(
            "Data Source:",
            ["yfinance", "vnstock"],
            key="signal_data_source",
            help="yfinance: global tickers (BTC-USD, AAPL…) | vnstock: Vietnamese stocks (VCB, VIC…)",
        )
        default_ticker = "BTC-USD" if data_source == "yfinance" else "VCB"
        ticker_input = st.sidebar.text_input(
            "Tickers (space-separated):",
            value=default_ticker,
            key="signal_ticker_input",
            help="e.g. BTC-USD ETH-USD MSFT" if data_source == "yfinance" else "e.g. VCB VIC GMD",
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
        signal: BaseSignal = config["signal"]

        try:
            signal_series = signal.calculate(df)

            report_gen = ReportGenerator(ticker, signal, df, signal_series, config["qr_threshold"])
            report_gen.calculate()
            report_text = report_gen.generate_text_report()
            display_report_text = report_gen.generate_display_report()
            stats_df, highlight_p = report_gen.build_stats_df()

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

    # ------------------------------------------------------------------
    # Stats table helper
    # ------------------------------------------------------------------

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

        st.dataframe(
            styled,
            hide_index=True,
            use_container_width=True,
            height=height,
        )

    # ------------------------------------------------------------------
    # Event tree helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_event_tree_df(np_events: List[NPEvent], qr_threshold: int) -> pd.DataFrame:
        """Walk the NPEvent tree and return a flat DataFrame ready for st.dataframe."""
        rows: list = []

        def walk(event: NPEvent, level: int = 0) -> None:
            # Skip Quick Recovery events
            if event.days_to_recover is not None and event.days_to_recover <= qr_threshold:
                return

            unrecovered = event.status == "Chưa phục hồi"
            prefix = "  " * level + ("└─ " if level > 0 else "")
            start_str = event.start_date.strftime(DATE_FORMAT_DISPLAY)

            rows.append({
                "Lv": level,
                "Start": prefix + start_str,
                "Zone": f"{event.percentile}%",
                "Entry": fmt_price(event.entry_price),
                "Low": fmt_price(event.min_price),
                "Low Date": event.min_date.strftime(DATE_FORMAT_DISPLAY),
                "MAE %": fmt_pct(event.mae_pct),
                "→ Low": event.days_to_bottom,
                "Recovery": event.recovery_date.strftime(DATE_FORMAT_DISPLAY) if event.recovery_date else "—",
                "→ Rec": str(event.days_to_recover) if event.days_to_recover is not None else "active",
                "Children": event.p_coverage,
                "_unrecovered": unrecovered,
            })

            children = sorted(
                [e for e in np_events if e.upline_id == event.id],
                key=lambda e: e.start_date,
            )
            for child in children:
                walk(child, level + 1)

        top_events = sorted(
            [e for e in np_events if e.upline_id is None],
            key=lambda e: e.start_date,
            reverse=True,
        )
        for event in top_events:
            walk(event)

        return pd.DataFrame(rows)

    @staticmethod
    def _render_event_tree(np_events: List[NPEvent], qr_threshold: int) -> None:
        df = SignalAnalysisPack._build_event_tree_df(np_events, qr_threshold)
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

        # Legend
        n_active = sum(unrecovered_mask)
        n_total = len(display_df)
        n_lv0 = sum(level_zero_mask)
        st.caption(
            f"{n_total} events shown  •  "
            f"🟡 {n_active} active (unrecovered)  •  "
            f"🔵 {n_lv0} top-level (Lv 0)  •  "
            f"QR threshold: ≤ {qr_threshold} days (hidden)"
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_results(self, result: AnalysisResult) -> None:
        if result.error:
            st.error(f"❌ [{result.ticker}] {result.error}")
            return

        report_text: str = result.data["report_text"]
        fig = result.data["fig"]
        fig_dist = result.data["fig_dist"]
        signal: BaseSignal = result.data["signal"]
        np_events: List[NPEvent] = result.data.get("np_events", [])
        qr_threshold: int = result.data.get("qr_threshold", 5)
        display_report_text: str = result.data.get("display_report_text", report_text)
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
