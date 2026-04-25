# New Suspect Investigation Workflow

Step-by-step checklist for investigating a new Claude-compatible proxy endpoint. Run these in order.

## Prerequisites

- [ ] Toolkit is at latest version (`SCORER_VERSION` in `scripts/fingerprint.py` matches `scorer_version` in `scripts/baselines.json`)
- [ ] Baselines are not expired (`metadata.expiry_date` in `scripts/baselines.json` is in future)
- [ ] `claude.exe` (v2.1.x) on PATH for official baseline comparison
- [ ] Target is accessible (manual `curl -I <url>` or a simple `--effort low -p "hi"` call succeeds at least once)

## Step 1. Gather target metadata

Capture before running any probe:

- [ ] **Command shape**: `claude-<name>.cmd --model X`, or plain `claude --model X`, or something else?
- [ ] **Gateway URL** (read from the wrapper script — usually `set ANTHROPIC_BASE_URL=...`)
- [ ] **Credential mechanism**: token in wrapper, env var, ambient OAuth?
- [ ] **Claimed backend**: what does the wrapper / operator claim runs on the other end?
- [ ] **Notes about context**: is it a paid service, a free trial, a pirate relay, a known operator?

## Step 2. Network-level fingerprint

**Cost**: zero LLM tokens (only TLS/HTTP HEAD requests)

```bash
python scripts/network_probe.py --url <gateway-url> --label "<name>" \
  --save-raw network_<name>.json
```

Note:
- [ ] `tls_ok`: yes / no / intermittent
- [ ] `aggressive_defense`: true / false
- [ ] `proxy_software_detected`: list (Cloudflare / LiteLLM / Portkey / etc.)
- [ ] `anthropic_direct_headers`: true / false (check auth'd response manually if false on unauth'd)
- [ ] `latency_median_ms`, `jitter_ms`
- [ ] Server header value

Compare against `NETWORK_FINGERPRINTS.md` baselines. Flag:
- Matches known legit path (Cloudflare + anthropic-direct headers) → possible legit reseller relaying to Anthropic
- Aggressive defense without CDN → likely custom middleware
- Custom CDN signature (Fly.io / Render / Railway) → hosted elsewhere, not relaying Anthropic directly

## Step 3. End-to-end LLM fingerprint

**Cost**: ~$0.50-1.50 per target depending on gateway pricing

```bash
python scripts/fingerprint.py --label "<name>" --cmd "<command>" --shell \
  --repeats 2 --save-raw results_<name>.json
```

Note verdict:
- [ ] Primary hypothesis (A+Middleware / A-clean / C / ambiguous)
- [ ] Confidence (high / medium / low)
- [ ] Gates passed (A+Middleware / A-clean / C)
- [ ] Evidence weights (middleware, capable_base, distill, recent_cutoff, feature_strip, suspicious_intercept)
- [ ] Any probe-level anomalies (timeouts, failed runs, inconsistent outputs)

## Step 4. Cross-evidence interpretation

Combine Step 2 + Step 3 findings:

| Step 2 | Step 3 | Likely interpretation |
|---|---|---|
| Cloudflare + anthropic-direct headers present | A-clean, high confidence | Legit Anthropic reseller |
| Cloudflare + no anthropic-direct headers | A+Middleware, any confidence | Third party using Cloudflare but NOT Anthropic |
| Aggressive defense + A+Middleware verdict | — | Custom middleware gateway — same pattern as original AW investigation |
| Aggressive defense + A-clean verdict | — | Conflict — re-examine classification |
| No network evidence + C distill verdict | — | Non-Anthropic backend, likely distill |
| Clean network + ambiguous verdict | — | Not enough LLM evidence; increase `--repeats` or add manual probes |

## Step 5. Escalation (optional, high-stakes only)

If verdict is ambiguous OR the decision has security / compliance / financial stakes:

- [ ] **mitmproxy HTTPS capture**: set up local intercepting proxy, capture actual `/v1/messages` request body. Reveals injected system prompt content, exact parameter handling. Setup: 30-60 min. See `NETWORK_FINGERPRINTS.md` for how to interpret the capture.
- [ ] **Tokenizer probe**: run `python scripts/tokenizer_probe.py --baseline-cmd "claude" --gateway-cmd "<suspect>" --gateway-shell --model claude-opus-4-7 --gateway-model opus --repeats 2 --save-raw tokenizer_<name>.json`. 10 sentinels, α·β linear fit, verdicts `claude_bpe`/`claude_bpe_weak`/`non_claude`/`ambiguous`/`insufficient_data`. Feed into `scripts/fingerprint.py --tokenizer-probe-raw tokenizer_<name>.json` to integrate into the classifier (opens `distill+middleware` hypothesis when `non_claude`, vetoes A-clean high confidence; `insufficient_data` / `ambiguous` → no classifier effect).
- [ ] **Opus 4.7 max expert consultation**: send full evidence dump to `claude -p --model claude-opus-4-7 --effort max` for independent re-ranking (template: `investigation/consult_opus47*.py`).

## Step 6. Document findings

Add an entry to `NETWORK_FINGERPRINTS.md` (sibling doc) with the new target's network profile. Archive raw JSON outputs (`network_<name>.json`, `results_<name>.json`) under `examples/<date>-<name>/` or your preferred local investigations directory.

## Common pitfalls

- **Env var `CLAUDE_CODE_EFFORT_LEVEL`** is inherited by subprocess and can affect outputs. The toolkit forces `--effort max` via CLI flag, so env var is normally overridden, but be aware.
- **`--shell True`** is required for `.cmd` wrappers on Windows. Command injection risk — never pass an untrusted `--cmd` value.
- **Sampling variance**: `--repeats 1` is unreliable for classification. Default 2, use 3+ for high-stakes targets.
- **Baseline drift**: if baselines are >90 days old or Anthropic has released a new Opus generation, regenerate before running comparisons. Tool blocks strong verdicts past `expiry_date`.
- **Cost reporting**: `cost_usd` returned by third-party gateways is often fabricated. Trust `out_tok`, `text`, `msg_id` prefix, `cache_create/read`.
- **Tool use**: always pass `--tools ""` (automatic in `scripts/fingerprint.py`). Otherwise WebSearch can fetch current events and defeat the temporal-cutoff probe.
- **Rate limits / aggressive defense**: some gateways limit probe frequency or actively drop probe-shaped requests. Space runs, try fallback methods (POST vs GET), or escalate to mitmproxy.

## Sanity check for new toolkit changes

Before applying the toolkit to a new important suspect:

- [ ] `python scripts/tests/test_fingerprint.py` → 134 tests pass (v0.6.1)
- [ ] `python scripts/tests/test_tokenizer_probe.py` → 33 tests pass
- [ ] `python scripts/tests/test_mitm_capture.py` → 9 tests pass
- [ ] `python scripts/fingerprint.py --list-probes` → 5 probes listed
- [ ] Run on a known baseline (plain `claude --model claude-opus-4-7`) and confirm A-clean high confidence (score ≈ 0.72, gap ≈ 0.42)
- [ ] Run on AW (known A+Middleware-like) and confirm that verdict (may be medium confidence due to gateway adaptation)
