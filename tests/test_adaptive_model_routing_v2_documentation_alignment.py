"""Documentation checks: current field names, not proof of runtime enforcement."""
from __future__ import annotations

import json
from pathlib import Path

V2 = Path(__file__).resolve().parents[1] / "docs/model-routing-v2"


def _result_contract_and_section():
    schema = json.loads((V2 / "adaptive-routing-operational.v2.schema.json").read_text(encoding="utf-8"))
    document = (V2 / "deep-review-operational-hardening.md").read_text(encoding="utf-8")
    section = document.split("## 9. Result admission and process settlement\n", 1)[1].split("\n## 10.", 1)[0]
    return schema["$defs"]["workerResultControl"], section


def test_result_documentation_names_execution_kind_and_settlement_fields():
    contract, section = _result_contract_and_section()
    for name in ("executionKind", "executionSettled", "processDisposition"):
        assert name in contract["required"]
        assert f"`{name}`" in section, f"result documentation omits {name}"
    for kind in contract["properties"]["executionKind"]["enum"]:
        assert f"`{kind}`" in section


def test_result_documentation_names_both_schema_ownership_fences():
    contract, section = _result_contract_and_section()
    for name in ("executionLeadFence", "admittingLeadFence"):
        assert name in contract["required"]
        assert f"`{name}`" in section, f"result documentation omits {name}"
    assert "`revalidated-after-transfer`" in section


def test_contract_index_exposes_the_committed_runtime_handoff_documents():
    guide = (V2 / "README.md").read_text(encoding="utf-8")
    for name in ("runtime-validation-obligations.md", "review-loop-closure.md"):
        assert (V2 / name).is_file()
        assert f"]({name})" in guide, f"contract index has no link to {name}"


def test_implementation_plan_requires_operational_admission_before_launch():
    root = V2.parents[1]
    plan = (root / "docs/superpowers/plans/2026-09-04-adaptive-lead-model-routing-v2-implementation.md").read_text(encoding="utf-8")
    scheduler = plan.split("## Phase 4:", 1)[1].split("\n## Phase 5:", 1)[0]
    assert "`dispatchSpec`" in scheduler
    assert "`dispatchControl`" in scheduler
    assert "launch revalidation" in scheduler


def test_normative_spec_uses_the_existing_all_contradictions_gate():
    root = V2.parents[1]
    spec = (root / "docs/superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md").read_text(encoding="utf-8")
    section = spec.split("## 6. Structured disagreement\n", 1)[1].split("\n## 7.", 1)[0]
    assert "every unresolved contradiction" in section
    assert "`humanGateRequired = true`" in section
    assert "`selected`" in section
