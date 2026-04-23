from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
from scipy.special import hankel1


def complex_to_json(value: complex) -> dict:
    return {"re": float(np.real(value)), "im": float(np.imag(value))}


def panel_centers(radius: float, segments: int) -> tuple[np.ndarray, np.ndarray]:
    angles = (np.arange(segments, dtype=float) + 0.5) * (2.0 * math.pi / segments)
    points = np.column_stack((radius * np.cos(angles), radius * np.sin(angles)))
    return angles, points


def incident_field(points: np.ndarray, wavenumber: float, incident_angle: float) -> np.ndarray:
    # BUG: this ignores incident_angle and only handles incidence along +x.
    phase = wavenumber * points[:, 0]
    return np.exp(1j * phase)


def build_impedance_matrix(radius: float, wavenumber: float, segments: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    angles, points = panel_centers(radius, segments)
    matrix = np.zeros((segments, segments), dtype=complex)
    for source in range(segments):
        source_point = points[source]
        distances = np.linalg.norm(points - source_point, axis=1)
        distances[source] = radius * 1e-6
        # BUG: midpoint-only integration, missing panel arc length, and a poor self-panel model.
        matrix[:, source] = 0.25j * hankel1(0, wavenumber * distances)
    return matrix, angles, points


def field_from_density(
    observation_points: np.ndarray,
    radius: float,
    wavenumber: float,
    density: np.ndarray,
) -> np.ndarray:
    _angles, source_points = panel_centers(radius, len(density))
    field = np.zeros(len(observation_points), dtype=complex)
    for source, source_point in enumerate(source_points):
        distances = np.linalg.norm(observation_points - source_point, axis=1)
        # BUG: missing panel arc length again.
        field += density[source] * 0.25j * hankel1(0, wavenumber * distances)
    return field


def solve_cylinder_mom(
    radius: float,
    wavenumber: float,
    segments: int,
    incident_angle: float,
    observation_radius: float,
    sample_angles: list[float],
) -> dict:
    started = time.perf_counter()
    matrix, angles, boundary_points = build_impedance_matrix(radius, wavenumber, segments)
    rhs = -incident_field(boundary_points, wavenumber, incident_angle)
    density = np.linalg.solve(matrix, rhs)
    residual = np.linalg.norm(matrix @ density - rhs) / max(np.linalg.norm(rhs), 1e-30)

    obs_angles = np.array(sample_angles, dtype=float)
    observation_points = np.column_stack((
        observation_radius * np.cos(obs_angles),
        observation_radius * np.sin(obs_angles),
    ))
    scattered = field_from_density(observation_points, radius, wavenumber, density)
    total = scattered + incident_field(observation_points, wavenumber, incident_angle)

    samples = []
    for angle, total_value, scattered_value in zip(obs_angles, total, scattered):
        samples.append({
            "angle": float(angle),
            "total": complex_to_json(total_value),
            "scattered": complex_to_json(scattered_value),
        })

    return {
        "radius": float(radius),
        "wavenumber": float(wavenumber),
        "segments": int(segments),
        "incident_angle": float(incident_angle),
        "observation_radius": float(observation_radius),
        "method": "pulse-basis MoM for PEC cylinder TMz EFIE",
        "panel_angles": [float(value) for value in angles],
        "density": [complex_to_json(value) for value in density],
        "boundary_residual_l2": float(residual),
        "field_samples": samples,
        "runtime_seconds": float(time.perf_counter() - started),
    }


def write_validation_report() -> None:
    report = {
        "method": "starter-stale",
        "oracle_use": "starter report has not validated the MoM solve",
        "cases": [],
        "convergence": {},
    }
    Path(__file__).with_name("validation-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    write_validation_report()
