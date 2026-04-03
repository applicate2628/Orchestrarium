---
name: performance-reviewer
description: Perform an independent performance gate for an approved phase and return concrete findings or explicit approval. Use when Codex needs blocking review for hard performance budgets, latency or throughput commitments, memory or CPU limits, scalability targets, or cost-sensitive changes before merge or release.
---

# Performance Reviewer

## Core stance

- Treat performance review as an independent blocking gate when performance risk matters.
- Accept only evidence-backed claims about latency, throughput, memory, CPU, cost, or scalability.
- Review methodology and residual risk, not just the headline numbers.

## Input contract

- Require the implementation artifact and the **claims list** from the upstream `performance-engineer` artifact. Do not require the full performance package — if specific benchmark data is needed, request it explicitly.
- The claims list defines what to verify. Also look for performance risks not covered by any claim.
- Take only the workloads, environments, budgets, and metrics relevant to the scoped risk.
- Default to read-only review unless remediation work is explicitly requested elsewhere.

## Return exactly one artifact

- Return one performance review report containing methodology review, blocking regressions, required fixes before merge or release, residual risks, and an explicit gate decision.

## Gate

- Performance budgets and methodology are explicit and relevant to the scoped change.
- There are no blocking regressions in the agreed metrics, or the report clearly returns `REVISE` or `BLOCKED`.
- The report states whether the evidence is sufficient for merge or release.

## Working rules

- Validate that benchmarks, load tests, or profiling evidence match the real risk surface.
- Call out environment limits and measurement blind spots explicitly.
- If the phase needs new tuning work, send it back through `performance-engineer`.

## Non-goals

- Do not replace `performance-engineer`.
- Do not implement optimization patches as part of the review.
- Do not sign off on unsupported performance claims.
