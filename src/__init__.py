"""Trading Statistics Engine — core packages.

Package structure:
    shared/       Cross-cutting utilities (no domain logic)
    ingestion/    Data download + disk cache
    indicators/   All computation (functions + indicator class wrappers)
    analysis/     Statistical analysis (rarity/NP events)
    strategy/     Buy/sell signal generation only
    position/     Single-position simulation (signals → trades + equity)
    portfolio/    Wraps positions into a portfolio
    backtest/     Shared analytics on portfolio/positions
    app/          All Streamlit-specific code (UI, packs, sidebar factories)
"""
