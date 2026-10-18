from __future__ import annotations

from importlib import metadata

import pytest

from scripts import check_vnstock


def _versions(values: dict[str, str]):
    def version(package: str) -> str:
        try:
            return values[package]
        except KeyError as exc:
            raise metadata.PackageNotFoundError(package) from exc

    return version


def test_check_environment_accepts_supported_generation_5_packages():
    status = check_vnstock.check_environment(
        version_getter=_versions({
            "vnstock": "5.1.0",
            "vnstock-quant": "0.4.0",
        })
    )

    assert status.core_version == "5.1.0"
    assert status.quant_version == "0.4.0"
    assert status.summary() == "vnstock 5.1.0; vnstock-quant 0.4.0"


def test_check_environment_rejects_generation_4_core():
    with pytest.raises(RuntimeError, match="vnstock 5.1.x is required"):
        check_vnstock.check_environment(
            version_getter=_versions({
                "vnstock": "4.0.5",
                "vnstock-quant": "0.4.0",
            })
        )


def test_check_environment_rejects_missing_quant_package():
    with pytest.raises(RuntimeError, match="vnstock-quant 0.4.x is required"):
        check_vnstock.check_environment(
            version_getter=_versions({"vnstock": "5.1.0"})
        )


def test_status_summary_does_not_include_environment_credentials(monkeypatch):
    secret = "vnstock-secret-value"
    monkeypatch.setenv("VNSTOCK_API_KEY", secret)
    status = check_vnstock.check_environment(
        version_getter=_versions({
            "vnstock": "5.1.0",
            "vnstock-quant": "0.4.0",
        })
    )

    assert secret not in status.summary()
