#!/usr/bin/env python3
"""Verifier for the V3L05 stamina-migration family (F1).

Graded breadth-completeness scorer for ONE homogeneous mechanical contract
migration across many hidden consumers, with a decoy precision floor.

Scoring (pre-registered in oracle/stamina-contract.json + discrimination.yaml):
  breadth_fraction = migrated_correct / total_consumers          (graded, 0..1)
  PASS iff breadth_fraction >= pass_fraction
          AND false_positives == 0 (no decoy touched)
          AND workspace imports AND visible tests pass (floor).

Candidate CODE is executed from the oracle-free exec root when BENCH_EXEC_ROOT is
set (H9 topology); the ORACLE is always read from the private scorer bundle root.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify V3L05 stamina migration (graded).")
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root,
                        help="Private scorer bundle root (holds oracle/, scenario.yaml).")
    parser.add_argument("--candidate-root", type=Path, default=None,
                        help="Alternate candidate/ dir (its workspace/src holds the code).")
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--metrics-out", type=Path, default=None)
    parser.add_argument("--changed-path", action="append", default=[])
    return parser.parse_args()


# --------------------------------------------------------------------------- yaml
def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path) -> dict:
    data: dict[str, Any] = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_key is not None:
                data.setdefault(current_key, []).append(strip_quotes(line[4:].strip()))
            continue
        if line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "[]":
            data[key] = []
            current_key = None
        elif value:
            data[key] = strip_quotes(value)
            current_key = None
        else:
            data[key] = []
            current_key = key
    return data


def top_level_yaml_keys(path: Path) -> list:
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        keys.append(line.split(":", 1)[0].strip())
    return keys


# --------------------------------------------------------------------------- shape
def load_contract(bundle_root: Path) -> dict:
    return json.loads((bundle_root / "oracle" / "stamina-contract.json").read_text(encoding="utf-8"))


def check_bundle_shape(bundle_root: Path, contract: dict, errors: list) -> None:
    for entry in contract["required_top_level_entries"]:
        if not (bundle_root / entry).exists():
            errors.append(f"Missing top-level entry: {entry}")
    for rel in contract["required_bundle_files"]:
        if not (bundle_root / rel).exists():
            errors.append(f"Missing required bundle file: {rel}")
    scenario_path = bundle_root / "scenario.yaml"
    if not scenario_path.exists():
        errors.append("Missing scenario.yaml")
        return
    if top_level_yaml_keys(scenario_path) != contract["scenario_yaml_fields"]:
        errors.append("scenario.yaml fields do not match the required contract order exactly")
    if parse_simple_yaml(scenario_path) != contract["required_metadata"]:
        errors.append("scenario.yaml metadata does not match the required contract")


# --------------------------------------------------------------------------- exec root
def resolve_src(bundle_root: Path, candidate_root: Path | None) -> Path:
    env = os.environ.get("BENCH_EXEC_ROOT")
    if env:
        return Path(env).resolve() / "candidate" / "workspace" / "src"
    if candidate_root is not None:
        return candidate_root.resolve() / "workspace" / "src"
    return bundle_root / "candidate" / "workspace" / "src"


def workspace_dir(src: Path) -> Path:
    return src.parent  # .../candidate/workspace


# --------------------------------------------------------------------------- import + call
def import_modules(src: Path, module_names: list) -> dict:
    """Import each ledgerkit.<module> in isolation. Returns {name: module|None}."""
    sys.dont_write_bytecode = True  # never litter __pycache__ into the scored tree
    sys.path.insert(0, str(src))
    try:
        for name in list(sys.modules):
            if name == "ledgerkit" or name.startswith("ledgerkit."):
                del sys.modules[name]
        result = {}
        for mod in module_names:
            try:
                result[mod] = importlib.import_module(f"ledgerkit.{mod}")
            except Exception:
                result[mod] = None
        return result
    finally:
        try:
            sys.path.remove(str(src))
        except ValueError:
            pass


def call_func(module, func_name):
    fn = getattr(module, func_name, None)
    if fn is None:
        return ("missing", None)
    try:
        return ("ok", fn())
    except Exception as exc:  # candidate broke the function
        return ("error", f"{type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------- visible tests (floor)
def _normalize_visible_log(output: str, workspace: Path) -> str:
    import re

    logical_workspace = "candidate/workspace"
    resolved_workspace = workspace.resolve()
    path_forms = {
        str(workspace),
        workspace.as_posix(),
        str(resolved_workspace),
        resolved_workspace.as_posix(),
    }
    for path_form in sorted(path_forms, key=len, reverse=True):
        output = output.replace(f"{path_form}\\", f"{logical_workspace}/")
        output = output.replace(f"{path_form}/", f"{logical_workspace}/")
        output = output.replace(path_form, logical_workspace)
    logical_path = re.compile(rf'{re.escape(logical_workspace)}[^"\r\n]*')
    return logical_path.sub(lambda match: match.group(0).replace("\\", "/"), output)


def run_visible_tests(workspace: Path) -> tuple[bool, str]:
    env_code = (
        "import os,sys,subprocess; "
        "os.environ['PYTHONPATH']='src'; "
        "os.environ['PYTHONDONTWRITEBYTECODE']='1'; "
        "raise SystemExit(subprocess.call([sys.executable,'-B','-m','unittest','discover','-s','tests'], "
        f"cwd=r'{workspace}', env=os.environ.copy()))"
    )
    completed = subprocess.run([sys.executable, "-c", env_code], text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    visible_log = _normalize_visible_log(completed.stdout.strip(), workspace)
    return completed.returncode == 0, visible_log


# --------------------------------------------------------------------------- scope (floor)
def check_scope(contract: dict, changed: list, errors: list) -> None:
    import fnmatch
    if not changed:
        return
    allowed = contract["required_metadata"]["allowed_change_surface"]
    forbidden = contract["required_metadata"]["must_not_touch"]
    for raw in changed:
        path = raw.replace("\\", "/").strip("/")
        if any(fnmatch.fnmatch(path, pat) for pat in forbidden):
            errors.append(f"changed protected path: {path}")
        elif not any(fnmatch.fnmatch(path, pat) for pat in allowed):
            errors.append(f"changed path outside allowed surface: {path}")


# --------------------------------------------------------------------------- score
def score_candidate(bundle_root: Path, candidate_root: Path | None, contract: dict) -> dict:
    consumers = contract["consumers"]
    report_decoys = contract["report_decoys"]
    audit_decoys = contract["audit_decoys"]
    all_decoys = report_decoys + audit_decoys
    total = len(consumers)

    module_names = sorted({e["module"] for e in consumers + all_decoys})
    src = resolve_src(bundle_root, candidate_root)
    modules = import_modules(src, module_names)

    completed = []
    missed = []
    for e in consumers:
        mod = modules.get(e["module"])
        if mod is None:
            missed.append(e["func"])
            continue
        status, value = call_func(mod, e["func"])
        if status == "ok" and value == e["expected"]:
            completed.append(e["func"])
        else:
            missed.append(e["func"])

    false_positives = []
    for e in all_decoys:
        mod = modules.get(e["module"])
        if mod is None:
            # module unreachable -> cannot confirm the decoy is unchanged; treat as touched.
            false_positives.append(e["func"])
            continue
        status, value = call_func(mod, e["func"])
        if not (status == "ok" and value == e["expected"]):
            false_positives.append(e["func"])

    ok_visible, visible_log = run_visible_tests(workspace_dir(src))

    breadth_fraction = (len(completed) / total) if total else 0.0
    pass_fraction = contract["score"]["pass_fraction"]
    import_ok = any(m is not None for m in modules.values())

    failure_ids = []
    if not import_ok:
        failure_ids.append("import")
    if breadth_fraction < pass_fraction:
        failure_ids.append("breadth-below-threshold")
    if false_positives:
        failure_ids.append("decoy-false-positive")
    if not ok_visible:
        failure_ids.append("tests-visible")

    verdict = "PASS" if not failure_ids else "FAIL"
    return {
        "variant": contract.get("variant"),
        "scenario_id": contract["scenario_id"],
        "total_consumers": total,
        "completed_count": len(completed),
        "missed": sorted(missed),
        "false_positives": sorted(false_positives),
        "breadth_fraction": round(breadth_fraction, 6),
        "points": round(breadth_fraction * contract["score"]["max_points"]),
        "pass_fraction": pass_fraction,
        "visible_tests_pass": ok_visible,
        "visible_log": "" if ok_visible else visible_log[:2000],
        "failure_ids": failure_ids,
        "verdict": verdict,
    }


def write_metrics(path: Path | None, payload: dict) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, indent=2) + "\n")


def main() -> int:
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    errors: list = []
    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1
    contract = load_contract(bundle_root)
    check_bundle_shape(bundle_root, contract, errors)

    if args.bundle_shape_only:
        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(f"V3L05 verifier PASS (bundle shape, variant {contract.get('variant')})")
        return 0

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    check_scope(contract, args.changed_path, errors)
    payload = score_candidate(bundle_root, args.candidate_root, contract)
    if errors:
        payload["failure_ids"] = ["scope"] + payload["failure_ids"]
        payload["verdict"] = "FAIL"
    write_metrics(args.metrics_out, payload)

    print(json.dumps({k: payload[k] for k in (
        "variant", "total_consumers", "completed_count", "breadth_fraction",
        "points", "pass_fraction", "false_positives", "failure_ids", "verdict")}, indent=2))
    return 0 if payload["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
