"""V2 scalar identities must match the entire value, not a line prefix."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

V2 = Path(__file__).resolve().parents[1] / "docs/model-routing-v2"
BUNDLES = {
    "semantic": ("adaptive-routing-contracts.v2.schema.json", "#/$defs/leadLease/$defs/"),
    "operational": ("adaptive-routing-operational.v2.schema.json", "#/$defs/"),
}
VALID = {"token": "identity-current", "digest": "a" * 64, "timestamp": "2028-02-29T16:00:00Z"}


def _validator(bundle: str, reference: str):
    schema = json.loads((V2 / BUNDLES[bundle][0]).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(
        {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": reference},
        format_checker=jsonschema.FormatChecker(),
    )


@pytest.mark.parametrize("bundle", BUNDLES)
@pytest.mark.parametrize("scalar", VALID)
@pytest.mark.parametrize("ending", ["\n", "\r", "\r\n", "\u2028", "\u2029"],
                         ids=["lf", "cr", "crlf", "line-separator", "paragraph-separator"])
def test_wire_scalar_rejects_a_trailing_line_terminator(bundle, scalar, ending):
    validator = _validator(bundle, BUNDLES[bundle][1] + scalar)
    validator.validate(VALID[scalar])
    value = json.loads(json.dumps(VALID[scalar] + ending))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(value)


@pytest.mark.parametrize("bundle", BUNDLES)
@pytest.mark.parametrize("scalar,value", [
    ("token", "A"), ("token", "A" * 128), ("token", "a._:/-9"),
    ("digest", "0123456789abcdef" * 4),
    ("timestamp", "2028-02-29T16:00:00Z"),
    ("timestamp", "2028-02-29T16:00:00.123456789Z"),
])
def test_scalar_boundaries_preserve_valid_identity_and_time(bundle, scalar, value):
    _validator(bundle, BUNDLES[bundle][1] + scalar).validate(value)


@pytest.mark.parametrize("bundle,example_file,example_name,definition,field", [
    ("semantic", "examples.v2.json", "leadLease", "leadLease", "leaseId"),
    ("semantic", "examples.v2.json", "leadLease", "leadLease", "acquiredAt"),
    ("semantic", "examples.v2.json", "workerResult", "workerResult", "artifactDigest"),
    ("operational", "operational-examples.v2.json", "dispatchControl", "dispatchControl", "dispatchId"),
    ("operational", "operational-examples.v2.json", "dispatchControl", "dispatchControl", "deadlineAt"),
    ("operational", "operational-examples.v2.json", "dispatchControl", "dispatchControl", "dispatchSpecDigest"),
])
def test_record_references_enforce_scalar_termination(bundle, example_file, example_name, definition, field):
    record = json.loads((V2 / example_file).read_text(encoding="utf-8"))[example_name]
    validator = _validator(bundle, f"#/$defs/{definition}")
    validator.validate(record)
    changed = copy.deepcopy(record)
    changed[field] += "\n"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(changed)
