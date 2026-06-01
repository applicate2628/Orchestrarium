"""Fail-closed branch coverage for scripts/validate-agents-spine.py.

The existing tests/test_agents_spine_validator.py proves the HAPPY path (the real
spine passes) plus ONE failure branch (an absurd `--size-cap` trips the size
check). The validator has THREE other independent fail-closed branches that were
unexercised — a regression that disabled any of them would have shipped green:

  (1) missing-manifest-token   (validate(): the per-group "FAIL: missing N/M"
                                loop, validate-agents-spine.py:206-216)
  (2) dead reference pointer    (the shared/references/...md pointer-resolution
                                check, validate-agents-spine.py:220-229)
  (3) orphaned discipline card  (the extract bold-name -> spine-card parity
                                check, validate-agents-spine.py:235-249)

These tests drive each branch with SYNTHETIC FAILING INPUT and assert the
validator FAILS CLOSED (ok is False / CLI exit is non-zero) with the matching
diagnostic. They do NOT weaken the validator — every mutation is applied to a
THROWAWAY COPY of the real spine subtree in a tempdir; the real
shared/AGENTS.shared.md is never touched.

Harness design (why copy-and-mutate rather than hand-author a spine):
  - validate() reads the spine from disk AND resolves pointers relative to
    `spine_path.resolve().parent.parent` AND reads the discipline extract at
    `spine_path.parent / references / spine / verification-and-decision-discipline.md`.
    A valid synthetic spine would therefore have to reproduce the entire ~40k-char
    governance file plus the whole shared/references/ tree. Instead we copy the
    REAL shared/ subtree into a tempdir (so the baseline copy PASSES, proving the
    harness is faithful) and then mutate exactly ONE thing per test.
  - Every mutated token / pointer / card name is DISCOVERED AT RUNTIME from the
    validator's own manifest or from the real spine/extract content, never
    hardcoded. So a future legitimate manifest reword does not rot these tests —
    they always mutate something that is currently present and currently checked.

Gate safety (this file is itself scanned by the publication gate): the source
contains NO machine-local-path literal. The only absolute path used is the real
repo root, which is derived at runtime from this file's own location via
`Path(__file__).resolve()`, not written as a literal.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate-agents-spine.py"
REAL_SHARED = REPO_ROOT / "shared"
EXTRACT_REL = Path("references") / "spine" / "verification-and-decision-discipline.md"


def _load_validator() -> ModuleType:
    """Import validate-agents-spine.py as a module (its filename has hyphens, so a
    normal import statement cannot reach it)."""
    spec = importlib.util.spec_from_file_location("_vspine", str(VALIDATOR))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _copy_spine_tree(dst_root: Path) -> Path:
    """Copy the real shared/ subtree under dst_root and return the spine path.

    The copy passes the validator (it is a byte copy of the real, passing spine
    plus its real references), so any later FAIL is provably caused by the single
    mutation a test then applies — not by a faithfulness gap in the harness."""
    shutil.copytree(REAL_SHARED, dst_root / "shared")
    return dst_root / "shared" / "AGENTS.shared.md"


def _run_cli(spine: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--spine", str(spine)],
        capture_output=True, text=True, encoding="utf-8",
    )


class TestSpineValidatorHarness(unittest.TestCase):
    """Sanity baseline: an unmutated COPY of the real spine subtree must PASS,
    both via the imported validate() and via the real --spine CLI. If this fails,
    the copy-and-mutate harness is unfaithful and the fail-branch assertions below
    would be meaningless."""

    def test_unmutated_copy_passes_via_import(self) -> None:
        mod = _load_validator()
        with tempfile.TemporaryDirectory() as td:
            spine = _copy_spine_tree(Path(td))
            ok, messages = mod.validate(spine)
            self.assertTrue(ok, f"baseline copy must PASS; messages:\n" + "\n".join(messages))

    def test_unmutated_copy_passes_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            spine = _copy_spine_tree(Path(td))
            p = _run_cli(spine)
            self.assertEqual(p.returncode, 0, f"baseline copy CLI must exit 0:\n{p.stdout}\n{p.stderr}")
            self.assertIn("RESULT: PASS", p.stdout, p.stdout)


class TestMissingManifestTokenFailsClosed(unittest.TestCase):
    """Branch (1): if an enforceable protection token (banned-phrase, gate name,
    probe, status label, ...) is silently dropped from the spine, the validator
    must FAIL CLOSED. We delete a real, currently-present manifest token from a
    throwaway copy and assert the missing-token diagnostic fires."""

    def _pick_token(self, mod: ModuleType) -> str:
        # Take the first banned-reasoning phrase from the validator's OWN manifest
        # so the test cannot drift out of sync with the pinned vocabulary.
        tok = mod.BANNED_REASONING_PHRASES[0]
        return tok

    def test_removed_token_fails_via_import(self) -> None:
        mod = _load_validator()
        tok = self._pick_token(mod)
        with tempfile.TemporaryDirectory() as td:
            spine = _copy_spine_tree(Path(td))
            text = spine.read_text(encoding="utf-8")
            self.assertIn(tok, text, "precondition: token present in real spine")
            spine.write_text(text.replace(tok, "XX-TOKEN-DELETED-XX"), encoding="utf-8")
            ok, messages = mod.validate(spine)
            self.assertFalse(ok, "deleting a manifest token must FAIL the validator")
            joined = "\n".join(messages)
            self.assertIn("FAIL: missing", joined, joined)
            self.assertIn("banned reasoning phrases", joined, joined)

    def test_removed_token_fails_via_cli(self) -> None:
        mod = _load_validator()
        tok = self._pick_token(mod)
        with tempfile.TemporaryDirectory() as td:
            spine = _copy_spine_tree(Path(td))
            text = spine.read_text(encoding="utf-8")
            spine.write_text(text.replace(tok, "XX-TOKEN-DELETED-XX"), encoding="utf-8")
            p = _run_cli(spine)
            self.assertEqual(p.returncode, 1, f"expected non-zero exit:\n{p.stdout}")
            self.assertIn("RESULT: FAIL", p.stdout, p.stdout)
            self.assertIn("FAIL: missing", p.stdout, p.stdout)
            # guard: the failure is the MUTATION, not an accidental file-not-found
            self.assertNotIn("not found", p.stdout, p.stdout)

    def test_multiple_removed_tokens_all_reported(self) -> None:
        # Removing tokens from two different groups must report BOTH groups, not
        # short-circuit on the first — proves the loop checks every group.
        mod = _load_validator()
        t_reason = mod.BANNED_REASONING_PHRASES[0]
        t_gate = mod.GATE_AND_DISCIPLINE_NAMES[0]
        with tempfile.TemporaryDirectory() as td:
            spine = _copy_spine_tree(Path(td))
            text = spine.read_text(encoding="utf-8")
            self.assertIn(t_reason, text)
            self.assertIn(t_gate, text)
            text = text.replace(t_reason, "XX1").replace(t_gate, "XX2")
            spine.write_text(text, encoding="utf-8")
            ok, messages = mod.validate(spine)
            self.assertFalse(ok)
            joined = "\n".join(messages)
            self.assertIn("banned reasoning phrases", joined, joined)
            self.assertIn("gate / discipline names", joined, joined)


class TestDeadReferencePointerFailsClosed(unittest.TestCase):
    """Branch (2): if the spine names a shared/references/...md pointer that no
    longer resolves to a file (a moved/renamed/deleted extract), the validator
    must FAIL CLOSED. We delete the pointed-to file from a throwaway copy while
    leaving the pointer text in the spine."""

    def _first_pointer(self, spine: Path) -> str:
        text = spine.read_text(encoding="utf-8")
        pointers = sorted(set(re.findall(r"shared/references/[A-Za-z0-9_./-]+\.md", text)))
        self.assertTrue(pointers, "precondition: spine names at least one reference pointer")
        return pointers[0]

    def test_dead_pointer_fails_via_import(self) -> None:
        mod = _load_validator()
        with tempfile.TemporaryDirectory() as td:
            spine = _copy_spine_tree(Path(td))
            pointer = self._first_pointer(spine)
            repo_root = spine.resolve().parent.parent  # matches validate()'s own resolution
            victim = repo_root / pointer
            self.assertTrue(victim.is_file(), f"precondition: {pointer} exists in the copy")
            victim.unlink()
            ok, messages = mod.validate(spine)
            self.assertFalse(ok, "a dead reference pointer must FAIL the validator")
            joined = "\n".join(messages)
            self.assertIn("resolve to no file", joined, joined)
            self.assertIn(pointer, joined, joined)

    def test_dead_pointer_fails_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            spine = _copy_spine_tree(Path(td))
            pointer = self._first_pointer(spine)
            victim = spine.resolve().parent.parent / pointer
            victim.unlink()
            p = _run_cli(spine)
            self.assertEqual(p.returncode, 1, f"expected non-zero exit:\n{p.stdout}")
            self.assertIn("RESULT: FAIL", p.stdout, p.stdout)
            self.assertIn("resolve to no file", p.stdout, p.stdout)


class TestOrphanedDisciplineCardFailsClosed(unittest.TestCase):
    """Branch (3): every bold rule-lead in the verification extract must still
    have its bold card in the spine (so an edit cannot drop a rule from the
    always-loaded spine while leaving it in the on-demand extract). We remove a
    real card's bold marker from a throwaway copy and assert the parity check
    fires."""

    def _pick_card(self, mod: ModuleType, spine: Path) -> str:
        extract = spine.parent / EXTRACT_REL
        self.assertTrue(extract.is_file(), f"precondition: extract present at {extract}")
        names = re.findall(r"(?m)^- \*\*([^*]+?):\*\*", extract.read_text(encoding="utf-8"))
        # Skip any card deliberately folded into another spine card.
        merged = getattr(mod, "MERGED_INTO_SPINE", set())
        candidate = next((n for n in names if n not in merged), None)
        self.assertIsNotNone(candidate, "precondition: extract has a non-merged bold card")
        return candidate  # type: ignore[return-value]

    def test_orphaned_card_fails_via_import(self) -> None:
        mod = _load_validator()
        with tempfile.TemporaryDirectory() as td:
            spine = _copy_spine_tree(Path(td))
            card = self._pick_card(mod, spine)
            text = spine.read_text(encoding="utf-8")
            self.assertIn(f"**{card}", text, f"precondition: spine has the '{card}' card")
            # Break only the bold marker so the spine card no longer exists, while
            # the extract still leads the rule -> orphan.
            spine.write_text(text.replace(f"**{card}", f"CARD-GONE_{card}"), encoding="utf-8")
            ok, messages = mod.validate(spine)
            self.assertFalse(ok, "an orphaned discipline card must FAIL the validator")
            joined = "\n".join(messages)
            self.assertIn("no spine card", joined, joined)
            self.assertIn(card, joined, joined)

    def test_orphaned_card_fails_via_cli(self) -> None:
        mod = _load_validator()
        with tempfile.TemporaryDirectory() as td:
            spine = _copy_spine_tree(Path(td))
            card = self._pick_card(mod, spine)
            text = spine.read_text(encoding="utf-8")
            spine.write_text(text.replace(f"**{card}", f"CARD-GONE_{card}"), encoding="utf-8")
            p = _run_cli(spine)
            self.assertEqual(p.returncode, 1, f"expected non-zero exit:\n{p.stdout}")
            self.assertIn("RESULT: FAIL", p.stdout, p.stdout)
            self.assertIn("no spine card", p.stdout, p.stdout)


class TestMissingSpineFileFailsClosed(unittest.TestCase):
    """validate() also fails closed when the spine path does not exist at all
    (the `is_file()` guard, validate-agents-spine.py:191-192). Cheap to lock in."""

    def test_nonexistent_spine_fails(self) -> None:
        mod = _load_validator()
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "does-not-exist" / "AGENTS.shared.md"
            ok, messages = mod.validate(missing)
            self.assertFalse(ok)
            self.assertTrue(any("not found" in m for m in messages), messages)


if __name__ == "__main__":
    unittest.main()
