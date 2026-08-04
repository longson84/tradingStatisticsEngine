"""Export FastAPI's canonical OpenAPI contract for frontend type generation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from api.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "frontend" / "openapi.json"


def export_schema(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    export_schema(args.output)
    print(f"OpenAPI schema written to {args.output}")


if __name__ == "__main__":
    main()
