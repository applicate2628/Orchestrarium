#!/usr/bin/env python3

from __future__ import annotations

import os
import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.special import hankel1, jv


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N31 MoM cylinder analytic-oracle bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_quotes(value: str):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path):
    data = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            data.setdefault(current_key, []).append(strip_quotes(line[4:].strip()))
            continue
        if ":" not in line or line.startswith(" "):
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value == "":
            data[key] = []
            current_key = key
        elif value == "[]":
            data[key] = []
            current_key = None
        else:
            data[key] = strip_quotes(value)
            current_key = None
    return data


def top_level_yaml_keys(path: Path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line and not line.startswith(" ") and not line.startswith("#") and ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    return keys


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def check_shape(root: Path, contract: dict, errors: list[str]):
    actual_entries = sorted(path.name for path in root.iterdir())
    require(
        actual_entries == sorted(contract["required_top_level_entries"]),
        f"Top-level bundle entries drifted: {actual_entries}",
        errors,
    )
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)


def import_solver(root: Path):
    exec_root = Path(os.environ["BENCH_EXEC_ROOT"]).resolve() if os.environ.get("BENCH_EXEC_ROOT") else root
    solver_path = exec_root / "candidate" / "workspace" / "mom_solver.py"
    spec = importlib.util.spec_from_file_location("n31_candidate_mom_solver", solver_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import solver from {solver_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def static_solver_failures(root: Path, contract: dict) -> list[dict]:
    text = (root / "candidate" / "workspace" / "mom_solver.py").read_text(encoding="utf-8").lower()
    failures = []
    for marker in contract["forbidden_solver_markers"]:
        if marker.lower() in text:
            failures.append({"id": "solver-forbidden-marker", "detail": marker})
    return failures


def sample_angles(count: int) -> list[float]:
    return [2.0 * math.pi * index / count for index in range(count)]


def boundary_points(radius: float, segments: int) -> tuple[np.ndarray, np.ndarray]:
    angles = (np.arange(segments, dtype=float) + 0.5) * (2.0 * math.pi / segments)
    points = np.column_stack((radius * np.cos(angles), radius * np.sin(angles)))
    return angles, points


def incident_field(points: np.ndarray, wavenumber: float, incident_angle: float) -> np.ndarray:
    phase = wavenumber * (points[:, 0] * math.cos(incident_angle) + points[:, 1] * math.sin(incident_angle))
    return np.exp(1j * phase)


def build_mom_matrix(radius: float, wavenumber: float, segments: int, quadrature_order: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    angles, collocation_points = boundary_points(radius, segments)
    nodes, weights = leggauss(quadrature_order)
    dphi = 2.0 * math.pi / segments
    matrix = np.zeros((segments, segments), dtype=complex)

    for source in range(segments):
        center = (source + 0.5) * dphi
        panel_angles = center + 0.5 * dphi * nodes
        panel_weights = weights * 0.5 * dphi * radius
        panel_points = np.column_stack((radius * np.cos(panel_angles), radius * np.sin(panel_angles)))
        for point, weight in zip(panel_points, panel_weights):
            distances = np.linalg.norm(collocation_points - point, axis=1)
            matrix[:, source] += 0.25j * hankel1(0, wavenumber * distances) * weight

    return matrix, angles, collocation_points


def field_from_density(
    observation_points: np.ndarray,
    radius: float,
    wavenumber: float,
    density: np.ndarray,
    quadrature_order: int,
) -> np.ndarray:
    segments = len(density)
    nodes, weights = leggauss(quadrature_order)
    dphi = 2.0 * math.pi / segments
    field = np.zeros(len(observation_points), dtype=complex)

    for source in range(segments):
        center = (source + 0.5) * dphi
        panel_angles = center + 0.5 * dphi * nodes
        panel_weights = weights * 0.5 * dphi * radius
        panel_points = np.column_stack((radius * np.cos(panel_angles), radius * np.sin(panel_angles)))
        for point, weight in zip(panel_points, panel_weights):
            distances = np.linalg.norm(observation_points - point, axis=1)
            field += density[source] * 0.25j * hankel1(0, wavenumber * distances) * weight

    return field


def analytic_total_field(
    observation_points: np.ndarray,
    radius: float,
    wavenumber: float,
    incident_angle: float,
    series_terms: int,
) -> np.ndarray:
    x = observation_points[:, 0]
    y = observation_points[:, 1]
    r = np.sqrt(x * x + y * y)
    phi = np.arctan2(y, x)
    incident = incident_field(observation_points, wavenumber, incident_angle)
    scattered = np.zeros(len(observation_points), dtype=complex)

    for order in range(-series_terms, series_terms + 1):
        coefficient = -(
            (1j ** order)
            * np.exp(-1j * order * incident_angle)
            * jv(order, wavenumber * radius)
            / hankel1(order, wavenumber * radius)
        )
        scattered += coefficient * hankel1(order, wavenumber * r) * np.exp(1j * order * phi)

    return incident + scattered


def parse_complex(value):
    if isinstance(value, complex):
        return value
    if isinstance(value, dict):
        return complex(float(value.get("re", 0.0)), float(value.get("im", 0.0)))
    if isinstance(value, list) and len(value) == 2:
        return complex(float(value[0]), float(value[1]))
    raise ValueError(f"Cannot parse complex value: {value!r}")


def check_case(module, contract_case: dict) -> tuple[dict, list[dict]]:
    failures = []
    case_id = contract_case["case_id"]
    radius = float(contract_case["radius"])
    wavenumber = float(contract_case["wavenumber"])
    segments = int(contract_case["segments"])
    incident_angle = float(contract_case["incident_angle"])
    observation_radius = float(contract_case["observation_radius"])
    angles = sample_angles(int(contract_case["sample_count"]))

    started = time.perf_counter()
    result = module.solve_cylinder_mom(
        radius=radius,
        wavenumber=wavenumber,
        segments=segments,
        incident_angle=incident_angle,
        observation_radius=observation_radius,
        sample_angles=angles,
    )
    wall_seconds = time.perf_counter() - started

    if not isinstance(result, dict):
        return {}, [{"id": f"solver-case-{case_id}", "detail": "solver did not return a dictionary"}]

    for key in [
        "radius",
        "wavenumber",
        "segments",
        "incident_angle",
        "observation_radius",
        "method",
        "panel_angles",
        "density",
        "boundary_residual_l2",
        "field_samples",
        "runtime_seconds",
    ]:
        if key not in result:
            failures.append({"id": f"solver-case-{case_id}", "detail": f"missing key {key}"})
    if failures:
        return result, failures

    try:
        density = np.array([parse_complex(value) for value in result["density"]], dtype=complex)
    except Exception as exc:  # noqa: BLE001
        return result, [{"id": f"solver-case-{case_id}", "detail": f"density parse failed: {exc}"}]
    if len(density) != segments:
        failures.append({"id": f"solver-case-{case_id}", "detail": f"density length {len(density)} != {segments}"})
        return result, failures
    if not np.all(np.isfinite(np.real(density))) or not np.all(np.isfinite(np.imag(density))):
        failures.append({"id": f"solver-case-{case_id}", "detail": "density contains non-finite values"})
        return result, failures

    matrix, _panel_angles, collocation_points = build_mom_matrix(
        radius,
        wavenumber,
        segments,
        int(contract_case["matrix_quadrature_order"]),
    )
    rhs = -incident_field(collocation_points, wavenumber, incident_angle)
    boundary_residual = float(np.linalg.norm(matrix @ density - rhs) / max(np.linalg.norm(rhs), 1e-30))
    reported_residual = float(result.get("boundary_residual_l2", 999.0))
    max_residual = max(boundary_residual, reported_residual)
    if max_residual > float(contract_case["max_boundary_residual_l2"]):
        failures.append({
            "id": f"solver-case-{case_id}",
            "detail": f"boundary residual {max_residual:.8g} exceeds {contract_case['max_boundary_residual_l2']}",
        })

    observation_angles = np.array(angles, dtype=float)
    observation_points = np.column_stack((
        observation_radius * np.cos(observation_angles),
        observation_radius * np.sin(observation_angles),
    ))
    scattered = field_from_density(
        observation_points,
        radius,
        wavenumber,
        density,
        int(contract_case["field_quadrature_order"]),
    )
    total = scattered + incident_field(observation_points, wavenumber, incident_angle)
    exact = analytic_total_field(
        observation_points,
        radius,
        wavenumber,
        incident_angle,
        int(contract_case["series_terms"]),
    )
    relative_field_error = float(np.linalg.norm(total - exact) / max(np.linalg.norm(exact), 1e-30))
    if relative_field_error > float(contract_case["max_relative_field_error"]):
        failures.append({
            "id": f"solver-case-{case_id}",
            "detail": f"relative field error {relative_field_error:.8g} exceeds {contract_case['max_relative_field_error']}",
        })

    field_samples = result.get("field_samples")
    if not isinstance(field_samples, list) or len(field_samples) != len(angles):
        failures.append({"id": f"solver-case-{case_id}", "detail": "field sample count mismatch"})
    else:
        for expected_angle, sample in zip(angles, field_samples):
            if abs(float(sample.get("angle", 999.0)) - expected_angle) > 1e-9:
                failures.append({"id": f"solver-case-{case_id}", "detail": "field sample angle mismatch"})
                break

    runtime_seconds = max(wall_seconds, float(result.get("runtime_seconds", 0.0)))
    if runtime_seconds > float(contract_case["max_runtime_seconds"]):
        failures.append({
            "id": f"solver-case-{case_id}",
            "detail": f"runtime {runtime_seconds:.3f}s exceeds {contract_case['max_runtime_seconds']}s",
        })

    metrics = {
        "case_id": case_id,
        "boundary_residual_l2": boundary_residual,
        "relative_field_error": relative_field_error,
        "runtime_seconds": runtime_seconds,
    }
    return metrics, failures


def check_report(root: Path, contract: dict, case_metrics: dict[str, dict]) -> list[dict]:
    failures = []
    try:
        report = load_json(root / "candidate" / "workspace" / "validation-report.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "report-json-invalid", "detail": str(exc)}]

    for field in contract["required_report_fields"]:
        if field not in report:
            failures.append({"id": "report-missing-fields", "detail": field})

    if report.get("method") != "pulse-basis MoM for PEC cylinder TMz EFIE":
        failures.append({"id": "report-method", "detail": str(report.get("method"))})
    if report.get("oracle_use") != "cylindrical-harmonic series only as validation oracle":
        failures.append({"id": "report-oracle-use", "detail": str(report.get("oracle_use"))})

    cases = report.get("cases")
    if not isinstance(cases, list):
        failures.append({"id": "report-missing-cases", "detail": "cases is not a list"})
        return failures
    by_id = {case.get("case_id"): case for case in cases if isinstance(case, dict)}
    missing = sorted(set(contract["required_report_cases"]) - set(by_id))
    if missing:
        failures.append({"id": "report-missing-cases", "detail": str(missing)})
        return failures

    case_limits = {case["case_id"]: case for case in contract["cases"]}
    for case_id in contract["required_report_cases"]:
        report_case = by_id[case_id]
        limit = case_limits[case_id]
        metrics = case_metrics.get(case_id)
        if metrics is None:
            continue
        if float(report_case.get("relative_field_error", 999.0)) > float(limit["max_relative_field_error"]):
            failures.append({"id": "report-case-values", "detail": f"{case_id}: relative field error too high"})
        if float(report_case.get("boundary_residual_l2", 999.0)) > float(limit["max_boundary_residual_l2"]):
            failures.append({"id": "report-case-values", "detail": f"{case_id}: boundary residual too high"})
        if abs(float(report_case.get("relative_field_error", 999.0)) - metrics["relative_field_error"]) > 0.002:
            failures.append({"id": "report-case-values", "detail": f"{case_id}: report field error not tied to solver"})

    convergence = report.get("convergence")
    if not isinstance(convergence, dict):
        failures.append({"id": "report-convergence", "detail": "convergence is not an object"})
        return failures
    expected_convergence = contract["convergence"]
    if convergence.get("coarse_case_id") != expected_convergence["coarse_case_id"]:
        failures.append({"id": "report-convergence", "detail": "coarse case id mismatch"})
    if convergence.get("refined_case_id") != expected_convergence["refined_case_id"]:
        failures.append({"id": "report-convergence", "detail": "refined case id mismatch"})
    try:
        improvement = float(convergence.get("field_error_improvement_ratio"))
    except Exception:  # noqa: BLE001
        improvement = 0.0
    if improvement < float(expected_convergence["min_field_error_improvement_ratio"]):
        failures.append({"id": "report-convergence", "detail": f"improvement {improvement}"})

    return failures


def check_notes(root: Path, contract: dict) -> list[dict]:
    text = (root / "candidate" / "workspace" / "validation-notes.md").read_text(encoding="utf-8").lower()
    missing = [phrase for phrase in contract["required_notes_phrases"] if phrase.lower() not in text]
    if missing:
        return [{"id": "notes-missing-phrases", "detail": ", ".join(missing)}]
    return []


def evaluate_bundle(root: Path, contract: dict) -> list[dict]:
    failures = static_solver_failures(root, contract)

    try:
        module = import_solver(root)
    except Exception as exc:  # noqa: BLE001
        return failures + [{"id": "solver-import-failed", "detail": str(exc)}]

    if not hasattr(module, contract["solver_api"]):
        return failures + [{"id": "solver-api-missing", "detail": contract["solver_api"]}]

    case_metrics = {}
    for contract_case in contract["cases"]:
        metrics, case_failures = check_case(module, contract_case)
        if metrics:
            case_metrics[metrics["case_id"]] = metrics
        failures.extend(case_failures)

    convergence = contract["convergence"]
    coarse = case_metrics.get(convergence["coarse_case_id"])
    refined = case_metrics.get(convergence["refined_case_id"])
    if coarse and refined:
        if refined["relative_field_error"] <= 0:
            improvement = float("inf")
        else:
            improvement = coarse["relative_field_error"] / refined["relative_field_error"]
        if improvement < float(convergence["min_field_error_improvement_ratio"]):
            failures.append({
                "id": "convergence-failed",
                "detail": f"improvement ratio {improvement:.4f}",
            })
    else:
        failures.append({"id": "convergence-failed", "detail": "missing case metrics"})

    failures.extend(check_report(root, contract, case_metrics))
    failures.extend(check_notes(root, contract))
    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "mom-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate_bundle(root, contract)
        failure_ids = sorted({failure["id"] for failure in failures})
        if args.expect_start_state:
            expected = set(contract["expected_start_state_failures"])
            missing = sorted(expected - set(failure_ids))
            require(not missing, f"Expected start-state failures missing: {missing}; found {failure_ids}", errors)
        elif failures:
            errors.append(f"Completed N31 MoM solver still fails checks: {json.dumps(failures, indent=2)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        mode = "bundle shape"
    elif args.expect_start_state:
        mode = "start state"
    else:
        mode = "completed solver"
    print(f"N31 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
