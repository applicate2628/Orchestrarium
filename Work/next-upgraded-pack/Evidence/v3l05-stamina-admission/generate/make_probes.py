#!/usr/bin/env python3
"""Materialise probe candidates for a V3L05 variant by applying the documented
mechanical migration to selected consumers (and, for the adversarial probe, also
corrupting the decoys). Deterministic; reads the hidden oracle to know which
functions are consumers/decoys.

Usage:
  python make_probes.py --root <bundleRoot> --out <candidateDir> --mode <mode> [--fraction F]
    modes: reference | partial | visible_only | decoy_blanket | keyword_stuffed
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

LEGACY_RETURN = '    return {"account": account, "amount": amount}'
MIGRATED_RETURN = ('    return {"account": account, "amount": amount, '
                   '"region": REGION, "currency": CURRENCY, "source": LEDGER_V2_SOURCE}')


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--mode", required=True)
    p.add_argument("--fraction", type=float, default=1.0)
    return p.parse_args()


def migration_order(consumers):
    # anchors first (so visible tests pass in partial mode), then by func name.
    anchors = [c for c in consumers if c["func"].startswith("quote_anchor_")]
    rest = sorted((c for c in consumers if not c["func"].startswith("quote_anchor_")),
                  key=lambda c: c["func"])
    return anchors + rest


def migrate_module_text(text: str, migrate_funcs: set, corrupt_report: set, corrupt_audit: set) -> str:
    lines = text.splitlines()
    out = []
    current = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def ") and stripped.endswith("():"):
            current = stripped[4:-3]
        if line == LEGACY_RETURN and current in migrate_funcs:
            out.append(MIGRATED_RETURN)
            continue
        if current in corrupt_report and stripped.startswith("return {") and '"source": "report-v2"' in line:
            out.append(line.replace('"source": "report-v2"', '"source": LEDGER_V2_SOURCE'))
            continue
        if current in corrupt_audit and stripped.startswith('return {"account": account, "ts":'):
            # blanket-edit also appends the v2 fields to the audit decoy
            new = line.rstrip()[:-1] + ', "region": REGION, "currency": CURRENCY, "source": LEDGER_V2_SOURCE}'
            out.append(new)
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def main() -> int:
    args = parse_args()
    contract = json.loads((args.root / "oracle" / "stamina-contract.json").read_text(encoding="utf-8"))
    consumers = contract["consumers"]
    report_decoys = contract["report_decoys"]
    audit_decoys = contract["audit_decoys"]

    if args.out.exists():
        shutil.rmtree(args.out)
    shutil.copytree(args.root / "candidate", args.out)

    ordered = migration_order(consumers)
    if args.mode == "reference":
        selected = {c["func"] for c in ordered}
    elif args.mode == "partial":
        k = math.ceil(args.fraction * len(ordered))
        selected = {c["func"] for c in ordered[:k]}
    elif args.mode == "visible_only":
        selected = {c["func"] for c in ordered if c["func"].startswith("quote_anchor_")}
    elif args.mode == "keyword_stuffed":
        # No code migration at all; only stuff the ledger with the right keywords.
        selected = set()
    elif args.mode == "decoy_blanket":
        selected = {c["func"] for c in ordered}  # all consumers migrated...
    else:
        raise SystemExit(f"unknown mode {args.mode}")

    corrupt_report = set()
    corrupt_audit = set()
    if args.mode == "decoy_blanket":
        corrupt_report = {d["func"] for d in report_decoys}
        corrupt_audit = {d["func"] for d in audit_decoys}

    ws = args.out / "workspace" / "src" / "ledgerkit"
    # group selected/corrupt by module for efficiency
    by_module = {}
    for c in consumers:
        by_module.setdefault(c["module"], {"mig": set(), "cr": set(), "ca": set()})
        if c["func"] in selected:
            by_module[c["module"]]["mig"].add(c["func"])
    for d in report_decoys:
        by_module.setdefault(d["module"], {"mig": set(), "cr": set(), "ca": set()})
        if d["func"] in corrupt_report:
            by_module[d["module"]]["cr"].add(d["func"])
    for d in audit_decoys:
        by_module.setdefault(d["module"], {"mig": set(), "cr": set(), "ca": set()})
        if d["func"] in corrupt_audit:
            by_module[d["module"]]["ca"].add(d["func"])

    for mod, sel in by_module.items():
        path = ws / f"{mod}.py"
        text = path.read_text(encoding="utf-8")
        path.write_text(migrate_module_text(text, sel["mig"], sel["cr"], sel["ca"]),
                        encoding="utf-8", newline="\n")

    # Ledger: for keyword_stuffed, cram every required-looking term; for others, a plausible ledger.
    ledger_path = args.out / "refactor-ledger.json"
    migrated = sorted(selected)
    if args.mode == "keyword_stuffed":
        ledger = {
            "contractId": f"{contract['scenario_id']}-stamina-migration",
            "changedFiles": [f"candidate/workspace/src/ledgerkit/{m}.py" for m in sorted({c['module'] for c in consumers})],
            "migratedConsumers": [c["func"] for c in consumers],  # CLAIMS all, but code untouched
            "notes": "ledger-v2 region currency source migration complete quote consumer breadth caller compatibility",
        }
    else:
        ledger = {
            "contractId": f"{contract['scenario_id']}-stamina-migration",
            "changedFiles": [f"candidate/workspace/src/ledgerkit/{m}.py" for m in sorted(by_module) if by_module[m]["mig"] or by_module[m]["cr"] or by_module[m]["ca"]],
            "migratedConsumers": migrated,
            "notes": "ledger-v2 migration",
        }
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"mode={args.mode} migrated={len(selected)}/{len(consumers)} corrupt_report={len(corrupt_report)} corrupt_audit={len(corrupt_audit)} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
