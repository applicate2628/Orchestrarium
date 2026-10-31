from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import ast
import hashlib
import dataclasses
from collections import Counter
from pathlib import Path
from unittest import mock

import pytest

from git_push_gate_target import GateTarget, target_for


ROOT = Path(__file__).resolve().parents[1]
CANON_DIR = ROOT / "scripts" / "universal-hooks" / "scripts"
SCRIPT_DIRS = (
    CANON_DIR,
    ROOT / "src.codex" / "skills" / "lead" / "scripts",
    ROOT / 'adapters/claude' / "agents" / "scripts",
)
POLICY_NAME = "check-git-push-gate.py"
RUNNER_NAME = "check-git-push-gate-runner.py"
EXPECTED_FAILURE_ID = "PRG-RUNNER-UNAVAILABLE"
TARGETS = tuple(
    target_for(label, directory)
    for label, directory in zip(("canonical", "codex", "claude"), SCRIPT_DIRS)
)


def test_shared_hook_input_applicability_preserves_publication_failure_contract() -> None:
    for target in TARGETS:
        owner = _load(target.preflight_path, f"shared_hook_input_{target.label}")
        for name, payload in (
            ("Bash", {"command": "git push origin main"}),
            ("exec_command", {"command": "git push origin main"}),
            ("functions.exec_command", {"cmd": "git push origin main"}),
        ):
            result = owner.build_preflight({"tool_name": name, "tool_input": payload})
            assert owner.validate_preflight_result(result) is result
            assert result.failure_id == "PRG-WORKDIR-INVALID"
            assert result.reason_id == "PFP-DENY-KNOWN"
        for payload in (None, {}, {"cmd": " "}, {"cmd": 0},
                        {"cmd": "", "command": "git push origin main"},
                        {"cmd": "git push origin main", "command": "git push origin main"}):
            with mock.patch.object(owner, "parse_shell_command", side_effect=AssertionError("unacquired input reached parser")):
                result = owner.build_preflight({"tool_name": "exec_command", "tool_input": payload})
            assert owner.validate_preflight_result(result) is result
            assert (result.outcome, result.reason_id, result.continuation, result.failure_id) == (
                "DEFER", "PFP-DENY-KNOWN", "RENDER_DENY", "PGG-PARSE-UNCERTAIN")
            assert result.command is None and result.dialect is None and result.parsed is None
            assert result.generic_decision is None
            assert result.repository_workdir == result.repository_workdir_source == ""
        for envelope in (
            {"tool_name": "update_plan", "tool_input": {"steps": []}},
            {"tool_name": "legacy-shell", "tool_input": {"command": "git push origin main"}},
            {"tool_input": {"command": "git push origin main"}},
        ):
            with mock.patch.object(owner, "parse_shell_command", side_effect=AssertionError("unrelated input reached parser")):
                result = owner.build_preflight(envelope)
            assert owner.validate_preflight_result(result) is result
            assert (result.outcome, result.reason_id, result.continuation) == ("ALLOW_FINAL", "PFP-ALLOW-NO-COMMAND", "NONE")
            assert result.command is None and result.dialect is None and result.parsed is None
        with mock.patch.object(owner, "acquire_tool_input", side_effect=RuntimeError("synthetic private detail")):
            result = owner.build_preflight({"tool_name": "Bash", "tool_input": {"command": "git push origin main"}})
        assert owner.validate_preflight_result(result) is result
        assert result.reason_id == "PFP-DENY-INTERNAL" and result.continuation == "RENDER_DENY"


def test_shared_hook_input_unavailable_command_is_denied_by_the_public_runner() -> None:
    for target in TARGETS:
        for envelope, denied in (
            ({"tool_name": "exec_command", "tool_input": {"cmd": "", "command": "git push origin main"}}, True),
            ({"tool_name": "update_plan", "tool_input": {"steps": []}}, False),
        ):
            actual = _run(target, envelope)
            assert actual.returncode == 0 and actual.stderr == ""
            if denied:
                body = json.loads(actual.stdout)
                assert body["hookSpecificOutput"]["permissionDecision"] == "deny"
                assert "PGG-PARSE-UNCERTAIN" in body["hookSpecificOutput"]["permissionDecisionReason"]
            else:
                assert actual.stdout == ""


def _load_gate_target(target: GateTarget, suffix: str):
    script_dir = str(target.policy_path.parent)
    added = script_dir not in sys.path
    if added:
        sys.path.insert(0, script_dir)
    try:
        sys.modules.pop("hook_common", None)
        sys.modules.pop("git_push_gate_preflight", None)
        common = _load(target.common_path, "hook_common")
        preflight = _load(target.preflight_path, "git_push_gate_preflight")
        policy = _load(target.policy_path, f"r5_policy_{target.label}_{suffix}")
        runner = _load(target.runner_path, f"r5_runner_{target.label}_{suffix}")
        return common, preflight, policy, runner
    finally:
        if added:
            sys.path.remove(script_dir)


def test_zero_signal_incomplete_analysis_abstains_without_authority() -> None:
    """S1/S3: unknown observation alone cannot veto or authorize an operation."""
    target = TARGETS[0]
    _common, preflight, _policy, _runner = _load_gate_target(target, "abstention")
    # Observer data only. The first input is valid PowerShell; its body remains
    # incomplete under the observed Bash/POSIX analysis without runtime claims.
    commands = (
        "@'\nconst value = { label: \"it's synthetic\" };\n"
        "console.log(JSON.stringify(value));\n'@ | node",
        "env 1=x\nprintf 'git push origin sample'",
    )
    for command in commands:
        envelope = {"tool_name": "Bash", "tool_input": {"command": command}}
        result = preflight.build_preflight(envelope)
        assert result[:3] == (
            "ABSTAIN", "PFP-ABSTAIN-NO-PUBLICATION-EVIDENCE", "NONE",
        )
        assert result.command == command and result.dialect == "posix"
        assert preflight.find_git_push_records(result.parsed) == []
        assert not preflight._has_malformed_minus_c_push_candidate(result.parsed)
        assert not result.parsed.effective_publications.exact_complete
        assert result.parsed.effective_publications.eligible_direct_dry == ()
        assert result.parsed.effective_publications.eligible_direct_generic == ()
        assert (result.repository_workdir, result.repository_workdir_source) == ("", "")
        assert result.generic_decision is result.failure_id is None
        for surface in ("policy", "runner"):
            completed = _run(target, envelope, surface=surface)
            assert (completed.returncode, completed.stdout, completed.stderr) == (0, "", "")
    # Real receiving paths still refuse an observed unauthorized publication.
    for surface in ("policy", "runner"):
        completed = _run(target, {
            "tool_name": "Bash", "tool_input": {"command": "git push origin main"},
        }, surface=surface)
        assert completed.returncode == 0 and completed.stderr == ""
        decision = json.loads(completed.stdout)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"
        assert decision["permissionDecisionReason"].startswith("PRG-WORKDIR-INVALID:")


def _load(path: Path, name: str):
    script_dir = str(path.parent)
    added = script_dir not in sys.path
    if added:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        if added:
            sys.path.remove(script_dir)


def _run(
    target: GateTarget,
    envelope: dict,
    *,
    surface: str = "runner",
    env: dict[str, str] | None = None,
):
    script = target.runner_path if surface == "runner" else target.policy_path
    return subprocess.run(
        [sys.executable, "-B", str(script)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=env,
        check=False,
        timeout=20,
    )


def _copy_runner(target_dir: Path) -> GateTarget:
    target = target_for("temporary", target_dir)
    shutil.copy2(CANON_DIR / RUNNER_NAME, target.runner_path)
    target.common_path.write_text("# fixed synthetic sibling\n", encoding="utf-8")
    target.preflight_path.write_text(
        "from typing import NamedTuple\n"
        "class Result(NamedTuple): outcome: str\n"
        "def build_preflight_from_stdin(): return Result('DEFER')\n"
        "def validate_preflight_result(value): return value\n",
        encoding="utf-8",
    )
    return target


@pytest.mark.parametrize(
    "selected,cwd_present,cwd,check,source,kind",
    (
        ({"workdir": {"PRIVATE-WORKDIR-CANARY": "secret"}}, True, None, "non-string", "tool", "object"),
        ({}, True, "PRIVATE-WORKDIR-CANARY", "relative", "envelope", "string"),
        ({}, False, None, "missing", "absent", "missing"),
        ({"workdir": ""}, False, None, "empty", "tool", "string"),
        ({"workdir": "PRIVATE-WORKDIR-CANARY\x00"}, False, None, "nul", "tool", "string"),
        ({"workdir": None}, True, None, "non-string", "tool", "null"),
    ),
)
def test_workdir_diagnostic_public_entry_preserves_denial_and_privacy(
    tmp_path: Path, selected, cwd_present, cwd, check, source, kind,
) -> None:
    transcript = tmp_path / "synthetic-transcript.jsonl"
    transcript.write_text(json.dumps({"type": "user", "message": {
        "role": "user", "content": "[approve-publication]",
    }}) + "\n", encoding="utf-8")
    envelope = {"tool_name": "Bash", "transcript_path": str(transcript),
                "tool_input": {"command": "git push origin HEAD:refs/heads/topic", **selected}}
    if cwd_present:
        envelope["cwd"] = str(tmp_path) if cwd is None else cwd
    expected = (f"Workdir diagnostics: stage=input-selection; check={check}; "
                f"subject=invocation; source={source}; value-kind={kind}.")
    for target in TARGETS:
        results = [_run(target, envelope, surface=surface) for surface in ("runner", "policy")]
        assert (results[0].returncode, results[0].stdout, results[0].stderr) == (
            results[1].returncode, results[1].stdout, results[1].stderr,
        )
        result = results[0]
        assert result.returncode == 0 and result.stderr == ""
        body = json.loads(result.stdout)
        assert set(body) == {"hookSpecificOutput"}
        output = body["hookSpecificOutput"]
        assert set(output) == {"hookEventName", "permissionDecision", "permissionDecisionReason"}
        assert output["hookEventName"] == "PreToolUse" and output["permissionDecision"] == "deny"
        assert output["permissionDecisionReason"].startswith(
            "PRG-WORKDIR-INVALID: Use one explicit absolute repository root for the push tool call."
        )
        assert output["permissionDecisionReason"].endswith(expected)
        assert "PRIVATE-WORKDIR-CANARY" not in result.stdout
        assert str(tmp_path) not in result.stdout and str(transcript) not in result.stdout


def test_workdir_diagnostic_public_normalization_preserves_selected_source(tmp_path: Path) -> None:
    (tmp_path / "child").mkdir()
    transcript = tmp_path / "synthetic-transcript.jsonl"
    transcript.write_text(json.dumps({"type": "user", "message": {
        "role": "user", "content": "[approve-publication]",
    }}) + "\n", encoding="utf-8")
    for target in TARGETS:
        _common, _preflight, policy, _runner = _load_gate_target(target, "canonical_workdir")
        command = shlex.join(("git", *policy.native_git_config_arguments(), "push", "origin", "HEAD:refs/heads/topic"))
        envelope = {"tool_name": "Bash", "transcript_path": str(transcript),
                    "cwd": str(tmp_path), "tool_input": {
                        "command": command,
                        "workdir": str(tmp_path / "child") + os.sep + "..",
                    }}
        direct, runner = (_run(target, envelope, surface=s) for s in ("policy", "runner"))
        assert (direct.returncode, direct.stdout, direct.stderr) == (runner.returncode, runner.stdout, runner.stderr)
        assert runner.returncode == 0 and runner.stderr == ""
        output = json.loads(runner.stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny"
        assert output["permissionDecisionReason"].endswith(
            "Workdir diagnostics: stage=invocation-qualification; check=canonical-mismatch; "
            "subject=invocation; source=tool; value-kind=string."
        )
        assert str(tmp_path) not in runner.stdout


def _assert_runner_deny(completed: subprocess.CompletedProcess[str]) -> None:
    assert completed.returncode == 0
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    specific = payload["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["permissionDecision"] == "deny"
    reason = specific["permissionDecisionReason"]
    assert reason.startswith(EXPECTED_FAILURE_ID + ":")
    for forbidden in (
        "Traceback",
        str(ROOT),
        "git push",
        "RuntimeError",
        "SENSITIVE-PREFAILURE-OUTPUT",
    ):
        assert forbidden not in completed.stdout


def test_runner_is_mirrored_and_installer_registers_it() -> None:
    runner_bytes = [(directory / RUNNER_NAME).read_bytes() for directory in SCRIPT_DIRS]
    assert runner_bytes[0] == runner_bytes[1] == runner_bytes[2]

    installer = _load(ROOT / "scripts" / "production_installer.py", "runner_installer")
    for provider, installed_root in (
        ("codex", Path("/installed/codex/lead")),
        ("claude", Path("/installed/claude/agents")),
    ):
        specs = installer._hook_specs(provider, installed_root)
        matches = [row for row in specs if row[0] == "check-git-push-gate"]
        assert len(matches) == 1
        assert matches[0][1].name == RUNNER_NAME


def test_runner_and_direct_policy_are_semantically_equivalent(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "[approve-publication]"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    envelopes = (
        {
            "tool_name": "Bash",
            "tool_input": {"command": "echo safe"},
            "transcript_path": str(transcript),
        },
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main"},
            "transcript_path": str(transcript),
        },
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main"},
            "transcript_path": str(tmp_path / "missing.jsonl"),
        },
    )
    for target in TARGETS:
        for envelope in envelopes:
            direct = _run(target, envelope, surface="policy")
            delegated = _run(target, envelope)
            assert (
                delegated.returncode,
                delegated.stdout,
                delegated.stderr,
            ) == (direct.returncode, direct.stdout, direct.stderr)


def test_runner_uses_only_fixed_sibling_and_cache_is_optional(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    (tmp_path / POLICY_NAME).write_text(
        "def main(_preflight=None):\n    print('SIBLING')\n    return 0\n",
        encoding="utf-8",
    )
    lookalike = tmp_path / "lookalike"
    lookalike.mkdir()
    (lookalike / POLICY_NAME).write_text(
        "raise RuntimeError('LOOKALIKE EXECUTED')\n", encoding="utf-8"
    )
    envelope = {"tool_name": "Bash", "tool_input": {"command": "git push"}}
    base_env = os.environ.copy()
    base_env["PYTHONPATH"] = str(lookalike)

    ordinary = _run(runner, envelope, env=base_env)
    no_cache_env = dict(base_env)
    no_cache_env["PYTHONDONTWRITEBYTECODE"] = "1"
    no_cache = _run(runner, envelope, env=no_cache_env)

    assert (ordinary.returncode, ordinary.stdout, ordinary.stderr) == (0, "SIBLING\n", "")
    assert (no_cache.returncode, no_cache.stdout, no_cache.stderr) == (0, "SIBLING\n", "")


def test_runner_rejects_ambient_bytecode_cache_prefix(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    (tmp_path / POLICY_NAME).write_text(
        "import sys\ndef main(_preflight=None):\n    print(repr(sys.pycache_prefix))\n    return 0\n",
        encoding="utf-8",
    )
    ambient_cache = tmp_path / "ambient-cache"
    ambient_cache.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPYCACHEPREFIX"] = str(ambient_cache)
    completed = _run(
        runner,
        {"tool_name": "Bash", "tool_input": {"command": "git push"}},
        env=environment,
    )
    assert (completed.returncode, completed.stdout, completed.stderr) == (0, "None\n", "")


def test_runner_terminal_preflight_never_loads_heavy_policy(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    (tmp_path / "git_push_gate_preflight.py").write_text(
        "from typing import NamedTuple\n"
        "class Result(NamedTuple): outcome: str\n"
        "def build_preflight_from_stdin(): return Result('ALLOW_FINAL')\n"
        "def validate_preflight_result(value): return value\n",
        encoding="utf-8",
    )
    (tmp_path / POLICY_NAME).write_text(
        "raise RuntimeError('HEAVY-POLICY-LOADED')\n", encoding="utf-8"
    )
    completed = _run(
        runner, {"tool_name": "Bash", "tool_input": {"command": "echo safe"}}
    )
    assert (completed.returncode, completed.stdout, completed.stderr) == (0, "", "")


def test_runner_preflight_failures_are_buffered_and_fail_closed(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    preflight = tmp_path / "git_push_gate_preflight.py"
    cases = (
        "raise RuntimeError('PRELOAD')\n",
        "print('SENSITIVE-PREFAILURE-OUTPUT')\nraise KeyboardInterrupt()\n",
        "def build_preflight_from_stdin(): return object()\n"
        "def validate_preflight_result(_value): raise TypeError('foreign')\n",
    )
    for source in cases:
        preflight.write_text(source, encoding="utf-8")
        _assert_runner_deny(
            _run(runner, {"tool_name": "Bash", "tool_input": {"command": "git push"}})
        )


def test_runner_denies_instead_of_importing_ambient_hook_common(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    fixed_common = tmp_path / "hook_common.py"
    fixed_common.unlink()
    (tmp_path / POLICY_NAME).write_text(
        "import hook_common\ndef main():\n    print(hook_common.SOURCE)\n    return 0\n",
        encoding="utf-8",
    )
    lookalike = tmp_path / "lookalike"
    lookalike.mkdir()
    (lookalike / "hook_common.py").write_text(
        "SOURCE = 'AMBIENT-HOOK-COMMON'\n", encoding="utf-8"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(lookalike)
    completed = _run(
        runner,
        {"tool_name": "Bash", "tool_input": {"command": "git push"}},
        env=environment,
    )
    _assert_runner_deny(completed)
    assert "AMBIENT-HOOK-COMMON" not in completed.stdout


def test_runner_fails_closed_for_all_predelegation_failures(tmp_path: Path) -> None:
    runner = _copy_runner(tmp_path)
    policy = tmp_path / POLICY_NAME
    envelope = {"tool_name": "Bash", "tool_input": {"command": "git push"}}

    cases: tuple[tuple[str, str | None], ...] = (
        ("missing", None),
        ("syntax", "def broken(:\n"),
        ("exception", "def main():\n    raise RuntimeError('raw')\n"),
        (
            "output-then-exception",
            "def main():\n    print('SENSITIVE-PREFAILURE-OUTPUT')\n    raise RuntimeError('raw')\n",
        ),
        ("interrupt", "def main():\n    raise KeyboardInterrupt()\n"),
        ("system-exit", "def main():\n    raise SystemExit(7)\n"),
        ("bad-result", "def main():\n    return 'allow'\n"),
    )
    for name, source in cases:
        if policy.exists():
            if policy.is_dir():
                policy.rmdir()
            else:
                policy.unlink()
        if source is not None:
            policy.write_text(source, encoding="utf-8")
        completed = _run(runner, envelope)
        _assert_runner_deny(completed)

    if policy.exists():
        policy.unlink()
    policy.mkdir()
    _assert_runner_deny(_run(runner, envelope))
