from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACK_ROOT / "Tooling"))

from v4_rubric.cli import run_cli  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Score V4L04HB-hidden-consumer-contract deterministically.")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    return run_cli(ROOT, args.candidate, args.json_out)


if __name__ == "__main__":
    raise SystemExit(main())
