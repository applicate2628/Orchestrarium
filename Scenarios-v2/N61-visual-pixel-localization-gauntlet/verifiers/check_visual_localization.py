#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = ["README.md", "candidate", "inputs", "oracle", "scenario.yaml", "verifiers"]
REQUIRED_POINTS = ["red", "cyan", "lime", "magenta", "amber", "blue"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check N61 visual pixel localization answers.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--answer-file", type=Path)
    parser.add_argument("--metrics-out", type=Path)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            data.setdefault(current_key or "", []).append(strip_quotes(line[4:].strip()))
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


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_shape(root: Path, errors: list[str]) -> None:
    actual = sorted(path.name for path in root.iterdir())
    require(actual == sorted(REQUIRED_TOP_LEVEL), f"Top-level bundle entries drifted: {actual}", errors)

    scenario = parse_simple_yaml(root / "scenario.yaml")
    require(scenario.get("id") == "N61", "scenario.yaml id mismatch", errors)
    require(scenario.get("surface_id") == "E51", "scenario.yaml surface_id mismatch", errors)
    require("image-localization" in scenario.get("overlay_flags", []), "scenario.yaml missing image-localization flag", errors)

    required_paths = [
        "inputs/task.md",
        "inputs/visual-localization-canvas.png",
        "oracle/answer-schema.json",
        "oracle/localization-oracle.json",
        "oracle/scoring-anchors.md",
        "candidate/answer.json",
        "verifiers/check_visual_localization.py",
    ]
    for relative in required_paths:
        require((root / relative).exists(), f"Missing required path: {relative}", errors)

    oracle = load_json(root / "oracle" / "localization-oracle.json")
    require(oracle.get("scenario_id") == "N61", "oracle scenario_id mismatch", errors)
    require(oracle.get("image_id") == "N61-visual-localization-canvas-v1", "oracle image_id mismatch", errors)
    require(oracle.get("image", {}).get("width") == 2200, "oracle width mismatch", errors)
    require(oracle.get("image", {}).get("height") == 1600, "oracle height mismatch", errors)
    target_ids = [target.get("id") for target in oracle.get("targets", [])]
    require(target_ids == REQUIRED_POINTS, f"oracle target ids mismatch: {target_ids}", errors)
    thresholds = oracle.get("thresholds", {})
    require(thresholds.get("pass_mean_px") == 5.0, "oracle pass_mean_px mismatch", errors)
    require(thresholds.get("pass_max_px") == 8.0, "oracle pass_max_px mismatch", errors)


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        value = None
        for match in re.finditer(r"\{", stripped):
            try:
                candidate, _ = decoder.raw_decode(stripped[match.start() :])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                value = candidate
                break
        if value is None:
            raise ValueError("No JSON object found in answer text") from None
    if not isinstance(value, dict):
        raise ValueError("Answer root must be a JSON object")
    return value


def normalize_point(raw: Any, forced_id: str | None = None) -> tuple[str, float, float]:
    if not isinstance(raw, dict):
        raise ValueError("point entries must be objects")
    target_id = forced_id or str(raw.get("id", "")).strip().lower()
    if not target_id:
        raise ValueError("point entry missing id")
    try:
        x = float(raw["x"])
        y = float(raw["y"])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"point {target_id!r} must contain numeric x and y") from None
    return target_id, x, y


def collect_points(raw_points: Any) -> tuple[list[tuple[str, float, float]], list[str]]:
    format_errors: list[str] = []
    points: list[tuple[str, float, float]] = []

    if isinstance(raw_points, dict):
        for target_id, raw_point in raw_points.items():
            try:
                points.append(normalize_point(raw_point, forced_id=str(target_id).strip().lower()))
            except ValueError as exc:
                format_errors.append(str(exc))
        return points, format_errors

    if isinstance(raw_points, list):
        for raw_point in raw_points:
            try:
                points.append(normalize_point(raw_point))
            except ValueError as exc:
                format_errors.append(str(exc))
        return points, format_errors

    format_errors.append("points must be an object keyed by target id")
    return points, format_errors


def score_answer(root: Path, answer_path: Path) -> dict[str, Any]:
    oracle = load_json(root / "oracle" / "localization-oracle.json")
    answer = extract_json_object(answer_path.read_text(encoding="utf-8", errors="replace"))

    expected = {
        target["id"]: (float(target["center"]["x"]), float(target["center"]["y"]))
        for target in oracle["targets"]
    }
    seen: dict[str, tuple[float, float]] = {}
    grouped: dict[str, list[tuple[float, float]]] = {}
    duplicate_ids: list[str] = []
    unknown_ids: list[str] = []

    normalized_points, format_errors = collect_points(answer.get("points"))
    for target_id, x, y in normalized_points:
        if target_id not in expected:
            unknown_ids.append(target_id)
            continue
        grouped.setdefault(target_id, []).append((x, y))
        if target_id in seen:
            duplicate_ids.append(target_id)
            continue
        seen[target_id] = (x, y)

    errors_by_id: dict[str, float | None] = {}
    distances: list[float] = []
    best_duplicate_errors_by_id: dict[str, float | None] = {}
    best_duplicate_distances: list[float] = []
    for target_id in REQUIRED_POINTS:
        if target_id not in seen:
            errors_by_id[target_id] = None
        else:
            actual_x, actual_y = seen[target_id]
            expected_x, expected_y = expected[target_id]
            distance = math.hypot(actual_x - expected_x, actual_y - expected_y)
            errors_by_id[target_id] = round(distance, 3)
            distances.append(distance)

        if target_id not in grouped:
            best_duplicate_errors_by_id[target_id] = None
            continue
        expected_x, expected_y = expected[target_id]
        best_distance = min(math.hypot(x - expected_x, y - expected_y) for x, y in grouped[target_id])
        best_duplicate_errors_by_id[target_id] = round(best_distance, 3)
        best_duplicate_distances.append(best_distance)

    missing_ids = [target_id for target_id in REQUIRED_POINTS if target_id not in seen]
    mean_error = sum(distances) / len(distances) if distances else float("inf")
    max_error = max(distances) if distances else float("inf")
    best_duplicate_mean_error = (
        sum(best_duplicate_distances) / len(best_duplicate_distances)
        if best_duplicate_distances
        else float("inf")
    )
    best_duplicate_max_error = max(best_duplicate_distances) if best_duplicate_distances else float("inf")
    thresholds = oracle["thresholds"]
    passed = (
        not missing_ids
        and not duplicate_ids
        and not unknown_ids
        and not format_errors
        and mean_error <= float(thresholds["pass_mean_px"])
        and max_error <= float(thresholds["pass_max_px"])
    )

    finite_mean = mean_error if math.isfinite(mean_error) else 1000.0
    finite_max = max_error if math.isfinite(max_error) else 1000.0
    within_window_count = sum(
        1
        for distance in best_duplicate_errors_by_id.values()
        if distance is not None and distance <= float(thresholds["pass_max_px"])
    )
    format_penalty = (5.0 * len(missing_ids)) + (3.0 * len(duplicate_ids)) + (4.0 * len(unknown_ids))
    score_components = {
        "coverage": round(20.0 * (len(best_duplicate_distances) / len(REQUIRED_POINTS)), 3),
        "format": round(max(0.0, 20.0 - format_penalty), 3),
        "within_window": round(20.0 * (within_window_count / len(REQUIRED_POINTS)), 3),
        "mean_error": round(25.0 * max(0.0, 1.0 - (finite_mean / 200.0)), 3),
        "max_error": round(15.0 * max(0.0, 1.0 - (finite_max / 300.0)), 3),
    }
    score = max(0.0, min(100.0, sum(score_components.values())))

    return {
        "scenario_id": "N61",
        "image_id": oracle["image_id"],
        "verdict": "PASS" if passed else "FAIL",
        "passed": passed,
        "mean_error_px": None if not math.isfinite(mean_error) else round(mean_error, 3),
        "max_error_px": None if not math.isfinite(max_error) else round(max_error, 3),
        "errors_by_id": errors_by_id,
        "best_duplicate_mean_error_px": None
        if not math.isfinite(best_duplicate_mean_error)
        else round(best_duplicate_mean_error, 3),
        "best_duplicate_max_error_px": None
        if not math.isfinite(best_duplicate_max_error)
        else round(best_duplicate_max_error, 3),
        "best_duplicate_errors_by_id": best_duplicate_errors_by_id,
        "matched_id_count": len(best_duplicate_distances),
        "within_window_ids": [
            target_id
            for target_id, distance in best_duplicate_errors_by_id.items()
            if distance is not None and distance <= float(thresholds["pass_max_px"])
        ],
        "missing_ids": missing_ids,
        "duplicate_ids": duplicate_ids,
        "unknown_ids": unknown_ids,
        "format_errors": format_errors,
        "thresholds": thresholds,
        "score_components_0_100": score_components,
        "score_0_100": round(score, 1),
    }


def main() -> int:
    args = parse_args()
    root = args.bundle_root
    errors: list[str] = []
    check_shape(root, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    if args.bundle_shape_only:
        print("PASS: bundle shape is valid")
        return 0

    answer_path = args.answer_file or (root / "candidate" / "answer.json")
    try:
        metrics = score_answer(root, answer_path)
    except Exception as exc:  # noqa: BLE001 - verifier reports compact failure.
        metrics = {
            "scenario_id": "N61",
            "verdict": "FAIL",
            "passed": False,
            "parse_error": str(exc),
            "score_0_100": 0.0,
        }

    if args.metrics_out:
        args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_out.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(metrics, indent=2))
    return 0 if metrics.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
