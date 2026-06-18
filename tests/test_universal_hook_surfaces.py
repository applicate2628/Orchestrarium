from __future__ import annotations

import filecmp
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RUNTIME_SCRIPT_NAMES = (
    "hook_common.py",
    "check-bugfix-discipline.py",
    "check-bugfix-discipline.sh",
    "check-bugfix-discipline.ps1",
    "check-passive-polling-stop.py",
    "check-passive-polling-stop.sh",
    "check-passive-polling-stop.ps1",
    "check-work-items-archival-stop.py",
    "check-work-items-archival-stop.sh",
    "check-work-items-archival-stop.ps1",
    "mcp-usage-reminder.sh",
    "mcp-usage-reminder.ps1",
    "check-publication-safety.sh",
    "check-publication-safety.ps1",
)

RUNTIME_HOOK_NAMES = (
    "check-machine-local-path.py",
    "check-machine-local-path.sh",
    "check-machine-local-path.ps1",
    "check-no-trash-in-repo.py",
    "check-no-trash-in-repo.sh",
    "check-no-trash-in-repo.ps1",
)


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
