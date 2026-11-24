#!/usr/bin/env python3
"""Check project preservation and migration-only global preferences."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path


STALE_OVERLAY = """\
consultantMode: internal
externalClaudeApiMode: auto
reserveResolver: claude-sonnet
externalPriorityProfiles:
  balanced:
    advisory.repo-understanding: [gemini, claude-secret, qwen, codex]
    worker.default-implementation: [gemini, reserve, qwen, codex]
  custom:
    advisory.repo-understanding: [gemini, claude-secret, codex]
    worker.default-implementation: [gemini, reserve, claude]
"""

HISTORICAL_CODEX_DEFAULT_AGENT = """\
name = "default"
description = "General-purpose fallback agent."
model = "gpt-5.4"
model_reasoning_effort = "xhigh"
developer_instructions = \"\"\"
General-purpose fallback agent.
Inherit the parent session's task context and focus on the assigned subtask.
Stay within the requested scope and return a concise, usable result.
\"\"\"
"""

HISTORICAL_CODEX_EXPLORER_AGENT = """\
name = "explorer"
description = "Read-heavy codebase exploration agent."
model = "gpt-5.5"
model_reasoning_effort = "xhigh"
developer_instructions = \"\"\"
Read-only evidence-gathering overlay under the universal AGENTS rules.
Stay in exploration mode, gather factual findings efficiently, and return clear pointers.
Do not edit or drift into implementation unless explicitly requested.
\"\"\"
"""

CUSTOM_CODEX_EXPLORER_AGENT = """\
name = "explorer"
description = "Read-heavy codebase exploration agent."
model = "user-custom-explorer-model"
model_reasoning_effort = "xhigh"
developer_instructions = \"\"\"
Read-only evidence-gathering overlay under the universal AGENTS rules.
Stay in exploration mode, gather factual findings efficiently, and return clear pointers.
Do not edit or drift into implementation unless explicitly requested.
\"\"\"
"""

CUSTOM_CODEX_WORKER_AGENT = """\
name = "worker"
description = "Execution-focused agent for implementation and fixes."
model = "user-custom-model"
model_reasoning_effort = "xhigh"
developer_instructions = \"\"\"
User-customized worker override that intentionally stays on an explicit model.
Do not replace this file during reinstall.
\"\"\"
"""


@dataclass(frozen=True)
class InstallerCase:
    name: str
    script: str
    overlay: str
    codex_line: bool = False


INSTALLER_CASES = [
    InstallerCase(
        name="codex",
        script="scripts/install-codex.py",
        overlay=".agents/.agents-mode.yaml",
        codex_line=True,
    ),
    InstallerCase(
        name="claude",
        script="scripts/install-claude.py",
        overlay=".claude/.agents-mode.yaml",
    ),
]

PRODUCTION_PROVIDER_NAMES = frozenset({"codex", "claude"})


def validate_production_provider_partition() -> None:
    actual = frozenset(case.name for case in INSTALLER_CASES)
    if actual != PRODUCTION_PROVIDER_NAMES:
        raise InstallerRegressionError(
            "production installer regression must cover exactly codex and claude"
        )


class InstallerRegressionError(Exception):
    """Raised when installer output does not match the agents-mode contract."""


def run_installer(root: Path, case: InstallerCase, target_rel: Path) -> None:
    command = [
        sys.executable if case.name in {"codex", "claude"} else "bash",
        case.script,
        "--target",
        target_rel.as_posix(),
        "--force",
        "--allow-unsafe-target",
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise InstallerRegressionError(
            f"{case.name} installer failed:\n{result.stdout}\n{result.stderr}"
        )


def run_global_installer(root: Path, case: InstallerCase, userprofile: Path) -> None:
    env = os.environ.copy()
    env["USERPROFILE"] = str(userprofile)
    env["HOME"] = str(userprofile)
    command = [
        sys.executable,
        str(root / case.script),
        "--global",
        "--force",
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        env=env,
    )
    if result.returncode != 0:
        raise InstallerRegressionError(
            f"{case.name} Python global installer failed:\n"
            f"{result.stdout}\n{result.stderr}"
        )


def seed_stale_overlay(project_root: Path, case: InstallerCase) -> Path:
    overlay = project_root / case.overlay
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(STALE_OVERLAY, encoding="utf-8")
    return overlay


def seed_codex_agent_overrides(
    project_root: Path, root: Path, *, historical_explorer: bool
) -> None:
    agents_dir = project_root / ".codex" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    current_default = (root / "src.codex/agents/default.toml").read_bytes()
    default = (
        current_default
        if historical_explorer
        else HISTORICAL_CODEX_DEFAULT_AGENT.encode("utf-8")
    )
    explorer = (
        HISTORICAL_CODEX_EXPLORER_AGENT
        if historical_explorer
        else CUSTOM_CODEX_EXPLORER_AGENT
    )
    (agents_dir / "default.toml").write_bytes(default)
    (agents_dir / "explorer.toml").write_bytes(explorer.encode("utf-8"))
    (agents_dir / "worker.toml").write_bytes(CUSTOM_CODEX_WORKER_AGENT.encode("utf-8"))


def validate_codex_native_role_install(project_root: Path, root: Path) -> None:
    agents_dir = project_root / ".codex" / "agents"
    source_roles = {
        path.name: path for path in (root / "src.codex" / "agents").glob("*.toml")
    }
    if (agents_dir / "orchestrarium-role-manifest.json").exists():
        raise InstallerRegressionError("Codex installed a native-role ownership receipt")
    for name, source_path in source_roles.items():
        path = agents_dir / name
        if path.read_bytes() != source_path.read_bytes():
            raise InstallerRegressionError(
                f"codex native role bytes drifted for {name}"
            )
    config = (project_root / ".codex" / "config.toml").read_text(encoding="utf-8")
    if "multi_agent_v2 = true" not in config:
        raise InstallerRegressionError("codex fresh role surface did not enable multi_agent_v2")
    if not (project_root / ".agents" / "skills" / "lead" / "SKILL.md").is_file():
        raise InstallerRegressionError("codex canonical .agents skills body missing")


def assert_overlay_bytes(path: Path, expected: bytes, label: str) -> None:
    if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
        raise InstallerRegressionError(f"{label}: preference bytes or file type changed: {path}")


def assert_no_overlay(path: Path, label: str) -> None:
    if any(os.path.lexists(candidate) for candidate in (path, path.with_suffix(""))):
        raise InstallerRegressionError(f"{label}: installer created a preferences file: {path}")


def validate_shared_preference_resolution(root: Path, case: InstallerCase, home: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(root / "scripts/resolve-agents-mode.py"),
         "--provider", case.name, "--project-root", str(home),
         "--home", str(home), "--repo-root", str(root), "--json"],
        cwd=root, text=True, capture_output=True,
    )
    if result.returncode != 0:
        raise InstallerRegressionError(
            f"{case.name} shared preference resolution failed:\n{result.stdout}\n{result.stderr}"
        )
    resolved = json.loads(result.stdout)
    expected = {"rank": "shared-global", "path": str(home / ".agents-mode.yaml")}
    if (resolved["values"].get("reserveResolver") != "disabled"
            or resolved["sources"].get("reserveResolver") != expected
            or resolved["values"].get("mcpMode") != "force"
            or resolved["sources"].get("mcpMode") != expected):
        raise InstallerRegressionError(f"{case.name} lost the shared preference value or provenance")


def run_regression(root: Path) -> None:
    validate_production_provider_partition()
    scratch = root / ".scratch" / "agents-mode-installer-regression" / uuid.uuid4().hex
    scratch.mkdir(parents=True, exist_ok=True)
    validation_error: BaseException | None = None
    try:
        for case in INSTALLER_CASES:
            project = scratch / f"{case.name}-project"
            overlay = seed_stale_overlay(project, case)
            original = overlay.read_bytes()
            if case.codex_line:
                original += b"externalCodexProfile: gpt-5.6-sol-max\n"
                overlay.write_bytes(original)
            legacy = overlay.with_suffix("")
            legacy_bytes = b"# legacy project preference\nexternalClaudeApiMode: disabled\n"
            legacy.write_bytes(legacy_bytes)
            run_installer(root, case, project.relative_to(root))
            assert_overlay_bytes(overlay, original, f"{case.name} project")
            assert_overlay_bytes(legacy, legacy_bytes, f"{case.name} project legacy")
            if case.codex_line:
                validate_codex_native_role_install(project, root)

            fresh = scratch / f"{case.name}-fresh-project"
            fresh.mkdir()
            run_installer(root, case, fresh.relative_to(root))
            assert_no_overlay(fresh / case.overlay, f"{case.name} fresh project")
            if case.codex_line:
                validate_codex_native_role_install(fresh, root)

            home = scratch / f"{case.name}-global-home"
            pack_global = home / f".{case.name}" / ".agents-mode.yaml"
            pack_global.parent.mkdir(parents=True)
            # Exercise in-place legacy handling for both provider adapters.
            pack_legacy = pack_global.with_suffix("")
            pack_bytes = b"consultantMode: external\r\n# local provider preference\r\n"
            pack_legacy.write_bytes(pack_bytes)
            shared = home / ".agents-mode.yaml"
            shared_before = b"# shared preference\r\nexternalClaudeApiMode: disabled  # intentional\r\nmcpMode: force\r\n"
            shared.write_bytes(shared_before)
            run_global_installer(root, case, home)
            assert_overlay_bytes(pack_legacy, pack_bytes, f"{case.name} global legacy")
            if os.path.lexists(pack_global):
                raise InstallerRegressionError(f"{case.name} moved its existing legacy preferences")
            assert_overlay_bytes(shared, shared_before, f"{case.name} shared global")
            validate_shared_preference_resolution(root, case, home)
            assert_overlay_bytes(shared, shared_before, f"{case.name} shared global after resolution")
            if case.codex_line:
                validate_codex_native_role_install(home, root)

            fresh_home = scratch / f"{case.name}-fresh-global-home"
            fresh_home.mkdir()
            run_global_installer(root, case, fresh_home)
            assert_no_overlay(fresh_home / f".{case.name}" / ".agents-mode.yaml", f"{case.name} fresh global")
            assert_no_overlay(fresh_home / ".agents-mode.yaml", f"{case.name} fresh shared global")
            if case.codex_line:
                validate_codex_native_role_install(fresh_home, root)
    except BaseException as exc:
        validation_error = exc
        raise
    finally:
        try:
            def retry_owned_readonly_unlink(func, path, error):
                candidate = Path(os.path.abspath(path))
                try:
                    relative = candidate.relative_to(scratch)
                    metadata = candidate.lstat()
                except (OSError, ValueError):
                    raise error
                attributes = getattr(metadata, "st_file_attributes", 0)
                if (
                    os.name != "nt"
                    or func is not os.unlink
                    or not isinstance(error, PermissionError)
                    or not relative.parts
                    or not stat.S_ISREG(metadata.st_mode)
                    or not attributes & stat.FILE_ATTRIBUTE_READONLY
                    or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise error
                os.chmod(candidate, metadata.st_mode | stat.S_IWRITE)
                func(candidate)

            shutil.rmtree(scratch, onexc=retry_owned_readonly_unlink)
            if scratch.exists() or scratch.is_symlink():
                raise OSError("owned UUID fixture remains after cleanup")
        except OSError as cleanup_error:
            cleanup_detail = f"owned UUID fixture cleanup failed at {scratch}: {cleanup_error}"
            if validation_error is not None:
                raise InstallerRegressionError(
                    f"{type(validation_error).__name__}: {validation_error}; {cleanup_detail}"
                ) from validation_error
            raise InstallerRegressionError(cleanup_detail) from cleanup_error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        run_regression(root)
    except InstallerRegressionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: agents-mode installer regression validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
