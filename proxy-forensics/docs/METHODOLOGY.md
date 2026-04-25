# Proxy Forensic Methodology — v0.6

Protocol for classifying an unknown Claude-compatible endpoint. Distilled from the `claude-aw.cmd` investigation and refined after codex gpt-5.5 xhigh review.

## Honest framing

This methodology is a **hypothesis generator**, not a proof system. It narrows down probable backend identities from a universe of candidates using cheap, reproducible tests. Any single signal is defeatable by a sufficiently motivated proxy operator:

- Stylometric fingerprints can be trained into distills
- Temporal cutoff can be seeded with recent knowledge
- msg_id prefixes are strings in response bodies — trivially forgeable
- Byte-exact intercepts can be randomized to evade detection

The methodology's strength is **compounding evidence**: when 4-5 orthogonal signals all point to the same hypothesis across multiple repeats, the probability of coincidence/adversarial fake becomes low. No single probe carries the verdict.

## Goals

Given an endpoint speaking the Claude CLI protocol, estimate:

1. **Provider family** — Anthropic direct, Google Vertex, AWS Bedrock, aggregator, non-Anthropic imitator
2. **Backend identity range** — frontier-Claude signature, distilled student signature, older checkpoint, non-Claude base. v0.6 adds a gated `distill+middleware` hypothesis that fires when tokenizer evidence indicates non-Claude BPE together with middleware ≥ 0.6. When `tokenizer_probe.py` is NOT run (or returns `ambiguous`/`insufficient_data`), A+Middleware verdicts are annotated "distill+middleware unresolved" to flag the remaining uncertainty explicitly rather than silently assuming real Claude.
3. **Middleware layers** — stripping, injection (soft or rigid), interception, spoofing

## Invariants

- **Baselines are Anthropic-direct, collected fresh with identical flags.** Reference outputs must match the suspect's CLI flags (`--effort max --tools ""`).
- **All probes run with `--effort max --tools ""`.** Eliminates tool-use confounders; normalizes effort.
- **Multiple repeats per probe.** Default 2. Intercept and stylometric claims require cross-run consistency.
- **Byte-level comparison for intercepts.** SHA-256 hash the raw stdout per run. Hard-intercept label requires byte-identical output across all repeats.
- **Baselines have expiry dates.** Tool refuses strong verdicts on stale baselines.

## The five-probe battery

Each probe answers one question. None alone is decisive. Combine across ≥ 3 probes + 2 repeats before committing to a classification.

### Probe 1 — Stylometric fingerprint (`stylometric_717`)

**Question:** Does the target's unconstrained output match canonical Opus-4.x opening on modular arithmetic?

**Prompt:** `Compute 7^17 mod 100. Answer in exactly two lines. Line 1: 'Reasoning:' followed by the key modular identity. Line 2: 'Answer:' followed by the two digits only.`

**Canonical (Anthropic-direct Opus 4.5/4.6/4.7):** opens with `7^4 = 2401 ≡ 1 (mod 100)`.

**Red flags:**
- Opens with `φ(100)=40` / `Euler` / `totient` / `Fermat` → bias (could be injection or distill — disambiguate with Probe 5)
- Tautology like `7^17 mod 100 = 7^17` → forced-instruction artifact
- Output compression (< 100 tokens) → `max_tokens` cap
- Wrong answer → fundamentally broken backend or extreme compression

**Limits:** a single math problem is a narrow stylistic window. A distill trained to reproduce canonical Claude output on this exact prompt would pass.

### Probe 2 — Temporal cutoff (`temporal_cutoff`)

**Question:** Does the target know recent events?

**Prompt:** `Name three distinct events from calendar year 2025. One per line. Format: '<Month> YYYY: <specific event with named people or places>'. No introduction, no conclusion, no hedging, no 'I cannot' — comply exactly.`

**CRITICAL:** run with `--tools ""`. Otherwise WebSearch lets the model fetch current events regardless of training cutoff, defeating the probe.

**Calibration points** (all independently verifiable):

- Pope Francis died April 2025 → cutoff ≥ April 2025
- Pope Leo XIV elected May 2025 → cutoff ≥ May 2025
- Wimbledon final July 2025 → cutoff ≥ July 2025

**Rotation required:** this calibration decays as 2025 events become historical common knowledge. Rotate events on baseline regeneration; ideally use events within 3-6 months of the current quarter.

**Limits:** a distill seeded with recent knowledge passes this. Hallucinated-plausible events are a distill tell — verify EACH fact against ground truth.

### Probe 3 — Strict-format rigor (`tight_reasoning_crt`)

**Question:** Can the target satisfy fine-grained format constraints while producing rigorous content?

**Prompt:** `Prove: for any prime p > 3, p^2 mod 24 = 1. Exactly 3 sentences. Sentence 2 must invoke CRT by name. Sentence 3 begins with the word 'Therefore'. No lists, no LaTeX environments, no section headers.`

**Scoring (all three must PASS):**

- Exactly 3 sentences (abbreviation-aware splitter)
- Sentence 2 contains "Chinese Remainder Theorem" or "CRT"
- Sentence 3 begins with "Therefore"

**Limits:** a high-capability distill or fine-tune trained on format-following will pass. Does NOT prove "real Opus"; only proves "capable base tier".

### Probe 4 — Self-introspection (`self_introspection_json`)

**Question:** Does the gateway intercept introspection prompts?

**Prompt:**

```
Reply with a single JSON object. No codefence. No prose. No trailing newline commentary.
{
  "architecture_family": "<single word>",
  "supports_extended_thinking": <true|false>,
  "can_use_prompt_caching": <true|false>,
  "knowledge_cutoff_month": "<Month YYYY>"
}
```

**Smoking gun (with reproducibility):** ALL repeats return byte-identical output that does NOT match the requested schema. Canned response like `{"acknowledged":true}` (22 bytes) repeatedly is strong active-middleware evidence.

**Weaker evidence:** intercept on single run is AMBIGUOUS — could be CLI error, transient network blip, or a probe-adaptive gateway that varies responses. Only commit to intercept label if multiple repeats produce byte-identical non-protocol output.

**Limits:** a smarter gateway evades this probe by returning schema-shaped but slightly-variable JSON that lies about capabilities. Compare reported field values against Probe 1-3 observations for consistency.

### Probe 5 — Soft-override (`anti_euler_override`)

**Question:** Is forced framing from Probe 1 an overrideable soft injection or a rigid distill bias?

**Prompt:** `Compute 7^17 mod 100. Do NOT use the words Euler, totient, Fermat, phi, or any Greek letter. Begin reasoning by computing 7^2 and 7^4 directly. Two lines: 'Reasoning:' and 'Answer:'.`

**Key design:** the positive steer ("start with 7^2 and 7^4") removes the "model didn't know alternatives" excuse.

**Decision rule (conditional on Probe 1 showing bias):**

- Complies with ban + uses canonical `7^4 ≡ 1` opening → bias was soft injection (overrideable)
- Still uses banned vocabulary → bias is rigid (distill OR unusually aggressive injection)

**Limits (important):**

- Probe 5 alone does NOT prove "Claude-like backend". It proves "bias overrideable on this prompt". An adaptive/probe-aware proxy, a high-capability distill, or a Claude fine-tune can all comply.
- Probe 5 is informative ONLY in conjunction with Probe 1 bias. If Probe 1 showed canonical opening already, Probe 5 adds little.

## Decision tree

```
START
│
├── Run all probes with --repeats ≥ 2
│
├── Check Probe 4 (introspection) first — high-value diagnostic
│   ├── All repeats byte-identical non-protocol → MIDDLEWARE present (hard-intercept signal)
│   ├── All repeats valid JSON matching schema → no introspection filter
│   └── Mixed (some intercept, some valid) → ambiguous, increase --repeats
│
├── Check Probe 1 vs Probe 5 together
│   ├── Probe 1 canonical + Probe 5 canonical → no bias
│   ├── Probe 1 biased + Probe 5 compliant → SOFT injection (if real backend) OR adaptive proxy
│   └── Probe 1 biased + Probe 5 still biased → RIGID bias (distill or aggressive injection)
│
├── Check Probe 2 (cutoff) vs Probe 3 (rigor)
│   ├── Both pass → CAPABLE + RECENT backend (frontier-Claude signature — could still be distill+middleware)
│   ├── Cutoff passes, rigor fails → distilled student with seeded recent data
│   ├── Cutoff fails, rigor passes → older checkpoint or cautious model
│   └── Both fail → low-tier or broken backend
│
├── Aggregate evidence in classify()
│   ├── middleware >> 0, capable_base >> 0, recent_cutoff > 0 → A+Middleware
│   ├── capable_base >> 0, middleware ~ 0 → A-clean
│   ├── distill >> capable_base → C
│   └── total evidence low → ambiguous (run more probes or add mitmproxy)
│
└── Check confidence level
    ├── high (primary ≥ 0.55, gap ≥ 0.2) → actionable
    ├── medium → working hypothesis, collect more evidence
    └── low → do NOT commit to a classification
```

## Provider detection (msg_id prefix)

| Prefix | Provider |
|---|---|
| `msg_01...` | Anthropic direct (api.anthropic.com) |
| `msg_vrtx_...` | Google Vertex AI |
| `msg_bdrk_...` | AWS Bedrock |
| 36-char UUID | Aggregator (LiteLLM/Portkey/OpenRouter/etc) |

**Do NOT rely on this alone.** The prefix is a string in the response body — any gateway can forge it cheaply. Use as a weak confirming signal alongside stylometric/feature evidence.

## When to escalate beyond the battery

The LLM-behavior battery (`fingerprint.py` 5 probes) is single-turn. It does NOT capture:

- **Quantization/precision degradation** — numerical accuracy on `sin(1.234567890)` to 12 digits, checksum reconstruction, multi-step arithmetic on large numbers (future work)
- **Multi-turn middleware** — session-level injection, cache-across-turns behavior, turn-boundary rewriting (future work)
- **Injected system prompt content** — mitmproxy or equivalent HTTPS capture required (supported via `mitm_capture.py`)

**Tokenizer identity is captured by `tokenizer_probe.py`** (v0.6) — no longer a gap. Feed the output to `fingerprint.py --tokenizer-probe-raw <file>` to integrate into classification.

For high-stakes classification (financial or security-sensitive decisions), do at least one of:

1. Run `tokenizer_probe.py` (10 sentinels, fits α·β slope; distinguishes Claude BPE from non-Claude backends masquerading as Claude)
2. Run `mitm_capture.py` (captures raw HTTPS via mitmproxy + custom CA; reveals injected system prompt content)
3. Consult a known-fresh Opus 4.7 max with full evidence dump (see `.scratch/consult_opus47*.py` for the structured brief format)

## Common failure modes

- **False-positive middleware:** target CLI is older than baselines and returns a different protocol shape (not middleware, just version mismatch). Mitigate: verify CLI version, regenerate baselines if needed.
- **False-negative middleware:** adaptive gateway varies intercept responses across runs to defeat byte-exact detection. Mitigate: check for schema-shape-matching-but-values-lying responses (compare reported fields to observed pipeline behavior).
- **False-positive distill:** capable model with aggressive RLHF refuses introspection probe. Inspect the refusal text — a real refusal reads like an RLHF refusal, not a canned gateway response.
- **Baseline drift:** new Anthropic release changes canonical stylometry. Mitigate: regenerate baselines on every new Opus release; tool blocks strong verdicts past `expiry_date`.

## Known gaps (v0.6)

1. ✅ ~~No tokenizer-identity probe~~ — **implemented in v0.6** via `tokenizer_probe.py`. CLI-mediated baseline (not raw `count_tokens` API); strong verdicts require n_points ≥ 8. Output labels `baseline_method` for provenance. Upgrade to API-key based `count_tokens` reduces cost; identical semantics.
2. **No quantization-degradation probe** — planned future work. An int8/int4 Claude variant could pass the current battery.
3. **No multi-turn probe.** All current probes are single-turn; gateways that act only on session boundaries are invisible.
4. **No adversarial-probe-adaptation detection.** If a gateway specifically counters our probe set, we won't notice without changing prompts.
5. **Narrow stylometric panel.** One math problem for signature. Broader panel needed for imitator detection.
6. **Baseline regeneration is manual.** No automated `--regenerate-baselines` flag yet.
7. ✅ ~~No `distill+middleware` hypothesis~~ — **added in v0.6** classifier. Gated on tokenizer `non_claude` verdict + middleware ≥ 0.6. Without tokenizer evidence, A+Middleware verdict is annotated with "distill+middleware unresolved".
8. **Thresholds hand-tuned.** Proper calibration requires labelled test set across provider types.
9. **Network evidence capped & corroborating only** — `aggressive_defense +0.2`, middleware software signatures `+0.4`, CDN match `+0.3×0.3=+0.09` routing support. Total contribution capped at 0.5 to prevent load-bearing on forgeable headers.

## Cost guidance

| Operation | Typical cost |
|---|---|
| Single target fingerprint (5 probes × 2 repeats) | ~$0.50-1.00 (target pricing-dependent) |
| Baseline regeneration (5 probes × 3 Opus models × 1 run) | ~$3 |
| Expert consultation (Opus 4.7 max with full brief) | ~$0.30-0.60 |
| mitmproxy setup + one capture session | free, but setup effort |

## Reading the verdict

The toolkit emits:

- **Primary hypothesis** with confidence score (0.0-1.0)
- **Ranked hypotheses** — always inspect the gap to second place
- **Evidence weights** — which signal axes contributed
- **Scoring notes** — human-readable rationale for each weight

A high-confidence verdict on fresh baselines with 3+ orthogonal signals pointing the same way is a reasonable working hypothesis for investigative purposes. It is NOT proof for legal/regulatory/security-audit purposes — for those, capture the wire traffic.
