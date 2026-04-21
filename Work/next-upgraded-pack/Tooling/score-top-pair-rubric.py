#!/usr/bin/env python3
"""Score diagnostic E2 top-pair artifacts with a bounded structural rubric.

This is intentionally separate from scenario verifiers. Verifiers answer
PASS/FAIL; this scorer gives a small quality signal when both rows pass.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


SCENARIOS = {
    "N11": Path("candidate/design-package.md"),
    "N12": Path("candidate/repository-fact-memo.md"),
    "N13": Path("candidate/review-report.md"),
}


@dataclass(frozen=True)
class Criterion:
    name: str
    max_points: int
    terms: tuple[str, ...]
    note: str


RUBRIC: dict[str, tuple[Criterion, ...]] = {
    "N11": (
        Criterion(
            "source specificity",
            4,
            (
                "Orchestrarium/shared/agents-mode.defaults.yaml",
                "Archive/legacy-provider-runbook.md",
                "benchmarks/Work/next-upgraded-pack/Results-drafts/short-results-current-2026-04-18.md",
                "Orchestrarium/shared/external-adapter-contract.md",
            ),
            "names the concrete evidence sources instead of only evidence IDs",
        ),
        Criterion(
            "conflict resolution precision",
            4,
            (
                "externalPriorityProfiles",
                "externalPriorityProfile",
                "compatibility alias",
                "visible deprecation signal",
            ),
            "separates plural source of truth from singular compatibility input",
        ),
        Criterion(
            "ownership seam",
            4,
            (
                "agents-mode loader",
                "normalized profile catalog",
                "single owner",
                "singular-to-plural rewrite",
            ),
            "keeps policy parsing owned by the loader",
        ),
        Criterion(
            "adapter boundary",
            4,
            (
                "adapters stay transport-only",
                "not exported",
                "forbidden direction",
                "lane taxonomy",
            ),
            "prevents adapter-side lane/profile parsing",
        ),
        Criterion(
            "route-policy separation",
            4,
            (
                "X4",
                "secret-backed Claude",
                "runtime transport",
                "X4 never appears as a key",
            ),
            "keeps route availability out of profile identity",
        ),
    ),
    "N12": (
        Criterion(
            "source ranking",
            4,
            (
                "agents-mode.defaults.yaml",
                "operator-routing.md",
                "hardened-core12.md",
                "legacy-notes.md",
            ),
            "orders the conflicting sources explicitly",
        ),
        Criterion(
            "confirmed fact precision",
            4,
            (
                "externalPriorityProfiles",
                "providerRoutes",
                "no lane-profile membership",
                "not a model capability failure",
            ),
            "states current config facts without turning route status into capability judgment",
        ),
        Criterion(
            "legacy conflict handling",
            4,
            (
                "externalPriorityProfile",
                "singular",
                "compatibility alias",
                "does not override",
            ),
            "classifies stale singular wording correctly",
        ),
        Criterion(
            "top-pair non-claim",
            4,
            (
                "not separated",
                "15 / 15",
                "No directional claim",
                "additional separators",
            ),
            "does not over-rank X1 versus X3 from tied evidence",
        ),
        Criterion(
            "gap discipline",
            4,
            (
                "High confidence",
                "Gap:",
                "recovery timeline",
                "additional separators",
            ),
            "states confidence and remaining evidence gaps",
        ),
    ),
    "N13": (
        Criterion(
            "finding localization",
            4,
            (
                "retry_policy.py",
                "classify_result",
                "lane_summary.py",
                "status_label",
            ),
            "localizes defects to file and symbol",
        ),
        Criterion(
            "scoreability semantics",
            4,
            (
                "REQUEUE",
                "not verifier FAIL",
                "not a clean PASS",
                "scoreable",
            ),
            "keeps quota, timeout, and verifier status separate",
        ),
        Criterion(
            "fix specificity",
            4,
            (
                "Fix:",
                "distinct",
                "TIMEOUT-ARTIFACT-OK",
                "len(scoreable)",
            ),
            "gives concrete repair guidance for each defect class",
        ),
        Criterion(
            "false-positive discipline",
            4,
            (
                "ui_helpers.py",
                "chip-neutral",
                "not blocking",
                "out of scope",
            ),
            "avoids the explicit decoy finding",
        ),
        Criterion(
            "denominator reporting",
            4,
            (
                "len(rows)",
                "denominator",
                "non-scoreable counts separately",
                "route status",
            ),
            "requires denominator and non-scoreable status clarity",
        ),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score X1/X3 E2 top-pair outputs.")
    parser.add_argument("--x1-root", type=Path, required=True)
    parser.add_argument("--x3-root", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def score_criterion(text: str, criterion: Criterion) -> tuple[int, list[str], list[str]]:
    lowered = text.lower()
    present = [term for term in criterion.terms if term.lower() in lowered]
    missing = [term for term in criterion.terms if term.lower() not in lowered]
    points = min(criterion.max_points, len(present))
    return points, present, missing


def score_artifact(root: Path, scenario_id: str) -> dict:
    artifact = root / scenario_id / "run" / SCENARIOS[scenario_id]
    text = artifact.read_text(encoding="utf-8-sig")
    criteria = []
    total = 0
    maximum = 0
    for criterion in RUBRIC[scenario_id]:
        points, present, missing = score_criterion(text, criterion)
        total += points
        maximum += criterion.max_points
        criteria.append(
            {
                "name": criterion.name,
                "points": points,
                "max": criterion.max_points,
                "present": present,
                "missing": missing,
                "note": criterion.note,
            }
        )
    return {
        "scenario": scenario_id,
        "artifact": str(artifact),
        "score": total,
        "max": maximum,
        "criteria": criteria,
        "char_count": len(text),
        "line_count": len(text.splitlines()),
        "file_refs": sorted(set(re.findall(r"[A-Za-z0-9_./-]+\\.(?:md|yaml|py|json|ps1)", text))),
    }


def score_row(root: Path, label: str) -> dict:
    scenarios = [score_artifact(root, scenario_id) for scenario_id in SCENARIOS]
    total = sum(item["score"] for item in scenarios)
    maximum = sum(item["max"] for item in scenarios)
    return {
        "row": label,
        "root": str(root),
        "score": total,
        "max": maximum,
        "scenarios": scenarios,
    }


def markdown_report(result: dict) -> str:
    rows = result["rows"]
    x1 = rows[0]
    x3 = rows[1]
    winner = "tie"
    if x1["score"] > x3["score"]:
        winner = "X1"
    elif x3["score"] > x1["score"]:
        winner = "X3"

    lines = [
        f"Date: {result.get('generated_on', date.today().isoformat())}",
        "Owner: `$lead`",
        "Status: `PASS`",
        "",
        "## Rubric Result",
        "",
        "| Row | Score | Read |",
        "|---|---:|---|",
        f"| `X1 / gpt-5.4` | `{x1['score']} / {x1['max']}` | {'wins E3' if winner == 'X1' else 'tied' if winner == 'tie' else 'below X3 on E3'} |",
        f"| `X3 / opus 4.7max` | `{x3['score']} / {x3['max']}` | {'wins E3' if winner == 'X3' else 'tied' if winner == 'tie' else 'below X1 on E3'} |",
        "",
        f"E3 verdict: `{winner}`.",
        "",
        "## Source Roots",
        "",
        "| Row | Scratch root |",
        "|---|---|",
        f"| `X1` | `{x1['root']}` |",
        f"| `X3` | `{x3['root']}` |",
        "",
        "## Scenario Scores",
        "",
        "| Scenario | X1 | X3 | Delta |",
        "|---|---:|---:|---:|",
    ]
    for sid in SCENARIOS:
        sx1 = next(item for item in x1["scenarios"] if item["scenario"] == sid)
        sx3 = next(item for item in x3["scenarios"] if item["scenario"] == sid)
        lines.append(f"| `{sid}` | `{sx1['score']} / {sx1['max']}` | `{sx3['score']} / {sx3['max']}` | `{sx3['score'] - sx1['score']}` |")

    lines.extend(
        [
            "",
            "## Criterion Detail",
            "",
            "| Scenario | Criterion | X1 | X3 | Delta |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for sid in SCENARIOS:
        sx1 = next(item for item in x1["scenarios"] if item["scenario"] == sid)
        sx3 = next(item for item in x3["scenarios"] if item["scenario"] == sid)
        for c1, c3 in zip(sx1["criteria"], sx3["criteria"]):
            lines.append(f"| `{sid}` | {c1['name']} | `{c1['points']}` | `{c3['points']}` | `{c3['points'] - c1['points']}` |")

    lines.extend(
        [
            "",
            "## Method",
            "",
            "This is a deterministic structural rubric over already generated artifacts.",
            "It does not replace scenario verifiers and does not add a routing lane.",
            "",
            "| Boundary | Meaning |",
            "|---|---|",
            "| supplied run roots | scores the `N11..N13` artifacts in the roots named above |",
            "| no pass/fail override | both rows still pass E2 binary verifiers |",
            "| diagnostic-only | use only as E3 top-pair signal, not as `externalPriorityProfiles` input |",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    result = {
        "rubric": "E3 top-pair-rubric",
        "generated_on": date.today().isoformat(),
        "rows": [
            score_row(args.x1_root, "X1 / gpt-5.4"),
            score_row(args.x3_root, "X3 / opus 4.7max"),
        ],
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = markdown_report(result)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
