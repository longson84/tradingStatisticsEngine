"""DataFrame builders for backtest display tables — no Streamlit."""
from typing import List

import pandas as pd

from src.position.trade import Trade
from src.shared.constants import DATE_FORMAT_DISPLAY
from src.shared.fmt import fmt_equity, fmt_pct, fmt_price


def build_trade_log_df(
    trades: List[Trade],
    bh_equity: pd.Series = None,
) -> pd.DataFrame:
    """Build a trade log DataFrame sorted by entry date (most recent first)."""
    sorted_trades = sorted(trades, key=lambda x: x.entry_date, reverse=True)
    rows = []
    for t in sorted_trades:
        eq_close = t.equity_at_close
        if t.exit_date is not None and bh_equity is not None:
            bh_close = float(bh_equity.asof(pd.Timestamp(t.exit_date)))
        else:
            bh_close = None

        rows.append({
            "Entry Date": t.entry_date.strftime(DATE_FORMAT_DISPLAY),
            "Entry Price": fmt_price(t.entry_price),
            "Exit Date": t.exit_date.strftime(DATE_FORMAT_DISPLAY) if t.exit_date else "—",
            "Exit Price": fmt_price(t.exit_price) if t.exit_price else "—",
            "Return %": fmt_pct(t.return_pct) if t.return_pct is not None else "—",
            "Equity at Close": fmt_equity(eq_close) if eq_close is not None else "—",
            "B&H at Close": fmt_equity(bh_close) if bh_close is not None else "—",
            "Holding": t.holding_days,
            "MAE %": fmt_pct(t.mae_pct) if t.mae_pct is not None else "—",
            "MAE Price": fmt_price(t.mae_price) if t.mae_price is not None else "—",
            "MFE %": fmt_pct(t.mfe_pct) if t.mfe_pct is not None else "—",
            "MFE Price": fmt_price(t.mfe_price) if t.mfe_price is not None else "—",
            "Retracement %": fmt_pct((t.mfe_price - t.exit_price) / t.mfe_price * 100)
                if (t.mfe_price and t.exit_price) else "—",
            "Status": t.status,
        })
    return pd.DataFrame(rows)
