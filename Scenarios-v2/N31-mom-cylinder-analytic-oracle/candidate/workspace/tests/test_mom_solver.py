from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mom_solver  # noqa: E402


def main() -> int:
    sample_angles = [2.0 * math.pi * index / 12.0 for index in range(12)]
    result = mom_solver.solve_cylinder_mom(
        radius=0.5,
        wavenumber=4.0,
        segments=64,
        incident_angle=0.35,
        observation_radius=2.0,
        sample_angles=sample_angles,
    )
    if len(result["density"]) != 64:
        print("density length mismatch")
        return 1
    if len(result["field_samples"]) != len(sample_angles):
        print("field sample count mismatch")
        return 1
    if result["boundary_residual_l2"] > 0.01:
        print(f"boundary residual too large: {result['boundary_residual_l2']}")
        return 1
    if result["runtime_seconds"] > 8.0:
        print(f"runtime too large: {result['runtime_seconds']}")
        return 1
    print("N31 MoM local smoke PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
