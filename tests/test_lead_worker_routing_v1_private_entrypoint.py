from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_CORE = (
    ROOT
    / "src.codex"
    / "skills"
    / "lead-worker-routing"
    / "scripts"
    / "_resolver_base.py"
)


def _request() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "dispatchId": "dispatch-private-entrypoint",
        "policySnapshotId": "policy-private-entrypoint",
        "leadHost": "codex",
        "assignedRole": "architecture-reviewer",
        "scopeId": "scope-private-entrypoint",
        "capabilitySlot": "engineering-challenge",
        "mutationClass": "read-only",
        "requiredTools": [],
        "excludedProviderFamilies": [],
        "artifactContract": "challenge-report-v1",
        "gateContract": "lead-verifies-v1",
        "candidates": [
            {
                "candidateId": "claude-worker",
                "provider": "claude",
                "runtime": "claude-cli",
                "providerFamily": "anthropic",
                "model": "runtime-observed-model",
                "effort": "high",
                "priority": 1,
                "availability": "available",
                "maxMutationClass": "read-only",
                "capabilities": ["engineering-challenge"],
                "tools": [],
                "isolatedFromLead": True,
                "maxDelegationDepth": 0,
                "authorizing": False,
                "evidenceSnapshotId": "evidence-private-entrypoint",
            }
        ],
    }


def test_private_selection_core_cannot_be_invoked_as_cli(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    run = subprocess.run(
        [sys.executable, "-S", str(PRIVATE_CORE), "--request-file", str(request_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert run.returncode == 2
    assert run.stderr == ""
    result = json.loads(run.stdout)
    assert result["status"] == "denied"
    assert result["stableId"] == "E_LEAD_WORKER_V1_PRIVATE_ENTRYPOINT"
    assert result["selectedCandidate"] is None
    assert result["authorizing"] is False
