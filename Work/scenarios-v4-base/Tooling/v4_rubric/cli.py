from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import jsonschema

from .contracts import ContractError
from .normalization import MISSING, canonical_identity, get_path
from .scoring import canonical_report_bytes, score_candidate


SAFE_INTEGER_EXCLUSIVE_LIMIT = 1 << 53


def scorer_error(scenario_id: str | None, code: str, message: str) -> dict[str, Any]:
    return {
        "report_version": "v4-score-report-1",
        "scenario_id": scenario_id,
        "scoreable": False,
        "status": "SCORER-ERROR",
        "raw_score": None,
        "score": None,
        "error": {"code": code, "message": message},
    }


def _json_pointer(parts: Any) -> str:
    encoded = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "" if not encoded else "/" + "/".join(encoded)


def _schema_diagnostics(validator: jsonschema.Draft202012Validator, candidate: Any) -> list[dict[str, Any]]:
    errors = sorted(
        validator.iter_errors(candidate),
        key=lambda error: (
            list(error.absolute_path),
            list(error.absolute_schema_path),
            str(error.validator),
        ),
    )
    return [
        {
            "code": "CANDIDATE-SCHEMA",
            "path": _json_pointer(error.absolute_path),
            "schema_path": _json_pointer(error.absolute_schema_path),
            "validator": str(error.validator),
        }
        for error in errors
    ]


class _JSONObject(dict):
    def __init__(self, pairs: list[tuple[str, Any]]) -> None:
        super().__init__()
        self.raw_duplicate_keys: list[dict[str, Any]] = []
        first_indexes: dict[str, int] = {}
        for index, (key, value) in enumerate(pairs):
            if key in first_indexes:
                self.raw_duplicate_keys.append(
                    {"key": key, "first_index": first_indexes[key], "duplicate_index": index}
                )
            else:
                first_indexes[key] = index
            self[key] = value


class _NumberLiteral:
    def __init__(self, raw: str, value: int | float | None, reason: str | None = None) -> None:
        self.raw = raw
        self.value = value
        self.reason = reason


def _parse_int_literal(raw: str) -> _NumberLiteral:
    try:
        value = int(raw)
    except ValueError:
        return _NumberLiteral(raw, None, "unsafe-integer")
    reason = "unsafe-integer" if abs(value) >= SAFE_INTEGER_EXCLUSIVE_LIMIT else None
    return _NumberLiteral(raw, value, reason)


def _parse_float_literal(raw: str) -> _NumberLiteral:
    try:
        decimal_value = Decimal(raw)
        float_value = float(raw)
    except (InvalidOperation, OverflowError, ValueError):
        return _NumberLiteral(raw, None, "invalid-decimal")
    if not decimal_value.is_finite() or not math.isfinite(float_value):
        return _NumberLiteral(raw, None, "not-binary64-finite")
    if decimal_value != 0 and float_value == 0.0:
        return _NumberLiteral(raw, None, "underflows-to-zero")
    if decimal_value == decimal_value.to_integral() and abs(decimal_value) >= SAFE_INTEGER_EXCLUSIVE_LIMIT:
        return _NumberLiteral(raw, None, "unsafe-integer")
    if Decimal(str(float_value)) != decimal_value:
        return _NumberLiteral(raw, None, "not-exactly-binary64-roundtrippable")
    return _NumberLiteral(raw, float_value)


def _parse_constant_literal(raw: str) -> _NumberLiteral:
    return _NumberLiteral(raw, None, "non-standard-non-finite")


def _candidate_object(pairs: list[tuple[str, Any]]) -> _JSONObject:
    return _JSONObject(pairs)


def _numeric_diagnostic(path: list[Any], literal: _NumberLiteral) -> dict[str, Any]:
    return {
        "code": "CANDIDATE-NUMERIC-DOMAIN",
        "path": _json_pointer(path),
        "literal": literal.raw,
        "reason": literal.reason,
    }


def _sanitize_candidate_value(value: Any, path: list[Any], diagnostics: list[dict[str, Any]]) -> Any:
    if isinstance(value, _NumberLiteral):
        if value.reason is not None:
            diagnostics.append(_numeric_diagnostic(path, value))
        return value.value
    if isinstance(value, _JSONObject):
        for duplicate in value.raw_duplicate_keys:
            diagnostics.append(
                {
                    "code": "CANDIDATE-DUPLICATE-JSON-KEY",
                    "path": _json_pointer(path),
                    **duplicate,
                }
            )
        return {key: _sanitize_candidate_value(child, [*path, key], diagnostics) for key, child in value.items()}
    if isinstance(value, list):
        return [_sanitize_candidate_value(child, [*path, index], diagnostics) for index, child in enumerate(value)]
    return value


def _load_candidate(candidate_path: Path) -> tuple[Any, list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    try:
        candidate_text = candidate_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, [{"code": "CANDIDATE-MISSING", "path": candidate_path.name}]
    except OSError:
        raise
    try:
        parsed = json.loads(
            candidate_text,
            object_pairs_hook=_candidate_object,
            parse_int=_parse_int_literal,
            parse_float=_parse_float_literal,
            parse_constant=_parse_constant_literal,
        )
    except json.JSONDecodeError as exc:
        return {}, [{"code": "CANDIDATE-INVALID-JSON", "message": str(exc)}]
    return _sanitize_candidate_value(parsed, [], diagnostics), diagnostics


def _identity_specs(rubric: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    collection_specs: dict[tuple[str, str], dict[str, Any]] = {}
    observation_specs: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for component in rubric["components"]:
        for atom in component["atoms"]:
            atom_type = atom["type"]
            if atom_type == "case_fraction":
                candidate_path = atom["candidate_path"]
                id_field = atom.get("id_field", "id")
                collection_specs[(candidate_path, id_field)] = {
                    "candidate_path": candidate_path,
                    "id_field": id_field,
                }
            elif atom_type == "source_binding_f1":
                candidate_path = atom["candidate_path"]
                id_field = atom.get("id_field", "id")
                collection_specs[(candidate_path, id_field)] = {
                    "candidate_path": candidate_path,
                    "id_field": id_field,
                }
            elif atom_type == "findings_f1":
                candidate_path = atom["candidate_path"]
                id_field = atom.get("reported_id_field", "id")
                match_fields = tuple(atom.get("match_fields", []))
                collection_specs[(candidate_path, id_field)] = {
                    "candidate_path": candidate_path,
                    "id_field": id_field,
                }
                observation_specs[(candidate_path, match_fields)] = {
                    "candidate_path": candidate_path,
                    "match_fields": match_fields,
                }
    id_fields_by_path: dict[str, set[str]] = {}
    for candidate_path, id_field in collection_specs:
        id_fields_by_path.setdefault(candidate_path, set()).add(id_field)
    for candidate_path, id_fields in sorted(id_fields_by_path.items()):
        if len(id_fields) > 1:
            raise ContractError(
                f"candidate_path {candidate_path} has ambiguous identity fields: {', '.join(sorted(id_fields))}"
            )
    return (
        [collection_specs[key] for key in sorted(collection_specs)],
        [observation_specs[key] for key in sorted(observation_specs)],
    )


def _set_path(root: dict[str, Any], path: str, value: Any) -> None:
    current = root
    parts = path.split(".") if path else []
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if parts and isinstance(current, dict):
        current[parts[-1]] = value


def _record_diagnostic(diagnostics: dict[str, dict[str, Any]], diagnostic: dict[str, Any]) -> None:
    key = json.dumps(diagnostic, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    diagnostics[key] = diagnostic


def _canonical_candidate_id(
    value: Any,
    *,
    candidate_path: str,
    id_field: str,
    diagnostics: dict[str, dict[str, Any]],
    index: int | None = None,
    map_key: str | None = None,
    embedded: bool = False,
) -> str | None:
    location: dict[str, Any] = {"candidate_path": candidate_path, "id_field": id_field}
    if index is not None:
        location["index"] = index
    if map_key is not None:
        location["map_key"] = map_key
    if embedded:
        location["embedded"] = True
    if not isinstance(value, str):
        _record_diagnostic(
            diagnostics,
            {
                "code": "CANDIDATE-INVALID-ID",
                **location,
                "reason": "missing" if value is MISSING else "non-string",
            },
        )
        return None
    logical_id = canonical_identity(value)
    if not logical_id:
        _record_diagnostic(
            diagnostics,
            {
                "code": "CANDIDATE-INVALID-ID",
                **location,
                "reason": "empty",
            },
        )
        return None
    return logical_id


def _normalize_identity_collection(
    collection: Any,
    *,
    candidate_path: str,
    id_field: str,
    diagnostics: dict[str, dict[str, Any]],
) -> Any:
    if isinstance(collection, list):
        normalized = []
        first_indexes: dict[str, int] = {}
        for index, raw_item in enumerate(collection):
            item = dict(raw_item) if isinstance(raw_item, dict) else raw_item
            if isinstance(item, dict):
                logical_id = _canonical_candidate_id(
                    item.get(id_field, MISSING),
                    candidate_path=candidate_path,
                    id_field=id_field,
                    diagnostics=diagnostics,
                    index=index,
                )
                if logical_id is None:
                    normalized.append(item)
                    continue
                if logical_id in first_indexes:
                    _record_diagnostic(
                        diagnostics,
                        {
                            "code": "CANDIDATE-DUPLICATE-ID",
                            "candidate_path": candidate_path,
                            "id_field": id_field,
                            "logical_id": logical_id,
                            "first_index": first_indexes[logical_id],
                            "duplicate_index": index,
                        },
                    )
                else:
                    first_indexes[logical_id] = index
                item[id_field] = logical_id
            normalized.append(item)
        return normalized

    if isinstance(collection, dict):
        normalized = []
        first_indexes: dict[str, int] = {}
        for index, key in enumerate(sorted(collection, key=str)):
            raw_item = collection[key]
            item = dict(raw_item) if isinstance(raw_item, dict) else {"value": raw_item}
            logical_id = _canonical_candidate_id(
                key,
                candidate_path=candidate_path,
                id_field=id_field,
                diagnostics=diagnostics,
                index=index,
                map_key=key,
            )
            if logical_id is None:
                normalized.append(item)
                continue
            if id_field in item:
                embedded_id = _canonical_candidate_id(
                    item[id_field],
                    candidate_path=candidate_path,
                    id_field=id_field,
                    diagnostics=diagnostics,
                    index=index,
                    map_key=key,
                    embedded=True,
                )
                if embedded_id is not None and embedded_id != logical_id:
                    _record_diagnostic(
                        diagnostics,
                        {
                            "code": "CANDIDATE-ID-CONTRADICTION",
                            "candidate_path": candidate_path,
                            "id_field": id_field,
                            "map_key": key,
                            "embedded_id": item[id_field],
                            "logical_id": logical_id,
                        },
                    )
            if logical_id in first_indexes:
                _record_diagnostic(
                    diagnostics,
                    {
                        "code": "CANDIDATE-DUPLICATE-ID",
                        "candidate_path": candidate_path,
                        "id_field": id_field,
                        "logical_id": logical_id,
                        "first_index": first_indexes[logical_id],
                        "duplicate_index": index,
                    },
                )
            else:
                first_indexes[logical_id] = index
            item[id_field] = logical_id
            normalized.append(item)
        return normalized

    return collection


def _normalize_observation_identities(
    scoring_view: dict[str, Any],
    observation_specs: list[dict[str, Any]],
    diagnostics: dict[str, dict[str, Any]],
) -> None:
    for spec in observation_specs:
        candidate_path = spec["candidate_path"]
        match_fields = spec["match_fields"]
        collection = get_path(scoring_view, candidate_path, [])
        if not isinstance(collection, list):
            continue
        first_indexes: dict[str, int] = {}
        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                continue
            observation = []
            invalid = False
            for field in match_fields:
                value = item.get(field, MISSING)
                if not isinstance(value, str):
                    _record_diagnostic(
                        diagnostics,
                        {
                            "code": "CANDIDATE-INVALID-OBSERVATION",
                            "candidate_path": candidate_path,
                            "match_field": field,
                            "index": index,
                            "reason": "missing" if value is MISSING else "non-string",
                        },
                    )
                    invalid = True
                    continue
                logical_value = canonical_identity(value)
                if not logical_value:
                    _record_diagnostic(
                        diagnostics,
                        {
                            "code": "CANDIDATE-INVALID-OBSERVATION",
                            "candidate_path": candidate_path,
                            "match_field": field,
                            "index": index,
                            "reason": "empty",
                        },
                    )
                    invalid = True
                    continue
                observation.append([field, logical_value])
            if invalid:
                continue
            logical_observation = json.dumps(
                observation,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            if logical_observation in first_indexes:
                _record_diagnostic(
                    diagnostics,
                    {
                        "code": "CANDIDATE-DUPLICATE-OBSERVATION",
                        "candidate_path": candidate_path,
                        "match_fields": list(match_fields),
                        "logical_observation": observation,
                        "first_index": first_indexes[logical_observation],
                        "duplicate_index": index,
                    },
                )
            else:
                first_indexes[logical_observation] = index
            for field, value in observation:
                item[field] = value


def _normalized_scoring_view(rubric: dict[str, Any], candidate: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scoring_view = deepcopy(candidate)
    collection_specs, observation_specs = _identity_specs(rubric)
    diagnostics: dict[str, dict[str, Any]] = {}
    for spec in collection_specs:
        candidate_path = spec["candidate_path"]
        collection = get_path(scoring_view, candidate_path, MISSING)
        if collection is MISSING:
            continue
        normalized = _normalize_identity_collection(
            collection,
            candidate_path=candidate_path,
            id_field=spec["id_field"],
            diagnostics=diagnostics,
        )
        _set_path(scoring_view, candidate_path, normalized)
    _normalize_observation_identities(scoring_view, observation_specs, diagnostics)
    return scoring_view, [diagnostics[key] for key in sorted(diagnostics)]


def score_root(root: Path, candidate: Path | None = None) -> dict[str, Any]:
    rubric_path = root / "oracle" / "rubric.json"
    try:
        rubric_text = rubric_path.read_text(encoding="utf-8")
    except OSError as exc:
        return scorer_error(None, "RUBRIC-LOAD", f"{type(exc).__name__} reading rubric.json")
    try:
        rubric = json.loads(rubric_text)
    except json.JSONDecodeError as exc:
        return scorer_error(None, "RUBRIC-LOAD", f"invalid rubric.json: {exc.msg} at line {exc.lineno} column {exc.colno}")

    schema_path = root / "inputs" / "output-schema.json"
    try:
        schema_text = schema_path.read_text(encoding="utf-8")
    except OSError as exc:
        return scorer_error(
            rubric.get("scenario_id"),
            "OUTPUT-SCHEMA-LOAD",
            f"{type(exc).__name__} reading output-schema.json",
        )
    try:
        schema = json.loads(schema_text)
    except json.JSONDecodeError as exc:
        return scorer_error(
            rubric.get("scenario_id"),
            "OUTPUT-SCHEMA-LOAD",
            f"invalid output-schema.json: {exc.msg} at line {exc.lineno} column {exc.colno}",
        )
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        schema_validator = jsonschema.Draft202012Validator(schema)
    except jsonschema.SchemaError as exc:
        return scorer_error(
            rubric.get("scenario_id"),
            "OUTPUT-SCHEMA-CONTRACT",
            f"invalid output-schema.json at {_json_pointer(exc.absolute_schema_path)}",
        )

    artifact = rubric.get("candidate_artifact", "answer.json")
    candidate_path = candidate or (root / "candidate" / artifact)
    if candidate_path.is_dir():
        candidate_path = candidate_path / artifact
    diagnostics: list[dict[str, Any]] = []
    try:
        candidate_data, diagnostics = _load_candidate(candidate_path)
    except FileNotFoundError:
        candidate_data = {}
        diagnostics.append({"code": "CANDIDATE-MISSING", "path": candidate_path.name})
    except OSError as exc:
        return scorer_error(
            rubric.get("scenario_id"),
            "CANDIDATE-IO",
            f"{type(exc).__name__} reading {candidate_path.name}",
        )

    if not diagnostics:
        diagnostics.extend(_schema_diagnostics(schema_validator, candidate_data))
    scoring_view = candidate_data
    if not diagnostics and isinstance(candidate_data, dict):
        try:
            scoring_view, identity_diagnostics = _normalized_scoring_view(rubric, candidate_data)
        except ContractError as exc:
            return scorer_error(rubric.get("scenario_id"), "RUBRIC-CONTRACT", str(exc))
        diagnostics.extend(identity_diagnostics)

    try:
        return score_candidate(rubric, scoring_view, candidate_diagnostics=diagnostics)
    except ContractError as exc:
        return scorer_error(rubric.get("scenario_id"), "RUBRIC-CONTRACT", str(exc))
    except Exception as exc:  # noqa: BLE001 - unexpected scorer failures must never become model zero.
        return scorer_error(rubric.get("scenario_id"), "SCORER-EXCEPTION", f"{type(exc).__name__}: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score one benchmark v4 candidate deterministically.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser


def run_cli(root: Path, candidate: Path | None, json_out: Path | None = None) -> int:
    report = score_root(root.resolve(), candidate.resolve() if candidate else None)
    payload = canonical_report_bytes(report)
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_bytes(payload + b"\n")
    sys.stdout.buffer.write(payload + b"\n")
    return 2 if report["status"] == "SCORER-ERROR" else 0


def main() -> int:
    args = build_parser().parse_args()
    return run_cli(args.root, args.candidate, args.json_out)


if __name__ == "__main__":
    raise SystemExit(main())
