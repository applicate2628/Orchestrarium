"""Unit tests for tokenizer_probe.py fit + classification logic.

Run from proxy-forensics/ root: python scripts/tests/test_tokenizer_probe.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tokenizer_probe as tp

FAILED = []
PASSED = 0


def assert_eq(name, actual, expected):
    global PASSED
    if actual == expected:
        print(f"  [OK] {name}")
        PASSED += 1
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name}\n       expected: {expected!r}\n       actual:   {actual!r}")


def assert_close(name, actual, expected, tol=0.01):
    global PASSED
    if abs(actual - expected) <= tol:
        print(f"  [OK] {name}  ({actual:.4f} ≈ {expected:.4f})")
        PASSED += 1
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name}  expected={expected:.4f}±{tol} actual={actual:.4f}")


def assert_true(name, cond, detail=""):
    global PASSED
    if cond:
        print(f"  [OK] {name}")
        PASSED += 1
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name}  {detail}")


# -------------------------------------------------------------------------
# least_squares_fit — correctness on synthetic points
# -------------------------------------------------------------------------
print("\n--- least_squares_fit ---")

# Exact line: gateway = baseline + 7 (constant offset, alpha=1)
xs = [10, 20, 30, 50, 100]
ys = [17, 27, 37, 57, 107]
alpha, beta, resid = tp.least_squares_fit(xs, ys)
assert_close("alpha_exact_1", alpha, 1.0, tol=1e-9)
assert_close("beta_exact_7", beta, 7.0, tol=1e-9)
assert_true("residuals_zero_on_exact_fit", all(abs(r) < 1e-9 for r in resid),
            f"resid={resid}")

# Proportional drift: gateway = 1.2 * baseline (alpha != 1)
xs = [10, 20, 30, 50, 100]
ys = [12, 24, 36, 60, 120]
alpha, beta, resid = tp.least_squares_fit(xs, ys)
assert_close("alpha_proportional_1_2", alpha, 1.2, tol=1e-9)
assert_close("beta_zero_on_proportional", beta, 0.0, tol=1e-9)

# Noisy data: should fit but with nonzero residuals
xs = [10, 20, 30, 50, 100]
ys = [17, 29, 37, 60, 110]  # same slope 1 + 7, noisy
alpha, beta, resid = tp.least_squares_fit(xs, ys)
max_r = max(abs(r) for r in resid)
assert_true("noisy_residuals_detected", max_r > 0.5, f"max_resid={max_r}")

# Degenerate: 1 point → cannot fit
alpha, beta, resid = tp.least_squares_fit([10], [17])
assert_eq("single_point_no_fit", alpha, None)

# Degenerate: 0 points
alpha, beta, resid = tp.least_squares_fit([], [])
assert_eq("zero_points_no_fit", alpha, None)

# Degenerate: all baseline values identical → division by zero protection
alpha, beta, resid = tp.least_squares_fit([10, 10, 10], [17, 17, 17])
assert_eq("degenerate_same_x_handled", alpha, None)


# -------------------------------------------------------------------------
# classify_fit — verdicts across scenarios
# -------------------------------------------------------------------------
print("\n--- classify_fit ---")

# Helper: 8+ points needed for strong verdicts after codex fix
zero_8 = [0] * 8

# Scenario: Claude BPE (alpha=1, zero residuals, stable repeats, 8+ points)
v = tp.classify_fit(1.00, 7.0, zero_8, repeat_spread_max=0)
assert_eq("claude_bpe_clean", v["verdict"], "claude_bpe")

# Alpha slightly off but within tolerance, 8+ points
v = tp.classify_fit(1.02, 12.0, [1, -1, 0, 1, -1, 0, 1, -1], repeat_spread_max=1)
assert_eq("claude_bpe_small_drift", v["verdict"], "claude_bpe")

# Non-Claude: alpha significantly != 1 (outside [0.9, 1.1]), 8+ points, stable repeats
v = tp.classify_fit(1.25, 0.0, [3, -2, 5, -3, 4, -1, 2, -4], repeat_spread_max=1)
assert_eq("non_claude_proportional", v["verdict"], "non_claude")

# Non-Claude: alpha near 1 BUT stable high class-dependent residuals
# (codex fix: this path was incorrectly → ambiguous in v0.1)
v = tp.classify_fit(1.02, 10.0, [20, -15, 18, -25, 30, -10, 22, -18], repeat_spread_max=1)
assert_eq("non_claude_high_residuals_alpha_near_1", v["verdict"], "non_claude")

# Ambiguous: noisy repeats, even with clean alpha
v = tp.classify_fit(1.01, 7.0, [1, 2, -1, 1, -2, 0, 1, -1], repeat_spread_max=10)
assert_eq("ambiguous_repeat_noise", v["verdict"], "ambiguous")

# Ambiguous: insufficient coverage (n_points < 8) even with perfect fit
v = tp.classify_fit(1.00, 7.0, [0, 0, 0, 0, 0, 0], repeat_spread_max=0)  # 6 points
assert_eq("ambiguous_insufficient_coverage", v["verdict"], "ambiguous")

# claude_bpe_weak: tight alpha, residual drift in [5, 10), stable repeats
# (residuals max must be < 10 to qualify as "small drift"; ≥ 10 triggers non_claude)
v = tp.classify_fit(1.00, 7.0, [5, 8, -6, 7, -9, 9, -5, 6], repeat_spread_max=1)
assert_eq("claude_bpe_weak_drift", v["verdict"], "claude_bpe_weak")

# Insufficient data: alpha=None
v = tp.classify_fit(None, None, [], 0)
assert_eq("insufficient_data_handled", v["verdict"], "insufficient_data")


# -------------------------------------------------------------------------
# Sentinel set basics
# -------------------------------------------------------------------------
print("\n--- SENTINELS set composition ---")
assert_true("sentinel_count_10", len(tp.SENTINELS) == 10,
            f"got {len(tp.SENTINELS)}")
names = [s[0] for s in tp.SENTINELS]
classes = {
    "ascii": sum(1 for n in names if "ascii" in n),
    "cyrillic": sum(1 for n in names if "cyrillic" in n),
    "cjk": sum(1 for n in names if "cjk" in n),
    "emoji": sum(1 for n in names if "emoji" in n),
    "code": sum(1 for n in names if "code" in n),
    "entropy": sum(1 for n in names if "entropy" in n or "hex" in n),
}
assert_true("ascii_paired_short_long", classes["ascii"] == 2,
            f"ascii_count={classes['ascii']}")
assert_true("cyrillic_paired", classes["cyrillic"] == 2)
assert_true("cjk_paired", classes["cjk"] == 2)
assert_true("emoji_present", classes["emoji"] >= 1)
assert_true("code_present", classes["code"] >= 2)
assert_true("high_entropy_present", classes["entropy"] >= 1)

# Sentinels unique
assert_true("sentinels_unique_names", len(set(names)) == len(names))
texts = [t for _, t in tp.SENTINELS]
assert_true("sentinels_unique_texts", len(set(texts)) == len(texts))

# Short/long pairing: shorter in pair < 30 chars, longer > 100 chars
ascii_short = next(t for n, t in tp.SENTINELS if n == "ascii_short")
ascii_long = next(t for n, t in tp.SENTINELS if n == "ascii_long")
assert_true("ascii_short_is_short", len(ascii_short) < 30, f"len={len(ascii_short)}")
assert_true("ascii_long_is_long", len(ascii_long) > 100, f"len={len(ascii_long)}")


# -------------------------------------------------------------------------
# Regression: classify_fit must NOT emit claude_bpe on non-claude-like data
# -------------------------------------------------------------------------
print("\n--- regression guards ---")

# A very-high-confidence non-claude pattern must NOT be claimed as claude_bpe
v = tp.classify_fit(1.5, 50.0, [10, -8, 12, -15, 20, -5, 8, -12], repeat_spread_max=1)
assert_true("non_claude_not_misclassified_as_claude",
            v["verdict"] != "claude_bpe",
            f"verdict={v['verdict']}")

# Claude-like data with minor repeat noise must not escalate to non_claude
v = tp.classify_fit(0.99, 8.0, [-1, 0, 1, 0, -1, 1, 0, -1], repeat_spread_max=2)
assert_true("claude_near_boundary_not_forced_non_claude",
            v["verdict"] in ("claude_bpe", "claude_bpe_weak", "ambiguous"),
            f"verdict={v['verdict']}")

# Codex regression: non_claude requires EITHER alpha drift OR stable high residuals
# Noisy (unstable) high residuals → ambiguous, not non_claude (can't rule out noise)
v = tp.classify_fit(1.00, 7.0, [20, -15, 18, -25, 30, -10, 22, -18], repeat_spread_max=5)
assert_eq("unstable_high_residuals_not_non_claude", v["verdict"], "ambiguous")

# Codex regression: n_points < 8 must never produce strong claude_bpe or non_claude
v = tp.classify_fit(1.00, 7.0, [0, 0, 0], repeat_spread_max=0)
assert_true("few_points_no_strong_claude_bpe",
            v["verdict"] not in ("claude_bpe", "non_claude"),
            f"verdict={v['verdict']}")

v = tp.classify_fit(1.5, 0.0, [2, -1, 3], repeat_spread_max=0)
assert_true("few_points_no_strong_non_claude",
            v["verdict"] not in ("claude_bpe", "non_claude"),
            f"verdict={v['verdict']}")


# -------------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------------
print(f"\n{'='*60}\nRESULTS: {PASSED} passed, {len(FAILED)} failed")
if FAILED:
    print("Failed:")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
print("All tests passed.")
sys.exit(0)
