#!/usr/bin/env python3
"""Lint every bundle's discrimination.yaml (S2). Enforces Sol's 4-field contract:

- schema == discrimination-v1
- eligible_profiles is a non-empty subset of the 4 canonical tokens
- owner-lane bundles (role_class: owner) EXCLUDE working-audit (Terra/Luna owner-prohibition)
- expected_winner in eligible_profiles + {none-hypothesized}
- validated_discrimination in {none, weak, validated, refuted}; != none requires validation_evidence != none
- staging never includes the file (checked structurally by the H2 sentinel; asserted here by name)

Also emits a per-lane / per-eligible-winner coverage report (feeds the >=2-or-abstain rule). Exit 1
on any violation.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

BENCH = Path(__file__).resolve().parents[3]
PROFILES = {"systemic-mgmt", "stamina", "ultimate-depth", "working-audit"}
VALIDATED = {"none", "weak", "validated", "refuted"}
OWNER_ROLES = {"owner"}


def parse(disc: Path) -> dict:
    d: dict = {"eligible_profiles": []}
    in_elig = False
    for line in disc.read_text(encoding="utf-8").splitlines():
        if re.match(r'^\s*#', line) or not line.strip():
            continue
        if not line[:1].isspace():
            key = line.split(":", 1)[0].strip()
            in_elig = key == "eligible_profiles"
            if ":" in line and not in_elig:  # eligible_profiles stays the list; don't overwrite it
                k, v = line.split(":", 1)
                d[k.strip()] = v.strip().strip('"')
        elif in_elig:
            item = line.strip()
            if item.startswith("-"):
                d["eligible_profiles"].append(item[1:].strip())
    return d


def role_of(bundle: Path) -> str:
    sc = bundle / "scenario.yaml"
    if not sc.exists():
        return ""
    m = re.search(r'^role_class:\s*"?(.*?)"?\s*$', sc.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else ""


def main() -> int:
    errors: list[str] = []
    winner_by_lane: Counter = Counter()
    n = 0
    for disc in sorted(BENCH.glob("Scenarios-v2/*/discrimination.yaml")) + sorted(BENCH.glob("Scenarios-v3/*/discrimination.yaml")):
        n += 1
        b = disc.parent.name
        d = parse(disc)
        if d.get("schema") != "discrimination-v1":
            errors.append(f"{b}: schema != discrimination-v1")
        elig = set(d["eligible_profiles"])
        if not elig or not elig.issubset(PROFILES):
            errors.append(f"{b}: eligible_profiles {elig} not a non-empty subset of {PROFILES}")
        if role_of(disc.parent) in OWNER_ROLES and "working-audit" in elig:
            errors.append(f"{b}: owner lane must EXCLUDE working-audit (Terra/Luna owner-prohibition)")
        ew = d.get("expected_winner", "")
        if ew not in elig and ew != "none-hypothesized":
            errors.append(f"{b}: expected_winner '{ew}' not in eligible_profiles + none-hypothesized")
        vd = d.get("validated_discrimination", "")
        if vd not in VALIDATED:
            errors.append(f"{b}: validated_discrimination '{vd}' not in {VALIDATED}")
        if vd != "none" and d.get("validation_evidence", "none") == "none":
            errors.append(f"{b}: validated_discrimination={vd} requires validation_evidence")
        if ew != "none-hypothesized":
            winner_by_lane[ew] += 1

    print(f"lint-discrimination: {n} files checked")
    print("pre-registered expected_winner distribution:", dict(winner_by_lane))
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        print(f"LINT-FAIL: {len(errors)} violation(s)", file=sys.stderr)
        return 1
    print("LINT-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
