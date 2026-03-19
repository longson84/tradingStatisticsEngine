"""Position backtest pack."""
from typing import Any, Dict

import pandas as pd
import streamlit as st

from src.shared.base import BasePack, PackResult
from src.shared.general_info_blocks import build_report_time_range_info

from src.app.strategy_sidebar_factories import strategy_backtest_sidebar
from src.app.strategy_compute import compute_strategy
from src.app.packs._renderers import (
    render_performance_summary,
    render_monthly_returns_tables,
    render_strategy_health_section,
)
from src.app.widgets.position_widget import (
    render_current_position,
    render_bh_comparison,
    render_trade_log,
    render_distributions,
    render_equity_curve,
)


class PositionPack(BasePack):
    @property
    def pack_name(self) -> str:
        return "Strategy Backtest"

    def render_sidebar(self) -> Dict[str, Any]:
        return strategy_backtest_sidebar(key_prefix="strat", header="Strategy Backtest")

    def run_computation(self, ticker: str, price: pd.DataFrame, config: Dict) -> PackResult:
        try:
            strategy = config["strategy"]
            data = compute_strategy(price, strategy, strategy.name, config.get("from_date"))
            return PackResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=data["price"],
                data=data,
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

        data = result.data
        perf = result.data["performance"]
        pos = data["current_position"]
        trades = data["trades"]
        strat_equity = data.get("strat_equity")
        bh_equity = data.get("bh_equity")
        bh_total_return: float = data.get("bh_total_return", 0.0)
        bh_max_drawdown: float = data.get("bh_max_drawdown", 0.0)
        strat_max_drawdown: float = data.get("strat_max_drawdown", 0.0)

        with st.expander(f"📊 {result.ticker} — {data['strategy_label']}", expanded=True):
            st.markdown(build_report_time_range_info(result.price_series))

            st.divider()
            render_current_position(pos)

            st.divider()
            render_performance_summary(perf, strat_max_drawdown)

            st.divider()
            render_bh_comparison(perf, strat_max_drawdown, bh_total_return, bh_max_drawdown)

            render_trade_log(trades, bh_equity)

            render_distributions(trades)

            render_equity_curve(result.ticker, strat_equity, bh_equity, data["strategy_label"])

            render_monthly_returns_tables(strat_equity, bh_equity, result.ticker, trades)

            render_strategy_health_section(trades, strat_equity, result.ticker)
