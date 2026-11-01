"""The shared orientation owner covers every additional working area."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_orientation_requires_target_scoped_instruction_discovery():
    text = (ROOT / "shared/AGENTS.shared.md").read_text(encoding="utf-8")
    rule = next(line for line in text.splitlines() if line.startswith("- **Repository orientation;"))
    for required in ("every additional directory or repository", "parallel assignments",
                     "AGENTS.md chain", "host-supported overrides", "their subtree",
                     "shell directory change", "Reuse unchanged guidance",
                     "without expanding permissions"):
        assert required in rule
    assert not re.search(r"[A-Za-z]:[\\/]", rule)
    assert "bug inbox" not in rule.lower()
