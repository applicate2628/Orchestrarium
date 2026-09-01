from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .contracts import validate_rubric
from .normalization import (
    MISSING,
    canonical_identity,
    get_path,
    normalize_collection,
    normalize_scalar,
    numeric_string_equivalent,
)
from .signals import findings_f1, numeric_credit, set_f1, source_ranking_credit


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _published_number(value: Decimal, places: str = "0.01") -> int | float:
    rounded = value.quantize(Decimal(places), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return int(rounded)
    return float(rounded)


def canonical_report_bytes(report: dict[str, Any]) -> bytes:
    return json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _categorical_credit(atom: dict[str, Any], candidate: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
    actual = get_path(candidate, atom["candidate_path"])
    if actual is MISSING:
        return Decimal(0), {"reason": "missing"}
    casefold = atom.get("casefold", False)
    aliases = atom.get("aliases")
    expected = normalize_scalar(atom.get("expected"), casefold=casefold, aliases=aliases)
    normalized_actual = normalize_scalar(actual, casefold=casefold, aliases=aliases)
    return (Decimal(1) if normalized_actual == expected else Decimal(0)), {
        "actual": normalized_actual,
        "expected": expected,
    }


def _numeric_credit(atom: dict[str, Any], candidate: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
    actual = get_path(candidate, atom["candidate_path"])
    if actual is MISSING:
        return Decimal(0), {"reason": "missing"}
    if isinstance(actual, dict):
        value = actual.get("value")
        unit = actual.get("unit")
    else:
        value = actual
        unit = get_path(candidate, atom.get("unit_path", ""), atom.get("unit"))
    credit = numeric_credit(
        value,
        atom.get("expected"),
        unit,
        atom.get("unit"),
        atom.get("full_tolerance"),
        atom.get("zero_tolerance"),
    )
    return _decimal(credit), {"actual": value, "unit": unit, "expected": atom.get("expected")}


def _set_credit(atom: dict[str, Any], candidate: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
    actual = get_path(candidate, atom["candidate_path"], [])
    if not isinstance(actual, list):
        actual = []
    detail = set_f1(
        atom.get("expected", []),
        actual,
        casefold=atom.get("casefold", False),
        aliases=atom.get("aliases"),
    )
    return _decimal(detail["f1"]), detail


def _source_binding_credit(atom: dict[str, Any], candidate: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
    id_field = atom.get("id_field", "id")
    source_field = atom.get("source_ids_field", "source_ids")
    actual_items = normalize_collection(get_path(candidate, atom["candidate_path"], []), id_field)
    actual_by_id = {item.get(id_field): item for item in actual_items}
    weighted_credit = Decimal(0)
    weight_total = Decimal(0)
    details = []
    for target in atom.get("expected", []):
        target_id = canonical_identity(target.get(id_field))
        weight = _decimal(target.get("weight", 1))
        actual = actual_by_id.get(target_id, {})
        sources = actual.get(source_field, []) if isinstance(actual.get(source_field, []), list) else []
        result = set_f1(
            target.get(source_field, []),
            sources,
            casefold=atom.get("casefold_sources", False),
            aliases=atom.get("source_aliases"),
        )
        weighted_credit += weight * _decimal(result["f1"])
        weight_total += weight
        details.append({"id": target_id, **result})
    credit = weighted_credit / weight_total if weight_total else Decimal(1)
    return credit, {"targets": details}


def _case_fraction_credit(atom: dict[str, Any], candidate: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
    id_field = atom.get("id_field", "id")
    value_field = atom.get("value_field", "value")
    actual_items = normalize_collection(get_path(candidate, atom["candidate_path"], []), id_field)
    actual_by_id = {item.get(id_field): item for item in actual_items}
    aliases = atom.get("aliases")
    casefold_values = atom.get("casefold_values", False)
    weighted_hits = Decimal(0)
    total = Decimal(0)
    cases = []
    for case_id, expected in sorted(atom.get("expected", {}).items()):
        normalized_id = canonical_identity(case_id)
        case_weight = _decimal(atom.get("case_weights", {}).get(case_id, 1))
        actual_item = actual_by_id.get(normalized_id, {})
        actual = actual_item.get(value_field, MISSING)
        normalized_actual = normalize_scalar(actual, casefold=casefold_values, aliases=aliases)
        normalized_expected = normalize_scalar(expected, casefold=casefold_values, aliases=aliases)
        correct = actual is not MISSING and (
            normalized_actual == normalized_expected
            or (
                atom.get("numeric_string_equivalence", False)
                and numeric_string_equivalent(normalized_actual, normalized_expected)
            )
        )
        if correct:
            weighted_hits += case_weight
        total += case_weight
        cases.append({"id": normalized_id, "correct": correct, "weight": _published_number(case_weight)})
    credit = weighted_hits / total if total else Decimal(1)
    return credit, {"cases": cases, "weighted_hits": _published_number(weighted_hits), "weight_total": _published_number(total)}


def _findings_credit(atom: dict[str, Any], candidate: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
    id_field = atom.get("reported_id_field", "id")
    reported = normalize_collection(get_path(candidate, atom["candidate_path"], []), id_field)
    detail = findings_f1(
        atom.get("expected", []),
        reported,
        match_fields=atom.get("match_fields", []),
        severity_weights=atom.get("severity_weights", {"high": 3, "medium": 2, "low": 1}),
        severity_field=atom.get("severity_field", "severity"),
        casefold_fields=atom.get("casefold_fields", []),
        aliases=atom.get("field_aliases", {}),
    )
    return _decimal(detail["f1"]), detail


def _required_fields_credit(atom: dict[str, Any], candidate: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
    fields = atom.get("required_paths", [])
    present = [path for path in fields if get_path(candidate, path) is not MISSING]
    credit = Decimal(len(present)) / Decimal(len(fields)) if fields else Decimal(1)
    return credit, {"present": sorted(present), "required": sorted(fields)}


def _atom_credit(atom: dict[str, Any], candidate: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
    atom_type = atom["type"]
    if atom_type == "categorical":
        return _categorical_credit(atom, candidate)
    if atom_type == "numeric":
        return _numeric_credit(atom, candidate)
    if atom_type == "set_f1":
        return _set_credit(atom, candidate)
    if atom_type == "source_binding_f1":
        return _source_binding_credit(atom, candidate)
    if atom_type == "source_ranking":
        actual = get_path(candidate, atom["candidate_path"], [])
        if not isinstance(actual, list):
            actual = []
        detail = source_ranking_credit(
            atom.get("expected", []),
            actual,
            casefold=atom.get("casefold", False),
            aliases=atom.get("aliases"),
        )
        return _decimal(detail["credit"]), detail
    if atom_type == "case_fraction":
        return _case_fraction_credit(atom, candidate)
    if atom_type == "findings_f1":
        return _findings_credit(atom, candidate)
    if atom_type == "required_fields":
        return _required_fields_credit(atom, candidate)
    raise AssertionError(f"validated atom type is not implemented: {atom_type}")


def _wrong_present_commitment_count(
    atom: dict[str, Any],
    candidate: dict[str, Any],
    credit: Decimal,
    detail: dict[str, Any],
) -> int:
    atom_type = atom["type"]
    if atom_type == "required_fields":
        return 0
    actual = get_path(candidate, atom["candidate_path"], MISSING)
    if actual is MISSING:
        return 0

    if atom_type == "categorical":
        return int(credit < 1)

    if atom_type == "numeric":
        if isinstance(actual, dict) and actual.get("value", MISSING) is MISSING:
            return 0
        return int(credit < 1)

    if atom_type == "set_f1":
        return int(detail.get("fp", 0))

    if atom_type == "findings_f1":
        return int(detail.get("unmatched_reported_count", 0))

    if atom_type == "source_binding_f1":
        return sum(
            int(target.get("fp", 0))
            for target in detail.get("targets", [])
        )

    if atom_type == "case_fraction":
        id_field = atom.get("id_field", "id")
        value_field = atom.get("value_field", "value")
        actual_items = normalize_collection(actual, id_field)
        actual_by_id = {item.get(id_field): item for item in actual_items}
        expected_ids = {canonical_identity(case_id) for case_id in atom.get("expected", {})}
        incorrect_present = sum(
            1
            for case in detail.get("cases", [])
            if case.get("id") in actual_by_id
            and actual_by_id[case["id"]].get(value_field, MISSING) is not MISSING
            and not case.get("correct", False)
        )
        unexpected_present = sum(
            1
            for item in actual_items
            if item.get(id_field, MISSING) not in expected_ids
            and item.get(value_field, MISSING) is not MISSING
        )
        return incorrect_present + unexpected_present

    if atom_type == "source_ranking":
        if not isinstance(actual, list):
            return 0
        casefold = atom.get("casefold", False)
        aliases = atom.get("aliases")
        expected = [normalize_scalar(item, casefold=casefold, aliases=aliases) for item in atom.get("expected", [])]
        reported = [normalize_scalar(item, casefold=casefold, aliases=aliases) for item in actual]
        expected_positions = {item: index for index, item in enumerate(expected)}
        present_positions = [expected_positions[item] for item in reported if item in expected_positions]
        false_items = sum(1 for item in reported if item not in expected_positions)
        duplicate_items = len(present_positions) - len(set(present_positions))
        inversions = sum(
            1
            for left in range(len(present_positions))
            for right in range(left + 1, len(present_positions))
            if present_positions[left] > present_positions[right]
        )
        return false_items + duplicate_items + inversions

    return 0


def _integrity_hits(rubric: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    hits = []
    for event in rubric.get("integrity_events", []):
        actual = get_path(candidate, event["candidate_path"])
        if actual is MISSING:
            continue
        forbidden = event.get("forbidden_values", [])
        if any(normalize_scalar(actual, casefold=True) == normalize_scalar(value, casefold=True) for value in forbidden):
            hits.append(deepcopy(event))
    return hits


def _diagnostic_key(diagnostic: dict[str, Any]) -> str:
    return json.dumps(diagnostic, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def invalid_candidate_report(
    rubric: dict[str, Any], candidate_diagnostics: list[dict[str, Any]]
) -> dict[str, Any]:
    diagnostics = sorted(candidate_diagnostics, key=_diagnostic_key)
    return {
        "report_version": "v4-score-report-1",
        "scenario_id": rubric["scenario_id"],
        "scoreable": True,
        "status": "INVALID-CANDIDATE",
        "raw_score": 0,
        "adjusted_components": {},
        "penalty": 0,
        "score": 0,
        "thresholds": {
            "partial": rubric["score"]["partial_threshold"],
            "pass": rubric["score"]["pass_threshold"],
        },
        "components": [],
        "integrity_events": [],
        "commitment_cap": rubric["score"].get("wrong_commitment_cap"),
        "commitment_violations": [],
        "candidate_diagnostics": diagnostics,
    }


def score_candidate(
    rubric: dict[str, Any],
    candidate: dict[str, Any],
    *,
    candidate_diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_rubric(rubric)
    diagnostics = list(candidate_diagnostics or [])
    if not isinstance(candidate, dict):
        diagnostics.append({"code": "CANDIDATE-TYPE", "message": "candidate root must be an object"})
        candidate = {}
    if diagnostics:
        return invalid_candidate_report(rubric, diagnostics)

    component_reports = []
    atom_lookup: dict[str, dict[str, Any]] = {}
    commitment_violations: list[dict[str, Any]] = []
    raw_score = Decimal(0)
    for component in rubric["components"]:
        component_weight = _decimal(component["weight"])
        atom_weight_total = sum((_decimal(atom["weight"]) for atom in component["atoms"]), Decimal(0))
        component_score = Decimal(0)
        atom_reports = []
        for atom in component["atoms"]:
            atom_points = component_weight * _decimal(atom["weight"]) / atom_weight_total
            try:
                credit, detail = _atom_credit(atom, candidate)
            except (KeyError, TypeError, ValueError) as exc:
                credit, detail = Decimal(0), {"reason": "invalid-candidate-value", "message": str(exc)}
            credit = max(Decimal(0), min(Decimal(1), credit))
            points = atom_points * credit
            atom_report = {
                "id": atom["id"],
                "type": atom["type"],
                "credit": _published_number(credit, "0.000001"),
                "max_points": _published_number(atom_points),
                "raw_points": _published_number(points),
                "adjusted_points": _published_number(points),
                "detail": detail,
            }
            atom_reports.append(atom_report)
            atom_ref = f"{component['id']}.{atom['id']}"
            atom_lookup[atom_ref] = atom_report
            if atom.get("commitment") is True:
                wrong_present_count = _wrong_present_commitment_count(atom, candidate, credit, detail)
                if wrong_present_count:
                    commitment_violations.append(
                        {
                            "atom_ref": atom_ref,
                            "wrong_present_count": wrong_present_count,
                        }
                    )
            component_score += points
        component_reports.append(
            {
                "id": component["id"],
                "weight": _published_number(component_weight),
                "semantic": component.get("semantic") is True,
                "score": _published_number(component_score),
                "atoms": atom_reports,
            }
        )
        raw_score += component_score

    integrity_hits = _integrity_hits(rubric, candidate)
    for event in integrity_hits:
        for atom_ref in event.get("zero_atoms", []):
            atom_lookup[atom_ref]["adjusted_points"] = 0

    adjusted_components: dict[str, int | float] = {}
    adjusted_total = Decimal(0)
    for component in component_reports:
        adjusted = sum((_decimal(atom["adjusted_points"]) for atom in component["atoms"]), Decimal(0))
        adjusted_components[component["id"]] = _published_number(adjusted)
        adjusted_total += adjusted

    penalty_cap = _decimal(rubric["score"]["integrity_penalty_cap"])
    penalty = min(
        penalty_cap,
        sum((_decimal(event.get("penalty", 0)) for event in integrity_hits), Decimal(0)),
    )
    pre_commitment_score = max(Decimal(0), min(Decimal(100), adjusted_total - penalty))
    commitment_cap = rubric["score"].get("wrong_commitment_cap")
    score = pre_commitment_score
    if commitment_violations and commitment_cap is not None:
        score = min(score, _decimal(commitment_cap))
    commitment_violations.sort(key=lambda violation: violation["atom_ref"])
    if integrity_hits:
        status = "FAIL-INTEGRITY"
    elif commitment_violations:
        status = "FAIL-COMMITMENT"
    elif score >= _decimal(rubric["score"]["pass_threshold"]):
        status = "PASS"
    elif score >= _decimal(rubric["score"]["partial_threshold"]):
        status = "PARTIAL"
    else:
        status = "FAIL"

    return {
        "report_version": "v4-score-report-1",
        "scenario_id": rubric["scenario_id"],
        "scoreable": True,
        "status": status,
        "raw_score": _published_number(raw_score),
        "adjusted_components": adjusted_components,
        "penalty": _published_number(penalty),
        "score": _published_number(score),
        "thresholds": {
            "partial": rubric["score"]["partial_threshold"],
            "pass": rubric["score"]["pass_threshold"],
        },
        "components": component_reports,
        "integrity_events": [
            {
                "id": event["id"],
                "zero_atoms": sorted(event.get("zero_atoms", [])),
                "penalty": event.get("penalty", 0),
            }
            for event in integrity_hits
        ],
        "commitment_cap": commitment_cap,
        "commitment_violations": commitment_violations,
        "candidate_diagnostics": diagnostics,
    }
