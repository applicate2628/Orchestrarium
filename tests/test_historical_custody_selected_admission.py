"""Candidate custody admission keeps explicit limits and the captured ledger."""

import hashlib
import json

import pytest

from test_mutate_work_item import historical_pass_fixture, tree_file_bytes


def _request(module, root, item, source, event, raw, args, **kwargs):
    return module.retain_historical_pass_custody(
        root, item.name, event["runId"], 2,
        args[args.index("--expected-raw-line-sha256") + 1],
        hashlib.sha256(raw).hexdigest(), "original-copy.md",
        hashlib.sha256(source.read_bytes()).hexdigest(), apply=True, **kwargs,
    )


@pytest.mark.parametrize("limited", ("events", "bytes"))
def test_candidate_custody_does_not_enlarge_explicit_resource_limit(tmp_path, limited):
    module, root, item, original, source, event, raw, args = historical_pass_fixture(tmp_path)
    original.unlink()
    extra = {**event, "runId": "later-neutral-terminal", "gate": "none"}
    extra.pop("artifact")
    raw += json.dumps(extra).encode() + b"\n"
    selected = item / "agent-runs.jsonl"
    selected.write_bytes(raw)
    validator = module._validator_module()
    budget = validator.resolve_ledger_resource_budget(
        1 if limited == "events" else 100,
        len(raw) - 1 if limited == "bytes" else len(raw) + 10000,
    )
    before = tree_file_bytes(root)

    with pytest.raises(module.LifecycleError) as refused:
        _request(module, root, item, source, event, raw, args, ledger_resource_budget=budget)

    assert refused.value.failure_id == "WI-LEDGER-RESOURCE-INCOMPLETE"
    assert tree_file_bytes(root) == before
    assert not (item / "review-artifact-custody").exists()


def test_candidate_custody_rejects_same_byte_new_ledger_identity_before_publication(
    tmp_path, monkeypatch
):
    module, root, item, original, source, event, raw, args = historical_pass_fixture(tmp_path)
    original.unlink()
    selected = item / "agent-runs.jsonl"
    retained = tmp_path / "original-ledger.jsonl"
    before = tree_file_bytes(root)
    original_identity = module._lifecycle_file_identity(selected.stat())
    real_association = module._historical_pass_association
    real_write = module._atomic_write
    replacements, writes = [], []

    def replace_after_candidate(*arguments, **kwargs):
        envelope = real_association(*arguments, **kwargs)
        selected.rename(retained)
        with selected.open("xb") as stream:
            stream.write(raw)
        replacements.append(module._lifecycle_file_identity(selected.stat()))
        return envelope

    def record_write(path, data, **kwargs):
        writes.append(path)
        return real_write(path, data, **kwargs)

    monkeypatch.setattr(module, "_historical_pass_association", replace_after_candidate)
    monkeypatch.setattr(module, "_atomic_write", record_write)
    with pytest.raises(module.LifecycleError) as refused:
        _request(module, root, item, source, event, raw, args)

    assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
    assert len(replacements) == 1 and replacements[0] != original_identity
    assert module._lifecycle_file_identity(selected.stat()) == replacements[0]
    assert module._lifecycle_file_identity(retained.stat()) == original_identity
    assert selected.read_bytes() == retained.read_bytes() == raw
    assert writes == []
    assert tree_file_bytes(root) == before
    assert not (item / "review-artifact-custody").exists()
