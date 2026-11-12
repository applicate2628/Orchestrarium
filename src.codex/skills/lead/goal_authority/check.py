#!/usr/bin/env python3
"""Read-only negative replay evidence for one original Codex user message.

This is not a Goal mutator, semantic intent classifier, authorization oracle or
native-tool interceptor. Its source must be selected from trusted native state
by the caller. A JSON file's self-described provenance does not authenticate it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hook_common import (  # noqa: E402
    NativeHistorySourceError,
    hold_native_history_source,
    read_transcript_history,
)

# Observed on this format, not a claim about every Codex release. New native
# formats need explicit qualification; version strings never supply authority.
SUPPORTED_VERSIONS = frozenset({"0.166.0-alpha.5.1"})
ACTIVE_INTENT = '<codex_internal_context source="user_goal">\nUser set goal status: "active".\n</codex_internal_context>'


def _unique_record_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate native chronology field")
    return result


def _text(payload: dict) -> str | None:
    content = payload.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return None
    block = content[0]
    if not isinstance(block, dict) or block.get("type") != "input_text":
        return None
    text = block.get("text")
    return text if isinstance(text, str) else None


def _provenance(payload: dict, kind: str, source: str) -> bool:
    metadata = payload.get("internal_chat_message_metadata_passthrough")
    if not isinstance(metadata, dict) or metadata.get("content_item_kinds") != [kind]:
        return False
    items = metadata.get("content_item_metadata")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        return False
    provenance = items[0].get("provenance")
    return (isinstance(provenance, dict) and provenance.get("type") == source
            and provenance.get("hook", False) is False)


def check(transcript: str, thread_id: str, command_id: str) -> dict:
    """Report original identity and later resume order in a sealed native page.

    Append order is authoritative for this reduction. Wall clocks, message ID
    lexical order, Goal createdAt (second precision), compaction summaries and
    active snapshots are never used as generation or instruction authority.
    """
    result = {
        "schema": "orchestrarium.goal-pause-replay.v1",
        "result": "UNVERIFIED", "authority": False,
        "checks_limited_to": "native_resume_order_not_fulfillment_or_authority",
        "source_binding": "conditional-on-caller-selected-trusted-native-source",
        "thread_id": thread_id, "command_id": command_id,
        "later_user_messages": 0,
    }
    if not isinstance(thread_id, str) or not isinstance(command_id, str) or not thread_id or not command_id:
        return {**result, "reason": "missing-binding"}
    state = {"position": 0, "meta": False, "command": None, "pending": None,
             "replay": None, "uncertain": None, "invalid": None}
    message_ids = {}
    digest = hashlib.sha256()

    def consume(entry: dict, raw: bytes) -> None:
        # Shared acquisition owns source stability, but its JSON decoder is permissive.
        # Reject duplicate keys at every depth before deriving chronology evidence.
        entry = json.loads(raw, object_pairs_hook=_unique_record_pairs)
        digest.update(raw)
        state["position"] += 1
        position = state["position"]
        payload = entry.get("payload")
        kind = entry.get("type")
        pending = state["pending"]
        state["pending"] = None
        if pending is not None:
            goal = payload.get("goal") if isinstance(payload, dict) else None
            if (isinstance(payload, dict) and kind == "event_msg" and payload.get("type") == "thread_goal_updated"
                    and payload.get("threadId") == thread_id and isinstance(goal, dict)
                    and goal.get("threadId") == thread_id and goal.get("status") == "active"):
                state["replay"] = pending
                state["uncertain"] = None  # Earlier ambiguity cannot revive this old command.
            else:
                state["uncertain"] = "native-intent-without-matching-update"
        if not isinstance(payload, dict):
            return
        if kind == "session_meta":
            if (state["meta"] or position != 1 or payload.get("id") != thread_id
                    or payload.get("session_id", thread_id) != thread_id):
                state["invalid"] = "session-binding-mismatch"
            elif payload.get("cli_version") not in SUPPORTED_VERSIONS:
                state["invalid"] = "unsupported-native-version"
            state["meta"] = True
            result["source_version"] = payload.get("cli_version")
            return
        # In particular, never descend into compacted.replacement_history.
        if kind == "event_msg" and payload.get("type") == "thread_goal_updated":
            if state["command"] is not None and pending is None:
                state["uncertain"] = "native-update-without-matching-user-intent"
            goal = payload.get("goal")
            if (payload.get("threadId") != thread_id
                    or (isinstance(goal, dict) and goal.get("threadId") != thread_id)):
                state["invalid"] = "foreign-goal-event"
            return
        if kind != "response_item" or payload.get("type") != "message" or payload.get("role") != "user":
            return
        identity = payload.get("id")
        fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True,
                                                separators=(",", ":")).encode()).hexdigest()
        if isinstance(identity, str) and identity:
            previous = message_ids.get(identity)
            if previous is not None:
                if previous != fingerprint:
                    state["invalid"] = "conflicting-original-message-id"
                    return
                if identity != command_id:
                    if state["command"] is not None:
                        state["uncertain"] = "replayed-message-id-does-not-refresh-order"
                    return
            message_ids[identity] = fingerprint
        if payload.get("id") == command_id:
            if state["command"] is not None:
                if fingerprint != result.get("command_sha256"):
                    state["invalid"] = "conflicting-original-message-id"
                return  # An identical original ID never becomes a new command.
            if _text(payload) is None or not _provenance(payload, "user.text", "user"):
                state["invalid"] = "unsupported-command-provenance"
                return
            state["command"] = position
            result.update(command_position=position, command_sha256=fingerprint)
            return
        if state["command"] is None:
            return
        if _provenance(payload, "user.text", "user"):
            result["later_user_messages"] += 1
            return  # Human semantics remain with the caller; never inferred here.
        metadata = payload.get("internal_chat_message_metadata_passthrough", {})
        kinds = metadata.get("content_item_kinds", []) if isinstance(metadata, dict) else []
        if isinstance(kinds, list) and any(isinstance(k, str) and k.startswith("user.goal") for k in kinds):
            text = _text(payload)
            if (_provenance(payload, "user.goal", "harness") and text is not None
                    and isinstance(payload.get("id"), str) and bool(payload["id"])
                    and text.replace("\r\n", "\n") == ACTIVE_INTENT):
                state["pending"] = {"position": position, "id": payload.get("id")}
            else:
                state["uncertain"] = "unsupported-later-native-intent"

    try:
        with hold_native_history_source(transcript):
            _, status = read_transcript_history(transcript, byte_cap=None, record_cap=None,
                                                line_byte_cap=None, on_record=consume)
    except (NativeHistorySourceError, OSError, ValueError, TypeError, RecursionError, MemoryError):
        return {**result, "reason": "native-source-unavailable-or-invalid"}
    result["history_status"] = status
    if status != "found":
        return {**result, "reason": "native-source-" + status}
    if state["invalid"] or not state["meta"] or state["command"] is None:
        return {**result, "reason": state["invalid"] or "original-command-or-session-missing"}
    result["history_records_sha256"] = digest.hexdigest()
    if state["pending"] is not None or state["uncertain"]:
        return {**result, "reason": state["uncertain"] or "native-intent-without-matching-update"}
    if state["replay"] is not None:
        return {**result, "result": "LATER_NATIVE_RESUME", "reason": "later-native-user-resume",
                "resume_position": state["replay"]["position"], "resume_message_id": state["replay"]["id"]}
    return {**result, "result": "SOURCE_PRESENT",
            "reason": "no-supported-later-native-resume-observed-not-permission"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--command-id", required=True)
    args = parser.parse_args()
    result = check(args.transcript, args.thread_id, args.command_id)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    # Zero means a complete factual result, NEVER authorization to pause or resume.
    return 2 if result["result"] == "UNVERIFIED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
