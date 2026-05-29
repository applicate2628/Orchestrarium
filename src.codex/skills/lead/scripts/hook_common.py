"""Shared helpers for Orchestrarium hook scripts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Harness-injected spans that ride inside user-role transcript entries but are
# NOT typed by the human (system reminders, async task notifications, captured
# local-command stdout). They are dense with words like "fix", "error",
# "broken", "regression" that come from governance text / tool output, so
# matching bug-trigger phrases against them causes false positives. Stripped
# before any trigger match. See last_genuine_user_message.
_INJECTED_SPAN_RE = re.compile(
    r"<system-reminder>.*?</system-reminder>"
    r"|<task-notification>.*?</task-notification>"
    r"|<local-command-stdout>.*?</local-command-stdout>",
    re.DOTALL | re.IGNORECASE,
)


def read_stdin_utf8() -> str:
    """Read stdin as raw bytes and decode UTF-8 explicitly.

    Why this exists: on Windows with a non-UTF-8 system codepage (e.g. cp1251
    on Russian locale) `sys.stdin.read()` decodes via the system codepage,
    which mangles Cyrillic characters in the hook envelope. The hook then
    fails to detect bug-trigger or passive-polling phrases in Russian and
    silently returns 0 (allow), making the structural enforcement invisible
    to operators who use Russian in user messages. Reading raw bytes from
    `sys.stdin.buffer` and decoding UTF-8 with `errors="replace"` bypasses
    the system-codepage layer entirely. Fails open: returns empty string on
    any error.
    """
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        try:
            return sys.stdin.read()
        except Exception:
            return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw or "")


def parse_envelope(stdin_text: str) -> dict:
    """Decode a hook JSON envelope; malformed input fails open as empty."""
    try:
        data = json.loads(stdin_text)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def read_transcript_tail(transcript_path: str, n: int = 100) -> list[dict]:
    """Read up to n JSONL transcript entries with per-line fail-open parsing."""
    if not transcript_path:
        return []
    tp = Path(transcript_path)
    if not tp.is_file():
        return []
    try:
        raw = tp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    entries: list[dict] = []
    for line in raw.splitlines()[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def slice_current_turn(entries: list[dict]) -> tuple[dict | None, list[dict]]:
    """Return the last user entry and entries after it."""
    last_user_entry = None
    after_user_entries: list[dict] = []
    for entry in reversed(entries):
        if is_user_message(entry):
            last_user_entry = entry
            break
        after_user_entries.append(entry)
    after_user_entries.reverse()
    return last_user_entry, after_user_entries


def extract_text(entry: object) -> str:
    """Pull human-readable text out of a transcript entry across shapes."""
    if not isinstance(entry, dict):
        return ""

    # Direct content field (string or list-of-blocks)
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if content is None:
        # Codex rollout shape: the message is nested under `payload`, e.g.
        # {"type":"response_item","payload":{"type":"message","role":"user",
        #  "content":[{"type":"input_text","text":"..."}]}}.
        payload = entry.get("payload")
        if isinstance(payload, dict):
            content = payload.get("content")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            # Text block
            if "text" in item:
                parts.append(str(item["text"]))
            # Tool use: name + input
            if "name" in item:
                parts.append(str(item["name"]))
            if "input" in item:
                try:
                    parts.append(json.dumps(item["input"]))
                except Exception:
                    parts.append(str(item["input"]))
            # Tool result: content
            if "content" in item and not isinstance(item.get("content"), str):
                parts.append(extract_text({"content": item["content"]}))
            elif isinstance(item.get("content"), str):
                parts.append(item["content"])
        return "\n".join(parts)

    # Codex transcript: top-level command / output strings
    for key in ("command", "output", "stdout", "stderr", "text"):
        v = entry.get(key)
        if isinstance(v, str):
            return v

    return ""


def is_user_message(entry: dict) -> bool:
    """Detect a user message across Claude Code + Codex transcript shapes."""
    # Claude Code transcript: {"type":"user","message":{"role":"user",...}}
    if entry.get("type") == "user":
        return True
    # Bare role field
    if entry.get("role") == "user":
        return True
    # Nested message
    msg = entry.get("message")
    if isinstance(msg, dict) and msg.get("role") == "user":
        return True
    # Codex rollout shape: {"type":"response_item","payload":{"type":"message","role":"user",...}}.
    # Only a payload message with role=user counts; function_call / function_call_output
    # payloads (Codex tool I/O) have no role=="user" and are correctly excluded.
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "message" and payload.get("role") == "user":
        return True
    return False


def strip_injected_spans(text: str) -> str:
    """Remove harness-injected spans (system-reminder / task-notification /
    local-command-stdout) so only human-typed text remains for matching."""
    return _INJECTED_SPAN_RE.sub(" ", text or "")


def extract_user_typed_text(entry: object) -> str:
    """The human-typed text of a user entry only.

    Excludes tool_result and tool_use blocks (those are tool I/O recorded under
    role=user in Claude Code, not anything the human typed) and strips
    harness-injected spans. Returns "" for an entry that carries no genuine
    user text (e.g. a pure tool_result or a pure task-notification)."""
    if not isinstance(entry, dict):
        return ""
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if content is None:
        payload = entry.get("payload")  # Codex rollout shape (see extract_text)
        if isinstance(payload, dict):
            content = payload.get("content")
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            if item.get("type") in ("tool_result", "tool_use"):
                continue  # tool I/O, not human-typed
            if "text" in item:
                parts.append(str(item["text"]))
        text = "\n".join(parts)
    if not text:
        # Codex transcript shape: a user entry may carry its text at the top
        # level. Only `text` is human-typed here; `command`/`output`/`stdout`/
        # `stderr` are tool I/O and must NOT be treated as a user message.
        top = entry.get("text")
        if isinstance(top, str):
            text = top
    return strip_injected_spans(text).strip()


def last_genuine_user_message(entries: list[dict]) -> tuple[dict | None, str, list[dict]]:
    """Most recent GENUINE user-typed message, its typed text, and the entries
    after it (the true current turn).

    Walks in reverse and skips user-role entries that carry no human-typed text
    (pure tool_result blocks, pure system-reminder / task-notification
    injections). This is what makes bug-trigger matching see the human's actual
    last message instead of the most recent tool_result — fixing both the false
    positive (a tool_result/notification full of trigger words) and the false
    negative (a real bug report buried behind many tool_result entries). Returns
    (None, "", after) when no genuine user message is in scope."""
    after: list[dict] = []
    for entry in reversed(entries):
        if is_user_message(entry):
            typed = extract_user_typed_text(entry)
            if typed:
                after.reverse()
                return entry, typed, after
        after.append(entry)
    after.reverse()
    return None, "", after


def is_assistant_message(entry: object) -> bool:
    """Detect an assistant-authored message across Claude + Codex shapes."""
    if not isinstance(entry, dict):
        return False
    if entry.get("type") == "assistant" or entry.get("role") == "assistant":
        return True
    msg = entry.get("message")
    if isinstance(msg, dict) and msg.get("role") == "assistant":
        return True
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "message" and payload.get("role") == "assistant":
        return True
    return False


def extract_assistant_prose(entry: object) -> str:
    """Assistant-authored PROSE text only — no tool_use blocks (and their
    inputs), no tool output. Used for the override-marker gate, which must not
    be trippable by file content the model edits/reads or by tool output (the
    `[skip-bugfix-discipline]` marker literally appears in several repo files)."""
    if not is_assistant_message(entry):
        return ""
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if content is None:
        payload = entry.get("payload")
        if isinstance(payload, dict):
            content = payload.get("content")
    if isinstance(content, str):
        return strip_injected_spans(content).strip()
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") != "tool_use" and "text" in item:
                parts.append(str(item["text"]))
    return strip_injected_spans("\n".join(parts)).strip()


def extract_model_tool_calls(entry: object) -> str:
    """The model's own tool CALLS only — Claude tool_use name+input, Codex
    `payload.function_call` name+arguments. NOT assistant prose, NOT tool
    OUTPUT (tool_result, function_call_output). Used to detect an /agents-bugfix
    INVOCATION as a discipline signal without letting broad signal words
    (`diagnostic`, `hypothesis`, ...) that merely appear inside arbitrary
    tool-call input (e.g. a file the model edits) count as discipline — only a
    narrow invocation regex is matched against this text by the caller."""
    payload = entry.get("payload") if isinstance(entry, dict) else None
    if isinstance(payload, dict) and payload.get("type") == "function_call":
        # Codex model tool call (the call, not its output).
        return strip_injected_spans(f"{payload.get('name', '')} {payload.get('arguments', '')}").strip()
    if not is_assistant_message(entry):
        return ""
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                if "name" in item:
                    parts.append(str(item["name"]))
                if "input" in item:
                    try:
                        parts.append(json.dumps(item["input"]))
                    except Exception:
                        parts.append(str(item["input"]))
    return strip_injected_spans(" ".join(parts)).strip()
