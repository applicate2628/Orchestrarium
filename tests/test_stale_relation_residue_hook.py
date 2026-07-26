"""Regression tests for the stale-relation-residue PreToolUse hook (AUDIT mode).

The hook is the structural backstop for architecture law C6 ("a superseding change
leaves only the correct current state"): it warns when an Edit/Write ADDS a
stale-relation residue phrase (deprecated alias / former name / "(was X)" /
misregistered as / arrow+alias / "is wrong ... correct is") into a LIVE-tree file,
and ALWAYS exits 0 (audit mode never blocks; fail-open on any internal error). On
a hit it emits one line of JSON to stdout --
`{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"..."}}`
-- the model-visible delivery channel (see `hook_common.emit_advisory`); silent
otherwise. This replaced a stderr-plus-exit-1 form measured to reach nobody on
either provider line (see
work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
sibling-calls-broken.md).

Tests drive the Python brain via subprocess for BOTH the Claude and Codex copies
(mirroring test_machine_local_path_hook.py / test_no_trash_hook.py) and assert:
  - each documented residue phrase is flagged when written to a live-tree file;
  - near-miss phrases the hook deliberately excludes (bare "old name",
    "is wrong, use X" without "correct is") are NOT flagged;
  - every documented exempt target class (work-items/, changelog/release-notes/
    history stems, /archive/, /legacy/, .scratch/, .git/) is NOT flagged, while a
    live file whose name merely CONTAINS an exempt stem (history_parser.py) IS;
  - the ADDS-only guarantee via its actual mechanisms: diff payloads are scanned
    on "+" lines only (a removed or context/preserved phrase never warns) and an
    Edit's old_string is never scanned;
  - exit code is 0 in every case, and a malformed envelope fails open silently.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CL = REPO_ROOT / "src.claude" / "agents" / "hooks"
CX = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks"

RESIDUE_SCRIPTS = (CL / "check-stale-relation-residue.py", CX / "check-stale-relation-residue.py")


def run_hook(script: Path, envelope: object, raw_stdin: str | None = None) -> subprocess.CompletedProcess:
    stdin_text = raw_stdin if raw_stdin is not None else json.dumps(envelope, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, str(script)],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _decode_context(stdout: str) -> tuple[str, str]:
    """Parse the hookSpecificOutput envelope; returns (hookEventName, additionalContext)."""
    payload = json.loads(stdout)
    specific = payload["hookSpecificOutput"]
    return specific["hookEventName"], specific["additionalContext"]


class StaleRelationResidueHookBase(unittest.TestCase):
    def assert_flagged(self, tool_input: dict, flagged: bool) -> None:
        for script in RESIDUE_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, {"tool_input": tool_input})
                # AUDIT never BLOCKS (never exit 2) and never uses a non-zero exit
                # for a hit either -- the advisory travels via stdout JSON, always
                # exit 0 (see hook_common.emit_advisory).
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stderr, "")
                self.assertEqual(bool(p.stdout.strip()), flagged, f"stdout={p.stdout!r}")
                if flagged:
                    event_name, _context = _decode_context(p.stdout)
                    self.assertEqual(event_name, "PreToolUse")

    def assert_content_flagged(self, content: str, flagged: bool, target: str = "docs/live-doc.md") -> None:
        self.assert_flagged({"file_path": target, "content": content}, flagged)


class TestResiduePhraseMatrix(StaleRelationResidueHookBase):
    """One test per documented residue-phrase family (the hook's _PATTERNS vocabulary)."""

    def test_deprecated_alias_flagged(self) -> None:
        self.assert_content_flagged("`foo_helper` is a deprecated alias for `bar_helper`.", True)

    def test_former_name_flagged(self) -> None:
        self.assert_content_flagged("its former name was FooBarManager", True)

    def test_former_alias_flagged(self) -> None:
        self.assert_content_flagged("keep the former alias in mind", True)

    def test_former_internal_name_flagged(self) -> None:
        self.assert_content_flagged("the former internal name leaked into the API", True)

    def test_old_alias_flagged(self) -> None:
        self.assert_content_flagged("the old alias still resolves", True)

    def test_now_retired_kept_example_flagged(self) -> None:
        self.assert_content_flagged("the now-retired helper is kept as a historical example", True)

    def test_kept_as_historical_example_flagged(self) -> None:
        self.assert_content_flagged("kept here only as a historical example of the pattern", True)

    def test_misregistered_as_flagged(self) -> None:
        self.assert_content_flagged("this hook was misregistered as a Stop hook", True)

    def test_misregistered_as_hyphenated_flagged(self) -> None:
        self.assert_content_flagged("the used-to-be-misregistered-as-Stop entry", True)

    def test_parenthetical_was_flagged(self) -> None:
        self.assert_content_flagged("check_stray_artifact (was check_no_trash) guards the tree", True)

    def test_parenthetical_formerly_flagged(self) -> None:
        self.assert_content_flagged("the audit hook (formerly the trash guard) warns only", True)

    def test_parenthetical_previously_flagged(self) -> None:
        self.assert_content_flagged("the scanner (previously the leak filter) runs first", True)

    def test_parenthetical_renamed_from_flagged(self) -> None:
        self.assert_content_flagged("the gate (renamed from check-gate) is blocking", True)

    def test_arrow_alias_flagged(self) -> None:
        self.assert_content_flagged("keep the check-x -> check-y alias for one release", True)

    def test_unicode_arrow_alias_flagged_and_utf8_survives(self) -> None:
        # The snippet must round-trip correctly regardless of console codepage:
        # the JSON envelope uses ensure_ascii=True, so the arrow / Cyrillic text
        # is \uXXXX-escaped on the wire and json.loads decodes it back exactly.
        for script in RESIDUE_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(
                    script,
                    {"tool_input": {"file_path": "docs/live-doc.md", "content": "старое → новое alias останется"}},
                )
                self.assertEqual(p.returncode, 0, p.stderr)  # AUDIT never exits non-zero
                self.assertEqual(p.stderr, "")
                self.assertTrue(p.stdout.strip(), "expected an advisory")
                _event_name, context = _decode_context(p.stdout)
                self.assertIn("новое", context)

    def test_is_wrong_correct_is_flagged(self) -> None:
        self.assert_content_flagged("this name is wrong, the correct is check_stray_artifact", True)

    # --- deliberate near-miss exclusions (documented in the hook's comments) ----

    def test_bare_old_name_not_flagged(self) -> None:
        # "old name" alone is common live prose ("ask for the old name and the new name").
        self.assert_content_flagged("ask for the old name and the new name", False)

    def test_is_wrong_use_without_correct_is_not_flagged(self) -> None:
        # bare "... is wrong, use X" is common live instruction prose.
        self.assert_content_flagged("this value is wrong, use the config default instead", False)

    def test_clean_content_not_flagged(self) -> None:
        self.assert_content_flagged("a live dependency: module A calls module B via the seam", False)


class TestExemptTargets(StaleRelationResidueHookBase):
    """A stale-relation phrase IS legitimate provenance in these targets."""

    RESIDUE = "the `foo` field is a deprecated alias for `bar`"

    def test_work_items_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target="work-items/decisions/2026-07-11-rename.md")

    def test_work_items_backslash_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target="work-items\\decisions\\2026-07-11-rename.md")

    def test_release_notes_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target="RELEASE_NOTES.md")

    def test_changelog_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target="CHANGELOG.md")

    def test_history_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target="docs/HISTORY.md")

    def test_archive_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target="docs/archive/old-design.md")

    def test_legacy_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target="src/legacy/old_module.py")

    def test_underscore_archive_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target="docs/_archive/old-notes.md")

    def test_scratch_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target=".scratch/raw-notes.md")

    def test_git_target_exempt(self) -> None:
        self.assert_content_flagged(self.RESIDUE, False, target=".git/COMMIT_EDITMSG")

    # --- exemptions are segment/stem-bounded, not substring-bounded -------------

    def test_history_parser_stem_not_exempt(self) -> None:
        # `history_parser.py` (stem history_parser, not history) is a LIVE file.
        self.assert_content_flagged(self.RESIDUE, True, target="src/history_parser.py")

    def test_myarchive_segment_not_exempt(self) -> None:
        # /archive/ is slash-bounded: `myarchive/` is a LIVE directory.
        self.assert_content_flagged(self.RESIDUE, True, target="myarchive/notes.md")


class TestAddedOnlyDetection(StaleRelationResidueHookBase):
    """The guard fires on residue being ADDED, never on residue removed/preserved."""

    def test_diff_added_line_flagged(self) -> None:
        patch = (
            "@@ -1,1 +1,2 @@\n"
            " a clean context line\n"
            "+the old field is a deprecated alias for the new one\n"
        )
        self.assert_flagged({"file_path": "docs/live-doc.md", "content": patch}, True)

    def test_diff_removed_line_not_flagged(self) -> None:
        # Erasing residue is exactly what C6 wants — the guard must not warn on it.
        patch = (
            "diff --git a/docs/live-doc.md b/docs/live-doc.md\n"
            "--- a/docs/live-doc.md\n"
            "+++ b/docs/live-doc.md\n"
            "@@ -1,2 +1,1 @@\n"
            "-the old field is a deprecated alias for the new one\n"
            " a clean context line\n"
        )
        self.assert_flagged({"file_path": "docs/live-doc.md", "content": patch}, False)

    def test_diff_preserved_context_line_not_flagged(self) -> None:
        # An edit that only PRESERVES an existing residue phrase (context line)
        # while adding clean content must not warn.
        patch = (
            "@@ -1,1 +1,2 @@\n"
            " the old field is a deprecated alias for the new one\n"
            "+a clean added line\n"
        )
        self.assert_flagged({"file_path": "docs/live-doc.md", "content": patch}, False)

    def test_apply_patch_added_line_flagged(self) -> None:
        patch = "*** Update File: docs/live-doc.md\n+the helper was misregistered as a Stop hook\n"
        self.assert_flagged({"input": patch}, True)

    def test_apply_patch_removed_line_not_flagged(self) -> None:
        patch = "*** Update File: docs/live-doc.md\n-the helper was misregistered as a Stop hook\n"
        self.assert_flagged({"input": patch}, False)

    def test_edit_old_string_not_scanned(self) -> None:
        # An Edit REMOVING residue: the phrase lives only in old_string -> no warn.
        self.assert_flagged(
            {
                "file_path": "docs/live-doc.md",
                "old_string": "the `foo` field is a deprecated alias for `bar`",
                "new_string": "the `bar` field is the canonical name",
            },
            False,
        )

    def test_edit_new_string_scanned(self) -> None:
        # An Edit ADDING residue in new_string -> warn.
        self.assert_flagged(
            {
                "file_path": "docs/live-doc.md",
                "old_string": "the `bar` field is the canonical name",
                "new_string": "the `foo` field is a deprecated alias for `bar`",
            },
            True,
        )

    def test_write_leading_dash_bullet_is_scanned(self) -> None:
        # Non-diff Write content starting with "- " is a markdown bullet, not a
        # removal — it must still be scanned.
        self.assert_content_flagged("- the `foo` field is a deprecated alias for `bar`", True)


class TestFailOpen(StaleRelationResidueHookBase):
    def test_malformed_stdin_fails_open(self) -> None:
        for script in RESIDUE_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, None, raw_stdin="not json at all {{{")
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")
                self.assertEqual(p.stdout.strip(), "")

    def test_envelope_without_tool_input_allows_silently(self) -> None:
        for script in RESIDUE_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, {"session_id": "x", "tool_name": "Write"})
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")
                self.assertEqual(p.stdout.strip(), "")

    def test_non_dict_tool_input_allows_silently(self) -> None:
        for script in RESIDUE_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, {"tool_input": "a bare string, is a deprecated alias for nothing"})
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")
                self.assertEqual(p.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
