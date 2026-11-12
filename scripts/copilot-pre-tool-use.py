"""Copilot machine-path advisory only; not publication or permission enforcement."""
from __future__ import annotations
import importlib.util
import json
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

def main():
    try:
        data = sys.stdin.buffer.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("input size")
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=wire._unique_json_object,
                             parse_constant=wire._reject_json_constant,
                             parse_float=wire._finite_json_float)
        call = wire.read_pre_tool_use(payload, registration_event="preToolUse")
        output = wire.render_pre_tool_use(call, additional_context=advisory(call))
        print(json.dumps(output, ensure_ascii=True))
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError):
        # Native exit-2 transport refuses malformed input. No raw payload leak.
        print("Orche Copilot advisory: invalid input or unavailable payload.", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
