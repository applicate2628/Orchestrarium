from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERIC_OWNER = Path("shared/AGENTS.shared.md")
GENERIC_CONSUMERS = (
    Path("shared/references/subagent-operating-model.md"),
    Path("shared/references/ru/subagent-operating-model.md"),
    Path("shared/references/workflow-strategy-comparison.md"),
    Path("shared/references/ru/workflow-strategy-comparison.md"),
    Path("shared/references/spine/delegation-principles.md"),
    Path("shared/references/cross-pack-reconciliation.md"),
    Path("src.claude/skills/lead/SKILL.md"),
    Path("src.claude/agents/contracts/operating-model.md"),
    Path("src.codex/skills/lead/SKILL.md"),
    Path("src.codex/skills/lead/operating-model.md"),
    Path("src.claude/commands/agents-bugfix.md"),
    Path("src.claude/commands/agents-design.md"),
    Path("src.claude/commands/agents-perf.md"),
    Path("src.claude/commands/agents-refactor.md"),
    Path("src.claude/commands/agents-research.md"),
    Path("src.claude/commands/agents-security.md"),
    Path("references-claude/operating-model-diagram.md"),
    Path("references-claude/ru/operating-model-diagram.md"),
    Path("references-codex/operating-model-diagram.md"),
    Path("references-codex/ru/operating-model-diagram.md"),
)
REVIEW_LOOP_CONSUMERS = (
    Path("shared/references/review-loop-methodology.md"),
    Path("shared/references/ru/review-loop-methodology.md"),
    Path("src.claude/agents/contracts/review-loop.md"),
    Path("src.claude/commands/agents-review-loop.md"),
    Path("src.codex/skills/review-loop/SKILL.md"),
    Path("src.claude/agents/hooks/dispatch_sentinels.py"),
)
GENERIC_SCAN_ROOTS = (
    Path("shared"),
    Path("src.claude"),
    Path("src.codex"),
    Path("references-claude"),
    Path("references-codex"),
)
REVIEW_LOOP_CAP_PATTERNS = {
    Path("shared/references/review-loop-methodology.md"): re.compile(
        r"cap at \*\*N = (?P<cap>\d+)\*\* rounds"
    ),
    Path("shared/references/ru/review-loop-methodology.md"): re.compile(
        r"ограничение в \*\*N = (?P<cap>\d+)\*\* раунда"
    ),
    Path("src.claude/agents/contracts/review-loop.md"): re.compile(
        r"cap at \*\*N = (?P<cap>\d+)\*\* rounds"
    ),
    Path("src.claude/commands/agents-review-loop.md"): re.compile(
        r"cap N=(?P<cap>\d+) reached"
    ),
    Path("src.codex/skills/review-loop/SKILL.md"): re.compile(
        r"cap at \*\*N = (?P<cap>\d+)\*\* rounds"
    ),
    Path("src.claude/agents/hooks/dispatch_sentinels.py"): re.compile(
        r"review family at\s+(?P<cap>\d+) rounds"
    ),
}

GENERIC_CAP_LINE = re.compile(
    r"(?i)(?=.*\bREVISE\b)(?=.*\b3\b)(?=.*(?:cap|cycle|iteration|round|предел|цикл|итерац|раунд))"
)
OWNER_CONTRACT = re.compile(
    r"REVISE.*?escalate after (?P<cap>\d+) consecutive cycles for the same role and artifact",
    re.IGNORECASE,
)
def _text(path: Path) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _review_loop_state_module():
    path = REPO_ROOT / "scripts" / "review_loop_state.py"
    spec = importlib.util.spec_from_file_location("review_loop_state_cap_contract", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReviseCapContractsTest(unittest.TestCase):
    def test_generic_lead_cap_has_one_numeric_owner(self) -> None:
        owner_match = OWNER_CONTRACT.search(_text(GENERIC_OWNER))
        self.assertIsNotNone(owner_match, "shared spine must own the generic REVISE cap")
        self.assertEqual(int(owner_match.group("cap")), 3)

        duplicate_rows: list[str] = []
        for path in GENERIC_CONSUMERS:
            for number, line in enumerate(_text(path).splitlines(), 1):
                if GENERIC_CAP_LINE.search(line):
                    duplicate_rows.append(f"{path}:{number}: {line.strip()}")
        self.assertEqual(
            duplicate_rows,
            [],
            "generic REVISE consumers must cite the shared spine instead of restating its number:\n"
            + "\n".join(duplicate_rows),
        )

    def test_generic_lead_cap_consumers_use_same_role_and_artifact_scope(self) -> None:
        stale_scope: list[str] = []
        for path in GENERIC_CONSUMERS:
            for number, line in enumerate(_text(path).splitlines(), 1):
                if "REVISE" in line and re.search(r"(?i)per stage", line):
                    stale_scope.append(f"{path}:{number}: {line.strip()}")
        self.assertEqual(
            stale_scope,
            [],
            "generic correction cap is scoped to the same role and artifact, never a stage:\n"
            + "\n".join(stale_scope),
        )

    def test_generic_cap_numeric_inventory_is_closed(self) -> None:
        matches: list[str] = []
        for root in GENERIC_SCAN_ROOTS:
            for path in sorted((REPO_ROOT / root).rglob("*.md")):
                relative = path.relative_to(REPO_ROOT)
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if GENERIC_CAP_LINE.search(line):
                        matches.append(f"{relative}:{number}")
        self.assertEqual(matches, [f"{GENERIC_OWNER}:39"])

    def test_retired_ambiguous_cap_owner_is_absent(self) -> None:
        module = _review_loop_state_module()
        self.assertFalse(
            hasattr(module, "DEFAULT_CAP"),
            "retired ambiguous DEFAULT_CAP must not remain as a compatibility alias",
        )
        wrapper = _text(Path("scripts/validate-review-loop-state.py"))
        self.assertNotIn("DEFAULT_CAP", wrapper)
        self.assertNotRegex(wrapper, r"\bcap\s*=\s*3\b")

    def test_review_loop_round_consumers_match_runtime_owner(self) -> None:
        module = _review_loop_state_module()
        self.assertTrue(
            hasattr(module, "REVIEW_LOOP_ROUND_CAP"),
            "review-loop round cap needs an unambiguous owner name",
        )
        cap = module.REVIEW_LOOP_ROUND_CAP
        self.assertEqual(cap, 3)
        for path in REVIEW_LOOP_CONSUMERS:
            match = REVIEW_LOOP_CAP_PATTERNS[path].search(_text(path))
            with self.subTest(path=path):
                self.assertIsNotNone(match)
                self.assertEqual(int(match.group("cap")), cap)

    def test_review_loop_cli_preserves_explicit_cap_override(self) -> None:
        module = _review_loop_state_module()
        default_args = module.build_parser().parse_args(
            ["validate", "--state", "state.json"]
        )
        override_args = module.build_parser().parse_args(
            ["validate", "--state", "state.json", "--cap", "7"]
        )
        self.assertEqual(default_args.cap, module.REVIEW_LOOP_ROUND_CAP)
        self.assertEqual(override_args.cap, 7)


if __name__ == "__main__":
    unittest.main()
