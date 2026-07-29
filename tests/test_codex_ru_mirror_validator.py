"""Regression coverage for the Codex validator's Russian-mirror policy."""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "src.codex" / "skills" / "lead" / "scripts" / "validate-skill-pack.sh"
EXTRACTOR = ROOT / "scripts" / "extract-provider-branch.py"

_extractor_spec = importlib.util.spec_from_file_location(
    "extract_provider_branch_for_ru_policy", EXTRACTOR
)
assert _extractor_spec is not None and _extractor_spec.loader is not None
_extractor = importlib.util.module_from_spec(_extractor_spec)
_extractor_spec.loader.exec_module(_extractor)

_BASH_MAINTAINER_ONLY_ARRAY_RE = re.compile(
    r'^  MAINTAINER_ONLY_SHARED_REFERENCE_NAMES=\(\n'
    r'(?P<body>(?:    "[^"]+"\n)*)'
    r'^  \)$',
    re.MULTILINE,
)


def _bash_maintainer_only_paths(validator_source: str) -> frozenset[str]:
    match = _BASH_MAINTAINER_ONLY_ARRAY_RE.search(validator_source)
    assert match is not None, "named Bash maintainer-only boundary is missing or not parseable"
    names = re.findall(r'^    "([^"]+)"$', match.group("body"), re.MULTILINE)
    assert len(names) == len(set(names)), "named Bash maintainer-only boundary has duplicates"
    return frozenset(f"shared/references/{name}" for name in names)


def _assert_maintainer_only_surfaces_match(
    python_paths: frozenset[str], validator_source: str
) -> None:
    bash_paths = _bash_maintainer_only_paths(validator_source)
    missing = sorted(python_paths - bash_paths)
    unexpected = sorted(bash_paths - python_paths)
    assert not missing and not unexpected, (
        f"maintainer-only drift: missing from Bash={missing}; "
        f"unexpected in Bash={unexpected}"
    )


def _canonical_maintainer_only_shared_names() -> tuple[str, ...]:
    prefix = "shared/references/"
    paths = frozenset(_extractor.MAINTAINER_ONLY_FILES)
    assert paths, "canonical maintainer-only set must exercise the Bash boundary"
    assert all(path.startswith(prefix) and "/" not in path[len(prefix):] for path in paths)
    return tuple(sorted(path[len(prefix):] for path in paths))


def _bash() -> str:
    """Resolve Bash without selecting Windows Subsystem for Linux by accident."""
    found = shutil.which("bash")
    if found and "System32" not in found:
        return found
    for candidate in (
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return found or "bash"


def _ru_mirror_policy_fragment() -> str:
    source = VALIDATOR.read_text(encoding="utf-8")
    start_marker = "  # ru/ localization policy"
    end_marker = '\n  echo ""\n  echo "=== Codex compatibility pointers ==="'
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _run_policy(shared_ref_dir: Path, codex_ref_dir: Path) -> subprocess.CompletedProcess[str]:
    fragment = _ru_mirror_policy_fragment()
    harness = f"""\
set -euo pipefail
SHARED_REF_DIR={shared_ref_dir.as_posix()!r}
CODEX_REF_DIR={codex_ref_dir.as_posix()!r}
CLAUDE_REF_DIR=/unused/claude
GEMINI_REF_DIR=/unused/gemini
QWEN_REF_DIR=/unused/qwen
STANDALONE=1
PASS=0
FAIL=0
pass() {{ PASS=$((PASS + 1)); printf 'PASS %s\\n' "$1"; }}
fail() {{ FAIL=$((FAIL + 1)); printf 'FAIL %s\\n' "$1"; }}
{fragment}
printf 'SUMMARY PASS=%s FAIL=%s\\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
"""
    return subprocess.run(
        [_bash(), "-c", harness],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _reference_fixture(tmp_path: Path) -> tuple[Path, Path]:
    shared_ref_dir = tmp_path / "shared" / "references"
    codex_ref_dir = tmp_path / "references-codex"
    (shared_ref_dir / "ru").mkdir(parents=True)
    (codex_ref_dir / "ru").mkdir(parents=True)
    for name in _canonical_maintainer_only_shared_names():
        (shared_ref_dir / name).write_text("maintainer only\n", encoding="utf-8")
    (shared_ref_dir / "ordinary-methodology.md").write_text("method\n", encoding="utf-8")
    (shared_ref_dir / "ru" / "ordinary-methodology.md").write_text("method ru\n", encoding="utf-8")
    return shared_ref_dir, codex_ref_dir


def test_exact_maintainer_only_manifest_does_not_require_russian_mirror(tmp_path: Path) -> None:
    shared_ref_dir, codex_ref_dir = _reference_fixture(tmp_path)

    result = _run_policy(shared_ref_dir, codex_ref_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    maintainer_names = _canonical_maintainer_only_shared_names()
    for name in maintainer_names:
        assert f"{name} is maintainer-only; Russian mirror not required" in result.stdout
    assert f"SUMMARY PASS={len(maintainer_names) + 1} FAIL=0" in result.stdout


def test_ordinary_top_level_reference_still_requires_russian_mirror(tmp_path: Path) -> None:
    shared_ref_dir, codex_ref_dir = _reference_fixture(tmp_path)
    (shared_ref_dir / "ru" / "ordinary-methodology.md").unlink()

    result = _run_policy(shared_ref_dir, codex_ref_dir)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL " in result.stdout
    assert "ru/ordinary-methodology.md missing for ordinary-methodology.md" in result.stdout
    assert f"SUMMARY PASS={len(_canonical_maintainer_only_shared_names())} FAIL=1" in result.stdout


@pytest.mark.parametrize("name", _canonical_maintainer_only_shared_names())
def test_maintainer_only_basename_outside_shared_dir_still_requires_mirror(
    tmp_path: Path, name: str
) -> None:
    shared_ref_dir, codex_ref_dir = _reference_fixture(tmp_path)
    (codex_ref_dir / name).write_text("ordinary provider reference\n", encoding="utf-8")

    result = _run_policy(shared_ref_dir, codex_ref_dir)

    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{codex_ref_dir.as_posix()}/ru/{name} missing for {name}" in result.stdout


def test_maintainer_only_python_and_bash_surfaces_match_exactly() -> None:
    _assert_maintainer_only_surfaces_match(
        frozenset(_extractor.MAINTAINER_ONLY_FILES),
        VALIDATOR.read_text(encoding="utf-8"),
    )


def test_python_only_maintainer_change_fails_cross_surface_gate() -> None:
    python_only_path = "shared/references/python-only-drift.md"
    mutated_python_paths = frozenset(_extractor.MAINTAINER_ONLY_FILES) | {python_only_path}

    with pytest.raises(AssertionError, match=r"missing from Bash=.*python-only-drift\.md"):
        _assert_maintainer_only_surfaces_match(
            mutated_python_paths,
            VALIDATOR.read_text(encoding="utf-8"),
        )


def test_bash_only_maintainer_change_fails_cross_surface_gate() -> None:
    validator_source = VALIDATOR.read_text(encoding="utf-8")
    array_start = "  MAINTAINER_ONLY_SHARED_REFERENCE_NAMES=(\n"
    assert validator_source.count(array_start) == 1
    mutated_validator_source = validator_source.replace(
        array_start,
        array_start + '    "bash-only-drift.md"\n',
        1,
    )

    with pytest.raises(AssertionError, match=r"unexpected in Bash=.*bash-only-drift\.md"):
        _assert_maintainer_only_surfaces_match(
            frozenset(_extractor.MAINTAINER_ONLY_FILES),
            mutated_validator_source,
        )
