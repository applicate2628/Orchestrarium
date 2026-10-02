"""Every retained warn-only audit must expose an unimportable hook_common.

The fixture copies each real hook and its immutable preflight dependency into
an isolated directory while deliberately omitting hook_common. Real hit-shaped
inputs must produce a visible nonzero import failure naming hook_common, empty
stdout, and never the exit-2 decision that would block a host tool call.
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

# The four audits mirrored across all three trees, plus the Claude-only fifth
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
    """Copy `hook_path` into a fresh `<tmp>/hooks/` dir alongside a dependency-only
    `<tmp>/scripts/` dir (no `hook_common.py` present), then run it as a
    subprocess fed a real hit-shaped envelope. Each retained hook's
    own `sys.path.insert(0, ..parent/"scripts")` line resolves to that isolated
    directory, so `import hook_common` fails exactly as it would on a
    partial/corrupted install that is missing the shared helper file."""
    workdir = Path(tempfile.mkdtemp())
    hooks_dir = workdir / "hooks"
    scripts_dir = workdir / "scripts"
    hooks_dir.mkdir()
    scripts_dir.mkdir()  # no hook_common.py anywhere in the isolated fixture
    shutil.copyfile(
        hook_path.parent.parent / "scripts" / "git_push_gate_preflight.py",
        scripts_dir / "git_push_gate_preflight.py",
    )
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
     {"tool_input": {"file_path": "README.md", "content": "see C:/" + "Users" + "/realuser/x"}}),
    ("check-no-trash-in-repo.py", SHARED_TREES,
     {"cwd": "/tmp", "tool_input": {"command": "git worktree add ../wt"}}),
    ("check-stale-relation-residue.py", SHARED_TREES,
     {"tool_input": {"file_path": "docs/live-doc.md", "content": "this is a deprecated alias for bar"}}),
    ("check-repository-orientation.py", SHARED_TREES, _repo_orientation_envelope),
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
        """Pins the chosen contract for every remaining audit: a missing
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
