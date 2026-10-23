"""Scope regressions for a design-only proposal; no provider execution."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "docs/model-routing-v2"
BUNDLES = ("adaptive-routing-contracts.v2.schema.json",
           "adaptive-routing-operational.v2.schema.json")


def test_every_retained_definition_has_one_ownership_disposition():
    scope = (V2 / "contract-scope.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([^`]+)` \|", scope, re.MULTILINE)
    definitions = set()
    for name in BUNDLES:
        definitions.update(json.loads((V2 / name).read_text(encoding="utf-8"))["$defs"])
    assert len(rows) == len(set(rows))
    assert set(rows) == definitions


@pytest.mark.parametrize("name", BUNDLES)
def test_bundle_scope_is_documented_without_new_validation_authority(name):
    bundle = json.loads((V2 / name).read_text(encoding="utf-8"))
    assert "deferred transferable-host" in bundle["$comment"]
    assert "contract-scope.md" in bundle["$comment"]
    jsonschema.Draft202012Validator.check_schema(bundle)


@pytest.mark.parametrize("bundle_name,example_name,definition,field", [
    (BUNDLES[0], "examples.v2.json", "routeRequest", "leadLeaseId"),
    (BUNDLES[1], "operational-examples.v2.json", "routeControl", "leadFence"),
])
def test_deferring_host_transfer_does_not_weaken_old_required_fields(
        bundle_name, example_name, definition, field):
    bundle = json.loads((V2 / bundle_name).read_text(encoding="utf-8"))
    record = copy.deepcopy(json.loads((V2 / example_name).read_text(encoding="utf-8"))[definition])
    assert field in bundle["$defs"][definition]["required"]
    del record[field]
    wrapper = {"$schema": bundle["$schema"], "$defs": bundle["$defs"],
               "$ref": f"#/$defs/{definition}"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(wrapper).validate(record)


def test_guide_does_not_present_old_examples_as_comparison_inputs():
    guide = (V2 / "README.md").read_text(encoding="utf-8")
    assert "NOT the" in guide
    assert "input/output schema of the initial pure comparison function" in guide
    assert "no runtime rollout" in (ROOT / "docs/README.md").read_text(encoding="utf-8")
    for name in ("contract-scope.md", "current-main-delta.md", "legacy-pr-disposition.md"):
        assert f"]({name})" in guide


def test_scope_does_not_create_a_second_mutable_store():
    scope = (V2 / "contract-scope.md").read_text(encoding="utf-8")
    assert "not a production registry or runtime configuration" in scope
    assert "no replacement process supervisor" in scope
    assert "No parallel writable review store" in scope
    assert "A worker result or route recommendation never grants publication or launch" in scope
