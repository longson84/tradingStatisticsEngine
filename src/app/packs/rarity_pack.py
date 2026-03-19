"""Rarity analysis pack."""
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from src.shared.base import BaseAnalysisPack, PackResult

from src.shared.general_info_blocks import build_report_time_range_info

from src.factors.base import BaseFactor

from src.analysis.rarity.events import NPEvent
from src.analysis.rarity.charts import create_price_factor_chart, create_factor_distribution_chart
from src.analysis.rarity.report import ReportGenerator

from src.app.ui import plot_chart
from src.app.analysis_sidebar_factories import rarity_analysis_sidebar
from src.app.widgets.rarity_widget import render_np_stats_table, render_event_tree


class RarityAnalysisPack(BaseAnalysisPack):
    @property
    def pack_name(self) -> str:
        return "Factor Analysis"

    def render_sidebar(self) -> Dict[str, Any]:
        return rarity_analysis_sidebar()

    def run_computation(self, ticker: str, price: pd.DataFrame, config: Dict) -> PackResult:
        factor: BaseFactor = config["factor"]

        try:
            factor_series = factor.calculate(price)

            report_gen = ReportGenerator(ticker, factor, price, factor_series, config["qr_threshold"])
            report_gen.calculate()

            price_factor_chart = create_price_factor_chart(ticker, price, factor_series, factor)
            current_value = factor_series.iloc[-1]
            factor_distribution_chart = create_factor_distribution_chart(factor_series, current_value, factor.name)

            return PackResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=price["Close"],
                factor_series=factor_series,
                data={
                    "price_factor_chart": price_factor_chart,
                    "factor_distribution_chart": factor_distribution_chart,
                    "factor": factor,
                    "np_events": report_gen.np_events,
                    "qr_threshold": report_gen.qr_threshold,
                    "current_status": report_gen.current_status,
                    "np_stats": report_gen.np_stats,
                },
            )
        except Exception as e:
            return PackResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=price["Close"] if "Close" in price.columns else pd.Series(dtype=float),
                error=str(e),
            )

    def render_results(self, result: PackResult) -> None:
        if result.error:
            st.error(f"❌ [{result.ticker}] {result.error}")
            return


        price_factor_chart = result.data["price_factor_chart"]
        factor_distribution_chart = result.data["factor_distribution_chart"]
        np_events: List[NPEvent] = result.data.get("np_events", [])
        qr_threshold: int = result.data.get("qr_threshold", 5)
        current_status: str = result.data.get("current_status")
        
        time_range = build_report_time_range_info(result.price_series)

        stats_df: pd.DataFrame = result.data.get("np_stats", pd.DataFrame())

        with st.expander(f"📊 Kết quả phân tích: {result.ticker}", expanded=True):
            
            # the statistics table of the NP events
            render_np_stats_table(stats_df)

            # the time range of the analysis
            st.markdown(time_range, unsafe_allow_html=True)

            # the current status of the factor
            st.markdown(current_status)

            # the event tree of the NP events
            render_event_tree(np_events, qr_threshold)

            plot_chart(factor_distribution_chart)

            plot_chart(price_factor_chart)
