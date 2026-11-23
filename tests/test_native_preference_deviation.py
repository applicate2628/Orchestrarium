"""Model-free contract for deviations from preference, separate from launch admission."""
from pathlib import Path
import json
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = [
    sys.executable, "-B", str(ROOT / "scripts/resolve-agents-mode.py"),
    "--provider", "codex", "--repo-root", str(ROOT), "--host-controls", "explicit",
    "--task-class", "critical-design", "--role", "computational-scientist", "--json",
]
REASON = "The current host inventory lists Sol but not the preferred Astra."
REQUIRED = "E_ORDINARY_NATIVE_PREFERENCE_DEVIATION_REASON_REQUIRED"


def select(model, effort, *args, rationale="Review the accepted scientific evidence."):
    result = subprocess.run(
        [*CLI, "--ordinary-native-action", "resolve", "--caller-rationale", rationale,
         "--approved-scope-json", '{"read":true}', "--requested-model", model,
         "--requested-effort", effort, *args],
        cwd=ROOT, capture_output=True, encoding="utf-8", check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("flags", [(), ("--preference-deviation-reason", " "),
                                  ("--reported-model", "gpt-6.2-sol")])
def test_admitted_nonpreferred_selection_needs_a_reason(flags):
    result = select("gpt-6.2-sol", "xhigh", *flags)
    assert result["stableId"] == REQUIRED
    assert result["configurationDiagnostic"]["preferredModel"] == "gpt-6.2-astra"
    assert "invocation" not in result
    assert result["fallback"] == "none"


def test_equal_reason_text_and_unavailable_preference_do_not_create_false_refusals():
    result = select("gpt-6.2-sol", "xhigh", "--reported-model", "gpt-6.2-sol",
                    "--preference-deviation-reason", REASON, rationale=REASON)
    assert result["status"] == "resolved"
    assert result["invocation"]["model"] == "gpt-6.2-sol"
    assert result["preferenceDeviation"] == {
        "preferredModel": "gpt-6.2-astra", "preferredEffort": "high", "reason": REASON,
    }


def test_preference_does_not_grant_approval_and_effort_changes_need_a_reason():
    extra = select("gpt-6.2-astra", "xhigh", "--preference-deviation-reason", REASON)
    assert extra["configurationDiagnostic"]["stage"] == "model-launch-policy"
    assert select("gpt-6.2-astra", "xhigh", "--user-approved-launch")["stableId"] == REQUIRED
    same = select("gpt-6.2-astra", "high", "--user-approved-launch")
    assert same["status"] == "resolved"
    assert "preferenceDeviation" not in same
