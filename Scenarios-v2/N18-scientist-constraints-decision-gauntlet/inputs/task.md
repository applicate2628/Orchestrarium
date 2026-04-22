# Task

You are acting as a scientist/constraint specialist for a release-gate subsystem.

## Goal

Update `candidate/constraint-decision-memo.md` into a bounded decision memo that chooses the only
admissible release-gate design under the supplied performance, security, reliability, and evidence
quality constraints.

## Required behavior

- choose exactly one option: `Option C - keyed index plus exact ledger replay`
- reject `Option A - linear exact ledger scan` because it violates p95 latency
- reject `Option B - probabilistic sketch gate` because it allows rollback false negatives
- preserve a non-claim that UI badge smoothness is not release safety evidence
- preserve a non-claim that stale benchmark notes cannot override current measured profiles
- include the exact hard limits from `inputs/hard-constraints.md`
- include the exact measured values from `inputs/measurement-ledger.md`
- include a falsification plan with latency, false-negative, source-trace, and memory checks
- state the residual risk and owner for each accepted mitigation

## Disallowed behavior

- do not propose an implementation patch
- do not route the decision to UI polish or stale benchmark advice
- do not choose multiple options
- do not treat probabilistic false negatives as acceptable for rollback gating
- do not edit files outside `candidate/constraint-decision-memo.md`
