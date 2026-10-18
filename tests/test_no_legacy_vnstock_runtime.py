from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_PATHS = (
    ROOT / "api",
    ROOT / "scripts",
    ROOT / "frontend" / "src",
)
ACTIVE_FILES = (
    ROOT / ".env.example",
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "package.json",
    ROOT / "pyproject.toml",
)
FORBIDDEN = (
    "vnstock" + "_data",
    "Vnstock" + "Data",
    "VNSTOCK" + "_DATA",
    "setup_" + "vnstock_data",
    "Vnstock" + "5Provider",
)


def test_active_runtime_has_no_generation_4_vnstock_references():
    files = list(ACTIVE_FILES)
    for path in ACTIVE_PATHS:
        files.extend(
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file()
            and candidate.suffix in {".py", ".ts", ".tsx", ".json", ".md"}
            and candidate != Path(__file__)
        )
    violations = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if token in text:
                violations.append(f"{path.relative_to(ROOT)} contains {token}")

    assert violations == []
