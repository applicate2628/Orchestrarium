from __future__ import annotations

import filecmp
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# The pack-neutral canon dir IS the single owner of "which universal hooks exist"
# — derive the name lists by GLOB, never a hardcoded tuple. A hardcoded list is
# exactly what hid check-stale-relation-residue from this gate (it shipped in the
# packs but was never added to the canon or the tuple), so the list must come
# from the canon dir itself and a set-equality check must flag a pack hook that
# has no canon counterpart.
_CANON = ROOT / "scripts" / "universal-hooks"
_HOOK_EXTS = (".py", ".sh", ".ps1")


def _canon_names(subdir: str) -> tuple:
    d = _CANON / subdir
    return tuple(sorted(
        p.name for p in d.iterdir()
        if p.is_file() and p.suffix in _HOOK_EXTS
    ))


RUNTIME_SCRIPT_NAMES = _canon_names("scripts")
RUNTIME_HOOK_NAMES = _canon_names("hooks")

# scripts/-dir members that intentionally have NO byte-identical canon
# counterpart. Every entry needs a justification comment; anything in a pack
# scripts/ dir that is neither canon nor declared here FAILS the set-equality
# test below. (This is the seam the amended hook-placement law names:
# shared/references/repository-source-hygiene.md, decision
# 2026-07-11-hook-placement-gate-semantics.)
PACK_ONLY_SCRIPTS = {
    "src.claude/agents/scripts": frozenset({
        # Provider-specialized SessionStart context hook: walks the CLAUDE-line
        # .agents-mode.yaml read-order (./.claude/, ~/.claude/) and speaks
        # Agent-tool dispatch idiom; the codex twin walks ./.agents/ + ~/.codex/
        # and speaks role/skill-activation idiom — intentionally different.
        "agents-mode-reminder.sh", "agents-mode-reminder.ps1",
        # Claude-line provider transport wrappers (no codex/canon analog).
        "invoke-claude-api.sh", "invoke-claude-api.ps1",
        "invoke-claude-prompt.sh", "invoke-claude-prompt.ps1",
        "invoke-codex-prompt.sh", "invoke-codex-prompt.ps1",
        # Claude-line active watcher emitted by the Codex dispatch wrappers;
        # it is provider-specific and has no Codex/canon mirror.
        "await-codex-dispatch.sh", "await-codex-dispatch.ps1",
        # Per-pack validator (content differs per pack by design).
        "validate-skill-pack.sh", "validate-skill-pack.ps1",
    }),
    "src.codex/skills/lead/scripts": frozenset({
        "agents-mode-reminder.sh", "agents-mode-reminder.ps1",  # see above
        "validate-skill-pack.sh", "validate-skill-pack.ps1",
    }),
}


class UniversalHookSurfaceTest(unittest.TestCase):
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
        """Set-equality: every audit-hook family in a pack's hooks/ dir must have
        a canon counterpart (and vice versa). The pack hooks/ dirs hold exactly
        the audit-hook set, so canon==pack is the right invariant here
        (scripts/ has its own set-equality below: canon ∪ declared
        `PACK_ONLY_SCRIPTS`). This is the check that would have
        caught check-stale-relation-residue being absent from the canon."""
        canon = set(RUNTIME_HOOK_NAMES)
        for pack_hooks in (
            ROOT / "src.claude" / "agents" / "hooks",
            ROOT / "src.codex" / "skills" / "lead" / "hooks",
        ):
            pack = {
                p.name for p in pack_hooks.iterdir()
                if p.is_file() and p.suffix in _HOOK_EXTS
            }
            with self.subTest(pack=str(pack_hooks)):
                self.assertEqual(
                    canon, pack,
                    f"hooks/ set mismatch: canon-only={canon - pack}, "
                    f"pack-only={pack - canon} (a pack hook absent from the "
                    f"universal canon, or vice versa)",
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
                if p.is_file() and p.suffix in _HOOK_EXTS
            }
            with self.subTest(pack=rel):
                self.assertEqual(
                    canon | set(extra), pack,
                    f"scripts/ set mismatch: undeclared pack-only="
                    f"{pack - canon - set(extra)}, missing-from-pack="
                    f"{(canon | set(extra)) - pack}",
                )

    def test_gemini_qwen_installers_copy_universal_hook_helpers(self) -> None:
        required_fragments = (
            "scripts/universal-hooks/scripts",
            "scripts/universal-hooks/hooks",
            "check-bugfix-discipline.py",
            "check-work-items-archival-stop.py",
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
