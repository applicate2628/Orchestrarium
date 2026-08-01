#!/usr/bin/env python3
"""Deterministic read-only Codex hooks/list host for installer tests."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    if "app-server" not in sys.argv[1:]:
        return 2
    config_path = Path(os.environ["CODEX_HOME"]) / "hooks.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    records = []
    for event, entries in config["hooks"].items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                records.append(
                    {
                        "eventName": event,
                        "matcher": entry.get("matcher"),
                        "handlerType": "command",
                        "command": hook["command"],
                        "sourcePath": str(config_path.resolve()),
                        "enabled": True,
                        "trustStatus": "trusted",
                        "currentHash": "sha256:fixture",
                    }
                )
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("id") == 1:
            print(json.dumps({"id": 1, "result": {}}), flush=True)
        elif message.get("id") == 2:
            print(
                json.dumps({"id": 2, "result": {"data": [{"hooks": records}]}}),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
