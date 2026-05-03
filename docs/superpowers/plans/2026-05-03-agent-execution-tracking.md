# Agent Execution Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real, machine-checkable work-item execution ledger so Orchestrarium can track launched agents, artifacts, verdicts, evidence, stale work, and required corrective loops instead of relying only on narrative reports.

**Architecture:** Keep `status.md` as the human-readable recovery snapshot, and add `agent-runs.jsonl` as the machine-readable event ledger inside each active work-item. Add one Python validator with Bash/PowerShell wrappers, then wire the contract into shared references, Codex/Claude/Gemini/Qwen role contracts, docs, tests, and release notes.

**Tech Stack:** Python standard library, JSON Lines, Markdown governance docs, existing PowerShell/Bash wrapper pattern, existing pytest suite.

---

## Baseline

- Baseline tag: `baseline-agent-tracking-2026-05-03`
- Baseline commit: `6732d4f tooling: sync agents-mode docs from contract`
- Baseline branch: `main`

## File Structure

- Create `shared/schemas/agent-runs.schema.json`: canonical JSON schema for one ledger event.
- Create `scripts/validate-work-item-state.py`: repository validator for `agent-runs.jsonl`, `status.md`, artifacts, and closeout readiness.
- Create `scripts/validate-work-item-state.sh`: POSIX wrapper that calls the Python validator.
- Create `scripts/validate-work-item-state.ps1`: PowerShell wrapper that calls the Python validator.
- Create `tests/test_work_item_state_validator.py`: validator tests covering PASS, REVISE, BLOCKED, stale running agents, evidence requirements, and closeout blocks.
- Modify `src.codex/skills/lead/subagent-contracts.md`: add the ledger contract to the Codex lead handoff and status rules.
- Modify `src.claude/agents/contracts/subagent-contracts.md`: mirror the same ledger contract for Claude.
- Modify `src.gemini/skills/lead/subagent-contracts.md`: mirror the same ledger contract for Gemini.
- Modify `src.qwen/skills/lead/subagent-contracts.md`: mirror the same ledger contract for Qwen.
- Modify `shared/references/subagent-operating-model.md`: add the shared execution-ledger model and validation gate.
- Modify `shared/references/ru/subagent-operating-model.md`: add the Russian equivalent.
- Modify `docs/agents-mode-reference.md`: document that `parallelMode`, `externalOpinionCounts`, and `external-brigade` must produce ledger entries when work-item tracking is enabled.
- Modify `docs/external-worker-design.md`: add execution-record-to-ledger mapping for external adapters.
- Modify `README.md` and `INSTALL.md`: mention the new validator and where it fits.
- Modify `RELEASE_NOTES.md`: explain the operator-facing improvement.
- Modify provider validators where appropriate:
  - `src.codex/skills/lead/scripts/validate-skill-pack.sh`
  - `src.claude/agents/scripts/validate-skill-pack.sh`
  - `src.gemini/scripts/validate-pack.sh`
  - `src.qwen/scripts/validate-pack.sh`

## Ledger Event Shape

Every line in `agent-runs.jsonl` is one JSON object:

```json
{
  "schemaVersion": 1,
  "runId": "2026-05-03T14-20-00Z-lead-qa-001",
  "workItem": "2026-05-03-agent-execution-tracking",
  "role": "qa-engineer",
  "executionRole": "internal",
  "assignedRole": "qa-engineer",
  "provider": "codex",
  "model": "gpt-5.4-xhigh",
  "status": "completed",
  "gate": "PASS",
  "scope": ["scripts/validate-work-item-state.py", "tests/test_work_item_state_validator.py"],
  "promptFile": ".scratch/prompts/2026-05-03-qa-001.md",
  "artifact": "work-items/active/2026-05-03-agent-execution-tracking/reviews/qa.md",
  "evidence": [
    {
      "kind": "command",
      "ref": "pytest tests/test_work_item_state_validator.py -q",
      "result": "passed"
    }
  ],
  "startedAt": "2026-05-03T14:20:00Z",
  "updatedAt": "2026-05-03T14:24:00Z",
  "notes": "Validated happy path and stale-running-agent failure."
}
```

Allowed values:

- `status`: `planned`, `running`, `completed`, `revise`, `blocked`, `cancelled`
- `gate`: `PASS`, `REVISE`, `BLOCKED:dependency`, `BLOCKED:prerequisite`, `RETURN(role)`, `advisory`, `none`
- `executionRole`: `main`, `lead`, `internal`, `consultant`, `external-worker`, `external-reviewer`, `external-brigade`

## Task 1: Schema And Fixture Tests

**Files:**
- Create: `shared/schemas/agent-runs.schema.json`
- Create: `tests/test_work_item_state_validator.py`

- [ ] **Step 1: Create the schema file**

Add `shared/schemas/agent-runs.schema.json` with this content:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://orchestrarium.local/schemas/agent-runs.schema.json",
  "title": "Orchestrarium agent run ledger event",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schemaVersion",
    "runId",
    "workItem",
    "role",
    "executionRole",
    "status",
    "gate",
    "scope",
    "startedAt",
    "updatedAt"
  ],
  "properties": {
    "schemaVersion": { "const": 1 },
    "runId": { "type": "string", "minLength": 8 },
    "workItem": { "type": "string", "minLength": 1 },
    "role": { "type": "string", "minLength": 1 },
    "executionRole": {
      "enum": ["main", "lead", "internal", "consultant", "external-worker", "external-reviewer", "external-brigade"]
    },
    "assignedRole": { "type": "string" },
    "provider": { "type": "string" },
    "model": { "type": "string" },
    "status": { "enum": ["planned", "running", "completed", "revise", "blocked", "cancelled"] },
    "gate": {
      "enum": ["PASS", "REVISE", "BLOCKED:dependency", "BLOCKED:prerequisite", "RETURN(role)", "advisory", "none"]
    },
    "scope": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
    "promptFile": { "type": "string" },
    "artifact": { "type": "string" },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["kind", "ref"],
        "properties": {
          "kind": { "enum": ["command", "artifact", "visual", "review", "manual-check", "log"] },
          "ref": { "type": "string", "minLength": 1 },
          "result": { "type": "string" }
        }
      }
    },
    "startedAt": { "type": "string", "minLength": 10 },
    "updatedAt": { "type": "string", "minLength": 10 },
    "notes": { "type": "string" }
  }
}
```

- [ ] **Step 2: Add the first failing tests**

Create `tests/test_work_item_state_validator.py` with this initial test content:

```python
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_validator(work_item: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--work-item", str(work_item)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def valid_status() -> str:
    return """---
template: full-delivery
orchestrator: lead
started: 2026-05-03
updated: 2026-05-03 14:24
---

## Current state

- **Primary task**: add agent run tracking
- **Primary task status**: active
- **Interruption marker**: none
- **Stage**: QA
- **Main conv role**: reviewing artifact
- **Last accepted artifact**: reviews/qa.md
- **Open obligations before closeout**: none

## Active agents

| Agent | Role | Status | Launched |
| --- | --- | --- | --- |

## Completed agents

| Agent | Role | Result | Artifact |
| --- | --- | --- | --- |
| qa-001 | qa-engineer | PASS | reviews/qa.md |

## Next action

Close the stage after publication gate.
"""


def ledger_event(**overrides):
    event = {
        "schemaVersion": 1,
        "runId": "2026-05-03T14-20-00Z-qa-001",
        "workItem": "agent-execution-tracking",
        "role": "qa-engineer",
        "executionRole": "internal",
        "assignedRole": "qa-engineer",
        "provider": "codex",
        "model": "gpt-5.4-xhigh",
        "status": "completed",
        "gate": "PASS",
        "scope": ["scripts/validate-work-item-state.py"],
        "promptFile": ".scratch/prompts/qa-001.md",
        "artifact": "reviews/qa.md",
        "evidence": [{"kind": "command", "ref": "pytest tests/test_work_item_state_validator.py -q", "result": "passed"}],
        "startedAt": "2026-05-03T14:20:00Z",
        "updatedAt": "2026-05-03T14:24:00Z",
        "notes": "happy path",
    }
    event.update(overrides)
    return event


def test_pass_ledger_with_artifact_and_evidence(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event()) + "\n")

    result = run_validator(item)

    assert result.returncode == 0, result.stdout
    assert "RESULT: PASS" in result.stdout


def test_pass_without_evidence_fails(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(evidence=[])) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "PASS gate requires evidence" in result.stdout
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_work_item_state_validator.py -q
```

Expected result: tests fail because `scripts/validate-work-item-state.py` does not exist.

- [ ] **Step 4: Commit the failing contract tests**

```powershell
git add shared/schemas/agent-runs.schema.json tests/test_work_item_state_validator.py
git commit -m "test: define agent run ledger contract"
```

## Task 2: Validator Core

**Files:**
- Create: `scripts/validate-work-item-state.py`
- Modify: `tests/test_work_item_state_validator.py`

- [ ] **Step 1: Implement the minimal validator**

Create `scripts/validate-work-item-state.py` with this implementation:

```python
#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


STATUS_VALUES = {"planned", "running", "completed", "revise", "blocked", "cancelled"}
GATE_VALUES = {"PASS", "REVISE", "BLOCKED:dependency", "BLOCKED:prerequisite", "RETURN(role)", "advisory", "none"}
EXECUTION_ROLES = {"main", "lead", "internal", "consultant", "external-worker", "external-reviewer", "external-brigade"}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_jsonl(path: Path, errors: list[str]) -> list[dict]:
    if not path.exists():
        fail(errors, f"missing ledger: {path}")
        return []
    events = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(errors, f"{path}:{line_no}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(event, dict):
            fail(errors, f"{path}:{line_no}: event must be an object")
            continue
        events.append(event)
    if not events:
        fail(errors, f"ledger has no events: {path}")
    return events


def validate_event(event: dict, item: Path, seen: set[str], errors: list[str]) -> None:
    required = ["schemaVersion", "runId", "workItem", "role", "executionRole", "status", "gate", "scope", "startedAt", "updatedAt"]
    for key in required:
        if key not in event:
            fail(errors, f"event missing required field: {key}")

    run_id = event.get("runId")
    if isinstance(run_id, str):
        if run_id in seen:
            fail(errors, f"duplicate runId: {run_id}")
        seen.add(run_id)

    if event.get("schemaVersion") != 1:
        fail(errors, f"{run_id}: schemaVersion must be 1")
    if event.get("status") not in STATUS_VALUES:
        fail(errors, f"{run_id}: invalid status {event.get('status')!r}")
    if event.get("gate") not in GATE_VALUES:
        fail(errors, f"{run_id}: invalid gate {event.get('gate')!r}")
    if event.get("executionRole") not in EXECUTION_ROLES:
        fail(errors, f"{run_id}: invalid executionRole {event.get('executionRole')!r}")
    if not isinstance(event.get("scope"), list) or not event.get("scope"):
        fail(errors, f"{run_id}: scope must be a non-empty list")

    gate = event.get("gate")
    status = event.get("status")
    artifact = event.get("artifact")
    evidence = event.get("evidence")

    if gate == "PASS":
        if status != "completed":
            fail(errors, f"{run_id}: PASS gate requires completed status")
        if not artifact:
            fail(errors, f"{run_id}: PASS gate requires artifact")
        elif not (item / artifact).exists():
            fail(errors, f"{run_id}: artifact does not exist: {artifact}")
        if not isinstance(evidence, list) or not evidence:
            fail(errors, f"{run_id}: PASS gate requires evidence")

    if gate == "REVISE" and status not in {"revise", "completed"}:
        fail(errors, f"{run_id}: REVISE gate requires revise or completed status")
    if isinstance(gate, str) and gate.startswith("BLOCKED") and status != "blocked":
        fail(errors, f"{run_id}: BLOCKED gate requires blocked status")


def validate_status(item: Path, events: list[dict], errors: list[str]) -> None:
    status_path = item / "status.md"
    if not status_path.exists():
        fail(errors, f"missing status.md: {status_path}")
        return
    text = status_path.read_text(encoding="utf-8")
    for section in ["## Current state", "## Active agents", "## Completed agents", "## Next action"]:
        if section not in text:
            fail(errors, f"status.md missing section: {section}")

    running_events = [event for event in events if event.get("status") == "running"]
    if running_events and "Primary task status**: closed" in text:
        fail(errors, "status.md cannot be closed while ledger has running agents")


def validate_work_item(item: Path) -> list[str]:
    errors: list[str] = []
    events = load_jsonl(item / "agent-runs.jsonl", errors)
    seen: set[str] = set()
    for event in events:
        validate_event(event, item, seen, errors)
    validate_status(item, events, errors)
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-item", required=True, help="Path to one work-items/active/<item> directory")
    args = parser.parse_args(argv)

    item = Path(args.work_item).resolve()
    errors = validate_work_item(item)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"RESULT: FAIL ({len(errors)} errors)")
        return 1
    print(f"RESULT: PASS ({item})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 2: Run the tests**

Run:

```powershell
pytest tests/test_work_item_state_validator.py -q
```

Expected result: both tests pass.

- [ ] **Step 3: Commit the validator core**

```powershell
git add scripts/validate-work-item-state.py tests/test_work_item_state_validator.py
git commit -m "feat: add work-item agent run validator"
```

## Task 3: Failure Modes And Wrappers

**Files:**
- Modify: `scripts/validate-work-item-state.py`
- Create: `scripts/validate-work-item-state.sh`
- Create: `scripts/validate-work-item-state.ps1`
- Modify: `tests/test_work_item_state_validator.py`

- [ ] **Step 1: Add stale running, duplicate, and blocked tests**

Append these tests to `tests/test_work_item_state_validator.py`:

```python
def test_closed_status_with_running_agent_fails(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    closed = valid_status().replace("Primary task status**: active", "Primary task status**: closed")
    write(item / "status.md", closed)
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(status="running", gate="none", artifact="", evidence=[])) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "cannot be closed while ledger has running agents" in result.stdout


def test_duplicate_run_id_fails(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    event = ledger_event()
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(event) + "\n" + json.dumps(event) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "duplicate runId" in result.stdout


def test_blocked_gate_requires_blocked_status(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(status="completed", gate="BLOCKED:dependency", artifact="", evidence=[])) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "BLOCKED gate requires blocked status" in result.stdout
```

- [ ] **Step 2: Run tests to verify they pass**

Run:

```powershell
pytest tests/test_work_item_state_validator.py -q
```

Expected result: all validator tests pass.

- [ ] **Step 3: Add POSIX wrapper**

Create `scripts/validate-work-item-state.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
else
  echo "FAIL: python or python3 is required" >&2
  exit 1
fi

exec "$PYTHON_BIN" "$REPO_ROOT/scripts/validate-work-item-state.py" "$@"
```

- [ ] **Step 4: Add PowerShell wrapper**

Create `scripts/validate-work-item-state.ps1`:

```powershell
[CmdletBinding(PositionalBinding = $false)]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $Arguments
)

$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'validate-work-item-state.py'
if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "Unable to locate validate-work-item-state.py next to $PSCommandPath."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
  throw "Unable to locate python or py."
}

& $python.Source $scriptPath @Arguments
exit $LASTEXITCODE
```

- [ ] **Step 5: Run wrappers**

Run:

```powershell
pytest tests/test_work_item_state_validator.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\validate-work-item-state.ps1 --work-item .\work-items\active\agent-execution-tracking
```

Expected result: pytest passes. The PowerShell wrapper may fail until a real work item exists; for this task the wrapper is structurally valid if it reaches the validator and reports `missing ledger`.

- [ ] **Step 6: Commit wrappers and failure-mode coverage**

```powershell
git add scripts/validate-work-item-state.py scripts/validate-work-item-state.sh scripts/validate-work-item-state.ps1 tests/test_work_item_state_validator.py
git commit -m "test: cover work-item tracking failure modes"
```

## Task 4: Contract Documentation

**Files:**
- Modify: `src.codex/skills/lead/subagent-contracts.md`
- Modify: `src.claude/agents/contracts/subagent-contracts.md`
- Modify: `src.gemini/skills/lead/subagent-contracts.md`
- Modify: `src.qwen/skills/lead/subagent-contracts.md`
- Modify: `shared/references/subagent-operating-model.md`
- Modify: `shared/references/ru/subagent-operating-model.md`

- [ ] **Step 1: Add ledger rule to Codex subagent contracts**

In `src.codex/skills/lead/subagent-contracts.md`, under `### status.md format`, add:

```markdown
### agent-runs.jsonl format

When task memory is configured, every delegated role, external adapter, consultant sweep, and main-session gate action that produces or accepts an artifact must append one JSON object to `agent-runs.jsonl` in the same work-item directory.

The ledger is machine-readable execution state; `status.md` remains the human-readable recovery summary. A `PASS` in `status.md` is not accepted unless the corresponding ledger event has `gate: "PASS"`, `status: "completed"`, an artifact path, and at least one evidence entry.

Minimum required fields are defined by `shared/schemas/agent-runs.schema.json`: `schemaVersion`, `runId`, `workItem`, `role`, `executionRole`, `status`, `gate`, `scope`, `startedAt`, and `updatedAt`.

Before closeout, run `scripts/validate-work-item-state.* --work-item <path>` or the installed equivalent when the repository exposes one. Closeout is blocked while the ledger contains running agents, duplicate run IDs, missing artifacts for `PASS`, `PASS` without evidence, or inconsistent `BLOCKED` / `REVISE` status.
```

- [ ] **Step 2: Mirror the same section into Claude, Gemini, and Qwen contracts**

Add the same section to:

- `src.claude/agents/contracts/subagent-contracts.md`
- `src.gemini/skills/lead/subagent-contracts.md`
- `src.qwen/skills/lead/subagent-contracts.md`

Use provider-specific wording only for the validator path if needed; keep field names identical.

- [ ] **Step 3: Update shared references**

In `shared/references/subagent-operating-model.md`, under `11.2 Task-memory root and recovery`, add:

```markdown
- `agent-runs.jsonl` is the machine-readable execution ledger for the work item. It records each launched or accepted agent run, assigned role, execution path, status, gate, artifact, and evidence. The lead must use it to reconcile active, completed, blocked, and revise states before closeout.
- `status.md` and `agent-runs.jsonl` must agree at stage boundaries: no closed task with running ledger entries, no accepted `PASS` without evidence, no missing artifact for a completed gate, and no dependent downstream `PASS` left untouched after a material upstream revision.
```

In `shared/references/ru/subagent-operating-model.md`, add the Russian equivalent:

```markdown
- `agent-runs.jsonl` — машиночитаемый журнал исполнения work-item. Он фиксирует каждый запуск или приём результата агента: роль, execution path, статус, gate, artifact и evidence. Lead обязан использовать его для сверки active, completed, blocked и revise состояний перед closeout.
- `status.md` и `agent-runs.jsonl` должны совпадать на границах стадий: нельзя закрывать задачу при running ledger entries, принимать `PASS` без evidence, принимать completed gate без artifact или оставлять downstream `PASS` без re-review после существенной правки upstream artifact.
```

- [ ] **Step 4: Run Markdown scan**

Run:

```powershell
rg -n "\$\$|\\\(|\\\)|\\sb|\\sp" shared src.codex src.claude src.gemini src.qwen
```

Expected result: no new Markdown formula violations from this task.

- [ ] **Step 5: Commit contract docs**

```powershell
git add src.codex/skills/lead/subagent-contracts.md src.claude/agents/contracts/subagent-contracts.md src.gemini/skills/lead/subagent-contracts.md src.qwen/skills/lead/subagent-contracts.md shared/references/subagent-operating-model.md shared/references/ru/subagent-operating-model.md
git commit -m "docs: define agent execution ledger contract"
```

## Task 5: Operator Docs And Release Notes

**Files:**
- Modify: `docs/agents-mode-reference.md`
- Modify: `docs/external-worker-design.md`
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `RELEASE_NOTES.md`

- [ ] **Step 1: Document routing-to-ledger behavior**

In `docs/agents-mode-reference.md`, near the `parallelMode` and `externalOpinionCounts` sections, add:

```markdown
When task memory is enabled, every parallel helper lane, external-opinion lane, and brigade item must write or be represented by an `agent-runs.jsonl` event. `parallelMode` decides whether independent work may fan out; the ledger records what actually ran and blocks closeout if a helper remains running, lacks evidence, or has no accepted artifact.
```

- [ ] **Step 2: Document external adapter mapping**

In `docs/external-worker-design.md`, near the execution record section, add:

```markdown
The provider execution record maps directly to `agent-runs.jsonl`: `Execution role` becomes `executionRole`; `Assigned / replaced internal role` becomes `assignedRole`; `Resolved provider` becomes `provider`; `Model / profile used` becomes `model`; `Actual execution path` is recorded in `notes` or a future `executionPath` field when the path is publication-safe. External adapter closeout is incomplete until the ledger has the adapter event, artifact, gate, and evidence.
```

- [ ] **Step 3: Update README and INSTALL**

Add one short paragraph to `README.md` under the task-memory or orchestration section:

```markdown
Work-item execution tracking uses `agent-runs.jsonl` beside `status.md` for machine-readable agent state. Use `scripts/validate-work-item-state.* --work-item <path>` before closeout to catch stale agents, missing evidence, inconsistent gates, or accepted artifacts that were never verified.
```

Add one short paragraph to `INSTALL.md` near the project-local runtime notes:

```markdown
Project repositories that use `work-items/` may also keep `agent-runs.jsonl` in each active work item. The file is local task memory, not publication content; validators use it to reconcile subagent execution before closeout.
```

- [ ] **Step 4: Update release notes**

Under today's `## 2026-05-03` heading in `RELEASE_NOTES.md`, add or create:

```markdown
- Added the first work-item execution tracking contract: active work items can now keep `agent-runs.jsonl` beside `status.md`, and the new validator catches stale agents, missing evidence, duplicate run IDs, and inconsistent gates before closeout. This turns the existing "verify subagents before trusting them" governance into an operator-checkable workflow.
```

- [ ] **Step 5: Commit docs**

```powershell
git add docs/agents-mode-reference.md docs/external-worker-design.md README.md INSTALL.md RELEASE_NOTES.md
git commit -m "docs: document work-item execution tracking"
```

## Task 6: Provider Pack Validators

**Files:**
- Modify: `src.codex/skills/lead/scripts/validate-skill-pack.sh`
- Modify: `src.claude/agents/scripts/validate-skill-pack.sh`
- Modify: `src.gemini/scripts/validate-pack.sh`
- Modify: `src.qwen/scripts/validate-pack.sh`
- Modify: `tests/test_work_item_state_validator.py`

- [ ] **Step 1: Add validator script existence checks**

In each provider validator, add checks that these files exist in the source repo:

```text
shared/schemas/agent-runs.schema.json
scripts/validate-work-item-state.py
scripts/validate-work-item-state.sh
scripts/validate-work-item-state.ps1
```

For standalone provider branches, guard the checks the same way existing root-level checks are guarded: source branch checks only when those files are part of the branch layout.

- [ ] **Step 2: Add contract text checks**

In each provider validator, check for these strings in the provider's subagent contract file:

```text
agent-runs.jsonl
PASS in status.md is not accepted
scripts/validate-work-item-state
```

- [ ] **Step 3: Add shared-reference checks**

In the Codex validator, add checks that `shared/references/subagent-operating-model.md` contains:

```text
machine-readable execution ledger
no accepted `PASS` without evidence
```

- [ ] **Step 4: Run provider validators**

Run:

```powershell
bash src.codex/skills/lead/scripts/validate-skill-pack.sh
powershell -ExecutionPolicy Bypass -File src.codex\skills\lead\scripts\validate-skill-pack.ps1
bash src.claude/agents/scripts/validate-skill-pack.sh
powershell -ExecutionPolicy Bypass -File src.claude\agents\scripts\validate-skill-pack.ps1
bash src.gemini/scripts/validate-pack.sh
powershell -ExecutionPolicy Bypass -File src.gemini\scripts\validate-pack.ps1
bash src.qwen/scripts/validate-pack.sh
powershell -ExecutionPolicy Bypass -File src.qwen\scripts\validate-pack.ps1
```

Expected result: all provider validators pass.

- [ ] **Step 5: Commit validator integration**

```powershell
git add src.codex/skills/lead/scripts/validate-skill-pack.sh src.claude/agents/scripts/validate-skill-pack.sh src.gemini/scripts/validate-pack.sh src.qwen/scripts/validate-pack.sh tests/test_work_item_state_validator.py
git commit -m "test: enforce agent execution tracking contract"
```

## Task 7: Full Verification And Install Check

**Files:**
- No new source files unless verification reveals a defect.

- [ ] **Step 1: Run Python tests**

```powershell
pytest -q
```

Expected result: all tests pass.

- [ ] **Step 2: Run diff hygiene**

```powershell
git diff --check
git diff --cached --check
```

Expected result: no whitespace or conflict-marker errors.

- [ ] **Step 3: Run publication gate**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-publication-gate.ps1
```

Expected result: publication gate passes or reports only expected release-note coverage already handled in Task 5.

- [ ] **Step 4: Run global install dry or live check**

If the user wants live global install after review, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Global
```

Expected result: installer reports success for the selected production providers. If only a dry verification is desired, skip this step and state that global install was not refreshed.

- [ ] **Step 5: Final commit if verification fixes were needed**

If Task 7 required any fixes:

```powershell
git add <fixed files>
git commit -m "chore: finalize agent execution tracking validation"
```

## Self-Review

- Spec coverage: The plan tags the baseline, adds a machine-readable ledger, validates artifacts/evidence/gates, updates shared and provider contracts, updates operator docs, and adds tests.
- Placeholder scan: No `TBD`, `TODO`, or open-ended "add appropriate handling" instructions are used.
- Type consistency: The same fields are used in schema, validator, tests, docs, and provider contracts: `schemaVersion`, `runId`, `workItem`, `role`, `executionRole`, `assignedRole`, `provider`, `model`, `status`, `gate`, `scope`, `promptFile`, `artifact`, `evidence`, `startedAt`, `updatedAt`, `notes`.

## Execution Options

1. **Subagent-Driven (recommended)**: dispatch one fresh worker per task group, review after each task, and keep the main session as integrator/verifier.
2. **Inline Execution**: implement the plan in this session with checkpoints after each commit.

## Terms and Abbreviations

- `agent-runs.jsonl`: JSON Lines ledger file recording one machine-readable agent execution event per line.
- `artifact`: a concrete output such as a patch, review report, QA report, design note, or closure memo.
- `BLOCKED`: gate state meaning work cannot proceed because a dependency or prerequisite is unavailable.
- `gate`: acceptance decision for a scoped artifact.
- `JSON`: JavaScript Object Notation; structured text data format.
- `JSON Lines`: file format where each line is one standalone JSON object.
- `ledger`: append-oriented record used as the source for machine checks.
- `PASS`: gate state meaning the scoped artifact passed required checks.
- `REVISE`: gate state meaning the artifact must return to the same role for bounded correction.
- `validator`: script that checks files and returns a pass/fail result.
- `work-item`: repository task-memory directory containing `brief.md`, `status.md`, plans, artifacts, and now the execution ledger.
