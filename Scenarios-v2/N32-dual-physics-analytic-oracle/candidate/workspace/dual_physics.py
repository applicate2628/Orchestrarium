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
    # BUG: ignores the supplied incident angle.
    return np.exp(1j * wavenumber * points[:, 0])


def solve_cylinder_mom(
    radius: float,
    wavenumber: float,
    segments: int,
    incident_angle: float,
    observation_radius: float,
    sample_angles: list[float],
) -> dict:
    started = time.perf_counter()
    angles, points = panel_centers(radius, segments)
    matrix = np.zeros((segments, segments), dtype=complex)
    for source, source_point in enumerate(points):
        distances = np.linalg.norm(points - source_point, axis=1)
        distances[source] = radius * 1e-6
        # BUG: midpoint-only model, missing panel arc length and self-panel quadrature.
        matrix[:, source] = 0.25j * hankel1(0, wavenumber * distances)

    rhs = -incident_field(points, wavenumber, incident_angle)
    density = np.linalg.solve(matrix, rhs)
    residual = np.linalg.norm(matrix @ density - rhs) / max(np.linalg.norm(rhs), 1e-30)

    obs_angles = np.array(sample_angles, dtype=float)
    observation_points = np.column_stack((
        observation_radius * np.cos(obs_angles),
        observation_radius * np.sin(obs_angles),
    ))
    scattered = np.zeros(len(observation_points), dtype=complex)
    for source, source_point in enumerate(points):
        distances = np.linalg.norm(observation_points - source_point, axis=1)
        scattered += density[source] * 0.25j * hankel1(0, wavenumber * distances)
    total = scattered + incident_field(observation_points, wavenumber, incident_angle)

    return {
        "domain": "electromagnetics",
        "radius": float(radius),
        "wavenumber": float(wavenumber),
        "segments": int(segments),
        "incident_angle": float(incident_angle),
        "observation_radius": float(observation_radius),
        "method": "starter midpoint MoM",
        "panel_angles": [float(value) for value in angles],
        "density": [complex_to_json(value) for value in density],
        "boundary_residual_l2": float(residual),
        "field_samples": [
            {
                "angle": float(angle),
                "total": complex_to_json(value),
            }
            for angle, value in zip(obs_angles, total)
        ],
        "runtime_seconds": float(time.perf_counter() - started),
    }


def solve_hydrogen_radial(
    z: float,
    n: int,
    l: int,
    r_max: float,
    grid_points: int,
    sample_r: list[float],
) -> dict:
    started = time.perf_counter()
    r_grid = np.linspace(r_max / grid_points, r_max, grid_points)
    # BUG: placeholder shape, not a finite-difference eigenstate.
    u_grid = r_grid ** (l + 1) * np.exp(-z * r_grid / max(n, 1))
    norm = float(np.sqrt(np.trapezoid(u_grid * u_grid, r_grid)))
    if norm:
        u_grid = u_grid / norm
    samples = np.interp(np.array(sample_r, dtype=float), r_grid, u_grid)

    return {
        "domain": "hydrogenic-radial-schrodinger",
        "z": float(z),
        "n": int(n),
        "l": int(l),
        "r_max": float(r_max),
        "grid_points": int(grid_points),
        "method": "starter analytic-shaped placeholder",
        "energy": -0.1,
        "r_grid": [float(value) for value in r_grid],
        "u_grid": [float(value) for value in u_grid],
        "normalization": 1.0,
        "residual_l2": 99.0,
        "sample_values": [
            {"r": float(radius), "u": float(value)}
            for radius, value in zip(sample_r, samples)
        ],
        "runtime_seconds": float(time.perf_counter() - started),
    }


def write_validation_report() -> None:
    report = {
        "method": "starter-stale",
        "oracle_use": "starter report has not validated either physics solver",
        "cases": [],
        "performance": {},
        "convergence": {},
    }
    Path(__file__).with_name("validation-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    write_validation_report()
