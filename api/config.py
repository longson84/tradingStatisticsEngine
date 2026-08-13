"""Application configuration helpers for local environment variables."""
from __future__ import annotations

from collections.abc import MutableMapping
import os
from pathlib import Path

from api.project_paths import PROJECT_ROOT


DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def load_env_file(
    path: Path = DEFAULT_ENV_PATH,
    *,
    environ: MutableMapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Load missing variables from a local env file without overriding the process.

    Values are intentionally returned only as variable names so callers can log
    configuration state without leaking credentials.
    """
    target = os.environ if environ is None else environ
    if not path.exists():
        return ()

    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in target:
            continue
        target[key] = value.strip().strip("\"'")
        loaded.append(key)
    return tuple(loaded)


def env_value(name: str, default: str | None = None) -> str | None:
    """Return one application setting after loading the project-local env file."""
    load_env_file()
    return os.environ.get(name, default)
