import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class NormalizeAgentsModeContractTest(unittest.TestCase):
    def test_profile_provider_sanitization_uses_adjacent_schema(self) -> None:
        root = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shared = tmp_path / "shared"
            shared.mkdir()
            template = shared / "agents-mode.defaults.yaml"
            target = tmp_path / ".agents-mode.yaml"
            schema = shared / "agents-mode.schema.json"

            template.write_text(
                textwrap.dedent(
                    """\
                    consultantMode: disabled
                    externalPriorityProfiles:
                      synthetic:
                        advisory.repo-understanding: [nova, shadow]
                        worker.default-implementation: [nova]
                    externalOpinionCounts:
                      advisory.repo-understanding: 1
                      worker.default-implementation: 1
                    """
                ),
                encoding="utf-8",
            )
            target.write_text(
                textwrap.dedent(
                    """\
                    externalPriorityProfiles:
                      custom:
                        advisory.repo-understanding: [gemini, shadow, codex]
                        worker.default-implementation: [shadow, nova]
                    """
                ),
                encoding="utf-8",
            )
            schema.write_text(
                textwrap.dedent(
                    """\
                    {
                      "version": 1,
                      "productionAutoProviders": ["nova"],
                      "exampleOnlyProviders": ["gemini"],
                      "advisoryReviewSupplementalProviders": ["shadow"],
                      "scalarKeys": [],
                      "priorityProfiles": {},
                      "externalOpinionCounts": {}
                    }
                    """
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "normalize-agents-mode.py"),
                    "--template",
                    str(template),
                    "--target",
                    str(target),
                    "--provider",
                    "shared",
                ],
                cwd=root,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = target.read_text(encoding="utf-8")
            self.assertIn(
                "advisory.repo-understanding: [nova, shadow]",
                output,
            )
            self.assertIn(
                "worker.default-implementation: [nova]",
                output,
            )
            self.assertNotIn("gemini", output)
            self.assertNotIn("codex", output)


if __name__ == "__main__":
    unittest.main()
