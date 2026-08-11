# Architecture review — REVISE cap contract separation

Gate: PASS

Reviewed surface: accepted design claims, runtime cap owner and callers, repository wrapper, generic consumer inventory, review-loop hard-boundary consumers, both pack validators, dedicated contract test, staged boundary, and release note.

| Claim | Verdict | Evidence |
| --- | --- | --- |
| 1. One generic numeric owner | verified | `test_generic_lead_cap_has_one_numeric_owner` and closed inventory |
| 2. Same-role/same-artifact unit | verified | exact consumer scope guard |
| 3. No `per stage` residue | verified | same scope guard plus live-tree scan |
| 4. Explicit round owner | verified | `REVIEW_LOOP_ROUND_CAP` with eight current callers in CodeGraph |
| 5. Provider round prose matches | verified | six-consumer drift matrix, six subtests |
| 6. Explicit `--cap` remains | verified | parser-level default/override guard plus full V2 suite |
| 7. `DEFAULT_CAP` deleted | verified | symbol, wrapper, and residue guard |
| 8. Claude/Codex generic scope agrees | verified | shared pointer prose, cross-pack row, validators 530/530 and 449/449 |
| 9. Parked p95 protected | verified | staged name-status and release-note index diff |
| 10. Ledger/exit behavior unchanged | verified | full review-loop state suite and validator self-test |

## Layering assessment

- C1: CLEAN-SINGLE-OWNER. The generic number and autonomous round number are intentionally different policy owners even while both currently equal three.
- C6: CLEAN. `per stage`, generic numeric copies, misleading identical-semantics prose, and `DEFAULT_CAP` are gone from live owner surfaces.
- Hard-boundary duplicates: JUSTIFIED-DEPTH. Self-contained provider review-loop bindings retain the runtime value and are exhaustively drift-gated.
- Anti-layering: no PILED class; the change removes duplicated ownership rather than adding guards around competing owners.

No blocking deviation, dependency inversion, state-lifetime change, or new abstraction debt was found.

## Terms and Abbreviations

- **C1:** single-owner invariant.
- **C6:** stale-relation deletion law.
- **JUSTIFIED-DEPTH:** duplication at a self-contained boundary with a drift gate.
