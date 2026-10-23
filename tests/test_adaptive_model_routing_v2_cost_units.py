"""Recorded numeric cost needs a unit; unknown cost remains unknown, not zero."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "model-routing-v2"


@pytest.fixture(scope="module")
def records():
    schema = json.loads((DOCS / "adaptive-routing-operational.v2.schema.json").read_text(encoding="utf-8"))
    examples = json.loads((DOCS / "operational-examples.v2.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema, examples


def validator(schema, name):
    return jsonschema.Draft202012Validator(
        {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{name}"},
        format_checker=jsonschema.FormatChecker(),
    )


@pytest.mark.parametrize("cost", [0, 1, 18.5])
def test_recorded_numeric_cost_without_currency_is_not_comparable(records, cost):
    schema, examples = records
    result = copy.deepcopy(examples["routeOutcome"])
    result["metrics"]["acceptedResultCost"] = cost
    result["metrics"]["currency"] = None
    assert list(validator(schema, "routeOutcome").iter_errors(result))


@pytest.mark.parametrize("cost,currency", [(0,"USD"), (18.5,"EUR"), (None,None), (None,"USD")])
def test_valid_and_unknown_cost_keep_their_declared_units(records, cost, currency):
    schema, examples = records
    result = copy.deepcopy(examples["routeOutcome"])
    result["metrics"]["acceptedResultCost"] = cost
    result["metrics"]["currency"] = currency
    validator(schema, "routeOutcome").validate(result)


@pytest.mark.parametrize("cost,currency", [(-1,"USD"), (True,"USD"), (1,""), (1,True)])
def test_invalid_cost_or_currency_remains_rejected(records, cost, currency):
    schema, examples = records
    result = copy.deepcopy(examples["routeOutcome"])
    result["metrics"]["acceptedResultCost"] = cost
    result["metrics"]["currency"] = currency
    assert list(validator(schema, "routeOutcome").iter_errors(result))


def test_outcome_rule_matches_existing_resource_budget_rule(records):
    schema, examples = records
    budget = copy.deepcopy(examples["routeControl"]["resourceBudget"])
    budget["maxAcceptedResultCost"] = 0
    budget["currency"] = None
    assert list(validator(schema,"resourceBudget").iter_errors(budget))
    budget["currency"] = "USD"
    validator(schema, "resourceBudget").validate(budget)


@pytest.mark.parametrize("name", ["routeControl", "dispatchControl", "writeDispatchControl", "decisionControl", "routeOutcome", "workerResultControl"])
def test_all_published_operational_examples_still_validate(records, name):
    schema, examples = records
    definition = "dispatchControl" if name == "writeDispatchControl" else name
    validator(schema, definition).validate(examples[name])
