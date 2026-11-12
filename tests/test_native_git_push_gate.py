"""Native Git input and captured-result receiving; all histories are synthetic."""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import io
import importlib.util
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import time
from types import SimpleNamespace
from unittest import mock

import pytest

from test_git_push_gate_hook import CANONICAL_HOOK, _load_gate_module, range_receipt_v3


def module():
    return _load_gate_module(CANONICAL_HOOK, "native_git_gate_test")


def observation(object_format="sha1"):
    directory = {"pathEncoding": "posix-bytes", "pathBase64": "L3JlcG8=", "device": "1", "inode": "2"}
    return {"status": "captured", "repository": {
        "kind": "native-worktree-v1", "objectFormat": object_format,
        "commonGit": directory, "worktreeGit": directory, "worktreeRoot": directory,
    }, "diagnostic": "none"}


def selected(owner, *, object_format="sha1", wire=None, endpoint="https://example.invalid/project.git"):
    length = 40 if object_format == "sha1" else 64
    if wire is None:
        wire = b"refs/tags/example " + b"a" * length + b" refs/tags/example " + b"0" * length + b"\n"
    native = owner.NativePushInput("origin", endpoint, wire)
    request, binding = owner._native_push_selection(native, observation(object_format), owner._native_canonical_bytes)
    return native, request, binding


def receipt(binding, *, objects=1, updates=1):
    content = objects > 0
    return {
        "kind": "publication-safety-native", "version": 4, "status": "clean",
        "coverageKind": "objects", "objectFormat": binding.object_format,
        "endpointIdentity": binding.endpoint_identity, "inputSha256": binding.input_sha256,
        "updateSetSha256": "2" * 64, "selectionSha256": binding.selection_sha256,
        "repositoryObservationSha256": binding.repository_observation_sha256,
        "updates": updates, "commits": 0, "commitSetSha256": "b" * 64,
        "objects": objects, "objectSetSha256": "c" * 64, "coverageSha256": "d" * 64,
        "tags": int(content), "blobs": 0, "blobSetSha256": "e" * 64, "blobBytes": 0,
        "text": 0, "binary": 0, "subjects": int(content), "subjectSetSha256": "f" * 64,
        "paths": 0, "pathSetSha256": "1" * 64, "review": None,
    }


def pending_result(owner, binding, output, *, captured_review=None):
    """Synthetic supervisor evidence for exercising the existing one-use owner."""
    interpreter = owner._interpreter_identity()
    root = owner.PathComponentIdentity(".", "directory", (1,))
    closure = owner.CanonicalSourceClosure(
        owner.SOURCE_LAYOUTS[0], root, (root,), (), "a" * 64, (2,), "b" * 64, interpreter,
        owner.RootLocatorIdentity("gate.py", ".", "directory", (1,), None, ".", (1,), "gate.py", (2,)),
    )
    pending = owner.PendingScanInvocation("invocation", "attempt", binding, closure, interpreter, ("python", "-I"), object(), captured_review)
    supervisor = owner.ChildSupervisor(SimpleNamespace(pid=41), attempt_seconds=0.01)
    tick = time.monotonic()
    streams = tuple(owner.GateTransportObservation(name, "owned", True, None, tick) for name in ("stdin", "stdout", "stderr"))
    certificate = owner.GateSettlementCertificate(supervisor.supervisor_id, 41, 0, streams, (), (), 1, tick + 1e-6)
    settlement = owner.GateSettlement(owner.GateSettlementState.SETTLED, certificate, True)
    pending.child_identity, pending.supervisor, pending.settlement = 41, supervisor, settlement
    pending.state = owner.PendingState.SETTLED
    launched = owner.LaunchedScanInvocation(pending, 41, supervisor, "invocation", "attempt", binding, pending.exact_argv, pending.result_slot)
    execution = owner.TrustedExecutionRecord(pending, launched, pending.result_slot, True, 0, output, b"", settlement, closure, interpreter, "trusted")

    def consume(*, records=None, after=None, finalize_review=None):
        return pending.correlate_and_consume_once(
            launched, records or (execution,), closure, interpreter, after or binding, tick + 0.001,
            finalize_review=finalize_review,
        )

    return pending, execution, consume


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
def test_native_selection_preserves_wire_and_surrogate_endpoint(object_format):
    owner = module()
    endpoint = "transport://example.invalid/" + chr(0xDCFF)
    native, request, binding = selected(owner, object_format=object_format, endpoint=endpoint)
    assert request["endpoint"] == endpoint
    assert json.loads(owner._native_canonical_bytes(request))["endpoint"] == endpoint
    assert binding.input_sha256 == hashlib.sha256(native.wire).hexdigest()
    assert binding.selection_sha256 == hashlib.sha256(owner._native_canonical_bytes(request)).hexdigest()
    assert base64.b64decode(request["wireBase64"]) == native.wire
    assert "updates" not in request
    result = receipt(binding)
    parsed = owner.parse_publication_safety_observation(json.dumps(result) + "\n")
    assert parsed.kind == "valid-v4"
    owner._verify_native_receipt_binding(parsed.receipt, binding)


@pytest.mark.parametrize("wire", [
    b"refs/heads/main " + b"a" * 40 + b" refs/heads/main " + b"0" * 40,
    b"refs/heads/main " + b"a" * 39 + b" refs/heads/main " + b"0" * 40 + b"\n",
    b"refs/heads/main " + b"A" * 40 + b" refs/heads/main " + b"0" * 40 + b"\n",
    b"refs/heads/main\t" + b"a" * 40 + b" refs/heads/main " + b"0" * 40 + b"\n",
    (b"refs/heads/main " + b"a" * 40 + b" refs/heads/main " + b"0" * 40 + b"\n") * 2,
    b":/source with\tspaces\nand a newline " + b"a" * 40 + b" refs/heads/main " + b"0" * 40 + b"\n",
])
def test_gate_preserves_opaque_wire_for_the_single_captured_decoder(wire):
    owner = module()
    native, request, binding = selected(owner, wire=wire)
    assert base64.b64decode(request["wireBase64"], validate=True) == wire == native.wire
    assert binding.input_sha256 == hashlib.sha256(wire).hexdigest()
    assert not hasattr(binding, "updates")


@pytest.mark.parametrize("wire,updates", [
    (b"", 0),
    (b"(delete) " + b"0" * 40 + b" refs/tags/example " + b"a" * 40 + b"\n", 1),
    (None, 1),
])
def test_zero_object_coverage_does_not_claim_ref_effect_or_completion(wire, updates):
    owner = module()
    _, _, binding = selected(owner, wire=wire)
    empty_graph = receipt(binding, objects=0, updates=updates)
    parsed = owner.parse_publication_safety_observation(json.dumps(empty_graph))
    assert parsed.kind == "valid-v4"
    owner._verify_native_receipt_binding(parsed.receipt, binding)
    assert parsed.receipt.objects == 0
    assert parsed.receipt.updates == updates
    assert not hasattr(parsed.receipt, "effect_kind")
    assert owner.parse_publication_safety_observation(json.dumps({**empty_graph, "effectKind": "no-op"})).kind == "malformed"
    if updates == 0:
        assert owner.parse_publication_safety_observation(json.dumps(receipt(binding, objects=1, updates=0))).kind == "malformed"


def test_native_receipt_rejects_unbound_malformed_or_private_fields():
    owner = module()
    _, _, binding = selected(owner)
    valid = receipt(binding)
    for key, value in (("updates", True), ("coverageKind", "commits"), ("objects", 0), ("version", 3), ("review", {}), ("endpoint", "private")):
        candidate = {**valid, key: value}
        assert owner.parse_publication_safety_observation(json.dumps(candidate)).kind == "malformed"
    assert owner.parse_publication_safety_observation(json.dumps(valid) + "\n" + json.dumps(valid)).kind == "malformed"
    for key in ("endpointIdentity", "inputSha256", "selectionSha256", "repositoryObservationSha256"):
        candidate = {**valid, key: ("sha256:" if key == "endpointIdentity" else "") + "0" * 64}
        parsed = owner.parse_publication_safety_observation(json.dumps(candidate))
        with pytest.raises(owner.PrRouteDenied, match="PGG-NATIVE-RECEIPT-BINDING"):
            owner._verify_native_receipt_binding(parsed.receipt, binding)


def test_native_result_uses_same_pending_identity_and_cannot_be_replayed():
    owner = module()
    _, _, binding = selected(owner)
    pending, execution, consume = pending_result(owner, binding, json.dumps(receipt(binding)).encode())
    assert consume().parsed_outcome.kind == "valid-v4"
    assert pending.state is owner.PendingState.CONSUMED
    with pytest.raises(owner.PrRouteDenied, match="PGG-RECEIPT-USED"):
        consume()
    _, _, binding = selected(owner, endpoint="https://example.invalid/other.git")
    pending, execution, consume = pending_result(owner, binding, json.dumps(receipt(binding)).encode())
    with pytest.raises(owner.PrRouteDenied, match="PGG-SCAN-CORRELATION"):
        consume(records=(dataclasses.replace(execution, result_slot=object()),))


def test_old_range_receipt_never_gives_native_scan_credit():
    owner = module()
    _, _, binding = selected(owner)
    line = range_receipt_v3(files=1, remote="origin", dst="refs/heads/main", tip="a" * 40)
    _, _, consume = pending_result(owner, binding, line.encode())
    with pytest.raises(owner.PrRouteDenied, match="PGG-NATIVE-RECEIPT-VERSION"):
        consume()


def test_qualified_native_receipt_keeps_final_used_authority_gate():
    owner = module()
    _, _, binding = selected(owner)
    used = [["synthetic-decision", "a" * 64]]
    token = base64.b64encode(owner._native_canonical_bytes(used)).decode("ascii")
    qualified = {**receipt(binding), "status": "qualified", "tags": 0, "blobs": 1,
        "blobBytes": 10, "text": 1, "paths": 1,
        "review": {"snapshotId": "b" * 64, "usedDecisions": used, "usedToken": token, "applied": 1, "appliedSet": "c" * 64},
    }
    policy = SimpleNamespace(C=owner._native_canonical_bytes)
    payload = b"synthetic-review"
    captured = owner.CapturedReviewPayload(
        owner.CapturedReviewModules(policy, object(), ()), {}, "b" * 64,
        observation(), observation()["repository"], True, payload, hashlib.sha256(payload).hexdigest(),
    )
    _, _, consume = pending_result(owner, binding, json.dumps(qualified).encode(), captured_review=captured)
    with pytest.raises(owner.PrRouteDenied, match="PGG-SCAN-CORRELATION"):
        consume()
    finalization = {"inputSnapshotId": "b" * 64, "usedList": used, "currentSnapshotId": "d" * 64,
        "repositorySha256": "e" * 64, "status": "valid", "reason": "none", "resourcesSettled": True}
    _, _, consume = pending_result(owner, binding, json.dumps(qualified).encode(), captured_review=captured)
    finalize = mock.Mock(return_value=(finalization, used))
    assert consume(finalize_review=finalize).parsed_outcome.kind == "qualified-v4"
    finalize.assert_called_once()
    malformed = {**qualified, "review": {**qualified["review"], "usedDecisions": [], "usedToken": "W10="}}
    assert owner.parse_publication_safety_observation(json.dumps(malformed)).kind == "malformed"


def test_native_main_redacts_failure_and_does_not_invent_callback_success():
    owner = module()
    stdout, stderr = io.StringIO(), io.StringIO()
    secret = "https://user:password@example.invalid/private"
    with mock.patch.object(owner, "_normalize_repository_workdir", return_value="/repo"), \
         mock.patch.object(owner, "_resolve_executable", return_value="git"), \
         mock.patch.object(owner, "_prove_repository_root", return_value="/repo"), \
         mock.patch.object(owner, "_run_authoritative_scan", side_effect=ValueError(secret)), \
         mock.patch.object(owner.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b""))), \
         mock.patch.object(owner.sys, "stdout", stdout), mock.patch.object(owner.sys, "stderr", stderr):
        assert owner._native_pre_push_main(["origin", secret]) != 0
    assert stdout.getvalue() == ""
    assert secret not in stderr.getvalue()
    assert "PGG-SCAN-EXECUTION" in stderr.getvalue()


@pytest.mark.parametrize("userinfo", ["synthetic-user", "synthetic-user:PUBLICATION_LITERAL_CANARY"])
def test_credential_bearing_literal_remote_is_refused_before_child_argv(userinfo):
    owner = module()
    remote = "https://" + userinfo + "@example.invalid/synthetic.git"
    output, errors = io.StringIO(), io.StringIO()
    with mock.patch.object(owner, "_normalize_repository_workdir", return_value="/repo"), \
         mock.patch.object(owner, "_resolve_executable", return_value="git"), \
         mock.patch.object(owner, "_prove_repository_root", return_value="/repo"), \
         mock.patch.object(owner, "_native_configuration_query") as query, \
         mock.patch.object(owner, "_run_authoritative_scan") as scan, \
         mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b""))), \
         mock.patch.object(sys, "stdout", output), mock.patch.object(sys, "stderr", errors):
        assert owner._native_pre_push_main([remote, remote]) == 2
    query.assert_not_called()
    scan.assert_not_called()
    assert output.getvalue() == ""
    assert "PGG-TARGET-IDENTITY" in errors.getvalue()
    assert userinfo not in output.getvalue() + errors.getvalue()


@pytest.fixture
def native_repository():
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    with mock.patch.dict(os.environ, environment, clear=True), tempfile.TemporaryDirectory(prefix="native-gate-config-") as directory:
        root = pathlib.Path(directory)
        subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=20)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "--allow-empty", "-qm", "Synthetic native gate input"], check=True, timeout=20)
        yield root


def native_preflight(owner, root, *, trailing=(), push_options=(), native=True, refspecs=None):
    options = owner.native_git_config_arguments() if native else ()
    oid = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, timeout=20).strip()
    mappings = (oid + ":refs/heads/main",) if refspecs is None else tuple(refspecs)
    command = shlex.join(("git", "-C", str(root), *options, *trailing, "push", *push_options, "origin", *mappings))
    return owner._a3_preflight.build_preflight({"tool_name": "Bash", "cwd": str(root), "tool_input": {"command": command}})


@pytest.mark.skipif(os.name != "nt", reason="This receiving exercises the Windows creator-owned Job")
@pytest.mark.parametrize("scenario", ["clean", "commit-secret", "source-drift", "head-drift", "endpoint-drift", "fake-v4", "scanner-failure"])
def test_v3_precedes_native_transfer_and_rechecks_target(native_repository, monkeypatch, scenario):
    owner = module()
    home = native_repository / "synthetic-user"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    remote = native_repository / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, timeout=20)
    subprocess.run(["git", "-C", str(native_repository), "remote", "add", "origin", str(remote)], check=True, timeout=20)
    original = subprocess.check_output(["git", "-C", str(native_repository), "rev-parse", "HEAD"], text=True, timeout=20).strip()
    (native_repository / "payload.txt").write_text(("AK" + "IA" + "A" * 16) if scenario == "commit-secret" else "synthetic safe content", encoding="utf-8")
    subprocess.run(["git", "-C", str(native_repository), "add", "payload.txt"], check=True, timeout=20)
    subprocess.run(["git", "-C", str(native_repository), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "search:colon"], check=True, timeout=20)
    subprocess.run(["git", "-C", str(native_repository), "update-ref", "refs/heads/selected", "HEAD"], check=True, timeout=20)
    source = "refs/heads/selected" if scenario == "source-drift" else ":/search:colon"
    preflight = native_preflight(owner, native_repository, refspecs=(source + ":refs/heads/main",))
    seen = []
    scan = owner._run_authoritative_scan

    def run_then_drift(*arguments, **keywords):
        if scenario == "scanner-failure":
            raise owner.PrRouteDenied("PGG-SCAN-EXECUTION")
        evidence = scan(*arguments, **keywords)
        seen.append(evidence)
        if scenario == "source-drift":
            subprocess.run(["git", "-C", str(native_repository), "update-ref", "refs/heads/selected", original], check=True, timeout=20)
        elif scenario == "head-drift":
            subprocess.run(["git", "-C", str(native_repository), "update-ref", "HEAD", original], check=True, timeout=20)
        elif scenario == "endpoint-drift":
            subprocess.run(["git", "-C", str(native_repository), "remote", "set-url", "--push", "origin", str(native_repository / "different.git")], check=True, timeout=20)
        if scenario == "fake-v4":
            return evidence._replace(parsed_outcome=owner.PublicationSafetyObservation("valid-v4", None))
        return evidence

    selected_oid = subprocess.check_output(["git", "-C", str(native_repository), "rev-parse", source], timeout=20).strip()
    wire = os.fsencode(source) + b" " + selected_oid + b" refs/heads/main " + b"0" * 40 + b"\n"
    monkeypatch.chdir(native_repository)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(wire)))
    output, errors = io.StringIO(), io.StringIO()
    with mock.patch.object(owner, "_run_authoritative_scan", side_effect=run_then_drift), \
         mock.patch.object(owner, "evaluate_heavy", wraps=owner.evaluate_heavy), \
         mock.patch.object(sys, "stdout", output), mock.patch.object(sys, "stderr", errors):
        assert owner.evaluate_heavy(preflight)
        code = owner._native_pre_push_main(["origin", str(remote)])
        if scenario == "clean":
            assert code == 0, errors.getvalue()
            assert [item.parsed_outcome.kind for item in seen] == ["valid-v3", "valid-v4"]
            assert isinstance(seen[0].parsed_outcome.receipt, owner.RangeReceiptV3)
        else:
            assert code == 2
            expected = {"commit-secret": "PGG-SCAN-FINDING", "fake-v4": "PGG-RANGE-RECEIPT-VERSION", "scanner-failure": "PGG-SCAN-EXECUTION"}.get(scenario, "PGG-TARGET-CURRENTNESS")
            assert expected in errors.getvalue()
            assert output.getvalue() == ""
            assert len(seen) == (0 if scenario in {"commit-secret", "scanner-failure"} else 1)
    refs = subprocess.check_output(["git", "--git-dir", str(remote), "for-each-ref", "--format=%(refname)"], timeout=20)
    assert refs == b""


def test_native_preflight_leaves_safe_config_for_the_actual_callback(native_repository):
    owner = module()
    preflight = native_preflight(owner, native_repository, trailing=("-c", "color.ui=false"))
    with mock.patch.object(owner, "_run_authoritative_scan", side_effect=AssertionError("unqualified configuration")):
        assert owner.evaluate_heavy(preflight)


def test_actual_native_configuration_qualified_without_scanner_or_user_hook_changes(native_repository):
    owner = module()
    user_hook = native_repository / ".git" / "hooks" / "pre-push"
    user_hook.write_bytes(b"#!/bin/sh\nexit 0\n")
    before = user_hook.read_bytes(), user_hook.stat().st_ino
    preflight = native_preflight(owner, native_repository)
    with mock.patch.object(owner, "_run_authoritative_scan", side_effect=AssertionError("qualification must not scan")):
        assert owner._qualify_native_push_command(preflight)
    assert (user_hook.read_bytes(), user_hook.stat().st_ino) == before
    saved = subprocess.run(["git", "-C", str(native_repository), "config", "--get-regexp", "^hook\\."], capture_output=True, timeout=20)
    assert saved.returncode == 1 and saved.stdout == b""


@pytest.mark.parametrize("trailing,push_options,expected", [
    (("-c", "hook.orchestrarium-publication.command=printf wrong"), (), "PGG-NATIVE-COLLISION"),
    (("-c", "hook.orchestrarium-publication.enabled=false"), (), "PGG-NATIVE-DISABLED"),
    (("-c", "hook.pre-push.enabled=false"), (), "PGG-NATIVE-DISABLED"),
    (("-c", "hook.orchestrarium-publication.event="), (), "PGG-NATIVE-ENTRY-REQUIRED"),
    ((), ("--no-verify",), "PGG-NATIVE-DISABLED"),
    ((), ("--recurse-submodules=on-demand",), "PGG-NATIVE-RECURSION-UNQUALIFIED"),
    ((), ("--recurse-submodules=only",), "PGG-NATIVE-RECURSION-UNQUALIFIED"),
])
def test_unsafe_effective_entry_stops_before_push(native_repository, trailing, push_options, expected):
    owner = module()
    preflight = native_preflight(owner, native_repository, trailing=trailing, push_options=push_options)
    with pytest.raises(owner.PrRouteDenied, match=expected):
        owner.evaluate_heavy(preflight)
    assert subprocess.run(["git", "-C", str(native_repository), "show-ref", "--verify", "--quiet", "refs/remotes/origin/main"], timeout=20).returncode == 1


def test_native_option_polarity_and_unrelated_config_keep_git_meaning(native_repository):
    owner = module()
    subprocess.run(["git", "-C", str(native_repository), "config", "push.recurseSubmodules", "on-demand"], check=True, timeout=20)
    preflight = native_preflight(owner, native_repository, trailing=("-c", "color.ui=false"), push_options=("--no-verify", "--verify", "--no-recurse-submodules"))
    assert owner._qualify_native_push_command(preflight)
    preflight = native_preflight(owner, native_repository, push_options=("--recurse-submodules=check",))
    assert owner._qualify_native_push_command(preflight)


def test_effective_owned_parallel_override_does_not_restrict_user_jobs(native_repository):
    owner = module()
    settings = {
        "hook.pre-push.jobs": "4",
        "hook.synthetic-user.parallel": "true",
        "hook.orchestrarium-publication.parallel": "true",
    }
    for key, value in settings.items():
        subprocess.run(["git", "-C", str(native_repository), "config", key, value], check=True, timeout=20)
    # The selected command's explicit false wins over an earlier stored true;
    # unrelated user hook concurrency is preserved, rather than prohibited.
    assert owner._qualify_native_push_command(native_preflight(owner, native_repository))
    overridden = native_preflight(owner, native_repository, trailing=("-c", "hook.orchestrarium-publication.parallel=true"))
    with pytest.raises(owner.PrRouteDenied, match="PGG-NATIVE-CONFIGURATION"):
        owner.evaluate_heavy(overridden)
    for key, expected in settings.items():
        actual = subprocess.check_output(["git", "-C", str(native_repository), "config", "--get", key], timeout=20)
        assert actual == expected.encode() + b"\n"


def test_unregistered_agent_push_cannot_claim_actual_set_scan(native_repository):
    owner = module()
    with pytest.raises(owner.PrRouteDenied, match="PGG-NATIVE-ENTRY-REQUIRED"):
        owner.evaluate_heavy(native_preflight(owner, native_repository, native=False))


def test_inherited_own_namespace_disable_is_preserved(native_repository):
    owner = module()
    subprocess.run(["git", "-C", str(native_repository), "config", "hook.orchestrarium-publication.enabled", "false"], check=True, timeout=20)
    with pytest.raises(owner.PrRouteDenied, match="PGG-NATIVE-DISABLED"):
        owner.evaluate_heavy(native_preflight(owner, native_repository))
    result = subprocess.run(["git", "-C", str(native_repository), "config", "--get", "hook.orchestrarium-publication.enabled"], capture_output=True, timeout=20)
    assert result.returncode == 0 and result.stdout == b"false\n"


def test_explicit_unpeeled_tag_oid_multiple_mappings_and_deletion_qualify(native_repository):
    owner = module()
    subprocess.run(["git", "-C", str(native_repository), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "tag", "-a", "example", "-m", "Synthetic annotation"], check=True, timeout=20)
    tag = subprocess.check_output(["git", "-C", str(native_repository), "rev-parse", "refs/tags/example"], text=True, timeout=20).strip()
    commit = subprocess.check_output(["git", "-C", str(native_repository), "rev-parse", "HEAD"], text=True, timeout=20).strip()
    assert tag != commit
    preflight = native_preflight(owner, native_repository, trailing=("-c", "push.followTags=true"), refspecs=("+" + commit + ":refs/heads/main", tag + ":refs/tags/example", ":refs/heads/retired"))
    assert owner._qualify_native_push_command(preflight)


@pytest.mark.parametrize("refspecs,push_options,expected", [
    ((":/text with\na newline:refs/heads/main",), (), "PGG-NATIVE-REFSPEC-LF"),
    ((), ("--mirror",), "PGG-NATIVE-REFSPEC-UNQUALIFIED"),
])
def test_unresolved_expansion_is_explicitly_held_without_rewriting(native_repository, refspecs, push_options, expected):
    owner = module()
    preflight = native_preflight(owner, native_repository, refspecs=refspecs, push_options=push_options)
    original = preflight.command
    with pytest.raises(owner.PrRouteDenied, match=expected):
        owner.evaluate_heavy(preflight)
    assert preflight.command == original
    if expected == "PGG-NATIVE-REFSPEC-LF":
        envelope = {"tool_name": "Bash", "cwd": str(native_repository), "tool_input": {"command": original}}
        runner = CANONICAL_HOOK.with_name("check-git-push-gate-runner.py")
        result = subprocess.run([sys.executable, "-B", str(runner)], input=json.dumps(envelope).encode(), capture_output=True, cwd=native_repository, timeout=30)
        body = json.loads(result.stdout)["hookSpecificOutput"]
        assert result.returncode == 0 and body["permissionDecision"] == "deny"
        assert expected in body["permissionDecisionReason"]
        assert "line feed" in body["permissionDecisionReason"]


def synthetic_review_payload(owner):
    snapshot_id = "c" * 64
    policy_source = (
        "POLICY_MODULE_CONTRACT_ID='orchestrarium.publication-review-policy.module.v1'\n"
        "POLICY_MODULE_KEY='_orchestrarium_publication_review_policy_v1'\n"
        "POLICY_INJECTION_KEY='__injected_review_policy_module__'\n"
        "def H(domain,value): return '" + snapshot_id + "'\n"
    ).encode()
    scanner_source = (
        "import base64,sys\n"
        "if '--native-push' in sys.argv:\n"
        " assert __injected_native_push__['inputSha256']\n"
        " assert base64.b64decode(__injected_native_push__['wireBase64']) == b'opaque\\nbytes'\n"
        " print('native-transport-received')\n"
        "else:\n"
        " assert '__injected_native_push__' not in globals()\n"
        " print('legacy-transport-received')\n"
    ).encode()
    bodies = {
        "gate": b"gate", "hook_common": b"", "classifier": b"def find_machine_paths(value): return []\n",
        "posix_helper": b"", "windows_job": b"", "scanner": scanner_source,
        "publication_review_policy": policy_source, "linked_runtime_subroots": b"",
    }
    interpreter = owner._interpreter_identity()
    root = owner.PathComponentIdentity(".", "directory", (1,))
    nodes = tuple(owner.SourceNode(role, role + ".py", (1,), 1, len(bodies[role]), hashlib.sha256(bodies[role]).hexdigest(), bodies[role]) for role in owner.SOURCE_ROLE_ORDER)
    closure = owner.CanonicalSourceClosure(
        owner.SOURCE_LAYOUTS[0], root, (root,), nodes, "a" * 64, (1,), "b" * 64, interpreter,
        owner.RootLocatorIdentity("gate.py", ".", "directory", (1,), None, ".", (1,), "gate.py", (1,)),
    )
    review = {
        "schemaVersion": 1, "repositoryObservation": observation(),
        "snapshot": {"schemaVersion": 1, "status": "absent", "origin": None, "rawBase64": None, "rawSha256": None, "diagnostic": "not-found"},
        "snapshotId": snapshot_id,
    }
    return closure, review


def test_native_bootstrap_injects_only_captured_opaque_wire_without_reading_scanner_source():
    owner = module()
    closure, review = synthetic_review_payload(owner)
    _, request, _ = selected(owner, wire=b"opaque\nbytes", endpoint="native-endpoint-" + chr(0xDCFF))
    payload = owner._closure_payload(closure, review, owner._native_canonical_bytes, native_push=request)
    for arguments, expected in ((("--native-push",), 0), (("--range", "origin", "main"), 1)):
        result = subprocess.run([sys.executable, "-B", "-I", "-c", owner._SCAN_BOOTSTRAP, "--gate-git-executable", "git", *arguments], input=payload, capture_output=True, timeout=20)
        assert (result.returncode == 0) == (expected == 0)
        if expected == 0:
            assert result.stdout.splitlines() == [b"native-transport-received"]
    original = owner._closure_payload(closure, review, owner._native_canonical_bytes)
    expected_payload = {
        "payloadVersion": 1,
        "sources": {node.role: base64.b64encode(node.source).decode("ascii") for node in closure.nodes if node.role != "gate"},
        "review": review,
    }
    assert original == owner._native_canonical_bytes(expected_payload)
    result = subprocess.run([sys.executable, "-B", "-I", "-c", owner._SCAN_BOOTSTRAP, "--gate-git-executable", "git", "--range", "origin", "main"], input=original, capture_output=True, timeout=20)
    assert result.returncode == 0 and result.stdout.splitlines() == [b"legacy-transport-received"]


def test_native_mode_captures_repository_even_without_exception_records():
    owner = module()
    closure, review = synthetic_review_payload(owner)
    policy = types.ModuleType("_orchestrarium_publication_review_policy_v1")
    policy.POLICY_MODULE_CONTRACT_ID = "orchestrarium.publication-review-policy.module.v1"

    @dataclasses.dataclass
    class PolicyRead:
        snapshot: dict
        snapshot_id: str
        usable_records: tuple
        issues: tuple

    policy.PolicyReadV1 = PolicyRead
    policy.resolve_trusted_origin = lambda: None
    policy.read_policy_snapshot = lambda origin, root: PolicyRead(review["snapshot"], review["snapshotId"], (), ())
    policy.H = lambda domain, value: review["snapshotId"]
    policy.origin_is_outside_repository = lambda snapshot, repository: False
    policy.C = owner._native_canonical_bytes
    modules = owner.CapturedReviewModules(policy, object(), ())
    with mock.patch.dict(sys.modules, {policy.__name__: policy}), \
         mock.patch.object(owner, "_capture_repository_observation", return_value=observation()) as capture, \
         mock.patch.object(owner, "_closure_payload", return_value=b"synthetic-payload"):
        legacy = owner._capture_review_payload(modules, closure, pathlib.Path("/repo"), "git")
        assert legacy.repository_observation["status"] == "not-requested"
        capture.assert_not_called()
        native = owner._capture_review_payload(modules, closure, pathlib.Path("/repo"), "git", require_repository=True)
        assert native.repository_observation == observation()
        capture.assert_called_once()


def _run_owned_git_job(argv, cwd):
    """Exercise the real transfer inside the existing creator-owned Job."""
    helper_path = CANONICAL_HOOK.parents[2] / "process_supervision" / "windows_job.py"
    specification = importlib.util.spec_from_file_location("_native_gate_test_job", helper_path)
    helper = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = helper
    specification.loader.exec_module(helper)
    process = None
    streams = []
    workers = []
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    failures = []
    closure = None
    try:
        process = helper.WindowsJobOwnerV1.launch(
            executable=argv[0], argv=argv, cwd=str(cwd), environment=dict(os.environ),
            stdin="null", stdout="pipe", stderr="pipe",
        )

        def drain(stream, key):
            try:
                while chunk := stream.read(8192):
                    outputs[key].extend(chunk)
            except BaseException as error:
                failures.append(error)

        for key, take in (("stdout", process.take_stdout_fd), ("stderr", process.take_stderr_fd)):
            descriptor = take()
            assert descriptor is not None
            stream = os.fdopen(descriptor, "rb", buffering=0)
            streams.append(stream)
            worker = threading.Thread(target=drain, args=(stream, key))
            worker.start()
            workers.append(worker)
        returncode = process.wait(time.monotonic() + 60)
        closure = process.settle(time.monotonic() + 5)
        for worker in workers:
            worker.join(timeout=5)
        assert closure.complete and not any(worker.is_alive() for worker in workers)
        assert not failures
        return returncode, bytes(outputs["stdout"]), bytes(outputs["stderr"]), closure
    finally:
        if process is not None and closure is None:
            closure = process.close()
        for worker in workers:
            worker.join(timeout=5)
        for stream in streams:
            stream.close()
        sys.modules.pop(specification.name, None)


@pytest.mark.skipif(os.name != "nt", reason="This target receiving verifies the Windows creator-owned Job")
@pytest.mark.parametrize("source_expression,secret_annotation", [
    ("HEAD", False), (":/Synthetic native gate input", False),
    (":/tab\tword", False), (":/carriage\rreturn", False),
    (":/unicode α", False), ("HEAD", True),
])
def test_actual_git_callback_captured_v4_and_annotation_refusal(native_repository, source_expression, secret_annotation, monkeypatch):
    owner = module()
    synthetic_home = native_repository / "synthetic-user"
    synthetic_home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(synthetic_home))
    scanner = CANONICAL_HOOK.with_name("check-publication-safety.py")
    scanner_before = hashlib.sha256(scanner.read_bytes()).hexdigest()
    remote = native_repository / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, timeout=20)
    subprocess.run(["git", "-C", str(native_repository), "remote", "add", "origin", str(remote)], check=True, timeout=20)
    subprocess.run(["git", "-C", str(native_repository), "config", "push.followTags", "true"], check=True, timeout=20)
    marker = ("AK" + "IA") + "A" * 16
    annotation = marker if secret_annotation else "Safe synthetic tag annotation"
    subprocess.run(["git", "-C", str(native_repository), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "tag", "-a", "extra", "-m", annotation], check=True, timeout=20)
    previous = subprocess.check_output(["git", "-C", str(native_repository), "rev-parse", "HEAD"], text=True, timeout=20).strip()
    tree = subprocess.check_output(["git", "-C", str(native_repository), "rev-parse", "HEAD^{tree}"], text=True, timeout=20).strip()
    commit = subprocess.run(["git", "-C", str(native_repository), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit-tree", tree], input="Synthetic native gate input\n\ntab\tword\ncarriage\rreturn\nunicode α\n".encode("utf-8"), capture_output=True, check=True, timeout=20).stdout.decode("ascii").strip()
    subprocess.run(["git", "-C", str(native_repository), "update-ref", "HEAD", commit], check=True, timeout=20)
    # The annotated tag must point to the selected commit for --follow-tags.
    subprocess.run(["git", "-C", str(native_repository), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "tag", "-f", "-a", "extra", "-m", annotation], check=True, timeout=20, capture_output=True)
    source = commit
    tag = subprocess.check_output(["git", "-C", str(native_repository), "rev-parse", "refs/tags/extra"], text=True, timeout=20).strip()
    log = native_repository / "user-hook.json"
    logger = native_repository / "user-hook.py"
    logger.write_text(
        "import base64,json,pathlib,sys\n"
        "pathlib.Path(sys.argv[1]).write_text(json.dumps({'arguments':sys.argv[2:],'wireBase64':base64.b64encode(sys.stdin.buffer.read()).decode('ascii')}))\n",
        encoding="utf-8",
    )
    user_hook = native_repository / ".git" / "hooks" / "pre-push"
    user_hook.write_text("#!/bin/sh\nexec " + shlex.join((sys.executable, "-B", str(logger), str(log))) + ' "$@"\n', encoding="utf-8")
    user_hook.chmod(0o700)
    hook_before = user_hook.read_bytes(), user_hook.stat().st_dev, user_hook.stat().st_ino
    executable = str(pathlib.Path(shutil.which("git")).resolve(strict=True))
    subprocess.run(["git", "-C", str(native_repository), "config", "protocol.allow", "never"], check=True, timeout=20)
    subprocess.run(["git", "-C", str(native_repository), "config", "protocol.file.allow", "always"], check=True, timeout=20)
    argv = (executable, "-C", str(native_repository),
        *owner.native_git_config_arguments(), "-c", "color.ui=false", "push", "--porcelain", "origin", source_expression + ":refs/heads/main")
    if source_expression == "HEAD":
        subprocess.run(["git", "-C", str(native_repository), "config", "--add", "remote.origin.push", ":/unused\ndefault:refs/heads/unused"], check=True, timeout=20)
    def public_preflight(arguments):
        envelope = {"tool_name": "Bash", "cwd": str(native_repository), "tool_input": {"command": shlex.join(arguments)}}
        runner = CANONICAL_HOOK.with_name("check-git-push-gate-runner.py")
        result = subprocess.run([sys.executable, "-B", str(runner)], input=json.dumps(envelope).encode(), capture_output=True, cwd=native_repository, timeout=30)
        assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")
    public_preflight(argv)
    returncode, stdout, stderr, closure = _run_owned_git_job(argv, native_repository)
    assert closure.complete
    assert (user_hook.read_bytes(), user_hook.stat().st_dev, user_hook.stat().st_ino) == hook_before
    assert log.exists()
    native = json.loads(log.read_text())
    wire = base64.b64decode(native["wireBase64"])
    assert source_expression.encode("utf-8") in wire and source.encode() in wire and tag.encode() in wire
    assert marker.encode() not in stdout + stderr
    refs = subprocess.check_output(["git", "--git-dir", str(remote), "for-each-ref", "--format=%(refname) %(objectname)"], timeout=20)
    if secret_annotation:
        assert returncode != 0 and b"PGG-SCAN-FINDING" in stderr
        assert refs == b""
        assert b'"kind":"publication-safety-native"' not in stdout
    else:
        assert returncode == 0, (stdout + stderr).decode("utf-8", "replace")
        receipts = [json.loads(line) for line in stdout.splitlines() if line.startswith(b'{"')]
        assert len(receipts) == 1
        received = receipts[0]
        assert received["kind"] == "publication-safety-native" and received["version"] == 4
        assert received["status"] == "clean" and received["updates"] == 2 and received["tags"] == 1
        assert received["inputSha256"] == hashlib.sha256(wire).hexdigest()
        assert received["endpointIdentity"] == owner._native_endpoint_identity(native["arguments"][1])
        assert "effectKind" not in received
        assert ("refs/heads/main " + source).encode() in refs
        assert ("refs/tags/extra " + tag).encode() in refs
        if source_expression == "HEAD":
            forced = (*argv[:-1], "+" + previous + ":refs/heads/main")
            public_preflight(forced)
            forced_code, forced_out, forced_err, forced_closure = _run_owned_git_job(forced, native_repository)
            assert forced_closure.complete and forced_code == 0, (forced_out + forced_err).decode("utf-8", "replace")
            forced_refs = subprocess.check_output(["git", "--git-dir", str(remote), "for-each-ref", "--format=%(refname) %(objectname)"], timeout=20)
            assert ("refs/heads/main " + previous).encode() in forced_refs
            assert ("refs/tags/extra " + tag).encode() in forced_refs
            assert b"refs/heads/unused" not in forced_refs
    assert hashlib.sha256(scanner.read_bytes()).hexdigest() == scanner_before


@pytest.mark.skipif(os.name != "nt", reason="Uses the Windows creator-owned Job")
@pytest.mark.parametrize("custom_receiver,secret_second", [(False, False), (False, True), (True, False), (True, True)])
def test_actual_push_v3_union_covers_disjoint_roots_and_custom_receiver(native_repository, monkeypatch, custom_receiver, secret_second):
    owner = module()
    home = native_repository / "synthetic-user"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    def git(*args, raw=None):
        return subprocess.run(["git", "-C", str(native_repository), *args], input=raw,
                              capture_output=True, check=True, timeout=20).stdout.strip()
    nominal = native_repository / "nominal.git"
    actual = native_repository / "actual.git" if custom_receiver else nominal
    git("init", "--bare", "-q", str(nominal))
    git("remote", "add", "origin", str(nominal))
    marker = ("AK" + "IA" + "A" * 16).encode()
    blob = git("hash-object", "-w", "--stdin", raw=marker if secret_second else b"safe disjoint content\n")
    tree = git("mktree", raw=b"100644 blob " + blob + b"\tsecond.txt\n")
    second = git("-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
                 "commit-tree", tree.decode(), raw=b"disjoint synthetic root\n").decode()
    first = git("rev-parse", "HEAD").decode()
    mappings = (first + ":refs/heads/first", second + ":refs/heads/second")
    receiver = ()
    if custom_receiver:
        # The advertised repository owns both roots; the actual receiver owns
        # neither. Probing the advertised repository would hide the finding.
        git("push", "-q", "origin", *mappings)
        git("init", "--bare", "-q", str(actual))
        wrapper = native_repository / "receive.sh"
        wrapper.write_text("#!/bin/sh\nexec git-receive-pack " + shlex.quote(str(actual)) + "\n", encoding="utf-8")
        wrapper.chmod(0o700)
        receiver = ("--receive-pack=" + shlex.join(("sh", str(wrapper))),)
    argv = (shutil.which("git"), "-C", str(native_repository), *owner.native_git_config_arguments(),
            "-c", "color.ui=false", "push", *receiver, "origin", *mappings)
    preflight = owner._a3_preflight.build_preflight({"tool_name": "Bash", "cwd": str(native_repository),
        "tool_input": {"command": shlex.join(argv)}})
    assert owner.evaluate_heavy(preflight)
    code, stdout, stderr, settlement = _run_owned_git_job(argv, native_repository)
    assert settlement.complete
    assert marker not in stdout + stderr
    refs = subprocess.check_output(["git", "--git-dir", str(actual), "for-each-ref", "--format=%(refname)"], timeout=20)
    if secret_second:
        assert code != 0 and b"PGG-SCAN-FINDING" in stderr
        assert refs == b""
        assert b"receipt=v3" not in stdout
    else:
        assert code == 0, (stdout + stderr).decode("utf-8", "replace")
        v3 = [owner.parse_publication_safety_observation(line.decode()) for line in stdout.splitlines() if b"receipt=v3" in line]
        assert len(v3) == 1 and v3[0].kind == "valid-v3"
        assert v3[0].receipt.commits == 2
        assert v3[0].receipt.source == first and v3[0].receipt.tip == first
        assert v3[0].receipt.destination == "refs/heads/first"
        assert b"refs/heads/first" in refs and b"refs/heads/second" in refs


@pytest.mark.skipif(os.name != "nt", reason="Uses the Windows creator-owned Job")
def test_actual_tag_only_push_retains_independent_v4_annotation_detection(native_repository, monkeypatch):
    owner = module()
    home = native_repository / "synthetic-user"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    remote = native_repository / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True, timeout=20)
    subprocess.run(["git", "-C", str(native_repository), "remote", "add", "origin", str(remote)], check=True, timeout=20)
    marker = "AK" + "IA" + "A" * 16
    subprocess.run(["git", "-C", str(native_repository), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
                    "tag", "-a", "annotation", "-m", marker], check=True, timeout=20)
    argv = (shutil.which("git"), "-C", str(native_repository), *owner.native_git_config_arguments(),
            "push", "origin", "refs/tags/annotation:refs/tags/annotation")
    code, stdout, stderr, settlement = _run_owned_git_job(argv, native_repository)
    assert settlement.complete
    assert code != 0 and b"PGG-SCAN-FINDING" in stderr
    assert marker.encode() not in stdout + stderr
    assert subprocess.check_output(["git", "--git-dir", str(remote), "for-each-ref"], timeout=20) == b""


@pytest.mark.skipif(os.name != "nt", reason="Uses captured Windows scanner children")
@pytest.mark.parametrize("scenario", ["v3-only-active", "v3-only-revoked", "distinct-active", "distinct-revoked", "overlap", "conflict", "origin-return", "origin-content"])
def test_v3_used_authority_is_received_again_after_v4_excludes_its_subject(native_repository, monkeypatch, request, scenario):
    slot_names = ("_orchestrarium_publication_review_policy_v1", "_orchestrarium_linked_runtime_subroots_v1")
    absent = object()
    previous_slots = {name: sys.modules.get(name, absent) for name in slot_names}
    def restore_fixture_modules():
        for name, previous in previous_slots.items():
            if previous is absent:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    request.addfinalizer(restore_fixture_modules)
    from test_publication_native_effects import load_scanner
    from tests.test_publication_review_policy import _record
    owner = module()
    scanner = load_scanner()
    policy = scanner._load_review_policy_module()
    temporary_home = tempfile.TemporaryDirectory(prefix="native-reviewed-user-")
    request.addfinalizer(temporary_home.cleanup)
    home = pathlib.Path(temporary_home.name)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(native_repository)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(native_repository), *args], timeout=20).strip()
    old = git("rev-parse", "HEAD").decode()
    raw = ("TOKEN=" + "aB9" * 16 + "\n").encode()
    path = b"reviewed.txt"
    (native_repository / path.decode()).write_bytes(raw)
    git("add", path.decode())
    git("-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "reviewed synthetic subject")
    commit = git("rev-parse", "HEAD").decode()
    blob = git("rev-parse", "HEAD:reviewed.txt").decode()
    remote = native_repository / "remote.git"
    git("init", "--bare", "-q", str(remote))
    git("remote", "add", "origin", str(remote))
    observed, _ = scanner._capture_review_repository(policy, native_repository, time.monotonic() + 30)
    candidate = scanner.analyze_review_candidates(raw, path, subject_kind="history-blob", policy_module=policy)["candidates"][0]
    record = _record()
    record.pop("recordSha256")
    record["id"] = "DEC-A"
    record["repository"] = observed["repository"]
    record["modes"] = ["range-blob-text"]
    record["rangeScope"] = {"kind": "exact-commits", "commits": [commit]}
    occurrence = record["occurrences"][0]
    occurrence.update(rawPathBase64=base64.b64encode(path).decode(), blobOid=blob,
        blobSha256=hashlib.sha256(raw).hexdigest(), blobByteCount=len(raw), gitMode="100644",
        detector=candidate["detector"], candidate=candidate["candidate"],
        reviewRegion=scanner._byte_region(raw, 0, len(raw)),
        contexts=[{"id": "fixture", "region": scanner._byte_region(raw, 0, len(raw))}])
    origin = home / ".agents" / "publication"
    origin.mkdir(parents=True)
    policy_file = origin / "reviewed-exceptions.json"
    record_a = policy.seal_record(record)
    record_b = policy.seal_record({**record, "id": "DEC-B"})
    changed_a = policy.seal_record({**record, "revision": 2,
        "previousRecordSha256": record_a["recordSha256"], "reason": "revised synthetic grant"})
    policy_file.write_bytes(policy.canonical_document(1, [record_a]))
    other_home = None
    if scenario == "origin-return":
        temporary_other = tempfile.TemporaryDirectory(prefix="native-reviewed-other-origin-")
        request.addfinalizer(temporary_other.cleanup)
        other_home = pathlib.Path(temporary_other.name)
        other_origin = other_home / ".agents" / "publication"
        other_origin.mkdir(parents=True)
        (other_origin / "reviewed-exceptions.json").write_bytes(policy.canonical_document(1, [record_a]))
    # V3 scans commit..old. The separate deletion's actual old root lets V4
    # legitimately exclude that same subject without using its exception.
    v3_only = scenario.startswith("v3-only-")
    wire = f"HEAD {commit} refs/heads/first {old}\n".encode()
    if v3_only:
        wire += f"(delete) {'0' * 40} refs/heads/retired {commit}\n".encode()
    original_child = owner._run_snapshot_child
    original_scan = owner._run_authoritative_scan
    seen = []
    def child(pending, *args):
        if isinstance(pending.binding, owner.NativePushScanBinding) and scenario == "v3-only-revoked":
            policy_file.write_bytes(policy.canonical_document(1, []))
        return original_child(pending, *args)
    def scan(*args, **kwargs):
        native_scan = isinstance(args[0], owner.NativePushInput)
        if native_scan and scenario == "origin-return":
            monkeypatch.setenv("USERPROFILE", str(other_home))
        if native_scan and scenario == "origin-content":
            unused = policy.seal_record({**record, "id": "DEC-UNUSED",
                "rangeScope": {"kind": "exact-commits", "commits": [old]}})
            policy_file.write_bytes(policy.canonical_document(1, [record_a, unused]))
        if native_scan and scenario in {"distinct-active", "distinct-revoked", "conflict"}:
            policy_file.write_bytes(policy.canonical_document(1,
                [changed_a if scenario == "conflict" else record_b]))
        try:
            evidence = original_scan(*args, **kwargs)
        finally:
            if native_scan and scenario == "origin-return":
                monkeypatch.setenv("USERPROFILE", str(home))
        seen.append(evidence)
        if native_scan and scenario.startswith("distinct-"):
            final_b = record_b
            if scenario == "distinct-revoked":
                final_b = policy.seal_record({**{key: value for key, value in record_b.items() if key != "recordSha256"},
                    "revision": 2, "previousRecordSha256": record_b["recordSha256"], "state": "revoked",
                    "revocation": {"reason": "synthetic final-capture revocation", "rootReceivingReference": "synthetic-root"}})
            policy_file.write_bytes(policy.canonical_document(1, [record_a, final_b]))
        return evidence
    output, errors = io.StringIO(), io.StringIO()
    verification_origins = []
    verification_used = []
    verification_captures = []
    finalizations = []
    original_verify = owner._verify_used_review_currentness
    def verify_current(*args, **kwargs):
        current_policy = args[0].policy_module
        verification_origins.append(current_policy.resolve_trusted_origin().status)
        actual_verify = current_policy.verify_used
        def verify_used(*parameters):
            result = actual_verify(*parameters)
            finalizations.append(result)
            return result
        with mock.patch.object(current_policy, "verify_used", side_effect=verify_used) as used, \
             mock.patch.object(current_policy, "_capture_policy_file", wraps=current_policy._capture_policy_file) as capture:
            try:
                return original_verify(*args, **kwargs)
            finally:
                verification_used.append(used.call_args.args[2] if used.called else None)
                verification_captures.append(capture.call_count)
    # Fixture preparation loads the standalone policy. The captured owner
    # requires these slots vacant and owns their lifetime during receiving.
    # patch.dict restores the exact pre-test modules even if receiving fails.
    with mock.patch.dict(sys.modules):
        for name in slot_names:
            sys.modules.pop(name, None)
        with mock.patch.object(owner, "_run_snapshot_child", side_effect=child), \
             mock.patch.object(owner, "_run_authoritative_scan", side_effect=scan), \
             mock.patch.object(owner, "_verify_used_review_currentness", side_effect=verify_current) as verify, \
             mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(wire))), \
             mock.patch.object(sys, "stdout", output), mock.patch.object(sys, "stderr", errors):
            result = owner._native_pre_push_main(["origin", str(remote)])
            assert "_orchestrarium_publication_review_policy_v1" not in sys.modules
            assert "_orchestrarium_linked_runtime_subroots_v1" not in sys.modules
    assert [item.parsed_outcome.kind for item in seen] == ["qualified-v3", "valid-v4" if v3_only else "qualified-v4"], errors.getvalue()
    if v3_only:
        assert seen[1].parsed_outcome.receipt.objects == 0
    if scenario in {"origin-return", "origin-content"}:
        first_review = seen[0].execution.pending.captured_review
        second_review = seen[1].execution.pending.captured_review
        assert first_review.snapshot_id != second_review.snapshot_id
        assert (policy._origin_core_from_snapshot(first_review.snapshot) ==
                policy._origin_core_from_snapshot(second_review.snapshot)) == (scenario == "origin-content")
        assert seen[0].parsed_outcome.qualification.used_decisions_b64 == seen[1].parsed_outcome.qualification.used_decisions_b64
    assert verify.call_count == (2 if v3_only else 3)
    assert verification_origins == ["selected"] * verify.call_count
    if scenario in {"conflict", "origin-return"}:
        assert verification_used[-1] is None and verification_captures[-1] == 0
    else:
        assert [pair[0] for pair in verification_used[-1]] == (["DEC-A", "DEC-B"] if scenario.startswith("distinct-") else ["DEC-A"])
        assert verification_captures[-1] == 1
    if scenario in {"v3-only-revoked", "distinct-revoked", "conflict", "origin-return"}:
        assert result == 2 and "PGG-SCAN-REFUSAL" in errors.getvalue()
        assert output.getvalue() == ""
        if scenario == "distinct-revoked":
            assert finalizations[-1]["reason"] == "used-record-revoked"
    else:
        assert result == 0, (errors.getvalue(), verification_origins)
        assert "qualified (range, receipt=v3" in output.getvalue()
    assert raw.decode().strip() not in output.getvalue() + errors.getvalue()


@pytest.mark.skipif(os.name != "nt", reason="Uses the Windows creator-owned Job")
def test_actual_credential_free_literal_url_preserves_the_real_v3_binding(native_repository, monkeypatch):
    owner = module()
    home = native_repository / "synthetic-user"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    remote = native_repository / "literal.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True, timeout=20)
    url = remote.as_uri()
    argv = (shutil.which("git"), "-C", str(native_repository), *owner.native_git_config_arguments(),
            "push", url, "HEAD:refs/heads/main")
    code, stdout, stderr, settlement = _run_owned_git_job(argv, native_repository)
    assert settlement.complete
    assert code == 0, (stdout + stderr).decode("utf-8", "replace")
    receipt_lines = [line for line in stdout.splitlines() if b"receipt=v3" in line]
    assert len(receipt_lines) == 1
    received = owner.parse_publication_safety_observation(receipt_lines[0].decode())
    assert received.kind == "valid-v3" and received.receipt.remote == url


@pytest.mark.skipif(os.name != "nt", reason="Uses captured Windows scanner children")
def test_named_remote_keeps_private_endpoint_inside_captured_stdin(native_repository, monkeypatch):
    owner = module()
    home = native_repository / "synthetic-user"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(native_repository)
    canary = "SYNTHETIC_ENDPOINT_CANARY"
    endpoint = "https://synthetic-user:" + canary + "@example.invalid/synthetic.git"
    subprocess.run(["git", "-C", str(native_repository), "remote", "add", "origin", endpoint], check=True, timeout=20)
    commit = subprocess.check_output(["git", "-C", str(native_repository), "rev-parse", "HEAD"], timeout=20).strip()
    wire = b"HEAD " + commit + b" refs/heads/main " + b"0" * 40 + b"\n"
    original = owner._run_snapshot_child
    received_payloads = []
    def child(pending, payload, *args):
        assert all(canary not in value for value in pending.exact_argv)
        assert json.loads(payload)["nativePush"]["endpoint"] == endpoint
        received_payloads.append(payload)
        return original(pending, payload, *args)
    output, errors = io.StringIO(), io.StringIO()
    with mock.patch.object(owner, "_run_snapshot_child", side_effect=child), \
         mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(wire))), \
         mock.patch.object(sys, "stdout", output), mock.patch.object(sys, "stderr", errors):
        result = owner._native_pre_push_main(["origin", endpoint])
    assert result == 0, errors.getvalue()
    assert len(received_payloads) == 2
    lines = output.getvalue().splitlines()
    v3 = owner.parse_publication_safety_observation(lines[0])
    v4 = owner.parse_publication_safety_observation(lines[1])
    assert v3.kind == "valid-v3" and v3.receipt.remote == "origin"
    assert v4.kind == "valid-v4" and v4.receipt.endpoint_identity == owner._native_endpoint_identity(endpoint)
    assert canary not in output.getvalue() + errors.getvalue()
