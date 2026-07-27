"""Read-only registration health checks for both provider schemas."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check-hook-health.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_hook_health_tests", CHECKER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


def _source_dirs(platform: str) -> tuple[Path, ...]:
    if platform == "claude":
        return (
            ROOT / "src.claude" / "agents" / "scripts",
            ROOT / "src.claude" / "agents" / "hooks",
        )
    return (
        ROOT / "src.codex" / "skills" / "lead" / "scripts",
        ROOT / "src.codex" / "skills" / "lead" / "hooks",
    )


def _target_for(platform: str, stem: str) -> Path:
    for directory in _source_dirs(platform):
        candidate = directory / f"{stem}.py"
        if candidate.is_file():
            return candidate
    raise AssertionError(f"missing Python target for {platform}:{stem}")


def _config(platform: str) -> dict:
    entries = []
    for stem in sorted(CHECKER._manifest_stems(ROOT, platform)):
        target = _target_for(platform, stem)
        if platform == "claude":
            hook = {
                "type": "command",
                "command": sys.executable,
                "args": [str(target)],
            }
        else:
            hook = {
                "type": "command",
                "command": " ".join(
                    shlex.quote(token) for token in (sys.executable, str(target))
                ),
            }
        entries.append({"hooks": [hook]})
    return {"hooks": {"PreToolUse": entries}}


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_registered_command_executes_every_owned_hook(
    tmp_path: Path, platform: str
) -> None:
    target = tmp_path / f"{platform}.json"
    target.write_text(json.dumps(_config(platform)), encoding="utf-8")
    messages = CHECKER.verify_config(
        target=target,
        platform=platform,
        host_os="posix",
        repo_root=ROOT,
        verify_fires=True,
    )
    expected = CHECKER._manifest_stems(ROOT, platform)
    assert len(messages) == len(expected)
    assert all(message.startswith(f"PASS {platform} ") for message in messages)


def test_missing_executable_and_missing_target_are_distinct(tmp_path: Path) -> None:
    executable_config = _config("claude")
    executable_config["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = str(
        tmp_path / "missing-python"
    )
    executable_json = tmp_path / "missing-executable.json"
    executable_json.write_text(json.dumps(executable_config), encoding="utf-8")
    with pytest.raises(ValueError, match="registered executable is missing"):
        CHECKER.verify_config(
            target=executable_json,
            platform="claude",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
        )

    target_config = _config("claude")
    target_config["hooks"]["PreToolUse"][0]["hooks"][0]["args"] = [
        str(tmp_path / "agents-mode-reminder.py")
    ]
    target_json = tmp_path / "missing-target.json"
    target_json.write_text(json.dumps(target_config), encoding="utf-8")
    with pytest.raises(ValueError, match="registered target is missing"):
        CHECKER.verify_config(
            target=target_json,
            platform="claude",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
        )


def test_leftover_wrapper_warning_is_read_only(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(_config("claude")), encoding="utf-8")
    installed = tmp_path / "agents"
    wrapper = installed / "scripts" / "check-bugfix-discipline.ps1"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("wrapper\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(CHECKER_PATH),
            "--target",
            str(target),
            "--platform",
            "claude",
            "--host-os",
            "posix",
            "--repo-root",
            str(ROOT),
            "--installed-root",
            str(installed),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert f"WARN leftover hook wrapper: {wrapper}" in completed.stdout
    assert wrapper.read_text(encoding="utf-8") == "wrapper\n"


def test_hook_health_nonzero_names_failing_hook(tmp_path: Path) -> None:
    failing_stem = "agents-mode-reminder"
    installed_root = tmp_path / "agents"
    for source_dir in _source_dirs("claude"):
        shutil.copytree(source_dir, installed_root / source_dir.name)

    config = _config("claude")
    for entry in config["hooks"]["PreToolUse"]:
        for hook in entry["hooks"]:
            source_target = Path(hook["args"][0])
            hook["args"] = [
                str(installed_root / source_target.parent.name / source_target.name)
            ]

    installed_target = installed_root / "scripts" / f"{failing_stem}.py"
    installed_target.write_text(
        "import sys\n"
        'sys.stderr.write("deliberate installed hook failure\\n")\n'
        "raise SystemExit(37)\n",
        encoding="utf-8",
    )

    matching_hooks = [
        hook
        for entry in config["hooks"]["PreToolUse"]
        for hook in entry["hooks"]
        if Path(hook["args"][0]).stem == failing_stem
    ]
    assert len(matching_hooks) == 1
    matching_hooks[0]["args"] = [str(installed_target)]

    target = tmp_path / "settings.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(CHECKER_PATH),
            "--target",
            str(target),
            "--platform",
            "claude",
            "--host-os",
            "windows" if os.name == "nt" else "posix",
            "--repo-root",
            str(ROOT),
            "--verify-fires",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode != 0
    assert failing_stem in completed.stderr
    assert "deliberate installed hook failure" in completed.stderr
