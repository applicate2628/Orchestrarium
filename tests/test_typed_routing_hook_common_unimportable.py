"""Regression test for the check-typed-routing import contract when the
shared `hook_common` helper is unimportable.

SIBLING TO `test_mcp_momentum_hook_common_unimportable.py` -- read that file's
docstring for the full defect background
(work-items/bugs/2026-07-26-the-mcp-momentum-audit-stubs-its-own-delivery-to-
a-no-op.md). This file exists separately because `check-typed-routing.py` is
NOT one of the five universal audits that filed bug covered: it is a
Claude-only hook with no canon copy under `scripts/universal-hooks/hooks/`
(see `PACK_ONLY_HOOKS["src.claude/agents/hooks"]` in
`scripts/universal_hooks_manifest.py`) and no Codex mirror (Codex CLI exposes
no analogous subagent-dispatch tool to key on). `scripts/sync-universal-
hooks.py` therefore NEVER propagates a fix to this file -- it is the one copy
outside the mirror mechanism entirely, which is exactly why it carried the
identical defect that the filed bug's own grep missed.

THE DEFECT, CONFIRMED BY READING THE FILE (not assumed from the sibling bug):
on `main`, `check-typed-routing.py`'s `try/except` around the `hook_common`
import stubbed only `read_stdin_utf8`/`parse_envelope` -- it did not yet use
`emit_advisory`. The delivery-channel fix that added `emit_advisory` (moving
this hook off the dead stderr-plus-exit-1 channel, same as its sibling
audits) widened the SAME stub to also cover `emit_advisory`, reintroducing
the silent-death shape: a missing `hook_common` makes `read_stdin_utf8()`
return `""`, `parse_envelope("")` return `{}`, so `envelope.get("tool_name")`
is never `"Agent"` (`DISPATCH_TOOL`) and `main()` returns 0 before the
`emit_advisory` stub could ever be reached -- an exit-0/empty-stdout/empty-
stderr run indistinguishable from "nothing to warn about".

THE CHOSEN CONTRACT (matches every universal audit, including the fixed
`check-mcp-momentum.py`): import `hook_common` directly, no fallback. A
broken install now surfaces as an uncaught `ImportError` -- nonzero exit,
traceback on stderr -- instead of silent success, while still honoring this
hook's own AUDIT-mode "never block" contract (only exit 2 blocks a
PreToolUse tool call; an uncaught exception's default exit 1 does not).
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

# Claude-only, no canon, no Codex mirror -- see module docstring.
HOOK = REPO_ROOT / "src.claude" / "agents" / "hooks" / "check-typed-routing.py"


def _run_with_unimportable_hook_common(hook_path: Path) -> subprocess.CompletedProcess:
    """Copy `hook_path` into a fresh `<tmp>/hooks/` dir alongside an empty
    `<tmp>/scripts/` dir (no `hook_common.py` present), then run it as a
    subprocess fed a real dispatch-hit envelope. The hook's own
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

    # A real hit-shaped envelope (matches _typed_routing_envelope in
    # test_audit_hook_payload_shape.py): general-purpose dispatch carrying a
    # specialist-work signal ("implement"). If the old widened stub were
    # still present, this is exactly the input that would have produced a
    # clean, silent exit 0 instead of a detectable failure.
    envelope = {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "general-purpose",
            "description": "",
            "prompt": "implement the fix",
        },
    }
    return subprocess.run(
        [sys.executable, str(isolated_hook)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class TypedRoutingHookCommonUnimportableTests(unittest.TestCase):
    def test_unimportable_hook_common_is_detectable_not_a_silent_pass(self) -> None:
        """Pins the chosen contract: a missing `hook_common` must be visibly
        different from a clean run (nonzero exit, non-empty stderr), and must
        NOT emit a fabricated advisory on stdout -- but must also not exit 2,
        which would violate this hook's own "AUDIT mode never blocks"
        contract."""
        result = _run_with_unimportable_hook_common(HOOK)
        self.assertNotEqual(
            result.returncode, 0,
            "a missing hook_common must not exit 0 silently -- that is "
            "the exact defect this test guards against",
        )
        self.assertNotEqual(
            result.returncode, 2,
            "must not BLOCK the tool call -- AUDIT mode never denies "
            "(only exit 2 blocks a PreToolUse tool call on Claude Code)",
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
