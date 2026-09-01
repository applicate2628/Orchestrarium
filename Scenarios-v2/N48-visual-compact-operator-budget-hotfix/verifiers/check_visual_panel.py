#!/usr/bin/env python3

from __future__ import annotations

import os
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


RGB = tuple[int, int, int]

PALETTE: dict[int, RGB] = {
    -2: (29, 78, 216),
    -1: (147, 197, 253),
    0: (248, 250, 252),
    1: (252, 165, 165),
    2: (220, 38, 38),
}
BACKGROUND: RGB = (17, 19, 24)
FOCUS_RING: RGB = (250, 204, 21)
ADDITIVE_HIGHLIGHT: RGB = (30, 24, 0)
FULL_FRAME_MISMATCH_TOLERANCE = 2


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N48 visual raster panel bundle.")
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
    require(actual_entries == sorted(contract["required_top_level_entries"]), f"Top-level bundle entries drifted: {actual_entries}", errors)
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)


def import_candidate_module(root: Path):
    exec_root = Path(os.environ["BENCH_EXEC_ROOT"]).resolve() if os.environ.get("BENCH_EXEC_ROOT") else root
    module_path = exec_root / "candidate" / "visual-owned" / "src" / "visual_panel" / "renderer.py"
    spec = importlib.util.spec_from_file_location("N48_candidate_renderer", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import candidate module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hex_to_rgb(value: str) -> RGB:
    cleaned = value.strip().lstrip("#")
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def fill_rect(frame: list[list[RGB]], left: int, top: int, width: int, height: int, color: RGB) -> None:
    for y in range(max(0, top), min(len(frame), top + height)):
        for x in range(max(0, left), min(len(frame[y]), left + width)):
            frame[y][x] = color


def add_rgb(base: RGB, delta: RGB) -> RGB:
    return tuple(min(255, base[index] + delta[index]) for index in range(3))


def reference_render(spec: dict) -> list[list[RGB]]:
    width = int(spec["width"])
    height = int(spec["height"])
    background = hex_to_rgb(spec["background"])
    frame = [[background for _ in range(width)] for _ in range(height)]
    grid = spec["grid"]
    cell = int(grid["cell"])
    gap = int(grid["gap"])
    x0 = int(grid["x"])
    y0 = int(grid["y"])
    selected = spec["selected"]

    for row_index, row in enumerate(spec["values"]):
        for col_index, raw_value in enumerate(row):
            if raw_value is None:
                continue
            left = x0 + col_index * (cell + gap)
            top = y0 + row_index * (cell + gap)
            fill_rect(frame, left, top, cell, cell, PALETTE[int(raw_value)])

    selected_left = x0 + int(selected["col"]) * (cell + gap)
    selected_top = y0 + int(selected["row"]) * (cell + gap)
    selected_value = spec["values"][int(selected["row"])][int(selected["col"])]
    selected_base = PALETTE[int(selected_value)]
    for offset in range(cell):
        frame[selected_top][selected_left + offset] = FOCUS_RING
        frame[selected_top + cell - 1][selected_left + offset] = FOCUS_RING
        frame[selected_top + offset][selected_left] = FOCUS_RING
        frame[selected_top + offset][selected_left + cell - 1] = FOCUS_RING
    frame[selected_top + cell // 2][selected_left + cell // 2] = add_rgb(selected_base, ADDITIVE_HIGHLIGHT)

    legend = spec["legend"]
    for index, value in enumerate(legend["values"]):
        fill_rect(frame, int(legend["x"]), int(legend["y"]) + index, int(legend["width"]), 1, PALETTE[int(value)])

    for annotation in spec["annotations"]:
        frame[int(annotation["y"])][int(annotation["x"])] = hex_to_rgb(annotation["color"])

    return frame


def load_case(root: Path) -> dict:
    return load_json(root / "inputs" / "panel-cases.json")["cases"][0]


def evaluate(root: Path):
    module = import_candidate_module(root)
    case = load_case(root)
    actual = module.render_panel(case)
    expected = reference_render(case)
    failures = set()

    if len(actual) != len(expected) or any(len(row) != len(expected[0]) for row in actual):
        failures.add("frame-shape")
        return sorted(failures)

    if actual[6][6] != BACKGROUND:
        failures.add("missing-transparent-gap")
    if actual[5][13] != FOCUS_RING or actual[6][14] != (250, 62, 38):
        failures.add("wrong-selected-layer")
    for y in range(1, 6):
        if actual[y][18] != expected[y][18] or actual[y][19] != expected[y][19]:
            failures.add("legend-not-zero-centered")
            break
    if actual[2][20] != (34, 197, 94) or actual[0][0] != FOCUS_RING:
        failures.add("missing-focus-annotation")

    try:
        ppm_lines = module.export_ppm(actual).splitlines()
    except Exception:  # noqa: BLE001 - report compact verifier failure.
        failures.add("ppm-metadata")
    else:
        if ppm_lines[:3] != ["P3", "22 15", "255"]:
            failures.add("ppm-metadata")
        else:
            channel_count = sum(len(line.split()) for line in ppm_lines[3:])
            if channel_count != 22 * 15 * 3:
                failures.add("ppm-metadata")

    if actual != expected:
        witness_points = [
            (2, 2),
            (6, 6),
            (13, 5),
            (14, 6),
            (18, 1),
            (18, 3),
            (20, 2),
        ]
        if any(actual[y][x] != expected[y][x] for x, y in witness_points):
            failures.add("witness-points")

        mismatch_count = sum(
            1
            for y in range(len(expected))
            for x in range(len(expected[0]))
            if actual[y][x] != expected[y][x]
        )
        if mismatch_count > FULL_FRAME_MISMATCH_TOLERANCE:
            failures.add("full-frame-mismatch")

    return sorted(failures)


def run_direct_tests(root: Path, errors: list[str]):
    exec_root = Path(os.environ["BENCH_EXEC_ROOT"]).resolve() if os.environ.get("BENCH_EXEC_ROOT") else root
    workspace = exec_root / "candidate" / "visual-owned"
    result = subprocess.run(
        [sys.executable, "tests/test_renderer.py"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    require(result.returncode == 0, f"Local renderer tests failed: {combined or 'no output'}", errors)


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "visual-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate(root)
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failures == expected, f"Expected start-state failures {expected}, found {failures}", errors)
        else:
            run_direct_tests(root, errors)
            require(not failures, f"Completed candidate still fails visual checks: {failures}", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        mode = "bundle shape"
    elif args.expect_start_state:
        mode = "start state"
    else:
        mode = "completed run"
    print(f"N48 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
