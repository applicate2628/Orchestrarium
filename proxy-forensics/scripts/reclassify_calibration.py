#!/usr/bin/env python3
"""Offline reclassification of saved calibration JSONs using v0.6.1 classifier.

Replays per_run text_head data through current scorer + aggregator + classify(),
updates the saved JSON's classification + signals fields. No API calls.

Useful when classifier semantics change (e.g. v0.6.1 codefence handling, april
cutoff weight, ambiguous divisor) and we want to re-evaluate existing data
without re-running probes.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fingerprint as fp


def reclassify_one(path):
    """Reload JSON, re-score per_run, re-aggregate, re-classify, save."""
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)

    findings = d.get("findings", {})
    new_findings = {}

    for probe_id, probe in findings.items():
        scorer = fp.PROBE_SCORERS.get(probe_id)
        if not scorer:
            new_findings[probe_id] = probe
            continue

        # Build run dicts compatible with scorer (it expects status, raw_hash, text, etc.)
        run_sigs = []
        for pr in probe.get("per_run", []):
            status = pr.get("status")
            text = pr.get("text_head", "") or pr.get("intercept_raw", "") or ""
            run = {
                "status": status,
                "raw_hash": pr.get("raw_hash", ""),
                "text": text,
                "out_tok": pr.get("out_tok"),
                "msg_id": "",  # not preserved in per_run; ok for re-scoring
                "msg_id_provider": pr.get("msg_id_provider"),
                "raw": text if status == "intercepted" else "",
                "raw_bytes": pr.get("raw_bytes", 0),
                # cache fields not in per_run; default to None so feature_strip detection
                # uses the original aggregated signals (preserved below for stylometric_717)
                "cache_create": None,
                "cache_read": None,
            }
            run_sigs.append(scorer(run))

        # For stylometric_717, preserve cache_create/read from prior aggregation
        # since per_run doesn't carry them and feature_strip_no_cache depends on them
        if probe_id == "stylometric_717":
            prior_sig = probe.get("signals", {})
            agg = fp.aggregate_probe(probe_id, run_sigs)
            # Retain feature_strip_no_cache from prior aggregation if it was set
            if "feature_strip_no_cache" in prior_sig and "feature_strip_no_cache" not in agg["signals"]:
                agg["signals"]["feature_strip_no_cache"] = prior_sig["feature_strip_no_cache"]
        else:
            agg = fp.aggregate_probe(probe_id, run_sigs)

        # Preserve per_run for traceability
        agg["per_run"] = probe.get("per_run", [])
        new_findings[probe_id] = agg

    # Re-classify
    network_evidence = d.get("network_evidence")
    tokenizer_evidence = d.get("tokenizer_evidence")
    new_verdict = fp.classify(new_findings,
                              network_evidence=network_evidence,
                              tokenizer_evidence=tokenizer_evidence)

    d["findings"] = new_findings
    d["classification"] = new_verdict
    d["scorer_version"] = fp.SCORER_VERSION
    d["reclassified"] = True

    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False, default=str)

    return new_verdict


def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
    calib_dir = project_root / "calibration"
    json_files = sorted(calib_dir.glob("calibration-*.json"))
    print(f"Reclassifying {len(json_files)} calibration JSONs...")
    print()
    print(f"{'label':<48} {'verdict':<60} {'score':<7} {'conf':<35}")
    for path in json_files:
        v = reclassify_one(path)
        primary = v.get("primary_hypothesis", "")
        score = v.get("primary_score", "")
        conf = v.get("confidence", "")
        gap = v.get("gap_to_second", "")
        label = path.stem
        print(f"{label:<48} {primary[:60]:<60} {str(score):<7} {conf} (gap={gap})")


if __name__ == "__main__":
    sys.exit(main())
