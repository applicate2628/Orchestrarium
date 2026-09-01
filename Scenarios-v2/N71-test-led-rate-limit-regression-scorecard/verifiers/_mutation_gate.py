#!/usr/bin/env python3
"""R7 mutation gate (B5): certify that a candidate's mandated regression test actually
detects EACH required defect class, not just one historical buggy baseline.

Design (rides on the Phase-0 exec-root isolation invariant, I1):
- The candidate's mandated test is READ from the oracle-free candidate exec root
  ($BENCH_EXEC_ROOT when set, else the bundle root) -- never executed in a tree that
  contains oracle/.
- The code-under-test comes from immutable, scorer-private snapshots under
  oracle/snapshots/ (fixed / buggy / one mutant per required defect class). For each
  variant the gate assembles a fresh disposable exec root in the system temp dir
  (snapshot package + the candidate test + a result-capturing conftest) and runs the
  test there with pytest. No oracle/ is ever on that exec path.

Verdict per the B5 contract:
- PASS-on-fixed is a precondition; if it is not met the gate is NOT-SATISFIABLE (abstain).
- The test must FAIL-on-buggy AND FAIL on every class-mutant, and the failure must be the
  EXPECTED assertion (a failing test node raising AssertionError). A variant on which the
  test merely passes -> "<variant> undetected"; a variant on which it only crashes with a
  non-assertion exception -> "<variant> not-asserted".
- Collection / import / no-tests / infra failures yield NOT-SATISFIABLE (a distinct code
  that counts as neither pass nor fail-certification), never a model-quality F.

Statuses: "pass" | "fail" | "not-satisfiable".
run_mutation_gate returns a report dict; report["failures"] is a list of (id, detail)
tuples that the caller adds to its own floor+runtime failures (augment, not replace).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# A pytest plugin (written into each disposable exec root) that records, per test node,
# the call outcome and the raised exception type -- enough to tell a clean AssertionError
# detection from an incidental crash from a collection/import error. Works on pytest 9.
_CONFTEST = '''\
import json, os
import pytest

_records = {}


def _rec(nodeid):
    return _records.setdefault(nodeid, {"nodeid": nodeid, "outcome": "passed", "exc_type": None, "phase": None})


def pytest_exception_interact(node, call, report):
    nodeid = getattr(report, "nodeid", None) or getattr(node, "nodeid", "<node>")
    rec = _rec(nodeid)
    rec["phase"] = getattr(report, "when", None) or "collect"
    if rec["phase"] == "collect":
        rec["outcome"] = "collect-error"
    elif rec["phase"] in ("setup", "teardown"):
        rec["outcome"] = "error"
    else:
        rec["outcome"] = "failed"
    if call is not None and getattr(call, "excinfo", None) is not None:
        rec["exc_type"] = call.excinfo.type.__name__


def pytest_runtest_logreport(report):
    if report.when == "call" and report.outcome == "passed":
        _rec(report.nodeid)["phase"] = "call"


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("MUTGATE_JSON_OUT")
    payload = {"records": list(_records.values()), "exitstatus": int(exitstatus)}
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
'''


def _load_manifest(snap_root: Path) -> dict[str, Any]:
    return json.loads((snap_root / "MANIFEST.json").read_text(encoding="utf-8"))


def candidate_test_path(bundle_root: Path, exec_root: Path) -> Path:
    """Resolve the candidate's mandated test file inside the oracle-free exec root."""
    manifest = _load_manifest(bundle_root / "oracle" / "snapshots")
    return exec_root / manifest["mandated_test_relpath"]


def _assemble(snap_root: Path, variant_dir: str, is_mutant: bool, manifest: dict, dest_src: Path) -> None:
    pkg = manifest["package"]
    if is_mutant:
        # a mutant is the fixed package with a one-file overlay reintroducing one defect class.
        shutil.copytree(snap_root / manifest["fixed"] / pkg, dest_src / pkg)
        overlay = snap_root / "mutants" / variant_dir / pkg
        for src_file in overlay.rglob("*"):
            if src_file.is_file():
                target = dest_src / pkg / src_file.relative_to(overlay)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src_file, target)
    else:
        # fixed and buggy are complete, standalone, immutable packages.
        shutil.copytree(snap_root / variant_dir / pkg, dest_src / pkg)


def _run_variant(snap_root: Path, variant_dir: str, is_mutant: bool, manifest: dict, test_src: Path) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="mutgate-"))
    try:
        src = tmp / "src"
        tests = tmp / "tests"
        src.mkdir()
        tests.mkdir()
        _assemble(snap_root, variant_dir, is_mutant, manifest, src)
        shutil.copyfile(test_src, tests / manifest["test_filename"])
        (tmp / "conftest.py").write_text(_CONFTEST, encoding="utf-8")
        out_json = tmp / "out.json"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(src)
        env["MUTGATE_JSON_OUT"] = str(out_json)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", f"tests/{manifest['test_filename']}",
             "-p", "no:cacheprovider", "-q", "-o", "addopts="],
            cwd=str(tmp), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        try:
            data = json.loads(out_json.read_text(encoding="utf-8"))
        except Exception:
            data = {"records": [], "exitstatus": proc.returncode}
        records = data.get("records", [])
        exitstatus = int(data.get("exitstatus", proc.returncode))
        uncollectable = (
            exitstatus in (2, 3, 5)
            or any(rec.get("outcome") == "collect-error" for rec in records)
            or not records
        )
        all_passed = bool(records) and all(rec.get("outcome") == "passed" for rec in records)
        assert_fail = [rec["nodeid"] for rec in records
                       if rec.get("outcome") == "failed" and rec.get("exc_type") == "AssertionError"]
        any_fail = [rec["nodeid"] for rec in records if rec.get("outcome") in ("failed", "error")]
        return {
            "exitstatus": exitstatus,
            "uncollectable": uncollectable,
            "all_passed": all_passed,
            "assert_fail_nodeids": assert_fail,
            "any_fail_nodeids": any_fail,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_mutation_gate(bundle_root: Path, test_src: Path) -> dict:
    """Run the mutation matrix. Returns {status, reason, variants, failures}."""
    snap_root = bundle_root / "oracle" / "snapshots"
    report: dict[str, Any] = {"status": None, "reason": None, "variants": {}, "failures": []}
    if not snap_root.exists():
        report["status"] = "not-satisfiable"
        report["reason"] = "oracle/snapshots missing"
        return report
    manifest = _load_manifest(snap_root)
    if not test_src.exists():
        report["status"] = "not-satisfiable"
        report["reason"] = f"mandated test not found at {test_src}"
        return report

    fixed = _run_variant(snap_root, manifest["fixed"], False, manifest, test_src)
    report["variants"]["fixed"] = fixed
    if fixed["uncollectable"]:
        report["status"] = "not-satisfiable"
        report["reason"] = "fixed-uncollectable (import/collection/infra failure)"
        return report
    if not fixed["all_passed"]:
        report["status"] = "not-satisfiable"
        report["reason"] = "fixed-not-green (mandated test does not pass on the correct reference)"
        return report

    matrix = [(manifest["buggy"], "buggy", False, "historical combined-defect baseline")]
    for mutant in manifest["mutants"]:
        matrix.append((mutant["id"], mutant["id"], True, mutant["defect_class"]))

    gate_failures: list[tuple[str, str]] = []
    for variant_dir, label, is_mutant, desc in matrix:
        res = _run_variant(snap_root, variant_dir, is_mutant, manifest, test_src)
        report["variants"][label] = res
        if res["uncollectable"]:
            report["status"] = "not-satisfiable"
            report["reason"] = f"{label}-uncollectable (import/collection/infra failure on a variant)"
            report["failures"] = []
            return report
        if res["assert_fail_nodeids"]:
            continue
        if res["all_passed"]:
            gate_failures.append((
                f"mutation-{label}-undetected",
                f"mandated test does not detect defect class [{desc}]: it PASSES on the {label} snapshot",
            ))
        else:
            gate_failures.append((
                f"mutation-{label}-not-asserted",
                f"mandated test reacts to defect class [{desc}] only by crashing (no AssertionError) on the {label} snapshot",
            ))

    if gate_failures:
        report["status"] = "fail"
        report["failures"] = gate_failures
    else:
        report["status"] = "pass"
    return report


def mutation_selftest(bundle_root: Path) -> tuple[bool, dict]:
    """Four-probe regression: reference must PASS the gate; vacuous and decoy must FAIL it."""
    snap_root = bundle_root / "oracle" / "snapshots"
    manifest = _load_manifest(snap_root)
    name = manifest["test_filename"]
    cases = {
        "reference": (snap_root / "reference-test" / name, "pass"),
        "vacuous": (snap_root / "probes" / "vacuous" / name, "fail"),
        "decoy": (snap_root / "probes" / "decoy" / name, "fail"),
    }
    results: dict[str, Any] = {}
    ok = True
    for probe, (path, expected) in cases.items():
        rep = run_mutation_gate(bundle_root, path)
        matched = rep["status"] == expected
        ok = ok and matched
        results[probe] = {
            "expected": expected,
            "actual": rep["status"],
            "matched": matched,
            "failures": [fid for fid, _ in rep["failures"]],
            "reason": rep["reason"],
        }
    return ok, results
