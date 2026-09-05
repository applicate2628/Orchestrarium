"""Run documented selector examples; never launch a model or trust synthetic costs."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs/routing-v1-operator-guide.md"
SELECTOR = "src.codex/skills/astra-routing/scripts/resolve.py"


@pytest.mark.parametrize("label,code,effort,reason", [
    ("quality-medium", 0, "medium", None),
    ("measured-medium", 0, "medium", None),
    ("effort-mismatch", 2, None, "E_ASTRA_V1_ECONOMICS_EFFORT_MISMATCH"),
    ("below-floor", 2, None, "E_ASTRA_V1_EFFORT_BELOW_MINIMUM"),
])
def test_documented_selector_example(label, code, effort, reason):
    assert GUIDE.is_file(), "operator guide missing"
    text = GUIDE.read_text(encoding="utf-8")
    pattern = rf"<!-- selector-example:{re.escape(label)} -->\s*```text\n(.*?)\n```"
    examples = re.findall(pattern, text, re.DOTALL)
    assert len(examples) == 1, "each documented example needs one exact command"
    argv = shlex.split(examples[0].replace("\\\n", " "))
    # Documentation is data: this test admits only the known pure selector.
    assert argv[:2] == ["python", SELECTOR]
    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / SELECTOR), *argv[2:]],
        cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == code, result.stderr
    assert result.stderr == ""
    decision = json.loads(result.stdout)
    assert decision["effort"] == effort
    assert decision["stableId"] == reason
    assert decision["executionAuthorized"] is False
    assert decision["authorizing"] is False
    assert decision["fallback"] == "none"
    if code:
        assert decision["codexFlags"] == []
    else:
        assert decision["codexFlags"] == [
            "--model", "gpt-6-astra", "-c", f"model_reasoning_effort={effort}",
        ]
        assert decision["requiresAdapterAdmission"] is True
        assert decision["requiresIndependentReview"] is True


def test_guide_distinguishes_source_and_installed_acceptance():
    assert GUIDE.is_file(), "operator guide missing"
    text = GUIDE.read_text(encoding="utf-8")
    assert "source-checkout examples" in text
    assert "not evidence of an installed-provider acceptance run" in text
    assert "synthetic" in text
    assert "independent" in text
    assert "../src.codex/skills/astra-routing/SKILL.md" in text
    assert "../src.codex/skills/lead-worker-routing/SKILL.md" in text
    assert "common-skill body pins" in text
    assert "accepted-prior" in text
