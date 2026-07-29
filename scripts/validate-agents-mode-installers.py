#!/usr/bin/env python3
"""Run installer-level regression checks for agents-mode normalization."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

LEGACY_CODEX_DEFAULT_AGENT = """\
name = "default"
description = "General-purpose fallback agent."
model = "gpt-legacy-default"
model_reasoning_effort = "xhigh"
developer_instructions = \"\"\"
General-purpose fallback agent.
Inherit the parent session's task context and focus on the assigned subtask.
Stay within the requested scope and return a concise, usable result.
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
        script="scripts/install-codex.sh",
        overlay=".agents/.agents-mode.yaml",
        codex_line=True,
    ),
    InstallerCase(
        name="claude",
        script="scripts/install-claude.sh",
        overlay=".claude/.agents-mode.yaml",
    ),
    InstallerCase(
        name="gemini",
        script="scripts/install-gemini.sh",
        overlay=".gemini/.agents-mode.yaml",
    ),
    InstallerCase(
        name="qwen",
        script="scripts/install-qwen.sh",
        overlay=".qwen/.agents-mode.yaml",
    ),
]

_UNIVERSAL_HOOK_EXTS = (".py", ".sh", ".ps1")


def universal_hook_helper_paths(root: Path) -> tuple[str, ...]:
    """The `scripts/<name>` + `hooks/<name>` relative paths the packs must carry,
    DERIVED by globbing the pack-neutral canon `scripts/universal-hooks/` — never
    a hardcoded list (a hardcoded list hid check-stale-relation-residue from this
    gate until 2026-07-07). Adding a hook to the canon auto-covers it here."""
    canon = root / "scripts" / "universal-hooks"
    paths: list[str] = []
    for sub in ("scripts", "hooks"):
        d = canon / sub
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix in _UNIVERSAL_HOOK_EXTS:
                paths.append(f"{sub}/{p.name}")
    return tuple(paths)


class InstallerRegressionError(Exception):
    """Raised when installer output does not match the agents-mode contract."""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_agents_mode(path: Path) -> dict[str, Any]:
    scalars: dict[str, str] = {}
    profiles: dict[str, dict[str, list[str]]] = {}
    counts: dict[str, int] = {}
    current_block: str | None = None
    current_profile: str | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            key, rest = line.split(":", 1)
            current_block = key.strip()
            current_profile = None
            if current_block not in {
                "externalPriorityProfiles",
                "externalOpinionCounts",
            }:
                scalars[current_block] = strip_comment(rest)
            continue
        if current_block == "externalPriorityProfiles":
            if line.startswith("  ") and not line.startswith("    ") and ":" in line:
                current_profile = line.split(":", 1)[0].strip()
                profiles[current_profile] = {}
                continue
            if line.startswith("    ") and current_profile and ":" in line:
                lane, rest = line.split(":", 1)
                profiles[current_profile][lane.strip()] = parse_provider_list(rest)
                continue
        if current_block == "externalOpinionCounts":
            if line.startswith("  ") and ":" in line:
                lane, rest = line.split(":", 1)
                counts[lane.strip()] = int(strip_comment(rest))

    return {"scalars": scalars, "profiles": profiles, "counts": counts}


def strip_comment(value: str) -> str:
    return value.split(" #", 1)[0].strip()


def parse_provider_list(value: str) -> list[str]:
    value = strip_comment(value)
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [provider.strip() for provider in value.split(",") if provider.strip()]


def run_installer(root: Path, case: InstallerCase, target_rel: Path) -> None:
    command = [
        "bash",
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


def powershell_executable() -> str | None:
    for name in ["powershell", "powershell.exe", "pwsh"]:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def run_powershell_codex_global_installer(root: Path, userprofile: Path) -> None:
    powershell = powershell_executable()
    if powershell is None:
        print(
            "SKIP: PowerShell executable not available; "
            "Codex PowerShell global installer regression not run",
            file=sys.stderr,
        )
        return

    env = os.environ.copy()
    env["USERPROFILE"] = str(userprofile)
    env.setdefault("HOME", str(userprofile))
    if "PSModulePath" not in env:
        system_root = env.get("SystemRoot", r"C:\Windows")
        program_files = env.get("ProgramFiles", r"C:\Program Files")
        env["PSModulePath"] = ";".join(
            [
                str(userprofile / "Documents" / "WindowsPowerShell" / "Modules"),
                rf"{program_files}\WindowsPowerShell\Modules",
                rf"{system_root}\System32\WindowsPowerShell\v1.0\Modules",
            ]
        )
    command = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "scripts" / "install-codex.ps1"),
        "-Global",
        "-Force",
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
            "codex PowerShell global installer failed:\n"
            f"{result.stdout}\n{result.stderr}"
        )


def seed_stale_overlay(project_root: Path, case: InstallerCase) -> Path:
    overlay = project_root / case.overlay
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(STALE_OVERLAY, encoding="utf-8")
    return overlay


def seed_codex_agent_overrides(project_root: Path, root: Path) -> None:
    agents_dir = project_root / ".codex" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "default.toml").write_text(
        LEGACY_CODEX_DEFAULT_AGENT,
        encoding="utf-8",
    )
    current_explorer = (root / "src.codex" / "agents" / "explorer.toml").read_text(
        encoding="utf-8"
    )
    stale_explorer = current_explorer.replace(
        'model = "gpt-5.6-sol"', 'model = "gpt-old-default"'
    )
    if stale_explorer == current_explorer:
        raise InstallerRegressionError(
            "seed_codex_agent_overrides: the model-string marker used to stage a "
            "stale explorer.toml was not found in src.codex/agents/explorer.toml "
            "(a silent no-op here would mean the reinstall-refresh check tests "
            "nothing) — update the replace() target to the current shipped model"
        )
    (agents_dir / "explorer.toml").write_text(stale_explorer, encoding="utf-8")
    (agents_dir / "worker.toml").write_text(
        CUSTOM_CODEX_WORKER_AGENT,
        encoding="utf-8",
    )


def validate_codex_agent_override_reclaim(project_root: Path) -> None:
    agents_dir = project_root / ".codex" / "agents"

    for name in ["default.toml", "explorer.toml"]:
        if (agents_dir / name).exists():
            raise InstallerRegressionError(
                f"codex did not reclaim retired pack-owned agent override {name}"
            )

    worker = (agents_dir / "worker.toml").read_text(encoding="utf-8")
    if worker != CUSTOM_CODEX_WORKER_AGENT:
        raise InstallerRegressionError(
            "codex replaced a customized built-in worker override"
        )


def validate_no_codex_agent_overrides(project_root: Path) -> None:
    agents_dir = project_root / ".codex" / "agents"
    if agents_dir.exists():
        raise InstallerRegressionError(
            "fresh codex install created the retired .codex/agents directory"
        )
    for name in ["default.toml", "explorer.toml", "worker.toml"]:
        if (agents_dir / name).exists():
            raise InstallerRegressionError(
                f"fresh codex install created retired built-in agent override {name}"
            )


def validate_overlay(
    case: InstallerCase,
    overlay: Path,
    schema_data: dict[str, Any],
) -> None:
    if not overlay.is_file():
        raise InstallerRegressionError(f"{case.name} did not create {overlay}")

    text = overlay.read_text(encoding="utf-8")
    if "externalClaudeApiMode" in text or "claude-secret" in text:
        raise InstallerRegressionError(f"{case.name} kept retired agents-mode data")
    parsed = parse_agents_mode(overlay)
    scalars = parsed["scalars"]
    profiles = parsed["profiles"]
    counts = parsed["counts"]

    expected_profiles = schema_data["priorityProfiles"]
    for profile_name, lanes in expected_profiles.items():
        if profiles.get(profile_name) != lanes:
            raise InstallerRegressionError(
                f"{case.name} shipped profile {profile_name} drifted"
            )

    expected_counts = {
        lane: int(value)
        for lane, value in schema_data["externalOpinionCounts"].items()
    }
    if counts != expected_counts:
        raise InstallerRegressionError(f"{case.name} opinion counts drifted")

    if scalars.get("externalCodexProfile") != "gpt-5.6-sol-xhigh":
        raise InstallerRegressionError(
            f"{case.name} missing shared externalCodexProfile default (gpt-5.6-sol-xhigh)"
        )

    custom = profiles.get("custom")
    if custom is None:
        raise InstallerRegressionError(f"{case.name} did not preserve custom profile")
    if custom.get("advisory.repo-understanding") != ["codex", "reserve"]:
        raise InstallerRegressionError(
            f"{case.name} did not sanitize advisory custom profile"
        )
    if custom.get("worker.default-implementation") != ["claude"]:
        raise InstallerRegressionError(
            f"{case.name} did not sanitize worker custom profile"
        )

    for profile_name, lanes in profiles.items():
        for lane_name, providers in lanes.items():
            if any(provider in {"gemini", "qwen"} for provider in providers):
                raise InstallerRegressionError(
                    f"{case.name} profile {profile_name}/{lane_name} kept example provider"
                )
            if "reserve" in providers:
                if not (lane_name.startswith("advisory.") or lane_name.startswith("review.")):
                    raise InstallerRegressionError(
                        f"{case.name} profile {profile_name}/{lane_name} kept worker reserve"
                    )
                if providers[-1] != "reserve":
                    raise InstallerRegressionError(
                        f"{case.name} profile {profile_name}/{lane_name} reserve is not last"
                    )

    if case.codex_line:
        if scalars.get("externalClaudeProfile") != "opus-xhigh":
            raise InstallerRegressionError(
                f"{case.name} missing Codex-only externalClaudeProfile"
            )
    elif "externalClaudeProfile" in scalars:
        raise InstallerRegressionError(
            f"{case.name} exposed Codex-only externalClaudeProfile"
        )


def validate_example_provider_universal_hooks(
    root: Path,
    case: InstallerCase,
    project_root: Path,
) -> None:
    if case.name not in {"gemini", "qwen"}:
        return

    manifest_path = root / f"src.{case.name}" / "extension" / f"{case.name}-extension.json"
    extension_name = load_json(manifest_path).get("name")
    if not extension_name:
        raise InstallerRegressionError(f"{case.name} extension manifest has no name")

    extension_root = project_root / f".{case.name}" / "extensions" / extension_name
    for rel in universal_hook_helper_paths(root):
        if not (extension_root / rel).is_file():
            raise InstallerRegressionError(
                f"{case.name} installer did not install universal hook/helper {rel}"
            )


def run_regression(root: Path) -> None:
    if shutil.which("bash") is None:
        raise InstallerRegressionError("bash is required for installer regression")

    schema_data = load_json(root / "shared" / "agents-mode.schema.json")
    scratch = root / ".scratch" / "agents-mode-installer-regression" / uuid.uuid4().hex
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        for case in INSTALLER_CASES:
            project_root = scratch / f"{case.name}-project"
            project_root.mkdir(parents=True, exist_ok=True)
            overlay = seed_stale_overlay(project_root, case)
            if case.codex_line:
                seed_codex_agent_overrides(project_root, root)
            run_installer(
                root,
                case,
                Path(".scratch")
                / "agents-mode-installer-regression"
                / scratch.name
                / f"{case.name}-project",
            )
            validate_overlay(case, overlay, schema_data)
            validate_example_provider_universal_hooks(root, case, project_root)
            if case.codex_line:
                validate_codex_agent_override_reclaim(project_root)

        codex_fresh_project = scratch / "codex-fresh-project"
        codex_fresh_project.mkdir(parents=True, exist_ok=True)
        codex_case = next(case for case in INSTALLER_CASES if case.name == "codex")
        run_installer(
            root,
            codex_case,
            Path(".scratch")
            / "agents-mode-installer-regression"
            / scratch.name
            / "codex-fresh-project",
        )
        validate_no_codex_agent_overrides(codex_fresh_project)

        codex_global_home = scratch / "codex-powershell-global-home"
        codex_global_home.mkdir(parents=True, exist_ok=True)
        codex_global_case = InstallerCase(
            name="codex-powershell-global",
            script="scripts/install-codex.ps1",
            overlay=".codex/.agents-mode.yaml",
            codex_line=True,
        )
        overlay = seed_stale_overlay(codex_global_home, codex_global_case)
        seed_codex_agent_overrides(codex_global_home, root)
        run_powershell_codex_global_installer(root, codex_global_home)
        validate_overlay(codex_global_case, overlay, schema_data)
        validate_codex_agent_override_reclaim(codex_global_home)

        codex_global_fresh_home = scratch / "codex-powershell-global-fresh-home"
        codex_global_fresh_home.mkdir(parents=True, exist_ok=True)
        run_powershell_codex_global_installer(root, codex_global_fresh_home)
        validate_no_codex_agent_overrides(codex_global_fresh_home)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


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
