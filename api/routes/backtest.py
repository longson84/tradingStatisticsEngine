"""POST /backtest — run a single portfolio backtest."""
from __future__ import annotations

from fastapi import APIRouter

from trading_engine import run_portfolio
from trading_engine.types import Portfolio

from api.deps import build_strategy, fetch_prices
from api.schemas.backtest import BacktestRequest, PortfolioResultResponse
from api.schemas.common import TradeSchema, WeightEventSchema

router = APIRouter(prefix="/backtest", tags=["backtest"])


def _date_key(ts) -> str:
    """Convert pandas Timestamp or date to ISO string key."""
    return str(ts.date()) if hasattr(ts, "date") and callable(ts.date) else str(ts)


@router.post("", response_model=PortfolioResultResponse)
def run_backtest(req: BacktestRequest) -> PortfolioResultResponse:
    prices = fetch_prices(
        req.symbols,
        req.date_range.start,
        req.date_range.end,
        req.data_source,
    )
    strategy = build_strategy(req.strategy)
    portfolio = Portfolio(
        initial_capital=req.initial_capital,
        strategy=strategy,
        max_leverage=req.max_leverage,
    )

    result = run_portfolio(portfolio=portfolio, prices=prices)

    equity_curve = {_date_key(ts): float(v) for ts, v in result.equity_curve.items()}
    initial = float(result.equity_curve.iloc[0])
    final = float(result.equity_curve.iloc[-1])
    total_return_pct = (final / initial - 1) * 100 if initial > 0 else 0.0

    weights = {
        col: {_date_key(ts): float(v) for ts, v in result.weights[col].items()}
        for col in result.weights.columns
    }

    trades = [
        TradeSchema(
            symbol=t.symbol,
            direction=t.direction,
            entry_date=t.entry_date,
            entry_price=t.entry_price,
            entry_weight=t.entry_weight,
            exit_date=t.exit_date,
            exit_price=t.exit_price,
            weight_history=[
                WeightEventSchema(date=we.date, weight=we.weight, price=we.price)
                for we in t.weight_history
            ],
            return_pct=t.return_pct,
            holding_days=t.holding_days,
            mae_pct=t.mae_pct,
            mfe_pct=t.mfe_pct,
        )
        for t in result.trades
    ]

    return PortfolioResultResponse(
        equity_curve=equity_curve,
        trades=trades,
        weights=weights,
        total_return_pct=total_return_pct,
        final_nav=final,
    )
