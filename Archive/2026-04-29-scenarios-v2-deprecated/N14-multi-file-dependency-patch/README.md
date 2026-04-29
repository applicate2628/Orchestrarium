# N14 Multi-file Dependency Patch

`N14` benchmarks a bounded implementation worker on a cross-file dependency patch. The candidate
must repair a small routing-result summarizer where correctness depends on coordinating profile
resolution, runtime status classification, score denominator math, and user-facing report rendering.

## Scenario summary

The candidate workspace contains a tiny Python package that builds benchmark row summaries from
provider policy config and per-row attempt records. The start state has four coupled defects:

- a stale singular profile field overrides the plural profile catalog
- runtime and route failures are counted as scoreable model failures
- score denominators include non-scoreable rows
- report rendering collapses verifier failures and runtime caveats into one failure bucket

Several neighboring files contain plausible but wrong local explanations. They are present as
decoys and are out of scope for the patch.

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/workspace/src/routing_eval/config.py`
- `candidate/workspace/src/routing_eval/status.py`
- `candidate/workspace/src/routing_eval/scorecard.py`
- `candidate/workspace/src/routing_eval/render.py`
- `candidate/workspace/tests/test_routing_eval.py`

The fix should keep the public owner API in `api.py` intact. It should not move logic into tests,
decoy docs, legacy helpers, UI labels, oracle files, or verifier code.

## What this bundle tests

- cross-file dependency tracing instead of one-file local patching
- scoreability semantics for runtime, route, and verifier outcomes
- profile-source precedence under stale compatibility fields
- resistance to decoy files that look relevant but are not owners of the behavior

## Bundle map

- `inputs/` describes the task and decoy boundaries without enumerating oracle rows
- `candidate/workspace/` is the mutable run root copied for each execution
- `oracle/` defines the behavior cases, start-state failures, defect map, and scoring anchors
- `verifiers/` contains bundle-shape, hidden behavior, source-hardcode, and scope checks
