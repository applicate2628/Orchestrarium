"""Wire scripts/validate-agents-spine.py into the standard test gate.

The spine validator guards `shared/AGENTS.shared.md` (the always-loaded governance
file merged into every installed AGENTS.md) against exceeding the Claude 40k-char
context-budget cap or dropping any manifest "protection tokens" that the
spine cut promised to keep. It shipped as a manual CLI with NO caller anywhere in
the repo (full-repo-review finding: the "fails-closed / enforces" claim was only
true if a human remembered to run it). This test makes it run on every
`pytest tests/`, so a future governance edit that drops a protection token, breaks
a reference pointer, orphans a discipline card, or blows the size cap fails the
suite — turning the manual CLI into an actually-enforced gate.

Scope note (honest): the manifest is a token-presence / deletion detector plus a
size and pointer/parity check. It proves the pinned vocabulary still appears and
the spine still fits; it does NOT prove each rule still BINDS (a MUST reworded to
"optional" while keeping the pinned token would still pass). See RELEASE_NOTES for
the precise guarantee wording.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate-agents-spine.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_validator_script_exists() -> None:
    assert VALIDATOR.is_file(), f"spine validator missing: {VALIDATOR}"


def test_spine_validator_passes_on_current_spine() -> None:
    # The actual gate: runs the real validator against the real spine on every
    # test run. Fails the suite if any protection token leaves the
    # spine, a reference pointer dies, a discipline card is orphaned, or the
    # size cap is exceeded.
    p = _run()
    assert p.returncode == 0, f"spine validator FAILED:\n{p.stdout}\n{p.stderr}"
    assert "RESULT: PASS" in p.stdout, p.stdout


def test_spine_validator_fails_on_tiny_size_cap() -> None:
    # Prove the failure path actually fires (the validator is not a no-op that
    # always passes): an absurdly low size cap must make it FAIL with non-zero exit.
    p = _run("--size-cap", "1000")
    assert p.returncode == 1, f"expected size-cap failure, got rc=0:\n{p.stdout}"
    assert "FAIL: spine size" in p.stdout, p.stdout


def test_manifest_pins_repository_orientation_teeth() -> None:
    validator_source = VALIDATOR.read_text(encoding="utf-8")
    for token in (
        "Repository orientation",
        "Names, counts, recency, and layout are not liveness evidence",
        "missing/conflicting status blocks side effects",
    ):
        assert token in validator_source, f"validator manifest does not pin {token!r}"


def test_spine_uses_single_current_owners_for_consolidated_rules() -> None:
    """The whole-spine consolidation must not regrow retired duplicate cards."""
    spine = (REPO_ROOT / "shared" / "AGENTS.shared.md").read_text(encoding="utf-8")
    validator_source = VALIDATOR.read_text(encoding="utf-8")

    for card in (
        "Verification-and-evidence core",
        "No logic duplication / no fix layering",
        "General-case over local symptoms",
        "Resource lifecycle hygiene",
    ):
        assert f"**{card}" in spine, f"missing consolidated owner {card!r}"

    for retired_card in (
        "Provider-contract evidence discipline",
        "Canonical-source maintenance discipline",
        "Markdown formula rendering format",
        "Formula scope and assumptions discipline",
        "Results-table provenance discipline",
    ):
        assert f"**{retired_card}" not in spine
        assert retired_card not in validator_source


if __name__ == "__main__":
    import unittest
    # allow `python tests/test_agents_spine_validator.py` as a quick manual run
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
