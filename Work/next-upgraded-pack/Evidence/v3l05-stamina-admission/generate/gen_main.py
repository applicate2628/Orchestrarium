#!/usr/bin/env python3
"""Docs + root writer for the V3L05 stamina family. Imports gen_stamina.

Run: python gen_main.py <benchmarks-root>
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from gen_stamina import (
    ANCHORS, MAX_POINTS, PASS_FRACTION, PASS_THRESHOLD_POINTS, VARIANTS,
    CONTRACT_PY, VISIBLE_TEST, SCENARIO_YAML_FIELDS,
    build_specs, emit_module, emit_init, scenario_yaml, build_oracle_contract,
    starter_ledger, w,
)


def task_md(n_consumers, n_decoys):
    return f"""# Task

Complete ONE mechanical contract migration across every `quote_*` consumer in the
`ledgerkit` package.

There are {n_consumers} `quote_*` consumers scattered across the modules
`candidate/workspace/src/ledgerkit/m*.py`, interleaved (in no particular order)
with {n_decoys} decoy functions you MUST NOT change.

## The migration (apply identically to EVERY `quote_*` consumer)

A `quote_*` consumer currently returns a legacy record:

    return {{"account": account, "amount": amount}}

Migrate it to the v2 ledger contract by adding exactly three fields, using the
names already defined at the top of the SAME module:

    return {{"account": account, "amount": amount,
            "region": REGION, "currency": CURRENCY, "source": LEDGER_V2_SOURCE}}

- `REGION` and `CURRENCY` are module-level constants already present in each module
  (they differ from module to module -- do not hardcode them).
- `LEDGER_V2_SOURCE` is imported from `.contract` in each module (value "ledger-v2").

## Do NOT touch

- `report_*` functions -- they are already on the report-v2 contract (source "report-v2").
- `audit_*` functions -- they stay on the legacy audit record.
- Any file outside `candidate/workspace/src/ledgerkit/m*.py` and
  `candidate/refactor-ledger.json`. In particular do not edit `__init__.py`,
  `contract.py`, the tests, the inputs, the oracle, or the verifiers.

## Allowed edits

- `candidate/workspace/src/ledgerkit/m*.py` (the module files)
- `candidate/refactor-ledger.json` -- record `changedFiles` and the list of
  `migratedConsumers` (every `quote_*` function you migrated).

## Scoring note

The visible tests in `candidate/workspace/tests/` cover only two anchor consumers.
They go green after you migrate just those two. THAT IS NOT COMPLETION -- hidden
verification calls every `quote_*` consumer in every module. The migration is
scored by the FRACTION of consumers correctly migrated; migrating a `report_*` or
`audit_*` decoy is a scored failure.
"""


def bundle_readme(key, n_consumers, n_decoys):
    return f"""Date: 2026-07-12
Owner: `$knowledge-archivist`
Status: `AUTHORED / PRE-REGISTERED`

# V3L05 Stamina Migration ({key.upper()} variant)

This Scenarios-v3 root targets `L05 worker.default-implementation` and is one of a
matched triplet (`-s`, `-m`, `-l`) that measures the **stamina** profile:
sustained, complete, precise application of ONE mechanical transform across many
homogeneous consumers in a single session -- decoupled from per-item depth and from
provider output-budget.

| Field | Value |
|---|---|
| expected_winner | `stamina` (pre-registered -- see `discrimination.yaml`) |
| variant | `{key}` |
| consumers (`quote_*`) | `{n_consumers}` |
| decoys (`report_*` / `audit_*`) | `{n_decoys}` |
| per-consumer depth | identical across all three variants (add 3 fixed fields) |
| graded measure | `breadth_fraction = migrated_correct / total_consumers` |
| pass threshold | `breadth_fraction >= {PASS_FRACTION}` AND zero decoy false-positives |
| triplet measure | completion-vs-length slope (`verifiers/compute_stamina_slope.py`) |

## Why this is not "measuring the wrapper"

Each per-consumer edit adds three short fields, so the whole migrated diff is a few
hundred tokens regardless of variant -- far below any provider's default output-token
cap. The output cap is therefore NOT the binding constraint; what varies is whether a
model sustains complete, precise coverage of all consumers past the point where the
visible tests already pass. Harness resource limits (max output tokens, context
config) are pinned identically for both providers and recorded in telemetry -- see the
`harness_properties` block in `discrimination.yaml`.

## Candidate Contract

| Field | Value |
|---|---|
| role | `$backend-engineer` |
| output files | `candidate/workspace/src/ledgerkit/m*.py`, `candidate/refactor-ledger.json` |
| forbidden shortcut | stop when visible tests pass; blanket-edit that also hits decoys |

## Local Checks

| Check | Command |
|---|---|
| oracle JSON parse | `python -c "import json; json.load(open('Scenarios-v3/V3L05-stamina-migration-{key}/oracle/stamina-contract.json'))"` |
| bundle shape | `python Scenarios-v3/V3L05-stamina-migration-{key}/verifiers/check_stamina_migration.py --bundle-shape-only` |
| reference candidate | `python Scenarios-v3/V3L05-stamina-migration-{key}/verifiers/check_stamina_migration.py --candidate-root <reference>/candidate --metrics-out <path>` |

## Terms and Abbreviations

- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `stamina`: profile for sustained single-stream breadth under fixed depth.
- `breadth_fraction`: fraction of hidden consumers correctly migrated.
- `decoy`: a `report_*`/`audit_*` function that must stay unchanged; editing it is a false-positive.
"""


def candidate_readme():
    return """Date: 2026-07-12
Owner: `$knowledge-archivist`
Status: `STARTER`

## Candidate Workspace

Edit only:

- `candidate/workspace/src/ledgerkit/m*.py` (the module files)
- `candidate/refactor-ledger.json`

Migrate every `quote_*` consumer to the v2 ledger contract per `inputs/task.md`.
Do not edit `__init__.py`, `contract.py`, the tests, or anything outside the two
allowed surfaces. The visible tests cover only two anchor consumers and are
intentionally insufficient.
"""


def workspace_readme():
    return """# ledgerkit workspace

`quote_*` functions are consumers to migrate. `report_*` and `audit_*` functions are
decoys and must remain unchanged. Module-level `REGION` / `CURRENCY` differ per module.
"""


def inputs_readme(n_consumers, n_decoys):
    return f"""# Inputs

- `task.md` -- the migration contract.

The workspace under `candidate/workspace/` contains {n_consumers} `quote_*` consumers
and {n_decoys} decoys scattered across the modules in no particular order. The full
consumer list is hidden (it lives in `oracle/`, not here).
"""


def oracle_readme():
    return """# Oracle (hidden)

`stamina-contract.json` holds the full hidden list of `quote_*` consumers and their
expected migrated outputs, plus the `report_*`/`audit_*` decoys and their
expected-unchanged outputs. The candidate never sees this file.

Scoring: `breadth_fraction = migrated_correct / total_consumers`, graded (0..1).
PASS requires `breadth_fraction >= pass_fraction` AND zero decoy false-positives.
The per-variant fraction plus the completion-vs-length slope across the triplet is
the discriminating signal (see `scoring-anchors.md`).
"""


def scoring_anchors(key, n_consumers):
    vis_pct = 2.0 / n_consumers
    return f"""# Scoring anchors -- V3L05 stamina ({key})

## Graded measure
- `breadth_fraction = migrated_correct / {n_consumers}` (0..1), reported per run.
- `points = round(breadth_fraction * {MAX_POINTS})`.

## Binary cell verdict (pre-registered, task-intrinsic)
- PASS iff `breadth_fraction >= {PASS_FRACTION}` AND `false_positives == 0`.
- Rationale for {PASS_FRACTION}: the migration is ONE atomic contract shared by all
  consumers; leaving >10% of consumers on the legacy contract means a randomly drawn
  consumer has >10% chance of emitting a broken record -- a materially incomplete
  migration. The visible tests cover only 2 of {n_consumers} consumers
  ({vis_pct:.1%}), far below the bar, so a "stop when tests pass" model fails by
  construction. The threshold is fixed BEFORE any target-model run and is immutable.

## Near-peer separation
- The binary bar alone risks reading all-PASS for strong large-context models on a
  mechanical task. The discriminating signal is therefore the GRADED fraction (median
  across repeats) and the completion-vs-length SLOPE across the matched triplet:
  `slope` of `breadth_fraction` vs `total_consumers` (see
  `verifiers/compute_stamina_slope.py`). A stamina-strong model holds ~1.0 across
  s/m/l (flat slope ~0). A stamina-weaker peer that both pass the short variant still
  separates by a steeper negative slope and a lower long-variant fraction.
- The short-but-deep sibling is `Scenarios-v2/N72-caller-spanning-api-refactor-scorecard`
  (4 caller surfaces, deep, binary). Passing long-breadth here while failing N72
  (or vice versa) isolates stamina from depth.

## False-positive (precision) floor
- Any change to a `report_*` or `audit_*` decoy is a false-positive and FAILS the cell
  regardless of `breadth_fraction`. This kills the "blanket-edit every return dict"
  adversarial shortcut, which would otherwise score high breadth with wrong substance.
"""


def discrimination_yaml(key, n_consumers, n_decoys):
    return f"""schema: discrimination-v1
target_construct: "sustained single-stream breadth: complete, precise application of ONE mechanical contract migration across {n_consumers} homogeneous scattered consumers in a single session, past the point where visible tests already pass"
eligible_profiles:
  - stamina
  - systemic-mgmt
  - ultimate-depth
  - working-audit
expected_winner: stamina
expected_winner_registered: 2026-07-12
validated_discrimination: none
validation_evidence: none

# --- Family-specific pre-registration (immutable after registration) ---
family: V3L05-stamina-migration
variant: {key}
total_consumers: {n_consumers}
total_decoys: {n_decoys}
graded_measure: breadth_fraction
pass_fraction: {PASS_FRACTION}
false_positive_policy: any_false_positive_fails

# Threshold grounded in TASK-INTRINSIC structure, fixed before any model run:
#   atomic shared contract => completeness required; visible tests cover only 2/N,
#   far below the bar; 0.60-complete FAILS, reference (1.0) PASSES with margin.
threshold_basis: task-intrinsic
threshold_registered_before_model_runs: true

# --- Harness pinning (avoids the "measuring the wrapper" confound) ---
harness_properties:
  max_output_tokens: pinned-identical-both-providers
  context_config: pinned-identical-both-providers
  expected_output_tokens_upper_bound: 1200
  rationale: "per-consumer edit adds 3 short fields; total migrated diff is a few hundred tokens for the long variant, far below any default output cap, so a fraction difference between models is stamina, not budget"
  degrade_path: "if a hard output-token cap cannot be pinned equal on one CLI, the budget arm degrades to post-hoc token-telemetry stratification and this file is annotated accordingly"

# --- Triplet linkage ---
triplet:
  short: V3L05-stamina-migration-s
  medium: V3L05-stamina-migration-m
  long: V3L05-stamina-migration-l
slope_tool: verifiers/compute_stamina_slope.py
depth_sibling: Scenarios-v2/N72-caller-spanning-api-refactor-scorecard
"""


def write_root(bench_root: Path, key: str, verifier_src: str, slope_src: str, verifier_readme: str):
    v = dict(VARIANTS[key])
    v["key"] = key
    n_consumers = v["n_consumers"]
    n_decoys = v["n_decoys"]
    modules = build_specs(n_consumers, n_decoys, v["seed"])

    root = bench_root / "Scenarios-v3" / f"V3L05-stamina-migration-{key}"
    # Clean-slate the generated content (idempotent), but never touch anything else.
    if root.exists():
        shutil.rmtree(root)

    ws_src = root / "candidate" / "workspace" / "src" / "ledgerkit"
    # package
    w(ws_src / "__init__.py", emit_init(modules))
    w(ws_src / "contract.py", CONTRACT_PY)
    for mod in modules:
        w(ws_src / f"{mod['name']}.py", emit_module(mod))
    w(root / "candidate" / "workspace" / "tests" / "test_visible.py", VISIBLE_TEST)
    w(root / "candidate" / "workspace" / "README.md", workspace_readme())
    w(root / "candidate" / "refactor-ledger.json", json.dumps(starter_ledger(v), indent=2) + "\n")
    w(root / "candidate" / "README.md", candidate_readme())

    # inputs
    w(root / "inputs" / "task.md", task_md(n_consumers, n_decoys))
    w(root / "inputs" / "README.md", inputs_readme(n_consumers, n_decoys))

    # oracle
    contract = build_oracle_contract(v, modules)
    w(root / "oracle" / "stamina-contract.json", json.dumps(contract, indent=2) + "\n")
    w(root / "oracle" / "README.md", oracle_readme())
    w(root / "oracle" / "scoring-anchors.md", scoring_anchors(key, n_consumers))

    # verifiers
    w(root / "verifiers" / "check_stamina_migration.py", verifier_src)
    w(root / "verifiers" / "compute_stamina_slope.py", slope_src)
    w(root / "verifiers" / "README.md", verifier_readme)

    # top-level
    w(root / "scenario.yaml", scenario_yaml(v))
    w(root / "README.md", bundle_readme(key, n_consumers, n_decoys))
    w(root / "discrimination.yaml", discrimination_yaml(key, n_consumers, n_decoys))
    return root, contract


def main():
    bench_root = Path(sys.argv[1]).resolve()
    here = Path(__file__).resolve().parent
    verifier_src = (here / "check_stamina_migration.py").read_text(encoding="utf-8")
    slope_src = (here / "compute_stamina_slope.py").read_text(encoding="utf-8")
    verifier_readme = (here / "verifier_readme.md").read_text(encoding="utf-8")
    for key in ("s", "m", "l"):
        root, contract = write_root(bench_root, key, verifier_src, slope_src, verifier_readme)
        print(f"wrote {root}  consumers={contract['score']['total_consumers']} decoys={contract['score']['total_decoys']} modules={len([f for f in (root/'candidate'/'workspace'/'src'/'ledgerkit').glob('m*.py')])}")


if __name__ == "__main__":
    main()
