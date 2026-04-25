# Claude Proxy Forensic Toolkit — v0.6

Fingerprint any Claude-compatible CLI endpoint (official `claude`, third-party wrappers like `claude-aw.cmd`, aggregator proxies) to estimate:

- Provider routing (Anthropic direct, Google Vertex, AWS Bedrock, aggregator)
- Whether the backend matches a frontier-Claude signature, a distilled student signature, or an imitator. v0.6 adds a gated `distill+middleware` hypothesis class that fires when tokenizer evidence indicates non-Claude BPE together with active middleware; without tokenizer evidence, A+Middleware verdicts are annotated "distill+middleware unresolved" instead of silently assuming real Claude.
- What middleware layers the gateway adds (stripping, injection, interception, spoofing)

**Status: v0.6, hypothesis generator**, not adjudicating forensic classifier. Use results as an investigative starting point, not as legal/security-grade proof. See `METHODOLOGY.md` for caveats and known gaps.

## Files

- **`fingerprint.py`** — main executable. Runs LLM-behavior probe battery, classify with confidence-graded verdict. Optional `--network-probe-url` + `--tokenizer-probe-raw` for cross-evidence.
- **`network_probe.py`** — TLS/headers/timing/proxy-software signatures. No LLM tokens. Standalone OR fed into `fingerprint.py`.
- **`tokenizer_probe.py`** — tokenizer-identity probe (10 sentinels, α·β linear fit, `claude_bpe`/`non_claude`/etc verdicts). Cheap (~$0.50/run).
- **`mitm_capture.py`** — one-shot HTTPS capture via mitmproxy (requires `pip install mitmproxy`). Windows-safe subprocess kill via `taskkill /F /T /PID`.
- **`parse_mitm_flow.py`** — parses saved mitmproxy `.flow` files.
- **`baselines.json`** — cached Anthropic-direct Opus 4.5/4.6/4.7 outputs (scorer_version=0.6.0).
- **`RESULTS.md`** — original `claude-aw.cmd` investigation findings.
- **`METHODOLOGY.md`** — protocol, decision tree, caveats.
- **`NETWORK_FINGERPRINTS.md`** — baseline network fingerprints.
- **`SUSPECT_WORKFLOW.md`** — step-by-step checklist.
- **`WIRE_CAPTURE_FINDINGS.md`** — AW wire-capture evidence.
- **`test_fingerprint.py`** — 124 unit tests.
- **`test_mitm_capture.py`** — 7 unit tests (subprocess kill + flow parser).
- **`test_tokenizer_probe.py`** — 33 unit tests (fit, classify, sentinel composition).

## Version changes

### v0.6 (fifth codex review round — current)

- **Tokenizer identity probe** (`tokenizer_probe.py`): sends 10 sentinels through baseline + suspect paths, fits `gateway = α·baseline + β`, verdicts `claude_bpe` / `claude_bpe_weak` / `non_claude` / `ambiguous` / `insufficient_data`. Requires n_points ≥ 8 for strong verdicts.
- **`distill+middleware` hypothesis** added to classifier: gated on `tokenizer_non_claude ≥ 0.5` AND `middleware ≥ 0.6`. Without tokenizer data, A+Middleware is annotated "distill+middleware unresolved" instead of silently assuming real Claude.
- **Network evidence integration**: `--network-probe-url` flag feeds TLS/CDN/aggressive-defense signals into classifier (capped contribution, not load-bearing).
- **Tokenizer non_claude vetoes A-clean**: gates now require `tok_nc < 0.3` for high-confidence A-clean.
- **Subprocess hang fix** in `mitm_capture.py`: replaces `subprocess.run(shell=True, timeout)` with `Popen` + poll-loop + `taskkill /F /T /PID` on Windows.
- **Live validation**: plain `claude --model claude-opus-4-7` reliably classifies as A-clean high confidence. 124 unit tests pass.

### v0.5 (fourth codex review round)

- Classifier has **hard evidence gates**: A+Middleware requires middleware ≥ 0.6 AND capable_base ≥ 0.5; A-clean requires capable_base ≥ 0.6 AND middleware < 0.4 AND suspicious_intercept < 0.3; C requires distill ≥ 0.6 AND capable_base < 0.5. Hypotheses failing their gate can't reach high confidence.
- **Introspection schema validation**: probe 4 only signals `clean_introspection` when all four required fields (`architecture_family`, `supports_extended_thinking`, `can_use_prompt_caching`, `knowledge_cutoff_month`) are present with credible types. JSON that parses but fails schema emits `schema_mismatch` and counts as middleware evidence.
- **Protocol-object detection stricter**: single-object JSON must have `result` string AND one of (usage dict with token counts / model string starting `claude-` / session_id ≥ 8 chars). Gateways like `{"result":"{\"acknowledged\":true}"}` now correctly classify as intercept.
- **Variable/inconsistent intercept penalizes A-clean**: adaptive gateways varying responses can no longer be classified clean.
- **Soft-override scored conditionally**: `soft_override_success` only fully counts as capable-base evidence when stylometric bias was first observed. On a neutral prompt, override success is weak (0.3× multiplier).
- **Temporal cutoff requires verifiable events**: generic `"June 2025"` hallucinations no longer promote cutoff to post-April.
- **Parser type-guards stream-list elements**: lists containing scalars correctly emit `parse_error`.

### v0.3

- Parser distinguishes `valid_single_object` (newer CLI) from `intercepted`.
- `status_failure` runs no longer convert to `rigid_bias` / `format_rigor_fail`.
- `hard_intercept` requires ≥ 2 repeats.
- Raw hash computed from bytes (not decoded text).
- Superscript regex matches only `⁴`.
- Missing/malformed `expiry_date` fails closed.

### v0.2

- Parser separates `cli_error` / `parse_error` / `intercepted` / `valid_stream`.
- Multi-run repeat support via `--repeats N` (default 2).
- Confidence-graded classification (`high` / `medium` / `low`).
- Hardened regexes: Unicode math, variant multiplication, phrasing.
- Baseline expiry check.
- Raw SHA-256 hash per run.
- `--shell` injection warning.
- Sentence splitter handles abbreviations.

## Quick start

List probes:

```bash
python fingerprint.py --list-probes
```

Fingerprint a Windows `.cmd` wrapper (default 2 repeats):

```bash
python fingerprint.py --label "AW" --cmd "claude-aw.cmd --model opus" --shell
```

Plain `claude` call:

```bash
python fingerprint.py --label "direct" --cmd "claude --model claude-opus-4-7"
```

Single run (cheaper, but no cross-run consistency check → lower confidence):

```bash
python fingerprint.py --label "AW" --cmd "claude-aw.cmd --model opus" --shell --repeats 1
```

Only specific probes:

```bash
python fingerprint.py --label "AW" --cmd "claude-aw.cmd --model opus" --shell \
  --probes self_introspection_json anti_euler_override
```

Save raw findings + classification:

```bash
python fingerprint.py --label "AW" --cmd "claude-aw.cmd --model opus" --shell \
  --save-raw results_aw.json
```

Run network fingerprint alongside (orthogonal evidence, no API cost):

```bash
python network_probe.py --url https://api.claudecodeapi.cloud --label AW \
  --save-raw results_aw_network.json
```

Run tokenizer probe for backend-identity evidence (distinguishes real Claude from non-Claude-tokenizer backends):

```bash
python tokenizer_probe.py \
  --baseline-cmd "claude" \
  --gateway-cmd "claude-aw.cmd" --gateway-shell \
  --model claude-opus-4-7 --gateway-model opus \
  --repeats 2 --save-raw tokenizer_aw.json
```

Combined v0.6 run (all evidence axes):

```bash
python fingerprint.py --label "AW" --cmd "claude-aw.cmd --model opus" --shell \
  --network-probe-url https://api.claudecodeapi.cloud \
  --tokenizer-probe-raw tokenizer_aw.json \
  --save-raw results_aw_full.json
```

Network probe detects:
- TLS cert details, cipher suite, protocol version
- Known proxy-software signatures (Cloudflare, LiteLLM, Portkey, OpenRouter, Helicone, etc.)
- Anthropic-specific headers
- Aggressive-defense patterns (server drops TCP/TLS without proper HTTP response)
- Timing / latency distribution

Example comparison (as of baseline collection):

| Target | aggressive_defense | CDN | Server | Median latency | Jitter |
|---|:-:|---|---|---:|---:|
| `api.anthropic.com` | No | Cloudflare | cloudflare | ~380 ms | ~60 ms |
| `api.claudecodeapi.cloud` | **Yes** | none | nginx (when reachable) | >3000 ms | >5000 ms |

## Probe battery

Five single-turn probes. Each targets one axis. None is decisive on its own — verdict requires multiple probes pointing the same way across ≥ 2 repeats.

| Probe | Axis | Detects | Decisive alone? |
|---|---|---|:-:|
| `stylometric_717` | Canonical opening | Generation, injected bias | No |
| `temporal_cutoff` | Training recency | Release era | No |
| `tight_reasoning_crt` | Format compliance + rigor | Capability tier | No |
| `self_introspection_json` | Active gateway filter | Middleware (if reproducible) | Only if byte-exact across repeats |
| `anti_euler_override` | Soft-injection vs distill | Bias overrideability | No, but informative with `stylometric_717` |

**Key methodological note:** the anti-Euler probe only tells you *"bias was overrideable in this prompt"*, not *"backend is Claude-like backend"*. An adaptive/probe-aware proxy can also pass it. Treat results as Bayesian updates, not proofs.

## Output format

```
=== CLASSIFICATION ===
  Primary:    A+Middleware (Claude-like backend + active gateway)
  Score:      0.756
  Confidence: high (gap to second: 0.412)

  Ranked hypotheses:
     0.756  A+Middleware (Claude-like backend + active gateway)
     0.344  A-clean (Claude-like backend, no detectable middleware)
     0.280  ambiguous / insufficient evidence
     0.000  C (distilled student)

  Evidence weights: {'middleware': 1.25, 'capable_base': 1.15, 'distill': 0.0, 'recent_cutoff': 0.7, 'feature_strip': 0.6}

  Scoring notes:
    - Middleware: hard_intercept +0.90
    - Capable-base: soft_override_success +0.85
    - Capable-base: format_rigor_pass +0.80
    - Recent-cutoff: post_april_2025 +0.70
    - Middleware: feature_strip +0.18
```

Confidence levels:

- **high** — primary score ≥ 0.55 AND gap to second hypothesis ≥ 0.2. Actionable.
- **medium** — primary score ≥ 0.35 AND gap ≥ 0.1. Use as working hypothesis; collect more evidence before committing.
- **low** — neither threshold met. Run more repeats, add probes, or capture mitmproxy HTTPS.

## Cost

Per target: roughly `5 probes × N repeats × ~$0.05-0.10 per call`. Default `--repeats 2` → ~$0.50-1.00 per target. Baseline regeneration (when triggered): ~$3 for 15 Opus calls.

## Known gaps (v0.6)

See `baselines.json → interpretation_rules.known_gaps` for the full list. Highlights:

- ✅ ~~No tokenizer-identity probe~~ — **implemented in v0.6** (`tokenizer_probe.py`). Uses CLI-mediated baseline (not raw Anthropic `count_tokens` API). Strong verdicts require n_points ≥ 8. Upgrade to API-key-based count_tokens reduces cost; identical semantics.
- ✅ ~~No `distill+middleware` hypothesis~~ — **added in v0.6**. Gated on `tokenizer_non_claude ≥ 0.5` AND `middleware ≥ 0.6`. Without tokenizer data, A+Middleware verdict is annotated "distill+middleware unresolved".
- **No quantization-degradation probe.** An int8-quantized Claude could pass the current battery. Planned future work.
- **No multi-turn probe.** Session-level middleware (cache-across-turns manipulation, session-boundary injection) is invisible here.
- **Narrow stylometric panel.** Single math problem gives narrow signal. Broader panel (safety refusals, code formatting, XML/tool-call conventions) would improve imitator detection.
- **Temporal probe rotation.** The 2025-event calibration will lose discriminative power as those events become general knowledge (~2027). Rotate during baseline regeneration.
- **Thresholds hand-tuned, not calibrated.** `0.55 / 0.35` confidence thresholds are heuristics. Proper calibration requires a labelled test set across provider types.
- **No adversarial-probe-adaptation detection.** If a gateway specifically counters our probe set, we won't notice without prompt rotation.

## Extending

Add a probe:

1. Edit `baselines.json`: add entry under `probes` with `prompt`, `purpose`, and `baselines` (collect officials once).
2. Implement a scorer in `fingerprint.py`: `score_run_<probe_id>()` function + entry in `PROBE_SCORERS` dict.
3. Implement aggregation in `aggregate_probe()` for the new `probe_id`.
4. Optionally thread scoring into `classify()` evidence weights.

## Security notes

- `--shell` (needed for `.cmd` wrappers on Windows) is command-injection unsafe if `--cmd` comes from an untrusted source. The toolkit prints a warning but cannot sandbox.
- The toolkit runs arbitrary subprocess commands against third-party gateways. Review your provider's ToS before automated probing.

## Trust model

Under what assumptions do classifications hold:

1. Target honors standard Claude Code CLI flags (`-p`, `--model`, `--effort`, `--tools ""`, `--output-format json`).
2. Tool invocation is *actually* disabled — target didn't secretly call WebSearch to pass the temporal cutoff probe.
3. Gateway is not probe-adaptive (if it knows the anti-Euler prompt and selectively complies, we can't detect that here).
4. Sampling variance on single calls doesn't flip the verdict — use `--repeats ≥ 2` for stability.
5. Baselines are fresh (within `expiry_date` window).

If any of these fail, verdict reliability drops sharply.
