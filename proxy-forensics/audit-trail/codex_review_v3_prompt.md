# Re-review round 3: Claude proxy forensic toolkit v0.3

You reviewed v0.1 (Critical/High findings) and v0.2 (verdict: RED). The toolkit is now v0.3. Re-review strictly and tell me whether to ship or iterate further.

## Files

`.scratch/proxy-forensics/` — read all:
- `README.md`
- `RESULTS.md`
- `METHODOLOGY.md`
- `fingerprint.py` (~600 lines, v0.3)
- `baselines.json`
- `test_fingerprint.py` (76 tests, 0 failures)

## What v0.2 → v0.3 addressed (your previous findings)

### Previously Critical (NEW issue in v0.2)
- **Parser treated all non-list JSON as `intercepted`**, conflicting with Claude docs that describe `--output-format json` as a structured object.
- **v0.3 fix:** `parse_cli_output` now checks for Claude CLI protocol fields (`result`, `type`, `subtype`, `session_id`, `total_cost_usd`, `duration_ms`) on dict outputs. If present → `valid_single_object` status (treated like `valid_stream`). If absent → `intercepted` (candidate only, still requires ≥2 repeat confirmation).

### Previously High
- **`status_failure` becomes evidence** (CLI errors converted to `rigid_bias` / `format_rigor_fail`).
- **v0.3 fix:** aggregators for `anti_euler_override` and `tight_reasoning_crt` now filter out `status_failure` runs BEFORE scoring. Explicit `no_valid_runs` signal emitted when all runs failed.

- **`hard_intercept` allowed with 1 repeat** (trivially one unique hash).
- **v0.3 fix:** `hard_intercept` now requires `len(run_signals) >= 2`. Single-run non-protocol emits weak `single_run_intercept_unverified` (0.2 confidence) with explicit message to re-run.

- **Raw hash over decoded text, not bytes**.
- **v0.3 fix:** `run_cli` captures `stdout_bytes` separately (text=False), passes bytes to `parse_cli_output` which hashes them directly.

- **Superscript regex `7[⁰-⁹²³¹]` accepts any superscript**.
- **v0.3 fix:** regex explicitly matches `7⁴` only. Test `7⁵` now correctly NOT matched.

- **Missing `expiry_date` fails open**.
- **v0.3 fix:** `check_baseline_freshness` returns `is_stale=True` for missing/malformed expiry. Tool blocks strong claims unless `--force-stale`.

### Previously Medium
- **RESULTS.md / baselines.json overclaim words ("Decisive", "CONFIRMED", "refuted", "Killer discriminator", "cannot")**.
- **v0.3 fix:**
  - `baselines.json` anti_euler_override purpose rewritten as "Discriminator probe... Not decisive on its own"
  - `baselines.json` intercept_signature description softened with adaptive-gateway caveat
  - `RESULTS.md` "Decisive result" → "Strong result (not on its own decisive)"
  - `RESULTS.md` ranking table "CONFIRMED/refuted" → "leading hypothesis / unlikely given observed data" with explicit caveat footer
  - `RESULTS.md` "killer probe" → "override probe"

## What remains deferred (documented gaps, v0.4 scope)

- Tokenizer identity probe
- Quantization/precision degradation probe
- Multi-turn middleware probe
- Broader stylometric panel (non-math prompts)
- "Distill + middleware" and "adaptive proxy" hypothesis classes
- Calibrated thresholds (currently hand-tuned heuristics)
- Automated `--regenerate-baselines`
- Label-spoofing auto-detection (currently manual inspection)

All explicit in `README.md:Known gaps`, `METHODOLOGY.md:Known gaps`, and `baselines.json:interpretation_rules.known_gaps`.

## Test coverage (76 tests, 0 failures)

Unit tests cover:
- Parser: all 6 states (`cli_error` ×2, `parse_error` ×2, `intercepted`, `valid_stream`, `valid_single_object`)
- Single-object Claude protocol detection
- Bytes-vs-text hash parity
- Provider detection (5 prefixes)
- Canonical regex (17 variants, including superscript discrimination ⁴ vs ⁵/³)
- Sentence splitter (abbreviations + CRT proof style)
- Scorers: stylometric, anti-euler, introspection
- Aggregators:
  - byte-identical 2-run → hard_intercept
  - different hashes → variable_intercept (not hard)
  - mixed intercept/valid → inconsistent
  - single-run intercept → NO hard_intercept (v0.3 fix test)
  - anti-euler all-failed → NO rigid_bias (v0.3 fix test)
  - anti-euler mixed → override from valid only (v0.3 fix test)
- Classifier: AW+middleware / distill / clean-direct / insufficient-evidence
- Baseline freshness: missing/malformed/past/future expiry

## Your task

For each of your previous findings, assess:
1. Is the v0.3 fix correct and complete?
2. Any new edge cases the fix misses?
3. Any NEW issues introduced in v0.3?

Then scan for:
4. Any still-overclaimed docs / missed overclaims
5. Calibration issues in the thresholds (0.55 / 0.35 / 0.2 / 0.1)
6. Test coverage gaps that matter
7. Anything that would cause WRONG classification on a plausible adversarial proxy

Output in the same format as your v0.2 review:

```
### Summary (3 sentences)
<overall v0.3 assessment>

### Previously Critical/High → v0.3 status
For each previous finding: FIXED / PARTIAL / REGRESSION — one-paragraph explanation.

### Any NEW issues in v0.3
- <item, severity>

### Remaining calibration / methodology concerns
- <item>

### Verdict
GREEN (ship as v0.3 stable) / YELLOW (land with caveats) / RED (more rounds needed)
```

Commit to a color. If RED, list the specific items that must be fixed before GREEN becomes possible. If GREEN, explicitly confirm that at the listed level of caveats (hypothesis generator, single-turn, single-prompt-stylometry) the toolkit is fit for the intended purpose.

Be strict but fair.
