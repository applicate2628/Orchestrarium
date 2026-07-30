"""Regression coverage for the Codex validator's Russian-mirror policy."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/skill_pack_validator_runtime.py"
EXTRACTOR = ROOT / "scripts/extract-provider-branch.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


_runtime = _load(RUNTIME, "canonical_validator_runtime_for_ru_policy")
_extractor = _load(EXTRACTOR, "extract_provider_branch_for_ru_policy")


def _canonical_maintainer_only_shared_names() -> frozenset[str]:
    prefix = "shared/references/"
    paths = frozenset(_extractor.MAINTAINER_ONLY_FILES)
    assert paths, "canonical maintainer-only set must exercise the Python boundary"
    assert all(path.startswith(prefix) and "/" not in path[len(prefix) :] for path in paths)
    return frozenset(path[len(prefix) :] for path in paths)


def _reference_fixture(tmp_path: Path) -> tuple[Path, Path]:
    shared_ref_dir = tmp_path / "shared/references"
    codex_ref_dir = tmp_path / "references-codex"
    (shared_ref_dir / "ru").mkdir(parents=True)
    (codex_ref_dir / "ru").mkdir(parents=True)
    for name in _canonical_maintainer_only_shared_names():
        (shared_ref_dir / name).write_text("maintainer only\n", encoding="utf-8")
    (shared_ref_dir / "ordinary-methodology.md").write_text("method\n", encoding="utf-8")
    (shared_ref_dir / "ru/ordinary-methodology.md").write_text(
        "method ru\n", encoding="utf-8"
    )
    return shared_ref_dir, codex_ref_dir


def _run_policy(shared_ref_dir: Path, codex_ref_dir: Path):
    return _runtime.validate_ru_mirror_policy(
        (shared_ref_dir, codex_ref_dir),
        shared_ref_dir,
        _canonical_maintainer_only_shared_names(),
    )


def test_python_owner_matches_canonical_maintainer_only_manifest() -> None:
    assert callable(_runtime.validate_ru_mirror_policy)
    assert _canonical_maintainer_only_shared_names()


def test_exact_maintainer_only_manifest_does_not_require_russian_mirror(
    tmp_path: Path,
) -> None:
    shared_ref_dir, codex_ref_dir = _reference_fixture(tmp_path)

    results = _run_policy(shared_ref_dir, codex_ref_dir)

    assert all(passed for passed, _ in results)
    for name in _canonical_maintainer_only_shared_names():
        assert any(
            message.endswith(f"{name} is maintainer-only; Russian mirror not required")
            for _, message in results
        )


def test_ordinary_top_level_reference_still_requires_russian_mirror(
    tmp_path: Path,
) -> None:
    shared_ref_dir, codex_ref_dir = _reference_fixture(tmp_path)
    (shared_ref_dir / "ru/ordinary-methodology.md").unlink()

    results = _run_policy(shared_ref_dir, codex_ref_dir)

    assert any(
        not passed
        and message.replace("\\", "/").endswith(
            "ru/ordinary-methodology.md missing for ordinary-methodology.md"
        )
        for passed, message in results
    )


@pytest.mark.parametrize("name", sorted(_canonical_maintainer_only_shared_names()))
def test_maintainer_only_basename_outside_shared_dir_still_requires_mirror(
    tmp_path: Path, name: str
) -> None:
    shared_ref_dir, codex_ref_dir = _reference_fixture(tmp_path)
    (codex_ref_dir / name).write_text("ordinary provider reference\n", encoding="utf-8")

    results = _run_policy(shared_ref_dir, codex_ref_dir)

    assert any(
        not passed
        and message.replace("\\", "/").endswith(f"ru/{name} missing for {name}")
        for passed, message in results
    )


def test_python_only_maintainer_change_fails_cross_surface_gate() -> None:
    mutated = set(_canonical_maintainer_only_shared_names())
    mutated.add("python-only-drift.md")
    assert frozenset(mutated) != _canonical_maintainer_only_shared_names()
