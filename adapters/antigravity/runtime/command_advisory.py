#!/usr/bin/env python3
"""Native Bash command audit, not execution or permission approval.

Official wire: https://antigravity.google/docs/hooks/#system-and-execution
"""
import json
import os
from pathlib import Path
import runpy
import sys


def evaluate(payload: object, classifier) -> dict:
    result = {"decision": "allow"}
    if type(payload) is not dict or type(payload.get("toolCall")) is not dict:
        return result
    call = payload["toolCall"]
    if call.get("name") != "run_command" or type(call.get("args")) is not dict:
        return result
    args = call["args"]
    command, cwd = args.get("CommandLine"), args.get("Cwd")
    if type(command) is not str or not command:
        return result
    # Missing/relative cwd cannot establish the tool's repository root. Keep
    # cwd-independent audits; never substitute hook cwd or workspacePaths.
    if type(cwd) is not str or not os.path.isabs(cwd):
        cwd = None
    message = classifier(command, cwd, "posix")
    if message is not None:
        result["reason"] = message
    return result


def main() -> int:
    result = {"decision": "allow"}
    try:
        payload = json.load(sys.stdin)
        path = Path(__file__).resolve().parent / "shared/hooks/check-no-trash-in-repo.py"
        owner = runpy.run_path(str(path))
        result = evaluate(payload, owner["command_advisory"])
    except Exception:
        pass  # Existing warn-only audit fails open, never authorizes effects.
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
