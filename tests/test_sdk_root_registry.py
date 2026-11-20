"""Explicit Root registration persisted in the existing admission receipt."""
from dataclasses import replace
import pytest
from test_sdk_dynamic_child_admission import proposed
from sdk_execution import runtime
from test_sdk_child_lead_authority import INSTANT


def registry_fixture(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root,proposal=proposed(tmp_path,monkeypatch)
    registry=runtime.RootTaskRegistry(root_authority=owner._root_authority,root_selection=root,source_environment={})
    child=runtime.ChildLeadAuthority(root_authority=registry,root_selection=root,child_id=assignment.child_id,
        selections=selections,closure_data=owner._closure_data,terminal_instant=INSTANT,repository_root=tmp_path)
    candidate=runtime.prepare_codex_request(replace(requests["task-one"],prompt="Explicit Root follow-up.",
        artifact_id="registered-task",external_dispatch_id="temporary-dispatch",external_evidence_run_id="temporary-evidence"))
    return registry,child,assignment,requests,selections,root,proposal,candidate


def admit(values,**changes):
    registry,owner,assignment,requests,selections,root,proposal,candidate=values
    kwargs=dict(authority=owner,proposal_id=proposal["proposal_id"],request=candidate,
        selection=selections["task-one"],artifact="registered.json",started_at=INSTANT)
    return registry.admit(**{**kwargs,**changes})


def test_registered_snapshot_restores_without_task_dictionary_and_hides_private_payload(tmp_path,monkeypatch):
    values=registry_fixture(tmp_path,monkeypatch)
    registry,owner,assignment,requests,selections,root,proposal,candidate=values
    outcome=admit(values);key=outcome["request_id"]
    assert key not in requests
    original=registry.resolve(key)
    assert original.prompt==candidate.prompt
    assert "registration" not in outcome["admission"]
    assert "registration" not in owner.proposal_results(assignment)[proposal["proposal_id"]]["admission"]
    fresh=runtime.RootTaskRegistry(root_authority=registry._root_authority,root_selection=root,source_environment={})
    child=runtime.ChildLeadAuthority(root_authority=fresh,root_selection=root,child_id=assignment.child_id,
        selections=selections,closure_data=owner._closure_data,terminal_instant=INSTANT,repository_root=tmp_path)
    restored=fresh.restore(child)
    assert restored["unavailable"]=={}
    assert fresh.resolve(key)==original
    assert restored["selections"]=={key:selections["task-one"]}
    child=runtime.ChildLeadAuthority(root_authority=fresh,root_selection=root,child_id=assignment.child_id,
        selections={**selections,**restored["selections"]},closure_data=owner._closure_data,
        terminal_instant=INSTANT,repository_root=tmp_path)
    runtime.claim_launch(child.resolve(key),restored["selections"][key],authority=child.assert_current,started_at=INSTANT)
    with pytest.raises(ValueError):
        runtime.claim_launch(child.resolve(key),restored["selections"][key],authority=child.assert_current,started_at=INSTANT)


@pytest.mark.parametrize("change",[{"required":False},{"request_prompt":"Changed explicit decision."}])
def test_committed_identity_does_not_accept_changed_root_decision(tmp_path,monkeypatch,change):
    values=registry_fixture(tmp_path,monkeypatch);admit(values)
    if "request_prompt" in change:
        change={"request":runtime.prepare_codex_request(replace(values[-1],prompt=change["request_prompt"]))}
    with pytest.raises(ValueError,match="conflict"):admit(values,**change)

def test_private_snapshot_uses_credential_detector_without_path_echo_ban(monkeypatch):
    from types import SimpleNamespace
    from provider_prompt import ProviderOutputContext
    secret="fixture-"+__import__("uuid").uuid4().hex
    monkeypatch.setattr(runtime,"prepare_environment",
        lambda selection,environment:({},ProviderOutputContext((secret.encode(),))))
    registry=runtime.RootTaskRegistry(root_authority=object(),root_selection=object(),source_environment={})
    selection=SimpleNamespace(to_dict=lambda:{"config_dir":"D:/authorized/source/config"})
    request=SimpleNamespace(to_dict=lambda:{"prompt":"Read D:/authorized/source/project"})
    snapshot=registry._scan(request,selection)
    assert snapshot["request"]["prompt"]=="Read D:/authorized/source/project"
    request=SimpleNamespace(to_dict=lambda:{"prompt":secret})
    with pytest.raises(ValueError,match="CREDENTIAL_ECHO"):registry._scan(request,selection)
