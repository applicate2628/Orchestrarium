# Re-review round 4: Claude proxy forensic toolkit v0.4

You've reviewed v0.1, v0.2 (RED), v0.3 (RED). Target: GREEN with caveats, or list specific blockers.

## Files under `.scratch/proxy-forensics/`

- `README.md`, `RESULTS.md`, `METHODOLOGY.md`
- `fingerprint.py` (~650 lines, v0.4)
- `baselines.json`
- `test_fingerprint.py` (97 tests, 0 failures)

## What v0.3 → v0.4 addressed (your round-3 findings)

### Previously High
- **Parser single-object too permissive** (any one of result/type/subtype/session_id → valid). **v0.4 fix:** `_looks_like_claude_single_object()` now requires `result` string AND one of: {usage dict with token counts, model string starting `claude-`/`msg_`, session_id ≥ 8 chars}. Wrapper attack `{"result":"{\"acknowledged\":true}"}` now correctly classifies as `intercepted`. Test `wrapped_intercept_detected_as_intercepted` confirms. `{"type":"ok"}` also intercepted — type alone insufficient.

- **Introspection clean for any parseable JSON**. **v0.4 fix:** `score_run_introspection` validates the 4-field schema (`architecture_family: str`, `supports_extended_thinking: bool`, `can_use_prompt_caching: bool`, `knowledge_cutoff_month: str`). `schema_match` tracks match status. Aggregator now only emits `clean_introspection` when ALL runs schema-match. JSON-parseable but schema-mismatched → new `schema_mismatch` signal that counts as middleware evidence. Tests `complete_schema_matches`, `partial_schema_no_match`, `wrong_type_schema_no_match`, `schema_mismatch_signal_emitted`.

- **Classifier has no hard evidence gates**. **v0.4 fix:** `classify()` enforces gates:
  - `A+Middleware` requires `middleware ≥ 0.6 AND capable_base ≥ 0.5`
  - `A-clean` requires `capable_base ≥ 0.6 AND middleware < 0.4 AND suspicious_intercept < 0.3`
  - `C` requires `distill ≥ 0.6 AND capable_base < 0.5`
  - Gates reported in `gates_passed` field. High confidence only possible if gate passes + score + gap meet thresholds.
  Tests: `hard_intercept_alone_NOT_high_confidence`, `A+Middleware_gate_fails_without_capable_base`.

- **Variable/inconsistent intercept ignored by classifier**. **v0.4 fix:** `variable_intercept` and `inconsistent_intercept` now populate `suspicious_intercept` bucket, which (a) disqualifies A-clean high confidence via gate, (b) contributes to middleware evidence. Test `variable_intercept_blocks_A_clean_high`.

### Previously Medium
- **Temporal cutoff scoring accepts generic late-2025**. **v0.4 fix:** aggregator now iterates `events_found`, cross-references `TEMPORAL_EVENTS`, and only counts events marked `verifiable: True` toward `post_april_2025_knowledge`. Test `generic_late_2025_NOT_post_april`.

- **v0.3 packaging/docs stale**. **v0.4 fix:** README bumped to v0.4, METHODOLOGY bumped to v0.4, fingerprint.py docstring rewritten, "planned v0.3" → "planned future work" in docs.

- **Parser list-of-scalars crashes**. **v0.4 fix:** type-guard `dict_elements = [x for x in parsed if isinstance(x, dict)]`; mismatch → `parse_error` with descriptive reason. Test `stream_list_with_scalars_parse_error`.

### Previously methodology
- **RESULTS.md categorical claims ("Real Claude Opus...", "underlying model is genuine frontier Claude")**. **v0.4 fix:** reworded as "Most consistent with: real Claude Opus" and "The observed signals are inconsistent with [alternatives] and most consistent with [leading hypothesis]. This is a compounding-evidence hypothesis, not a proof."

- **`soft_override_success` treated as capable-base even without observed bias**. **v0.4 fix:** classifier checks `stylometric_euler_bias` before applying full capable_base boost from override. Without prior bias, override contributes only 0.3× (weak signal). Test `bias_observed_gives_higher_capable_base`.

## New adversarial tests added (21 of them, 97 total)

- `hard_intercept_alone_NOT_high_confidence` — hard intercept without capable_base can't produce high A+Middleware
- `A+Middleware_gate_fails_without_capable_base` — gate status explicitly False
- `A+Middleware_gate_still_fails_without_capable_base` — even with temporal cutoff added
- `variable_intercept_blocks_A_clean_high` — adaptive gateway blocked from A-clean
- `AW_reproduces_A+Middleware_primary` — original AW-profile reaches correct classification
- `AW_A+Middleware_gate_passes` — gate status True for full AW profile
- `wrapped_intercept_detected_as_intercepted` — `{"result": "..."}` wrapper correctly intercepted
- `type_only_not_enough_for_single_object` — `{"type":"ok"}` intercepted
- `genuine_single_object_accepted` — `{result, usage, model}` accepted
- `non_claude_model_intercepted` — model=gpt-5.5 fails heuristic
- `stream_list_with_scalars_parse_error` — type-guard works
- `complete_schema_matches` — all 4 fields with types
- `partial_schema_no_match` — missing field detected
- `wrong_type_schema_no_match` — bool-as-string detected
- `schema_mismatch_signal_emitted` — aggregator routes to schema_mismatch
- `schema_mismatch_no_clean_introspection` — no false clean signal
- `generic_late_2025_NOT_post_april` — verifiable-only cutoff scoring
- `pope_leo_xiv_IS_post_april` — verifiable May 2025 event counts
- `bias_observed_gives_higher_capable_base` — soft_override conditional on bias

## What remains deferred

- Tokenizer identity probe (gap — RESULTS.md evidence not reproducible via toolkit)
- Quantization degradation probe
- Multi-turn middleware probe
- `distill+middleware` hypothesis class
- Automated `--regenerate-baselines`
- Threshold calibration (0.55/0.35/0.2/0.1 are hand-tuned heuristics)

All documented in README/METHODOLOGY known-gaps sections.

## Your task

Same format as previous rounds. For each previous High/Medium finding, assess:
1. Correct fix?
2. Any missed edge cases?
3. NEW issues introduced?

Then scan for:
4. Remaining overclaims or inconsistencies
5. Any plausible adversarial proxy that would still receive a misleading high-confidence label
6. Test coverage gaps
7. Deferred items that should have been in scope for "stable"

Output format:

```
### Summary (3 sentences)

### Round-3 findings → v0.4 status
For each: FIXED / PARTIAL / REGRESSION — explanation.

### Any NEW issues in v0.4
- <item, severity>

### Remaining concerns
- <item>

### Verdict
GREEN (ship as v0.4 stable with documented gaps) / YELLOW (land with caveats) / RED (specific blockers below)
```

Be strict. If GREEN is possible now, confirm it. If RED, list the exact blockers and nothing more.
