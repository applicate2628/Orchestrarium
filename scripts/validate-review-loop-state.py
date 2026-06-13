#!/usr/bin/env python3
"""Structural validator for a review-loop-state ledger.

The review-loop-state ledger is the per-round audit trail a SHIPPED autonomous
parallel-review-loop must persist (see the installed runtime bindings:
Claude `agents/contracts/review-loop.md`, Codex `skills/review-loop/SKILL.md`,
and the provider-neutral design trunk `shared/references/review-loop-methodology.md`).

This validator checks STRUCTURE ONLY. It deliberately does NOT and CANNOT check
semantics (whether the reasoning was sound, whether a blocker was real, whether a
PASS was justified) — that stays review territory. The honest boundary is:
structure is mechanically enforceable, soundness is not.

Structural assertions:
  - pinned `objective`, `scope`, `runtime_root` are present AND identical across
    every round (a round may re-pin them, but a re-pinned value must match);
  - at least one round is present and each round carries a non-empty `diff`;
  - each round carries BOTH verdict angles (`surgical`, `deep`) AND the `scout`;
  - no bare PASS — each verdict angle states a `verdict` of PASS or REVISE and
    cites either `blockers` (non-empty) or a `rationale`;
  - round numbers are >= 1 and <= the cap (default 3).

Ledger formats: JSON (stdlib) or YAML (only when PyYAML is importable). The
ledger root must be a mapping with top-level pinned anchors and a `rounds` list.

Usage:
  validate-review-loop-state.py <ledger.json|ledger.yaml> [--cap N]
  validate-review-loop-state.py --self-test
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_CAP = 3
PINNED_KEYS = ("objective", "scope", "runtime_root")
VERDICT_ANGLES = ("surgical", "deep")
VALID_VERDICTS = ("PASS", "REVISE")


def _load_yaml(text):
    try:
        import yaml  # type: ignore
    except Exception:
        return None, (
            "ledger looks like YAML but PyYAML is not importable; "
            "install PyYAML or supply a JSON ledger"
        )
    try:
        return yaml.safe_load(text), None
    except Exception as exc:  # pragma: no cover - exercised via bad YAML input
        return None, f"YAML parse error: {exc}"


def load_ledger(path):
    """Return (data, error). data is a dict on success, else None with error str."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read ledger '{path}': {exc}"

    suffix = Path(path).suffix.lower()
    if suffix in (".json",):
        try:
            return json.loads(text), None
        except json.JSONDecodeError as exc:
            return None, f"JSON parse error: {exc}"
    if suffix in (".yaml", ".yml"):
        return _load_yaml(text)

    # Unknown suffix: try JSON first (stdlib), then YAML as a fallback.
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        return _load_yaml(text)


def _verdict_errors(round_label, angle, block):
    errors = []
    if not isinstance(block, dict):
        errors.append(f"{round_label}: angle '{angle}' must be a mapping")
        return errors
    verdict = block.get("verdict")
    if verdict is None:
        errors.append(f"{round_label}: angle '{angle}' is missing 'verdict'")
    elif not isinstance(verdict, str) or verdict.strip().upper() not in VALID_VERDICTS:
        errors.append(
            f"{round_label}: angle '{angle}' verdict must be one of "
            f"{VALID_VERDICTS}, got {verdict!r}"
        )
    # Reject a bare PASS / REVISE: require blockers or a rationale.
    blockers = block.get("blockers")
    rationale = block.get("rationale")
    has_blockers = isinstance(blockers, (list, tuple)) and len(blockers) > 0
    has_rationale = isinstance(rationale, str) and rationale.strip() != ""
    if not has_blockers and not has_rationale:
        errors.append(
            f"{round_label}: angle '{angle}' is a bare verdict — it must cite "
            "non-empty 'blockers' or a specific 'rationale'"
        )
    return errors


def _scout_errors(round_label, scout):
    errors = []
    if not isinstance(scout, dict):
        errors.append(f"{round_label}: 'scout' must be a mapping")
        return errors
    if "findings" not in scout:
        errors.append(f"{round_label}: 'scout' is missing 'findings'")
    elif not isinstance(scout.get("findings"), (list, tuple)):
        errors.append(f"{round_label}: 'scout.findings' must be a list")
    # The scout must not smuggle in a verdict — it feeds the verdicts, it does
    # not cast one.
    if "verdict" in scout:
        errors.append(
            f"{round_label}: 'scout' must not carry a 'verdict' — the scout "
            "feeds the verdict angles, it does not co-judge"
        )
    return errors


def validate(data, cap=DEFAULT_CAP):
    """Return a list of structural error strings (empty list == valid)."""
    errors = []
    if not isinstance(data, dict):
        return ["ledger root must be a mapping/object"]

    # 1. Top-level pinned anchors present and non-empty.
    pinned = {}
    for key in PINNED_KEYS:
        value = data.get(key)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            errors.append(f"top-level pinned anchor '{key}' is missing or empty")
        else:
            pinned[key] = value

    rounds = data.get("rounds")
    if not isinstance(rounds, (list, tuple)) or len(rounds) == 0:
        errors.append("'rounds' must be a non-empty list")
        return errors

    if len(rounds) > cap:
        errors.append(
            f"round count {len(rounds)} exceeds cap {cap}"
        )

    seen_round_numbers = []
    for idx, rnd in enumerate(rounds):
        label = f"round[{idx}]"
        if not isinstance(rnd, dict):
            errors.append(f"{label}: each round must be a mapping")
            continue

        number = rnd.get("round")
        if number is not None:
            label = f"round {number}"
            if not isinstance(number, int) or number < 1:
                errors.append(f"{label}: 'round' must be an integer >= 1")
            elif number > cap:
                errors.append(f"{label}: 'round' {number} exceeds cap {cap}")
            else:
                seen_round_numbers.append(number)

        # 2. Pinned anchors identical across rounds: a round may re-pin, but the
        #    re-pinned value must match the top-level pinned value.
        for key in PINNED_KEYS:
            if key in rnd and key in pinned and rnd[key] != pinned[key]:
                errors.append(
                    f"{label}: pinned anchor '{key}' differs from the top-level "
                    "pinned value (anchors must be identical across all rounds)"
                )

        # 3. Per-round diff present and non-empty.
        diff = rnd.get("diff")
        if diff is None or (isinstance(diff, str) and diff.strip() == ""):
            errors.append(f"{label}: per-round 'diff' is missing or empty")

        # 4. Both verdict angles present, no bare PASS.
        for angle in VERDICT_ANGLES:
            if angle not in rnd:
                errors.append(f"{label}: missing verdict angle '{angle}'")
            else:
                errors.extend(_verdict_errors(label, angle, rnd[angle]))

        # 5. Scout present, casts no verdict.
        if "scout" not in rnd:
            errors.append(f"{label}: missing the mechanical 'scout'")
        else:
            errors.extend(_scout_errors(label, rnd["scout"]))

    return errors


def _sample_good():
    return {
        "objective": "stop the editor freezing on first Ctrl+E",
        "scope": "EditWorkspaceView warm-up path only",
        "runtime_root": "trace 2026-06-03: first-layout shaping of 2525 words at real bounds",
        "rounds": [
            {
                "round": 1,
                "diff": "initial artifact",
                "surgical": {
                    "verdict": "REVISE",
                    "blockers": ["TextBox is empty at synthetic-mount: editWorkspace.DataContext == null (EditWorkspaceView.xaml.cs:88)"],
                    "root_proven": "yes — trace captured this session",
                    "scope_unchanged": "yes",
                    "verification_adequate": "no — needs a real-bounds trace marker",
                },
                "deep": {
                    "verdict": "REVISE",
                    "blockers": ["needs an explicit 'edit surface completes first real-bounds layout before first activation' invariant"],
                    "root_proven": "yes",
                    "scope_unchanged": "yes",
                    "verification_adequate": "partial",
                },
                "scout": {
                    "findings": ["SourceText binding resolves only on first Ctrl+E (bridge.cs:142)"],
                    "reconciliation": ["folded into the surgical blocker about empty-at-mount"],
                },
                "evidence": [".scratch/reviews/round1-codex.out"],
            },
            {
                "round": 2,
                "diff": "added real-bounds pre-measure + the completion invariant answering both round-1 blockers",
                "surgical": {
                    "verdict": "PASS",
                    "rationale": "empty-at-mount addressed: pre-measure now runs after DataContext is set",
                    "root_proven": "yes",
                    "scope_unchanged": "yes",
                    "verification_adequate": "yes — trace marker added",
                },
                "deep": {
                    "verdict": "PASS",
                    "blockers": [],
                    "rationale": "invariant present; blast radius confined to the warm-up path",
                    "root_proven": "yes",
                    "scope_unchanged": "yes",
                    "verification_adequate": "yes",
                },
                "scout": {
                    "findings": [],
                    "reconciliation": [],
                },
                "evidence": [".scratch/reviews/round2-codex.out"],
            },
        ],
    }


def _sample_bad():
    # Defects: runtime_root missing; round 2 mutates the objective (drift);
    # round 1 surgical is a BARE PASS; round 2 has no scout; round 3 exceeds cap.
    return {
        "objective": "stop the editor freezing on first Ctrl+E",
        "scope": "EditWorkspaceView warm-up path only",
        "rounds": [
            {
                "round": 1,
                "diff": "initial artifact",
                "surgical": {"verdict": "PASS"},
                "deep": {
                    "verdict": "REVISE",
                    "blockers": ["needs an invariant"],
                },
                "scout": {"findings": []},
            },
            {
                "round": 2,
                "objective": "rewrite the entire editor with AvaloniaEdit",
                "diff": "",
                "surgical": {"verdict": "PASS", "rationale": "ok"},
                "deep": {"verdict": "PASS", "rationale": "ok"},
            },
            {
                "round": 4,
                "diff": "fourth round",
                "surgical": {"verdict": "PASS", "rationale": "ok"},
                "deep": {"verdict": "PASS", "rationale": "ok"},
                "scout": {"findings": []},
            },
        ],
    }


def self_test():
    failures = []

    good_errors = validate(_sample_good())
    if good_errors:
        failures.append(
            "sample-good ledger was rejected but should pass:\n  - "
            + "\n  - ".join(good_errors)
        )

    bad_errors = validate(_sample_bad())
    if not bad_errors:
        failures.append("sample-bad ledger was accepted but should be rejected")

    if failures:
        print("SELF-TEST FAIL")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print("SELF-TEST PASS")
    print(f"  sample-good: accepted (0 structural errors)")
    print(f"  sample-bad:  rejected ({len(bad_errors)} structural errors)")
    return 0


def main(argv):
    parser = argparse.ArgumentParser(
        description="Structural validator for a review-loop-state ledger (structure only, never semantics).",
    )
    parser.add_argument("ledger", nargs="?", help="path to a review-loop-state ledger (JSON or YAML)")
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP, help=f"max rounds (default {DEFAULT_CAP})")
    parser.add_argument("--self-test", action="store_true", help="validate a sample-good and reject a sample-bad ledger")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.ledger:
        parser.error("a ledger path is required unless --self-test is given")

    data, load_error = load_ledger(args.ledger)
    if load_error:
        print(f"FAIL: {load_error}")
        return 1

    errors = validate(data, cap=args.cap)
    if errors:
        print(f"FAIL: review-loop-state ledger '{args.ledger}' has {len(errors)} structural error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"PASS: review-loop-state ledger '{args.ledger}' is structurally valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
