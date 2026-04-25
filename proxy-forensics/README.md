# Claude Proxy Forensic Toolkit

Fingerprint any Claude-compatible CLI endpoint (official `claude`, third-party wrappers, aggregator proxies) across 4 orthogonal evidence axes:

1. **LLM behavior** (`fingerprint.py`) — 5-probe battery: stylometric, temporal cutoff, format rigor, self-introspection, anti-Euler override
2. **Tokenizer identity** (`tokenizer_probe.py`) — 10-sentinel α·β linear fit (Claude BPE vs non-Claude)
3. **Network fingerprint** (`network_probe.py`) — TLS / headers / timing / known-proxy-software signatures (no LLM cost)
4. **Wire capture** (`mitm_capture.py`) — HTTPS request body intercept via mitmproxy (for high-stakes classification)

**Status: v0.6.1, hypothesis generator** — investigative tool, not legal/security-grade proof. See `docs/METHODOLOGY.md`.

**Calibration**: 25/25 combinations classify A-clean across all 5 official Claude models (Opus 4.5/4.6/4.7, Sonnet 4.6, Haiku 4.5) × all 5 efforts (low/medium/high/xhigh/max). See `docs/CALIBRATION_REPORT.md`.

## Layout

```
proxy-forensics/
├── README.md             ← this file (quickstart + usage)
├── scripts/              ← all executable Python
│   ├── fingerprint.py        main runner
│   ├── tokenizer_probe.py    tokenizer identity probe
│   ├── network_probe.py      network-level probe
│   ├── mitm_capture.py       HTTPS wire capture (requires mitmproxy)
│   ├── parse_mitm_flow.py    flow parser utility
│   ├── calibration_runner.py full model×effort matrix runner
│   ├── calibration_rerun.py  affected-combos rerun
│   ├── reclassify_calibration.py  offline re-classify saved findings
│   ├── baselines.json        cached Anthropic-direct outputs (scorer 0.6.1)
│   └── tests/                176 unit tests (no API)
│       ├── test_fingerprint.py        (134)
│       ├── test_tokenizer_probe.py    (33)
│       └── test_mitm_capture.py       (9)
├── docs/                 ← methodology + investigation findings
│   ├── METHODOLOGY.md         protocol, decision tree, caveats
│   ├── RESULTS.md             original AW investigation
│   ├── NETWORK_FINGERPRINTS.md baseline TLS/header profiles
│   ├── SUSPECT_WORKFLOW.md    step-by-step checklist for new suspects
│   ├── WIRE_CAPTURE_FINDINGS.md mitmproxy capture findings on AW
│   └── CALIBRATION_REPORT.md  multi-model calibration matrix results
├── examples/             ← sample raw outputs
│   ├── network_anthropic.json     Anthropic-direct network probe
│   ├── network_aw.json            AW gateway network probe (aggressive_defense=True)
│   ├── results_aw_smoketest.json  AW LLM-behavior smoke test
│   └── results_official_validation.json  plain claude-opus-4-7 → A-clean high
├── calibration/          ← 25 combo JSONs from full matrix run + logs
├── audit-trail/          ← 14 codex gpt-5.5 xhigh review rounds (prompts + outputs)
└── investigation/        ← original AW investigation iteration scripts (pre-toolkit)
```

## Quickstart

### Prerequisites

- Python 3.9+
- Official `claude` CLI (Anthropic Claude Code) — used for baselines and as known-good comparison target
- Optional: `pip install mitmproxy` (only for wire capture)

### Verify toolkit

```bash
cd proxy-forensics

# Run all 176 unit tests (no API calls)
python scripts/tests/test_fingerprint.py
python scripts/tests/test_tokenizer_probe.py
python scripts/tests/test_mitm_capture.py

# List available probes
python scripts/fingerprint.py --list-probes
```

### Investigate a new suspect

For a third-party wrapper like `claude-aw.cmd` (sets `ANTHROPIC_BASE_URL` to a gateway):

```bash
# 1. Network probe (free, ~30 sec)
python scripts/network_probe.py --url https://api.suspect-gateway.example \
  --label "suspect" --save-raw network_suspect.json

# 2. LLM-behavior probe (5 probes × 2 repeats, ~$0.50-1.50)
python scripts/fingerprint.py --label "suspect" \
  --cmd "claude-suspect.cmd --model opus" --shell \
  --save-raw results_suspect.json

# 3. (optional) Tokenizer identity probe (~$0.50)
python scripts/tokenizer_probe.py \
  --baseline-cmd "claude" \
  --gateway-cmd "claude-suspect.cmd" --gateway-shell \
  --model claude-opus-4-7 --gateway-model opus \
  --repeats 2 --save-raw tokenizer_suspect.json

# 4. (optional) Combined run with all evidence integrated into classify()
python scripts/fingerprint.py --label "suspect" \
  --cmd "claude-suspect.cmd --model opus" --shell \
  --network-probe-url https://api.suspect-gateway.example \
  --tokenizer-probe-raw tokenizer_suspect.json \
  --save-raw results_suspect_full.json

# 5. (high-stakes only, ~30-60 min setup) Wire capture
python scripts/mitm_capture.py \
  --cmd "claude-suspect.cmd --model opus" --shell \
  --prompt "Reply with '1'."
python scripts/parse_mitm_flow.py mitm_flows/<timestamp>.flow
```

Read `docs/SUSPECT_WORKFLOW.md` for the full step-by-step checklist with interpretation guidance.

### Verdict reading

`fingerprint.py` outputs a confidence-graded classification:

| Verdict | Meaning |
|---|---|
| `A-clean` | Claude-like backend, no detectable middleware (default expected for official Claude) |
| `A+Middleware` | Claude-like backend behind active middleware gateway (e.g. AW) |
| `C` | Distilled student, no middleware |
| `distill+middleware` | Non-Claude tokenizer + active middleware (requires tokenizer probe) |
| `ambiguous / insufficient evidence` | Not enough signal; collect more probes |

Confidence levels:

- **high** — primary score ≥ 0.55 AND gap to second hypothesis ≥ 0.2 (actionable)
- **medium** — primary score ≥ 0.35 AND gap ≥ 0.1 (working hypothesis, collect more evidence)
- **low** — neither threshold met (do NOT commit to a classification)

Each high-confidence verdict requires its hypothesis-specific gate to pass. See `docs/METHODOLOGY.md` for gate semantics.

### Verify expected behavior on known-good

```bash
# Plain claude → A-clean high (validated baseline)
python scripts/fingerprint.py --label "official-validation" \
  --cmd "claude --model claude-opus-4-7" --repeats 2
# Expected: A-clean, score ≈ 0.725, confidence high
```

### Re-run full calibration matrix (only after toolkit changes)

```bash
# 25 combinations (5 models × 5 efforts), ~50 min, ~$10-15 official Claude API
python scripts/calibration_runner.py
# Results in calibration/calibration-*.json + calibration/_calibration_log.json
```

## Cost guidance

| Operation | Typical cost |
|---|---|
| Single suspect fingerprint (5 probes × 2 repeats) | ~$0.50-1.50 |
| Tokenizer probe on suspect | ~$0.50 |
| Network probe | $0 (TLS + HTTP HEAD only) |
| Wire capture (1 prompt) | ~$0.05 + setup time |
| Full calibration matrix regeneration | ~$10-15 |

Third-party gateway "cost" reported by CLI is locally computed and may not reflect actual gateway billing — trust `out_tok`, `text`, `msg_id` prefix, `cache_create/read` instead.

## Trust model + caveats

The toolkit assumes:

1. Target honors standard Claude Code CLI flags (`-p`, `--model`, `--effort`, `--tools`, `--output-format json`)
2. Tool invocation is actually disabled (`--tools ""` is added automatically by `fingerprint.py`)
3. Gateway is not probe-adaptive (if it specifically counters our probe set, we won't detect that)
4. Sampling variance on single calls doesn't flip verdict — `--repeats ≥ 2` for stability
5. Baselines fresh (within `expiry_date` window — currently 2026-07-23)

**No probe is decisive on its own.** Strong classifications require multiple probes pointing the same way across ≥ 2 repeats. See `docs/METHODOLOGY.md` for failure modes and known gaps.

## Codex audit trail

The toolkit was developed through 14 codex gpt-5.5 xhigh review rounds (round 0 plan → round 14 calibration final approval). All review prompts + outputs preserved in `audit-trail/` for methodology provenance. Final verdict: GREEN multi-model stable.

## Investigation history

The original investigation classified `claude-aw.cmd` (proxy at `api.claudecodeapi.cloud`) as **Claude-like backend behind aggressive middleware gateway**. Wire capture (`docs/WIRE_CAPTURE_FINDINGS.md`) directly captured server-side Euler-bias system prompt injection, confirming the soft-injection hypothesis from `fingerprint.py`'s anti-Euler override probe. Pre-toolkit iteration scripts in `investigation/`.

## Known gaps

- Tokenizer probe baseline is CLI-mediated (~$1) instead of free Anthropic `messages.count_tokens` API (would require API key — not in current scope)
- No quantization-degradation probe (int8/int4 Claude variants would pass current battery)
- No multi-turn middleware probe (all probes single-turn)
- No adversarial-probe-adaptation detection
- Hand-tuned thresholds (not statistically calibrated; would need labelled test set)

See `docs/METHODOLOGY.md` for the complete known-gaps list.
