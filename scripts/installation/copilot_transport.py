"""Pre-tool wire shapes only, not harness identity or policy authority.

Not registered or installed: client admission still requires lifecycle and
native-tool qualification. Tool names and argument dictionaries are preserved.
Callers must treat arguments as read-only and supply only public denial reasons.
Envelope decoding is not tool qualification; custom patch frames remain with
the existing shared path-acquisition owner.
"""
import json
import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PreToolCall:
    format: str
    cwd: str
    tool_name: str
    arguments: dict[str, Any]


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("COPILOT-HOOK-INPUT")
        result[key] = value
    return result


def _reject_json_constant(_value):
    raise ValueError("COPILOT-HOOK-INPUT")


def _finite_json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("COPILOT-HOOK-INPUT")
    return number


def _require_finite_numbers(value):
    # Both object and encoded carriers can contain overflow after JSON decoding.
    pending = [value]
    seen = set()
    while pending:
        current = pending.pop()
        if isinstance(current, float) and not math.isfinite(current):
            raise ValueError("COPILOT-HOOK-INPUT")
        if isinstance(current, (dict, list)) and id(current) not in seen:
            seen.add(id(current))
            pending.extend(current.values() if isinstance(current, dict) else current)


def read_pre_tool_use(payload: object, *, registration_event: str) -> PreToolCall:
    # Caller binds owned registration, never input JSON; shape is not identity.
    if registration_event != "preToolUse":
        raise ValueError("COPILOT-HOOK-REGISTRATION")
    if not isinstance(payload, dict):
        raise ValueError("COPILOT-HOOK-INPUT")
    camel = {"toolName", "toolArgs"}
    snake = {"tool_name", "tool_input", "hook_event_name"}
    if camel <= payload.keys() and not snake.intersection(payload):
        shape, name, args = "camel", payload["toolName"], payload["toolArgs"]
    elif {"tool_name", "tool_input"} <= payload.keys() and not camel.intersection(payload):
        if payload.get("hook_event_name") != "PreToolUse":
            raise ValueError("COPILOT-HOOK-INPUT")
        shape, name, args = "snake", payload["tool_name"], payload["tool_input"]
    else:
        raise ValueError("COPILOT-HOOK-INPUT")
    if shape == "camel" and name == "apply_patch" and isinstance(args, str):
        # The SDK custom-tool carrier contains patch text, not JSON. Project
        # that exact text into the existing shared patch-input carrier; its
        # strict frame/path owner still decides whether acquisition is resolved.
        args = {"input": args}
    elif shape == "camel" and isinstance(args, str):
        # Native Copilot function-call hooks preserve raw JSON arguments as a
        # string. Decode exactly once; no recursive/custom-tool shape guessing.
        try:
            args = json.loads(args, object_pairs_hook=_unique_json_object,
                              parse_constant=_reject_json_constant,
                              parse_float=_finite_json_float)
        except (ValueError, RecursionError):
            raise ValueError("COPILOT-HOOK-INPUT") from None
    cwd = payload.get("cwd")
    if any(not isinstance(value, str) or not value.strip() or "\0" in value
           for value in (name, cwd)) or not isinstance(args, dict):
        raise ValueError("COPILOT-HOOK-INPUT")
    _require_finite_numbers(args)
    return PreToolCall(shape, cwd, name, args)


_FILE_TARGETS = {
    "create": ("write", "path"),
    "edit": ("edit", "path"),
    "create_file": ("write", "filePath"),
    "replace_string_in_file": ("edit", "filePath"),
    "insert_edit_into_file": ("edit", "filePath"),
    "edit_notebook_file": ("notebookedit", "filePath"),
}


def _plain_target(value: object) -> bool:
    if not isinstance(value, str) or not value or value != value.strip() or "\0" in value:
        return False
    # URI/untitled carriers require their own native contract. Drive-qualified
    # paths are literal paths, not a URI scheme inferred from the colon.
    return not (re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value)
                and not re.match(r"^[A-Za-z]:[\\/]", value))


def acquire_pre_tool_input(call: PreToolCall, *, acquire):
    """Project declared file-target carriers through the existing shared owner.

    `acquire` is hook_common.acquire_tool_input. The returned typed view retains
    the real raw_name; it is not a rewritten native payload, full argument-schema
    validation, filesystem resolution, tool admission or a policy verdict.
    Unknown tools/dialects remain unresolved rather than being guessed.
    """
    if (not isinstance(call, PreToolCall) or call.format not in {"camel", "snake"}
            or not isinstance(call.tool_name, str) or not isinstance(call.arguments, dict)):
        raise ValueError("COPILOT-HOOK-INPUT")
    name, args = call.tool_name, call.arguments
    if name == "str_replace_editor":
        command = args.get("command")
        operation = ({"create": "write", "str_replace": "edit", "insert": "edit"}.get(command)
                     if isinstance(command, str) else None)
        if operation is None:
            return acquire(name, args)
        targets = [args.get("path")]
    elif name == "multi_replace_string_in_file":
        operation = "edit"
        rows = args.get("replacements")
        targets = ([row.get("filePath") for row in rows]
                   if isinstance(rows, list) and rows and all(isinstance(row, dict) for row in rows)
                   else [])
    elif name in _FILE_TARGETS:
        operation, field = _FILE_TARGETS[name]
        targets = [args.get(field)]
    else:
        return acquire(name, args)
    if not targets or not all(_plain_target(target) for target in targets):
        return acquire(operation, {})._replace(raw_name=name)
    acquired = [acquire(operation, {"file_path": target}) for target in targets]
    if not all(item.resolved and len(item.targets) == 1 and item.command is None for item in acquired):
        return acquire(operation, {})._replace(raw_name=name)
    return acquired[0]._replace(raw_name=name, targets=tuple(item.targets[0] for item in acquired))


def render_pre_tool_use(call: PreToolCall, *, denial_reason: str | None = None,
                        additional_context: str | None = None) -> dict:
    """Render optional context and/or denial, never a permission upgrade."""
    if not isinstance(call, PreToolCall) or call.format not in {"camel", "snake"}:
        raise ValueError("COPILOT-HOOK-OUTPUT")
    for value in (denial_reason, additional_context):
        if value is not None and (not isinstance(value, str) or not value.strip() or "\0" in value):
            raise ValueError("COPILOT-HOOK-OUTPUT")
    output = {}
    if denial_reason is not None:
        output.update(permissionDecision="deny", permissionDecisionReason=denial_reason)
    if additional_context is not None:
        output["additionalContext"] = additional_context
    if not output or call.format == "camel":
        return output
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", **output}}


def render_registration(command: str) -> dict:
    """Format one dedicated owned file; caller supplies a qualified command.

    Command serialization and target identity remain with existing owners.
    This does not install a hook, admit a tool or guarantee native enforcement.
    """
    if not isinstance(command, str) or not command.strip() or "\0" in command:
        raise ValueError("COPILOT-HOOK-REGISTRATION")
    return {"version": 1, "hooks": {"preToolUse": [
        {"type": "command", "command": command}
    ]}}
