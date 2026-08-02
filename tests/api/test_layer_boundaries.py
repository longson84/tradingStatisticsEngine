from __future__ import annotations

import ast
from pathlib import Path


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


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result
