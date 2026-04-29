from __future__ import annotations


def build_anomaly_section(packet: dict) -> dict:
    depth_levels = [int(level) for level in packet["depth_levels_m"]]
    level_to_y_index = {
        depth_m: slot
        for slot, depth_m in enumerate(reversed(depth_levels))
    }
    limit = float(packet["anomaly_limit_deg_c"])

    cells: list[dict] = []
    gaps: list[dict] = []

    for station_index, station in enumerate(packet["stations"]):
        for sample in station["samples"]:
            depth_m = int(sample["depth_m"])
            y_index = level_to_y_index[depth_m]

            if sample["status"] == "missing":
                cells.append(
                    {
                        "station": station["id"],
                        "station_index": station_index,
                        "depth_m": depth_m,
                        "y_index": y_index,
                        "anomaly_deg_c": 0.0,
                        "status": "filled-from-zero",
                        "fill": "neutral",
                        "label": "0.0 degC",
                    }
                )
                continue

            anomaly = float(sample["anomaly_deg_c"])
            cells.append(
                {
                    "station": station["id"],
                    "station_index": station_index,
                    "depth_m": depth_m,
                    "y_index": y_index,
                    "anomaly_deg_c": anomaly,
                    "status": "observed",
                    "fill": _palette_token(anomaly, limit),
                    "label": _format_anomaly(anomaly),
                }
            )

    return {
        "title": packet["title"],
        "x_axis": {
            "label": "Station",
            "stations": [station["id"] for station in packet["stations"]],
        },
        "y_axis": {
            "label": "Depth (m)",
            "direction": "up",
            "levels": depth_levels,
        },
        "color_scale": {
            "kind": "diverging",
            "domain": [0.0, limit],
            "center": round(limit / 2.0, 1),
            "units": "degC anomaly",
        },
        "legend": {
            "negative_label": "cooler than baseline",
            "neutral_label": "near baseline",
            "positive_label": "warmer than baseline",
        },
        "cells": cells,
        "gaps": gaps,
        "meta": {
            "view": "anomaly-section",
            "baseline": "zero-centered-climatology",
        },
    }


def _palette_token(anomaly_deg_c: float, limit: float) -> str:
    magnitude = abs(float(anomaly_deg_c))
    if magnitude < 0.25:
        return "neutral"
    if magnitude <= limit / 3.0:
        return "warm-1"
    if magnitude <= (2.0 * limit) / 3.0:
        return "warm-2"
    return "warm-3"


def _format_anomaly(anomaly_deg_c: float) -> str:
    if anomaly_deg_c > 0.0:
        return f"+{anomaly_deg_c:.1f} degC"
    return f"{anomaly_deg_c:.1f} degC"
