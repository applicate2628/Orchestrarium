"""Exercise both home-selection policies without changing os.name globally."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import production_installer as installer  # noqa: E402


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_explicit_platform_uses_its_own_environment_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setenv("USERPROFILE" if platform == "nt" else "HOME", str(home))
    assert installer._resolve_global_home(platform=platform) == home


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_missing_required_environment_is_not_satisfied_by_other_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setenv("HOME" if platform == "nt" else "USERPROFILE", str(home))
    with pytest.raises(ValueError, match="E_GLOBAL_HOME_AMBIGUOUS"):
        installer._resolve_global_home(platform=platform)


def test_windows_policy_rejects_disagreeing_homes_on_any_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    primary = tmp_path / "primary"
    alternate = tmp_path / "alternate"
    primary.mkdir()
    alternate.mkdir()
    monkeypatch.setenv("USERPROFILE", str(primary))
    monkeypatch.setenv("HOME", str(alternate))
    with pytest.raises(ValueError, match="USERPROFILE and HOME disagree"):
        installer._resolve_global_home(platform="nt")
    assert installer._resolve_global_home(platform="posix") == alternate


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_selected_home_link_is_rejected_on_any_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    home = tmp_path / "actual"
    link = tmp_path / "link"
    home.mkdir()
    try:
        link.symlink_to(home, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink prerequisite unavailable: {exc}")
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setenv("USERPROFILE" if platform == "nt" else "HOME", str(link))
    with pytest.raises(ValueError, match="E_GLOBAL_HOME_REPARSE"):
        installer._resolve_global_home(platform=platform)


def test_default_selection_remains_the_real_host_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    assert installer._resolve_global_home() == home
    assert installer._select_global_home_environment(str(home), str(home)) == (
        ("USERPROFILE", str(home), str(home)) if os.name == "nt" else ("HOME", str(home), None)
    )
