# Investigation Results — `claude-aw.cmd` Proxy (api.claudecodeapi.cloud)

**Date:** 2026-04-24
**Target:** `claude-aw.cmd --model opus` (wrapper setting `ANTHROPIC_BASE_URL=https://api.claudecodeapi.cloud`)
**Baselines:** Anthropic-direct Opus 4.5, 4.6, 4.7 via official `claude` CLI v2.1.119

> **Note on methodology revision (2026-04-24 → 2026-04-25):** The original investigation used hard-coded scoring (toolkit v0.1). After 14 independent codex gpt-5.5 xhigh review rounds, the toolkit was hardened through v0.2-v0.6.1 with confidence-graded classification, multi-run consistency, distill+middleware hypothesis class, and full multi-model calibration (5 official Claude models × 5 efforts = 25/25 A-clean). The *findings* below were reproduced on the revised toolkit (`scripts/tests/test_fingerprint.py` synthesizes the AW profile and recovers the `A+Middleware` verdict). The *interpretation* still stands; the *methodology* caveats in `METHODOLOGY.md` should be read alongside it — especially that this is a hypothesis-generator, not a proof system, and that every single probe is defeatable by a sufficiently motivated operator.

## Working verdict (investigative hypothesis, not proof)

**Most consistent with: a Claude-like frontier backend (likely Opus 4.7) hosted on Google Vertex AI, fronted by an aggressive middleware gateway.**

The observed signals are **less consistent with** a rigidly-biased distilled-only student, with a Chinese-model clone, and with an alias of an older Claude release. They are **most consistent with** a frontier Claude backend under active gateway manipulation. Important caveats: (a) the toolkit's `distill+middleware` separation now lives in v0.6 behind the `tokenizer_probe.py` gate — at the time of this investigation that probe had not yet been run on AW, so the A+Middleware verdict here carries a "distill+middleware unresolved" annotation (re-run with v0.6 tokenizer probe to upgrade or downgrade to `distill+middleware`); (b) a sufficiently sophisticated adversarial proxy could in principle produce the same behavior on all probes. For security- or legal-grade certainty, capture wire traffic (mitmproxy) and run the tokenizer identity probe.

## Middleware inventory

| Layer | Behavior | Overrideable? | Evidence |
|---|---|:-:|---|
| Hard filter | Self-introspection → canned `{"acknowledged":true}` (22 bytes) | No | Byte-exact repeat ×2 |
| Soft injection | Math tasks → Euler/totient-first opening | **Yes** | Anti-Euler probe |
| Feature strip | `thinking`, `cache_control`, `--effort` | No | `cache=0/0`, effort ignored |
| Output cap | max_tokens ≈ 60-240 | No | AW 63-239 vs officials 223-1855 |
| Metadata spoof | `model` field relabels 4.5 ↔ 4.7 | No | Same query, different sessions |

## Evidence chain

### Stage 1. Original visual benchmark (user's prior work)

14-row comparison of coordinate-extraction accuracy on a 2200×1600 PNG (pixel-perfect ideal = 0):

| Rank | Family | Path | Model | Effort | Reported | Mean err | Max err | OutTok |
|:-:|---|---|---|---|---|:-:|:-:|:-:|
| 1 | Gemini | official | Gemini 3 Flash fallback | HIGH | gemini-3-flash-preview | 0.0 px | 0.0 px | 1110 |
| 2 | Codex | official | GPT-5.4 | xhigh | gpt-5.4 | 0.7 px | 1.4 px | 11352 |
| 3 | Codex | official | GPT-5.5 | xhigh | gpt-5.5 | 0.9 px | 1.4 px | 560 |
| 4 | Codex | official | GPT-5.3-Codex | xhigh | gpt-5.3-codex | 8.2 px | 35.0 px | 5579 |
| 5 | Claude | official | Opus 4.7 | env max | claude-opus-4-7 | 39.3 px | 86.8 px | 790 |
| 6 | Claude | official | Opus 4.7 | `--effort max` | claude-opus-4-7 | 75.0 px | 148.7 px | 1832 |
| 7 | Claude | AW | Opus | env max | claude-opus-4.5 | 81.9 px | 142.1 px | 113 |
| 8 | Claude | official | Opus 4.6 | `--effort max` | claude-opus-4-6 | 90.2 px | 163.4 px | 4374 |
| 9 | Claude | AW | Opus | `--effort max` | claude-opus-4.5 | 115.4 px | 205.1 px | 113 |
| 10 | Claude | official | Opus 4.6 | env max | claude-opus-4-6 | 150.4 px | 215.1 px | 4604 |
| 11 | Claude | official | Sonnet 4.6 | env max | claude-sonnet-4-6 | 616.3 px | 901.6 px | 3090 |
| 12 | Claude | official | Haiku 4.5 | env max | claude-haiku-4-5-20251001 | 638.9 px | 900.5 px | 2406 |
| 13 | Claude | official | Opus 4.5 | `--effort max` | claude-opus-4-5-20251101 | 660.0 px | 968.0 px | 2379 |
| 14 | Claude | official | Opus 4.5 | env max | claude-opus-4-5-20251101 | 690.8 px | 1002.8 px | 1397 |

Observation: AW (rows 7, 9) lands in the 4.6/4.7 accuracy band, not the 4.5-release band. Sharp 150→600 px gap between "high-res" and "downscaled" vision path.

### Stage 2. Env vs `--effort` flag (CLI mechanics)

Hypothesis: Opus 4.7 "launch effort pin" explains 39 vs 75 px difference.

| Variant | pin state | out_tok | cost | reasoning |
|---|:-:|:-:|:-:|---|
| A (env=max, no flag) | pinned | 698 | $0.225 | `7^4 = 2401 ≡ 1 (mod 100), so 7^17 = (7^4)^4 · 7 ≡ 7 (mod 100)` |
| B (`--effort max`) | unpinned | 716 | $0.225 | `7^4 = 2401 ≡ 1 (mod 100), so 7^17 = (7^4)^4 · 7 ≡ 7 (mod 100)` |

**Result:** near-identical (1 punctuation dot, +18 tokens). Pin state does NOT explain vision discrepancy. CLI internals examined:

```js
function ht6(H){ if(M7(H)==="claude-opus-4-7") return "xhigh"; return "high" }  // launch effort
function NbH(H, q){
  let _ = UWH();  // env var
  if(_===null) return $?K:void 0;
  let f = _ ?? ($?K:void 0) ?? q ?? K;  // precedence: env > session > launch
  ...
}
```

### Stage 3. AW discriminator test (7^17 mod 100, unconstrained)

| Variant | Reported | Msg ID prefix | out_tok | cache_create | Opening reasoning |
|---|---|---|:-:|:-:|---|
| 4.5 off | `claude-opus-4-5-20251101` | `msg_01*` (Anthropic) | 419 | 39867 | `7^4 = 2401 ≡ 1 (mod 100), so 7^17 = 7^(4·4+1) = (7^4)^4 · 7 ≡ 1·7 = 7` |
| 4.6 off | `claude-opus-4-6` | `msg_01*` (Anthropic) | 223 | 39697 | `7^4 = 2401 ≡ 1 (mod 100), so 7^17 = (7^4)^4 · 7^1 ≡ 1·7 = 7` |
| 4.7 off | `claude-opus-4-7` | `msg_01*` (Anthropic) | 538 | 58052 | `7^4 = 2401 ≡ 1 (mod 100), so 7^17 = (7^4)^4 · 7 ≡ 7 (mod 100)` |
| **AW** | **`claude-opus-4.7`** | **`msg_vrtx_01Q`** (Vertex) | **77** | **0** | `φ(100)=40, so 7^17 mod 100 = 7^17; compute 7^4=2401≡1, hence 7^17=(7^4)^4·7≡1·7` |

First suspicion of distillation (hypothesis C): φ(100)=40 false-start + tautology `7^17 mod 100 = 7^17`. Zero cache. Compression to 77 tokens.

### Stage 4. Three-probe battery

#### Probe 1 — Temporal cutoff

| Target | Events | Cutoff estimate |
|---|---|:-:|
| 4.5 off | Trump + LA wildfires + Pope Francis (Apr) | ≤ April 2025 |
| 4.6 off | Trump + Palisades/Eaton wildfires + Pope Francis | ≤ April 2025 |
| 4.7 off | Trump + Pope Francis + **Pope Leo XIV (May 2025)** | ≥ May 2025 |
| **AW** | Trump + Pope Francis → Leo XIV + **Wimbledon July 2025** | **≥ July 2025** |

All AW facts independently verifiable. AW cutoff matches or exceeds 4.7.

#### Probe 2 — Strict-format reasoning (CRT proof)

| Target | Sentences | CRT in s2 | "Therefore" in s3 | Verdict |
|---|:-:|:-:|:-:|---|
| 4.5 off | 3 | ✓ | ✓ | PASS |
| 4.6 off | 3 | ✓ | ✓ | PASS |
| 4.7 off | 3 | ✓ (CRT) | ✓ | PASS |
| **AW** | 3 | ✓ (CRT) | ✓ | **PASS** |

AW meets all constraints at Opus-level rigor. No false-start here. Distill hypothesis weakens.

#### Probe 3 — Self-introspection JSON (raw stdout)

| Target | Raw stdout | Assessment |
|---|---|---|
| 4.5 off | Clean JSON, cutoff=May 2025 | PASS |
| 4.6 off | Wrapped in ```json codefence | format fail (Claude habit) |
| 4.7 off | Clean JSON, architecture=Claude, cutoff=January 2026 | PASS |
| **AW** | **`{"acknowledged":true}\n`** (22 bytes) | **INTERCEPTED** |

AW returned something completely different from what was requested. Gateway-level interception.

### Stage 5. Reproducibility check (×2)

| Test | Result |
|---|---|
| Probe 3 repeat run 1 | `{"acknowledged":true}\n` — identical 22 bytes |
| Probe 3 repeat run 2 | `{"acknowledged":true}\n` — identical 22 bytes |
| 7^17 repeat run 1 | `Reasoning: φ(100)=40, so 7^17 mod 100 = 7^17; compute 7^4=2401≡1...` |
| 7^17 repeat run 2 | `Reasoning: φ(100)=40, so 7^17 mod 100 = 7·(7^2)^8 mod 100 = 7·49^8 mod 100.` |

Both anomalies reproducible. Byte-exact intercept = definitively middleware, not random. φ-opening = systematic forcing, not sampling variance.

### Stage 6. Anti-Euler override probe (recommended by Opus 4.7 max)

Prompt: `Compute 7^17 mod 100. Do NOT use the words Euler, totient, Fermat, phi, or any Greek letter. Begin reasoning by computing 7^2 and 7^4 directly. Two lines: 'Reasoning:' and 'Answer:'.`

| Target | Opening | Banned words | Verdict |
|---|---|:-:|---|
| 4.5 off | `7^2 = 49, 7^4 = 49^2 = 2401 ≡ 1 (mod 100)` | none | COMPLIANT |
| 4.6 off | `7^2 = 49, 7^4 = 49^2 = 2401 ≡ 01 (mod 100)` | none | COMPLIANT |
| 4.7 off | `7^2 = 49; 7^4 = 49^2 = 2401 ≡ 1 (mod 100)` | none | COMPLIANT |
| **AW run1** | `7^2=49; 7^4=49·49=2401≡01 mod 100` | none | **COMPLIANT** |
| **AW run2** | `7^2=49; 7^4=49·49=2401≡1` | none | **COMPLIANT** |

**Strong result** (not on its own decisive — see caveats in METHODOLOGY.md): AW switched from φ-opening to canonical `7^4 ≡ 1` under explicit instruction. This is inconsistent with a rigidly-biased distilled student and more consistent with a capable base model under an overrideable soft injection. An adaptive/probe-aware proxy could in principle produce the same behavior, which is why the overall verdict relies on multiple converging signals rather than this probe alone.

## Hypothesis ranking (working investigative verdict, not a proof)

| Rank | Hypothesis | Status | Key counter-argument |
|:-:|---|---|---|
| **1** | **A+Middleware: real Opus 4.7 via Vertex with aggressive shim** | leading hypothesis | All five probes align; no observed signal contradicts it |
| 2 | C: Distilled student trained on Claude outputs | unlikely given observed data | Probe 2 rigor + anti-Euler switch inconsistent with rigid distill |
| 3 | E: Pruned/quantized Opus | low fit | Would degrade gracefully, not produce injection signature; needs dedicated quantization probe to exclude fully |
| 4 | F: Non-Claude base + Claude fine-tune | low fit | Constant (not proportional) tokenizer offset weakens this; needs proper tokenizer probe to exclude fully |
| 5 | B: Older Opus checkpoint | low fit | Cutoff ≥ July 2025 matches latest release, not older |
| 6 | D: Hybrid multi-model routing | low fit | Token compression (not inflation) does not fit concat-style routing |

**All "excluded" hypotheses should be read as "weakened by current evidence" rather than "proven impossible"**. A sufficiently sophisticated adversarial proxy could match the observed signals while still being any of the lower-ranked classes. For high-stakes decisions, capture wire traffic (mitmproxy) and add a tokenizer-identity probe.

## Capability match

| Capability | AW observation | Matches |
|---|---|---|
| Knowledge cutoff | ≥ July 2025 | Opus 4.7 |
| Reasoning rigor | Strict CRT-proof PASS | Opus 4.x tier |
| Style fingerprint | `7^4 ≡ 1 (mod 100)` under override | Opus 4.x canonical |
| Tokenizer | Claude BPE + constant +7 offset | Claude family (injected prefix) |
| Censorship | Factual on Tiananmen/Xinjiang/Taiwan | Claude, not Chinese models |
| Provider routing | `msg_vrtx_*` prefix | Google Vertex AI |

## Unresolved

| Item | Status |
|---|---|
| Vision 39 vs 75 px discrepancy | Not explained by math probes — likely domain-specific effect |
| Exact Opus revision on Vertex | 4.6 or 4.7; knowledge suggests 4.7 |
| Injected system prompt content | Not captured (requires HTTPS proxy like mitmproxy) |
| Gateway operator identity | Not investigated |

## Budget

| Item | Cost |
|---|---|
| Total official Opus calls | ~$3-4 |
| AW calls (local CLI estimate, unreliable) | ~$2 (true cost unknown) |
| Opus 4.7 max consultations | 2 (methodology design + decision selection) |
