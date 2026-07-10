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
  - each angle (`surgical`, `deep`, `scout`) carries a non-empty `attempt_id`, and
    the three current attempt IDs are unique within a round (A5b: a died/errored
    lane must be re-dispatched under a fresh attempt, not folded into silence);
  - `lane_failures` is present as a list (`[]` when none failed); each entry names
    exactly `lane` (one of surgical/deep/scout), the failed `attempt_id`, a
    `failure` kind (`error | died | limit`), and a `redispatched_as` that differs
    from the failed attempt AND equals that lane's current `attempt_id` — the
    successful re-dispatch that supersedes the failure (A5b fail-closed
    reconciliation);
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
ALL_ANGLES = ("surgical", "deep", "scout")
VALID_VERDICTS = ("PASS", "REVISE")
VALID_LANES = ("surgical", "deep", "scout")
VALID_FAILURES = ("error", "died", "limit")
LANE_FAILURE_FIELDS = ("lane", "attempt_id", "failure", "redispatched_as")


def _nonempty_id(value):
    """True iff value is a present, non-empty id scalar (non-empty str or any non-None non-str scalar)."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _norm_id(value):
    """Normalize an id for comparison (strip strings; pass non-strings through)."""
    return value.strip() if isinstance(value, str) else value


def _angle_attempt_id(round_label, angle, block, errors):
    """Return the normalized non-empty attempt_id for an angle block, or None (recording an error)."""
    if not isinstance(block, dict):
        return None  # a non-dict block is already flagged elsewhere
    aid = block.get("attempt_id")
    if not _nonempty_id(aid):
        errors.append(f"{round_label}: angle '{angle}' is missing a non-empty 'attempt_id'")
        return None
    return _norm_id(aid)


def _lane_failure_errors(round_label, lane_failures, current_attempt_ids):
    """Validate the round's `lane_failures` list against A5b fail-closed reconciliation."""
    errors = []
    if lane_failures is None:
        errors.append(
            f"{round_label}: 'lane_failures' is required (use [] when no lane failed)"
        )
        return errors
    if not isinstance(lane_failures, (list, tuple)):
        errors.append(f"{round_label}: 'lane_failures' must be a list")
        return errors
    for j, lf in enumerate(lane_failures):
        lbl = f"{round_label} lane_failures[{j}]"
        if not isinstance(lf, dict):
            errors.append(f"{lbl}: each lane_failure must be a mapping")
            continue
        missing = [k for k in LANE_FAILURE_FIELDS if k not in lf]
        if missing:
            errors.append(f"{lbl}: missing field(s) {missing}")
        extra = [k for k in lf if k not in LANE_FAILURE_FIELDS]
        if extra:
            errors.append(
                f"{lbl}: unexpected field(s) {extra}; exactly {list(LANE_FAILURE_FIELDS)} required"
            )
        lane = lf.get("lane")
        if lane not in VALID_LANES:
            errors.append(f"{lbl}: 'lane' must be one of {VALID_LANES}, got {lane!r}")
        failure = lf.get("failure")
        if failure not in VALID_FAILURES:
            errors.append(f"{lbl}: 'failure' must be one of {VALID_FAILURES}, got {failure!r}")
        failed_aid = lf.get("attempt_id")
        redispatched = lf.get("redispatched_as")
        if not _nonempty_id(failed_aid):
            errors.append(f"{lbl}: 'attempt_id' (the failed attempt) must be non-empty")
        if not _nonempty_id(redispatched):
            errors.append(f"{lbl}: 'redispatched_as' must be non-empty")
        if _nonempty_id(failed_aid) and _nonempty_id(redispatched) and _norm_id(failed_aid) == _norm_id(redispatched):
            errors.append(
                f"{lbl}: 'attempt_id' (failed) and 'redispatched_as' (successful) must differ"
            )
        # Fail-closed reconciliation: the re-dispatch must be this lane's current attempt.
        if lane in VALID_LANES and _nonempty_id(redispatched):
            if lane not in current_attempt_ids:
                errors.append(
                    f"{lbl}: lane '{lane}' has a recorded failure but no current "
                    "attempt_id to reconcile against (the re-dispatch is unverified)"
                )
            elif _norm_id(redispatched) != current_attempt_ids[lane]:
                errors.append(
                    f"{lbl}: 'redispatched_as' {redispatched!r} must equal the current "
                    f"'{lane}' attempt_id {current_attempt_ids[lane]!r} — the successful "
                    "re-dispatch that supersedes the failure (unreconciled failed lane)"
                )
    return errors


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

        # 4. Both verdict angles present, no bare PASS, each with an attempt_id.
        current_attempt_ids = {}
        for angle in VERDICT_ANGLES:
            if angle not in rnd:
                errors.append(f"{label}: missing verdict angle '{angle}'")
            else:
                errors.extend(_verdict_errors(label, angle, rnd[angle]))
                aid = _angle_attempt_id(label, angle, rnd[angle], errors)
                if aid is not None:
                    current_attempt_ids[angle] = aid

        # 5. Scout present, casts no verdict, carries an attempt_id.
        if "scout" not in rnd:
            errors.append(f"{label}: missing the mechanical 'scout'")
        else:
            errors.extend(_scout_errors(label, rnd["scout"]))
            aid = _angle_attempt_id(label, "scout", rnd["scout"], errors)
            if aid is not None:
                current_attempt_ids["scout"] = aid

        # 5b. The three current attempt_ids must be unique within a round (A5b: a
        #     re-dispatched lane gets a fresh attempt, distinct from its siblings).
        present_ids = [current_attempt_ids[a] for a in ALL_ANGLES if a in current_attempt_ids]
        dup_ids = sorted({str(v) for v in present_ids if present_ids.count(v) > 1})
        if dup_ids:
            errors.append(
                f"{label}: angle attempt_id values must be unique within a round; "
                f"duplicated {dup_ids}"
            )

        # 6. lane_failures: fail-closed reconciliation of died/errored lanes.
        errors.extend(_lane_failure_errors(label, rnd.get("lane_failures"), current_attempt_ids))

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
                    "attempt_id": "surgical-r1",
                    "verdict": "REVISE",
                    "blockers": ["TextBox is empty at synthetic-mount: editWorkspace.DataContext == null (EditWorkspaceView.xaml.cs:88)"],
                    "root_proven": "yes — trace captured this session",
                    "scope_unchanged": "yes",
                    "verification_adequate": "no — needs a real-bounds trace marker",
                },
                "deep": {
                    "attempt_id": "deep-r1",
                    "verdict": "REVISE",
                    "blockers": ["needs an explicit 'edit surface completes first real-bounds layout before first activation' invariant"],
                    "root_proven": "yes",
                    "scope_unchanged": "yes",
                    "verification_adequate": "partial",
                },
                "scout": {
                    "attempt_id": "scout-r1",
                    "findings": ["SourceText binding resolves only on first Ctrl+E (bridge.cs:142)"],
                    "reconciliation": ["folded into the surgical blocker about empty-at-mount"],
                },
                "lane_failures": [],
                "evidence": [".scratch/reviews/round1-codex.out"],
            },
            {
                "round": 2,
                "diff": "added real-bounds pre-measure + the completion invariant answering both round-1 blockers",
                "surgical": {
                    "attempt_id": "surgical-r2",
                    "verdict": "PASS",
                    "rationale": "empty-at-mount addressed: pre-measure now runs after DataContext is set",
                    "root_proven": "yes",
                    "scope_unchanged": "yes",
                    "verification_adequate": "yes — trace marker added",
                },
                "deep": {
                    "attempt_id": "deep-r2",
                    "verdict": "PASS",
                    "blockers": [],
                    "rationale": "invariant present; blast radius confined to the warm-up path",
                    "root_proven": "yes",
                    "scope_unchanged": "yes",
                    "verification_adequate": "yes",
                },
                "scout": {
                    "attempt_id": "scout-r2",
                    "findings": [],
                    "reconciliation": [],
                },
                "lane_failures": [],
                "evidence": [".scratch/reviews/round2-codex.out"],
            },
        ],
    }


def _sample_good_redispatch():
    """A valid single-round ledger where the scout lane died and was re-dispatched
    under a fresh attempt reconciled by `lane_failures` (A5b happy path)."""
    return {
        "objective": "stop the editor freezing on first Ctrl+E",
        "scope": "EditWorkspaceView warm-up path only",
        "runtime_root": "trace 2026-06-03: first-layout shaping of 2525 words at real bounds",
        "rounds": [
            {
                "round": 1,
                "diff": "initial artifact",
                "surgical": {
                    "attempt_id": "surgical-r1",
                    "verdict": "REVISE",
                    "blockers": ["empty-at-mount (EditWorkspaceView.xaml.cs:88)"],
                },
                "deep": {
                    "attempt_id": "deep-r1",
                    "verdict": "REVISE",
                    "blockers": ["needs a completion invariant"],
                },
                "scout": {
                    "attempt_id": "scout-r1-retry",
                    "findings": ["SourceText binds only on first Ctrl+E (bridge.cs:142)"],
                    "reconciliation": ["folded into the surgical blocker"],
                },
                "lane_failures": [
                    {
                        "lane": "scout",
                        "attempt_id": "scout-r1",
                        "failure": "died",
                        "redispatched_as": "scout-r1-retry",
                    }
                ],
                "evidence": [".scratch/reviews/round1-scout-retry.out"],
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


def _valid_round(**over):
    """A minimal structurally-valid round (attempt IDs unique, lane_failures empty)."""
    rnd = {
        "round": 1,
        "diff": "initial artifact",
        "surgical": {"attempt_id": "s1", "verdict": "REVISE", "blockers": ["b (f.cs:1)"]},
        "deep": {"attempt_id": "d1", "verdict": "REVISE", "blockers": ["needs invariant"]},
        "scout": {"attempt_id": "sc1", "findings": []},
        "lane_failures": [],
    }
    rnd.update(over)
    return rnd


def _ledger(rnd):
    return {"objective": "o", "scope": "sc", "runtime_root": "r", "rounds": [rnd]}


def _fixture_null_verdict():
    return _ledger(_valid_round(surgical={"attempt_id": "s1", "verdict": None, "blockers": ["b"]}))


def _fixture_missing_lane():
    rnd = _valid_round()
    rnd.pop("deep")  # a dispatched verdict lane is silently absent
    return _ledger(rnd)


def _fixture_null_findings():
    return _ledger(_valid_round(scout={"attempt_id": "sc1", "findings": None}))


def _fixture_unresolved_failure():
    # A scout lane died but its recorded re-dispatch does not match the current
    # scout attempt_id — the failure is never reconciled (fail-closed => reject).
    return _ledger(_valid_round(lane_failures=[
        {"lane": "scout", "attempt_id": "sc0", "failure": "died", "redispatched_as": "sc-nope"},
    ]))


def _fixture_wrong_lane_redispatch():
    # A surgical failure whose re-dispatch points at another lane's attempt id
    # (deep's), not surgical's current attempt id.
    return _ledger(_valid_round(lane_failures=[
        {"lane": "surgical", "attempt_id": "s0", "failure": "error", "redispatched_as": "d1"},
    ]))


def _fixture_missing_attempt_id():
    return _ledger(_valid_round(surgical={"verdict": "REVISE", "blockers": ["b"]}))


def _fixture_duplicate_attempt_id():
    return _ledger(_valid_round(deep={"attempt_id": "s1", "verdict": "REVISE", "blockers": ["b"]}))


def self_test():
    failures = []

    good_cases = {
        "sample-good": _sample_good(),
        "sample-good-redispatch": _sample_good_redispatch(),
    }
    for name, ledger in good_cases.items():
        errs = validate(ledger)
        if errs:
            failures.append(
                f"{name} ledger was rejected but should pass:\n  - " + "\n  - ".join(errs)
            )

    bad_cases = {
        "sample-bad": _sample_bad(),
        "null-verdict": _fixture_null_verdict(),
        "missing-lane": _fixture_missing_lane(),
        "null-findings": _fixture_null_findings(),
        "unresolved-failure": _fixture_unresolved_failure(),
        "wrong-lane-redispatch": _fixture_wrong_lane_redispatch(),
        "missing-attempt-id": _fixture_missing_attempt_id(),
        "duplicate-attempt-id": _fixture_duplicate_attempt_id(),
    }
    bad_counts = {}
    for name, ledger in bad_cases.items():
        errs = validate(ledger)
        bad_counts[name] = len(errs)
        if not errs:
            failures.append(f"{name} ledger was accepted but should be rejected")

    if failures:
        print("SELF-TEST FAIL")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print("SELF-TEST PASS")
    for name in good_cases:
        print(f"  {name}: accepted (0 structural errors)")
    for name, n in bad_counts.items():
        print(f"  {name}: rejected ({n} structural error(s))")
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
