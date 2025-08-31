# conftest.py
from __future__ import annotations
from dataclasses import dataclass
import platform
import pytest


@dataclass(frozen=True)
class CxPlat:
    windows: bool
    directory: str
    native: bool


def _make_cfg(target: str) -> CxPlat:
    """target in {'linux','windows'}"""
    is_native_windows = platform.system() == "Windows"
    if target == "linux":
        return CxPlat(
            windows=False, directory="castxml_linux", native=(not is_native_windows)
        )
    elif target == "windows":
        return CxPlat(
            windows=True, directory="castxml_windows", native=is_native_windows
        )
    else:
        raise ValueError(f"unknown target: {target}")


@pytest.fixture(params=["linux", "windows"], ids=lambda p: f"cx-{p}")
def cxplat(request) -> CxPlat:
    """Parametrized CastXML platform configuration for tests."""
    return _make_cfg(request.param)
