"""Execute the guide's schema-validation example; no runtime or provider is launched."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import jsonschema
import pytest

V2 = Path(__file__).resolve().parents[1] / "docs/model-routing-v2"
BUNDLES = {
    "core": "adaptive-routing-contracts.v2.schema.json",
    "operational": "adaptive-routing-operational.v2.schema.json",
}


def _example():
    guide = (V2 / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)\n```", guide, re.DOTALL)
    blocks = [block for block in blocks if "def validate_record(" in block]
    assert len(blocks) == 1, "guide must supply one executable record-validation example"
    namespace = {}
    exec(compile(blocks[0], str(V2 / "README.md"), "exec"), namespace)
    return namespace["validate_record"]


def _bundle(kind):
    return json.loads((V2 / BUNDLES[kind]).read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind,example_file,name,definition", [
    ("core", "examples.v2.json", "leadLease", "leadLease"),
    ("core", "examples.v2.json", "registrySnapshot", "modelRegistrySnapshot"),
    ("core", "examples.v2.json", "routeRequest", "routeRequest"),
    ("core", "examples.v2.json", "routeDecision", "routeDecision"),
    ("core", "examples.v2.json", "workerResult", "workerResult"),
    ("operational", "operational-examples.v2.json", "routeControl", "routeControl"),
    ("operational", "operational-examples.v2.json", "dispatchControl", "dispatchControl"),
    ("operational", "operational-examples.v2.json", "writeDispatchControl", "dispatchControl"),
    ("operational", "operational-examples.v2.json", "decisionControl", "decisionControl"),
    ("operational", "operational-examples.v2.json", "workerResultControl", "workerResultControl"),
    ("operational", "operational-examples.v2.json", "routeOutcome", "routeOutcome"),
])
def test_documented_validator_accepts_record_shapes_but_rejects_an_empty_record(kind, example_file, name, definition):
    validate = _example()
    bundle = _bundle(kind)
    record = json.loads((V2 / example_file).read_text(encoding="utf-8"))[name]
    before = copy.deepcopy(record)
    validate(bundle, definition, record)
    assert record == before
    with pytest.raises(jsonschema.ValidationError):
        validate(bundle, definition, {})


@pytest.mark.parametrize("kind,definition", [("core", "leadLease"), ("operational", "dispatchControl")])
def test_documented_validator_rejects_a_wrong_record_type(kind, definition):
    with pytest.raises(jsonschema.ValidationError):
        _example()(_bundle(kind), definition, [])


@pytest.mark.parametrize("kind", BUNDLES)
def test_documented_validator_refuses_unknown_contract_names(kind):
    with pytest.raises(ValueError, match="unknown record definition"):
        _example()(_bundle(kind), "missing-record", {})


@pytest.mark.parametrize("timestamp", ["2026-02-30T16:00:00Z", "2026-09-05T25:00:00Z"])
def test_documented_validator_checks_calendar_formats(timestamp):
    record = json.loads((V2 / "examples.v2.json").read_text(encoding="utf-8"))["leadLease"]
    record["acquiredAt"] = timestamp
    with pytest.raises(jsonschema.ValidationError):
        _example()(_bundle("core"), "leadLease", record)


def test_documented_validator_uses_the_callers_expected_contract():
    record = json.loads((V2 / "examples.v2.json").read_text(encoding="utf-8"))["workerResult"]
    with pytest.raises(jsonschema.ValidationError):
        _example()(_bundle("core"), "leadLease", record)


def test_documented_validator_refuses_missing_calendar_support(monkeypatch):
    record = json.loads((V2 / "examples.v2.json").read_text(encoding="utf-8"))["leadLease"]
    monkeypatch.delitem(jsonschema.FormatChecker.checkers, "date-time", raising=False)
    with pytest.raises(RuntimeError, match="date-time format checker is unavailable"):
        _example()(_bundle("core"), "leadLease", record)
