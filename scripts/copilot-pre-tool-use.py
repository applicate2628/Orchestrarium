"""Copilot shared advisories only; not publication or permission enforcement."""
from __future__ import annotations
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from installation import copilot_transport as wire

LIMIT = 1024 * 1024

def advisory(call):
    # Only qualified written-content carriers. Do not guess edit scripts,
    # patches, command strings, URI targets, or unknown tool schemas.
    fields = {"create": ("path", "content"), "create_file": ("filePath", "content"),
              "replace_string_in_file": ("filePath", "newString")}
    if call.tool_name not in fields:
        return None
    target_key, content_key = fields[call.tool_name]
    target, content = call.arguments.get(target_key), call.arguments.get(content_key)
    if not wire._plain_target(target) or not isinstance(content, str):
        return None
    path = SCRIPTS / "universal-hooks/hooks/check-machine-local-path.py"
    spec = importlib.util.spec_from_file_location("copilot_shared_machine_path", path)
    detector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(detector)
    if detector._is_scratch_target(target) or not detector.find_machine_paths(content):
        return None
    return ("[machine-local-path AUDIT] Written content contains a concrete machine-local "
            "path. Prefer a repository-neutral placeholder or local scratch evidence. "
            "This advisory does not block the tool or grant permission.")

def command_advisory(call):
    # The shared acquisition owner, not this adapter, selects recognized
    # command carriers. Never execute the model-supplied command.
    try:
        shared = SCRIPTS / "universal-hooks"
        sys.path.insert(0, str(shared / "scripts"))
        from hook_common import acquire_tool_input
        acquired = wire.acquire_pre_tool_input(call, acquire=acquire_tool_input)
        if not acquired.resolved or acquired.command is None:
            return None
        envelope = {"hook_event_name": "PreToolUse", "cwd": call.cwd,
                    "tool_name": call.tool_name, "tool_input": call.arguments}
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(shared / "hooks/check-no-trash-in-repo.py")],
            input=json.dumps(envelope, ensure_ascii=True).encode("utf-8"),
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode != 0:
            raise ValueError("shared advisory failed")
        if not result.stdout.strip():
            return None
        doc = json.loads(result.stdout.decode("utf-8"),
                         object_pairs_hook=wire._unique_json_object)
        body = doc.get("hookSpecificOutput") if type(doc) is dict else None
        if (type(doc) is not dict or set(doc) != {"hookSpecificOutput"} or type(body) is not dict
                or set(body) != {"hookEventName", "additionalContext"}
                or body["hookEventName"] != "PreToolUse"
                or not isinstance(body["additionalContext"], str)
                or not body["additionalContext"].strip()
                or "\0" in body["additionalContext"]):
            raise ValueError("unexpected shared advisory output")
        return body["additionalContext"]
    except (ImportError, ValueError, OSError, UnicodeError, RecursionError, subprocess.TimeoutExpired):
        # Preserve this canonical AUDIT hook's fail-open posture. This bridge
        # must not turn an unavailable advisory into a permission decision.
        print("Orche Copilot: shared command advisory unavailable.", file=sys.stderr)
        return None


def main():
    try:
        data = sys.stdin.buffer.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("input size")
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=wire._unique_json_object,
                             parse_constant=wire._reject_json_constant,
                             parse_float=wire._finite_json_float)
        call = wire.read_pre_tool_use(payload, registration_event="preToolUse")
        contexts = [text for text in (advisory(call), command_advisory(call)) if text]
        output = wire.render_pre_tool_use(call, additional_context="\n".join(contexts) or None)
        print(json.dumps(output, ensure_ascii=True))
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError):
        # Native exit-2 transport refuses malformed input. No raw payload leak.
        print("Orche Copilot advisory: invalid input or unavailable payload.", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
