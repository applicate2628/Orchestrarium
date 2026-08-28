"""Phase A contracts for the pure solution-attempt reducer."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "solution-attempt-v3"
CLAIMS = FIXTURES / "claim-coverage.json"
MATRICES = FIXTURES / "contract-matrices.json"

EXPECTED_CLAIM_IDS = {
    *(f"A{index}" for index in range(1, 15)),
    *(f"S{index}" for index in range(1, 21)),
    *(f"R{index}" for index in range(1, 17)),
}
EXPECTED_DESIGN_GUARDS = {
    "test_clean_quick_fix_capsule",
    "test_declaration_set_freezes_on_first_claim",
    "test_unresolved_revise_forbids_any_object_or_class_change",
    "test_predeclared_disjoint_objects",
    "test_distinct_attempt_replay",
    "test_multiple_reviews_one_attempt",
    "test_immediate_rejection",
    "test_route_registry_binding_matrix",
    "test_route_projection_is_ephemeral",
    "test_attempt_window_byte_contract",
    "test_delta_window_matrix",
    "test_spawn_boundary_kill_matrix",
    "test_cancel_timeout_requires_reaped",
    "test_cross_dimension_and_closure",
    "test_expand_contract_and_reader_floor",
}

VALID_GUARDS = [
    "mutation-surface-subset",
    "no-new-dependency",
    "no-new-contract-risk-owner",
    "forbidden-mechanism-tag",
    "required-oracle",
    "item-specific-stop",
]


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_owner(path: Path, module_name: str, contract: str):
    if not path.is_file():
        pytest.fail(f"missing-contract: {path.relative_to(ROOT)} must own {contract}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"missing-contract: cannot load owner {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _owner():
    return _load_owner(
        ROOT / "scripts" / "solution_attempt" / "reducer.py",
        "solution_attempt_reducer_phase_b",
        "the pure V3 solution-attempt reducer",
    )


def _capsule(*, two_objects: bool = False) -> dict:
    objects = [
        {
            "decisionObjectId": "object-one",
            "mutationSurfaces": ["scripts/example.py"],
            "solutionClasses": ["class-one", "class-alternate"],
            "initialClassId": "class-one",
            "initialAttemptId": "attempt-one",
            "guardIds": VALID_GUARDS,
        }
    ]
    if two_objects:
        objects.append(
            {
                "decisionObjectId": "object-two",
                "mutationSurfaces": ["docs/example.md"],
                "solutionClasses": ["class-two"],
                "initialClassId": "class-two",
                "initialAttemptId": "attempt-two",
                "guardIds": VALID_GUARDS,
            }
        )
    return {
        "version": 1,
        "declarationSetId": "declaration-one",
        "objects": objects,
        "baseline": "b" * 64,
        "author": "accepted-admission-run",
    }


def _event(
    state: dict | None,
    event_type: str,
    payload: dict,
    *,
    operation: str,
    fingerprint_char: str,
) -> dict:
    return {
        "schemaVersion": 3,
        "eventId": f"event-{operation}",
        "operationId": operation,
        "fingerprint": fingerprint_char * 64,
        "priorHead": "GENESIS" if state is None else state["head"],
        "recordedAt": "2026-08-13T07:30:00Z",
        "eventType": event_type,
        "payload": payload,
    }


def _bootstrap(owner, capsule: dict | None = None) -> dict:
    event = _event(
        None,
        "solution-bootstrap",
        {"capsule": capsule or _capsule()},
        operation="bootstrap-0001",
        fingerprint_char="1",
    )
    result = owner.reduce_solution_attempt(None, event)
    assert result["result"] == "SOL-OK", result
    assert result["changed"] is True
    return result["state"]


_DELETE = object()


def _mutate_state_path(state: dict, path: tuple[str, ...], value: object) -> None:
    owner = state
    for key in path[:-1]:
        owner = owner[key]
    if value is _DELETE:
        owner.pop(path[-1])
    else:
        owner[path[-1]] = value


@pytest.mark.parametrize(
    ("name", "path", "value"),
    [
        ("unknown-state-key", ("unexpected",), True),
        ("empty-operations", ("operations",), {}),
        ("head-not-in-operations", ("head",), "f" * 64),
        ("malformed-capsule", ("capsule",), {}),
        ("capsule-digest-mismatch", ("capsuleDigest",), "f" * 64),
        ("declaration-set-mismatch", ("declarationSetId",), "other-declaration"),
        ("missing-object-projection", ("objects", "object-two"), _DELETE),
        ("malformed-object-record", ("objects", "object-one"), "not-an-object"),
        ("changed-object-record", ("objects", "object-one", "guardIds"), ["required-oracle"]),
        ("malformed-attempt-record", ("attempts", "attempt-one"), "not-an-attempt"),
        ("attempt-dangling-object", ("attempts", "attempt-one", "decisionObjectId"), "object-missing"),
        ("attempt-undeclared-class", ("attempts", "attempt-one", "solutionClassId"), "class-two"),
        ("attempt-scalar-surfaces", ("attempts", "attempt-one", "mutationSurfaces"), "scripts/example.py"),
        ("attempt-undeclared-surface", ("attempts", "attempt-one", "mutationSurfaces"), ["docs/example.md"]),
        ("missing-active-object", ("activeAttemptByObject", "object-two"), _DELETE),
        ("active-dangling-attempt", ("activeAttemptByObject", "object-one"), "attempt-missing"),
        ("active-attempt-wrong-object", ("activeAttemptByObject", "object-one"), "attempt-two"),
        ("missing-rejected-class", ("rejectedAttempts", "class-two"), _DELETE),
        ("scalar-rejected-bucket", ("rejectedAttempts", "class-one"), "attempt-one"),
        ("dangling-rejected-id", ("rejectedAttempts", "class-one"), ["attempt-missing"]),
        ("rejected-attempt-wrong-class", ("rejectedAttempts", "class-one"), ["attempt-two"]),
        ("missing-review-bucket", ("reviewRunIdsByAttempt", "attempt-two"), _DELETE),
        ("scalar-review-bucket", ("reviewRunIdsByAttempt", "attempt-one"), "review-run-0001"),
        ("dangling-review-bucket", ("reviewRunIdsByAttempt", "attempt-missing"), []),
        ("invalid-review-id", ("reviewRunIdsByAttempt", "attempt-one"), ["bad review id"]),
        ("duplicate-review-id", ("reviewRunIdsByAttempt", "attempt-one"), ["review-one", "review-one"]),
        ("undeclared-rejected-class", ("rejectedClasses",), ["class-missing"]),
        ("duplicate-rejected-class", ("rejectedClasses",), ["class-one", "class-one"]),
        ("scalar-frontier-bucket", ("reassessmentFrontier", "object-one"), "attempt-one"),
        ("dangling-frontier-object", ("reassessmentFrontier", "object-missing"), []),
        ("dangling-frontier-attempt", ("reassessmentFrontier", "object-one"), ["attempt-missing"]),
        ("frontier-attempt-wrong-object", ("reassessmentFrontier", "object-one"), ["attempt-two"]),
        ("terminal-outcome-before-terminal", ("terminalOutcome",), "pass"),
        ("terminal-without-outcome", ("launchState",), "TERMINAL"),
    ],
    ids=lambda row: row if isinstance(row, str) else None,
)
def test_malformed_derived_state_fails_closed_without_exception(
    name: str,
    path: tuple[str, ...],
    value: object,
) -> None:
    owner = _owner()
    state = _bootstrap(owner, _capsule(two_objects=True))
    event = _event(
        state,
        "launch-claimed",
        {"outcome": "claim"},
        operation="launch-claim-0002",
        fingerprint_char="2",
    )
    _mutate_state_path(state, path, value)
    before = copy.deepcopy(state)

    result = owner.reduce_solution_attempt(state, event)

    assert result == {
        "result": "SOL-E001-STATE-INVALID",
        "changed": False,
        "state": before,
    }, name
    assert state == before


def test_generated_transition_chain_remains_valid() -> None:
    owner = _owner()
    state = _bootstrap(owner)
    transitions = [
        (
            "revise-binding",
            {
                "attemptId": "attempt-one",
                "reviewRunId": "review-run-0001",
                "disposition": "bounded-correction",
            },
        ),
        (
            "attempt-admission",
            {
                "decisionObjectId": "object-one",
                "solutionClassId": "class-one",
                "attemptId": "attempt-two",
                "mutationSurfaces": ["scripts/example.py"],
            },
        ),
        (
            "revise-binding",
            {
                "attemptId": "attempt-two",
                "reviewRunId": "review-run-0002",
                "disposition": "bounded-correction",
            },
        ),
        (
            "reassessment",
            {
                "decisionObjectId": "object-one",
                "rejectedAttemptIds": ["attempt-one", "attempt-two"],
                "decision": "retain-class",
                "reviewRunId": "review-run-0003",
            },
        ),
        ("launch-claimed", {"outcome": "claim"}),
        ("spawn-boundary", {"outcome": "spawn-boundary"}),
        ("launch-started", {"outcome": "authenticated-start"}),
        ("launch-terminal", {"outcome": "pass"}),
        (
            "process-reaped",
            {
                "outcome": "resources-absent",
                "processTreeAbsent": True,
                "finalSnapshot": "e" * 64,
            },
        ),
    ]
    for index, (event_type, payload) in enumerate(transitions, start=2):
        event = _event(
            state,
            event_type,
            payload,
            operation=f"transition-{index:04d}",
            fingerprint_char=f"{index:x}"[-1],
        )
        result = owner.reduce_solution_attempt(state, event)
        assert result["result"] == "SOL-OK", (event_type, result)
        assert result["changed"] is True
        state = result["state"]
    assert state["launchState"] == "REAPED"
    assert state["terminalOutcome"] == "pass"


def test_claim_coverage_is_exact() -> None:
    rows = _json(CLAIMS)
    ids = [row["claimId"] for row in rows]
    assert len(rows) == 50
    assert len(ids) == len(set(ids))
    assert set(ids) == EXPECTED_CLAIM_IDS
    assert len({row["testNode"] for row in rows}) == 50
    actual_guards = {
        guard for row in rows for guard in row.get("designGuards", [])
    }
    assert actual_guards == EXPECTED_DESIGN_GUARDS


def test_capsule_and_path_bounds_matrix_is_closed() -> None:
    cases = _json(MATRICES)["capsulePathBounds"]
    assert {case["case"] for case in cases} == {
        "minimal-clean",
        "undeclared-object",
        "undeclared-surface",
        "overlapping-roots",
        "parent-traversal",
        "absolute-path",
        "empty-guard-set",
    }
    assert all(case["expected"] for case in cases)


def test_attempt_and_reviewer_cardinality_matrix_is_closed() -> None:
    cases = _json(MATRICES)["attemptReviewCardinality"]
    by_case = {case["case"]: case for case in cases}
    assert by_case["one-rejected-attempt-many-reviewers"]["rejectedAttempts"] == 1
    assert by_case["two-distinct-rejected-attempts"]["expected"] == (
        "SOL-E004-REASSESSMENT-REQUIRED"
    )
    assert by_case["class-rejected-first-attempt"]["expected"] == (
        "SOL-E003-CLASS-REJECTED"
    )


def test_launch_transition_matrix_is_exhaustive() -> None:
    matrices = _json(MATRICES)
    states = set(matrices["launchStates"])
    transitions = matrices["legalLaunchTransitions"]
    assert states == {
        "CLAIMED_NO_SPAWN",
        "SPAWNED_UNCONFIRMED",
        "STARTED",
        "TERMINAL",
        "REAPED",
    }
    assert len(transitions) == 17
    assert len(
        {(row["source"], row["target"], row["outcome"]) for row in transitions}
    ) == 17
    assert all(row["source"] in states and row["target"] in states for row in transitions)


def test_version_matrix_has_expand_contract_and_reader_floor() -> None:
    cases = {
        row["case"]: row["expected"]
        for row in _json(MATRICES)["versionInstallRollback"]
    }
    assert cases["v1-read"] == cases["v2-read"] == cases["v3-read"] == "READABLE"
    assert cases["old-writer-v3"] == "REFUSED"
    assert cases["v3-down-conversion"] == "REFUSED"
    assert cases["post-v3-rollback"] == "READERS_AND_OBLIGATIONS_RETAINED"


def test_red_reducer_owner_missing() -> None:
    owner = _load_owner(
        ROOT / "scripts" / "solution_attempt" / "reducer.py",
        "solution_attempt_reducer_phase_a",
        "the pure V3 solution-attempt reducer",
    )
    assert callable(getattr(owner, "reduce_solution_attempt", None)), (
        "missing-contract: scripts/solution_attempt/reducer.py must expose "
        "reduce_solution_attempt"
    )


def test_clean_quick_fix_capsule() -> None:
    owner = _owner()
    raw = json.dumps(_capsule(), sort_keys=True, separators=(",", ":"))
    decoded = owner.decode_capsule(raw)
    assert decoded["result"] == "SOL-OK"
    assert decoded["capsule"] == _capsule()
    assert len(raw.encode("utf-8")) <= 4096


@pytest.mark.parametrize(
    ("name", "raw_or_capsule", "expected"),
    [
        (
            "duplicate-key",
            '{"version":1,"version":1,"declarationSetId":"declaration-one",'
            '"objects":[],"baseline":"' + "b" * 64 + '","author":"accepted-run"}',
            "SOL-E001-STATE-INVALID",
        ),
        ("unknown-top-key", {**_capsule(), "explanation": "heuristic prose"}, "SOL-E001-STATE-INVALID"),
        ("oversize", {**_capsule(), "author": "a" * 4097}, "SOL-E001-STATE-INVALID"),
        ("empty-objects", {**_capsule(), "objects": []}, "SOL-E001-STATE-INVALID"),
        (
            "unknown-object-key",
            {**_capsule(), "objects": [{**_capsule()["objects"][0], "role": "reviewer"}]},
            "SOL-E001-STATE-INVALID",
        ),
        (
            "empty-guards",
            {**_capsule(), "objects": [{**_capsule()["objects"][0], "guardIds": []}]},
            "SOL-E001-STATE-INVALID",
        ),
        (
            "unknown-guard",
            {**_capsule(), "objects": [{**_capsule()["objects"][0], "guardIds": ["guess-similarity"]}]},
            "SOL-E001-STATE-INVALID",
        ),
    ],
)
def test_capsule_closed_keys_bytes_depth_and_count(name, raw_or_capsule, expected) -> None:
    owner = _owner()
    raw = raw_or_capsule if isinstance(raw_or_capsule, str) else json.dumps(raw_or_capsule)
    assert owner.decode_capsule(raw)["result"] == expected, name


@pytest.mark.parametrize(
    "path",
    [
        "/absolute",
        "C:/drive-absolute",
        "C:drive-relative",
        "//server/share",
        "\\\\server\\share",
        "\\\\?\\C:\\device",
        "scripts/../outside.py",
        "scripts//empty.py",
        "scripts/name:stream",
        "scripts/CON",
        "scripts/com1.txt",
        "scripts/trailing.",
        "scripts/trailing ",
        "",
    ],
)
def test_capsule_rejects_unsafe_path_grammar(path: str) -> None:
    owner = _owner()
    capsule = _capsule()
    capsule["objects"][0]["mutationSurfaces"] = [path]
    assert owner.decode_capsule(json.dumps(capsule))["result"] == "SOL-E001-STATE-INVALID"


@pytest.mark.parametrize(
    "paths",
    [
        ["scripts", "scripts/example.py"],
        ["Scripts/example.py", "scripts/EXAMPLE.py"],
        ["docs/caf\u00e9.md", "docs/cafe\u0301.md"],
    ],
)
def test_capsule_rejects_overlap_case_and_unicode_collisions(paths: list[str]) -> None:
    owner = _owner()
    capsule = _capsule(two_objects=True)
    capsule["objects"][0]["mutationSurfaces"] = [paths[0]]
    capsule["objects"][1]["mutationSurfaces"] = [paths[1]]
    assert owner.decode_capsule(json.dumps(capsule))["result"] == "SOL-E001-STATE-INVALID"


def test_declaration_set_freezes_on_first_claim() -> None:
    owner = _owner()
    state = _bootstrap(owner)
    event = _event(
        state,
        "attempt-admission",
        {
            "decisionObjectId": "object-one",
            "solutionClassId": "class-one",
            "attemptId": "attempt-new",
            "mutationSurfaces": ["scripts/not-declared.py"],
        },
        operation="admission-0001",
        fingerprint_char="2",
    )
    before = copy.deepcopy(state)
    result = owner.reduce_solution_attempt(state, event)
    assert result["result"] == "SOL-E005-IDENTITY-UNAUTHORED"
    assert result["changed"] is False
    assert result["state"] == before == state


def _bind_revise(owner, state: dict, *, operation: str, review: str, disposition: str = "bounded-correction") -> dict:
    event = _event(
        state,
        "revise-binding",
        {
            "attemptId": "attempt-one",
            "reviewRunId": review,
            "disposition": disposition,
        },
        operation=operation,
        fingerprint_char=operation[-1],
    )
    result = owner.reduce_solution_attempt(state, event)
    assert result["result"] == "SOL-OK", result
    return result["state"]


def test_unresolved_revise_forbids_any_object_or_class_change() -> None:
    owner = _owner()
    state = _bind_revise(owner, _bootstrap(owner), operation="revise-0002", review="review-run-0001")
    event = _event(
        state,
        "attempt-admission",
        {
            "decisionObjectId": "object-one",
            "solutionClassId": "class-alternate",
            "attemptId": "attempt-alternate",
            "mutationSurfaces": ["scripts/example.py"],
        },
        operation="admission-0003",
        fingerprint_char="3",
    )
    result = owner.reduce_solution_attempt(state, event)
    assert result["result"] == "SOL-E004-REASSESSMENT-REQUIRED"
    assert result["state"] == state


def test_predeclared_disjoint_objects() -> None:
    owner = _owner()
    state = _bootstrap(owner, _capsule(two_objects=True))
    state = _bind_revise(owner, state, operation="revise-0002", review="review-run-0001")
    event = _event(
        state,
        "attempt-admission",
        {
            "decisionObjectId": "object-two",
            "solutionClassId": "class-two",
            "attemptId": "attempt-two-correction",
            "mutationSurfaces": ["docs/example.md"],
        },
        operation="admission-0003",
        fingerprint_char="3",
    )
    result = owner.reduce_solution_attempt(state, event)
    assert result["result"] == "SOL-OK"
    assert result["state"]["rejectedAttempts"]["class-one"] == ["attempt-one"]
    assert result["state"]["rejectedAttempts"]["class-two"] == []


def test_distinct_attempt_replay() -> None:
    owner = _owner()
    state = _bind_revise(owner, _bootstrap(owner), operation="revise-0002", review="review-run-0001")
    admission = _event(
        state,
        "attempt-admission",
        {
            "decisionObjectId": "object-one",
            "solutionClassId": "class-one",
            "attemptId": "attempt-correction",
            "mutationSurfaces": ["scripts/example.py"],
        },
        operation="admission-0003",
        fingerprint_char="3",
    )
    admitted = owner.reduce_solution_attempt(state, admission)
    assert admitted["result"] == "SOL-OK"
    state = admitted["state"]
    revise = _event(
        state,
        "revise-binding",
        {
            "attemptId": "attempt-correction",
            "reviewRunId": "review-run-0002",
            "disposition": "bounded-correction",
        },
        operation="revise-0004",
        fingerprint_char="4",
    )
    state = owner.reduce_solution_attempt(state, revise)["state"]
    denied = _event(
        state,
        "attempt-admission",
        {
            "decisionObjectId": "object-one",
            "solutionClassId": "class-one",
            "attemptId": "attempt-third",
            "mutationSurfaces": ["scripts/example.py"],
        },
        operation="admission-0005",
        fingerprint_char="5",
    )
    result = owner.reduce_solution_attempt(state, denied)
    assert result["result"] == "SOL-E004-REASSESSMENT-REQUIRED"
    assert state["rejectedAttempts"]["class-one"] == ["attempt-one", "attempt-correction"]


def test_multiple_reviews_one_attempt() -> None:
    owner = _owner()
    state = _bind_revise(owner, _bootstrap(owner), operation="revise-0002", review="review-run-0001")
    state = _bind_revise(owner, state, operation="revise-0003", review="review-run-0002")
    assert state["rejectedAttempts"]["class-one"] == ["attempt-one"]
    assert state["reviewRunIdsByAttempt"]["attempt-one"] == ["review-run-0001", "review-run-0002"]


def test_immediate_rejection() -> None:
    owner = _owner()
    initial = _bootstrap(owner)
    for event_type, payload in (
        (
            "revise-binding",
            {
                "attemptId": "attempt-one",
                "reviewRunId": "review-run-0001",
                "disposition": "solution-class-rejected",
            },
        ),
        (
            "guard-triggered",
            {
                "attemptId": "attempt-one",
                "guardId": "forbidden-mechanism-tag",
                "evidenceRunId": "evidence-run-0001",
            },
        ),
    ):
        event = _event(
            initial,
            event_type,
            payload,
            operation=f"reject-{event_type}",
            fingerprint_char="6",
        )
        rejected = owner.reduce_solution_attempt(initial, event)
        assert rejected["result"] == "SOL-E003-CLASS-REJECTED"
        assert rejected["changed"] is True


def test_exact_replay_and_conflicting_operation_are_closed() -> None:
    owner = _owner()
    event = _event(
        None,
        "solution-bootstrap",
        {"capsule": _capsule()},
        operation="bootstrap-0001",
        fingerprint_char="1",
    )
    first = owner.reduce_solution_attempt(None, event)
    replay = owner.reduce_solution_attempt(first["state"], event)
    assert replay["result"] == "SOL-R000-EXACT-REPLAY"
    assert replay["changed"] is False
    conflict = copy.deepcopy(event)
    conflict["fingerprint"] = "f" * 64
    conflict["priorHead"] = first["state"]["head"]
    denied = owner.reduce_solution_attempt(first["state"], conflict)
    assert denied["result"] == "SOL-E010-OPERATION-CONFLICT"
    assert denied["state"] == first["state"]


def test_launch_state_outcome_cartesian_is_closed() -> None:
    owner = _owner()
    base = _bootstrap(owner)
    legal = {
        ("CLAIMED_NO_SPAWN", "spawn-boundary", "spawn-boundary"),
        ("CLAIMED_NO_SPAWN", "launch-terminal", "abandoned-before-spawn"),
        ("CLAIMED_NO_SPAWN", "launch-terminal", "cancelled-before-spawn"),
        ("CLAIMED_NO_SPAWN", "launch-terminal", "failed-before-spawn"),
        ("SPAWNED_UNCONFIRMED", "launch-started", "authenticated-start"),
        ("SPAWNED_UNCONFIRMED", "launch-terminal", "spawn-failed"),
        ("SPAWNED_UNCONFIRMED", "launch-terminal", "spawn-outcome-unknown"),
        ("SPAWNED_UNCONFIRMED", "launch-terminal", "cancelled-before-authentication"),
        ("SPAWNED_UNCONFIRMED", "launch-terminal", "timed-out-before-authentication"),
        ("SPAWNED_UNCONFIRMED", "launch-terminal", "unadoptable-child-terminated"),
        ("STARTED", "launch-terminal", "pass"),
        ("STARTED", "launch-terminal", "revise"),
        ("STARTED", "launch-terminal", "failed"),
        ("STARTED", "launch-terminal", "cancelled"),
        ("STARTED", "launch-terminal", "timed-out"),
        ("STARTED", "launch-terminal", "orphaned-after-start"),
        ("TERMINAL", "process-reaped", "resources-absent"),
    }
    all_states = ["CLAIMED_NO_SPAWN", "SPAWNED_UNCONFIRMED", "STARTED", "TERMINAL", "REAPED"]
    event_outcomes = {
        "spawn-boundary": ["spawn-boundary"],
        "launch-started": ["authenticated-start"],
        "launch-terminal": [
            "abandoned-before-spawn",
            "cancelled-before-spawn",
            "failed-before-spawn",
            "spawn-failed",
            "spawn-outcome-unknown",
            "cancelled-before-authentication",
            "timed-out-before-authentication",
            "unadoptable-child-terminated",
            "pass",
            "revise",
            "failed",
            "cancelled",
            "timed-out",
            "orphaned-after-start",
        ],
        "process-reaped": ["resources-absent"],
    }
    index = 0
    for source in all_states:
        for event_type, outcomes in event_outcomes.items():
            for outcome in outcomes:
                index += 1
                state = copy.deepcopy(base)
                state["launchState"] = source
                state["terminalOutcome"] = "pass" if source in {"TERMINAL", "REAPED"} else None
                payload = {"outcome": outcome}
                if event_type == "process-reaped":
                    payload.update({"processTreeAbsent": True, "finalSnapshot": "e" * 64})
                event = _event(
                    state,
                    event_type,
                    payload,
                    operation=f"cartesian-{index:04d}",
                    fingerprint_char="a",
                )
                before = copy.deepcopy(state)
                result = owner.reduce_solution_attempt(state, event)
                if (source, event_type, outcome) in legal:
                    assert result["result"] == "SOL-OK", (source, event_type, outcome, result)
                    assert result["changed"] is True
                else:
                    assert result["result"] == "SOL-E001-STATE-INVALID", (source, event_type, outcome, result)
                    assert result["changed"] is False
                    assert result["state"] == before == state


def test_solution_attempt_owner_is_pure_and_heuristic_free() -> None:
    path = ROOT / "scripts" / "solution_attempt" / "reducer.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported.isdisjoint({"os", "pathlib", "subprocess", "time", "datetime", "random", "secrets", "socket"})
    folded = source.casefold()
    for forbidden in ("similarity", "natural language", "embedding", "levenshtein", "difflib", "role heuristic", "filename heuristic"):
        assert forbidden not in folded
