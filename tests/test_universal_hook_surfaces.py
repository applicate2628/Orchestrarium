from __future__ import annotations

import filecmp
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# The pack-neutral canon dir IS the single owner of "which universal hooks exist"
# — derive the name lists by GLOB, never a hardcoded tuple. A hardcoded list is
# exactly what hid check-stale-relation-residue from this gate (it shipped in the
# packs but was never added to the canon or the tuple), so the list must come
# from the canon dir itself and a set-equality check must flag a pack hook that
# has no canon counterpart.
#
# The canon-name derivation AND the declared pack-only exceptions below live in
# scripts/universal_hooks_manifest.py — a small, dependency-free module (no
# dataclasses, no subprocess, no argparse) shared by this test AND the CLI
# propagation tool (scripts/sync-universal-hooks.py), so neither can drift from
# the other about what the complete file set even is (the two-owners-drift
# shape this test exists to catch elsewhere — see work-items/bugs/2026-07-26-
# mirror-parity-is-detected-but-never-propagated.md).
#
# Deliberately NOT importing scripts/sync-universal-hooks.py itself here: an
# earlier version of this file did, and a `dataclasses` + Python-3.14
# interaction inside that CLI tool's own `DriftEntry` (fixed by moving it to
# this manifest as a `NamedTuple`) took THIS FILE'S ENTIRE COLLECTION down with
# it — every test below, including ones with nothing to do with the sync tool,
# stopped running, and another lane had to `--ignore` this file to get a clean
# suite run. Importing only the tiny manifest module here means a future bug in
# the CLI tool's argparse/subprocess/git-integration code can no longer do that;
# see test_sync_tool_cli_module_is_importable below for how the CLI tool's own
# importability is still checked, but as one attributable test, not a
# collection-time crash for this whole file.
#
# Load it the way tests/test_cleanup_engine.py and tests/test_work_item_state_
# validator.py already load scripts/ modules by file path via importlib
# (registering in sys.modules BEFORE exec_module — dataclasses-era modules in
# this repo need that; this module has no dataclass but the pattern is kept for
# consistency and because NamedTuple costs nothing extra from it).
_MANIFEST_PATH = ROOT / "scripts" / "universal_hooks_manifest.py"
_manifest_spec = importlib.util.spec_from_file_location("universal_hooks_manifest", _MANIFEST_PATH)
assert _manifest_spec is not None and _manifest_spec.loader is not None
universal_hooks_manifest = importlib.util.module_from_spec(_manifest_spec)
sys.modules[_manifest_spec.name] = universal_hooks_manifest
_manifest_spec.loader.exec_module(universal_hooks_manifest)

RUNTIME_SCRIPT_NAMES = universal_hooks_manifest.canon_names(ROOT, "scripts")
RUNTIME_HOOK_NAMES = universal_hooks_manifest.canon_names(ROOT, "hooks")
PACK_ONLY_SCRIPTS = universal_hooks_manifest.PACK_ONLY_SCRIPTS
PACK_ONLY_HOOKS = universal_hooks_manifest.PACK_ONLY_HOOKS
DEPRECATED_EXAMPLE_COMPATIBILITY_LAUNCHERS = {"mcp-usage-reminder.sh"}


class UniversalHookSurfaceTest(unittest.TestCase):
    def test_mcp_policy_is_mirrored_support_and_never_a_registered_stem(self) -> None:
        relative = Path("scripts/mcp_continuity_policy.py")
        paths = (
            ROOT / "scripts" / "universal-hooks" / relative,
            ROOT / "src.claude" / "agents" / relative,
            ROOT / "src.codex" / "skills" / "lead" / relative,
        )
        for path in paths:
            self.assertTrue(path.is_file(), f"missing MCP policy support module: {path}")
            self.assertFalse(path.with_suffix(".sh").exists())
            self.assertFalse(path.with_suffix(".ps1").exists())
        self.assertTrue(filecmp.cmp(paths[0], paths[1], shallow=False))
        self.assertTrue(filecmp.cmp(paths[0], paths[2], shallow=False))

        checker_path = ROOT / "scripts" / "check-hook-health.py"
        spec = importlib.util.spec_from_file_location(
            "check_hook_health_support_module_test", checker_path
        )
        assert spec is not None and spec.loader is not None
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        for platform in ("claude", "codex"):
            self.assertNotIn(
                "mcp_continuity_policy", checker._manifest_stems(ROOT, platform)
            )

    def test_pack_neutral_hook_sources_exist_and_match_production_packs(self) -> None:
        universal_scripts = ROOT / "scripts" / "universal-hooks" / "scripts"
        universal_hooks = ROOT / "scripts" / "universal-hooks" / "hooks"
        provider_pairs = (
            (ROOT / "src.codex" / "skills" / "lead" / "scripts", RUNTIME_SCRIPT_NAMES),
            (ROOT / "src.claude" / "agents" / "scripts", RUNTIME_SCRIPT_NAMES),
            (ROOT / "src.codex" / "skills" / "lead" / "hooks", RUNTIME_HOOK_NAMES),
            (ROOT / "src.claude" / "agents" / "hooks", RUNTIME_HOOK_NAMES),
        )

        for name in RUNTIME_SCRIPT_NAMES:
            universal_path = universal_scripts / name
            self.assertTrue(universal_path.is_file(), f"missing universal script {name}")
        for name in RUNTIME_HOOK_NAMES:
            universal_path = universal_hooks / name
            self.assertTrue(universal_path.is_file(), f"missing universal hook {name}")

        for provider_dir, names in provider_pairs:
            universal_dir = universal_scripts if provider_dir.name == "scripts" else universal_hooks
            for name in names:
                self.assertTrue(
                    filecmp.cmp(universal_dir / name, provider_dir / name, shallow=False),
                    f"{provider_dir / name} drifted from universal hook source",
                )

    def test_pack_hooks_dir_has_no_hook_missing_from_canon(self) -> None:
        """Set-equality for hooks/: pack == canon ∪ declared `PACK_ONLY_HOOKS`.
        Every audit-hook family in a pack's hooks/ dir must be either a canon
        (universal) counterpart or a DECLARED provider-specific exception; an
        undeclared pack-only hook still FAILS. This is the check that would have
        caught check-stale-relation-residue being absent from the canon, now with
        the same declared-exception seam scripts/ uses (`PACK_ONLY_SCRIPTS`) so a
        genuinely provider-specific hook (check-typed-routing keys on the Agent
        dispatch tool, which Codex has no analog for) is declared, not smuggled."""
        canon = set(RUNTIME_HOOK_NAMES)
        for rel in ("src.claude/agents/hooks", "src.codex/skills/lead/hooks"):
            pack_hooks = ROOT / Path(rel)
            extra = PACK_ONLY_HOOKS.get(rel, frozenset())
            pack = {
                p.name for p in pack_hooks.iterdir()
                if p.is_file() and p.suffix in universal_hooks_manifest.HOOK_EXTS
            }
            with self.subTest(pack=rel):
                self.assertEqual(
                    canon | set(extra), pack,
                    f"hooks/ set mismatch: undeclared pack-only="
                    f"{pack - canon - set(extra)}, missing-from-pack="
                    f"{(canon | set(extra)) - pack}",
                )

    def test_pack_scripts_dir_is_canon_plus_declared_pack_only(self) -> None:
        """Set-equality for scripts/: pack == canon ∪ declared pack-only set.
        Catches BOTH a hook parked in scripts/ with no canon counterpart and
        no declaration (the exact class that let agents-mode-reminder ship in
        both packs while invisible to this gate) AND a declared name that
        disappeared from a pack."""
        canon = set(RUNTIME_SCRIPT_NAMES)
        for rel, extra in PACK_ONLY_SCRIPTS.items():
            pack_dir = ROOT / Path(rel)
            pack = {
                p.name for p in pack_dir.iterdir()
                if p.is_file() and p.suffix in universal_hooks_manifest.HOOK_EXTS
            }
            with self.subTest(pack=rel):
                self.assertEqual(
                    canon | set(extra), pack,
                    f"scripts/ set mismatch: undeclared pack-only="
                    f"{pack - canon - set(extra)}, missing-from-pack="
                    f"{(canon | set(extra)) - pack}",
                )

    def test_sync_tool_drift_detection_matches_primary_parity_loop(self) -> None:
        """universal_hooks_manifest.find_drift() must enumerate exactly the same
        drifted files as the byte-for-byte loop in
        test_pack_neutral_hook_sources_exist_and_match_production_packs above —
        otherwise a lane's fast standalone `--check` (point 2 of
        work-items/bugs/2026-07-26-mirror-parity-is-detected-but-never-
        propagated.md: detection belongs where a lane hits it before reporting,
        not only in the full suite) could report clean while the full-suite gate
        still fails, or vice versa. This test re-derives provider_pairs
        independently (deliberately not sharing code with the primary test
        above) so the two detection paths are cross-checked, not just aliased."""
        universal_scripts = ROOT / "scripts" / "universal-hooks" / "scripts"
        universal_hooks = ROOT / "scripts" / "universal-hooks" / "hooks"
        provider_pairs = (
            (ROOT / "src.codex" / "skills" / "lead" / "scripts", RUNTIME_SCRIPT_NAMES),
            (ROOT / "src.claude" / "agents" / "scripts", RUNTIME_SCRIPT_NAMES),
            (ROOT / "src.codex" / "skills" / "lead" / "hooks", RUNTIME_HOOK_NAMES),
            (ROOT / "src.claude" / "agents" / "hooks", RUNTIME_HOOK_NAMES),
        )
        expected_drifted: set[str] = set()
        for provider_dir, names in provider_pairs:
            universal_dir = universal_scripts if provider_dir.name == "scripts" else universal_hooks
            for name in names:
                m_path = provider_dir / name
                if not m_path.is_file() or not filecmp.cmp(universal_dir / name, m_path, shallow=False):
                    expected_drifted.add(m_path.relative_to(ROOT).as_posix())

        actual_drifted = {
            e.mirror_path.relative_to(ROOT).as_posix()
            for e in universal_hooks_manifest.find_drift(ROOT)
        }
        self.assertEqual(expected_drifted, actual_drifted)

    def test_sync_tool_check_cli_exit_code_matches_drift_presence(self) -> None:
        """Exercise the actual CLI subprocess (not just the importable
        functions) — that is what a lane runs in its own targeted pass before
        reporting a result, per the documented obligation in
        docs/new-session-guide.md. A subprocess crash here fails only this one
        test; it cannot take down this file's collection (see the module-level
        comment above and test_sync_tool_cli_module_is_importable below)."""
        result = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "sync-universal-hooks.py"),
                "--check", "--root", str(ROOT),
            ],
            capture_output=True, text=True,
        )
        has_drift = bool(universal_hooks_manifest.find_drift(ROOT))
        self.assertEqual(
            result.returncode, 1 if has_drift else 0,
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

    def test_one_sided_epic_terminal_parity(self) -> None:
        mirror = (
            ROOT
            / "src.codex"
            / "skills"
            / "lead"
            / "scripts"
            / "workitem_sentinels.py"
        )
        original = mirror.read_bytes()
        try:
            mirror.write_bytes(original + b"\n# deliberate one-sided parity probe\n")
            failed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "sync-universal-hooks.py"),
                    "--check",
                    "--root",
                    str(ROOT),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(
                "src.codex/skills/lead/scripts/workitem_sentinels.py",
                failed.stdout + failed.stderr,
            )
        finally:
            mirror.write_bytes(original)

        clean = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "sync-universal-hooks.py"),
                "--check",
                "--root",
                str(ROOT),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            clean.returncode,
            0,
            f"stdout={clean.stdout!r} stderr={clean.stderr!r}",
        )

    def test_sync_tool_cli_module_is_importable(self) -> None:
        """scripts/sync-universal-hooks.py (the CLI/mutation tool — argparse,
        subprocess, git integration — as opposed to the manifest module
        imported at the top of this file) is loaded HERE, inside this single
        test method, specifically so a defect in it fails as ONE named,
        attributable test rather than crashing collection for this entire
        file. That crash is exactly what happened before the manifest split:
        a `dataclasses` + Python-3.14 interaction in an earlier `DriftEntry`
        implementation living in this file took every test below down with
        it, and a neighbouring lane had to run the full suite with
        `--ignore=tests/test_universal_hook_surfaces.py` to get a clean
        result — the parity gate was unavailable, not failing loud, exactly
        the defect class work-items/bugs/2026-07-26-mirror-parity-is-
        detected-but-never-propagated.md is about one dependency over."""
        tool_path = ROOT / "scripts" / "sync-universal-hooks.py"
        spec = importlib.util.spec_from_file_location("sync_universal_hooks_cli_probe", tool_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any
            # import-time failure in the CLI tool must show up as THIS named
            # test failing, never as a collection-time crash for the module.
            self.fail(f"scripts/sync-universal-hooks.py failed to import: {exc!r}")
        finally:
            sys.modules.pop(spec.name, None)

    def test_gemini_qwen_installers_copy_universal_hook_helpers(self) -> None:
        required_fragments = (
            "scripts/universal-hooks/scripts",
            "scripts/universal-hooks/hooks",
            "check-bugfix-discipline.py",
            "mcp-usage-reminder.sh",
            "check-machine-local-path.py",
            "check-no-trash-in-repo.py",
        )

        for rel in (
            "scripts/install-gemini.sh",
            "scripts/install-gemini.ps1",
            "scripts/install-qwen.sh",
            "scripts/install-qwen.ps1",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(installer=rel):
                for fragment in required_fragments:
                    self.assertIn(fragment, text)

    def test_deprecated_examples_have_only_the_required_universal_compatibility_launcher(
        self,
    ) -> None:
        universal_scripts = ROOT / "scripts" / "universal-hooks" / "scripts"
        compatibility_launchers = {
            path.name
            for path in universal_scripts.glob("*.sh")
            if path.name != "check-publication-safety.sh"
        }
        self.assertEqual(
            compatibility_launchers,
            DEPRECATED_EXAMPLE_COMPATIBILITY_LAUNCHERS,
        )
        for name in DEPRECATED_EXAMPLE_COMPATIBILITY_LAUNCHERS:
            self.assertTrue((universal_scripts / name).with_suffix(".py").is_file())

    def test_docs_do_not_describe_gemini_qwen_hooks_as_absent(self) -> None:
        docs = [
            ROOT / "INSTALL.md",
            ROOT / "src.gemini" / "skills" / "lead" / "subagent-contracts.md",
            ROOT / "src.qwen" / "skills" / "lead" / "subagent-contracts.md",
        ]
        for path in docs:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("do not auto-install the production Codex/Claude helper or hook surfaces", text)
                self.assertIn("universal hook/helper", text)


if __name__ == "__main__":
    unittest.main()
