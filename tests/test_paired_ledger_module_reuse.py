"""Paired code generation reuse, not ledger or authorization caching."""
import importlib.util
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import provider_prompt as owner


@pytest.fixture
def cohort(tmp_path, monkeypatch):
    monkeypatch.setattr(owner, "_LEDGER_OWNER_GENERATION", None)
    script = tmp_path / "provider_prompt.py"
    script.write_text("# selected wrapper")
    writer = tmp_path / "agent-run-ledger.py"
    writer.write_bytes((ROOT / "scripts/agent-run-ledger.py").read_bytes())
    validator = tmp_path / "validate-work-item-state.py"
    validator.write_text("import json\ndef read_current(path):\n    return json.loads(path.read_text())\n")
    members = [writer, validator]
    for name in ("mutate-work-item.py", "reducer.py", "agent-runs.schema.json"):
        path = tmp_path / name
        path.write_text("# source witness")
        members.append(path)

    def select():
        return owner._LedgerHelperBinding(
            helper=writer, script=script, script_identity=owner._ledger_file_identity(script),
            roots=(), members=tuple((p, owner._ledger_file_identity(p)) for p in members),
        )
    monkeypatch.setattr(owner, "_ledger_helper_binding", select)
    return members


def test_same_generation_reuses_modules_not_ledger_data(cohort, tmp_path):
    writer = owner._ledger_owner()
    validator = writer.load_validator()
    assert owner._ledger_owner() is writer
    assert writer.load_validator() is validator
    ledger = tmp_path / "ledger.json"
    ledger.write_text('{"current": 1}')
    assert validator.read_current(ledger) == {"current": 1}
    ledger.write_text('{"current": 2}')
    assert owner._ledger_owner().load_validator().read_current(ledger) == {"current": 2}


@pytest.mark.parametrize("member", range(5))
def test_cohort_drift_refuses_held_owner_but_new_consumer_refreshes(cohort, member):
    held = owner._ledger_owner()
    old = held.load_validator()
    path = cohort[member]
    path.write_bytes(path.read_bytes() + b"\n# changed generation\n")
    with pytest.raises(ValueError, match="DRIFT"):
        held.load_validator()
    fresh = owner._ledger_owner()
    assert fresh is not held
    assert fresh.load_validator() is not old
    with pytest.raises(ValueError, match="DRIFT"):
        held.load_validator()


def test_failed_validator_construction_is_not_cached(cohort):
    cohort[1].write_text("this is not valid Python !!!")
    writer = owner._ledger_owner()
    with pytest.raises(SyntaxError):
        writer.load_validator()
    assert writer._VALIDATOR_MODULE is None
    cohort[1].write_text("VALUE = 23")
    assert owner._ledger_owner().load_validator().VALUE == 23


def test_concurrent_construction_publishes_one_graph(cohort):
    def acquire(_):
        writer = owner._ledger_owner()
        return writer, writer.load_validator()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(acquire, range(12)))
    assert all(w is results[0][0] and v is results[0][1] for w, v in results)


def test_standalone_writer_retains_fresh_loader_semantics(cohort):
    spec = importlib.util.spec_from_file_location("standalone_test_writer", cohort[0])
    writer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(writer)
    first = writer.load_validator()
    assert writer.load_validator() is not first
    cohort[1].write_text("VALUE = 314")
    assert writer.load_validator().VALUE == 314


def test_actual_validator_reads_changed_ledger_on_reused_graph(tmp_path, monkeypatch):
    monkeypatch.setattr(owner, "_LEDGER_OWNER_GENERATION", None)
    writer = owner._ledger_owner()
    validator = writer.load_validator()
    ledger = tmp_path / "agent-runs.jsonl"
    ledger.write_text('{"runId":"first"}\n')
    first = validator.load_jsonl(ledger, [])
    ledger.write_text('{"runId":"second"}\n')
    assert owner._ledger_owner() is writer
    assert writer.load_validator() is validator
    second = validator.load_jsonl(ledger, [])
    assert first != second
    assert "second" in repr(second)


def test_different_selected_scope_never_aliases_graph(cohort, tmp_path, monkeypatch):
    from dataclasses import replace
    first = owner._ledger_owner()
    binding = first._paired_source_binding
    other = tmp_path / "other"
    other.mkdir()
    paths = []
    for path in cohort:
        dest = other / path.name
        dest.write_bytes(path.read_bytes())
        paths.append(dest)
    selected = replace(binding, helper=paths[0],
        members=tuple((p, owner._ledger_file_identity(p)) for p in paths))
    monkeypatch.setattr(owner, "_ledger_helper_binding", lambda: selected)
    second = owner._ledger_owner()
    assert second is not first
    assert second.load_validator() is not first.load_validator()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction ownership regression")
def test_reloaded_link_authority_classes_reuse_same_generation(cohort, tmp_path, monkeypatch):
    from dataclasses import replace
    import subprocess
    destination = tmp_path / "linked-destination"
    destination.mkdir()
    link = tmp_path / "linked-root"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(destination)],
                   check=True, capture_output=True)
    original_select = owner._ledger_helper_binding
    loaded = []
    def select():
        name = "_test_link_owner_" + str(len(loaded))
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/linked_runtime_subroots.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        loaded.append(module)
        authority = module.LinkedRuntimeSubrootAuthority.bind(
            link, scope="global", trusted_global_roots=(link,))
        assert authority is not None
        return replace(original_select(), authorities=(authority,))
    monkeypatch.setattr(owner, "_ledger_helper_binding", select)
    first = owner._ledger_owner()
    second = owner._ledger_owner()
    assert loaded[0].LinkedRuntimeSubrootAuthority is not loaded[1].LinkedRuntimeSubrootAuthority
    assert first is second
    assert first.load_validator() is second.load_validator()


def test_actual_paired_graph_roundtrip_and_cached_lifecycle_drift(tmp_path, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(owner, "_LEDGER_OWNER_GENERATION", None)
    selected = owner._ledger_helper_binding()
    witness = tmp_path / "generation-source"
    witness.write_text("first")
    def select():
        return replace(selected, members=selected.members + (
            (witness, owner._ledger_file_identity(witness)),))
    monkeypatch.setattr(owner, "_ledger_helper_binding", select)
    writer = owner._ledger_owner()
    validator = writer.load_validator()
    lifecycle = validator.load_lifecycle_owner()
    assert lifecycle._LIFECYCLE_MODULE_ORIGIN is lifecycle
    assert lifecycle._validator_module() is validator
    assert validator.load_lifecycle_owner() is lifecycle
    witness.write_text("second-generation")
    with pytest.raises(ValueError, match="DRIFT"):
        validator.load_lifecycle_owner()
    with pytest.raises(ValueError, match="DRIFT"):
        lifecycle._validator_module()
    fresh = owner._ledger_owner().load_validator()
    assert fresh is not validator
    assert fresh.load_lifecycle_owner()._validator_module() is fresh


def test_concurrent_actual_generation_origins_are_not_aliased(tmp_path, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(owner, "_LEDGER_OWNER_GENERATION", None)
    selected = owner._ledger_helper_binding()
    witness = tmp_path / "scope-witness"
    witness.write_text("scope-one")
    monkeypatch.setattr(owner, "_ledger_helper_binding", lambda: selected)
    first = owner._ledger_owner().load_validator()
    other = replace(selected, members=selected.members + (
        (witness, owner._ledger_file_identity(witness)),))
    monkeypatch.setattr(owner, "_ledger_helper_binding", lambda: other)
    second = owner._ledger_owner().load_validator()
    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = list(pool.map(lambda v: v.load_lifecycle_owner(), (first, second)))
    assert left is not right
    assert left._LIFECYCLE_MODULE_ORIGIN is left
    assert right._LIFECYCLE_MODULE_ORIGIN is right
    assert left._validator_module() is first
    assert right._validator_module() is second
