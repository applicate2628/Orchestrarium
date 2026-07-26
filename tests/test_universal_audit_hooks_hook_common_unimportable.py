"""Regression coverage for what EVERY warn-only PreToolUse audit does when the
shared `hook_common` helper is unimportable.

THE COVERAGE HOLE THIS FILE CLOSES (work-items/bugs/2026-07-26-the-mcp-
momentum-audit-stubs-its-own-delivery-to-a-no-op.md, "Expected" item 3): "no
test asserts what any audit does when `hook_common` is unimportable." Two
audits were pinned first, each in its own file
(`test_mcp_momentum_hook_common_unimportable.py`,
`test_typed_routing_hook_common_unimportable.py`) because they were the two
found to still carry a silent fallback stub. The other four
(`check-machine-local-path`, `check-no-trash-in-repo`,
`check-stale-relation-residue`, `check-repository-orientation`) already
imported `hook_common` directly with no fallback, so no test ever asserted
that EITHER: a re-added stub in any of the six would go uncaught.

THIS FILE REPLACES THE TWO SINGLE-AUDIT FILES ABOVE (now deleted) rather than
adding four more near-identical ones beside them: the harness (copy the hook
into an isolated directory with an empty sibling `scripts/` dir, run it as a
subprocess fed a real hit-shaped envelope, assert the failure shape) is ONE
invariant applied per audit, not six separately-owned copies of the same
logic. Parameterizing over the audit set here mirrors
`tests/test_audit_hook_payload_shape.py`'s own `SIMPLE_CASES` /
`RepositoryOrientationPayloadShapeTests` split for the identical reason that
file gives: repository-orientation needs a git-root + transcript fixture on
disk, the other five need only a flat envelope.

THE CHOSEN CONTRACT (uniform across all six, per the parent bug's own
"Expected" item 1 -- "decide the contract once ... not one per file, chosen
by accident"): import `hook_common` directly, no fallback stub. A broken
install now surfaces as an uncaught `ImportError` -- Python's default exit
code 1 and a traceback naming the missing module on stderr -- instead of a
silent, indistinguishable exit 0. This still satisfies every audit's own
AUDIT-mode contract ("never block"): only an exit-2 PreToolUse hook blocks
the tool call on either Claude Code or Codex CLI (work-items/bugs/2026-07-26-
mcp-reminder-uses-the-once-per-session-form-its-sibling-calls-broken.md);
exit 1 (an uncaught exception's default) still ALLOWS the tool call on both
runtimes.

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

Each envelope is a real HIT-shaped payload (matching the corresponding
envelope-builder in `test_audit_hook_payload_shape.py`): if a silent fallback
stub were reintroduced, this is exactly the input that would have produced a
clean, silent exit 0 instead of a detectable failure -- feeding a miss-shaped
envelope would pass this test identically whether the code detects the
broken install or merely happens not to fire, which would prove nothing.
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

CLAUDE_HOOKS = REPO_ROOT / "src.claude" / "agents" / "hooks"
UNIVERSAL_HOOKS = REPO_ROOT / "scripts" / "universal-hooks" / "hooks"
CODEX_HOOKS = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks"

# The five audits mirrored across all three trees, plus the Claude-only sixth
# (check-typed-routing has no canon copy and no Codex mirror -- see
# PACK_ONLY_HOOKS in scripts/universal_hooks_manifest.py and
# test_typed_routing_hook.py's own module docstring for why: there is no
# subagent-dispatch tool on the Codex line to key on).
SHARED_TREES = (
    ("universal (canon)", UNIVERSAL_HOOKS),
    ("claude mirror", CLAUDE_HOOKS),
    ("codex mirror", CODEX_HOOKS),
)
CLAUDE_ONLY_TREES = (
    ("claude (pack-only, no mirror)", CLAUDE_HOOKS),
)


def _run_with_unimportable_hook_common(hook_path: Path, envelope: dict) -> subprocess.CompletedProcess:
    """Copy `hook_path` into a fresh `<tmp>/hooks/` dir alongside an empty
    `<tmp>/scripts/` dir (no `hook_common.py` present), then run it as a
    subprocess fed a real hit-shaped envelope. Every one of these six hooks'
    own `sys.path.insert(0, ..parent/"scripts")` line resolves to that empty
    directory, so `import hook_common` fails exactly as it would on a
    partial/corrupted install that is missing the shared helper file."""
    workdir = Path(tempfile.mkdtemp())
    hooks_dir = workdir / "hooks"
    scripts_dir = workdir / "scripts"
    hooks_dir.mkdir()
    scripts_dir.mkdir()  # deliberately empty: no hook_common.py anywhere in it
    isolated_hook = hooks_dir / hook_path.name
    shutil.copy2(hook_path, isolated_hook)
    return subprocess.run(
        [sys.executable, str(isolated_hook)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _repo_orientation_envelope() -> dict:
    """A git-root repo + transcript with no REPOSITORY ORIENTATION: record,
    matching `_repo_orientation_fixture` in test_audit_hook_payload_shape.py
    so the hit path is real (not a miss that would pass this test for the
    wrong reason)."""
    repo = Path(tempfile.mkdtemp())
    (repo / ".git").mkdir()
    (repo / "src").mkdir()
    entries = [
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Update it."}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Editing."}]}},
    ]
    transcript = repo / "transcript.jsonl"
    transcript.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return {
        "cwd": str(repo),
        "transcript_path": str(transcript),
        "tool_name": "Edit",
        "tool_input": {"file_path": str(repo / "src" / "app.py")},
    }


# One row per audit: (script filename, trees it lives in, a real hit-shaped
# envelope). Envelope shapes mirror test_audit_hook_payload_shape.py's own
# per-audit builders exactly (same file/pattern/command choices) so a
# regression there and a regression here are testing the identical hit path.
AUDITS = (
    ("check-machine-local-path.py", SHARED_TREES,
     {"tool_input": {"file_path": "README.md", "content": "see C:/Users/realuser/x"}}),
    ("check-no-trash-in-repo.py", SHARED_TREES,
     {"cwd": "/tmp", "tool_input": {"command": "git worktree add ../wt"}}),
    ("check-stale-relation-residue.py", SHARED_TREES,
     {"tool_input": {"file_path": "docs/live-doc.md", "content": "this is a deprecated alias for bar"}}),
    ("check-repository-orientation.py", SHARED_TREES, _repo_orientation_envelope),
    ("check-mcp-momentum.py", SHARED_TREES,
     {"tool_name": "Grep", "tool_input": {"pattern": "def parse_config"}}),
    ("check-typed-routing.py", CLAUDE_ONLY_TREES,
     {
         "tool_name": "Agent",
         "tool_input": {
             "subagent_type": "general-purpose",
             "description": "",
             "prompt": "implement the fix",
         },
     }),
)


class AllAuditsHookCommonUnimportableTests(unittest.TestCase):
    def test_unimportable_hook_common_is_detectable_not_a_silent_pass(self) -> None:
        """Pins the chosen contract for all six audits: a missing
        `hook_common` must be visibly different from a clean run (nonzero
        exit, non-empty stderr naming the module), and must NOT emit a
        fabricated advisory on stdout -- but must also not exit 2, which
        would violate AUDIT mode's own "never blocks" contract."""
        for script_name, trees, envelope_or_factory in AUDITS:
            envelope = envelope_or_factory() if callable(envelope_or_factory) else envelope_or_factory
            for tree_label, tree_dir in trees:
                hook_path = tree_dir / script_name
                with self.subTest(hook=f"{script_name} [{tree_label}]"):
                    result = _run_with_unimportable_hook_common(hook_path, envelope)
                    self.assertNotEqual(
                        result.returncode, 0,
                        "a missing hook_common must not exit 0 silently -- that is "
                        "the exact defect class this test guards against",
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
