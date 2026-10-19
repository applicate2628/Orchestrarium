"""Finite input admission and actual owner-output resource regression guards."""
import hashlib
import importlib.util
import json
import os
import random
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_owner(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/mutate-work-item.py")
    owner = importlib.util.module_from_spec(spec)
    sys.modules[name] = owner
    spec.loader.exec_module(owner)
    return owner


def test_numeric_admission_is_complete_finite_and_not_a_payload_grant():
    owner = load_owner("transition_numeric_owner")
    assert owner.resolve_transition_resource_budget(0, 0, 0) == owner.TransitionResourceBudgetV1(0, 0, 0)
    for values in ((None, 1, 1), (True, 1, 1), (-1, 1, 1), (2, 1, 1)):
        with pytest.raises(owner.LifecycleError, match="complete coherent"):
            owner.resolve_transition_resource_budget(*values)


def test_selected_native_census_is_exact_before_decode_and_rejects_drift(tmp_path, monkeypatch):
    owner = load_owner("transition_native_census_owner")
    root = tmp_path / "repo"
    root.mkdir()
    empty = owner.select_transition_resource_inputs(root, input_role="repository-root", read_admission="selected-native")
    assert empty.acquisition == owner.TransitionResourceBudgetV1(0, 0, 0)
    directory = root / ".scratch/work-items-lifecycle-transitions"
    directory.mkdir(parents=True)
    raw = b'{"untrustedBudget":999999999999999999}' + b" " * (256 * 1024)
    selected = directory / "selected.json"
    selected.write_bytes(raw)
    (directory / "non-json-entry").write_bytes(b"not a resource grant")

    def forbidden_decode(*_args, **_kwargs):
        raise AssertionError("metadata admission decoded untrusted JSON")

    with monkeypatch.context() as patch:
        patch.setattr(owner.json, "loads", forbidden_decode)
        admitted = owner.select_transition_resource_inputs(root, input_role="repository-root", read_admission="selected-native")
        assert admitted.acquisition == owner.TransitionResourceBudgetV1(len(raw), len(raw), 2)
        with pytest.raises(owner.LifecycleError, match="ceiling"):
            owner.select_transition_resource_inputs(root, input_role="repository-root", read_admission="selected-native",
                acquisition_ceiling=owner.TransitionResourceBudgetV1(len(raw)-1, len(raw), 2))
        with pytest.raises(owner.LifecycleError, match="ceiling"):
            owner.select_transition_resource_inputs(root, input_role="repository-root", read_admission="explicit",
                acquisition_ceiling=owner.TransitionResourceBudgetV1(len(raw), len(raw), 1))
    selected.write_bytes(raw + b" ")
    with pytest.raises(owner.LifecycleError):
        admitted.verify()


def flat_fixture(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tests/test_legacy_flat_terminal_close.py")
    fixture = importlib.util.module_from_spec(spec)
    sys.modules[name] = fixture
    spec.loader.exec_module(fixture)
    case = fixture.LegacyFlatTerminalTests()
    case.setUp()
    # A failing native test keeps its acquired state for diagnosis; successful
    # disposal belongs to the orchestrating test-resource disposition.
    case.temp._finalizer.detach()
    return fixture, case


@pytest.mark.skipif(os.name != "nt", reason="actual Windows legacy creator owner")
def test_first_empty_apply_reserves_once_before_durable_receiving_and_replays(monkeypatch):
    fixture, case = flat_fixture("transition_first_empty_fixture")
    owner = fixture.m
    _evidence, arguments = case.legacy_request()
    reserves, saves = [], []
    reserve = owner._PendingLegacyCompletionPlan.reserve
    save = owner._legacy_save_intent

    def observe_reserve(cls, *args, **kwargs):
        plan = reserve(*args, **kwargs)
        reserves.append(plan)
        assert not hasattr(plan, "durable") and not hasattr(plan, "native_progress")
        assert plan.transaction.transition_resource_budget == owner.TransitionResourceBudgetV1(0, 0, 0)
        assert plan.resource_budget.max_intent_bytes > 0
        return plan

    def observe_save(path, intent, **kwargs):
        plan = kwargs["_plan"]
        data = owner._migration_receipt_bytes(intent)
        saves.append((len(data), plan.resource_budget))
        assert len(data) <= plan.resource_budget.max_intent_bytes
        return save(path, intent, **kwargs)

    monkeypatch.setattr(owner._PendingLegacyCompletionPlan, "reserve", classmethod(observe_reserve))
    monkeypatch.setattr(owner, "_legacy_save_intent", observe_save)
    invocation = arguments + ["--apply", "--transition-read-admission", "selected-native"]
    assert owner.main(invocation) == 0
    archive = case.root / "work-items/archive/2026-10" / case.slug
    metadata = json.loads((archive / owner.LEGACY_COMPLETION_METADATA).read_bytes())
    proof = next(row for row in metadata["custodyMap"] if row["originalPath"] == "evidence/proof.md")
    expected = (case.root / "evidence/proof.md").read_bytes()
    assert (archive / proof["preservedPath"]).read_bytes() == expected
    assert hashlib.sha256(expected).hexdigest() == proof["sha256"]
    receipt = (archive / owner.LEGACY_COMPLETION_RECEIPT).read_bytes()
    assert not case.source.exists()
    assert len(reserves) == 1 and len(saves) > 1
    assert len({budget for _length, budget in saves}) == 1
    assert reserves[0].transaction._file is None and not reserves[0].transaction._locked
    port = owner.acquire_settled_work_item_history(case.root, f"work-item:{case.slug}")
    validator = owner._validator_module()
    binding = validator.bind_settled_work_item_history(port)
    cursor = validator._CapturedHistoryPath(binding, case.root)
    absent = case.root / "proved-absent-native-metadata.json"
    assert port.origin_entry(absent) is None and not port.exists(absent)
    with pytest.raises(FileNotFoundError):
        port.current_native_metadata(absent)
    with pytest.raises(FileNotFoundError):
        cursor.current_native_metadata(absent)
    assert cursor.acquisition_failures == []
    assert not owner._read_project_topology_at(case.root / "work-items", acquired_input=cursor).root_contract_present
    unselected = case.root / "closure-input.md"
    assert port.exists(unselected) and unselected not in port.files
    with pytest.raises(owner.LifecycleError, match="not acquired"):
        cursor.current_native_metadata(unselected)
    assert cursor.acquisition_failures
    selected = next(iter(port.files))
    snapshot = port.files[selected].current
    stat = Path.lstat
    file_snapshot = type(port).file_snapshot
    with monkeypatch.context() as patch:
        def missing_after_verified_custody(path, *args, **kwargs):
            if path == snapshot.path:
                raise FileNotFoundError("selected current metadata disappeared after verified custody")
            return stat(path, *args, **kwargs)
        def checked_then_missing(self, path, **kwargs):
            result = file_snapshot(self, path, **kwargs)
            if path == selected:
                patch.setattr(Path, "lstat", missing_after_verified_custody)
            return result
        patch.setattr(type(port), "file_snapshot", checked_then_missing)
        with pytest.raises(owner.LifecycleError):
            port.current_native_metadata(selected)
    port.verify()
    assert owner.main(invocation) == 0
    assert len(reserves) == 1
    assert (archive / owner.LEGACY_COMPLETION_RECEIPT).read_bytes() == receipt
    assert not list((case.root / ".scratch/work-items-lifecycle-transitions").glob("*.json"))


@pytest.mark.skipif(os.name != "nt", reason="actual Windows legacy creator owner")
def test_hard_output_ceiling_refuses_before_initial_intent_and_business_effects(monkeypatch):
    fixture, case = flat_fixture("transition_hard_output_fixture")
    owner = fixture.m
    _evidence, arguments = case.legacy_request()
    before = case.canonical_images()
    original = owner._legacy_intent_resource_demand
    demands = []
    def observe(*args, **kwargs):
        demand = original(*args, **kwargs)
        demands.append(demand)
        return demand
    monkeypatch.setattr(owner, "_legacy_intent_resource_demand", observe)
    assert owner.main(arguments + ["--apply", "--transition-read-admission", "selected-native",
        "--transition-output-max-intent-bytes", "0", "--transition-output-max-inventory-bytes", "0",
        "--transition-output-max-inventory-entries", "0"]) == 1
    assert len(demands) == 1
    assert case.canonical_images() == before
    assert case.source.exists()
    assert not list((case.root / ".scratch/work-items-lifecycle-transitions").glob("*.json"))


@pytest.mark.skipif(os.name != "nt", reason="actual Windows expected-image native owner")
def test_known_large_native_image_promotes_and_removes_with_exact_identity(tmp_path):
    owner = load_owner("transition_large_native_image_owner")
    path = tmp_path / "selected.bin"
    payload = b"actual selected native image\n" + b"x" * (4 * 1024 * 1024)
    with owner.LifecycleWriteTarget(path, failure_id="WI-TEST-LARGE-NATIVE") as target:
        created = target.stage_create(payload)
        target.promote_create(created)
        image = target.owned_image(maximum_bytes=len(payload))
        assert image == {key: created[key] for key in ("identity", "sha256", "data")}
        target.remove_owned(path.name, image)
    assert not path.exists()
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="actual transaction/native publication binding")
def test_matching_acquired_input_cannot_borrow_reserved_output_before_publication(tmp_path):
    owner = load_owner("transition_output_publication_owner")
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    directory = root / ".scratch/work-items-lifecycle-transitions"
    directory.mkdir(parents=True)
    path = directory / "publication-guard.json"
    intent = dict.fromkeys(owner.BUG_SUPERSESSION_INTENT_FIELDS)
    intent.update(schemaVersion=1, owner=owner.BUG_SUPERSESSION_OWNER, kind=owner.BUG_SUPERSESSION_KIND,
                  status="intent", operationId="publication-guard", links=[])
    data = owner._migration_receipt_bytes(intent)
    path.write_bytes(data)
    with owner.LifecycleTransaction(root, input_role="repository-root", transition_read_admission="selected-native") as tx:
        token = owner._CURRENT_LIFECYCLE_TRANSACTION.set(tx)
        try:
            snapshot = owner._capture_file_snapshot(path, failure_id="WI-TEST-INPUT", maximum_bytes=len(data))
            tx.observe_retained_inputs((snapshot,))
            owner._transition_reserve_fixed_output(path, data)
            # Current-map input custody plus matching prepared bytes are not
            # evidence that this reservation has actually published output.
            with pytest.raises(owner.LifecycleError):
                owner._read_transition_intent_envelope(root, path,
                    transition_resource_budget=owner.TransitionResourceBudgetV1(0, 0, 0))
            owner._atomic_write(path, data)
            acquired = owner._read_transition_intent_envelope(root, path,
                transition_resource_budget=owner.TransitionResourceBudgetV1(0, 0, 0))
            assert acquired[0] == intent
            assert acquired[1].identity != snapshot.identity
            owner._remove_lifecycle_file(path, failure_id="WI-TEST-OUTPUT-SETTLE")
        finally:
            owner._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    assert not path.exists()


def test_ordinary_captured_history_does_not_acquire_unselected_runtime_namespace():
    spec = importlib.util.spec_from_file_location("transition_original_history_fixture", ROOT / "tests/test_legacy_flat_history_binding.py")
    fixtures = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fixtures
    spec.loader.exec_module(fixtures)
    case = fixtures.CapturedHistoryBindingTests()
    case.setUp()
    case.temp._finalizer.detach()
    case.ledger(modern=True)
    scratch = case.root / ".scratch"
    scratch.mkdir()
    (scratch / "runtime-note").write_bytes(b"unselected runtime state\n")
    binding = case.binding(contract="current")
    files = tuple(row for row in binding.files if not (case.root/row.original_path).is_relative_to(scratch))
    directories = {path: row for path, row in binding.acquired_input.directories.items() if not path.is_relative_to(scratch)}
    acquired = case.owner.AcquiredWorkItemInputV1(case.root,
        tuple(binding.acquired_input.files[case.root/row.original_path] for row in files), tuple(directories.values()))
    selected = replace(binding, files=files, acquired_input=acquired,
        directory_members={name: names for name, names in binding.directory_members.items()
                           if not (case.root/name).is_relative_to(scratch)})
    observed = fixtures.v.observe_captured_work_item_history(selected,
        transition_resource_budget=case.owner.TransitionResourceBudgetV1(0, 0, 0))
    assert observed.acquisition_complete, observed.diagnostics
    assert observed.diagnostics == ()


def test_fixed_reservation_cannot_change_before_publication_and_serial_requires_owned_removal(tmp_path):
    owner = load_owner("transition_fixed_reservation_epoch_owner")
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    first = root / ".scratch/work-items-lifecycle-transitions/first.json"
    second = first.with_name("second.json")
    initial = b'{"selected":"first"}\n'
    later = b'{"selected":"second with distinct finite output demand"}\n'
    with owner.LifecycleTransaction(root, input_role="repository-root",
            transition_read_admission="selected-native") as transaction:
        token = owner._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            original = owner._transition_reserve_fixed_output(first, initial)
            with pytest.raises(owner.LifecycleError, match="unsettled|reserved"):
                owner._transition_reserve_fixed_output(first, later)
            with pytest.raises(owner.LifecycleError, match="unsettled|reserved"):
                owner._transition_reserve_fixed_output(second, later)
            assert owner._transition_reserve_fixed_output(first, initial) is original
            owner._atomic_write(first, initial)
            with pytest.raises(owner.LifecycleError, match="unsettled|reserved"):
                owner._transition_reserve_fixed_output(second, later)
            owner._remove_lifecycle_file(first, failure_id="WI-TEST-SERIAL-OUTPUT")
            assert not first.exists()
            next_budget = owner._transition_reserve_fixed_output(second, later)
            assert next_budget.max_intent_bytes == len(later)
            assert original.max_intent_bytes == len(initial)
            assert transaction.transition_resource_budget == owner.TransitionResourceBudgetV1(0, 0, 0)
            owner._atomic_write(second, later)
            owner._remove_lifecycle_file(second, failure_id="WI-TEST-SERIAL-OUTPUT")
        finally:
            owner._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    assert not first.exists() and not second.exists()


def test_missing_published_output_without_owned_removal_cannot_settle_reservation(tmp_path):
    owner = load_owner("transition_unowned_absence_owner")
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    first = root / ".scratch/work-items-lifecycle-transitions/first.json"
    second = first.with_name("second.json")
    parked = first.with_name("fixture-preserved-original")
    data = b'{"selected":"original"}\n'
    transaction = owner.LifecycleTransaction(root, input_role="repository-root", transition_read_admission="selected-native")
    with pytest.raises(owner.LifecycleError, match="directory identity/membership changed"):
        with transaction:
            token = owner._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            try:
                owner._transition_reserve_fixed_output(first, data)
                owner._atomic_write(first, data)
                first.rename(parked)
                with pytest.raises(owner.LifecycleError, match="unsettled|reserved"):
                    owner._transition_reserve_fixed_output(second, data)
                assert not second.exists() and parked.read_bytes() == data
            finally:
                owner._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    assert transaction._file is None and not transaction._locked
    assert parked.read_bytes() == data and not first.exists() and not second.exists()


def test_public_nested_boundaries_inherit_same_owner_and_refuse_control_changes(tmp_path, monkeypatch):
    owner = load_owner("transition_nested_public_owner")
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    zero = owner.TransitionResourceBudgetV1(0, 0, 0)
    changed = owner.TransitionResourceBudgetV1(1, 1, 1)
    render = owner._render_readme_bytes
    observed = []

    def inspect_nested(root, **kwargs):
        transaction = owner._CURRENT_LIFECYCLE_TRANSACTION.get()
        inputs = transaction.transition_resource_inputs
        assert transaction.transition_resource_budget == transaction.transition_output_ceiling == zero
        owner.audit_categories(root)
        assert owner._CURRENT_LIFECYCLE_TRANSACTION.get() is transaction
        assert owner.project_root_identity(root)[0] == root
        for controls in ({"transition_resource_budget": changed}, {"transition_output_ceiling": changed},
                         {"transition_read_admission": "explicit"}):
            with pytest.raises(owner.LifecycleError, match="nested operation changed"):
                owner.render_readme_bytes(root, **controls)
            with pytest.raises(owner.LifecycleError, match="nested operation changed"):
                owner.project_root_identity(root, **controls)
        assert transaction.transition_resource_inputs is inputs
        assert transaction.transition_resource_budget == transaction.transition_output_ceiling == zero
        observed.append(transaction)
        return render(root, **kwargs)

    monkeypatch.setattr(owner, "_render_readme_bytes", inspect_nested)
    result = owner.render_readme_bytes(root, transition_read_admission="selected-native", transition_output_ceiling=zero)
    assert isinstance(result, bytes) and len(observed) == 1
    assert observed[0]._file is None and not observed[0]._locked
    assert owner._CURRENT_LIFECYCLE_TRANSACTION.get() is None


@pytest.mark.skipif(os.name != "nt", reason="actual Windows public interrupted owner")
def test_public_large_pending_receives_explicit_resources_and_recovers_with_exact_input(monkeypatch, capsys):
    fixture, case = flat_fixture("transition_public_large_pending_fixture")
    owner = fixture.m
    proof = case.root / "evidence/proof.md"
    proof.write_bytes(b"# accepted\n" + random.Random(41020).randbytes(
        owner.TRANSITION_INTENT_FILE_BYTE_CAP + 1).hex().encode())
    expected = proof.read_bytes()
    evidence, _arguments = case.legacy_request()
    with pytest.raises(owner.LifecycleError, match="interruption after derived board"):
        owner.close_item(case.root, case.slug, case.closure, case.instant, legacy_evidence_data=evidence,
            apply=True, inject_failure_at="after-board", transition_read_admission="selected-native")
    pending = case.root / ".scratch/work-items-lifecycle-transitions/flat-terminal-001.json"
    original = pending.read_bytes()
    original_identity = owner._lifecycle_file_identity(pending.lstat())
    assert len(original) > owner.TRANSITION_INTENT_FILE_BYTE_CAP
    spec = importlib.util.spec_from_file_location("transition_public_pending_checker", ROOT / "scripts/check-work-items-state.py")
    checker = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = checker
    spec.loader.exec_module(checker)
    invocation = ["--root", str(case.root), "--transition-read-admission", "selected-native"]
    capsys.readouterr()
    assert checker.main(invocation) == 1
    output = capsys.readouterr().out
    assert "WI-LEGACY-COMPLETION-PENDING" in output and "WI-LIFECYCLE-RESOURCE-INCOMPLETE" not in output
    check = checker.command_check

    def omit_actual_edge(args, *, ledger_resource_budget=None, transition_resource_budget=None):
        assert transition_resource_budget.max_intent_bytes == len(original)
        return check(args, ledger_resource_budget=ledger_resource_budget)

    with monkeypatch.context() as patch:
        patch.setattr(checker, "command_check", omit_actual_edge)
        assert checker.main(invocation) == 1
    assert "WI-LIFECYCLE-RESOURCE-INCOMPLETE" in capsys.readouterr().out
    assert pending.read_bytes() == original and owner._lifecycle_file_identity(pending.lstat()) == original_identity
    budget = owner.select_transition_resource_inputs(case.root, input_role="repository-root",
        read_admission="selected-native").acquisition
    assert budget == owner.TransitionResourceBudgetV1(len(original), len(original), 1)
    save = owner._legacy_save_intent
    saves = []

    def observe_save(path, intent, **kwargs):
        plan = kwargs["_plan"]
        actual = len(owner._migration_receipt_bytes(intent))
        assert plan.transaction.transition_resource_budget == budget
        assert actual <= plan.resource_budget.max_intent_bytes
        saves.append((actual, plan.resource_budget))
        return save(path, intent, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(owner, "_legacy_save_intent", observe_save)
        assert owner.main(["recover-transition", "--root", str(case.root), "--operation-id", "flat-terminal-001", "--apply",
            "--transition-max-intent-bytes", str(budget.max_intent_bytes),
            "--transition-max-inventory-bytes", str(budget.max_inventory_bytes),
            "--transition-max-inventory-entries", str(budget.max_inventory_entries)]) == 0
    assert saves and max(actual for actual, _budget in saves) > len(original)
    assert len({reserved for _actual, reserved in saves}) == 1
    archive = case.root / "work-items/archive/2026-10" / case.slug
    metadata = json.loads((archive / owner.LEGACY_COMPLETION_METADATA).read_bytes())
    selected = next(row for row in metadata["custodyMap"] if row["originalPath"] == "evidence/proof.md")
    assert (archive / selected["preservedPath"]).read_bytes() == expected
    assert selected["sha256"] == hashlib.sha256(expected).hexdigest()
    assert (archive / owner.LEGACY_COMPLETION_RECEIPT).is_file()
    assert not pending.exists() and not case.source.exists()
    owner.check_readme(case.root, transition_read_admission="selected-native")
