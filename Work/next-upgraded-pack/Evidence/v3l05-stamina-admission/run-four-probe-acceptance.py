#!/usr/bin/env python3
"""End-to-end four-probe acceptance for the V3L05 stamina family.

Runs bundle-shape + the four probes across the matched triplet and asserts every
expected outcome. Exit 0 iff all assertions hold.

Usage: python run-four-probe-acceptance.py <benchmarks-root>
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAKE = HERE / "generate" / "make_probes.py"


def roots(bench: Path):
    return {k: bench / "Scenarios-v3" / f"V3L05-stamina-migration-{k}" for k in "sml"}


def verifier(root: Path) -> Path:
    return root / "verifiers" / "check_stamina_migration.py"


def run(cmd) -> tuple[int, str]:
    p = subprocess.run([sys.executable, *map(str, cmd)], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout


def score(root: Path, candidate: Path, metrics: Path) -> dict:
    run([verifier(root), "--candidate-root", candidate, "--metrics-out", metrics])
    return json.loads(metrics.read_text())


def make(root: Path, out: Path, mode: str, fraction: float | None = None) -> None:
    cmd = [MAKE, "--root", root, "--out", out, "--mode", mode]
    if fraction is not None:
        cmd += ["--fraction", str(fraction)]
    run(cmd)


def slope(root: Path, s: Path, m: Path, l: Path) -> dict:
    rc, out = run([root / "verifiers" / "compute_stamina_slope.py", "--short", s, "--medium", m, "--long", l])
    return json.loads(out)


def main() -> int:
    bench = Path(sys.argv[1]).resolve()
    R = roots(bench)
    checks: list[tuple[str, bool]] = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # bundle shape (all three)
        for k in "sml":
            rc, _ = run([verifier(R[k]), "--bundle-shape-only"])
            check(f"bundle-shape[{k}] PASS", rc == 0)

        # PROBE 1 — reference PASSES on all three
        for k in "sml":
            cand = tmp / f"ref-{k}" / "candidate"
            make(R[k], cand, "reference")
            m = score(R[k], cand, tmp / f"ref-{k}.json")
            check(f"probe1 reference[{k}] PASS@1.0", m["verdict"] == "PASS" and m["breadth_fraction"] == 1.0)

        # PROBE 2 — vacuous FAILS (starter + keyword-stuffed), long
        m = score(R["l"], R["l"] / "candidate", tmp / "starter.json")
        check("probe2a starter FAIL@0.0", m["verdict"] == "FAIL" and m["breadth_fraction"] == 0.0)
        cand = tmp / "kw" / "candidate"; make(R["l"], cand, "keyword_stuffed")
        m = score(R["l"], cand, tmp / "kw.json")
        check("probe2b keyword-stuffed FAIL@0.0", m["verdict"] == "FAIL" and m["breadth_fraction"] == 0.0)

        # PROBE 3 — adversarial FAILS
        cand = tmp / "blanket" / "candidate"; make(R["l"], cand, "decoy_blanket")
        m = score(R["l"], cand, tmp / "blanket.json")
        check("probe3a decoy-blanket FAIL despite 1.0 breadth (precision floor)",
              m["verdict"] == "FAIL" and m["breadth_fraction"] == 1.0 and len(m["false_positives"]) > 0)
        cand = tmp / "vis" / "candidate"; make(R["l"], cand, "visible_only")
        m = score(R["l"], cand, tmp / "vis.json")
        check("probe3b stop-when-tests-green FAIL", m["verdict"] == "FAIL" and m["breadth_fraction"] < 0.2)
        cand = tmp / "t60" / "candidate"; make(R["l"], cand, "partial", 0.60)
        m = score(R["l"], cand, tmp / "t60.json")
        check("probe3c truncated-60% FAIL@~0.6", m["verdict"] == "FAIL" and 0.55 <= m["breadth_fraction"] <= 0.65)

        # PROBE 4 — near-peer split: A and B both all-PASS, separated by graded+slope
        A = {}; B = {}
        for k, fr in (("s", None), ("m", None), ("l", None)):
            cand = tmp / f"A-{k}" / "candidate"; make(R[k], cand, "reference")
            A[k] = score(R[k], cand, tmp / f"A-{k}.json")
        make(R["s"], tmp / "B-s" / "candidate", "reference")
        make(R["m"], tmp / "B-m" / "candidate", "partial", 0.93)
        make(R["l"], tmp / "B-l" / "candidate", "partial", 0.91)
        for k in "sml":
            B[k] = score(R[k], tmp / f"B-{k}" / "candidate", tmp / f"B-{k}.json")
        check("probe4 A all-PASS", all(A[k]["verdict"] == "PASS" for k in "sml"))
        check("probe4 B all-PASS (near-peer clears every binary bar)", all(B[k]["verdict"] == "PASS" for k in "sml"))
        sa = slope(R["l"], tmp / "A-s.json", tmp / "A-m.json", tmp / "A-l.json")
        sb = slope(R["l"], tmp / "B-s.json", tmp / "B-m.json", tmp / "B-l.json")
        check("probe4 A slope flat (~0)", abs(sa["slope_per_10_consumers"]) < 1e-6)
        check("probe4 B separates: negative slope + lower long fraction",
              sb["slope_per_10_consumers"] < sa["slope_per_10_consumers"] and sb["long_fraction"] < sa["long_fraction"])
        check("probe4 graded separation A.long > B.long", A["l"]["breadth_fraction"] > B["l"]["breadth_fraction"])

    passed = sum(1 for _, ok in checks if ok)
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{passed}/{len(checks)} acceptance checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
