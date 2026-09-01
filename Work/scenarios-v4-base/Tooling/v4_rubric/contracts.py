from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from .normalization import normalize_scalar


SUPPORTED_ATOM_TYPES = {
    "categorical",
    "numeric",
    "set_f1",
    "source_binding_f1",
    "source_ranking",
    "case_fraction",
    "findings_f1",
    "required_fields",
}


class ContractError(ValueError):
    """The hidden rubric is invalid or internally inconsistent."""


def _identity_value(value: Any, *, casefold: bool = False, aliases: dict[str, str] | None = None) -> str:
    normalized = normalize_scalar(value, casefold=casefold, aliases=aliases)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _observation_identities(atom: dict[str, Any]) -> list[tuple[str, str]]:
    atom_type = atom["type"]
    if atom_type == "required_fields":
        paths = atom.get("required_paths", [])
        if not isinstance(paths, list) or not all(isinstance(path, str) and path for path in paths):
            raise ContractError(f"required_fields atom {atom.get('id')} requires non-empty string paths")
        return [(path, "presence") for path in paths]

    candidate_path = atom.get("candidate_path")
    if not isinstance(candidate_path, str) or not candidate_path:
        raise ContractError(f"atom {atom.get('id')} requires candidate_path")

    if atom_type == "case_fraction":
        expected = atom.get("expected")
        if not isinstance(expected, dict):
            raise ContractError(f"case_fraction atom {atom.get('id')} requires an expected object")
        id_field = atom.get("id_field", "id")
        value_field = atom.get("value_field", "value")
        casefold_ids = atom.get("casefold_ids", False)
        return [
            (
                candidate_path,
                f"{id_field}={_identity_value(case_id, casefold=casefold_ids)};field={value_field}",
            )
            for case_id in sorted(expected, key=str)
        ]

    if atom_type == "source_binding_f1":
        expected = atom.get("expected")
        if not isinstance(expected, list) or not all(isinstance(item, dict) for item in expected):
            raise ContractError(f"source_binding_f1 atom {atom.get('id')} requires expected objects")
        id_field = atom.get("id_field", "id")
        source_field = atom.get("source_ids_field", "source_ids")
        casefold_ids = atom.get("casefold_ids", False)
        return [
            (
                candidate_path,
                f"{id_field}={_identity_value(item.get(id_field), casefold=casefold_ids)};field={source_field}",
            )
            for item in expected
        ]

    if atom_type == "findings_f1":
        expected = atom.get("expected")
        match_fields = atom.get("match_fields")
        if not isinstance(expected, list) or not all(isinstance(item, dict) for item in expected):
            raise ContractError(f"findings_f1 atom {atom.get('id')} requires expected objects")
        if not isinstance(match_fields, list) or not all(isinstance(field, str) and field for field in match_fields):
            raise ContractError(f"findings_f1 atom {atom.get('id')} requires match_fields")
        casefold_fields = set(atom.get("casefold_fields", []))
        aliases = atom.get("field_aliases", {})
        return [
            (
                candidate_path,
                "match="
                + json.dumps(
                    [
                        [
                            field,
                            _identity_value(
                                item.get(field),
                                casefold=field in casefold_fields,
                                aliases=aliases.get(field),
                            ),
                        ]
                        for field in match_fields
                    ],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
            for item in expected
        ]

    return [(candidate_path, "value")]


def as_decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ContractError(f"{label} must be a finite number") from exc
    if not result.is_finite():
        raise ContractError(f"{label} must be a finite number")
    return result


def validate_rubric(rubric: dict[str, Any]) -> None:
    if not isinstance(rubric, dict):
        raise ContractError("rubric must be an object")
    if rubric.get("schema_version") != "v4-rubric-1":
        raise ContractError("schema_version must be v4-rubric-1")
    if not isinstance(rubric.get("scenario_id"), str) or not rubric["scenario_id"]:
        raise ContractError("scenario_id is required")

    score = rubric.get("score")
    if not isinstance(score, dict):
        raise ContractError("score contract is required")
    if as_decimal(score.get("max_points"), "score.max_points") != 100:
        raise ContractError("score.max_points must equal 100")
    partial = as_decimal(score.get("partial_threshold"), "score.partial_threshold")
    passed = as_decimal(score.get("pass_threshold"), "score.pass_threshold")
    if not (Decimal(0) <= partial < passed <= Decimal(100)):
        raise ContractError("score thresholds must satisfy 0 <= partial < pass <= 100")
    penalty_cap = as_decimal(score.get("integrity_penalty_cap"), "score.integrity_penalty_cap")
    if not (Decimal(0) <= penalty_cap <= Decimal(15)):
        raise ContractError("integrity penalty cap must be between 0 and 15")
    wrong_commitment_cap = None
    if "wrong_commitment_cap" in score:
        wrong_commitment_cap = as_decimal(score["wrong_commitment_cap"], "score.wrong_commitment_cap")
        if not (Decimal(0) <= wrong_commitment_cap < partial):
            raise ContractError("score.wrong_commitment_cap must be below the partial threshold")

    components = rubric.get("components")
    if not isinstance(components, list) or not components:
        raise ContractError("components must be a non-empty list")

    component_ids: set[str] = set()
    atom_refs: set[str] = set()
    observation_refs: dict[tuple[str, str], str] = {}
    total_weight = Decimal(0)
    semantic_weight = Decimal(0)
    has_commitment_atom = False
    for component in components:
        if not isinstance(component, dict):
            raise ContractError("each component must be an object")
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id or component_id in component_ids:
            raise ContractError("component ids must be unique non-empty strings")
        component_ids.add(component_id)
        component_weight = as_decimal(component.get("weight"), f"component {component_id} weight")
        if component_weight <= 0:
            raise ContractError(f"component {component_id} weight must be positive")
        total_weight += component_weight
        if component.get("semantic") is True:
            semantic_weight += component_weight

        atoms = component.get("atoms")
        if not isinstance(atoms, list) or not atoms:
            raise ContractError(f"component {component_id} must have atoms")
        atom_ids: set[str] = set()
        atom_weight_total = Decimal(0)
        for atom in atoms:
            if not isinstance(atom, dict):
                raise ContractError(f"component {component_id} contains a non-object atom")
            atom_id = atom.get("id")
            if not isinstance(atom_id, str) or not atom_id or atom_id in atom_ids:
                raise ContractError(f"component {component_id} atom ids must be unique")
            atom_ids.add(atom_id)
            atom_refs.add(f"{component_id}.{atom_id}")
            if atom.get("type") not in SUPPORTED_ATOM_TYPES:
                raise ContractError(f"unsupported atom type for {component_id}.{atom_id}")
            if "numeric_string_equivalence" in atom and (
                atom["type"] != "case_fraction" or not isinstance(atom["numeric_string_equivalence"], bool)
            ):
                raise ContractError(
                    f"numeric_string_equivalence is only a boolean case_fraction option for {component_id}.{atom_id}"
                )
            if "commitment" in atom and not isinstance(atom["commitment"], bool):
                raise ContractError(f"commitment must be boolean for {component_id}.{atom_id}")
            if atom.get("commitment") is True:
                has_commitment_atom = True
            atom_ref = f"{component_id}.{atom_id}"
            for identity in _observation_identities(atom):
                previous_ref = observation_refs.get(identity)
                if previous_ref is not None:
                    path, projection = identity
                    rendered = path if not projection else f"{path} [{projection}]"
                    raise ContractError(
                        f"duplicate observation identity {rendered}: {previous_ref} and {atom_ref}"
                    )
                observation_refs[identity] = atom_ref
            atom_weight = as_decimal(atom.get("weight"), f"atom {component_id}.{atom_id} weight")
            if atom_weight <= 0:
                raise ContractError(f"atom {component_id}.{atom_id} weight must be positive")
            atom_weight_total += atom_weight

        for atom in atoms:
            atom_weight = as_decimal(atom["weight"], f"atom {component_id}.{atom['id']} weight")
            atom_points = component_weight * atom_weight / atom_weight_total
            if atom_points > 10:
                raise ContractError(
                    f"ordinary atom {component_id}.{atom['id']} is worth {atom_points} points (>10)"
                )
            if atom["type"] == "numeric":
                full = as_decimal(atom.get("full_tolerance"), f"{component_id}.{atom['id']} full_tolerance")
                zero = as_decimal(atom.get("zero_tolerance"), f"{component_id}.{atom['id']} zero_tolerance")
                if full < 0 or zero <= full:
                    raise ContractError(
                        f"numeric atom {component_id}.{atom['id']} requires 0 <= full_tolerance < zero_tolerance"
                    )

    if total_weight != 100:
        raise ContractError(f"component weights sum to {total_weight}, expected 100")
    if semantic_weight < 70:
        raise ContractError(f"semantic component weight is {semantic_weight}, expected at least 70")
    if has_commitment_atom and wrong_commitment_cap is None:
        raise ContractError("score.wrong_commitment_cap is required for commitment-bearing atoms")

    for event in rubric.get("integrity_events", []):
        if not isinstance(event, dict) or event.get("type") != "forbidden_value":
            raise ContractError("integrity events must use type forbidden_value")
        penalty = as_decimal(event.get("penalty", 0), f"integrity event {event.get('id')} penalty")
        if penalty < 0 or penalty > penalty_cap:
            raise ContractError(f"integrity event {event.get('id')} penalty exceeds the declared cap")
        for atom_ref in event.get("zero_atoms", []):
            if atom_ref not in atom_refs:
                raise ContractError(f"integrity event {event.get('id')} references unknown atom {atom_ref}")
