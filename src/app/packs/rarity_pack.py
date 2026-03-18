"""Rarity analysis pack (was SignalBasePack)."""
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from src.shared.base import BasePack, PackResult
from src.shared.fmt import fmt_pct, fmt_price

from src.signals.base import BaseSignal

from src.analysis.rarity.events import NPEvent
from src.analysis.rarity.charts import create_price_signal_chart, create_signal_distribution_chart
from src.analysis.rarity.report import ReportGenerator

from src.app.ui import plot_chart
from src.app.analysis_sidebar_factories import rarity_analysis_sidebar
from src.app.widgets.rarity_widget import render_np_stats_table, render_event_tree


class RarityBasePack(BasePack):
    @property
    def pack_name(self) -> str:
        return "Signal Analysis"

    def render_sidebar(self) -> Dict[str, Any]:
        return rarity_analysis_sidebar()

    def run_computation(self, ticker: str, price: pd.DataFrame, config: Dict) -> PackResult:
        signal: BaseSignal = config["signal"]

        try:
            signal_series = signal.calculate(price)

            report_gen = ReportGenerator(ticker, signal, price, signal_series, config["qr_threshold"])
            report_gen.calculate()

            price_signal_chart = create_price_signal_chart(ticker, price, signal_series, signal)
            current_value = signal_series.iloc[-1]
            signal_distribution_chart = create_signal_distribution_chart(signal_series, current_value, signal.name)

            return PackResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=price["Close"],
                signal_series=signal_series,
                data={
                    "price_signal_chart": price_signal_chart,
                    "signal_distribution_chart": signal_distribution_chart,
                    "signal": signal,
                    "np_events": report_gen.np_events,
                    "qr_threshold": report_gen.qr_threshold,
                    "report_text": report_gen.report_text,
                    "np_stats": report_gen.np_stats,
                    "highlight_p": report_gen.highlight_p,
                },
            )
        except Exception as e:
            return PackResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=price["Close"] if "Close" in price.columns else pd.Series(dtype=float),
                signal_series=pd.Series(dtype=float),
                error=str(e),
            )

    def render_results(self, result: PackResult) -> None:
        if result.error:
            st.error(f"❌ [{result.ticker}] {result.error}")
            return

        price_signal_chart = result.data["price_signal_chart"]
        signal_distribution_chart = result.data["signal_distribution_chart"]
        np_events: List[NPEvent] = result.data.get("np_events", [])
        qr_threshold: int = result.data.get("qr_threshold", 5)
        report_text: str = result.data.get("report_text", "")
        stats_df: pd.DataFrame = result.data.get("np_stats", pd.DataFrame())

        with st.expander(f"📊 Kết quả phân tích: {result.ticker}", expanded=True):
            render_np_stats_table(stats_df)

            st.markdown(report_text, unsafe_allow_html=True)

            render_event_tree(np_events, qr_threshold)

            plot_chart(signal_distribution_chart)
            
            plot_chart(price_signal_chart)

