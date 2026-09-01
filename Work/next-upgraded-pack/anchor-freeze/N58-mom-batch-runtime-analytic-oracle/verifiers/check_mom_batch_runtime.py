#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np


LAST_METRICS: dict = {}


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N58 repeated-RHS MoM batch runtime oracle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def import_python_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def import_base_verifier():
    return import_python_module(Path(__file__).with_name("check_science_optimizer.py"), "n58_science_optimizer_base")


def import_candidate(root: Path):
    return import_python_module(root / "candidate" / "workspace" / "dual_physics.py", "n58_candidate_dual_physics")


def static_batch_failures(root: Path, contract: dict) -> list[dict]:
    text = (root / "candidate" / "workspace" / "dual_physics.py").read_text(encoding="utf-8").lower()
    failures = []
    for marker in contract.get("forbidden_solver_markers", []):
        if marker.lower() in text:
            failures.append({"id": "solver-forbidden-marker", "detail": marker})
    markers = contract.get("required_solver_marker_groups", {}).get("em_batch_factor_reuse", [])
    if markers and not any(marker.lower() in text for marker in markers):
        failures.append({"id": "solver-missing-marker-em_batch_factor_reuse", "detail": ", ".join(markers)})
    return failures


def parse_complex(value):
    if isinstance(value, complex):
        return value
    if isinstance(value, dict):
        return complex(float(value.get("re", 0.0)), float(value.get("im", 0.0)))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return complex(float(value[0]), float(value[1]))
    if isinstance(value, str):
        return complex(value.replace("i", "j"))
    raise ValueError(f"Cannot parse complex value: {value!r}")


def normalize_batch_result(result, incident_angles: list[float]):
    if isinstance(result, list):
        return result, {}
    if not isinstance(result, dict):
        raise ValueError("batch solver did not return a dict or list")
    if isinstance(result.get("solutions"), list):
        return result["solutions"], result
    if isinstance(result.get("cases"), list):
        return result["cases"], result
    if isinstance(result.get("densities"), list):
        densities = result["densities"]
        solutions = [
            {"incident_angle": angle, "density": density}
            for angle, density in zip(incident_angles, densities)
        ]
        return solutions, result
    raise ValueError("batch solver result missing solutions/cases/densities list")


def solution_density(solution, segments: int):
    if isinstance(solution, dict):
        raw = solution.get("density")
        if raw is None:
            raw = solution.get("surface_density")
        if raw is None:
            raw = solution.get("density_samples")
    else:
        raw = solution
    if raw is None:
        raise ValueError("solution missing density")
    density = np.array([parse_complex(value) for value in raw], dtype=complex)
    if len(density) != segments:
        raise ValueError(f"density length {len(density)} != {segments}")
    if not np.all(np.isfinite(np.real(density))) or not np.all(np.isfinite(np.imag(density))):
        raise ValueError("density has non-finite values")
    return density


def solution_reported_angle(solution, fallback: float):
    if isinstance(solution, dict) and "incident_angle" in solution:
        return float(solution["incident_angle"])
    return float(fallback)


def check_one_solution(base, solution, contract_case: dict, incident_angle: float, matrix, panel_angles, collocation_points):
    failures = []
    case_id = contract_case["case_id"]
    radius = float(contract_case["radius"])
    wavenumber = float(contract_case["wavenumber"])
    segments = int(contract_case["segments"])
    observation_radius = float(contract_case["observation_radius"])
    sample_angles = base.sample_angles(int(contract_case["sample_count"]))

    try:
        reported_angle = solution_reported_angle(solution, incident_angle)
        if abs(reported_angle - incident_angle) > 1e-9:
            failures.append({
                "id": f"mom-batch-case-{case_id}",
                "detail": f"incident angle mismatch {reported_angle} != {incident_angle}",
            })
        density = solution_density(solution, segments)
    except Exception as exc:  # noqa: BLE001
        return {}, [{"id": f"mom-batch-case-{case_id}", "detail": str(exc)}]

    rhs = -base.incident_field(collocation_points, wavenumber, incident_angle)
    boundary_residual = float(np.linalg.norm(matrix @ density - rhs) / max(np.linalg.norm(rhs), 1e-30))
    reported_residual = None
    if isinstance(solution, dict) and "boundary_residual_l2" in solution:
        reported_residual = float(solution["boundary_residual_l2"])
    residual_for_gate = max(boundary_residual, reported_residual if reported_residual is not None else 0.0)
    if residual_for_gate > float(contract_case["max_boundary_residual_l2"]):
        failures.append({
            "id": f"mom-batch-case-{case_id}",
            "detail": f"angle {incident_angle}: boundary residual {residual_for_gate:.8g}",
        })

    observation_angles = np.array(sample_angles, dtype=float)
    observation_points = np.column_stack((
        observation_radius * np.cos(observation_angles),
        observation_radius * np.sin(observation_angles),
    ))
    total = (
        base.field_from_density(
            observation_points,
            radius,
            wavenumber,
            density,
            int(contract_case["field_quadrature_order"]),
        )
        + base.incident_field(observation_points, wavenumber, incident_angle)
    )
    exact = base.analytic_total_field(
        observation_points,
        radius,
        wavenumber,
        incident_angle,
        int(contract_case["series_terms"]),
    )
    relative_field_error = float(np.linalg.norm(total - exact) / max(np.linalg.norm(exact), 1e-30))
    if relative_field_error > float(contract_case["max_relative_field_error"]):
        failures.append({
            "id": f"mom-batch-field-{case_id}",
            "detail": f"angle {incident_angle}: relative field error {relative_field_error:.8g}",
        })

    modes = np.arange(-int(contract_case["density_modes"]), int(contract_case["density_modes"]) + 1)
    observed_modes = base.density_coefficients_from_samples(density, panel_angles, modes)
    exact_modes = base.analytic_density_coefficients(radius, wavenumber, incident_angle, modes)
    density_mode_error = float(np.linalg.norm(observed_modes - exact_modes) / max(np.linalg.norm(exact_modes), 1e-30))
    if density_mode_error > float(contract_case["max_density_mode_error"]):
        failures.append({
            "id": f"mom-batch-density-{case_id}",
            "detail": f"angle {incident_angle}: density Fourier error {density_mode_error:.8g}",
        })

    if isinstance(solution, dict) and "field_samples" in solution:
        field_samples = solution["field_samples"]
        if not isinstance(field_samples, list) or len(field_samples) != len(sample_angles):
            failures.append({"id": f"mom-batch-case-{case_id}", "detail": f"angle {incident_angle}: field sample count mismatch"})

    metrics = {
        "domain": "mom-batch-angle",
        "case_id": f"{case_id}:{incident_angle:.6g}",
        "parent_case_id": case_id,
        "incident_angle": incident_angle,
        "boundary_residual_l2": boundary_residual,
        "relative_field_error": relative_field_error,
        "density_mode_error": density_mode_error,
    }
    return metrics, failures


def check_batch_case(base, module, contract_case: dict):
    failures = []
    case_id = contract_case["case_id"]
    radius = float(contract_case["radius"])
    wavenumber = float(contract_case["wavenumber"])
    segments = int(contract_case["segments"])
    incident_angles = [float(value) for value in contract_case["incident_angles"]]
    observation_radius = float(contract_case["observation_radius"])
    sample_angles = base.sample_angles(int(contract_case["sample_count"]))

    started = time.perf_counter()
    result = module.solve_cylinder_batch_mom(
        radius=radius,
        wavenumber=wavenumber,
        segments=segments,
        incident_angles=incident_angles,
        observation_radius=observation_radius,
        sample_angles=sample_angles,
    )
    wall_seconds = time.perf_counter() - started

    try:
        solutions, envelope = normalize_batch_result(result, incident_angles)
    except Exception as exc:  # noqa: BLE001
        return {}, [{"id": f"mom-batch-case-{case_id}", "detail": str(exc)}]
    if len(solutions) != len(incident_angles):
        return {}, [{"id": f"mom-batch-case-{case_id}", "detail": f"solution count {len(solutions)} != {len(incident_angles)}"}]

    matrix, panel_angles, collocation_points = base.build_mom_matrix(
        radius,
        wavenumber,
        segments,
        int(contract_case["matrix_quadrature_order"]),
    )

    angle_metrics = []
    for incident_angle, solution in zip(incident_angles, solutions):
        metrics, solution_failures = check_one_solution(
            base,
            solution,
            contract_case,
            incident_angle,
            matrix,
            panel_angles,
            collocation_points,
        )
        if metrics:
            angle_metrics.append(metrics)
        failures.extend(solution_failures)

    reported_runtime = 0.0
    for key in ("runtime_seconds", "batch_runtime_seconds", "total_runtime_seconds"):
        if isinstance(envelope, dict) and key in envelope:
            reported_runtime = max(reported_runtime, float(envelope[key]))
    runtime_seconds = max(wall_seconds, reported_runtime)
    if runtime_seconds > float(contract_case["max_runtime_seconds"]):
        failures.append({
            "id": f"mom-batch-runtime-{case_id}",
            "detail": f"runtime {runtime_seconds:.3f}s exceeds {contract_case['max_runtime_seconds']}s",
        })

    if angle_metrics:
        aggregate = {
            "domain": "mom-batch",
            "case_id": case_id,
            "incident_count": len(incident_angles),
            "max_boundary_residual_l2": max(item["boundary_residual_l2"] for item in angle_metrics),
            "max_relative_field_error": max(item["relative_field_error"] for item in angle_metrics),
            "max_density_mode_error": max(item["density_mode_error"] for item in angle_metrics),
            "runtime_seconds": runtime_seconds,
        }
    else:
        aggregate = {"domain": "mom-batch", "case_id": case_id, "runtime_seconds": runtime_seconds}
    return {"aggregate": aggregate, "angles": angle_metrics}, failures


def evaluate_with_metrics(root: Path, contract: dict):
    failures = static_batch_failures(root, contract)
    metrics: list[dict] = []
    base = import_base_verifier()

    try:
        module = import_candidate(root)
    except Exception as exc:  # noqa: BLE001
        return failures + [{"id": "mom-batch-import-failed", "detail": str(exc)}], metrics

    api_name = contract.get("mom_batch_solver_api", "solve_cylinder_batch_mom")
    if not hasattr(module, api_name):
        return failures + [{"id": "mom-batch-api-missing", "detail": api_name}], metrics

    for contract_case in contract.get("mom_batch_cases", []):
        case_metrics, case_failures = check_batch_case(base, module, contract_case)
        if case_metrics:
            metrics.append(case_metrics["aggregate"])
            metrics.extend(case_metrics["angles"])
        failures.extend(case_failures)

    total_runtime = sum(
        float(item.get("runtime_seconds", 0.0))
        for item in metrics
        if item.get("domain") == "mom-batch"
    )
    metrics.append({"domain": "mom-batch", "case_id": "mom-batch-total-runtime", "runtime_seconds": total_runtime})
    if total_runtime > float(contract.get("max_total_batch_runtime_seconds", float("inf"))):
        failures.append({"id": "mom-batch-total-runtime", "detail": f"total runtime {total_runtime:.3f}s"})
    return failures, metrics


def evaluate_bundle(root: Path, contract: dict) -> list[dict]:
    failures, metrics = evaluate_with_metrics(root, contract)
    global LAST_METRICS
    LAST_METRICS = {"metrics": metrics}
    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "optimizer-contract.json")
    base = import_base_verifier()

    shape_errors: list[str] = []
    base.check_shape(root, contract, shape_errors)
    if shape_errors:
        for error in shape_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N58 MoM batch verifier PASS (bundle shape)")
        return 0

    failures, metrics = evaluate_with_metrics(root, contract)
    if args.metrics_out:
        args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_out.write_text(json.dumps({"metrics": metrics, "failures": failures}, indent=2) + "\n", encoding="utf-8")

    if args.expect_start_state:
        actual = {failure["id"] for failure in failures}
        expected = {"mom-batch-api-missing", "solver-missing-marker-em_batch_factor_reuse"}
        missing = sorted(expected - actual)
        if missing:
            print(f"ERROR: expected start-state batch failures missing: {missing}", file=sys.stderr)
            print(f"Actual failures: {sorted(actual)}", file=sys.stderr)
            return 1
        print("N58 MoM batch verifier PASS (start state)")
        return 0

    if failures:
        for failure in failures:
            print(f"ERROR[{failure['id']}]: {failure.get('detail', '')}", file=sys.stderr)
        return 1

    print("N58 MoM batch verifier PASS (repeated-RHS runtime analytical oracle)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
