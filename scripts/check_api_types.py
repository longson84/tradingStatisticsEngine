"""Verify generated frontend API artifacts without depending on Git state."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from scripts.export_openapi import PROJECT_ROOT, export_schema


OPENAPI_PATH = PROJECT_ROOT / "frontend" / "openapi.json"
TYPES_PATH = PROJECT_ROOT / "frontend" / "src" / "lib" / "generated" / "api-schema.ts"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="trading-api-contract-") as temp_dir:
        temporary = Path(temp_dir)
        openapi = temporary / "openapi.json"
        types = temporary / "api-schema.ts"
        export_schema(openapi)
        subprocess.run(
            [
                "pnpm", "--filter", "frontend", "exec", "openapi-typescript",
                str(openapi), "-o", str(types),
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )
        stale = [
            path
            for path, generated in ((OPENAPI_PATH, openapi), (TYPES_PATH, types))
            if not path.exists() or path.read_bytes() != generated.read_bytes()
        ]
    if stale:
        names = ", ".join(str(path.relative_to(PROJECT_ROOT)) for path in stale)
        raise SystemExit(
            f"Generated API contract is stale: {names}. Run `pnpm generate:api`."
        )
    print("Generated API contract is current")


if __name__ == "__main__":
    main()
