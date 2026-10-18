"""Verify the Vnstock generation 5 runtime without making a data request."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Callable


VersionGetter = Callable[[str], str]


@dataclass(frozen=True)
class VnstockEnvironmentStatus:
    core_version: str
    quant_version: str

    def summary(self) -> str:
        return (
            f"vnstock {self.core_version}; "
            f"vnstock-quant {self.quant_version}"
        )


def check_environment(
    *,
    version_getter: VersionGetter = metadata.version,
) -> VnstockEnvironmentStatus:
    """Return installed Gen 5 versions or raise with a setup-oriented error."""
    core_version = _required_version(
        "vnstock", "5.1.", "vnstock 5.1.x is required", version_getter
    )
    quant_version = _required_version(
        "vnstock-quant",
        "0.4.",
        "vnstock-quant 0.4.x is required",
        version_getter,
    )
    return VnstockEnvironmentStatus(
        core_version=core_version,
        quant_version=quant_version,
    )


def _required_version(
    package: str,
    prefix: str,
    message: str,
    version_getter: VersionGetter,
) -> str:
    try:
        version = version_getter(package)
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(message) from exc
    if not version.startswith(prefix):
        raise RuntimeError(f"{message}; found {version}")
    return version


def main() -> None:
    print(check_environment().summary())


if __name__ == "__main__":
    main()
