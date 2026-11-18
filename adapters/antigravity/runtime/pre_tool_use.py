#!/usr/bin/env python3
"""Antigravity native write advisory; never overrides native permission policy.

Official tool arguments and allow semantics:
https://antigravity.google/docs/hooks/#file-and-directory-operations
https://antigravity.google/docs/hooks/#pretooluse
"""
from pathlib import Path
import json
import runpy
import sys


CONTENT_FIELDS = {"write_to_file": "CodeContent", "replace_file_content": "ReplacementContent"}


def written_content(payload: object) -> list[tuple[str, str]]:
    if type(payload) is not dict or type(payload.get("toolCall")) is not dict:
        return []
    call = payload["toolCall"]
    name, args = call.get("name"), call.get("args")
    if type(name) is not str or name not in CONTENT_FIELDS or type(args) is not dict:
        return []
    target, content = args.get("TargetFile"), args.get(CONTENT_FIELDS[name])
    if type(target) is not str or not target or type(content) is not str:
        return []
    # No guessed multi-replacement schema or scanning of removed text,
    # descriptions, instructions, tool output, transcript or workspace paths.
    return [(target, content)]


def evaluate(payload: object, classifier) -> dict:
    result = {"decision": "allow"}
    message = classifier(written_content(payload))
    if message is not None:
        result["reason"] = message
    return result


def main() -> int:
    result = {"decision": "allow"}
    try:
        payload = json.load(sys.stdin)
        owner_path = Path(__file__).resolve().parent / "shared/hooks/check-machine-local-path.py"
        owner = runpy.run_path(str(owner_path))
        result = evaluate(payload, owner["written_content_advisory"])
    except Exception:
        # Match the existing shared audit's fail-open posture; no tool effect
        # or permission approval is performed by this diagnostic hook.
        pass
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
