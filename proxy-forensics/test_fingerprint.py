"""Unit tests for fingerprint.py v0.2 — validates the fixes applied after codex review.

Run: python test_fingerprint.py
No API calls, no network — pure logic validation with mocked CLI outputs.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fingerprint as fp

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


def assert_true(name, cond, detail=""):
    global PASSED
    if cond:
        print(f"  [OK] {name}")
        PASSED += 1
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name}  {detail}")


# -------------------------------------------------------------------------
# Parser tests — distinguishes cli_error vs parse_error vs intercepted
# -------------------------------------------------------------------------
print("\n--- parse_cli_output status classification ---")

# Case 1: CLI error (nonzero return code)
r = fp.parse_cli_output("some stdout", "error message", 1)
assert_eq("nonzero_returncode -> cli_error", r["status"], "cli_error")

# Case 2: Empty stdout (common gateway failure mode)
r = fp.parse_cli_output("", "", 0)
assert_eq("empty_stdout -> cli_error", r["status"], "cli_error")

# Case 3: Invalid JSON
r = fp.parse_cli_output("not valid json at all", "", 0)
assert_eq("invalid_json -> parse_error", r["status"], "parse_error")

# Case 4a: Valid JSON but single object WITHOUT protocol fields → intercepted
r = fp.parse_cli_output('{"acknowledged":true}\n', "", 0)
assert_eq("canned_object -> intercepted", r["status"], "intercepted")
assert_eq("intercepted_raw_hash_computed", len(r["raw_hash"]), 16)
assert_eq("intercepted_raw_bytes", r["raw_bytes"], 22)

# Case 4b: Single-object JSON WITH Claude protocol fields → valid_single_object
# (covers newer CLI versions that may emit single-object --output-format json)
single_obj = json.dumps({
    "type": "result",
    "result": "Hello.",
    "model": "claude-opus-4-7",
    "id": "msg_01ABC",
    "total_cost_usd": 0.01,
    "usage": {"output_tokens": 10},
})
r = fp.parse_cli_output(single_obj, "", 0)
assert_eq("single_object_with_protocol -> valid_single_object", r["status"], "valid_single_object")
assert_eq("single_object_text", r["text"], "Hello.")
assert_eq("single_object_model", r["reported_model"], "claude-opus-4-7")
assert_eq("single_object_out_tok", r["out_tok"], 10)

# Case 4c: Byte-hash priority — when stdout_bytes is supplied, hash is from bytes
b_out = '{"x":1}'.encode("utf-8")
r_b = fp.parse_cli_output('{"x":1}', "", 0, stdout_bytes=b_out)
r_s = fp.parse_cli_output('{"x":1}', "", 0)  # no bytes → fallback to text-hash
assert_eq("bytes_hash_matches_text_hash_on_ascii", r_b["raw_hash"], r_s["raw_hash"])  # same bytes, same hash
assert_eq("bytes_raw_bytes_field", r_b["raw_bytes"], 7)

# Case 5: Valid stream-list (normal CLI output)
stream = json.dumps([
    {"type": "system", "subtype": "init"},
    {"type": "assistant", "message": {
        "model": "claude-opus-4-7",
        "id": "msg_01ABC1234567",
        "content": [{"type": "text", "text": "Hello."}]
    }},
    {"type": "result", "usage": {"output_tokens": 10, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 50}, "total_cost_usd": 0.01},
])
r = fp.parse_cli_output(stream, "", 0)
assert_eq("valid_stream_status", r["status"], "valid_stream")
assert_eq("valid_stream_model", r["reported_model"], "claude-opus-4-7")
assert_eq("valid_stream_msg_id_provider", r["msg_id_provider"], "anthropic-direct")
assert_eq("valid_stream_text", r["text"], "Hello.")
assert_eq("valid_stream_out_tok", r["out_tok"], 10)

# Case 6: Valid list JSON but no assistant message (malformed)
r = fp.parse_cli_output(json.dumps([{"type": "system"}]), "", 0)
assert_eq("no_assistant_messages -> parse_error", r["status"], "parse_error")


# -------------------------------------------------------------------------
# Provider detection
# -------------------------------------------------------------------------
print("\n--- detect_provider ---")
assert_eq("anthropic-direct", fp.detect_provider("msg_01XYZ12345"), "anthropic-direct")
assert_eq("google-vertex",    fp.detect_provider("msg_vrtx_01ABC123"), "google-vertex")
assert_eq("aws-bedrock",      fp.detect_provider("msg_bdrk_01DEF"), "aws-bedrock")
assert_eq("aggregator-uuid",  fp.detect_provider("01234567-89ab-cdef-0123-456789abcdef"), "aggregator-uuid")
assert_eq("empty_msg_id",     fp.detect_provider(""), "unknown")


# -------------------------------------------------------------------------
# Canonical regex — hardened for Unicode / variants
# -------------------------------------------------------------------------
print("\n--- CANONICAL_7_4_OPENING regex (hardened) ---")
cases = [
    ("7^4 = 2401", True),
    ("7 ^ 4 = 2401", True),
    ("7**4=2401", True),
    ("7⁴ = 2401", True),
    ("49^2 = 2401", True),
    ("49·49 = 2401", True),      # AW run1 used this
    ("49·49=2401", True),        # tight variant
    ("49 · 49 = 2401", True),
    ("49*49=2401", True),
    ("49 squared = 2401", True),
    ("49² = 2401", True),
    ("7⁴ ≡ 2401", True),
    ("The answer is 49", False),
    ("2401 = 7^4", False),        # order matters, this is reverse
    # Superscript discrimination — only ⁴ matches, not ⁵ or ³ (v0.3 fix)
    ("7⁵ = 16807", False),        # 7^5 mustn't fool the regex
    ("7³ = 343", False),          # 7^3 mustn't fool it either
]
for text, expected in cases:
    actual = bool(fp.CANONICAL_7_4_OPENING.search(text))
    assert_eq(f'"{text}"', actual, expected)


# -------------------------------------------------------------------------
# Sentence splitter handles abbreviations
# -------------------------------------------------------------------------
print("\n--- split_sentences (abbreviation-aware) ---")
# Should be 1 sentence (U.S. is abbreviation)
s = fp.split_sentences("The U.S. declared independence. And then celebrated. Thus ended the war.")
assert_eq("abbrev_U.S.", len(s), 3)

# CRT proof style from Opus 4.7 output
proof = ("Since p > 3 is prime, p is odd and not divisible by 3, so writing p = 2k+1 gives p² = 4k(k+1)+1 ≡ 1 (mod 8) because k(k+1) is always even, while p ≡ ±1 (mod 3) forces p² ≡ 1 (mod 3). "
         "By the Chinese Remainder Theorem (CRT), since gcd(8,3) = 1 and 8·3 = 24, the pair of congruences p² ≡ 1 (mod 8) and p² ≡ 1 (mod 3) is equivalent to the single congruence p² ≡ 1 (mod 24). "
         "Therefore p² mod 24 = 1 for every prime p > 3.")
sents = fp.split_sentences(proof)
assert_eq("crt_proof_sentence_count", len(sents), 3)
assert_true("s2_contains_crt", "CRT" in sents[1], f"s2 = {sents[1][:80]}")
assert_true("s3_starts_therefore", sents[2].lower().startswith("therefore"), f"s3 = {sents[2][:80]}")


# -------------------------------------------------------------------------
# Scorer: stylometric detects euler bias + answer
# -------------------------------------------------------------------------
print("\n--- score_run_stylometric ---")
# AW-style false-start run
aw_run = {
    "status": "valid_stream",
    "raw_hash": "abc1234567890abc",
    "text": "Reasoning: φ(100)=40, so 7^17 mod 100 = 7^17; compute 7^4=2401≡1, hence 7^17=(7^4)^4·7≡1·7.\nAnswer: 07",
    "cache_create": 0,
    "cache_read": 0,
    "out_tok": 77,
    "msg_id_provider": "google-vertex",
}
s = fp.score_run_stylometric(aw_run)
assert_eq("aw_euler_phrasing", s["euler_phrasing"], True)
assert_eq("aw_tautology", s["tautology"], True)
assert_eq("aw_answer_correct", s["answer_correct"], True)
assert_eq("aw_cache_zero", s["cache_create"], 0)

# Anthropic-direct 4.7 run
direct_run = {
    "status": "valid_stream",
    "raw_hash": "def9876543210def",
    "text": "Reasoning: 7^4 = 2401 ≡ 1 (mod 100), so 7^17 = (7^4)^4 · 7 ≡ 7 (mod 100)\nAnswer: 07",
    "cache_create": 58000,
    "cache_read": 0,
    "out_tok": 538,
    "msg_id_provider": "anthropic-direct",
}
s = fp.score_run_stylometric(direct_run)
assert_eq("direct_no_euler", s["euler_phrasing"], False)
assert_eq("direct_canonical", s["canonical_opening"], True)
assert_eq("direct_answer_correct", s["answer_correct"], True)


# -------------------------------------------------------------------------
# Scorer: anti-euler detects ban compliance + canonical (via hardened regex)
# -------------------------------------------------------------------------
print("\n--- score_run_anti_euler ---")
# AW compliant run (49·49 not 49^2 — this is the regex case codex flagged)
aw_compliant = {
    "status": "valid_stream",
    "raw_hash": "aaa",
    "text": "Reasoning: 7^2=49; 7^4=49·49=2401≡01 mod 100, so 7^17=(7^4)^4·7≡1·7=7.\nAnswer: 7",
}
s = fp.score_run_anti_euler(aw_compliant)
assert_eq("aw_compliant_no_violations", s["banned_violations"], [])
assert_eq("aw_compliant_ban_ok", s["ban_compliant"], True)
assert_eq("aw_compliant_canonical_FIXED", s["canonical_opening"], True)  # v0.2 regex catches 49·49
assert_eq("aw_compliant_answer", s["answer_correct"], True)

# Violator: uses Euler
violator = {
    "status": "valid_stream",
    "raw_hash": "bbb",
    "text": "By Euler's theorem, 7^φ(100) = 7^40 ≡ 1 mod 100, so 7^17 = ...",
}
s = fp.score_run_anti_euler(violator)
assert_true("violator_detects_euler", "euler" in s["banned_violations"])
assert_true("violator_detects_phi", "φ" in s["banned_violations"])
assert_eq("violator_ban_fail", s["ban_compliant"], False)


# -------------------------------------------------------------------------
# Aggregator: multi-run intercept requires byte-identical
# -------------------------------------------------------------------------
print("\n--- aggregate_probe: introspection ---")

# Case: 2 runs, both intercepted, SAME hash -> hard_intercept
sigs = [
    {"raw_hash": "same1234567890ab", "status": "intercepted", "intercept_candidate": True,
     "canned_ack_match": True, "raw_stripped": '{"acknowledged":true}'},
    {"raw_hash": "same1234567890ab", "status": "intercepted", "intercept_candidate": True,
     "canned_ack_match": True, "raw_stripped": '{"acknowledged":true}'},
]
agg = fp.aggregate_probe("self_introspection_json", sigs)
assert_true("byte_identical_2runs -> hard_intercept",
            "hard_intercept" in agg["signals"],
            f"signals: {agg['signals']}")

# Case: 2 runs, both intercepted, DIFFERENT hashes -> variable_intercept (weaker)
sigs = [
    {"raw_hash": "hash_one_abcdef00", "status": "intercepted", "intercept_candidate": True},
    {"raw_hash": "hash_two_abcdef00", "status": "intercepted", "intercept_candidate": True},
]
agg = fp.aggregate_probe("self_introspection_json", sigs)
assert_true("different_hashes -> variable_intercept (not hard)",
            "variable_intercept" in agg["signals"] and "hard_intercept" not in agg["signals"],
            f"signals: {agg['signals']}")

# Case: 2 runs, one intercept one valid -> inconsistent
sigs = [
    {"raw_hash": "hash1", "status": "intercepted", "intercept_candidate": True},
    {"raw_hash": "hash2", "status": "valid_stream", "intercept_candidate": False, "json_parse_ok": True},
]
agg = fp.aggregate_probe("self_introspection_json", sigs)
assert_true("mixed -> inconsistent (no hard intercept)",
            "hard_intercept" not in agg["signals"],
            f"signals: {agg['signals']}")

# v0.3 fix: single-run intercept should NOT emit hard_intercept
# (was a bug — single run has trivially one unique hash, passed old check)
sigs_single = [
    {"raw_hash": "only_one_run_abc", "status": "intercepted", "intercept_candidate": True,
     "canned_ack_match": True},
]
agg = fp.aggregate_probe("self_introspection_json", sigs_single)
assert_true("single_run_intercept -> NO hard_intercept (v0.3 fix)",
            "hard_intercept" not in agg["signals"],
            f"signals: {agg['signals']}")
assert_true("single_run_intercept -> single_run_intercept_unverified",
            "single_run_intercept_unverified" in agg["signals"],
            f"signals: {agg['signals']}")


# -------------------------------------------------------------------------
# Aggregator: anti-euler requires all runs compliant for signal
# -------------------------------------------------------------------------
print("\n--- aggregate_probe: anti_euler ---")
# Both runs compliant
sigs = [
    {"raw_hash": "a", "ban_compliant": True, "canonical_opening": True, "answer_correct": True},
    {"raw_hash": "b", "ban_compliant": True, "canonical_opening": True, "answer_correct": True},
]
agg = fp.aggregate_probe("anti_euler_override", sigs)
assert_true("anti_euler_both_pass -> soft_override_success",
            "soft_override_success" in agg["signals"])

# One violates
sigs = [
    {"raw_hash": "a", "ban_compliant": True, "canonical_opening": True, "answer_correct": True, "banned_violations": []},
    {"raw_hash": "b", "ban_compliant": False, "canonical_opening": False, "answer_correct": True, "banned_violations": ["euler"]},
]
agg = fp.aggregate_probe("anti_euler_override", sigs)
assert_true("anti_euler_one_fail -> rigid_bias",
            "rigid_bias" in agg["signals"],
            f"signals: {agg['signals']}")

# v0.3 fix: status_failure runs (CLI errors, intercepts) must NOT convert
# to rigid_bias. Ban-compliance check only applies to valid runs.
sigs = [
    {"raw_hash": "a", "status_failure": "cli_error"},
    {"raw_hash": "b", "status_failure": "cli_error"},
]
agg = fp.aggregate_probe("anti_euler_override", sigs)
assert_true("anti_euler_all_failed_runs -> NO rigid_bias (v0.3 fix)",
            "rigid_bias" not in agg["signals"],
            f"signals: {agg['signals']}")
assert_true("anti_euler_all_failed_runs -> no_valid_runs",
            "no_valid_runs" in agg["signals"],
            f"signals: {agg['signals']}")

# Mixed: one valid (compliant), one status_failure → should treat as single-valid-run
# and NOT force rigid_bias from the failure.
sigs = [
    {"raw_hash": "a", "ban_compliant": True, "canonical_opening": True, "answer_correct": True, "banned_violations": []},
    {"raw_hash": "b", "status_failure": "timeout"},
]
agg = fp.aggregate_probe("anti_euler_override", sigs)
assert_true("anti_euler_mixed_valid_and_failure -> override from valid only",
            "rigid_bias" not in agg["signals"],
            f"signals: {agg['signals']}")


# -------------------------------------------------------------------------
# Classify: AW-like profile produces A+Middleware with high confidence
# -------------------------------------------------------------------------
print("\n--- classify: AW-profile synthetic scenario ---")
# Simulated probe findings mirroring what AW produces
findings = {
    "self_introspection_json": {"signals": {"hard_intercept": 0.9}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.8}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {"feature_strip_no_cache": 0.6, "stylometric_euler_bias": 0.6,
                                     "tautology_artifact": 0.5}, "notes": []},
}
v = fp.classify(findings)
assert_true("AW_profile_primary_is_A+Middleware",
            v["primary_hypothesis"].startswith("A+Middleware"),
            f"primary={v['primary_hypothesis']}")
assert_true("AW_profile_high_confidence", v["confidence"] in ("high", "medium"),
            f"confidence={v['confidence']} primary={v['primary_score']}")


# -------------------------------------------------------------------------
# Classify: pure-distill profile (no middleware, no override)
# -------------------------------------------------------------------------
print("\n--- classify: distill-profile synthetic scenario ---")
findings = {
    "self_introspection_json": {"signals": {}, "notes": []},
    "anti_euler_override": {"signals": {"rigid_bias": 0.7}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_fail": 0.5}, "notes": []},
    "temporal_cutoff": {"signals": {"early_2025_knowledge": 0.3}, "notes": []},
    "stylometric_717": {"signals": {"stylometric_euler_bias": 0.6}, "notes": []},
}
v = fp.classify(findings)
assert_true("distill_profile_picks_C",
            "C (distill" in v["primary_hypothesis"] or v["evidence_weights"]["distill"] > 0.5,
            f"primary={v['primary_hypothesis']} weights={v['evidence_weights']}")


# -------------------------------------------------------------------------
# Classify: clean direct Opus (no middleware, passes all)
# -------------------------------------------------------------------------
print("\n--- classify: clean-direct profile ---")
findings = {
    "self_introspection_json": {"signals": {"clean_introspection": 0.7}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.85}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}
v = fp.classify(findings)
# Should not pick A+Middleware (middleware evidence low)
# Should pick A-clean (note: both hypotheses contain "middleware" as a word)
assert_true("clean_direct_picks_A_clean_not_A_plus",
            v["primary_hypothesis"].startswith("A-clean") and "+" not in v["primary_hypothesis"],
            f"primary={v['primary_hypothesis']}")


# -------------------------------------------------------------------------
# Classify: insufficient evidence → low confidence
# -------------------------------------------------------------------------
print("\n--- classify: insufficient-evidence profile ---")
findings = {
    "self_introspection_json": {"signals": {}, "notes": []},
    "anti_euler_override": {"signals": {}, "notes": []},
    "tight_reasoning_crt": {"signals": {}, "notes": []},
    "temporal_cutoff": {"signals": {}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}
v = fp.classify(findings)
assert_eq("insufficient_evidence_confidence", v["confidence"], "low")


# -------------------------------------------------------------------------
# v0.4 adversarial classifier matrices
# -------------------------------------------------------------------------
print("\n--- classify: v0.4 adversarial scenarios ---")

# Scenario 1: hard-intercept ONLY (no capable_base) → A+Middleware gate fails
findings = {
    "self_introspection_json": {"signals": {"hard_intercept": 0.9}, "notes": []},
    "anti_euler_override": {"signals": {}, "notes": []},
    "tight_reasoning_crt": {"signals": {}, "notes": []},
    "temporal_cutoff": {"signals": {}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}
v = fp.classify(findings)
assert_true("hard_intercept_alone_NOT_high_confidence",
            v["confidence"] != "high" or "A+Middleware" not in v["primary_hypothesis"],
            f"confidence={v['confidence']} primary={v['primary_hypothesis']} gates={v.get('gates_passed')}")
assert_eq("A+Middleware_gate_fails_without_capable_base",
          v["gates_passed"]["A+Middleware"], False)

# Scenario 2: hard-intercept + temporal-cutoff only (no capable_base) → A+Middleware gate still fails
findings = {
    "self_introspection_json": {"signals": {"hard_intercept": 0.9}, "notes": []},
    "anti_euler_override": {"signals": {}, "notes": []},
    "tight_reasoning_crt": {"signals": {}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}
v = fp.classify(findings)
assert_eq("A+Middleware_gate_still_fails_without_capable_base",
          v["gates_passed"]["A+Middleware"], False)

# Scenario 3: variable-intercept + otherwise-clean → A-clean gate fails (suspicious_intercept present)
findings = {
    "self_introspection_json": {"signals": {"variable_intercept": 0.45}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.85}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}
v = fp.classify(findings)
# Variable intercept should disqualify A-clean from high confidence
assert_true("variable_intercept_blocks_A_clean_high",
            v["confidence"] != "high" or "A-clean" not in v["primary_hypothesis"] or not v["gates_passed"]["A-clean"],
            f"confidence={v['confidence']} primary={v['primary_hypothesis']} gates={v.get('gates_passed')}")

# Scenario 4: hard_intercept + capable_base (AW-like) → high A+Middleware as expected
findings = {
    "self_introspection_json": {"signals": {"hard_intercept": 0.9}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.8}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {"feature_strip_no_cache": 0.6, "stylometric_euler_bias": 0.6}, "notes": []},
}
v = fp.classify(findings)
assert_true("AW_reproduces_A+Middleware_primary",
            v["primary_hypothesis"].startswith("A+Middleware"),
            f"primary={v['primary_hypothesis']}")
assert_eq("AW_A+Middleware_gate_passes", v["gates_passed"]["A+Middleware"], True)


# -------------------------------------------------------------------------
# v0.4 protocol-object detection — stricter heuristic
# -------------------------------------------------------------------------
print("\n--- parse_cli_output: stricter single-object protocol detection ---")

# Adversarial: gateway wraps intercept in {"result": "..."} without usage/model/session
wrapper = json.dumps({"result": "{\"acknowledged\":true}"})
r = fp.parse_cli_output(wrapper, "", 0)
assert_eq("wrapped_intercept_detected_as_intercepted",
          r["status"], "intercepted")

# Only has `type` field — too weak for protocol object, should be intercepted
r = fp.parse_cli_output(json.dumps({"type": "ok"}), "", 0)
assert_eq("type_only_not_enough_for_single_object",
          r["status"], "intercepted")

# Genuine: result + usage.output_tokens → valid_single_object
genuine = json.dumps({
    "result": "Hello",
    "usage": {"output_tokens": 5, "input_tokens": 10},
    "model": "claude-opus-4-7",
})
r = fp.parse_cli_output(genuine, "", 0)
assert_eq("genuine_single_object_accepted", r["status"], "valid_single_object")

# Non-Claude-looking model string rejected
not_claude = json.dumps({"result": "Hi", "model": "gpt-5.5"})
r = fp.parse_cli_output(not_claude, "", 0)
assert_eq("non_claude_model_intercepted", r["status"], "intercepted")

# v0.5: forged "claude" prefix without hyphen must NOT pass single-object heuristic
forged = json.dumps({"result": "Hi", "model": "claudefake"})
r = fp.parse_cli_output(forged, "", 0)
assert_eq("forged_claude_prefix_intercepted", r["status"], "intercepted")

forged2 = json.dumps({"result": "Hi", "model": "claude"})
r = fp.parse_cli_output(forged2, "", 0)
assert_eq("bare_claude_intercepted", r["status"], "intercepted")

# But hyphenated Claude family IDs pass
legit = json.dumps({"result": "Hi", "model": "claude-opus-4-7"})
r = fp.parse_cli_output(legit, "", 0)
assert_eq("claude-opus-4-7_accepted", r["status"], "valid_single_object")

# Stream list containing scalars → parse_error (v0.4 type-guard)
r = fp.parse_cli_output(json.dumps([{"type": "system"}, "scalar_string", 42]), "", 0)
assert_eq("stream_list_with_scalars_parse_error", r["status"], "parse_error")


# -------------------------------------------------------------------------
# v0.4 introspection schema validation
# -------------------------------------------------------------------------
print("\n--- score_run_introspection: full schema required ---")

# Complete schema → schema_match=True
complete = {"status": "valid_stream", "raw_hash": "h1",
            "text": '{"architecture_family":"Claude","supports_extended_thinking":true,"can_use_prompt_caching":true,"knowledge_cutoff_month":"January 2026"}'}
s = fp.score_run_introspection(complete)
assert_eq("complete_schema_matches", s.get("schema_match"), True)

# Missing one field → schema_match=False
partial = {"status": "valid_stream", "raw_hash": "h2",
           "text": '{"architecture_family":"Claude","supports_extended_thinking":true}'}
s = fp.score_run_introspection(partial)
assert_eq("partial_schema_no_match", s.get("schema_match"), False)
assert_true("partial_schema_missing_field_recorded",
            "schema_missing_field" in s and "can_use_prompt_caching" in s["schema_missing_field"])

# Wrong type (bool as string) → schema_match=False
wrong_type = {"status": "valid_stream", "raw_hash": "h3",
              "text": '{"architecture_family":"Claude","supports_extended_thinking":"yes","can_use_prompt_caching":true,"knowledge_cutoff_month":"January 2026"}'}
s = fp.score_run_introspection(wrong_type)
assert_eq("wrong_type_schema_no_match", s.get("schema_match"), False)
assert_true("wrong_type_recorded", "schema_wrong_type" in s)

# v0.6.1: codefenced schema-correct introspection → codefence_wrap=True + schema_match=True
# Aggregator emits clean_introspection at REDUCED weight (0.6 vs 0.7) — was bug A in
# v0.6 calibration that produced ambiguous verdicts on Opus 4.6 (codefenced output).
codefenced = {"status": "valid_stream", "raw_hash": "h4",
              "text": '```json\n{"architecture_family":"Claude","supports_extended_thinking":true,"can_use_prompt_caching":true,"knowledge_cutoff_month":"January 2026"}\n```'}
s = fp.score_run_introspection(codefenced)
assert_eq("codefenced_schema_match", s.get("schema_match"), True)
assert_eq("codefenced_wrap_detected", s.get("codefence_wrap"), True)
agg = fp.aggregate_probe("self_introspection_json", [s, s])
assert_true("codefenced_schema_emits_clean_at_reduced_weight",
            agg["signals"].get("clean_introspection") == 0.6,
            f"signals: {agg['signals']}")

# Aggregator: schema_mismatch emitted when JSON parses but schema fails
sigs = [
    {"raw_hash": "a", "status": "valid_stream", "intercept_candidate": False,
     "json_parse_ok": True, "schema_match": False, "codefence_wrap": False},
    {"raw_hash": "b", "status": "valid_stream", "intercept_candidate": False,
     "json_parse_ok": True, "schema_match": False, "codefence_wrap": False},
]
agg = fp.aggregate_probe("self_introspection_json", sigs)
assert_true("schema_mismatch_signal_emitted",
            "schema_mismatch" in agg["signals"],
            f"signals: {agg['signals']}")
assert_true("schema_mismatch_no_clean_introspection",
            "clean_introspection" not in agg["signals"])


# -------------------------------------------------------------------------
# v0.4 temporal cutoff — verifiable-only
# -------------------------------------------------------------------------
print("\n--- aggregate_probe: temporal verifiable-only ---")

# Generic late-2025 mention (verifiable=False) must NOT promote post_april
sigs = [
    {"raw_hash": "a", "events_found": ["Late-2025 event (cutoff > April 2025)"], "latest_month_code": 6},
    {"raw_hash": "b", "events_found": ["Late-2025 event (cutoff > April 2025)"], "latest_month_code": 6},
]
agg = fp.aggregate_probe("temporal_cutoff", sigs)
assert_true("generic_late_2025_NOT_post_april",
            "post_april_2025_knowledge" not in agg["signals"],
            f"signals: {agg['signals']}")

# Verifiable Pope Leo XIV mention → post_april_2025
sigs = [
    {"raw_hash": "a", "events_found": ["May 2025 Pope Leo XIV election"], "latest_month_code": 5},
]
agg = fp.aggregate_probe("temporal_cutoff", sigs)
assert_true("pope_leo_xiv_IS_post_april",
            "post_april_2025_knowledge" in agg["signals"],
            f"signals: {agg['signals']}")

# v0.5: False-dated event (April 2025 Pope Leo XIV — model hallucinates wrong month)
# should NOT match the tightened May-only pattern.
false_dated_text = "Reasoning\nApril 2025 Pope Leo XIV elected at the Vatican."
mock_run = {"status": "valid_stream", "raw_hash": "h", "text": false_dated_text}
s = fp.score_run_temporal(mock_run)
assert_true("false_dated_leo_xiv_not_matched",
            "May 2025 Pope Leo XIV election" not in s.get("events_found", []),
            f"events_found: {s.get('events_found')}")


# -------------------------------------------------------------------------
# v0.4 soft-override conditional scoring
# -------------------------------------------------------------------------
print("\n--- classify: soft_override conditional on stylometric bias ---")

# With bias observed → full capable_base credit
findings_with_bias = {
    "self_introspection_json": {"signals": {}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.85}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {"stylometric_euler_bias": 0.6}, "notes": []},
}
v_bias = fp.classify(findings_with_bias)

# Without bias observed → weaker capable_base signal
findings_without_bias = {
    "self_introspection_json": {"signals": {}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.85}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}
v_nobias = fp.classify(findings_without_bias)
assert_true("bias_observed_gives_higher_capable_base",
            v_bias["evidence_weights"]["capable_base"] > v_nobias["evidence_weights"]["capable_base"],
            f"with_bias={v_bias['evidence_weights']['capable_base']} without={v_nobias['evidence_weights']['capable_base']}")


# -------------------------------------------------------------------------
# v0.5 adversarial tests (codex round-4 findings)
# -------------------------------------------------------------------------
print("\n--- classify: v0.5 inconsistent_intercept blocks A-clean high ---")

# Blocker fix: inconsistent_intercept (0.25) + otherwise-clean should NOT yield high A-clean
findings = {
    "self_introspection_json": {"signals": {"inconsistent_intercept": 0.25}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.85}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {"stylometric_euler_bias": 0.6}, "notes": []},
}
v = fp.classify(findings)
assert_eq("inconsistent_intercept_A_clean_gate_fails",
          v["gates_passed"]["A-clean"], False)
# Even if A-clean still ranks, confidence can't be high
assert_true("inconsistent_intercept_no_high_confidence_A_clean",
            not (v["primary_hypothesis"].startswith("A-clean") and v["confidence"] == "high"),
            f"primary={v['primary_hypothesis']} confidence={v['confidence']}")

# Also check: single_run_intercept_unverified blocks A-clean
findings["self_introspection_json"] = {"signals": {"single_run_intercept_unverified": 0.2}, "notes": []}
v = fp.classify(findings)
assert_eq("single_run_intercept_unverified_A_clean_gate_fails",
          v["gates_passed"]["A-clean"], False)

# And schema_mismatch blocks A-clean
findings["self_introspection_json"] = {"signals": {"schema_mismatch": 0.4}, "notes": []}
v = fp.classify(findings)
assert_eq("schema_mismatch_A_clean_gate_fails",
          v["gates_passed"]["A-clean"], False)

# Positive control: truly clean introspection → A-clean gate can pass
findings["self_introspection_json"] = {"signals": {"clean_introspection": 0.7}, "notes": []}
v = fp.classify(findings)
assert_eq("clean_introspection_A_clean_gate_can_pass",
          v["gates_passed"]["A-clean"], True)


# -------------------------------------------------------------------------
# v0.6: tokenizer evidence integration
# -------------------------------------------------------------------------
print("\n--- classify: v0.6 tokenizer evidence ---")

# Scenario: AW-like profile + tokenizer verdict = non_claude
# → distill+middleware should now be primary (not A+Middleware)
findings_aw = {
    "self_introspection_json": {"signals": {"hard_intercept": 0.9}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.8}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {"feature_strip_no_cache": 0.6, "stylometric_euler_bias": 0.6}, "notes": []},
}

# Without tokenizer evidence → A+Middleware primary + annotation
v = fp.classify(findings_aw)
assert_true("A+Middleware_without_tokenizer_has_annotation",
            any("distill+middleware UNRESOLVED" in a for a in v.get("annotations", [])),
            f"annotations={v.get('annotations')}")

# With tokenizer=non_claude → distill+middleware should now be primary
v = fp.classify(findings_aw, tokenizer_evidence={"verdict": "non_claude"})
assert_true("tokenizer_non_claude_opens_distill_middleware",
            v["gates_passed"]["distill+middleware"],
            f"gates={v.get('gates_passed')}")
assert_true("tokenizer_non_claude_blocks_A_plus_middleware",
            not v["gates_passed"]["A+Middleware"],
            f"gates={v.get('gates_passed')}")

# With tokenizer=claude_bpe → A+Middleware stays primary, tokenizer_claude evidence helps
v = fp.classify(findings_aw, tokenizer_evidence={"verdict": "claude_bpe"})
assert_true("tokenizer_claude_keeps_A_plus_middleware",
            v["gates_passed"]["A+Middleware"],
            f"gates={v.get('gates_passed')}")

# Clean profile + non_claude tokenizer → A-clean VETOED
findings_clean = {
    "self_introspection_json": {"signals": {"clean_introspection": 0.7}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.85}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}
v_clean = fp.classify(findings_clean, tokenizer_evidence={"verdict": "non_claude"})
assert_eq("non_claude_tokenizer_vetoes_A_clean_gate",
          v_clean["gates_passed"]["A-clean"], False)

# Ambiguous tokenizer should NOT contribute (codex regression)
v = fp.classify(findings_aw, tokenizer_evidence={"verdict": "ambiguous"})
assert_true("ambiguous_tokenizer_no_contribution",
            v["evidence_weights"]["tokenizer_non_claude"] == 0.0
            and v["evidence_weights"]["tokenizer_claude"] == 0.0,
            f"weights={v['evidence_weights']}")

# insufficient_data also → no contribution
v = fp.classify(findings_aw, tokenizer_evidence={"verdict": "insufficient_data"})
assert_true("insufficient_tokenizer_no_contribution",
            v["evidence_weights"]["tokenizer_non_claude"] == 0.0
            and v["evidence_weights"]["tokenizer_claude"] == 0.0)


# -------------------------------------------------------------------------
# v0.6: network evidence integration
# -------------------------------------------------------------------------
print("\n--- classify: v0.6 network evidence ---")

findings_minimal = {
    "self_introspection_json": {"signals": {}, "notes": []},
    "anti_euler_override": {"signals": {}, "notes": []},
    "tight_reasoning_crt": {"signals": {}, "notes": []},
    "temporal_cutoff": {"signals": {}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}

# aggressive_defense alone → +0.2 middleware (bounded)
v = fp.classify(findings_minimal, network_evidence={"aggressive_defense": True})
assert_true("aggressive_defense_contributes_middleware",
            v["evidence_weights"]["middleware"] >= 0.15,
            f"weights={v['evidence_weights']}")

# aggressive_defense alone must NOT produce high confidence A+Middleware
# (codex regression: "network alone must not override behavioral evidence")
v = fp.classify(findings_minimal, network_evidence={"aggressive_defense": True})
assert_true("network_alone_no_high_confidence",
            v["confidence"] != "high" or not v["primary_hypothesis"].startswith("A+Middleware"),
            f"verdict={v['primary_hypothesis']} confidence={v['confidence']}")

# middleware_software_detected (LiteLLM) → stronger signal
v = fp.classify(findings_minimal, network_evidence={"middleware_software_detected": ["LiteLLM"]})
assert_true("middleware_software_detected_contributes",
            v["evidence_weights"]["middleware"] >= 0.3,
            f"weights={v['evidence_weights']}")

# cdn_match_anthropic → network_support evidence
v = fp.classify(findings_minimal, network_evidence={"cdn_match_anthropic": True})
assert_true("cdn_match_anthropic_network_support",
            v["evidence_weights"]["network_support"] > 0,
            f"weights={v['evidence_weights']}")

# A-clean without network probe must NOT be penalized (codex regression)
v_no_net = fp.classify(findings_clean)
v_with_net_empty = fp.classify(findings_clean, network_evidence={})
# A-clean gate status should be identical
assert_eq("A_clean_no_penalty_missing_network",
          v_no_net["gates_passed"]["A-clean"],
          v_with_net_empty["gates_passed"]["A-clean"])

# Network cap: all three network signals fire simultaneously, middleware not unbounded
v = fp.classify(findings_minimal, network_evidence={
    "aggressive_defense": True,
    "middleware_software_detected": ["LiteLLM", "Portkey"],
    "cdn_match_anthropic": True,
})
assert_true("network_contribution_capped",
            v["evidence_weights"]["middleware"] <= 0.8,
            f"middleware weight={v['evidence_weights']['middleware']}")


# -------------------------------------------------------------------------
# v0.6 codex regression: tokenizer absent must not split confident distill/MW
# -------------------------------------------------------------------------
print("\n--- v0.6 regression: tokenizer absent ---")
findings_aw_like = {
    "self_introspection_json": {"signals": {"hard_intercept": 0.9}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.8}, "notes": []},
    "temporal_cutoff": {"signals": {"post_april_2025_knowledge": 0.7}, "notes": []},
    "stylometric_717": {"signals": {"feature_strip_no_cache": 0.6, "stylometric_euler_bias": 0.6}, "notes": []},
}
v = fp.classify(findings_aw_like)  # no tokenizer_evidence
assert_eq("no_tokenizer_distill_middleware_gate_false",
          v["gates_passed"]["distill+middleware"], False)
assert_true("no_tokenizer_A_plus_middleware_primary",
            v["primary_hypothesis"].startswith("A+Middleware"),
            f"primary={v['primary_hypothesis']}")


# -------------------------------------------------------------------------
# v0.6.1 calibration bugs (Bug A: codefenced introspection, Bug C: april cutoff)
# -------------------------------------------------------------------------
print("\n--- v0.6.1 calibration regressions ---")

# Bug A: codefenced schema-correct introspection should still emit clean_introspection
# (was: dropped to no-signal when codefence_wrap=True, breaking Opus 4.6 calibration)
codefenced_match = {"raw_hash": "h",
                    "status": "valid_stream",
                    "intercept_candidate": False,
                    "json_parse_ok": True,
                    "schema_match": True,
                    "codefence_wrap": True}
agg = fp.aggregate_probe("self_introspection_json", [codefenced_match, codefenced_match])
assert_true("codefenced_schema_match_emits_clean_introspection",
            "clean_introspection" in agg["signals"],
            f"signals={agg['signals']}")
# But weight is reduced (0.6) vs unfenced (0.7)
assert_true("codefenced_clean_introspection_weight_lower",
            agg["signals"]["clean_introspection"] == 0.6,
            f"got={agg['signals'].get('clean_introspection')}")

# Mixed: one clean + one codefenced → still clean_introspection (0.6)
clean_match = {"raw_hash": "h", "status": "valid_stream",
               "intercept_candidate": False, "json_parse_ok": True,
               "schema_match": True, "codefence_wrap": False}
agg = fp.aggregate_probe("self_introspection_json", [clean_match, codefenced_match])
assert_true("mixed_clean_and_codefenced_still_emits_clean",
            "clean_introspection" in agg["signals"])

# Bug D (v0.6.1): Haiku-tier models have no 2025 knowledge (pre-2025 cutoff)
# but still produce valid clean A-clean signals on other probes. Verify they
# can reach at least medium confidence with the tightened ambiguous divisor.
findings_haiku = {
    "self_introspection_json": {"signals": {"clean_introspection": 0.6}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.8}, "notes": []},
    "temporal_cutoff": {"signals": {"no_verified_2025": 0.3}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}
v_haiku = fp.classify(findings_haiku)
assert_true("haiku_no_2025_still_A_clean_primary",
            v_haiku["primary_hypothesis"].startswith("A-clean"),
            f"primary={v_haiku['primary_hypothesis']}")
assert_true("haiku_reaches_medium_confidence_minimum",
            v_haiku["confidence"] in ("medium", "high"),
            f"confidence={v_haiku['confidence']} score={v_haiku['primary_score']} gap={v_haiku['gap_to_second']}")

# Bug C: april_2025_knowledge → recent_cutoff evidence (was: silently dropped)
findings_4_5 = {
    "self_introspection_json": {"signals": {"clean_introspection": 0.7}, "notes": []},
    "anti_euler_override": {"signals": {"soft_override_success": 0.85}, "notes": []},
    "tight_reasoning_crt": {"signals": {"format_rigor_pass": 0.8}, "notes": []},
    "temporal_cutoff": {"signals": {"april_2025_knowledge": 0.5}, "notes": []},
    "stylometric_717": {"signals": {}, "notes": []},
}
v = fp.classify(findings_4_5)
assert_true("april_2025_contributes_recent_cutoff",
            v["evidence_weights"]["recent_cutoff"] > 0,
            f"weights={v['evidence_weights']}")

# A-clean primary + high confidence achievable for older-Opus profile (4.5/4.6)
assert_true("opus_april_cutoff_reaches_A_clean",
            v["primary_hypothesis"].startswith("A-clean"),
            f"primary={v['primary_hypothesis']}")
assert_eq("opus_april_cutoff_A_clean_gate_passes",
          v["gates_passed"]["A-clean"], True)

# early_2025_knowledge gives weaker signal (0.5 weight × 0.5)
findings_early = dict(findings_4_5)
findings_early["temporal_cutoff"] = {"signals": {"early_2025_knowledge": 0.3}, "notes": []}
v_early = fp.classify(findings_early)
assert_true("early_2025_weaker_than_april",
            v_early["evidence_weights"]["recent_cutoff"] < v["evidence_weights"]["recent_cutoff"])

# no_verified_2025 should not contribute recent_cutoff
findings_none = dict(findings_4_5)
findings_none["temporal_cutoff"] = {"signals": {"no_verified_2025": 0.3}, "notes": []}
v_none = fp.classify(findings_none)
assert_eq("no_verified_2025_no_recent_cutoff_credit",
          v_none["evidence_weights"]["recent_cutoff"], 0.0)


# -------------------------------------------------------------------------
# Baseline freshness — v0.3 fix: missing/malformed expiry_date fails closed
# -------------------------------------------------------------------------
print("\n--- check_baseline_freshness (fails closed on missing expiry) ---")

stale, msg = fp.check_baseline_freshness({"metadata": {}})
assert_true("missing_expiry_date_fails_closed", stale, msg)

stale, msg = fp.check_baseline_freshness({"metadata": {"expiry_date": "not-a-date"}})
assert_true("malformed_expiry_date_fails_closed", stale, msg)

stale, msg = fp.check_baseline_freshness({"metadata": {"expiry_date": "2000-01-01"}})
assert_true("past_expiry_stale", stale, msg)

# Valid future date → not stale
from datetime import date, timedelta
future = (date.today() + timedelta(days=30)).isoformat()
stale, msg = fp.check_baseline_freshness({"metadata": {"expiry_date": future}})
assert_true("future_expiry_not_stale", not stale, msg)


# -------------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------------
print(f"\n{'='*60}\nRESULTS: {PASSED} passed, {len(FAILED)} failed")
if FAILED:
    print("Failed tests:")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("All tests passed.")
    sys.exit(0)
