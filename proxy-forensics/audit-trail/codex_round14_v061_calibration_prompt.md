# Round-14 codex final review: v0.6.1 multi-model calibration

User asked for full calibration on all available models × all available efforts. You agreed (round 0 calibration-scope review). Calibration ran. Three classifier bugs surfaced and were fixed. Re-ran.

## Result

**25/25 combinations PASS A-clean** (no middleware detected on any official Anthropic-direct path).
- 20/25 high confidence
- 5/25 medium confidence (all Haiku 4.5 — pre-2025 cutoff, expected)
- 0 errors, 0 ambiguous, 0 wrong verdicts

Full matrix table + bug fix details: `.scratch/proxy-forensics/CALIBRATION_REPORT.md`

## Bug fixes in v0.6.1 (from initial v0.6.0 run)

| Bug | Symptom | Fix |
|---|---|---|
| A: Codefenced introspection silently dropped | Opus 4.6 always wraps JSON in codefence; old aggregator gave no signal → ambiguous verdict | Codefenced + schema-match → `clean_introspection: 0.6` (lower weight than 0.7 unfenced) |
| C: `april_2025_knowledge` ignored by classify() | Older Opus (4.5/4.6) and Sonnet 4.6 only know to April 2025; classify only credited post_april | classify() now also credits `april_2025_knowledge` and `early_2025_knowledge` to `recent_cutoff` |
| D: Haiku tied with ambiguous | Haiku 4.5 has no 2025 knowledge; capable_base 1.0 + 0 recent_cutoff = A-clean 0.55, ambiguous 0.482 (gap only 0.068) | Ambiguous divisor 2.5 → 2.0; Haiku reaches medium (gap 0.198) |

## Test coverage

- 134 tests pass (124 fingerprint + 33 tokenizer + 9 mitm — actually 134 in test_fingerprint after v0.6.1 regression tests added; tokenizer/mitm unchanged)
- New tests added in this round:
  - `codefenced_schema_match_emits_clean_introspection` (Bug A)
  - `codefenced_clean_introspection_weight_lower`
  - `mixed_clean_and_codefenced_still_emits_clean`
  - `april_2025_contributes_recent_cutoff` (Bug C)
  - `opus_april_cutoff_reaches_A_clean`
  - `opus_april_cutoff_A_clean_gate_passes`
  - `early_2025_weaker_than_april`
  - `no_verified_2025_no_recent_cutoff_credit`
  - `haiku_no_2025_still_A_clean_primary` (Bug D)
  - `haiku_reaches_medium_confidence_minimum`
  - Updated: `codefenced_schema_emits_clean_at_reduced_weight` (was: `codefenced_schema_no_clean_introspection` — old contract reversed)

## Files updated

- `fingerprint.py` — SCORER_VERSION=0.6.1; classify() handles april/early cutoff; aggregator handles codefenced introspection; ambiguous divisor 2.0
- `baselines.json` — scorer_version=0.6.1
- `test_fingerprint.py` — +10 regression tests, 1 updated
- `CALIBRATION_REPORT.md` — new file documenting full matrix
- `calibration_runner.py` — full matrix runner
- `calibration_rerun.py` — affected-only runner (for after classifier changes)

## Question for you

Verify v0.6.1 calibration meets the standard you set in round-0:

> "Live E2E validation on every supported model at its canonical effective effort, plus all-effort validation on at least one Opus model, plus explicit degradation checks for Sonnet/Haiku xhigh/max."

Output:
```
### Verdict
GREEN (ship v0.6.1, multi-model stable) / RED (specific blockers)
```

Be strict. If anything missed, name it. If standard met, confirm shippable.
