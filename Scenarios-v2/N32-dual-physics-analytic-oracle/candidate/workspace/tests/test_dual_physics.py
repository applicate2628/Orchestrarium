from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dual_physics  # noqa: E402


def main() -> int:
    angles = [2.0 * math.pi * index / 8.0 for index in range(8)]
    em = dual_physics.solve_cylinder_mom(
        radius=0.5,
        wavenumber=4.0,
        segments=32,
        incident_angle=0.35,
        observation_radius=2.0,
        sample_angles=angles,
    )
    if len(em["density"]) != 32:
        print("EM density length mismatch")
        return 1
    if len(em["field_samples"]) != len(angles):
        print("EM field sample length mismatch")
        return 1

    sample_r = [2.0, 4.0, 8.0, 12.0]
    radial = dual_physics.solve_hydrogen_radial(
        z=1.0,
        n=2,
        l=1,
        r_max=35.0,
        grid_points=300,
        sample_r=sample_r,
    )
    if len(radial["r_grid"]) != 300 or len(radial["u_grid"]) != 300:
        print("radial grid length mismatch")
        return 1
    if len(radial["sample_values"]) != len(sample_r):
        print("radial sample length mismatch")
        return 1

    print("N32 dual physics local smoke PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
