# Checkpoint 2a: Tokenizer probe output schema review

You asked for a checkpoint after Item 2 output schema lands before Items 3, 4, 5 build on it. Here's the schema + implementation.

## Files

- `.scratch/proxy-forensics/tokenizer_probe.py` (~240 lines, new)
- `.scratch/proxy-forensics/test_tokenizer_probe.py` (28 tests, 0 failures)

## Design adapted from your round-0 feedback

- 10 sentinels (within 8-12 range), paired short/long per character class:
  - ascii × 2 (short / long)
  - cyrillic × 2
  - cjk × 2
  - emoji × 1 (single — mixed character densities hard to pair meaningfully)
  - code × 2 (Python + JSON)
  - high-entropy hex × 1
- Least-squares fit `gateway_tokens = α · baseline_tokens + β`
- Classification checks: α ∈ [0.97, 1.03], |β| < 100 (absorbs CLI wrapping), max residual, repeat stability
- Verdicts: `claude_bpe` / `claude_bpe_weak` / `non_claude` / `ambiguous` / `insufficient_data`

## Design deviation from your recommendation, with rationale

You asked for `messages.count_tokens` API as the Anthropic-direct baseline (free, separate rate limit). I cannot use it: the only Anthropic-side creds on this system are a Claude CLI OAuth token (no API key), and `messages.count_tokens` requires raw API key auth.

**Fallback chosen**: make both baseline and gateway calls through the Claude CLI with minimal `max_tokens` (via `--effort low`). This costs a tiny amount (~$0.001-0.01/call) instead of free. The CLI wraps both paths with identical system-prompt content, so `β` absorbs that wrapping as a constant offset — α still tells us tokenizer match.

Explicit call-out in code header. Doc will note this as a v0.6 limitation: when a raw Anthropic API key is available, switch to `count_tokens` for cleaner baseline. Accepted trade-off?

## Output schema (JSON saved via `--save-raw`)

```json
{
  "probe_version": "0.1.0",
  "baseline_cmd": "claude",
  "gateway_cmd": "claude-aw.cmd",
  "model": "claude-opus-4-7",
  "gateway_model": "opus",
  "repeats": 2,
  "per_sentinel": {
    "ascii_short": {
      "text_len_chars": 5,
      "baseline_runs": [
        {"input_tokens": N, "cache_create": N, "cache_read": N,
         "total_input": N, "out_tok": N, "model_reported": "claude-opus-4-7",
         "msg_id_prefix": "msg_01..."}
      ],
      "gateway_runs": [...]
    },
    ...
  },
  "fit": {
    "labels": ["ascii_short", "ascii_long", ...],
    "baseline_tokens": [N, N, ...],   // averaged across repeats per sentinel
    "gateway_tokens": [N, N, ...],
    "residuals": [R, R, ...],
    "repeat_variances": [V, V, ...]
  },
  "verdict": {
    "alpha": 1.0,
    "beta": 7.0,
    "max_abs_residual": 0.5,
    "mean_abs_residual": 0.2,
    "repeat_variance_max": 1,
    "n_points": 10,
    "verdict": "claude_bpe",
    "reason": "alpha=1.000 ≈ 1, residuals ≤ 0.5, repeats stable"
  }
}
```

## Integration surface for Items 3/4/5

The output schema exposes these fields for downstream consumption by `classify()` in `fingerprint.py`:

```python
tokenizer_findings = tokenizer_probe_output["verdict"]
signal = tokenizer_findings["verdict"]  # "claude_bpe" | "non_claude" | "ambiguous" | "insufficient_data" | "claude_bpe_weak"
```

Item 3 (distill+middleware hypothesis) gate design:
- `distill_plus_middleware` hypothesis requires `tokenizer_findings["verdict"] == "non_claude"` AND middleware ≥ 0.6
- If tokenizer not run (flag absent, or still `insufficient_data`): emit `"distill+middleware unresolved"` annotation on A+Middleware verdict, not a separate hypothesis

Item 5 (test regression priorities):
- Test: `classify()` with tokenizer_findings=None must NOT commit to distill+middleware
- Test: `classify()` with `insufficient_data` must not flip A+Middleware to A-clean or C
- Test: mock `tokenizer_findings["verdict"]="non_claude"` + middleware=0.8 → correct distill+middleware verdict

## Unit test coverage (28 tests)

- least_squares_fit: exact (alpha=1, beta=7), proportional drift, noisy, degenerate (1 point, 0 points, same-x)
- classify_fit: 6 scenarios covering each verdict category + boundary cases
- SENTINELS composition: count, pairing, uniqueness, short/long length thresholds
- Regression guards: non-claude-like data must NOT be claimed as claude_bpe; claude-near-boundary must NOT escalate to non_claude

## Questions for your review

1. **Fallback CLI-mediated baseline instead of `count_tokens`**: acceptable trade-off given no raw API key, or should I require an API key and block v0.6 until provided?
2. **Thresholds**: α ∈ [0.97, 1.03] tight enough? |β| < 100 too permissive (absorbs CLI wrapping which could be ~40-60 tokens constant)?
3. **Sentinel set**: 10 prompts with pairing by class. Should emoji / high-entropy also be paired (currently single)?
4. **Verdict categories**: 5 categories (`claude_bpe`, `claude_bpe_weak`, `non_claude`, `ambiguous`, `insufficient_data`). Right granularity or collapse some?
5. **Integration contract for Item 3**: `non_claude` tokenizer + middleware → `distill+middleware`; any other combination should stay `unresolved`. Or should `non_claude` alone (without middleware) also trigger something (pure distill without gateway)?
6. **Per-sentinel repeat variance max 2 tokens for "stable"**: reasonable cutoff, or too strict?

Output format:
```
### Summary (2 sentences)
### Schema assessment (per field / design choice)
### Answers to 6 questions
### Blockers before Items 3, 4, 5 can build on this
### Verdict
APPROVE SCHEMA / MODIFY (list specific changes) / BLOCK (explain)
```

If APPROVE → I proceed to Item 4 (network integration), Item 3 (distill+middleware hypothesis with this schema), then Item 5 (tests), then Item 6 (live validation).

Be strict on schema semantics. Schema changes after Items 3/5 lock in are expensive.
