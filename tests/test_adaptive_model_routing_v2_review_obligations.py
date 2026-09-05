from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "docs" / "model-routing-v2"
RUNTIME = V2 / "runtime-validation-obligations.md"
CLOSURE = V2 / "review-loop-closure.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_deep_review_obligation_documents_exist() -> None:
    assert RUNTIME.is_file()
    assert CLOSURE.is_file()


def test_direct_lead_never_fabricates_independence() -> None:
    text = _text(RUNTIME)
    assert "Direct Lead work cannot satisfy independent-family" in text
    assert "same-provider worker must still be a separately admitted isolated run" in text


def test_policy_precedence_is_restrictive() -> None:
    text = _text(RUNTIME)
    assert "project restrictions that may only narrow" in text
    for forbidden_expansion in (
        "enable an external provider",
        "larger budget",
        "broader mutation",
        "waived gate",
    ):
        assert forbidden_expansion in text


def test_core_and_operational_contracts_have_one_authority_direction() -> None:
    text = _text(RUNTIME)
    assert "semantic routing records and subordinate operational envelopes agree" in text
    assert "operational controls may narrow execution but cannot override" in text


def test_portfolio_is_stage_local_and_cannot_consume_future_output() -> None:
    text = _text(RUNTIME)
    assert "stage-local" in text
    assert "no dispatch consumes a result from another dispatch in the same stage" in text


def test_model_and_tool_identity_are_observed_and_content_bound() -> None:
    text = _text(RUNTIME)
    for phrase in (
        "model identity evidence",
        "exact harness/tool identities",
        "raw provider output digest",
        "normalization transform",
    ):
        assert phrase in text


def test_shared_resource_pools_and_external_effects_are_separate_contracts() -> None:
    text = _text(RUNTIME)
    assert "entitlement/quota/billing/concurrency pool" in text
    assert "separate external-effect contract" in text
    assert "workspace-write alone is insufficient" in text


def test_synthesis_and_material_findings_remain_accountable() -> None:
    text = _text(RUNTIME)
    assert "every important or critical finding receives" in text
    assert "critical synthesis artifact is reviewed in a later stage" in text


def test_review_explicitly_rejects_unnecessary_architecture() -> None:
    text = _text(CLOSURE)
    for phrase in (
        "self-learning router",
        "cryptographic signatures",
        "automatic inference of correlated model failures",
        "permanent model-generation rankings",
    ):
        assert phrase in text


def test_unavailable_lead_never_promotes_a_worker() -> None:
    text = _text(RUNTIME)
    assert "no admitted Lead Host is available" in text
    assert "no worker or reviewer is promoted automatically" in text


def test_human_gate_is_an_identity_bound_record_not_a_boolean() -> None:
    text = _text(RUNTIME)
    for phrase in (
        "approving principal and authority source",
        "exact decision/artifact digests",
        "revocation state",
        "boolean `resolved` field is never sufficient",
    ):
        assert phrase in text


def test_build_evidence_and_generated_code_need_external_verification() -> None:
    text = _text(RUNTIME)
    assert "exact command, working root, toolchain/runtime versions" in text
    assert "worker summary is not test evidence" in text
    assert "license, provenance, attribution, vulnerability" in text
    assert "model assertion that code is original or compatible is not evidence" in text


def test_adaptive_evidence_cannot_be_poisoned_by_model_self_ratings() -> None:
    text = _text(RUNTIME)
    assert "model self-ratings" in text
    assert "retain negative and abandoned outcomes" in text
    assert "survivor bias" in text


def test_documentation_links_resolve_to_existing_headings() -> None:
    import re

    for path in (RUNTIME, CLOSURE):
        text = _text(path)
        headings = set()
        for heading in re.findall(r"^#{1,6} (.+)$", text, re.MULTILINE):
            slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
            headings.add(slug)
        for target in re.findall(r"\]\(#([^\)]+)\)", text):
            assert target in headings, (path.name, target)


def test_documentation_does_not_claim_runtime_enforcement() -> None:
    for path in (RUNTIME, CLOSURE):
        assert "not runtime enforcement" in _text(path)
