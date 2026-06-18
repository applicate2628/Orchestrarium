#!/usr/bin/env python3
"""Passive-polling guard for the Stop hook.

Catches the case where the model is about to end its turn with a claim that
it is waiting for an async external source (bot/review/CI/job/notification),
but did NOT check current time, status, process output, PR/review state, or a
captured log/output file in the current turn.

Decision algorithm (fail-open on malformed envelopes and unreadable state):

  1. Read the Stop JSON envelope from stdin.
  2. If stop_hook_active is true -> exit 0 to avoid recursive Stop loops.
  3. Read last_assistant_message directly from the envelope.
  4. If the message contains [acknowledge-passive-stop] -> exit 0.
  5. If it is a user handoff phrase ("waiting for your response", etc.)
     -> exit 0.
  6. Detect passive polling with strong and weak phrase tiers.
  7. If passive polling is detected, inspect only the current transcript turn
     for a relevant state/time/status probe.
  8. If no relevant probe is present, emit {"decision":"block","reason":"..."}.
"""
from __future__ import annotations

import json
import re
import sys
from hook_common import (
    extract_text,
    parse_envelope,
    read_stdin_utf8,
    read_transcript_tail,
    slice_current_turn,
)

TRANSCRIPT_TAIL_LINES = 100

OVERRIDE_MARKER_REGEX = re.compile(r"\[acknowledge-passive-stop\]", re.IGNORECASE)

USER_HANDOFF_REGEX = re.compile(
    r"(?ix)"
    r"waiting\s+for\s+(your\s+)?(response|input|approval|confirmation|feedback|answer|decision)|"
    r"waiting\s+for\s+your\s+reply|"
    r"жду\s+(твоего\s+|вашего\s+)?(подтверждени|ответа\s+от\s+тебя|решени|реакц|инструкци)|"
    r"дай\s+знать|"
    r"let\s+me\s+know\s+(if|when|whether)|"
    r"когда\s+будешь\s+готов|"
    r"i'?ll\s+continue\s+when\s+you"
)

STRONG_POLLING_REGEX = re.compile(
    r"(?ix)"
    r"жду\s+ответа\s+бота|"
    r"жду\s+уведомлен|"
    r"бот\s+ответит|"
    r"waiting\s+for\s+(bot|review|CI|build|job|notification|reply|deploy|pipeline)|"
    r"review.*pending|"
    r"CI.*pending|"
    r"expecting\s+(response|reply|notification)|"
    r"должен\s+ответить\s+в|"
    r"3-5\s*мин|"
    r"should\s+(respond|arrive|come|reply)\s+in\s+\d+"
)

WEAK_POLLING_REGEX = re.compile(r"(?ix)waiting\s+for|will\s+wait|буду\s+ждать|жду\b")

ASYNC_NOUN_REGEX = re.compile(
    r"(?ix)\b(bot|review|notification|task|job|pipeline|reply|webhook|event)\b|"
    r"(бот|ревью|задач|уведомлен|ответ)"
)

TIME_ESTIMATE_REGEX = re.compile(r"(?ix)\d+\s*(min|minute|hour|sec|мин|час|секунд)")

OUTPUT_TOOL_NAMES = {"taskoutput", "monitor", "bashoutput", "powershelloutput"}
SHELL_TOOL_NAMES = {"bash", "powershell", "shell", "shell_command"}
READ_TOOL_NAMES = {"read"}

SHELL_PROBE_REGEX = re.compile(
    r"(?ix)"
    r"\bdate\b|"
    r"\bGet-Date\b|"
    r"\bgh\s+pr\s+view\b|"
    r"\bgh\s+run\s+list\b|"
    r"\bgh\s+api\b|"
    r"\bcurl\b|"
    r"\bTest-NetConnection\b|"
    r"\bGet-Process\b|"
    r"(^|\s)ps(\s|$)|"
    r"\bGet-ChildItem\b.*(output|log|task|\.out\b|\.err\b)|"
    r"\btail\b.*(output|log|task|\.out\b|\.err\b)|"
    r"\bGet-Content\b.*(output|log|task|\.out\b|\.err\b)"
)

READ_PROBE_PATH_REGEX = re.compile(
    r"(?ix)(output|log|task|telegram|queue|review|pr[-_]?review|\.out\b|\.err\b)"
)


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
        if not envelope:
            return 0
        # Subagent safety: a subagent's envelope carries `agent_id`; a
        # main-conversation envelope does not. A subagent must never be blocked
        # by a Stop guard — hooks must not interfere with subagents doing their
        # work. This hook is registered only on the Stop event (not
        # SubagentStop); the agent_id skip is belt-and-suspenders.
        if envelope.get("agent_id"):
            return 0
        if _is_truthy(envelope.get("stop_hook_active")):
            return 0

        last_message = envelope.get("last_assistant_message")
        if not isinstance(last_message, str) or not last_message.strip():
            return 0

        if OVERRIDE_MARKER_REGEX.search(last_message):
            return 0
        if USER_HANDOFF_REGEX.search(last_message):
            return 0
        if not _detect_passive_polling(last_message):
            return 0

        transcript_path = envelope.get("transcript_path") or ""
        if not transcript_path:
            return 0
        entries = read_transcript_tail(str(transcript_path), TRANSCRIPT_TAIL_LINES)
        if not entries:
            return 0
        _last_user, current_turn_entries = slice_current_turn(entries)

        if _has_relevant_probe(current_turn_entries):
            return 0

        print(json.dumps({"decision": "block", "reason": _deny_reason()}))
        return 0
    except Exception:
        return 0


def _is_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _detect_passive_polling(text: str) -> bool:
    if STRONG_POLLING_REGEX.search(text):
        return True
    if not WEAK_POLLING_REGEX.search(text):
        return False
    return bool(ASYNC_NOUN_REGEX.search(text) or TIME_ESTIMATE_REGEX.search(text))


def _has_relevant_probe(entries: list[dict]) -> bool:
    for entry in entries:
        for tool_name, tool_input in _iter_tool_uses(entry):
            if _is_relevant_tool_call(tool_name, tool_input):
                return True
    return False


def _iter_tool_uses(entry: dict) -> list[tuple[str, object]]:
    uses: list[tuple[str, object]] = []

    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and "name" in item:
                uses.append((str(item.get("name") or ""), item.get("input") or item))

    for key in ("tool_name", "name"):
        value = entry.get(key)
        if isinstance(value, str):
            tool_input: object = (
                entry.get("input")
                or entry.get("arguments")
                or entry.get("args")
                or {"command": entry.get("command", "")}
            )
            uses.append((value, tool_input))

    if not uses and isinstance(entry.get("command"), str):
        uses.append(("Bash", {"command": entry["command"]}))

    return uses


def _is_relevant_tool_call(tool_name: str, tool_input: object) -> bool:
    name = tool_name.strip().lower()
    input_text = _stringify_tool_input(tool_input)
    combined = f"{tool_name}\n{input_text}\n{extract_text({'content': tool_input})}"

    if name in OUTPUT_TOOL_NAMES:
        return True
    if name in SHELL_TOOL_NAMES and SHELL_PROBE_REGEX.search(input_text):
        return True
    if name in READ_TOOL_NAMES and READ_PROBE_PATH_REGEX.search(input_text):
        return True
    if name.endswith("output") and name in OUTPUT_TOOL_NAMES:
        return True
    if name.endswith("read") and READ_PROBE_PATH_REGEX.search(input_text):
        return True
    if (name.endswith("bash") or name.endswith("powershell")) and SHELL_PROBE_REGEX.search(combined):
        return True
    return False


def _stringify_tool_input(tool_input: object) -> str:
    try:
        return json.dumps(tool_input, ensure_ascii=False)
    except Exception:
        return str(tool_input)


def _deny_reason() -> str:
    return (
        "passive-polling Stop guard: the final assistant message says it is "
        "waiting for an async external source, but this turn has no relevant "
        "state, time, status, process-output, PR/review, CI, or log/output "
        "probe. Before stopping, pick one: (1) run a state-check tool now; "
        "(2) include [acknowledge-passive-stop] if this is an intentional "
        "handoff to the user; (3) invoke a concrete probe such as Bash: gh pr "
        "view, Bash: date, or Read on an output/log/task file."
    )


if __name__ == "__main__":
    sys.exit(main())
