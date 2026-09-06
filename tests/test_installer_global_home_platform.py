"""Exercise explicit platform routing without replacing os.name or pathlib."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import production_installer as installer  # noqa: E402


@pytest.fixture
def homes(tmp_path, monkeypatch):
    primary = tmp_path / "primary"
    alternate = tmp_path / "alternate"
    primary.mkdir()
    alternate.mkdir()
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    return primary, alternate


def test_windows_home_requires_userprofile_even_when_home_exists(homes, monkeypatch):
    primary, _ = homes
    monkeypatch.setenv("HOME", str(primary))
    with pytest.raises(ValueError, match="USERPROFILE is required"):
        installer._resolve_global_home(platform="nt")


@pytest.mark.parametrize("alternate_kind", ["absent", "matching", "different", "missing-path"])
def test_windows_home_checks_optional_home_against_userprofile(homes, monkeypatch, alternate_kind):
    primary, alternate = homes
    monkeypatch.setenv("USERPROFILE", str(primary))
    if alternate_kind == "matching":
        monkeypatch.setenv("HOME", str(primary))
    elif alternate_kind == "different":
        monkeypatch.setenv("HOME", str(alternate))
    elif alternate_kind == "missing-path":
        monkeypatch.setenv("HOME", str(alternate / "missing"))
    if alternate_kind in {"absent", "matching"}:
        assert installer._resolve_global_home(platform="nt") == primary
    else:
        with pytest.raises(ValueError, match="E_GLOBAL_HOME_AMBIGUOUS"):
            installer._resolve_global_home(platform="nt")


def test_posix_home_ignores_userprofile(homes, monkeypatch):
    primary, alternate = homes
    monkeypatch.setenv("HOME", str(primary))
    monkeypatch.setenv("USERPROFILE", str(alternate))
    assert installer._resolve_global_home(platform="posix") == primary


def test_posix_home_never_falls_back_to_userprofile(homes, monkeypatch):
    primary, _ = homes
    monkeypatch.setenv("USERPROFILE", str(primary))
    with pytest.raises(ValueError, match="HOME is required"):
        installer._resolve_global_home(platform="posix")


@pytest.mark.parametrize("platform,variable", [("nt", "USERPROFILE"), ("posix", "HOME")])
def test_home_link_is_rejected_under_both_routes(homes, monkeypatch, platform, variable):
    primary, alternate = homes
    link = alternate / "linked-home"
    try:
        link.symlink_to(primary, target_is_directory=True)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Creating a symbolic link requires Windows developer mode or privilege")
        raise
    monkeypatch.setenv(variable, str(link))
    with pytest.raises(ValueError, match="E_GLOBAL_HOME_REPARSE"):
        installer._resolve_global_home(platform=platform)
    assert primary.is_dir()
    assert link.is_symlink()


def test_default_route_still_uses_real_host_platform(homes, monkeypatch):
    primary, alternate = homes
    monkeypatch.setenv("HOME", str(primary))
    monkeypatch.setenv("USERPROFILE", str(alternate))
    if os.name == "nt":
        with pytest.raises(ValueError, match="USERPROFILE and HOME disagree"):
            installer._resolve_global_home()
    else:
        assert installer._resolve_global_home() == primary
