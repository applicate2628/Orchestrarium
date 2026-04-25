# Re-review round 5: Claude proxy forensic toolkit v0.5

v0.1 initial review → v0.2/v0.3/v0.4 all RED. Target: GREEN with documented gaps.

## Files under `.scratch/proxy-forensics/`

- `README.md`, `RESULTS.md`, `METHODOLOGY.md`
- `fingerprint.py` (~680 lines, v0.5)
- `baselines.json` (scorer_version 0.5.0)
- `test_fingerprint.py` (109 tests, 0 failures)

## What v0.4 → v0.5 addressed (your round-4 findings)

### The one identified blocker
- **`inconsistent_intercept` could still produce high-confidence A-clean.** **v0.5 fix:** A-clean gate now explicitly fails if ANY intercept signal is present (`hard_intercept`, `variable_intercept`, `inconsistent_intercept`, `schema_mismatch`, `single_run_intercept_unverified`). Also tightened suspicious_intercept threshold from 0.3 → 0.1.
  Tests: `inconsistent_intercept_A_clean_gate_fails`, `single_run_intercept_unverified_A_clean_gate_fails`, `schema_mismatch_A_clean_gate_fails`, `clean_introspection_A_clean_gate_can_pass` (positive control).

### Medium items
- **baselines.json scorer_version still 0.3.0.** **v0.5 fix:** bumped to 0.5.0. Also `planned v0.3` → `planned future work` in known_gaps. Added `distill+middleware` blind-spot entry to known_gaps.
- **argparse description still v0.2.** **v0.5 fix:** updated to v0.5.
- **Scorer-version drift only printed, not enforced.** **v0.5 fix:** major-version mismatch now blocks execution (return code 2) unless `--force-stale`.
- **`model.startswith("claude")` too permissive.** **v0.5 fix:** tightened to `claude-` with hyphen (forged `claudefake` / bare `claude` now intercepted). Tests `forged_claude_prefix_intercepted`, `bare_claude_intercepted`, `claude-opus-4-7_accepted`.
- **Pope Leo XIV regex accepted both April and May.** **v0.5 fix:** restricted to May only (Leo XIV was elected May 2025; April would be hallucinated). Test `false_dated_leo_xiv_not_matched`.
- **Hypothesis names said "real Claude".** **v0.5 fix:** renamed to "Claude-like backend" to reflect the documented distill+middleware blind spot honestly. `RESULTS.md` verdict also softened: "inconsistent with a distilled student" → "less consistent with a rigidly-biased distilled-only student" with explicit mention of the blind spot.

### Low
- **RESULTS.md categorical "inconsistent with distilled student".** Softened as above.

### Test coverage additions (v0.5)
- `inconsistent_intercept_A_clean_gate_fails`
- `single_run_intercept_unverified_A_clean_gate_fails`
- `schema_mismatch_A_clean_gate_fails`
- `clean_introspection_A_clean_gate_can_pass` (positive control)
- `forged_claude_prefix_intercepted`, `bare_claude_intercepted`, `claude-opus-4-7_accepted`
- `false_dated_leo_xiv_not_matched`
- `codefenced_schema_match`, `codefenced_wrap_detected`, `codefenced_schema_no_clean_introspection`

Total: 109 tests, 0 failures.

## Still-deferred (documented gaps)

1. Tokenizer identity probe
2. Quantization/precision degradation probe
3. Multi-turn middleware probe
4. `distill+middleware` hypothesis class (noted as blind spot affecting label interpretation)
5. Threshold calibration (hand-tuned heuristics, not calibrated probabilities)
6. Automated `--regenerate-baselines` implementation

## Your task

Strict re-review. Assess:
1. Is the `inconsistent_intercept` blocker from round 4 actually fixed?
2. Any NEW issues introduced in v0.5?
3. Any remaining medium/high issue missed across all four rounds?
4. Now that hypothesis names say "Claude-like" not "real Claude", is the `distill+middleware` blind spot adequately managed for documentation purposes (while deferred from implementation)?

Output format:

```
### Summary (3 sentences)

### Round-4 blocker → v0.5 status
FIXED / PARTIAL / REGRESSION — explanation.

### Other Round-4 items → v0.5 status
- <item>: FIXED / PARTIAL / REGRESSION — explanation.

### Any NEW issues in v0.5
- <item, severity>

### Verdict
GREEN (ship v0.5 as stable with documented gaps) / YELLOW (land with caveats) / RED (exact blockers)
```

If GREEN, confirm explicitly that at the documented gap level the toolkit is fit for its intended "hypothesis generator" purpose. If YELLOW, list the caveats that must accompany any use. If RED, list the exact blockers and nothing more.

Be strict but recognize diminishing returns. Don't raise new concerns of a severity you wouldn't have raised in round 1 (scope creep).
