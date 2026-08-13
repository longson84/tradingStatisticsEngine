from __future__ import annotations

import ast
from pathlib import Path

from api.db.models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_services_do_not_import_framework_or_persistence_implementations():
    forbidden = ("fastapi", "sqlalchemy", "api.db")
    for path in (PROJECT_ROOT / "api" / "services").glob("*.py"):
        imports = _imports(path)
        assert not any(
            imported == prefix or imported.startswith(f"{prefix}.")
            for imported in imports
            for prefix in forbidden
        ), f"{path.name} crosses the service boundary: {imports}"


def test_company_route_depends_on_service_not_repository_or_database():
    imports = _imports(PROJECT_ROOT / "api" / "routes" / "companies.py")
    assert not any(
        imported.startswith("api.repositories") or imported.startswith("api.db")
        for imported in imports
    )


def test_price_routes_do_not_depend_on_repository_or_database_models():
    for filename in ("instrument_history.py",):
        imports = _imports(PROJECT_ROOT / "api" / "routes" / filename)
        assert not any(
            imported.startswith("api.repositories") or imported.startswith("api.db")
            for imported in imports
        ), f"{filename} crosses the route boundary: {imports}"


def test_application_has_no_legacy_fundamentals_cache_module():
    assert not (PROJECT_ROOT / "api" / "fundamentals_cache.py").exists()
    for root in (PROJECT_ROOT / "api", PROJECT_ROOT / "scripts"):
        for path in root.rglob("*.py"):
            assert "api.fundamentals_cache" not in _imports(path)


def test_retired_collection_history_and_bulk_scripts_are_absent():
    assert not (PROJECT_ROOT / "scripts" / "refresh_universe_prices.py").exists()
    assert not (
        PROJECT_ROOT / "scripts" / "migrate_legacy_benchmark_cache.py"
    ).exists()
    assert "fundamental_refresh_runs" not in Base.metadata.tables


def test_sqlalchemy_repositories_are_not_imported_outside_dependency_wiring():
    allowed = PROJECT_ROOT / "api" / "deps.py"
    violations = []
    for path in (PROJECT_ROOT / "api").rglob("*.py"):
        if path == allowed or "repositories" in path.parts:
            continue
        imports = _imports(path)
        if any(
            imported.startswith("api.repositories.sqlalchemy_")
            for imported in imports
        ):
            violations.append(path.relative_to(PROJECT_ROOT))
    assert violations == []


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result
