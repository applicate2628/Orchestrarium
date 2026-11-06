"""Conservative owned-configuration renderers. No filesystem writes or host operations."""
from __future__ import annotations

import hashlib
import json
import re
import tomllib

MARKERS = {
    "copilot": ("<!-- BEGIN ORCHESTRARIUM COPILOT MANAGED -->", "<!-- END ORCHESTRARIUM COPILOT MANAGED -->"),
    "codex": ("<!-- BEGIN ORCHESTRARIUM CODEX PACK -->", "<!-- END ORCHESTRARIUM CODEX PACK -->"),
    "claude": ("<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->", "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->"),
    "shared": ("<!-- BEGIN ORCHESTRARIUM SHARED MANAGED -->", "<!-- END ORCHESTRARIUM SHARED MANAGED -->"),
}


def owned_block(text: str, kind: str, document_context) -> tuple[int, int] | None:
    begin, end = MARKERS[kind]
    visible, _ = document_context(text)
    starts = list(re.finditer(r"(?m)^" + re.escape(begin) + r"\r?$", visible))
    stops = list(re.finditer(r"(?m)^" + re.escape(end) + r"\r?$", visible))
    if not starts and not stops:
        return None
    if len(starts) != 1 or len(stops) != 1 or starts[0].start() >= stops[0].start():
        raise ValueError("Ambiguous managed document block")
    return starts[0].start(), stops[0].start() + len(end)


def text_receipt_digest(text: str) -> str:
    """Hash the existing LF-decoded UTF-8 configuration-text contract."""
    canonical = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def block_digest(text: str, kind: str, document_context) -> str | None:
    bounds = owned_block(text, kind, document_context)
    if bounds is None:
        return None
    return text_receipt_digest(text[bounds[0]:bounds[1]])


def remove_owned_block(text: str, kind: str, expected: str, document_context) -> str:
    bounds = owned_block(text, kind, document_context)
    if bounds is None:
        return text
    if block_digest(text, kind, document_context) != expected:
        raise ValueError("Modified managed document block preserved")
    start, stop = bounds
    # Keep every byte outside the owned markers, including user imports/comments.
    return text[:start] + text[stop:]


def merge_owned_block(text: str | None, kind: str, payload: str, document_context,
                      *, expected_digest: str | None = None) -> str:
    """Render an install/update without claiming user edits or marker examples.

    The existing receipt supplies the digest for updates. Publication and
    recording the resulting digest remain with the installation transaction.
    """
    begin, end = MARKERS[kind]
    if (text is not None and not isinstance(text, str)
            or not isinstance(payload, str) or not payload or not payload.endswith("\n")
            or "\0" in payload
            or any(marker.removesuffix(" -->") in payload
                   for pair in MARKERS.values() for marker in pair)):
        raise ValueError("Invalid managed document payload")
    current = "" if text is None else text
    bounds = owned_block(current, kind, document_context)
    visible, _ = document_context(current)
    count = 0 if bounds is None else 1
    if any(visible.count(marker.removesuffix(" -->")) != count for marker in (begin, end)):
        raise ValueError("Ambiguous managed document block")
    block = begin + "\n" + payload + end
    if bounds is None:
        if expected_digest is not None:
            raise ValueError("Missing recorded managed document block")
        start = 0
        result = block + "\n" + ("\n" + current if current else "")
    else:
        if expected_digest is None or block_digest(current, kind, document_context) != expected_digest:
            raise ValueError("Unowned or modified managed document block preserved")
        start, stop = bounds
        result = current[:start] + block + current[stop:]
    # Source fences must not swallow the closing marker or foreign user text.
    if owned_block(result, kind, document_context) != (start, start + len(block)):
        raise ValueError("Invalid managed document frame")
    return result


def remove_native_roles(payload: bytes, registrations: dict[str, dict[str, str]]) -> bytes:
    """Remove exact generated tables; preserve other TOML bytes verbatim."""
    text = payload.decode("utf-8")
    parsed = tomllib.loads(text)
    agents = parsed.get("agents", {})
    if type(agents) is not dict:
        raise ValueError("Invalid native role configuration")
    lines = text.splitlines(keepends=True)
    spans = []
    for name, expected in registrations.items():
        if not re.fullmatch(r"[a-z0-9_-]+", name):
            raise ValueError("Invalid native role name")
        if name not in agents:
            continue
        if agents[name] != expected or set(expected) != {"description", "config_file"}:
            raise ValueError("Modified native role preserved: " + name)
        indices = [i for i, line in enumerate(lines) if line.strip() == f"[agents.{name}]"]
        if len(indices) != 1:
            raise ValueError("Noncanonical native role table preserved: " + name)
        start = indices[0]
        stop = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
        actual = tuple(line.strip() for line in lines[start:stop] if line.strip())
        expected_lines = (f"[agents.{name}]",
            "description = " + json.dumps(expected["description"], ensure_ascii=False),
            "config_file = " + json.dumps(expected["config_file"], ensure_ascii=False))
        if actual != expected_lines:
            raise ValueError("Customized native role table preserved: " + name)
        spans.append((start, stop))
    for start, stop in sorted(spans, reverse=True):
        del lines[start:stop]
    result = "".join(lines).encode("utf-8")
    after = tomllib.loads(result.decode("utf-8"))
    expected_data = dict(parsed)
    if "agents" in expected_data:
        expected_data["agents"] = {k: v for k, v in agents.items() if k not in registrations}
        if not expected_data["agents"]:
            expected_data.pop("agents")
    # An explicitly retained empty parent [agents] is harmless and still user-owned.
    if after.get("agents") == {} and "agents" not in expected_data:
        after.pop("agents")
    if after != expected_data:
        raise ValueError("Unrelated native configuration changed")
    return result


def remove_native_features(payload: bytes, owned: dict[str, bool]) -> bytes:
    """Remove only still-equal feature values introduced by this installation."""
    text = payload.decode("utf-8")
    parsed = tomllib.loads(text)
    features = parsed.get("features", {})
    if type(features) is not dict:
        raise ValueError("Invalid native feature configuration")
    selected = {key: value for key, value in owned.items()
                if type(features.get(key)) is bool and features[key] is value}
    if not selected:
        return payload
    lines = text.splitlines(keepends=True)
    headers = [i for i, line in enumerate(lines) if line.strip() == "[features]"]
    if len(headers) != 1:
        raise ValueError("Customized feature table preserved")
    start = headers[0]
    stop = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
    indices = []
    for key, value in selected.items():
        expected = key + " = " + ("true" if value else "false")
        found = [i for i in range(start + 1, stop) if lines[i].strip() == expected]
        if len(found) != 1:
            raise ValueError("Customized feature assignment preserved: " + key)
        indices.extend(found)
    for index in sorted(indices, reverse=True):
        del lines[index]
    result = "".join(lines).encode("utf-8")
    expected_data = dict(parsed)
    expected_data["features"] = {key: value for key, value in features.items() if key not in selected}
    if tomllib.loads(result.decode("utf-8")) != expected_data:
        raise ValueError("Unrelated native features changed")
    return result
