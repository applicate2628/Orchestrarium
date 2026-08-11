# Plan — separate REVISE cap contracts

## Change-Surface Contract consumed

Use only the surfaces named in `design.md`: review-loop owner/wrapper, generic and review-loop cap prose consumers, reconciliation, one dedicated test, release/lifecycle artifacts. The parked p95 surface and unrelated limits remain protected.

## Phase A — durable contract RED

**Scope:** add `tests/test_revise_cap_contracts.py` only.

**Actions:** encode exact generic/review inventories, owner values, scope terms, and C6 absence. Run the focused module against current source and preserve failures for duplicate generic numerics, `per stage`, and `DEFAULT_CAP`.

**Acceptance criteria:**

- **A-AC1:** focused collection succeeds and at least one assertion fails for each of the three known defect classes.
- **A-AC2:** the test explicitly inventories both provider bindings, shared/English/Russian review-loop docs, and generic command/reference consumers.

**Diff-invisible invariants / guards:** p95 files unchanged; `git diff --name-only` contains only the test plus work-item artifacts.

**Rollback:** standalone while intentionally RED; delete the new test.

## Phase B — owner and prose migration

**Scope:** `scripts/review_loop_state.py`, `scripts/validate-review-loop-state.py`, admitted cap prose/reconciliation consumers.

**Actions:** rename the runtime owner, update every engine caller, remove generic numeric restatements, normalize Claude scope to same role/artifact, preserve review-loop `N=3 rounds`, and erase stale `per stage`/`DEFAULT_CAP` relations.

**Acceptance criteria:**

- **B-AC1:** focused contract module passes with one generic numeric owner and one runtime round owner.
- **B-AC2:** full review-loop-state tests pass with default 3 and explicit override behavior unchanged.
- **B-AC3:** exact C6 scan finds zero unclassified `per stage`, generic numeric restatement, or `DEFAULT_CAP` hits in live admitted surfaces.

**Diff-invisible invariants / guards:** explicit override regression; provider parity; p95 isolation.

**Rollback:** atomic with Phase A because the RED test encodes the new contract.

## Phase C — integration and delivery truth

**Scope:** release note, implementation artifact, validators, lifecycle disposition.

**Acceptance criteria:**

- **C-AC1:** Codex/Claude pack validators and AGENTS spine pass with exact counts.
- **C-AC2:** `git diff --check`, LF/NUL, CodeGraph freshness, and work-item state pass.
- **C-AC3:** QA and architecture review map all 10 design claims and return PASS.
- **C-AC4:** the decision becomes accepted, the bug becomes fixed, lifecycle owner archives the item, and a local isolated commit excludes p95 files.

**Diff-invisible invariants / guards:** staged name-status audit and staged publication-safety scan.

**Rollback:** one atomic local commit/reset before push; no persisted external state.

## Execution order and roles

Serial: `$platform-engineer` A→B→C integration, then `$qa-engineer`, then `$architecture-reviewer`, then Lead lifecycle/commit. Parallel mutation is unnecessary because the prose inventories and test observe the same surfaces.

## Gate decision

PASS.

## Terms and Abbreviations

- **C6:** deletion of stale live relationships after a superseding change.
- **PASS:** the plan can enter implementation without redefining architecture.
