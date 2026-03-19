"""Trading Engine API — FastAPI application entrypoint.

Run with:
    uv run uvicorn api.main:app --reload

Docs available at:
    http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import backtest, factors, sweep

app = FastAPI(
    title="Trading Statistics Engine",
    description="Backtesting and factor analysis API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backtest.router)
app.include_router(sweep.router)
app.include_router(factors.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
