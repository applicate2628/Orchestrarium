"""Boundary corpus for the Python prompt oracle's fatal-marker expression."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from tests.fixtures.codex_hook_fixture import (
    FAKE_CODEX_HOOKS_HOST,
    prepare_codex_home,
)
from tests.fixtures.provider_prompt_projection import (
    materialize_provider_prompt_runtime,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/provider_prompt.py"
CODEX = ROOT / "src.claude/agents/scripts/invoke-codex-prompt.py"
spec = importlib.util.spec_from_file_location("provider_prompt_marker_test", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

SHIPPED_PATTERN = (
    r"^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(\.[0-9]+)?Z? )?(ERROR|FATAL|API Error)"
    r"(: | [A-Za-z0-9_]+(::[A-Za-z0-9_]+)*: )"
)


def _projected_codex_entrypoint(tmp_path: Path) -> Path:
    scripts = tmp_path / "claude-projection" / "agents" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    projection_shared = scripts.parents[1] / "shared"
    projection_shared.mkdir()
    (projection_shared / "provider-prompt-projections.v1.json").write_bytes(
        (ROOT / "shared" / "provider-prompt-projections.v1.json").read_bytes()
    )
    policy_shared = scripts.parent / "shared"
    policy_shared.mkdir()
    (policy_shared / "role-routing-policy.v1.json").write_bytes(
        (ROOT / "shared" / "role-routing-policy.v1.json").read_bytes()
    )
    materialize_provider_prompt_runtime(ROOT, scripts)
    (scripts / "resolve-agents-mode.py").write_bytes(
        (ROOT / "scripts" / "resolve-agents-mode.py").read_bytes()
    )
    entrypoint = scripts / CODEX.name
    entrypoint.write_bytes(CODEX.read_bytes())
    (scripts / "external-prompt-governance.md").write_bytes(
        (ROOT / "shared" / "external-prompt-governance.md").read_bytes()
    )
    (scripts / "external-role-taxonomy.v1.json").write_bytes(
        (ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes()
    )
    support = tmp_path / "scripts"
    support.mkdir(exist_ok=True)
    for name in ("check-hook-health.py", "universal_hooks_manifest.py", "agent-run-ledger.py"):
        (support / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    shared = tmp_path / "shared"
    shared.mkdir(exist_ok=True)
    (shared / "AGENTS.shared.md").write_bytes(
        (ROOT / "shared" / "AGENTS.shared.md").read_bytes()
    )
    return entrypoint
ORIGINAL_PATTERN = r"^(ERROR|FATAL|API Error): "
REAL_INCIDENT_LINE = (
    "2026-07-25T23:20:34.729085Z ERROR rmcp::transport::worker: worker quit "
    "with fatal: Transport channel closed"
)
REAL_SECOND_LINE = (
    "2026-07-26T01:32:22.205989Z ERROR codex_core::tools::router: "
    "error=provider transport failed"
)
POSITIVE_LINES = (
    "ERROR: plain anchored original shape",
    "FATAL: plain anchored original shape",
    "API Error: plain anchored original shape",
    REAL_INCIDENT_LINE,
    REAL_SECOND_LINE,
)
NEGATIVE_LINES = (
    "ERROR handling notes: see below",
    "API Errors will be retried automatically",
    "  fragment mentioning ^ERROR:|^FATAL: inside prose",
    "2026-07-26T01:00:00Z INFO codex_core::foo: error=None",
    "2026-07-26T01:00:00Z WARN codex_core::foo: concerning but not fatal",
    "ERROR - transient issue, retrying",
    "this line mentions ERROR in ordinary prose",
)


@pytest.mark.parametrize(
    "line", POSITIVE_LINES
)
def test_fatal_shapes_match(line: str) -> None:
    assert module.ERROR_MARKER.match(line)


@pytest.mark.parametrize(
    "line", NEGATIVE_LINES
)
def test_nonfatal_shapes_do_not_match(line: str) -> None:
    assert not module.ERROR_MARKER.match(line)


def test_python_owner_carries_the_exact_canonical_pattern() -> None:
    assert module.ERROR_MARKER.pattern == SHIPPED_PATTERN


def test_original_pattern_reproduces_the_timestamped_fatal_gap() -> None:
    for line in POSITIVE_LINES[:3]:
        assert re.match(ORIGINAL_PATTERN, line)
    for line in (REAL_INCIDENT_LINE, REAL_SECOND_LINE):
        assert not re.match(ORIGINAL_PATTERN, line)
        assert module.ERROR_MARKER.match(line)


def _make_work_item(tmp_path: Path, suffix: str) -> Path:
    item = tmp_path / "work-items" / "active" / f"2026-01-01-{suffix}"
    item.mkdir(parents=True)
    (item / "design.md").write_text("fixture artifact\n", encoding="utf-8")
    (item / "status.md").write_text(
        "# Status\n\n- state: open\n\n"
        "## Current state\n\nFixture item.\n\n"
        "## Active agents\n\n- none\n\n"
        "## Completed agents\n\n- none\n\n"
        "## Next action\n\n- none\n",
        encoding="utf-8",
    )
    return item


def _run_transport(tmp_path: Path, err_line: str) -> dict:
    fake = tmp_path / "fake-codex.py"
    fake.write_text(
        "import json,os,runpy,sys\n"
        "args=sys.argv[1:]\n"
        "if 'app-server' in args:\n"
        f"    runpy.run_path({str(FAKE_CODEX_HOOKS_HOST)!r}, run_name='__main__')\n"
        "sys.stdin.buffer.read()\n"
        "print(json.dumps({'type':'item.completed','item':"
        "{'type':'agent_message','text':'GATE: PASS\\n'}}))\n"
        f"print({err_line!r}, file=sys.stderr)\n",
        encoding="utf-8",
    )
    item = _make_work_item(tmp_path, "fatal-marker-fixture")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture prompt\n", encoding="utf-8")
    env = os.environ.copy()
    env["CODEX_BIN"] = str(fake)
    env["CODEX_PROMPTS_DIR"] = str(tmp_path / "outputs")
    env["CODEX_HOME"] = str(prepare_codex_home(tmp_path))
    result = subprocess.run(
        [
            sys.executable,
            str(_projected_codex_entrypoint(tmp_path)),
            "fatal-marker-fixture",
            "--prompt-file",
            str(prompt),
            "--ledger",
            str(item),
            "--ledger-role",
            "architecture-reviewer",
            "--ledger-lane",
            "fixture-lane",
            "--ledger-artifact",
            "design.md",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    events = [
        json.loads(line)
        for line in (item / "agent-runs.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    return next(
        event for event in events if event.get("eventKind") == "terminal"
    )


def test_real_captured_fatal_line_blocks_an_otherwise_passing_run(
    tmp_path: Path,
) -> None:
    terminal = _run_transport(tmp_path, REAL_INCIDENT_LINE)
    assert terminal["status"] == "blocked"
    assert terminal["gate"] == "none"
    assert "err markers present" in terminal["notes"]


def test_control_clean_err_with_same_shape_run_settles_as_pass(
    tmp_path: Path,
) -> None:
    terminal = _run_transport(
        tmp_path,
        "2026-07-26T01:00:00Z INFO codex_core::foo: normal operation",
    )
    assert terminal["status"] == "completed"
    assert terminal["gate"] == "PASS"
