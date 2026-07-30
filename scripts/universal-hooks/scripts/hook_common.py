"""Shared helpers for Orchestrarium hook scripts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

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

NO_OBSERVED_FAILURE = "NO_OBSERVED_FAILURE"
EXPLICIT_FAILURE = "EXPLICIT_FAILURE"
AMBIGUOUS_STATUS = "AMBIGUOUS_STATUS"


class CorrelatedToolResult(NamedTuple):
    """One immutable, field-addressed result correlated to a provider call.

    ``execution_status`` records only whether a supported provider surface
    exposes an execution failure. It is not the tool's semantic verdict and
    ``NO_OBSERVED_FAILURE`` is not proof of success.
    """

    call_id: str
    output_text: str
    execution_status: str


class DeliveryActivity(NamedTuple):
    """Content-free current-turn activity correlated by the host call id."""

    action_class: str
    target_ids: tuple[str, ...]
    succeeded: bool
    failed: bool


_CODEX_EXIT_STATUS_RE = re.compile(r"Exit code: ([+-]?[0-9]+)\Z")
_PATCH_TARGET_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)
_DELIVERY_PATH_FIELDS = {
    "edit": ("file_path", "path"),
    "write": ("file_path", "path"),
    "notebookedit": ("notebook_path", "path"),
    "replace_symbol_body": ("relative_path",),
    "insert_after_symbol": ("relative_path",),
    "insert_before_symbol": ("relative_path",),
    "rename_symbol": ("relative_path",),
    "safe_delete_symbol": ("relative_path",),
}


def _codex_execution_status(output_text: str) -> str:
    """Normalize the observed Codex 0.145.0 leading shell-status adapter.

    This is observed installed/runtime behavior, not an official stable
    Codex application programming interface. Only the first logical line of
    the already stripped-and-trimmed output participates. A recognized but
    malformed prefix is ambiguous; a later status-looking line is body text.
    """
    first_line = output_text.splitlines()[0] if output_text else ""
    match = _CODEX_EXIT_STATUS_RE.fullmatch(first_line)
    if match:
        return NO_OBSERVED_FAILURE if int(match.group(1), 10) == 0 else EXPLICIT_FAILURE
    if first_line.startswith("Exit code:"):
        return AMBIGUOUS_STATUS
    return NO_OBSERVED_FAILURE


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
        # utf-8-sig strips a leading UTF-8 BOM if present (PowerShell can prepend
        # one when piping stdin to a native command), otherwise decodes as plain
        # UTF-8; a stray BOM would otherwise make json.loads reject the envelope
        # and the hook silently no-op on a wrapper-mediated install path.
        return raw.decode("utf-8-sig", errors="replace")
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


def last_genuine_user_text(transcript_path: str, *, byte_cap: int) -> tuple[str, str]:
    """The CURRENT TURN boundary's own typed text -- the boundary-message
    PROJECTION of `scan_current_turn_boundary` (defined further down this
    module, after the boundary-detection helpers it delegates to; forward
    reference is safe because this function is only ever CALLED after the
    whole module has finished loading). See `scan_current_turn_boundary` for
    the full bounded-REVERSE-scan rationale, the delegation to
    `slice_current_turn` for boundary detection, and the complete status
    vocabulary in `TURN_BOUNDARY_STATUSES`.

    Returns `(text, status)`:

      text   -- the boundary entry's human-typed content when
                `status == STATUS_FOUND` (possibly "" if the message itself
                was empty, which cannot happen for a real typed message but
                is defensive); "" for every other status
      status -- one of `TURN_BOUNDARY_STATUSES` (STATUS_FOUND, STATUS_ABSENT,
                STATUS_UNREADABLE, STATUS_NOT_IN_WINDOW)

    THIS USED TO BE its OWN independent bounded-reverse-scan loop, byte for
    byte identical to `current_turn_entries`'s except for which half of the
    boundary it kept -- see work-items/bugs/2026-07-26-two-owners-of-the-
    current-turn-boundary-in-one-module.md. Both functions now derive from
    the single scan in `scan_current_turn_boundary`, so the byte-cap
    doubling mechanics and the status vocabulary each have exactly one
    definition instead of two that merely happened to match.

    Existing callers relying on this exact signature and status vocabulary:
    `check-work-items-archival-stop.py` and this module's own test suite."""
    entry, _after_entries, status = scan_current_turn_boundary(transcript_path, byte_cap=byte_cap)
    if status != STATUS_FOUND:
        return "", status
    return extract_user_typed_text(entry), status


def slice_current_turn(entries: list[dict]) -> tuple[dict | None, list[dict]]:
    """Return the last GENUINE user-typed entry and the entries after it.

    Delegates to `last_genuine_user_message` so the boundary skips tool_result
    entries and harness injections (compact-summary / isMeta), matching every
    other transcript-slicing caller in this module.

    A prior version used `is_user_message` directly as the boundary predicate.
    In Claude Code a tool_result is ALSO recorded as `{"type":"user",...}`, so
    in any tool-using turn the boundary landed on the trailing tool_result
    instead of the human's real last message -- the "current turn" collapsed to
    just the entries after that tool_result, silently discarding every actual
    tool call the turn made before it. That defeated any caller trying to find
    a probe/action within "the current turn" (confirmed: the passive-polling
    Stop guard's probe-allowance never saw a real tool_result in its own test
    suite, which is exactly what masked this)."""
    result = last_genuine_user_message(entries)
    return result[0], result[2]


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


def is_compact_summary(entry: object) -> bool:
    """Is this user-role entry the harness's post-compaction continuation prompt?

    Claude Code records it with `role=user` and real prose, so every text-shaped
    genuine-user test passes it — but no human typed it. The harness did, and it
    quotes the whole prior session back: file paths, error output, and an
    "Errors and fixes" section listing every defect the session touched.

    That makes it the WORST possible input to a trigger-phrase matcher, and the
    failure is self-amplifying: the more bug-fixing a session did, the more bug
    vocabulary the summary carries, so the guard is most certain to misfire on
    exactly the sessions that worked hardest. It also fires at the worst moment
    -- immediately after compaction, on every edit, until the next human message.
    Reproduced: a synthetic continuation prompt carrying only summary prose drove
    a `permissionDecision: deny` on an unrelated test edit. The live transcript
    that reproduced it carried 21 of these entries.

    Detected by the harness's own `isCompactSummary` flag rather than by matching
    the preamble's wording: the flag is structural, the wording is not ours and
    can change under us. `isMeta` covers the sibling harness-authored user entries
    for the same reason.

    Fails OPEN by design: an entry without the flag is treated as genuine. A
    missed summary costs a false positive the operator can override; a summary
    misread as human costs nothing but noise, while wrongly discarding a REAL bug
    report would silently disarm the guard.
    """
    if not isinstance(entry, dict):
        return False
    return bool(entry.get("isCompactSummary") or entry.get("isMeta"))


def extract_user_typed_text(entry: object) -> str:
    """The human-typed text of a user entry only.

    Excludes tool_result and tool_use blocks (those are tool I/O recorded under
    role=user in Claude Code, not anything the human typed), skips the harness's
    post-compaction continuation prompt (see `is_compact_summary`), and strips
    harness-injected spans. Returns "" for an entry that carries no genuine
    user text (e.g. a pure tool_result or a pure task-notification)."""
    if not isinstance(entry, dict):
        return ""
    if is_compact_summary(entry):
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


def extract_model_tool_calls_with_ids(entry: object) -> list[tuple[str, str]]:
    """Like `extract_model_tool_calls`, but returns a list of `(call_id,
    call_text)` pairs — one per distinct model tool CALL in this entry — so a
    caller can correlate a SPECIFIC invocation with its SPECIFIC result (see
    `extract_tool_outputs_with_ids`), instead of merely knowing that some call
    and some result both occurred somewhere in the turn.

    `call_id` is the Claude `tool_use` block's own `id`, or the Codex
    `function_call` payload's `call_id` — verified against real transcripts on
    this installation (a Claude tool_use block carries `id`; its answering
    tool_result carries the SAME value under `tool_use_id`. A Codex
    `function_call` payload carries `call_id`; its answering
    `function_call_output` carries the SAME value under `call_id`). A tool
    call with no id is skipped — it cannot be correlated to anything, and
    skipping (not fabricating an id) is the fail-closed direction: an
    uncorrelatable call can never open a caller's correlated-evidence gate.

    A SIBLING to `extract_model_tool_calls` — not a replacement. That function
    stays byte-unchanged for its own caller (check-bugfix-discipline.py, an
    invocation-only signal that never needed correlation). This function
    exists because joining two independent per-entry haystacks (one for all
    calls, one for all outputs, `\\n`-joined across the whole turn) lets an
    UNRELATED tool result satisfy a result check that no scan ever produced —
    e.g. a `Read` of a file that happens to quote the scanner's own clean-
    result text (this very module's test fixtures do) would satisfy an
    uncorrelated check with zero scan output at all. Demonstrated live against
    the shipped hook (adversarial gate finding, 2026-07-26): an empty-index
    scan plus an unrelated `Read` of a file containing the clean-result string
    ALLOWed under haystack-joining and must DENY under id correlation."""
    pairs: list[tuple[str, str]] = []
    if not isinstance(entry, dict):
        return pairs
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"function_call", "custom_tool_call"}:
        call_id = payload.get("call_id")
        if isinstance(call_id, str) and call_id:
            arguments = payload.get("arguments", payload.get("input", ""))
            text = strip_injected_spans(f"{payload.get('name', '')} {arguments}").strip()
            pairs.append((call_id, text))
        return pairs
    if not is_assistant_message(entry):
        return pairs
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            call_id = item.get("id")
            if not isinstance(call_id, str) or not call_id:
                continue
            parts: list[str] = []
            if "name" in item:
                parts.append(str(item["name"]))
            if "input" in item:
                try:
                    parts.append(json.dumps(item["input"]))
                except Exception:
                    parts.append(str(item["input"]))
            pairs.append((call_id, strip_injected_spans(" ".join(parts)).strip()))
    return pairs


def extract_tool_outputs_with_ids(entry: object) -> list[CorrelatedToolResult]:
    """The correlation-half counterpart to `extract_model_tool_calls_with_ids`:
    returns immutable `CorrelatedToolResult` records for this entry's tool
    OUTPUT — Claude `tool_result` content keyed by its own `tool_use_id`, or
    Codex `payload.function_call_output` (and its Codex top-level fallback
    shape) output keyed by its own `call_id`. NOT tool CALLS, NOT assistant
    prose, NOT user text. An output with no id is skipped — uncorrelatable,
    so it can never satisfy a caller's correlated check (fail-closed).

    Claude's optional Boolean `tool_result.is_error` is official provider
    behavior: exact `True` is an explicit failure, exact `False` or absence
    means no failure was observed, and any present non-Boolean is ambiguous.
    For Codex, only the observed installed/runtime 0.145.0 leading
    `Exit code: N` wrapper line is normalized; this repository does not claim
    that prefix as an official or stable Codex contract. Output text retains
    the existing injected-span stripping plus outer-trim semantics."""
    results: list[CorrelatedToolResult] = []
    if not isinstance(entry, dict):
        return results
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
        call_id = payload.get("call_id")
        if isinstance(call_id, str) and call_id:
            output_text = strip_injected_spans(str(payload.get("output", ""))).strip()
            results.append(CorrelatedToolResult(
                call_id, output_text, _codex_execution_status(output_text),
            ))
        return results
    # Codex top-level fallback shape (mirrors extract_text's own fallback).
    if entry.get("type") == "function_call_output":
        call_id = entry.get("call_id")
        if isinstance(call_id, str) and call_id:
            output_text = strip_injected_spans(str(entry.get("output", ""))).strip()
            results.append(CorrelatedToolResult(
                call_id, output_text, _codex_execution_status(output_text),
            ))
        return results

    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_result":
                continue
            call_id = item.get("tool_use_id")
            if not isinstance(call_id, str) or not call_id:
                continue
            inner = item.get("content")
            if isinstance(inner, str):
                text = inner
            elif inner is not None:
                text = extract_text({"content": inner})
            else:
                text = ""
            output_text = strip_injected_spans(text).strip()
            if "is_error" not in item or item.get("is_error") is False:
                execution_status = NO_OBSERVED_FAILURE
            elif item.get("is_error") is True:
                execution_status = EXPLICIT_FAILURE
            else:
                execution_status = AMBIGUOUS_STATUS
            results.append(CorrelatedToolResult(call_id, output_text, execution_status))
    return results


def _delivery_target(value: str) -> str | None:
    target = value.strip().strip("'\"` ,;:()[]{}").replace("\\", "/")
    while target.startswith("./"):
        target = target[2:]
    if not target or len(target) > 240 or target.startswith("/"):
        return None
    if re.match(r"^[A-Za-z]:/", target) or ".." in target.split("/"):
        return None
    return target


def _delivery_tool_identity(tool_name: object) -> str:
    if not isinstance(tool_name, str):
        return ""
    identity = tool_name.strip().lower()
    if identity.startswith("mcp__serena__"):
        return identity.removeprefix("mcp__serena__")
    if identity.startswith("serena."):
        return identity.removeprefix("serena.")
    if identity.startswith("tools."):
        return identity.removeprefix("tools.")
    return identity


def _delivery_input_object(tool_input: object) -> dict | None:
    if isinstance(tool_input, dict):
        return tool_input
    if not isinstance(tool_input, str):
        return None
    try:
        decoded = json.loads(tool_input)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _delivery_patch_text(tool_input: object) -> str:
    if isinstance(tool_input, dict):
        for key in ("patch", "input"):
            value = tool_input.get(key)
            if isinstance(value, str):
                return value
        return ""
    if not isinstance(tool_input, str):
        return ""
    stripped = tool_input.strip()
    if stripped.startswith("{"):
        decoded = _delivery_input_object(tool_input)
        if decoded is None:
            return ""
        return _delivery_patch_text(decoded)
    return tool_input


def _classify_delivery_call(tool_name: object, tool_input: object) -> tuple[str, tuple[str, ...]]:
    """Classify one direct host call from its typed identity and semantic input."""
    identity = _delivery_tool_identity(tool_name)
    candidates: list[str] = []
    if identity == "apply_patch":
        action_class = "mutation"
        candidates.extend(_PATCH_TARGET_RE.findall(_delivery_patch_text(tool_input)))
    elif identity in _DELIVERY_PATH_FIELDS:
        action_class = "mutation"
        input_object = _delivery_input_object(tool_input)
        if input_object is not None:
            for field in _DELIVERY_PATH_FIELDS[identity]:
                candidate = input_object.get(field)
                if isinstance(candidate, str):
                    candidates.append(candidate)
                    break
    else:
        action_class = "other"
    targets: list[str] = []
    for candidate in candidates:
        normalized = _delivery_target(candidate)
        if normalized and normalized not in targets:
            targets.append(normalized)
        if len(targets) >= 16:
            break
    return action_class, tuple(targets)


def _extract_delivery_calls_with_ids(entry: object) -> list[tuple[str, str, tuple[str, ...]]]:
    """Extract only direct host-recorded calls with typed delivery semantics."""
    calls: list[tuple[str, str, tuple[str, ...]]] = []
    if not isinstance(entry, dict):
        return calls
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"function_call", "custom_tool_call"}:
        call_id = payload.get("call_id")
        if isinstance(call_id, str) and call_id:
            tool_input = payload.get("arguments", payload.get("input"))
            action_class, targets = _classify_delivery_call(payload.get("name"), tool_input)
            calls.append((call_id, action_class, targets))
        return calls
    if not is_assistant_message(entry):
        return calls
    content = entry.get("content")
    if content is None:
        message = entry.get("message")
        if isinstance(message, dict):
            content = message.get("content")
    if not isinstance(content, list):
        return calls
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "tool_use":
            continue
        call_id = item.get("id")
        if not isinstance(call_id, str) or not call_id:
            continue
        action_class, targets = _classify_delivery_call(item.get("name"), item.get("input"))
        calls.append((call_id, action_class, targets))
    return calls


def _delivery_result_flags(entry: object) -> list[tuple[str, bool, bool]]:
    """Provider-aware host result status; ambiguous output grants no credit."""
    if not isinstance(entry, dict):
        return []
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
        call_id = payload.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            return []
        output = strip_injected_spans(str(payload.get("output", ""))).strip()
        first_line = output.splitlines()[0] if output else ""
        execution_status = _codex_execution_status(output)
        succeeded = execution_status == NO_OBSERVED_FAILURE and (
            first_line == "Exit code: 0" or first_line.startswith("Script completed")
        )
        failed = execution_status == EXPLICIT_FAILURE or first_line.startswith(("Script failed", "Script error:"))
        return [(call_id, succeeded, failed)]
    content = entry.get("content")
    if content is None:
        message = entry.get("message")
        if isinstance(message, dict):
            content = message.get("content")
    flags: list[tuple[str, bool, bool]] = []
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_result":
                continue
            call_id = item.get("tool_use_id")
            if not isinstance(call_id, str) or not call_id:
                continue
            is_error = item.get("is_error")
            flags.append((call_id, is_error is False, is_error is True))
    return flags


def correlated_delivery_activity(entries: list[dict], *, event_cap: int = 64) -> list[DeliveryActivity]:
    """Normalize correlated call/results without retaining transcript content."""
    calls: dict[str, tuple[str, tuple[str, ...]]] = {}
    results: dict[str, tuple[bool, bool]] = {}
    order: list[str] = []
    for entry in entries:
        for call_id, action_class, target_ids in _extract_delivery_calls_with_ids(entry):
            if call_id not in calls and len(order) < event_cap:
                calls[call_id] = (action_class, target_ids)
                order.append(call_id)
        for call_id, succeeded, failed in _delivery_result_flags(entry):
            if call_id not in results:
                results[call_id] = (succeeded, failed)
    activities: list[DeliveryActivity] = []
    for call_id in order:
        result_flags = results.get(call_id, (False, False))
        action_class, target_ids = calls[call_id]
        succeeded, failed = result_flags
        activities.append(DeliveryActivity(
            action_class,
            target_ids,
            succeeded,
            failed,
        ))
    return activities


def extract_model_shell_commands_with_ids(entry: object) -> list[tuple[str, str]]:
    """Like `extract_model_tool_calls_with_ids`, but returns the RAW SHELL
    COMMAND STRING for each shell-executing tool call, keyed by call id --
    NOT a flattened `"<tool name> <full JSON input>"` blob. A consumer that
    needs to parse the command the same way a live PreToolUse envelope's
    `tool_input["command"]` would be parsed (shlex tokenization, command-
    position / execution-vs-mention detection) cannot work from the
    flattened blob at all -- `Bash {"command": "bash x.sh", "description":
    "..."}` is not a parseable shell command, the flattening was only ever
    meant for keyword search, not structural analysis.

    Claude: any `tool_use` whose `input` is a dict with a STRING `command`
    field (the Bash tool's own shape; not filtered by tool `name`, since
    `command` is the load-bearing field regardless of what the tool happens
    to be called).
    Codex: a `function_call` payload whose `arguments` is a JSON string that
    parses to an object with a STRING `command` field (verified against 65
    real `function_call` entries in this machine's own `~/.codex/
    archived_sessions/*.jsonl`, 2026-07-26 -- all 65 used a plain string,
    none an argv-array form; real payloads carry `name: "shell_command"`,
    NOT the `"shell"` name this module's own test fixtures had assumed, but
    this extractor does not filter on `name` at all, so that naming
    difference cannot cause a miss). A missing, non-string, or unparseable/
    array-form `command` is skipped.

    A call with no id, same as the sibling extractors, is skipped entirely
    -- fail-closed: an uncorrelatable call can never be credited as a scan
    execution by a caller keying off this function's output."""
    pairs: list[tuple[str, str]] = []
    if not isinstance(entry, dict):
        return pairs
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "function_call":
        call_id = payload.get("call_id")
        if isinstance(call_id, str) and call_id:
            raw_args = payload.get("arguments")
            command = None
            if isinstance(raw_args, str):
                try:
                    parsed = json.loads(raw_args)
                except Exception:
                    parsed = None
                if isinstance(parsed, dict) and isinstance(parsed.get("command"), str):
                    command = parsed["command"]
            if command:
                pairs.append((call_id, strip_injected_spans(command)))
        return pairs
    if not is_assistant_message(entry):
        return pairs
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            call_id = item.get("id")
            if not isinstance(call_id, str) or not call_id:
                continue
            input_obj = item.get("input")
            if isinstance(input_obj, dict) and isinstance(input_obj.get("command"), str):
                pairs.append((call_id, strip_injected_spans(input_obj["command"])))
    return pairs


# Status vocabulary for `scan_current_turn_boundary` and its two
# projections (`current_turn_entries`, `last_genuine_user_text`) -- defined
# ONCE here so neither projection can restate it as a second literal set
# that quietly drifts from this one (see work-items/bugs/2026-07-26-two-
# owners-of-the-current-turn-boundary-in-one-module.md). Existing callers
# that compare against the raw string ("found", "absent", ...) are
# unaffected: these constants ARE those exact strings, not a new
# representation of them.
STATUS_FOUND = "found"
STATUS_ABSENT = "absent"
STATUS_UNREADABLE = "unreadable"
STATUS_NOT_IN_WINDOW = "not-in-window"
TURN_BOUNDARY_STATUSES = (STATUS_FOUND, STATUS_ABSENT, STATUS_UNREADABLE, STATUS_NOT_IN_WINDOW)


def scan_current_turn_boundary(transcript_path: str, *, byte_cap: int) -> tuple[dict | None, list[dict], str]:
    """THE single bounded REVERSE scan to the CURRENT TURN's boundary -- the
    most recent genuine user-typed message -- without ever reading the whole
    transcript file. `current_turn_entries` and `last_genuine_user_text` are
    both thin projections of this function's return value; neither
    re-implements the scan loop or the boundary predicate (see
    work-items/bugs/2026-07-26-two-owners-of-the-current-turn-boundary-in-
    one-module.md -- they used to each run this loop independently, which is
    exactly the defect this function removes).

    Returns `(boundary_entry, after_entries, status)`:

      boundary_entry -- the last genuine user-typed transcript entry (dict),
                         or None when status != STATUS_FOUND
      after_entries  -- entries strictly AFTER boundary_entry, in original
                         (forward) order; [] when status != STATUS_FOUND, or
                         when the boundary is the very last record in the
                         window
      status         -- one of TURN_BOUNDARY_STATUSES:
          STATUS_FOUND          -- boundary_entry located within byte_cap
          STATUS_ABSENT         -- transcript_path is empty/None
          STATUS_UNREADABLE     -- the path does not resolve to a readable
                                    file
          STATUS_NOT_IN_WINDOW  -- no genuine user message within byte_cap
                                    bytes of end-of-file

    BOUNDARY DETECTION IS DELEGATED, NEVER REIMPLEMENTED. Each candidate
    window's parsed entries are handed to `slice_current_turn`, which itself
    delegates to `last_genuine_user_message` -- the SAME function every
    other transcript-slicing caller in this module uses. This function owns
    ONLY the I/O half of the scan (chunked reads, the doubling retry,
    byte_cap, decode, per-line parse); it must never re-test
    `is_user_message` or "typed text" itself. That split is load-bearing:
    `slice_current_turn`'s own docstring records a real, previously-shipped
    defect where a prior version used `is_user_message` ALONE as the
    boundary predicate -- a tool_result is ALSO recorded as
    `{"type":"user",...}` in Claude Code, so in any tool-using turn the
    boundary landed on the trailing tool_result instead of the human's real
    last message, silently discarding every actual tool call the turn made
    before it. Routing through `slice_current_turn` here means this
    function cannot independently reopen that defect by re-deriving the
    predicate itself.

    WHY A SEPARATE SCAN FROM `read_transcript_tail` (design.md,
    review-round-cap-enforcement, S4.5 / F2). The turn boundary (where the
    CURRENT turn started) is a SEMANTIC position; a fixed record window
    (`read_transcript_tail`'s `n`) is a COST CAP. Conflating them under one
    constant loses the boundary whenever a turn produces more records than
    the window -- measured at 36.8% of real turns for n=100 and still 19.5%
    for n=200 (a bigger constant does not fix the defect class, it only
    moves the failure rate). This function anchors on the boundary itself:
    start with a small trailing read (1 MiB) and only read MORE when that
    chunk does not contain the boundary, doubling up to `byte_cap`. Measured
    cheaper on both axes than the fixed-window approach: 8 records / 0.6 ms
    to find the boundary on the largest transcript measured here, versus
    `read_transcript_tail`'s whole-file `read_text()` at 1,482 ms for the
    same file. This refactor's own regression measurement (this session, a
    different machine and fixture than the figures above, so not a literal
    reproduction of them): a 100 MiB synthetic transcript, 8 MiB byte_cap,
    20 reps of the bounded scan versus 5 reps of `read_transcript_tail` as a
    whole-file-read control -- bounded scan p95 9.03 ms against a 239.96 ms
    control mean (see tests/test_hook_common.py's opt-in `TestScanCost`,
    `ORCHESTRARIUM_RUN_SCAN_COST_BENCHMARK=1`). The bounded scan stays
    roughly two orders of magnitude cheaper than the whole-file control,
    which is the property this refactor is required to preserve; the
    absolute numbers differ from the design-time citation because they were
    captured on a different machine under different load, not because the
    scan's cost characteristics changed.

    `read_transcript_tail` and every other export in this module besides
    `current_turn_entries` / `last_genuine_user_text` are BYTE-UNCHANGED by
    this function -- a caller that needs a whole-turn-agnostic tail keeps
    using `read_transcript_tail` exactly as before. `read_transcript_tail`'s
    own whole-file-read cost on a blocking path is a SEPARATE, still-open
    defect (work-items/bugs/2026-07-26-transcript-tail-reads-the-whole-
    file-on-a-blocking-path.md), not fixed here -- this function makes that
    fix EASIER, not harder, if it later routes callers through a shared
    chunked-read primitive of its own, because the doubling-read mechanics
    now have exactly one home to extend rather than two to keep in sync."""
    if not transcript_path:
        return None, [], STATUS_ABSENT
    tp = Path(transcript_path)
    try:
        if not tp.is_file():
            return None, [], STATUS_UNREADABLE
        file_size = tp.stat().st_size
    except Exception:
        return None, [], STATUS_UNREADABLE

    chunk = min(1024 * 1024, byte_cap)  # start at 1 MiB, never exceeding byte_cap
    while True:
        read_size = min(chunk, file_size)
        start_offset = file_size - read_size
        try:
            with tp.open("rb") as f:
                f.seek(start_offset)
                raw = f.read(read_size)
        except Exception:
            return None, [], STATUS_UNREADABLE

        text_blob = raw.decode("utf-8", errors="replace")
        lines = text_blob.split("\n")
        # Discard the leading partial line UNLESS the read started at true
        # file offset 0 (in which case there is no partial line -- the read
        # begins at a real record boundary). A doubling retry re-includes
        # the discarded partial line whole, so this is safe rather than lossy.
        if start_offset > 0 and lines:
            lines = lines[1:]

        entries: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if isinstance(entry, dict):
                entries.append(entry)

        boundary_entry, after_entries = slice_current_turn(entries)
        if boundary_entry is not None:
            return boundary_entry, after_entries, STATUS_FOUND

        if start_offset == 0:
            # Read the whole file and still found no boundary -- there is
            # nothing more to read.
            return None, [], STATUS_NOT_IN_WINDOW
        if chunk >= byte_cap:
            return None, [], STATUS_NOT_IN_WINDOW
        chunk = min(chunk * 2, byte_cap)


def current_turn_entries(transcript_path: str, *, byte_cap: int) -> tuple[list[dict], str]:
    """The CURRENT TURN's entries -- the after-boundary PROJECTION of
    `scan_current_turn_boundary` (see that function for the full bounded-
    REVERSE-scan rationale, the delegation to `slice_current_turn` for
    boundary detection, and the complete status vocabulary in
    `TURN_BOUNDARY_STATUSES`).

    Returns `(entries, status)`:

      entries -- every parsed record strictly AFTER the boundary, in
                 original (forward) order, when `status == STATUS_FOUND`
                 (possibly [] if the boundary is the very last record in the
                 window); [] for every other status
      status  -- one of `TURN_BOUNDARY_STATUSES` (STATUS_FOUND,
                 STATUS_ABSENT, STATUS_UNREADABLE, STATUS_NOT_IN_WINDOW)

    Existing callers relying on this exact signature and status vocabulary:
    `dispatch_sentinels.py` (the round-depth observer) and this module's own
    test suite."""
    _boundary_entry, after_entries, status = scan_current_turn_boundary(transcript_path, byte_cap=byte_cap)
    return after_entries, status


def emit_advisory(envelope: object, message: str, *, default_event: str = "PreToolUse") -> None:
    """Deliver a warn-only advisory to the MODEL, never the operator terminal.

    Writes ``{"hookSpecificOutput": {"hookEventName": <event>, "additionalContext":
    message}}`` as one line of JSON to stdout and returns (the caller still exits
    0 itself -- this function does not exit the process). This REPLACES the
    stderr-plus-exit-1 delivery every warn-only PreToolUse audit in this pack used
    before it, which was measured to reach NOBODY: on Claude Code 2.1.220 a
    non-blocking exit-1's stderr lands in the transcript record but is
    model-invisible, and on Codex CLI 0.145.0 the non-2-exit branch never even
    copies stderr (the operator console shows a bare "PreToolUse Failed" label).
    `hookSpecificOutput.additionalContext` on `PreToolUse`, by contrast, was
    measured to reach the model on BOTH runtimes when emitted on stdout with exit
    0. See work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-
    its-sibling-calls-broken.md for the full falsification-controlled measurement.

    THE EVENT NAME TRAP (why `default_event` exists but is a FALLBACK, never a
    hardcoded override): Claude Code silently discards the ENTIRE
    `hookSpecificOutput` object when `hookEventName` does not match the event that
    ACTUALLY fired -- measured, with the runtime emitting "Hook returned incorrect
    event name: expected 'PreToolUse' but got 'PostToolUse'". `envelope`'s own
    `hook_event_name` field is therefore read FIRST and used verbatim whenever
    present; `default_event` is used ONLY when the envelope carries no
    `hook_event_name` at all (e.g. a hand-built test envelope that omits it).
    Every current caller of this helper is registered exclusively on `PreToolUse`,
    which is why that is the documented default -- it is not a license for a
    caller to skip reading the envelope's own field.

    Exit-0 framing bonus: this also drops the misleading `hook_non_blocking_error`
    label a warn-only audit's exit-1 form carried on the runtime's own transcript
    -- a warn-only audit allowing its own tool call should never present as an
    error. Fails open: any exception here is swallowed, matching the fail-open
    posture of every caller.
    """
    event = envelope.get("hook_event_name") if isinstance(envelope, dict) else None
    if not isinstance(event, str) or not event:
        event = default_event
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": message,
        }
    }
    try:
        print(json.dumps(payload, ensure_ascii=True))
    except Exception:
        pass


def emit_session_start_context(message: str) -> None:
    """Emit a SessionStart `hookSpecificOutput` context block as compact,
    literal-UTF-8 JSON -- the byte-parity contract this pack's Python
    SessionStart reminders (mcp-usage-reminder.py, agents-mode-reminder.py)
    were historically checked against their hand-authored shell siblings:
    ``{"hookSpecificOutput":{"hookEventName":"SessionStart",
    "additionalContext":"..."}}``, no separator whitespace, and a literal
    (non-escaped) UTF-8 em-dash rather than `\\u2014` -- verified byte-for-byte
    against a captured legacy reminder-wrapper run on 2026-07-27 (the shell
    heredoc form matches once its own CRLF-vs-LF line ending, which is a
    platform artifact of `[Console]::Out.WriteLine` vs a bash heredoc, not a
    content difference, is set aside).

    DELIBERATELY NOT `emit_advisory` above: that function hardcodes
    `ensure_ascii=True` and default `json.dumps` spacing for its own PreToolUse
    audit callers (a different, already-shipped contract this function must
    not silently change), and always reads `envelope.get("hook_event_name")`
    -- every caller of THIS function is a SessionStart reminder with no such
    envelope-declared variability, so the event name is hardcoded here,
    matching every SessionStart reminder's own historical shell source (none of
    which read `hook_event_name` from an envelope either).

    UTF-8 SAFETY: reconfigures stdout to UTF-8 before writing, mirroring the
    `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` line every
    legacy SessionStart reminder set at its own top. Without this, a
    non-UTF-8 system codepage (e.g. `cp437`, which cannot encode U+2014) can
    raise `UnicodeEncodeError` on a literal em-dash and silently drop the
    whole reminder -- confirmed empirically: `'\\u2014'.encode('cp437')`
    raises, `'\\u2014'.encode('cp1251')` does not, so this is a real,
    codepage-dependent failure mode, not a theoretical one. `reconfigure` is
    itself wrapped in its own `try`/`except` (it is a Python 3.7+
    `TextIOWrapper` method; absent or failing, the write is attempted anyway
    under whatever encoding stdout already had).

    Fails open: any exception here (including the write itself) is
    swallowed; the caller still exits 0."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        }
    }
    try:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        pass
