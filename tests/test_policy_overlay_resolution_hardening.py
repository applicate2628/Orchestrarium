from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "src.codex" / "skills" / "policy-overlay"
CORE = SKILL / "scripts" / "policy_overlay_core.py"
ENTRYPOINT = SKILL / "scripts" / "policy-overlays.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _copy_skill(tmp_path: Path) -> Path:
    target = tmp_path / "policy-overlay"
    shutil.copytree(SKILL, target)
    return target


def test_no_selection_is_an_exact_empty_projection(tmp_path: Path) -> None:
    module = _load(ENTRYPOINT, "policy_overlay_noop_test")
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()

    selection = module.resolve_config_selection(
        project_root=project,
        home=home,
        policy_root=SKILL,
    )
    overlays = module.resolve_from_config(
        provider="codex",
        project_root=project,
        home=home,
        lane="worker.default-implementation",
        target="external-worker",
        policy_root=SKILL,
    )

    assert selection == ()
    assert overlays == ()
    assert module.render_overlay_instructions(overlays) == ""


def test_exact_provider_lane_target_and_project_restriction(tmp_path: Path) -> None:
    module = _load(ENTRYPOINT, "policy_overlay_context_test")
    project = tmp_path / "project"
    home = tmp_path / "home"
    (project / ".orche").mkdir(parents=True)
    home.mkdir()
    (project / ".orche" / "policy.yaml").write_text(
        "allowedPolicyOverlays: [complexity-review]\n",
        encoding="utf-8",
    )

    with pytest.raises(module.PolicyOverlayError):
        module.resolve_from_config(
            provider="codex",
            project_root=project,
            home=home,
            lane="worker.default-implementation",
            target="external-worker",
            explicit_selection="lean-implementation",
            policy_root=SKILL,
        )

    kimi = module.resolve_from_config(
        provider="kimi",
        project_root=project,
        home=home,
        lane="review.pre-pr",
        target="external-reviewer",
        explicit_selection="complexity-review",
        policy_root=SKILL,
    )
    assert [item.overlay_id for item in kimi] == ["complexity-review"]
    assert all(not item.authorizing for item in kimi)

    filtered = module.resolve_selected_overlays(
        selection="complexity-review",
        provider="codex",
        lane="worker.default-implementation",
        target="external-worker",
        policy_root=SKILL,
    )
    assert filtered == ()


def test_render_rejects_mixed_projection_contexts() -> None:
    module = _load(ENTRYPOINT, "policy_overlay_render_test")
    first = module.ResolvedPolicyOverlay(
        "lean-implementation",
        "builtin",
        "policies/lean-implementation.md",
        "Use the existing owner.\n",
        False,
        "codex",
        "worker.default-implementation",
        "external-worker",
    )
    second = module.ResolvedPolicyOverlay(
        "complexity-review",
        "builtin",
        "policies/complexity-review.md",
        "Remove avoidable complexity.\n",
        False,
        "claude",
        "review.pre-pr",
        "external-reviewer",
    )
    with pytest.raises(module.PolicyOverlayError):
        module.render_overlay_instructions((first, second))


def test_cli_output_is_deterministic_and_denial_is_nonzero(tmp_path: Path) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    command = [
        sys.executable,
        "-S",
        str(ENTRYPOINT),
        "--provider",
        "codex",
        "--project-root",
        str(project),
        "--home",
        str(home),
        "--policy-root",
        str(SKILL),
        "--selection",
        "lean-implementation",
        "--lane",
        "worker.default-implementation",
        "--target",
        "external-worker",
    ]
    first = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    second = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert first.returncode == 0
    assert first.stdout == second.stdout
    assert first.stderr == ""
    assert json.loads(first.stdout)["overlays"][0]["id"] == "lean-implementation"

    denied_command = list(command)
    denied_command[denied_command.index("--selection") + 1] = "unknown"
    denied = subprocess.run(
        denied_command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert denied.returncode == 2
    assert denied.stdout == ""
    assert denied.stderr.startswith("E_POLICY_OVERLAY_INVALID:")


def test_catalog_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    catalog = skill / "policy-overlays.v1.json"
    body = catalog.read_text(encoding="utf-8")
    body = body.replace(
        '"schemaVersion": 1,',
        '"schemaVersion": 999,\n  "schemaVersion": 1,',
        1,
    )
    catalog.write_text(body, encoding="utf-8")
    core = _load(skill / "scripts" / "policy_overlay_core.py", "policy_overlay_duplicate_test")

    with pytest.raises(core.PolicyOverlayError, match="duplicate JSON key"):
        core._load_catalog(skill)


def test_catalog_parser_turns_excessive_nesting_into_typed_denial(
    tmp_path: Path,
) -> None:
    skill = _copy_skill(tmp_path)
    (skill / "policy-overlays.v1.json").write_text(
        "[" * 10000 + "0" + "]" * 10000,
        encoding="utf-8",
    )
    core = _load(skill / "scripts" / "policy_overlay_core.py", "policy_overlay_depth_test")

    with pytest.raises(core.PolicyOverlayError, match="invalid policy overlay catalog"):
        core._load_catalog(skill)


def test_same_size_file_mutation_during_read_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = _load(CORE, "policy_overlay_file_race_test")
    target = tmp_path / "catalog.json"
    target.write_bytes(b"AAAA")
    original_read = core.os.read
    changed = False

    def mutating_read(fd: int, size: int) -> bytes:
        nonlocal changed
        chunk = original_read(fd, size)
        if chunk and not changed:
            changed = True
            before = target.stat()
            target.write_bytes(b"BBBB")
            os.utime(
                target,
                ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000),
            )
        return chunk

    monkeypatch.setattr(core.os, "read", mutating_read)
    with pytest.raises(core.PolicyOverlayError, match="changed while reading"):
        core._read_regular(target, 1024, label="test file")


def test_core_star_export_is_intentional_and_does_not_leak_modules() -> None:
    core = _load(CORE, "policy_overlay_exports_test")
    for leaked in ("argparse", "json", "os", "re", "stat", "sys", "Path"):
        assert leaked not in core.__all__
    for required in (
        "PolicyOverlayError",
        "ResolvedPolicyOverlay",
        "_load_catalog",
        "_read_regular",
        "_root",
    ):
        assert required in core.__all__
