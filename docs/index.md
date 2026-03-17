# Trading Statistics Engine

A Streamlit-based backtesting and signal analysis engine for trading strategies.

## Modules

| Module | Description |
|--------|-------------|
| `src.strategy.analytics` | Core trade computation — signals, equity curves, drawdown |
| `src.strategy.strategies` | Strategy registry and all strategy implementations |
| `src.strategy.pack` | Single-strategy backtest pack |
| `src.strategy.sweep_pack` | Parameter sweep pack |
| `src.strategy.batch_pack` | Multi-ticker batch pack |
| `src.strategy.monthly` | Monthly returns DataFrame builders |
| `src.strategy.annual` | Annual trade summary builder |
| `src.signal.signals` | Market signal definitions (MA, AHR999, etc.) |
| `src.signal.analytics` | Signal analytics and NP event detection |
| `src.fmt` | Display formatting utilities |
| `src.styling` | CSS styling utilities for Styler |
| `src.constants` | Application-wide constants |
