#!/usr/bin/env python3
"""S2 scaffold: write a discrimination.yaml (Sol's 4-field schema) into every bundle that lacks one.

Sol's 4-field replacement for the circular `discriminates_profile`: target_construct (task demand) /
eligible_profiles (policy — owner lanes exclude working-audit, the Terra/Luna owner-prohibition) /
expected_winner (pre-run hypothesis; v2 slots start none-hypothesized) / validated_discrimination
(post-run, starts none). Lives in a SEPARATE bundle-root file — never staged to the provider root
(H2 stages only inputs/candidate/README/scenario.yaml) so expected_winner is never candidate-visible.

Idempotent: skips any bundle that already has a discrimination.yaml (the new v3 families carry their
own pre-registered winners). Binary-mode write (Windows LF).
"""
from __future__ import annotations

import re
from pathlib import Path

BENCH = Path(__file__).resolve().parents[3]
PROFILES = ("systemic-mgmt", "stamina", "ultimate-depth", "working-audit")


def flat_get(scenario_yaml: Path, key: str) -> str:
    for line in scenario_yaml.read_text(encoding="utf-8").splitlines():
        m = re.match(rf'^{key}:\s*"?(.*?)"?\s*$', line)
        if m:
            return m.group(1).strip()
    return ""


def render(role_class: str, target: str) -> str:
    # Owner lanes exclude working-audit (Terra): the hard Terra/Luna owner-prohibition policy invariant.
    eligible = [p for p in PROFILES if not (role_class == "owner" and p == "working-audit")]
    excl = "  # owner lane: working-audit (Terra) excluded — Terra/Luna owner-prohibition invariant\n" if role_class == "owner" else ""
    lines = [
        "schema: discrimination-v1",
        f'target_construct: "{target}"',
        "eligible_profiles:",
    ]
    body = "\n".join(lines) + "\n"
    body += excl
    body += "".join(f"  - {p}\n" for p in eligible)
    body += (
        "expected_winner: none-hypothesized\n"
        "expected_winner_registered: 2026-07-12\n"
        "validated_discrimination: none\n"
        "validation_evidence: none\n"
    )
    return body


def main() -> int:
    written = skipped = 0
    for scenario in sorted(BENCH.glob("Scenarios-v2/*/scenario.yaml")) + sorted(BENCH.glob("Scenarios-v3/*/scenario.yaml")):
        bundle = scenario.parent
        disc = bundle / "discrimination.yaml"
        if disc.exists():
            skipped += 1
            continue
        role_class = flat_get(scenario, "role_class") or "implementation"
        target = flat_get(scenario, "modality_family") or flat_get(scenario, "artifact_type") or bundle.name
        disc.write_bytes(render(role_class, target).encode("utf-8"))
        written += 1
    print(f"S2 scaffold: {written} written, {skipped} skipped (already had discrimination.yaml)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
