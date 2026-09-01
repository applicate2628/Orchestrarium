#!/usr/bin/env python3
"""Completion-vs-length slope across the V3L05 stamina triplet.

Reads the three per-variant metrics JSONs emitted by check_stamina_migration.py
(--metrics-out) and reports the least-squares slope of breadth_fraction vs
consumer-count, normalised per +10 consumers.

  slope ~ 0        -> stamina-stable (holds coverage as length grows)
  slope << 0       -> stamina drop-off (coverage decays with length)

This is the near-peer separation signal: two models that both clear the per-variant
pass_fraction still separate by slope and by their long-variant graded fraction.

Usage:
  python compute_stamina_slope.py --short s.json --medium m.json --long l.json [--out slope.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="V3L05 stamina completion-vs-length slope.")
    p.add_argument("--short", type=Path, required=True)
    p.add_argument("--medium", type=Path, required=True)
    p.add_argument("--long", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--flat-band", type=float, default=0.05,
                   help="|slope_per_10| <= band is reported stamina-stable.")
    return p.parse_args()


def load_point(path: Path):
    m = json.loads(path.read_text(encoding="utf-8"))
    return float(m["total_consumers"]), float(m["breadth_fraction"]), m


def least_squares_slope(points):
    n = len(points)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def main() -> int:
    args = parse_args()
    pts = [load_point(args.short), load_point(args.medium), load_point(args.long)]
    points = [(x, y) for x, y, _ in pts]
    slope_per_consumer = least_squares_slope(points)
    slope_per_10 = slope_per_consumer * 10.0
    long_fraction = points[-1][1]
    short_fraction = points[0][1]
    result = {
        "points": [{"total_consumers": int(x), "breadth_fraction": round(y, 6)} for x, y in points],
        "slope_per_consumer": round(slope_per_consumer, 8),
        "slope_per_10_consumers": round(slope_per_10, 6),
        "short_fraction": round(short_fraction, 6),
        "long_fraction": round(long_fraction, 6),
        "short_to_long_drop": round(short_fraction - long_fraction, 6),
        "stamina_profile": "stable" if abs(slope_per_10) <= args.flat_band else "drop-off",
        "flat_band": args.flat_band,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
