"""Pure semantic receipt deltas, never acquisition authority or persisted receipts.

The existing physical transaction must separately receive every outstanding
requirement before applying content and receipt together. This module performs
no I/O, invents no storage binding, and never calls the layout-asserting encoder.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .clients import get_client
from . import configuration, ownership


@dataclass(frozen=True)
class Outcome:
    path: str
    kind: str  # file or block
    before: bytes | None
    after: bytes | None
    intent: str = "update"  # update, create, adopt, remove, replace
    adoption_sha256: str | None = None
    adoption_span: tuple[int, int] | None = None


@dataclass(frozen=True)
class ArtifactPlan:
    path: str
    route: str
    before_sha256: str | None
    after_sha256: str | None
    reason: str
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class Change:
    category: str
    path: str
    expected_json: str | None
    proposed_json: str | None


@dataclass(frozen=True)
class ReceiptPlan:
    provider: str
    scope: str
    receipt_sha256: str | None  # None means absent, never an empty record.
    artifacts: tuple[ArtifactPlan, ...]
    changes: tuple[Change, ...]


def _digest(value: bytes | None) -> str | None:
    return None if value is None else hashlib.sha256(value).hexdigest()


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _record(payload, provider, scope):
    get_client(provider)
    if scope not in {"global", "project"}:
        raise ValueError("E_RECEIPT_PLAN_SCOPE")
    if payload is not None and type(payload) is not bytes:
        raise ValueError("E_RECEIPT_PLAN_INPUT")
    return (ownership.decode_record(payload, provider, scope) if payload is not None
            else {"schema": ownership.SCHEMA, "provider": provider, "scope": scope, "files": {}})


def _index(record):
    result = {}
    for category in ("files", "configs"):
        for path, spec in record.get(category, {}).items():
            result[path.casefold()] = (category, path, spec)
    for path in record.get("directories", []):
        result[path.casefold()] = ("directories", path, None)
    return result


def _block(payload: bytes, kind, context):
    text = payload.decode("utf-8")
    bounds = configuration.owned_block(text, kind, context)
    if bounds is None:
        raise ValueError("missing managed block")
    return text, bounds, configuration.block_digest(text, kind, context)


def _same_outside(before, after, old, new):
    if before[:old[0]] != after[:new[0]] or before[old[1]:] != after[new[1]:]:
        raise ValueError("outside text changed")


def _legacy_selection(before, after, bounds, span, context, document_digest):
    # Renderer and planner use one exact-current boundary contract. The digest
    # is still only a precondition, never evidence of permission or acquisition.
    start, end = configuration.validate_selected_document(
        before, "codex", context, document_digest=document_digest, span=span)
    suffix = before[end:]
    replacement_end = len(after) - len(suffix)
    if (replacement_end < bounds[1] or after[:start] != before[:start]
            or after[replacement_end:] != suffix or bounds[0] != start
            or after[bounds[1]:replacement_end] not in {"", "\n"}):
        raise ValueError("outside reviewed span changed")


def _proposed_spec(outcome, claim, block_kind, context):
    """Validate the rendered outcome, not the caller's right to publish it."""
    if outcome.after is None and outcome.intent != "remove":
        raise ValueError("missing rendered outcome")
    if outcome.kind == "file":
        if outcome.intent == "remove":
            if outcome.after is not None:
                raise ValueError("file removal still has content")
            return None
        return _digest(outcome.after)
    if outcome.intent == "remove":
        before = outcome.before.decode("utf-8")
        expected = configuration.remove_owned_block(before, block_kind, claim["sha256"], context)
        if outcome.after is None or outcome.after.decode("utf-8") != expected:
            raise ValueError("outside removed block changed")
        return None
    after, new, digest = _block(outcome.after, block_kind, context)
    before = None if outcome.before is None else outcome.before.decode("utf-8")
    if outcome.intent == "create":
        if before is None:
            if new[0] != 0 or after[new[1]:] not in {"", "\n"}:
                raise ValueError("invalid created document")
        else:
            if configuration.owned_block(before, block_kind, context) is not None:
                raise ValueError("creation would adopt existing block")
            if new[0] != 0 or after[new[1]:] not in {"\n\n" + before, "\n" + before}:
                raise ValueError("creation changed original document")
    elif outcome.intent == "replace":
        selected = configuration.validate_selected_document(
            before, block_kind, context, document_digest=outcome.adoption_sha256,
            span=outcome.adoption_span)
        # The new frame must be strict too; malformed marker prefixes outside
        # an otherwise valid pair are not a valid rendered replacement.
        configuration.validate_selected_document(
            after, block_kind, context, document_digest=_digest(outcome.after), span=new)
        old = configuration.owned_block(before, block_kind, context)
        if old is not None:
            _same_outside(before, after, selected, new)
        else:
            _legacy_selection(before, after, new, selected, context,
                              outcome.adoption_sha256)
    elif outcome.intent == "adopt":
        old = configuration.owned_block(before, block_kind, context)
        if old is not None:
            if outcome.adoption_span is not None and outcome.adoption_span != old:
                raise ValueError("adoption selection differs from marked block")
            _same_outside(before, after, old, new)
        elif block_kind == "codex":
            _legacy_selection(before, after, new, outcome.adoption_span, context,
                              outcome.adoption_sha256)
        else:
            raise ValueError("unmarked adoption is not qualified for this document")
    else:
        old = configuration.owned_block(before, block_kind, context)
        _same_outside(before, after, old, new)
    return {"kind": "block", "blockKind": block_kind, "sha256": digest}


def plan_changes(receipt: bytes | None, provider: str, scope: str,
                 outcomes: tuple[Outcome, ...], document_context) -> ReceiptPlan:
    """Return conditional per-artifact deltas while retaining legacy behavior."""
    record = _record(receipt, provider, scope)
    client, index = get_client(provider), _index(record)
    artifacts, changes, seen = [], [], set()
    for item in outcomes:
        if (type(item) is not Outcome or item.kind not in {"file", "block"}
                or item.intent not in {"update", "create", "adopt", "remove", "replace"}
                or item.before is not None and type(item.before) is not bytes
                or item.after is not None and type(item.after) is not bytes):
            raise ValueError("E_RECEIPT_PLAN_OUTCOME")
        ownership.validate_path(item.path, provider, scope)
        key = item.path.casefold()
        if key in seen:
            raise ValueError("E_RECEIPT_PLAN_ALIAS")
        seen.add(key)
        category = "files" if item.kind == "file" else "configs"
        block_kind = client["documents"][scope].get(item.path)
        if (item.kind == "file" and not any(item.path.startswith(root + "/") for root in client["payload_roots"])
                or item.kind == "block" and block_kind is None):
            raise ValueError("E_RECEIPT_PLAN_ARTIFACT")
        existing = index.get(key)
        if existing is not None and (existing[0] != category or existing[1] != item.path):
            raise ValueError("E_RECEIPT_PLAN_ALIAS")
        claim = existing[2] if existing is not None else None
        if item.intent not in {"adopt", "replace"} and (item.adoption_sha256 is not None or item.adoption_span is not None):
            raise ValueError("E_RECEIPT_PLAN_UNUSED_SELECTION")
        def result(route, reason, requirements=()):
            return ArtifactPlan(item.path, route, _digest(item.before), _digest(item.after),
                                reason, tuple(requirements))
        if claim is None and item.intent == "update":
            artifacts.append(result("legacy", "No claimed entry; no ownership acquired."))
            continue
        if claim is None and item.intent == "remove":
            artifacts.append(result("preserve", "Unrecorded removal is not planned."))
            continue
        try:
            if item.intent == "replace":
                # Exact-current selection is separate from historical ownership.
                # Its digest is a precondition, never approval or a capability.
                if item.kind == "file" and item.adoption_span is not None:
                    raise ValueError("selected replacement requires a complete file")
                if item.kind == "block" and (provider != "codex" or block_kind != "codex"):
                    raise ValueError("selected replacement requires a Codex document")
                if item.before is None or item.adoption_sha256 != _digest(item.before):
                    raise ValueError("selected replacement preimage changed")
            elif claim is not None:
                if item.intent != "update" and item.intent != "remove":
                    raise ValueError("creation or adoption cannot override a claim")
                if item.before is None:
                    raise ValueError("claimed artifact missing")
                actual = (_digest(item.before) if item.kind == "file"
                          else _block(item.before, block_kind, document_context)[2])
                expected = claim if item.kind == "file" else claim["sha256"]
                if actual != expected:
                    raise ValueError("claimed artifact changed")
            elif item.intent == "create":
                if item.kind == "file" and item.before is not None:
                    raise ValueError("file creation would adopt existing bytes")
                if item.adoption_sha256 is not None or item.adoption_span is not None:
                    raise ValueError("unexpected creation selection")
            elif item.intent == "adopt":
                if (item.adoption_span is not None and
                        (type(item.adoption_span) is not tuple or len(item.adoption_span) != 2
                         or any(type(index) is not int for index in item.adoption_span))):
                    raise ValueError("invalid adoption selection")
                if item.before is None or item.adoption_sha256 != _digest(item.before):
                    raise ValueError("reviewed artifact preimage changed")
                if item.kind == "file" and item.adoption_span is not None:
                    raise ValueError("file adoption requires complete preimage")
            proposed = _proposed_spec(item, claim, block_kind, document_context)
        except (ValueError, RuntimeError, KeyError) as error:
            artifacts.append(result("preserve", str(error)))
            continue
        requirements = ["artifact-and-receipt-currentness", "atomic-owner-commit-and-rollback"]
        if item.intent == "replace":
            requirements.extend(("exact-current-replacement-approval", "selected-storage-acquisition"))
        elif claim is not None:
            requirements.append("historical-storage-authority")
        elif item.intent == "adopt":
            requirements.extend(("exact-user-adoption-approval", "selected-storage-acquisition"))
        else:
            requirements.append("fresh-creation-acquisition")
        route = {"update": "recorded-proposal", "create": "creation-proposal",
                 "adopt": "adoption-proposal", "remove": "removal-proposal",
                 "replace": "selected-replacement-proposal"}[item.intent]
        artifacts.append(result(route, "Semantic proposal only; acquisition is outstanding.", requirements))
        changes.append(Change(category, item.path, None if claim is None else _json(claim),
                              None if proposed is None else _json(proposed)))
    plan = ReceiptPlan(provider, scope, _digest(receipt), tuple(artifacts), tuple(changes))
    apply_delta(receipt, plan)  # Validate combined aliases and schema, without persistence.
    return plan


def apply_delta(receipt: bytes | None, plan: ReceiptPlan) -> dict | None:
    """Apply only to an in-memory record; preserve layout, never call encoder."""
    if type(plan) is not ReceiptPlan:
        raise ValueError("E_RECEIPT_PLAN_STALE")
    record = _record(receipt, plan.provider, plan.scope)
    if _digest(receipt) != plan.receipt_sha256:
        raise ValueError("E_RECEIPT_PLAN_STALE")
    if not plan.changes:
        return record if receipt is not None else None
    seen = set()
    for change in plan.changes:
        if type(change) is not Change or change.category not in {"files", "configs"}:
            raise ValueError("E_RECEIPT_PLAN_CHANGE")
        ownership.validate_path(change.path, plan.provider, plan.scope)
        if change.path.casefold() in seen:
            raise ValueError("E_RECEIPT_PLAN_ALIAS")
        seen.add(change.path.casefold())
        entries = record.setdefault(change.category, {})
        old = entries.get(change.path)
        if (None if old is None else _json(old)) != change.expected_json:
            raise ValueError("E_RECEIPT_PLAN_STALE")
        if change.proposed_json is None:
            if old is None:
                raise ValueError("E_RECEIPT_PLAN_STALE")
            del entries[change.path]
        else:
            entries[change.path] = json.loads(change.proposed_json)
    return ownership.validate_record(record, plan.provider, plan.scope)


def serialize_delta(receipt: bytes | None, plan: ReceiptPlan) -> bytes | None:
    """Return candidate bytes only; no persistence or acquisition authority.

    A no-op preserves the original receipt exactly, including its absence.
    Capacity validation happens before any future owner starts writing.
    """
    record = apply_delta(receipt, plan)
    if not plan.changes:
        return receipt
    return ownership.serialize_record(record, plan.provider, plan.scope)
