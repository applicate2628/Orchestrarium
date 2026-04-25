#!/usr/bin/env python3
"""Re-run calibration only on combos affected by v0.6.1 fixes:
- Opus 4.5/4.6: april_2025_knowledge → recent_cutoff (Bug C); codefenced
  schema → clean_introspection at 0.6 (Bug A on 4.6)
- Haiku 4.5: prior run cli_error from rate limit, retry now that limit reset

Sonnet 4.6 / Opus 4.7 already passed; their classifier paths weren't changed
by the fixes (no codefence on those, no april-only cutoff).
"""
import json, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
CALIB_DIR = ROOT / "calibration"
CALIB_DIR.mkdir(exist_ok=True)

# Only the affected combos
MATRIX = [
    ("claude-opus-4-5",          "low",    "primary"),
    ("claude-opus-4-5",          "medium", "explore"),
    ("claude-opus-4-5",          "high",   "explore"),
    ("claude-opus-4-5",          "xhigh",  "explore"),
    ("claude-opus-4-5",          "max",    "primary"),
    ("claude-opus-4-6",          "low",    "primary"),
    ("claude-opus-4-6",          "medium", "explore"),
    ("claude-opus-4-6",          "high",   "explore"),
    ("claude-opus-4-6",          "xhigh",  "explore"),
    ("claude-opus-4-6",          "max",    "primary"),
    ("claude-haiku-4-5-20251001", "low",    "primary"),
    ("claude-haiku-4-5-20251001", "medium", "primary"),
    ("claude-haiku-4-5-20251001", "high",   "explore"),
    ("claude-haiku-4-5-20251001", "xhigh",  "degraded"),
    ("claude-haiku-4-5-20251001", "max",    "degraded"),
]


def run_one(model, effort, lane, idx, total):
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
    print(f"\n[{idx}/{total}] {label} (lane={lane})", flush=True)
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT", flush=True)
        return {"label": label, "model": model, "effort": effort, "lane_type": lane, "error": "timeout"}
    elapsed = time.monotonic() - t0
    out = r.stdout or ""
    verdict = score = conf = ""
    for ln in out.splitlines():
        if "Primary:" in ln: verdict = ln.strip()
        elif "Score:" in ln: score = ln.strip()
        elif "Confidence:" in ln: conf = ln.strip()
    print(f"    elapsed: {elapsed:.0f}s  exit: {r.returncode}", flush=True)
    if verdict: print(f"    {verdict}", flush=True)
    if score: print(f"    {score}", flush=True)
    if conf: print(f"    {conf}", flush=True)
    return {
        "label": label, "model": model, "effort": effort, "lane_type": lane,
        "elapsed_s": round(elapsed, 1), "returncode": r.returncode,
        "raw_path": str(raw_path),
        "verdict_line": verdict, "score_line": score, "confidence_line": conf,
        "stderr_tail": (r.stderr or "")[-300:],
    }


def main():
    print(f"=== Calibration RERUN (v0.6.1 fixes) ===")
    print(f"    timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"    combinations: {len(MATRIX)} (affected only)")
    results = []
    t0 = time.monotonic()
    for i, (model, effort, lane) in enumerate(MATRIX, 1):
        r = run_one(model, effort, lane, i, len(MATRIX))
        results.append(r)
        with (CALIB_DIR / "_calibration_log_v061.json").open("w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "matrix_size": len(MATRIX),
                "completed": len(results),
                "elapsed_total_s": round(time.monotonic() - t0, 1),
                "results": results,
            }, f, indent=2, ensure_ascii=False)
    print(f"\n=== Done. {time.monotonic() - t0:.0f}s total ===")


if __name__ == "__main__":
    sys.exit(main())
