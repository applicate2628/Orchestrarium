import json
import os
import hashlib
import io
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

import test_mutate_work_item as existing_tests
from test_mutate_work_item import load_module


def diagnostic_payload(error):
    marker = " [diagnostic="
    rendered = str(error)
    assert marker in rendered
    prefix, _, suffix = rendered.rpartition(marker)
    assert prefix
    assert suffix.endswith("]")
    return json.loads(suffix[:-1])


def test_captured_file_refusal_exposes_first_checked_predicate_without_private_data(tmp_path):
    module = load_module()
    target = tmp_path / "private-path-sentinel" / "private-name-sentinel.bin"
    target.parent.mkdir()
    target.write_bytes(b"original private buffer")
    snapshot = module._capture_file_snapshot(target, failure_id="WI-CAPTURE-DETAIL")
    altered = replace(snapshot, data=b"DIAGNOSTIC_BUFFER_SENTINEL")

    with pytest.raises(module.LifecycleError) as refused:
        module._verify_captured_file(altered, "WI-CAPTURE-DETAIL")

    error = refused.value
    rendered = str(error)
    assert error.failure_id == "WI-CAPTURE-DETAIL"
    assert rendered.startswith("captured file path identity or content changed")
    payload = diagnostic_payload(error)
    assert payload["kind"] == "captured-file"
    assert payload["predicate"] == "captured-bytes-differ"
    assert payload["locatorKind"] == "redacted-lexical-sha256"
    assert payload["locator"].startswith("redacted-lexical-sha256:")
    assert "private-name-sentinel" not in rendered
    assert "DIAGNOSTIC_BUFFER_SENTINEL" not in rendered

    with patch.object(module.Path, "lstat", side_effect=AssertionError("diagnostic rendering reread the filesystem")):
        assert str(error) == rendered

def test_captured_parent_refusal_names_first_checked_predicate_and_redacts_path(tmp_path):
    module = load_module()
    parent = tmp_path / "private-parent-sentinel"
    target = parent / "record.bin"
    parent.mkdir()
    target.write_bytes(b"captured")
    snapshot = module._capture_file_snapshot(target, failure_id="WI-CAPTURE-PARENT")

    parent.rename(tmp_path / "moved-parent-sentinel")
    parent.mkdir()
    (parent / "record.bin").write_bytes(b"captured")

    with pytest.raises(module.LifecycleError) as refused:
        module._verify_captured_file(snapshot, "WI-CAPTURE-PARENT")

    error = refused.value
    assert error.failure_id == "WI-CAPTURE-PARENT"
    assert str(error).startswith("captured file parent chain changed")
    payload = diagnostic_payload(error)
    assert payload["kind"] == "captured-parent"
    assert payload["predicate"] == "parent-identity-changed"
    assert payload["locator"].startswith("redacted-lexical-sha256:")
    assert "private-parent-sentinel" not in str(error)


def test_descriptor_path_sample_mismatch_reports_predicate_and_closes_stream(tmp_path, monkeypatch):
    module = load_module()
    target = tmp_path / "private-descriptor-path-sentinel.bin"
    displaced = tmp_path / "displaced-original.bin"
    replacement = tmp_path / "replacement.bin"
    same_bytes = b"same captured contents"
    target.write_bytes(same_bytes)
    replacement.write_bytes(same_bytes)
    snapshot = module._capture_file_snapshot(
        target, failure_id="WI-CAPTURE-DESCRIPTOR-PATH"
    )
    original_open = module._open_readonly_nofollow
    opened = []

    def replace_path_then_open(path):
        assert path == target
        path.replace(displaced)
        replacement.replace(path)
        descriptor = original_open(path)
        opened.append(
            (descriptor, module._lifecycle_file_identity(os.fstat(descriptor)))
        )
        return descriptor

    monkeypatch.setattr(module, "_open_readonly_nofollow", replace_path_then_open)
    with pytest.raises(module.LifecycleError) as refused:
        module._verify_captured_file(snapshot, "WI-CAPTURE-DESCRIPTOR-PATH")

    error = refused.value
    rendered = str(error)
    prefix, marker, suffix = rendered.rpartition(" [diagnostic=")
    assert marker and suffix.endswith("]")
    assert error.failure_id == "WI-CAPTURE-DESCRIPTOR-PATH"
    assert prefix == "captured file path is no longer available"
    assert isinstance(error.__cause__, OSError)
    assert str(error.__cause__) == "captured descriptor differs from its pathname"
    assert "private-descriptor-path-sentinel" not in rendered
    payload = json.loads(suffix[:-1])
    assert payload["predicate"] == "descriptor-path-sample-differs"
    assert payload["stage"] == "descriptor-before-stat"
    assert payload["observations"] == ["observed-file-stat", "descriptor-before-stat"]
    assert len(opened) == 1
    assert opened[0][1] != snapshot.identity
    with pytest.raises(OSError):
        os.fstat(opened[0][0])


def test_captured_file_acquisition_refusal_marks_unavailable_without_cause_text(tmp_path):
    module = load_module()
    target = tmp_path / "private-acquisition-name.bin"
    target.write_bytes(b"captured")
    snapshot = module._capture_file_snapshot(target, failure_id="WI-CAPTURE-UNAVAILABLE")
    target.unlink()

    with pytest.raises(module.LifecycleError) as refused:
        module._verify_captured_file(snapshot, "WI-CAPTURE-UNAVAILABLE")

    error = refused.value
    assert error.failure_id == "WI-CAPTURE-UNAVAILABLE"
    assert isinstance(error.__cause__, OSError)
    assert "private-acquisition-name" not in str(error)
    payload = diagnostic_payload(error)
    assert payload["kind"] == "captured-file"
    assert payload["predicate"] == "file-observation-unavailable"
    assert payload["observations"] == []

def _captured_data_error(module, tmp_path, failure_id="WI-CAPTURE-DETAIL"):
    target = tmp_path / "private-error-source" / "private-buffer.bin"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"original private bytes")
    snapshot = module._capture_file_snapshot(target, failure_id=failure_id)
    with pytest.raises(module.LifecycleError) as refused:
        module._verify_captured_file(
            replace(snapshot, data=b"DIAGNOSTIC_PRIVATE_BUFFER"), failure_id
        )
    return refused.value


def test_diagnostic_construction_failure_is_visible_without_replacing_refusal(tmp_path, monkeypatch):
    module = load_module()
    target = tmp_path / "private-path.bin"
    target.write_bytes(b"captured")
    snapshot = module._capture_file_snapshot(target, failure_id="WI-CAPTURE-UNAVAILABLE")

    def refuse_hash(_value):
        raise RuntimeError("DIAGNOSTIC_CONSTRUCTION_SENTINEL")

    monkeypatch.setattr(module.hashlib, "sha256", refuse_hash)
    with pytest.raises(module.LifecycleError) as refused:
        module._verify_captured_file(
            replace(snapshot, data=b"different"), "WI-CAPTURE-UNAVAILABLE"
        )

    error = refused.value
    assert error.failure_id == "WI-CAPTURE-UNAVAILABLE"
    assert str(error).startswith("captured file path identity or content changed")
    assert diagnostic_payload(error) == {"kind": "unavailable"}
    assert "DIAGNOSTIC_CONSTRUCTION_SENTINEL" not in str(error)


def test_bound_transaction_path_is_logical_and_outside_path_stays_redacted(tmp_path):
    module = load_module()
    root = tmp_path / "repo"
    logical = root / "work-items" / "active" / "owner" / "status.md"
    outside = tmp_path / "private-outside-name" / "notes.bin"
    logical.parent.mkdir(parents=True)
    outside.parent.mkdir()
    logical.write_bytes(b"bound file")
    outside.write_bytes(b"outside file")
    observations = []

    def observe_bound_diagnostics(actual_root):
        assert actual_root == root
        for path in (logical, outside):
            snapshot = module._capture_file_snapshot(path, failure_id="WI-BOUND-DETAIL")
            with pytest.raises(module.LifecycleError) as refused:
                module._verify_captured_file(
                    replace(snapshot, data=b"different"), "WI-BOUND-DETAIL"
                )
            observations.append(diagnostic_payload(refused.value))

    participant = module._lifecycle_participant(
        observe_bound_diagnostics, input_role="repository-root"
    )
    participant(root)

    assert observations[0]["locatorKind"] == "repository-relative"
    assert observations[0]["locator"] == "work-items/active/owner/status.md"
    assert observations[1]["locatorKind"] == "redacted-lexical-sha256"
    assert observations[1]["locator"].startswith("redacted-lexical-sha256:")
    assert "private-outside-name" not in str(observations[1])


def test_explicit_observer_receives_detail_without_cleanup_output_leak(tmp_path):
    module = load_module()
    primary = _captured_data_error(module, tmp_path / "failure")
    observer = module.LifecycleDiagnosticObserver()

    @module._lifecycle_participant
    def fail_with_cleanup(root):
        composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
        composer.record_cleanup(
            phase="transaction-release",
            failure_id="WI-TEST-CLEANUP",
            resource="owned-handle",
            diagnostic="cleanup-only diagnostic",
        )
        raise primary

    root = tmp_path / "repository"
    root.mkdir()
    with pytest.raises(module.LifecycleError) as refused:
        fail_with_cleanup(root, diagnostic_observer=observer)

    assert refused.value is primary
    assert observer.state == "delivered"
    assert observer.snapshot.primaryFailureId == primary.failure_id
    primary_detail = getattr(observer.snapshot, "primaryDetail", None)
    assert primary_detail is not None and primary_detail.kind == "captured-file"
    output = io.StringIO()
    with redirect_stdout(output):
        module._emit_lifecycle_cleanup_diagnostics(observer)
    assert "cleanup-only diagnostic" in output.getvalue()
    assert "captured-bytes-differ" not in output.getvalue()
    assert "redacted-lexical-sha256" not in output.getvalue()


def test_public_supersession_projection_keeps_fixed_output_for_detail_failure(tmp_path):
    module = load_module()
    root = tmp_path / "repo"
    operation_id = "supersession-safe-detail"
    argv, _source, _binding_file, _successor = existing_tests._supersede_current_bug_cli_fixture(
        module, root, "2026-09-10-supersession-safe-detail", operation_id
    )
    detail_error = _captured_data_error(module, tmp_path / "error", "WI-BUG-SUCCESSOR-BINDING")
    before = existing_tests.tree_file_bytes(root)
    output = io.StringIO()
    errors = io.StringIO()
    with patch.object(module, "supersede_current_bug", side_effect=detail_error), \
            redirect_stdout(output), redirect_stderr(errors):
        result = module.main(argv)

    assert result == 1
    assert output.getvalue() == (
        "WI-BUG-SUCCESSOR-BINDING: current bug supersession rejected\n"
    )
    assert errors.getvalue() == ""
    assert "redacted-lexical-sha256" not in output.getvalue()
    assert existing_tests.tree_file_bytes(root) == before


def test_validator_text_adapter_forwards_captured_detail(tmp_path, monkeypatch):
    module = load_module()
    validator = module._validator_module()
    root = tmp_path / "repo"
    existing_tests.seed_active(module, root, "data-owner")
    item = root / "work-items" / "active" / "data-owner"
    payload = item / "inputs" / "source.dat"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"original ordinary data\n")
    files = [
        module._capture_file_snapshot(path, failure_id="TEST-CAPTURE")
        for path in root.rglob("*") if path.is_file()
    ]
    directories = [
        module._capture_directory_snapshot(path, failure_id="TEST-CAPTURE")
        for path in [root] + [path for path in root.rglob("*") if path.is_dir()]
    ]
    native = module.AcquiredWorkItemInputV1(
        root,
        [module.CapturedInputAssociationV1(snapshot, snapshot) for snapshot in files],
        [module.CapturedInputAssociationV1(snapshot, snapshot) for snapshot in directories],
    )
    criteria = validator.HistoricalLedgerCriteriaV1(
        "synthetic-criteria", "synthetic-acquisition", False, "current"
    )
    binding = validator.CapturedWorkItemHistoryBindingV1(
        root, item.name, item.relative_to(root).as_posix(), item.relative_to(root).as_posix(),
        (item / "agent-runs.jsonl").relative_to(root).as_posix(), criteria, (), (), {}, native,
    )
    original_verify = module._verify_captured_file
    injected = []

    def fail_selected_snapshot(snapshot, failure_id, *args, **kwargs):
        if snapshot.path == payload and not injected:
            injected.append(True)
            snapshot = replace(snapshot, data=snapshot.data + b"DIAGNOSTIC_SENTINEL")
        return original_verify(snapshot, failure_id, *args, **kwargs)

    monkeypatch.setattr(module, "_verify_captured_file", fail_selected_snapshot)
    observation = validator.observe_captured_work_item_history(binding)

    assert injected == [True]
    assert any("captured-bytes-differ" in error for error in observation.diagnostics)
    assert any("redacted-lexical-sha256" in error for error in observation.diagnostics)
    assert all("DIAGNOSTIC_SENTINEL" not in error for error in observation.diagnostics)


def test_agent_run_ledger_text_adapter_forwards_captured_detail(tmp_path):
    module = load_module()
    ledger = module._load_agent_run_ledger()
    validator = ledger.load_validator()
    lifecycle = validator.load_lifecycle_owner()
    detail_error = _captured_data_error(lifecycle, tmp_path / "failure")
    with patch.object(validator, "load_lifecycle_owner", return_value=lifecycle), \
            patch.object(ledger, "load_validator", return_value=validator), \
            patch.object(ledger, "command_rollup", side_effect=detail_error):
        error = io.StringIO()
        with redirect_stderr(error):
            result = ledger.main(["rollup", "--root", str(tmp_path / "unused-root")])

    assert result == 1
    assert "FAIL: captured file path identity or content changed [diagnostic=" in error.getvalue()
    assert "captured-bytes-differ" in error.getvalue()
    assert "DIAGNOSTIC_PRIVATE_BUFFER" not in error.getvalue()


def test_audit_exposes_validated_family_metadata_once_and_preserves_rolled_back_semantics(tmp_path):
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-10-audit-family-detail"
    operation_id = "audit-family-detail"
    argv, source, binding_file, successor = existing_tests._supersede_current_bug_cli_fixture(
        module, root, slug, operation_id
    )
    inventory = root / "input" / "incoming-links.json"
    readme = root / "work-items" / "README.md"
    terminal = argv[argv.index("--terminal-instant") + 1]
    with pytest.raises(module.LifecycleError):
        module.supersede_current_bug(
            root,
            slug,
            successor,
            binding_file.read_bytes(),
            terminal,
            inventory.read_bytes(),
            hashlib.sha256(source.read_bytes()).hexdigest(),
            hashlib.sha256(readme.read_bytes()).hexdigest(),
            operation_id,
            inject_failure_at="B1",
        )
    intent_path = root / ".scratch" / "work-items-lifecycle-transitions" / f"{operation_id}.json"
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    expected_links = len(intent["links"])
    before = existing_tests.tree_file_bytes(root)

    with pytest.raises(module.LifecycleError) as refused:
        module.audit(root)

    error = refused.value
    assert error.failure_id == "WI-LIFECYCLE-TRANSITION-RECOVERY-REQUIRED"
    assert str(error).startswith("pending lifecycle transition(s): audit-family-detail; run: ")
    payload = diagnostic_payload(error)
    assert payload["kind"] == "transition-audit"
    assert len(payload["entries"]) == 1
    row = payload["entries"][0]
    assert row["family"] == "bug-supersession"
    assert row["linksCount"] == expected_links
    assert "workItem" not in row and "slug" not in row and "bugsCount" not in row
    assert str(intent_path) not in str(error)
    assert existing_tests.tree_file_bytes(root) == before

    output = io.StringIO()
    errors = io.StringIO()
    with redirect_stdout(output), redirect_stderr(errors):
        assert module.main(["audit", "--root", str(root)]) == 1
    assert output.getvalue().startswith("WI-LIFECYCLE-TRANSITION-RECOVERY-REQUIRED: pending lifecycle transition(s):")
    assert "transition-audit" in output.getvalue()
    assert errors.getvalue() == ""

    recovered_output = io.StringIO()
    with redirect_stdout(recovered_output):
        assert module.main([
            "recover-transition", "--root", str(root), "--operation-id", operation_id, "--apply"
        ]) == 0
    assert f"operation={operation_id} outcome=rolled-back" in recovered_output.getvalue()
    module.audit(root)

def test_audit_invalid_and_drifting_intents_stay_nonclean_without_family_metadata(tmp_path, monkeypatch):
    module = load_module()
    root = tmp_path / "repo"
    operation_id = "audit-invalid-detail"
    argv, source, binding_file, successor = existing_tests._supersede_current_bug_cli_fixture(
        module, root, "2026-09-10-audit-invalid-detail", operation_id
    )
    inventory = root / "input" / "incoming-links.json"
    readme = root / "work-items" / "README.md"
    with pytest.raises(module.LifecycleError):
        module.supersede_current_bug(
            root,
            "2026-09-10-audit-invalid-detail",
            successor,
            binding_file.read_bytes(),
            argv[argv.index("--terminal-instant") + 1],
            inventory.read_bytes(),
            hashlib.sha256(source.read_bytes()).hexdigest(),
            hashlib.sha256(readme.read_bytes()).hexdigest(),
            operation_id,
            inject_failure_at="B1",
        )
    intent_path = root / ".scratch" / "work-items-lifecycle-transitions" / f"{operation_id}.json"
    original = intent_path.read_bytes()
    before = existing_tests.tree_file_bytes(root)

    intent_path.write_bytes(b"{malformed transition envelope")
    malformed_image = existing_tests.tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as malformed:
        module.audit(root)
    assert malformed.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    assert "transition-audit" not in str(malformed.value)
    assert existing_tests.tree_file_bytes(root) == malformed_image
    intent_path.write_bytes(original)
    assert existing_tests.tree_file_bytes(root) == before

    real_verify = module._verify_captured_file
    drifted = []

    def change_after_capture(snapshot, failure_id, *args, **kwargs):
        if snapshot.path == intent_path and not drifted:
            intent_path.write_bytes(snapshot.data + b" ")
            drifted.append(True)
        return real_verify(snapshot, failure_id, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(module, "_verify_captured_file", change_after_capture)
        with pytest.raises(module.LifecycleError) as changed:
            module.audit(root)
    assert drifted == [True]
    assert changed.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    assert "transition-audit" not in str(changed.value)
    current = existing_tests.tree_file_bytes(root)
    expected = dict(before)
    relative = intent_path.relative_to(root).as_posix()
    expected[relative] = original + b" "
    assert current == expected
    intent_path.write_bytes(original)
    assert existing_tests.tree_file_bytes(root) == before

def test_oserror_cause_is_preserved_but_not_in_rendered_detail(tmp_path, monkeypatch):
    module = load_module()
    target = tmp_path / "private-cause-path.bin"
    target.write_bytes(b"captured")
    snapshot = module._capture_file_snapshot(target, failure_id="WI-CAPTURE-CAUSE")
    cause = OSError("CAUSE_PRIVATE_SENTINEL")

    def refuse_open(_path):
        raise cause

    monkeypatch.setattr(module, "_open_readonly_nofollow", refuse_open)
    with pytest.raises(module.LifecycleError) as refused:
        module._verify_captured_file(snapshot, "WI-CAPTURE-CAUSE")

    error = refused.value
    assert error.__cause__ is cause
    assert "CAUSE_PRIVATE_SENTINEL" in str(cause)
    assert error.failure_id == "WI-CAPTURE-CAUSE"
    rendered = str(error)
    assert "CAUSE_PRIVATE_SENTINEL" not in rendered
    assert "private-cause-path.bin" not in rendered
    payload = diagnostic_payload(error)
    assert payload["predicate"] == "file-observation-unavailable"
    assert payload["stage"] == "no-follow-open"
    assert payload["observations"] == ["observed-file-stat"]