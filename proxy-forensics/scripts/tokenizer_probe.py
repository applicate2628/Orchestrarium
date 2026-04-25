#!/usr/bin/env python3
"""
Tokenizer-identity probe for Claude-compatible gateways.

Question answered: does the gateway's backend use the same tokenizer (Claude BPE)
as Anthropic-direct Claude, or a different tokenizer (indicating non-Claude base)?

Method: send each of 8-12 sentinel strings through both a trusted Anthropic-direct
path and the suspect gateway. For each, capture `usage.input_tokens` from the
response. Fit `gateway_tokens = alpha * baseline_tokens + beta` via least squares,
inspect:
  - `alpha ≈ 1`: same tokenizer
  - `beta` stable integer-ish across classes: constant injection offset
  - low residuals across character classes: tokenizer not drifting per class
  - repeat stability: run each sentinel twice, consistent counts

Verdict (must match code in classify_fit() — do not drift):
  - `claude_bpe`: alpha ∈ [0.97, 1.03] AND max_abs_residual < 5 AND
                   repeat_spread_max ≤ 2 AND n_points ≥ 8
  - `claude_bpe_weak`: alpha ∈ [0.97, 1.03] AND max_abs_residual ∈ [5, 10)
                   (close but small drift suggests minor within-family tokenizer
                   differences; annotate only, do not flip classification)
  - `non_claude`: (alpha NOT in [0.9, 1.1])  OR  (alpha ∈ [0.97, 1.03] AND
                   max_abs_residual ≥ 10 AND repeat_spread_max ≤ 2 —
                   i.e. repeat-stable class-dependent significant residuals)
  - `ambiguous`: noisy repeats (repeat_spread_max > 2) OR insufficient
                   coverage (n_points < 8) OR inconsistent signals
  - `insufficient_data`: < 2 valid data points (cannot fit)

NOTE on baseline method: Anthropic `messages.count_tokens` would be the ideal
free baseline, but requires a raw API key. On systems where only the Claude CLI
OAuth is available, we fall back to CLI-mediated calls with `--effort low` to
minimize cost (~$0.001 per call). The JSON output identifies this via
`baseline_method: "claude_cli_usage_total_input"`. When an API key is available,
switch to `baseline_method: "anthropic_count_tokens"` for cleaner semantics.
The `beta` intercept absorbs CLI wrapping overhead; we interpret α + residuals
+ stability, not β, as identity signal.

Usage:
  python tokenizer_probe.py \\
    --baseline-cmd "claude" \\
    --gateway-cmd "claude-aw.cmd" \\
    --gateway-shell \\
    --model claude-opus-4-7 \\
    --repeats 2 \\
    --save-raw tokenizer_aw.json
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROBE_VERSION = "0.1.0"

# Sentinel strings: 10 prompts, paired short/long per character class.
# Crafted to have widely varying tokenization under non-Claude tokenizers
# (especially byte-level fallback and emoji handling).
SENTINELS = [
    ("ascii_short", "hello"),
    ("ascii_long",
     "The quick brown fox jumps over the lazy dog. "
     "Pack my box with five dozen liquor jugs. "
     "How vexingly quick daft zebras jump."),
    ("cyrillic_short", "Привет мир"),
    ("cyrillic_long",
     "Привет мир! Это развёрнутое сообщение на русском языке для проверки "
     "того, как токенизатор разбивает кириллические символы и учитывает ли "
     "различие тона при обработке длинных последовательностей."),
    ("cjk_short", "你好"),
    ("cjk_long",
     "你好,世界。这是一个用于测试分词器的较长消息,包含若干句子,"
     "以便观察模型如何处理中文字符、标点符号与句子边界的切分行为。"),
    ("emoji", "🚀✨🎉🎊🎈🎁🎀⭐🌟💫🎯🎪🎨🎬🎭"),
    ("code_python",
     "def fib(n):\n"
     "    \"\"\"Return n-th Fibonacci number.\"\"\"\n"
     "    return n if n < 2 else fib(n - 1) + fib(n - 2)"),
    ("code_json",
     json.dumps({"key": "value", "nested": {"arr": [1, 2, 3, 4, 5], "bool": True},
                 "mixed": {"a": None, "b": 3.14159, "c": "x" * 40}}, indent=2)),
    ("high_entropy_hex",
     "a1b2c3d4e5f60718293a4b5c6d7e8f9011223344556677889900aabbccddeeff"
     "1122334455667788990011223344556677889900aabbccddeeff00112233"),
]


def run_probe_call(cmd_tokens, shell, sentinel_text, model, timeout=120):
    """Issue a minimal claude CLI call with sentinel as user prompt, return
    (input_tokens, out_tok, msg_id_provider) or (None, None, None) on failure.
    """
    full_cmd = cmd_tokens + [
        "-p", sentinel_text,
        "--model", model,
        "--tools", "",
        "--output-format", "json",
        "--effort", "low",  # minimize cost — input_tokens independent of effort
    ]
    try:
        r = subprocess.run(
            full_cmd,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            shell=shell, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    if r.returncode != 0 or not r.stdout:
        return {"error": f"exit={r.returncode}", "stderr_head": (r.stderr or "")[:200]}
    try:
        parsed = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": "not_json", "raw_head": r.stdout[:200]}

    # v0.6 (codex round 7 blocker fix): accept both stream-list (historical)
    # AND single-object Claude CLI output (newer versions). Match
    # fingerprint.py's `_looks_like_claude_single_object` heuristic.
    usage = None
    last = {}
    if isinstance(parsed, list):
        result = next((x for x in parsed if isinstance(x, dict) and x.get("type") == "result"), {})
        assistants = [x for x in parsed if isinstance(x, dict) and x.get("type") == "assistant"]
        last = assistants[-1].get("message", {}) if assistants else {}
        usage = result.get("usage", {}) if isinstance(result, dict) else {}
    elif isinstance(parsed, dict):
        # Single-object CLI: check for protocol fields
        result_val = parsed.get("result")
        usage_val = parsed.get("usage")
        model_val = parsed.get("model")
        session_val = parsed.get("session_id")
        looks_like_claude = (
            isinstance(result_val, str) and len(result_val) > 0
            and (
                (isinstance(usage_val, dict)
                 and ("output_tokens" in usage_val or "input_tokens" in usage_val))
                or (isinstance(model_val, str) and model_val.startswith(("claude-", "msg_")))
                or (isinstance(session_val, str) and len(session_val) >= 8)
            )
        )
        if looks_like_claude:
            usage = usage_val if isinstance(usage_val, dict) else {}
            last = {"model": model_val, "id": parsed.get("id") or parsed.get("message_id") or ""}
        else:
            return {"error": "intercepted", "raw": r.stdout[:200]}
    else:
        return {"error": "intercepted", "raw": r.stdout[:200]}

    msg_id = last.get("id", "")
    # CLI reports input_tokens; this includes system prompt + user msg overhead.
    # For a given CLI version, the overhead is constant across sentinels, so
    # differences across sentinels are due to user-message token count.
    in_tok = usage.get("input_tokens")
    cache_create = usage.get("cache_creation_input_tokens") or 0
    cache_read = usage.get("cache_read_input_tokens") or 0
    # Effective input tokens = input_tokens + cache_creation + cache_read
    # (the `input_tokens` field is only the uncached portion)
    total_input = (in_tok or 0) + cache_create + cache_read
    return {
        "input_tokens": in_tok,
        "cache_create": cache_create,
        "cache_read": cache_read,
        "total_input": total_input,
        "out_tok": usage.get("output_tokens"),
        "model_reported": last.get("model"),
        "msg_id_prefix": msg_id[:14],
    }


def least_squares_fit(xs, ys):
    """Fit y = alpha*x + beta via simple least squares. Returns (alpha, beta, residuals)."""
    if len(xs) < 2:
        return None, None, []
    n = len(xs)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_xx = sum(x * x for x in xs)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return None, None, []
    alpha = (n * sum_xy - sum_x * sum_y) / denom
    beta = (sum_y - alpha * sum_x) / n
    residuals = [y - (alpha * x + beta) for x, y in zip(xs, ys)]
    return alpha, beta, residuals


MIN_POINTS_FOR_STRONG_VERDICT = 8


def classify_fit(alpha, beta, residuals, repeat_spread_max):
    """Given fit result, emit verdict. Codex-reviewed contract:

    - Strong verdicts (`claude_bpe` / `non_claude`) require n_points ≥ 8.
      With < 8 points, best we can claim is `ambiguous` / `claude_bpe_weak`.
    - `non_claude` fires on EITHER alpha outside tolerance OR class-dependent
      high residuals stable across repeats (not just alpha).
    - `repeat_spread_max` is max-min spread in tokens per sentinel across
      repeats (not statistical variance; renamed from prior `repeat_variance`).
    """
    if alpha is None:
        return {
            "verdict": "insufficient_data",
            "reason": "too few successful probe points to fit (need ≥ 2)",
        }
    max_resid = max(abs(r) for r in residuals) if residuals else float("inf")
    mean_abs_resid = sum(abs(r) for r in residuals) / len(residuals) if residuals else float("inf")
    n_points = len(residuals)
    findings = {
        "alpha": round(alpha, 4),
        "beta": round(beta, 2),
        "max_abs_residual": round(max_resid, 2),
        "mean_abs_residual": round(mean_abs_resid, 2),
        "repeat_spread_max": repeat_spread_max,
        "n_points": n_points,
    }

    alpha_in_claude_band = 0.97 <= alpha <= 1.03
    alpha_near_claude_loose = 0.9 <= alpha <= 1.1
    residual_low = max_resid < 5
    residual_drift = 5 <= max_resid < 10    # small tokenizer drift within claude family
    residual_meaningful = max_resid >= 10   # significant class-dependent difference
    repeat_stable = repeat_spread_max <= 2
    coverage_strong = n_points >= MIN_POINTS_FOR_STRONG_VERDICT

    # Strong claude_bpe: tight alpha + low residuals + stable repeats + coverage
    if alpha_in_claude_band and residual_low and repeat_stable and coverage_strong:
        findings["verdict"] = "claude_bpe"
        findings["reason"] = (
            f"alpha={alpha:.3f} ∈ [0.97, 1.03], residuals ≤ {max_resid:.1f}, "
            f"repeat_spread ≤ {repeat_spread_max}, n={n_points} ≥ {MIN_POINTS_FOR_STRONG_VERDICT}"
        )
    # Weak claude: tight alpha but residual drift in [5, 10] — small drift,
    # within-family variation, NOT enough to claim non-Claude tokenizer
    elif alpha_in_claude_band and residual_drift and repeat_stable and coverage_strong:
        findings["verdict"] = "claude_bpe_weak"
        findings["reason"] = (
            f"alpha={alpha:.3f} claude-like but max residual {max_resid:.1f} ∈ [5, 10] "
            "suggests small tokenizer drift — annotate only, do not flip classification"
        )
    # Strong non_claude: EITHER alpha drift (α outside [0.9, 1.1])
    # OR MEANINGFUL class-dependent residuals (max_resid ≥ 10) with stable repeats
    # (rules out sampling noise as explanation; small drift is claude_bpe_weak, not this)
    elif coverage_strong and repeat_stable and (
        not alpha_near_claude_loose
        or (alpha_in_claude_band and residual_meaningful)
    ):
        if not alpha_near_claude_loose:
            reason = f"alpha={alpha:.3f} significantly ≠ 1 (outside [0.9, 1.1])"
        else:
            reason = (
                f"alpha={alpha:.3f} within band but class-dependent residuals "
                f"(max={max_resid:.1f} ≥ 10) stable across repeats → different tokenizer"
            )
        findings["verdict"] = "non_claude"
        findings["reason"] = reason
    # Ambiguous: noisy repeats, insufficient coverage, or conflicting signals
    elif not repeat_stable:
        findings["verdict"] = "ambiguous"
        findings["reason"] = f"noisy repeats: spread={repeat_spread_max} > 2"
    elif not coverage_strong:
        findings["verdict"] = "ambiguous"
        findings["reason"] = (
            f"insufficient coverage: n_points={n_points} < {MIN_POINTS_FOR_STRONG_VERDICT}"
        )
    else:
        findings["verdict"] = "ambiguous"
        findings["reason"] = (
            f"mixed signals: alpha={alpha:.3f}, max_resid={max_resid:.1f}, "
            f"repeat_spread={repeat_spread_max}"
        )
    return findings


def main():
    ap = argparse.ArgumentParser(description=f"Claude tokenizer-identity probe v{PROBE_VERSION}")
    ap.add_argument("--baseline-cmd", default="claude",
                    help="Command for trusted Anthropic-direct baseline (default: plain `claude`)")
    ap.add_argument("--baseline-shell", action="store_true")
    ap.add_argument("--gateway-cmd", required=True,
                    help="Command for suspect gateway (e.g. 'claude-aw.cmd')")
    ap.add_argument("--gateway-shell", action="store_true")
    ap.add_argument("--model", default="claude-opus-4-7",
                    help="Model to use (baseline path sends this; gateway may remap internally)")
    ap.add_argument("--gateway-model", default=None,
                    help="Model for gateway side (default: same as --model; use 'opus' for AW)")
    ap.add_argument("--repeats", type=int, default=2,
                    help="Repeat each sentinel N times for stability check (default 2)")
    ap.add_argument("--save-raw", help="Path to save raw JSON output")
    ap.add_argument("--skip-sentinels", nargs="+", default=[],
                    help="Sentinel names to skip")
    args = ap.parse_args()

    import shlex
    baseline_tokens = shlex.split(args.baseline_cmd, posix=False)
    gateway_tokens = shlex.split(args.gateway_cmd, posix=False)
    gateway_model = args.gateway_model or args.model

    sentinels = [(name, text) for name, text in SENTINELS if name not in args.skip_sentinels]
    print(f"=== Tokenizer probe v{PROBE_VERSION} ===")
    print(f"    baseline: {args.baseline_cmd} (shell={args.baseline_shell})")
    print(f"    gateway:  {args.gateway_cmd} (shell={args.gateway_shell})")
    print(f"    model:    {args.model} (gateway: {gateway_model})")
    print(f"    repeats:  {args.repeats}")
    print(f"    sentinels: {len(sentinels)}\n")

    per_sentinel = {}
    for name, text in sentinels:
        print(f"[probe] {name} ({len(text)} chars)")
        per_sentinel[name] = {
            "text_len_chars": len(text),
            "baseline_runs": [],
            "gateway_runs": [],
        }
        # Baseline runs
        for i in range(args.repeats):
            print(f"  baseline run {i+1}/{args.repeats}... ", end="", flush=True)
            t0 = time.monotonic()
            r = run_probe_call(baseline_tokens, args.baseline_shell, text, args.model)
            elapsed = time.monotonic() - t0
            per_sentinel[name]["baseline_runs"].append({**r, "elapsed_s": round(elapsed, 1)})
            if "error" in r:
                print(f"ERROR {r['error']}")
            else:
                print(f"in_tok={r['input_tokens']} total={r['total_input']} ({elapsed:.1f}s)")
        # Gateway runs
        for i in range(args.repeats):
            print(f"  gateway  run {i+1}/{args.repeats}... ", end="", flush=True)
            t0 = time.monotonic()
            r = run_probe_call(gateway_tokens, args.gateway_shell, text, gateway_model)
            elapsed = time.monotonic() - t0
            per_sentinel[name]["gateway_runs"].append({**r, "elapsed_s": round(elapsed, 1)})
            if "error" in r:
                print(f"ERROR {r['error']}")
            else:
                print(f"in_tok={r['input_tokens']} total={r['total_input']} ({elapsed:.1f}s)")

    # Build data arrays for fit
    baseline_points = []
    gateway_points = []
    point_labels = []
    repeat_spreads = []
    for name, data in per_sentinel.items():
        b_runs = [r for r in data["baseline_runs"] if r.get("total_input") is not None]
        g_runs = [r for r in data["gateway_runs"] if r.get("total_input") is not None]
        if not b_runs or not g_runs:
            continue
        b_tokens = [r["total_input"] for r in b_runs]
        g_tokens = [r["total_input"] for r in g_runs]
        b_avg = sum(b_tokens) / len(b_tokens)
        g_avg = sum(g_tokens) / len(g_tokens)
        # Spread = max-min across repeats (NOT statistical variance; renamed
        # from prior 'variance' per codex feedback)
        b_spread = max(b_tokens) - min(b_tokens)
        g_spread = max(g_tokens) - min(g_tokens)
        repeat_spreads.append(max(b_spread, g_spread))
        baseline_points.append(b_avg)
        gateway_points.append(g_avg)
        point_labels.append(name)

    print(f"\n=== Fit ===")
    print(f"Points: {len(baseline_points)}")
    for lbl, b, g in zip(point_labels, baseline_points, gateway_points):
        print(f"  {lbl:<20}  baseline={b:>6.1f}  gateway={g:>6.1f}  diff={g-b:+.1f}")

    alpha, beta, residuals = least_squares_fit(baseline_points, gateway_points)
    max_repeat_spread = max(repeat_spreads) if repeat_spreads else 0

    verdict = classify_fit(alpha, beta, residuals, max_repeat_spread)

    print(f"\n=== Verdict ===")
    for k, v in verdict.items():
        print(f"  {k}: {v}")

    if args.save_raw:
        full = {
            "probe_version": PROBE_VERSION,
            "baseline_method": "claude_cli_usage_total_input",  # codex-requested provenance
            "token_metric": "total_input_tokens_avg",
            "baseline_cmd": args.baseline_cmd,
            "baseline_shell": args.baseline_shell,
            "gateway_cmd": args.gateway_cmd,
            "gateway_shell": args.gateway_shell,
            "model": args.model,
            "gateway_model": gateway_model,
            "repeats": args.repeats,
            "per_sentinel": per_sentinel,
            "fit": {
                "labels": point_labels,
                "baseline_total_input_avg": baseline_points,
                "gateway_total_input_avg": gateway_points,
                "residuals": residuals,
                "repeat_spread_tokens": repeat_spreads,
            },
            "verdict": verdict,
        }
        with open(args.save_raw, "w", encoding="utf-8") as f:
            json.dump(full, f, indent=2, ensure_ascii=False)
        print(f"\n  raw saved to {args.save_raw}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
