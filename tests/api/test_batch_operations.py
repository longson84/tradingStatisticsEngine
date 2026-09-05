from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.db.models import Base
from api.main import app
from api.repositories.sqlalchemy_batch_operation_repository import (
    SqlAlchemyBatchOperationRepository,
)
from api.services.batch_operation_service import (
    BatchOperationService,
    DuplicateBatchOperationPlanError,
    UnknownBatchOperationPlanError,
)


def _step(target_type: str, target_id: str, dataset: str = "prices", mode: str = "incremental"):
    return SimpleNamespace(
        target_type=target_type,
        target_id=target_id,
        dataset=dataset,
        mode=mode,
    )


def test_batch_plan_crud_preserves_step_order_and_dynamic_targets():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = BatchOperationService(SqlAlchemyBatchOperationRepository(session))
        created = service.create_plan(
            "  Daily   market update ",
            "Prices first",
            [_step("category", "equity"), _step("category", "reference_rate")],
        )
        session.commit()

        assert created.name == "Daily market update"
        assert [(step.position, step.target_type, step.target_id) for step in created.steps] == [
            (0, "category", "equity"),
            (1, "category", "reference_rate"),
        ]

        updated = service.update_plan(
            created.id,
            "Daily market update",
            "Current memberships resolve at launch",
            [_step("universe", "VN100"), _step("watchlist", "12", "fundamentals")],
        )
        session.commit()
        assert [step.target_id for step in updated.steps] == ["VN100", "12"]
        assert service.list_plans()[0].description == "Current memberships resolve at launch"

        service.delete_plan(created.id)
        session.commit()
        with pytest.raises(UnknownBatchOperationPlanError):
            service.get_plan(created.id)


def test_batch_plan_validation_rejects_duplicate_names_and_unknown_categories():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = BatchOperationService(SqlAlchemyBatchOperationRepository(session))
        service.create_plan("Daily", "", [_step("category", "equity")])
        with pytest.raises(DuplicateBatchOperationPlanError):
            service.create_plan(" daily ", "", [_step("category", "reference_rate")])
        with pytest.raises(ValueError, match="Unsupported Instrument category"):
            service.create_plan("Bad target", "", [_step("category", "not_real")])


def test_openapi_exposes_batch_plan_and_run_contracts():
    paths = app.openapi()["paths"]

    assert paths["/data-operations/batch-plans"]["post"]["operationId"] == "createBatchOperationPlan"
    assert paths["/data-operations/batch-plans/{plan_id}/runs"]["post"]["operationId"] == "startBatchOperationRun"
    assert paths["/data-operations/batch-runs/{run_id}"]["get"]["operationId"] == "getBatchOperationRun"
