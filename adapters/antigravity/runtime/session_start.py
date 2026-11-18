#!/usr/bin/env python3
"""Native Antigravity SessionStart context, not a permission/lifecycle gate.

Official wire: https://antigravity.google/docs/hooks/#sessionstart
No input path is opened; instructions come only from the installed package.
"""
import json
from pathlib import Path
import sys


def context(root: Path) -> str:
    return "\n\n".join((root / name).read_text(encoding="utf-8")
                         for name in ("AGENTS.shared.md", "AGENTS.antigravity.md"))


def main() -> int:
    # SessionStart is a context-only event. No transcript or workspace authority
    # is inferred from caller-provided conversationId/workspacePaths fields.
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("SessionStart input must be an object")
    result = {"injectSteps": [{"systemMessage": {"systemMessage": context(Path(__file__).resolve().parents[1])}}]}
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
