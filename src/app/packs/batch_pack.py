"""Batch backtest pack — run one strategy across multiple tickers."""
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from src.shared.base import PackResult
from src.shared.constants import (
    COLOR_POSITIVE,
    DATE_FORMAT_DISPLAY,
    SUMMARY_PERCENTILES,
)
from src.shared.fmt import fmt_capture, fmt_pct
from src.app.styling import style_capture, style_positive_negative
from src.backtest.utils import compute_summary_percentiles
from src.app.packs.position_pack import PositionPack
from src.app.strategy_sidebar_factories import strategy_backtest_sidebar
from src.app.strategy_compute import compute_ticker_core


# ---------------------------------------------------------------------------
# Module-level style helpers
# ---------------------------------------------------------------------------

def _style_percentile(val) -> str:
    try:
        return style_positive_negative(float(val))
    except (TypeError, ValueError):
        return ""


def _style_in_trade(val) -> str:
    return COLOR_POSITIVE if val == "Yes" else ""


class BatchPositionPack(PositionPack):
    @property
    def pack_name(self) -> str:
        return "Batch Backtest"

    def render_sidebar(self) -> Dict[str, Any]:
        return strategy_backtest_sidebar(key_prefix="batch", header="Batch Backtest")

    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> PackResult:
        try:
            strategy = config["strategy"]
            core = compute_ticker_core(df, strategy, strategy.name, config.get("from_date"))
            return PackResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=core["price"],
                data=core,
            )
        except Exception as e:
            return PackResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=df["Close"] if "Close" in df.columns else pd.Series(dtype=float),
                error=str(e),
            )

    def render_results(self, result: PackResult) -> None:
        pass  # Not used — batch rendering via render_batch_results()

    def render_batch_results(self, results: List[PackResult], strategy_label: str) -> None:
        st.subheader(f"📊 Batch Backtest — {strategy_label}")
        st.caption(f"Ngày thống kê: {datetime.now().strftime(DATE_FORMAT_DISPLAY)}")

        errors = [r for r in results if r.error]
        ok = [r for r in results if not r.error]

        if errors:
            with st.expander(f"⚠️ {len(errors)} ticker(s) failed", expanded=False):
                for r in errors:
                    st.error(f"**{r.ticker}**: {r.error}")

        if not ok:
            st.warning("No results to display.")
            return

        rows = []
        for r in ok:
            perf = r.data["performance"]
            pos = r.data["current_position"]
            trades = r.data["trades"]
            bh_return = r.data["bh_total_return"]

            closed_returns = [
                t.return_pct for t in trades
                if t.status == "closed" and t.return_pct is not None
            ]

            strat_return = perf.total_return
            if bh_return and bh_return > 0:
                capture = round(strat_return / bh_return, 2)
            else:
                capture = None

            rows.append({
                "Symbol":          r.ticker,
                "Return %":        round(strat_return, 2),
                "B&H %":           round(bh_return, 2),
                "Capture":         capture,
                "Win Rate %":      round(perf.win_rate, 2),
                "Trades":          perf.closed_trades,
                "Wins":            perf.win_count,
                "Losses":          perf.loss_count,
                **compute_summary_percentiles(closed_returns),
                "Max DD %":        round(r.data["strat_max_drawdown"], 2),
                "Max DD B&H %":    round(r.data["bh_max_drawdown"], 2),
                "Avg Hold Days":   int(round(perf.avg_holding_days)),
                "In Trade":        "Yes" if pos.in_trade else "No",
            })

        df = pd.DataFrame(rows)

        PERCENTILE_COLS = [f"P{p} %" for p in SUMMARY_PERCENTILES]

        _fmt_pct_or_dash = lambda v: fmt_pct(v) if v is not None else "—"
        pct_formatters = {f"P{p} %": _fmt_pct_or_dash for p in SUMMARY_PERCENTILES}

        styled = (
            df.style
            .applymap(style_capture, subset=["Capture"])
            .applymap(_style_percentile, subset=PERCENTILE_COLS)
            .applymap(_style_in_trade, subset=["In Trade"])
            .format(
                {
                    "Return %":     fmt_pct,
                    "B&H %":        fmt_pct,
                    "Capture":      fmt_capture,
                    "Win Rate %":   fmt_pct,
                    **pct_formatters,
                    "Max DD %":     fmt_pct,
                    "Max DD B&H %": fmt_pct,
                },
                na_rep="—",
            )
        )

        height = 38 + min(len(df), 30) * 35
        st.dataframe(styled, hide_index=True, use_container_width=True, height=height)
