"""Install or verify the private Vnstock sponsor bundle safely."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib import metadata, util
import json
from pathlib import Path
import stat
import subprocess
import tempfile
from urllib.request import urlopen

from api.config import env_value
from api.market_data_config import PROJECT_ROOT


INSTALLER_URL = "https://vnstocks.com/files/vnstock-cli-installer.run"
MINIMUM_VERSION = (3, 2, 7)
PACKAGE = "vnstock_data"


@dataclass(frozen=True)
class SponsorStatus:
    installed: bool
    version: str | None
    supported: bool
    api_key_configured: bool


def sponsor_status(*, home: Path | None = None) -> SponsorStatus:
    installed = util.find_spec(PACKAGE) is not None
    version: str | None = None
    if installed:
        try:
            version = metadata.version(PACKAGE)
        except metadata.PackageNotFoundError:
            installed = False
    return SponsorStatus(
        installed=installed,
        version=version,
        supported=bool(version and _version_tuple(version) >= MINIMUM_VERSION),
        api_key_configured=_api_key_configured(home=home),
    )


def installer_command(installer: Path, api_key: str, venv: Path) -> list[str]:
    return [
        str(installer),
        "--",
        "--non-interactive",
        "--api-key",
        api_key,
        "--venv-path",
        str(venv),
        "--language",
        "en",
    ]


def install(*, api_key: str, venv: Path) -> None:
    if not api_key.strip():
        raise RuntimeError(
            "VNSTOCK_API_KEY is missing; add it to the ignored project .env file"
        )
    if not venv.exists():
        raise RuntimeError("Project .venv is missing; run uv sync --inexact first")
    with tempfile.TemporaryDirectory(prefix="vnstock-installer-") as temp_dir:
        installer = Path(temp_dir) / "vnstock-cli-installer.run"
        with urlopen(INSTALLER_URL, timeout=60) as response:
            installer.write_bytes(response.read())
        installer.chmod(installer.stat().st_mode | stat.S_IXUSR)
        try:
            subprocess.run(
                installer_command(installer, api_key, venv),
                check=True,
                cwd=PROJECT_ROOT,
            )
        except subprocess.CalledProcessError as exc:
            # Do not allow the official command's API-key argument to appear in
            # a Python exception or traceback.
            raise RuntimeError(
                f"Official Vnstock installer failed with exit code {exc.returncode}"
            ) from None


def _api_key_configured(*, home: Path | None = None) -> bool:
    if (env_value("VNSTOCK_API_KEY") or "").strip():
        return True
    key_path = (home or Path.home()) / ".vnstock" / "api_key.json"
    try:
        payload = json.loads(key_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    return bool(str(payload.get("api_key", "")).strip())


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in value.split("."):
        digits = "".join(character for character in part if character.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    status = sponsor_status()
    if args.check:
        print(
            f"{PACKAGE}: installed={status.installed} version={status.version or '-'} "
            f"supported={status.supported} api_key_configured={status.api_key_configured}"
        )
        if not status.supported or not status.api_key_configured:
            raise SystemExit(1)
        return
    if status.supported and status.api_key_configured and not args.force:
        print(f"{PACKAGE} {status.version} is installed and configured")
        return
    api_key = (env_value("VNSTOCK_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "Installing the sponsor bundle requires VNSTOCK_API_KEY in .env"
        )
    install(api_key=api_key, venv=PROJECT_ROOT / ".venv")
    installed = sponsor_status()
    if not installed.supported:
        raise RuntimeError(
            f"Sponsor installer did not provide {PACKAGE} >= "
            f"{'.'.join(map(str, MINIMUM_VERSION))}"
        )
    print(f"{PACKAGE} {installed.version} installed successfully")


if __name__ == "__main__":
    main()
