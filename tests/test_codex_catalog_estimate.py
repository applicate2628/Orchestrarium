"""Historical estimates cannot establish actual runtime catalog visibility."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-codex-skill-catalog-budget.py"


class CatalogEstimateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orche-catalog-estimate-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "codex"
        self.repo = self.root / "repo"
        for base in (self.home / "skills", self.repo):
            skill = base / "alpha" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text('---\nname: alpha\ndescription: "' + "x" * 80 + '"\n---\n',
                             encoding="utf-8")
        self.process_guard = patch("subprocess.Popen", side_effect=AssertionError("process launch forbidden"))
        self.process_guard.start()
        self.addCleanup(self.process_guard.stop)
        self.module = runpy.run_path(str(SCRIPT))
        self.globals = self.module["main"].__globals__

    def invoke(self, args, observation=None):
        output = io.StringIO()
        forbidden = AssertionError("offline estimate attempted client resolution")
        with contextlib.redirect_stdout(output), patch.dict(os.environ, {"CODEX_HOME": str(self.home)}), \
                patch.object(Path, "home", return_value=self.root):
            if observation is None:
                with patch.object(self.globals["shutil"], "which", side_effect=forbidden):
                    result = self.module["main"](args)
            else:
                self.globals["DEFAULT_REPO_SKILLS"] = self.repo
                self.globals["observe_runtime_catalog"] = lambda *_args: observation
                with patch.object(self.globals["shutil"], "which", return_value="fake-codex"):
                    result = self.module["main"](args)
        return result, output.getvalue()

    def custom_args(self):
        return ["--codex-home", str(self.home), "--agents-skills-home", str(self.root / "empty"),
                "--repo-skills", str(self.repo)]

    def test_high_estimate_is_warning_not_runtime_failure(self):
        code, output = self.invoke(self.custom_args() + ["--context-window", "100", "--fail-fraction", "0.1"])
        self.assertEqual(code, 0)
        self.assertIn("RESULT: ESTIMATE", output)
        self.assertIn("WARNING: historical estimate", output)
        self.assertIn("not verified", output)
        self.assertNotIn("FAIL:", output)
        self.assertNotIn("must still claw back", output)

    def test_low_estimate_does_not_claim_runtime_pass(self):
        code, output = self.invoke(self.custom_args() + ["--context-window", "1000000"])
        self.assertEqual(code, 0)
        self.assertIn("RESULT: ESTIMATE", output)
        self.assertNotIn("PASS:", output)

    def test_high_threshold_and_legacy_alias_agree(self):
        base = self.custom_args() + ["--context-window", "100"]
        self.assertEqual(self.invoke(base + ["--high-fraction", "0.2"]),
                         self.invoke(base + ["--fail-fraction", "0.2"]))

    def test_custom_estimate_parameters_do_not_launch_default_client(self):
        self.globals["DEFAULT_REPO_SKILLS"] = self.repo
        for option, value in (("--context-window", "100"), ("--warn-fraction", "0.1"),
                              ("--high-fraction", "0.2"), ("--fail-fraction", "0.2")):
            with self.subTest(option=option):
                code, output = self.invoke([option, value])
                self.assertEqual(code, 0)
                self.assertIn("RESULT: ESTIMATE", output)

    def test_explicit_default_calibration_remains_offline(self):
        self.globals["DEFAULT_REPO_SKILLS"] = self.repo
        for option, value in (("--context-window", "272000"),
                              ("--warn-fraction", "0.8"),
                              ("--high-fraction", "0.9"),
                              ("--fail-fraction", "0.9")):
            for args in ([option, value], [option + "=" + value]):
                with self.subTest(args=args):
                    code, output = self.invoke(args)
                    self.assertEqual(code, 0)
                    self.assertIn("RESULT: ESTIMATE", output)
                    self.assertNotIn("Runtime catalog:", output)

    def observe_description(self, description):
        block = ("<skills_instructions>\n- `r0` = `" + (self.home / "skills").as_posix()
                 + "`\n- alpha: " + description + " (file: r0/alpha/SKILL.md)\n</skills_instructions>")
        payload = json.dumps([{"content": [{"type": "input_text", "text": block}]}])
        return self.module["parse_runtime_prompt_input"](payload, self.repo, self.home / "skills")

    def test_equal_or_longer_replacement_is_not_shortening(self):
        for description in ("y" * 80, "y" * 81, "x" * 80 + "extra"):
            with self.subTest(description=description):
                observation = self.observe_description(description)
                self.assertEqual(observation.status, "description-mismatch")
                self.assertEqual(observation.diagnostic, "CATALOG-DESCRIPTION-MISMATCH")
                code, output = self.invoke([], observation)
                self.assertEqual(code, 1)
                self.assertIn("RESULT: FAIL", output)
                self.assertNotIn("WARNING: CATALOG-DESCRIPTION-SHORTENED", output)

    def test_matching_and_shorter_description_contract_unchanged(self):
        self.assertEqual(self.observe_description("x" * 80).status, "complete")
        short = self.observe_description("short alpha")
        self.assertEqual(short.status, "shortened")
        self.assertEqual(short.shortened_chars, 69)

    def test_shorter_warning_does_not_claim_truncation_provenance(self):
        for description in ("x" * 10, "unrelated"):
            with self.subTest(description=description):
                observation = self.observe_description(description)
                code, output = self.invoke([], observation)
                self.assertEqual(observation.status, "shortened")
                self.assertEqual(code, 0)
                self.assertIn("RESULT: PASS", output)
                self.assertIn("descriptions are shorter", output)
                self.assertIn("description content and provenance are unverified", output)
                self.assertIn("Without version-pinned runtime and render-source binding", output)
                self.assertIn("description-length-difference=", output)
                self.assertIn(f"removed-chars={observation.shortened_chars}", output)
                self.assertIn(f"description-length-difference={observation.shortened_chars}", output)
                self.assertIn("deprecated length-difference alias, not removal evidence", output)
                self.assertNotIn("shortens 1 descriptions", output)

    def test_zero_context_is_still_only_an_estimate(self):
        code, output = self.invoke(self.custom_args() + ["--context-window", "0"])
        self.assertEqual(code, 0)
        self.assertIn("RESULT: ESTIMATE", output)
        self.assertIn("not verified", output)

    def test_missing_ownership_reference_still_fails(self):
        code, output = self.invoke(["--repo-skills", str(self.root / "absent")])
        self.assertEqual(code, 1)
        self.assertIn("RESULT: FAIL", output)

    def test_missing_catalog_still_skips(self):
        code, output = self.invoke(["--codex-home", str(self.root / "absent"),
                                    "--repo-skills", str(self.repo)])
        self.assertEqual(code, 0)
        self.assertIn("RESULT: SKIP", output)

    def test_fake_runtime_verdicts_remain_authoritative(self):
        cases = (("complete", "CATALOG-COMPLETE", 0),
                 ("shortened", "CATALOG-DESCRIPTION-SHORTENED", 0),
                 ("omitted-pack", "CATALOG-PACK-IDENTITY-OMITTED", 1),
                 ("unavailable", "CATALOG-RUNTIME-UNAVAILABLE", 1),
                 ("malformed", "CATALOG-RUNTIME-MALFORMED", 1))
        for status, diagnostic, expected in cases:
            with self.subTest(status=status):
                observation = self.module["RuntimeCatalogObservation"](
                    status=status, diagnostic=diagnostic, total_entries=1,
                    pack_expected=1, pack_rendered=0 if expected else 1,
                    shortened_count=1 if status == "shortened" else 0,
                    shortened_chars=3 if status == "shortened" else 0,
                    omitted_pack=("alpha",) if status == "omitted-pack" else ())
                code, output = self.invoke([], observation=observation)
                self.assertEqual(code, expected)
                self.assertIn(diagnostic, output)
                self.assertIn("RESULT: " + ("FAIL" if expected else "PASS"), output)


if __name__ == "__main__":
    unittest.main()
