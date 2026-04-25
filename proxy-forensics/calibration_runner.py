#!/usr/bin/env python3
"""Calibration runner: full {model × effort} matrix across all available
official Claude models. Captures fingerprint.py verdict for each combo,
aggregates into a calibration report.

Per codex round-13 + calibration-scope reviews:
- Run 5 probes × 2 repeats per combo
- Record requested_effort (effective_effort not directly exposed in JSON)
- Mark Sonnet/Haiku xhigh/max as degradation checks (CLI silently caps)

Expected: every (real-Anthropic-direct, any-effort) combination produces
A-clean verdict (high or medium confidence). Anything else is a calibration
issue requiring fix BEFORE stamping v0.6 as multi-model stable.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CALIB_DIR = ROOT / "calibration"
CALIB_DIR.mkdir(exist_ok=True)

# (model_id, effort, lane_type)
# lane_type: "primary" (canonical default-supported), "explore" (less common combo),
#            "degraded" (CLI silently degrades to lower effort)
MATRIX = [
    # Opus 4.5 — supports all efforts including max
    ("claude-opus-4-5",          "low",    "primary"),
    ("claude-opus-4-5",          "medium", "explore"),
    ("claude-opus-4-5",          "high",   "explore"),
    ("claude-opus-4-5",          "xhigh",  "explore"),
    ("claude-opus-4-5",          "max",    "primary"),
    # Opus 4.6 — supports all
    ("claude-opus-4-6",          "low",    "primary"),
    ("claude-opus-4-6",          "medium", "explore"),
    ("claude-opus-4-6",          "high",   "explore"),
    ("claude-opus-4-6",          "xhigh",  "explore"),
    ("claude-opus-4-6",          "max",    "primary"),
    # Opus 4.7 — current frontier; max already validated, include for completeness
    ("claude-opus-4-7",          "low",    "primary"),
    ("claude-opus-4-7",          "medium", "explore"),
    ("claude-opus-4-7",          "high",   "explore"),
    ("claude-opus-4-7",          "xhigh",  "explore"),
    ("claude-opus-4-7",          "max",    "primary"),
    # Sonnet 4.6 — max/xhigh likely cap to high
    ("claude-sonnet-4-6",        "low",    "primary"),
    ("claude-sonnet-4-6",        "medium", "explore"),
    ("claude-sonnet-4-6",        "high",   "primary"),
    ("claude-sonnet-4-6",        "xhigh",  "degraded"),
    ("claude-sonnet-4-6",        "max",    "degraded"),
    # Haiku 4.5 — typically caps higher efforts; only low/medium are reliable
    ("claude-haiku-4-5-20251001", "low",    "primary"),
    ("claude-haiku-4-5-20251001", "medium", "primary"),
    ("claude-haiku-4-5-20251001", "high",   "explore"),
    ("claude-haiku-4-5-20251001", "xhigh",  "degraded"),
    ("claude-haiku-4-5-20251001", "max",    "degraded"),
]


def run_one_calibration(model, effort, lane_type, idx, total):
    label = f"calibration-{model.replace('claude-','').replace('-20251001','')}-{effort}"
    raw_path = CALIB_DIR / f"{label}.json"
    cmd = [
        "python", str(ROOT / "fingerprint.py"),
        "--label", label,
        "--cmd", f"claude --model {model}",
        "--repeats", "2",
        "--probe-effort", effort,
        "--save-raw", str(raw_path),
    ]
    print(f"\n[{idx}/{total}] {label} (lane={lane_type})", flush=True)
    print(f"    cmd: {' '.join(cmd)}", flush=True)
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            cmd,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=900,  # 15 min cap per combo
        )
        elapsed = time.monotonic() - t0
        # Extract verdict line for quick visibility
        out = r.stdout or ""
        verdict_line = ""
        score_line = ""
        confidence_line = ""
        for ln in out.splitlines():
            if "Primary:" in ln:
                verdict_line = ln.strip()
            elif "Score:" in ln:
                score_line = ln.strip()
            elif "Confidence:" in ln:
                confidence_line = ln.strip()
        print(f"    elapsed: {elapsed:.0f}s   exit: {r.returncode}", flush=True)
        if verdict_line:
            print(f"    {verdict_line}", flush=True)
            print(f"    {score_line}", flush=True)
            print(f"    {confidence_line}", flush=True)
        return {
            "label": label,
            "model": model,
            "effort": effort,
            "lane_type": lane_type,
            "elapsed_s": round(elapsed, 1),
            "returncode": r.returncode,
            "raw_path": str(raw_path),
            "verdict_line": verdict_line,
            "score_line": score_line,
            "confidence_line": confidence_line,
            "stderr_tail": (r.stderr or "")[-300:],
        }
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT after 15 min", flush=True)
        return {
            "label": label,
            "model": model,
            "effort": effort,
            "lane_type": lane_type,
            "error": "timeout",
        }


def main():
    print(f"=== Calibration matrix run ===")
    print(f"    timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"    combinations: {len(MATRIX)}")
    print(f"    output dir:   {CALIB_DIR}")
    results = []
    t0 = time.monotonic()
    for i, (model, effort, lane) in enumerate(MATRIX, 1):
        result = run_one_calibration(model, effort, lane, i, len(MATRIX))
        results.append(result)
        # Save partial after each (resilient to interruption)
        with (CALIB_DIR / "_calibration_log.json").open("w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "matrix_size": len(MATRIX),
                "completed": len(results),
                "elapsed_total_s": round(time.monotonic() - t0, 1),
                "results": results,
            }, f, indent=2, ensure_ascii=False)
    total_elapsed = time.monotonic() - t0
    print(f"\n=== Calibration complete ===")
    print(f"    total elapsed: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"    log saved to: {CALIB_DIR}/_calibration_log.json")


if __name__ == "__main__":
    sys.exit(main())
