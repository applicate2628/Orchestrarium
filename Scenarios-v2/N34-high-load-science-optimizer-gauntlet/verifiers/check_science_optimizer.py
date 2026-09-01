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
from scipy.special import eval_genlaguerre, factorial, hankel1, jv


LAST_METRICS: dict = {}


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N34 staged high-load science optimizer bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
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


def import_candidate(root: Path):
    exec_root = Path(os.environ["BENCH_EXEC_ROOT"]).resolve() if os.environ.get("BENCH_EXEC_ROOT") else root
    solver_path = exec_root / "candidate" / "workspace" / "dual_physics.py"
    spec = importlib.util.spec_from_file_location("n34_candidate_dual_physics", solver_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import candidate from {solver_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def static_solver_failures(root: Path, contract: dict) -> list[dict]:
    text = (root / "candidate" / "workspace" / "dual_physics.py").read_text(encoding="utf-8").lower()
    failures = []
    for marker in contract["forbidden_solver_markers"]:
        if marker.lower() in text:
            failures.append({"id": "solver-forbidden-marker", "detail": marker})
    for group_id, markers in contract["required_solver_marker_groups"].items():
        if not any(marker.lower() in text for marker in markers):
            failures.append({"id": f"solver-missing-marker-{group_id}", "detail": ", ".join(markers)})
    return failures


def sample_angles(count: int) -> list[float]:
    return [2.0 * math.pi * index / count for index in range(count)]


def sample_radii(r_max: float, count: int) -> list[float]:
    start = max(0.06 * r_max, 0.35)
    stop = 0.84 * r_max
    return [float(value) for value in np.linspace(start, stop, count)]


def parse_complex(value):
    if isinstance(value, complex):
        return value
    if isinstance(value, dict):
        return complex(float(value.get("re", 0.0)), float(value.get("im", 0.0)))
    if isinstance(value, list) and len(value) == 2:
        return complex(float(value[0]), float(value[1]))
    raise ValueError(f"Cannot parse complex value: {value!r}")


def boundary_points(radius: float, segments: int) -> tuple[np.ndarray, np.ndarray]:
    angles = (np.arange(segments, dtype=float) + 0.5) * (2.0 * math.pi / segments)
    points = np.column_stack((radius * np.cos(angles), radius * np.sin(angles)))
    return angles, points


def incident_field(points: np.ndarray, wavenumber: float, incident_angle: float) -> np.ndarray:
    phase = wavenumber * (points[:, 0] * math.cos(incident_angle) + points[:, 1] * math.sin(incident_angle))
    return np.exp(1j * phase)


def build_mom_matrix(radius: float, wavenumber: float, segments: int, quadrature_order: int):
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


def field_from_density(observation_points: np.ndarray, radius: float, wavenumber: float, density: np.ndarray, quadrature_order: int):
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


def analytic_total_field(observation_points: np.ndarray, radius: float, wavenumber: float, incident_angle: float, series_terms: int):
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


def analytic_density_coefficients(radius: float, wavenumber: float, incident_angle: float, modes: np.ndarray):
    coeffs = []
    for order in modes:
        coeffs.append(-2.0 * (1j ** int(order)) * np.exp(-1j * int(order) * incident_angle) / (1j * math.pi * radius * hankel1(int(order), wavenumber * radius)))
    return np.array(coeffs, dtype=complex)


def density_coefficients_from_samples(density: np.ndarray, angles: np.ndarray, modes: np.ndarray):
    coeffs = []
    for order in modes:
        coeffs.append(np.mean(density * np.exp(-1j * int(order) * angles)))
    return np.array(coeffs, dtype=complex)


def check_em_case(module, contract_case: dict):
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
        return {}, [{"id": f"em-case-{case_id}", "detail": "solver did not return a dictionary"}]

    required = [
        "domain",
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
    ]
    missing = [key for key in required if key not in result]
    if missing:
        return result, [{"id": f"em-case-{case_id}", "detail": f"missing keys {missing}"}]

    try:
        density = np.array([parse_complex(value) for value in result["density"]], dtype=complex)
    except Exception as exc:  # noqa: BLE001
        return result, [{"id": f"em-case-{case_id}", "detail": f"density parse failed: {exc}"}]
    if len(density) != segments:
        return result, [{"id": f"em-case-{case_id}", "detail": f"density length {len(density)} != {segments}"}]
    if not np.all(np.isfinite(np.real(density))) or not np.all(np.isfinite(np.imag(density))):
        return result, [{"id": f"em-case-{case_id}", "detail": "density has non-finite values"}]

    matrix, panel_angles, collocation_points = build_mom_matrix(
        radius,
        wavenumber,
        segments,
        int(contract_case["matrix_quadrature_order"]),
    )
    rhs = -incident_field(collocation_points, wavenumber, incident_angle)
    boundary_residual = float(np.linalg.norm(matrix @ density - rhs) / max(np.linalg.norm(rhs), 1e-30))
    reported_residual = float(result.get("boundary_residual_l2", 999.0))
    if max(boundary_residual, reported_residual) > float(contract_case["max_boundary_residual_l2"]):
        failures.append({
            "id": f"em-case-{case_id}",
            "detail": f"boundary residual {max(boundary_residual, reported_residual):.8g}",
        })

    observation_angles = np.array(angles, dtype=float)
    observation_points = np.column_stack((
        observation_radius * np.cos(observation_angles),
        observation_radius * np.sin(observation_angles),
    ))
    total = field_from_density(
        observation_points,
        radius,
        wavenumber,
        density,
        int(contract_case["field_quadrature_order"]),
    ) + incident_field(observation_points, wavenumber, incident_angle)
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
            "id": f"em-case-{case_id}",
            "detail": f"relative field error {relative_field_error:.8g}",
        })

    modes = np.arange(-int(contract_case["density_modes"]), int(contract_case["density_modes"]) + 1)
    observed_modes = density_coefficients_from_samples(density, panel_angles, modes)
    exact_modes = analytic_density_coefficients(radius, wavenumber, incident_angle, modes)
    density_mode_error = float(np.linalg.norm(observed_modes - exact_modes) / max(np.linalg.norm(exact_modes), 1e-30))
    if density_mode_error > float(contract_case["max_density_mode_error"]):
        failures.append({
            "id": f"em-density-{case_id}",
            "detail": f"density Fourier error {density_mode_error:.8g}",
        })

    runtime_seconds = max(wall_seconds, float(result.get("runtime_seconds", 0.0)))
    if runtime_seconds > float(contract_case["max_runtime_seconds"]):
        failures.append({
            "id": f"em-runtime-{case_id}",
            "detail": f"runtime {runtime_seconds:.3f}s exceeds {contract_case['max_runtime_seconds']}s",
        })

    field_samples = result.get("field_samples")
    if not isinstance(field_samples, list) or len(field_samples) != len(angles):
        failures.append({"id": f"em-case-{case_id}", "detail": "field sample count mismatch"})

    metrics = {
        "domain": "em",
        "case_id": case_id,
        "boundary_residual_l2": boundary_residual,
        "relative_field_error": relative_field_error,
        "density_mode_error": density_mode_error,
        "runtime_seconds": runtime_seconds,
    }
    return metrics, failures


def exact_hydrogen_energy(z: float, n: int):
    return -(z * z) / (2.0 * n * n)


def exact_u_grid(z: float, n: int, l: int, r: np.ndarray):
    rho = 2.0 * z * r / n
    prefactor = math.sqrt((2.0 * z / n) ** 3 * float(factorial(n - l - 1, exact=False)) / (2.0 * n * float(factorial(n + l, exact=False))))
    radial = prefactor * np.exp(-rho / 2.0) * np.power(rho, l) * eval_genlaguerre(n - l - 1, 2 * l + 1, rho)
    u = r * radial
    norm = math.sqrt(float(np.trapezoid(u * u, r)))
    if norm > 0:
        u = u / norm
    return u


def radial_residual_l2(z: float, l: int, energy: float, r: np.ndarray, u: np.ndarray):
    if len(r) < 5:
        return float("inf")
    drs = np.diff(r)
    if float(np.max(np.abs(drs - drs[0]))) > 1e-8:
        return float("inf")
    dr = float(drs[0])
    potential = l * (l + 1) / (2.0 * r * r) - z / r
    diag = 1.0 / (dr * dr) + potential
    off = -0.5 / (dr * dr)
    hu = diag * u
    hu[1:] += off * u[:-1]
    hu[:-1] += off * u[1:]
    residual = hu - energy * u
    return float(np.linalg.norm(residual) / max(np.linalg.norm(energy * u), 1e-30))


def check_hydrogen_case(module, contract_case: dict):
    failures = []
    case_id = contract_case["case_id"]
    z = float(contract_case["z"])
    n = int(contract_case["n"])
    l = int(contract_case["l"])
    r_max = float(contract_case["r_max"])
    grid_points = int(contract_case["grid_points"])
    samples = sample_radii(r_max, int(contract_case["sample_count"]))

    started = time.perf_counter()
    result = module.solve_hydrogen_radial(
        z=z,
        n=n,
        l=l,
        r_max=r_max,
        grid_points=grid_points,
        sample_r=samples,
    )
    wall_seconds = time.perf_counter() - started
    if not isinstance(result, dict):
        return {}, [{"id": f"hydrogen-case-{case_id}", "detail": "solver did not return a dictionary"}]

    required = [
        "domain",
        "z",
        "n",
        "l",
        "r_max",
        "grid_points",
        "method",
        "energy",
        "r_grid",
        "u_grid",
        "normalization",
        "residual_l2",
        "sample_values",
        "runtime_seconds",
    ]
    missing = [key for key in required if key not in result]
    if missing:
        return result, [{"id": f"hydrogen-case-{case_id}", "detail": f"missing keys {missing}"}]

    try:
        r = np.array(result["r_grid"], dtype=float)
        u = np.array(result["u_grid"], dtype=float)
        energy = float(result["energy"])
    except Exception as exc:  # noqa: BLE001
        return result, [{"id": f"hydrogen-case-{case_id}", "detail": f"array parse failed: {exc}"}]
    if len(r) != grid_points or len(u) != grid_points:
        return result, [{"id": f"hydrogen-case-{case_id}", "detail": "grid length mismatch"}]
    if not np.all(np.isfinite(r)) or not np.all(np.isfinite(u)) or not np.all(np.diff(r) > 0):
        return result, [{"id": f"hydrogen-case-{case_id}", "detail": "invalid radial grid or wavefunction"}]

    norm = math.sqrt(float(np.trapezoid(u * u, r)))
    if not math.isfinite(norm) or abs(norm - 1.0) > 0.02:
        failures.append({"id": f"hydrogen-case-{case_id}", "detail": f"normalization {norm:.8g}"})
    if norm > 0:
        u = u / norm

    exact_energy = exact_hydrogen_energy(z, n)
    energy_abs_error = abs(energy - exact_energy)
    if energy_abs_error > float(contract_case["max_energy_abs_error"]):
        failures.append({"id": f"hydrogen-case-{case_id}", "detail": f"energy error {energy_abs_error:.8g}"})

    exact_u = exact_u_grid(z, n, l, r)
    dot = float(np.dot(u, exact_u))
    if dot < 0:
        u = -u
    wave_l2_error = float(np.linalg.norm(u - exact_u) / max(np.linalg.norm(exact_u), 1e-30))
    if wave_l2_error > float(contract_case["max_wave_l2_error"]):
        failures.append({"id": f"hydrogen-case-{case_id}", "detail": f"wave L2 error {wave_l2_error:.8g}"})

    residual_l2 = radial_residual_l2(z, l, energy, r, u)
    reported_residual = float(result.get("residual_l2", 999.0))
    if max(residual_l2, reported_residual) > float(contract_case["max_residual_l2"]):
        failures.append({"id": f"hydrogen-case-{case_id}", "detail": f"residual {max(residual_l2, reported_residual):.8g}"})

    sample_values = result.get("sample_values")
    if not isinstance(sample_values, list) or len(sample_values) != len(samples):
        failures.append({"id": f"hydrogen-case-{case_id}", "detail": "sample count mismatch"})

    runtime_seconds = max(wall_seconds, float(result.get("runtime_seconds", 0.0)))
    if runtime_seconds > float(contract_case["max_runtime_seconds"]):
        failures.append({
            "id": f"hydrogen-runtime-{case_id}",
            "detail": f"runtime {runtime_seconds:.3f}s exceeds {contract_case['max_runtime_seconds']}s",
        })

    metrics = {
        "domain": "hydrogen",
        "case_id": case_id,
        "energy_abs_error": energy_abs_error,
        "wave_l2_error": wave_l2_error,
        "residual_l2": residual_l2,
        "runtime_seconds": runtime_seconds,
    }
    return metrics, failures


def check_report(root: Path, contract: dict, metrics: list[dict]) -> list[dict]:
    failures = []
    try:
        report = load_json(root / "candidate" / "optimization-report.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "report-json-invalid", "detail": str(exc)}]

    for field in contract["required_report_fields"]:
        if field not in report:
            failures.append({"id": "report-missing-fields", "detail": field})

    if report.get("method") != "high-load dual numerical physics optimizer: MoM PEC cylinder plus tridiagonal hydrogenic radial solver":
        failures.append({"id": "report-method", "detail": str(report.get("method"))})
    if report.get("oracle_use") != "analytical cylinder and hydrogenic formulas used only for verifier validation":
        failures.append({"id": "report-oracle-use", "detail": str(report.get("oracle_use"))})

    cases = report.get("cases")
    if not isinstance(cases, list):
        failures.append({"id": "report-missing-cases", "detail": "cases is not a list"})
        return failures
    by_id = {case.get("case_id"): case for case in cases if isinstance(case, dict)}
    missing = sorted(set(contract["required_case_ids"]) - set(by_id))
    if missing:
        failures.append({"id": "report-missing-cases", "detail": str(missing)})

    metric_by_id = {item["case_id"]: item for item in metrics}
    for case_id in contract["required_case_ids"]:
        if case_id not in by_id or case_id not in metric_by_id:
            continue
        report_case = by_id[case_id]
        metric = metric_by_id[case_id]
        if "runtime_seconds" not in report_case:
            failures.append({"id": "report-case-values", "detail": f"{case_id}: missing runtime"})
        elif float(report_case["runtime_seconds"]) < 0:
            failures.append({"id": "report-case-values", "detail": f"{case_id}: negative runtime"})

    performance = report.get("performance")
    if not isinstance(performance, dict) or "total_solver_runtime_seconds" not in performance:
        failures.append({"id": "report-performance", "detail": "missing total solver runtime"})
    stage_trace = report.get("stage_trace")
    trace_ids = set()
    if isinstance(stage_trace, list):
        for item in stage_trace:
            if isinstance(item, dict):
                trace_ids.add(item.get("id"))
            elif isinstance(item, str):
                trace_ids.add(item)
    if set(contract["required_stage_ids"]) - trace_ids:
        failures.append({"id": "report-stage-trace", "detail": "missing required stage ids"})

    return failures


def as_json_text(value) -> str:
    return json.dumps(value, sort_keys=True).lower()


def find_stage(stage_state: dict, phase_id: str):
    for item in stage_state.get("phases", []):
        if isinstance(item, dict) and item.get("id") == phase_id:
            return item
    return None


def check_stage_state(root: Path, contract: dict) -> list[dict]:
    failures = []
    try:
        stage_state = load_json(root / "candidate" / "stage-state.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "stage-ledger-json-invalid", "detail": str(exc)}]

    text = as_json_text(stage_state)
    if stage_state.get("plan_fingerprint") != contract["plan_fingerprint"]:
        failures.append({"id": "stage-ledger-incomplete", "detail": "plan fingerprint mismatch"})
    for phase_id in contract["required_stage_ids"]:
        phase = find_stage(stage_state, phase_id)
        if not phase or str(phase.get("status", "")).lower() not in {"complete", "completed", "pass", "passed"}:
            failures.append({"id": "stage-ledger-incomplete", "detail": f"missing complete phase {phase_id}"})
            break
        if not phase.get("owner") or not phase.get("source_cues") or not phase.get("affected_artifacts") or not phase.get("visible_return_cue"):
            failures.append({"id": "stage-ledger-incomplete", "detail": f"incomplete fields for {phase_id}"})
            break
    for cue in contract["required_stage_source_cues"]:
        if cue.lower() not in text:
            failures.append({"id": "stage-ledger-incomplete", "detail": f"missing cue {cue}"})
            break
    for path in contract["required_artifact_paths"]:
        if path.lower() not in text:
            failures.append({"id": "stage-ledger-incomplete", "detail": f"missing artifact {path}"})
            break
    reentry = stage_state.get("reentry")
    if not isinstance(reentry, dict) or reentry.get("last_completed_phase") != contract["required_stage_ids"][-1]:
        failures.append({"id": "stage-ledger-incomplete", "detail": "reentry last_completed_phase mismatch"})
    return failures


def check_perf_ledger(root: Path, contract: dict, metrics: list[dict]) -> list[dict]:
    failures = []
    try:
        ledger = load_json(root / "candidate" / "workspace" / "perf-ledger.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "perf-ledger-json-invalid", "detail": str(exc)}]

    text = as_json_text(ledger)
    if ledger.get("plan_fingerprint") != contract["plan_fingerprint"]:
        failures.append({"id": "perf-ledger-incomplete", "detail": "plan fingerprint mismatch"})
    for phase_id in contract["required_stage_ids"]:
        if phase_id.lower() not in text:
            failures.append({"id": "perf-ledger-incomplete", "detail": f"missing phase {phase_id}"})
            break
    required_cases = set(contract["required_case_ids"])
    measurements = ledger.get("measurements", [])
    measured_cases = {item.get("case_id") for item in measurements if isinstance(item, dict)}
    missing_cases = sorted(required_cases - measured_cases)
    if missing_cases:
        failures.append({"id": "perf-ledger-incomplete", "detail": f"missing cases {missing_cases}"})
    budgets = ledger.get("budgets")
    if not isinstance(budgets, dict) or "max_total_solver_runtime_seconds" not in budgets:
        failures.append({"id": "perf-ledger-incomplete", "detail": "missing total runtime budget"})
    scaling = ledger.get("scaling")
    if not isinstance(scaling, dict) or "em_segments" not in scaling or "hydrogen_grid_points" not in scaling:
        failures.append({"id": "perf-ledger-incomplete", "detail": "missing scaling dimensions"})

    reported_total = ledger.get("total_solver_runtime_seconds", budgets.get("total_solver_runtime_seconds") if isinstance(budgets, dict) else None)
    if reported_total is not None and float(reported_total) < 0:
        failures.append({"id": "perf-ledger-values", "detail": "negative total runtime"})
    return failures


def check_notes(root: Path, contract: dict) -> list[dict]:
    text = (root / "candidate" / "workspace" / "validation-notes.md").read_text(encoding="utf-8").lower()
    missing = [phrase for phrase in contract["required_notes_phrases"] if phrase.lower() not in text]
    if missing:
        return [{"id": "notes-missing-phrases", "detail": ", ".join(missing)}]
    return []


def evaluate_with_metrics(root: Path, contract: dict):
    failures = static_solver_failures(root, contract)
    metrics: list[dict] = []

    try:
        module = import_candidate(root)
    except Exception as exc:  # noqa: BLE001
        return failures + [{"id": "solver-import-failed", "detail": str(exc)}], metrics

    if not hasattr(module, contract["em_solver_api"]):
        failures.append({"id": "solver-api-missing", "detail": contract["em_solver_api"]})
    if not hasattr(module, contract["hydrogen_solver_api"]):
        failures.append({"id": "solver-api-missing", "detail": contract["hydrogen_solver_api"]})
    if any(failure["id"] == "solver-api-missing" for failure in failures):
        return failures, metrics

    for contract_case in contract["em_cases"]:
        case_metrics, case_failures = check_em_case(module, contract_case)
        if case_metrics:
            metrics.append(case_metrics)
        failures.extend(case_failures)

    convergence = contract["em_convergence"]
    coarse_case = dict(convergence["coarse"])
    coarse_case["case_id"] = "em-convergence-coarse"
    coarse_case["max_boundary_residual_l2"] = 0.03
    coarse_case["max_relative_field_error"] = 0.06
    coarse_case["max_density_mode_error"] = 0.25
    coarse_case["max_runtime_seconds"] = 3.0
    coarse_case["density_modes"] = 14
    coarse_metrics, coarse_failures = check_em_case(module, coarse_case)
    if coarse_metrics:
        metrics.append(coarse_metrics)
    refined = next((item for item in metrics if item.get("case_id") == convergence["refined_case_id"]), None)
    if coarse_metrics and refined:
        improvement = coarse_metrics["relative_field_error"] / max(refined["relative_field_error"], 1e-30)
        metrics.append({"domain": "em", "case_id": "em-convergence", "field_error_improvement_ratio": improvement, "runtime_seconds": 0.0})
        if improvement < float(convergence["min_field_error_improvement_ratio"]):
            failures.append({"id": "em-convergence-failed", "detail": f"improvement {improvement:.8g}"})
    failures.extend(coarse_failures)

    for contract_case in contract["hydrogen_cases"]:
        case_metrics, case_failures = check_hydrogen_case(module, contract_case)
        if case_metrics:
            metrics.append(case_metrics)
        failures.extend(case_failures)

    total_runtime = sum(float(item.get("runtime_seconds", 0.0)) for item in metrics if item.get("case_id") != "em-convergence")
    metrics.append({"domain": "all", "case_id": "total-solver-runtime", "runtime_seconds": total_runtime})
    if total_runtime > float(contract["max_total_solver_runtime_seconds"]):
        failures.append({"id": "solver-total-runtime", "detail": f"total runtime {total_runtime:.3f}s"})

    failures.extend(check_stage_state(root, contract))
    failures.extend(check_perf_ledger(root, contract, metrics))
    failures.extend(check_report(root, contract, metrics))
    failures.extend(check_notes(root, contract))
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

    shape_errors: list[str] = []
    check_shape(root, contract, shape_errors)
    if shape_errors:
        for error in shape_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N34 verifier PASS (bundle shape)")
        return 0

    failures, metrics = evaluate_with_metrics(root, contract)
    if args.metrics_out:
        args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_out.write_text(json.dumps({"metrics": metrics, "failures": failures}, indent=2) + "\n", encoding="utf-8")

    if args.expect_start_state:
        expected = set(contract["expected_start_state_failures"])
        actual = {failure["id"] for failure in failures}
        missing = sorted(expected - actual)
        if missing:
            print(f"ERROR: expected start-state failures missing: {missing}", file=sys.stderr)
            print(f"Actual failures: {sorted(actual)}", file=sys.stderr)
            return 1
        print("N34 verifier PASS (start state)")
        return 0

    if failures:
        for failure in failures:
            print(f"ERROR[{failure['id']}]: {failure.get('detail', '')}", file=sys.stderr)
        return 1

    print("N34 verifier PASS (staged high-load science optimizer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
