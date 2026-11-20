"""Direct registration persistence uses the existing credential scanner."""
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from test_sdk_root_registry import registry_fixture
from provider_prompt import ProviderOutputContext
from sdk_execution import runtime
from test_sdk_child_lead_authority import INSTANT


@pytest.mark.parametrize("include_credential", [False, True])
def test_direct_publisher_scans_registration_without_banning_root_source_paths(
        tmp_path, monkeypatch, include_credential):
    registry, owner, assignment, requests, selections, root, proposal, candidate = registry_fixture(tmp_path, monkeypatch)
    needle = "synthetic-" + uuid4().hex
    prompt = "Inspect the Root-authorized source at " + str(tmp_path / "source.py")
    if include_credential:
        prompt += " " + needle
    request = runtime.prepare_codex_request(replace(candidate, prompt=prompt))
    requests["direct-root-task"] = request
    selection = selections["task-one"]
    registration = {"schemaVersion": 1, "request": request.to_dict(), "selection": selection.to_dict()}
    monkeypatch.setattr(runtime, "prepare_environment", lambda *a: ({}, ProviderOutputContext((needle.encode(),))))
    ledger = Path(root.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes()
    artifact = "direct-registration.json"
    def publish():
        return runtime.publish_child_task_admission(
            authority=owner, proposal_id=proposal["proposal_id"], accepted=True,
            request_id="direct-root-task", selection=selection, artifact=artifact,
            started_at=INSTANT, registration=registration)
    if include_credential:
        with pytest.raises(ValueError, match="E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"):
            publish()
        assert ledger.read_bytes() == before
        assert not (Path(root.work_item) / artifact).exists()
        assert owner.proposal_results(assignment)[proposal["proposal_id"]]["status"] == "pending"
    else:
        outcome = publish()
        assert outcome["status"] == "accepted"
        assert "registration" not in outcome["admission"]
        assert runtime._child_admission_document(owner, assignment, proposal["proposal_id"])["registration"] == registration
