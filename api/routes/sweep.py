"""POST /sweep — run multiple strategy configs and compare results."""
from __future__ import annotations

from fastapi import APIRouter

from trading_engine import run_comparison
from trading_engine.types import BacktestConfig

from api.deps import build_strategy, fetch_prices
from api.schemas.backtest import SweepErrorItem, SweepRequest, SweepResponse, SweepResultItem

router = APIRouter(prefix="/sweep", tags=["sweep"])


def _date_key(ts) -> str:
    return str(ts.date()) if hasattr(ts, "date") and callable(ts.date) else str(ts)


@router.post("", response_model=SweepResponse)
def run_sweep(req: SweepRequest) -> SweepResponse:
    prices = fetch_prices(
        req.symbols,
        req.date_range.start,
        req.date_range.end,
        req.data_source,
    )

    configs = [
        BacktestConfig(
            strategy=build_strategy(s),
            symbols=req.symbols,
            start=req.date_range.start,
            end=req.date_range.end,
        )
        for s in req.strategies
    ]

    report = run_comparison(configs=configs, prices=prices, max_workers=req.max_workers)

    results = []
    for portfolio_result, config in zip(report.results, report.configs):
        ec = portfolio_result.equity_curve
        initial = float(ec.iloc[0])
        final = float(ec.iloc[-1])
        total_return_pct = (final / initial - 1) * 100 if initial > 0 else 0.0
        results.append(
            SweepResultItem(
                strategy_type=type(config.strategy).__name__,
                equity_curve={_date_key(ts): float(v) for ts, v in ec.items()},
                total_return_pct=total_return_pct,
                final_nav=final,
                trade_count=len(portfolio_result.trades),
            )
        )

    errors = [
        SweepErrorItem(
            strategy_type=type(cfg.strategy).__name__,
            error=str(exc),
        )
        for cfg, exc in report.errors
    ]

    return SweepResponse(results=results, errors=errors)
