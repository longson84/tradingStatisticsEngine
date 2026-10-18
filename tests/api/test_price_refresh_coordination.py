from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from api import data_operation_jobs
from api.db.models import Base

from api.price_refresh_coordination import (
    acquire_price_refresh,
    release_price_refresh,
)


def test_refresh_lease_blocks_same_adapter_but_not_other_adapter():
    acquire_price_refresh("yfinance", "us-owner", "US500")
    try:
        with pytest.raises(RuntimeError, match="US500"):
            acquire_price_refresh("yfinance", "other-us-owner", "watchlist Leaders")

        acquire_price_refresh("vnstock", "vn-owner", "VN100")
        release_price_refresh("vnstock", "vn-owner")
    finally:
        release_price_refresh("yfinance", "us-owner")


def test_only_owner_can_release_refresh_lease():
    acquire_price_refresh("vnstock", "owner", "VN100")
    try:
        release_price_refresh("vnstock", "not-owner")
        with pytest.raises(RuntimeError, match="VN100"):
            acquire_price_refresh("vnstock", "second-owner", "VN30")
    finally:
        release_price_refresh("vnstock", "owner")


def test_generation_4_adapter_name_is_rejected():
    with pytest.raises(ValueError, match="Unsupported price refresh adapter"):
        acquire_price_refresh("vnstock_data", "legacy-owner", "VN30")


@pytest.mark.parametrize("dataset", ["foreign_flow", "session_stats", "trade_history"])
def test_vietnam_activity_and_price_jobs_share_the_vnstock_lease(monkeypatch, dataset):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    class DormantThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(data_operation_jobs, "Thread", DormantThread)
    flow = data_operation_jobs.start_data_operation_job(
        scope_type="instrument",
        scope_id="1",
        scope_name="FPT",
        dataset=dataset,
        mode="full",
        adapter_keys=("vnstock",),
        total=1,
        engine=engine,
    )
    try:
        with pytest.raises(RuntimeError, match="FPT"):
            data_operation_jobs.start_data_operation_job(
                scope_type="instrument",
                scope_id="2",
                scope_name="VN30",
                dataset="prices",
                mode="incremental",
                adapter_keys=("vnstock",),
                total=1,
                engine=engine,
            )
    finally:
        release_price_refresh("vnstock", flow.id)
        data_operation_jobs._active_keys.clear()
        data_operation_jobs._jobs.clear()
