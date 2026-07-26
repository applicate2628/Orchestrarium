"""Regression test for the check-mcp-momentum import contract when the shared
`hook_common` helper is unimportable.

THE BUG THIS FILE GUARDS AGAINST (work-items/bugs/2026-07-26-the-mcp-momentum-
audit-stubs-its-own-delivery-to-a-no-op.md): a prior version of
`check-mcp-momentum.py` (and its two byte-identical mirrors) caught the
`hook_common` import in a `try/except Exception` and substituted no-op stubs
on failure -- `read_stdin_utf8()` returning `""`, `parse_envelope()` returning
`{}`, `emit_advisory()` doing nothing. That made a broken install produce an
exit-0, empty-stdout, empty-stderr run: BYTE-IDENTICAL to a clean run where
the model made no code-navigation search at all. No test in this repository
asserted what any of the five universal audits do when `hook_common` cannot
be imported -- the same coverage hole that let the original delivery defect
(dead PreToolUse stderr-plus-exit-1 channel) live in all six audits at once
before it was caught.

THE CHOSEN CONTRACT (matches the other four universal audits, none of which
ever caught this import): import `hook_common` directly, with no fallback.
A broken install now surfaces as an uncaught `ImportError` -- Python's default
exit code 1 and a traceback on stderr -- instead of a silent, indistinguishable
exit 0. This still satisfies the hook's own AUDIT-mode contract ("never
block"): per work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-
session-form-its-sibling-calls-broken.md, only an exit-2 PreToolUse hook
blocks the tool call on either Claude Code or Codex CLI -- exit 1 (which an
uncaught exception produces) still ALLOWS the tool call on both runtimes.

WHY THE FIXTURE COPIES THE HOOK INTO AN ISOLATED TEMP DIRECTORY rather than
hiding/renaming the real `hook_common.py` in place: this repository's
`Worktree safety` rule forbids mutating tracked files outside the task's own
edits, and mutating the real shared helper (even temporarily, even restored
afterward) risks a race with any other process reading it during the test
run. Copying the hook script alone into a throwaway directory with an EMPTY
sibling `scripts/` folder (no `hook_common.py` present at all) reproduces
"the shared helper is unimportable" with zero risk to the real tree: a fresh
`sys.path` per subprocess means nothing from the real repo's own
`sys.path`/`PYTHONPATH` can smuggle the real module in underneath the
isolated copy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE_HOOK = REPO_ROOT / "src.claude" / "agents" / "hooks" / "check-mcp-momentum.py"
UNIVERSAL_HOOK = REPO_ROOT / "scripts" / "universal-hooks" / "hooks" / "check-mcp-momentum.py"
CODEX_HOOK = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks" / "check-mcp-momentum.py"

# The canon plus its two byte-identical mirrors (see
# scripts/sync-universal-hooks.py for the canonical direction).
HOOKS = (
    ("universal (canon)", UNIVERSAL_HOOK),
    ("claude mirror", CLAUDE_HOOK),
    ("codex mirror", CODEX_HOOK),
)


def _run_with_unimportable_hook_common(hook_path: Path) -> subprocess.CompletedProcess:
    """Copy `hook_path` into a fresh `<tmp>/hooks/` dir alongside an empty
    `<tmp>/scripts/` dir (no `hook_common.py` present), then run it as a
    subprocess fed a real code-navigation envelope. The hook's own
    `sys.path.insert(0, ..parent/"scripts")` line resolves to that empty
    directory, so `import hook_common` fails exactly as it would on a
    partial/corrupted install that is missing the shared helper file."""
    workdir = Path(tempfile.mkdtemp())
    hooks_dir = workdir / "hooks"
    scripts_dir = workdir / "scripts"
    hooks_dir.mkdir()
    scripts_dir.mkdir()  # deliberately empty: no hook_common.py anywhere in it
    isolated_hook = hooks_dir / hook_path.name
    shutil.copy2(hook_path, isolated_hook)

    # A real hit-shaped envelope (matches _mcp_momentum_envelope in
    # test_audit_hook_payload_shape.py): if the old silent-stub behavior were
    # still present, this is exactly the input that would have produced a
    # clean, silent exit 0 instead of a detectable failure.
    envelope = {"tool_name": "Grep", "tool_input": {"pattern": "def parse_config"}}
    return subprocess.run(
        [sys.executable, str(isolated_hook)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class McpMomentumHookCommonUnimportableTests(unittest.TestCase):
    def test_unimportable_hook_common_is_detectable_not_a_silent_pass(self) -> None:
        """Pins the chosen contract: a missing `hook_common` must be visibly
        different from a clean run (nonzero exit, non-empty stderr), and must
        NOT emit a fabricated advisory on stdout -- but must also not exit 2,
        which would violate this hook's own "AUDIT mode never blocks"
        contract."""
        for label, hook_path in HOOKS:
            with self.subTest(hook=label):
                result = _run_with_unimportable_hook_common(hook_path)
                self.assertNotEqual(
                    result.returncode, 0,
                    "a missing hook_common must not exit 0 silently -- that is "
                    "the exact defect this test guards against",
                )
                self.assertNotEqual(
                    result.returncode, 2,
                    "must not BLOCK the tool call -- AUDIT mode never denies "
                    "(only exit 2 blocks on either runtime)",
                )
                self.assertEqual(
                    result.stdout, "",
                    "a broken import must not fabricate an advisory payload on stdout",
                )
                self.assertIn(
                    "hook_common", result.stderr,
                    "the failure must name the missing module, not just fail generically",
                )


if __name__ == "__main__":
    unittest.main()
