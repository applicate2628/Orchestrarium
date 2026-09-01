from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from v4_rubric.cli import score_root
from v4_rubric.scoring import canonical_report_bytes


ROOT_NAMES = [
    "V4C01-source-bound-advice",
    "V4C02-numeric-reasoning",
    "V4C03-implementation-runtime",
    "V4C04-findings-review",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _adapter_report(root: Path, candidate: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(root / "verifiers" / "score.py"), "--candidate", str(candidate)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"adapter failed for {root.name}: exit={completed.returncode}; stderr={completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def validate_calibration(pack_root: Path) -> dict[str, Any]:
    roots: dict[str, Any] = {}
    all_scores: list[float] = []
    monotonic_total = 0
    monotonic_passed = 0
    deterministic_total = 0
    deterministic_passed = 0
    paraphrase_deltas: list[float] = []
    adapter_passed = 0
    integrity_probe_passed = False
    one_atom_locality_passed = 0
    threshold_neighborhood_passed = 0

    for root_name in ROOT_NAMES:
        root = pack_root / "Fixtures" / root_name
        corpus = _load_json(root / "oracle" / "synthetic-answers.json")
        order = corpus["monotonic_order"]
        scores: dict[str, float] = {}
        statuses: dict[str, str] = {}
        reports_by_id: dict[str, dict[str, Any]] = {}
        for answer_id in order:
            candidate = root / "oracle" / "synthetic" / f"{answer_id}.json"
            reports = [score_root(root, candidate) for _ in range(3)]
            deterministic_total += 1
            if len({canonical_report_bytes(report) for report in reports}) == 1:
                deterministic_passed += 1
            report = reports[0]
            reports_by_id[answer_id] = report
            if not report["scoreable"]:
                raise RuntimeError(f"{root_name}/{answer_id} unexpectedly returned {report['status']}")
            scores[answer_id] = float(report["score"])
            statuses[answer_id] = report["status"]
            all_scores.append(float(report["score"]))

        for better, worse in zip(order, order[1:]):
            monotonic_total += 1
            if scores[better] >= scores[worse]:
                monotonic_passed += 1

        paraphrase_delta = abs(scores["reference"] - scores["paraphrase"])
        paraphrase_deltas.append(paraphrase_delta)
        if scores["reference"] < 95:
            raise RuntimeError(f"{root_name} reference score {scores['reference']} is below 95")
        if scores["vacuous"] > 10:
            raise RuntimeError(f"{root_name} vacuous score {scores['vacuous']} exceeds 10")
        if not 30 <= scores["decoy"] <= 70:
            raise RuntimeError(f"{root_name} decoy score {scores['decoy']} is outside 30..70")
        if paraphrase_delta > float(corpus["paraphrase_max_delta"]):
            raise RuntimeError(f"{root_name} paraphrase delta {paraphrase_delta} exceeds its contract")

        reference_components = {item["id"]: float(item["score"]) for item in reports_by_id["reference"]["components"]}
        strong_components = {item["id"]: float(item["score"]) for item in reports_by_id["strong"]["components"]}
        changed_components = [
            component_id
            for component_id in reference_components
            if reference_components[component_id] != strong_components[component_id]
        ]
        one_atom_locality = (
            abs(scores["reference"] - scores["strong"] - 10) < 1e-9
            and len(changed_components) == 1
            and abs(
                reference_components[changed_components[0]]
                - strong_components[changed_components[0]]
                - 10
            )
            < 1e-9
        )
        one_atom_locality_passed += int(one_atom_locality)
        threshold_neighborhood = 72 <= scores["threshold"] <= 84
        threshold_neighborhood_passed += int(threshold_neighborhood)

        reference_candidate = root / "oracle" / "synthetic" / "reference.json"
        direct_reference = score_root(root, reference_candidate)
        adapter_reference = _adapter_report(root, reference_candidate)
        adapter_equal = canonical_report_bytes(direct_reference) == canonical_report_bytes(adapter_reference)
        adapter_passed += int(adapter_equal)

        roots[root_name] = {
            "scores": scores,
            "statuses": statuses,
            "score_spread": max(scores.values()) - min(scores.values()),
            "monotonic": all(scores[better] >= scores[worse] for better, worse in zip(order, order[1:])),
            "paraphrase_delta": paraphrase_delta,
            "adapter_matches_common_scorer": adapter_equal,
            "one_atom_locality": one_atom_locality,
            "one_atom_changed_components": changed_components,
            "threshold_neighborhood": threshold_neighborhood,
        }

    integrity_root = pack_root / "Fixtures" / ROOT_NAMES[0]
    integrity_report = score_root(integrity_root, integrity_root / "oracle" / "synthetic" / "integrity.json")
    integrity_probe_passed = (
        integrity_report["scoreable"]
        and integrity_report["status"] == "FAIL-INTEGRITY"
        and integrity_report["score"] is not None
        and integrity_report["penalty"] > 0
    )

    aggregate = {
        "root_count": len(ROOT_NAMES),
        "minimum_score": min(all_scores),
        "maximum_score": max(all_scores),
        "score_spread": max(all_scores) - min(all_scores),
        "unique_score_count": len(set(all_scores)),
        "intermediate_score_count": sum(0 < score < 100 for score in all_scores),
        "diagnostic_partial_count": sum(
            status == "PARTIAL" for root in roots.values() for status in root["statuses"].values()
        ),
        "monotonic_comparisons_passed": monotonic_passed,
        "monotonic_comparisons_total": monotonic_total,
        "max_paraphrase_delta": max(paraphrase_deltas),
        "mean_paraphrase_delta": sum(paraphrase_deltas) / len(paraphrase_deltas),
        "deterministic_replays_passed": deterministic_passed,
        "deterministic_replays_total": deterministic_total,
        "adapter_checks_passed": adapter_passed,
        "adapter_checks_total": len(ROOT_NAMES),
        "integrity_probe_passed": integrity_probe_passed,
        "one_atom_locality_checks_passed": one_atom_locality_passed,
        "one_atom_locality_checks_total": len(ROOT_NAMES),
        "threshold_neighborhood_checks_passed": threshold_neighborhood_passed,
        "threshold_neighborhood_checks_total": len(ROOT_NAMES),
    }

    if monotonic_passed != monotonic_total:
        raise RuntimeError("one or more synthetic ladders are not monotonic")
    if deterministic_passed != deterministic_total:
        raise RuntimeError("one or more reports changed across deterministic replay")
    if adapter_passed != len(ROOT_NAMES):
        raise RuntimeError("one or more per-root adapters differ from the common scorer")
    if not integrity_probe_passed:
        raise RuntimeError("structured integrity probe did not retain a numeric FAIL-INTEGRITY report")
    if one_atom_locality_passed != len(ROOT_NAMES):
        raise RuntimeError("one or more one-atom mutations changed the wrong score surface")
    if threshold_neighborhood_passed != len(ROOT_NAMES):
        raise RuntimeError("one or more 20-point deletions missed the 72..84 threshold neighborhood")

    return {
        "report_version": "v4-calibration-mechanism-1",
        "scope": "synthetic calibration only; no provider/model runs",
        "roots": roots,
        "aggregate": aggregate,
    }


def print_summary(summary: dict[str, Any]) -> None:
    print("| Root | Reference | Paraphrase | Strong | Threshold | Partial | Decoy | Vacuous | Para delta |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for root_name, result in summary["roots"].items():
        scores = result["scores"]
        print(
            f"| {root_name} | {scores['reference']:.2f} | {scores['paraphrase']:.2f} | "
            f"{scores['strong']:.2f} | {scores['threshold']:.2f} | {scores['partial']:.2f} | {scores['decoy']:.2f} | "
            f"{scores['vacuous']:.2f} | {result['paraphrase_delta']:.2f} |"
        )
    aggregate = summary["aggregate"]
    print(
        "Aggregate: spread={score_spread:.2f}; monotonic={monotonic_comparisons_passed}/"
        "{monotonic_comparisons_total}; paraphrase-max-delta={max_paraphrase_delta:.2f}; "
        "replay={deterministic_replays_passed}/{deterministic_replays_total}; "
        "adapters={adapter_checks_passed}/{adapter_checks_total}.".format(**aggregate)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the four v4 calibration-only roots.")
    default_pack = Path(__file__).resolve().parents[1]
    parser.add_argument("--pack-root", type=Path, default=default_pack)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    summary = validate_calibration(args.pack_root.resolve())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
