"""Filesystem oracle for the repository-standard pytest output boundary."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_standard_pytest_command_uses_scratch_cache_and_no_bytecode(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copy2(ROOT / "pytest.ini", repo / "pytest.ini")
    (repo / "test_fixture.py").write_text(
        "def test_fixture():\n    assert True\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert (repo / ".scratch" / "pytest-cache").is_dir()
    assert not (repo / ".pytest_cache").exists()
    assert not any(repo.rglob("__pycache__"))


def test_declared_full_suite_command_disables_bytecode_writes() -> None:
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "python -B -m pytest tests/" in text
