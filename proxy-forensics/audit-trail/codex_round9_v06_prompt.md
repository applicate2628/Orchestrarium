# Round-9 codex review: v0.6 final docs fix

Round 8: 3/4 PASS, 1 RED (stale docs). Applied:

- `README.md:9` "Status: v0.5" → "Status: v0.6" ✓
- `README.md:6` "toolkit does not distinguish real Claude from Claude-like distill..." rewritten to say v0.6 adds gated `distill+middleware` hypothesis; annotates "unresolved" when tokenizer not run ✓
- `METHODOLOGY.md:21` "distill+middleware a documented blind spot" rewritten to reference v0.6 gated hypothesis with unresolved-annotation fallback ✓
- Verified: no other stale v0.5 or "blind spot" / "does not distinguish" wording remains (only `### v0.5 (fourth codex review round)` in version-history section, which is legitimate historical reference)

## Files state

- `fingerprint.py` v0.6, 124 tests
- `tokenizer_probe.py` v0.1, 33 tests
- `mitm_capture.py` v0.6, 9 tests
- 166 total tests, 0 failures
- Live validation on plain claude-4.7: A-clean high confidence

## Request

Verify 4th blocker now PASS. Give final verdict.

Output:
```
### Blocker 4 status
### Verdict
GREEN (ship v0.6) / RED (exact remaining blocker)
```
