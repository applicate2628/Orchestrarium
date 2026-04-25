# Plan review: Proxy forensic toolkit v0.6 roadmap

Current state: `fingerprint.py` v0.5 GREEN (you validated after 6 rounds), plus `network_probe.py` v0.1 + `mitm_capture.py` v0.1 added in follow-up session (not yet reviewed by you). `RESULTS.md`, `METHODOLOGY.md`, `NETWORK_FINGERPRINTS.md`, `SUSPECT_WORKFLOW.md`, `WIRE_CAPTURE_FINDINGS.md` all landed at v0.5 state.

User now wants to close these gaps before the next suspect arrives, with a v0.6 pass that goes through you for review.

## Proposed v0.6 scope (7 items)

### Item 1: Fix `mitm_capture.py` subprocess hang on Windows
**Problem**: `subprocess.run(shell=True, timeout=N)` on Windows doesn't actually kill shell-spawned children on timeout. mitm_capture hung indefinitely in live test, required external `taskkill`.

**Fix design**: replace `subprocess.run` with `Popen` + poll-loop with deadline + `taskkill /F /T /PID` (Windows) or `os.killpg(SIGKILL)` (POSIX) on timeout. New `--subprocess-timeout` flag (default 60s).

**Effort**: ~30min, already drafted in mitm_capture.py.

### Item 2: `tokenizer_probe.py` — tokenizer identity check
**Rationale**: `RESULTS.md` cites "constant +7 tokenizer offset" as key evidence that AW uses Claude BPE (not a non-Claude base fine-tuned on Claude outputs). But toolkit does not reproduce this; it's noted as a known gap.

**Design**:
- Send 4-5 sentinel strings of varied character classes:
  - Pure ASCII (short / long)
  - Mixed Unicode (Cyrillic / CJK / emoji)
  - Code snippet (Python / JSON)
  - Base64 / hex high-entropy
- Capture each response's `usage.input_tokens`
- Compute local Claude BPE count using either `anthropic.tokenize()` SDK call OR a cheap Anthropic-direct comparison request (same prompt through plain `claude`)
- Fit: `gateway_tokens = baseline_tokens + constant_offset` (linear regression on 4-5 points)
- Output:
  - `constant_offset: N` → likely same tokenizer + injected prefix (Claude family)
  - `proportional_drift: R²` → different tokenizer (non-Claude base)
  - `noisy_mixed`: neither fits cleanly → ambiguous

**Budget**: ~$1-2 on gateway + ~$1-2 on Anthropic-direct baseline (4-5 short prompts each). Total ~$3-4.

**Output**: new `tokenizer_probe.py` script + JSON results file. Integration with `fingerprint.py` classifier via new signal `tokenizer_match: {claude | non-claude | ambiguous}`.

**Effort**: ~2h.

**Concerns for review**:
- Is linear regression across 4-5 sentinels enough to discriminate tokenizer identity reliably?
- Should we use raw `count_tokens` API instead of comparing full request calls (cheaper, more deterministic)?
- What's the right number of sentinel strings?

### Item 3: Add `distill+middleware` hypothesis class to classifier
**Rationale**: Current classifier has 4 hypotheses (A+Middleware, A-clean, C distill, ambiguous). You flagged in round 3-4 that a high-quality distilled student fronted by the same middleware would classify as A+Middleware — indistinguishable. This is the "distill+middleware" blind spot.

**Design**:
- Add 5th hypothesis: `distill+middleware` (Claude-like-trained student + active gateway)
- Gate: requires `middleware ≥ 0.6` AND `tokenizer_non_claude_evidence ≥ 0.5` (needs Item 2 tokenizer probe signal)
- If tokenizer probe not run: emit WARNING that this hypothesis cannot be distinguished from A+Middleware without tokenizer evidence, and default to A+Middleware (current behavior) — but annotate verdict with caveat.

**Effort**: ~1h (after Item 2).

**Concerns for review**:
- Is tokenizer mismatch the only disambiguator, or should we add other signals (e.g. numerical precision for quantization detection bleeding through)?
- Should gate require BOTH middleware + tokenizer_non_claude, or EITHER? What's the false-positive risk?

### Item 4: Wire `network_probe` signals into `fingerprint.py` classifier
**Rationale**: Network evidence (aggressive_defense, CDN match, proxy signatures) is orthogonal to LLM behavior. Currently manual correlation per `SUSPECT_WORKFLOW.md`. Should feed into unified `classify()`.

**Design**:
- `fingerprint.py` gains optional `--network-probe-url <url>` flag
- When set, runs `network_probe.py` logic pre-LLM-probes, stores network evidence
- `classify()` adds new evidence weights:
  - `aggressive_defense=True` → +0.4 middleware
  - `cdn=cloudflare` + `anthropic-ratelimit-*` → +0.3 capable_base (legit routing evidence)
  - `middleware_signatures detected` (LiteLLM/Portkey/etc) → +0.5 middleware
  - `no_valid_http` → flag as operational issue (not evidence)
- A-clean gate tightened: `cdn_match_anthropic == True` required for high-confidence A-clean

**Effort**: ~2-3h.

**Concerns**:
- Over-weighting network evidence (forgeable by any proxy)?
- What's the right weight for each signal type?
- Should network probe run on every fingerprint, or only when explicitly requested?

### Item 5: Unit tests for `network_probe.py`, `mitm_capture.py`, `tokenizer_probe.py`
**Rationale**: `fingerprint.py` has 109 tests; other scripts have none.

**Design**:
- `network_probe`: test `detect_proxy_software()` with mock headers, `classify_network_evidence()` with mock inputs, edge cases (aggressive_defense detection with various TLS error strings)
- `mitm_capture`: test `_kill_tree()` safely (mock subprocess), flow parser (mock flow file)
- `tokenizer_probe`: test offset fitting with mock point sets (constant / proportional / noisy), edge cases (1 point, 2 points, high variance)

**Effort**: ~1-2h.

### Item 6: Live validation on plain `claude --model claude-opus-4-7`
**Rationale**: We have never run the full `fingerprint.py` pipeline on a known-good A-clean target. The toolkit was validated via synthetic unit tests + AW live test only. A live baseline validation confirms that the classifier correctly identifies official Claude as A-clean high confidence.

**Budget**: ~$1-2 for 5 probes × 2 repeats on Opus 4.7 direct.

**Effort**: ~5min.

### Item 7: Round-7 codex review of v0.6
After items 1-6 land and unit tests pass, submit full diff for your review.

## Order of execution

1. Item 1 (quick fix, unblocks future work)
2. Item 2 (tokenizer probe — biggest new capability, independent)
3. Item 3 (distill+middleware, depends on Item 2)
4. Item 4 (network integration, independent)
5. Item 5 (unit tests for all new code, depends on Items 1-4)
6. Item 6 (live validation)
7. Item 7 (codex review)

## Questions for your review BEFORE we start coding

1. **Is this scope right?** Are we missing anything that should be in v0.6, OR should anything be deferred further?
2. **Item 2 tokenizer probe design**: use `count_tokens` API (cheap, deterministic) or compare full-request `usage.input_tokens`? Which is more reliable for detecting tokenizer drift?
3. **Item 3 gate logic**: tokenizer-only disambiguator for distill+middleware, or add more signals?
4. **Item 4 network weights**: is 0.4 for aggressive_defense reasonable, or should it be higher/lower?
5. **Item 5 test priorities**: is there a specific regression I should guard against, given what you've flagged across previous rounds?
6. **Priority order**: should any item move earlier/later, given diminishing returns vs blocker status?

Output format:
```
### Summary (2-3 sentences)
### Item-by-item assessment
1. FIX: ok as described / modify / reconsider
2. TOKENIZER: [design verdict + specific recommendations]
3. DISTILL+MW: [gate logic recommendation]
4. NETWORK INTEGRATION: [weight calibration advice]
5. UNIT TESTS: [specific high-value test cases I'm missing]
6. LIVE VALIDATION: ok / change
7. REVIEW TIMING: ok / change

### Answers to 6 questions

### Overall
PROCEED / MODIFY SCOPE (list changes) / RECONSIDER FIRST (explain)
```

Be strict. If the plan has structural issues, flag before coding starts. If it's reasonable, say PROCEED so we can start with Item 1.
