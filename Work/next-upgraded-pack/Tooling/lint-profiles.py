#!/usr/bin/env python3
"""Lint the profile registry (`Instrument/profiles.yaml`).

Phase-1 harness item S1 (BUILD-PLAN-v2.1.md). The registry maps the 4 canonical C4-vocabulary
profile tokens to the provider + model + effort that runs them plus a one-line construct
definition. Model bindings live ONLY in that file (fable's staleness objection); this linter is the
guard that keeps the registry shape trustworthy for every downstream reader (H7 runner row configs,
S2 discrimination.yaml `eligible_profiles`, the aggregator's I5 tables).

Checks:
  * top-level `schema: profiles-v1` key present.
  * `profiles` is a mapping whose key set is EXACTLY the 4 canonical tokens (systemic-mgmt, stamina,
    ultimate-depth, working-audit) -- no missing token, no unknown/typo'd token.
  * each profile entry has:
      - `provider` in {claude, codex}
      - `model`: non-empty string
      - `effort`: non-empty string, and (per this build pass's operator input) equal to "xhigh"
      - `construct`: non-empty string, single physical line (no embedded newline)
  * `measurability`, if present, is one of {pf-measurable, assumption-unverified} (advisory field;
    not required, but must not silently hold a typo'd value if authored).

Usage:
  python lint-profiles.py [--file <path to profiles.yaml>]

Exit 0 with "LINT-OK" on a clean registry; exit 1 with one "LINT-FAIL: ..." line per violation on
stderr (all violations are collected and reported together, not fail-fast on the first one).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment guard, not a logic branch
    print(f"LINT-FAIL: PyYAML is required to lint profiles.yaml ({exc})", file=sys.stderr)
    raise SystemExit(2)

CANONICAL_TOKENS = ("systemic-mgmt", "stamina", "ultimate-depth", "working-audit")
VALID_PROVIDERS = ("claude", "codex")
VALID_MEASURABILITY = ("pf-measurable", "assumption-unverified")
REQUIRED_EFFORT = "xhigh"

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "Instrument" / "profiles.yaml"


def lint(data: object) -> list[str]:
    """Return a list of violation messages; empty means the registry is clean."""
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["registry root is not a mapping"]

    if data.get("schema") != "profiles-v1":
        errors.append(f"top-level 'schema' must equal 'profiles-v1', got {data.get('schema')!r}")

    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        errors.append("top-level 'profiles' key missing or not a mapping")
        return errors  # nothing further is checkable

    present = set(profiles.keys())
    missing = [t for t in CANONICAL_TOKENS if t not in present]
    unknown = sorted(present - set(CANONICAL_TOKENS))
    if missing:
        errors.append(f"missing required profile token(s): {missing}")
    if unknown:
        errors.append(f"unknown/unexpected profile token(s) (typo against C4 vocabulary?): {unknown}")

    for token in CANONICAL_TOKENS:
        if token not in profiles:
            continue  # already reported as missing
        entry = profiles[token]
        if not isinstance(entry, dict):
            errors.append(f"profiles.{token}: entry is not a mapping")
            continue

        provider = entry.get("provider")
        if provider not in VALID_PROVIDERS:
            errors.append(f"profiles.{token}.provider must be one of {VALID_PROVIDERS}, got {provider!r}")

        model = entry.get("model")
        if not isinstance(model, str) or not model.strip():
            errors.append(f"profiles.{token}.model missing or empty")

        effort = entry.get("effort")
        if not isinstance(effort, str) or not effort.strip():
            errors.append(f"profiles.{token}.effort missing or empty")
        elif effort != REQUIRED_EFFORT:
            errors.append(f"profiles.{token}.effort must equal {REQUIRED_EFFORT!r}, got {effort!r}")

        construct = entry.get("construct")
        if not isinstance(construct, str) or not construct.strip():
            errors.append(f"profiles.{token}.construct missing or empty")
        elif "\n" in construct.strip("\n"):
            errors.append(f"profiles.{token}.construct must be a single line")

        measurability = entry.get("measurability")
        if measurability is not None and measurability not in VALID_MEASURABILITY:
            errors.append(
                f"profiles.{token}.measurability must be one of {VALID_MEASURABILITY} or absent, "
                f"got {measurability!r}"
            )

    return errors


def lint_file(path: Path) -> list[str]:
    if not path.is_file():
        return [f"registry file not found: {path}"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"registry file is not valid YAML: {exc}"]
    return lint(data)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lint the S1 profile registry (profiles.yaml).")
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    args = ap.parse_args(argv)

    errors = lint_file(args.file)
    if errors:
        for msg in errors:
            print(f"LINT-FAIL: {msg}", file=sys.stderr)
        print(f"LINT-FAIL: {len(errors)} violation(s) in {args.file}", file=sys.stderr)
        return 1

    print(f"LINT-OK: {args.file} -- {len(CANONICAL_TOKENS)} profile tokens valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
