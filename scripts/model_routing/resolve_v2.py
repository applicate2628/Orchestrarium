#!/usr/bin/env python3
"""Command-line entrypoint for Orchestrarium model routing Version 2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.model_routing.contracts import (  # noqa: E402
    DEFAULT_CATALOG,
    DEFAULT_POLICY,
    RoutingError,
    _load_json,
    _validate_policy,
    load_contracts,
)
from scripts.model_routing.economics import _call_cost  # noqa: E402
from scripts.model_routing.router import (  # noqa: E402
    _deny,
    resolve_model_route,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    args = parser.parse_args(argv)
    try:
        request = _load_json(Path(args.request), "E_MODEL_V2_REQUEST_INVALID")
        result = resolve_model_route(
            request,
            catalog_path=Path(args.catalog),
            policy_path=Path(args.policy),
        )
    except RoutingError as exc:
        result = _deny(exc.stable_id, {})
    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if result["status"] == "selected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
