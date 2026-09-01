#!/usr/bin/env python3
"""Pure, deterministic reducer for bounded solution-attempt V3 events."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata


OK = "SOL-OK"
EXACT_REPLAY = "SOL-R000-EXACT-REPLAY"
STATE_INVALID = "SOL-E001-STATE-INVALID"
CLASS_REJECTED = "SOL-E003-CLASS-REJECTED"
REASSESSMENT_REQUIRED = "SOL-E004-REASSESSMENT-REQUIRED"
IDENTITY_UNAUTHORED = "SOL-E005-IDENTITY-UNAUTHORED"
RECEIPT_STALE = "SOL-E006-RECEIPT-STALE"
OPERATION_CONFLICT = "SOL-E010-OPERATION-CONFLICT"

MAX_CAPSULE_BYTES = 4096
MAX_JSON_DEPTH = 8
MAX_OBJECTS = 64
MAX_LIST_ITEMS = 256
MAX_ID_LENGTH = 128
MAX_PATH_LENGTH = 512

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", re.ASCII)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_RFC3339_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$",
    re.ASCII,
)
_CAPSULE_KEYS = {"version", "declarationSetId", "objects", "baseline", "author"}
_OBJECT_KEYS = {
    "decisionObjectId",
    "mutationSurfaces",
    "solutionClasses",
    "initialClassId",
    "initialAttemptId",
    "guardIds",
}
GUARD_IDS = {
    "mutation-surface-subset",
    "no-new-dependency",
    "no-new-contract-risk-owner",
    "forbidden-mechanism-tag",
    "required-oracle",
    "item-specific-stop",
}
EVENT_TYPES = {
    "solution-bootstrap",
    "attempt-admission",
    "revise-binding",
    "guard-triggered",
    "reassessment",
    "dispatch-admitted",
    "launch-claimed",
    "spawn-boundary",
    "launch-started",
    "launch-terminal",
    "process-reaped",
    "template-transition",
    "projection-settled",
}
_EVENT_KEYS = {
    "schemaVersion",
    "eventId",
    "operationId",
    "fingerprint",
    "priorHead",
    "recordedAt",
    "eventType",
    "payload",
}
_STATE_KEYS = {
    "head",
    "operations",
    "declarationSetId",
    "capsuleDigest",
    "capsule",
    "objects",
    "attempts",
    "activeAttemptByObject",
    "rejectedAttempts",
    "reviewRunIdsByAttempt",
    "rejectedClasses",
    "reassessmentFrontier",
    "launchState",
    "terminalOutcome",
}
_ATTEMPT_KEYS = {"decisionObjectId", "solutionClassId", "mutationSurfaces"}
_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_PRE_SPAWN_OUTCOMES = {
    "abandoned-before-spawn",
    "cancelled-before-spawn",
    "failed-before-spawn",
}
_PRE_AUTH_OUTCOMES = {
    "spawn-failed",
    "spawn-outcome-unknown",
    "cancelled-before-authentication",
    "timed-out-before-authentication",
    "unadoptable-child-terminated",
}
_STARTED_OUTCOMES = {
    "pass",
    "revise",
    "failed",
    "cancelled",
    "timed-out",
    "orphaned-after-start",
}
_TERMINAL_OUTCOMES = _PRE_SPAWN_OUTCOMES | _PRE_AUTH_OUTCOMES | _STARTED_OUTCOMES


class _DuplicateKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _depth(value: object) -> int:
    maximum = 0
    pending: list[tuple[object, int]] = [(value, 0)]
    while pending:
        current, current_depth = pending.pop()
        maximum = max(maximum, current_depth)
        if maximum > MAX_JSON_DEPTH:
            return maximum
        if isinstance(current, dict):
            pending.extend((child, current_depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, current_depth + 1) for child in current)
    return maximum


def _is_id(value: object) -> bool:
    return isinstance(value, str) and len(value) <= MAX_ID_LENGTH and _ID_RE.fullmatch(value) is not None


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _closed_list(value: object, *, maximum: int = MAX_LIST_ITEMS) -> bool:
    return isinstance(value, list) and 0 < len(value) <= maximum


def _valid_surface(value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > MAX_PATH_LENGTH:
        return False
    if value != unicodedata.normalize("NFC", value):
        return False
    if "\\" in value or ":" in value or value.startswith("/") or "//" in value:
        return False
    parts = value.split("/")
    for part in parts:
        normalized = unicodedata.normalize("NFKC", part)
        if normalized in {"", ".", ".."} or normalized.endswith((".", " ")):
            return False
        stem = normalized.split(".", 1)[0].upper()
        if stem in _RESERVED_WINDOWS_NAMES:
            return False
        if any(ord(character) < 32 or character in '<>:"|?*' for character in normalized):
            return False
    return True


def _canonical_surface(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _validate_capsule(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != _CAPSULE_KEYS:
        return False
    if value.get("version") != 1:
        return False
    if not _is_id(value.get("declarationSetId")) or not _is_digest(value.get("baseline")):
        return False
    if not _is_id(value.get("author")):
        return False
    objects = value.get("objects")
    if not _closed_list(objects, maximum=MAX_OBJECTS):
        return False

    object_ids: set[str] = set()
    class_ids: set[str] = set()
    attempt_ids: set[str] = set()
    all_surfaces: list[str] = []
    assert isinstance(objects, list)
    for entry in objects:
        if not isinstance(entry, dict) or set(entry) != _OBJECT_KEYS:
            return False
        object_id = entry.get("decisionObjectId")
        initial_attempt = entry.get("initialAttemptId")
        if not _is_id(object_id) or object_id in object_ids:
            return False
        if not _is_id(initial_attempt) or initial_attempt in attempt_ids:
            return False
        object_ids.add(object_id)
        attempt_ids.add(initial_attempt)

        classes = entry.get("solutionClasses")
        if not _closed_list(classes) or any(not _is_id(item) for item in classes):
            return False
        assert isinstance(classes, list)
        if len(classes) != len(set(classes)) or any(item in class_ids for item in classes):
            return False
        class_ids.update(classes)
        if entry.get("initialClassId") not in classes:
            return False

        guards = entry.get("guardIds")
        if not _closed_list(guards) or any(item not in GUARD_IDS for item in guards):
            return False
        assert isinstance(guards, list)
        if len(guards) != len(set(guards)):
            return False

        surfaces = entry.get("mutationSurfaces")
        if not _closed_list(surfaces) or any(not _valid_surface(item) for item in surfaces):
            return False
        assert isinstance(surfaces, list)
        all_surfaces.extend(surfaces)

    canonical = [_canonical_surface(item) for item in all_surfaces]
    if len(canonical) != len(set(canonical)):
        return False
    for index, left in enumerate(canonical):
        for right in canonical[index + 1 :]:
            if left.startswith(right + "/") or right.startswith(left + "/"):
                return False
    return True


def decode_capsule(raw: str | bytes | dict) -> dict:
    """Decode one bounded capsule and return a stable result object."""

    try:
        if isinstance(raw, dict):
            value = copy.deepcopy(raw)
            encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        elif isinstance(raw, (str, bytes)):
            encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
            if len(encoded) > MAX_CAPSULE_BYTES:
                return {"result": STATE_INVALID, "capsule": None}
            value = json.loads(encoded, object_pairs_hook=_reject_duplicate_keys)
        else:
            return {"result": STATE_INVALID, "capsule": None}
    except (UnicodeError, json.JSONDecodeError, _DuplicateKey, RecursionError, TypeError, ValueError):
        return {"result": STATE_INVALID, "capsule": None}
    if len(encoded) > MAX_CAPSULE_BYTES or _depth(value) > MAX_JSON_DEPTH or not _validate_capsule(value):
        return {"result": STATE_INVALID, "capsule": None}
    return {"result": OK, "capsule": copy.deepcopy(value)}


def _payload_is(payload: object, keys: set[str]) -> bool:
    return isinstance(payload, dict) and set(payload) == keys


def _event_shape_valid(event: object) -> bool:
    if not isinstance(event, dict) or set(event) != _EVENT_KEYS:
        return False
    if event.get("schemaVersion") != 3 or event.get("eventType") not in EVENT_TYPES:
        return False
    if not _is_id(event.get("eventId")) or not _is_id(event.get("operationId")):
        return False
    if not _is_digest(event.get("fingerprint")):
        return False
    prior_head = event.get("priorHead")
    if prior_head != "GENESIS" and not _is_digest(prior_head):
        return False
    recorded_at = event.get("recordedAt")
    return isinstance(recorded_at, str) and _RFC3339_UTC_RE.fullmatch(recorded_at) is not None


def _unchanged(state: dict | None, result: str) -> dict:
    return {"result": result, "changed": False, "state": copy.deepcopy(state)}


def _capsule_bytes(capsule: dict) -> bytes:
    return json.dumps(
        capsule,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _is_unique_id_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and all(_is_id(item) for item in value)
        and len(value) == len(set(value))
    )


def _state_shape_valid(state: object) -> bool:
    if not isinstance(state, dict) or set(state) != _STATE_KEYS:
        return False
    head = state["head"]
    if not _is_digest(head):
        return False
    operations = state["operations"]
    if not isinstance(operations, dict) or not operations or any(
        not _is_id(operation_id) or not _is_digest(fingerprint)
        for operation_id, fingerprint in operations.items()
    ) or head not in operations.values():
        return False

    decoded = decode_capsule(state["capsule"])
    if decoded["result"] != OK:
        return False
    capsule = decoded["capsule"]
    if (
        state["declarationSetId"] != capsule["declarationSetId"]
        or state["capsuleDigest"] != hashlib.sha256(_capsule_bytes(capsule)).hexdigest()
    ):
        return False

    expected_objects = {
        entry["decisionObjectId"]: entry
        for entry in capsule["objects"]
    }
    objects = state["objects"]
    if not isinstance(objects, dict) or objects != expected_objects:
        return False

    declared_classes: set[str] = set()
    initial_attempts: dict[str, dict] = {}
    for object_id, declaration in expected_objects.items():
        declared_classes.update(declaration["solutionClasses"])
        initial_attempts[declaration["initialAttemptId"]] = {
            "decisionObjectId": object_id,
            "solutionClassId": declaration["initialClassId"],
            "mutationSurfaces": declaration["mutationSurfaces"],
        }

    attempts = state["attempts"]
    if not isinstance(attempts, dict) or not attempts:
        return False
    for attempt_id, attempt in attempts.items():
        if not _is_id(attempt_id) or not isinstance(attempt, dict) or set(attempt) != _ATTEMPT_KEYS:
            return False
        object_id = attempt["decisionObjectId"]
        declaration = expected_objects.get(object_id)
        surfaces = attempt["mutationSurfaces"]
        if (
            declaration is None
            or attempt["solutionClassId"] not in declaration["solutionClasses"]
            or not isinstance(surfaces, list)
            or not surfaces
            or any(not isinstance(surface, str) for surface in surfaces)
            or len(surfaces) != len(set(surfaces))
            or set(surfaces) - set(declaration["mutationSurfaces"])
        ):
            return False
    if any(attempts.get(attempt_id) != projection for attempt_id, projection in initial_attempts.items()):
        return False

    active = state["activeAttemptByObject"]
    if not isinstance(active, dict) or set(active) != set(expected_objects):
        return False
    for object_id, attempt_id in active.items():
        attempt = attempts.get(attempt_id)
        if not _is_id(attempt_id) or attempt is None or attempt["decisionObjectId"] != object_id:
            return False

    rejected_attempts = state["rejectedAttempts"]
    if not isinstance(rejected_attempts, dict) or set(rejected_attempts) != declared_classes:
        return False
    for class_id, rejected_ids in rejected_attempts.items():
        if not _is_unique_id_list(rejected_ids):
            return False
        if any(
            rejected_id not in attempts
            or attempts[rejected_id]["solutionClassId"] != class_id
            for rejected_id in rejected_ids
        ):
            return False

    reviews = state["reviewRunIdsByAttempt"]
    if not isinstance(reviews, dict) or set(reviews) != set(attempts):
        return False
    if any(not _is_unique_id_list(review_ids) for review_ids in reviews.values()):
        return False

    rejected_classes = state["rejectedClasses"]
    if (
        not _is_unique_id_list(rejected_classes)
        or any(class_id not in declared_classes for class_id in rejected_classes)
    ):
        return False

    frontier = state["reassessmentFrontier"]
    if not isinstance(frontier, dict) or any(object_id not in expected_objects for object_id in frontier):
        return False
    for object_id, rejected_ids in frontier.items():
        if not _is_unique_id_list(rejected_ids) or not rejected_ids:
            return False
        first_attempt = attempts.get(rejected_ids[0])
        if first_attempt is None or first_attempt["decisionObjectId"] != object_id:
            return False
        class_id = first_attempt["solutionClassId"]
        if rejected_ids != rejected_attempts[class_id]:
            return False
        for attempt_id in rejected_ids:
            attempt = attempts.get(attempt_id)
            if (
                attempt is None
                or attempt["decisionObjectId"] != object_id
                or attempt["solutionClassId"] != class_id
            ):
                return False

    launch_state = state["launchState"]
    terminal = state["terminalOutcome"]
    if launch_state not in {
        None,
        "CLAIMED_NO_SPAWN",
        "SPAWNED_UNCONFIRMED",
        "STARTED",
        "TERMINAL",
        "REAPED",
    }:
        return False
    if launch_state in {"TERMINAL", "REAPED"}:
        return terminal in _TERMINAL_OUTCOMES
    return terminal is None


def _commit(state: dict, event: dict, result: str = OK) -> dict:
    state["head"] = event["fingerprint"]
    state["operations"][event["operationId"]] = event["fingerprint"]
    return {"result": result, "changed": True, "state": state}


def _bootstrap_state(event: dict) -> dict:
    capsule = copy.deepcopy(event["payload"]["capsule"])
    objects: dict[str, dict] = {}
    attempts: dict[str, dict] = {}
    rejected: dict[str, list[str]] = {}
    active: dict[str, str] = {}
    for entry in capsule["objects"]:
        object_id = entry["decisionObjectId"]
        objects[object_id] = copy.deepcopy(entry)
        initial_attempt = entry["initialAttemptId"]
        attempts[initial_attempt] = {
            "decisionObjectId": object_id,
            "solutionClassId": entry["initialClassId"],
            "mutationSurfaces": copy.deepcopy(entry["mutationSurfaces"]),
        }
        active[object_id] = initial_attempt
        for class_id in entry["solutionClasses"]:
            rejected[class_id] = []
    return {
        "head": event["fingerprint"],
        "operations": {event["operationId"]: event["fingerprint"]},
        "declarationSetId": capsule["declarationSetId"],
        "capsuleDigest": hashlib.sha256(_capsule_bytes(capsule)).hexdigest(),
        "capsule": capsule,
        "objects": objects,
        "attempts": attempts,
        "activeAttemptByObject": active,
        "rejectedAttempts": rejected,
        "reviewRunIdsByAttempt": {attempt_id: [] for attempt_id in attempts},
        "rejectedClasses": [],
        "reassessmentFrontier": {},
        "launchState": None,
        "terminalOutcome": None,
    }


def _attempt_admission(state: dict, event: dict) -> dict:
    payload = event["payload"]
    keys = {"decisionObjectId", "solutionClassId", "attemptId", "mutationSurfaces"}
    if not _payload_is(payload, keys):
        return _unchanged(state, STATE_INVALID)
    object_id = payload["decisionObjectId"]
    class_id = payload["solutionClassId"]
    attempt_id = payload["attemptId"]
    surfaces = payload["mutationSurfaces"]
    if not all(_is_id(item) for item in (object_id, class_id, attempt_id)):
        return _unchanged(state, STATE_INVALID)
    declaration = state["objects"].get(object_id)
    if declaration is None or class_id not in declaration["solutionClasses"]:
        return _unchanged(state, IDENTITY_UNAUTHORED)
    if not isinstance(surfaces, list) or not surfaces or any(not isinstance(item, str) for item in surfaces):
        return _unchanged(state, STATE_INVALID)
    if set(surfaces) - set(declaration["mutationSurfaces"]):
        return _unchanged(state, IDENTITY_UNAUTHORED)
    if attempt_id in state["attempts"] or len(surfaces) != len(set(surfaces)):
        return _unchanged(state, STATE_INVALID)
    if class_id in state["rejectedClasses"]:
        return _unchanged(state, CLASS_REJECTED)

    rejected_for_object: list[dict] = []
    for rejected_ids in state["rejectedAttempts"].values():
        for rejected_id in rejected_ids:
            attempt = state["attempts"][rejected_id]
            if attempt["decisionObjectId"] == object_id:
                rejected_for_object.append(attempt)
    if len(state["rejectedAttempts"].get(class_id, [])) >= 2:
        return _unchanged(state, REASSESSMENT_REQUIRED)
    if rejected_for_object and any(
        attempt["solutionClassId"] != class_id
        or attempt["mutationSurfaces"] != surfaces
        for attempt in rejected_for_object
    ):
        return _unchanged(state, REASSESSMENT_REQUIRED)

    changed = copy.deepcopy(state)
    changed["attempts"][attempt_id] = {
        "decisionObjectId": object_id,
        "solutionClassId": class_id,
        "mutationSurfaces": copy.deepcopy(surfaces),
    }
    changed["activeAttemptByObject"][object_id] = attempt_id
    changed["reviewRunIdsByAttempt"][attempt_id] = []
    return _commit(changed, event)


def _revise_binding(state: dict, event: dict) -> dict:
    payload = event["payload"]
    if not _payload_is(payload, {"attemptId", "reviewRunId", "disposition"}):
        return _unchanged(state, STATE_INVALID)
    attempt_id = payload["attemptId"]
    review_id = payload["reviewRunId"]
    disposition = payload["disposition"]
    if not _is_id(attempt_id) or not _is_id(review_id):
        return _unchanged(state, STATE_INVALID)
    if disposition not in {"bounded-correction", "solution-class-rejected"}:
        return _unchanged(state, STATE_INVALID)
    attempt = state["attempts"].get(attempt_id)
    if attempt is None:
        return _unchanged(state, IDENTITY_UNAUTHORED)
    changed = copy.deepcopy(state)
    reviews = changed["reviewRunIdsByAttempt"].setdefault(attempt_id, [])
    if review_id not in reviews:
        reviews.append(review_id)
    class_id = attempt["solutionClassId"]
    if disposition == "solution-class-rejected":
        if class_id not in changed["rejectedClasses"]:
            changed["rejectedClasses"].append(class_id)
        return _commit(changed, event, CLASS_REJECTED)
    rejected = changed["rejectedAttempts"].setdefault(class_id, [])
    if attempt_id not in rejected:
        rejected.append(attempt_id)
    changed["reassessmentFrontier"][attempt["decisionObjectId"]] = copy.deepcopy(rejected)
    return _commit(changed, event)


def _guard_triggered(state: dict, event: dict) -> dict:
    payload = event["payload"]
    if not _payload_is(payload, {"attemptId", "guardId", "evidenceRunId"}):
        return _unchanged(state, STATE_INVALID)
    attempt_id = payload["attemptId"]
    guard_id = payload["guardId"]
    evidence_id = payload["evidenceRunId"]
    if not _is_id(attempt_id) or not _is_id(evidence_id) or guard_id not in GUARD_IDS:
        return _unchanged(state, STATE_INVALID)
    attempt = state["attempts"].get(attempt_id)
    if attempt is None:
        return _unchanged(state, IDENTITY_UNAUTHORED)
    declaration = state["objects"][attempt["decisionObjectId"]]
    if guard_id not in declaration["guardIds"]:
        return _unchanged(state, IDENTITY_UNAUTHORED)
    changed = copy.deepcopy(state)
    class_id = attempt["solutionClassId"]
    if class_id not in changed["rejectedClasses"]:
        changed["rejectedClasses"].append(class_id)
    return _commit(changed, event, CLASS_REJECTED)


def _reassessment(state: dict, event: dict) -> dict:
    payload = event["payload"]
    required = {"decisionObjectId", "rejectedAttemptIds", "decision", "reviewRunId"}
    if not _payload_is(payload, required):
        return _unchanged(state, STATE_INVALID)
    object_id = payload["decisionObjectId"]
    rejected_ids = payload["rejectedAttemptIds"]
    if not _is_id(object_id) or not _is_id(payload["reviewRunId"]):
        return _unchanged(state, STATE_INVALID)
    if payload["decision"] not in {"retain-class", "replace-class", "expand-declaration-set"}:
        return _unchanged(state, STATE_INVALID)
    if not isinstance(rejected_ids, list) or any(not _is_id(item) for item in rejected_ids):
        return _unchanged(state, STATE_INVALID)
    if state["objects"].get(object_id) is None:
        return _unchanged(state, IDENTITY_UNAUTHORED)
    frontier = state["reassessmentFrontier"].get(object_id)
    if not frontier:
        return _unchanged(state, RECEIPT_STALE)
    if rejected_ids != frontier:
        return _unchanged(state, RECEIPT_STALE)
    changed = copy.deepcopy(state)
    changed["reassessmentFrontier"].pop(object_id, None)
    return _commit(changed, event)


def _launch_transition(state: dict, event: dict) -> dict:
    event_type = event["eventType"]
    payload = event["payload"]
    source = state.get("launchState")
    target: str | None = None
    terminal: str | None = None

    if event_type == "launch-claimed":
        if not _payload_is(payload, {"outcome"}) or payload.get("outcome") != "claim":
            return _unchanged(state, STATE_INVALID)
        if source is None:
            target = "CLAIMED_NO_SPAWN"
    elif event_type == "spawn-boundary":
        if _payload_is(payload, {"outcome"}) and payload.get("outcome") == "spawn-boundary" and source == "CLAIMED_NO_SPAWN":
            target = "SPAWNED_UNCONFIRMED"
    elif event_type == "launch-started":
        if _payload_is(payload, {"outcome"}) and payload.get("outcome") == "authenticated-start" and source == "SPAWNED_UNCONFIRMED":
            target = "STARTED"
    elif event_type == "launch-terminal":
        if not _payload_is(payload, {"outcome"}) or not isinstance(payload.get("outcome"), str):
            return _unchanged(state, STATE_INVALID)
        outcome = payload["outcome"]
        if source == "CLAIMED_NO_SPAWN" and outcome in _PRE_SPAWN_OUTCOMES:
            target, terminal = "TERMINAL", outcome
        elif source == "SPAWNED_UNCONFIRMED" and outcome in _PRE_AUTH_OUTCOMES:
            target, terminal = "TERMINAL", outcome
        elif source == "STARTED" and outcome in _STARTED_OUTCOMES:
            target, terminal = "TERMINAL", outcome
    elif event_type == "process-reaped":
        if (
            _payload_is(payload, {"outcome", "processTreeAbsent", "finalSnapshot"})
            and payload.get("outcome") == "resources-absent"
            and payload.get("processTreeAbsent") is True
            and _is_digest(payload.get("finalSnapshot"))
            and source == "TERMINAL"
        ):
            target = "REAPED"

    if target is None:
        return _unchanged(state, STATE_INVALID)
    changed = copy.deepcopy(state)
    changed["launchState"] = target
    if terminal is not None:
        changed["terminalOutcome"] = terminal
    return _commit(changed, event)


def _closed_auxiliary_event(state: dict, event: dict) -> dict:
    return _unchanged(state, STATE_INVALID)


def reduce_solution_attempt(state: dict | None, event: dict) -> dict:
    """Reduce one validated event without mutating inputs or touching ambient state."""

    if not _event_shape_valid(event):
        return _unchanged(state, STATE_INVALID)
    operation_id = event["operationId"]
    fingerprint = event["fingerprint"]
    if state is not None:
        if not _state_shape_valid(state):
            return _unchanged(state, STATE_INVALID)
        existing = state["operations"].get(operation_id)
        if existing is not None:
            return _unchanged(
                state,
                EXACT_REPLAY if existing == fingerprint else OPERATION_CONFLICT,
            )
        if event["priorHead"] != state.get("head"):
            return _unchanged(state, RECEIPT_STALE)
    elif event["priorHead"] != "GENESIS":
        return _unchanged(state, RECEIPT_STALE)

    event_type = event["eventType"]
    if event_type == "solution-bootstrap":
        if state is not None or not _payload_is(event["payload"], {"capsule"}):
            return _unchanged(state, STATE_INVALID)
        decoded = decode_capsule(event["payload"]["capsule"])
        if decoded["result"] != OK:
            return _unchanged(state, decoded["result"])
        normalized = copy.deepcopy(event)
        normalized["payload"]["capsule"] = decoded["capsule"]
        return {"result": OK, "changed": True, "state": _bootstrap_state(normalized)}
    if state is None:
        return _unchanged(state, STATE_INVALID)
    if event_type == "attempt-admission":
        return _attempt_admission(state, event)
    if event_type == "revise-binding":
        return _revise_binding(state, event)
    if event_type == "guard-triggered":
        return _guard_triggered(state, event)
    if event_type == "reassessment":
        return _reassessment(state, event)
    if event_type in {"launch-claimed", "spawn-boundary", "launch-started", "launch-terminal", "process-reaped"}:
        return _launch_transition(state, event)
    return _closed_auxiliary_event(state, event)
