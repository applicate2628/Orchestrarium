# Round-7 codex review: Claude proxy forensic toolkit v0.6

v0.5 was GREEN (round 6). v0.6 adds 5 scope items you reviewed in the plan phase. I applied your MODIFY feedback and ran checkpoint 2a on the tokenizer schema (you said MODIFY → I applied all 6 fixes). Now I need final approval on v0.6 before shipping.

## What changed v0.5 → v0.6

### Item 1: `mitm_capture.py` subprocess hang fix
- Replaced `subprocess.run(shell=True, timeout=N)` with `Popen` + poll-loop + `_kill_tree()`
- Windows: `taskkill /F /T /PID`; POSIX: `os.killpg(SIGKILL)`
- New `--subprocess-timeout` flag (default 60s)
- 7 unit tests in `test_mitm_capture.py`: platform-specific kill, exception swallow, hung-child simulation

### Item 2: `tokenizer_probe.py` (new)
- 10 sentinels, paired short/long per char class (ascii × 2, cyrillic × 2, cjk × 2, emoji, code × 2, high-entropy hex)
- CLI-mediated baseline (no raw API key available); `baseline_method: "claude_cli_usage_total_input"` in output
- Least-squares fit `gateway = α·baseline + β`; checks α ∈ [0.97, 1.03], residuals, repeat spread ≤ 2, n_points ≥ 8
- 5 verdicts: `claude_bpe`, `claude_bpe_weak`, `non_claude`, `ambiguous`, `insufficient_data`
- **Applied checkpoint 2a fixes:**
  - Renamed `repeat_variances` → `repeat_spread_tokens` (was misnamed; stores max-min spread, not variance)
  - Added provenance: `baseline_method`, `token_metric`, `baseline_shell`, `gateway_shell`
  - Enforced `n_points ≥ 8` for strong verdicts (< 8 → `ambiguous`)
  - Split `non_claude` path: triggers on (α outside [0.9, 1.1]) OR (α near 1 AND residuals ≥ 10 AND stable)
  - Differentiated `claude_bpe_weak` (residuals [5, 10)) from `non_claude` (residuals ≥ 10)
  - Docstring thresholds synced with code
- 33 unit tests in `test_tokenizer_probe.py`: fit correctness (exact / proportional / noisy / degenerate), classify verdicts (all 5), sentinel composition, regression guards (non-claude not as claude_bpe; claude near boundary not as non_claude; n<8 never strong; unstable high residuals → ambiguous)

### Item 3: `distill+middleware` hypothesis in classifier
- New 5th hypothesis in `classify()` ranking
- Gate: `middleware ≥ 0.6` AND `tokenizer_non_claude ≥ 0.5`
- Without tokenizer data → A+Middleware gets annotation "distill+middleware unresolved"
- Codex-required A-clean veto: `tokenizer_non_claude ≥ 0.3` kills A-clean gate (not just opens distill+middleware)

### Item 4: Network evidence integration
- `classify()` accepts `network_evidence` dict with {aggressive_defense, middleware_software_detected, cdn_match_anthropic}
- Weights per your round-0 feedback: `aggressive_defense +0.2`, `middleware_software +0.4`, `cdn_match +0.09` (routing support only)
- Total network contribution capped at 0.5 (prevents load-bearing on forgeable signals)
- `fingerprint.py` gains `--network-probe-url` flag that co-runs `network_probe.py` inline

### Item 5: Tests per item (not batch at end, per your recommendation)
- `test_fingerprint.py`: 124 tests (109 existing + 15 new for v0.6 tokenizer/network)
- `test_mitm_capture.py`: 7 tests (new)
- `test_tokenizer_probe.py`: 33 tests (new)
- **164 total, 0 failures**

Codex-required regression tests added:
- Tokenizer absent → must NOT produce confident distill/MW split ✓
- Network alone → must NOT override behavioral evidence ✓
- A-clean without network probe → must NOT be penalized ✓
- Noisy tokenizer → must become ambiguous ✓
- Windows timeout → must kill descendants ✓

### Item 6: Live validation
Ran `fingerprint.py` on plain `claude --model claude-opus-4-7`:
```
Primary:    A-clean (Claude-like backend, no detectable middleware)
Score:      0.725
Confidence: high (gap to second: 0.425)
Gates passed: A-clean=True, A+Middleware=False, C=False, distill+middleware=False
Evidence:   middleware=0.0, capable_base=1.335, recent_cutoff=0.7
```
All 5 probes executed cleanly: clean_introspection (byte-distinct JSON across repeats), format_rigor_pass, post_april_2025_knowledge (knows Pope Leo XIV), soft_override_success, no false bias.

Validation PASS.

## Current deliverable state

```
.scratch/proxy-forensics/
├── fingerprint.py          v0.6, scorer 0.6.0, classify() extended
├── network_probe.py        v0.1
├── tokenizer_probe.py      v0.1 (NEW)
├── mitm_capture.py         v0.6 (subprocess fix)
├── parse_mitm_flow.py      utility
├── baselines.json          scorer_version=0.6.0
├── test_fingerprint.py     124 tests
├── test_tokenizer_probe.py 33 tests
├── test_mitm_capture.py    7 tests
├── README.md               v0.6
├── METHODOLOGY.md          v0.6
├── RESULTS.md              original investigation
├── NETWORK_FINGERPRINTS.md baseline network profiles
├── WIRE_CAPTURE_FINDINGS.md AW wire-capture evidence
└── SUSPECT_WORKFLOW.md     step-by-step checklist
```

## Remaining documented gaps (deferred)

- No quantization-degradation probe
- No multi-turn middleware probe
- No adversarial-probe-adaptation detection
- Narrow stylometric panel (one math problem)
- Automated `--regenerate-baselines` flag
- Hand-tuned thresholds (need labelled test set for real calibration)
- Tokenizer probe CLI-mediated baseline (not raw count_tokens; noted in output as `baseline_method`)

## Your task

Final review of v0.6. For each Item 1-6, assess:
1. Fix correctness
2. Any regressions introduced
3. Schema / contract semantics

Plus overall:
4. Does the combined evidence integration (network + tokenizer) preserve classifier robustness, or does it open new overconfidence paths?
5. Are the cap on network contribution and the gate on tokenizer correctly calibrated?
6. Any remaining issue that should block v0.6 as stable?

Output:
```
### Summary (2-3 sentences)
### Item-by-item status (1-6): FIXED / PARTIAL / REGRESSION
### Classifier robustness
### Any NEW issues in v0.6
### Verdict
GREEN (ship v0.6) / YELLOW (land with specific caveats) / RED (exact blockers)
```

If GREEN, confirm fit-for-purpose for "hypothesis generator on mixed-evidence axes". If RED, list blockers only.
