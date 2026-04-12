# Performance Review — Orchestrarium Monorepo

**Date:** 2026-04-09  
**Stage:** performance-reviewer  
**Gate:** PASS  

## Findings

| # | Metric | Value | Rating |
|---|--------|-------|--------|
| 1 | Claude session context load | ~23 KB (vs 15 KB guideline) | WARNING |
| 2 | Codex session context load | ~25 KB (vs 15 KB guideline) | WARNING |
| 3 | Installer execution — no network, local ops only | <2s expected | OK |
| 4 | AGENTS.shared.md duplication | 19.8 KB × 2 — justified by design | OK |
| 5 | Identical duplication waste | `evidence-based-answer-pipeline.md` 2.8 KB | OK (trivial) |
| 6 | Installer file ops | ~18 (Claude), ~11 (Codex) — no redundancy | OK |
| 7 | `lead.md` + `operating-model.md` combined | ~31 KB in lead subagent context | WARNING |
| 8 | Pack artifact sizes | src.claude ~207 KB, src.codex ~201 KB | OK |

## Recommendations (non-blocking)

1. Split `operating-model.md` into compact summary + full reference (on-demand)
2. Add file-size threshold check to `validate-skill-pack.sh`
