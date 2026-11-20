"""Installed native association CLI; no AGY child/session or model invocation."""
import json
import os
from pathlib import Path
import subprocess
import sys

from test_agent_run_ledger import prepare_valid_work_item
from test_mutate_work_item import quick_status

ROOT = Path(__file__).resolve().parents[1]
INSTANT = "2026-11-18T15:00:00Z"


def test_installed_native_binding_uses_own_cohort_and_preserves_neighbors(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "isolated-home"
    home.mkdir()
    neighbor = project / ".agents/skills/codex-owned/SKILL.md"
    neighbor.parent.mkdir(parents=True)
    neighbor.write_bytes(b"Unrelated Codex skill")
    environment = dict(os.environ, HOME=str(home), USERPROFILE=str(home),
                       PYTHONDONTWRITEBYTECODE="1")
    environment.pop("PYTHONPATH", None)
    environment.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    installed = subprocess.run([sys.executable, str(ROOT / "scripts/install-client.py"),
        "--client", "antigravity", "--target", str(project), "--allow-unsafe-target"],
        cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    scripts = project / ".agents/orchestrarium-antigravity/scripts"
    entrypoint = scripts / "sdk_execution/native_binding.py"
    assert entrypoint.read_bytes() == (ROOT / "scripts/sdk_execution/native_binding.py").read_bytes()
    item = prepare_valid_work_item(tmp_path / "task-state")
    (item / "status.md").write_text(quick_status())
    assignment = dict(schema_version=1, kind="native-child-assignment",
        assignment_id="installed-native-research", provider="antigravity",
        parent_conversation_id="native-parent", role="researcher",
        scope=["source analysis"], task="Inspect supplied source without modification.",
        expected_artifact="research.md", acceptance="Root verifies source evidence.")
    source = tmp_path / "assignment.json"
    source.write_text(json.dumps(assignment))
    def command(*args, succeeds=True):
        result = subprocess.run([sys.executable, str(entrypoint), "--work-item", str(item), *args],
            cwd=project, env=environment, capture_output=True, text=True, encoding="utf-8")
        if not succeeds:
            assert result.returncode != 0, result.stdout
            return result
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout.splitlines()[-1])
    prepared = command("prepare", "--assignment-file", str(source), "--started-at", INSTANT)
    assert prepared["status"] == "prepared-unbound" and prepared["binding"] is None
    args = ("bind", "--assignment-id", assignment["assignment_id"],
        "--assignment-sha256", prepared["assignment_sha256"],
        "--child-conversation-id", "native-child",
        "--evidence-reference", "Root observed native child in UI", "--started-at", INSTANT)
    bound = command(*args)
    assert bound["status"] == "root-bound"
    assert all(bound[key] is False for key in
               ("authorizing", "native_execution_verified", "completion_verified"))
    ledger = item / "agent-runs.jsonl"
    before = ledger.read_bytes()
    assert command("readback", "--assignment-id", assignment["assignment_id"]) == bound
    assert command(*args) == bound
    assert ledger.read_bytes() == before
    rows = [json.loads(line) for line in before.splitlines()]
    assert len(rows) == 2
    assert all(row["eventKind"] == "standalone" and row["gate"] == "none" for row in rows)
    assert all("sdkExecution" not in row and "launchRunId" not in row for row in rows)
    # The checkout still exists, but missing installed authority cannot fall back to it.
    helper = scripts / "agent-run-ledger.py"
    saved = tmp_path / "retained-installed-ledger.py"
    helper.rename(saved)
    try:
        command("readback", "--assignment-id", assignment["assignment_id"], succeeds=False)
        assert ledger.read_bytes() == before
    finally:
        saved.rename(helper)
    assert command("readback", "--assignment-id", assignment["assignment_id"]) == bound
    assert neighbor.read_bytes() == b"Unrelated Codex skill"
