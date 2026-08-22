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
EXAMPLE_PROVIDER_NAMES = frozenset({"gemini", "qwen"})


def validate_production_provider_partition() -> None:
    actual = frozenset(case.name for case in INSTALLER_CASES)
    if actual != PRODUCTION_PROVIDER_NAMES:
        raise InstallerRegressionError(
            "production installer regression must cover exactly codex and claude"
        )
    if actual & EXAMPLE_PROVIDER_NAMES:
        raise InstallerRegressionError(
            "example providers must not be treated as production installer cases"
        )


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


def run_python_codex_global_installer(root: Path, userprofile: Path) -> None:
    env = os.environ.copy()
    env["USERPROFILE"] = str(userprofile)
    env.setdefault("HOME", str(userprofile))
    command = [
        sys.executable,
        str(root / "scripts" / "install-codex.py"),
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
            "codex Python global installer failed:\n"
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


def run_regression(root: Path) -> None:
    validate_production_provider_partition()
    schema_data = load_json(root / "shared" / "agents-mode.schema.json")
    scratch = root / ".scratch" / "agents-mode-installer-regression" / uuid.uuid4().hex
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        for case in INSTALLER_CASES:
            project_root = scratch / f"{case.name}-project"
            project_root.mkdir(parents=True, exist_ok=True)
            overlay = seed_stale_overlay(project_root, case)
            run_installer(
                root,
                case,
                Path(".scratch")
                / "agents-mode-installer-regression"
                / scratch.name
                / f"{case.name}-project",
            )
            validate_overlay(case, overlay, schema_data)
            if case.codex_line:
                validate_codex_native_role_install(project_root, root)

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
        validate_codex_native_role_install(codex_fresh_project, root)

        codex_global_home = scratch / "codex-python-global-home"
        codex_global_home.mkdir(parents=True, exist_ok=True)
        codex_global_case = InstallerCase(
            name="codex-python-global",
            script="scripts/install-codex.py",
            overlay=".codex/.agents-mode.yaml",
            codex_line=True,
        )
        overlay = seed_stale_overlay(codex_global_home, codex_global_case)
        run_python_codex_global_installer(root, codex_global_home)
        validate_overlay(codex_global_case, overlay, schema_data)
        validate_codex_native_role_install(codex_global_home, root)

        codex_global_fresh_home = scratch / "codex-python-global-fresh-home"
        codex_global_fresh_home.mkdir(parents=True, exist_ok=True)
        run_python_codex_global_installer(root, codex_global_fresh_home)
        validate_codex_native_role_install(codex_global_fresh_home, root)
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
