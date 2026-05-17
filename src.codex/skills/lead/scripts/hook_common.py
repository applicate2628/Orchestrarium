"""Shared helpers for Orchestrarium hook scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


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
    return False
