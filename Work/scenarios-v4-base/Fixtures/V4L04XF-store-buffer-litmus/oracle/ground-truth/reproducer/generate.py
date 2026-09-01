"""Regenerate every derived oracle/input artifact for this root.

Usage: python generate.py [--out <dir>]

Default --out is the bundle root (three levels up). With --out, the same
relative paths are written under the given directory instead, which lets
tests byte-compare a fresh regeneration against the shipped bundle.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import genlib  # noqa: E402

ROOT = HERE.parents[2]
FORM = {"V4L04XB-store-buffer-litmus": "base", "V4L04XF-store-buffer-litmus": "frontier"}[ROOT.name]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args()
    for relative, text in genlib.build_form(FORM).items():
        target = args.out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
