from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / ("adapters/claude" if (ROOT / "adapters/claude").is_dir() else "src.claude")


def test_class_trigger_covers_all_evidence_without_granting_mutation():
    paths = (ROOT / "src.codex/skills/lead/subagent-contracts.md",
             CLAUDE / "agents/contracts/subagent-contracts.md")
    rules = []
    for path in paths:
        text = path.read_text(encoding="utf8")
        assert "(e) when the Class-completeness trigger applies, including findings after dispatch" in text
        rule = next(line for line in text.splitlines()
                    if line.startswith("**Class-completeness trigger"))
        for evidence in ("including a user report or an inline finding",
                         "same cause and contract",
                         "smallest correction at that owner",
                         "preserve independent owners",
                         "without write authority",
                         "supported neighboring case",
                         "required rejection",
                         "superseded logic"):
            assert evidence in rule, (path, evidence)
        rules.append(rule)
    assert rules[0] == rules[1]
