#!/usr/bin/env python3
"""Deterministic generator for the V3L05 stamina-migration family (F1).

Materialises three matched sub-roots (s/m/l) of ONE homogeneous mechanical
contract migration across N scattered consumers, with decoys, randomized
consumer order per variant, and a hidden-consumer oracle. Same per-consumer
depth in every variant; variants differ ONLY in consumer count.

Run: python gen_stamina.py <benchmarks-root>
Writes committed STARTER roots into <root>/Scenarios-v3/V3L05-stamina-migration-{s,m,l}/
Idempotent: fully rewrites the workspace/oracle/docs for each variant.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Migration contract (shared, identical across variants)
# ---------------------------------------------------------------------------
REGIONS = ["eu", "us", "uk", "jp"]
CURRENCY_BY_REGION = {"eu": "EUR", "us": "USD", "uk": "GBP", "jp": "JPY"}
LEDGER_V2_SOURCE = "ledger-v2"
REPORT_SOURCE = "report-v2"
FUNCS_PER_MODULE = 6

# Two anchor consumers, pinned to module m00 (region eu) in EVERY variant so the
# visible test file is variant-invariant and "tests-go-green-early" is identical.
ANCHORS = [
    ("quote_anchor_alpha", "acct-anchor-alpha", 100),
    ("quote_anchor_beta", "acct-anchor-beta", 110),
]

VARIANTS = {
    "s": {"id": "V3L05S", "surface_id": "V3-W5-S", "n_consumers": 8, "n_decoys": 4, "seed": 5011},
    "m": {"id": "V3L05M", "surface_id": "V3-W5-M", "n_consumers": 18, "n_decoys": 9, "seed": 5012},
    "l": {"id": "V3L05L", "surface_id": "V3-W5-L", "n_consumers": 36, "n_decoys": 18, "seed": 5013},
}

PASS_FRACTION = 0.90  # pre-registered, task-intrinsic (see discrimination.yaml)
MAX_POINTS = 100
PASS_THRESHOLD_POINTS = 90


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def region_for_module(mod_index: int) -> str:
    return REGIONS[mod_index % len(REGIONS)]


def build_specs(n_consumers: int, n_decoys: int, seed: int):
    """Return (modules, consumers, report_decoys, audit_decoys).

    modules: list of dicts {name, region, funcs:[func-spec ...]}
    Each func-spec: {kind: quote|report|audit, func, account, amount|ts, module, region, expected}
    Order within/across modules is seed-shuffled (randomized consumer order per variant).
    """
    rng = random.Random(seed)

    # Non-anchor consumers.
    non_anchor = n_consumers - len(ANCHORS)
    assert non_anchor >= 0
    consumers = []
    for i in range(non_anchor):
        consumers.append({"kind": "quote", "func": f"quote_c{i:02d}", "account": f"acct-c{i:02d}", "amount": 100 + i})
    report_decoys = []
    audit_decoys = []
    for i in range(n_decoys):
        if i % 2 == 0:
            report_decoys.append({"kind": "report", "func": f"report_r{i:02d}", "account": f"acct-r{i:02d}", "amount": 200 + i})
        else:
            audit_decoys.append({"kind": "audit", "func": f"audit_a{i:02d}", "account": f"acct-a{i:02d}", "ts": 1000 + i})

    # Pool that gets scattered/shuffled (everything except the two anchors, which
    # are pinned to m00). Shuffle assigns them to modules in randomized order.
    pool = consumers + report_decoys + audit_decoys
    rng.shuffle(pool)

    # Module 0 holds the two anchors first, then filled from the pool.
    total_funcs = len(ANCHORS) + len(pool)
    n_modules = max(1, -(-total_funcs // FUNCS_PER_MODULE))  # ceil

    modules = [{"name": f"m{k:02d}", "region": region_for_module(k), "funcs": []} for k in range(n_modules)]

    # Place anchors in m00.
    for func, account, amount in ANCHORS:
        modules[0]["funcs"].append({"kind": "quote", "func": func, "account": account, "amount": amount})

    # Distribute pool round-robin starting after anchors, but respecting the
    # shuffled order so scatter differs per variant.
    slot = len(ANCHORS)
    for spec in pool:
        # find next module with room, scanning in a seed-rotated order
        mod_index = slot % n_modules
        # avoid overfilling m00 beyond FUNCS_PER_MODULE
        guard = 0
        while len(modules[mod_index]["funcs"]) >= FUNCS_PER_MODULE and guard < n_modules:
            mod_index = (mod_index + 1) % n_modules
            guard += 1
        modules[mod_index]["funcs"].append(spec)
        slot += 1

    # Shuffle order WITHIN each module too (randomized consumer order).
    for mod in modules:
        rng.shuffle(mod["funcs"])

    # Annotate every func with its module + region + expected output.
    for mod in modules:
        for spec in mod["funcs"]:
            spec["module"] = mod["name"]
            spec["region"] = mod["region"]
            cur = CURRENCY_BY_REGION[mod["region"]]
            if spec["kind"] == "quote":
                spec["expected"] = {
                    "account": spec["account"], "amount": spec["amount"],
                    "region": mod["region"], "currency": cur, "source": LEDGER_V2_SOURCE,
                }
            elif spec["kind"] == "report":
                spec["expected"] = {
                    "account": spec["account"], "amount": spec["amount"],
                    "region": mod["region"], "currency": cur, "source": REPORT_SOURCE,
                }
            else:  # audit
                spec["expected"] = {"account": spec["account"], "ts": spec["ts"]}
    return modules


# ---------------------------------------------------------------------------
# Source emitters
# ---------------------------------------------------------------------------
def emit_quote_starter(spec) -> str:
    return (
        f"def {spec['func']}():\n"
        f"    account = \"{spec['account']}\"\n"
        f"    amount = {spec['amount']}\n"
        f"    return {{\"account\": account, \"amount\": amount}}\n"
    )


def emit_report(spec) -> str:
    # Decoy: already v2-shaped, source=report-v2. MUST stay byte-equal.
    return (
        f"def {spec['func']}():\n"
        f"    account = \"{spec['account']}\"\n"
        f"    amount = {spec['amount']}\n"
        f"    return {{\"account\": account, \"amount\": amount, "
        f"\"region\": REGION, \"currency\": CURRENCY, \"source\": \"{REPORT_SOURCE}\"}}\n"
    )


def emit_audit(spec) -> str:
    # Decoy: legacy audit record, no region/currency/source. MUST stay legacy.
    return (
        f"def {spec['func']}():\n"
        f"    account = \"{spec['account']}\"\n"
        f"    return {{\"account\": account, \"ts\": {spec['ts']}}}\n"
    )


def emit_module(mod) -> str:
    head = (
        "from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE\n\n"
        f"REGION = \"{mod['region']}\"\n"
        "CURRENCY = CURRENCY_BY_REGION[REGION]\n\n\n"
    )
    body = []
    for spec in mod["funcs"]:
        if spec["kind"] == "quote":
            body.append(emit_quote_starter(spec))
        elif spec["kind"] == "report":
            body.append(emit_report(spec))
        else:
            body.append(emit_audit(spec))
    return head + "\n\n".join(body)


CONTRACT_PY = (
    '"""Shared migration contract constants (protected: do not edit)."""\n\n'
    'CURRENCY_BY_REGION = {"eu": "EUR", "us": "USD", "uk": "GBP", "jp": "JPY"}\n'
    'LEDGER_V2_SOURCE = "ledger-v2"\n'
)


def emit_init(modules) -> str:
    # Plain package marker: modules are imported independently by the verifier so a
    # syntax error in one module isolates to that module's consumers (truer fraction).
    return '"""ledgerkit package (protected: do not edit __init__)."""\n'


VISIBLE_TEST = '''import unittest

from ledgerkit.m00 import quote_anchor_alpha, quote_anchor_beta


class VisibleQuoteContract(unittest.TestCase):
    """Intentionally insufficient: covers only the two anchor consumers.

    Hidden verification exercises every quote_* consumer across all modules.
    Passing these two tests does NOT mean the migration is complete.
    """

    def test_anchor_alpha_migrated(self):
        self.assertEqual(
            quote_anchor_alpha(),
            {"account": "acct-anchor-alpha", "amount": 100,
             "region": "eu", "currency": "EUR", "source": "ledger-v2"},
        )

    def test_anchor_beta_migrated(self):
        self.assertEqual(
            quote_anchor_beta(),
            {"account": "acct-anchor-beta", "amount": 110,
             "region": "eu", "currency": "EUR", "source": "ledger-v2"},
        )


if __name__ == "__main__":
    unittest.main()
'''


# ---------------------------------------------------------------------------
# Root writer
# ---------------------------------------------------------------------------
def scenario_yaml(v) -> str:
    return f"""id: {v['id']}
surface_id: {v['surface_id']}
pack_id: V3P05
role_class: implementation
artifact_type: homogeneous breadth contract migration
modality_family: single-stream breadth under fixed depth
rf12_line: L05
role_trigger: homogeneous-breadth-contract-migration
target_separator: stamina-breadth-slope
allowed_change_surface:
  - candidate/workspace/src/ledgerkit/m*.py
  - candidate/refactor-ledger.json
must_not_touch:
  - inputs/**
  - oracle/**
  - verifiers/**
  - candidate/README.md
  - candidate/workspace/README.md
  - candidate/workspace/tests/**
  - candidate/workspace/src/ledgerkit/__init__.py
  - candidate/workspace/src/ledgerkit/contract.py
score_profile: "homogeneous breadth migration, hidden consumers, decoy precision, graded fraction, completion-vs-length slope"
overlay_flags:
  - stamina
  - graded-fraction
  - hidden-consumer
  - decoy-precision
  - matched-length-triplet
"""


def required_metadata(v):
    return {
        "id": v["id"],
        "surface_id": v["surface_id"],
        "pack_id": "V3P05",
        "role_class": "implementation",
        "artifact_type": "homogeneous breadth contract migration",
        "modality_family": "single-stream breadth under fixed depth",
        "rf12_line": "L05",
        "role_trigger": "homogeneous-breadth-contract-migration",
        "target_separator": "stamina-breadth-slope",
        "allowed_change_surface": [
            "candidate/workspace/src/ledgerkit/m*.py",
            "candidate/refactor-ledger.json",
        ],
        "must_not_touch": [
            "inputs/**",
            "oracle/**",
            "verifiers/**",
            "candidate/README.md",
            "candidate/workspace/README.md",
            "candidate/workspace/tests/**",
            "candidate/workspace/src/ledgerkit/__init__.py",
            "candidate/workspace/src/ledgerkit/contract.py",
        ],
        "score_profile": "homogeneous breadth migration, hidden consumers, decoy precision, graded fraction, completion-vs-length slope",
        "overlay_flags": [
            "stamina", "graded-fraction", "hidden-consumer", "decoy-precision", "matched-length-triplet",
        ],
    }


SCENARIO_YAML_FIELDS = [
    "id", "surface_id", "pack_id", "role_class", "artifact_type", "modality_family",
    "rf12_line", "role_trigger", "target_separator", "allowed_change_surface",
    "must_not_touch", "score_profile", "overlay_flags",
]


def build_oracle_contract(v, modules):
    consumers = []
    report_decoys = []
    audit_decoys = []
    for mod in modules:
        for spec in mod["funcs"]:
            entry = {"module": spec["module"], "func": spec["func"], "expected": spec["expected"]}
            if spec["kind"] == "quote":
                consumers.append(entry)
            elif spec["kind"] == "report":
                report_decoys.append(entry)
            else:
                audit_decoys.append(entry)
    consumers.sort(key=lambda e: e["func"])
    report_decoys.sort(key=lambda e: e["func"])
    audit_decoys.sort(key=lambda e: e["func"])
    module_files = [f"candidate/workspace/src/ledgerkit/{mod['name']}.py" for mod in modules]
    required_bundle_files = [
        "inputs/README.md", "inputs/task.md",
        "candidate/README.md", "candidate/refactor-ledger.json",
        "candidate/workspace/README.md",
        "candidate/workspace/src/ledgerkit/__init__.py",
        "candidate/workspace/src/ledgerkit/contract.py",
        "candidate/workspace/tests/test_visible.py",
        "oracle/README.md", "oracle/stamina-contract.json", "oracle/scoring-anchors.md",
        "verifiers/README.md", "verifiers/check_stamina_migration.py",
        "verifiers/compute_stamina_slope.py",
    ] + module_files
    return {
        "schema_version": "scenarios-v3-oracle-2026-05-01",
        "scenario_id": v["id"],
        "root_name": f"V3L05-stamina-migration-{v['key']}",
        "rf12_line": "L05",
        "role_trigger": "homogeneous-breadth-contract-migration",
        "target_separator": "stamina-breadth-slope",
        "variant": v["key"],
        "seed": v["seed"],
        "score": {
            "max_points": MAX_POINTS,
            "graded_measure": "breadth_fraction",
            "pass_fraction": PASS_FRACTION,
            "pass_threshold_points": PASS_THRESHOLD_POINTS,
            "false_positive_policy": "any_false_positive_fails",
            "total_consumers": len(consumers),
            "total_decoys": len(report_decoys) + len(audit_decoys),
            "visible_covered": [a[0] for a in ANCHORS],
        },
        "required_top_level_entries": ["README.md", "scenario.yaml", "inputs", "candidate", "oracle", "verifiers"],
        "scenario_yaml_fields": SCENARIO_YAML_FIELDS,
        "required_metadata": required_metadata(v),
        "required_bundle_files": required_bundle_files,
        "migration_rule": {
            "consumer_selector": "quote_*",
            "add_fields": {"region": "module REGION", "currency": "CURRENCY_BY_REGION[REGION]", "source": LEDGER_V2_SOURCE},
            "must_not_touch_selectors": ["report_*", "audit_*"],
        },
        "consumers": consumers,
        "report_decoys": report_decoys,
        "audit_decoys": audit_decoys,
        "not_run_classification": ["quota", "timeout_without_summary", "route_failure", "wrapper_failure"],
    }


def starter_ledger(v):
    return {
        "contractId": f"{v['id']}-stamina-migration",
        "changedFiles": [],
        "migratedConsumers": [],
        "notes": "STARTER — replace with the completed migration ledger.",
    }
