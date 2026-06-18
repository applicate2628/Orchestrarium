import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ResolveAgentsModeTest(unittest.TestCase):
    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")

    def _resolve(self, provider: str, project_root: Path, home: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "resolve-agents-mode.py"),
                "--provider",
                provider,
                "--project-root",
                str(project_root),
                "--home",
                str(home),
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_codex_layers_compose_per_key_without_synthesizing_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()

            self._write(
                home / ".agents-mode.yaml",
                """
                consultantMode: internal
                mcpMode: force
                externalPriorityProfile: quality-first
                """,
            )
            self._write(
                home / ".codex" / ".agents-mode.yaml",
                """
                mcpMode: auto
                parallelMode: force
                """,
            )
            self._write(
                project / ".agents" / ".agents-mode",
                """
                parallelMode: manual
                preferExternalReviewer: true
                """,
            )
            self._write(
                project / ".agents" / ".agents-mode.yaml",
                """
                consultantMode: disabled
                """,
            )

            resolved = self._resolve("codex", project, home)

            values = resolved["values"]
            sources = resolved["sources"]
            self.assertEqual(values["consultantMode"], "disabled")
            self.assertEqual(sources["consultantMode"]["rank"], "local")
            self.assertEqual(values["parallelMode"], "manual")
            self.assertEqual(sources["parallelMode"]["rank"], "local-legacy")
            self.assertEqual(values["mcpMode"], "auto")
            self.assertEqual(sources["mcpMode"]["rank"], "global")
            self.assertEqual(values["externalPriorityProfile"], "quality-first")
            self.assertEqual(sources["externalPriorityProfile"]["rank"], "shared-global")
            self.assertEqual(values["preferExternalReviewer"], "true")
            self.assertEqual(values["delegationMode"], "manual")
            self.assertEqual(sources["delegationMode"]["rank"], "defaults")
            self.assertEqual(values["externalClaudeProfile"], "opus-max")

            self.assertFalse((project / ".agents" / ".agents-mode.yaml.generated").exists())

    def test_example_providers_use_shared_global_as_demo_fallback_without_becoming_auto_production(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()
            self._write(
                home / ".agents-mode.yaml",
                """
                mcpMode: force
                externalProvider: auto
                """,
            )

            for provider in ("gemini", "qwen"):
                with self.subTest(provider=provider):
                    resolved = self._resolve(provider, project, home)
                    self.assertEqual(resolved["values"]["mcpMode"], "force")
                    self.assertEqual(resolved["sources"]["mcpMode"]["rank"], "shared-global")
                    self.assertEqual(resolved["values"]["externalProvider"], "auto")
                    self.assertNotIn(
                        provider,
                        resolved["values"]["externalPriorityProfiles"]["balanced"][
                            "worker.default-implementation"
                        ],
                    )


if __name__ == "__main__":
    unittest.main()
