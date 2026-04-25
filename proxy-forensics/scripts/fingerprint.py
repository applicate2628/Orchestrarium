#!/usr/bin/env python3
"""
Claude proxy forensic fingerprinter — v0.6.

Given a command that speaks the Claude Code CLI protocol (plain `claude` or
a wrapper like `claude-aw.cmd`), run a battery of probes to classify the
backend and detect middleware interference.

v0.6 changes (fifth codex gpt-5.5 xhigh review):
  - tokenizer_probe.py added (separate script): sends 10 sentinels through
    baseline + suspect, fits alpha/beta/residuals, emits claude_bpe /
    non_claude / ambiguous verdict.
  - distill+middleware hypothesis added to classifier: gated on
    tokenizer_non_claude >= 0.5 AND middleware >= 0.6. When tokenizer probe
    is NOT run, A+Middleware verdicts are annotated "distill+middleware
    unresolved" rather than silently assuming real Claude.
  - Network evidence integration: --network-probe-url flag co-runs
    network_probe.py and feeds TLS/CDN/defense signals into classifier
    with capped contribution (corroborating only, not load-bearing).
  - Tokenizer non_claude vetoes A-clean high confidence.
  - mitm_capture.py subprocess hang fix: Popen + poll-loop + taskkill
    /F /T /PID on Windows; start_new_session=True + pgid safety guard
    on POSIX.

v0.5 changes (fourth codex gpt-5.5 xhigh review):
  - A-clean gate now blocks on ANY intercept signal (hard/variable/inconsistent/
    schema_mismatch/single_run_intercept_unverified), not just those crossing
    an arbitrary threshold. Suspicious_intercept threshold tightened 0.3 → 0.1.
  - Hypothesis labels softened: "real Claude" → "Claude-like backend".
  - Scorer-version major-mismatch blocks execution (fail-closed), not just
    prints a warning.
  - baselines.json scorer_version bumped to 0.5.0; planned-v0.3 text cleaned
    up; distill+middleware entry added to known_gaps (now resolved in v0.6
    via tokenizer-gated hypothesis).
  - RESULTS.md softened further: "inconsistent with distilled student" →
    "less consistent with rigidly-biased distilled-only student".

v0.4 changes (third codex gpt-5.5 xhigh review):
  - Classifier has HARD EVIDENCE GATES: A+Middleware requires both
    middleware ≥ 0.6 AND capable_base ≥ 0.5; A-clean requires capable_base
    ≥ 0.6 AND middleware/suspicious_intercept low; C requires distill ≥
    0.6 AND low capable_base. Hypotheses failing their gate can't reach
    high confidence.
  - Introspection schema validation: clean_introspection requires all 4
    fields with credible types. Schema-shaped-but-wrong JSON emits
    schema_mismatch (middleware evidence) instead of clean.
  - Protocol-object detection stricter: single-object JSON must have
    `result` string AND (usage dict with token counts OR model starting
    "claude-" OR session_id ≥ 8 chars). Prevents gateway wrappers like
    `{"result":"{\"acknowledged\":true}"}` from evading intercept.
  - Variable/inconsistent intercept penalizes A-clean (adaptive gateway
    can't be classified clean).
  - Soft-override conditional: fully counts as capable-base evidence only
    when stylometric bias was first observed; otherwise 0.3× multiplier.
  - Temporal cutoff requires verifiable events; generic month-only
    mentions no longer promote cutoff.
  - Parser type-guards stream-list elements (scalars → parse_error).

v0.3:
  - valid_single_object vs intercepted distinction.
  - status_failure runs filtered from scoring.
  - hard_intercept ≥ 2 repeats.
  - Byte-level raw hash.
  - Superscript regex only ⁴.
  - Missing expiry_date fails closed.

v0.2:
  - cli_error/parse_error/intercepted/valid_stream separation.
  - --repeats N flag.
  - Confidence-graded classification.
  - Hardened Unicode regex.
  - Baseline expiry check.

Usage (run from `proxy-forensics/` root):
  python scripts/fingerprint.py --label "AW" --cmd "claude-aw.cmd --model opus" --shell
  python scripts/fingerprint.py --label "direct" --cmd "claude --model claude-opus-4-7"
  python scripts/fingerprint.py --list-probes
  python scripts/fingerprint.py --label "X" --cmd "..." --repeats 2

Dependencies: Python 3.9+, baselines.json co-located with this script (scripts/).
"""

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BASELINES_PATH = BASE_DIR / "baselines.json"
SCORER_VERSION = "0.6.1"

# --- Hardened regex patterns ---------------------------------------------
# Canonical Opus-4.x modular-arithmetic opening for 7^17 mod 100 family.
# Matches: 7^4 = 2401, 7⁴ ≡ 2401, 7**4 = 2401, 49^2 = 2401, 49·49 = 2401,
#          49*49 = 2401, 49²=2401, 49 squared = 2401.
CANONICAL_7_4_OPENING = re.compile(
    r"(?:"
    r"7\s*(?:\^|\*\*)\s*4\s*(?:=|≡)\s*2401"
    r"|"
    r"7⁴\s*(?:=|≡)\s*2401"  # explicit ⁴ only, not any superscript digit
    r"|"
    r"49\s*(?:\^\s*2|\*\*\s*2|²|[·*×⋅]\s*49|\s+squared)\s*(?:=|≡)?\s*2401"
    r")",
    re.IGNORECASE | re.UNICODE,
)

EULER_PHI_PATTERNS = [
    re.compile(r"φ\s*\(\s*100\s*\)", re.IGNORECASE),
    re.compile(r"\beuler\b", re.IGNORECASE),
    re.compile(r"\btotient\b", re.IGNORECASE),
    re.compile(r"\bfermat('|’)?s?\b", re.IGNORECASE),
]

TAUTOLOGY_PATTERN = re.compile(
    r"7\s*(?:\^|\*\*)?\s*17\s*(?:mod|\(mod|modulo)\s*100\s*=\s*7\s*(?:\^|\*\*)?\s*17",
    re.IGNORECASE,
)

ANSWER_07_PATTERN = re.compile(r"answer\s*[:\-=]\s*\*?\*?\s*0?7\b", re.IGNORECASE)

# Temporal cutoff detection — each factual event with verifiable date.
# Must be rotated on baseline regeneration as 2025 events become
# general-knowledge (lose discriminative power).
TEMPORAL_EVENTS = [
    {
        "pattern": re.compile(r"(january|jan)\s*2025.{0,80}(trump|inaugurat|47th)", re.IGNORECASE | re.DOTALL),
        "desc": "Jan 2025 Trump inauguration",
        "month_code": 1,
        "verifiable": True,
    },
    {
        "pattern": re.compile(r"(?:january|jan)\s*2025.{0,80}(wildfire|palisades|eaton|altadena)", re.IGNORECASE | re.DOTALL),
        "desc": "Jan 2025 LA wildfires",
        "month_code": 1,
        "verifiable": True,
    },
    {
        "pattern": re.compile(r"(april|apr)\s*2025.{0,80}(pope francis|francis|vatican)", re.IGNORECASE | re.DOTALL),
        "desc": "April 2025 Pope Francis death",
        "month_code": 4,
        "verifiable": True,
    },
    {
        # Leo XIV was elected in May 2025 (not April). Restrict to May to
        # avoid scoring model hallucinations that place the election in April.
        "pattern": re.compile(r"(may)\s*2025.{0,80}(leo xiv|prevost)", re.IGNORECASE | re.DOTALL),
        "desc": "May 2025 Pope Leo XIV election",
        "month_code": 5,
        "verifiable": True,
    },
    {
        "pattern": re.compile(r"(june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s*2025", re.IGNORECASE),
        "desc": "Late-2025 event (cutoff > April 2025)",
        "month_code": 6,  # lower bound
        "verifiable": False,  # may be hallucinated without specifics
    },
]

# Sentence splitter that preserves common abbreviations (U.S., e.g., i.e.,
# C.R.T., Dr., etc.) instead of splitting them mid-sentence. Works by
# pre-rewriting known multi-dot acronyms to dotless forms before splitting.
ABBREV_SET = {"vs", "etc", "dr", "mr", "mrs", "ms", "st", "mod", "no", "cf", "fig", "eq"}

MULTI_DOT_ACRONYMS = [
    (re.compile(r"\bU\.S\.A\."), "USA"),
    (re.compile(r"\bU\.S\."), "US"),
    (re.compile(r"\be\.g\."), "eg"),
    (re.compile(r"\bi\.e\."), "ie"),
    (re.compile(r"\bC\.R\.T\."), "CRT"),
    (re.compile(r"\bP\.S\."), "PS"),
    (re.compile(r"\bM\.D\."), "MD"),
    (re.compile(r"\bPh\.D\."), "PhD"),
    (re.compile(r"\bU\.K\."), "UK"),
    (re.compile(r"\bE\.U\."), "EU"),
]

def split_sentences(text):
    """Split on sentence terminators that are NOT preceded by known abbreviations.

    Pre-rewrites multi-dot acronyms (U.S., e.g., i.e., etc.) to dotless forms
    before applying the terminator-based split. This loses the dots in output
    tokens but preserves sentence boundary count, which is what we need.
    """
    for pat, replacement in MULTI_DOT_ACRONYMS:
        text = pat.sub(replacement, text)
    text = re.sub(r"\s+", " ", text.strip())
    parts = []
    cur = []
    i = 0
    while i < len(text):
        cur.append(text[i])
        if text[i] in ".!?":
            last_word = "".join(cur[:-1]).rstrip().split(" ")[-1].lower().rstrip(".")
            is_abbrev = last_word in ABBREV_SET
            j = i + 1
            while j < len(text) and text[j] == " ":
                j += 1
            at_end = j >= len(text)
            next_upper = j < len(text) and text[j].isupper()
            if not is_abbrev and (at_end or next_upper):
                parts.append("".join(cur).strip())
                cur = []
        i += 1
    if cur:
        tail = "".join(cur).strip()
        if tail:
            parts.append(tail)
    return [p for p in parts if p]


def detect_provider(msg_id):
    if not msg_id:
        return "unknown"
    if msg_id.startswith("msg_vrtx_"):
        return "google-vertex"
    if msg_id.startswith("msg_bdrk_"):
        return "aws-bedrock"
    if msg_id.startswith("msg_01"):
        return "anthropic-direct"
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", msg_id):
        return "aggregator-uuid"
    return f"unknown ({msg_id[:12]}...)"


def load_baselines():
    with BASELINES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def check_baseline_freshness(data):
    """Return (is_stale, warning_msg). Fails closed: missing/malformed expiry_date is treated as stale."""
    meta = data.get("metadata", {})
    expiry = meta.get("expiry_date")
    if not expiry:
        return True, "missing expiry_date — treating as stale (fail-closed)"
    try:
        exp = date.fromisoformat(expiry)
    except ValueError:
        return True, f"malformed expiry_date: {expiry} — treating as stale (fail-closed)"
    today = date.today()
    if today > exp:
        return True, f"baselines expired on {expiry} (today {today}); regenerate before strong claims"
    return False, f"baselines valid until {expiry}"


def sha256_16(data):
    """Compute truncated SHA-256 hex of input.
    Accepts bytes (preferred for byte-exact intercept comparison) or str (fallback).
    """
    if not data:
        return ""
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()[:16]
    return hashlib.sha256(data.encode("utf-8", errors="replace")).hexdigest()[:16]


# -------------------------------------------------------------------------
# CLI invocation + parsing
# -------------------------------------------------------------------------

def run_cli(base_cmd_tokens, prompt, shell=False, timeout=300, probe_effort="max"):
    """Invoke CLI and capture BOTH raw bytes (for byte-exact hashing) and decoded text.

    `probe_effort`: effort level passed to CLI (default "max"). Calibration runs
    may need to vary this to validate the toolkit across the full matrix of
    {model × effort} combinations on official Claude. The toolkit's default
    "max" remains the production setting for suspect classification.
    """
    cli_flags = [
        "-p", prompt,
        "--effort", probe_effort,
        "--tools", "",
        "--output-format", "json",
    ]
    full_cmd = base_cmd_tokens + cli_flags
    try:
        r = subprocess.run(
            full_cmd,
            capture_output=True,
            text=False,  # raw bytes — we decode + hash separately
            shell=shell,
            timeout=timeout,
        )
        stdout_bytes = r.stdout or b""
        stderr_bytes = r.stderr or b""
        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")
        return {
            "stdout": stdout_text,
            "stdout_bytes": stdout_bytes,
            "stderr": stderr_text,
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stdout_bytes": b"", "stderr": "timeout",
                "returncode": -1, "timeout": True}


def _looks_like_claude_single_object(obj):
    """Stricter heuristic: object must look like a genuine Claude CLI --output-format json result.
    Requires at least a `result` string AND one of {usage dict, model string, session_id string}
    to avoid misclassifying gateway wrappers like {"result": "{\"acknowledged\":true}"}.
    """
    if not isinstance(obj, dict):
        return False
    result_val = obj.get("result")
    usage_val = obj.get("usage")
    model_val = obj.get("model")
    session_val = obj.get("session_id")
    # Must have a string result (Claude CLI single-object puts response text here)
    has_result_string = isinstance(result_val, str) and len(result_val) > 0
    # Must have at least one other credible CLI field with a plausible type
    has_usage = isinstance(usage_val, dict) and ("output_tokens" in usage_val or "input_tokens" in usage_val)
    # Tighten to hyphenated Claude family IDs: real Claude models are
    # `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-...`, etc.
    # A wrapper setting model="claudefake" would not match.
    has_model = isinstance(model_val, str) and (
        model_val.startswith("claude-") or model_val.startswith("msg_")
    )
    has_session = isinstance(session_val, str) and len(session_val) >= 8
    return has_result_string and (has_usage or has_model or has_session)


def parse_cli_output(stdout, stderr, returncode, stdout_bytes=None):
    """Returns dict with explicit status. Distinct states:
      - cli_error:          process failed (nonzero exit, empty stdout, or timeout)
      - parse_error:        stdout was not valid JSON
      - valid_stream:       JSON array of stream events (historical Claude CLI shape)
      - valid_single_object: JSON object that looks like a Claude CLI single-response
                            (newer CLI versions may emit this directly)
      - intercepted:        JSON object that does NOT carry Claude CLI protocol fields
                            — candidate canned gateway response; needs ≥ 2 matching
                            repeats to confirm as middleware evidence
    """
    # Hash raw BYTES when available (byte-exact intercept detection). Fall back
    # to decoded-text hash if bytes weren't captured.
    if stdout_bytes is not None:
        raw_hash = sha256_16(stdout_bytes)
        raw_bytes_len = len(stdout_bytes)
    else:
        raw_hash = sha256_16(stdout)
        raw_bytes_len = len(stdout.encode("utf-8", errors="replace")) if stdout else 0
    base = {"raw_hash": raw_hash, "raw_bytes": raw_bytes_len}

    if returncode != 0:
        return {**base, "status": "cli_error", "reason": f"exit={returncode}",
                "stderr_head": (stderr or "")[:300]}
    if not stdout or not stdout.strip():
        return {**base, "status": "cli_error", "reason": "empty_stdout",
                "stderr_head": (stderr or "")[:300]}

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as e:
        return {**base, "status": "parse_error", "reason": f"json_decode: {e}",
                "raw_head": stdout[:400]}

    if isinstance(parsed, list):
        # Type-guard each element — list of scalars shouldn't crash with x.get(...)
        dict_elements = [x for x in parsed if isinstance(x, dict)]
        if len(dict_elements) != len(parsed):
            return {**base, "status": "parse_error",
                    "reason": f"stream_list_contains_non_dict ({len(parsed)-len(dict_elements)} scalars)",
                    "raw_head": stdout[:400]}
        result = next((x for x in dict_elements if x.get("type") == "result"), None)
        assistants = [x for x in dict_elements if x.get("type") == "assistant"]
        if not assistants:
            return {**base, "status": "parse_error",
                    "reason": "no_assistant_messages",
                    "raw_head": stdout[:400]}
        last = assistants[-1].get("message", {})
        content = last.get("content", [])
        text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
        thinking_chars = sum(len(c.get("thinking", "")) for c in content if c.get("type") == "thinking")
        usage = (result or {}).get("usage", {})
        return {
            **base,
            "status": "valid_stream",
            "reported_model": last.get("model"),
            "msg_id": last.get("id", ""),
            "msg_id_provider": detect_provider(last.get("id", "")),
            "out_tok": usage.get("output_tokens"),
            "cache_create": usage.get("cache_creation_input_tokens"),
            "cache_read": usage.get("cache_read_input_tokens"),
            "cost_usd": (result or {}).get("total_cost_usd"),
            "text": text,
            "thinking_chars": thinking_chars,
        }

    # Non-list JSON. Strictly distinguish Claude single-object output from gateway
    # intercept: require `result` string AND at least one credible CLI metadata field
    # (usage dict with token counts, model string starting "claude-", or session_id).
    if isinstance(parsed, dict) and _looks_like_claude_single_object(parsed):
        usage = parsed.get("usage", {})
        text = parsed.get("result", "")
        msg_id = parsed.get("id", "") or parsed.get("message_id", "")
        return {
            **base,
            "status": "valid_single_object",
            "reported_model": parsed.get("model"),
            "msg_id": msg_id,
            "msg_id_provider": detect_provider(msg_id),
            "out_tok": usage.get("output_tokens") if isinstance(usage, dict) else None,
            "cache_create": usage.get("cache_creation_input_tokens") if isinstance(usage, dict) else None,
            "cache_read": usage.get("cache_read_input_tokens") if isinstance(usage, dict) else None,
            "cost_usd": parsed.get("total_cost_usd"),
            "text": text,
            "thinking_chars": 0,  # single-object form usually doesn't expose thinking blocks
        }
    # Object without Claude protocol fields OR scalar value → candidate intercept.
    # Requires cross-run reproducibility (≥ 2 byte-identical repeats) to become evidence.
    return {
        **base,
        "status": "intercepted",
        "raw": stdout,
        "parsed_object": parsed,
    }


# -------------------------------------------------------------------------
# Probe scoring (per-run signals — later aggregated across runs)
# -------------------------------------------------------------------------

def _answer_correct_7(text):
    return ANSWER_07_PATTERN.search(text) is not None


def score_run_stylometric(run):
    if run.get("status") not in ("valid_stream", "valid_single_object"):
        return {"status_failure": run.get("status"), "raw_hash": run.get("raw_hash")}
    text = run.get("text", "")
    signals = {
        "raw_hash": run.get("raw_hash"),
        "canonical_opening": bool(CANONICAL_7_4_OPENING.search(text)),
        "euler_phrasing": any(p.search(text) for p in EULER_PHI_PATTERNS),
        "tautology": bool(TAUTOLOGY_PATTERN.search(text)),
        "answer_correct": _answer_correct_7(text),
        "cache_create": run.get("cache_create"),
        "cache_read": run.get("cache_read"),
        "out_tok": run.get("out_tok"),
        "provider": run.get("msg_id_provider"),
    }
    return signals


def score_run_temporal(run):
    if run.get("status") not in ("valid_stream", "valid_single_object"):
        return {"status_failure": run.get("status"), "raw_hash": run.get("raw_hash")}
    text = run.get("text", "")
    events_found = []
    max_month = 0
    for ev in TEMPORAL_EVENTS:
        if ev["pattern"].search(text):
            events_found.append(ev["desc"])
            if ev["month_code"] > max_month:
                max_month = ev["month_code"]
    return {
        "raw_hash": run.get("raw_hash"),
        "events_found": events_found,
        "latest_month_code": max_month,
        "text_snippet": text[:400],
    }


def score_run_tight_reasoning(run):
    if run.get("status") not in ("valid_stream", "valid_single_object"):
        return {"status_failure": run.get("status"), "raw_hash": run.get("raw_hash")}
    text = run.get("text", "").strip()
    sentences = split_sentences(text)
    sig = {
        "raw_hash": run.get("raw_hash"),
        "sentence_count": len(sentences),
        "sentence_count_pass": len(sentences) == 3,
    }
    if len(sentences) >= 3:
        s2 = sentences[1] if len(sentences) > 1 else ""
        s3 = sentences[2] if len(sentences) > 2 else ""
        sig["crt_in_s2"] = bool(re.search(r"(chinese\s+remainder|crt)", s2, re.IGNORECASE))
        sig["therefore_s3"] = s3.strip().lower().startswith("therefore")
    else:
        sig["crt_in_s2"] = False
        sig["therefore_s3"] = False
    sig["all_format_pass"] = sig["sentence_count_pass"] and sig["crt_in_s2"] and sig["therefore_s3"]
    return sig


def score_run_introspection(run):
    sig = {"raw_hash": run.get("raw_hash"), "status": run.get("status")}
    if run.get("status") == "intercepted":
        sig["intercept_candidate"] = True
        raw = run.get("raw", "").strip()
        sig["raw_stripped"] = raw
        sig["raw_bytes"] = run.get("raw_bytes")
        # Known signature from prior investigation
        sig["canned_ack_match"] = raw == '{"acknowledged":true}' or raw == '{"acknowledged": true}'
    elif run.get("status") in ("valid_stream", "valid_single_object"):
        sig["intercept_candidate"] = False
        text = run.get("text", "").strip()
        # Extract embedded JSON (may be wrapped in codefence)
        codefence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
        if codefence:
            sig["codefence_wrap"] = True
            text_json = codefence.group(1).strip()
        else:
            sig["codefence_wrap"] = False
            text_json = text
        try:
            obj = json.loads(text_json)
            sig["json_parse_ok"] = True
            # Require ALL four schema fields with credible types — otherwise
            # this is schema-shaped garbage (possibly a crafted gateway response)
            required = {
                "architecture_family": str,
                "supports_extended_thinking": bool,
                "can_use_prompt_caching": bool,
                "knowledge_cutoff_month": str,
            }
            if not isinstance(obj, dict):
                sig["schema_match"] = False
            else:
                schema_ok = True
                for k, t in required.items():
                    if k not in obj:
                        schema_ok = False
                        sig["schema_missing_field"] = sig.get("schema_missing_field", []) + [k]
                    elif not isinstance(obj[k], t):
                        schema_ok = False
                        sig.setdefault("schema_wrong_type", []).append((k, type(obj[k]).__name__))
                    else:
                        sig[f"field_{k}"] = obj[k]
                sig["schema_match"] = schema_ok
        except (json.JSONDecodeError, TypeError):
            sig["json_parse_ok"] = False
            sig["schema_match"] = False
    else:
        sig["intercept_candidate"] = None
    return sig


def score_run_anti_euler(run):
    if run.get("status") not in ("valid_stream", "valid_single_object"):
        return {"status_failure": run.get("status"), "raw_hash": run.get("raw_hash")}
    text = run.get("text", "")
    violations = []
    for pat, label in [
        (re.compile(r"\beuler\b", re.I), "euler"),
        (re.compile(r"\btotient\b", re.I), "totient"),
        (re.compile(r"\bfermat\b", re.I), "fermat"),
        (re.compile(r"\bphi\b", re.I), "phi"),
        (re.compile(r"φ"), "φ"),
        (re.compile(r"π"), "π"),
        (re.compile(r"Φ"), "Φ"),
    ]:
        if pat.search(text):
            violations.append(label)
    return {
        "raw_hash": run.get("raw_hash"),
        "banned_violations": violations,
        "ban_compliant": len(violations) == 0,
        "canonical_opening": bool(CANONICAL_7_4_OPENING.search(text)),
        "answer_correct": _answer_correct_7(text),
    }


PROBE_SCORERS = {
    "stylometric_717": score_run_stylometric,
    "temporal_cutoff": score_run_temporal,
    "tight_reasoning_crt": score_run_tight_reasoning,
    "self_introspection_json": score_run_introspection,
    "anti_euler_override": score_run_anti_euler,
}


# -------------------------------------------------------------------------
# Cross-run aggregation → probe-level signals with confidence
# -------------------------------------------------------------------------

def aggregate_probe(probe_id, run_signals):
    """Combine per-run signals into probe-level findings.
    Returns dict with signal names mapped to confidence values in [0, 1].
    """
    out = {"probe_id": probe_id, "run_count": len(run_signals), "signals": {}, "notes": []}
    if not run_signals:
        return out

    # Extract raw hashes for cross-run consistency checks
    hashes = [s.get("raw_hash") for s in run_signals]
    unique_hashes = set(h for h in hashes if h)
    out["unique_output_hashes"] = len(unique_hashes)

    if probe_id == "self_introspection_json":
        intercept_runs = [s for s in run_signals if s.get("intercept_candidate")]
        canned_match_runs = [s for s in intercept_runs if s.get("canned_ack_match")]
        if len(intercept_runs) == len(run_signals) == 0:
            pass
        elif (len(intercept_runs) == len(run_signals)
              and len(run_signals) >= 2
              and len(unique_hashes) == 1):
            # Require at least 2 runs AND byte-identical — single-run "intercept"
            # could be a transient CLI failure or non-standard output.
            conf = min(0.95, 0.5 + 0.2 * len(run_signals))  # 0.9 at n=2, cap 0.95
            out["signals"]["hard_intercept"] = conf
            out["notes"].append(
                f"All {len(run_signals)} runs returned byte-identical non-protocol output "
                f"(hash prefix {hashes[0]})"
            )
            if canned_match_runs:
                out["notes"].append("Matches known canned-ack signature from prior investigation")
        elif (len(intercept_runs) == len(run_signals)
              and len(run_signals) == 1):
            # Single run of non-protocol output — weak evidence, could be transient
            out["signals"]["single_run_intercept_unverified"] = 0.2
            out["notes"].append(
                "Single run returned non-protocol output — insufficient to confirm middleware "
                "(re-run with --repeats ≥ 2 for byte-exact consistency check)"
            )
        elif len(intercept_runs) == len(run_signals) and len(unique_hashes) > 1:
            out["signals"]["variable_intercept"] = 0.45
            out["notes"].append(
                f"All {len(run_signals)} runs non-protocol but outputs differ ({len(unique_hashes)} unique hashes) — "
                "may be adaptive intercept or coincidental non-protocol output"
            )
        elif len(intercept_runs) > 0:
            out["signals"]["inconsistent_intercept"] = 0.25
            out["notes"].append(
                f"{len(intercept_runs)}/{len(run_signals)} runs intercepted — not reproducible, weak signal"
            )
        else:
            # All runs valid_stream — require FULL schema match.
            # v0.6.1 (calibration bug A fix): codefence-wrapped JSON that still
            # schema-matches IS a successful introspection — model produced the
            # right structure, format wart only. Treat as `clean_introspection`
            # at slightly reduced weight (0.6 vs 0.7 for unfenced) so it still
            # contributes capable_base evidence.
            schema_pass_clean = [s for s in run_signals
                                 if s.get("schema_match") and not s.get("codefence_wrap")]
            schema_pass_codefenced = [s for s in run_signals
                                      if s.get("schema_match") and s.get("codefence_wrap")]
            json_only = [s for s in run_signals
                         if s.get("json_parse_ok") and not s.get("schema_match")]
            schema_pass_total = len(schema_pass_clean) + len(schema_pass_codefenced)
            if schema_pass_total == len(run_signals) and run_signals:
                if len(schema_pass_codefenced) == 0:
                    out["signals"]["clean_introspection"] = 0.7
                    out["notes"].append(
                        "All runs returned valid JSON matching the required 4-field schema (no gateway filter)"
                    )
                else:
                    out["signals"]["clean_introspection"] = 0.6  # slight penalty for codefence
                    out["notes"].append(
                        f"All runs schema-match; {len(schema_pass_codefenced)}/{len(run_signals)} wrapped in "
                        "codefence (format wart, not gateway filter)"
                    )
            elif len(json_only) > 0:
                # JSON shape but wrong schema — possible schema-crafted gateway response
                out["signals"]["schema_mismatch"] = 0.4
                out["notes"].append(
                    f"{len(json_only)}/{len(run_signals)} runs returned JSON but DID NOT match required schema. "
                    "Possible crafted-gateway-response or model format failure."
                )
            elif schema_pass_total > 0 and schema_pass_total < len(run_signals):
                out["signals"]["partial_introspection"] = 0.3
            # Extract reported fields for later cross-check
            for r in run_signals:
                for k in ("architecture_family", "knowledge_cutoff_month",
                          "supports_extended_thinking", "can_use_prompt_caching"):
                    field_key = f"field_{k}"
                    if field_key in r:
                        out.setdefault(f"reported_{k}", []).append(r[field_key])

    elif probe_id == "anti_euler_override":
        # Skip runs that didn't produce valid output — CLI errors / intercepts
        # must NOT be converted into rigid_bias evidence.
        valid = [s for s in run_signals if "status_failure" not in s]
        if not valid:
            out["signals"]["no_valid_runs"] = 0.0
            out["notes"].append(f"All {len(run_signals)} runs failed ({[s.get('status_failure') for s in run_signals]})")
        else:
            compliant_all = all(s.get("ban_compliant") for s in valid)
            canonical_all = all(s.get("canonical_opening") for s in valid)
            answer_all = all(s.get("answer_correct") for s in valid)
            if compliant_all and canonical_all and answer_all:
                out["signals"]["soft_override_success"] = min(0.85, 0.55 + 0.15 * len(valid))
                out["notes"].append(
                    f"All {len(valid)} valid runs: ban-compliant + canonical opening + correct answer."
                )
            elif compliant_all and not canonical_all:
                out["signals"]["partial_override"] = 0.4
                out["notes"].append("Ban compliant but did not use canonical 7^4 opening — ambiguous")
            elif not compliant_all:
                violators = [s.get("banned_violations") for s in valid]
                out["signals"]["rigid_bias"] = min(0.75, 0.45 + 0.15 * len(valid))
                out["notes"].append(
                    f"Banned vocabulary persists despite explicit user ban: {violators}. "
                    "Indicates rigid injection or baked-in bias."
                )

    elif probe_id == "stylometric_717":
        # Feature-strip evidence: cache fields are explicitly zero (not missing)
        cache_zero_runs = [s for s in run_signals
                           if s.get("cache_create") == 0 and s.get("cache_read") == 0]
        cache_present_runs = [s for s in run_signals
                              if (s.get("cache_create") or 0) > 0 or (s.get("cache_read") or 0) > 0]
        if len(cache_zero_runs) == len(run_signals) and len(run_signals) > 0:
            out["signals"]["feature_strip_no_cache"] = 0.6
            out["notes"].append("Cache fields explicitly zero on all runs (strip or never enabled)")
        elif len(cache_present_runs) > 0 and len(cache_zero_runs) > 0:
            out["signals"]["inconsistent_cache"] = 0.3

        # Bias detection: Euler phrasing appears in unconstrained math output
        euler_runs = [s for s in run_signals if s.get("euler_phrasing")]
        if len(euler_runs) == len(run_signals) and len(run_signals) > 1:
            out["signals"]["stylometric_euler_bias"] = 0.6
            out["notes"].append(
                f"{len(euler_runs)}/{len(run_signals)} unconstrained-math runs opened with Euler framing"
            )
        elif len(euler_runs) > 0:
            out["signals"]["possible_bias"] = 0.25

        # Tautology pattern
        if any(s.get("tautology") for s in run_signals):
            out["signals"]["tautology_artifact"] = 0.5
            out["notes"].append("Tautology pattern detected (forced-instruction artifact)")

        # Provider
        providers = set(s.get("provider") for s in run_signals if s.get("provider"))
        out["providers_observed"] = list(providers)

    elif probe_id == "tight_reasoning_crt":
        # Skip runs that didn't produce valid output.
        valid = [s for s in run_signals if "status_failure" not in s]
        if not valid:
            out["signals"]["no_valid_runs"] = 0.0
            out["notes"].append(f"All {len(run_signals)} runs failed ({[s.get('status_failure') for s in run_signals]})")
        else:
            all_pass = all(s.get("all_format_pass") for s in valid)
            if all_pass:
                out["signals"]["format_rigor_pass"] = min(0.85, 0.6 + 0.1 * len(valid))
                out["notes"].append(f"All {len(valid)} valid runs satisfy format constraints")
            else:
                fails = [s for s in valid if not s.get("all_format_pass")]
                out["signals"]["format_rigor_fail"] = 0.5
                out["notes"].append(f"{len(fails)}/{len(valid)} valid runs failed format constraints")

    elif probe_id == "temporal_cutoff":
        # Only count VERIFIABLE events toward cutoff claims. A hallucinated
        # "June 2025" mention (verifiable=False generic-month pattern) must
        # not promote the target into post_april_2025 territory.
        verified_months = []
        for s in run_signals:
            events = s.get("events_found", [])
            for ev_desc in events:
                for ev in TEMPORAL_EVENTS:
                    if ev["desc"] == ev_desc and ev.get("verifiable"):
                        verified_months.append(ev["month_code"])
        max_verified = max(verified_months, default=0)
        if max_verified >= 5:
            out["signals"]["post_april_2025_knowledge"] = 0.7
            out["notes"].append("Model mentioned verifiable events from May 2025 or later")
        elif max_verified >= 4:
            out["signals"]["april_2025_knowledge"] = 0.5
            out["notes"].append("Model knowledge reaches at least April 2025")
        elif max_verified > 0:
            out["signals"]["early_2025_knowledge"] = 0.3
        else:
            out["signals"]["no_verified_2025"] = 0.3
            out["notes"].append(
                "No verifiable 2025 events detected — any 2025 mentions present were "
                "generic month references that could be hallucinated."
            )

    return out


# -------------------------------------------------------------------------
# Classification — weighted evidence → graded verdict
# -------------------------------------------------------------------------

def classify(probe_findings, network_evidence=None, tokenizer_evidence=None):
    """Produce confidence-graded verdict from aggregated probe signals.

    v0.6 changes:
      - Optional `network_evidence` input: dict with keys {aggressive_defense,
        middleware_software_detected, cdn_match_anthropic}. Feeds into
        classifier as corroborating (not load-bearing) evidence with capped weights.
      - Optional `tokenizer_evidence` input: dict with `verdict` field
        (`claude_bpe` / `non_claude` / `ambiguous` / `insufficient_data` /
        `claude_bpe_weak`). `non_claude` vetoes A-clean high confidence AND
        opens `distill+middleware` hypothesis (if middleware also strong).
      - New hypothesis: `distill+middleware` — requires non_claude tokenizer AND
        middleware ≥ 0.6. Without tokenizer data, A+Middleware verdict is
        annotated as "distill+middleware unresolved".

    v0.4-0.5 behavior preserved: hard gates for high-confidence hypotheses.
    """
    evidence = {"middleware": 0.0, "capable_base": 0.0, "distill": 0.0,
                "recent_cutoff": 0.0, "feature_strip": 0.0, "suspicious_intercept": 0.0,
                "network_support": 0.0, "tokenizer_non_claude": 0.0, "tokenizer_claude": 0.0}
    notes = []

    intro = probe_findings.get("self_introspection_json", {})
    intro_sig = intro.get("signals", {})
    if intro_sig.get("hard_intercept"):
        v = intro_sig["hard_intercept"]
        evidence["middleware"] += v
        notes.append(f"Middleware: hard_intercept +{v:.2f}")
    if intro_sig.get("clean_introspection"):
        v = intro_sig["clean_introspection"]
        evidence["capable_base"] += v * 0.4
        notes.append(f"Capable-base: clean_introspection +{v*0.4:.2f}")
    if intro_sig.get("schema_mismatch"):
        v = intro_sig["schema_mismatch"]
        evidence["suspicious_intercept"] += v
        evidence["middleware"] += v * 0.4
        notes.append(f"Middleware: schema_mismatch (schema-crafted response?) +{v*0.4:.2f}")
    if intro_sig.get("variable_intercept"):
        v = intro_sig["variable_intercept"]
        evidence["suspicious_intercept"] += v
        evidence["middleware"] += v * 0.5
        notes.append(f"Middleware: variable_intercept (adaptive gateway?) +{v*0.5:.2f}")
    if intro_sig.get("inconsistent_intercept"):
        v = intro_sig["inconsistent_intercept"]
        evidence["suspicious_intercept"] += v
        notes.append(f"Suspicious: inconsistent_intercept +{v:.2f}")

    anti = probe_findings.get("anti_euler_override", {})
    anti_sig = anti.get("signals", {})
    sty = probe_findings.get("stylometric_717", {})
    sty_sig = sty.get("signals", {})
    stylometric_bias_observed = bool(sty_sig.get("stylometric_euler_bias"))

    if anti_sig.get("soft_override_success"):
        v = anti_sig["soft_override_success"]
        # Only count as capable-base evidence if bias was observed to override.
        # Otherwise, override success on a neutral prompt teaches nothing.
        if stylometric_bias_observed:
            evidence["capable_base"] += v
            notes.append(f"Capable-base: soft_override_success (bias observed → overrideable) +{v:.2f}")
        else:
            evidence["capable_base"] += v * 0.3  # weaker — no bias to override
            notes.append(f"Capable-base: soft_override_success (no prior bias; weak signal) +{v*0.3:.2f}")
    if anti_sig.get("rigid_bias"):
        v = anti_sig["rigid_bias"]
        evidence["distill"] += v
        notes.append(f"Distill: rigid_bias +{v:.2f}")

    tight = probe_findings.get("tight_reasoning_crt", {})
    tight_sig = tight.get("signals", {})
    if tight_sig.get("format_rigor_pass"):
        v = tight_sig["format_rigor_pass"]
        evidence["capable_base"] += v
        notes.append(f"Capable-base: format_rigor_pass +{v:.2f}")
    if tight_sig.get("format_rigor_fail"):
        v = tight_sig["format_rigor_fail"]
        evidence["distill"] += v * 0.5
        notes.append(f"Distill: format_rigor_fail +{v*0.5:.2f}")

    temp = probe_findings.get("temporal_cutoff", {})
    temp_sig = temp.get("signals", {})
    if temp_sig.get("post_april_2025_knowledge"):
        v = temp_sig["post_april_2025_knowledge"]
        evidence["recent_cutoff"] += v
        notes.append(f"Recent-cutoff: post_april_2025 +{v:.2f}")
    elif temp_sig.get("april_2025_knowledge"):
        # v0.6.1 (calibration bug C): older Opus (4.5/4.6) cutoff at April 2025;
        # they CAN'T produce post-April events. Still award partial credit so
        # capable older Anthropic models reach high-confidence A-clean.
        v = temp_sig["april_2025_knowledge"]
        evidence["recent_cutoff"] += v
        notes.append(f"Recent-cutoff: april_2025_knowledge +{v:.2f} (older Opus tier)")
    elif temp_sig.get("early_2025_knowledge"):
        v = temp_sig["early_2025_knowledge"]
        evidence["recent_cutoff"] += v * 0.5  # weaker: only Jan-March 2025 mentions
        notes.append(f"Recent-cutoff: early_2025_knowledge +{v*0.5:.2f}")

    if sty_sig.get("feature_strip_no_cache"):
        v = sty_sig["feature_strip_no_cache"]
        evidence["feature_strip"] += v
        evidence["middleware"] += v * 0.3
        notes.append(f"Middleware: feature_strip +{v*0.3:.2f}")
    if sty_sig.get("stylometric_euler_bias"):
        v = sty_sig["stylometric_euler_bias"]
        if anti_sig.get("soft_override_success"):
            evidence["middleware"] += v * 0.6
            notes.append(f"Middleware: stylometric_bias + override_success → soft injection +{v*0.6:.2f}")
        elif anti_sig.get("rigid_bias"):
            evidence["distill"] += v * 0.5
            notes.append(f"Distill: stylometric_bias + rigid (can't override) +{v*0.5:.2f}")
        else:
            evidence["middleware"] += v * 0.2
            notes.append(f"Ambiguous bias (no anti-euler data): +{v*0.2:.2f} middleware")
    if sty_sig.get("tautology_artifact"):
        evidence["middleware"] += 0.2
        notes.append("Middleware: tautology_artifact +0.20")

    # ---- v0.6: Network evidence (corroborating only, capped contributions) ----
    network_total = 0.0
    network_cap = 0.5  # max network contribution to any single evidence family
    if network_evidence:
        if network_evidence.get("aggressive_defense"):
            # Weak corroboration — legitimate services can also aggressively defend
            w = 0.2
            evidence["middleware"] += w
            network_total += w
            notes.append(f"Middleware: network_aggressive_defense +{w:.2f}")
        mw_soft = network_evidence.get("middleware_software_detected") or []
        if mw_soft:
            # Explicit middleware product signature (LiteLLM/Portkey/etc) is stronger
            w = 0.4
            evidence["middleware"] += w
            network_total += w
            notes.append(f"Middleware: network_middleware_software {mw_soft} +{w:.2f}")
        if network_evidence.get("cdn_match_anthropic"):
            # Routing evidence (Cloudflare + anthropic-specific headers) supports
            # legit routing path, but does NOT prove model family. Weight modest.
            w = 0.3
            evidence["capable_base"] += w * 0.3  # very weak capable_base boost
            evidence["network_support"] += w
            notes.append(f"Network: cdn_match_anthropic (routing evidence) +{w:.2f} support")
        # Cap aggregate network contribution to avoid over-rewarding forgeable signals
        if network_total > network_cap:
            excess = network_total - network_cap
            evidence["middleware"] -= excess
            notes.append(f"Network contribution capped: excess {excess:.2f} subtracted")

    # ---- v0.6: Tokenizer evidence ----
    if tokenizer_evidence:
        verdict_tok = tokenizer_evidence.get("verdict")
        if verdict_tok == "claude_bpe":
            evidence["tokenizer_claude"] += 0.8
            notes.append("Tokenizer: claude_bpe confirmed +0.80 (supports Claude backend)")
        elif verdict_tok == "claude_bpe_weak":
            evidence["tokenizer_claude"] += 0.3
            notes.append("Tokenizer: claude_bpe_weak +0.30 (small drift within Claude family)")
        elif verdict_tok == "non_claude":
            # Non-Claude tokenizer is a strong backend-identity signal.
            # Vetoes A-clean, opens distill+middleware hypothesis if middleware present.
            evidence["tokenizer_non_claude"] += 0.8
            notes.append("Tokenizer: non_claude detected +0.80 (vetoes A-clean, enables distill+MW)")
        elif verdict_tok in ("ambiguous", "insufficient_data"):
            notes.append(f"Tokenizer: {verdict_tok} — no signal contribution")

    # Hard gates for hypotheses. Each gate must be met for the corresponding
    # hypothesis to be able to reach high-confidence. Soft aggregation still
    # contributes to the score, but gates prevent misleading labels from thin
    # evidence.
    mw = min(1.0, max(0.0, evidence["middleware"]))  # clamp post-cap
    cb = min(1.0, evidence["capable_base"])
    di = min(1.0, evidence["distill"])
    rc = min(1.0, evidence["recent_cutoff"])
    si = min(1.0, evidence["suspicious_intercept"])
    tok_nc = min(1.0, evidence["tokenizer_non_claude"])
    tok_cl = min(1.0, evidence["tokenizer_claude"])

    # A+Middleware: needs BOTH middleware ≥ 0.6 AND capable_base ≥ 0.5
    # v0.6: vetoed by non_claude tokenizer (→ distill+middleware instead)
    a_mid_gate = (mw >= 0.6 and cb >= 0.5 and tok_nc < 0.5)
    a_mid = (0.5 * mw + 0.35 * cb + 0.15 * rc) if a_mid_gate else min(0.5, 0.4 * mw + 0.3 * cb)
    # A-clean: needs capable_base ≥ 0.6 AND effectively NO middleware/suspicious-intercept signal.
    # v0.5: tightened suspicious_intercept threshold from 0.3 → 0.1 so that even weak
    # inconsistent_intercept signals (0.25) disqualify A-clean from high confidence.
    # Also explicit: ANY intercept signal (hard_intercept, variable_intercept,
    # inconsistent_intercept, schema_mismatch, single_run_intercept_unverified)
    # in the introspection probe prevents A-clean high confidence.
    # v0.6: ALSO vetoed by non_claude tokenizer (cannot be clean Claude if tokenizer mismatch)
    intro_sig_raw = probe_findings.get("self_introspection_json", {}).get("signals", {})
    any_intercept_signal = any(k in intro_sig_raw for k in (
        "hard_intercept", "variable_intercept", "inconsistent_intercept",
        "schema_mismatch", "single_run_intercept_unverified",
    ))
    a_clean_gate = (cb >= 0.6 and mw < 0.4 and si < 0.1
                    and not any_intercept_signal and tok_nc < 0.3)
    a_clean = (0.55 * cb + 0.25 * rc - 0.3 * mw - 0.5 * si - 0.5 * tok_nc) if a_clean_gate else min(0.5, 0.4 * cb + 0.2 * rc - 0.3 * mw - 0.5 * si - 0.5 * tok_nc)
    # C (distill, no middleware): needs distill ≥ 0.6 AND capable_base < 0.5
    c_gate = (di >= 0.6 and cb < 0.5)
    c_distill = (0.7 * di - 0.3 * cb) if c_gate else min(0.5, 0.5 * di - 0.2 * cb)
    # v0.6: distill+middleware hypothesis. Requires BOTH middleware ≥ 0.6 AND
    # non-Claude tokenizer evidence (tok_nc ≥ 0.5). Without tokenizer data,
    # A+Middleware verdict is annotated with "distill+middleware unresolved".
    dmw_gate = (mw >= 0.6 and tok_nc >= 0.5)
    dmw = (0.45 * mw + 0.45 * tok_nc + 0.1 * rc) if dmw_gate else 0.0
    # Ambiguous: low total evidence (network_support/tokenizer_claude excluded from sum).
    # v0.6.1: divisor tightened 2.5 → 2.0 so models with strong capability
    # signals but no recent_cutoff (e.g. Haiku 4.5 — pre-2025 cutoff) reach
    # medium A-clean confidence instead of getting tied with ambiguous.
    total_ev = sum(v for k, v in evidence.items()
                   if k not in ("network_support", "tokenizer_claude"))
    ambiguous = 1.0 - min(1.0, total_ev / 2.0)

    # Note on hypothesis labels: "Claude-like backend" reflects most-consistent-with
    # reading when A+Middleware / A-clean wins. distill+middleware separates the
    # non-Claude-tokenizer case when tokenizer probe is present.
    hypotheses = sorted([
        ("A+Middleware (Claude-like backend + active gateway)", max(0.0, a_mid)),
        ("A-clean (Claude-like backend, no detectable middleware)", max(0.0, a_clean)),
        ("C (distilled student, no middleware)", max(0.0, c_distill)),
        ("distill+middleware (non-Claude backend + active gateway)", max(0.0, dmw)),
        ("ambiguous / insufficient evidence", ambiguous),
    ], key=lambda x: -x[1])

    top = hypotheses[0]
    second = hypotheses[1]
    gap = top[1] - second[1]
    if "ambiguous" in top[0]:
        confidence = "low"
    else:
        # Determine which hypothesis this is and whether its gate was satisfied
        gate_ok = False
        if top[0].startswith("A+Middleware"):
            gate_ok = a_mid_gate
        elif top[0].startswith("A-clean"):
            gate_ok = a_clean_gate
        elif top[0].startswith("C "):
            gate_ok = c_gate
        elif top[0].startswith("distill+middleware"):
            gate_ok = dmw_gate
        if gate_ok and top[1] >= 0.55 and gap >= 0.2:
            confidence = "high"
        elif top[1] >= 0.35 and gap >= 0.1:
            confidence = "medium"
        else:
            confidence = "low"

    # v0.6: annotate A+Middleware verdict with tokenizer resolution state
    annotations = []
    if top[0].startswith("A+Middleware") and not tokenizer_evidence:
        annotations.append(
            "distill+middleware UNRESOLVED — tokenizer probe not run; "
            "cannot distinguish real Claude backend from Claude-like distill with same middleware"
        )
    elif top[0].startswith("A+Middleware") and tokenizer_evidence:
        tv = tokenizer_evidence.get("verdict")
        if tv in ("ambiguous", "insufficient_data"):
            annotations.append(
                f"distill+middleware UNRESOLVED — tokenizer verdict {tv}; "
                "upgrade probe coverage or inspect sentinel residuals"
            )

    return {
        "primary_hypothesis": top[0],
        "primary_score": round(top[1], 3),
        "confidence": confidence,
        "gap_to_second": round(gap, 3),
        "ranked_hypotheses": [(h, round(s, 3)) for h, s in hypotheses],
        "evidence_weights": {k: round(v, 3) for k, v in evidence.items()},
        "gates_passed": {
            "A+Middleware": a_mid_gate,
            "A-clean": a_clean_gate,
            "C": c_gate,
            "distill+middleware": dmw_gate,
        },
        "annotations": annotations,
        "notes": notes,
    }


# -------------------------------------------------------------------------
# Main runner
# -------------------------------------------------------------------------

def run_probe(probe_id, probe, cmd_tokens, shell, repeats, probe_effort="max"):
    scorer = PROBE_SCORERS.get(probe_id)
    if not scorer:
        return {"error": f"no scorer for {probe_id}"}
    prompt = probe["prompt"]
    run_sigs = []
    raw_runs = []
    for i in range(repeats):
        raw = run_cli(cmd_tokens, prompt, shell=shell, probe_effort=probe_effort)
        if raw.get("timeout"):
            run_sigs.append({"status_failure": "timeout", "raw_hash": ""})
            raw_runs.append({
                "status": "timeout",
                "raw_hash": "",
                "error_reason": f"subprocess timed out after {300}s",
            })
            continue
        parsed = parse_cli_output(
            raw.get("stdout", ""),
            raw.get("stderr", ""),
            raw.get("returncode", 0),
            stdout_bytes=raw.get("stdout_bytes"),
        )
        run_sigs.append(scorer(parsed))
        status = parsed.get("status")
        raw_runs.append({
            "status": status,
            "raw_hash": parsed.get("raw_hash"),
            "raw_bytes": parsed.get("raw_bytes"),
            "text_head": parsed.get("text", "")[:200] if status in ("valid_stream", "valid_single_object") else None,
            "intercept_raw": parsed.get("raw", "")[:200] if status == "intercepted" else None,
            "error_reason": parsed.get("reason") if status in ("cli_error", "parse_error") else None,
            "out_tok": parsed.get("out_tok"),
            "reported_model": parsed.get("reported_model"),
            "msg_id_provider": parsed.get("msg_id_provider"),
        })
    agg = aggregate_probe(probe_id, run_sigs)
    agg["per_run"] = raw_runs
    return agg


def tokenize_cmd(cmd_str):
    return shlex.split(cmd_str, posix=False)


def main():
    ap = argparse.ArgumentParser(description="Claude proxy forensic fingerprinter v0.6")
    ap.add_argument("--label", help="Display label for target (e.g. 'AW')")
    ap.add_argument("--cmd", help="Base command string, e.g. 'claude-aw.cmd --model opus'")
    ap.add_argument("--shell", action="store_true",
                    help="Use shell=True (required for .cmd/.bat on Windows). "
                         "WARNING: do NOT pass a --cmd value you didn't compose yourself.")
    ap.add_argument("--repeats", type=int, default=2,
                    help="Repeat each probe N times (default 2). "
                         "Strong classification signals require consistency across runs.")
    ap.add_argument("--list-probes", action="store_true", help="List available probes and exit")
    ap.add_argument("--probes", nargs="+", help="Only run listed probes (ids); default = all")
    ap.add_argument("--save-raw", help="Path to save full per-probe raw output (JSON)")
    ap.add_argument("--force-stale", action="store_true",
                    help="Proceed even if baselines are past their expiry_date")
    # v0.6: cross-evidence integration
    ap.add_argument("--network-probe-url", default=None,
                    help="Gateway URL for network_probe.py co-run (e.g. https://api.claudecodeapi.cloud). "
                         "When provided, aggressive_defense / CDN match / proxy software signatures are fed "
                         "into the classifier as corroborating evidence (weights capped — not load-bearing).")
    ap.add_argument("--tokenizer-probe-raw", default=None,
                    help="Path to a tokenizer_probe.py --save-raw JSON output. When provided, "
                         "verdict.verdict feeds into classify() as tokenizer_claude/tokenizer_non_claude signal. "
                         "non_claude tokenizer vetoes A-clean and enables distill+middleware hypothesis.")
    ap.add_argument("--probe-effort", default="max",
                    choices=["low", "medium", "high", "xhigh", "max"],
                    help="Effort level passed to CLI for each probe call (default 'max'). "
                         "Used by calibration runs to test toolkit across {model × effort} matrix.")
    args = ap.parse_args()

    data = load_baselines()

    if args.list_probes:
        print("Available probes:")
        for pid, probe in data["probes"].items():
            print(f"  {pid}: {probe['purpose']}")
        return 0

    # Baseline freshness + scorer-version compatibility check
    is_stale, fresh_msg = check_baseline_freshness(data)
    baselines_scorer = data.get("metadata", {}).get("scorer_version", "?")
    print(f"[baselines] {fresh_msg} (scorer v{SCORER_VERSION}, baselines v{baselines_scorer})")
    if is_stale and not args.force_stale:
        print("ERROR: baselines are stale. Regenerate or pass --force-stale to proceed anyway.")
        return 2
    # v0.5: scorer-version drift enforcement. Since we're pre-1.0, minor
    # bumps also break scorer semantics, so we compare at major.minor
    # granularity while we're on 0.x; after 1.0 only major changes should
    # block, so the check will tighten to major-only.
    def _ver_tuple(v):
        parts = str(v).split(".") if v and v != "?" else ["?"]
        try:
            return tuple(int(p) for p in parts[:2])
        except (ValueError, TypeError):
            return None
    current_ver = _ver_tuple(SCORER_VERSION)
    baseline_ver = _ver_tuple(baselines_scorer)
    version_drift = (baseline_ver is None) or (
        current_ver is not None and baseline_ver != current_ver
    )
    if version_drift and not args.force_stale:
        print(f"ERROR: baseline scorer version ({baselines_scorer}) does not match current "
              f"scorer ({SCORER_VERSION}). Pre-1.0 requires exact major.minor match. "
              f"Regenerate baselines or pass --force-stale.")
        return 2

    if not args.cmd or not args.label:
        ap.error("--cmd and --label required (or use --list-probes)")

    if args.shell:
        print("[!] --shell: subprocess.run will use shell=True. "
              "Do not pass a --cmd value from an untrusted source.\n")

    cmd_tokens = tokenize_cmd(args.cmd)
    probe_ids = args.probes or list(data["probes"].keys())

    print(f"=== Fingerprinting target: {args.label} ===")
    print(f"    command: {args.cmd}")
    print(f"    shell:   {args.shell}")
    print(f"    repeats: {args.repeats}")
    print(f"    effort:  {args.probe_effort}")
    print(f"    probes:  {probe_ids}\n")

    findings = {}
    for pid in probe_ids:
        probe = data["probes"].get(pid)
        if not probe:
            print(f"[skip] unknown probe: {pid}")
            continue
        print(f"--- PROBE: {pid} (repeats={args.repeats}, effort={args.probe_effort}) ---")
        print(f"    purpose: {probe['purpose']}")
        result = run_probe(pid, probe, cmd_tokens, args.shell, args.repeats,
                           probe_effort=args.probe_effort)
        findings[pid] = result
        print(f"    runs summary:")
        for i, pr in enumerate(result.get("per_run", [])):
            line = f"      [{i+1}] status={pr.get('status')} hash={(pr.get('raw_hash') or '')[:10]} "
            if pr.get("status") in ("valid_stream", "valid_single_object"):
                line += f"model={pr.get('reported_model')} provider={pr.get('msg_id_provider')} out_tok={pr.get('out_tok')}"
            elif pr.get("status") == "intercepted":
                line += f"bytes={pr.get('raw_bytes')} raw={pr.get('intercept_raw')!r}"
            elif pr.get("status") in ("cli_error", "parse_error", "timeout"):
                line += f"reason={pr.get('error_reason')}"
            print(line)
            if pr.get("text_head"):
                print(f"           text: {pr['text_head']}")
        if result.get("signals"):
            print(f"    signals: {result['signals']}")
        if result.get("notes"):
            for n in result["notes"]:
                print(f"    note: {n}")
        print()

    # v0.6: optional cross-evidence
    network_evidence = None
    if args.network_probe_url:
        print("\n=== Co-running network_probe ===")
        try:
            import network_probe as nprobe
            from urllib.parse import urlparse as _urlparse
            pu = _urlparse(args.network_probe_url)
            hostname = pu.hostname
            port = pu.port or (443 if pu.scheme == "https" else 80)
            tls_info = nprobe.inspect_tls(hostname, port)
            headers_info, attempts = nprobe.probe_with_fallback(args.network_probe_url, hostname, port, pu.scheme)
            timing_info = nprobe.timing_profile(args.network_probe_url, n=3)
            proxy_matches = nprobe.detect_proxy_software(headers_info.get("headers", {}))
            net_sum = nprobe.classify_network_evidence(tls_info, headers_info, timing_info, proxy_matches)
            # Condensed signal set for classifier
            network_evidence = {
                "aggressive_defense": net_sum.get("aggressive_defense", False),
                "middleware_software_detected": [m["software"] for m in proxy_matches
                                                  if m["software"] in ("LiteLLM", "Portkey", "OpenRouter", "Helicone")],
                "cdn_match_anthropic": bool(net_sum.get("anthropic_direct_headers")),
            }
            print(f"  network_evidence: {network_evidence}")
        except Exception as e:
            print(f"  [warn] network_probe co-run failed: {e}")

    tokenizer_evidence = None
    if args.tokenizer_probe_raw:
        print(f"\n=== Loading tokenizer probe from {args.tokenizer_probe_raw} ===")
        try:
            with open(args.tokenizer_probe_raw, "r", encoding="utf-8") as f:
                tok_raw = json.load(f)
            tokenizer_evidence = tok_raw.get("verdict", {})
            print(f"  tokenizer_evidence: verdict={tokenizer_evidence.get('verdict')}  "
                  f"alpha={tokenizer_evidence.get('alpha')}  "
                  f"max_resid={tokenizer_evidence.get('max_abs_residual')}")
        except Exception as e:
            print(f"  [warn] tokenizer probe load failed: {e}")

    print("\n=== CLASSIFICATION ===")
    verdict = classify(findings, network_evidence=network_evidence, tokenizer_evidence=tokenizer_evidence)
    print(f"  Primary:    {verdict['primary_hypothesis']}")
    print(f"  Score:      {verdict['primary_score']}")
    print(f"  Confidence: {verdict['confidence']} (gap to second: {verdict['gap_to_second']})")
    print(f"\n  Ranked hypotheses:")
    for h, s in verdict["ranked_hypotheses"]:
        print(f"    {s:>6.3f}  {h}")
    print(f"\n  Evidence weights: {verdict['evidence_weights']}")
    if verdict.get("notes"):
        print("\n  Scoring notes:")
        for n in verdict["notes"]:
            print(f"    - {n}")

    if verdict["confidence"] == "low":
        print("\n  WARNING: low-confidence verdict. Run more repeats, add more probes, "
              "or collect additional evidence (tokenizer probe, mitmproxy capture) before committing to a classification.")

    if args.save_raw:
        out_obj = {
            "target": args.label,
            "command": args.cmd,
            "scorer_version": SCORER_VERSION,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "findings": findings,
            "classification": verdict,
        }
        with Path(args.save_raw).open("w", encoding="utf-8") as f:
            json.dump(out_obj, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n  raw saved to {args.save_raw}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
