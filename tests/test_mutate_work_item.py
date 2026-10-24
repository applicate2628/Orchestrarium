import asyncio
import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(
    os.environ.get("MUTATE_WORK_ITEM_SCRIPT", ROOT / "scripts" / "mutate-work-item.py")
)
LEDGER = ROOT / "scripts" / "agent-run-ledger.py"
STATE_VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
FIXTURE = ROOT / "tests" / "fixtures" / "work-items-lifecycle-v1" / "five-item.json"
LIFECYCLE_SCHEMA_MARKER = "Lifecycle-schema: work-items-physical-v1"


def load_module():
    spec = importlib.util.spec_from_file_location("mutate_work_item", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _recover_pending_transitions(module, root):
    """Exercise each actual pending intent through its public held-owner entry."""
    for intent_path in module._iter_transition_intents(root):
        module.recover_transition(root, intent_path.stem)


def _runtime_authority_fixture(tmp_path, monkeypatch, layout="codex", linked=True):
    module = load_module()
    home = tmp_path / "synthetic-home"
    home.mkdir()
    physical = tmp_path / "runtime-backing"
    physical.mkdir()
    alias = home / (".agents" if layout == "codex" else ".claude")
    if linked:
        alias.symlink_to(physical, target_is_directory=True)
    else:
        alias.mkdir()
    runtime = alias / ("skills/lead" if layout == "codex" else "agents")
    scripts = runtime / "scripts"
    scripts.mkdir(parents=True)
    for name in ("mutate-work-item.py", "validate-work-item-state.py", "linked_runtime_subroots.py"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    schema = runtime / "shared/schemas/agent-runs.schema.json"
    schema.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "shared/schemas/agent-runs.schema.json", schema)
    monkeypatch.setattr(module, "__file__", str(scripts / "mutate-work-item.py"))
    monkeypatch.setattr(module.Path, "home", classmethod(lambda cls: home))
    subject = tmp_path / "subject"
    (subject / "work-items").mkdir(parents=True)
    return module, runtime, alias, physical, subject


@pytest.mark.parametrize("layout", ("codex", "claude"))
def test_runtime_source_authority_declared_global_load_and_reuse(tmp_path, monkeypatch, layout):
    module, runtime, alias, physical, subject = _runtime_authority_fixture(tmp_path, monkeypatch, layout)
    with module.LifecycleTransaction(subject) as tx:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(tx)
        try:
            validator = module._validator_module()
            assert module._validator_module() is validator
            assert validator._LIFECYCLE_OWNER is module
            assert validator.load_lifecycle_owner() is module
            assert validator._LIFECYCLE_OWNER.CapturedFileSnapshot is module.CapturedFileSnapshot
            assert validator._LIFECYCLE_OWNER.LifecycleError is module.LifecycleError
            assert validator._LIFECYCLE_OWNER._CURRENT_LIFECYCLE_TRANSACTION is module._CURRENT_LIFECYCLE_TRANSACTION
            assert validator._LIFECYCLE_OWNER._DIRECTORY_CAPTURE_OWNER is module._DIRECTORY_CAPTURE_OWNER
            assert validator.__file__ == str(runtime / "scripts/validate-work-item-state.py")
            assert tx._runtime_source_authority is not None
            snapshot = module._capture_runtime_source(Path("scripts/mutate-work-item.py"), failure_id="TEST")
            assert snapshot.data == SCRIPT.read_bytes()
            leaf = subject / "linked-status.md"
            leaf.symlink_to(runtime / "shared/schemas/agent-runs.schema.json")
            with pytest.raises(module.LifecycleError):
                module._capture_file_snapshot(leaf, failure_id="TEST-SUBJECT")
            parent_link = subject / "linked-parent"
            parent_link.symlink_to(runtime / "shared", target_is_directory=True)
            with pytest.raises(module.LifecycleError):
                module._capture_file_snapshot(parent_link / "schemas/agent-runs.schema.json", failure_id="TEST-SUBJECT")
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    assert tx._validator_reuse is None and tx._runtime_source_authority is not None


def test_validator_factory_binds_actual_registered_owner_for_aliases(tmp_path: Path):
    aliases = ("mutate_work_item_owner_alias_r3_a", "mutate_work_item_owner_alias_r3_b")
    standalone_name = "validator_owner_standalone_r3"
    owner_name = "work_item_lifecycle_owner_for_validation"
    names = (*aliases, standalone_name, owner_name)
    missing = object()
    saved = {name: sys.modules.get(name, missing) for name in names}

    def load_alias(name: str):
        spec = importlib.util.spec_from_file_location(name, SCRIPT)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    try:
        first, second = (load_alias(name) for name in aliases)
        first_validator = first._validator_module()
        second_validator = second._validator_module()
        for owner, validator in ((first, first_validator), (second, second_validator)):
            assert sys.modules[owner.__name__] is owner
            assert validator._LIFECYCLE_OWNER is owner
            assert validator.load_lifecycle_owner() is owner
            assert validator._LIFECYCLE_OWNER.CapturedFileSnapshot is owner.CapturedFileSnapshot
            assert validator._LIFECYCLE_OWNER.LifecycleError is owner.LifecycleError
            assert validator._LIFECYCLE_OWNER._CURRENT_LIFECYCLE_TRANSACTION is owner._CURRENT_LIFECYCLE_TRANSACTION
            assert validator._LIFECYCLE_OWNER._DIRECTORY_CAPTURE_OWNER is owner._DIRECTORY_CAPTURE_OWNER
        assert first_validator is not second_validator
        assert first_validator._LIFECYCLE_OWNER is not second_validator._LIFECYCLE_OWNER
        assert first._CURRENT_LIFECYCLE_TRANSACTION is not second._CURRENT_LIFECYCLE_TRANSACTION
        assert first._DIRECTORY_CAPTURE_OWNER is not second._DIRECTORY_CAPTURE_OWNER

        spec = importlib.util.spec_from_file_location(standalone_name, STATE_VALIDATOR)
        assert spec and spec.loader
        standalone = importlib.util.module_from_spec(spec)
        sys.modules[standalone_name] = standalone
        spec.loader.exec_module(standalone)
        assert standalone._LIFECYCLE_OWNER is None
        standalone_owner = standalone.load_lifecycle_owner()
        assert standalone._LIFECYCLE_OWNER is standalone_owner
        assert standalone_owner.__name__ == owner_name
        assert standalone_owner is not first and standalone_owner is not second
        assert standalone_owner._CURRENT_LIFECYCLE_TRANSACTION is not first._CURRENT_LIFECYCLE_TRANSACTION
        assert standalone_owner._CURRENT_LIFECYCLE_TRANSACTION is not second._CURRENT_LIFECYCLE_TRANSACTION
    finally:
        for name, previous in saved.items():
            if previous is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


@pytest.mark.parametrize(
    "origin",
    [pytest.param(None, id="missing"), pytest.param(sys, id="foreign-module"), pytest.param(object(), id="lookalike")],
)
def test_validator_factory_refuses_unqualified_lifecycle_origin(tmp_path, monkeypatch, origin):
    module, _runtime, _alias, _physical, subject = _runtime_authority_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_LIFECYCLE_MODULE_ORIGIN", origin, raising=False)
    subject_before = {
        path.relative_to(subject).as_posix(): path.read_bytes()
        for path in subject.rglob("*")
        if path.is_file()
    }
    with pytest.raises(module.LifecycleError) as refused:
        module.LifecycleTransaction(subject)
    assert refused.value.failure_id == "WI-VALIDATOR-LOAD"
    assert not (subject / module.LIFECYCLE_LOCK_RELATIVE).exists()
    assert {
        path.relative_to(subject).as_posix(): path.read_bytes()
        for path in subject.rglob("*")
        if path.is_file()
    } == subject_before


def test_standalone_validator_owners_survive_registration_replacement_and_removal(tmp_path, monkeypatch):
    _module, runtime, _alias, _physical, subject = _runtime_authority_fixture(tmp_path, monkeypatch)
    validator_path = runtime / "scripts" / "validate-work-item-state.py"
    v1_name = "validator_owner_standalone_lifetime_r3_a"
    v2_name = "validator_owner_standalone_lifetime_r3_b"
    owner_name = "work_item_lifecycle_owner_for_validation"
    names = (v1_name, v2_name, owner_name)
    missing = object()
    saved = {name: sys.modules.get(name, missing) for name in names}

    def load_standalone_validator(name: str):
        spec = importlib.util.spec_from_file_location(name, validator_path)
        assert spec and spec.loader
        validator = importlib.util.module_from_spec(spec)
        sys.modules[name] = validator
        spec.loader.exec_module(validator)
        return validator

    try:
        sys.modules.pop(owner_name, None)
        v1 = load_standalone_validator(v1_name)
        owner_a = v1.load_lifecycle_owner()
        assert sys.modules[owner_name] is owner_a
        transaction = owner_a.LifecycleTransaction(subject)
        with transaction:
            token = owner_a._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            try:
                validator_a_transaction = owner_a._validator_module()
                assert validator_a_transaction._LIFECYCLE_OWNER is owner_a
                assert owner_a._validator_module() is validator_a_transaction

                v2 = load_standalone_validator(v2_name)
                owner_b = v2.load_lifecycle_owner()
                assert owner_b is not owner_a
                assert sys.modules[owner_name] is owner_b
                assert v1.load_lifecycle_owner() is owner_a
                assert v2.load_lifecycle_owner() is owner_b
                assert owner_a._validator_module() is validator_a_transaction
            finally:
                owner_a._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
        assert transaction._validator_reuse is None
        assert v1.load_lifecycle_owner() is owner_a

        validator_a_replaced = owner_a._validator_module()
        validator_b_replaced = owner_b._validator_module()
        assert validator_a_replaced._LIFECYCLE_OWNER is owner_a
        assert validator_b_replaced._LIFECYCLE_OWNER is owner_b
        assert validator_a_replaced._LIFECYCLE_OWNER.CapturedFileSnapshot is owner_a.CapturedFileSnapshot
        assert validator_a_replaced._LIFECYCLE_OWNER.LifecycleError is owner_a.LifecycleError
        assert validator_a_replaced._LIFECYCLE_OWNER._CURRENT_LIFECYCLE_TRANSACTION is owner_a._CURRENT_LIFECYCLE_TRANSACTION
        assert validator_a_replaced._LIFECYCLE_OWNER._DIRECTORY_CAPTURE_OWNER is owner_a._DIRECTORY_CAPTURE_OWNER
        assert validator_b_replaced._LIFECYCLE_OWNER.CapturedFileSnapshot is owner_b.CapturedFileSnapshot
        assert validator_b_replaced._LIFECYCLE_OWNER.LifecycleError is owner_b.LifecycleError
        assert validator_b_replaced._LIFECYCLE_OWNER._CURRENT_LIFECYCLE_TRANSACTION is owner_b._CURRENT_LIFECYCLE_TRANSACTION
        assert validator_b_replaced._LIFECYCLE_OWNER._DIRECTORY_CAPTURE_OWNER is owner_b._DIRECTORY_CAPTURE_OWNER

        sys.modules.pop(owner_name)
        validator_a_removed = owner_a._validator_module()
        validator_b_removed = owner_b._validator_module()
        assert validator_a_removed._LIFECYCLE_OWNER is owner_a
        assert validator_b_removed._LIFECYCLE_OWNER is owner_b
        assert v1.load_lifecycle_owner() is owner_a
        assert v2.load_lifecycle_owner() is owner_b
        assert owner_a.LifecycleError is not owner_b.LifecycleError
        assert owner_a.CapturedFileSnapshot is not owner_b.CapturedFileSnapshot
        assert owner_a._CURRENT_LIFECYCLE_TRANSACTION is not owner_b._CURRENT_LIFECYCLE_TRANSACTION
        assert owner_a._DIRECTORY_CAPTURE_OWNER is not owner_b._DIRECTORY_CAPTURE_OWNER
    finally:
        for name, previous in saved.items():
            if previous is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


@pytest.mark.parametrize("fault", ("imitation", "filename", "missing-home", "relative-home", "missing-helper", "linked-leaf"))
def test_runtime_source_authority_refuses_unadmitted_origins(tmp_path, monkeypatch, fault):
    module, runtime, alias, physical, subject = _runtime_authority_fixture(tmp_path, monkeypatch)
    if fault == "imitation":
        monkeypatch.setattr(module.Path, "home", classmethod(lambda cls: tmp_path / "independent-other-home"))
    elif fault == "filename":
        monkeypatch.setattr(module, "__file__", str(runtime / "scripts/other.py"))
    elif fault == "missing-home":
        def absent(cls):
            raise RuntimeError("no home")
        monkeypatch.setattr(module.Path, "home", classmethod(absent))
    elif fault == "relative-home":
        monkeypatch.setattr(module.Path, "home", classmethod(lambda cls: Path("relative")))
    elif fault == "missing-helper":
        (runtime / "scripts/linked_runtime_subroots.py").unlink()
    else:
        leaf = runtime / "scripts/validate-work-item-state.py"
        raw = leaf.read_bytes()
        leaf.unlink()
        other = tmp_path / "validator.py"
        other.write_bytes(raw)
        leaf.symlink_to(other)
    with pytest.raises(module.LifecycleError):
        module._capture_runtime_source(Path("scripts/validate-work-item-state.py"), failure_id="TEST")


@pytest.mark.parametrize("fault", ("alias", "validator", "schema"))
def test_runtime_source_authority_reuse_rejects_drift(tmp_path, monkeypatch, fault):
    module, runtime, alias, physical, subject = _runtime_authority_fixture(tmp_path, monkeypatch)
    tx = module.LifecycleTransaction(subject)
    original_authority = tx._runtime_source_authority
    with pytest.raises(module.LifecycleError) as closing, tx:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(tx)
        try:
            module._validator_module()
            if fault == "alias":
                replacement = tmp_path / "replacement"
                shutil.copytree(physical, replacement)
                alias.unlink()
                alias.symlink_to(replacement, target_is_directory=True)
            else:
                path = runtime / ("scripts/validate-work-item-state.py" if fault == "validator" else "shared/schemas/agent-runs.schema.json")
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
            with pytest.raises(module.LifecycleError) as first:
                module._validator_module()
            assert tx._validator_reuse is None and tx._runtime_source_authority is original_authority
            move_source = subject / "move-source"
            move_source.mkdir()
            missing = subject / "not-created" / "output.md"
            for operation in (tx.verify, module._validator_module,
                              lambda: module._capture_runtime_source(Path("scripts/mutate-work-item.py"), failure_id="TEST", authority=object()),
                              lambda: tx.replace_directory(move_source, subject / "moved"),
                              lambda: module.LifecycleWriteTarget(missing, failure_id="TEST").__enter__(),
                              tx.__enter__):
                with pytest.raises(module.LifecycleError) as repeated:
                    operation()
                assert repeated.value is first.value
            assert not missing.parent.exists() and move_source.exists() and not (subject / "moved").exists()
            assert len(tx._retained_observations) == 2
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    assert closing.value is first.value and tx._file is None and not tx._locked


@pytest.mark.parametrize("fault", ("origin", "content", "compile", "spec"))
def test_runtime_source_authority_schema_failure_clears_cache(tmp_path, monkeypatch, fault):
    module, runtime, alias, physical, subject = _runtime_authority_fixture(tmp_path, monkeypatch)
    path = runtime / "scripts/validate-work-item-state.py"
    addition = "\ninvalid syntax !\n" if fault == "compile" else "\nAGENT_RUN_SCHEMA = {}\n" if fault == "content" else "\nAGENT_RUN_SCHEMA_PATH = AGENT_RUN_SCHEMA_PATH.with_name('other.json')\n"
    path.write_bytes(path.read_bytes() + addition.encode())
    tx = module.LifecycleTransaction(subject)
    original_authority = tx._runtime_source_authority
    if fault == "spec":
        monkeypatch.setattr(module.importlib.util, "spec_from_file_location", lambda *a, **kw: None)
    with pytest.raises((module.LifecycleError, SyntaxError)) as closing, tx:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(tx)
        try:
            with pytest.raises((module.LifecycleError, SyntaxError)) as first:
                module._validator_module()
            assert tx._validator_reuse is None and tx._runtime_source_authority is original_authority
            alias.unlink()
            shutil.copytree(physical, alias)
            (runtime / "scripts/validate-work-item-state.py").write_bytes(STATE_VALIDATOR.read_bytes())
            with pytest.raises(type(first.value)) as second:
                module._validator_module()
            assert second.value is first.value
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    assert closing.value is first.value and tx._file is None and not tx._locked


def test_runtime_source_failure_keeps_owned_compensation(tmp_path, monkeypatch):
    module, runtime, alias, physical, subject = _runtime_authority_fixture(tmp_path, monkeypatch)
    tx = module.LifecycleTransaction(subject)
    composer = module.LifecycleOutcomeComposer()
    composer_token = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.set(composer)
    try:
        with tx:
            token = module._CURRENT_LIFECYCLE_TRANSACTION.set(tx)
            try:
                module._validator_module()
                with module.LifecycleWriteTarget(subject / "owned.md", failure_id="TEST") as target:
                    module._atomic_write(target.path, b"owned", target=target)
                    image = target.owned_image()
                    owned_identity = module._lifecycle_file_identity(target.path.lstat())
                    assert image["identity"]["value"] == list(owned_identity)
                    owned_bytes = target.path.read_bytes()
                    alias.unlink()
                    replacement = tmp_path / "replacement"
                    shutil.copytree(physical, replacement)
                    alias.symlink_to(replacement, target_is_directory=True)
                    with pytest.raises(module.LifecycleError) as first:
                        tx.verify()
                    assert tx._source_admission_failure is first.value
                    def nested(root):
                        pytest.fail("nested body ran after source refusal")
                    with pytest.raises(module.LifecycleError) as repeated:
                        module._lifecycle_participant(nested)(subject)
                    assert repeated.value is first.value
                    with pytest.raises(module.LifecycleError) as removal:
                        target.remove_owned(target.leaf, image)
                    assert removal.value is first.value
                    assert tx._source_admission_failure is first.value
                    assert target.path.read_bytes() == owned_bytes
                    assert module._lifecycle_file_identity(target.path.lstat()) == owned_identity
            finally:
                module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
        bundle = composer.finalize()
        assert bundle.primary is first.value and not bundle.cleanup_failures
        assert tx._file is None and not tx._locked
    finally:
        module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.reset(composer_token)


def test_runtime_source_first_failure_precedes_later_body_error(tmp_path, monkeypatch):
    module, runtime, alias, physical, subject = _runtime_authority_fixture(tmp_path, monkeypatch)
    first = []
    transactions = []
    bundles = []
    original_finalize = module.LifecycleOutcomeComposer.finalize
    def record_bundle(composer):
        bundle = original_finalize(composer)
        bundles.append(bundle)
        return bundle
    monkeypatch.setattr(module.LifecycleOutcomeComposer, "finalize", record_bundle)
    def action(root):
        transactions.append(module._CURRENT_LIFECYCLE_TRANSACTION.get())
        module._validator_module()
        replacement = tmp_path / "replacement"
        shutil.copytree(physical, replacement)
        alias.unlink()
        alias.symlink_to(replacement, target_is_directory=True)
        try:
            transactions[0].verify()
        except module.LifecycleError as failure:
            first.append(failure)
        raise ValueError("later body failure")
    with pytest.raises(BaseException) as received:
        module._lifecycle_participant(action)(subject)
    assert len(first) == 1
    assert received.value is first[0]
    assert bundles[-1].primary is first[0] and not bundles[-1].cleanup_failures
    assert transactions[0]._file is None and not transactions[0]._locked


def test_runtime_source_authority_ordinary_layout_stays_strict(tmp_path, monkeypatch):
    module, runtime, alias, physical, subject = _runtime_authority_fixture(tmp_path, monkeypatch, linked=False)
    # An ordinary custom layout remains supported without global declaration.
    monkeypatch.setattr(module.Path, "home", classmethod(lambda cls: tmp_path / "unrelated-home"))
    assert module._declared_runtime_source_authority() is None
    samples = []
    def sample_once(cls):
        samples.append(True)
        return tmp_path / "unrelated-home"
    monkeypatch.setattr(module.Path, "home", classmethod(sample_once))
    with module.LifecycleTransaction(subject) as tx:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(tx)
        try:
            assert module._validator_module().AGENT_RUN_SCHEMA
            assert tx._runtime_source_authority is None
            assert module._validator_module().AGENT_RUN_SCHEMA
            assert len(samples) == 1
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def run_cli_separate_streams(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_state_validator(work_item: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(STATE_VALIDATOR), "--work-item", str(work_item)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def run_ledger(work_item: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LEDGER), "--work-item", str(work_item), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_root_contract(root: Path, auxiliary_roots: dict[str, dict[str, str]]) -> None:
    write(
        root / "work-items" / "root-contract.json",
        json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": auxiliary_roots,
            }
        )
        + "\n",
    )


def expanded_root_contract(auxiliary_names: tuple[str, ...]) -> dict[str, object]:
    return {
        "schema": "work-items-root-contract",
        "version": 2,
        "rootFiles": ["README.md", "root-contract.json"],
        "lifecycleRoots": [
            {"path": "active", "kind": "active-items"},
            {"path": "archive", "kind": "archived-items"},
        ],
        "registries": [
            {"path": "backlog", "kind": "flat-markdown"},
            *(
                {"path": name, "kind": "flat-markdown-with-month-archive"}
                for name in ("bugs", "decisions", "epics")
            ),
            {"path": "lessons", "kind": "flat-markdown"},
            {"path": "roadmaps", "kind": "flat-markdown-with-month-archive"},
        ],
        "auxiliaryRoots": [
            {"path": name, "kind": "flat-json"} for name in auxiliary_names
        ],
        "activeItemSubdirectories": ["notes"],
        "archiveRootFiles": ["README.md"],
        "historicalItemDirectoryExceptions": [
            "archive/2026-01/old-item/retained-evidence"
        ],
    }


def quick_status(task: str = "Complete bounded repair.") -> str:
    return f"""---
template: quick-fix
status: active
started: 2026-07-31T00:00:00Z
updated: 2026-07-31T00:00:00Z
---

- **Task**: {task}
- **Current step**: Execute the current step.
- **Last result**: Not started.
- **Next action**: Run the oracle.
"""


def staged_status(reopens: str) -> str:
    return f"""---
template: staged
status: active
started: 2026-07-31T00:00:00Z
updated: 2026-07-31T00:00:00Z
---

Task: Reopen the archived concern.
Current step: Create a successor.
Last result: Original concern was archived.
Next action: Verify successor identity.
Scope boundary: Successor only.
Owner: toolchain-engineer
Integration owner: toolchain-engineer
Evidence gate: successor test
Reopens: {reopens}
"""


def closure(instant: str) -> str:
    return f"""Closed: {instant}
Outcome: Lifecycle transition completed.
Evidence: focused unit test
Residual risk: None in fixture.
"""


def marked_status(status: str = "completed") -> str:
    return f"status: {status}\n{LIFECYCLE_SCHEMA_MARKER}\n"


def marked_closure(
    instant: str,
    *,
    evidence: str = "focused unit test",
) -> str:
    return closure(instant).replace(
        "Evidence: focused unit test",
        f"Evidence: {evidence}",
    ) + f"{LIFECYCLE_SCHEMA_MARKER}\n"


def seed_legacy_archives(root: Path) -> dict[Path, str]:
    work_items = root / "work-items"
    records = {
        work_items / "archive" / "2026-06" / "legacy-date": {
            "status.md": "template: quick-fix\nstatus: done\n",
            "closure.md": (
                "Closed: 2026-06-02\n"
                "Outcome: Date-only legacy outcome.\n"
                "Residual risk: Date-only legacy risk.\n"
            ),
        },
        work_items / "archive" / "2026-04" / "legacy-closed-on": {
            "status.md": "template: full-delivery\nstatus: closed\n",
            "closure.md": (
                "- Closed on: 2026-04-09\n"
                "- Outcome: Closed-on legacy outcome.\n"
                "- Residual risk: Closed-on legacy risk.\n"
            ),
        },
        work_items / "archive" / "2026-03" / "legacy-no-closed": {
            "status.md": "status: archived\n",
            "closure.md": (
                "Outcome: Missing-Closed legacy outcome.\n"
                "Residual risk: Missing-Closed legacy risk.\n"
            ),
        },
        work_items / "archive" / "2026-02" / "legacy-no-status": {
            "closure.md": "Outcome: Missing-status legacy outcome.\n",
        },
    }
    for item, files in records.items():
        for name, data in files.items():
            write(item / name, data)
    return {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for item, files in records.items()
        for name in files
        for path in (item / name,)
    }


def seed_active(module, root: Path, slug: str) -> None:
    source = root / "candidate.md"
    status = root / "status.md"
    write(source, f"Task: {slug}\nNext action: Start.\nupdated: 2026-07-31T00:00:00Z\n")
    write(status, quick_status(slug))
    module.create_candidate(root, slug, source.read_bytes())
    module.start_item(root, slug, status.read_bytes())


def test_root_aliases_share_recorded_scratch_and_real_ownership_guards(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "root-binding-item"
    seed_active(module, root, slug)
    item = root / "work-items" / "active" / slug
    write(item / "implementation.md", "Retained synthetic evidence pointer.\n")
    retained = root / ".scratch" / "work-items" / slug / "scratch-terminal-001" / "evidence"
    write(retained / "payload.txt", "Original retained bytes.\n")
    entry = {"entryId": "evidence", "path": retained.relative_to(root).as_posix(), "disposition": "retain",
             "reason": "Explicitly retained synthetic test evidence.", "canonicalPointer": "implementation.md"}
    for run_id, status, gate, kind, extra in (
        ("scratch-launch-001", "running", "none", "launch", []),
        ("scratch-terminal-001", "completed", "PASS", "terminal", ["--artifact", "implementation.md",
         "--evidence", "command:focused root contract", "--launch-run-id", "scratch-launch-001", "--scratch-evidence-json", json.dumps(entry)])):
        result = run_ledger(item, "append", "--run-id", run_id, "--role", "platform-engineer", "--execution-role", "internal",
            "--status", status, "--gate", gate, "--scope", "scratch lifecycle", "--event-kind", kind,
            "--started-at", "2026-08-09T00:00:00Z", "--updated-at", "2026-08-09T00:00:00Z", *extra)
        assert result.returncode == 0, result.stdout + result.stderr
    instant = "2026-08-11T10:00:00Z"
    write_bug_dispositions(root, slug, instant, [])
    closure_file = root / "closure.md"
    write(closure_file, closure(instant))
    extra_root = root / ".scratch" / "work-items" / slug / "unclaimed"
    write(extra_root / "payload.txt", "Undeclared owned fixture evidence.\n")
    before = tree_file_bytes(item)
    def close_at(alias):
        return run_cli("close", "--root", str(alias), "--slug", slug, "--closure-file", str(closure_file), "--terminal-instant", instant)
    for alias in (root, root / "work-items"):
        failed = close_at(alias)
        assert failed.returncode == 1 and "WI-SCRATCH-OWNERSHIP-INCOMPLETE" in failed.stdout, failed.stdout
        assert tree_file_bytes(item) == before and retained.is_dir()
    extra_root.rename(root / "held-unclaimed")
    closed = close_at(root / "work-items")
    archived = root / "work-items" / "archive" / "2026-08" / slug
    assert closed.returncode == 0 and (archived / module.BUG_DISPOSITIONS_RECEIPT).is_file(), closed.stdout
    assert close_at(root).returncode == 0
    retained.rename(root / "held-retained")
    missing = close_at(root / "work-items")
    assert missing.returncode == 1 and "WI-SCRATCH-RETAINED-EVIDENCE-MISSING" in missing.stdout, missing.stdout
    (root / "held-retained").rename(retained)
    assert (retained / "payload.txt").read_text() == "Original retained bytes.\n"
    zero = tmp_path / "zero-recorded"
    seed_active(module, zero, "zero")
    write_bug_dispositions(zero, "zero", instant, [])
    write(zero / "closure.md", closure(instant))
    write(zero / ".scratch" / "work-items" / "zero" / "unclaimed" / "data", "No declaration.\n")
    for alias in (zero, zero / "work-items"):
        failed = run_cli("close", "--root", str(alias), "--slug", "zero", "--closure-file", str(zero / "closure.md"), "--terminal-instant", instant)
        assert failed.returncode == 1 and "WI-SCRATCH-OWNERSHIP-INCOMPLETE" in failed.stdout, failed.stdout
        assert (zero / "work-items" / "active" / "zero").is_dir()


def test_held_root_role_survives_supported_basename_and_nested_scope(tmp_path: Path) -> None:
    module = load_module()
    repository = tmp_path / "work-items"
    work_items = repository / "work-items"
    work_items.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    calls = []
    @module._lifecycle_participant
    def inner(root):
        calls.append(root)
        assert root == repository and module._work_items_root(root) == work_items
        assert module._resolve_project_topology(root).repository_root == repository
        return module._CURRENT_LIFECYCLE_TRANSACTION.get()
    @module._lifecycle_participant
    def outer(root):
        held = module._CURRENT_LIFECYCLE_TRANSACTION.get()
        assert held.work_items_root == work_items and root == repository
        assert inner(work_items) is held and inner(repository) is held
        with pytest.raises(module.LifecycleError) as wrong:
            inner(foreign)
        assert wrong.value.failure_id == "WI-LIFECYCLE-LOCK-IDENTITY"
        token = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.set(None)
        try:
            with pytest.raises(module.LifecycleError):
                inner(work_items)
        finally:
            module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.reset(token)
        with pytest.raises(TypeError):
            inner(work_items, diagnostic_observer=module.LifecycleDiagnosticObserver())
    with pytest.raises(module.LifecycleError) as unbound:
        outer(work_items)
    assert "acquisition unbound" in str(unbound.value)
    outer = module._lifecycle_participant(outer.__wrapped__, input_role="repository-root")
    outer(repository)
    assert calls == [repository, repository] and module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
    linked = tmp_path / "linked-root"
    linked.symlink_to(work_items, target_is_directory=True)
    with pytest.raises(module.LifecycleError) as unsafe:
        outer(linked)
    assert unsafe.value.failure_id == "WI-LIFECYCLE-LOCK-IDENTITY"
    def seed_proved(_root):
        seed_active(module, work_items, "role-variation-item")
    module._lifecycle_participant(seed_proved, input_role="repository-root")(repository)
    instant = "2026-08-11T10:00:00Z"
    write_bug_dispositions(repository, "role-variation-item", instant, [])
    write(tmp_path / "closure.md", closure(instant))
    result = run_cli("close", "--root", str(work_items), "--slug", "role-variation-item", "--closure-file", str(tmp_path / "closure.md"), "--terminal-instant", instant)
    assert result.returncode == 0, result.stdout
    assert (work_items / "archive" / "2026-08" / "role-variation-item").is_dir() and not (repository / "active").exists()


def test_transition_subject_syntax_is_independent_of_raw_held_and_proved_roots(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    repository = tmp_path / "work-items"
    work_items = repository / "work-items"
    work_items.mkdir(parents=True)
    # The owner parser is pure even for a valid operation id, not only a failure.
    with monkeypatch.context() as patch:
        patch.setattr(module, "_resolve_project_root_identity", lambda *a, **k: pytest.fail("syntax resolved a root"))
        module._validate_transition_operation_id("known-absent-intent")
        with pytest.raises(module.LifecycleError, match="invalid transition operation id"):
            module._validate_transition_operation_id("../bad")
        with pytest.raises(TypeError):
            module._validate_transition_operation_id(None)
    def image():
        return {p.relative_to(repository).as_posix(): (p.stat().st_dev, p.stat().st_ino,
                p.stat().st_size,
                p.read_bytes() if p.is_file() and p.name != "work-items-lifecycle-owner.lock" else None)
                for p in repository.rglob("*")}
    def body(root):
        held = module._CURRENT_LIFECYCLE_TRANSACTION.get()
        before = image()
        for alias in (repository, work_items):
            for role in ("caller-root", "repository-root" if alias == repository else "work-items-root"):
                with pytest.raises(module.LifecycleError) as missing:
                    module.recover_transition(alias, "known-absent-intent", _input_role=role)
                assert missing.value.failure_id == "WI-LIFECYCLE-TRANSITION-RECOVERY-REQUIRED"
                assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is held
                assert image() == before
            with pytest.raises(module.LifecycleError, match="invalid transition operation id"):
                module.recover_transition(alias, "../bad")
            with pytest.raises(TypeError):
                module.recover_transition(alias, None)
        assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is held
    module._lifecycle_participant(body, input_role="repository-root")(repository)
    assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
    assert module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get() is None
    def seed(root):
        seed_active(module, work_items, "selected-existing")
    module._lifecycle_participant(seed, input_role="repository-root")(repository)
    for alias in (repository, work_items):
        with pytest.raises(module.LifecycleError) as missing:
            module.recover_transition(alias, "known-absent-intent")
        assert missing.value.failure_id == "WI-LIFECYCLE-TRANSITION-RECOVERY-REQUIRED"


def seed_context_bug(root: Path, item_slug: str, bug_slug: str) -> Path:
    target = root / "work-items" / "bugs" / f"{bug_slug}.md"
    write(
        target,
        (
            f"# Bug: {bug_slug}\n\n"
            f"- id: {bug_slug}\n"
            f"- context: {item_slug}\n"
            "- status: open\n"
            "- severity: medium\n"
        ),
    )
    return target


@pytest.mark.parametrize("state", ["matching", "stale", "missing", "invalid"])
def test_observe_readme_is_byte_no_write_without_scratch_and_with_epic_relation(tmp_path: Path, state: str):
    module = load_module()
    root = tmp_path / "repo"
    item = root / "work-items" / "active" / "read-model-item"
    write(item / "status.md", "status: active\nTask: Current fixture.\nCurrent step: Check.\nEpic: read-model-epic\n")
    write(root / "work-items" / "epics" / "read-model-epic.md", "status: active\n")
    readme = root / "work-items" / "README.md"
    expected = module._render_readme_bytes(root)
    if state == "matching":
        readme.write_bytes(expected)
    elif state == "stale":
        readme.write_bytes(expected.replace(b"Current fixture.", b"Old fixture."))
    elif state == "invalid":
        readme.write_bytes(b"Unmarked invalid read model.\n")
    before = {str(p.relative_to(root)): (p.lstat().st_ino, p.read_bytes() if p.is_file() else None)
              for p in root.rglob("*")}
    if state == "invalid":
        with pytest.raises(module.LifecycleError):
            module.observe_readme(root)
    else:
        observation = module.observe_readme(root)
        assert set(observation) == {"matches", "observedSha256", "expectedSha256", "inputDigest", "archiveInventory"}
        assert observation["archiveInventory"] == {"schemaVersion": 1,
            "acquisitionComplete": True, "classificationComplete": True, "unbound": []}
        assert observation["matches"] == (state == "matching")
        assert observation["expectedSha256"] == hashlib.sha256(expected).hexdigest()
        assert (observation["observedSha256"] is None) == (state == "missing")
    after = {str(p.relative_to(root)): (p.lstat().st_ino, p.read_bytes() if p.is_file() else None)
             for p in root.rglob("*")}
    assert before == after and not (root / ".scratch").exists()


def test_observe_readme_detects_injected_input_drift_without_writer_lock(tmp_path: Path):
    module = load_module()
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "drift-item" / "status.md"
    write(status, "status: active\nTask: Original.\n")
    readme = root / "work-items" / "README.md"
    readme.write_bytes(module._render_readme_bytes(root))
    original = module._render_readme_bytes
    calls = 0
    def render_then_change(*args, **kwargs):
        nonlocal calls
        data = original(*args, **kwargs)
        calls += 1
        if calls == 1:
            status.write_bytes(status.read_bytes().replace(b"Original.", b"Concurrent."))
        return data
    module._render_readme_bytes = render_then_change
    with pytest.raises(module.LifecycleError) as drift:
        module.observe_readme(root)
    assert drift.value.failure_id == "WI-README-STALE"
    assert b"Concurrent." in status.read_bytes() and not (root / ".scratch").exists()


def test_unbound_archive_inventory_projects_every_leaf_and_preserves_selected_authority(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    archive = root / "work-items" / "archive"
    for name in ("ordinary-collection", "other-collection"):
        collection = archive / "2026-07" / name
        collection.mkdir(parents=True)
        (collection / "record.any").write_bytes(b"Narrative CLOSED 2026-07-09\n")
        (collection / "binary-leaf").write_bytes(b"\xff\x00unknown")
    original = tree_file_bytes(archive)
    observations = []
    module.refresh_readme(root, allow_marker_bootstrap=True, archive_inventory_out=observations)
    inventory = observations[0]
    assert inventory["acquisitionComplete"] is True and inventory["classificationComplete"] is False
    assert len(inventory["unbound"]) == 6
    board = (root / "work-items" / "README.md").read_text(encoding="utf-8")
    for row in inventory["unbound"]:
        assert f"- [ ] [{row['path']}]({row['path']})" in board
        assert row["diagnostic"] == "WI-ARCHIVE-ENTITY-UNBOUND"
        if row["kind"] == "leaf":
            assert row["sha256"] == hashlib.sha256((root / "work-items" / row["path"]).read_bytes()).hexdigest()
    before = tree_file_bytes(root)
    assert module.observe_readme(root)["archiveInventory"] == inventory
    module.check_readme(root)
    assert tree_file_bytes(root) == before
    with pytest.raises(module.LifecycleError, match="unresolved archive entities"):
        module.audit(root)
    for reference in ("work-item:ordinary-collection", "work-item:record"):
        with pytest.raises(module.LifecycleError) as failure:
            module.resolve_category(root, reference)
        assert failure.value.failure_id == "WI-ARCHIVE-ENTITY-UNBOUND"
    with pytest.raises(module.LifecycleError) as selected:
        module.resolve_legacy_path(root, "work-items/archive/2026-07/ordinary-collection/record.any")
    assert selected.value.failure_id == "WI-ARCHIVE-ENTITY-UNBOUND"
    module.create_candidate(root, "unrelated", b"Task: Unrelated admitted work.\n")
    module.start_item(root, "unrelated", quick_status("unrelated").encode())
    assert tree_file_bytes(archive) == original


def test_archive_membership_uses_exact_name_order_and_still_rejects_real_drift(tmp_path: Path) -> None:
    from pathlib import PureWindowsPath
    module = load_module()
    root = tmp_path / "repo"
    collection = root / "work-items" / "archive" / "2026-07" / "collection"
    collection.mkdir(parents=True)
    names = ("alpha.md", "Zeta.md", "Beta.md", "beta.md")
    # Casefold ties must have an exact-name total order, even on a host that
    # cannot create both names physically in this fixture directory.
    expected = sorted(names)
    assert [p.name for p in sorted(map(PureWindowsPath, reversed(names)), key=lambda p: p.name)] == expected
    for name in names:
        try:
            with (collection / name).open("xb") as stream:
                stream.write(name.encode())
        except FileExistsError:
            assert name == "beta.md" and (collection / "Beta.md").is_file()
    inventory = module._archive_entity_inventory(root)
    inventory.verify()
    captured = next(row[2] for row in inventory.directories if row[0] == collection)
    assert captured == tuple(sorted(path.name for path in collection.iterdir()))
    (collection / "Zeta.md").unlink()
    with pytest.raises(module.LifecycleError) as removal:
        inventory.verify()
    assert removal.value.failure_id == "WI-README-STALE"
    (collection / "Zeta.md").write_bytes(b"Zeta.md")
    inventory = module._archive_entity_inventory(root)
    (collection / "alpha.md").rename(collection / "renamed-leaf")
    with pytest.raises(module.LifecycleError) as rename:
        inventory.verify()
    assert rename.value.failure_id == "WI-README-STALE"
    (collection / "renamed-leaf").rename(collection / "alpha.md")
    inventory = module._archive_entity_inventory(root)
    collection.rename(root / "held-collection")
    collection.mkdir()
    for path in (root / "held-collection").iterdir():
        (collection / path.name).write_bytes(path.read_bytes())
    with pytest.raises(module.LifecycleError) as identity:
        inventory.verify()
    assert identity.value.failure_id == "WI-README-STALE"


def test_archive_inventory_detects_drift_and_rejects_mixed_collection(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    collection = root / "work-items" / "archive" / "2026-07" / "collection"
    collection.mkdir(parents=True)
    (collection / "leaf").write_bytes(b"original")
    inventory = module._archive_entity_inventory(root)
    (collection / "new-leaf").write_bytes(b"new")
    with pytest.raises(module.LifecycleError) as drift:
        inventory.verify()
    assert drift.value.failure_id == "WI-README-STALE"
    (collection / "new-leaf").unlink()
    (collection / "leaf").write_bytes(b"concurrent leaf bytes")
    with pytest.raises(module.LifecycleError) as byte_drift:
        inventory.verify()
    assert byte_drift.value.failure_id == "WI-README-STALE"
    direct = collection.parent / "unexpected"
    direct.write_bytes(b"unsupported direct data")
    before = tree_file_bytes(root)
    observed = module.observe_readme(root)
    assert observed["archiveInventory"]["classificationComplete"] is False
    assert any(entity.kind == "archive-metadata" and entity.path == direct
               for entity in module._archive_entity_inventory(root).entities)
    assert tree_file_bytes(root) == before
    direct.unlink()
    (collection / "nested").mkdir()
    before = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as mixed:
        module.observe_readme(root)
    assert mixed.value.failure_id == "WI-ARCHIVE-ENTITY-UNBOUND"
    assert tree_file_bytes(root) == before


def test_noncanonical_evidence_domain_is_lexical_and_owned_input_still_refuses(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    outer = root / "work-items" / "archive" / "arbitrary-evidence-tree"
    write(outer / "direct.any", "Non-owning evidence.\n")
    child = outer / "attachments"
    write(child / "anything", "Not lifecycle authority.\n")
    write(child / "nested" / "closure.md", "Nested attachment only.\n")
    before = tree_file_bytes(outer)
    assert module.collect_readme_entries(root) == []
    module.refresh_readme(root)
    assert module.audit(root) == ()
    assert module._category_locations(root, module.CATEGORIES["work-item"], child.name) == []
    assert tree_file_bytes(outer) == before
    write(child / "status.md", marked_status())
    assert module._category_locations(root, module.CATEGORIES["work-item"], child.name) == [child]
    with pytest.raises(module.LifecycleError) as failure:
        module.collect_readme_entries(root)
    assert failure.value.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"


def test_direct_archive_metadata_restores_public_resolve_board_and_close(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    seed_active(module, root, "selected-item")
    archive = root / "work-items" / "archive"
    month = archive / "2026-06"
    month.mkdir(parents=True)
    baseline = (root / "work-items" / "README.md").read_bytes()
    monthly = month / "README.md"
    monthly.write_bytes(b"# Monthly archive guide\n\nSynthetic prose metadata; no terminal authority.\n")
    assert hashlib.sha256(monthly.read_bytes()).hexdigest() == "18077d573cfca832a938e2b70df63feee1d127c5d076190e73349b54990c69e4"
    (archive / "selected-item.md").write_bytes(b"\xff\x00opaque")
    (archive / "empty-data").write_bytes(b"")
    (month / "task-shaped.data").write_bytes(b"Closed: 2099-01-01T00:00:00Z\nUpdated: 2099-01-01T00:00:00Z\nstatus: completed\n")
    before = tree_file_bytes(archive)
    identities = {path: (path.lstat().st_dev, path.lstat().st_ino) for path in archive.rglob("*")}
    for selection in (("--reference", "work-item:selected-item"), ("--legacy-path", "work-items/active/selected-item")):
        result = run_cli("resolve", "--root", str(root), *selection)
        assert result.returncode == 0, result.stdout
        expected_prefix = "WI-LEGACY-READ-COMPAT " if selection[0] == "--legacy-path" else ""
        assert result.stdout.strip() == expected_prefix + str(root / "work-items" / "active" / "selected-item")
    refreshed = run_cli("refresh", "--root", str(root))
    assert refreshed.returncode == 0, refreshed.stdout
    board = (root / "work-items" / "README.md").read_bytes()
    assert b"## Archive metadata" not in baseline and b"## Archive metadata" in board
    assert next(line for line in baseline.splitlines() if line.startswith(b"Canonical changes through:")) == next(
        line for line in board.splitlines() if line.startswith(b"Canonical changes through:"))
    section = board.decode().split("## Archive metadata\n", 1)[1]
    assert "- [ ]" not in section and "- [x]" not in section
    for relative, data in before.items():
        link = "archive/" + Path(relative).as_posix()
        assert f"[{link}]({link})" in section and hashlib.sha256(data).hexdigest() in section
    observation = module.observe_readme(root)
    assert observation["matches"] is True
    assert observation["archiveInventory"] == {"schemaVersion": 1, "acquisitionComplete": True,
        "classificationComplete": True, "unbound": []}
    # Bind the independently known fixture inputs, so omitted metadata source
    # paths cannot pass by comparing the producer with itself.
    inputs = {"active/selected-item/status.md": (root / "work-items" / "active" / "selected-item" / "status.md").read_bytes()}
    inputs.update({"archive/" + Path(relative).as_posix(): data for relative, data in before.items()})
    expected_digest = hashlib.sha256()
    for relative, data in sorted(inputs.items()):
        encoded = relative.encode()
        expected_digest.update(len(encoded).to_bytes(8, "big") + encoded + len(data).to_bytes(8, "big") + data)
    assert observation["inputDigest"] == expected_digest.hexdigest()
    module.check_readme(root)
    assert module.audit(root) == ()
    assert identities == {path: (path.lstat().st_dev, path.lstat().st_ino) for path in archive.rglob("*")}
    module.reset_readme_static_guide(root, hashlib.sha256(board).hexdigest())
    instant = "2026-08-11T10:07:00Z"
    write_bug_dispositions(root, "selected-item", instant, [])
    archived = module.close_item(root, "selected-item", closure(instant).encode(), instant)
    assert archived.is_dir() and (archived / module.BUG_DISPOSITIONS_RECEIPT).is_file()
    assert all((archive / relative).read_bytes() == data for relative, data in before.items())


def test_observe_rejects_same_byte_metadata_identity_replacement_between_renders(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    metadata = root / "work-items" / "archive" / "2026-06" / "metadata"
    write(metadata, "Closed: 2099-01-01T00:00:00Z\nNon-authorizing metadata.\n")
    original = metadata.read_bytes()
    old_identity = module._lifecycle_file_identity(metadata.lstat())
    held = root / "held-original-metadata"
    readme = root / "work-items" / "README.md"
    readme.write_bytes(module._render_readme_bytes(root))
    before = readme.read_bytes()
    assert module.observe_readme(root)["matches"] is True
    render = module._render_readme_bytes
    calls = 0
    def render_then_replace(*args, **kwargs):
        nonlocal calls
        data = render(*args, **kwargs)
        calls += 1
        if calls == 1:
            metadata.rename(held)
            metadata.write_bytes(original)
            assert module._lifecycle_file_identity(held.lstat()) == old_identity
            assert module._lifecycle_file_identity(metadata.lstat()) != old_identity
        return data
    module._render_readme_bytes = render_then_replace
    with pytest.raises(module.LifecycleError) as changed:
        module.observe_readme(root)
    assert changed.value.failure_id == "WI-README-STALE" and calls == 2
    assert metadata.read_bytes() == held.read_bytes() == original
    assert readme.read_bytes() == before and not (root / ".scratch").exists()


def test_archive_metadata_defaults_native_link_and_drift_stay_strict(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    leaf = root / "work-items" / "archive" / "empty"
    leaf.parent.mkdir(parents=True)
    leaf.write_bytes(b"")
    inventory = module._archive_entity_inventory(root)
    entity = inventory.entities[0]
    assert entity.kind == "archive-metadata" and entity.snapshots[0].data == b""
    for kind, reference, snapshots in (("archive-metadata", None, ()), ("unknown", None, entity.snapshots),
            ("archive-metadata", "work-item:empty", entity.snapshots), ("archive-metadata", None, (None,))):
        with pytest.raises(module.LifecycleError) as invalid:
            module.ArchiveEntity(leaf, kind, reference, snapshots)
        assert invalid.value.failure_id == "WI-ARCHIVE-ENTITY-UNBOUND"
    with pytest.raises(module.LifecycleError) as migration:
        module._validated_migration_payload_target(root, module.CATEGORIES["bug"], "empty", leaf)
    assert migration.value.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    leaf.write_bytes(b"concurrent bytes")
    with pytest.raises(module.LifecycleError) as drift:
        inventory.verify()
    assert drift.value.failure_id == "WI-README-STALE"
    render = module._render_readme_bytes
    calls = 0
    def render_then_change(*args, **kwargs):
        nonlocal calls
        data = render(*args, **kwargs)
        calls += 1
        if calls == 1:
            leaf.write_bytes(b"late metadata bytes")
        return data
    module._render_readme_bytes = render_then_change
    with pytest.raises(module.LifecycleError) as late:
        module.observe_readme(root)
    assert late.value.failure_id == "WI-README-STALE" and not (root / ".scratch").exists()
    unsafe = tmp_path / "unsafe"
    month = unsafe / "work-items" / "archive" / "2026-06"
    month.mkdir(parents=True)
    canary = tmp_path / "outside-canary"
    canary.write_bytes(b"canary bytes")
    (month / "README.md").symlink_to(canary)
    captures = []
    def profile(frame, event, arg):
        if event == "call" and frame.f_code is module._capture_file_snapshot.__code__:
            captures.append(frame.f_locals["path"])
    sys.setprofile(profile)
    try:
        with pytest.raises(module.LifecycleError) as linked:
            module._archive_entity_inventory(unsafe)
    finally:
        sys.setprofile(None)
    assert linked.value.failure_id == "WI-ARCHIVE-ENTITY-UNBOUND" and captures == []
    assert canary.read_bytes() == b"canary bytes"


def _unrelated_current_status_record(root: Path, kind: str) -> tuple[Path, str, str]:
    if kind == "backlog":
        path = root / "work-items" / "backlog" / "distant-candidate.md"
        status, failure = "open", "WI-CATEGORY-STATUS-INVALID"
        text = f"Task: Distant candidate.\nstatus: {status}\n"
    elif kind == "active":
        path = root / "work-items" / "active" / "alternate-active" / "status.md"
        status, failure = "unexpected-active", "WI-CATEGORY-STATUS-INVALID"
        text = f"Task: Alternate active item.\nstatus: {status}\n"
    else:
        path = root / "work-items" / "roadmaps" / "alternate-horizon.md"
        status, failure = "superseded", "WI-CATEGORY-TERMINAL-IN-CURRENT"
        text = f"Format: roadmap-v1\nstatus: {status}\n"
    write(path, text)
    return path, status, failure


@pytest.mark.parametrize("kind", ["backlog", "active", "roadmap"])
def test_local_close_projects_unrelated_current_status_diagnostics(tmp_path: Path, kind: str) -> None:
    module = load_module()
    root = tmp_path / kind
    slug = "bounded-close"
    instant = "2026-10-03T01:00:00Z"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "preserved-bug")
    write_bug_dispositions(root, slug, instant, [{
        "id": bug.stem, "action": "preserve-current", "status": "open",
        "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
        "reason": "Retain independent finding.", "evidence": "Synthetic accepted residual.",
    }])
    unrelated, value, failure = _unrelated_current_status_record(root, kind)
    before = {path: path.read_bytes() for path in (unrelated, bug)}

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert archived == root / "work-items" / "archive" / "2026-10" / slug
    assert all(path.read_bytes() == data for path, data in before.items())
    readme = root / "work-items" / "README.md"
    text = readme.read_text(encoding="utf-8")
    blockers = text.split("## Blockers\n", 1)[1].split("\n## ", 1)[0]
    source_link = unrelated.relative_to(root / "work-items").as_posix()
    assert "- [ ]" in blockers and failure in blockers and value in blockers
    assert source_link in blockers
    assert hashlib.sha256(before[unrelated]).hexdigest() in blockers
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_bytes())
    assert receipt["readmeSha256"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    after = tree_file_bytes(root)
    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived
    assert tree_file_bytes(root) == after
    audit = run_cli("audit", "--root", str(root))
    assert audit.returncode == 1 and failure in audit.stdout, audit.stdout
    assert tree_file_bytes(root) == after


def test_local_index_keeps_selected_candidate_and_start_strict(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "selected"
    module.create_candidate(root, "valid-seed", b"Task: Legacy candidate without status.\n")
    before = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as created:
        module.create_candidate(root, "invalid-selected", b"status: open\nTask: Invalid candidate.\n")
    assert created.value.failure_id == "WI-README-STALE"
    assert tree_file_bytes(root) == before
    selected = root / "work-items" / "backlog" / "valid-seed.md"
    selected.write_bytes(b"status: open\nTask: Selected invalid candidate.\n")
    before = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as started:
        module.start_item(root, "valid-seed", quick_status().encode())
    assert started.value.failure_id == "WI-CATEGORY-STATUS-INVALID"
    assert tree_file_bytes(root) == before


@pytest.mark.parametrize("status_value,failure_id", [
    ("unexpected-active", "WI-CATEGORY-STATUS-INVALID"),
    ("closed", "WI-CATEGORY-TERMINAL-IN-CURRENT"),
])
def test_local_update_refuses_invalid_selected_source(
    tmp_path: Path, status_value: str, failure_id: str,
) -> None:
    module = load_module()
    root = tmp_path / status_value
    slug = "selected-update"
    seed_active(module, root, slug)
    source = root / "work-items" / "active" / slug / "status.md"
    original = source.read_text(encoding="utf-8")
    assert "status: active\n" in original
    write(source, original.replace("status: active\n", f"status: {status_value}\n"))
    assert module._parse_fields(source.read_text(encoding="utf-8"))["status"] == status_value
    module.refresh_readme(root)
    replacement = tmp_path / "replacement.md"
    replacement.write_bytes(quick_status("Valid replacement.").encode())
    before = tree_file_bytes(root)

    result = run_cli("update", "--root", str(root), "--slug", slug, "--status-file", str(replacement))

    assert result.returncode == 1 and failure_id in result.stdout, result.stdout
    assert tree_file_bytes(root) == before


def test_local_update_accepts_valid_selected_source_with_unrelated_diagnostic(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "control"
    slug = "selected-update"
    seed_active(module, root, slug)
    unrelated, value, failure = _unrelated_current_status_record(root, "active")
    unrelated_before = unrelated.read_bytes()
    module.refresh_readme(root)
    replacement = tmp_path / "replacement.md"
    replacement.write_bytes(quick_status("Valid replacement.").encode())

    result = run_cli("update", "--root", str(root), "--slug", slug, "--status-file", str(replacement))

    assert result.returncode == 0, result.stdout
    assert (root / "work-items" / "active" / slug / "status.md").read_bytes() == replacement.read_bytes()
    assert unrelated.read_bytes() == unrelated_before
    readme = (root / "work-items" / "README.md").read_text(encoding="utf-8")
    blockers = readme.split("## Blockers\n", 1)[1].split("\n## ", 1)[0]
    assert "- [ ]" in blockers and failure in blockers and value in blockers
    assert hashlib.sha256(unrelated_before).hexdigest() in blockers


def test_local_index_omission_compatibility_and_non_v1_exclusion(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "legacy-backlog"
    write(root / "work-items" / "backlog" / "missing.md", "Task: Missing legacy status.\n")
    write(root / "work-items" / "backlog" / "empty.md", "status:\nTask: Empty legacy status.\n")
    write(root / "work-items" / "roadmaps" / "non-v1.md", "status: superseded\n")
    entries = module.collect_readme_entries(root)
    assert [entry.logical_reference for entry in entries] == ["work-item:empty", "work-item:missing"]
    assert all(entry.section == "Next actions" for entry in entries)
    for kind in ("active", "roadmap"):
        for value in (None, ""):
            case_root = tmp_path / f"{kind}-{'missing' if value is None else 'empty'}"
            source = (
                case_root / "work-items" / "active" / "record" / "status.md"
                if kind == "active" else case_root / "work-items" / "roadmaps" / "record.md"
            )
            data = ("Format: roadmap-v1\n" if kind == "roadmap" else "")
            if value is not None:
                data += "status:\n"
            write(source, data)
            module.refresh_readme(case_root, allow_marker_bootstrap=True)
            projected = module.collect_readme_entries(case_root)
            assert len(projected) == 1 and projected[0].section == "Blockers"
            before = tree_file_bytes(case_root)
            with pytest.raises(module.LifecycleError):
                module.audit(case_root)
            assert tree_file_bytes(case_root) == before


def test_local_index_direct_shadow_and_both_precomputers_agree(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "views"
    slug = "view-selected"
    instant = "2026-10-03T02:00:00Z"
    seed_active(module, root, slug)
    unrelated, _, _ = _unrelated_current_status_record(root, "backlog")
    unrelated_before = unrelated.read_bytes()
    module.refresh_readme(root)
    work_items = root / "work-items"
    source = work_items / "bugs" / "view-bug.md"
    source_after = b"status: fixed\n"
    write(source, "status: open\n")
    archive_bug = work_items / "bugs" / "archive" / "2026-10" / source.name
    predicted_bug = module._precompute_single_bug_readme_sha256(root, source, archive_bug, source_after, [])
    bug_shadow = tmp_path / "bug-shadow"
    shutil.copytree(work_items, bug_shadow / "work-items")
    shadow_source = bug_shadow / "work-items" / source.relative_to(work_items)
    shadow_target = bug_shadow / "work-items" / archive_bug.relative_to(work_items)
    shadow_source.write_bytes(source_after)
    shadow_target.parent.mkdir(parents=True)
    shadow_source.rename(shadow_target)
    assert predicted_bug == hashlib.sha256(module.render_readme_bytes(bug_shadow)).hexdigest()
    active = work_items / "active" / slug
    archive = work_items / "archive" / "2026-10" / slug
    successor = work_items / "backlog" / "view-successor.md"
    status_after = module._terminalize_status((active / "status.md").read_bytes())
    closure_after = module._stamp_schema_marker(closure(instant).encode(), "closure.md")
    successor_data = b"status: candidate\nTask: View successor.\n"
    predicted_transition = module._precompute_transition_readme_sha256(
        root, active, archive, successor, status_after, closure_after, successor_data, (),
    )
    transition_shadow = tmp_path / "transition-shadow"
    shutil.copytree(work_items, transition_shadow / "work-items")
    shadow_active = transition_shadow / "work-items" / active.relative_to(work_items)
    shadow_archive = transition_shadow / "work-items" / archive.relative_to(work_items)
    (shadow_active / "status.md").write_bytes(status_after)
    (shadow_active / "closure.md").write_bytes(closure_after)
    shadow_archive.parent.mkdir(parents=True)
    shadow_active.rename(shadow_archive)
    (transition_shadow / "work-items" / successor.relative_to(work_items)).write_bytes(successor_data)
    assert predicted_transition == hashlib.sha256(module.render_readme_bytes(transition_shadow)).hexdigest()
    assert unrelated.read_bytes() == unrelated_before


def test_local_index_keeps_uncertain_sources_and_selected_close_strict(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-10-03T03:00:00Z"
    for case in ("duplicate", "unreadable", "relation", "selected-missing", "selected-empty"):
        root = tmp_path / case
        slug = "strict-local-target"
        seed_active(module, root, slug)
        write_empty_bug_dispositions(root, slug, instant)
        unrelated = root / "work-items" / "active" / "distant-record" / "status.md"
        if case == "duplicate":
            write(unrelated, "status: unexpected-active\n")
            write(root / "work-items" / "backlog" / "distant-record.md", "status: candidate\n")
        elif case == "unreadable":
            unrelated.parent.mkdir(parents=True)
            unrelated.write_bytes(b"status: unexpected-active\n\xff")
        elif case == "relation":
            write(unrelated, "status: unexpected-active\nRoadmap: missing-roadmap\n")
        else:
            status = root / "work-items" / "active" / slug / "status.md"
            replacement = "" if case == "selected-missing" else "status:\n"
            original = status.read_text(encoding="utf-8")
            assert "status: active\n" in original
            write(status, original.replace("status: active\n", replacement))
            assert module._parse_fields(status.read_text(encoding="utf-8")).get("status") in {None, ""}
        before = tree_file_bytes(root)
        with pytest.raises((module.LifecycleError, UnicodeDecodeError)):
            module.close_item(root, slug, closure(instant).encode(), instant)
        assert tree_file_bytes(root) == before, case
        assert not (root / "work-items" / "archive" / "2026-10" / slug).exists()


@pytest.mark.parametrize("owner_state", ["absent", "unheld", "wrong", "off-root"])
def test_structural_directory_requires_explicit_held_owner_before_effect(tmp_path, owner_state):
    module = load_module()
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    destination = root / "work-items" / "archive" / "2026-10"
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            selected = transaction
            if owner_state == "absent":
                selected = None
            elif owner_state in {"unheld", "wrong"}:
                selected = module.LifecycleTransaction(root)
            elif owner_state == "off-root":
                destination = tmp_path / "foreign" / "archive"
            if owner_state == "wrong":
                wrong_token = module._CURRENT_LIFECYCLE_TRANSACTION.set(selected)
                try:
                    with pytest.raises(module.LifecycleError):
                        module.LifecycleWriteTarget.make_directories(destination, transaction)
                finally:
                    module._CURRENT_LIFECYCLE_TRANSACTION.reset(wrong_token)
            else:
                with pytest.raises(module.LifecycleError):
                    module.LifecycleWriteTarget.make_directories(destination, selected)
            assert not destination.parent.exists()
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_structural_directory_native_creation_settles_and_owns_empty_rollback(tmp_path, monkeypatch):
    module = load_module()
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    destination = root / "work-items" / "archive" / "2026-10"
    observations = []
    verify_snapshot = module._verify_owned_directory_snapshot
    def verify_removal(snapshot, failure_id, *, creation_owner=None):
        removal = creation_owner._source_observation if creation_owner is not None else None
        if removal is not None:
            assert removal.source == snapshot.path and removal.destination is None
            assert removal.source_owner is creation_owner and removal.handle is not None
            assert removal.current_pair_is_bound()
            observations.append(removal)
        return verify_snapshot(snapshot, failure_id, creation_owner=creation_owner)
    monkeypatch.setattr(module, "_verify_owned_directory_snapshot", verify_removal)
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            records = module.LifecycleWriteTarget.make_directories(destination, transaction)
            assert [record.locator for record in records] == [destination.parent, destination]
            assert all(record.creator and record.creation_published and record.finished
                       and record.release_complete and record.identity == module._lifecycle_file_identity(record.locator.lstat())
                       for record in records)
            if os.name == "nt":
                assert all(record.native_result == 2 for record in records)
            assert module.LifecycleWriteTarget.make_directories(destination, transaction) == ()
            transaction.verify()
            for record in reversed(records):
                module.LifecycleWriteTarget.remove_created_directory(record, transaction)
            assert len(observations) == len(records)
            assert all(removal.owner._source_observation is None and not removal.owner._open
                       for removal in observations)
            assert not destination.parent.exists()
            transaction.verify()
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_structural_directory_unpublished_abort_retains_actual_creator_result(tmp_path, monkeypatch):
    module = load_module()
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    destination = root / "work-items" / "archive"
    original = module.LifecycleWriteTarget._publish_effect
    failure = module.LifecycleError("TEST-PUBLICATION", "controlled pre-publication failure")
    def refuse(owner, prepared, identity):
        if prepared.directory and prepared.source is None and prepared.destination == destination:
            raise failure
        return original(owner, prepared, identity)
    monkeypatch.setattr(module.LifecycleWriteTarget, "_publish_effect", refuse)
    records = []
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            with pytest.raises(module.LifecycleError) as failed:
                module.LifecycleWriteTarget.make_directories(destination, transaction, created=records)
            assert failed.value is failure
            assert len(records) == 1
            record = records[0]
            assert record.creator and record.finished and record.release_complete
            assert record.deletion_accepted and record.projection_complete
            assert record.primary is failure and record.phase == "disposed"
            assert not destination.exists()
            transaction.verify()
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


@pytest.mark.skipif(os.name != "nt", reason="Windows native creator sharing boundary")
@pytest.mark.parametrize("retarget", ["child", "parent"])
def test_structural_directory_windows_native_create_prevents_retarget(tmp_path, monkeypatch, retarget):
    module = load_module()
    root = tmp_path / "repo"
    existing = root / "work-items" / "archive"
    existing.mkdir(parents=True)
    destination = existing / "2026-10"
    original = module.LifecycleWriteTarget._publish_effect
    attempts = []
    def probe(owner, prepared, identity):
        if prepared.directory and prepared.source is None and prepared.destination == destination:
            record = owner._creations[-1]
            assert record.native_result == 2 and owner._identity(record.handle) == identity
            selected = destination if retarget == "child" else existing
            with pytest.raises(OSError) as denied:
                selected.rename(selected.with_name(selected.name + "-substituted"))
            attempts.append(denied.value.winerror)
            assert owner._identity(record.handle) == module._lifecycle_file_identity(destination.lstat())
        return original(owner, prepared, identity)
    monkeypatch.setattr(module.LifecycleWriteTarget, "_publish_effect", probe)
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            records = module.LifecycleWriteTarget.make_directories(destination, transaction)
            assert len(records) == 1 and len(attempts) == 1
            assert records[0].finished and records[0].release_complete
            # Ordinary readers work after the delete-capable creator is settled.
            assert module._capture_owned_directory_snapshot(destination, failure_id="TEST").members == ()
            transaction.verify()
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


@pytest.mark.parametrize("foreign", ["replacement", "nonempty"])
def test_structural_directory_rollback_preserves_foreign_or_nonempty_state(tmp_path, foreign):
    module = load_module()
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    destination = root / "work-items" / "archive"
    with pytest.raises(module.LifecycleError):
        with module.LifecycleTransaction(root) as transaction:
            token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            try:
                record, = module.LifecycleWriteTarget.make_directories(destination, transaction)
                if foreign == "replacement":
                    destination.rename(root / "held-original")
                    destination.mkdir()
                else:
                    (destination / "foreign.txt").write_bytes(b"Preserve this author state.\n")
                with pytest.raises(module.LifecycleError):
                    module.LifecycleWriteTarget.remove_created_directory(record, transaction)
                assert destination.is_dir()
                if foreign == "nonempty":
                    assert (destination / "foreign.txt").read_bytes() == b"Preserve this author state.\n"
            finally:
                module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    assert destination.is_dir()


def test_lifecycle_prediction_failure_restores_tokens_after_disposable_cleanup(tmp_path, monkeypatch):
    module = load_module()
    root = tmp_path / "repo"
    bug, _ = seed_fixed_bug_with_active_parent(module, root, "prediction-exception")
    failure = RuntimeError("controlled shadow write failure")
    original_write = module._atomic_write
    original_cleanup = module.tempfile.TemporaryDirectory.cleanup
    cleanups = []
    def fail_shadow(path, *args, **kwargs):
        if not path.is_relative_to(root):
            assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
            assert module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get() is None
            raise failure
        return original_write(path, *args, **kwargs)
    def cleanup(temporary):
        cleanups.append((module._CURRENT_LIFECYCLE_TRANSACTION.get(),
                         module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()))
        return original_cleanup(temporary)
    monkeypatch.setattr(module, "_atomic_write", fail_shadow)
    monkeypatch.setattr(module.tempfile.TemporaryDirectory, "cleanup", cleanup)
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        composer = object()
        composer_token = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.set(composer)
        try:
            with pytest.raises(RuntimeError) as failed:
                module._precompute_single_bug_readme_sha256(root, bug,
                    root / "work-items/bugs/archive/2026-10/prediction-exception.md", bug.read_bytes(), [])
            assert failed.value is failure
            assert cleanups == [(None, None)]
            assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is transaction
            assert module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get() is composer
            monkeypatch.setattr(module, "_atomic_write", original_write)
            with pytest.raises(module.LifecycleError, match="escapes admitted repository"):
                module._atomic_write(tmp_path / "off-root.md", b"No canonical authority.\n")
            assert not (tmp_path / "off-root.md").exists()
        finally:
            module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.reset(composer_token)
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def seed_fixed_bug_with_active_parent(module, root: Path, slug: str) -> tuple[Path, Path]:
    parent_slug = "fixed-bug-parent"
    seed_active(module, root, parent_slug)
    bug = seed_context_bug(root, parent_slug, slug)
    bug.write_text(
        bug.read_text(encoding="utf-8").replace("- status: open", "- status: fixed"),
        encoding="utf-8",
    )
    parent_status = root / "work-items" / "active" / parent_slug / "status.md"
    parent_status.write_bytes(
        parent_status.read_bytes()
        + f"Related: bug:{slug}\n[physical](../../bugs/{slug}.md#proof)\n".encode()
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    return bug, parent_status


def test_archive_fixed_bug_active_parent_links_receipt_and_exact_replay(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-fixed-bug"
    instant = "2026-09-26T12:00:00Z"
    resolution = "The reported filesystem defect is fixed."
    evidence = "Focused test receipt: 9 of 9 passing."
    bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
    bug_before = bug.read_bytes()
    status_before = status.read_bytes()
    ledger = status.parent / "agent-runs.jsonl"
    ledger_before = ledger.read_bytes() if ledger.exists() else None
    expected_href = f"../../bugs/archive/2026-09/{slug}.md#proof"
    command = (
        "archive-fixed-bug", "--root", str(root), "--slug", slug,
        "--terminal-instant", instant, "--resolution", resolution,
        "--evidence", evidence, "--apply",
    )

    result = run_cli(*command)

    assert result.returncode == 0, result.stdout
    assert "WI-FIXED-BUG-ARCHIVE-COMMITTED" in result.stdout
    archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
    receipt_path = archive.with_name(f"{slug}.fixed-archive-receipt.json")
    readme = root / "work-items" / "README.md"
    assert not bug.exists()
    assert archive.is_file()
    fields = module._parse_fields(archive.read_text(encoding="utf-8"))
    assert fields["id"] == slug
    assert fields["status"] == "fixed"
    assert fields["context"] == "fixed-bug-parent"
    assert fields["terminal-at"] == instant
    assert fields["resolution"] == resolution
    assert fields["evidence"] == evidence
    assert status.parent.is_dir()
    assert (ledger.read_bytes() if ledger.exists() else None) == ledger_before
    assert f"bug:{slug}".encode() in status.read_bytes()
    assert f"[{ 'physical' }]({expected_href})".encode() in status.read_bytes()
    assert f"../../bugs/{slug}.md#proof".encode() in status_before
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert set(receipt) == {
        "schemaVersion", "owner", "kind", "status", "operationId",
        "sourceReference", "sourcePath", "archivePath", "terminalInstant",
        "sourceBeforeSha256", "archivedBugSha256", "links", "readmeSha256",
    }
    assert receipt["owner"] == "mutate-work-item:fixed-bug-archive-v1"
    assert receipt["kind"] == "fixed-bug-archive-v1"
    assert receipt["status"] == "settled"
    assert receipt["sourceBeforeSha256"] == hashlib.sha256(bug_before).hexdigest()
    assert receipt["archivedBugSha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert receipt["readmeSha256"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    assert receipt["links"] == [{
        "path": status.relative_to(root).as_posix(),
        "beforeSha256": hashlib.sha256(status_before).hexdigest(),
        "afterSha256": hashlib.sha256(status.read_bytes()).hexdigest(),
    }]
    before_replay = (archive.read_bytes(), status.read_bytes(), receipt_path.read_bytes(), readme.read_bytes())
    replay = run_cli(*command)
    assert replay.returncode == 0, replay.stdout
    assert (archive.read_bytes(), status.read_bytes(), receipt_path.read_bytes(), readme.read_bytes()) == before_replay


def retained_preimage_fixture(tmp_path: Path, *, text_payload: bool = False):
    """Synthetic retained-input contract; never the actual retained preimage."""
    module = load_module()
    root = tmp_path / "repo"
    bug, status = seed_fixed_bug_with_active_parent(module, root, "retained-input-probe")
    seed_active(module, root, "preimage-custodian")
    item = root / "work-items" / "active" / "preimage-custodian"
    payload = item / "inputs" / "old-guidance" / ("renamed-guide.before" if text_payload else "opaque-source.saved")
    payload.parent.mkdir(parents=True)
    href = os.path.relpath(bug, payload.parent).replace(os.sep, "/")
    data = f"Historical link: [prior]({href})\n".encode() + (b"UTF-8 history\n" if text_payload else b"\x82\x00opaque history\n")
    payload.write_bytes(data)
    report = item / "stewardship.md"
    report.write_bytes(b"Synthetic accepted custody report; not current task completion.\n")
    report_digest = hashlib.sha256(report.read_bytes()).hexdigest()
    profile = {"kind": "artifact", "ref": payload.relative_to(item).as_posix(), "result": json.dumps({
        "schemaVersion": 1, "kind": "retained-preimage", "workItem": item.name,
        "purpose": "historical-only", "byteCount": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "provenance": {"ref": report.name, "sha256": report_digest,
                       "snapshot": f"review-artifact-custody/{report_digest}"},
    }, sort_keys=True)}
    return module, root, bug, status, item, payload, data, report, profile


def retained_preimage_cli(item: Path, script: Path, *args: str):
    """Keep every public command's complete output beside the private fixture."""
    result = subprocess.run([sys.executable, "-B", str(script), *args], cwd=ROOT,
                            capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    proof_root = item.parents[2]
    number = len(list(proof_root.glob("retained-cli-*.log")))
    (proof_root / f"retained-cli-{number}.log").write_bytes(
        result.stdout + b"\nSTDERR:\n" + result.stderr + f"\nEXIT:{result.returncode}\n".encode())
    return result


def retained_preimage_append(item: Path, profile: dict, *, role="knowledge-archivist", run_id="retained-custody-record"):
    provenance = json.loads(profile["result"])["provenance"]
    return retained_preimage_cli(item, LEDGER, "--work-item", str(item), "append", "--run-id", run_id,
                                "--role", role, "--execution-role", "internal", "--status", "completed",
                                "--gate", "PASS", "--event-kind", "standalone", "--scope", profile["ref"],
                                "--artifact", provenance["ref"], "--artifact-revision", provenance["sha256"],
                                "--evidence", f"artifact:{provenance['ref']}", "--evidence-json", json.dumps(profile))


def retained_preimage_archive_oracle(tmp_path: Path, *, text_payload: bool):
    """Removing semantic admission reproduces binary refusal or UTF-8 history rewriting."""
    module, root, bug, status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path, text_payload=text_payload)
    appended = retained_preimage_append(item, profile)
    assert appended.returncode == 0, appended.stdout + appended.stderr
    result = retained_preimage_cli(item, SCRIPT, "archive-fixed-bug", "--root", str(root), "--slug", bug.stem,
                                  "--terminal-instant", "2026-10-05T00:00:00Z", "--resolution", "Synthetic verified fix.",
                                  "--evidence", "Synthetic public archive oracle.", "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    assert payload.read_bytes() == before
    assert payload.parent == item / "inputs" / "old-guidance"
    assert f"../../bugs/archive/2026-10/{bug.stem}.md#proof".encode() in status.read_bytes()
    snapshot = item / json.loads(profile["result"])["provenance"]["snapshot"]
    assert snapshot.read_bytes() == report.read_bytes()


def test_retained_preimage_public_binary_archive_preserves_exact_bytes(tmp_path: Path):
    retained_preimage_archive_oracle(tmp_path, text_payload=False)


def test_retained_preimage_public_utf8_archive_does_not_rewrite_history(tmp_path: Path):
    retained_preimage_archive_oracle(tmp_path, text_payload=True)


def test_retained_preimage_wire_refuses_nonsteward_live_path_and_bad_binding(tmp_path: Path):
    for case in ("issuer", "live", "count-type", "hash", "duplicate"):
        _module, _root, _bug, _status, item, payload, before, _report, profile = retained_preimage_fixture(tmp_path / case)
        profile = copy.deepcopy(profile)
        decoded = json.loads(profile["result"])
        role = "knowledge-archivist"
        if case == "issuer":
            role = "platform-engineer"
        elif case == "live":
            profile["ref"] = "status.md"
        elif case == "count-type":
            decoded["byteCount"] = True
        elif case == "hash":
            decoded["sha256"] = "0" * 64
        profile["result"] = json.dumps(decoded)
        if case == "duplicate":
            profile["result"] = profile["result"].replace('"purpose": "historical-only"',
                                                          '"purpose": "historical-only", "purpose": "historical-only"')
        result = retained_preimage_append(item, profile, role=role)
        assert result.returncode != 0, result.stdout + result.stderr
        assert payload.read_bytes() == before
        assert not (item / "agent-runs.jsonl").exists()
        assert not (item / "review-artifact-custody").exists()


def test_retained_preimage_selected_record_is_local_and_snapshot_exact(tmp_path: Path):
    module, root, bug, _status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path)
    result = retained_preimage_append(item, profile)
    assert result.returncode == 0, result.stdout + result.stderr
    snapshot = item / json.loads(profile["result"])["provenance"]["snapshot"]
    report.unlink()
    ledger = item / "agent-runs.jsonl"
    # Declared synthetic unrelated legacy rows: not ordinary-producer recipes.
    ledger.write_bytes(ledger.read_bytes() + b'{"runId":"unrelated-old-record","schemaVersion":"obsolete","artifact":"missing.md"}\nnot-json\n')
    write(item / "review-artifact-custody" / "historical-pass" / ("e" * 64 + ".json"), "unrelated invalid association\n")
    assert module._retained_preimage_consumer(payload, root / "work-items")
    assert module._retained_preimage_consumer(snapshot, root / "work-items")
    assert module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)["result"] == "unmapped"
    unknown = item / "review-artifact-custody" / ("f" * 64)
    unknown.write_bytes(b"unadmitted\x82")
    with pytest.raises(module.LifecycleError, match="cannot classify live incoming-link consumer"):
        module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
    unknown.unlink()
    assert payload.read_bytes() == before
    # Matching decoded identity remains reserved even on a schema-invalid row.
    ledger.write_bytes(ledger.read_bytes() + b'{"runId":"RETAINED-CUSTODY-RECORD","schemaVersion":"obsolete"}\n')
    assert not module._retained_preimage_consumer(payload, root / "work-items")
    with pytest.raises(module.LifecycleError, match="cannot classify live incoming-link consumer"):
        module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)


class SnapshotReadProbe:
    """Observe real requested sizes without allocating a schema-ceiling buffer."""
    def __init__(self, stream, requests, after_first_read=None):
        self.stream, self.requests, self.after_first_read = stream, requests, after_first_read
        self.reads = 0

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def read(self, size):
        self.requests.append(size)
        data = self.stream.read(min(size, 2 * 1024 * 1024))
        self.reads += 1
        if self.reads == 1 and self.after_first_read is not None:
            self.after_first_read()
        return data


def test_retained_consumer_acquires_validator_once_per_lazy_scan(tmp_path: Path):
    module, root, bug, _status, item, payload, before, _report, profile = retained_preimage_fixture(tmp_path)
    assert retained_preimage_append(item, profile).returncode == 0
    write(item / "inputs" / "unmatched-a.md", "Ordinary live neighbor.\n")
    write(item / "inputs" / "unmatched-b.md", "Another ordinary neighbor.\n")
    seed_active(module, root, "without-ledger")
    real_loader, real_fdopen = module._validator_module, module.os.fdopen
    loads, requests = [], []

    def counted_loader():
        loads.append(1)
        return real_loader()

    def observed_fdopen(*args, **kwargs):
        return SnapshotReadProbe(real_fdopen(*args, **kwargs), requests)

    with patch.object(module, "_validator_module", side_effect=counted_loader), \
         patch.object(module.os, "fdopen", side_effect=observed_fdopen):
        result = module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
        assert result["result"] == "unmapped"
        assert payload.read_bytes() == before
        assert len(loads) == 1
        loads.clear()
        assert module._retained_preimage_consumer(payload, root / "work-items")
        assert len(loads) == 1  # Existing direct-selector default remains usable.

    empty = tmp_path / "early-return"
    owned = empty / "work-items" / "bugs" / "owned.md"
    write(owned, "Owned input.\n")
    failure = module.LifecycleError("WI-VALIDATOR-LOAD", "Injected acquisition failure")
    with patch.object(module, "_validator_module", side_effect=failure):
        assert module._incoming_link_result(empty, {owned}, "bug:owned")["result"] == "clear"
        with pytest.raises(module.LifecycleError) as caught:
            module._incoming_link_result(root, {bug}, f"bug:{bug.stem}")
        assert caught.value is failure
        with pytest.raises(module.LifecycleError) as direct:
            module._retained_preimage_consumer(root / "work-items" / "active" / "without-ledger" / "status.md", root / "work-items")
        assert direct.value is failure  # Preserve the current acquisition point.


def test_retained_consumer_prepares_each_item_once(tmp_path: Path):
    module, root, bug, _status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path)
    assert retained_preimage_append(item, profile).returncode == 0
    seed_active(module, root, "preparation-peer")
    peer = root / "work-items" / "active" / "preparation-peer"
    peer_payload = peer / profile["ref"]
    peer_payload.parent.mkdir(parents=True)
    peer_payload.write_bytes(before)
    (peer / report.name).write_bytes(report.read_bytes())
    peer_profile = {**profile, "result": json.dumps({**json.loads(profile["result"]), "workItem": peer.name})}
    assert retained_preimage_append(peer, peer_profile, run_id="peer-custody-record").returncode == 0
    for owner in (item, peer):
        write(owner / "inputs" / "ordinary-a.md", "Unmatched live input.\n")
        write(owner / "inputs" / "ordinary-b.md", "Another unmatched live input.\n")
    paths = {item / "agent-runs.jsonl", peer / "agent-runs.jsonl"}
    captures, decodes = {}, {}
    real_capture, real_loader = module._capture_file_snapshot, module._validator_module

    def counted_capture(path, **kwargs):
        if path in paths:
            captures[path] = captures.get(path, 0) + 1
        return real_capture(path, **kwargs)

    def counted_loader():
        validator = real_loader()
        real_decode = validator.load_jsonl
        def counted_decode(path, *args, **kwargs):
            # Selected-proof prefix decoding is separate, still candidate-owned.
            if path in paths and sys._getframe(1).f_code.co_name != "resolve_historical_pass_custody":
                decodes[path] = decodes.get(path, 0) + 1
            return real_decode(path, *args, **kwargs)
        validator.load_jsonl = counted_decode
        return validator

    with patch.object(module, "_capture_file_snapshot", side_effect=counted_capture), \
         patch.object(module, "_validator_module", side_effect=counted_loader):
        result = module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
    assert result["result"] == "unmapped"
    assert payload.read_bytes() == before and peer_payload.read_bytes() == before
    assert captures == {path: 1 for path in paths}
    assert decodes == {path: 1 for path in paths}


def test_retained_consumer_cached_carrier_drift_never_refreshes_approval(tmp_path: Path):
    for fault in ("growth", "content", "replacement", "parent"):
        module, root, bug, status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path / fault)
        assert retained_preimage_append(item, profile).returncode == 0
        ledger = item / "agent-runs.jsonl"
        # Declared synthetic whitespace suffix; original public record/proof stays exact.
        original = ledger.read_bytes() + b" \n"
        ledger.write_bytes(original)
        observed = {path: path.read_bytes() for path in (bug, status, root / "work-items" / "README.md")}
        real_selector = module._retained_preimage_consumer
        injected = []

        def select_then_drift(consumer, work_items, **kwargs):
            result = real_selector(consumer, work_items, **kwargs)
            if consumer == ledger and not injected:
                if fault == "growth":
                    ledger.write_bytes(original + b" \n")
                elif fault == "content":
                    ledger.write_bytes(original[:-2] + b"\t\n")
                elif fault == "replacement":
                    replacement = item / "replacement-ledger.jsonl"
                    replacement.write_bytes(original)
                    os.replace(replacement, ledger)
                else:
                    item.rename(item.with_name("moved-custodian"))
                injected.append(True)
            return result

        with patch.object(module, "_retained_preimage_consumer", side_effect=select_then_drift):
            with pytest.raises(module.LifecycleError, match="cannot classify live incoming-link consumer"):
                module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
        assert injected == [True]
        assert all(path.read_bytes() == data for path, data in observed.items())
        assert (item if fault != "parent" else item.with_name("moved-custodian")).joinpath(profile["ref"]).read_bytes() == before


def test_snapshot_reads_captured_size_and_preserves_drift_refusal(tmp_path: Path):
    module = load_module()
    real_fdopen = module.os.fdopen
    original = b"captured payload"
    for fault in (None, "empty", "growth", "shrink", "rewrite", "replace", "parent"):
        folder = tmp_path / str(fault) / "parent"
        target = folder / "input.bin"
        folder.mkdir(parents=True)
        case_bytes = b"" if fault == "empty" else original
        target.write_bytes(case_bytes)
        requests = []
        mutated = []

        def drift():
            if fault == "growth":
                target.write_bytes(original + b"growing")
            elif fault == "shrink":
                target.write_bytes(original[:3])
            elif fault == "rewrite":
                target.write_bytes(b"x" * len(original))
            elif fault == "replace":
                replacement = folder / "replacement.bin"
                replacement.write_bytes(original)
                os.replace(replacement, target)
            elif fault == "parent":
                folder.rename(folder.with_name("moved-parent"))
            if fault not in (None, "empty"):
                mutated.append(True)

        def observed_fdopen(*args, **kwargs):
            return SnapshotReadProbe(real_fdopen(*args, **kwargs), requests, drift)

        # Relax only this synthetic handle's sharing to exercise content races;
        # ordinary native no-follow behavior remains covered by adjacent tests.
        capture_open = module._open_readonly_nofollow
        if fault not in (None, "empty"):
            capture_open = lambda path: os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with patch.object(module, "_open_readonly_nofollow", side_effect=capture_open), \
             patch.object(module.os, "fdopen", side_effect=observed_fdopen):
            if fault in (None, "empty"):
                snapshot = module._capture_file_snapshot(target, failure_id="WI-SNAPSHOT-COST", maximum_bytes=0 if fault == "empty" else 1024)
                assert snapshot.data == case_bytes
            else:
                with pytest.raises(module.LifecycleError) as caught:
                    module._capture_file_snapshot(target, failure_id="WI-SNAPSHOT-COST", maximum_bytes=1024)
                assert caught.value.failure_id == "WI-SNAPSHOT-COST"
        if fault in (None, "empty", "growth", "shrink", "rewrite"):
            assert requests == [len(case_bytes) + 1, len(case_bytes) + 1], fault
            if fault not in (None, "empty"):
                assert mutated == [True], fault
        else:
            # Windows may refuse replacement/parent moves while the file is open.
            assert 1 <= len(requests) <= 2 and all(size == len(case_bytes) + 1 for size in requests), fault


def test_retained_preimage_multiple_descriptors_keep_runtime_binding_local(tmp_path: Path):
    module, root, bug, status, item, first, original, report, profile = retained_preimage_fixture(tmp_path)
    second = item / "inputs" / "separate-source.before"
    second.write_bytes(b"Second retained historical bytes.\n")
    second_result = {**json.loads(profile["result"]), "byteCount": second.stat().st_size,
                     "sha256": hashlib.sha256(second.read_bytes()).hexdigest()}
    second_profile = {**profile, "ref": second.relative_to(item).as_posix(),
                      "result": json.dumps(second_result, sort_keys=True)}
    provenance = json.loads(profile["result"])["provenance"]
    appended = retained_preimage_cli(item, LEDGER, "--work-item", str(item), "append",
        "--run-id", "multiple-retained-record", "--role", "knowledge-archivist",
        "--execution-role", "internal", "--status", "completed", "--gate", "PASS",
        "--event-kind", "standalone", "--scope", profile["ref"], "--artifact", provenance["ref"],
        "--artifact-revision", provenance["sha256"], "--evidence", f"artifact:{provenance['ref']}",
        "--evidence-json", json.dumps(profile), "--evidence-json", json.dumps(second_profile))
    assert appended.returncode == 0, appended.stdout + appended.stderr
    ledger = item / "agent-runs.jsonl"
    snapshot = item / provenance["snapshot"]
    association = next((item / "review-artifact-custody" / "historical-pass").iterdir())
    observed = (first, ledger, report, snapshot, association, bug, status, root / "work-items" / "README.md")
    before = {path: path.read_bytes() for path in observed}
    assert module._retained_preimage_consumer(first, root / "work-items")
    second.write_bytes(second.read_bytes() + b"Changed second payload.\x82")
    assert {path: path.read_bytes() for path in observed} == before
    assert first.read_bytes() == original
    assert module._retained_preimage_consumer(first, root / "work-items")
    assert not module._retained_preimage_consumer(second, root / "work-items")
    with pytest.raises(module.LifecycleError, match="cannot classify live incoming-link consumer"):
        module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)

    # Selective runtime capture never relaxes same-record descriptor schemas.
    validator = module._validator_module()
    record = json.loads(ledger.read_bytes())
    first_capture = validator.capture_retained_preimage_payload(item, profile, json.loads(profile["result"]))
    invalid_second = {**second_profile, "result": json.dumps({**second_result, "purpose": "invalid-purpose"})}
    invalid_record = {**record, "evidence": [invalid_second if row.get("ref") == second_profile["ref"] else row
                                            for row in record["evidence"]]}
    schema_errors = []
    assert not validator._validate_event(invalid_record, item, set(), schema_errors,
                                        retained_payloads={profile["ref"]: first_capture})
    assert any("WI-RETAINED-PREIMAGE" in error for error in schema_errors)

    # None and an explicit complete mapping both retain full payload checks.
    full_errors = []
    assert not validator._validate_event(record, item, set(), full_errors)
    assert any("WI-RETAINED-PREIMAGE" in error for error in full_errors)
    second_capture = validator.load_lifecycle_owner()._capture_file_snapshot(second, failure_id="WI-RETAINED-PREIMAGE")
    mapped_errors = []
    assert not validator._validate_event(record, item, set(), mapped_errors,
        retained_payloads={profile["ref"]: first_capture, second_profile["ref"]: second_capture})
    assert any("WI-RETAINED-PREIMAGE" in error for error in mapped_errors)
    refused = retained_preimage_append(item, second_profile, run_id="invalid-second-append")
    assert refused.returncode != 0
    assert {path: path.read_bytes() for path in observed} == before


def test_retained_preimage_observation_drift_refuses_before_intent(tmp_path: Path):
    for participant in ("payload", "carrier", "association", "snapshot"):
        module, root, bug, status, item, payload, _data, _report, profile = retained_preimage_fixture(tmp_path / participant)
        appended = retained_preimage_append(item, profile)
        assert appended.returncode == 0, appended.stdout + appended.stderr
        ledger = item / "agent-runs.jsonl"
        selected = {
            "payload": payload, "carrier": ledger,
            "association": next((item / "review-artifact-custody" / "historical-pass").iterdir()),
            "snapshot": item / json.loads(profile["result"])["provenance"]["snapshot"],
        }[participant]
        before = (bug.read_bytes(), status.read_bytes(), (root / "work-items" / "README.md").read_bytes())
        original = module._precompute_single_bug_readme_sha256

        def drift(*args, **kwargs):
            result = original(*args, **kwargs)
            selected.write_bytes(selected.read_bytes() + b"changed after semantic selection")
            return result

        with patch.object(module, "_precompute_single_bug_readme_sha256", side_effect=drift):
            with pytest.raises(module.LifecycleError):
                module.archive_fixed_bug(root, bug.stem, "2026-10-05T00:00:00Z", "Synthetic fix.", "Synthetic proof.")
        assert (bug.read_bytes(), status.read_bytes(), (root / "work-items" / "README.md").read_bytes()) == before
        assert not (root / "work-items" / "lifecycle-transitions").exists()
        assert not (root / "work-items" / "bugs" / "archive").exists()


def test_invalid_retained_claim_in_inputs_is_still_scanned_as_a_consumer(tmp_path: Path):
    module, root, bug, _status, item, payload, before, _report, profile = retained_preimage_fixture(
        tmp_path, text_payload=True,
    )
    appended = retained_preimage_append(item, profile)
    assert appended.returncode == 0, appended.stdout + appended.stderr

    payload.write_bytes(before + b" selected payload drift")
    result = module._incoming_link_result(
        root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True,
    )
    assert result == {
        "result": "unmapped",
        "references": [
            {"consumer": "active/fixed-bug-parent/status.md", "kind": "logical", "value": f"bug:{bug.stem}"},
            {
                "consumer": "active/fixed-bug-parent/status.md",
                "kind": "physical",
                "value": f"../../bugs/{bug.name}#proof",
            },
            {
                "consumer": payload.relative_to(root / "work-items").as_posix(),
                "kind": "physical",
                "value": os.path.relpath(bug, payload.parent).replace(os.sep, "/"),
            },
        ],
    }
    assert payload.read_bytes() == before + b" selected payload drift"


def test_failed_ledger_preparation_never_becomes_no_claim(tmp_path: Path):
    module, root, bug, _status, item, payload, before, _report, profile = retained_preimage_fixture(tmp_path)
    appended = retained_preimage_append(item, profile)
    assert appended.returncode == 0, appended.stdout + appended.stderr
    changed = before + b" failed selected scan preparation"
    payload.write_bytes(changed)

    with pytest.raises(module.LifecycleError) as baseline:
        module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
    assert baseline.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
    assert "cannot classify live incoming-link consumer" in str(baseline.value)

    original_capture = module._capture_file_snapshot
    failures = []

    def fail_one_selected_ledger_capture(path, *args, **kwargs):
        if path == item / "agent-runs.jsonl" and not failures:
            failures.append(path)
            raise module.LifecycleError("TEST-SELECTED-LEDGER-CAPTURE", "Synthetic selected ledger capture failure")
        return original_capture(path, *args, **kwargs)

    with patch.object(module, "_capture_file_snapshot", side_effect=fail_one_selected_ledger_capture):
        with pytest.raises(module.LifecycleError) as injected:
            module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
    assert injected.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
    assert "cannot classify live incoming-link consumer" in str(injected.value)
    assert failures == [item / "agent-runs.jsonl"]
    assert payload.read_bytes() == changed


def test_acquired_input_role_exclusion_keeps_per_leaf_currentness(tmp_path: Path):
    def acquired_fixture(base: Path):
        module = load_module()
        validator = module._validator_module()
        root = base / "repo"
        seed_active(module, root, "data-owner")
        item = root / "work-items" / "active" / "data-owner"
        payload = item / "inputs" / "source.dat"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"original ordinary data\n")
        owned = item / "unused-target.md"
        files = [module._capture_file_snapshot(path, failure_id="TEST-CAPTURE")
                 for path in root.rglob("*") if path.is_file()]
        directories = [module._capture_directory_snapshot(path, failure_id="TEST-CAPTURE")
                       for path in [root] + [path for path in root.rglob("*") if path.is_dir()]]
        native = module.AcquiredWorkItemInputV1(
            root,
            [module.CapturedInputAssociationV1(snapshot, snapshot) for snapshot in files],
            [module.CapturedInputAssociationV1(snapshot, snapshot) for snapshot in directories],
        )
        criteria = validator.HistoricalLedgerCriteriaV1("synthetic-criteria", "synthetic-acquisition", False, "current")
        binding = validator.CapturedWorkItemHistoryBindingV1(
            root, item.name, item.relative_to(root).as_posix(), item.relative_to(root).as_posix(),
            (item / "agent-runs.jsonl").relative_to(root).as_posix(), criteria, (), (), {}, native,
        )
        port = validator._CapturedHistoryPath(binding, root)
        return module, root, payload, owned, port

    def scan(module, root, payload, owned, port):
        return module._incoming_link_result(
            root, {owned}, "work-item:unused-target", strict_consumer_reads=True, acquired_input=port,
        )

    module, root, payload, owned, port = acquired_fixture(tmp_path / "unchanged")
    assert scan(module, root, payload, owned, port) == {"result": "clear", "references": []}

    module, root, payload, owned, port = acquired_fixture(tmp_path / "before-entry")
    payload.write_bytes(b"changed before scan\n")
    with pytest.raises(module.LifecycleError) as before_entry:
        scan(module, root, payload, owned, port)
    assert before_entry.value.failure_id == "WI-LEGACY-COMPLETION-DRIFT"

    module, root, payload, owned, port = acquired_fixture(tmp_path / "after-entry")
    original_selector = module._owned_work_item_input_location
    injected_paths = []

    def drift_after_role_selection(consumer_rel, *args):
        location = original_selector(consumer_rel, *args)
        if consumer_rel == payload.relative_to(root / "work-items").as_posix():
            payload.write_bytes(b"changed after role selection\n")
            injected_paths.append(consumer_rel)
        return location

    with patch.object(module, "_owned_work_item_input_location", side_effect=drift_after_role_selection):
        with pytest.raises(module.LifecycleError) as after_entry:
            scan(module, root, payload, owned, port)
    assert after_entry.value.failure_id == "WI-LEGACY-COMPLETION-DRIFT"
    assert injected_paths == ["active/data-owner/inputs/source.dat"]
    with pytest.raises(module.LifecycleError) as direct_read:
        port.file_snapshot(payload)
    assert direct_read.value.failure_id == "WI-LEGACY-COMPLETION-DRIFT"
    with pytest.raises(module.LifecycleError) as next_invocation:
        scan(module, root, payload, owned, port)
    assert next_invocation.value.failure_id == "WI-LEGACY-COMPLETION-DRIFT"


def test_retained_preimage_relocated_archive_and_live_neighbor_stay_strict(tmp_path: Path):
    module, root, bug, _status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path)
    assert retained_preimage_append(item, profile).returncode == 0
    report.write_bytes(b"current report pointer is replaced")
    archive = root / "work-items" / "archive" / "2026-10" / item.name
    archive.parent.mkdir(parents=True)
    item.rename(archive)  # Declared synthetic relocation; never move an actual preimage.
    relocated = archive / payload.relative_to(item)
    assert module._retained_preimage_consumer(relocated, root / "work-items")
    assert relocated.read_bytes() == before
    neighbor = archive / "inputs" / "unadmitted-neighbor"
    neighbor.write_bytes(b"unknown\x82")
    full = module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
    assert full["result"] == "unmapped"
    assert all(row["consumer"] != neighbor.relative_to(root / "work-items").as_posix()
               for row in full["references"])
    assert neighbor.read_bytes() == b"unknown\x82"
    assert module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True,
                                       mutable_consumers_only=True)["result"] == "unmapped"
    assert relocated.read_bytes() == before


def test_archive_fixed_bug_requires_positive_apply_and_preserves_state(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-no-apply"
    bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
    before = (bug.read_bytes(), status.read_bytes())

    result = run_cli(
        "archive-fixed-bug", "--root", str(root), "--slug", slug,
        "--terminal-instant", "2026-09-26T12:00:00Z",
        "--resolution", "Fixed.", "--evidence", "Test receipt.",
    )

    assert result.returncode == 1
    assert "WI-FIXED-BUG-APPLY-REQUIRED" in result.stdout
    assert (bug.read_bytes(), status.read_bytes()) == before


def test_archive_fixed_bug_preserves_existing_evidence_and_rejects_conflicts(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-existing-evidence"
    instant = "2026-10-01T00:00:00Z"
    bug, _status = seed_fixed_bug_with_active_parent(module, root, slug)
    with bug.open("ab") as stream:
        stream.write(b"- terminal-at: 2026-10-01T00:00:00Z\n- resolution: Fixed.\n- evidence: Verified.\n")
    preserved = bug.read_bytes()
    with unittest.TestCase().assertRaises(module.LifecycleError) as conflict:
        module.archive_fixed_bug(root, slug, instant, "Different.", "Verified.")
    assert conflict.exception.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    assert bug.read_bytes() == preserved

    receipt = module.archive_fixed_bug(root, slug, instant, "Fixed.", "Verified.")

    archive = root / receipt["archivePath"]
    assert archive.read_bytes() == preserved
    assert archive.parent.name == "2026-10"


def test_archive_fixed_bug_rejects_immutable_physical_link_and_collision(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-unsafe-link"
    bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
    historical = root / "work-items" / "archive" / "2026-08" / "old" / "notes.md"
    write(historical, f"[old](../../../bugs/{slug}.md)\n")
    before = (bug.read_bytes(), status.read_bytes(), historical.read_bytes())
    with unittest.TestCase().assertRaises(module.LifecycleError) as unsafe:
        module.archive_fixed_bug(root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.")
    assert unsafe.exception.failure_id == "WI-FIXED-BUG-LINK-INVENTORY"
    assert (bug.read_bytes(), status.read_bytes(), historical.read_bytes()) == before

    historical.unlink()
    archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
    write(archive, "unrelated archive identity\n")
    with unittest.TestCase().assertRaises(module.LifecycleError) as collision:
        module.archive_fixed_bug(root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.")
    assert collision.exception.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    assert (bug.read_bytes(), status.read_bytes()) == before[:2]
    assert archive.read_text(encoding="utf-8") == "unrelated archive identity\n"


def test_archive_fixed_bug_precommit_restores_and_postcommit_recovers(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-09-26T12:00:00Z"
    for phase in ("F1", "F3"):
        root = tmp_path / phase
        slug = f"2026-09-26-{phase.lower()}-recovery"
        bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
        readme = root / "work-items" / "README.md"
        before = (bug.read_bytes(), status.read_bytes(), readme.read_bytes())
        with unittest.TestCase().assertRaises(module.LifecycleError) as injected:
            module.archive_fixed_bug(
                root, slug, instant, "Fixed.", "Verified.", inject_failure_at=phase,
            )
        assert injected.exception.failure_id == (
            "WI-FIXED-BUG-ROLLBACK-INDETERMINATE" if phase == "F1"
            else "WI-FIXED-BUG-ROLLFORWARD-INDETERMINATE"
        )

        _recover_pending_transitions(module, root)

        archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
        receipt = archive.with_name(f"{slug}.fixed-archive-receipt.json")
        if phase == "F1":
            assert (bug.read_bytes(), status.read_bytes(), readme.read_bytes()) == before
            assert not archive.exists() and not receipt.exists()
        else:
            assert not bug.exists()
            assert archive.is_file() and receipt.is_file()
            assert f"../../bugs/archive/2026-09/{slug}.md#proof".encode() in status.read_bytes()
            assert module._verify_fixed_bug_archive_settlement(root, receipt)["status"] == "settled"
        intents = root / ".scratch" / "work-items-lifecycle-transitions"
        assert not list(intents.glob("*.json"))


def test_archive_fixed_bug_readme_failure_recovers_after_move(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-readme-failure"
    bug, _status = seed_fixed_bug_with_active_parent(module, root, slug)
    archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
    original_refresh = module._safe_refresh_readme
    with patch.object(module, "_safe_refresh_readme", side_effect=module.LifecycleError("WI-README-STALE", "injected")):
        with unittest.TestCase().assertRaises(module.LifecycleError) as failure:
            module.archive_fixed_bug(root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.")
    assert failure.exception.failure_id == "WI-FIXED-BUG-ROLLFORWARD-INDETERMINATE"
    assert not bug.exists() and archive.is_file()
    assert module._safe_refresh_readme is original_refresh
    _recover_pending_transitions(module, root)
    receipt = archive.with_name(f"{slug}.fixed-archive-receipt.json")
    assert module._verify_fixed_bug_archive_settlement(root, receipt)["status"] == "settled"


def test_archive_fixed_bug_recovery_errors_name_fixed_archive_not_supersession(tmp_path: Path) -> None:
    module = load_module()
    for phase, target_kind in (("F1", "link"), ("F3", "archive")):
        root = tmp_path / phase
        slug = f"2026-09-26-{phase.lower()}-diagnostic"
        _bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
        with unittest.TestCase().assertRaises(module.LifecycleError):
            module.archive_fixed_bug(
                root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.",
                inject_failure_at=phase,
            )
        archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
        target = status if target_kind == "link" else archive
        target_before_drift = target.read_bytes()
        target.write_bytes(b"foreign mutation\n")

        with unittest.TestCase().assertRaises(module.LifecycleError) as failed_recovery:
            _recover_pending_transitions(module, root)

        assert failed_recovery.exception.failure_id == (
            "WI-FIXED-BUG-ROLLBACK-INDETERMINATE" if phase == "F1"
            else "WI-FIXED-BUG-ROLLFORWARD-INDETERMINATE"
        )
        assert "fixed-bug archive" in str(failed_recovery.exception)
        assert "supersession" not in str(failed_recovery.exception)
        assert target.read_bytes() == b"foreign mutation\n"
        target.write_bytes(target_before_drift)
        _recover_pending_transitions(module, root)
        assert not list((root / ".scratch" / "work-items-lifecycle-transitions").glob("*.json"))

    root = tmp_path / "F3-readme"
    slug = "2026-09-26-readme-diagnostic"
    bug, _status = seed_fixed_bug_with_active_parent(module, root, slug)
    with unittest.TestCase().assertRaises(module.LifecycleError):
        module.archive_fixed_bug(
            root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.",
            inject_failure_at="F3",
        )
    archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
    archive_before = archive.read_bytes()
    assert not bug.exists()
    with patch.object(module, "_safe_refresh_readme", return_value="0" * 64):
        with unittest.TestCase().assertRaises(module.LifecycleError) as readme_mismatch:
            _recover_pending_transitions(module, root)

    assert readme_mismatch.exception.failure_id == "WI-FIXED-BUG-ROLLFORWARD-INDETERMINATE"
    assert str(readme_mismatch.exception) == "fixed-bug archive README afterimage differs"
    assert archive.read_bytes() == archive_before
    assert not archive.with_name(f"{slug}.fixed-archive-receipt.json").exists()
    _recover_pending_transitions(module, root)
    assert not list((root / ".scratch" / "work-items-lifecycle-transitions").glob("*.json"))


def write_bug_dispositions(
    root: Path,
    item_slug: str,
    instant: str,
    rows: list[dict],
) -> Path:
    target = root / "work-items" / "active" / item_slug / "bug-dispositions.json"
    write(
        target,
        json.dumps(
            {
                "schemaVersion": 1,
                "workItem": item_slug,
                "closedAt": instant,
                "bugs": rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return target


def write_empty_bug_dispositions(root: Path, item_slug: str, instant: str) -> Path:
    return write_bug_dispositions(root, item_slug, instant, [])


def _seed_ordinary_ledger_close(tmp_path, slug="ordinary-ledger"):
    module = load_module()
    root = tmp_path / "repo"
    seed_active(module, root, slug)
    item = root / "work-items/active" / slug
    result = run_ledger(item, "append", "--run-id", "ordinary-current-record", "--role", "analyst",
        "--execution-role", "internal", "--status", "completed", "--gate", "none", "--event-kind", "standalone",
        "--scope", "actual ordinary lifecycle fixture", "--evidence", "manual-check:synthetic useful current result")
    assert result.returncode == 0, result.stdout + result.stderr
    instant = "2026-10-24T00:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    return module, root, item, instant


def test_ordinary_close_settlement_binds_inputs_migrations_and_immutable_retry(tmp_path):
    module, root, item, instant = _seed_ordinary_ledger_close(tmp_path)
    migrations = item / "ledger-migration-receipts"
    migrations.mkdir()
    for name in ("alpha.json", "omega.json"):
        (migrations / name).write_text(json.dumps({"synthetic": name}), encoding="utf-8")
    ledger_before = (item / "agent-runs.jsonl").read_bytes()
    readme_before = (root / "work-items/README.md").read_bytes()
    (item / "criteria.md").write_bytes(b"Ledger required: True.\n")
    (item / "acquisition.md").write_bytes(b"Synthetic original history selection.\n")
    requested_closure = closure(instant).encode()
    archive = module.close_item(root, item.name, requested_closure, instant)
    receipt = archive / "lifecycle-transition-receipt.json"
    raw = receipt.read_bytes()
    proof = json.loads(raw)
    assert set(proof) == module.ORDINARY_CLOSE_TRANSITION_SETTLEMENT_FIELDS and len(proof) == 17
    assert proof["operationId"] == module._ordinary_close_operation_id(proof)
    assert proof["requestExpectedReadmeSha256"] == hashlib.sha256(readme_before).hexdigest()
    assert proof["requestClosureSha256"] == hashlib.sha256(requested_closure).hexdigest()
    assert proof["closureSha256"] == hashlib.sha256((archive / "closure.md").read_bytes()).hexdigest()
    assert (archive / "agent-runs.jsonl").read_bytes() == ledger_before
    assert proof["migrationReceipts"] == [{"path": p.relative_to(root).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                          for p in sorted((archive / "ledger-migration-receipts").glob("*.json"))]
    logical = f"work-items/active/{item.name}"
    direct = module.resolve_work_item_ledger_location(root, logical_work_item=logical,
        logical_ledger_path=logical + "/agent-runs.jsonl")
    assert direct.physical_work_item == archive.relative_to(root).as_posix()
    omitted = {**proof, "migrationReceipts": proof["migrationReceipts"][:1]}
    receipt.write_bytes(module._migration_receipt_bytes(omitted))
    with pytest.raises(module.LifecycleError, match="migration receipt set differs"):
        module.resolve_work_item_ledger_location(root, logical_work_item=logical,
            logical_ledger_path=logical + "/agent-runs.jsonl")
    receipt.write_bytes(raw)
    from tests.test_ledger_h1_effective_view import _capture_current_history
    validator = module._validator_module()
    captured = _capture_current_history(validator, root, archive, prepare=False)
    transfer_errors = []
    assert validator._transfer_receipts(root, transfer_errors) == {} and transfer_errors == []
    receiver = validator.load_lifecycle_owner()
    bound = receiver.resolve_work_item_ledger_location(root, logical_work_item=logical,
        logical_ledger_path=logical + "/agent-runs.jsonl", acquired_input=captured._current_item.owner_input)
    assert bound.logical_ledger_path == direct.logical_ledger_path and bound.ledger_sha256 == direct.ledger_sha256
    assert captured.operation_diagnostics() == ()
    module.create_candidate(root, "later-legitimate-task", b"Task: Later real item.\nNext action: Start.\nupdated: 2026-10-24T00:00:00Z\n")
    assert (root / "work-items/README.md").read_bytes() != readme_before
    assert module.close_item(root, item.name, requested_closure, instant) == archive
    assert receipt.read_bytes() == raw
    board = (root / "work-items/README.md").read_bytes()
    with pytest.raises(module.LifecycleError, match="ordinary replay inputs differ"):
        module.close_item(root, item.name, requested_closure + b"\n", instant)
    assert receipt.read_bytes() == raw and (root / "work-items/README.md").read_bytes() == board


def test_ordinary_close_settlement_refuses_distinct_invalid_bindings_and_locations(tmp_path):
    module, root, item, instant = _seed_ordinary_ledger_close(tmp_path)
    archive = module.close_item(root, item.name, closure(instant).encode(), instant)
    receipt = archive / "lifecycle-transition-receipt.json"
    original = receipt.read_bytes()
    proof = json.loads(original)
    logical = f"work-items/active/{item.name}"
    cases = []
    missing = dict(proof); missing.pop("requestExpectedReadmeSha256"); cases.append(missing)
    for key, value in (("schemaVersion", True), ("owner", module.TRANSITION_OWNER),
        ("operationId", "close-" + "0" * 64), ("statusSha256", "0" * 64),
        ("ledgerSha256", "0" * 64), ("requestClosureSha256", "0" * 64),
        ("archivePath", "work-items/archive/2026-10/other"), ("requestTerminalInstant", "2026-10-25T00:00:00Z"),
        ("requestExpectedReadmeSha256", ""), ("migrationReceipts", None), ("readmeSha256", "short"),
        ("readmeSha256", "0" * 64)):
        case = dict(proof); case[key] = value; cases.append(case)
    extra = dict(proof, successorPath="work-items/backlog/foreign.md"); cases.append(extra)
    for case in cases:
        receipt.write_bytes(module._migration_receipt_bytes(case))
        before = receipt.read_bytes()
        with pytest.raises(module.LifecycleError):
            module.resolve_work_item_ledger_location(root, logical_work_item=logical,
                logical_ledger_path=logical + "/agent-runs.jsonl")
        assert receipt.read_bytes() == before
        board = (root / "work-items/README.md").read_bytes()
        with pytest.raises(module.LifecycleError):
            module.close_item(root, item.name, closure(instant).encode(), instant)
        assert receipt.read_bytes() == before and (root / "work-items/README.md").read_bytes() == board
    receipt.write_bytes(original)
    held = archive / "owned-held-proof"
    receipt.rename(held)
    with pytest.raises(module.LifecycleError, match="no lifecycle relocation proof"):
        module.resolve_work_item_ledger_location(root, logical_work_item=logical,
            logical_ledger_path=logical + "/agent-runs.jsonl")
    receipt.symlink_to(held.name)
    with pytest.raises(module.LifecycleError):
        module.resolve_work_item_ledger_location(root, logical_work_item=logical,
            logical_ledger_path=logical + "/agent-runs.jsonl")
    receipt.unlink(); held.rename(receipt)
    item.mkdir()
    with pytest.raises(module.LifecycleError, match="one physical lifecycle location"):
        module.resolve_work_item_ledger_location(root, logical_work_item=logical,
            logical_ledger_path=logical + "/agent-runs.jsonl")
    item.rmdir()
    assert receipt.read_bytes() == original


@pytest.mark.parametrize("phase", ["write", "readback", "foreign-replacement"])
def test_ordinary_close_settlement_failure_uses_owned_rollback(tmp_path, monkeypatch, phase):
    module, root, item, instant = _seed_ordinary_ledger_close(tmp_path)
    before = {p: p.read_bytes() for p in (item / "status.md", item / "agent-runs.jsonl", root / "work-items/README.md")}
    original_write, original_verify = module._atomic_write, module._verify_settlement
    replacement = {}
    def write(path, data, **kwargs):
        if phase == "write" and path.name == "lifecycle-transition-receipt.json":
            raise module.LifecycleError("WI-TEST-PROOF-WRITE", "controlled ordinary proof write failure")
        return original_write(path, data, **kwargs)
    def verify(root, receipt, *args, **kwargs):
        result = original_verify(root, receipt, *args, **kwargs)
        if phase == "foreign-replacement":
            foreign = tmp_path / "foreign-replacement.json"
            replacement["bytes"] = receipt.read_bytes()
            foreign.write_bytes(replacement["bytes"])
            os.replace(foreign, receipt)
            replacement["identity"] = module._lifecycle_file_identity(receipt.lstat())
        raise module.LifecycleError("WI-TEST-PROOF-READBACK", "controlled ordinary proof receiving failure")
    monkeypatch.setattr(module, "_atomic_write", write)
    monkeypatch.setattr(module, "_verify_settlement", verify)
    with pytest.raises(module.LifecycleError):
        module.close_item(root, item.name, closure(instant).encode(), instant)
    archive = root / "work-items/archive/2026-10" / item.name
    if phase == "foreign-replacement":
        leaves = [p for p in (archive / "lifecycle-transition-receipt.json", item / "lifecycle-transition-receipt.json") if p.exists()]
        assert len(leaves) == 1 and leaves[0].read_bytes() == replacement["bytes"]
        assert module._lifecycle_file_identity(leaves[0].lstat()) == replacement["identity"]
    else:
        assert item.is_dir() and not archive.exists() and not (item / "closure.md").exists()
        assert all(p.read_bytes() == data for p, data in before.items())


def test_ordinary_close_output_ceiling_refuses_before_business_effects(tmp_path):
    module, root, item, instant = _seed_ordinary_ledger_close(tmp_path)
    paths = (item / "status.md", item / "agent-runs.jsonl", root / "work-items/README.md")
    before = tuple(p.read_bytes() for p in paths)
    @module._lifecycle_participant
    def constrained(root):
        return module.close_item(root, item.name, closure(instant).encode(), instant)
    with pytest.raises(module.LifecycleError, match="exceeds"):
        constrained(root, transition_output_ceiling=module.resolve_transition_resource_budget(0, 0, 0))
    assert tuple(p.read_bytes() for p in paths) == before
    assert not (root / "work-items/archive/2026-10" / item.name).exists()


@pytest.mark.parametrize("presence", ["absent", "empty"])
def test_ordinary_close_readme_absence_is_not_an_empty_preimage(tmp_path, presence):
    module, root, item, instant = _seed_ordinary_ledger_close(tmp_path)
    readme = root / "work-items/README.md"
    if presence == "empty":
        readme.write_bytes(b"")
        with pytest.raises(module.LifecycleError, match="ordered generated marker pair"):
            module.close_item(root, item.name, closure(instant).encode(), instant)
        assert readme.read_bytes() == b"" and item.is_dir()
    else:
        readme.unlink()
        archive = module.close_item(root, item.name, closure(instant).encode(), instant)
        proof = json.loads((archive / "lifecycle-transition-receipt.json").read_bytes())
        assert proof["requestExpectedReadmeSha256"] is None
        changed = {**proof, "requestExpectedReadmeSha256": hashlib.sha256(b"").hexdigest()}
        assert module._ordinary_close_operation_id(changed) != proof["operationId"]


def test_ordinary_close_updates_standalone_incoming_evidence_links(tmp_path: Path) -> None:
    """NCL1: public close preserves both targets and every non-URI byte."""
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-10-08-fixture-parent"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    documents = {"evidence.md": b"# check\nUseful outcome verified.\n",
                 "stewardship.md": b"Receiving responsibilities verified.\n"}
    for name, data in documents.items():
        (active / name).write_bytes(data)
    bug = seed_context_bug(root, "standalone", "2026-10-08-unselected-open")
    hrefs = [f"../active/{slug}/evidence.md#check", f"../active/{slug}/stewardship.md"]
    before = bug.read_bytes() + (f"\n[Evidence]({hrefs[0]})\n[Stewardship]({hrefs[1]})\n").encode()
    bug.write_bytes(before)
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    closure_file = root / "closure-input.md"
    closure_file.write_text(closure(instant), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "close", "--root", str(root),
         "--slug", slug, "--closure-file", str(closure_file), "--terminal-instant", instant],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    archived = root / "work-items" / "archive" / "2026-10" / slug
    assert not active.exists()
    expected = before
    for href in hrefs:
        relocated = href.replace("../active/", "../archive/2026-10/", 1)
        expected = expected.replace(href.encode(), relocated.encode())
        assert (bug.parent / relocated.split("#", 1)[0]).is_file()
    assert bug.read_bytes() == expected
    for name, data in documents.items():
        assert (archived / name).read_bytes() == data
    module.check_readme(root)
    receipt = json.loads((archived / module.BUG_DISPOSITIONS_RECEIPT).read_bytes())
    assert receipt["bugs"] == []
    assert receipt["linkMaintenance"]["consumers"][0]["authority"] == "current-metadata"


def test_close_updates_mutable_terminal_registry_consumers(tmp_path: Path) -> None:
    module = load_module()
    root, slug = tmp_path / "repo", "2026-10-18-pao-target"
    instant = "2026-10-18T00:00:00Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    payload = b"# proof\nImmutable referenced result.\n"
    (active / "evidence.md").write_bytes(payload)
    prior_slug, successor_slug = "2026-10-18-prior", "2026-10-18-successor"
    decision = root / "work-items" / "decisions" / f"{prior_slug}.md"
    successor = decision.with_name(f"{successor_slug}.md")
    lesson = root / "work-items" / "lessons" / "2026-10-18-lesson.md"
    href = f"../active/{slug}/evidence.md"
    write(decision, _current_decision_record(prior_slug, status="superseded", body=f"[Proof]({href}?view=1#proof)\n").replace(
        "- superseded-by: none", f"- superseded-by: {successor_slug}"))
    write(successor, _current_decision_record(successor_slug, status="accepted", body=f"[Proof]({href})\n").replace(
        "- supersedes: none", f"- supersedes: {prior_slug}"))
    write(lesson, f"- id: {lesson.stem}\n- status: dropped\n- source: fixture\n- category: workflow\n\n# Lesson\n[Proof]({href}#proof)\n")
    before = {path: path.read_bytes() for path in (decision, successor, lesson)}
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    closure_file = root / "closure-input.md"
    write(closure_file, closure(instant))
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "close", "--root", str(root), "--slug", slug,
         "--closure-file", str(closure_file), "--terminal-instant", instant],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    archived = root / "work-items" / "archive" / "2026-10" / slug
    assert archived.is_dir() and not active.exists()
    assert (archived / "evidence.md").read_bytes() == payload
    relocated = href.replace("../active/", "../archive/2026-10/", 1)
    for path, data in before.items():
        assert path.read_bytes() == data.replace(href.encode(), relocated.encode())
        assert (path.parent / relocated).resolve() == archived / "evidence.md"
    receipt = json.loads((archived / module.BUG_DISPOSITIONS_RECEIPT).read_bytes())
    rows = receipt["linkMaintenance"]["consumers"]
    assert {row["source"] for row in rows} == {path.relative_to(root / "work-items").as_posix() for path in before}
    assert all(row["source"] == row["target"] and row["authority"] == "current-metadata" for row in rows)
    for row in rows:
        path = root / "work-items" / row["source"]
        assert row["beforeSha256"].lower() == hashlib.sha256(before[path]).hexdigest()
        assert row["afterSha256"].lower() == hashlib.sha256(path.read_bytes()).hexdigest()
    module.check_readme(root)
    assert module.close_item(root, slug, closure_file.read_bytes(), instant) == archived


@pytest.mark.parametrize("decision_format", ["v0", "h1"])
def test_close_refuses_authentic_read_only_decision_consumers(tmp_path: Path, decision_format: str) -> None:
    module = load_module()
    root, slug = tmp_path / "repo", "2026-10-18-readonly-target"
    instant = "2026-10-18T00:00:00Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "evidence.md", "Referenced payload.\n")
    decision_slug = "2026-08-01-frozen"
    decision = root / "work-items" / "decisions" / f"{decision_slug}.md"
    body = f"[Proof](../active/{slug}/evidence.md)\n"
    if decision_format == "v0":
        write(decision, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {decision_slug}", body=body))
        manifest_writer, preflight = _write_decision_v0_manifest, module._preflight_current_decision_v0
    else:
        write(decision, _legacy_h1_decision_record(status="accepted", body="status: dropped\n\n" + body))
        manifest_writer, preflight = _write_decision_h1_manifest, module._preflight_current_decision_h1
    manifest = manifest_writer(root, [{"path": decision.name, "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(), "state": "admitted"}])
    record = preflight(root)[decision.name]
    assert record.legacy_read_only is True
    assert record.raw_status == ("superseded" if decision_format == "v0" else "accepted")
    assert record.admitted_current_status == (None if decision_format == "v0" else "accepted")
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    closure_file = root / "closure-input.md"
    write(closure_file, closure(instant))
    preserved = {path: path.read_bytes() for path in (root / "work-items").rglob("*") if path.is_file()}
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "close", "--root", str(root), "--slug", slug,
         "--closure-file", str(closure_file), "--terminal-instant", instant],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "WI-CLOSE-LINK-AUTHORITY" in result.stdout + result.stderr
    assert "read-only" in result.stdout + result.stderr
    assert active.is_dir() and not (active / "closure.md").exists()
    assert not (root / "work-items" / "archive" / "2026-10" / slug).exists()
    assert {path: path.read_bytes() for path in preserved} == preserved
    assert manifest.read_bytes() == preserved[manifest]


@pytest.mark.parametrize("status", ["accepted", "superseded", "unknown-state"])
def test_decision_structural_parse_keeps_current_validator_policy(tmp_path: Path, status: str) -> None:
    module = load_module()
    slug = "2026-10-18-parse-policy"
    text = _current_decision_record(slug, status=status)
    path = tmp_path / f"{slug}.md"
    write(path, text)
    before = path.read_bytes()
    if status == "accepted":
        assert module._validate_current_decision_record(path, slug).admitted_current_status == status
    else:
        with pytest.raises(module.LifecycleError) as failure:
            module._validate_current_decision_record(path, slug)
        assert failure.value.failure_id == "WI-DECISION-SCHEMA-INVALID"
    parsed = module._parse_decision_record_text(before.decode("utf-8"), slug)
    assert parsed.raw_status == status and parsed.legacy_read_only is False
    assert parsed.admitted_current_status == (status if status == "accepted" else None)
    assert path.read_bytes() == before


def test_close_updates_owned_ordinary_documents_and_replays_after_owner_advances(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    target_slug, owner_slug = "2026-10-08-target", "2026-10-08-consumer"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, target_slug)
    seed_active(module, root, owner_slug)
    active = root / "work-items" / "active" / target_slug
    owner = root / "work-items" / "active" / owner_slug
    write(active / "evidence.md", "Accepted result.\n")
    target_before = (active / "evidence.md").read_bytes()
    direct = owner / "canonical-artifact-link-authority-design.md"
    nested = owner / "results" / "renamed.MD"
    old_direct = f"../{target_slug}/evidence.md?view=1#proof"
    old_nested = f"../../{target_slug}/evidence.md#proof"
    unrelated = "https://example.invalid/unchanged"
    direct_before = (f"Owner: arbitrary\nRevision: draft-text\n[Proof]({old_direct})\n"
                     f"[Repeat]({old_direct})\n[Other]({unrelated})\n").encode()
    nested_before = b"\xef\xbb\xbf" + f"[Result]({old_nested})\r\nOther prose.\r\n".encode()
    direct.write_bytes(direct_before)
    nested.parent.mkdir()
    nested.write_bytes(nested_before)
    write_empty_bug_dispositions(root, target_slug, instant)
    module.refresh_readme(root)

    archived = module.close_item(root, target_slug, closure(instant).encode(), instant)
    new_direct = f"../../archive/2026-10/{target_slug}/evidence.md?view=1#proof"
    new_nested = f"../../../archive/2026-10/{target_slug}/evidence.md#proof"
    direct_after = direct_before.replace(old_direct.encode(), new_direct.encode())
    nested_after = nested_before.replace(old_nested.encode(), new_nested.encode())
    assert direct.read_bytes() == direct_after
    assert nested.read_bytes() == nested_after
    assert (archived / "evidence.md").read_bytes() == target_before
    assert (direct.parent / new_direct.split("?", 1)[0]).resolve() == archived / "evidence.md"
    assert (nested.parent / new_nested.split("#", 1)[0]).resolve() == archived / "evidence.md"
    module.check_readme(root)
    receipt_path = archived / module.BUG_DISPOSITIONS_RECEIPT
    receipt_before = receipt_path.read_bytes()
    rows = json.loads(receipt_before)["linkMaintenance"]["consumers"]
    assert [row["source"] for row in rows] == [
        f"active/{owner_slug}/canonical-artifact-link-authority-design.md",
        f"active/{owner_slug}/results/renamed.MD",
    ]
    assert all(row["authority"] == "current-metadata" for row in rows)
    assert rows[0]["uriChanges"] == [{"from": old_direct, "to": new_direct}] * 2

    direct.write_bytes(direct_after + b"Later legitimate authoring.\n")
    assert module.close_item(root, target_slug, closure(instant).encode(), instant) == archived
    owner_instant = "2026-10-08T11:15:00Z"
    write_empty_bug_dispositions(root, owner_slug, owner_instant)
    module.refresh_readme(root)
    archived_owner = module.close_item(root, owner_slug, closure(owner_instant).encode(), owner_instant)
    assert module.close_item(root, target_slug, closure(instant).encode(), instant) == archived
    assert receipt_path.read_bytes() == receipt_before
    for forged in ("path", "authority", "suffix"):
        damaged = json.loads(receipt_before)
        row = damaged["linkMaintenance"]["consumers"][0]
        if forged == "path":
            row["source"] = row["target"] = f"active/{owner_slug}/inputs/retained.md"
        elif forged == "authority":
            row["authority"] = "protected-uri-maintenance"
            damaged["linkMaintenance"]["allowProtectedUriUpdates"] = True
        else:
            row["uriChanges"][0]["to"] += "-forged"
        receipt_path.write_text(json.dumps(damaged), encoding="utf-8")
        with pytest.raises(module.LifecycleError) as failure:
            module.close_item(root, target_slug, closure(instant).encode(), instant)
        assert failure.value.failure_id == "WI-IMMUTABLE-ARCHIVE", forged
        assert (archived_owner / direct.name).read_bytes() == direct_after + b"Later legitimate authoring.\n"
    receipt_path.write_bytes(receipt_before)


def test_close_link_consumer_descriptor_preserves_typed_and_protected_boundaries() -> None:
    module = load_module()
    describe = module._close_link_consumer_descriptor
    assert describe("active/valid-owner/results/renamed.MD")[:2] == (
        "active-document", "active/valid-owner")
    assert describe("bugs/valid-bug.md")[0] == "registry"
    for path in (
        "active/valid-owner/inputs/retained.md",
        "active/valid-owner/review-artifact-custody/snapshot.md",
        "active/valid-owner/notes/raw.json", "active/invalid owner/result.md",
        "active/valid-owner/../other.md", "archive/2026-10/old/result.md",
    ):
        assert describe(path) is None


def test_close_link_owner_refuses_missing_duplicate_status_and_native_bytes(tmp_path: Path) -> None:
    module = load_module()
    root, owner_slug = tmp_path / "repo", "2026-10-08-owner"
    seed_active(module, root, owner_slug)
    owner = root / "work-items" / "active" / owner_slug
    consumer = owner / "result.md"
    before = b"[Proof](../other/status.md)\n"
    consumer.write_bytes(before)
    assert module._close_link_authority(root, consumer, before, before, None, False, 1) == "current-metadata"
    with pytest.raises(module.LifecycleError) as native:
        module._close_link_authority(root, consumer, b"%PDF-1.7\n" + before, before, None, False, 1)
    assert native.value.failure_id == "WI-CLOSE-LINK-AUTHORITY"
    duplicate = root / "work-items" / "backlog" / f"{owner_slug}.md"
    duplicate.write_bytes(b"Task: duplicate\n")
    with pytest.raises(module.LifecycleError) as dual:
        module._close_link_authority(root, consumer, before, before, None, False, 1)
    assert dual.value.failure_id == "WI-CLOSE-LINK-AUTHORITY"
    duplicate.unlink()
    status = owner / "status.md"
    status.unlink()
    with pytest.raises(module.LifecycleError) as missing:
        module._close_link_authority(root, consumer, before, before, None, False, 1)
    assert missing.value.failure_id == "WI-CATEGORY-STATUS-INVALID"


def test_close_refuses_changed_consumer_parent_before_any_lifecycle_write(tmp_path: Path) -> None:
    module = load_module()
    root, slug, owner_slug = tmp_path / "repo", "2026-10-08-target", "2026-10-08-owner"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    seed_active(module, root, owner_slug)
    active = root / "work-items" / "active" / slug
    owner = root / "work-items" / "active" / owner_slug
    write(active / "evidence.md", "Accepted result.\n")
    consumer = owner / "result.md"
    consumer_before = f"[Proof](../{slug}/evidence.md)\n".encode()
    consumer.write_bytes(consumer_before)
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    readme_before = (root / "work-items" / "README.md").read_bytes()
    protected = (active / "status.md", root / "work-items" / "README.md")
    identities_before = [(path.stat().st_dev, path.stat().st_ino) for path in protected]
    tree_before = tree_file_bytes(root)
    original = module._plan_parent_archive_links
    def change_owner_after_plan(*args, **kwargs):
        plan = original(*args, **kwargs)
        (owner / "status.md").write_bytes((owner / "status.md").read_bytes() + b"New owner state.\n")
        return plan
    module._plan_parent_archive_links = change_owner_after_plan
    with pytest.raises(module.LifecycleError) as failed:
        module.close_item(root, slug, closure(instant).encode(), instant)
    assert failed.value.failure_id == "WI-CLOSE-LINK-DRIFT"
    assert active.is_dir() and consumer.read_bytes() == consumer_before
    assert (root / "work-items" / "README.md").read_bytes() == readme_before
    assert not (root / "work-items" / "archive" / "2026-10" / slug).exists()
    assert [(path.stat().st_dev, path.stat().st_ino) for path in protected] == identities_before
    owner_status = (owner / "status.md").relative_to(root).as_posix()
    tree_after = tree_file_bytes(root)
    assert {key: value for key, value in tree_after.items() if key != owner_status} == {
        key: value for key, value in tree_before.items() if key != owner_status
    }


def test_close_protected_uri_opt_in_is_bound_and_does_not_freeze_later_authoring(tmp_path: Path) -> None:
    module = load_module()
    root, slug, bug_slug = tmp_path / "repo", "link-preservation", "2026-10-08-protected"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "evidence.md", "Verified target.\n")
    bug = seed_context_bug(root, slug, bug_slug)
    before = bug.read_bytes() + f"[Evidence](../active/{slug}/evidence.md#check)\n".encode()
    bug.write_bytes(before)
    write_bug_dispositions(root, slug, instant, [{
        "id": bug_slug, "action": "preserve-current", "inputSha256": hashlib.sha256(before).hexdigest(),
        "status": "open", "reason": "Still useful current finding.", "evidence": "Original evidence retained.",
    }])
    module.refresh_readme(root)
    readme_before = (root / "work-items" / "README.md").read_bytes()
    with pytest.raises(module.LifecycleError) as omitted:
        module.close_item(root, slug, closure(instant).encode(), instant)
    assert omitted.value.failure_id == "WI-CLOSE-LINK-PRESERVATION"
    assert bug.read_bytes() == before and active.is_dir()
    assert (root / "work-items" / "README.md").read_bytes() == readme_before
    archived = module.close_item(root, slug, closure(instant).encode(), instant, allow_protected_uri_updates=True)
    expected = before.replace(f"../active/{slug}/".encode(), f"../archive/2026-10/{slug}/".encode())
    assert bug.read_bytes() == expected
    receipt_path = archived / module.BUG_DISPOSITIONS_RECEIPT
    receipt_before = receipt_path.read_bytes()
    receipt = json.loads(receipt_before)
    assert receipt["bugs"][0]["afterSha256"] == hashlib.sha256(expected).hexdigest()
    assert receipt["linkMaintenance"]["consumers"][0]["authority"] == "protected-uri-maintenance"
    later = expected + b"Later authorized current authoring.\n"
    bug.write_bytes(later)
    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived
    assert bug.read_bytes() == later and receipt_path.read_bytes() == receipt_before
    for corruption in ("flag", "version", "duplicate", "href"):
        damaged = json.loads(receipt_before)
        maintenance = damaged["linkMaintenance"]
        if corruption == "flag":
            maintenance["allowProtectedUriUpdates"] = False
        elif corruption == "version":
            maintenance["version"] = 2
        elif corruption == "duplicate":
            maintenance["consumers"].append(copy.deepcopy(maintenance["consumers"][0]))
        else:
            maintenance["consumers"][0]["uriChanges"][0]["to"] = "../../private.md?seeded-secret"
        receipt_path.write_text(json.dumps(damaged), encoding="utf-8")
        with pytest.raises(module.LifecycleError) as invalid:
            module.close_item(root, slug, closure(instant).encode(), instant)
        assert invalid.value.failure_id == "WI-IMMUTABLE-ARCHIVE", corruption
        assert "seeded-secret" not in str(invalid.value)
        assert bug.read_bytes() == later
    receipt_path.write_bytes(receipt_before)


def test_close_descendant_links_preserve_suffixes_bom_crlf_and_sibling(tmp_path: Path) -> None:
    module = load_module()
    root, slug = tmp_path / "repo", "descendant-parent"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "nested" / "evidence.md", "Nested target.\n")
    seed_active(module, root, slug + "-other")
    sibling = root / "work-items" / "active" / (slug + "-other") / "evidence.md"
    write(sibling, "Sibling target.\n")
    evidence_before = (active / "nested" / "evidence.md").read_bytes()
    sibling_before = sibling.read_bytes()
    bug = seed_context_bug(root, "standalone", "2026-10-08-suffixes")
    href = f"../active/{slug}/nested/evidence.md?check=1#section"
    noise = f"../active/{slug}-other/evidence.md"
    before = b"\xef\xbb\xbf" + bug.read_bytes().replace(b"\n", b"\r\n")
    before += f"[Проверка]({href})\r\n[Repeat]({href})\r\n[Sibling]({noise})\r\n".encode()
    bug.write_bytes(before)
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    relocated = href.replace("../active/", "../archive/2026-10/", 1)
    assert bug.read_bytes() == before.replace(href.encode(), relocated.encode())
    assert (archived / "nested" / "evidence.md").read_bytes() == evidence_before
    assert sibling.read_bytes() == sibling_before
    receipt = json.loads((archived / module.BUG_DISPOSITIONS_RECEIPT).read_bytes())
    assert receipt["linkMaintenance"]["consumers"][0]["uriChanges"] == [
        {"from": href, "to": relocated}, {"from": href, "to": relocated}
    ]


def test_close_terminalize_link_overlap_uses_final_consumer_location(tmp_path: Path) -> None:
    module = load_module()
    root, slug, bug_slug = tmp_path / "repo", "composed-close", "2026-10-08-composed"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "evidence.md", "Delivered evidence.\n")
    bug = seed_context_bug(root, slug, bug_slug)
    before = bug.read_bytes() + f"[Proof](../active/{slug}/evidence.md#check)\n".encode()
    bug.write_bytes(before)
    write_bug_dispositions(root, slug, instant, [{
        "id": bug_slug, "action": "terminalize", "inputSha256": hashlib.sha256(before).hexdigest(),
        "status": "fixed", "resolution": "Verified outcome.", "evidence": "Accepted QA evidence.",
    }])
    module.refresh_readme(root)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    final_bug = root / "work-items" / "bugs" / "archive" / "2026-10" / bug.name
    href = f"../../../archive/2026-10/{slug}/evidence.md#check"
    assert href in final_bug.read_text(encoding="utf-8")
    assert (final_bug.parent / href.split("#")[0]).resolve() == archived / "evidence.md"
    assert module._parse_fields(final_bug.read_text(encoding="utf-8"))["status"] == "fixed"
    receipt = json.loads((archived / module.BUG_DISPOSITIONS_RECEIPT).read_bytes())
    assert receipt["bugs"][0]["afterSha256"] == hashlib.sha256(final_bug.read_bytes()).hexdigest()
    assert receipt["linkMaintenance"]["consumers"][0]["authority"] == "selected-terminalize"
    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived


@pytest.mark.parametrize("concurrent_authoring", [False, True])
def test_close_uri_rollback_restores_owned_bytes_or_preserves_concurrent_authoring(
    tmp_path: Path, concurrent_authoring: bool,
) -> None:
    module = load_module()
    root, slug = tmp_path / "repo", "rollback-links"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "evidence.md", "Original target.\n")
    bug = seed_context_bug(root, "standalone", "2026-10-08-rollback-link")
    before = bug.read_bytes() + f"[Proof](../active/{slug}/evidence.md)\n".encode()
    bug.write_bytes(before)
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    status_before, readme_before = (active / "status.md").read_bytes(), (root / "work-items" / "README.md").read_bytes()
    original_refresh = module.refresh_readme
    concurrent = None
    def fail_after_move(_root, *, ledger_resource_budget=None):
        nonlocal concurrent
        if concurrent_authoring:
            concurrent = bug.read_bytes() + b"Concurrent user bytes.\n"
            bug.write_bytes(concurrent)
        raise module.LifecycleError("WI-README-STALE", "controlled failure after URI write and item move")
    module.refresh_readme = fail_after_move
    try:
        with pytest.raises(module.LifecycleError) as failure:
            module.close_item(root, slug, closure(instant).encode(), instant)
    finally:
        module.refresh_readme = original_refresh
    assert failure.value.failure_id == ("WI-BUG-DISPOSITIONS-ROLLBACK" if concurrent_authoring else "WI-README-STALE")
    assert bug.read_bytes() == (concurrent if concurrent_authoring else before)
    assert active.is_dir() and (active / "status.md").read_bytes() == status_before
    assert not (root / "work-items" / "archive" / "2026-10" / slug).exists()
    assert (root / "work-items" / "README.md").read_bytes() == readme_before


@pytest.mark.parametrize("consumer_kind", ["bug", "decision-format"])
def test_close_uri_preflight_drift_refuses_without_overwriting_consumer(tmp_path: Path, consumer_kind: str) -> None:
    module = load_module()
    root, slug = tmp_path / "repo", "preflight-link-drift"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "evidence.md", "Original target.\n")
    href = f"[Proof](../active/{slug}/evidence.md)\n"
    if consumer_kind == "bug":
        bug = seed_context_bug(root, "standalone", "2026-10-08-preflight-link")
        before = bug.read_bytes() + href.encode()
        changed = before + b"Concurrent current authoring.\n"
    else:
        bug = root / "work-items" / "decisions" / "2026-10-08-preflight-link.md"
        before = _current_decision_record(bug.stem, status="accepted", body=href).encode()
        changed = _legacy_v0_decision_record(status="accepted", identity_line=f"id: {bug.stem}", body=href + "Concurrent format authoring.\n").encode()
        bug.parent.mkdir(parents=True, exist_ok=True)
    bug.write_bytes(before)
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    original = module._close_link_authority
    def classify_then_change(*args, **kwargs):
        authority = original(*args, **kwargs)
        bug.write_bytes(changed)
        return authority
    module._close_link_authority = classify_then_change
    with pytest.raises(module.LifecycleError) as failure:
        module.close_item(root, slug, closure(instant).encode(), instant)
    assert failure.value.failure_id == "WI-CLOSE-LINK-DRIFT", f"{failure.value!r}; cause={failure.value.__cause__!r}"
    assert bug.read_bytes() == changed and active.is_dir()
    assert not (root / "work-items" / "archive" / "2026-10" / slug).exists()


def test_close_existing_closure_prewrite_drift_verifies_unchanged_native_preimages(tmp_path: Path) -> None:
    module = load_module()
    root, slug = tmp_path / "repo", "existing-closure-link-drift"
    instant = "2026-10-18T00:00:00Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "evidence.md", "Original retained target.\n")
    write(active / "closure.md", closure(instant))
    bug = seed_context_bug(root, "standalone", "2026-10-18-existing-closure-link")
    before = bug.read_bytes() + f"[Proof](../active/{slug}/evidence.md)\n".encode()
    bug.write_bytes(before)
    changed = before + b"Concurrent consumer authoring.\n"
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    paths = (active / "status.md", active / "closure.md", active / "evidence.md",
             root / "work-items" / "README.md")
    preimages = {path: (path.read_bytes(), module._lifecycle_file_identity(path.lstat())) for path in paths}
    classify = module._close_link_authority
    qualify = module.LifecycleTransaction.qualify_owned_inverse
    write_atomic = module._atomic_write
    retained, inverses, writes = {}, [], []

    def classify_then_change(*args):
        authority = classify(*args)
        held = module._CURRENT_LIFECYCLE_TRANSACTION.get()
        for path in paths[:2]:
            retained[path] = held._retained_observations.get(path)
        bug.write_bytes(changed)
        return authority

    def record_inverse(held, origin, **kwargs):
        inverses.append(origin)
        return qualify(held, origin, **kwargs)

    def record_write(path, data):
        writes.append(path)
        return write_atomic(path, data)

    module._close_link_authority = classify_then_change
    module.LifecycleTransaction.qualify_owned_inverse = record_inverse
    module._atomic_write = record_write
    with pytest.raises(module.LifecycleError) as failure:
        module.close_item(root, slug, closure(instant).encode(), instant)
    assert failure.value.failure_id == "WI-CLOSE-LINK-DRIFT"
    assert not inverses and not writes
    for path in paths[:2]:
        assert isinstance(retained[path], module.CapturedFileSnapshot)
        assert (retained[path].data, retained[path].identity) == preimages[path]
    for path, preimage in preimages.items():
        assert (path.read_bytes(), module._lifecycle_file_identity(path.lstat())) == preimage
    assert bug.read_bytes() == changed and active.is_dir()
    assert not (root / "work-items" / "archive" / "2026-10" / slug).exists()


def test_close_uri_target_drift_preserves_actual_target_and_restores_consumer(tmp_path: Path) -> None:
    module = load_module()
    root, slug = tmp_path / "repo", "2026-10-18-target-drift"
    instant = "2026-10-18T00:00:00Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    evidence = active / "evidence.md"
    write(evidence, "Original target.\n")
    decision = root / "work-items" / "decisions" / "2026-10-18-target-consumer.md"
    write(decision, _current_decision_record(decision.stem, status="accepted", body=f"[Proof](../active/{slug}/evidence.md)\n"))
    before = decision.read_bytes()
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    status_before, readme_before = (active / "status.md").read_bytes(), (root / "work-items" / "README.md").read_bytes()
    original = module._verify_parent_archive_link_targets
    injected = []
    changed = b"Concurrent target authoring.\n"

    def change_target_then_verify(plan, *, archived, failure_id):
        if not archived and not injected:
            evidence.write_bytes(changed)
            injected.append(True)
        return original(plan, archived=archived, failure_id=failure_id)

    module._verify_parent_archive_link_targets = change_target_then_verify
    with pytest.raises(module.LifecycleError) as failure:
        module.close_item(root, slug, closure(instant).encode(), instant)
    assert injected and failure.value.failure_id == "WI-CLOSE-LINK-DRIFT", f"{failure.value!r}; cause={failure.value.__cause__!r}"
    assert evidence.read_bytes() == changed and decision.read_bytes() == before
    assert active.is_dir() and (active / "status.md").read_bytes() == status_before
    assert (root / "work-items" / "README.md").read_bytes() == readme_before
    assert not (active / "closure.md").exists()
    assert not (root / "work-items" / "archive" / "2026-10" / slug).exists()


def test_close_link_uri_delta_refuses_non_href_authoring() -> None:
    module = load_module()
    before = b"status: accepted\n[Proof](../active/target/evidence.md#proof)\n"
    after = before.replace(b"active/", b"archive/2026-10/").replace(b"accepted", b"superseded")
    with pytest.raises(module.LifecycleError) as failure:
        module._close_link_uri_changes(before, after)
    assert failure.value.failure_id == "WI-CLOSE-LINK-VERIFY"


def test_close_v2_unselected_placeholder_requires_public_positive_uri_flag(tmp_path: Path) -> None:
    module = load_module()
    root, slug = tmp_path / "repo", "v2-placeholder-links"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "evidence.md", "Original evidence.\n")
    bug = seed_context_bug(root, "standalone", "2026-10-08-v2-unselected")
    before = bug.read_bytes() + f"[Proof](../active/{slug}/evidence.md#check)\n".encode()
    bug.write_bytes(before)
    manifest_path = write_empty_bug_dispositions(root, slug, instant)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["schemaVersion"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    module.refresh_readme(root)
    with pytest.raises(module.LifecycleError) as omitted:
        module.close_item(root, slug, closure(instant).encode(), instant)
    assert omitted.value.failure_id == "WI-CLOSE-LINK-PRESERVATION"
    assert bug.read_bytes() == before and active.is_dir()
    input_closure = root / "closure-input.md"
    input_closure.write_text(closure(instant), encoding="utf-8")
    result = subprocess.run([
        sys.executable, "-B", str(SCRIPT), "close", "--root", str(root), "--slug", slug,
        "--closure-file", str(input_closure), "--terminal-instant", instant,
        "--allow-protected-uri-updates",
    ], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    archived = root / "work-items" / "archive" / "2026-10" / slug
    expected = before.replace(f"../active/{slug}/".encode(), f"../archive/2026-10/{slug}/".encode())
    assert bug.read_bytes() == expected
    receipt = json.loads((archived / module.BUG_DISPOSITIONS_RECEIPT).read_bytes())
    assert receipt["bugs"] == []
    assert receipt["linkMaintenance"]["allowProtectedUriUpdates"] is True
    assert receipt["linkMaintenance"]["consumers"][0]["authority"] == "protected-uri-maintenance"


def test_close_uri_failure_after_receipt_restores_preimages(tmp_path: Path) -> None:
    module = load_module()
    root, slug = tmp_path / "repo", "post-receipt-links"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "evidence.md", "Target before move.\n")
    bug = seed_context_bug(root, "standalone", "2026-10-08-post-receipt")
    before = bug.read_bytes() + f"[Proof](../active/{slug}/evidence.md)\n".encode()
    bug.write_bytes(before)
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    readme_before = (root / "work-items" / "README.md").read_bytes()
    original_verify = module._verify_archived_bug_dispositions
    def reject_written_receipt(*args, **kwargs):
        original_verify(*args, **kwargs)
        assert (args[1] / module.BUG_DISPOSITIONS_RECEIPT).is_file()
        raise module.LifecycleError("WI-CLOSE-LINK-VERIFY", "controlled failure after verified receipt")
    module._verify_archived_bug_dispositions = reject_written_receipt
    with pytest.raises(module.LifecycleError) as failure:
        module.close_item(root, slug, closure(instant).encode(), instant)
    assert failure.value.failure_id == "WI-CLOSE-LINK-VERIFY"
    assert bug.read_bytes() == before and active.is_dir()
    assert not (active / module.BUG_DISPOSITIONS_RECEIPT).exists()
    assert not (root / "work-items" / "archive" / "2026-10" / slug).exists()
    assert (root / "work-items" / "README.md").read_bytes() == readme_before


@pytest.mark.parametrize("state,with_uri", [
    ("occupied-source", True), ("occupied-source", False),
    ("drifted-target", True), ("drifted-source-before-move", False),
])
def test_close_bug_compensation_preserves_unowned_source_and_target_images(
    tmp_path: Path, state: str, with_uri: bool,
) -> None:
    """S1 and distinct moved/unmoved compensation states, including legacy no-URI."""
    module = load_module()
    root, slug, bug_slug = tmp_path / "repo", "compensation-images", "2026-10-08-compensation"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, slug)
    active = root / "work-items" / "active" / slug
    write(active / "evidence.md", "Delivered target.\n")
    bug = seed_context_bug(root, slug, bug_slug)
    before = bug.read_bytes()
    if with_uri:
        before += f"[Proof](../active/{slug}/evidence.md#check)\n".encode()
    bug.write_bytes(before)
    write_bug_dispositions(root, slug, instant, [{
        "id": bug_slug, "action": "terminalize", "inputSha256": hashlib.sha256(before).hexdigest(),
        "status": "fixed", "resolution": "Verified fix.", "evidence": "Accepted synthetic QA.",
    }])
    module.refresh_readme(root)
    archived_bug = root / "work-items" / "bugs" / "archive" / "2026-10" / bug.name
    concurrent = b"Distinct concurrent author bytes; preserve exactly.\n"
    archived_before_failure = None
    original_refresh, original_replace = module.refresh_readme, module.os.replace
    def fail_after_move(_root):
        nonlocal archived_before_failure
        archived_before_failure = archived_bug.read_bytes()
        if state == "occupied-source":
            bug.write_bytes(concurrent)
        elif state == "drifted-target":
            archived_bug.write_bytes(concurrent)
        raise module.LifecycleError("WI-README-STALE", "S1 controlled failure after bug and parent moves")
    def fail_bug_move(source, target):
        if Path(source) == bug and Path(target) == archived_bug:
            bug.write_bytes(concurrent)
            raise OSError("controlled failure before bug archive move")
        return original_replace(source, target)
    if state == "drifted-source-before-move":
        module.os.replace = fail_bug_move
    else:
        module.refresh_readme = fail_after_move
    try:
        with pytest.raises(module.LifecycleError) as failure:
            module.close_item(root, slug, closure(instant).encode(), instant)
    finally:
        module.refresh_readme, module.os.replace = original_refresh, original_replace
    assert failure.value.failure_id == "WI-BUG-DISPOSITIONS-ROLLBACK"
    assert failure.value.__cause__ is not None
    if state == "occupied-source":
        assert bug.read_bytes() == concurrent
        assert archived_bug.read_bytes() == archived_before_failure
    elif state == "drifted-target":
        assert not bug.exists()
        assert archived_bug.read_bytes() == concurrent
    else:
        assert bug.read_bytes() == concurrent
        assert not archived_bug.exists()
    assert active.is_dir()


@pytest.mark.parametrize("state", ["dual-locations", "target-before-image", "known-before-only"])
def test_successor_recovery_rejects_ambiguous_bug_location_images(tmp_path: Path, state: str) -> None:
    """Supported recover-transition must retain ambiguous data and its intent."""
    module = load_module()
    root, parent, bug_slug = tmp_path / "repo", "recovery-parent", "2026-10-08-recovery-bug"
    seed_active(module, root, parent)
    item = root / "work-items" / "active" / parent
    recorded = run_ledger(item, "append", "--run-id", "recovery-synthetic-terminal", "--role", "qa-engineer",
        "--execution-role", "internal", "--status", "completed", "--gate", "none", "--scope", "synthetic recovery",
        "--started-at", "2026-10-08T00:00:00Z", "--updated-at", "2026-10-08T00:00:00Z")
    assert recorded.returncode == 0, recorded.stdout
    bug = seed_context_bug(root, parent, bug_slug)
    before = bug.read_bytes()
    instant, operation = "2026-10-08T00:05:00Z", "recovery-image-operation"
    write_bug_dispositions(root, parent, instant, [{
        "id": bug_slug, "action": "terminalize", "inputSha256": hashlib.sha256(before).hexdigest(),
        "status": "fixed", "resolution": "Verified fix.", "evidence": "Accepted synthetic evidence.",
    }])
    module.refresh_readme(root)
    ledger_sha = hashlib.sha256((item / "agent-runs.jsonl").read_bytes()).hexdigest()
    readme_sha = hashlib.sha256((root / "work-items" / "README.md").read_bytes()).hexdigest()
    successor = (f"Task: Continue independent scope.\nContinues: {parent}\nObligation-transfer: {operation}\n"
                 "Next action: Inspect scope.\nupdated: 2026-10-08T00:05:00Z\n").encode()
    transfer = json.dumps({"schemaVersion": 1, "sourceWorkItem": parent, "successorWorkItem": "recovery-successor",
        "expectedSourceLedgerSha256": ledger_sha, "obligations": []}).encode()
    with pytest.raises(module.LifecycleError) as interrupted:
        module.archive_with_successor(root, parent, closure(instant).encode(), instant, "recovery-successor",
            successor, operation, ledger_sha, readme_sha, obligation_transfer_data=transfer,
            inject_failure_at="T0" if state == "known-before-only" else "T1")
    assert interrupted.value.failure_id == "WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE"
    archived_bug = root / "work-items" / "bugs" / "archive" / "2026-10" / bug.name
    if state == "dual-locations":
        bug.write_bytes(before)  # Occupied source even though its bytes match a known image.
    elif state == "target-before-image":
        archived_bug.write_bytes(before)  # Wrong image at the moved target is not ownership.
    source_before = bug.read_bytes() if bug.exists() else None
    target_before = archived_bug.read_bytes() if archived_bug.exists() else None
    source_identity = module._lifecycle_file_identity(bug.lstat()) if bug.exists() else None
    intent = module._transition_intent_path(root, operation)
    intent_before = intent.read_bytes()
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), "recover-transition", "--root", str(root),
                             "--operation-id", operation, "--apply"], capture_output=True, text=True, timeout=30)
    if state == "known-before-only":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "outcome=rolled-back" in result.stdout and not intent.exists()
        assert bug.read_bytes() == before and not archived_bug.exists()
        assert module._lifecycle_file_identity(bug.lstat()) == source_identity
        return
    assert result.returncode != 0, result.stdout + result.stderr
    assert "WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE" in result.stderr + result.stdout
    assert (bug.read_bytes() if bug.exists() else None) == source_before
    assert archived_bug.read_bytes() == target_before
    assert intent.read_bytes() == intent_before


def seed_retained_scratch_manifest(
    module,
    root: Path,
    slug: str,
    instant: str,
    *,
    leaf_name: str = "historical-evidence",
    regular_file: bool = False,
):
    seed_active(module, root, slug)
    item = root / "work-items" / "active" / slug
    retained = root / ".scratch" / "work-items" / slug / "run-001" / leaf_name
    if regular_file:
        write(retained, f"preserve {leaf_name} historical evidence\n")
    else:
        write(retained / "proof.txt", "preserve this historical evidence\n")
    pointer = item / "historical-evidence.md"
    write(pointer, f"{leaf_name}\n")
    retained_before = module._payload_digest(retained)[1]
    pointer_before = pointer.read_bytes()
    manifest = {
        "schemaVersion": 3,
        "workItem": slug,
        "closedAt": instant,
        "bugs": [],
        "evidenceRetention": [
            {
                "path": retained.relative_to(root).as_posix(),
                "disposition": "retain",
                "treeSha256": retained_before,
                "canonicalPointer": pointer.relative_to(item).as_posix(),
                "canonicalPointerSha256": hashlib.sha256(pointer_before).hexdigest(),
            }
        ],
    }
    (item / "bug-dispositions.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return item, retained, pointer, retained_before, pointer_before, manifest


def test_close_retains_declared_unmatched_scratch_evidence_root(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-scratch-root"
    instant = "2026-08-11T10:00:00Z"
    item, retained, pointer, retained_before, pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert module._payload_digest(retained)[1] == retained_before
    assert archived == root / "work-items" / "archive" / "2026-08" / slug
    archived_pointer = archived / pointer.name
    assert archived_pointer.read_bytes() == pointer_before
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8"))
    assert receipt["evidenceRetention"] == manifest["evidenceRetention"]

    shutil.rmtree(retained.parent)
    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived


def test_close_retains_declared_unmatched_regular_file_scratch_evidence(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-scratch-file"
    instant = "2026-08-11T10:00:30Z"
    _item, retained, pointer, retained_before, pointer_before, manifest = seed_retained_scratch_manifest(
        module,
        root,
        slug,
        instant,
        leaf_name="receiving_probe.py",
        regular_file=True,
    )

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert retained.is_file()
    assert module._payload_digest(retained)[1] == retained_before
    assert (archived / pointer.name).read_bytes() == pointer_before
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8"))
    assert receipt["evidenceRetention"] == manifest["evidenceRetention"]
    retained.unlink()
    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived


def test_close_retention_receipt_accepts_relative_repository_root(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-relative-root"
    instant = "2026-08-11T10:00:45Z"
    item, retained, _pointer, retained_before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    closure_path = root / "closure.md"
    closure_path.write_text(closure(instant), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "close",
            "--root",
            ".",
            "--slug",
            slug,
            "--closure-file",
            str(closure_path),
            "--terminal-instant",
            instant,
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archived = root / "work-items" / "archive" / "2026-08" / slug
    assert result.stdout.strip() == str(archived.resolve())
    assert module._payload_digest(retained)[1] == retained_before
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8"))
    assert receipt["evidenceRetention"] == manifest["evidenceRetention"]
    assert not item.exists()


def test_close_retention_receipt_preserves_unsorted_manifest_row_order(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-unsorted-order"
    instant = "2026-08-11T10:01:15Z"
    item, retained, _pointer, retained_before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant, leaf_name="zeta-capture"
    )
    file_leaf = root / ".scratch" / "work-items" / slug / "run-002" / "alpha_probe.py"
    write(file_leaf, "preserve alpha_probe.py historical evidence\n")
    file_pointer = item / "alpha-probe.md"
    write(file_pointer, "alpha_probe.py\n")
    manifest["evidenceRetention"].append(
        {
            "path": file_leaf.relative_to(root).as_posix(),
            "disposition": "retain",
            "treeSha256": module._payload_digest(file_leaf)[1],
            "canonicalPointer": file_pointer.relative_to(item).as_posix(),
            "canonicalPointerSha256": hashlib.sha256(file_pointer.read_bytes()).hexdigest(),
        }
    )
    (item / "bug-dispositions.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    closure_path = root / "closure.md"
    closure_path.write_text(closure(instant), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "close",
            "--root",
            ".",
            "--slug",
            slug,
            "--closure-file",
            str(closure_path),
            "--terminal-instant",
            instant,
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archived = root / "work-items" / "archive" / "2026-08" / slug
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8"))
    assert receipt["evidenceRetention"] == manifest["evidenceRetention"]
    assert module._payload_digest(retained)[1] == retained_before
    assert file_leaf.read_text(encoding="utf-8") == "preserve alpha_probe.py historical evidence\n"
    file_leaf.unlink()
    shutil.rmtree(retained)
    assert module.close_item(root, slug, closure_path.read_bytes(), instant) == archived


def test_close_relative_root_rejects_undeclared_scratch_leaf(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-with-undeclared-leaf"
    instant = "2026-08-11T10:01:30Z"
    item, retained, _pointer, retained_before, _pointer_before, _manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    undeclared = root / ".scratch" / "work-items" / slug / "run-002" / "extra.txt"
    write(undeclared, "unclaimed evidence\n")
    undeclared_before = undeclared.read_bytes()
    closure_path = root / "closure.md"
    closure_path.write_text(closure(instant), encoding="utf-8")
    manifest_before = (item / "bug-dispositions.json").read_bytes()

    result = subprocess.run(
        [
            sys.executable, str(SCRIPT), "close", "--root", ".", "--slug", slug,
            "--closure-file", str(closure_path), "--terminal-instant", instant,
        ],
        cwd=root, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 1
    assert "WI-SCRATCH-OWNERSHIP-INCOMPLETE" in result.stdout
    assert item.is_dir()
    assert (item / "bug-dispositions.json").read_bytes() == manifest_before
    assert module._payload_digest(retained)[1] == retained_before
    assert undeclared.read_bytes() == undeclared_before
    assert not (root / "work-items" / "archive" / "2026-08" / slug).exists()


def test_retained_scratch_hash_drift_and_close_rollback_preserve_active_state(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-08-11T10:01:00Z"

    drift_root = tmp_path / "drift"
    drift_slug = "retained-scratch-drift"
    drift_item, retained, _pointer, retained_before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, drift_root, drift_slug, instant
    )
    manifest["evidenceRetention"][0]["treeSha256"] = "0" * 64
    (drift_item / "bug-dispositions.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    try:
        module.close_item(drift_root, drift_slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-DRIFT"
    else:
        raise AssertionError("retained scratch hash drift was accepted")
    assert module._payload_digest(retained)[1] == retained_before
    assert drift_item.is_dir()

    rollback_root = tmp_path / "rollback"
    rollback_slug = "retained-scratch-rollback"
    item, retained, pointer, retained_before, pointer_before, _manifest = seed_retained_scratch_manifest(
        module, rollback_root, rollback_slug, instant
    )
    try:
        module.close_item(
            rollback_root,
            rollback_slug,
            closure(instant).encode(),
            instant,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected close failure did not roll back")
    assert item.is_dir()
    assert pointer.read_bytes() == pointer_before
    assert module._payload_digest(retained)[1] == retained_before
    assert not (rollback_root / "work-items" / "archive" / "2026-08" / rollback_slug).exists()


def test_retained_scratch_pointer_parent_link_is_rejected_before_archive(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-pointer-parent-link"
    instant = "2026-08-11T10:02:00Z"
    item, retained, _pointer, retained_before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    external = tmp_path / "external-pointer"
    write(external / "proof.md", "historical-evidence\n")
    linked_parent = item / "linked-parent"
    try:
        os.symlink(external, linked_parent, target_is_directory=True)
    except OSError as exc:
        raise AssertionError("parent-link retention regression requires symlink support") from exc
    external_pointer = external / "proof.md"
    manifest["evidenceRetention"][0]["canonicalPointer"] = "linked-parent/proof.md"
    manifest["evidenceRetention"][0]["canonicalPointerSha256"] = hashlib.sha256(
        external_pointer.read_bytes()
    ).hexdigest()
    (item / "bug-dispositions.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-INVALID"
    else:
        raise AssertionError("canonical pointer escaped through a linked parent")

    assert item.is_dir()
    assert module._payload_digest(retained)[1] == retained_before
    assert external_pointer.read_text(encoding="utf-8") == "historical-evidence\n"
    assert not (root / "work-items" / "archive" / "2026-08" / slug).exists()


def test_retained_payload_digest_optional_limits_keep_legacy_golden_bytes(
    tmp_path: Path,
) -> None:
    module = load_module()
    payload = tmp_path / "payload"
    (payload / "proof.txt").parent.mkdir(parents=True, exist_ok=True)
    (payload / "proof.txt").write_bytes(b"proof\n")
    (payload / "nested").mkdir()
    (payload / "nested" / "data.bin").write_bytes(b"xy")

    assert module._payload_digest(payload) == (
        "sha256-tree-entries-v1",
        "81dfbcb39577424a703e807dd5712bdb0d3decf231edd85327e3438a48ffba5f",
    )
    legacy_file = tmp_path / "legacy-file.txt"
    legacy_file.write_bytes(b"legacy file\n")
    assert module._payload_digest(legacy_file) == (
        "sha256-file-bytes-v1",
        "2ed93b04807efb14d2186e20bb6f8c45264a32d08bd97df62316cccd6ded4894",
    )
    assert module._payload_digest(
        payload,
        limits=module.PayloadDigestLimits(
            max_files=8, max_entries=8, max_bytes=1024
        ),
    ) == module._payload_digest(payload)

    cases = (
        (module.PayloadDigestLimits(max_files=8, max_entries=1, max_bytes=1024), "entry"),
        (module.PayloadDigestLimits(max_files=1, max_entries=8, max_bytes=1024), "file"),
        (module.PayloadDigestLimits(max_files=8, max_entries=8, max_bytes=1), "byte"),
    )
    for limits, label in cases:
        try:
            module._payload_digest(payload, limits=limits)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-MIGRATION-PAYLOAD", label
        else:
            raise AssertionError(f"{label} payload limit was accepted")


def test_retained_payload_digest_limit_stops_scandir_before_preloading(tmp_path: Path) -> None:
    module = load_module()
    payload = tmp_path / "payload"
    for name in ("one.txt", "two.txt", "three.txt"):
        write(payload / name, name + "\n")

    original_scandir = module.os.scandir
    consumed: list[str] = []
    closed: list[bool] = []

    class TrackingScandir:
        def __init__(self, path) -> None:
            self._context = original_scandir(path)
            self._iterator = self._context.__enter__()
            self._track = Path(path) == payload
            self._closed = False

        def __iter__(self):
            return self

        def __next__(self):
            entry = next(self._iterator)
            if self._track:
                consumed.append(entry.name)
            return entry

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            self._closed = True
            if self._track:
                closed.append(self._closed)
            self._context.__exit__(exc_type, exc, traceback)

    with patch.object(module.os, "scandir", side_effect=TrackingScandir):
        try:
            module._payload_digest(
                payload,
                limits=module.PayloadDigestLimits(
                    max_files=8, max_entries=1, max_bytes=1024
                ),
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-MIGRATION-PAYLOAD"
        else:
            raise AssertionError("bounded payload walk accepted three entries")

    assert len(consumed) == 2
    assert closed == [True]


def test_retained_evidence_limits_use_cleanup_owner_ceilings(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-ceiling"
    instant = "2026-08-11T10:02:30Z"
    item, retained, _pointer, _before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    write(retained / "second-proof.txt", "second retained proof\n")
    manifest["evidenceRetention"][0]["treeSha256"] = module._payload_digest(retained)[1]

    classifier = module._scratch_classifier_module()
    with (
        patch.object(module, "_scratch_classifier_module", return_value=classifier),
        patch.object(classifier, "MAX_OWNED_TREE_FILES", 1),
    ):
        try:
            module._prepare_evidence_retention(root, item, manifest)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-SCRATCH-UNSAFE-ENTRY"
        else:
            raise AssertionError("retained evidence exceeded the cleanup owner file ceiling")


def test_retained_evidence_pointer_requires_literal_root_or_manifest_path(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-11T10:02:45Z"
    cases = (
        ("plain", "historical-evidence", "historical-evidence\n", True),
        ("quoted", "historical-evidence", '"historical-evidence"\n', True),
        (
            "manifest-path-with-spaces",
            "historical evidence",
            ".scratch/work-items/retained-manifest-path-with-spaces/run-001/historical evidence\n",
            True,
        ),
        ("catalog", "log", "catalog\n", False),
        ("unrelated-label", "evidence", "unrelated-evidence-label\n", False),
        ("wrong-path", "log", "wrong/path/log\n", False),
    )
    for suffix, leaf_name, pointer_text, accepted in cases:
        root = tmp_path / suffix
        slug = f"retained-{suffix}"
        item, _retained, pointer, _before, _pointer_before, manifest = seed_retained_scratch_manifest(
            module, root, slug, instant, leaf_name=leaf_name
        )
        pointer.write_text(pointer_text, encoding="utf-8")
        manifest["evidenceRetention"][0]["canonicalPointerSha256"] = hashlib.sha256(
            pointer.read_bytes()
        ).hexdigest()

        if accepted:
            plans = module._prepare_evidence_retention(root, item, manifest)
            assert len(plans) == 1, suffix
            continue
        try:
            module._prepare_evidence_retention(root, item, manifest)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-DRIFT", suffix
        else:
            raise AssertionError(f"false pointer reference was admitted: {suffix}")


def test_retained_evidence_pointer_snapshot_limit_fails_before_hashing(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-pointer-limit"
    instant = "2026-08-11T10:03:00Z"
    item, _retained, _pointer, _before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    capture = module._capture_file_snapshot

    def capture_with_tiny_limit(path: Path, *, failure_id: str, maximum_bytes: int = 4 * 1024 * 1024):
        return capture(path, failure_id=failure_id, maximum_bytes=1)

    with patch.object(module, "_capture_file_snapshot", side_effect=capture_with_tiny_limit):
        try:
            module._prepare_evidence_retention(root, item, manifest)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-INVALID"
        else:
            raise AssertionError("oversized canonical pointer was admitted")


def successor_binding_bytes(
    source_slug: str,
    successor_bytes: bytes,
    operation_id: str,
    *,
    accepted_by: str = "receiving-owner",
) -> bytes:
    return (
        json.dumps(
            {
                "schemaVersion": 1,
                "operationId": operation_id,
                "sourceReference": f"bug:{source_slug}",
                "registryReference": "external-bug-registry",
                "recordReference": "bug:accepted-successor",
                "recordSha256": hashlib.sha256(successor_bytes).hexdigest(),
                "acceptedBy": accepted_by,
                "acceptedAt": "2026-09-10T08:00:00Z",
                "acceptanceEvidence": "Receiving owner accepted the current successor.",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def successor_link_inventory_bytes(
    source_slug: str,
    source_bytes: bytes,
    binding_bytes: bytes,
    operation_id: str,
    links: list[dict] | None = None,
) -> bytes:
    return (
        json.dumps(
            {
                "schemaVersion": 1,
                "owner": "mutate-work-item:current-bug-supersession-v1",
                "operationId": operation_id,
                "sourceReference": f"bug:{source_slug}",
                "sourceBugSha256": hashlib.sha256(source_bytes).hexdigest(),
                "successorBindingSha256": hashlib.sha256(binding_bytes).hexdigest(),
                "links": [] if links is None else links,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def tree_file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def historical_pass_fixture(tmp_path: Path):
    module = load_module()
    root = tmp_path / "repo"
    slug = "historical-pass"
    seed_active(module, root, slug)
    item = root / "work-items" / "active" / slug
    original = root / ".scratch" / "approved" / "original.md"
    write(original, "Original accepted artifact bytes.\n")
    source = root / "original-copy.md"
    source.write_bytes(original.read_bytes())
    event = {
        "schemaVersion": 2, "runId": "historical-pass-001", "workItem": slug,
        "role": "qa-engineer", "executionRole": "internal", "status": "completed",
        "gate": "PASS", "scope": ["historical artifact"],
        "artifact": ".scratch/approved/original.md", "eventKind": "standalone",
        "evidence": [{"kind": "review", "ref": "Original acceptance recorded"}],
        "startedAt": "2026-09-30T00:00:00Z", "updatedAt": "2026-09-30T00:00:00Z",
    }
    raw = json.dumps(event, separators=(",", ":")).encode("utf-8")
    # Physical ordinal and CR/LF-excluding identity must survive blank lines.
    ledger_bytes = b"\n" + raw + b"\r\n"
    (item / "agent-runs.jsonl").write_bytes(ledger_bytes)
    args = (
        "retain-pass-artifact", "--root", str(root), "--slug", slug,
        "--run-id", event["runId"], "--raw-line-ordinal", "2",
        "--expected-raw-line-sha256", hashlib.sha256(raw).hexdigest(),
        "--expected-ledger-sha256", hashlib.sha256(ledger_bytes).hexdigest(),
        "--source-artifact", "original-copy.md", "--expected-original-sha256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    return module, root, item, original, source, event, ledger_bytes, args


def test_historical_pass_custody_cli_restores_exact_active_and_archive_authority(tmp_path: Path) -> None:
    module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path)
    validator = module._load_agent_run_ledger().load_validator()
    baseline = []
    assert validator.validate_work_item(item, authority_state_out=baseline) == []
    original.unlink()
    assert any("artifact does not exist" in error for error in validator.validate_work_item(item))

    result = run_cli(*args, "--apply")

    assert result.returncode == 0, result.stdout
    assert "WI-PASS-CUSTODY:" in result.stdout
    assert (item / "agent-runs.jsonl").read_bytes() == before
    current = []
    assert validator.validate_work_item(item, authority_state_out=current) == []
    assert current == baseline
    # Replacement current-path bytes must not stand in for the old artifact.
    original.write_bytes(b"Replacement bytes, not the accepted artifact.\n")
    assert validator.validate_work_item(item) == []
    archive = root / "work-items" / "archive" / "2026-10" / item.name
    archive.parent.mkdir(parents=True)
    shutil.move(str(item), archive)
    archived_errors, open_revise, open_launches = validator.validate_archived_ledger_obligations(archive)
    assert (archived_errors, open_revise, open_launches) == ([], [], [])
    assert (archive / "agent-runs.jsonl").read_bytes() == before
    association = next((archive / "review-artifact-custody" / "historical-pass").iterdir())
    snapshot = archive / json.loads(association.read_bytes())["snapshot"]
    assert snapshot.read_bytes() == source.read_bytes()
    snapshot.write_bytes(b"Replacement bytes, not the accepted artifact.\n")
    assert any("WI-LEDGER-CUSTODY-SNAPSHOT-MISMATCH" in error
               for error in validator.validate_archived_ledger_obligations(archive)[0])


def test_historical_pass_custody_omitted_apply_and_rewritten_source_preserve_bytes(tmp_path: Path) -> None:
    module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path)
    original.unlink()
    untouched = tree_file_bytes(root)
    refusal = run_cli(*args)
    assert refusal.returncode != 0 and "WI-LEDGER-CUSTODY-APPLY-REQUIRED" in refusal.stdout
    assert tree_file_bytes(root) == untouched
    with unittest.TestCase().assertRaises(module.LifecycleError) as failure:
        module.retain_historical_pass_custody(
            root, item.name, event["runId"], 2, args[args.index("--expected-raw-line-sha256") + 1],
            args[args.index("--expected-ledger-sha256") + 1], "original-copy.md",
            args[args.index("--expected-original-sha256") + 1],
        )
    assert failure.exception.failure_id == "WI-LEDGER-CUSTODY-APPLY-REQUIRED"
    assert tree_file_bytes(root) == untouched
    source.write_bytes(b"Rewritten current candidate, not the original.\n")
    untouched = tree_file_bytes(root)
    refusal = run_cli(*args, "--apply")
    assert refusal.returncode != 0 and "WI-LEDGER-CUSTODY-SOURCE-DRIFT" in refusal.stdout
    assert tree_file_bytes(root) == untouched
    assert (item / "agent-runs.jsonl").read_bytes() == before


def test_historical_pass_custody_exact_replay_after_append_is_publication_free(tmp_path: Path) -> None:
    module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path)
    original.unlink()
    assert run_cli(*args, "--apply").returncode == 0
    terminal = {**event, "runId": "later-neutral-terminal", "gate": "none"}
    terminal.pop("artifact")
    (item / "agent-runs.jsonl").write_bytes(before + json.dumps(terminal).encode("utf-8") + b"\n")
    untouched = tree_file_bytes(root)
    replay = run_cli(*args, "--apply")
    assert replay.returncode == 0, replay.stdout
    assert tree_file_bytes(root) == untouched
    conflicted = list(args)
    conflicted[conflicted.index("--expected-original-sha256") + 1] = "0" * 64
    refusal = run_cli(*conflicted, "--apply")
    assert refusal.returncode != 0 and "WI-LEDGER-CUSTODY-STALE-TARGET" in refusal.stdout
    assert tree_file_bytes(root) == untouched


def test_historical_pass_custody_tampered_prefix_ordinal_and_codec_fail_closed(tmp_path: Path) -> None:
    for defect in ("ledger-prefix", "ordinal", "noncanonical-envelope"):
        module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path / defect)
        original.unlink()
        assert run_cli(*args, "--apply").returncode == 0
        validator = module._load_agent_run_ledger().load_validator()
        association = next((item / "review-artifact-custody" / "historical-pass").iterdir())
        if defect == "ledger-prefix":
            (item / "agent-runs.jsonl").write_bytes(before.replace(b"historical artifact", b"changed artifact"))
        elif defect == "ordinal":
            envelope = json.loads(association.read_bytes())
            envelope["rawLineOrdinal"] = 1
            association.write_bytes(validator._canonical_projection_bytes(envelope))
        else:
            association.write_bytes(json.dumps(json.loads(association.read_bytes()), indent=2).encode("utf-8"))
        errors = validator.validate_work_item(item)
        assert any("WI-LEDGER-CUSTODY-STALE-TARGET" in error for error in errors), (defect, errors)
        untouched = tree_file_bytes(root)
        refusal = run_cli(*args, "--apply")
        assert refusal.returncode != 0 and "WI-LEDGER-CUSTODY-STALE-TARGET" in refusal.stdout
        assert tree_file_bytes(root) == untouched


def test_historical_pass_custody_failed_publication_removes_only_new_snapshot(tmp_path: Path) -> None:
    for shared in (False, True):
        module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path / str(shared))
        original.unlink()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if shared:
            directory = item / "review-artifact-custody"
            directory.mkdir()
            (directory / digest).write_bytes(source.read_bytes())
        untouched = tree_file_bytes(root)
        with patch.object(module, "_atomic_write", side_effect=OSError("injected publication failure")):
            with unittest.TestCase().assertRaises(OSError):
                module.retain_historical_pass_custody(
                    root, item.name, event["runId"], 2, args[args.index("--expected-raw-line-sha256") + 1],
                    hashlib.sha256(before).hexdigest(), "original-copy.md", digest, apply=True,
                )
        assert tree_file_bytes(root) == untouched
        assert not (item / "review-artifact-custody" / "historical-pass").exists()
        assert (item / "review-artifact-custody" / digest).exists() is shared


def test_historical_pass_custody_snapshot_acquisition_failure_preserves_canonical_bytes(tmp_path: Path) -> None:
    module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path)
    original.unlink()
    untouched = tree_file_bytes(root)
    ledger = module._load_agent_run_ledger()
    acquire = ledger._acquire_custody_snapshot

    def fail_after_capture(*arguments, **kwargs):
        acquire(*arguments, **kwargs)
        raise OSError("injected failure after snapshot acquisition")

    with patch.object(ledger, "_acquire_custody_snapshot", side_effect=fail_after_capture):
        with unittest.TestCase().assertRaises(OSError):
            module.retain_historical_pass_custody(
                root, item.name, event["runId"], 2, args[args.index("--expected-raw-line-sha256") + 1],
                hashlib.sha256(before).hexdigest(), "original-copy.md", hashlib.sha256(source.read_bytes()).hexdigest(),
                apply=True,
            )
    assert tree_file_bytes(root) == untouched


def test_historical_pass_custody_candidate_uses_one_captured_ledger(tmp_path: Path) -> None:
    fixture_spec = importlib.util.spec_from_file_location("captured_custody_fixtures", ROOT / "tests" / "test_agent_run_ledger.py")
    h1_fixtures = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(h1_fixtures)
    for state in ("ordinary", "active", "revoked"):
        if state == "ordinary":
            module, root, item, original, source, event, raw, args = historical_pass_fixture(tmp_path / state)
            original.unlink()
            ordinal = 2
            line_sha = args[args.index("--expected-raw-line-sha256") + 1]
            validator = module._load_agent_run_ledger().load_validator()
        else:
            validator, root, item, source, raw, line, event, _path = h1_fixtures.historical_pass_h1_fixture(tmp_path / state, state)
            (item / "target.md").unlink()
            module = load_module()
            ordinal = 4
            line_sha = hashlib.sha256(line).hexdigest()
        selected = item / "agent-runs.jsonl"
        ledger = module._load_agent_run_ledger()
        capture = module._capture_file_snapshot
        resolve = validator.resolve_historical_pass_custody
        read = Path.read_bytes
        captured = []
        resolver_sources = []
        forbidden_reads = []

        def observe_capture(path, **kwargs):
            snapshot = capture(path, **kwargs)
            if path == selected:
                captured.append(snapshot)
            return snapshot

        def observe_resolver(custody_item, source_bytes, *arguments, **kwargs):
            if custody_item == item:
                resolver_sources.append(source_bytes)
            return resolve(custody_item, source_bytes, *arguments, **kwargs)

        def deny_reacquisition(path):
            if path == selected:
                forbidden_reads.append(path)
                raise OSError("selected ledger was already captured by its owner")
            return read(path)

        failure = None
        with patch.object(ledger, "load_validator", return_value=validator), \
                patch.object(module, "_capture_file_snapshot", side_effect=observe_capture), \
                patch.object(validator, "resolve_historical_pass_custody", side_effect=observe_resolver), \
                patch.object(Path, "read_bytes", deny_reacquisition):
            try:
                module.retain_historical_pass_custody(
                    root, item.name, event["runId"], ordinal, line_sha,
                    hashlib.sha256(raw).hexdigest(), "original-copy.md",
                    hashlib.sha256(read(source)).hexdigest(), apply=True,
                )
            except module.LifecycleError as exc:
                failure = exc
        assert forbidden_reads == [], (state, failure)
        assert failure is None, (state, failure)
        assert len(captured) == 1 and len(resolver_sources) == 1, (state, len(captured), len(resolver_sources))
        assert resolver_sources[0] is captured[0].data
        assert selected.read_bytes() == raw


def _active_successor_preflight_fixture(root: Path, *, leaf_count: int = 30) -> dict:
    module = load_module()
    old, new = "front-old", "front-new"
    work_items = root / "work-items"
    archive = work_items / "archive" / "2026-09" / old
    source = work_items / "active" / old
    archive.mkdir(parents=True)
    source.mkdir(parents=True)
    equal_count = leaf_count - 8
    for ordinal in range(equal_count):
        name = f"shared-{ordinal:02d}.md"
        data = f"historical evidence {ordinal}\n".encode()
        (archive / name).write_bytes(data)
        (source / name).write_bytes(data)
    archived_rows = []
    admission = json.loads(module._staged_admission_ledger_bytes(old, staged_status(old).encode()))
    for ordinal in range(29):
        row = dict(admission, runId=f"{old}-run-{ordinal:02d}")
        archived_rows.append((json.dumps(row, sort_keys=True) + "\n").encode())
    (archive / "agent-runs.jsonl").write_bytes(b"".join(archived_rows))
    (source / "agent-runs.jsonl").write_bytes(b"".join(archived_rows[:25]))
    write(archive / "status.md", "status: completed\n")
    write(archive / "closure.md", closure("2026-09-20T03:41:38Z"))
    write(archive / "bug-dispositions-receipt.json", '{"state":"committed"}\n')
    for name in (
        "architecture-adversarial-reverify.md", "design.md", "performance-review.md",
        "performance.md", "qa-reverify.md", "recovery-index-audit.md",
    ):
        write(source / name, f"later source evidence: {name}\n")
    write(source / "status.md", quick_status("A2 installed receiving remains open."))
    index_before = f"- [Front current](active/{old}/status.md)\n"
    index_after = f"- [{new} current](active/{new}/status.md)\n"
    (work_items / "index.md").write_bytes(
        ("# Compatibility\n" + index_before + "\nOther row.\n").encode()
    )
    write(
        work_items / "README.md",
        module._default_static_guide() + module.README_BEGIN + "\n" + module.README_END + "\n",
    )
    status = staged_status(old).replace(
        "Next action: Verify successor identity.",
        "Next action: Complete the open A2 installed receiving gate.",
    ).encode()
    dispositions = {
        "indexRowBefore": index_before,
        "indexRowAfter": index_after,
        "references": [],
    }
    return {
        "module": module, "old": old, "new": new, "source": source,
        "archive": archive, "status": status, "dispositions": dispositions,
    }


def test_import_active_successor_preflight_binds_all_bytes_without_writes(tmp_path: Path) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    before = tree_file_bytes(root / "work-items")
    assert hasattr(module, "preflight_import_active_successor")
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-1",
    )
    bindings = plan["fileBindings"]
    assert len(bindings) == 30
    assert {row["sourceRelativePath"] for row in bindings} == {
        path.relative_to(fixture["source"]).as_posix()
        for path in fixture["source"].rglob("*") if path.is_file()
    }
    assert {row["sourceSha256"] for row in bindings} == {
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in fixture["source"].rglob("*") if path.is_file()
    }
    assert [row["kind"] for row in bindings].count("archive-equal") == 22
    assert [row["kind"] for row in bindings].count("archive-ledger-prefix") == 1
    assert [row["kind"] for row in bindings].count("successor-copy") == 7
    assert plan["ledgerArchivePrefix"]["lineCount"] == 25
    assert plan["ledgerArchivePrefix"]["byteCount"] == len(
        (fixture["source"] / "agent-runs.jsonl").read_bytes()
    )
    assert next(row for row in bindings if row["sourceRelativePath"] == "status.md")["targetPath"].endswith(
        "/imported-source/status.md"
    )
    assert not (root / "work-items" / "active" / fixture["new"] / "agent-runs.jsonl").exists()
    assert tree_file_bytes(root / "work-items") == before
    alternate_root = tmp_path / "different-leaf-count"
    alternate = _active_successor_preflight_fixture(alternate_root, leaf_count=11)
    alternate_plan = alternate["module"].preflight_import_active_successor(
        alternate_root, alternate["old"], alternate["new"], alternate["status"],
        alternate["dispositions"], "front-import-2",
    )
    assert len(alternate_plan["fileBindings"]) == 11
    assert [row["kind"] for row in alternate_plan["fileBindings"]].count("archive-equal") == 3


def test_import_active_successor_preflight_binds_index_and_dual_readme(tmp_path: Path) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    work_items = root / "work-items"
    before = tree_file_bytes(work_items)
    try:
        module.render_readme_bytes(root)
    except module.LifecycleError as error:
        assert error.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("ordinary renderer admitted the dual input")
    consumer = work_items / "backlog" / "consumer.md"
    write(consumer, (
        f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n"
        f"Relation: work-item:{fixture['old']}\n"
    ))
    before = tree_file_bytes(work_items)
    fixture["dispositions"]["references"] = [{
        "consumer": "backlog/consumer.md", "kind": "physical",
        "value": f"../active/{fixture['old']}/status.md",
        "target": f"work-items/active/{fixture['new']}/status.md",
    }, {
        "consumer": "backlog/consumer.md", "kind": "logical",
        "value": f"work-item:{fixture['old']}",
        "meaning": "current-successor",
    }]
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-1",
    )
    assert plan["compatibilityIndex"]["beforeSha256"] == hashlib.sha256(
        (work_items / "index.md").read_bytes()
    ).hexdigest()
    assert plan["compatibilityIndex"]["afterBytes"].endswith(
        b"\nOther row.\n"
    )
    assert plan["readme"]["beforeSha256"] == hashlib.sha256(
        (work_items / "README.md").read_bytes()
    ).hexdigest()
    assert b"active/front-new/status.md" in plan["readme"]["afterBytes"]
    assert b"archive/2026-09/front-old/closure.md" in plan["readme"]["afterBytes"]
    assert b"work-item:front-new" in base64.b64decode(plan["links"][0]["afterBase64"])
    assert plan["digest"] == hashlib.sha256(plan["canonicalBytes"]).hexdigest()
    assert tree_file_bytes(work_items) == before
    assert module.preflight_import_active_successor(
        work_items, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-1",
    )["digest"] == plan["digest"]
    status_input = tmp_path / "successor-status.md"
    links_input = tmp_path / "successor-links.json"
    status_input.write_bytes(fixture["status"])
    links_input.write_bytes(json.dumps(fixture["dispositions"]).encode())
    argv = (
        "import-active-successor", "--root", str(root),
        "--predecessor-slug", fixture["old"],
        "--successor-slug", fixture["new"],
        "--status-file", str(status_input),
        "--links-file", str(links_input),
        "--operation-id", "front-import-1",
    )
    result = run_cli(*argv)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["digest"] == plan["digest"]
    assert tree_file_bytes(work_items) == before


def test_import_active_successor_preflight_rejects_unsafe_inputs(tmp_path: Path) -> None:
    cases = (
        ("ledger", "WI-SUCCESSOR-LEDGER-DIVERGENCE"),
        ("occupied", "WI-SUCCESSOR-IDENTITY-CONFLICT"),
        ("index", "WI-SUCCESSOR-LINK-UNMAPPED"),
        ("readme", "WI-README-MARKERS"),
        ("unclassified", "WI-SUCCESSOR-LINK-UNMAPPED"),
        ("hardlink", "WI-SUCCESSOR-IMPORT-UNSAFE-INPUT"),
        ("index_extra", "WI-SUCCESSOR-LINK-UNMAPPED"),
        ("third", "WI-SUCCESSOR-IDENTITY-CONFLICT"),
        ("projection", "WI-SUCCESSOR-LEDGER-DIVERGENCE"),
        ("escape", "WI-SUCCESSOR-LINK-UNMAPPED"),
        ("shadow", "WI-SUCCESSOR-READMODEL-INVALID"),
        ("occupied_file", "WI-SUCCESSOR-IDENTITY-CONFLICT"),
        ("third_file", "WI-SUCCESSOR-IDENTITY-CONFLICT"),
        ("malformed_disposition", "WI-SUCCESSOR-LINK-UNMAPPED"),
    )
    for case, failure_id in cases:
        root = tmp_path / case
        fixture = _active_successor_preflight_fixture(root)
        work_items = root / "work-items"
        if case == "ledger":
            with (fixture["source"] / "agent-runs.jsonl").open("ab") as stream:
                stream.write(b"not a prefix\n")
        elif case == "occupied":
            write(work_items / "active" / fixture["new"] / "status.md", "status: active\n")
        elif case == "index":
            (work_items / "index.md").write_bytes(b"# No current row\n")
        elif case == "readme":
            (work_items / "README.md").write_bytes(b"# No markers\n")
        elif case == "unclassified":
            write(work_items / "backlog" / "consumer.md",
                  f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n")
        elif case == "hardlink":
            os.link(fixture["source"] / "design.md", fixture["source"] / "linked.md")
        elif case == "index_extra":
            with (work_items / "index.md").open("ab") as stream:
                stream.write(f"- [Old evidence](active/{fixture['old']}/design.md)\n".encode())
        elif case == "third":
            write(work_items / "backlog" / f"{fixture['old']}.md", "status: candidate\n")
        elif case == "projection":
            ledger = fixture["archive"] / "agent-runs.jsonl"
            rows = ledger.read_bytes().splitlines(keepends=True)
            rows[-1] = b"{invalid json}\n"
            ledger.write_bytes(b"".join(rows))
        elif case == "escape":
            fixture["dispositions"]["indexRowAfter"] = (
                f"- [{fixture['new']} current](../outside/status.md)\n"
            )
        elif case == "shadow":
            fixture["status"] += b"Roadmap: missing-roadmap\n"
        elif case == "occupied_file":
            write(work_items / "active" / fixture["new"], "occupied\n")
        elif case == "third_file":
            write(work_items / "archive" / "2026-10" / fixture["old"], "occupied\n")
        elif case == "malformed_disposition":
            write(work_items / "backlog" / "consumer.md",
                  f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n")
            fixture["dispositions"]["references"] = [{
                "consumer": "backlog/consumer.md", "kind": "physical",
                "value": f"../active/{fixture['old']}/status.md",
                "target": [f"work-items/active/{fixture['new']}/status.md"],
            }]
        before = tree_file_bytes(work_items)
        try:
            fixture["module"].preflight_import_active_successor(
                root, fixture["old"], fixture["new"], fixture["status"],
                fixture["dispositions"], "front-import-1",
            )
        except fixture["module"].LifecycleError as error:
            assert error.failure_id == failure_id, case
        else:
            raise AssertionError(f"unsafe {case} input was admitted")
        assert tree_file_bytes(work_items) == before, case


def test_import_active_successor_preflight_keeps_valid_source_status_as_evidence(tmp_path: Path) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    source_status = fixture["source"] / "status.md"
    before = tree_file_bytes(root / "work-items")
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-status",
    )
    binding = next(row for row in plan["fileBindings"] if row["sourceRelativePath"] == "status.md")
    assert binding["kind"] == "successor-copy"
    assert binding["targetPath"] == "work-items/active/front-new/imported-source/status.md"
    assert tree_file_bytes(root / "work-items") == before

    source_status.write_bytes((fixture["archive"] / "status.md").read_bytes())
    before = tree_file_bytes(root / "work-items")
    try:
        module.preflight_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], "front-import-status",
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-CATEGORY-TERMINAL-IN-CURRENT"
    else:
        raise AssertionError("terminal source status was admitted as current")
    assert tree_file_bytes(root / "work-items") == before


@pytest.mark.parametrize("opaque", (False, True))
def test_import_active_successor_preflight_projects_planned_consumer_bytes(tmp_path: Path, opaque: bool) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    work_items = root / "work-items"
    relative = "active/side/design.md" if opaque else "backlog/consumer.md"
    if opaque:
        write(work_items / "active/side/status.md", quick_status())
    consumer = work_items / relative
    href = f"{'../../' if opaque else '../'}active/{fixture['old']}/status.md#work-item:{fixture['old']}"
    write(consumer, (
        f"status: candidate\n[Current]({href})\n"
    ))
    if opaque:
        consumer.write_bytes(b"\xef\xbb\xbf\xc3\xa9\x97\r\n" + consumer.read_bytes() + b"\x81")
    fixture["dispositions"]["references"] = [{
        "consumer": relative, "kind": "physical",
        "value": href,
        "target": f"work-items/active/{fixture['new']}/status.md",
    }, {
        "consumer": relative, "kind": "logical",
        "value": f"work-item:{fixture['old']}", "meaning": "current-successor",
    }]
    before = tree_file_bytes(work_items)
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-links",
    )
    after_consumer = base64.b64decode(plan["links"][0]["afterBase64"])
    new_href = (f"../{fixture['new']}/status.md" if opaque else f"../active/{fixture['new']}/status.md") + f"#work-item:{fixture['old']}"
    assert after_consumer == consumer.read_bytes().replace(href.encode(), new_href.encode()).replace(
        f"work-item:{fixture['old']}".encode(), f"work-item:{fixture['new']}".encode())
    with tempfile.TemporaryDirectory() as directory:
        shadow_root = Path(directory)
        shadow_work_items = shadow_root / "work-items"
        shutil.copytree(work_items, shadow_work_items)
        shutil.rmtree(shadow_work_items / "active" / fixture["old"])
        shadow_status = shadow_work_items / "active" / fixture["new"] / "status.md"
        shadow_status.parent.mkdir(parents=True)
        shadow_status.write_bytes(fixture["status"])
        (shadow_work_items / relative).write_bytes(after_consumer)
        expected = module.render_readme_bytes(
            shadow_root, static_guide_override=module._static_guide(work_items / "README.md"),
        )
    assert plan["readme"]["afterBytes"] == expected
    canonical_relative = "active/side/status.md" if opaque else relative
    canonical_bytes = (work_items / canonical_relative).read_bytes() if opaque else after_consumer
    assert next(row for row in plan["canonicalInputs"]
                if row["path"] == "work-items/" + canonical_relative)["sha256"] == hashlib.sha256(canonical_bytes).hexdigest()
    assert tree_file_bytes(work_items) == before


def test_import_active_successor_preflight_rejects_old_visible_index_label(tmp_path: Path) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    fixture["dispositions"]["indexRowAfter"] = (
        f"- [{fixture['old']} current](active/{fixture['new']}/status.md)\n"
    )
    before = tree_file_bytes(root / "work-items")
    try:
        module.preflight_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], "front-import-index",
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-LINK-UNMAPPED"
    else:
        raise AssertionError("old visible index label was admitted")
    assert tree_file_bytes(root / "work-items") == before


def test_import_active_successor_apply_preserves_archive_and_run_authority(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-apply-1",
    )
    source_before = tree_file_bytes(fixture["source"])
    archive_before = tree_file_bytes(fixture["archive"])
    assert hasattr(module, "apply_import_active_successor")
    result = module.apply_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-apply-1", plan["digest"],
    )
    successor = root / "work-items" / "active" / fixture["new"]
    receipt = root / result["receiptPath"]
    persisted = json.loads(receipt.read_bytes())
    assert result["state"] == "committed" and result["alreadySettled"] is False
    assert persisted["operationId"] == "front-apply-1"
    assert persisted["preflightDigest"] == plan["digest"]
    assert persisted["sourceTreeSha256"] == plan["sourceTreeSha256"]
    assert persisted["archiveTreeSha256"] == plan["archiveTreeSha256"]
    assert persisted["ledgerArchivePrefix"] == plan["ledgerArchivePrefix"]
    assert persisted["fileBindings"] == plan["fileBindings"]
    assert tree_file_bytes(fixture["archive"]) == archive_before
    assert not fixture["source"].exists()
    assert module.resolve_category(root, f"work-item:{fixture['old']}") == fixture["archive"]
    assert module.resolve_category(root, f"work-item:{fixture['new']}") == successor
    assert (successor / "status.md").read_bytes() == fixture["status"]
    assert not (successor / "agent-runs.jsonl").exists()
    assert not (successor / "imported-source" / "agent-runs.jsonl").exists()
    for binding in plan["fileBindings"]:
        original = source_before[binding["sourceRelativePath"]]
        target = root / binding["targetPath"]
        if binding["kind"] == "archive-ledger-prefix":
            assert target.read_bytes().startswith(original)
        else:
            assert target.read_bytes() == original
    assert (successor / "imported-source" / "status.md").read_bytes() == source_before["status.md"]
    assert (root / "work-items" / "README.md").read_bytes() == plan["readme"]["afterBytes"]
    module.check_readme(root)
    assert receipt.parent == successor
    assert not module._transition_intent_path(root, "front-apply-1").exists()
    assert not (root / ".scratch" / "work-items-lifecycle-successor-imports").exists()


@pytest.mark.parametrize("stage_parent_state", ("absent", "empty", "sibling"))
def test_import_active_successor_apply_maps_index_links_and_readme(tmp_path: Path, stage_parent_state: str) -> None:
    root = tmp_path / "candidate"
    stage_parent = root / ".scratch" / "work-items-lifecycle-successor-imports"
    if stage_parent_state != "absent":
        stage_parent.mkdir(parents=True)
    sibling = stage_parent / "separately-owned.txt"
    if stage_parent_state == "sibling":
        sibling.write_bytes(b"Preserve shared staging evidence.\n")
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    work_items = root / "work-items"
    consumer = work_items / "backlog" / "consumer.md"
    write(consumer, (
        f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n"
        f"Relation: work-item:{fixture['old']}\n"
    ))
    fixture["dispositions"]["references"] = [{
        "consumer": "backlog/consumer.md", "kind": "physical",
        "value": f"../active/{fixture['old']}/status.md",
        "target": f"work-items/active/{fixture['new']}/status.md",
    }, {
        "consumer": "backlog/consumer.md", "kind": "logical",
        "value": f"work-item:{fixture['old']}", "meaning": "current-successor",
    }]
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-apply-links",
    )
    archive_before = tree_file_bytes(fixture["archive"])
    index_before = (work_items / "index.md").read_bytes()
    status_input = tmp_path / "status.md"
    links_input = tmp_path / "links.json"
    status_input.write_bytes(fixture["status"])
    links_input.write_bytes(json.dumps(fixture["dispositions"]).encode())
    result = run_cli(
        "import-active-successor", "--root", str(root),
        "--predecessor-slug", fixture["old"],
        "--successor-slug", fixture["new"],
        "--status-file", str(status_input), "--links-file", str(links_input),
        "--operation-id", "front-apply-links", "--apply",
        "--preflight-digest", plan["digest"],
    )
    assert result.returncode == 0, result.stdout
    applied = json.loads(result.stdout)
    assert applied["state"] == "committed" and applied["alreadySettled"] is False
    assert tree_file_bytes(fixture["archive"]) == archive_before
    assert consumer.read_bytes() == base64.b64decode(plan["links"][0]["afterBase64"])
    assert b"work-item:front-new" in consumer.read_bytes()
    assert (work_items / "index.md").read_bytes() == plan["compatibilityIndex"]["afterBytes"]
    assert (work_items / "index.md").read_bytes().replace(
        fixture["dispositions"]["indexRowAfter"].encode(),
        fixture["dispositions"]["indexRowBefore"].encode(),
    ) == index_before
    assert (consumer.parent / f"../active/{fixture['new']}/status.md").resolve().is_file()
    assert (work_items / "README.md").read_bytes() == plan["readme"]["afterBytes"]
    module.check_readme(root)
    replay = module.apply_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-apply-links", plan["digest"],
    )
    assert replay["state"] == "committed" and replay["alreadySettled"] is True
    try:
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"] + b"changed\n",
            fixture["dispositions"], "front-apply-links", plan["digest"],
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IDENTITY-CONFLICT"
    else:
        raise AssertionError("changed replay was accepted")
    operation_stage = stage_parent / "front-apply-links"
    assert not operation_stage.exists()
    if stage_parent_state == "absent":
        assert not stage_parent.exists()
    elif stage_parent_state == "empty":
        assert stage_parent.is_dir() and list(stage_parent.iterdir()) == []
    else:
        assert sibling.read_bytes() == b"Preserve shared staging evidence.\n"
        assert list(stage_parent.iterdir()) == [sibling]



def test_successor_commit_recovery_replay_keeps_unproven_shared_parent(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    work_items = root / "work-items"
    consumer = work_items / "backlog" / "consumer.md"
    write(consumer, (
        f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n"
        f"Relation: work-item:{fixture['old']}\n"
    ))
    fixture["dispositions"]["references"] = [{
        "consumer": "backlog/consumer.md", "kind": "physical",
        "value": f"../active/{fixture['old']}/status.md",
        "target": f"work-items/active/{fixture['new']}/status.md",
    }, {
        "consumer": "backlog/consumer.md", "kind": "logical",
        "value": f"work-item:{fixture['old']}", "meaning": "current-successor",
    }]
    operation = "front-commit-replay"
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], operation,
    )
    staging_parent = root / ".scratch" / "work-items-lifecycle-successor-imports"
    stage_root = staging_parent / operation
    assert not staging_parent.exists()
    archive_before = tree_file_bytes(fixture["archive"])
    with pytest.raises(module.LifecycleError) as interrupted:
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation, plan["digest"],
            inject_failure_at="after-receipt-publish",
        )
    assert interrupted.value.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
    intent_path = module._transition_intent_path(root, operation)
    assert intent_path.is_file() and stage_root.is_dir() and staging_parent.is_dir()

    deleted_before_publish = []
    original_publish = module.LifecycleWriteTarget._publish_effect
    publication_failure = module.LifecycleError("TEST-PUBLICATION", "injected after native directory removal")

    def fail_after_native_directory_removal(owner, prepared, identity):
        if (prepared.directory and prepared.source == stage_root and prepared.destination is None
                and not deleted_before_publish):
            assert not stage_root.exists()
            deleted_before_publish.append((owner, prepared, identity))
            raise publication_failure
        return original_publish(owner, prepared, identity)

    monkeypatch.setattr(module.LifecycleWriteTarget, "_publish_effect", fail_after_native_directory_removal)
    with pytest.raises(module.LifecycleError) as failed_publication:
        module.recover_transition(root, operation)
    assert failed_publication.value.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
    assert "injected after native directory removal" in str(failed_publication.value)
    assert len(deleted_before_publish) == 1
    removed_owner, removed_effect, removed_identity = deleted_before_publish[0]
    assert removed_effect.source == stage_root and removed_identity is not None
    assert not removed_owner._open and removed_owner._source_observation is None
    assert not stage_root.exists() and staging_parent.is_dir() and intent_path.is_file()

    monkeypatch.undo()
    recovered = run_cli(
        "recover-transition", "--root", str(root), "--operation-id", operation, "--apply",
    )
    assert recovered.returncode == 0, recovered.stdout
    assert not intent_path.exists()
    assert not stage_root.exists() and staging_parent.is_dir() and list(staging_parent.iterdir()) == []
    assert tree_file_bytes(fixture["archive"]) == archive_before
    assert not fixture["source"].exists()
    successor = root / "work-items" / "active" / fixture["new"]
    receipt = successor / module.SUCCESSOR_IMPORT_RECEIPT
    assert successor.is_dir() and receipt.is_file()
    assert (successor / "status.md").read_bytes() == fixture["status"]
    assert consumer.read_bytes() == base64.b64decode(plan["links"][0]["afterBase64"])
    assert (work_items / "index.md").read_bytes() == plan["compatibilityIndex"]["afterBytes"]
    assert (work_items / "README.md").read_bytes() == plan["readme"]["afterBytes"]
    module.check_readme(root)

    status_input = tmp_path / "replay-status.md"
    links_input = tmp_path / "replay-links.json"
    status_input.write_bytes(fixture["status"])
    links_input.write_bytes(json.dumps(fixture["dispositions"]).encode())
    settled_before_replay = tree_file_bytes(root)
    replay = run_cli(
        "import-active-successor", "--root", str(root),
        "--predecessor-slug", fixture["old"], "--successor-slug", fixture["new"],
        "--status-file", str(status_input), "--links-file", str(links_input),
        "--operation-id", operation, "--apply", "--preflight-digest", plan["digest"],
    )
    assert replay.returncode == 0, replay.stdout
    replayed = json.loads(replay.stdout)
    assert replayed["state"] == "committed" and replayed["alreadySettled"] is True
    assert tree_file_bytes(root) == settled_before_replay
    assert staging_parent.is_dir() and list(staging_parent.iterdir()) == []
    assert not intent_path.exists() and receipt.is_file()


def test_successor_recovery_preserves_member_added_before_native_directory_retirement(
    tmp_path: Path, monkeypatch,
) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    operation = "front-late-member"
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], operation,
    )
    with pytest.raises(module.LifecycleError):
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation, plan["digest"],
            inject_failure_at="after-source-hold",
        )
    intent_path = module._transition_intent_path(root, operation)
    stage_root = root / ".scratch" / "work-items-lifecycle-successor-imports" / operation
    foreign = stage_root / "unowned-evidence.bin"
    foreign_bytes = b"Preserve late foreign stage evidence.\n"
    original_verify = module._verify_owned_directory_snapshot
    injected = []

    def add_foreign_member(snapshot, failure_id, *, creation_owner=None):
        if (snapshot.path == stage_root and snapshot.members == () and creation_owner is not None
                and not injected):
            foreign.write_bytes(foreign_bytes)
            injected.append(module._lifecycle_file_identity(foreign.lstat()))
        return original_verify(snapshot, failure_id, creation_owner=creation_owner)

    monkeypatch.setattr(module, "_verify_owned_directory_snapshot", add_foreign_member)
    with pytest.raises(module.LifecycleError) as refused:
        module.recover_transition(root, operation)
    assert refused.value.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
    assert injected and foreign.read_bytes() == foreign_bytes
    assert module._lifecycle_file_identity(foreign.lstat()) == injected[0]
    assert intent_path.is_file() and stage_root.is_dir()
    assert fixture["source"].is_dir()
    assert not (root / "work-items" / "active" / fixture["new"]).exists()


def test_import_active_successor_fault_recovery_and_replay(tmp_path: Path) -> None:
    checkpoints = (
        "before-source-hold", "after-source-hold", "after-successor-publish",
        "after-links-publish", "after-readme-publish", "after-receipt-publish",
    )
    for checkpoint in checkpoints:
        root = tmp_path / checkpoint
        fixture = _active_successor_preflight_fixture(root)
        module = fixture["module"]
        operation = "front-fault-1"
        plan = module.preflight_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation,
        )
        before = tree_file_bytes(root / "work-items")
        assert hasattr(module, "apply_import_active_successor")
        try:
            module.apply_import_active_successor(
                root, fixture["old"], fixture["new"], fixture["status"],
                fixture["dispositions"], operation, plan["digest"],
                inject_failure_at=checkpoint,
            )
        except module.LifecycleError as error:
            assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY", checkpoint
            assert operation in str(error) and checkpoint in str(error)
        else:
            raise AssertionError(f"fault {checkpoint} reported success")
        intent_path = module._transition_intent_path(root, operation)
        if intent_path.exists():
            intent = module._load_transition_intent(root, intent_path)
            assert intent["operationId"] == operation
            if checkpoint == "after-receipt-publish":
                pending_before = tree_file_bytes(root)
                try:
                    module.apply_import_active_successor(
                        root, fixture["old"], fixture["new"], fixture["status"],
                        fixture["dispositions"], operation, plan["digest"],
                    )
                except module.LifecycleError as error:
                    assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
                    assert operation in str(error)
                else:
                    raise AssertionError("pending committed intent replay reported success")
                assert tree_file_bytes(root) == pending_before
                assert intent_path.is_file()
            if checkpoint == "after-source-hold":
                with module.LifecycleTransaction(root):
                    try:
                        module._recover_transition(root, intent_path)
                    except module.LifecycleError as error:
                        assert error.failure_id == "WI-LIFECYCLE-LOCK-HELD"
                    else:
                        raise AssertionError("successor recovery bypassed the lifecycle lock")
            module._recover_transition(root, intent_path)
        successor = root / "work-items" / "active" / fixture["new"]
        if checkpoint == "after-receipt-publish":
            assert successor.is_dir() and not fixture["source"].exists()
            replay = module.apply_import_active_successor(
                root, fixture["old"], fixture["new"], fixture["status"],
                fixture["dispositions"], operation, plan["digest"],
            )
            assert replay["alreadySettled"] is True
            module.check_readme(root)
        else:
            assert tree_file_bytes(root / "work-items") == before, checkpoint
            assert fixture["source"].is_dir() and not successor.exists()
        assert not intent_path.exists(), checkpoint

    corrupt_root = tmp_path / "corrupt-held-source"
    corrupt_fixture = _active_successor_preflight_fixture(corrupt_root)
    corrupt_module = corrupt_fixture["module"]
    corrupt_plan = corrupt_module.preflight_import_active_successor(
        corrupt_root, corrupt_fixture["old"], corrupt_fixture["new"],
        corrupt_fixture["status"], corrupt_fixture["dispositions"], "front-corrupt-1",
    )
    try:
        corrupt_module.apply_import_active_successor(
            corrupt_root, corrupt_fixture["old"], corrupt_fixture["new"],
            corrupt_fixture["status"], corrupt_fixture["dispositions"],
            "front-corrupt-1", corrupt_plan["digest"],
            inject_failure_at="after-source-hold",
        )
    except corrupt_module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
    else:
        raise AssertionError("held-source interruption reported success")
    corrupt_intent_path = corrupt_module._transition_intent_path(corrupt_root, "front-corrupt-1")
    corrupt_intent = corrupt_module._load_transition_intent(corrupt_root, corrupt_intent_path)
    held_design = corrupt_root / corrupt_intent["sourceHoldPath"] / "design.md"
    held_design.write_bytes(b"corrupt held source\n")
    corrupted_before = tree_file_bytes(corrupt_root)
    try:
        corrupt_module._recover_transition(corrupt_root, corrupt_intent_path)
    except corrupt_module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
        assert "front-corrupt-1" in str(error)
    else:
        raise AssertionError("corrupt staging was silently recovered")
    assert tree_file_bytes(corrupt_root) == corrupted_before
    assert corrupt_intent_path.is_file()

    for surface in ("source", "archive", "consumer", "index", "readme", "digest"):
        root = tmp_path / f"drift-{surface}"
        fixture = _active_successor_preflight_fixture(root)
        module = fixture["module"]
        if surface == "consumer":
            write(root / "work-items" / "backlog" / "consumer.md",
                  f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n")
            fixture["dispositions"]["references"] = [{
                "consumer": "backlog/consumer.md", "kind": "physical",
                "value": f"../active/{fixture['old']}/status.md",
                "target": f"work-items/active/{fixture['new']}/status.md",
            }]
        plan = module.preflight_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], "front-drift-1",
        )
        if surface == "source":
            with (fixture["source"] / "design.md").open("ab") as stream:
                stream.write(b"drift\n")
        elif surface == "archive":
            with (fixture["archive"] / "design.md").open("ab") as stream:
                stream.write(b"drift\n")
        elif surface == "index":
            with (root / "work-items" / "index.md").open("ab") as stream:
                stream.write(b"drift\n")
        elif surface == "consumer":
            with (root / "work-items" / "backlog" / "consumer.md").open("ab") as stream:
                stream.write(b"drift\n")
        elif surface == "readme":
            with (root / "work-items" / "README.md").open("ab") as stream:
                stream.write(b"drift\n")
        before = tree_file_bytes(root / "work-items")
        try:
            module.apply_import_active_successor(
                root, fixture["old"], fixture["new"], fixture["status"],
                fixture["dispositions"], "front-drift-1",
                ("0" * 64 if surface == "digest" else plan["digest"]),
            )
        except module.LifecycleError as error:
            assert error.failure_id == "WI-SUCCESSOR-IMPORT-DRIFT", surface
        else:
            raise AssertionError(f"drifted {surface} input was applied")
        assert tree_file_bytes(root / "work-items") == before, surface
        assert not module._transition_intent_path(root, "front-drift-1").exists()


def test_import_active_successor_fault_post_receipt_corrupt_hold_replay_refuses(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    operation = "front-post-receipt-corrupt"
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], operation,
    )
    try:
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation, plan["digest"],
            inject_failure_at="after-receipt-publish",
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
    else:
        raise AssertionError("post-receipt interruption reported success")
    intent_path = module._transition_intent_path(root, operation)
    intent = module._load_transition_intent(root, intent_path)
    held_design = root / intent["sourceHoldPath"] / "design.md"
    held_design.write_bytes(b"corrupt after receipt\n")
    pending_before = tree_file_bytes(root)
    try:
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation, plan["digest"],
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
        assert operation in str(error)
    else:
        raise AssertionError("corrupt held source was replayed as settled")
    assert tree_file_bytes(root) == pending_before
    assert intent_path.is_file() and held_design.read_bytes() == b"corrupt after receipt\n"


def test_import_active_successor_fault_corrupt_receipt_refuses_replay(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-receipt-1",
    )
    applied = module.apply_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-receipt-1", plan["digest"],
    )
    receipt_path = root / applied["receiptPath"]
    corrupted = json.loads(receipt_path.read_bytes())
    corrupted.pop("fileBindings")
    receipt_path.write_bytes((json.dumps(corrupted, indent=2, sort_keys=True) + "\n").encode())
    before = tree_file_bytes(root / "work-items")
    try:
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], "front-receipt-1", plan["digest"],
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
    else:
        raise AssertionError("corrupt committed receipt was replayed")
    assert tree_file_bytes(root / "work-items") == before


def test_close_requires_exact_bug_disposition_manifest(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "missing-closeout-manifest"
    seed_active(module, root, slug)
    instant = "2026-08-11T10:00:00Z"

    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-MISSING"
    else:
        raise AssertionError("work-item closed without bug-dispositions.json")

    assert (root / "work-items" / "active" / slug).is_dir()
    assert not (root / "work-items" / "archive" / "2026-08" / slug).exists()


def test_close_rejects_complete_invalid_bug_disposition_schema_matrix(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-11T10:00:30Z"

    def mutate_header(payload: dict, key: str, value) -> None:
        payload[key] = value

    def mutate_row(payload: dict, key: str, value) -> None:
        payload["bugs"][0][key] = value

    cases = (
        ("unknown-header", lambda payload: mutate_header(payload, "unexpected", True)),
        ("schema-version", lambda payload: mutate_header(payload, "schemaVersion", 2)),
        ("work-item", lambda payload: mutate_header(payload, "workItem", "another-item")),
        ("closed-at", lambda payload: mutate_header(payload, "closedAt", "2026-08-11T10:00:31Z")),
        ("bugs-type", lambda payload: mutate_header(payload, "bugs", {})),
        ("duplicate-id", lambda payload: payload["bugs"].append(dict(payload["bugs"][0]))),
        ("unsafe-id", lambda payload: mutate_row(payload, "id", "../unsafe")),
        ("unknown-row", lambda payload: mutate_row(payload, "unexpected", True)),
        ("action", lambda payload: mutate_row(payload, "action", "close-it")),
        ("digest", lambda payload: mutate_row(payload, "inputSha256", "not-a-digest")),
        ("terminal-status", lambda payload: mutate_row(payload, "status", "open")),
        ("multiline-resolution", lambda payload: mutate_row(payload, "resolution", "line one\nline two")),
        ("multiline-evidence", lambda payload: mutate_row(payload, "evidence", "line one\r\nline two")),
    )

    for suffix, mutate in cases:
        root = tmp_path / suffix
        slug = f"invalid-schema-{suffix}"
        seed_active(module, root, slug)
        bug = seed_context_bug(root, slug, f"2026-08-11-{suffix}-bug")
        before = bug.read_bytes()
        payload = {
            "schemaVersion": 1,
            "workItem": slug,
            "closedAt": instant,
            "bugs": [
                {
                    "id": bug.stem,
                    "action": "terminalize",
                    "inputSha256": hashlib.sha256(before).hexdigest(),
                    "status": "fixed",
                    "resolution": "The accepted implementation fixes this defect.",
                    "evidence": "The final regression suite passed.",
                }
            ],
        }
        mutate(payload)
        write(
            root / "work-items" / "active" / slug / "bug-dispositions.json",
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        )

        try:
            module.close_item(root, slug, closure(instant).encode(), instant)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-INVALID", suffix
        else:
            raise AssertionError(f"invalid bug disposition schema passed: {suffix}")

        assert bug.read_bytes() == before, suffix
        assert (root / "work-items" / "active" / slug).is_dir(), suffix
        assert not (root / "work-items" / "archive" / "2026-08" / slug).exists(), suffix


def test_close_terminalizes_exact_context_bug_in_same_owner_transaction(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "closeout-with-bug"
    bug_slug = "2026-08-11-closeout-with-bug"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, bug_slug)
    instant = "2026-08-11T10:01:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug_slug,
                "action": "terminalize",
                "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
                "status": "fixed",
                "resolution": "Accepted regression suite proves the defect is fixed.",
                "evidence": "Final QA and architecture gates PASS.",
            }
        ],
    )

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    archived_bug = (
        root / "work-items" / "bugs" / "archive" / "2026-08" / f"{bug_slug}.md"
    )
    assert archived.is_dir()
    assert archived_bug.is_file()
    fields = module._parse_fields(archived_bug.read_text(encoding="utf-8"))
    assert fields["status"] == "fixed"
    assert fields["terminal-at"] == instant
    assert (archived / "bug-dispositions-receipt.json").is_file()
    assert not bug.exists()


def test_close_rejects_missing_and_extra_context_bug_dispositions(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-11T10:02:00Z"
    for suffix, rows in (("missing", []), ("extra", None)):
        root = tmp_path / suffix
        slug = f"exact-set-{suffix}"
        seed_active(module, root, slug)
        linked = seed_context_bug(root, slug, f"2026-08-11-{suffix}-linked")
        if rows is None:
            rows = [
                {
                    "id": f"2026-08-11-{suffix}-linked",
                    "action": "preserve-current",
                    "inputSha256": hashlib.sha256(linked.read_bytes()).hexdigest(),
                    "status": "open",
                    "reason": "The defect remains independently actionable.",
                    "evidence": "The close review explicitly preserved this bug.",
                },
                {
                    "id": f"2026-08-11-{suffix}-not-linked",
                    "action": "preserve-current",
                    "inputSha256": "0" * 64,
                    "status": "open",
                    "reason": "This row must be rejected as unrelated.",
                    "evidence": "The exact context set excludes this identity.",
                },
            ]
        write_bug_dispositions(root, slug, instant, rows)

        try:
            module.close_item(root, slug, closure(instant).encode(), instant)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-INCOMPLETE", suffix
        else:
            raise AssertionError(f"{suffix} bug disposition set was accepted")

        assert (root / "work-items" / "active" / slug).is_dir()
        assert linked.is_file()


def test_close_uses_exact_parsed_context_not_substring_or_prose(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "exact-context-owner"
    seed_active(module, root, slug)
    near = seed_context_bug(root, f"{slug}-suffix", "2026-08-11-near-context")
    near.write_bytes(
        near.read_bytes()
        + f"\nThis prose mentions {slug} but does not change context ownership.\n".encode()
    )
    before = near.read_bytes()
    instant = "2026-08-11T10:02:30Z"
    write_empty_bug_dispositions(root, slug, instant)

    module.close_item(root, slug, closure(instant).encode(), instant)

    assert near.read_bytes() == before
    assert not (root / "work-items" / "bugs" / "archive").exists()


def test_close_preserves_declared_current_bug_and_unrelated_bug_bytes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "preserve-current-bug"
    seed_active(module, root, slug)
    linked = seed_context_bug(root, slug, "2026-08-11-preserved-linked")
    unrelated = seed_context_bug(root, "another-item", "2026-08-11-unrelated")
    linked_before = linked.read_bytes()
    unrelated_before = unrelated.read_bytes()
    instant = "2026-08-11T10:03:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": linked.stem,
                "action": "preserve-current",
                "inputSha256": hashlib.sha256(linked_before).hexdigest(),
                "status": "open",
                "reason": "The remaining defect has a separate accepted owner.",
                "evidence": "The close review recorded the residual explicitly.",
            }
        ],
    )

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert linked.read_bytes() == linked_before
    assert unrelated.read_bytes() == unrelated_before
    receipt = json.loads(
        (archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["bugs"][0]["action"] == "preserve-current"
    assert receipt["bugs"][0]["target"] is None
    module.audit_categories(root)


def test_close_rejects_context_bug_hash_drift_without_mutation(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "bug-hash-drift"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "2026-08-11-hash-drift")
    before = bug.read_bytes()
    instant = "2026-08-11T10:04:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug.stem,
                "action": "terminalize",
                "inputSha256": "0" * 64,
                "status": "fixed",
                "resolution": "This stale declaration must not be applied.",
                "evidence": "The input digest deliberately differs.",
            }
        ],
    )

    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-DRIFT"
    else:
        raise AssertionError("stale bug digest was accepted")

    assert bug.read_bytes() == before
    assert (root / "work-items" / "active" / slug).is_dir()


def test_close_rejects_non_utf8_current_bug_with_typed_failure(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "invalid-current-bug"
    seed_active(module, root, slug)
    invalid = root / "work-items" / "bugs" / "2026-08-11-invalid-utf8.md"
    invalid.parent.mkdir(parents=True, exist_ok=True)
    invalid.write_bytes(b"context: " + slug.encode() + b"\nstatus: open\n\xff")
    instant = "2026-08-11T10:04:30Z"
    write_empty_bug_dispositions(root, slug, instant)

    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-INVALID"
    else:
        raise AssertionError("non-UTF-8 current bug escaped typed close refusal")

    assert invalid.read_bytes().endswith(b"\xff")
    assert (root / "work-items" / "active" / slug).is_dir()


def test_terminalized_bug_preserves_crlf_line_endings(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "crlf-terminal-bug"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "2026-08-11-crlf-terminal-bug")
    bug.write_bytes(bug.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    instant = "2026-08-11T10:04:45Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug.stem,
                "action": "terminalize",
                "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
                "status": "fixed",
                "resolution": "The defect is fixed by the accepted implementation.",
                "evidence": "The final regression suite passed.",
            }
        ],
    )

    module.close_item(root, slug, closure(instant).encode(), instant)

    archived_bug = (
        root / "work-items" / "bugs" / "archive" / "2026-08" / f"{bug.stem}.md"
    ).read_bytes()
    assert b"\r\n" in archived_bug
    assert b"\n" not in archived_bug.replace(b"\r\n", b"")


def test_close_rolls_back_bug_bytes_when_bug_archive_move_fails(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "bug-move-rollback"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "2026-08-11-bug-move-rollback")
    before = bug.read_bytes()
    instant = "2026-08-11T10:05:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug.stem,
                "action": "terminalize",
                "inputSha256": hashlib.sha256(before).hexdigest(),
                "status": "fixed",
                "resolution": "The defect is fixed by the accepted implementation.",
                "evidence": "The final regression suite passed.",
            }
        ],
    )
    original_replace = module.os.replace

    def fail_bug_move(source, target):
        if Path(source) == bug:
            raise OSError("injected bug archive move failure")
        return original_replace(source, target)

    module.os.replace = fail_bug_move
    try:
        try:
            module.close_item(root, slug, closure(instant).encode(), instant)
        except OSError as exc:
            assert "injected bug archive move failure" in str(exc)
        else:
            raise AssertionError("bug archive move failure returned success")
    finally:
        module.os.replace = original_replace

    assert bug.read_bytes() == before
    assert (root / "work-items" / "active" / slug).is_dir()
    assert not (root / "work-items" / "archive" / "2026-08" / slug).exists()


def test_close_rolls_back_all_context_bugs_after_partial_disposition(
    tmp_path: Path,
) -> None:
    module = load_module()
    for fail_after in (1, 2):
        root = tmp_path / f"repo-{fail_after}"
        slug = f"partial-bug-rollback-{fail_after}"
        seed_active(module, root, slug)
        bugs = [
            seed_context_bug(
                root, slug, f"2026-08-11-partial-{fail_after}-bug-{index}"
            )
            for index in (1, 2)
        ]
        before = {bug: bug.read_bytes() for bug in bugs}
        readme_before = (root / "work-items" / "README.md").read_bytes()
        instant = f"2026-08-11T10:06:0{fail_after}Z"
        write_bug_dispositions(
            root,
            slug,
            instant,
            [
                {
                    "id": bug.stem,
                    "action": "terminalize",
                    "inputSha256": hashlib.sha256(before[bug]).hexdigest(),
                    "status": "fixed",
                    "resolution": "The defect is fixed by the accepted implementation.",
                    "evidence": "The final regression suite passed.",
                }
                for bug in bugs
            ],
        )

        try:
            module.close_item(
                root,
                slug,
                closure(instant).encode(),
                instant,
                inject_bug_failure_after=fail_after,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-DRIFT", fail_after
        else:
            raise AssertionError(
                f"partial bug disposition failure {fail_after} returned success"
            )

        assert (root / "work-items" / "active" / slug).is_dir()
        assert all(bug.read_bytes() == before[bug] for bug in bugs)
        assert (root / "work-items" / "README.md").read_bytes() == readme_before
        assert not (root / "work-items" / "bugs" / "archive").exists()


def test_close_replay_verifies_bug_receipt_and_archived_bug_bytes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "verified-close-replay"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "2026-08-11-verified-replay")
    instant = "2026-08-11T10:07:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug.stem,
                "action": "terminalize",
                "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
                "status": "fixed",
                "resolution": "The defect is fixed by the accepted implementation.",
                "evidence": "The final regression suite passed.",
            }
        ],
    )
    closure_bytes = closure(instant).encode()
    archived = module.close_item(root, slug, closure_bytes, instant)
    assert module.close_item(root, slug, closure_bytes, instant) == archived
    archived_bug = (
        root / "work-items" / "bugs" / "archive" / "2026-08" / f"{bug.stem}.md"
    )
    archived_bug.write_bytes(archived_bug.read_bytes() + b"tampered\n")

    try:
        module.close_item(root, slug, closure_bytes, instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IMMUTABLE-ARCHIVE"
    else:
        raise AssertionError("tampered archived bug passed replay verification")


def test_close_replay_rejects_deterministic_receipt_binding_drift(
    tmp_path: Path,
) -> None:
    module = load_module()
    mutations = {
        "source": "bugs/2026-08-11-wrong-source.md",
        "target": "bugs/archive/2026-08/2026-08-11-wrong-target.md",
        "statusBefore": "fixed",
    }
    for field, replacement in mutations.items():
        root = tmp_path / field
        slug = f"receipt-binding-{field.casefold()}"
        seed_active(module, root, slug)
        bug = seed_context_bug(root, slug, f"2026-08-11-receipt-{field.casefold()}")
        instant = "2026-08-11T10:07:30Z"
        write_bug_dispositions(
            root,
            slug,
            instant,
            [
                {
                    "id": bug.stem,
                    "action": "terminalize",
                    "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
                    "status": "fixed",
                    "resolution": "The defect is fixed by the accepted implementation.",
                    "evidence": "The final regression suite passed.",
                }
            ],
        )
        closure_bytes = closure(instant).encode()
        archived = module.close_item(root, slug, closure_bytes, instant)
        receipt_path = archived / "bug-dispositions-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["bugs"][0][field] = replacement
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        try:
            module.close_item(root, slug, closure_bytes, instant)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-IMMUTABLE-ARCHIVE", field
        else:
            raise AssertionError(f"tampered receipt {field} passed replay")


def test_close_replay_accepts_historical_archive_without_bug_manifest(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "historical-close-replay"
    instant = "2026-08-11T10:08:00Z"
    archived = root / "work-items" / "archive" / "2026-08" / slug
    write(archived / "status.md", marked_status())
    (archived / "closure.md").write_bytes(
        module._stamp_schema_marker(closure(instant).encode(), "closure.md")
    )
    module.refresh_readme(root)

    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived
    assert not (archived / "bug-dispositions.json").exists()
    assert not (archived / "bug-dispositions-receipt.json").exists()


def test_supersede_current_bug_requires_exact_accepted_successor_binding_without_local_mutation(
    tmp_path: Path,
) -> None:
    operation_id = "supersede-current-bug-binding"
    for case in ("missing", "malformed", "unaccepted", "wrong-operation", "hash-drifted"):
        module = load_module()
        root = tmp_path / case
        slug = f"2026-09-10-{case}-source"
        source = seed_context_bug(root, "source-owner", slug)
        successor = root / "receiving-registry" / "accepted-successor.md"
        successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
        successor.parent.mkdir(parents=True)
        successor.write_bytes(successor_bytes)
        module.refresh_readme(root, allow_marker_bootstrap=True)
        binding = successor_binding_bytes(slug, successor_bytes, operation_id)
        if case == "missing":
            supplied_binding = None
        elif case == "malformed":
            supplied_binding = b"{"
        elif case == "unaccepted":
            supplied_binding = successor_binding_bytes(
                slug, successor_bytes, operation_id, accepted_by=""
            )
        elif case == "wrong-operation":
            supplied_binding = successor_binding_bytes(
                slug, successor_bytes, operation_id + "-other"
            )
        else:
            supplied_binding = binding
            successor.write_bytes(successor_bytes + b"drift\n")
        inventory = successor_link_inventory_bytes(
            slug, source.read_bytes(), binding, operation_id
        )
        before = tree_file_bytes(root / "work-items")
        successor_before = successor.read_bytes()

        try:
            module.supersede_current_bug(
                root,
                slug,
                successor,
                supplied_binding,
                "2026-09-10T08:01:00Z",
                inventory,
                hashlib.sha256(source.read_bytes()).hexdigest(),
                hashlib.sha256(
                    (root / "work-items" / "README.md").read_bytes()
                ).hexdigest(),
                operation_id,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-SUCCESSOR-BINDING", case
        else:
            raise AssertionError(f"{case} successor binding was accepted")

        assert tree_file_bytes(root / "work-items") == before, case
        assert source.is_file(), case
        assert successor.read_bytes() == successor_before, case


def test_supersede_current_bug_rechecks_same_length_successor_bytes_before_intent(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "same-length-successor"
    slug = "2026-09-10-same-length-successor"
    operation_id = "supersede-same-length-successor"
    source = seed_context_bug(root, "source-owner", slug)
    source_before = source.read_bytes()
    successor = root / "receiving-registry" / "accepted-successor.md"
    accepted_bytes = b"id: accepted-successor\nstatus: accepted\n"
    updated_bytes = b"id: accepted-successor\nstatus: reviewed\n"
    assert len(accepted_bytes) == len(updated_bytes)
    successor.parent.mkdir(parents=True)
    successor.write_bytes(accepted_bytes)
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    binding = successor_binding_bytes(slug, accepted_bytes, operation_id)
    inventory = successor_link_inventory_bytes(
        slug, source_before, binding, operation_id
    )
    original_verify = module._verify_captured_file
    injected = False

    def update_before_final_verify(snapshot, failure_id):
        nonlocal injected
        if not injected and snapshot.path == successor:
            successor.write_bytes(updated_bytes)
            injected = True
        return original_verify(snapshot, failure_id)

    module._verify_captured_file = update_before_final_verify
    try:
        try:
            module.supersede_current_bug(
                root,
                slug,
                successor,
                binding,
                "2026-09-10T08:02:00Z",
                inventory,
                hashlib.sha256(source_before).hexdigest(),
                hashlib.sha256(readme.read_bytes()).hexdigest(),
                operation_id,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-SUCCESSOR-BINDING"
        else:
            raise AssertionError("same-length successor drift was accepted")
    finally:
        module._verify_captured_file = original_verify

    assert injected is True
    assert source.read_bytes() == source_before
    assert successor.read_bytes() == updated_bytes
    assert not list((root / "work-items" / "bugs" / "archive").glob("*/*.md"))
    assert not (
        root
        / ".scratch"
        / "work-items-lifecycle-transitions"
        / f"{operation_id}.json"
    ).exists()


def _supersede_current_bug_cli_fixture(
    module,
    root: Path,
    slug: str,
    operation_id: str,
) -> tuple[list[str], Path, Path, Path]:
    source = seed_context_bug(root, "source-owner", slug)
    successor = root / "receiving-registry" / "accepted-successor.md"
    successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
    successor.parent.mkdir(parents=True)
    successor.write_bytes(successor_bytes)
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    binding = successor_binding_bytes(slug, successor_bytes, operation_id)
    binding_file = root / "input" / "successor-binding.json"
    inventory_file = root / "input" / "incoming-links.json"
    binding_file.parent.mkdir(parents=True)
    binding_file.write_bytes(binding)
    inventory_file.write_bytes(
        successor_link_inventory_bytes(
            slug, source.read_bytes(), binding, operation_id
        )
    )
    return (
        [
            "supersede-current-bug",
            "--root",
            str(root),
            "--slug",
            slug,
            "--successor-record",
            str(successor),
            "--successor-binding-file",
            str(binding_file),
            "--terminal-instant",
            "2026-09-10T08:05:00Z",
            "--incoming-links-inventory",
            str(inventory_file),
            "--expected-bug-sha256",
            hashlib.sha256(source.read_bytes()).hexdigest(),
            "--expected-readme-sha256",
            hashlib.sha256(readme.read_bytes()).hexdigest(),
            "--operation-id",
            operation_id,
            "--apply",
        ],
        source,
        binding_file,
        successor,
    )


def test_shared_bug_recovery_preserves_supersession_error_text(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-10-supersession-diagnostic"
    operation_id = "supersession-diagnostic"
    argv, source, binding_file, successor = _supersede_current_bug_cli_fixture(
        module, root, slug, operation_id,
    )
    with unittest.TestCase().assertRaises(module.LifecycleError):
        module.supersede_current_bug(
            root, slug, successor, binding_file.read_bytes(),
            argv[argv.index("--terminal-instant") + 1],
            (root / "input" / "incoming-links.json").read_bytes(),
            hashlib.sha256(source.read_bytes()).hexdigest(),
            hashlib.sha256((root / "work-items" / "README.md").read_bytes()).hexdigest(),
            operation_id, inject_failure_at="B1",
        )
    source_before_drift = source.read_bytes()
    source.write_bytes(b"foreign mutation\n")

    with unittest.TestCase().assertRaises(module.LifecycleError) as failed_recovery:
        _recover_pending_transitions(module, root)

    assert failed_recovery.exception.failure_id == "WI-BUG-SUPERSESSION-ROLLBACK-INDETERMINATE"
    assert str(failed_recovery.exception) == "bug supersession rollback identity differs"
    assert source.read_bytes() == b"foreign mutation\n"
    source.write_bytes(source_before_drift)
    _recover_pending_transitions(module, root)
    assert not list((root / ".scratch" / "work-items-lifecycle-transitions").glob("*.json"))


def test_supersede_current_bug_cli_projects_failure_output_without_caller_content(
    tmp_path: Path,
) -> None:
    cases = (
        (
            "duplicate-token-key",
            "SYNTHETIC_TOKEN_LIKE_sk_FAKE_6f3d9a0c",
            "duplicate",
            "WI-BUG-SUCCESSOR-BINDING: current bug supersession rejected\n",
        ),
        (
            "duplicate-log-key",
            "SYNTHETIC_RAW_LOG_2026-09-10T08_30_00Z_ERROR_5b72c1e4",
            "duplicate",
            "WI-BUG-SUCCESSOR-BINDING: current bug supersession rejected\n",
        ),
        (
            "missing-path",
            "SYNTHETIC_MACHINE_LOCAL_PATH_91e7c4ab",
            "missing",
            "WI-IO: required current bug supersession input could not be read\n",
        ),
        (
            "malformed-control",
            "SYNTHETIC_MALFORMED_CONTROL_2dc848ae",
            "malformed",
            "WI-BUG-SUCCESSOR-BINDING: current bug supersession rejected\n",
        ),
    )
    for case, sentinel, mode, expected_stdout in cases:
        module = load_module()
        root = tmp_path / case
        slug = f"2026-09-10-{case}-failure-output"
        operation_id = f"failure-output-{case}"
        argv, source, binding_file, successor = _supersede_current_bug_cli_fixture(
            module, root, slug, operation_id
        )
        if mode == "duplicate":
            valid = binding_file.read_bytes()
            binding_file.write_bytes(
                (f'{{"{sentinel}":"first","{sentinel}":"second",').encode()
                + valid[1:]
            )
        elif mode == "missing":
            missing = root / "missing-input" / sentinel / "successor-binding.json"
            argv[argv.index(str(binding_file))] = str(missing)
        else:
            binding_file.write_bytes(b"{" + sentinel.encode("ascii"))
        before = tree_file_bytes(root)

        result = run_cli_separate_streams(*argv)

        assert result.returncode == 1, case
        assert result.stdout == expected_stdout, case
        assert result.stderr == "", case
        assert sentinel not in result.stdout, case
        assert sentinel not in result.stderr, case
        assert tree_file_bytes(root) == before, case
        assert source.is_file(), case
        assert successor.is_file(), case
        assert not list((root / "work-items" / "bugs").glob("archive/*/*.md")), case
        assert not list(root.rglob("*.supersession-receipt.json")), case
        assert not (
            root
            / ".scratch"
            / "work-items-lifecycle-transitions"
            / f"{operation_id}.json"
        ).exists(), case


def test_supersede_current_bug_main_projects_unexpected_exception_and_preserves_controls(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "unexpected"
    argv, _source, _binding_file, _successor = _supersede_current_bug_cli_fixture(
        module,
        root,
        "2026-09-10-unexpected-failure-output",
        "failure-output-unexpected",
    )
    marker = "SYNTHETIC_UNEXPECTED_RUNTIME_MARKER_7c91e2"
    output = io.StringIO()
    error = io.StringIO()
    with patch.object(
        module,
        "supersede_current_bug",
        side_effect=RuntimeError(marker),
    ), redirect_stdout(output), redirect_stderr(error):
        assert module.main(argv) == 1
    assert output.getvalue() == (
        "WI-BUG-SUPERSESSION-UNEXPECTED: "
        "current bug supersession failed unexpectedly\n"
    )
    assert error.getvalue() == ""
    assert marker not in output.getvalue()
    assert "Traceback" not in output.getvalue()

    for interruption in (
        KeyboardInterrupt("synthetic keyboard interruption"),
        asyncio.CancelledError("synthetic cancellation"),
    ):
        output = io.StringIO()
        error = io.StringIO()
        with patch.object(
            module,
            "supersede_current_bug",
            side_effect=interruption,
        ), redirect_stdout(output), redirect_stderr(error):
            with unittest.TestCase().assertRaises(type(interruption)) as caught:
                module.main(argv)
        assert caught.exception is interruption
        assert output.getvalue() == ""
        assert error.getvalue() == ""

    detailed = "other command retains its detailed diagnostic"
    output = io.StringIO()
    error = io.StringIO()
    with patch.object(
        module,
        "refresh_readme",
        side_effect=module.LifecycleError("WI-README-STALE", detailed),
    ), redirect_stdout(output), redirect_stderr(error):
        assert module.main(["refresh", "--root", str(root)]) == 1
    assert output.getvalue() == f"WI-README-STALE: {detailed}\n"
    assert error.getvalue() == ""


def test_supersede_current_bug_rejects_unreadable_live_reference_consumers_without_mutation(
    tmp_path: Path,
) -> None:
    for failure_kind in ("unicode", "oserror"):
        for inventory_kind in ("zero", "partial"):
            module = load_module()
            case = f"{failure_kind}-{inventory_kind}"
            root = tmp_path / case
            slug = f"2026-09-10-unreadable-{case}"
            operation_id = f"supersede-unreadable-{case}"
            source = seed_context_bug(root, "source-owner", slug)
            source_before = source.read_bytes()
            active = root / "work-items" / "active"
            write(active / "unreadable-consumer" / "status.md", quick_status())
            unreadable = active / "unreadable-consumer" / "notes.md"
            unreadable.parent.mkdir(parents=True, exist_ok=True)
            unreadable.write_bytes(
                f"Related: bug:{slug}\n".encode("utf-8")
                + (b"\xff" if failure_kind == "unicode" else b"")
            )
            valid = active / "valid-consumer" / "notes.md"
            valid_before = f"Related: bug:{slug}\n".encode("utf-8")
            valid_after = (
                "Related: external-bug-registry#bug:accepted-successor\n"
            ).encode("utf-8")
            if inventory_kind == "partial":
                write(active / "valid-consumer" / "status.md", quick_status())
                valid.parent.mkdir(parents=True, exist_ok=True)
                valid.write_bytes(valid_before)
            successor = root / "receiving-registry" / "accepted-successor.md"
            successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
            successor.parent.mkdir(parents=True)
            successor.write_bytes(successor_bytes)
            module.refresh_readme(root, allow_marker_bootstrap=True)
            readme = root / "work-items" / "README.md"
            binding = successor_binding_bytes(slug, successor_bytes, operation_id)
            links = (
                [
                    {
                        "path": valid.relative_to(root).as_posix(),
                        "beforeSha256": hashlib.sha256(valid_before).hexdigest(),
                        "afterSha256": hashlib.sha256(valid_after).hexdigest(),
                        "afterBytesBase64": base64.b64encode(valid_after).decode("ascii"),
                    }
                ]
                if inventory_kind == "partial"
                else []
            )
            inventory = successor_link_inventory_bytes(
                slug, source_before, binding, operation_id, links
            )
            work_items_before = tree_file_bytes(root / "work-items")
            successor_before = successor.read_bytes()
            original_read_bytes = Path.read_bytes

            def injected_read_bytes(path: Path) -> bytes:
                if failure_kind == "oserror" and path == unreadable:
                    raise OSError("injected unreadable live reference consumer")
                return original_read_bytes(path)

            try:
                with patch.object(Path, "read_bytes", injected_read_bytes):
                    module.supersede_current_bug(
                        root,
                        slug,
                        successor,
                        binding,
                        "2026-09-10T08:01:30Z",
                        inventory,
                        hashlib.sha256(source_before).hexdigest(),
                        hashlib.sha256(readme.read_bytes()).hexdigest(),
                        operation_id,
                    )
            except module.LifecycleError as exc:
                assert exc.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY", case
            else:
                raise AssertionError(f"{case} unreadable live consumer was omitted")

            assert tree_file_bytes(root / "work-items") == work_items_before, case
            assert successor.read_bytes() == successor_before, case
            assert not (
                root
                / ".scratch"
                / "work-items-lifecycle-transitions"
                / f"{operation_id}.json"
            ).exists(), case


def test_supersede_current_bug_excludes_unreadable_archived_consumers_from_strict_inventory(
    tmp_path: Path,
) -> None:
    for failure_kind in ("unicode", "oserror"):
        module = load_module()
        root = tmp_path / failure_kind
        slug = f"2026-09-10-archived-control-{failure_kind}"
        operation_id = f"supersede-archived-control-{failure_kind}"
        source = seed_context_bug(root, "source-owner", slug)
        source_before = source.read_bytes()
        historical = (
            root
            / "work-items"
            / "archive"
            / "2026-08"
            / "unrelated-history"
        )
        write(historical / "status.md", marked_status())
        write(
            historical / "closure.md",
            marked_closure("2026-08-01T00:00:00Z"),
        )
        archived_consumer = historical / "notes.bin"
        archived_consumer.write_bytes(
            f"Historical: bug:{slug}\n".encode("utf-8")
            + (b"\xff" if failure_kind == "unicode" else b"")
        )
        archived_consumer_before = archived_consumer.read_bytes()
        successor = root / "receiving-registry" / "accepted-successor.md"
        successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
        successor.parent.mkdir(parents=True)
        successor.write_bytes(successor_bytes)
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme = root / "work-items" / "README.md"
        binding = successor_binding_bytes(slug, successor_bytes, operation_id)
        inventory = successor_link_inventory_bytes(
            slug, source_before, binding, operation_id
        )
        original_read_bytes = Path.read_bytes

        def injected_read_bytes(path: Path) -> bytes:
            if failure_kind == "oserror" and path == archived_consumer:
                raise OSError("injected unreadable archived consumer")
            return original_read_bytes(path)

        with patch.object(Path, "read_bytes", injected_read_bytes):
            settled = module.supersede_current_bug(
                root,
                slug,
                successor,
                binding,
                "2026-09-10T08:01:45Z",
                inventory,
                hashlib.sha256(source_before).hexdigest(),
                hashlib.sha256(readme.read_bytes()).hexdigest(),
                operation_id,
            )

        archive = (
            root
            / "work-items"
            / "bugs"
            / "archive"
            / "2026-09"
            / f"{slug}.md"
        )
        assert settled["status"] == "settled", failure_kind
        assert not source.exists() and archive.is_file(), failure_kind
        assert archived_consumer.read_bytes() == archived_consumer_before, failure_kind
        assert successor.read_bytes() == successor_bytes, failure_kind
        assert not (
            root
            / ".scratch"
            / "work-items-lifecycle-transitions"
            / f"{operation_id}.json"
        ).exists(), failure_kind


@pytest.mark.parametrize("opaque", (False, True))
def test_supersede_current_bug_archives_links_and_readme_in_one_recoverable_intent(
    tmp_path: Path, opaque: bool,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-10-source-bug"
    operation_id = "supersede-current-bug-success"
    terminal_instant = "2026-09-10T08:02:00Z"
    source = seed_context_bug(root, "source-owner", slug)
    source_before = source.read_bytes()
    consumer = root / "work-items" / "active" / "consumer" / ("design.md" if opaque else "status.md")
    old_href = f"../../bugs/{slug}.md"
    successor_reference = "external-bug-registry#bug:accepted-successor"
    consumer_before = (
        quick_status("Track the source bug.")
        + f"\nRelated: bug:{slug}\n[physical]({old_href})\n"
    ).encode("utf-8")
    if opaque:
        consumer_before = b"\xef\xbb\xbf\xc3\xa9\x97\r\n" + consumer_before + b"\x81"
    consumer_after = consumer_before.replace(
        f"bug:{slug}".encode("utf-8"), successor_reference.encode("utf-8")
    ).replace(old_href.encode("utf-8"), successor_reference.encode("utf-8"))
    consumer.parent.mkdir(parents=True)
    if opaque:
        (consumer.parent / "status.md").write_text(quick_status(), encoding="utf-8")
    consumer.write_bytes(consumer_before)
    successor = root / "receiving-registry" / "accepted-successor.md"
    successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
    successor.parent.mkdir(parents=True)
    successor.write_bytes(successor_bytes)
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    readme_before_sha256 = hashlib.sha256(readme.read_bytes()).hexdigest()
    binding = successor_binding_bytes(slug, successor_bytes, operation_id)
    inventory = successor_link_inventory_bytes(
        slug,
        source_before,
        binding,
        operation_id,
        [
            {
                "path": consumer.relative_to(root).as_posix(),
                "beforeSha256": hashlib.sha256(consumer_before).hexdigest(),
                "afterSha256": hashlib.sha256(consumer_after).hexdigest(),
                "afterBytesBase64": base64.b64encode(consumer_after).decode("ascii"),
            }
        ],
    )
    binding_file = root / "successor-binding.json"
    inventory_file = root / "incoming-links.json"
    binding_file.write_bytes(binding)
    inventory_file.write_bytes(inventory)
    successor_before = successor.read_bytes()

    result = run_cli(
        "supersede-current-bug",
        "--root",
        str(root),
        "--slug",
        slug,
        "--successor-record",
        str(successor),
        "--successor-binding-file",
        str(binding_file),
        "--terminal-instant",
        terminal_instant,
        "--incoming-links-inventory",
        str(inventory_file),
        "--expected-bug-sha256",
        hashlib.sha256(source_before).hexdigest(),
        "--expected-readme-sha256",
        readme_before_sha256,
        "--operation-id",
        operation_id,
        "--apply",
    )
    assert result.returncode == 0, result.stdout
    assert "WI-BUG-SUPERSESSION-COMMITTED" in result.stdout

    archive = (
        root
        / "work-items"
        / "bugs"
        / "archive"
        / "2026-09"
        / f"{slug}.md"
    )
    receipt_path = archive.with_name(f"{slug}.supersession-receipt.json")
    assert not source.exists()
    assert archive.is_file()
    assert consumer.read_bytes() == consumer_after
    assert successor.read_bytes() == successor_before
    fields = module._parse_fields(archive.read_text(encoding="utf-8"))
    assert fields["status"] == "superseded"
    assert fields["terminal-at"] == terminal_instant
    assert fields["resolution"] == f"Superseded by {successor_reference}."
    assert fields["evidence"] == "Receiving owner accepted the current successor."
    assert fields["successor"] == successor_reference
    assert str(successor) not in archive.read_text(encoding="utf-8")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert set(receipt) == {
        "schemaVersion",
        "owner",
        "kind",
        "status",
        "operationId",
        "terminalInstant",
        "sourceReference",
        "sourcePath",
        "archivePath",
        "archivedBugSha256",
        "successorBindingSha256",
        "successorRegistryReference",
        "successorRecordReference",
        "successorRecordSha256",
        "acceptedBy",
        "acceptedAt",
        "acceptanceEvidence",
        "incomingLinksInventorySha256",
        "links",
        "readmeSha256",
        "requestExpectedBugSha256",
        "requestExpectedReadmeSha256",
    }
    assert receipt["owner"] == "mutate-work-item:current-bug-supersession-v1"
    assert receipt["kind"] == "current-bug-supersession-v1"
    assert receipt["status"] == "settled"
    assert receipt["sourceReference"] == f"bug:{slug}"
    assert receipt["successorRegistryReference"] == "external-bug-registry"
    assert receipt["successorRecordReference"] == "bug:accepted-successor"
    assert receipt["links"] == [
        {
            "path": consumer.relative_to(root).as_posix(),
            "beforeSha256": hashlib.sha256(consumer_before).hexdigest(),
            "afterSha256": hashlib.sha256(consumer_after).hexdigest(),
        }
    ]
    assert receipt["readmeSha256"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    assert not (
        root / ".scratch" / "work-items-lifecycle-transitions" / f"{operation_id}.json"
    ).exists()


def test_supersede_current_bug_replay_is_exact_and_mismatch_fails(
    tmp_path: Path,
) -> None:
    def prepare(root: Path, suffix: str) -> tuple[object, dict, bytes, bytes]:
        module = load_module()
        slug = f"2026-09-10-recovery-{suffix}"
        operation_id = f"supersede-recovery-{suffix}"
        terminal_instant = "2026-09-10T08:03:00Z"
        source = seed_context_bug(root, "source-owner", slug)
        source_before = source.read_bytes()
        consumer = root / "work-items" / "active" / f"consumer-{suffix}" / "status.md"
        successor_reference = "external-bug-registry#bug:accepted-successor"
        consumer_before = (
            quick_status("Track one source bug.") + f"\nRelated: bug:{slug}\n"
        ).encode("utf-8")
        consumer_after = consumer_before.replace(
            f"bug:{slug}".encode(), successor_reference.encode()
        )
        consumer.parent.mkdir(parents=True)
        consumer.write_bytes(consumer_before)
        successor = root / "receiving-registry" / "accepted-successor.md"
        successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
        successor.parent.mkdir(parents=True)
        successor.write_bytes(successor_bytes)
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme = root / "work-items" / "README.md"
        binding = successor_binding_bytes(slug, successor_bytes, operation_id)
        inventory = successor_link_inventory_bytes(
            slug,
            source_before,
            binding,
            operation_id,
            [
                {
                    "path": consumer.relative_to(root).as_posix(),
                    "beforeSha256": hashlib.sha256(consumer_before).hexdigest(),
                    "afterSha256": hashlib.sha256(consumer_after).hexdigest(),
                    "afterBytesBase64": base64.b64encode(consumer_after).decode("ascii"),
                }
            ],
        )
        request = {
            "root": root,
            "slug": slug,
            "successor_record": successor,
            "successor_binding_data": binding,
            "terminal_instant": terminal_instant,
            "incoming_links_inventory_data": inventory,
            "expected_bug_sha256": hashlib.sha256(source_before).hexdigest(),
            "expected_readme_sha256": hashlib.sha256(readme.read_bytes()).hexdigest(),
            "operation_id": operation_id,
        }
        return module, request, consumer_after, successor_bytes

    replay_root = tmp_path / "replay"
    module, request, consumer_after, successor_bytes = prepare(replay_root, "replay")
    settled = module.supersede_current_bug(**request)
    assert settled["status"] == "settled"
    assert request["successor_record"].read_bytes() == successor_bytes
    before_replay = tree_file_bytes(replay_root / "work-items")
    missing_runtime_path = replay_root / "receiving-registry" / "not-present.md"
    replay_request = dict(request)
    replay_request["successor_record"] = missing_runtime_path
    assert module.supersede_current_bug(**replay_request) == settled
    assert tree_file_bytes(replay_root / "work-items") == before_replay

    mismatch_requests = {
        "binding": {
            "successor_binding_data": request["successor_binding_data"] + b" "
        },
        "inventory": {
            "incoming_links_inventory_data": request["incoming_links_inventory_data"]
            + b" "
        },
        "bug-hash": {"expected_bug_sha256": "0" * 64},
        "readme-hash": {"expected_readme_sha256": "1" * 64},
        "terminal": {"terminal_instant": "2026-09-10T08:04:00Z"},
        "operation": {"operation_id": request["operation_id"] + "-other"},
    }
    for case, delta in mismatch_requests.items():
        mismatched = dict(replay_request)
        mismatched.update(delta)
        try:
            module.supersede_current_bug(**mismatched)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-SUPERSESSION-SETTLEMENT-MISMATCH", case
        else:
            raise AssertionError(f"{case} replay mismatch was accepted")
        assert tree_file_bytes(replay_root / "work-items") == before_replay, case

    drift_root = tmp_path / "archive-byte-drift"
    module, request, _consumer_after, _successor_bytes = prepare(
        drift_root, "archive-byte-drift"
    )
    module.supersede_current_bug(**request)
    archived_bug = (
        drift_root
        / "work-items"
        / "bugs"
        / "archive"
        / "2026-09"
        / f"{request['slug']}.md"
    )
    archived_bug.write_bytes(b"\xff")
    drift_replay = dict(request)
    drift_replay["successor_record"] = drift_root / "missing-runtime-record.md"
    try:
        module.supersede_current_bug(**drift_replay)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-SUPERSESSION-SETTLEMENT-MISMATCH"
    else:
        raise AssertionError("non-UTF-8 archived bug drift passed replay")

    for boundary_index in range(8):
        boundary = f"B{boundary_index}"
        root = tmp_path / boundary.casefold()
        module, request, expected_consumer, successor_bytes = prepare(
            root, boundary.casefold()
        )
        try:
            module.supersede_current_bug(
                **request, inject_failure_at=boundary
            )
        except module.LifecycleError as exc:
            expected_failure = (
                "WI-BUG-SUPERSESSION-ROLLBACK-INDETERMINATE"
                if boundary_index <= 2
                else "WI-BUG-SUPERSESSION-ROLLFORWARD-INDETERMINATE"
            )
            assert exc.failure_id == expected_failure, boundary
        else:
            raise AssertionError(f"{boundary} did not interrupt settlement")

        recovered = module.supersede_current_bug(**request)
        assert recovered["status"] == "settled", boundary
        source = root / "work-items" / "bugs" / f"{request['slug']}.md"
        archive = (
            root
            / "work-items"
            / "bugs"
            / "archive"
            / "2026-09"
            / f"{request['slug']}.md"
        )
        consumer = (
            root
            / "work-items"
            / "active"
            / f"consumer-{boundary.casefold()}"
            / "status.md"
        )
        assert not source.exists() and archive.is_file(), boundary
        assert consumer.read_bytes() == expected_consumer, boundary
        assert request["successor_record"].read_bytes() == successor_bytes, boundary
        assert not (
            root
            / ".scratch"
            / "work-items-lifecycle-transitions"
            / f"{request['operation_id']}.json"
        ).exists(), boundary


def test_category_audit_rejects_unapplied_active_bug_dispositions(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "pending-close-reconciliation"
    seed_active(module, root, slug)
    write_empty_bug_dispositions(root, slug, "2026-08-11T10:09:00Z")

    try:
        module.audit_categories(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-PENDING"
    else:
        raise AssertionError("unapplied active bug disposition passed category audit")


def test_start_staged_publishes_valid_settled_admission_ledger(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "staged-ledger-birth"
    candidate = b"Task: publish a valid staged admission.\n"
    status = staged_status("2026-07-01-archived-concern").encode("utf-8")
    module.create_candidate(root, slug, candidate)

    target = module.start_item(root, slug, status)

    assert (target / "admission.md").read_bytes() == candidate
    assert (target / "status.md").read_bytes() == status
    lines = (target / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "schemaVersion": 2,
        "runId": f"{slug}-lifecycle-start",
        "workItem": slug,
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": ["candidate -> active lifecycle admission"],
        "startedAt": "2026-07-31T00:00:00Z",
        "updatedAt": "2026-07-31T00:00:00Z",
        "eventKind": "standalone",
    }
    result = run_state_validator(target)
    assert result.returncode == 0, result.stdout


def test_start_staged_cli_publishes_valid_admission_ledger(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    slug = "staged-ledger-cli"
    candidate = root / "candidate.md"
    status = root / "status.md"
    write(candidate, "Task: publish staged admission through the CLI.\n")
    write(status, staged_status("2026-07-01-archived-concern"))

    created = run_cli(
        "candidate", "--root", str(root), "--slug", slug, "--file", str(candidate)
    )
    started = run_cli(
        "start", "--root", str(root), "--slug", slug, "--status-file", str(status)
    )

    assert created.returncode == 0, created.stdout
    assert started.returncode == 0, started.stdout
    target = root / "work-items" / "active" / slug
    event = json.loads((target / "agent-runs.jsonl").read_text(encoding="utf-8"))
    assert event["runId"] == f"{slug}-lifecycle-start"
    result = run_state_validator(target)
    assert result.returncode == 0, result.stdout


def test_staged_start_loader_failures_use_stable_id_and_preserve_candidate(tmp_path: Path) -> None:
    cases = (
        ("construction-import", "construct", ImportError("injected construction failure")),
        ("execution-import", "execute", ImportError("injected import failure")),
        ("execution-syntax", "execute", SyntaxError("injected syntax failure")),
        ("execution-os", "execute", OSError("injected execution failure")),
    )

    for name, phase, injected in cases:
        module = load_module()
        root = tmp_path / name
        slug = f"staged-loader-{name}"
        candidate = f"Task: preserve {name} candidate bytes.\n".encode("utf-8")
        status_path = root / "status.md"
        write(status_path, staged_status("2026-07-01-archived-concern"))
        module.create_candidate(root, slug, candidate)
        backlog = root / "work-items" / "backlog" / f"{slug}.md"
        candidate_sha256 = hashlib.sha256(backlog.read_bytes()).hexdigest()
        original_from_spec = module.importlib.util.spec_from_file_location
        original_module_from_spec = module.importlib.util.module_from_spec

        class FailingLoader:
            def create_module(self, _spec):
                return None

            def exec_module(self, _loaded_module) -> None:
                raise injected

        def injected_spec(name_arg, path_arg):
            spec = original_from_spec(name_arg, path_arg)
            if name_arg == "agent_run_ledger":
                assert spec is not None
                spec.loader = FailingLoader()
            return spec

        def injected_module_from_spec(spec):
            if phase == "construct" and spec.name == "agent_run_ledger":
                raise injected
            return original_module_from_spec(spec)

        module.importlib.util.spec_from_file_location = injected_spec
        module.importlib.util.module_from_spec = injected_module_from_spec
        try:
            try:
                module._agent_run_ledger_module()
            except module.LifecycleError as exc:
                assert exc.failure_id == "WI-LEDGER-BOOTSTRAP-INVALID"
                assert exc.__cause__ is injected
            else:
                raise AssertionError(f"{name} escaped the typed ledger boundary")

            output = io.StringIO()
            with redirect_stdout(output):
                result = module.main(
                    [
                        "start",
                        "--root",
                        str(root),
                        "--slug",
                        slug,
                        "--status-file",
                        str(status_path),
                    ]
                )
        finally:
            module.importlib.util.spec_from_file_location = original_from_spec
            module.importlib.util.module_from_spec = original_module_from_spec

        assert result == 1, name
        assert "WI-LEDGER-BOOTSTRAP-INVALID" in output.getvalue(), name
        assert "Traceback" not in output.getvalue(), name
        assert hashlib.sha256(backlog.read_bytes()).hexdigest() == candidate_sha256, name
        active = root / "work-items" / "active"
        assert not (active / slug).exists(), name
        assert not list(active.glob(f".{slug}.*")) if active.exists() else True


def test_agent_run_ledger_loader_does_not_swallow_base_exception(tmp_path: Path) -> None:
    module = load_module()
    original_from_spec = module.importlib.util.spec_from_file_location
    interruption = KeyboardInterrupt("injected cancellation signal")

    class InterruptingLoader:
        def create_module(self, _spec):
            return None

        def exec_module(self, _loaded_module) -> None:
            raise interruption

    def injected_spec(name_arg, path_arg):
        spec = original_from_spec(name_arg, path_arg)
        if name_arg == "agent_run_ledger":
            assert spec is not None
            spec.loader = InterruptingLoader()
        return spec

    module.importlib.util.spec_from_file_location = injected_spec
    try:
        try:
            module._agent_run_ledger_module()
        except KeyboardInterrupt as exc:
            assert exc is interruption
        else:
            raise AssertionError("BaseException cancellation signal was swallowed")
    finally:
        module.importlib.util.spec_from_file_location = original_from_spec


def test_staged_start_ledger_failure_restores_candidate(tmp_path: Path) -> None:
    cases = ("build", "serialize", "write", "temporary-validation", "final-replace")

    for phase in cases:
        module = load_module()
        root = tmp_path / phase
        slug = f"staged-ledger-{phase}"
        candidate = f"Task: preserve {phase} candidate bytes.\n".encode("utf-8")
        status = staged_status("2026-07-01-archived-concern").encode("utf-8")
        module.create_candidate(root, slug, candidate)
        backlog = root / "work-items" / "backlog" / f"{slug}.md"
        candidate_sha256 = hashlib.sha256(backlog.read_bytes()).hexdigest()
        original_ledger_module = module._agent_run_ledger_module
        original_atomic_write = module._atomic_write
        original_validator_module = module._validator_module
        original_replace = module.os.replace
        real_ledger = original_ledger_module()

        class InjectedLedger:
            def build_event(self, args):
                if phase == "build":
                    raise ValueError("injected event build failure")
                return real_ledger.build_event(args)

            def serialize_event(self, event):
                if phase == "serialize":
                    raise ValueError("injected event serialization failure")
                return real_ledger.serialize_event(event)

        class RejectingValidator:
            def validate_obligation_transfer_ownership(self, _root):
                return []

            def validate_work_item(self, _item, *, strict_revise=True):
                return ["injected temporary validation failure"]

        def injected_atomic_write(path: Path, data: bytes) -> None:
            if phase == "write" and path.name == "agent-runs.jsonl":
                raise OSError("injected ledger write failure")
            original_atomic_write(path, data)

        def injected_replace(source, target) -> None:
            if phase == "final-replace" and Path(source).is_dir():
                raise OSError("injected final replace failure")
            original_replace(source, target)

        module._agent_run_ledger_module = lambda: InjectedLedger()
        module._atomic_write = injected_atomic_write
        if phase == "temporary-validation":
            module._validator_module = lambda: RejectingValidator()
        module.os.replace = injected_replace
        try:
            try:
                module.start_item(root, slug, status)
            except (module.LifecycleError, OSError):
                pass
            else:
                raise AssertionError(f"{phase} failure did not abort staged start")
        finally:
            module._agent_run_ledger_module = original_ledger_module
            module._atomic_write = original_atomic_write
            module._validator_module = original_validator_module
            module.os.replace = original_replace

        assert hashlib.sha256(backlog.read_bytes()).hexdigest() == candidate_sha256, phase
        active = root / "work-items" / "active"
        assert not (active / slug).exists(), phase
        assert not list(active.glob(f".{slug}.*")), phase


def test_staged_bootstrap_event_allows_close_after_terminal_work(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "staged-bootstrap-close"
    candidate = b"Task: exercise staged admission through archive.\n"
    status = staged_status("2026-07-01-archived-concern").encode("utf-8")
    module.create_candidate(root, slug, candidate)
    active = module.start_item(root, slug, status)

    launch_id = "staged-real-launch-001"
    launched = run_ledger(
        active,
        "append",
        "--run-id",
        launch_id,
        "--role",
        "platform-engineer",
        "--execution-role",
        "internal",
        "--status",
        "running",
        "--gate",
        "none",
        "--scope",
        "staged lifecycle implementation",
        "--event-kind",
        "launch",
        "--started-at",
        "2026-07-31T00:01:00Z",
        "--updated-at",
        "2026-07-31T00:01:00Z",
    )
    assert launched.returncode == 0, launched.stdout
    open_validation = run_state_validator(active)
    assert open_validation.returncode == 1
    assert "unsettled launch" in open_validation.stdout

    terminal = run_ledger(
        active,
        "append",
        "--run-id",
        "staged-real-terminal-001",
        "--role",
        "platform-engineer",
        "--execution-role",
        "internal",
        "--status",
        "completed",
        "--gate",
        "none",
        "--scope",
        "staged lifecycle implementation",
        "--event-kind",
        "terminal",
        "--launch-run-id",
        launch_id,
        "--started-at",
        "2026-07-31T00:01:00Z",
        "--updated-at",
        "2026-07-31T00:02:00Z",
    )
    assert terminal.returncode == 0, terminal.stdout
    settled_validation = run_state_validator(active)
    assert settled_validation.returncode == 0, settled_validation.stdout

    instant = "2026-07-31T00:03:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert archived == root / "work-items" / "archive" / "2026-07" / slug
    assert run_state_validator(archived).returncode == 0
    rollup = run_ledger(archived, "rollup")
    assert rollup.returncode == 0, rollup.stdout
    assert "total runs: 3" in rollup.stdout
    assert "lead=1" in rollup.stdout
    assert "platform-engineer=2" in rollup.stdout


def test_staged_start_readme_failure_leaves_valid_canonical_item(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "staged-ledger-readme"
    candidate = b"Task: preserve canonical start on README failure.\n"
    status = staged_status("2026-07-01-archived-concern").encode("utf-8")
    module.create_candidate(root, slug, candidate)

    try:
        module.start_item(root, slug, status, inject_readme_failure=True)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
        assert str(exc) == (
            "start committed canonical state; README refresh required; "
            "do not retry start; run refresh, then verify the target."
        )
    else:
        raise AssertionError("injected README failure did not abort the derived-view refresh")

    target = root / "work-items" / "active" / slug
    assert target.is_dir()
    assert not (root / "work-items" / "backlog" / f"{slug}.md").exists()
    result = run_state_validator(target)
    assert result.returncode == 0, result.stdout
    try:
        module.check_readme(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("post-commit start unexpectedly refreshed README")
    module.refresh_readme(root)
    module.audit(root)
    assert module.resolve_category(root, f"work-item:{slug}") == target.resolve()


def test_update_and_reopen_readme_failures_share_actionable_postcommit_diagnostic(
    tmp_path: Path,
) -> None:
    module = load_module()

    update_root = tmp_path / "update"
    update_slug = "postcommit-update"
    seed_active(module, update_root, update_slug)
    updated_status = quick_status("Updated canonical task state.").encode("utf-8")
    try:
        module.update_status(
            update_root,
            update_slug,
            updated_status,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
        assert str(exc) == (
            "update committed canonical state; README refresh required; "
            "do not retry update; run refresh, then verify the target."
        )
    else:
        raise AssertionError("injected update README failure returned success")
    updated = update_root / "work-items" / "active" / update_slug / "status.md"
    assert updated.read_bytes() == updated_status
    module.refresh_readme(update_root)
    module.audit(update_root)

    reopen_root = tmp_path / "reopen"
    archived_slug = "postcommit-reopen-source"
    successor_slug = "postcommit-reopen-successor"
    seed_active(module, reopen_root, archived_slug)
    instant = "2026-07-31T13:00:00Z"
    write_empty_bug_dispositions(reopen_root, archived_slug, instant)
    archived = module.close_item(
        reopen_root,
        archived_slug,
        closure(instant).encode("utf-8"),
        instant,
    )
    successor_status = staged_status(archived_slug).encode("utf-8")
    try:
        module.reopen_item(
            reopen_root,
            archived_slug,
            successor_slug,
            successor_status,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
        assert str(exc) == (
            "reopen committed canonical state; README refresh required; "
            "do not retry reopen; run refresh, then verify the target."
        )
    else:
        raise AssertionError("injected reopen README failure returned success")
    successor = reopen_root / "work-items" / "active" / successor_slug
    assert successor.joinpath("status.md").read_bytes() == successor_status
    assert archived.is_dir()
    module.refresh_readme(reopen_root)
    module.audit(reopen_root)
    assert module.resolve_category(
        reopen_root, f"work-item:{archived_slug}"
    ) == archived.resolve()


def test_start_quick_fix_preserves_ledger_free_contract(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "quick-fix-ledger-free"
    candidate = b"Task: preserve the quick-fix exception.\n"
    status = quick_status(slug).encode("utf-8")
    module.create_candidate(root, slug, candidate)

    target = module.start_item(root, slug, status)

    assert not (target / "agent-runs.jsonl").exists()
    result = run_state_validator(target)
    assert result.returncode == 0, result.stdout


def test_five_item_readme_trial(tmp_path: Path) -> None:
    trial_root = tmp_path / "trial"
    result = run_cli("trial", "--root", str(trial_root), "--fixture", str(FIXTURE))

    assert result.returncode == 0, result.stdout
    assert "TRIAL: PASS" in result.stdout
    assert "items=5" in result.stdout
    assert (
        "sections=Current focus|Next actions|Blockers|Roadmap and milestones|Recently completed"
        in result.stdout
    )
    hashes = [
        line.split("=", 1)[1]
        for line in result.stdout.splitlines()
        if line.startswith("readme_sha256_")
    ]
    assert len(hashes) == 2
    assert hashes[0] == hashes[1]
    assert all(len(value) == 64 for value in hashes)
    text = (trial_root / "work-items" / "README.md").read_text(encoding="utf-8")
    assert sum(line.startswith("- [") for line in text.splitlines()) == 5
    assert all(
        line.startswith(("- [ ]", "- [x]"))
        for line in text.splitlines()
        if line.startswith("- [")
    )
    assert "[roadmap](" in text and "[epic](" in text and "[work item](" in text


def test_trial_repeat_success_preserves_hashes(tmp_path: Path) -> None:
    trial_root = tmp_path / "repeatable-trial"
    first = run_cli("trial", "--root", str(trial_root), "--fixture", str(FIXTURE))
    readme_before = (trial_root / "work-items" / "README.md").read_bytes()
    receipt_before = (
        trial_root / ".work-items-lifecycle-v1-trial.json"
    ).read_bytes()

    second = run_cli("trial", "--root", str(trial_root), "--fixture", str(FIXTURE))

    assert first.returncode == 0, first.stdout
    assert second.returncode == 0, second.stdout
    first_hashes = [
        line.split("=", 1)[1]
        for line in first.stdout.splitlines()
        if line.startswith("readme_sha256_")
    ]
    second_hashes = [
        line.split("=", 1)[1]
        for line in second.stdout.splitlines()
        if line.startswith("readme_sha256_")
    ]
    assert first_hashes == second_hashes
    assert len(first_hashes) == 2
    assert (trial_root / "work-items" / "README.md").read_bytes() == readme_before
    assert (
        trial_root / ".work-items-lifecycle-v1-trial.json"
    ).read_bytes() == receipt_before


def test_trial_foreign_root_is_preserved_and_fails_closed(tmp_path: Path) -> None:
    trial_root = tmp_path / "foreign-root"
    foreign = trial_root / "user-content.txt"
    write(foreign, "preserve this user content\n")
    before = foreign.read_bytes()

    result = run_cli("trial", "--root", str(trial_root), "--fixture", str(FIXTURE))

    assert result.returncode == 1
    assert "WI-TRIAL-NOT-OWNED" in result.stdout
    assert foreign.read_bytes() == before
    assert sorted(path.name for path in trial_root.iterdir()) == [
        ".scratch",
        "user-content.txt",
    ]
    assert (
        trial_root / ".scratch" / "work-items-lifecycle-owner.lock"
    ).read_bytes() == b"work-items-lifecycle-owner-v1\n"


def test_utc_same_instant_boundary_replay(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "utc-boundary"
    seed_active(module, root, slug)
    instant = "2026-08-01T00:00:00Z"
    closure_bytes = closure(instant).encode()

    write_empty_bug_dispositions(root, slug, instant)
    first = module.close_item(root, slug, closure_bytes, instant)
    first_hash = hashlib.sha256((first / "closure.md").read_bytes()).hexdigest()
    original_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "Pacific/Honolulu"
        replay_a = module.close_item(root, slug, closure_bytes, instant)
        os.environ["TZ"] = "Pacific/Kiritimati"
        replay_b = module.close_item(root, slug, closure_bytes, instant)
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz

    expected = root / "work-items" / "archive" / "2026-08" / slug
    assert first == expected
    assert replay_a == expected and replay_b == expected
    assert hashlib.sha256((expected / "closure.md").read_bytes()).hexdigest() == first_hash
    assert not (root / "work-items" / "active" / slug).exists()
    assert len(list((root / "work-items" / "archive").glob(f"*/*{slug}"))) == 1


def test_terminalization_stamps_schema_pair_once_and_replay_is_idempotent(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "schema-stamped"
    seed_active(module, root, slug)
    active_status = root / "work-items" / "active" / slug / "status.md"
    status_before = active_status.read_bytes()
    assert status_before == (root / "status.md").read_bytes()
    module._validate_active_status_bytes(status_before)
    assert LIFECYCLE_SCHEMA_MARKER.encode() not in status_before
    instant = "2026-08-01T00:00:00Z"
    closure_input = closure(instant).encode()

    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure_input, instant)
    status_after = (archived / "status.md").read_bytes()
    closure_after = (archived / "closure.md").read_bytes()
    hashes_after = {
        "status": hashlib.sha256(status_after).hexdigest(),
        "closure": hashlib.sha256(closure_after).hexdigest(),
    }

    assert status_after.count(LIFECYCLE_SCHEMA_MARKER.encode()) == 1
    assert closure_after.count(LIFECYCLE_SCHEMA_MARKER.encode()) == 1
    assert closure_input == closure(instant).encode()
    assert module.close_item(root, slug, closure_input, instant) == archived
    assert hashlib.sha256((archived / "status.md").read_bytes()).hexdigest() == hashes_after[
        "status"
    ]
    assert hashlib.sha256((archived / "closure.md").read_bytes()).hexdigest() == hashes_after[
        "closure"
    ]
    assert (archived / "status.md").read_bytes().count(
        LIFECYCLE_SCHEMA_MARKER.encode()
    ) == 1
    assert (archived / "closure.md").read_bytes().count(
        LIFECYCLE_SCHEMA_MARKER.encode()
    ) == 1


def test_archive_evidence_child_does_not_block_public_start(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "admitted-candidate"
    module.create_candidate(root, slug, b"Task: Run the admitted repair.\n")
    legacy_root = root / "work-items" / "archive" / "legacy-campaign"
    write(legacy_root / "handoff.md", "Historical campaign evidence.\n")
    evidence = legacy_root / "measurements-run"
    write(evidence / "evidence.md", "Measurements only.\n")
    write(evidence / "results.csv", "sample,value\n1,42\n")
    before = tree_file_bytes(legacy_root)

    target = module.start_item(root, slug, quick_status(slug).encode("utf-8"))

    assert target == root / "work-items" / "active" / slug
    assert target.joinpath("status.md").read_bytes() == quick_status(slug).encode("utf-8")
    assert not root.joinpath("work-items", "backlog", f"{slug}.md").exists()
    assert tree_file_bytes(legacy_root) == before
    assert {entry.logical_reference for entry in module.collect_readme_entries(root)} == {
        f"work-item:{slug}"
    }
    assert module._category_locations(root, module.CATEGORIES["work-item"], evidence.name) == []
    assert module.audit(root) == ()


def test_archive_canonical_missing_closure_still_blocks_public_start(
    tmp_path: Path,
) -> None:
    module = load_module()
    for owned_status in (False, True):
        root = tmp_path / str(owned_status)
        slug = "admitted-candidate"
        module.create_candidate(root, slug, b"Task: Preserve terminal refusal.\n")
        archived = root / "work-items" / "archive" / "2026-10" / "canonical-item"
        archived.mkdir(parents=True)
        if owned_status:
            write(archived / "status.md", marked_status())
        before = tree_file_bytes(root / "work-items")

        with pytest.raises(module.LifecycleError) as failure:
            module.start_item(root, slug, quick_status(slug).encode("utf-8"))

        assert failure.value.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
        assert tree_file_bytes(root / "work-items") == before
        assert not root.joinpath("work-items", "active", slug).exists()
        assert module._category_locations(root, module.CATEGORIES["work-item"], archived.name) == [archived]


def test_archive_candidate_selection_preserves_valid_identity_and_nested_attachment(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    archived = root / "work-items" / "archive" / "2026-10" / "canonical-item"
    write(archived / "status.md", marked_status())
    write(archived / "closure.md", marked_closure("2026-10-06T12:00:00Z"))
    write(archived / "attachments" / "nested-item" / "closure.md", "Outcome: attachment\n")
    before = tree_file_bytes(archived)

    module.refresh_readme(root, allow_marker_bootstrap=True)
    entries = module.collect_readme_entries(root)

    assert len(entries) == 1
    assert entries[0].logical_reference == "work-item:canonical-item"
    assert entries[0].link == archived / "closure.md"
    assert entries[0].classification is None
    assert module.resolve_category(root, "work-item:canonical-item") == archived.resolve()
    assert module.audit(root) == ()
    assert tree_file_bytes(archived) == before


def test_archive_nonmonth_owned_legacy_closure_keeps_compatibility(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    seed_legacy_archives(root)
    original = root / "work-items" / "archive" / "2026-03" / "legacy-no-closed"
    archived = root / "work-items" / "archive" / "legacy-campaign" / original.name
    archived.parent.mkdir()
    shutil.move(original, archived)
    before = tree_file_bytes(archived)

    module.refresh_readme(root, allow_marker_bootstrap=True)
    entries = [entry for entry in module.collect_readme_entries(root)
               if entry.logical_reference == "work-item:legacy-no-closed"]

    assert len(entries) == 1
    assert entries[0].classification == "WI-LEGACY-READ-COMPAT"
    assert entries[0].link == archived / "closure.md"
    assert module.resolve_category(root, "work-item:legacy-no-closed") == archived.resolve()
    assert module.audit(root) == ()
    assert tree_file_bytes(archived) == before


def test_archive_nonmonth_owned_status_is_not_hidden(
    tmp_path: Path,
) -> None:
    module = load_module()
    for member_kind in ("empty", "malformed", "directory"):
        root = tmp_path / member_kind
        archived = root / "work-items" / "archive" / "legacy-campaign" / "owned-item"
        status = archived / "status.md"
        if member_kind == "directory":
            status.mkdir(parents=True)
        else:
            write(status, "" if member_kind == "empty" else "Lifecycle-schema: invalid\n")

        assert module._category_locations(root, module.CATEGORIES["work-item"], archived.name) == [archived]
        with pytest.raises(module.LifecycleError) as failure:
            module.collect_readme_entries(root)
        assert failure.value.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"


def test_archive_candidate_calendar_slot_requires_exact_valid_month(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    archive = root / "work-items" / "archive"
    for container in ("2026-13", "2026-00", "2026-1", "0000-10"):
        (archive / container / "unowned-child").mkdir(parents=True)
    assert module.collect_readme_entries(root) == []
    assert module._category_locations(root, module.CATEGORIES["work-item"], "unowned-child") == []
    assert module.audit_categories(root) == ()
    canonical = archive / "2026-10" / "unowned-child"
    canonical.mkdir(parents=True)
    assert module._category_locations(root, module.CATEGORIES["work-item"], "unowned-child") == [canonical]
    with pytest.raises(module.LifecycleError) as failure:
        module.collect_readme_entries(root)
    assert failure.value.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"


def test_archive_nonmonth_disposition_owner_keeps_terminal_obligation(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    archived = root / "work-items" / "archive" / "legacy-campaign" / "disposition-owner"
    write(archived / module.BUG_DISPOSITIONS_MANIFEST, "{}\n")

    assert module._category_locations(root, module.CATEGORIES["work-item"], archived.name) == [archived]
    with pytest.raises(module.LifecycleError) as failure:
        module.audit_categories(root)
    assert failure.value.failure_id == "WI-IMMUTABLE-ARCHIVE"
    with pytest.raises(module.LifecycleError) as failure:
        module.collect_readme_entries(root)
    assert failure.value.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"


def test_archive_candidate_selection_keeps_genuine_duplicate_refusal(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    for container in ("2026-10", "legacy-campaign"):
        archived = root / "work-items" / "archive" / container / "duplicate-item"
        write(archived / "closure.md", "Outcome: existing legacy record.\n")

    assert len(module._category_locations(root, module.CATEGORIES["work-item"], "duplicate-item")) == 2
    for operation in (module.collect_readme_entries, module.audit_categories):
        with pytest.raises(module.LifecycleError) as failure:
            operation(root)
        assert failure.value.failure_id == "WI-CATEGORY-DUAL-LOCATION"


def test_legacy_archive_projection_is_informational_and_byte_preserving(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    before = seed_legacy_archives(root)

    module.refresh_readme(root, allow_marker_bootstrap=True)

    after = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in before
    }
    assert after == before
    entries = {
        entry.logical_reference: entry
        for entry in module.collect_readme_entries(root)
    }
    assert set(entries) == {
        "work-item:legacy-date",
        "work-item:legacy-closed-on",
        "work-item:legacy-no-closed",
        "work-item:legacy-no-status",
    }
    assert {
        entry.classification
        for entry in entries.values()
    } == {"WI-LEGACY-READ-COMPAT"}
    assert entries["work-item:legacy-date"].label == "Date-only legacy outcome."
    assert entries["work-item:legacy-closed-on"].label == "Closed-on legacy outcome."
    assert entries["work-item:legacy-no-closed"].label == "Missing-Closed legacy outcome."
    assert entries["work-item:legacy-no-status"].label == "Missing-status legacy outcome."
    readme = (root / "work-items" / "README.md").read_text(encoding="utf-8")
    assert readme.count("WI-LEGACY-READ-COMPAT") == 4
    assert "archive/2026-06/legacy-date/closure.md" in readme
    assert "archive/2026-04/legacy-closed-on/closure.md" in readme


@pytest.mark.parametrize("missing", ("status", "closure", "absent-status"))
def test_incomplete_archive_schema_is_catalogue_only(tmp_path: Path, missing: str) -> None:
    module = load_module()
    root = tmp_path / "repo"
    item = root / "work-items/archive/2037-02/unfamiliar-record"
    status = "status: completed\nupdated: 2099-01-01T00:00:00Z\n"
    closure_text = "Closed: 2099-02-01\nOutcome: Synthetic incomplete history.\n"
    if missing != "closure":
        closure_text += LIFECYCLE_SCHEMA_MARKER + "\n"
    else:
        status += LIFECYCLE_SCHEMA_MARKER + "\n"
    write(item / "closure.md", closure_text)
    if missing != "absent-status":
        write(item / "status.md", status)
    before = tree_file_bytes(item)
    entry, = module.collect_readme_entries(root)
    assert entry.section == "Archive metadata" and not entry.checked
    assert entry.classification == "WI-CATEGORY-SCHEMA-INVALID"
    assert entry.logical_reference == "work-item:unfamiliar-record"
    assert set(entry.source_paths) == {item / name for name in before}
    assert module._canonical_timestamp([entry]) == "none"
    with pytest.raises(module.LifecycleError) as strict:
        module._archived_work_item_entry(item)
    assert strict.value.failure_id == "WI-CATEGORY-SCHEMA-INVALID"
    expected_member = "closure.md" if missing == "closure" else "status.md"
    assert "input-role=strict" in str(strict.value)
    assert f"work-items/archive/2037-02/unfamiliar-record/{expected_member}" in str(strict.value)
    with pytest.raises(ValueError, match="input role"):
        module._archived_work_item_entry(item, input_role="unknown")
    assert tree_file_bytes(item) == before


def test_incomplete_schema_refresh_is_visible_byte_current_but_audit_strict(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    item = root / "work-items/archive/2037-02/historical"
    write(item / "status.md", "status: completed\nupdated: 2099-01-01T00:00:00Z\n")
    write(item / "closure.md", "Closed: 2099-02-01T00:00:00Z\n" + LIFECYCLE_SCHEMA_MARKER + "\n")
    before = {path: (path.read_bytes(), module._lifecycle_file_identity(path.lstat())) for path in item.iterdir()}
    result = run_cli("refresh", "--root", str(root))
    assert result.returncode == 0, result.stdout
    assert "INFO WI-CATEGORY-SCHEMA-INVALID:" in result.stdout
    assert "input-role=historical-catalogue" in result.stdout
    assert "work-items/archive/2037-02/historical/status.md" in result.stdout
    assert "Version 1 terminal proof unavailable" in result.stdout
    readme = root / "work-items/README.md"
    board = readme.read_bytes()
    assert b"Canonical changes through: none" in board
    section = board.decode().split("## Archive metadata\n", 1)[1]
    assert "- [x]" not in section and "- [ ]" not in section
    observed = module.observe_readme(root)
    assert observed["matches"] is True
    assert observed["archiveInventory"] == {"schemaVersion": 1, "acquisitionComplete": True,
        "classificationComplete": True, "unbound": []}
    expected = hashlib.sha256()
    for path, (data, _) in sorted(before.items()):
        logical = path.relative_to(root / "work-items").as_posix().encode()
        expected.update(len(logical).to_bytes(8, "big") + logical + len(data).to_bytes(8, "big") + data)
    assert observed["inputDigest"] == expected.hexdigest()
    module.check_readme(root)
    for operation in (module.audit_categories, module.audit):
        with pytest.raises(module.LifecycleError) as rejected:
            operation(root)
        assert rejected.value.failure_id == "WI-CATEGORY-SCHEMA-INVALID"
        assert "input-role=strict" in str(rejected.value)
    reset = run_cli("refresh", "--root", str(root), "--reset-static-guide",
        "--expected-readme-sha256", hashlib.sha256(board).hexdigest())
    assert reset.returncode == 0 and "INFO WI-CATEGORY-SCHEMA-INVALID:" in reset.stdout
    assert readme.read_bytes() == board
    assert all(path.read_bytes() == data and module._lifecycle_file_identity(path.lstat()) == identity
        for path, (data, identity) in before.items())
    (item / "status.md").write_bytes(before[item / "status.md"][0] + b"\nIndependent history bytes.\n")
    assert module.observe_readme(root)["matches"] is False
    with pytest.raises(module.LifecycleError) as stale:
        module.check_readme(root)
    assert stale.value.failure_id == "WI-README-STALE"


def test_close_with_unfamiliar_incomplete_history_preserves_rollback_and_selected_input(tmp_path: Path) -> None:
    slug = "selected-current"
    module, root, active, instant = _seed_ordinary_ledger_close(tmp_path, slug)
    historical = root / "work-items/archive/2037-02/unfamiliar-opposite"
    write(historical / "status.md", marked_status())
    write(historical / "closure.md", "Closed: 2037-02-01\nOutcome: Synthetic incomplete history.\n")
    history_before = tree_file_bytes(historical)
    module.refresh_readme(root)
    before = tree_file_bytes(root / "work-items")
    with pytest.raises(module.LifecycleError) as failed:
        module.close_item(root, slug, closure(instant).encode(), instant, inject_readme_failure=True)
    assert failed.value.failure_id == "WI-README-STALE"
    assert tree_file_bytes(root / "work-items") == before
    original_status = (active / "status.md").read_bytes()
    (active / "status.md").write_bytes(original_status + (LIFECYCLE_SCHEMA_MARKER + "\n").encode())
    with pytest.raises(module.LifecycleError) as marked_active:
        module.close_item(root, slug, closure(instant).encode(), instant)
    assert marked_active.value.failure_id == "WI-LEDGER-UNSETTLED"
    with pytest.raises(module.LifecycleError) as producer_refusal:
        module._terminalize_status((active / "status.md").read_bytes())
    assert producer_refusal.value.failure_id == "WI-CATEGORY-SCHEMA-INVALID"
    (active / "status.md").write_bytes(original_status)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    assert not active.exists() and (archived / module.BUG_DISPOSITIONS_RECEIPT).is_file()
    assert json.loads((archived / "lifecycle-transition-receipt.json").read_bytes())["schemaVersion"] == 3
    assert all((archived / name).read_bytes().count(LIFECYCLE_SCHEMA_MARKER.encode()) == 1
        for name in ("status.md", "closure.md"))
    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived
    assert tree_file_bytes(historical) == history_before
    with pytest.raises(module.LifecycleError) as selected_history:
        module.close_item(root, historical.name, closure(instant).encode(), instant)
    assert selected_history.value.failure_id == "WI-CATEGORY-SCHEMA-INVALID"
    module.check_readme(root)


def test_archive_schema_marker_matrix_fails_closed(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-08-01T00:00:00Z"
    canonical_status = marked_status()
    canonical_closure = marked_closure(instant)
    cases = {
        "unsupported-only": ("", closure(instant) + "Lifecycle-schema: unsupported\n"),
        "duplicate-status": (
            canonical_status + f"{LIFECYCLE_SCHEMA_MARKER}\n",
            canonical_closure,
        ),
        "duplicate-closure": (
            canonical_status,
            canonical_closure + f"{LIFECYCLE_SCHEMA_MARKER}\n",
        ),
        "empty-status": (
            "status: completed\nLifecycle-schema:\n",
            canonical_closure,
        ),
        "unknown-status": (
            "status: completed\nLifecycle-schema: work-items-physical-v2\n",
            canonical_closure,
        ),
        "wrong-case-status": (
            "status: completed\nLifecycle-schema: Work-Items-Physical-V1\n",
            canonical_closure,
        ),
        "wrong-case-key": (
            "status: completed\nlifecycle-schema: work-items-physical-v1\n",
            canonical_closure,
        ),
        "mismatch": (
            "status: completed\nLifecycle-schema: work-items-physical-v2\n",
            "Closed: 2026-08-01T00:00:00Z\n"
            "Outcome: mismatch\nEvidence: mismatch\nResidual risk: mismatch\n"
            "Lifecycle-schema: work-items-physical-v3\n",
        ),
    }

    for slug, (status, closure_text) in cases.items():
        root = tmp_path / slug
        item = root / "work-items" / "archive" / "2026-08" / slug
        write(item / "status.md", status)
        write(item / "closure.md", closure_text)
        for operation in (module.collect_readme_entries, lambda _root: module._archived_work_item_entry(item)):
            with pytest.raises(module.LifecycleError) as failure:
                operation(root)
            assert failure.value.failure_id == "WI-CATEGORY-SCHEMA-INVALID", slug


@pytest.mark.parametrize("kind", ("absent", "empty", "directory"))
def test_historical_status_presence_requires_acquired_file_or_true_absence(tmp_path: Path, kind: str) -> None:
    module = load_module()
    root, slug, instant = tmp_path / "repo", "selected-current", "2026-10-24T10:00:00Z"
    seed_active(module, root, slug)
    write_empty_bug_dispositions(root, slug, instant)
    item = root / "work-items/archive/2037-02/historical"
    write(item / "closure.md", marked_closure("2037-02-01T00:00:00Z"))
    status = item / "status.md"
    if kind == "directory":
        status.mkdir()
    elif kind == "empty":
        status.write_bytes(b"")
    close_file = root / "requested-closure.md"
    write(close_file, closure(instant))

    def snapshot(base):
        return {path.relative_to(base).as_posix(): (
            "directory" if path.is_dir() else "file", module._lifecycle_file_identity(path.lstat()),
            None if path.is_dir() else path.read_bytes()) for path in (base, *sorted(base.rglob("*")))}

    before, archive_before = snapshot(root), snapshot(item)
    if kind == "directory":
        with pytest.raises(module.LifecycleError) as rejected:
            module.collect_readme_entries(root)
        assert rejected.value.failure_id == "WI-CATEGORY-SCHEMA-INVALID"
        assert "work-items/archive/2037-02/historical/status.md" in str(rejected.value)
    else:
        entry = next(row for row in module.collect_readme_entries(root)
            if row.logical_reference == "work-item:historical")
        assert entry.classification == "WI-CATEGORY-SCHEMA-INVALID"
        assert (status in entry.source_paths) is (kind == "empty")
    refreshed = run_cli("refresh", "--root", str(root))
    if kind == "directory":
        assert refreshed.returncode != 0 and "WI-CATEGORY-SCHEMA-INVALID" in refreshed.stdout
        assert "INFO " not in refreshed.stdout and "README-SHA256:" not in refreshed.stdout
    else:
        assert refreshed.returncode == 0 and "INFO WI-CATEGORY-SCHEMA-INVALID:" in refreshed.stdout
        inputs = [item / "closure.md", root / "work-items/active" / slug / "status.md"]
        if kind == "empty":
            inputs.append(status)
        expected = hashlib.sha256()
        for path in sorted(inputs):
            logical = path.relative_to(root / "work-items").as_posix().encode()
            data = path.read_bytes()
            expected.update(len(logical).to_bytes(8, "big") + logical + len(data).to_bytes(8, "big") + data)
        assert module.observe_readme(root)["inputDigest"] == expected.hexdigest()
    closed = run_cli("close", "--root", str(root), "--slug", slug,
        "--closure-file", str(close_file), "--terminal-instant", instant)
    if kind == "directory":
        assert closed.returncode != 0 and "WI-CATEGORY-SCHEMA-INVALID" in closed.stdout
        assert "INFO " not in closed.stdout and "README-SHA256:" not in closed.stdout
        assert snapshot(root) == before
    else:
        assert closed.returncode == 0, closed.stdout
        assert not (root / "work-items/active" / slug).exists()
    assert snapshot(item) == archive_before


def test_archive_schema_acquisition_and_fenced_declarations_stay_strict(tmp_path: Path) -> None:
    module = load_module()
    item = tmp_path / "repo/work-items/archive/2037-02/acquired"
    write(item / "status.md", "status: completed\n```\nLifecycle-schema: unsupported\n```\n")
    write(item / "closure.md", "Outcome: Synthetic history.\n" + LIFECYCLE_SCHEMA_MARKER + "\n")
    entry, = module.collect_readme_entries(tmp_path / "repo")
    assert entry.classification == "WI-CATEGORY-SCHEMA-INVALID"
    (item / "status.md").write_bytes(b"\xff")
    with pytest.raises(module.LifecycleError) as utf8:
        module.collect_readme_entries(tmp_path / "repo")
    assert utf8.value.failure_id == "WI-CATEGORY-SCHEMA-INVALID"
    assert "work-items/archive/2037-02/acquired/status.md" in str(utf8.value)
    (item / "status.md").write_bytes(b"status: completed\n")
    (item / "closure.md").unlink()
    with pytest.raises(module.LifecycleError) as missing:
        module._archived_work_item_entry(item, input_role="historical-catalogue")
    assert missing.value.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"


def test_v1_archive_pair_preserves_strict_evidence_status_and_month(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-01T00:00:00Z"

    valid_root = tmp_path / "valid"
    valid_item = valid_root / "work-items" / "archive" / "2026-08" / "valid-v1"
    write(valid_item / "status.md", marked_status())
    write(valid_item / "closure.md", marked_closure(instant))
    entries = module.collect_readme_entries(valid_root)
    assert len(entries) == 1
    assert entries[0].classification is None

    cases = {
        "wrong-month": (
            "2026-07",
            marked_status(),
            marked_closure(instant),
            "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
        ),
        "date-only": (
            "2026-08",
            marked_status(),
            marked_closure("2026-08-01"),
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
        ),
        "missing-evidence": (
            "2026-08",
            marked_status(),
            marked_closure(instant, evidence="").replace("Evidence: \n", ""),
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
        ),
        "current-status": (
            "2026-08",
            marked_status("active"),
            marked_closure(instant),
            "WI-CATEGORY-CURRENT-IN-ARCHIVE",
        ),
    }
    for slug, (month, status, closure_text, failure_id) in cases.items():
        root = tmp_path / slug
        item = root / "work-items" / "archive" / month / slug
        write(item / "status.md", status)
        write(item / "closure.md", closure_text)
        try:
            module.collect_readme_entries(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == failure_id, slug
        else:
            raise AssertionError(f"invalid V1 archive pair passed: {slug}")


def test_close_readme_failure_rolls_back_canonical_and_readme(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "stale-readme"
    seed_active(module, root, slug)
    old_readme = (root / "work-items" / "README.md").read_bytes()
    instant = "2026-07-31T10:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)

    try:
        module.close_item(
            root,
            slug,
            closure(instant).encode(),
            instant,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected README failure returned success")

    archived = root / "work-items" / "archive" / "2026-07" / slug
    active = root / "work-items" / "active" / slug
    assert active.is_dir()
    assert not archived.exists()
    validator = module._validator_module()
    assert validator.validate_work_item(active) == []
    assert (root / "work-items" / "README.md").read_bytes() == old_readme
    module.check_readme(root)


def test_category_location_matrix_guard(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write(root / "work-items" / "decisions" / "choice.md", "status: proposed\n")
    current = module.resolve_category(root, "decision:choice")
    assert current.name == "choice.md"
    archived = root / "work-items" / "decisions" / "archive" / "2026-07" / "choice.md"
    archived.parent.mkdir(parents=True)
    shutil.move(str(current), str(archived))
    assert module.resolve_category(root, "decision:choice") == archived.resolve()
    write(root / "work-items" / "decisions" / "choice.md", "status: proposed\n")
    try:
        module.resolve_category(root, "decision:choice")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("dual location was selected silently")


def test_logical_link_relocation_and_legacy_inventory_guard(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "relocatable"
    seed_active(module, root, slug)
    assert module.resolve_category(root, f"work-item:{slug}").parent.name == "active"
    instant = "2026-07-31T11:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    assert module.resolve_category(root, f"work-item:{slug}") == archived.resolve()
    try:
        module.migrate_legacy(root, f"work-item:{slug}", incoming_links_inventory=None)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEGACY-LINK-UNMAPPED"
    else:
        raise AssertionError("legacy migration lacked link inventory")


def test_prewrite_failure_preserves_canonical_and_readme_bytes(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "preserved"
    seed_active(module, root, slug)
    status_before = (root / "work-items" / "active" / slug / "status.md").read_bytes()
    readme_before = (root / "work-items" / "README.md").read_bytes()
    bad_instant = "2026-07-31 12:00:00"
    try:
        module.close_item(root, slug, closure(bad_instant).encode(), bad_instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("malformed local-time instant was admitted")
    assert (root / "work-items" / "active" / slug / "status.md").read_bytes() == status_before
    assert (root / "work-items" / "README.md").read_bytes() == readme_before
    assert not (root / "work-items" / "archive").exists()

    duplicate_source = root / "duplicate.md"
    write(duplicate_source, "Task: duplicate\n")
    try:
        module.create_candidate(root, slug, duplicate_source.read_bytes())
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("duplicate slug was admitted")
    assert (root / "work-items" / "active" / slug / "status.md").read_bytes() == status_before
    assert (root / "work-items" / "README.md").read_bytes() == readme_before


def test_missing_readme_markers_fail_before_canonical_write(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    readme = root / "work-items" / "README.md"
    write(readme, "# Human guide without generated ownership markers\n")
    before = readme.read_bytes()

    try:
        module.create_candidate(root, "marker-preflight", b"Task: preserve bytes\n")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-MARKERS"
    else:
        raise AssertionError("missing README markers mutated canonical state")

    assert readme.read_bytes() == before
    assert not (root / "work-items" / "backlog" / "marker-preflight.md").exists()


def test_markerless_bootstrap_replaces_legacy_board_with_default_guide(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write(
        root / "work-items" / "active" / "freshness" / "status.md",
        quick_status("Current freshness repair.").replace(
            "Execute the current step.",
            "Reset the stale README guide.",
        ),
    )
    readme = root / "work-items" / "README.md"
    write(
        readme,
        "# Work items\n\n"
        "Snapshot commit: `964ee371`\n\n"
        "## Active work\n\n"
        "- Old pre-implementation task text.\n\n"
        "## Archived status\n\n"
        "- Clean worktree; lifecycle counts are old.\n",
    )

    module.refresh_readme(root, allow_marker_bootstrap=True)

    rendered = readme.read_text(encoding="utf-8")
    assert rendered.startswith(module._default_static_guide())
    assert rendered.count(module.README_BEGIN) == 1
    assert rendered.count(module.README_END) == 1
    assert "Snapshot commit" not in rendered
    assert "## Active work" not in rendered
    assert "## Archived status" not in rendered
    assert "Old pre-implementation task text" not in rendered
    assert "Current freshness repair." in rendered
    assert "Reset the stale README guide." in rendered


def test_valid_human_static_guide_is_preserved_by_ordinary_refresh(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write(
        root / "work-items" / "active" / "preserve-guide" / "status.md",
        quick_status("Preserve the human guide."),
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    generated = readme.read_text(encoding="utf-8")
    marker_region = generated[generated.index(module.README_BEGIN) :]
    human_guide = (
        "# Work items\n\n"
        "Read the generated board, use the lifecycle owner for updates, "
        "and open linked detail.\n\n"
    )
    write(readme, human_guide + marker_region)

    module.refresh_readme(root)

    refreshed = readme.read_text(encoding="utf-8")
    assert refreshed.startswith(human_guide)
    assert refreshed.count(module.README_BEGIN) == 1
    assert refreshed.count(module.README_END) == 1


def test_static_guide_reset_propagates_verified_inventory_on_every_success(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    archive = root / "work-items" / "archive"
    for name in ("first-collection", "second-collection"):
        write(archive / "2026-07" / name / "record.any", "Unbound narrative.\n")
        (archive / "2026-07" / name / "binary-leaf").write_bytes(b"\xff\x00")
    before = tree_file_bytes(archive)
    module.refresh_readme(root)
    readme = root / "work-items" / "README.md"
    readme.write_bytes(readme.read_bytes().replace(b"# Work items", b"# Retained old guide", 1))
    targeted = hashlib.sha256(readme.read_bytes()).hexdigest()
    inventory = module.observe_readme(root)["archiveInventory"]
    received = []
    repaired_hash = module.reset_readme_static_guide(root, targeted, archive_inventory_out=received)
    assert received == [inventory]
    for expected_hash in (targeted, repaired_hash):
        received = []
        assert module.reset_readme_static_guide(root, expected_hash, archive_inventory_out=received) == repaired_hash
        assert received == [inventory]
    public = run_cli("refresh", "--root", str(root), "--reset-static-guide",
                     "--expected-readme-sha256", repaired_hash)
    assert public.returncode == 0, public.stdout
    assert [line for line in public.stdout.splitlines() if line.startswith("INFO ")] == [
        f"INFO WI-ARCHIVE-ENTITY-UNBOUND: {row['path']}" for row in inventory["unbound"]]
    assert len(inventory["unbound"]) == 6
    assert f"README-SHA256: {repaired_hash}" in public.stdout
    assert module.observe_readme(root)["archiveInventory"]["classificationComplete"] is False
    assert tree_file_bytes(archive) == before


def test_static_guide_reset_withholds_inventory_on_idempotent_input_drift(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    leaf = root / "work-items" / "archive" / "2026-07" / "unknown" / "leaf"
    write(leaf, "Original unbound bytes.\n")
    module.refresh_readme(root)
    readme = root / "work-items" / "README.md"
    before = readme.read_bytes()
    render = module._render_readme_bytes
    calls = 0
    def render_then_drift(*args, **kwargs):
        nonlocal calls
        rendered = render(*args, **kwargs)
        calls += 1
        if calls == 1:
            leaf.write_bytes(b"Concurrent unbound bytes.\n")
        return rendered
    module._render_readme_bytes = render_then_drift
    received = []
    with pytest.raises(module.LifecycleError) as failure:
        module.reset_readme_static_guide(root, hashlib.sha256(before).hexdigest(), archive_inventory_out=received)
    assert failure.value.failure_id == "WI-README-STALE"
    assert received == [] and readme.read_bytes() == before
    assert leaf.read_bytes() == b"Concurrent unbound bytes.\n"


def test_explicit_static_guide_reset_adopts_retained_legacy_board(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "adopt-legacy" / "status.md"
    write(status, quick_status("Current legacy adoption task."))
    status_before = status.read_bytes()
    readme = root / "work-items" / "README.md"
    legacy_bytes = (
        b"# Work items\r\n\r\n"
        b"Snapshot commit: `964ee371`\r\n\r\n"
        b"## Active work\r\n\r\n"
        b"- Old lifecycle counts and clean worktree claim.\r\n"
    )
    readme.write_bytes(legacy_bytes)
    retained = status.parent / "data" / "legacy-readme.md"
    retained.parent.mkdir()
    retained.write_bytes(readme.read_bytes())
    legacy_hash = hashlib.sha256(legacy_bytes).hexdigest()
    assert retained.read_bytes() == legacy_bytes
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == legacy_hash

    ordinary = run_cli("refresh", "--root", str(root))
    assert ordinary.returncode == 1
    assert "WI-README-MARKERS" in ordinary.stdout
    assert readme.read_bytes() == legacy_bytes
    assert retained.read_bytes() == legacy_bytes
    assert status.read_bytes() == status_before

    repaired = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        legacy_hash,
    )

    assert repaired.returncode == 0, repaired.stdout
    repaired_bytes = readme.read_bytes()
    rendered = repaired_bytes.decode("utf-8")
    begin = "<!-- BEGIN GENERATED WORK-ITEMS STATUS -->"
    end = "<!-- END GENERATED WORK-ITEMS STATUS -->"
    assert rendered.startswith(
        "# Work items\n\nRead this page for current delivery status."
    )
    assert rendered.count(begin) == 1
    assert rendered.count(end) == 1
    assert rendered.index(begin) < rendered.index(end)
    assert "Read-model: work-items-readme-v1" in rendered
    assert "Current legacy adoption task." in rendered
    assert "Snapshot commit" not in rendered
    assert "## Active work" not in rendered
    assert "Old lifecycle counts" not in rendered
    repaired_hash = hashlib.sha256(repaired_bytes).hexdigest()
    assert f"README-SHA256: {repaired_hash}" in repaired.stdout
    assert status.read_bytes() == status_before
    assert retained.read_bytes() == legacy_bytes
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == legacy_hash
    assert not (root / "work-items" / "archive").exists()

    replay = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        legacy_hash,
    )
    assert replay.returncode == 0, replay.stdout
    assert readme.read_bytes() == repaired_bytes
    assert retained.read_bytes() == legacy_bytes
    assert status.read_bytes() == status_before

    readme.write_bytes(retained.read_bytes())
    assert readme.read_bytes() == legacy_bytes
    assert hashlib.sha256(readme.read_bytes()).hexdigest() == legacy_hash
    assert status.read_bytes() == status_before


def test_explicit_legacy_static_guide_reset_refuses_wrong_or_malformed_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "target-guard" / "status.md"
    write(status, quick_status("Preserve canonical task data."))
    status_before = status.read_bytes()
    readme = root / "work-items" / "README.md"
    legacy_bytes = b"# Reviewed legacy board without ownership markers\n"
    readme.write_bytes(legacy_bytes)

    for expected_hash in ("0" * 64, "not-a-digest"):
        refused = run_cli(
            "refresh",
            "--root",
            str(root),
            "--reset-static-guide",
            "--expected-readme-sha256",
            expected_hash,
        )
        assert refused.returncode == 1
        assert "WI-README-REPAIR-TARGET-MISMATCH" in refused.stdout
        assert readme.read_bytes() == legacy_bytes
        assert status.read_bytes() == status_before


def test_explicit_static_guide_reset_refuses_corrupt_marker_pairs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "marker-guard" / "status.md"
    write(status, quick_status("Preserve marker ownership."))
    status_before = status.read_bytes()
    readme = root / "work-items" / "README.md"
    begin = b"<!-- BEGIN GENERATED WORK-ITEMS STATUS -->\n"
    end = b"<!-- END GENERATED WORK-ITEMS STATUS -->\n"

    for invalid in (begin, begin + begin + end, end + begin):
        readme.write_bytes(invalid)
        refused = run_cli(
            "refresh",
            "--root",
            str(root),
            "--reset-static-guide",
            "--expected-readme-sha256",
            hashlib.sha256(invalid).hexdigest(),
        )
        assert refused.returncode == 1
        assert "WI-README-MARKERS" in refused.stdout
        assert readme.read_bytes() == invalid
        assert status.read_bytes() == status_before


def test_explicit_static_guide_reset_is_target_bound_and_idempotent(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write(
        root / "work-items" / "active" / "repair-guide" / "status.md",
        quick_status("Repair the current README.").replace(
            "Execute the current step.",
            "Run the explicit static-guide repair.",
        ),
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    generated = readme.read_text(encoding="utf-8")
    marker_region = generated[generated.index(module.README_BEGIN) :]
    stale_prefix = (
        "# Work items\n\n"
        "Snapshot commit: `964ee371`\n\n"
        "## Active work\n\n"
        "- Old lifecycle counts and clean worktree claim.\n\n"
        "## Archived status\n\n"
    )
    write(readme, stale_prefix + marker_region)
    stale_bytes = readme.read_bytes()
    stale_hash = hashlib.sha256(stale_bytes).hexdigest()

    wrong_target = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        "0" * 64,
    )
    assert wrong_target.returncode == 1
    assert "WI-README-REPAIR-TARGET-MISMATCH" in wrong_target.stdout
    assert readme.read_bytes() == stale_bytes

    invalid = stale_bytes.replace(module.README_END.encode(), b"")
    readme.write_bytes(invalid)
    invalid_result = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        hashlib.sha256(invalid).hexdigest(),
    )
    assert invalid_result.returncode == 1
    assert "WI-README-MARKERS" in invalid_result.stdout
    assert readme.read_bytes() == invalid
    readme.write_bytes(stale_bytes)

    repaired = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        stale_hash,
    )
    assert repaired.returncode == 0, repaired.stdout
    repaired_bytes = readme.read_bytes()
    repaired_text = repaired_bytes.decode("utf-8")
    assert repaired_text.startswith(module._default_static_guide())
    assert repaired_text.count(module.README_BEGIN) == 1
    assert repaired_text.count(module.README_END) == 1
    assert "Snapshot commit" not in repaired_text
    assert "## Active work" not in repaired_text
    assert "## Archived status" not in repaired_text
    assert "Repair the current README." in repaired_text
    assert "Run the explicit static-guide repair." in repaired_text

    replay = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        stale_hash,
    )
    assert replay.returncode == 0, replay.stdout
    assert readme.read_bytes() == repaired_bytes

    current = readme.read_text(encoding="utf-8")
    current_region = current[current.index(module.README_BEGIN) :]
    valid_human_guide = "# Work items\n\nKeep this reviewed human guide.\n\n"
    write(readme, valid_human_guide + current_region)
    changed_bytes = readme.read_bytes()
    refused = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        stale_hash,
    )
    assert refused.returncode == 1
    assert "WI-README-REPAIR-TARGET-MISMATCH" in refused.stdout
    assert readme.read_bytes() == changed_bytes


def test_location_status_matrix_rejects_semantic_escape(tmp_path: Path) -> None:
    module = load_module()
    terminal_root = tmp_path / "terminal-root"
    write(
        terminal_root / "work-items" / "decisions" / "terminal.md",
        "status: superseded\n",
    )
    try:
        module.audit(terminal_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-IN-CURRENT"
    else:
        raise AssertionError("terminal decision remained in current root")

    current_archive = tmp_path / "current-archive"
    write(
        current_archive
        / "work-items"
        / "decisions"
        / "archive"
        / "2026-07"
        / "current.md",
        "status: proposed\n",
    )
    try:
        module.audit(current_archive)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-CURRENT-IN-ARCHIVE"
    else:
        raise AssertionError("current decision remained in archive")


def test_depends_on_remains_bare_slug_and_bypasses_generic_resolver(tmp_path: Path) -> None:
    module = load_module()
    absent = staged_status("archived-original").replace(
        "Reopens: archived-original\n",
        "Depends-on: none\n",
    )
    module._validate_active_status_bytes(absent.encode())

    bare = staged_status("archived-original").replace(
        "Reopens: archived-original\n",
        "Depends-on: first-work-item, second-work-item\n",
    )
    module._validate_active_status_bytes(bare.encode())

    qualified = bare.replace(
        "Depends-on: first-work-item, second-work-item",
        "Depends-on: decision:first-work-item",
    )
    try:
        module._validate_active_status_bytes(qualified.encode())
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-DEPENDENCY-NON-WORK-ITEM"
    else:
        raise AssertionError("Depends-on routed through the category resolver")


def test_optional_epic_none_is_ignored_by_readme_renderer(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "no-epic" / "status.md"
    write(
        status,
        quick_status("Render without an epic.") + "\nRoadmap: none\nEpic: none\n",
    )

    module.refresh_readme(root, allow_marker_bootstrap=True)

    readme = (root / "work-items" / "README.md").read_text(encoding="utf-8")
    assert "[work item](active/no-epic/status.md)" in readme
    assert "[roadmap](" not in readme
    assert "[epic](" not in readme


def test_real_epic_reference_remains_strict_and_resolves_when_present(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "epic-member" / "status.md"

    for unresolved in ("null", "missing-slug"):
        write(
            status,
            quick_status("Render an epic member.") + f"\nEpic: {unresolved}\n",
        )
        try:
            module.collect_readme_entries(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-REFERENCE-MISSING"
        else:
            raise AssertionError(f"missing real Epic reference was accepted: {unresolved}")

    write(status, quick_status("Render an epic member.") + "\nEpic: None\n")
    try:
        module.collect_readme_entries(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-INVALID-SLUG"
    else:
        raise AssertionError("non-canonical absence spelling was accepted")

    write(root / "work-items" / "epics" / "real-epic.md", "status: active\n")
    write(status, quick_status("Render an epic member.") + "\nEpic: real-epic\n")
    entries = module.collect_readme_entries(root)

    item_entry = next(
        entry for entry in entries if entry.logical_reference == "work-item:epic-member"
    )
    assert "[epic](epics/real-epic.md)" in item_entry.detail


def test_unsettled_ledger_rejects_archive_without_mutation(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "unsettled-ledger"
    seed_active(module, root, slug)
    item = root / "work-items" / "active" / slug
    revise = {
        "schemaVersion": 2,
        "runId": "unsettled-review-run",
        "workItem": slug,
        "role": "qa-engineer",
        "executionRole": "internal",
        "status": "revise",
        "gate": "REVISE",
        "scope": ["scripts/mutate-work-item.py"],
        "artifact": "status.md",
        "evidence": [{"kind": "review", "ref": "fixture", "result": "revise"}],
        "startedAt": "2026-07-31T00:00:00Z",
        "updatedAt": "2026-07-31T00:01:00Z",
        "eventKind": "standalone",
        "findingClass": "correctness",
    }
    write(item / "agent-runs.jsonl", json.dumps(revise) + "\n")
    readme_before = (root / "work-items" / "README.md").read_bytes()
    instant = "2026-07-31T12:00:00Z"
    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEDGER-UNSETTLED"
    else:
        raise AssertionError("unsettled REVISE was archived")
    assert item.is_dir()
    assert not (item / "closure.md").exists()
    assert (root / "work-items" / "README.md").read_bytes() == readme_before


def test_reopen_creates_new_successor_and_preserves_archive(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "original-concern"
    seed_active(module, root, slug)
    instant = "2026-07-31T13:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    archive_hash = hashlib.sha256((archived / "closure.md").read_bytes()).hexdigest()
    successor = module.reopen_item(
        root, slug, "successor-concern", staged_status(slug).encode()
    )
    assert successor == root / "work-items" / "active" / "successor-concern"
    assert archived.is_dir()
    assert hashlib.sha256((archived / "closure.md").read_bytes()).hexdigest() == archive_hash
    assert module.resolve_category(root, f"work-item:{slug}") == archived.resolve()


def test_index_is_compatibility_only_and_cannot_change_render(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "trial"
    first, second = module.run_trial(root, FIXTURE)
    assert first == second
    readme = root / "work-items" / "README.md"
    before = readme.read_bytes()
    write(root / "work-items" / "index.md", "# Fabricated lifecycle truth\n")
    assert module.refresh_readme(root) == first
    assert readme.read_bytes() == before


def test_decision_promotion_supersedes_proposed_guard(tmp_path: Path) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(
        tmp_path, names=("physical-lifecycle-v1",), status="proposed"
    )
    module.admit_current_decision_v0(root, **request)
    decision = root / "work-items" / "decisions" / "2026-08-01-physical-lifecycle-v1.md"
    reference = f"decision:{decision.stem}"
    before = decision.read_bytes()
    inventory = root / "incoming.json"
    write(
        inventory,
        json.dumps({
            "reference": reference,
            "expectedSourceSha256": hashlib.sha256(before).hexdigest().upper(),
            "archivedAt": "2026-08-18T00:00:00Z",
            "rationale": "Synthetic nonterminal promotion probe.",
            "evidence": "The proposed decision must remain current and byte-identical.",
            "incomingLinks": [],
        }),
    )
    try:
        module.migrate_legacy(
            root,
            reference,
            incoming_links_inventory=inventory,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("a non-terminal proposed decision was promoted")
    assert decision.read_bytes() == before
    assert module.resolve_category(root, reference) == decision.resolve()


def _terminal_record(
    category: str,
    instant: str,
    *,
    status_override: str | None = None,
) -> str:
    status = status_override or {
        "bug": "fixed",
        "decision": "dropped",
        "lesson": "archived",
        "roadmap": "archived",
        "epic": "closed",
    }[category]
    utc_field = "Closed" if category == "epic" else "Terminal-at"
    detail_field = {
        "bug": "Resolution",
        "decision": "Rationale",
        "lesson": "Disposition",
        "roadmap": "Disposition",
        "epic": "Outcome",
    }[category]
    return (
        f"status: {status}\n"
        f"{utc_field}: {instant}\n"
        f"{detail_field}: accepted terminal evidence\n"
        "Evidence: focused lifecycle test\n"
    )


def _terminal_decision_record(
    slug: str,
    instant: str,
    *,
    status: str = "dropped",
) -> str:
    return (
        f"- id: {slug}\n"
        f"- status: {status}\n"
        f"- date: {slug[:10]}\n"
        "- decided-by: lifecycle test\n"
        "- context: terminal-lifecycle-test\n"
        "- supersedes: none\n"
        "- superseded-by: none\n"
        "\n"
        f"# Decision: {slug}\n\n"
        "Historical decision body.\n"
        f"Terminal-at: {instant}\n"
        "Rationale: accepted terminal evidence\n"
        "Evidence: focused lifecycle test\n"
    )


def _current_decision_record(
    slug: str,
    *,
    status: str = "proposed",
    body: str = "Synthetic decision.\n",
) -> str:
    date = slug[:10]
    return (
        f"- id: {slug}\n"
        f"- status: {status}\n"
        f"- date: {date}\n"
        "- decided-by: lifecycle test\n"
        "- context: lifecycle-test\n"
        "- supersedes: none\n"
        "- superseded-by: none\n"
        "\n"
        f"# Decision: {slug}\n\n"
        f"{body}"
    )


def test_category_migration_admission_table_has_six_complete_rows(tmp_path: Path) -> None:
    module = load_module()
    rows = module.CATEGORY_ADMISSION_TABLE
    assert len(rows) == 6
    assert {row.category for row in rows} == set(module.CATEGORIES)
    for row in rows:
        assert all(
            (
                row.category,
                row.current_reader,
                row.terminal_validator,
                row.utc_field_owner,
                row.negative_fixture,
            )
        )
        assert module._admission_for(row.category) == row


def test_category_migration_missing_admission_cell_fails_closed(tmp_path: Path) -> None:
    module = load_module()
    decision = next(
        row for row in module.CATEGORY_ADMISSION_TABLE if row.category == "decision"
    )
    module.CATEGORY_ADMISSION_TABLE = tuple(
        replace(row, negative_fixture="")
        if row.category == "decision"
        else row
        for row in module.CATEGORY_ADMISSION_TABLE
    )
    assert decision.negative_fixture
    try:
        module._admission_for("decision")
    except module.LifecycleError as exc:
        assert exc.failure_id == "CATEGORY-MIGRATION-ADMISSION-GATE"
    else:
        raise AssertionError("an incomplete admission row was accepted")


def test_flat_categories_archive_replay_and_reopen_successor(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    instant = "2026-08-01T00:00:00Z"
    current_status = {
        "bug": "open",
        "decision": "proposed",
        "lesson": "open",
        "roadmap": "draft",
        "epic": "active",
    }
    for category_name in ("bug", "decision", "lesson", "roadmap", "epic"):
        category = module.CATEGORIES[category_name]
        slug = (
            f"2026-08-01-{category_name}-original"
            if category_name == "decision"
            else f"{category_name}-original"
        )
        reference = f"{category_name}:{slug}"
        source = (
            root
            / "work-items"
            / category.current_root
            / f"{slug}.md"
        )
        terminal = (
            _terminal_decision_record(slug, instant)
            if category_name == "decision"
            else _terminal_record(category_name, instant)
        ).encode()
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(terminal)
        inventory = root / f"{category_name}-incoming.json"
        write(inventory, json.dumps({"reference": reference, "incomingLinks": []}))

        archived = module.migrate_legacy(
            root, reference, incoming_links_inventory=inventory
        )
        archived_hash = hashlib.sha256(archived.read_bytes()).hexdigest()
        original_tz = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "Pacific/Honolulu"
            replayed = module.migrate_legacy(
                root, reference, incoming_links_inventory=inventory
            )
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
        assert replayed == archived
        assert archived.parent.name == "2026-08"
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == archived_hash

        successor_slug = (
            "2026-08-01-decision-successor"
            if category_name == "decision"
            else f"{category_name}-successor"
        )
        successor_data = (
            _current_decision_record(
                successor_slug,
                status=current_status[category_name],
                body=f"Reopens: {slug}\n",
            ).encode()
            if category_name == "decision"
            else (
                f"status: {current_status[category_name]}\n"
                f"Reopens: {slug}\n"
            ).encode()
        )
        successor = module.reopen_category_record(
            root, reference, successor_slug, successor_data
        )
        assert successor.read_bytes() == successor_data
        assert archived.read_bytes() == terminal
        assert module.resolve_category(root, reference) == archived.resolve()
    module.audit(root)


def test_decision_v1_terminal_migration_preflights_schema_before_effects(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-01T00:00:00Z"
    cases = (
        (
            "wrong-id",
            "WI-DECISION-IDENTITY-MISMATCH",
            lambda text, slug: text.replace(
                f"- id: {slug}\n", "- id: 2026-08-01-other\n"
            ),
        ),
        (
            "wrong-date",
            "WI-DECISION-IDENTITY-MISMATCH",
            lambda text, _slug: text.replace("- date: 2026-08-01\n", "- date: 2026-08-02\n"),
        ),
        (
            "missing-required-field",
            "WI-DECISION-SCHEMA-INVALID",
            lambda text, _slug: text.replace(
                "- context: terminal-lifecycle-test\n", ""
            ),
        ),
        (
            "mixed-case-duplicate",
            "WI-DECISION-FIELD-DUPLICATE",
            lambda text, slug: text.replace(
                f"- id: {slug}\n", f"- id: {slug}\n- ID: {slug}\n"
            ),
        ),
        (
            "duplicate-terminal-evidence",
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            lambda text, _slug: text + "- terminal-at: 2026-08-02T00:00:00Z\n",
        ),
    )
    for name, expected_failure, mutate in cases:
        root = tmp_path / name
        slug = f"2026-08-01-preflight-{name}"
        reference = f"decision:{slug}"
        work_items = root / "work-items"
        source = work_items / "decisions" / f"{slug}.md"
        original = _terminal_decision_record(slug, instant)
        source_bytes = mutate(original, slug).encode("utf-8")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(source_bytes)
        readme = work_items / "README.md"
        readme_bytes = b"# Human-owned lifecycle notes\n\nPreserve these bytes.\n"
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_bytes(readme_bytes)
        consumer = work_items / "lessons" / "consumer.md"
        consumer_bytes = (
            f"# Consumer\n\n[decision](../decisions/{slug}.md)\n"
        ).encode("utf-8")
        consumer.parent.mkdir(parents=True, exist_ok=True)
        consumer.write_bytes(consumer_bytes)
        inventory = root / "incoming.json"
        write(inventory, json.dumps({"reference": reference, "incomingLinks": []}))

        planned = module.build_migration_inventory(root)
        planned_row = next(
            row for row in planned["rows"] if row["reference"] == reference
        )
        assert planned_row["admission"]["result"] == "denied", name
        assert planned_row["admission"]["failureId"] == expected_failure, name

        with pytest.raises(module.LifecycleError) as caught:
            module.migrate_legacy(
                root,
                reference,
                incoming_links_inventory=inventory,
            )

        assert caught.value.failure_id == expected_failure, name
        assert source.read_bytes() == source_bytes
        assert not (work_items / "decisions" / "archive").exists()
        assert readme.read_bytes() == readme_bytes
        assert consumer.read_bytes() == consumer_bytes


@pytest.mark.parametrize("shape", ("leading-blank", "non-list-id", "fenced-id"))
def test_selected_decision_unsupported_format_refuses_public_migration(tmp_path, shape):
    module = load_module()
    slug = f"2026-08-01-{shape}"
    text = _terminal_decision_record(slug, "2026-08-01T00:00:00Z")
    if shape == "leading-blank":
        text = "\n" + text
    elif shape == "non-list-id":
        text = text.replace("- id:", "id:", 1)
    else:
        first, rest = text.split("\n", 1)
        text = f"```text\n{first}\n```\n{rest}"
    root = tmp_path / "repo"
    source = root / "work-items/decisions" / f"{slug}.md"
    write(source, text)
    readme = root / "work-items/README.md"
    write(readme, module._default_static_guide() + module.README_BEGIN + "\n" + module.README_END + "\n")
    incoming = root / "incoming.json"
    write(incoming, json.dumps({"reference": f"decision:{slug}", "incomingLinks": []}))
    before = {p.relative_to(root / "work-items"): p.read_bytes()
              for p in (root / "work-items").rglob("*") if p.is_file()}
    row, = module.build_migration_inventory(root)["rows"]
    assert row["admission"]["failureId"] == "WI-DECISION-FORMAT-UNSUPPORTED"
    assert row["target"] is None and row["terminalInstant"] is None
    with pytest.raises(module.LifecycleError) as caught:
        module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=incoming)
    assert caught.value.failure_id == "WI-DECISION-FORMAT-UNSUPPORTED"
    assert {p.relative_to(root / "work-items"): p.read_bytes()
            for p in (root / "work-items").rglob("*") if p.is_file()} == before
    assert not (source.parent / "archive").exists()


def test_selected_decision_terminalization_preflights_all_rows_before_writing(tmp_path):
    module = load_module()
    root = tmp_path / "repo"
    sources = []
    for suffix in ("a-valid", "z-invalid"):
        slug = f"2026-08-01-{suffix}"
        source = root / "work-items/decisions" / f"{slug}.md"
        text = _current_decision_record(slug, status="dropped")
        if suffix == "z-invalid":
            text = text.replace("- context: lifecycle-test\n", "")
        write(source, text)
        sources.append(source)
    inventory = module.build_migration_inventory(root)
    # Even matching hashes and a plausible caller-supplied missing-evidence label
    # cannot stand in for current structure admission.
    for row in inventory["rows"]:
        row["admission"] = {"result": "denied", "failureId": module.V1_TERMINALIZATION_FAILURE}
    inventory_path = root / ".scratch/inventory.json"
    receipt = root / ".scratch/receipt.json"
    write(inventory_path, json.dumps(inventory))
    before = {path: path.read_bytes() for path in sources}
    with pytest.raises(module.LifecycleError) as caught:
        module.terminalize_v1_inventory(root, inventory_path,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker=module.V1_TERMINALIZATION_AUTHORIZATION,
            receipt_path=receipt)
    assert caught.value.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert all(path.read_bytes() == data for path, data in before.items())
    assert not receipt.exists()


def test_selected_decision_terminalization_appends_after_body_and_replays(tmp_path):
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-supported-append"
    source = root / "work-items/decisions" / f"{slug}.md"
    write(source, _current_decision_record(slug, status="superseded", body="Body stays exact.\n"))
    before = source.read_bytes()
    inventory_path = root / ".scratch/inventory.json"
    receipt = root / ".scratch/receipt.json"
    write(inventory_path, json.dumps(module.build_migration_inventory(root)))
    kwargs = dict(terminal_at="2026-08-01T00:00:00Z",
                  authorization_marker=module.V1_TERMINALIZATION_AUTHORIZATION,
                  receipt_path=receipt)
    with pytest.raises(module.LifecycleError) as injected:
        module.terminalize_v1_inventory(root, inventory_path, inject_failure_after=1, **kwargs)
    assert "injected terminalization failure after row 1" in str(injected.value)
    assert source.read_bytes() == before and not receipt.exists()
    assert module.terminalize_v1_inventory(root, inventory_path, **kwargs) == (1, False)
    after = source.read_bytes()
    assert after.startswith(before) and b"Terminal-at: 2026-08-01T00:00:00Z\n" in after[len(before):]
    receipt_before = receipt.read_bytes()
    assert module.terminalize_v1_inventory(root, inventory_path, **kwargs) == (1, True)
    assert source.read_bytes() == after and receipt.read_bytes() == receipt_before
    # A forged self-consistent hash cannot certify malformed still-current bytes.
    invalid = b"".join(line for line in after.splitlines(keepends=True)
                       if not line.startswith(b"- context:"))
    assert invalid != after
    source.write_bytes(invalid)
    payload = json.loads(receipt_before)
    payload["rows"][0]["afterSha256"] = hashlib.sha256(invalid).hexdigest()
    write(receipt, json.dumps(payload))
    with pytest.raises(module.LifecycleError) as caught:
        module.terminalize_v1_inventory(root, inventory_path, **kwargs)
    assert caught.value.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert source.read_bytes() == invalid


def test_selected_decision_reopen_validates_prospective_structure(tmp_path):
    module = load_module()
    root = tmp_path / "repo"
    predecessor = "2026-08-01-predecessor"
    archived = root / "work-items/decisions/archive/2026-08" / f"{predecessor}.md"
    write(archived, _terminal_decision_record(predecessor, "2026-08-01T00:00:00Z"))
    successor = "2026-08-02-successor"
    text = _current_decision_record(successor) + f"Reopens: {predecessor}\n"
    invalid = text.replace("- decided-by: lifecycle test\n", "")
    with pytest.raises(module.LifecycleError) as caught:
        module.reopen_category_record(root, f"decision:{predecessor}", successor, invalid.encode())
    assert caught.value.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert not (root / "work-items/decisions" / f"{successor}.md").exists()
    target = module.reopen_category_record(root, f"decision:{predecessor}", successor, text.encode())
    assert target.read_bytes() == text.encode()


def test_selected_decision_identity_plan_admits_target_without_waiving_other_structure(tmp_path):
    module = load_module()
    root = tmp_path / "repo"
    old, new = "2026-08-01-Identity", "2026-08-01-identity"
    source = root / "work-items/decisions" / f"{old}.md"
    write(source, _current_decision_record(old, status="accepted"))
    inventory = root / ".scratch/identity.json"
    planned = module.write_current_identity_normalization_inventory(
        root, "decision", source.relative_to(root).as_posix(), new, inventory)
    assert planned["oldIdentity"] == f"decision:{old}"
    assert planned["newIdentity"] == f"decision:{new}"
    before_inventory = inventory.read_bytes()
    invalid = _current_decision_record(old, status="accepted").replace("- date: 2026-08-01\n", "- date: 2026-08-02\n")
    write(source, invalid)
    before_source = source.read_bytes()
    with pytest.raises(module.LifecycleError) as caught:
        module.write_current_identity_normalization_inventory(
            root, "decision", source.relative_to(root).as_posix(), new, inventory)
    assert caught.value.failure_id == "WI-DECISION-IDENTITY-MISMATCH"
    assert source.read_bytes() == before_source and inventory.read_bytes() == before_inventory
    assert not module._normalization_exact_file(source.parent / f"{new}.md")


def test_every_category_terminal_status_and_missing_evidence_fixture(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-01T00:00:00Z"
    root = tmp_path / "repo"
    for category_name in ("bug", "decision", "lesson", "roadmap", "epic"):
        category = module.CATEGORIES[category_name]
        for status in sorted(category.terminal_statuses):
            base_slug = f"{category_name}-{status}"
            slug = (
                f"2026-08-01-{base_slug}"
                if category_name == "decision"
                else base_slug
            )
            reference = f"{category_name}:{slug}"
            source = (
                root
                / "work-items"
                / category.current_root
                / f"{slug}.md"
            )
            source.parent.mkdir(parents=True, exist_ok=True)
            terminal_record = (
                _terminal_decision_record(slug, instant, status=status)
                if category_name == "decision"
                else _terminal_record(
                    category_name,
                    instant,
                    status_override=status,
                )
            )
            source.write_bytes(terminal_record.encode())
            inventory = root / f"incoming-{slug}.json"
            write(
                inventory,
                json.dumps({"reference": reference, "incomingLinks": []}),
            )
            archived = module.migrate_legacy(
                root,
                reference,
                incoming_links_inventory=inventory,
            )
            assert archived.parent.name == "2026-08"

        missing = terminal_record.replace("Evidence: focused lifecycle test\n", "")
        try:
            module._validate_flat_terminal(category, missing.encode())
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
        else:
            raise AssertionError(f"{category_name} missing evidence was accepted")

    for status in sorted(module.CATEGORIES["work-item"].terminal_statuses):
        item = (
            root
            / "work-items"
            / "archive"
            / "2026-08"
            / f"work-item-{status}"
        )
        write(item / "status.md", f"status: {status}\n")
        write(item / "closure.md", closure(instant))
    module.audit_categories(root)
    try:
        module._validate_closure(
            f"Closed: {instant}\nOutcome: missing evidence\n".encode(),
            instant,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("work-item missing terminal evidence was accepted")


def test_all_categories_dual_location_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    for category_name, category in module.CATEGORIES.items():
        root = tmp_path / category_name
        slug = "duplicate"
        if category_name == "work-item":
            write(root / "work-items" / "active" / slug / "status.md", "status: active\n")
            write(
                root / "work-items" / "archive" / "2026-07" / slug / "status.md",
                "status: completed\n",
            )
        else:
            write(
                root / "work-items" / category.current_root / f"{slug}.md",
                f"status: {next(iter(category.current_statuses))}\n",
            )
            write(
                root
                / "work-items"
                / category.current_root
                / "archive"
                / "2026-07"
                / f"{slug}.md",
                f"status: {next(iter(category.terminal_statuses))}\n",
            )
        try:
            module.audit_categories(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
        else:
            raise AssertionError(f"{category_name} dual location was accepted")


def test_interrupted_category_moves_preserve_current_bytes(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-07-31T23:59:59Z"

    work_root = tmp_path / "work-item"
    seed_active(module, work_root, "interrupted-work-item")
    active = work_root / "work-items" / "active" / "interrupted-work-item"
    write(active / "closure.md", closure(instant))
    work_inventory = work_root / "incoming.json"
    work_reference = "work-item:interrupted-work-item"
    write(
        work_inventory,
        json.dumps({"reference": work_reference, "incomingLinks": []}),
    )
    status_before = (active / "status.md").read_bytes()
    readme_before = (work_root / "work-items" / "README.md").read_bytes()
    move_api = "rename" if module.os.name == "nt" else "replace"
    original_move = getattr(module.os, move_api)

    def fail_work_item_move(source, target):
        if Path(source) == active:
            raise OSError("injected directory move interruption")
        return original_move(source, target)

    setattr(module.os, move_api, fail_work_item_move)
    try:
        try:
            module.migrate_legacy(
                work_root,
                work_reference,
                incoming_links_inventory=work_inventory,
            )
        except OSError as exc:
            assert "injected directory move interruption" in str(exc)
        else:
            raise AssertionError("interrupted work-item move returned success")
    finally:
        setattr(module.os, move_api, original_move)
    assert active.is_dir()
    assert (active / "status.md").read_bytes() == status_before
    assert (work_root / "work-items" / "README.md").read_bytes() == readme_before

    for category_name in ("bug", "decision", "lesson", "roadmap", "epic"):
        category = module.CATEGORIES[category_name]
        root = tmp_path / category_name
        slug = (
            f"2026-07-31-interrupted-{category_name}"
            if category_name == "decision"
            else f"interrupted-{category_name}"
        )
        reference = f"{category_name}:{slug}"
        source = root / "work-items" / category.current_root / f"{slug}.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        terminal_record = (
            _terminal_decision_record(slug, instant)
            if category_name == "decision"
            else _terminal_record(category_name, instant)
        )
        source.write_bytes(terminal_record.encode())
        before = source.read_bytes()
        inventory = root / "incoming.json"
        write(inventory, json.dumps({"reference": reference, "incomingLinks": []}))

        def fail_flat_move(candidate, target):
            if Path(candidate) == source:
                raise OSError("injected flat move interruption")
            return original_move(candidate, target)

        setattr(module.os, move_api, fail_flat_move)
        try:
            try:
                module.migrate_legacy(
                    root,
                    reference,
                    incoming_links_inventory=inventory,
                )
            except OSError as exc:
                assert "injected flat move interruption" in str(exc)
            else:
                raise AssertionError(f"interrupted {category_name} move returned success")
        finally:
            setattr(module.os, move_api, original_move)
        assert source.read_bytes() == before


def test_all_category_location_status_negatives_are_exact(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-07-31T19:00:00Z"
    for category_name in ("bug", "decision", "lesson", "roadmap", "epic"):
        category = module.CATEGORIES[category_name]
        terminal_root = tmp_path / f"{category_name}-terminal-current"
        terminal = (
            terminal_root
            / "work-items"
            / category.current_root
            / "record.md"
        )
        write(terminal, _terminal_record(category_name, instant))
        try:
            module.audit_categories(terminal_root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-IN-CURRENT"
        else:
            raise AssertionError(f"{category_name} terminal current location was accepted")

        current_root = tmp_path / f"{category_name}-current-archive"
        current = (
            current_root
            / "work-items"
            / category.current_root
            / "archive"
            / "2026-07"
            / "record.md"
        )
        write(current, f"status: {next(iter(category.current_statuses))}\n")
        try:
            module.audit_categories(current_root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-CURRENT-IN-ARCHIVE"
        else:
            raise AssertionError(f"{category_name} current archive location was accepted")


def test_work_item_archive_status_is_terminal_and_active_terminal_fails(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "terminalized-work-item"
    seed_active(module, root, slug)
    instant = "2026-07-31T20:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    status = module._parse_fields((archived / "status.md").read_text(encoding="utf-8"))
    assert status["status"] == "completed"
    module.audit_categories(root)

    active = root / "work-items" / "active" / "invalid-terminal"
    write(active / "status.md", "status: completed\n")
    try:
        module.audit_categories(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-IN-CURRENT"
    else:
        raise AssertionError("terminal work-item remained active")


def test_inventory_cli_exact_three_command_contract(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "bugs" / "terminal-bug.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        _terminal_record(
            "bug",
            "2026-08-01T00:00:00Z",
            status_override="fixed",
        ).encode()
    )
    write(
        work_items / "decisions" / "consumer.md",
        "status: proposed\nRelated: bug:terminal-bug\n",
    )
    write(
        work_items / "README.md",
        "# Legacy work-items guide\n\nHuman-owned migration context.\n",
    )
    inventory = root / ".scratch" / "work-items-lifecycle-v1" / "migration-inventory.json"

    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    assert "AUDIT: PASS" in audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == 1
    assert payload["digestAlgorithms"] == {
        "file": "sha256-file-bytes-v1",
        "directory": "sha256-tree-entries-v1",
    }
    assert len(payload["rows"]) == 1
    row = payload["rows"][0]
    assert {
        "category",
        "source",
        "target",
        "terminalInstant",
        "inputSha256",
        "digestAlgorithm",
        "incomingLinks",
        "admission",
    } <= set(row)
    assert row["category"] == "bug"
    assert row["admission"]["result"] == "admitted"
    assert row["incomingLinks"]["result"] == "logical-only"

    migrated = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert migrated.returncode == 0, migrated.stdout
    assert "MIGRATION: PASS" in migrated.stdout
    assert "readme_byte_check=PASS" in migrated.stdout
    assert "source_target_disjoint=PASS" in migrated.stdout

    verified = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--verify-migration",
        str(inventory),
    )
    assert verified.returncode == 0, verified.stdout
    assert "AUDIT: PASS" in verified.stdout
    assert "migration_rows=1" in verified.stdout
    target = work_items / Path(row["target"])
    assert not source.exists()
    assert target.is_file()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]
    readme = (work_items / "README.md").read_text(encoding="utf-8")
    assert readme.startswith(load_module()._default_static_guide())
    assert "# Legacy work-items guide" not in readme
    assert "Human-owned migration context." not in readme
    assert readme.count("<!-- BEGIN GENERATED WORK-ITEMS STATUS -->") == 1
    assert readme.count("<!-- END GENERATED WORK-ITEMS STATUS -->") == 1


def test_inventory_migration_partial_parent_creation_rolls_back_owned_directories(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "bugs" / "terminal-bug.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        _terminal_record(
            "bug",
            "2026-08-01T00:00:00Z",
            status_override="fixed",
        ).encode()
    )
    consumer = work_items / "decisions" / "consumer.md"
    write(consumer, "status: proposed\nRelated: bug:terminal-bug\n")
    readme = work_items / "README.md"
    write(readme, "# Legacy work-items guide\n\nHuman-owned migration context.\n")
    inventory = root / ".scratch" / "work-items-lifecycle-v1" / "migration-inventory.json"
    audited = run_cli("audit", "--root", str(work_items), "--output", str(inventory))
    assert audited.returncode == 0, audited.stdout
    payload = json.loads(inventory.read_bytes())
    assert len(payload["rows"]) == 1

    archive_parent = work_items / "bugs" / "archive"
    month_parent = archive_parent / "2026-08"
    target = month_parent / source.name
    source_before = source.read_bytes()
    consumer_before = consumer.read_bytes()
    readme_before = readme.read_bytes()
    inventory_before = inventory.read_bytes()
    injected = module.LifecycleError(
        "TEST-STRUCTURAL-PARENT-PUBLISH", "controlled second-parent publication refusal",
    )
    original_publish = module.LifecycleWriteTarget._publish_effect
    original_remove = module.LifecycleWriteTarget.remove_created_directory
    published_records = []
    failed_records = []
    removed_records = []

    def fail_second_parent(owner, prepared, identity):
        if prepared.directory and prepared.source is None and prepared.destination == month_parent:
            failed_records.append(owner._creations[-1])
            raise injected
        result = original_publish(owner, prepared, identity)
        if prepared.directory and prepared.source is None and prepared.destination == archive_parent:
            published_records.append(owner._creations[-1])
        return result

    def remove_actual_creator(record, transaction, *, failure_id="WI-LIFECYCLE-EFFECT"):
        removed_records.append(record)
        return original_remove(record, transaction, failure_id=failure_id)

    monkeypatch.setattr(module.LifecycleWriteTarget, "_publish_effect", fail_second_parent)
    monkeypatch.setattr(module.LifecycleWriteTarget, "remove_created_directory", remove_actual_creator)
    with pytest.raises(module.LifecycleError) as failed:
        module.apply_migration_inventory(root, inventory, render_readme=True, byte_check=True)

    assert failed.value is injected
    assert len(published_records) == len(failed_records) == 1
    assert removed_records == published_records
    aborted = failed_records[0]
    assert aborted.creator and aborted.finished and aborted.release_complete
    assert not aborted.creation_published and aborted.primary is injected
    assert aborted.phase == "disposed"
    assert not archive_parent.exists() and not month_parent.exists() and not target.exists()
    assert tuple(path.name for path in source.parent.iterdir()) == (source.name,)
    assert source.read_bytes() == source_before
    assert consumer.read_bytes() == consumer_before
    assert readme.read_bytes() == readme_before
    assert inventory.read_bytes() == inventory_before


def test_inventory_preflight_denial_moves_no_selected_record(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    for slug in ("first", "second"):
        source = work_items / "bugs" / f"{slug}.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(
            _terminal_record(
                "bug",
                "2026-07-31T23:59:59Z",
                status_override="fixed",
            ).encode()
        )
    inventory = root / "inventory.json"
    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 0, audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    payload["rows"][1]["admission"] = {
        "result": "denied",
        "failureId": "CATEGORY-MIGRATION-ADMISSION-GATE",
        "reason": "injected denial",
    }
    inventory.write_text(json.dumps(payload), encoding="utf-8")
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (work_items / "bugs").glob("*.md")
    }

    migrated = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert migrated.returncode == 1
    assert "CATEGORY-MIGRATION-ADMISSION-GATE" in migrated.stdout
    after = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (work_items / "bugs").glob("*.md")
    }
    assert after == before
    assert not (work_items / "bugs" / "archive").exists()


def test_inventory_payload_drift_is_preflighted_before_first_move(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    for slug in ("first", "second"):
        path = work_items / "bugs" / f"{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_terminal_record("bug", "2026-08-01T00:00:00Z").encode())
    inventory = root / "inventory.json"
    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 0, audited.stdout
    second = work_items / "bugs" / "second.md"
    second.write_bytes(second.read_bytes() + b"Drift: after inventory\n")
    first_hash = hashlib.sha256(
        (work_items / "bugs" / "first.md").read_bytes()
    ).hexdigest()

    migrated = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert migrated.returncode == 1
    assert "WI-CATEGORY-MIGRATION-PAYLOAD" in migrated.stdout
    assert hashlib.sha256(
        (work_items / "bugs" / "first.md").read_bytes()
    ).hexdigest() == first_hash
    assert not (work_items / "bugs" / "archive").exists()


def test_inventory_unmapped_physical_link_fails_before_move(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "bugs" / "linked.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(_terminal_record("bug", "2026-08-01T00:00:00Z").encode())
    write(
        work_items / "decisions" / "consumer.md",
        "status: proposed\n[physical](../bugs/linked.md)\n",
    )
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    inventory = root / "inventory.json"

    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 1
    assert "WI-LEGACY-LINK-UNMAPPED" in audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert payload["rows"][0]["incomingLinks"]["result"] == "unmapped"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert not (work_items / "bugs" / "archive").exists()


def test_inventory_target_self_identity_is_excluded_on_replay(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    reference = "bug:self-identifying"
    source = work_items / "bugs" / "self-identifying.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        (
            _terminal_record("bug", "2026-08-01T00:00:00Z")
            + f"- id: self-identifying\nRelated: {reference}\n"
        ).encode()
    )
    external = work_items / "decisions" / "external-consumer.md"
    write(external, f"status: proposed\nRelated: {reference}\n")
    inventory = root / ".scratch" / "migration-inventory.json"

    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
    assert row["incomingLinks"] == {
        "result": "logical-only",
        "references": [
            {
                "consumer": "decisions/external-consumer.md",
                "kind": "logical",
                "value": reference,
            }
        ],
    }

    first = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert first.returncode == 0, first.stdout
    replay = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert replay.returncode == 0, replay.stdout
    verified = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--verify-migration",
        str(inventory),
    )
    assert verified.returncode == 0, verified.stdout


def test_incoming_link_owned_path_set_does_not_hide_third_consumers(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    reference = "bug:owned-record"
    source = work_items / "bugs" / "owned-record.md"
    target = work_items / "bugs" / "archive" / "2026-08" / "owned-record.md"
    write(source, f"Related: {reference}\n")
    write(target, f"Related: {reference}\n")
    logical = work_items / "decisions" / "logical-consumer.md"
    physical = work_items / "decisions" / "physical-consumer.md"
    write(logical, f"status: proposed\nRelated: {reference}\n")
    write(physical, "status: proposed\n[record](../bugs/owned-record.md)\n")

    result = module._incoming_link_result(
        root,
        {source, target},
        reference,
    )
    assert result["result"] == "unmapped"
    assert {
        (row["consumer"], row["kind"])
        for row in result["references"]
    } == {
        ("decisions/logical-consumer.md", "logical"),
        ("decisions/physical-consumer.md", "physical"),
    }


def test_incoming_link_inventory_normalizes_fragment_and_query_for_identity(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    owned = work_items / "roadmaps" / "historical.md"
    write(owned, "status: archived\n")
    consumer = (
        work_items
        / "epics"
        / "archive"
        / "2026-07"
        / "closed-epic.md"
    )
    content = (
        "[fragment](../../../roadmaps/historical.md#section)\n"
        "[query](../../../roadmaps/historical.md?view=full)\n"
        "[external](https://example.invalid/roadmaps/historical.md#section)\n"
        "[mailto](mailto:historical@example.invalid)\n"
        "[anchor](#section)\n"
        "[root](/roadmaps/historical.md)\n"
    )
    write(consumer, content)

    parsed = list(module._markdown_local_links(content))
    assert parsed
    assert all(content[link.href_start : link.href_end] == link.href for link in parsed)

    result = module._incoming_link_result(root, {owned}, "roadmap:historical")

    assert result == {
        "result": "unmapped",
        "references": [
            {
                "consumer": "epics/archive/2026-07/closed-epic.md",
                "kind": "physical",
                "value": "../../../roadmaps/historical.md#section",
            },
            {
                "consumer": "epics/archive/2026-07/closed-epic.md",
                "kind": "physical",
                "value": "../../../roadmaps/historical.md?view=full",
            },
        ],
    }


def test_verify_migration_allows_logical_churn_but_rejects_physical_links(
    tmp_path: Path,
) -> None:
    for case in ("removed-logical", "added-logical", "added-physical"):
        root = tmp_path / case
        work_items = root / "work-items"
        reference = "bug:link-change"
        source = work_items / "bugs" / "link-change.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(
            _terminal_record("bug", "2026-08-01T00:00:00Z").encode()
        )
        consumer = work_items / "decisions" / "consumer.md"
        if case == "removed-logical":
            write(consumer, f"status: proposed\nRelated: {reference}\n")
        inventory = root / ".scratch" / "migration-inventory.json"
        audited = run_cli(
            "audit",
            "--root",
            str(work_items),
            "--output",
            str(inventory),
        )
        assert audited.returncode == 0, audited.stdout
        row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
        migrated = run_cli(*_bulk_migrate_args(work_items, inventory))
        assert migrated.returncode == 0, migrated.stdout

        if case == "removed-logical":
            write(consumer, "status: proposed\n")
        elif case == "added-logical":
            write(consumer, f"status: proposed\nRelated: {reference}\n")
        else:
            target = work_items / Path(row["target"])
            relative = os.path.relpath(target, consumer.parent).replace("\\", "/")
            write(consumer, f"status: proposed\n[record]({relative})\n")

        verified = run_cli(
            "audit",
            "--root",
            str(work_items),
            "--verify-migration",
            str(inventory),
        )
        if case == "added-physical":
            assert verified.returncode == 1, case
            assert "WI-LEGACY-LINK-UNMAPPED" in verified.stdout, case
        else:
            assert verified.returncode == 0, verified.stdout
            assert "AUDIT: PASS" in verified.stdout


def test_inventory_allows_post_inventory_implementation_artifact_logical_link(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    reference = "bug:canonical-shape"
    source = work_items / "bugs" / "canonical-shape.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        _terminal_record("bug", "2026-08-01T00:00:00Z").encode()
    )
    inventory = root / ".scratch" / "migration-inventory.json"
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
    assert row["incomingLinks"] == {"result": "clear", "references": []}

    active = work_items / "active" / "implementation-record"
    write(active / "status.md", quick_status("Record migration implementation."))
    write(
        active / "implementation-phase2.md",
        f"# Implementation evidence\n\nFailing row: `{reference}`.\n",
    )

    migrated = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert migrated.returncode == 0, migrated.stdout
    target = work_items / Path(row["target"])
    assert not source.exists()
    assert target.is_file()
    verified = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--verify-migration",
        str(inventory),
    )
    assert verified.returncode == 0, verified.stdout


def test_inventory_post_inventory_physical_link_fails_before_move(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "bugs" / "late-physical.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        _terminal_record("bug", "2026-08-01T00:00:00Z").encode()
    )
    inventory = root / ".scratch" / "migration-inventory.json"
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
    consumer = work_items / "decisions" / "late-physical-consumer.md"
    write(consumer, "status: proposed\n[record](../bugs/late-physical.md)\n")

    migrated = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert migrated.returncode == 1
    assert "WI-LEGACY-LINK-UNMAPPED" in migrated.stdout
    assert source.is_file()
    assert not (work_items / Path(row["target"])).exists()


def test_inventory_directory_digest_reused_by_post_audit(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    slug = "directory-payload"
    seed_active(module, root, slug)
    instant = "2026-08-01T00:00:00Z"
    write(work_items / "active" / slug / "closure.md", closure(instant))
    inventory = root / "inventory.json"

    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 0, audited.stdout
    row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
    assert row["digestAlgorithm"] == "sha256-tree-entries-v1"
    migrated = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert migrated.returncode == 0, migrated.stdout
    replayed = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert replayed.returncode == 0, replayed.stdout
    module.audit_categories(root)
    verified = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--verify-migration",
        str(inventory),
    )
    assert verified.returncode == 0, verified.stdout


def _admitted_bug_inventory(
    root: Path,
    slugs: tuple[str, ...],
) -> tuple[Path, dict]:
    work_items = root / "work-items"
    for slug in slugs:
        source = work_items / "bugs" / f"{slug}.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(
            _terminal_record(
                "bug",
                "2026-08-01T00:00:00Z",
                status_override="fixed",
            ).encode()
        )
    inventory = root / ".scratch" / "migration-inventory.json"
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    return inventory, json.loads(inventory.read_text(encoding="utf-8"))


def _bulk_migrate_args(work_items: Path, inventory: Path) -> tuple[str, ...]:
    return (
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )


def test_inventory_post_move_renderer_failure_exact_rerun_passes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    inventory, payload = _admitted_bug_inventory(root, ("renderer-retry",))
    row = payload["rows"][0]
    source = work_items / Path(row["source"])
    target = work_items / Path(row["target"])
    original_refresh = module.refresh_readme

    def fail_after_moves(*_args, **_kwargs):
        raise module.LifecycleError(
            "WI-README-STALE",
            "injected renderer failure after all moves",
        )

    module.refresh_readme = fail_after_moves
    try:
        try:
            module.apply_migration_inventory(
                root,
                inventory,
                render_readme=True,
                byte_check=True,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-README-STALE"
        else:
            raise AssertionError("post-move renderer failure returned success")
    finally:
        module.refresh_readme = original_refresh

    assert not source.exists()
    assert target.is_file()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]

    rerun = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert rerun.returncode == 0, rerun.stdout
    assert "MIGRATION: PASS" in rerun.stdout
    assert "migration_rows=1" in rerun.stdout
    assert not source.exists()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]


def test_inventory_all_target_replay_is_a_verified_noop(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    inventory, payload = _admitted_bug_inventory(root, ("already-settled",))
    args = _bulk_migrate_args(work_items, inventory)
    first = run_cli(*args)
    assert first.returncode == 0, first.stdout
    row = payload["rows"][0]
    target = work_items / Path(row["target"])
    target_before = target.read_bytes()
    readme_before = (work_items / "README.md").read_bytes()

    replay = run_cli(*args)
    assert replay.returncode == 0, replay.stdout
    assert "migration_rows=1" in replay.stdout
    assert target.read_bytes() == target_before
    assert (work_items / "README.md").read_bytes() == readme_before
    assert not (work_items / Path(row["source"])).exists()


def test_inventory_target_only_replay_renders_active_epic_none(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    inventory, payload = _admitted_bug_inventory(root, ("settled-with-no-epic",))
    legacy_before = seed_legacy_archives(root)
    row = payload["rows"][0]
    source = work_items / Path(row["source"])
    target = work_items / Path(row["target"])
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    write(
        work_items / "active" / "unrelated-active" / "status.md",
        quick_status("Keep rendering during replay.") + "\nEpic: none\n",
    )

    replay = run_cli(*_bulk_migrate_args(work_items, inventory))

    assert replay.returncode == 0, replay.stdout
    assert "MIGRATION: PASS" in replay.stdout
    assert not source.exists()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in legacy_before
    } == legacy_before
    readme = (work_items / "README.md").read_text(encoding="utf-8")
    assert "[work item](active/unrelated-active/status.md)" in readme
    assert "[epic](" not in readme
    assert readme.count("WI-LEGACY-READ-COMPAT") == 4


def test_inventory_mixed_source_and_target_rows_resume_only_sources(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    inventory, payload = _admitted_bug_inventory(
        root,
        ("pending-row", "settled-row"),
    )
    rows = {row["reference"]: row for row in payload["rows"]}
    settled = rows["bug:settled-row"]
    settled_source = work_items / Path(settled["source"])
    settled_target = work_items / Path(settled["target"])
    settled_target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(settled_source, settled_target)
    settled_before = settled_target.read_bytes()

    resumed = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert resumed.returncode == 0, resumed.stdout
    assert "migration_rows=2" in resumed.stdout
    for row in payload["rows"]:
        source = work_items / Path(row["source"])
        target = work_items / Path(row["target"])
        assert not source.exists()
        assert target.is_file()
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]
    assert settled_target.read_bytes() == settled_before


def test_inventory_resume_negatives_fail_before_any_new_move(
    tmp_path: Path,
) -> None:
    for case in (
        "both",
        "neither",
        "target-hash-drift",
        "wrong-target",
        "category-mismatch",
    ):
        root = tmp_path / case
        work_items = root / "work-items"
        inventory, payload = _admitted_bug_inventory(
            root,
            ("first-pending", "second-invalid"),
        )
        first = next(
            row for row in payload["rows"] if row["reference"] == "bug:first-pending"
        )
        invalid = next(
            row for row in payload["rows"] if row["reference"] == "bug:second-invalid"
        )
        first_source = work_items / Path(first["source"])
        first_target = work_items / Path(first["target"])
        invalid_source = work_items / Path(invalid["source"])
        invalid_target = work_items / Path(invalid["target"])
        observed_invalid_target: Path | None = None

        if case == "both":
            invalid_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(invalid_source, invalid_target)
            observed_invalid_target = invalid_target
        elif case == "neither":
            invalid_source.unlink()
        elif case == "target-hash-drift":
            invalid_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(invalid_source, invalid_target)
            invalid_target.write_bytes(invalid_target.read_bytes() + b"drift\n")
            observed_invalid_target = invalid_target
        elif case == "wrong-target":
            wrong_target = (
                work_items
                / "bugs"
                / "archive"
                / "2026-07"
                / invalid_source.name
            )
            wrong_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(invalid_source, wrong_target)
            observed_invalid_target = wrong_target
        else:
            invalid["category"] = "decision"
            inventory.write_text(json.dumps(payload), encoding="utf-8")

        result = run_cli(*_bulk_migrate_args(work_items, inventory))
        assert result.returncode == 1, case
        assert first_source.is_file(), case
        assert not first_target.exists(), case
        if observed_invalid_target is not None:
            assert observed_invalid_target.exists(), case


def _pre_v1_terminal_record(status: str, title: str) -> bytes:
    return (
        f"---\nstatus: {status}\n---\n\n# {title}\n\n"
        "Preserved pre-V1 terminal content.\n"
    ).encode()


def _denied_terminalization_inventory(
    work_items: Path,
    inventory: Path,
) -> dict:
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 1, audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert payload["rows"]
    assert {
        row["admission"]["failureId"]
        for row in payload["rows"]
    } == {"WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"}
    return payload


def test_v1_terminalization_mixed_records_exact_evidence_and_replay(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    bug = work_items / "bugs" / "historic-bug.md"
    decision = work_items / "decisions" / "2026-08-01-historic-decision.md"
    bug.parent.mkdir(parents=True, exist_ok=True)
    decision.parent.mkdir(parents=True, exist_ok=True)
    original = {
        bug: _pre_v1_terminal_record("fixed", "Historic bug"),
        decision: _current_decision_record(decision.stem, status="dropped").encode(),
    }
    for path, data in original.items():
        path.write_bytes(data)
    original_hashes = {
        path: hashlib.sha256(data).hexdigest() for path, data in original.items()
    }
    inventory = root / ".scratch" / "terminalization-inventory.json"
    receipt = root / ".scratch" / "terminalization-receipt.json"
    payload = _denied_terminalization_inventory(work_items, inventory)
    assert len(payload["rows"]) == 2

    args = (
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T00:00:00Z",
        "--authorization-marker",
        "operator-authorized-v1-terminalization",
        "--receipt",
        str(receipt),
    )
    applied = run_cli(*args)
    assert applied.returncode == 0, applied.stdout
    assert (
        "TERMINALIZE-V1: PASS rows=2 "
        "marker=operator-authorized-v1-terminalization"
    ) in applied.stdout

    expected_details = {
        bug: (
            "Resolution: Pre-V1 terminal status `fixed` is preserved during "
            "operator-authorized V1 physical migration."
        ),
        decision: (
            "Rationale: Pre-V1 terminal status `dropped` is preserved during "
            "operator-authorized V1 physical migration."
        ),
    }
    first_bytes: dict[Path, bytes] = {}
    for path, before in original.items():
        after = path.read_bytes()
        first_bytes[path] = after
        assert after.startswith(before)
        text = after.decode()
        assert text.count("Terminal-at: 2026-08-01T00:00:00Z") == 1
        assert text.count(expected_details[path]) == 1
        assert text.splitlines().count(
            "Evidence: Historical terminal time is unknown; preserved pre-V1 "
            f"input SHA-256 `{original_hashes[path]}`; original terminal status "
            f"`{'fixed' if path == bug else 'dropped'}`; explicit "
            "operator-authorized V1 migration."
        ) == 1

    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert receipt_payload["owner"] == "work-items-lifecycle-v1-terminalization"
    assert receipt_payload["rowCount"] == 2
    assert receipt_payload["terminalAt"] == "2026-08-01T00:00:00Z"
    assert receipt_payload["authorizationMarker"] == (
        "operator-authorized-v1-terminalization"
    )
    receipt_before = receipt.read_bytes()

    replay = run_cli(*args)
    assert replay.returncode == 0, replay.stdout
    assert "TERMINALIZE-V1: PASS rows=2 replay=true" in replay.stdout
    assert receipt.read_bytes() == receipt_before
    for path, expected in first_bytes.items():
        assert path.read_bytes() == expected

    refreshed = root / ".scratch" / "post-terminalization-inventory.json"
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(refreshed),
    )
    assert audited.returncode == 0, audited.stdout
    refreshed_payload = json.loads(refreshed.read_text(encoding="utf-8"))
    assert len(refreshed_payload["rows"]) == 2
    assert {
        row["admission"]["result"] for row in refreshed_payload["rows"]
    } == {"admitted"}
    assert {
        row["terminalInstant"] for row in refreshed_payload["rows"]
    } == {"2026-08-01T00:00:00Z"}
    assert all("/archive/2026-08/" in row["target"] for row in refreshed_payload["rows"])


def test_v1_terminalization_rejects_invalid_authority_and_utc_without_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "bugs" / "historic.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(_pre_v1_terminal_record("fixed", "Historic"))
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    _denied_terminalization_inventory(work_items, inventory)
    before = source.read_bytes()

    invalid_utc = run_cli(
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T03:00:00+03:00",
        "--authorization-marker",
        "operator-authorized-v1-terminalization",
        "--receipt",
        str(receipt),
    )
    assert invalid_utc.returncode == 1
    assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in invalid_utc.stdout
    assert source.read_bytes() == before
    assert not receipt.exists()

    invalid_authority = run_cli(
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T00:00:00Z",
        "--authorization-marker",
        "operator-approved",
        "--receipt",
        str(receipt),
    )
    assert invalid_authority.returncode == 1
    assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in invalid_authority.stdout
    assert source.read_bytes() == before
    assert not receipt.exists()


def test_v1_terminalization_preflights_all_rows_before_first_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    sources = [
        work_items / "bugs" / "first.md",
        work_items / "decisions" / "second.md",
    ]
    for path, status in zip(sources, ("fixed", "dropped")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_pre_v1_terminal_record(status, path.stem))
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    payload = _denied_terminalization_inventory(work_items, inventory)
    payload["rows"][1]["admission"]["failureId"] = "INJECTED-WRONG-DENIAL"
    inventory.write_text(json.dumps(payload), encoding="utf-8")
    before = {path: path.read_bytes() for path in sources}

    result = run_cli(
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T00:00:00Z",
        "--authorization-marker",
        "operator-authorized-v1-terminalization",
        "--receipt",
        str(receipt),
    )
    assert result.returncode == 1
    assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in result.stdout
    assert {path: path.read_bytes() for path in sources} == before
    assert not receipt.exists()


def test_v1_terminalization_rejects_hash_drift_unsupported_category_and_conflict(
    tmp_path: Path,
) -> None:
    for case in ("hash-drift", "unsupported-category", "conflicting-field"):
        root = tmp_path / case
        work_items = root / "work-items"
        source = work_items / "bugs" / "historic.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        if case == "conflicting-field":
            source.write_bytes(
                _pre_v1_terminal_record("fixed", "Historic")
                + b"\nTerminal-at: 2025-01-01T00:00:00Z\n"
            )
        else:
            source.write_bytes(_pre_v1_terminal_record("fixed", "Historic"))
        inventory = root / ".scratch" / "inventory.json"
        receipt = root / ".scratch" / "receipt.json"
        payload = _denied_terminalization_inventory(work_items, inventory)
        if case == "hash-drift":
            source.write_bytes(source.read_bytes() + b"\nDrift: after audit\n")
        elif case == "unsupported-category":
            payload["rows"][0]["category"] = "lesson"
            inventory.write_text(json.dumps(payload), encoding="utf-8")
        before = source.read_bytes()

        result = run_cli(
            "terminalize-v1",
            "--root",
            str(work_items),
            "--inventory",
            str(inventory),
            "--terminal-at",
            "2026-08-01T00:00:00Z",
            "--authorization-marker",
            "operator-authorized-v1-terminalization",
            "--receipt",
            str(receipt),
        )
        assert result.returncode == 1
        assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in result.stdout
        assert source.read_bytes() == before
        assert not receipt.exists()


def test_v1_terminalization_rejects_degenerate_authoritative_field_occurrences(
    tmp_path: Path,
) -> None:
    cases = {
        "terminal-at-empty": b"Terminal-at:\n",
        "terminal-at-duplicate": (
            b"Terminal-at: 2025-01-01T00:00:00Z\n"
            b"Terminal-at: 2025-01-02T00:00:00Z\n"
        ),
        "terminal-at-last-empty": (
            b"Terminal-at: 2025-01-01T00:00:00Z\n"
            b"Terminal-at:\n"
        ),
        "migration-evidence-empty": b"V1-Migration-Evidence:\n",
        "migration-evidence-duplicate": (
            b"V1-Migration-Evidence: first proof\n"
            b"V1-Migration-Evidence: second proof\n"
        ),
        "migration-evidence-last-empty": (
            b"V1-Migration-Evidence: first proof\n"
            b"V1-Migration-Evidence:\n"
        ),
    }
    for case, conflicting_fields in cases.items():
        root = tmp_path / case
        work_items = root / "work-items"
        sources = [
            work_items / "bugs" / "first.md",
            work_items / "decisions" / "2026-08-01-second.md",
        ]
        sources[0].parent.mkdir(parents=True, exist_ok=True)
        sources[1].parent.mkdir(parents=True, exist_ok=True)
        sources[0].write_bytes(_pre_v1_terminal_record("fixed", "first"))
        sources[1].write_bytes(
            _current_decision_record(sources[1].stem, status="dropped").encode()
            + b"\n"
            + conflicting_fields
        )
        inventory = root / ".scratch" / "inventory.json"
        receipt = root / ".scratch" / "receipt.json"
        payload = _denied_terminalization_inventory(work_items, inventory)
        assert len(payload["rows"]) == 2
        before = {path: path.read_bytes() for path in sources}

        result = run_cli(
            "terminalize-v1",
            "--root",
            str(work_items),
            "--inventory",
            str(inventory),
            "--terminal-at",
            "2026-08-01T00:00:00Z",
            "--authorization-marker",
            "operator-authorized-v1-terminalization",
            "--receipt",
            str(receipt),
        )

        assert result.returncode == 1, case
        assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in result.stdout, case
        assert {path: path.read_bytes() for path in sources} == before, case
        assert not receipt.exists(), case


def test_v1_terminalization_preserves_existing_detail_and_evidence_fields(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    bug = work_items / "bugs" / "historic-bug.md"
    decision = work_items / "decisions" / "2026-08-01-historic-decision.md"
    bug.parent.mkdir(parents=True, exist_ok=True)
    decision.parent.mkdir(parents=True, exist_ok=True)
    originals = {
        bug: (
            _pre_v1_terminal_record("fixed", "Historic bug")
            + b"\nResolution: Historical issue was corrected.\n"
        ),
        decision: (
            _current_decision_record(decision.stem, status="dropped").encode()
            + b"\nEvidence: Historical decision record.\n"
        ),
    }
    for path, data in originals.items():
        path.write_bytes(data)
    hashes = {
        path: hashlib.sha256(data).hexdigest() for path, data in originals.items()
    }
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    _denied_terminalization_inventory(work_items, inventory)

    result = run_cli(
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T00:00:00Z",
        "--authorization-marker",
        "operator-authorized-v1-terminalization",
        "--receipt",
        str(receipt),
    )
    assert result.returncode == 0, result.stdout
    for path, before in originals.items():
        after = path.read_bytes()
        assert after.startswith(before)
        text = after.decode()
        status = "fixed" if path == bug else "dropped"
        assert text.count("Terminal-at: 2026-08-01T00:00:00Z") == 1
        assert text.count(
            "V1-Migration-Evidence: Historical terminal time is unknown; "
            f"preserved pre-V1 input SHA-256 `{hashes[path]}`; original terminal "
            f"status `{status}`; explicit operator-authorized V1 migration."
        ) == 1
    bug_text = bug.read_text(encoding="utf-8")
    assert bug_text.count("Resolution: Historical issue was corrected.") == 1
    assert bug_text.count("\nResolution:") == 1
    assert bug_text.count("\nEvidence:") == 1
    decision_text = decision.read_text(encoding="utf-8")
    assert decision_text.count("Evidence: Historical decision record.") == 1
    assert decision_text.count("\nEvidence:") == 1
    assert decision_text.count("\nRationale:") == 1


def test_v1_terminalization_mid_batch_failure_rolls_back_every_byte(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    sources = [
        work_items / "bugs" / "first.md",
        work_items / "decisions" / "2026-08-01-second.md",
    ]
    for path, status in zip(sources, ("fixed", "dropped")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_current_decision_record(path.stem, status=status).encode()
                         if path.parent.name == "decisions" else _pre_v1_terminal_record(status, path.stem))
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    _denied_terminalization_inventory(work_items, inventory)
    before = {path: path.read_bytes() for path in sources}

    try:
        module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
            inject_failure_after=1,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("injected mid-batch failure was not surfaced")
    assert {path: path.read_bytes() for path in sources} == before
    assert not receipt.exists()


def _seed_legacy_backlog(
    root: Path, slug: str, files: dict[str, bytes]
) -> tuple[Path, dict[str, bytes]]:
    source = root / "work-items" / "backlog" / slug
    for relative, data in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return source, {relative: data for relative, data in files.items()}


def test_convert_legacy_candidate_preserves_sources_hashes_and_readme(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-admitted"
    sources = {
        "brief.md": b"# Accepted brief\n\nEpic: none\nDepends-on: none\n",
        "roadmap.md": b"# Accepted roadmap\n\nPriority: medium\n",
    }
    source, before = _seed_legacy_backlog(root, slug, sources)
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate = (
        "status: candidate\n"
        "Task: Fix the current Python completion-oracle owner.\n"
        "Next action: Reverify current scope before delivery.\n"
        "Epic: none\n"
        "Depends-on: none\n"
    ).encode()

    target = module.convert_legacy_candidate(root, slug, candidate)

    assert target == root / "work-items" / "backlog" / f"{slug}.md"
    assert target.is_file() and not source.exists()
    converted = target.read_bytes()
    assert converted.startswith(candidate)
    for relative, data in before.items():
        assert data in converted
        assert f"### `{relative}`".encode() in converted
        assert hashlib.sha256(data).hexdigest().encode() in converted
        assert f"Source byte length: `{len(data)}`".encode() in converted
    entries = [
        entry
        for entry in module.collect_readme_entries(root)
        if entry.logical_reference == f"work-item:{slug}"
    ]
    assert len(entries) == 1 and entries[0].section == "Next actions"
    module.audit(root)


def test_legacy_appendix_fields_are_non_authoritative_and_byte_safe(
    tmp_path: Path,
) -> None:
    module = load_module()
    exact_legacy = (
        b"# Accepted roadmap\n\n"
        b"- status: **ADMITTED to backlog**, not started\n"
        b"Task: legacy wording must remain evidence only\n"
    )
    candidate = (
        b"status: candidate\n"
        b"Task: Fix the current Python completion-oracle owner.\n"
        b"Next action: Reverify current scope before delivery.\n"
        b"Epic: none\n"
        b"Depends-on: none\n"
    )

    root = tmp_path / "success"
    slug = "completion-oracle-reachability"
    source, before = _seed_legacy_backlog(root, slug, {"roadmap.md": exact_legacy})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    target = module.convert_legacy_candidate(root, slug, candidate)

    converted = target.read_bytes()
    assert not source.exists()
    assert exact_legacy in converted
    assert hashlib.sha256(exact_legacy).hexdigest().encode() in converted
    assert module._parse_fields(converted.decode("utf-8"))["status"] == "candidate"
    entries = [
        entry
        for entry in module.collect_readme_entries(root)
        if entry.logical_reference == f"work-item:{slug}"
    ]
    assert len(entries) == 1 and entries[0].section == "Next actions"
    assert (root / "work-items" / "README.md").read_bytes() == module.render_readme_bytes(root)

    rollback_root = tmp_path / "rollback"
    rollback_source, rollback_before = _seed_legacy_backlog(
        rollback_root, slug, {"roadmap.md": exact_legacy}
    )
    module.refresh_readme(rollback_root, allow_marker_bootstrap=True)
    readme_before = (rollback_root / "work-items" / "README.md").read_bytes()
    try:
        module.convert_legacy_candidate(
            rollback_root,
            slug,
            candidate,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected legacy conversion failure returned success")
    assert rollback_source.is_dir()
    assert (rollback_source / "roadmap.md").read_bytes() == rollback_before["roadmap.md"]
    assert not (rollback_root / "work-items" / "backlog" / f"{slug}.md").exists()
    assert (rollback_root / "work-items" / "README.md").read_bytes() == readme_before


def test_field_parser_respects_fenced_markdown_boundary_and_fails_closed(
    tmp_path: Path,
) -> None:
    del tmp_path
    module = load_module()
    text = (
        "status: candidate\n"
        "Task: authoritative task\n"
        "```markdown\n"
        "status: fixed\n"
        "Task: preserved evidence\n"
        "```\n"
        "~~~text\n"
        "status: dropped\n"
        "~~~~\n"
        "Next action: deliver\n"
    )
    assert module._parse_fields(text) == {
        "status": "candidate",
        "task": "authoritative task",
        "next action": "deliver",
    }

    for malformed in (
        "status: candidate\n```markdown\nstatus: fixed\n",
        "status: candidate\n~~~text\nstatus: dropped\n````\n",
    ):
        try:
            module._parse_fields(malformed)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-MARKDOWN-INVALID"
        else:
            raise AssertionError("unterminated fenced record was accepted")


def _assert_invalid_legacy_candidate_header(
    tmp_path: Path,
    case: str,
    candidate: bytes,
) -> None:
    module = load_module()
    root = tmp_path / case
    slug = f"legacy-header-{case}"
    source, before = _seed_legacy_backlog(
        root,
        slug,
        {
            "brief.md": b"# Accepted brief\n\nPreserve exact bytes.\n",
            "roadmap.md": (
                b"# Accepted roadmap\n\n"
                b"- status: **ADMITTED to backlog**, not started\n"
            ),
        },
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    readme_before = readme.read_bytes()
    target = root / "work-items" / "backlog" / f"{slug}.md"

    try:
        module.convert_legacy_candidate(root, slug, candidate)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-STATUS-INVALID", case
    else:
        raise AssertionError(f"{case} canonical candidate header was accepted")

    assert source.is_dir() and not target.exists(), case
    assert {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    } == before, case
    assert readme.read_bytes() == readme_before, case
    assert not list(target.parent.glob(f".{slug}.legacy-candidate.*")), case


def test_convert_legacy_candidate_rejects_missing_canonical_status_before_write(
    tmp_path: Path,
) -> None:
    _assert_invalid_legacy_candidate_header(
        tmp_path,
        "missing-status",
        b"Task: Candidate without status.\nNext action: Reject before mutation.\n",
    )


def test_convert_legacy_candidate_rejects_duplicate_canonical_status_before_write(
    tmp_path: Path,
) -> None:
    cases = {
        "duplicate-status": (
            b"status: candidate\n"
            b"status: candidate\n"
            b"Task: Duplicate status must fail closed.\n"
            b"Next action: Reject before mutation.\n"
        ),
        "conflicting-status": (
            b"status: candidate\n"
            b"status: fixed\n"
            b"Task: Conflicting status must fail closed.\n"
            b"Next action: Reject before mutation.\n"
        ),
        "post-fence-status": (
            b"status: candidate\n"
            b"Task: Lifecycle field after evidence must fail closed.\n"
            b"```markdown\n"
            b"status: preserved evidence\n"
            b"```\n"
            b"status: fixed\n"
        ),
    }
    for case, candidate in cases.items():
        _assert_invalid_legacy_candidate_header(tmp_path, case, candidate)


def test_convert_legacy_candidate_rejects_malformed_canonical_status_before_write(
    tmp_path: Path,
) -> None:
    _assert_invalid_legacy_candidate_header(
        tmp_path,
        "malformed-status",
        (
            b"status candidate\n"
            b"Task: Malformed status must fail closed.\n"
            b"Next action: Reject before mutation.\n"
        ),
    )
    _assert_invalid_legacy_candidate_header(
        tmp_path,
        "valid-plus-malformed-status",
        (
            b"status: candidate\n"
            b"status candidate\n"
            b"Task: Additional malformed status must fail closed.\n"
            b"Next action: Reject before mutation.\n"
        ),
    )


def test_convert_legacy_candidate_accepts_one_real_canonical_header(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "valid-real-header"
    slug = "completion-oracle-reachability"
    exact_legacy = (
        b"# Accepted roadmap\n\n"
        b"- status: **ADMITTED to backlog**, not started\n"
    )
    source, _before = _seed_legacy_backlog(
        root,
        slug,
        {"roadmap.md": exact_legacy},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate = (
        b"---\n"
        b"status: candidate\n"
        b"created: 2026-07-31\n"
        b"source: legacy-backlog-conversion\n"
        b"---\n\n"
        b"# Completion-oracle reachability\n\n"
        b"Task: Correct the current completion-oracle owner.\n"
        b"Next action: Reverify admitted scope.\n"
    )

    target = module.convert_legacy_candidate(root, slug, candidate)

    converted = target.read_bytes()
    assert not source.exists() and converted.startswith(candidate)
    assert exact_legacy in converted
    assert hashlib.sha256(exact_legacy).hexdigest().encode() in converted
    assert module._parse_fields(converted.decode("utf-8"))["status"] == "candidate"
    module.audit(root)


def test_convert_legacy_candidate_does_not_add_non_status_header_policy(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "unrelated-body-content"
    slug = "legacy-unrelated-body-content"
    source, _before = _seed_legacy_backlog(
        root,
        slug,
        {"brief.md": b"# Preserved evidence\n"},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate = (
        b"status: candidate\n"
        b"Task: First retained task value.\n"
        b"Task: Second retained task value.\n"
        b"Next action: Verify the admitted status contract.\n\n"
        b"# Notes\n\n"
        b"status candidate is ordinary body text without field syntax.\n"
    )

    target = module.convert_legacy_candidate(root, slug, candidate)

    assert not source.exists() and target.read_bytes().startswith(candidate)
    assert module._parse_fields(target.read_text(encoding="utf-8"))["status"] == "candidate"
    module.audit(root)


def test_convert_legacy_candidate_accepts_safe_dotted_slug_and_keeps_header_gate(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-07-19-model-ranking-aa-coding-index-v1.1"
    candidate = (
        b"status: candidate\n"
        b"Task: Re-rank the admitted model index.\n"
        b"Next action: Verify the dotted canonical identity.\n"
    )

    root = tmp_path / "valid-dotted"
    source, before = _seed_legacy_backlog(
        root,
        slug,
        {"brief.md": b"- id: 2026-07-19-model-ranking-aa-coding-index-v1.1\n"},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    target = module.convert_legacy_candidate(root, slug, candidate)

    assert target.name == f"{slug}.md" and not source.exists()
    assert before["brief.md"] in target.read_bytes()
    assert module.resolve_category(root, f"work-item:{slug}") == target.resolve()
    module.audit(root)

    invalid_header_root = tmp_path / "dotted-invalid-header"
    invalid_source, invalid_before = _seed_legacy_backlog(
        invalid_header_root,
        slug,
        {"brief.md": before["brief.md"]},
    )
    module.refresh_readme(invalid_header_root, allow_marker_bootstrap=True)
    readme_before = (invalid_header_root / "work-items" / "README.md").read_bytes()
    try:
        module.convert_legacy_candidate(
            invalid_header_root,
            slug,
            b"Task: Missing canonical status.\nNext action: Reject before mutation.\n",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-STATUS-INVALID"
    else:
        raise AssertionError("dotted slug bypassed the canonical candidate-header gate")
    assert invalid_source.is_dir()
    assert (invalid_source / "brief.md").read_bytes() == invalid_before["brief.md"]
    assert not (invalid_source.parent / f"{slug}.md").exists()
    assert (invalid_header_root / "work-items" / "README.md").read_bytes() == readme_before


def test_invalid_dotted_slug_grammar_fails_before_conversion_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    candidate = (
        b"status: candidate\n"
        b"Task: Reject unsafe identity.\n"
        b"Next action: Preserve source and README.\n"
    )
    invalid_slugs = (
        ".leading",
        "trailing.",
        "double..dot",
        "../traversal",
        "path/segment",
        r"path\segment",
        "Uppercase",
        "under_score",
        "unsafe space",
        "unsafe@char",
    )
    for index, slug in enumerate(invalid_slugs):
        root = tmp_path / f"invalid-{index}"
        sentinel_slug = f"preserved-source-{index}"
        source, _before = _seed_legacy_backlog(
            root,
            sentinel_slug,
            {"brief.md": f"preserve {slug}\n".encode()},
        )
        module.refresh_readme(root, allow_marker_bootstrap=True)
        work_items = root / "work-items"
        state_before = {
            path.relative_to(work_items).as_posix(): path.read_bytes()
            for path in work_items.rglob("*")
            if path.is_file()
        }
        try:
            module.convert_legacy_candidate(root, slug, candidate)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-INVALID-SLUG", slug
        else:
            raise AssertionError(f"unsafe dotted slug was accepted: {slug!r}")
        assert source.is_dir(), slug
        assert {
            path.relative_to(work_items).as_posix(): path.read_bytes()
            for path in work_items.rglob("*")
            if path.is_file()
        } == state_before, slug
        assert not list(source.parent.glob(f".{sentinel_slug}.legacy-candidate.*")), slug


def test_public_slug_predicate_is_the_mutation_grammar_owner(tmp_path: Path) -> None:
    del tmp_path
    module = load_module()
    for slug in (
        "a",
        "legacy-valid-",
        "2026-07-19-model-ranking-aa-coding-index-v1.1",
        "safe.dot-segment",
    ):
        assert module.is_valid_slug(slug), slug
        module._validate_slug(slug)
    for slug in (
        "",
        ".leading",
        "trailing.",
        "double..dot",
        "Uppercase",
        "under_score",
        "path/segment",
        r"path\segment",
        "../traversal",
        "unsafe@char",
    ):
        assert not module.is_valid_slug(slug), slug
        try:
            module._validate_slug(slug)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-INVALID-SLUG", slug
        else:
            raise AssertionError(f"mutation validator diverged from public predicate: {slug!r}")


def test_audit_rejects_noncanonical_physical_slug(tmp_path: Path) -> None:
    module = load_module()
    invalid_slug = "2026-06-19-arch-layering-runtime-laws-D"
    cases = {
        "backlog": lambda root: write(
            root / "work-items" / "backlog" / f"{invalid_slug}.md",
            "Status: candidate\nTask: invalid\nNext action: reject\n",
        ),
        "active": lambda root: write(
            root / "work-items" / "active" / invalid_slug / "status.md",
            quick_status(),
        ),
        "work-item-archive": lambda root: write(
            root / "work-items" / "archive" / "2026-07" / invalid_slug / "closure.md",
            "Closed: 2026-07-31\n",
        ),
        "flat-current": lambda root: write(
            root / "work-items" / "decisions" / f"{invalid_slug}.md",
            "status: accepted\n",
        ),
        "flat-archive": lambda root: write(
            root
            / "work-items"
            / "decisions"
            / "archive"
            / "2026-07"
            / f"{invalid_slug}.md",
            "status: dropped\nTerminal-at: 2026-07-31T00:00:00Z\nRationale: done\n",
        ),
    }
    for case, seed in cases.items():
        root = tmp_path / case
        seed(root)
        try:
            module.audit_categories(root)
        except module.LifecycleError as exc:
            expected = (
                "WI-INVALID-SLUG"
                if case in {"backlog", "active", "flat-current"}
                else "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
            )
            assert exc.failure_id == expected, case
        else:
            raise AssertionError(f"audit accepted a noncanonical {case} slug")

    valid_root = tmp_path / "valid-neighbor"
    valid_slug = "2026-08-11-valid-neighbor"
    write(
        valid_root / "work-items" / "decisions" / f"{valid_slug}.md",
        _current_decision_record(valid_slug),
    )
    module.audit_categories(valid_root)


def test_audit_accepts_only_canonical_top_level_roots_and_root_files(tmp_path: Path) -> None:
    module = load_module()
    work_items = tmp_path / "work-items"
    canonical_roots = {"backlog", "active", "archive"}
    canonical_roots.update(
        category.current_root
        for category in module.CATEGORIES.values()
        if category.current_kind == "flat"
    )
    for name in canonical_roots:
        (work_items / name).mkdir(parents=True)
    write(work_items / "README.md", "# Generated view\n")
    write(work_items / "index.md", "# Compatibility view\n")

    assert module.audit_categories(tmp_path) == ()


def test_audit_rejects_unknown_top_level_directory(tmp_path: Path) -> None:
    module = load_module()
    (tmp_path / "work-items" / "unknown-category").mkdir(parents=True)

    try:
        module.audit_categories(tmp_path)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-UNKNOWN-ROOT"
        assert "unknown-category" in str(exc)
        assert "work-items/root-contract.json" in str(exc)
        assert "creator/data owner" in str(exc)
        assert "classify" in str(exc)
        assert "flat-json" in str(exc)
    else:
        raise AssertionError("audit accepted an unknown top-level work-items directory")


def test_no_contract_preserves_linked_repository_and_work_items_read_compatibility(
    tmp_path: Path,
) -> None:
    module = load_module()
    repository = tmp_path / "repository"
    (repository / "work-items").mkdir(parents=True)
    repository_link = tmp_path / "repository-link"
    work_items_link_repository = tmp_path / "work-items-link-repository"
    work_items_target = tmp_path / "work-items-target"
    work_items_target.mkdir()
    try:
        os.symlink(repository, repository_link, target_is_directory=True)
        work_items_link_repository.mkdir()
        os.symlink(
            work_items_target,
            work_items_link_repository / "work-items",
            target_is_directory=True,
        )
    except OSError as exc:
        if os.name == "nt":
            import pytest

            pytest.skip(f"symlink creation unavailable: {exc}")
        raise

    assert module._work_items_root(repository_link) == repository / "work-items"
    assert module._work_items_root(work_items_link_repository).resolve() == work_items_target


def test_no_contract_alias_observation_keeps_repository_and_mutation_authority_separate(
    tmp_path: Path,
) -> None:
    module = load_module()
    repository = tmp_path / "repository"
    write(repository / "work-items" / "sentinel", "Preserved observation bytes.\n")
    alias = tmp_path / "repository-alias"
    namespace_repository = tmp_path / "namespace-repository"
    namespace_repository.mkdir()
    namespace_target = tmp_path / "external" / "namespace-target"
    namespace_target.mkdir(parents=True)
    alias.symlink_to(repository, target_is_directory=True)
    (namespace_repository / "work-items").symlink_to(namespace_target, target_is_directory=True)
    before = tree_file_bytes(tmp_path)
    entries = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    topology = module._resolve_project_topology(alias)
    assert topology.repository_root == repository
    linked_namespace = module._resolve_project_topology(namespace_repository)
    assert linked_namespace.repository_root == namespace_repository
    assert linked_namespace.work_items == namespace_repository / "work-items"
    assert linked_namespace.work_items.resolve() == namespace_target
    assert not topology.root_contract_present and not linked_namespace.auxiliary_roots
    with pytest.raises(module.LifecycleError):
        module._resolve_project_root_identity(alias)
    with pytest.raises(module.LifecycleError):
        module._work_items_root(alias, input_role="repository-root")
    for bound in ({"input_role": "repository-root"}, {"selected_reference": ("work-item", "target")},
                  {"binding_evidence_out": []}):
        with pytest.raises(module.LifecycleError, match="incompatible project topology observation context"):
            module._resolve_project_root_identity(alias, acquisition_purpose="topology-observation", **bound)
    with pytest.raises(module.LifecycleError, match="unknown project root acquisition purpose"):
        module._resolve_project_root_identity(repository, acquisition_purpose="unknown")
    with pytest.raises(module.LifecycleError) as mutation:
        module.create_candidate(alias, "target", b"Task: Refused original alias.\nNext action: Check.\nupdated: 2026-08-11T10:00:00Z\n")
    assert mutation.value.failure_id == "WI-LIFECYCLE-LOCK-IDENTITY"
    assert tree_file_bytes(tmp_path) == before
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == entries
    def held(_root):
        with pytest.raises(module.LifecycleError):
            module._work_items_root(alias)
        with pytest.raises(module.LifecycleError, match="incompatible project topology observation context"):
            module._resolve_project_root_identity(repository, acquisition_purpose="topology-observation")
    module._lifecycle_participant(held, input_role="repository-root")(repository)
    assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None


def test_topology_observation_preserves_contract_presence_and_read_failure(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    repository = tmp_path / "repository"
    write_root_contract(repository, {})
    alias = tmp_path / "repository-alias"
    alias.symlink_to(repository, target_is_directory=True)
    namespace_repository = tmp_path / "namespace-repository"
    namespace_repository.mkdir()
    (namespace_repository / "work-items").symlink_to(repository / "work-items", target_is_directory=True)
    for root in (alias, namespace_repository):
        with pytest.raises(module.LifecycleError):
            module._resolve_project_topology(root)
    contract = repository / "work-items" / "root-contract.json"
    contract.write_bytes(b"{\n")
    with pytest.raises(module.LifecycleError) as malformed:
        module._resolve_project_topology(repository)
    assert malformed.value.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
    original_lstat = Path.lstat
    def unavailable_entry(path, *args, **kwargs):
        if path == contract:
            raise PermissionError("synthetic declaration inspection refusal")
        return original_lstat(path, *args, **kwargs)
    with monkeypatch.context() as inspection:
        inspection.setattr(Path, "lstat", unavailable_entry)
        with pytest.raises(module.LifecycleError, match="root contract entry cannot be inspected") as unavailable:
            module._resolve_project_topology(repository)
        assert isinstance(unavailable.value.__cause__, PermissionError)
    real_read = Path.read_text
    def unreadable_entry(path, *args, **kwargs):
        if path == contract:
            raise PermissionError("synthetic declaration read refusal")
        return real_read(path, *args, **kwargs)
    with monkeypatch.context() as reading:
        reading.setattr(Path, "read_text", unreadable_entry)
        with pytest.raises(module.LifecycleError, match="root contract must be valid UTF-8 JSON") as unreadable:
            module._resolve_project_topology(repository)
        assert isinstance(unreadable.value.__cause__, PermissionError)
    contract.unlink()
    contract.symlink_to(repository / "missing-contract.json")
    with pytest.raises(module.LifecycleError, match="root contract contains a link or reparse point"):
        module._resolve_project_topology(repository)


def test_contract_unknown_root_rejects_lifecycle_and_read_model_before_work_items_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write_root_contract(root, {})
    (root / "work-items" / "unknown-category").mkdir()
    candidate = b"Status: candidate\nTask: reject unknown root\nNext action: none\n"

    for operation in (
        lambda: module.create_candidate(root, "unknown-root-candidate", candidate),
        lambda: module.refresh_readme(root),
        lambda: module.audit_categories(root),
    ):
        try:
            operation()
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-UNKNOWN-ROOT"
        else:
            raise AssertionError("contracted unknown root reached a lifecycle or read-model operation")
        assert not (root / "work-items" / "backlog").exists()
        assert not (root / "work-items" / "README.md").exists()


def test_unknown_root_validation_has_one_topology_owner(tmp_path: Path) -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    audit_start = source.index("def audit_categories(")
    audit_end = source.index("\ndef audit(", audit_start)
    audit_source = source[audit_start:audit_end]

    assert source.count("def assert_known_top_level_roots(") == 1
    assert source.count('"WI-CATEGORY-UNKNOWN-ROOT"') == 1
    assert "topology.assert_known_top_level_roots()" in audit_source
    assert "work_items.iterdir()" not in audit_source


def test_root_contract_topology_is_shared_by_audit_close_reopen_and_refresh(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    declared = ("repair-receipts", "status-repair-receipts")
    write_root_contract(root, {name: {"kind": "flat-json"} for name in declared})
    for name in declared:
        write(root / "work-items" / name / "receipt.json", "{}\n")

    slug = "contract-topology"
    seed_active(module, root, slug)
    module.audit_categories(root)

    instant = "2026-09-01T00:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    module.audit(root)
    successor = module.reopen_item(
        root,
        slug,
        "contract-topology-successor",
        staged_status(slug).encode(),
    )
    module.audit(root)
    first_readme = (root / "work-items" / "README.md").read_bytes()
    module.refresh_readme(root)

    assert archived == root / "work-items" / "archive" / "2026-09" / slug
    assert successor == root / "work-items" / "active" / "contract-topology-successor"
    assert (root / "work-items" / "README.md").read_bytes() == first_readme
    assert all((root / "work-items" / name / "receipt.json").is_file() for name in declared)


def test_expanded_root_contract_uses_generic_auxiliary_roots_across_lifecycle(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    declared = ("alpha-receipts", "zeta-receipts")
    contract = expanded_root_contract(declared)
    write(root / "work-items" / "root-contract.json", json.dumps(contract) + "\n")
    for name in declared:
        write(root / "work-items" / name / "receipt.json", "{}\n")

    slug = "expanded-topology"
    seed_active(module, root, slug)
    module.audit_categories(root)
    instant = "2026-09-01T00:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    successor = module.reopen_item(
        root, slug, "expanded-topology-successor", staged_status(slug).encode()
    )
    module.audit(root)
    before_refresh = (root / "work-items" / "README.md").read_bytes()
    module.refresh_readme(root)

    assert archived == root / "work-items" / "archive" / "2026-09" / slug
    assert successor == root / "work-items" / "active" / "expanded-topology-successor"
    assert (root / "work-items" / "README.md").read_bytes() == before_refresh
    assert all((root / "work-items" / name / "receipt.json").is_file() for name in declared)


def test_expanded_root_contract_accepts_pinned_reader_shape(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    contract = expanded_root_contract(("repair-receipts", "status-repair-receipts"))
    contract["rootFiles"] = [
        "README.md", "active-pipeline.md", "index.md", "root-contract.json",
        "semantic-readiness.json",
    ]
    contract["activeItemSubdirectories"] = ["constraints"]
    write(root / "work-items" / "root-contract.json", json.dumps(contract) + "\n")
    for name in ("repair-receipts", "status-repair-receipts"):
        write(root / "work-items" / name / "receipt.json", "{}\n")

    topology = module._resolve_project_topology(root)
    module.audit_categories(root)

    assert topology.auxiliary_roots == frozenset(
        {"repair-receipts", "status-repair-receipts"}
    )


def test_expanded_root_contract_rejects_invalid_envelopes_before_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    base = expanded_root_contract(("alpha-receipts", "zeta-receipts"))
    cases: dict[str, dict[str, object]] = {}

    def changed(name: str, field: str, value: object) -> None:
        contract = copy.deepcopy(base)
        contract[field] = value
        cases[name] = contract

    changed("extra-key", "unexpected", [])
    missing = copy.deepcopy(base)
    del missing["rootFiles"]
    cases["missing-key"] = missing
    changed("boolean-version", "version", True)
    changed("wrong-auxiliary-shape", "auxiliaryRoots", {"alpha-receipts": {"kind": "flat-json"}})
    changed("unknown-nested-key", "auxiliaryRoots", [{"path": "alpha-receipts", "kind": "flat-json", "other": 1}])
    changed("unhashable-kind", "auxiliaryRoots", [{"path": "alpha-receipts", "kind": []}])
    changed("unsorted-auxiliary", "auxiliaryRoots", list(reversed(base["auxiliaryRoots"])))
    changed("duplicate-auxiliary", "auxiliaryRoots", [base["auxiliaryRoots"][0]] * 2)
    changed("wrong-auxiliary-kind", "auxiliaryRoots", [{"path": "alpha-receipts", "kind": "flat-markdown"}])
    changed("duplicate-across-sections", "auxiliaryRoots", [{"path": "backlog", "kind": "flat-json"}])
    changed("renamed-active", "lifecycleRoots", [{"path": "ongoing", "kind": "active-items"}, {"path": "archive", "kind": "archived-items"}])
    changed("missing-archive", "lifecycleRoots", [{"path": "active", "kind": "active-items"}])
    changed("unsupported-registry", "registries", [{"path": "other", "kind": "flat-markdown"}])
    changed("direct-slash", "rootFiles", ["README.md", "nested/root-contract.json", "root-contract.json"])
    changed("dot-segment", "activeItemSubdirectories", ["."])
    changed("empty-segment", "historicalItemDirectoryExceptions", ["archive//item/notes"])
    changed("traversal", "historicalItemDirectoryExceptions", ["archive/2026-01/../notes"])
    changed("backslash", "archiveRootFiles", ["back\\slash"])
    changed("drive-colon", "archiveRootFiles", ["C:drive"])
    changed("rooted", "archiveRootFiles", ["/rooted"])
    changed("shallow-exception", "historicalItemDirectoryExceptions", ["archive/2026-01/item"])
    changed("root-file-collision", "rootFiles", ["ALPHA-receipts", "README.md", "root-contract.json"])

    for name, contract in cases.items():
        root = tmp_path / name
        write(root / "work-items" / "root-contract.json", json.dumps(contract) + "\n")
        try:
            module._resolve_project_topology(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", name
        else:
            raise AssertionError(f"invalid expanded contract passed: {name}")
        assert not (root / "work-items" / "README.md").exists(), name
        assert not (root / "work-items" / "active").exists(), name


def test_expanded_root_contract_reuses_auxiliary_file_and_link_guards(
    tmp_path: Path,
) -> None:
    module = load_module()
    for shape in ("file", "link"):
        root = tmp_path / shape
        contract = expanded_root_contract(("receipts",))
        write(root / "work-items" / "root-contract.json", json.dumps(contract) + "\n")
        auxiliary = root / "work-items" / "receipts"
        if shape == "file":
            write(auxiliary, "not a directory\n")
        else:
            target = tmp_path / "link-target"
            target.mkdir(exist_ok=True)
            try:
                os.symlink(target, auxiliary, target_is_directory=True)
            except OSError as exc:
                if os.name == "nt":
                    import pytest

                    pytest.skip(f"symlink creation unavailable: {exc}")
                raise
        try:
            module._resolve_project_topology(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", shape
        else:
            raise AssertionError(f"expanded contract admitted auxiliary {shape}")


def test_expanded_root_contract_rejects_nested_duplicate_json_key(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    contract = json.dumps(expanded_root_contract(("receipts",)))
    contract = contract.replace(
        '"path": "receipts", "kind": "flat-json"',
        '"path": "receipts", "kind": "flat-json", "kind": "flat-json"',
    )
    write(root / "work-items" / "root-contract.json", contract + "\n")

    try:
        module._resolve_project_topology(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
    else:
        raise AssertionError("expanded contract admitted nested duplicate JSON key")


def test_root_contract_has_one_shared_documentation_owner_and_pack_pointers(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    shared = root / "shared" / "references" / "work-items-root-contract.md"
    shared_text = shared.read_text(encoding="utf-8")
    for token in (
        "ProjectTopology",
        '"version": 2',
        "auxiliaryRoots",
        "flat-json",
        "MUST NOT be redeclared",
        "non-reparse",
        "audit, close, reopen",
        "WI-CATEGORY-ROOT-CONTRACT-INVALID",
    ):
        assert token in shared_text

    pointer = "work-items-root-contract.md"
    for relative in (
        "shared/references/README.md",
        "docs/work-item-execution-tracking.md",
        "references-codex/repository-task-memory.md",
        "references-claude/repository-task-memory.md",
    ):
        assert pointer in (root / relative).read_text(encoding="utf-8")


def test_root_contract_does_not_admit_undeclared_root(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write_root_contract(root, {"repair-receipts": {"kind": "flat-json"}})
    (root / "work-items" / "repair-receipts").mkdir()
    (root / "work-items" / "performance").mkdir()

    try:
        module.audit_categories(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-UNKNOWN-ROOT"
        assert "performance" in str(exc)
        assert "work-items/root-contract.json" in str(exc)
        assert "creator/data owner" in str(exc)
        assert "classify" in str(exc)
        assert "flat-json" in str(exc)
    else:
        raise AssertionError("contract admitted an undeclared work-items root")


def test_root_contract_rejects_lifecycle_and_read_model_root_collisions(
    tmp_path: Path,
) -> None:
    module = load_module()
    reserved_roots = (
        "active",
        "archive",
        "backlog",
        "bugs",
        "decisions",
        "epics",
        "legacy-ledger-historical-dispositions",
        "lessons",
        "roadmaps",
    )

    for name in reserved_roots:
        root = tmp_path / name
        write_root_contract(root, {name: {"kind": "flat-json"}})
        try:
            module._resolve_project_topology(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", name
            assert name in str(exc), name
        else:
            raise AssertionError(f"root contract admitted reserved root: {name}")


def test_root_contract_collision_fails_before_candidate_mutation(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write_root_contract(root, {"backlog": {"kind": "flat-json"}})

    try:
        module.create_candidate(
            root,
            "collision-must-not-mutate",
            b"Status: candidate\nTask: reject collision\nNext action: none\n",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
    else:
        raise AssertionError("candidate mutation accepted a colliding root contract")

    assert not (root / "work-items" / "backlog").exists()
    assert not (root / "work-items" / "README.md").exists()


def test_root_contract_rejects_generated_readme_alias_before_refresh_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write_root_contract(root, {"readme.md": {"kind": "flat-json"}})

    try:
        module.refresh_readme(root, allow_marker_bootstrap=True)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
        assert "generated README" in str(exc)
    else:
        raise AssertionError("root contract admitted generated README alias")

    assert not (root / "work-items" / "README.md").exists()
    assert not (root / "work-items" / "readme.md").exists()


def test_root_contract_rejects_malformed_and_unconfined_roots(tmp_path: Path) -> None:
    module = load_module()
    cases = {
        "malformed-json": "{\n",
        "wrong-schema": json.dumps(
            {"schema": "other", "version": 2, "auxiliaryRoots": {}}
        ),
        "wrong-version": json.dumps(
            {"schema": "work-items-root-contract", "version": 1, "auxiliaryRoots": {}}
        ),
        "wrong-roots-shape": json.dumps(
            {"schema": "work-items-root-contract", "version": 2, "auxiliaryRoots": []}
        ),
        "wrong-kind": json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": {"receipts": {"kind": "directory"}},
            }
        ),
        "traversal": json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": {"../escape": {"kind": "flat-json"}},
            }
        ),
        "absolute-posix": json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": {"/absolute": {"kind": "flat-json"}},
            }
        ),
        "absolute-windows": json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": {"C:\\absolute": {"kind": "flat-json"}},
            }
        ),
    }
    for name, contract in cases.items():
        root = tmp_path / name
        write(root / "work-items" / "root-contract.json", contract + "\n")
        try:
            module.audit_categories(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", name
        else:
            raise AssertionError(f"invalid root contract passed: {name}")


def test_root_contract_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    module = load_module()
    cases = {
        "schema": '{"schema":"work-items-root-contract","schema":"work-items-root-contract","version":2,"auxiliaryRoots":{}}',
        "version": '{"schema":"work-items-root-contract","version":2,"version":2,"auxiliaryRoots":{}}',
        "auxiliary-roots": '{"schema":"work-items-root-contract","version":2,"auxiliaryRoots":{},"auxiliaryRoots":{}}',
        "auxiliary-root-name": '{"schema":"work-items-root-contract","version":2,"auxiliaryRoots":{"receipts":{"kind":"flat-json"},"receipts":{"kind":"flat-json"}}}',
    }

    for name, contract in cases.items():
        root = tmp_path / name
        write(root / "work-items" / "root-contract.json", contract + "\n")
        try:
            module._resolve_project_topology(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", name
        else:
            raise AssertionError(f"duplicate JSON key passed: {name}")


def test_root_contract_rejects_linked_contract_and_repository_root(tmp_path: Path) -> None:
    module = load_module()
    target_contract = tmp_path / "contract-target.json"
    write_root_contract(tmp_path / "contract-source", {})
    shutil.copyfile(
        tmp_path / "contract-source" / "work-items" / "root-contract.json",
        target_contract,
    )
    linked_contract_root = tmp_path / "linked-contract"
    (linked_contract_root / "work-items").mkdir(parents=True)
    try:
        os.symlink(target_contract, linked_contract_root / "work-items" / "root-contract.json")
    except OSError as exc:
        if os.name == "nt":
            import pytest

            pytest.skip(f"symlink creation unavailable: {exc}")
        raise
    try:
        module.audit_categories(linked_contract_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
    else:
        raise AssertionError("linked root contract passed")

    linked_auxiliary_root = tmp_path / "linked-auxiliary"
    write_root_contract(
        linked_auxiliary_root,
        {"repair-receipts": {"kind": "flat-json"}},
    )
    auxiliary_target = tmp_path / "auxiliary-target"
    auxiliary_target.mkdir()
    os.symlink(
        auxiliary_target,
        linked_auxiliary_root / "work-items" / "repair-receipts",
        target_is_directory=True,
    )
    try:
        module.audit_categories(linked_auxiliary_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
    else:
        raise AssertionError("linked contract-declared root passed")

    repository_target = tmp_path / "repository-target"
    write_root_contract(repository_target, {})
    repository_link = tmp_path / "repository-link"
    os.symlink(repository_target, repository_link, target_is_directory=True)
    try:
        module.audit_categories(repository_link)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LIFECYCLE-LOCK-IDENTITY"
    else:
        raise AssertionError("linked repository root passed")


def test_noncanonical_archive_is_physical_read_compat_only(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-06-13-batchA1-decisions-deps"
    archived = root / "work-items" / "archive" / "2026-06" / slug
    write(archived / "closure.md", "Closed: 2026-06-13\nOutcome: delivered\n")
    write(archived / "status.md", "status: completed\n")
    assert module.audit_categories(root) == (
        f"archive/2026-06/{slug}",
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    result = run_cli("audit", "--root", str(root))
    assert result.returncode == 0, result.stdout
    assert f"WI-LEGACY-READ-COMPAT archive/2026-06/{slug}" in result.stdout
    try:
        module.resolve_category(root, f"work-item:{slug}")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-INVALID-SLUG"
    else:
        raise AssertionError("legacy archive became a logical resolver alias")


def test_noncanonical_flat_archive_requires_unique_terminal_month(tmp_path: Path) -> None:
    module = load_module()
    slug = "Legacy-Decision"
    terminal = (
        "status: reverted\n"
        "Terminal-at: 2026-06-13T00:00:00Z\n"
        "Rationale: retired\n"
        "Evidence: historical decision\n"
    )
    valid_root = tmp_path / "valid"
    valid = (
        valid_root
        / "work-items"
        / "decisions"
        / "archive"
        / "2026-06"
        / f"{slug}.md"
    )
    write(valid, terminal)
    assert module.audit_categories(valid_root) == (
        f"decisions/archive/2026-06/{slug}.md",
    )
    try:
        module.resolve_category(valid_root, f"decision:{slug}")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-INVALID-SLUG"
    else:
        raise AssertionError("noncanonical flat archive became a logical alias")

    wrong_month_root = tmp_path / "wrong-month"
    write(
        wrong_month_root
        / "work-items"
        / "decisions"
        / "archive"
        / "2026-07"
        / f"{slug}.md",
        terminal,
    )
    try:
        module.audit_categories(wrong_month_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH"
    else:
        raise AssertionError("wrong-month legacy archive was admitted")

    duplicate_root = tmp_path / "duplicate"
    for month in ("2026-06", "2026-07"):
        write(
            duplicate_root
            / "work-items"
            / "decisions"
            / "archive"
            / month
            / f"{slug}.md",
            terminal,
        )
    try:
        module.audit_categories(duplicate_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("duplicate legacy archive identity was admitted")


def _identity_normalization_fixture(root: Path):
    module = load_module()
    work_items = root / "work-items"
    old = "2026-06-19-arch-layering-runtime-laws-D-group-meta-C6"
    new = old.lower()
    source = work_items / "decisions" / f"{old}.md"
    write(source, _current_decision_record(old, status="accepted"))
    lineage = work_items / "decisions" / "2026-07-07-d1-amendment.md"
    write(
        lineage,
        _current_decision_record(
            "2026-07-07-d1-amendment",
            status="accepted",
            body=(
                f"Lineage: {old}; Related: decision:{old}\n"
                f"```text\nhistorical evidence: {old}\n```\n"
            ),
        ),
    )
    physical = work_items / "epics" / "current-link.md"
    write(
        physical,
        f"- id: current-link\n- status: active\n"
        f"[decision](../decisions/{old}.md?view=full#d1)\n",
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    inventory = root / ".scratch" / "identity-normalization.json"
    receipt = root / ".scratch" / "identity-normalization-receipt.json"
    module.write_current_identity_normalization_inventory(
        root, "decision", source.relative_to(root).as_posix(), new, inventory
    )
    return module, work_items, old, new, source, lineage, physical, inventory, receipt


def test_normalize_current_identity_success_links_and_replay(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    module, work_items, old, new, source, lineage, physical, inventory, receipt = _identity_normalization_fixture(root)
    target, replay = module.normalize_current_identity(
        root, "decision", source.relative_to(root).as_posix(), new, inventory, receipt
    )
    assert replay is False and not module._normalization_exact_file(source)
    assert module._normalization_exact_file(target)
    target_fields = module._parse_fields(target.read_text(encoding="utf-8"))
    assert target_fields["status"] == "accepted" and target_fields["id"] == new
    lineage_text = lineage.read_text(encoding="utf-8")
    assert f"Lineage: {new}; Related: decision:{new}" in lineage_text
    assert f"historical evidence: {old}" in lineage_text
    assert f"../decisions/{new}.md?view=full#d1" in physical.read_text(encoding="utf-8")
    assert module.resolve_category(root, f"decision:{new}") == target.resolve()
    module.audit(root)
    for row in json.loads(inventory.read_text(encoding="utf-8"))["rows"]:
        path = target if row["path"] == source.relative_to(work_items).as_posix() else work_items / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["afterSha256"]
    settled = {path.relative_to(work_items): path.read_bytes() for path in work_items.rglob("*") if path.is_file()}
    assert not [path for path in source.parent.iterdir() if path.is_dir() and (".normalize." in path.name or ".rollback." in path.name)]
    with patch.object(module.LifecycleWriteTarget, "make_directories", wraps=module.LifecycleWriteTarget.make_directories) as create:
        replay_target, replay = module.normalize_current_identity(
            root, "decision", source.relative_to(root).as_posix(), new, inventory, receipt
        )
        create.assert_not_called()
    assert replay is True and replay_target == target
    assert {path.relative_to(work_items): path.read_bytes() for path in work_items.rglob("*") if path.is_file()} == settled


def test_normalize_current_identity_rollback_matrix(tmp_path: Path) -> None:
    for injection in ("after-rewrites", "after-move", "after-readme"):
        root = tmp_path / injection
        module, work_items, _old, new, source, _lineage, _physical, inventory, receipt = _identity_normalization_fixture(root)
        before = {path.relative_to(work_items).as_posix(): path.read_bytes() for path in work_items.rglob("*") if path.is_file()}
        try:
            module.normalize_current_identity(
                root, "decision", source.relative_to(root).as_posix(), new,
                inventory, receipt, inject_failure_at=injection,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-IDENTITY-NORMALIZE-ROLLBACK", injection
        else:
            raise AssertionError(f"injected failure settled: {injection}")
        assert {path.relative_to(work_items).as_posix(): path.read_bytes() for path in work_items.rglob("*") if path.is_file()} == before
        assert source.is_file() and not receipt.exists()
        assert module._normalization_exact_file(source)
        assert not module._normalization_exact_file(source.parent / f"{new}.md")
        assert not [path for path in source.parent.iterdir() if path.is_dir() and (".normalize." in path.name or ".rollback." in path.name)]


@pytest.mark.parametrize("boundary", ("before-first", "before-second"))
def test_normalize_current_identity_owned_stage_prefixes(tmp_path, monkeypatch, boundary):
    root = tmp_path / "repo"
    module, work_items, _old, new, source, _lineage, _physical, inventory, receipt = _identity_normalization_fixture(root)
    before = {path.relative_to(work_items): path.read_bytes() for path in work_items.rglob("*") if path.is_file()}
    move = module.LifecycleTransaction.replace_directory
    moves = []
    def intercept(transaction, origin, destination, **kwargs):
        first = origin == source and ".normalize." in destination.parent.name
        second = ".normalize." in origin.parent.name and destination.name == f"{new}.md"
        if (boundary == "before-first" and first) or (boundary == "before-second" and second):
            if second:
                assert moves and origin.is_file() and not module._normalization_exact_file(source)
            raise module.LifecycleError("TEST-NORMALIZATION-PREFIX", boundary)
        result = move(transaction, origin, destination, **kwargs)
        moves.append((origin.name, destination.name))
        return result
    monkeypatch.setattr(module.LifecycleTransaction, "replace_directory", intercept)
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError) as failure:
        module.normalize_current_identity(root, "decision", source.relative_to(root).as_posix(), new, inventory, receipt,
                                          diagnostic_observer=observer)
    assert failure.value.failure_id == "WI-IDENTITY-NORMALIZE-ROLLBACK"
    assert boundary in str(failure.value) and observer.snapshot.rollback == "completed"
    assert {path.relative_to(work_items): path.read_bytes() for path in work_items.rglob("*") if path.is_file()} == before
    assert module._normalization_exact_file(source) and not receipt.exists()
    assert not [path for path in source.parent.iterdir() if path.is_dir() and (".normalize." in path.name or ".rollback." in path.name)]
    print(json.dumps({"probe": "native-normalization-prefix", "boundary": boundary, "actualMoves": moves,
                      "failureId": failure.value.failure_id, "rollback": observer.snapshot.rollback,
                      "exactPreimages": True, "stageResidue": False}), flush=True)


def test_normalize_current_identity_retirement_failure_retains_target_progress(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    module, work_items, _old, new, source, _lineage, _physical, inventory, receipt = _identity_normalization_fixture(root)
    before = {path.relative_to(work_items): path.read_bytes() for path in work_items.rglob("*") if path.is_file()}
    remove = module.LifecycleWriteTarget.remove_created_directory
    observed = []
    sentinel = OSError("controlled stage retirement failure after target placement")
    def intercept(cls, record, transaction, **kwargs):
        if ".normalize." in record.locator.name:
            assert not observed and record.creator and record.acquired and record.creation_published
            assert record.finished and record.release_complete
            assert module._normalization_exact_file(source.parent / f"{new}.md")
            assert not module._normalization_exact_file(source)
            observed.append(record)
            raise sentinel
        return remove(record, transaction, **kwargs)
    monkeypatch.setattr(module.LifecycleWriteTarget, "remove_created_directory", classmethod(intercept))
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError) as failure:
        module.normalize_current_identity(root, "decision", source.relative_to(root).as_posix(), new, inventory, receipt,
                                          diagnostic_observer=observer)
    assert observed and sentinel.args[0] in str(failure.value)
    assert observer.snapshot.rollback == "incomplete" and observer.snapshot.cleanupFailures
    assert {path.relative_to(work_items): path.read_bytes() for path in work_items.rglob("*") if path.is_file()} == before
    assert module._normalization_exact_file(source) and not receipt.exists()
    stage, = observed
    assert stage.locator.is_dir() and not list(stage.locator.iterdir())
    assert module._lifecycle_file_identity(stage.locator.lstat()) == stage.identity
    assert not [path for path in source.parent.iterdir() if path.is_dir() and ".rollback." in path.name]
    print(json.dumps({"probe": "native-normalization-retirement-refusal", "retainedStage": stage.locator.name,
                      "creatorIdentity": list(stage.identity), "nativeResult": stage.native_result,
                      "retirementAttempts": len(observed), "rollback": observer.snapshot.rollback,
                      "exactPreimages": True, "receiptAbsent": True}), flush=True)


@pytest.mark.parametrize("mutation", ("collision", "replacement", "foreign-member"))
def test_normalize_current_identity_stage_ownership_refusals(tmp_path, monkeypatch, mutation):
    root = tmp_path / "repo"
    module, work_items, _old, new, source, _lineage, _physical, inventory, receipt = _identity_normalization_fixture(root)
    remove = module.LifecycleWriteTarget.remove_created_directory
    observed = {}
    foreign = b"synthetic foreign stage member; preserve exact bytes"
    if mutation == "collision":
        fixed = type("FixedStageName", (), {"hex": "0123456789abcdef0123456789abcdef"})()
        monkeypatch.setattr(module.uuid, "uuid4", lambda: fixed)
        stage = source.parent / f".{new}.normalize.{fixed.hex}"
        stage.mkdir()
        member = stage / "foreign.bin"
        member.write_bytes(foreign)
        observed.update(stage=stage, member=member, identity=module._lifecycle_file_identity(member.lstat()))
    def intercept(cls, record, transaction, **kwargs):
        if ".normalize." in record.locator.name:
            assert "record" not in observed
            observed["record"] = record
            observed["stage"] = record.locator
            if mutation == "replacement":
                preserved = record.locator.with_name(record.locator.name + ".preserved")
                record.locator.rename(preserved)
                record.locator.mkdir()
                observed["preserved"] = preserved
            member = record.locator / "foreign.bin"
            member.write_bytes(foreign)
            observed.update(member=member, identity=module._lifecycle_file_identity(member.lstat()))
        return remove(record, transaction, **kwargs)
    monkeypatch.setattr(module.LifecycleWriteTarget, "remove_created_directory", classmethod(intercept))
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError):
        module.normalize_current_identity(root, "decision", source.relative_to(root).as_posix(), new, inventory, receipt,
                                          diagnostic_observer=observer)
    assert observed["member"].read_bytes() == foreign
    assert module._lifecycle_file_identity(observed["member"].lstat()) == observed["identity"]
    assert not receipt.exists()
    if mutation == "collision":
        assert "record" not in observed and module._normalization_exact_file(source)
    else:
        assert observer.snapshot.rollback == "incomplete" and observer.snapshot.cleanupFailures
        assert module._normalization_exact_file(source.parent / f"{new}.md")
    if mutation == "replacement":
        assert module._lifecycle_file_identity(observed["preserved"].lstat()) == observed["record"].identity
        assert module._lifecycle_file_identity(observed["stage"].lstat()) != observed["record"].identity
    print(json.dumps({"probe": "native-normalization-stage-ownership", "mutation": mutation,
                      "foreignIdentity": list(observed["identity"]), "foreignBytesPreserved": True,
                      "rollback": observer.snapshot.rollback, "receiptAbsent": True,
                      "retirementAttempts": int("record" in observed)}), flush=True)


def test_normalize_current_identity_inventory_collision_and_source_gates(tmp_path: Path) -> None:
    module = load_module()
    archive_root = tmp_path / "archive-source"
    archived = archive_root / "work-items" / "decisions" / "archive" / "2026-06" / "Legacy.md"
    write(archived, "status: reverted\nTerminal-at: 2026-06-01T00:00:00Z\nRationale: done\nEvidence: test\n")
    try:
        module.write_current_identity_normalization_inventory(
            archive_root, "decision", "work-items/decisions/archive/2026-06/Legacy.md", "legacy",
            archive_root / ".scratch" / "i.json",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-SOURCE"
    else:
        raise AssertionError("archive source was admitted")

    for case in ("stale-inventory", "collision", "duplicate"):
        root = tmp_path / case
        module, work_items, _old, new, source, _lineage, _physical, inventory, receipt = _identity_normalization_fixture(root)
        if case == "stale-inventory":
            payload = json.loads(inventory.read_text(encoding="utf-8"))
            payload["rows"].pop()
            inventory.write_text(json.dumps(payload), encoding="utf-8")
        elif case == "collision":
            write(
                work_items / "decisions" / "archive" / "2026-06" / f"{new}.md",
                "status: reverted\nTerminal-at: 2026-06-01T00:00:00Z\nRationale: done\nEvidence: test\n",
            )
        else:
            write(
                work_items / "decisions" / "archive" / "2026-06" / source.name,
                "status: reverted\nTerminal-at: 2026-06-01T00:00:00Z\nRationale: done\nEvidence: test\n",
            )
        before = source.read_bytes()
        try:
            module.normalize_current_identity(
                root, "decision", source.relative_to(root).as_posix(), new, inventory, receipt
            )
        except module.LifecycleError as exc:
            expected = "WI-IDENTITY-NORMALIZE-INVENTORY" if case == "stale-inventory" else "WI-CATEGORY-DUAL-LOCATION"
            assert exc.failure_id == expected, case
        else:
            raise AssertionError(f"{case} was admitted")
        assert source.read_bytes() == before and not receipt.exists()

    non_utf = tmp_path / "non-utf8"
    module, work_items, _old, new, source, *_rest = _identity_normalization_fixture(non_utf)
    bad = work_items / "bugs" / "bad.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"\xff")
    try:
        module.write_current_identity_normalization_inventory(
            non_utf, "decision", source.relative_to(non_utf).as_posix(), new,
            non_utf / ".scratch" / "identity-normalization.json",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-INVENTORY"
    else:
        raise AssertionError("non-UTF8 current record was not fail-closed")


def test_normalize_current_identity_preserves_archive_evidence_and_rejects_mixed_replay(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "archive-physical-consumer"
    work_items = root / "work-items"
    old = "2026-08-01-Legacy-Decision"
    new = "2026-08-01-legacy-decision"
    source = work_items / "decisions" / f"{old}.md"
    write(source, _current_decision_record(old, status="accepted"))
    archived_evidence = (
        work_items / "archive" / "2026-07" / "historical-record" / "evidence.md"
    )
    write(
        archived_evidence,
        f"[historical decision](../../../decisions/{old}.md#decision)\n",
    )
    tree_before = {
        path.relative_to(work_items).as_posix(): path.read_bytes()
        for path in work_items.rglob("*")
        if path.is_file()
    }
    inventory = root / ".scratch" / "identity-normalization.json"
    try:
        module.write_current_identity_normalization_inventory(
            root,
            "decision",
            source.relative_to(root).as_posix(),
            new,
            inventory,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-INVENTORY"
    else:
        raise AssertionError("immutable archive physical consumer was classified mutable")
    assert not inventory.exists()
    assert {
        path.relative_to(work_items).as_posix(): path.read_bytes()
        for path in work_items.rglob("*")
        if path.is_file()
    } == tree_before

    settled_root = tmp_path / "mixed-replay"
    (
        module,
        work_items,
        _old,
        new,
        source,
        lineage,
        _physical,
        inventory,
        receipt,
    ) = _identity_normalization_fixture(settled_root)
    target, replay = module.normalize_current_identity(
        settled_root,
        "decision",
        source.relative_to(settled_root).as_posix(),
        new,
        inventory,
        receipt,
    )
    assert replay is False and target.is_file()
    lineage.write_text(lineage.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
    try:
        module.normalize_current_identity(
            settled_root,
            "decision",
            source.relative_to(settled_root).as_posix(),
            new,
            inventory,
            receipt,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-RECOVERY"
    else:
        raise AssertionError("mixed settled replay was accepted")

    source.write_text(f"id: {_old}\nstatus: accepted\n", encoding="utf-8")
    try:
        module.normalize_current_identity(
            settled_root,
            "decision",
            source.relative_to(settled_root).as_posix(),
            new,
            inventory,
            receipt,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-RECOVERY"
    else:
        raise AssertionError("dual physical state with receipt was accepted")


def test_normalize_current_identity_replay_requires_complete_exact_receipt_rows(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    (
        module,
        work_items,
        _old,
        new,
        source,
        _lineage,
        _physical,
        inventory,
        receipt,
    ) = _identity_normalization_fixture(root)
    target, replay = module.normalize_current_identity(
        root,
        "decision",
        source.relative_to(root).as_posix(),
        new,
        inventory,
        receipt,
    )
    assert replay is False and target.is_file()
    canonical_receipt = json.loads(receipt.read_text(encoding="utf-8"))
    canonical_rows = canonical_receipt["rows"]
    assert len(canonical_rows) == 3

    variants = {
        "zero-of-three": [],
        "one-of-three": canonical_rows[:1],
        "two-of-three": canonical_rows[:2],
        "mixed": [
            canonical_rows[0],
            canonical_rows[1],
            {**canonical_rows[2], "afterPath": canonical_rows[1]["afterPath"]},
        ],
        "duplicate": [canonical_rows[0], canonical_rows[1], canonical_rows[1]],
        "tampered": [
            canonical_rows[0],
            {**canonical_rows[1], "afterSha256": "0" * 64},
            canonical_rows[2],
        ],
    }
    for name, rows in variants.items():
        candidate = json.loads(json.dumps(canonical_receipt))
        candidate["rows"] = rows
        receipt.write_text(json.dumps(candidate), encoding="utf-8")
        receipt_before = receipt.read_bytes()
        tree_before = {
            path.relative_to(work_items).as_posix(): path.read_bytes()
            for path in work_items.rglob("*")
            if path.is_file()
        }
        try:
            module.normalize_current_identity(
                root,
                "decision",
                source.relative_to(root).as_posix(),
                new,
                inventory,
                receipt,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-IDENTITY-NORMALIZE-RECOVERY", name
        else:
            raise AssertionError(f"incomplete/tampered receipt replayed: {name}")
        assert receipt.read_bytes() == receipt_before, name
        assert {
            path.relative_to(work_items).as_posix(): path.read_bytes()
            for path in work_items.rglob("*")
            if path.is_file()
        } == tree_before, name

    receipt.write_text(json.dumps(canonical_receipt), encoding="utf-8")
    replay_target, replay = module.normalize_current_identity(
        root,
        "decision",
        source.relative_to(root).as_posix(),
        new,
        inventory,
        receipt,
    )
    assert replay is True and replay_target == target


def test_normalize_current_identity_ignores_fenced_links_but_rewrites_live_links(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    old = "2026-08-01-Legacy-Decision"
    new = "2026-08-01-legacy-decision"
    source = work_items / "decisions" / f"{old}.md"
    write(source, _current_decision_record(old, status="accepted"))
    current = work_items / "epics" / "current-link.md"
    write(
        current,
        f"id: current-link\nstatus: active\n"
        f"[live](../decisions/{old}.md?view=full#d1)\n"
        f"```md\n[fenced](../decisions/{old}.md?view=old#evidence)\n```\n",
    )
    archived = (
        work_items
        / "decisions"
        / "archive"
        / "2026-07"
        / "historical-evidence.md"
    )
    write(
        archived,
        "id: historical-evidence\n"
        "status: reverted\n"
        "Terminal-at: 2026-07-01T00:00:00Z\n"
        "Rationale: historical evidence\n"
        "Evidence: fenced example\n"
        f"```md\n[historical](../../{old}.md?view=old#evidence)\n```\n",
    )
    archived_before = archived.read_bytes()
    module.refresh_readme(root, allow_marker_bootstrap=True)
    inventory = root / ".scratch" / "identity-normalization.json"
    receipt = root / ".scratch" / "identity-normalization-receipt.json"
    data = module.write_current_identity_normalization_inventory(
        root,
        "decision",
        source.relative_to(root).as_posix(),
        new,
        inventory,
    )
    rows = {row["path"]: row for row in data["rows"]}
    assert rows["epics/current-link.md"]["kinds"] == ["physical-link"]
    assert "decisions/archive/2026-07/historical-evidence.md" not in rows

    target, replay = module.normalize_current_identity(
        root,
        "decision",
        source.relative_to(root).as_posix(),
        new,
        inventory,
        receipt,
    )
    assert replay is False and target.is_file()
    current_text = current.read_text(encoding="utf-8")
    assert f"[live](../decisions/{new}.md?view=full#d1)" in current_text
    assert f"[fenced](../decisions/{old}.md?view=old#evidence)" in current_text
    assert archived.read_bytes() == archived_before


def test_normalize_current_identity_rejects_invalid_paths_targets_and_reparse(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "decisions" / "Legacy.md"
    write(source, "id: Legacy\nstatus: accepted\n")
    inventory = root / ".scratch" / "identity-normalization.json"
    before = source.read_bytes()
    cases = (
        ("decisions/Legacy.md", "legacy", "WI-IDENTITY-NORMALIZE-SOURCE"),
        ("work-items/../outside.md", "legacy", "WI-IDENTITY-NORMALIZE-SOURCE"),
        (source.relative_to(root).as_posix(), "Invalid_Target", "WI-INVALID-SLUG"),
    )
    for source_arg, target_slug, expected in cases:
        try:
            module.write_current_identity_normalization_inventory(
                root, "decision", source_arg, target_slug, inventory
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == expected
        else:
            raise AssertionError(f"invalid normalization input was admitted: {source_arg}")
        assert source.read_bytes() == before and not inventory.exists()

    link_root = tmp_path / "reparse"
    real = link_root / "real-work-items"
    write(real / "decisions" / "Legacy.md", "id: Legacy\nstatus: accepted\n")
    linked = link_root / "work-items"
    try:
        os.symlink(real, linked, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    try:
        module.write_current_identity_normalization_inventory(
            link_root,
            "decision",
            "work-items/decisions/Legacy.md",
            "legacy",
            link_root / ".scratch" / "identity-normalization.json",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-SOURCE"
    else:
        raise AssertionError("reparse-backed source was admitted")


def test_normalize_current_identity_cli_prepare_apply_and_replay(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    source = root / "work-items" / "decisions" / "2026-08-01-Legacy.md"
    write(
        source,
        _current_decision_record("2026-08-01-Legacy", status="accepted"),
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    inventory = root / ".scratch" / "identity-normalization.json"
    receipt = root / ".scratch" / "identity-normalization-receipt.json"
    common = (
        "normalize-current-identity",
        "--root",
        str(root),
        "--category",
        "decision",
        "--source",
        "work-items/decisions/2026-08-01-Legacy.md",
        "--target-slug",
        "2026-08-01-legacy",
        "--inventory",
        str(inventory),
    )
    prepared = run_cli(*common, "--prepare-only")
    assert prepared.returncode == 0, prepared.stdout
    assert "NORMALIZE-CURRENT-IDENTITY: INVENTORY" in prepared.stdout
    applied = run_cli(*common, "--receipt", str(receipt))
    assert applied.returncode == 0, applied.stdout
    assert "NORMALIZE-CURRENT-IDENTITY: PASS" in applied.stdout
    assert "replay=false" in applied.stdout
    replayed = run_cli(*common, "--receipt", str(receipt))
    assert replayed.returncode == 0, replayed.stdout
    assert "NORMALIZE-CURRENT-IDENTITY: PASS" in replayed.stdout
    assert "replay=true" in replayed.stdout


def test_convert_legacy_candidate_duplicate_and_failure_are_byte_rollback(
    tmp_path: Path,
) -> None:
    module = load_module()
    duplicate_root = tmp_path / "duplicate"
    slug = "legacy-duplicate"
    source, before = _seed_legacy_backlog(
        duplicate_root, slug, {"brief.md": b"preserve duplicate source\n"}
    )
    write(
        duplicate_root / "work-items" / "backlog" / f"{slug}.md",
        "Task: existing identity\nNext action: preserve\n",
    )
    module.refresh_readme(duplicate_root, allow_marker_bootstrap=True)
    readme_before = (duplicate_root / "work-items" / "README.md").read_bytes()
    try:
        module.convert_legacy_candidate(duplicate_root, slug, b"Task: replacement\n")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("duplicate legacy identity was converted")
    assert (source / "brief.md").read_bytes() == before["brief.md"]
    assert (duplicate_root / "work-items" / "README.md").read_bytes() == readme_before

    rollback_root = tmp_path / "rollback"
    source, before = _seed_legacy_backlog(
        rollback_root,
        slug,
        {
            "brief.md": b"preserve rollback source\n",
            "notes/design.md": b"preserve recursive rollback source\n",
        },
    )
    module.refresh_readme(rollback_root, allow_marker_bootstrap=True)
    readme_before = (rollback_root / "work-items" / "README.md").read_bytes()
    try:
        module.convert_legacy_candidate(
            rollback_root,
            slug,
            b"status: candidate\nTask: candidate\nNext action: verify\n",
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected conversion failure returned success")
    assert {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    } == before
    assert not (rollback_root / "work-items" / "backlog" / f"{slug}.md").exists()
    assert (rollback_root / "work-items" / "README.md").read_bytes() == readme_before
    assert not list((rollback_root / "work-items" / "backlog").glob(f".{slug}.legacy-candidate.*"))


def test_legacy_transitions_reject_physical_consumers_before_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "legacy-linked"
    operations = (
        (
            "convert",
            lambda root: module.convert_legacy_candidate(
                root, slug, b"Task: candidate\nNext action: verify\n"
            ),
            lambda root: root / "work-items" / "backlog" / f"{slug}.md",
        ),
        (
            "retire",
            lambda root: module.retire_legacy_backlog(
                root,
                slug,
                b"Rejected before admission.\n",
                "2026-08-01T00:00:00Z",
            ),
            lambda root: root / "work-items" / "archive" / "2026-08" / slug,
        ),
    )
    for name, transition, target_for in operations:
        root = tmp_path / name
        source, before = _seed_legacy_backlog(
            root,
            slug,
            {"brief.md": b"preserve every source byte\n", "notes/design.md": b"design bytes\n"},
        )
        consumer = root / "work-items" / "bugs" / "consumer.md"
        write(
            consumer,
            f"[legacy source](../backlog/{slug}/brief.md)\nContext: work-item:{slug}\n",
        )
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme_before = (root / "work-items" / "README.md").read_bytes()

        try:
            transition(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-LINK-UNMAPPED"
        else:
            raise AssertionError(f"{name} admitted a physical consumer")

        assert {
            path.relative_to(source).as_posix(): path.read_bytes()
            for path in source.rglob("*")
            if path.is_file()
        } == before
        assert (consumer.parent / f"../backlog/{slug}/brief.md").resolve() == source / "brief.md"
        assert (root / "work-items" / "README.md").read_bytes() == readme_before
        assert not target_for(root).exists()


def test_convert_legacy_candidate_commits_before_partial_cleanup_failure(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-commit"
    source, before = _seed_legacy_backlog(
        root,
        slug,
        {"brief.md": b"preserve brief bytes\n", "notes/design.md": b"preserve design bytes\n"},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    original_rmtree = module.shutil.rmtree
    injected = False

    def partial_cleanup(path: Path | str, *args: object, **kwargs: object) -> None:
        nonlocal injected
        candidate = Path(path)
        if candidate.name == "source" and not injected:
            injected = True
            (candidate / "brief.md").unlink()
            raise OSError("injected partial cleanup failure")
        original_rmtree(path, *args, **kwargs)

    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve complete legacy evidence\n"
        b"Next action: verify\n"
    )
    module.shutil.rmtree = partial_cleanup
    try:
        try:
            module.convert_legacy_candidate(root, slug, candidate_data)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
            assert "state=committed" in str(exc)
        else:
            raise AssertionError("post-commit cleanup fault returned success")
    finally:
        module.shutil.rmtree = original_rmtree

    assert injected
    target = root / "work-items" / "backlog" / f"{slug}.md"
    readme = root / "work-items" / "README.md"
    converted = target.read_bytes()
    assert converted.startswith(candidate_data) and not source.exists()
    for relative, data in before.items():
        assert f"### `{relative}`".encode() in converted
        assert data in converted
        assert hashlib.sha256(data).hexdigest().encode() in converted
    assert readme.read_bytes() == module.render_readme_bytes(root)
    residues = list((root / "work-items" / "backlog").glob(f".{slug}.legacy-candidate.*"))
    assert len(residues) == 1
    marker = residues[0] / module.LEGACY_CLEANUP_FILE
    marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    assert marker_payload["schemaVersion"] == module.LEGACY_CLEANUP_SCHEMA_VERSION
    assert marker_payload["owner"] == module.LEGACY_CLEANUP_OWNER
    assert marker_payload["slug"] == slug
    assert marker_payload["transactionId"] == residues[0].name
    assert marker_payload["canonicalTarget"] == f"backlog/{slug}.md"
    assert marker_payload["candidateSha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert marker_payload["sourceFiles"]
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()

    replay = module.convert_legacy_candidate(root, slug, candidate_data)

    assert replay == target
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before
    assert not residues[0].exists()
    module.audit(root)


def test_convert_legacy_candidate_replays_final_rmdir_failure_with_sidecar_marker(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-final-rmdir"
    source, _before = _seed_legacy_backlog(root, slug, {"brief.md": b"owned source\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve final cleanup marker\n"
        b"Next action: verify\n"
    )
    backlog = root / "work-items" / "backlog"
    original_rmdir = module.Path.rmdir
    injected = False

    def fail_final_rmdir(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal injected
        if (
            path.parent == backlog
            and path.name.startswith(f".{slug}.legacy-candidate.")
            and not injected
        ):
            injected = True
            raise OSError("injected final transaction rmdir failure")
        original_rmdir(path, *args, **kwargs)

    module.Path.rmdir = fail_final_rmdir
    try:
        try:
            module.convert_legacy_candidate(root, slug, candidate_data)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
            assert "state=committed" in str(exc)
        else:
            raise AssertionError("final transaction rmdir fault returned success")
    finally:
        module.Path.rmdir = original_rmdir

    target = backlog / f"{slug}.md"
    readme = root / "work-items" / "README.md"
    residues = list(backlog.glob(f".{slug}.legacy-candidate.*"))
    assert injected and not source.exists() and len(residues) == 1
    residue = residues[0]
    sidecar = module._legacy_cleanup_sidecar(backlog, residue.name)
    assert not (residue / module.LEGACY_CLEANUP_FILE).exists()
    assert list(residue.iterdir()) == []
    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_payload["transactionId"] == residue.name
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()

    replay = module.convert_legacy_candidate(root, slug, candidate_data)

    assert replay == target
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before
    assert not residue.exists() and not sidecar.exists()
    module.audit(root)


def test_convert_legacy_candidate_replays_sidecar_marker_unlink_failure(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-sidecar-unlink"
    source, _before = _seed_legacy_backlog(root, slug, {"brief.md": b"owned source\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve sidecar cleanup marker\n"
        b"Next action: verify\n"
    )
    backlog = root / "work-items" / "backlog"
    original_unlink = module.Path.unlink
    injected = False

    def fail_sidecar_unlink(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal injected
        if (
            path.parent == backlog
            and path.name.startswith(f".legacy-candidate-cleanup.{slug}.legacy-candidate.")
            and not injected
        ):
            injected = True
            raise OSError("injected sidecar marker unlink failure")
        original_unlink(path, *args, **kwargs)

    module.Path.unlink = fail_sidecar_unlink
    try:
        try:
            module.convert_legacy_candidate(root, slug, candidate_data)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
            assert "state=committed" in str(exc)
        else:
            raise AssertionError("sidecar marker cleanup fault returned success")
    finally:
        module.Path.unlink = original_unlink

    target = backlog / f"{slug}.md"
    readme = root / "work-items" / "README.md"
    sidecars = list(backlog.glob(f".legacy-candidate-cleanup.{slug}.legacy-candidate.*.json"))
    assert injected and not source.exists() and len(sidecars) == 1
    sidecar = sidecars[0]
    assert not list(backlog.glob(f".{slug}.legacy-candidate.*"))
    assert json.loads(sidecar.read_text(encoding="utf-8"))["slug"] == slug
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()

    replay = module.convert_legacy_candidate(root, slug, candidate_data)

    assert replay == target
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before
    assert not sidecar.exists()
    module.audit(root)


def test_convert_legacy_candidate_replay_rejects_unmarked_spoof_without_deletion(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-spoof"
    source, _before = _seed_legacy_backlog(root, slug, {"brief.md": b"owned source\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve cleanup ownership\n"
        b"Next action: verify\n"
    )
    target = module.convert_legacy_candidate(root, slug, candidate_data)
    assert not source.exists()
    readme = root / "work-items" / "README.md"
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()
    spoof = root / "work-items" / "backlog" / f".{slug}.legacy-candidate.user-owned"
    valuable = spoof / "valuable.txt"
    valuable.parent.mkdir(parents=True)
    valuable.write_bytes(b"unowned valuable bytes\n")

    try:
        module.convert_legacy_candidate(root, slug, candidate_data)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEGACY-CLEANUP-REPLAY-INVALID"
    else:
        raise AssertionError("unmarked matching residue was deleted")

    assert valuable.read_bytes() == b"unowned valuable bytes\n"
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before


def test_convert_legacy_candidate_replay_rejects_marker_mismatch_without_deletion(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-marker-mismatch"
    source, _before = _seed_legacy_backlog(
        root, slug, {"brief.md": b"owned source\n", "notes/design.md": b"owned design\n"}
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve owner marker\n"
        b"Next action: verify\n"
    )
    original_rmtree = module.shutil.rmtree
    injected = False

    def partial_cleanup(path: Path | str, *args: object, **kwargs: object) -> None:
        nonlocal injected
        candidate = Path(path)
        if candidate.name == "source" and not injected:
            injected = True
            (candidate / "brief.md").unlink()
            raise OSError("injected partial cleanup failure")
        original_rmtree(path, *args, **kwargs)

    module.shutil.rmtree = partial_cleanup
    try:
        try:
            module.convert_legacy_candidate(root, slug, candidate_data)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
        else:
            raise AssertionError("post-commit cleanup fault returned success")
    finally:
        module.shutil.rmtree = original_rmtree

    target = root / "work-items" / "backlog" / f"{slug}.md"
    readme = root / "work-items" / "README.md"
    residue = next((root / "work-items" / "backlog").glob(f".{slug}.legacy-candidate.*"))
    marker = residue / module.LEGACY_CLEANUP_FILE
    marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    marker_payload["candidateSha256"] = "0" * 64
    marker.write_text(json.dumps(marker_payload, sort_keys=True) + "\n", encoding="utf-8")
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()
    residue_before = {
        path.relative_to(residue).as_posix(): path.read_bytes()
        for path in residue.rglob("*")
        if path.is_file()
    }

    try:
        module.convert_legacy_candidate(root, slug, candidate_data)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEGACY-CLEANUP-REPLAY-INVALID"
    else:
        raise AssertionError("mismatched owner marker was accepted")

    assert injected and not source.exists()
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before
    assert {
        path.relative_to(residue).as_posix(): path.read_bytes()
        for path in residue.rglob("*")
        if path.is_file()
    } == residue_before


def test_retire_legacy_backlog_records_links_and_no_fake_active_history(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-rejected"
    source, before = _seed_legacy_backlog(
        root,
        slug,
        {"design.md": b"# Design only -- not admitted\n\nDecision: reject.\n"},
    )
    write(
        root / "work-items" / "bugs" / "consumer.md",
        f"status: open\nContext: work-item:{slug}\n",
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    instant = "2026-08-01T00:00:00Z"
    disposition = b"Rejected before admission; future components require fresh intake.\n"

    target = module.retire_legacy_backlog(root, slug, disposition, instant)

    assert target == root / "work-items" / "archive" / "2026-08" / slug
    assert not source.exists()
    assert (target / "design.md").read_bytes() == before["design.md"]
    metadata = json.loads(
        (target / "legacy-retirement.json").read_text(encoding="utf-8")
    )
    assert metadata["terminalAt"] == instant
    assert metadata["status"] == "rejected-before-admission"
    assert metadata["admissionHistory"] == "never-admitted"
    assert metadata["syntheticTransitions"] == []
    assert metadata["sourceFiles"] == [
        {
            "path": "design.md",
            "byteLength": len(before["design.md"]),
            "sha256": hashlib.sha256(before["design.md"]).hexdigest(),
        }
    ]
    assert metadata["incomingLinks"]["result"] == "logical-only"
    assert {row["kind"] for row in metadata["incomingLinks"]["references"]} == {"logical"}
    for forbidden in ("status.md", "closure.md", "admission.md", "agent-runs.jsonl"):
        assert not (target / forbidden).exists()
    entries = [
        entry
        for entry in module.collect_readme_entries(root)
        if entry.logical_reference == f"work-item:{slug}"
    ]
    assert len(entries) == 1
    assert entries[0].section == "Recently completed" and entries[0].checked
    assert entries[0].classification == "WI-LEGACY-RETIRED-BEFORE-ADMISSION"
    module.audit(root)


def test_audit_rejects_live_plain_path_to_retired_backlog_but_ignores_archive_history(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retired-path-citation"
    _source, _before = _seed_legacy_backlog(
        root,
        slug,
        {"design.md": b"# Design only\n"},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    target = module.retire_legacy_backlog(
        root,
        slug,
        b"Rejected before admission.\n",
        "2026-08-01T00:00:00Z",
    )
    retired_path = f"work-items/backlog/{slug}/design.md"
    archived_consumer = root / "work-items" / "decisions" / "archive" / "2026-08" / "history.md"
    write(
        archived_consumer,
        f"Historical context: work-item:{slug}; `{retired_path}`.\n",
    )
    false_positive_slug = "2026-08-01-current"
    false_positive = root / "work-items" / "decisions" / f"{false_positive_slug}.md"
    write(
        false_positive,
        _current_decision_record(
            false_positive_slug,
            body=f"Not a path: `not-{retired_path}`.\n",
        ),
    )

    assert module._incoming_link_result(
        root,
        {target},
        f"work-item:{slug}",
        literal_path_references=(retired_path,),
        mutable_consumers_only=True,
        scan_markdown_links=False,
    ) == {"result": "clear", "references": []}

    live_slug = "2026-08-01-live"
    live_consumer = root / "work-items" / "decisions" / f"{live_slug}.md"
    write(
        live_consumer,
        _current_decision_record(
            live_slug,
            body=f"Stale context: `{retired_path}`.\n",
        ),
    )
    try:
        module.audit(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEGACY-RETIREMENT-INVALID"
        assert "mutable record retains a retired backlog path" in str(exc)
    else:
        raise AssertionError("live literal citation to retired backlog passed audit")


def test_retire_legacy_backlog_strict_utc_and_failure_rollback(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-retire-rollback"
    source, before = _seed_legacy_backlog(
        root, slug, {"design.md": b"preserve retirement source\n"}
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme_before = (root / "work-items" / "README.md").read_bytes()
    try:
        module.retire_legacy_backlog(
            root,
            slug,
            b"Rejected before admission.\n",
            "2026-08-01T03:00:00+03:00",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("non-UTC retirement was admitted")
    assert (source / "design.md").read_bytes() == before["design.md"]

    try:
        module.retire_legacy_backlog(
            root,
            slug,
            b"Rejected before admission.\n",
            "2026-08-01T00:00:00Z",
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected retirement failure returned success")
    assert (source / "design.md").read_bytes() == before["design.md"]
    assert not (root / "work-items" / "archive").exists()
    assert (root / "work-items" / "README.md").read_bytes() == readme_before


def test_terminalize_v1_supports_every_flat_category(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    records = {
        "bug": ("bugs", "fixed", "Terminal-at", "Resolution"),
        "decision": ("decisions", "dropped", "Terminal-at", "Rationale"),
        "lesson": ("lessons", "archived", "Terminal-at", "Disposition"),
        "roadmap": ("roadmaps", "archived", "Terminal-at", "Disposition"),
        "epic": ("epics", "closed", "Closed", "Outcome"),
    }
    for category, (directory, status, _utc_field, _detail_field) in records.items():
        write(
            work_items / directory / f"legacy-{category}.md",
            f"status: {status}\nTask: Preserve {category}.\n",
        )
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 1, audited.stdout
    assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert {row["category"] for row in payload["rows"]} == set(records)
    assert {row["admission"]["result"] for row in payload["rows"]} == {"denied"}

    count, replay = module.terminalize_v1_inventory(
        root,
        inventory,
        terminal_at="2026-08-01T00:00:00Z",
        authorization_marker="operator-authorized-v1-terminalization",
        receipt_path=receipt,
    )

    assert count == len(records) and replay is False
    for category, (directory, _status, utc_field, detail_field) in records.items():
        text = (work_items / directory / f"legacy-{category}.md").read_text(
            encoding="utf-8"
        )
        assert f"{utc_field}: 2026-08-01T00:00:00Z" in text
        assert f"{detail_field}: Pre-V1 terminal status" in text
        assert text.count("V1-Migration-Evidence:") == 1
        assert text.count("Evidence:") == 2
    refreshed = root / ".scratch" / "refreshed.json"
    checked = run_cli(
        "audit", "--root", str(work_items), "--output", str(refreshed)
    )
    assert checked.returncode == 0, checked.stdout
    assert {
        row["admission"]["result"]
        for row in json.loads(refreshed.read_text(encoding="utf-8"))["rows"]
    } == {"admitted"}


def _physical_relocation_inventory(root: Path) -> tuple[Path, Path, Path, Path, dict]:
    work_items = root / "work-items"
    slug = "roadmap-decision-2026-07-27"
    target = work_items / "roadmaps" / f"{slug}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_pre_v1_terminal_record("archived", "Historical roadmap"))
    consumer = (
        work_items
        / "epics"
        / "archive"
        / "2026-07"
        / "2026-07-27-always-on-hook-layer-fitness.md"
    )
    label = f"work-items/roadmaps/{slug}.md"
    old_href = f"../../../roadmaps/{slug}.md"
    write(consumer, f"# Closed epic\n\n[{label}]({old_href}).\n")
    inventory = root / ".scratch" / "terminalization-inventory.json"
    receipt = root / ".scratch" / "terminalization-receipt.json"
    payload = _denied_terminalization_inventory(work_items, inventory)
    row = next(row for row in payload["rows"] if row["reference"] == f"roadmap:{slug}")
    assert row["incomingLinks"] == {
        "result": "unmapped",
        "references": [
            {
                "consumer": consumer.relative_to(work_items).as_posix(),
                "kind": "physical",
                "value": old_href,
            }
        ],
    }
    row["incomingLinks"] = {
        "result": "physical-relocation",
        "references": row["incomingLinks"]["references"],
        "physicalRelocation": {
            "source": consumer.relative_to(work_items).as_posix(),
            "label": label,
            "href": old_href,
            "expectedIdentity": f"roadmap:{slug}",
            "sourceSha256": hashlib.sha256(consumer.read_bytes()).hexdigest(),
            "targetSha256": row["inputSha256"],
            "receipt": receipt.relative_to(root).as_posix(),
        },
    }
    inventory.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return inventory, receipt, consumer, target, payload


@pytest.mark.parametrize("opaque", (False, True))
def test_exact_physical_relocation_is_admitted_then_moved_atomically(
    tmp_path: Path, opaque: bool,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    inventory, receipt, consumer, current_target, payload = _physical_relocation_inventory(root)
    work_items = root / "work-items"
    row = payload["rows"][0]
    if opaque:
        consumer.write_bytes(b"\xef\xbb\xbf\xc3\xa9\x97\r\n" + consumer.read_bytes() + b"\x81")
        row["incomingLinks"]["physicalRelocation"]["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        inventory.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    consumer_before = consumer.read_bytes()
    target_before = current_target.read_bytes()

    count, replay = module.terminalize_v1_inventory(
        root,
        inventory,
        terminal_at="2026-08-01T00:00:00Z",
        authorization_marker="operator-authorized-v1-terminalization",
        receipt_path=receipt,
    )

    assert count == 1 and replay is False
    assert consumer.read_bytes() == consumer_before
    assert current_target.is_file()
    assert current_target.read_bytes().startswith(target_before)
    terminalized_target = current_target.read_bytes()

    migrated, _readme_hash = module.apply_migration_inventory(
        root,
        inventory,
        render_readme=True,
        byte_check=True,
    )

    final_target = (
        work_items
        / "roadmaps"
        / "archive"
        / "2026-08"
        / current_target.name
    )
    expected_new_href = f"../../../roadmaps/archive/2026-08/{current_target.name}"
    consumer_after = consumer.read_bytes()
    assert migrated == 1
    assert not current_target.exists() and final_target.read_bytes() == terminalized_target
    assert consumer_after == consumer_before.replace(
        row["incomingLinks"]["physicalRelocation"]["href"].encode(),
        expected_new_href.encode(),
    )
    assert (consumer.parent / expected_new_href).resolve() == final_target.resolve()
    assert module._category_locations(
        root, module.CATEGORIES["roadmap"], current_target.stem
    ) == [final_target]
    assert module.verify_migration_inventory(root, inventory) == 1
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    evidence = receipt_payload["rows"][0]["physicalRelocation"]
    assert evidence["oldHref"] == row["incomingLinks"]["physicalRelocation"]["href"]
    assert evidence["newHref"] == expected_new_href
    assert evidence["finalTarget"] == final_target.relative_to(work_items).as_posix()
    assert evidence["sourceBeforeSha256"] == hashlib.sha256(consumer_before).hexdigest()
    assert evidence["sourceAfterSha256"] == hashlib.sha256(consumer_after).hexdigest()
    assert evidence["targetBeforeSha256"] == hashlib.sha256(terminalized_target).hexdigest()
    assert evidence["targetAfterSha256"] == hashlib.sha256(final_target.read_bytes()).hexdigest()


@pytest.mark.parametrize("failure_kind", ("ordinary", "cancellation"))
def test_physical_relocation_parent_creation_rolls_back_before_move(
    tmp_path: Path, monkeypatch, failure_kind: str,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    inventory, receipt, consumer, source, _payload = _physical_relocation_inventory(root)
    module.terminalize_v1_inventory(
        root,
        inventory,
        terminal_at="2026-08-01T00:00:00Z",
        authorization_marker="operator-authorized-v1-terminalization",
        receipt_path=receipt,
    )
    work_items = root / "work-items"
    archive_parent = source.parent / "archive"
    month_parent = archive_parent / "2026-08"
    target = month_parent / source.name
    readme = work_items / "README.md"
    source_before = source.read_bytes()
    consumer_before = consumer.read_bytes()
    receipt_before = receipt.read_bytes()
    inventory_before = inventory.read_bytes()
    readme_before = readme.read_bytes() if readme.is_file() else None
    injected = (
        module.LifecycleError(
            "TEST-PHYSICAL-PARENT-PUBLISH", "controlled second-parent ordinary failure",
        )
        if failure_kind == "ordinary"
        else KeyboardInterrupt("controlled second-parent cancellation")
    )
    original_publish = module.LifecycleWriteTarget._publish_effect
    original_remove = module.LifecycleWriteTarget.remove_created_directory
    published_records = []
    failed_records = []
    removed_records = []
    removed_identities = []

    def fail_second_parent(owner, prepared, identity):
        if (
            prepared.directory
            and prepared.source is None
            and prepared.destination == month_parent
        ):
            failed_records.append(owner._creations[-1])
            raise injected
        result = original_publish(owner, prepared, identity)
        if (
            prepared.directory
            and prepared.source is None
            and prepared.destination == archive_parent
        ):
            published_records.append(owner._creations[-1])
        return result

    def remove_actual_creator(record, transaction, *, failure_id="WI-LIFECYCLE-EFFECT"):
        removed_records.append(record)
        removed_identities.append(module._lifecycle_file_identity(record.locator.lstat()))
        return original_remove(record, transaction, failure_id=failure_id)

    monkeypatch.setattr(module.LifecycleWriteTarget, "_publish_effect", fail_second_parent)
    monkeypatch.setattr(
        module.LifecycleWriteTarget, "remove_created_directory", remove_actual_creator,
    )
    with pytest.raises(type(injected)) as failed:
        module.apply_migration_inventory(
            root, inventory, render_readme=True, byte_check=True,
        )

    assert failed.value is injected
    assert len(published_records) == len(failed_records) == 1
    assert removed_records == published_records
    published = published_records[0]
    assert published.creator and published.finished and published.release_complete
    assert removed_identities == [published.identity]
    aborted = failed_records[0]
    assert aborted.creator and aborted.finished and aborted.release_complete
    assert not aborted.creation_published and aborted.primary is injected
    assert aborted.phase == "disposed"
    assert not archive_parent.exists() and not month_parent.exists() and not target.exists()
    assert source.read_bytes() == source_before
    assert consumer.read_bytes() == consumer_before
    assert receipt.read_bytes() == receipt_before
    assert inventory.read_bytes() == inventory_before
    if readme_before is None:
        assert not readme.exists()
    else:
        assert readme.read_bytes() == readme_before


def test_physical_relocation_cleanup_baseexception_continues_and_preserves_nonempty_state(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    inventory, receipt, consumer, source, _payload = _physical_relocation_inventory(root)
    module.terminalize_v1_inventory(
        root,
        inventory,
        terminal_at="2026-08-01T00:00:00Z",
        authorization_marker="operator-authorized-v1-terminalization",
        receipt_path=receipt,
    )
    work_items = root / "work-items"
    archive_parent = source.parent / "archive"
    month_parent = archive_parent / "2026-08"
    final_target = month_parent / source.name
    readme = work_items / "README.md"
    source_before = source.read_bytes()
    consumer_before = consumer.read_bytes()
    receipt_before = receipt.read_bytes()
    inventory_before = inventory.read_bytes()
    readme_before = readme.read_bytes() if readme.is_file() else None
    primary = module.LifecycleError(
        "TEST-PHYSICAL-PRIMARY", "controlled failure after physical move",
    )
    class CleanupAbort(BaseException):
        pass

    cleanup_interrupt = CleanupAbort("controlled cancellation during move reversal")
    original_refresh = module.refresh_readme
    original_replace = module._replace_lifecycle_directory
    original_atomic_write = module._atomic_write
    original_restore_readme = module._restore_readme_snapshot
    original_remove = module.LifecycleWriteTarget.remove_created_directory
    cleanup_stages = []
    removal_attempts = []
    removal_refusals = []
    foreign = archive_parent / "foreign.keep"

    def fail_after_move(*_args, **_kwargs):
        raise primary

    def cancel_reverse(source_path, destination, *args, **kwargs):
        if source_path == final_target and destination == source:
            cleanup_stages.append("move-reversal")
            raise cleanup_interrupt
        return original_replace(source_path, destination, *args, **kwargs)

    def observe_atomic_write(path, data, *args, **kwargs):
        if path == consumer and data == consumer_before:
            cleanup_stages.append("consumer-restore")
        if path == receipt and data == receipt_before:
            cleanup_stages.append("receipt-restore")
        return original_atomic_write(path, data, *args, **kwargs)

    def observe_readme_restore(*args, **kwargs):
        cleanup_stages.append("readme-restore")
        return original_restore_readme(*args, **kwargs)

    def preserve_actual_creator(record, transaction, *, failure_id="WI-LIFECYCLE-EFFECT"):
        cleanup_stages.append("directory-rollback")
        removal_attempts.append(record)
        if not foreign.exists():
            foreign.write_bytes(b"unowned cleanup-time content\n")
        try:
            return original_remove(record, transaction, failure_id=failure_id)
        except BaseException as exc:
            removal_refusals.append(exc)
            raise

    monkeypatch.setattr(module, "refresh_readme", fail_after_move)
    monkeypatch.setattr(module, "_replace_lifecycle_directory", cancel_reverse)
    monkeypatch.setattr(module, "_atomic_write", observe_atomic_write)
    monkeypatch.setattr(module, "_restore_readme_snapshot", observe_readme_restore)
    monkeypatch.setattr(
        module.LifecycleWriteTarget, "remove_created_directory", preserve_actual_creator,
    )

    with pytest.raises(module.LifecycleError) as failed:
        module.apply_migration_inventory(
            root, inventory, render_readme=True, byte_check=True,
        )

    assert failed.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
    assert failed.value.__cause__ is primary
    assert str(cleanup_interrupt) in str(failed.value)
    assert cleanup_stages == [
        "move-reversal",
        "consumer-restore",
        "readme-restore",
        "receipt-restore",
        "directory-rollback",
        "directory-rollback",
    ]
    assert len(removal_attempts) == 2 and len(removal_refusals) == 2
    assert all(isinstance(exc, module.LifecycleError) for exc in removal_refusals)
    assert consumer.read_bytes() == consumer_before
    assert receipt.read_bytes() == receipt_before
    assert inventory.read_bytes() == inventory_before
    if readme_before is None:
        assert not readme.exists()
    else:
        assert readme.read_bytes() == readme_before
    assert not source.exists() and final_target.read_bytes() == source_before
    assert foreign.read_bytes() == b"unowned cleanup-time content\n"
    assert archive_parent.is_dir() and month_parent.is_dir()
    assert all(record.creator and record.finished and record.release_complete for record in removal_attempts)
    assert all(
        module._lifecycle_file_identity(record.locator.lstat()) == record.identity
        for record in removal_attempts
    )


def test_physical_relocation_preserves_fragment_and_query_suffix_atomically(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case, suffix in (("fragment", "#section"), ("query", "?view=full")):
        root = tmp_path / case
        inventory, receipt, consumer, current_target, payload = (
            _physical_relocation_inventory(root)
        )
        row = payload["rows"][0]
        admission = row["incomingLinks"]["physicalRelocation"]
        raw_href = admission["href"] + suffix
        consumer.write_text(
            f"# Closed epic\n\n[{admission['label']}]({raw_href}).\n",
            encoding="utf-8",
        )
        row["incomingLinks"]["references"][0]["value"] = raw_href
        admission["href"] = raw_href
        admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        count, replay = module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
        )
        assert count == 1 and replay is False, case
        migrated, _readme_hash = module.apply_migration_inventory(
            root,
            inventory,
            render_readme=True,
            byte_check=True,
        )

        final_target = (
            root
            / "work-items"
            / "roadmaps"
            / "archive"
            / "2026-08"
            / current_target.name
        )
        new_path = f"../../../roadmaps/archive/2026-08/{current_target.name}"
        new_href = new_path + suffix
        consumer_text = consumer.read_text(encoding="utf-8")
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        evidence = receipt_payload["rows"][0]["physicalRelocation"]
        assert migrated == 1 and final_target.is_file(), case
        assert f"]({new_href})" in consumer_text and raw_href not in consumer_text, case
        assert evidence["oldHref"] == raw_href and evidence["newHref"] == new_href, case
        assert module.verify_migration_inventory(root, inventory) == 1, case


def test_physical_relocation_tuple_mismatches_fail_before_any_write(
    tmp_path: Path,
) -> None:
    module = load_module()
    cases = {
        "source": lambda admission: admission.__setitem__(
            "source", "epics/archive/2026-07/other.md"
        ),
        "label": lambda admission: admission.__setitem__("label", admission["label"] + "-wrong"),
        "href": lambda admission: admission.__setitem__("href", admission["href"] + "-wrong"),
        "identity": lambda admission: admission.__setitem__(
            "expectedIdentity", "roadmap:other"
        ),
        "source-hash": lambda admission: admission.__setitem__("sourceSha256", "0" * 64),
        "target-hash": lambda admission: admission.__setitem__("targetSha256", "0" * 64),
        "receipt-escape": lambda admission: admission.__setitem__("receipt", "../receipt.json"),
    }
    for case, mutate in cases.items():
        root = tmp_path / case
        inventory, receipt, consumer, target, payload = _physical_relocation_inventory(root)
        admission = payload["rows"][0]["incomingLinks"]["physicalRelocation"]
        mutate(admission)
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        consumer_before = consumer.read_bytes()
        target_before = target.read_bytes()

        try:
            module.terminalize_v1_inventory(
                root,
                inventory,
                terminal_at="2026-08-01T00:00:00Z",
                authorization_marker="operator-authorized-v1-terminalization",
                receipt_path=receipt,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
        else:
            raise AssertionError(f"{case} mismatch was admitted")

        assert consumer.read_bytes() == consumer_before, case
        assert target.read_bytes() == target_before, case
        assert not receipt.exists(), case


def test_terminalization_receipt_must_stay_under_repository_scratch(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case in ("outside", "traversal", "scratch-root", "reparse"):
        root = tmp_path / f"repo-{case}"
        work_items = root / "work-items"
        source = work_items / "bugs" / "historic.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(_pre_v1_terminal_record("fixed", "Historic"))
        inventory = root / ".scratch" / "inventory.json"
        payload = _denied_terminalization_inventory(work_items, inventory)
        assert payload["rows"][0]["incomingLinks"]["result"] == "clear"
        before = source.read_bytes()
        if case == "outside":
            escaped_receipt = tmp_path / "outside" / ".scratch" / "receipt.json"
        elif case == "traversal":
            escaped_receipt = root / ".scratch" / ".." / "outside" / "receipt.json"
        elif case == "scratch-root":
            escaped_receipt = root / ".scratch"
        else:
            redirect = root / ".scratch" / "redirect"
            redirect.mkdir(parents=True)
            escaped_receipt = redirect / "receipt.json"

        original_reparse = module._terminalization_has_reparse
        if case == "reparse":
            module._terminalization_has_reparse = (
                lambda path, redirect=redirect: path == redirect or original_reparse(path)
            )
        try:
            try:
                module.terminalize_v1_inventory(
                    root,
                    inventory,
                    terminal_at="2026-08-01T00:00:00Z",
                    authorization_marker="operator-authorized-v1-terminalization",
                    receipt_path=escaped_receipt,
                )
            except module.LifecycleError as exc:
                assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
            else:
                raise AssertionError(f"{case} receipt path was accepted")
        finally:
            module._terminalization_has_reparse = original_reparse

        assert source.read_bytes() == before, case
        assert not escaped_receipt.is_file(), case

    physical_root = tmp_path / "physical-admission"
    physical_receipt = physical_root / ".scratch" / "receipt.json"
    for case, relative in {
        "absolute": str(physical_receipt.resolve()),
        "traversal": ".scratch/../outside/receipt.json",
    }.items():
        try:
            module._bound_physical_receipt(physical_root, relative)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
        else:
            raise AssertionError(f"physical admission accepted {case} receipt path")


def test_physical_relocation_rejects_unclosed_or_prefix_markdown_destinations(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case, suffix in {
        "unterminated": "",
        "trailing": " trailing)",
        "fragment": "#section)",
        "query": "?view=full)",
        "title": ' "historic")',
    }.items():
        root = tmp_path / case
        inventory, receipt, consumer, target, payload = _physical_relocation_inventory(root)
        admission = payload["rows"][0]["incomingLinks"]["physicalRelocation"]
        consumer.write_text(
            f"[{admission['label']}]({admission['href']}{suffix}\n", encoding="utf-8"
        )
        admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        try:
            module.terminalize_v1_inventory(
                root,
                inventory,
                terminal_at="2026-08-01T00:00:00Z",
                authorization_marker="operator-authorized-v1-terminalization",
                receipt_path=receipt,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
        else:
            raise AssertionError(f"{case} Markdown destination was admitted")

        assert target.is_file(), case
        assert not receipt.exists(), case


def test_physical_relocation_duplicate_nonarchive_and_wrong_resolution_fail_closed(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case in ("duplicate", "nonarchive", "wrong-resolution"):
        root = tmp_path / case
        inventory, receipt, consumer, target, payload = _physical_relocation_inventory(root)
        row = payload["rows"][0]
        admission = row["incomingLinks"]["physicalRelocation"]
        if case == "duplicate":
            consumer.write_bytes(consumer.read_bytes() + consumer.read_bytes().split(b"\n")[-2] + b"\n")
            row["incomingLinks"]["references"].append(
                dict(row["incomingLinks"]["references"][0])
            )
            admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        elif case == "nonarchive":
            live_consumer = target.parents[1] / "epics" / "live-consumer.md"
            new_href = f"../roadmaps/{target.name}"
            write(live_consumer, f"[{admission['label']}]({new_href})\n")
            consumer.unlink()
            consumer = live_consumer
            row["incomingLinks"]["references"][0]["consumer"] = consumer.relative_to(
                root / "work-items"
            ).as_posix()
            row["incomingLinks"]["references"][0]["value"] = new_href
            admission["source"] = row["incomingLinks"]["references"][0]["consumer"]
            admission["href"] = new_href
            admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        else:
            wrong = target.parent / "other.md"
            wrong.write_bytes(_pre_v1_terminal_record("archived", "Other"))
            wrong_href = f"../../../roadmaps/{wrong.name}"
            consumer.write_text(
                f"[{admission['label']}]({wrong_href})\n", encoding="utf-8"
            )
            row["incomingLinks"]["references"][0]["value"] = wrong_href
            admission["href"] = wrong_href
            admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        consumer_before = consumer.read_bytes()
        target_before = target.read_bytes()

        try:
            module.terminalize_v1_inventory(
                root,
                inventory,
                terminal_at="2026-08-01T00:00:00Z",
                authorization_marker="operator-authorized-v1-terminalization",
                receipt_path=receipt,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
        else:
            raise AssertionError(f"{case} physical relocation was admitted")

        assert consumer.read_bytes() == consumer_before, case
        assert target.read_bytes() == target_before, case
        assert not receipt.exists(), case


def test_physical_relocation_apply_drift_and_post_move_failure_roll_back(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case in ("consumer-drift", "target-drift", "receipt-drift", "post-move"):
        root = tmp_path / case
        inventory, receipt, consumer, target, _payload = _physical_relocation_inventory(root)
        module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
        )
        consumer_before = consumer.read_bytes()
        target_before = target.read_bytes()
        receipt_before = receipt.read_bytes()
        readme = root / "work-items" / "README.md"
        readme_before = readme.read_bytes() if readme.is_file() else None
        if case == "consumer-drift":
            consumer.write_bytes(consumer_before + b"drift\n")
        elif case == "target-drift":
            target.write_bytes(target_before + b"drift\n")
        elif case == "receipt-drift":
            receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
            receipt_payload["rows"][0]["physicalRelocation"]["label"] += "-wrong"
            receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
        original_refresh = module.refresh_readme
        if case == "post-move":
            def fail_after_move(*_args, **_kwargs):
                raise module.LifecycleError("WI-README-STALE", "injected after move")

            module.refresh_readme = fail_after_move
        try:
            try:
                module.apply_migration_inventory(
                    root,
                    inventory,
                    render_readme=True,
                    byte_check=True,
                )
            except module.LifecycleError:
                pass
            else:
                raise AssertionError(f"{case} returned success")
        finally:
            module.refresh_readme = original_refresh

        final_target = (
            root
            / "work-items"
            / "roadmaps"
            / "archive"
            / "2026-08"
            / target.name
        )
        assert target.is_file() and not final_target.exists(), case
        if case == "consumer-drift":
            assert consumer.read_bytes() == consumer_before + b"drift\n"
        else:
            assert consumer.read_bytes() == consumer_before, case
        if case == "target-drift":
            assert target.read_bytes() == target_before + b"drift\n"
        else:
            assert target.read_bytes() == target_before, case
        if case == "receipt-drift":
            assert receipt.read_bytes() != receipt_before
        else:
            assert receipt.read_bytes() == receipt_before, case
        if readme_before is None:
            assert not readme.exists(), case
        else:
            assert readme.read_bytes() == readme_before, case


def test_settled_physical_relocation_receipt_fields_are_bound_to_admission(
    tmp_path: Path,
) -> None:
    module = load_module()
    for field, replacement in {
        "expectedIdentity": "roadmap:other",
        "oldHref": "../../../roadmaps/other.md",
        "sourceBeforeSha256": "0" * 64,
        "targetBeforeSha256": "f" * 64,
    }.items():
        root = tmp_path / field
        inventory, receipt, consumer, target, _payload = _physical_relocation_inventory(root)
        module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
        )
        module.apply_migration_inventory(
            root,
            inventory,
            render_readme=True,
            byte_check=True,
        )
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        receipt_payload["rows"][0]["physicalRelocation"][field] = replacement
        receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
        consumer_before = consumer.read_bytes()
        final_target = target.parent / "archive" / "2026-08" / target.name
        target_before = final_target.read_bytes()

        try:
            module.apply_migration_inventory(
                root,
                inventory,
                render_readme=True,
                byte_check=True,
            )
        except module.LifecycleError:
            pass
        else:
            raise AssertionError(f"settled {field} drift was accepted")

        assert consumer.read_bytes() == consumer_before, field
        assert final_target.read_bytes() == target_before, field


def test_settled_physical_relocation_replay_binds_its_owner_row_in_both_orders(
    tmp_path: Path,
) -> None:
    module = load_module()
    for owner_position in ("first", "last"):
        root = tmp_path / owner_position
        inventory, receipt, consumer, target, initial_payload = (
            _physical_relocation_inventory(root)
        )
        work_items = root / "work-items"
        unrelated = work_items / "roadmaps" / "roadmap-z.md"
        unrelated.write_bytes(_pre_v1_terminal_record("archived", "Unrelated roadmap"))

        payload = _denied_terminalization_inventory(work_items, inventory)
        owner_reference = f"roadmap:{target.stem}"
        owner_row = next(
            row for row in payload["rows"] if row["reference"] == owner_reference
        )
        owner_row["incomingLinks"] = initial_payload["rows"][0]["incomingLinks"]
        unrelated_row = next(
            row for row in payload["rows"] if row["reference"] != owner_reference
        )
        payload["rows"] = (
            [owner_row, unrelated_row]
            if owner_position == "first"
            else [unrelated_row, owner_row]
        )
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        count, replay = module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
        )
        assert count == 2 and replay is False, owner_position

        migrated, _readme_hash = module.apply_migration_inventory(
            root,
            inventory,
            render_readme=True,
            byte_check=True,
        )
        assert migrated == 2, owner_position
        replayed, _readme_hash = module.apply_migration_inventory(
            root,
            inventory,
            render_readme=True,
            byte_check=True,
        )
        assert replayed == 2, owner_position

        final_target = target.parent / "archive" / "2026-08" / target.name
        expected_new_href = f"../../../roadmaps/archive/2026-08/{target.name}"
        assert (consumer.parent / expected_new_href).resolve() == final_target.resolve()
        assert module.verify_migration_inventory(root, inventory) == 2


def _canonical_decision_record(slug: str) -> str:
    return (
        f"- id: {slug}\n"
        "- status: proposed\n"
        "- date: 2026-08-11\n"
        "- decided-by: $architect\n"
        "- context: schema-test\n"
        "- supersedes: none\n"
        "- superseded-by: none\n"
        "- accepted-evidence: first line\n"
        "  continuation line\n"
        "\n"
        f"# Decision: {slug}\n"
        "\n"
        "## Decision\n"
        "Synthetic decision.\n"
    )


def _accepted_v0_policy_record(
    slug: str,
    baseline_sha256: str,
    *,
    manifest_path: str = "work-items/decision-v0-compatibility.json",
    cutover_date: str = "2026-08-18",
) -> str:
    return _canonical_decision_record(slug).replace(
        "- status: proposed\n",
        "- status: accepted\n",
    ).replace(
        "- date: 2026-08-11\n",
        f"- date: {slug[:10]}\n",
    ).replace(
        "\n# Decision:",
        (
            f"- v0-manifest: {manifest_path}\n"
            f"- v0-baseline-sha256: {baseline_sha256}\n"
            f"- v0-cutover-date: {cutover_date}\n"
            "\n# Decision:"
        ),
    )


def _legacy_v0_decision_record(
    *,
    status: str = "accepted",
    identity_line: str | None = None,
    extra_header: str = "",
    body: str = "Legacy decision body.\n",
) -> str:
    identity = f"{identity_line}\n" if identity_line else ""
    return f"---\nstatus: {status}\n{identity}{extra_header}---\n{body}"


def _decision_v0_baseline(entries: list[dict[str, str]]) -> str:
    payload = b"".join(
        entry["path"].encode("utf-8")
        + b"\0"
        + entry["sha256"].encode("ascii")
        + b"\n"
        for entry in sorted(entries, key=lambda row: row["path"])
    )
    return hashlib.sha256(payload).hexdigest().upper()


def _initial_v0_public_fixture(tmp_path: Path, *, names=("alpha", "beta"), status="accepted"):
    module = load_module()
    root = tmp_path / "repo"
    for name in reversed(names):
        write(root / "work-items" / "decisions" / f"2026-08-01-{name}.md", _legacy_v0_decision_record(status=status))
    write(root / "work-items" / "README.md", "Independent static guide.\n")
    captured = module.admit_current_decision_v0(root)
    policy_slug = "2026-08-18-present-owner-policy"
    policy = root / "work-items" / "decisions" / f"{policy_slug}.md"
    # Synthetic current-owner acceptance for this exact public capture; no manifest fixture writer.
    write(policy, _accepted_v0_policy_record(policy_slug, captured["baselineSha256"]) +
          "\nSynthetic current acceptance of preserved bytes; old approval/review facts are unknown.\n")
    request = {"policy_decision": policy_slug, "cutover_date": "2026-08-18",
               "expected_baseline_sha256": captured["baselineSha256"],
               "expected_policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest().upper(),
               "operation_id": "initial-owner-case", "receipt": ".scratch/initial-owner-receipt.json", "apply": True}
    return module, root, captured, request


def _initial_v0_cli_args(root: Path, request: dict) -> list[str]:
    return ["admit-current-decision-v0", "--root", str(root), "--apply", *[
        part for key, value in request.items() if key != "apply" for part in ("--" + key.replace("_", "-"), str(value))]]


@pytest.mark.parametrize("names,status", [(("alpha", "beta", "gamma", "delta", "epsilon"), "accepted"), (("unusual", "another", "third"), "historical-pending")])
def test_initial_v0_public_cli_complete_capture_apply_and_replay(tmp_path: Path, names, status) -> None:
    module, root, captured, request = _initial_v0_public_fixture(tmp_path, names=names, status=status)
    before = {path: path.read_bytes() for path in (root / "work-items").rglob("*") if path.is_file()}
    preview = module.admit_current_decision_v0(root, policy_decision=request["policy_decision"], cutover_date=request["cutover_date"])
    assert preview["state"] == "prepared" and preview["receipt"] is None
    assert not (root / "work-items" / "decision-v0-compatibility.json").exists()
    applied = run_cli(*_initial_v0_cli_args(root, request))
    assert applied.returncode == 0, applied.stdout
    result = json.loads(applied.stdout)
    assert result["state"] == "applied" and result["entries"] == captured["entries"]
    assert [row["path"] for row in result["entries"]] == sorted(row["path"] for row in result["entries"])
    assert all(path.read_bytes() == data for path, data in before.items())
    admitted = module._preflight_current_decision_v0(root)
    assert len(admitted) == len(names)
    if status == "historical-pending":
        assert all(row.admitted_current_status is None for row in admitted.values())
    receipt = root / request["receipt"]
    receipt_before = receipt.read_bytes()
    assert json.loads(receipt_before)["settlement"] == "initial"
    write(root / "work-items" / "README.md", "Legitimate independently advanced static guide.\n")
    assert module.admit_current_decision_v0(root / "work-items", **request)["state"] == "replayed"
    assert receipt.read_bytes() == receipt_before
    assert not receipt.with_name(receipt.name + ".pending").exists()
    assert not list(root.rglob("*.tmp"))


def test_initial_v0_capture_unknown_and_degraded_apply_inputs(tmp_path: Path) -> None:
    module, root, captured, request = _initial_v0_public_fixture(tmp_path)
    assert captured["policy"] is None and captured["cutoverDate"] is None
    manifest = root / "work-items" / "decision-v0-compatibility.json"
    for delta in ({"apply": 1}, {"apply": "true"}, {"expected_policy_sha256": None},
                  {"expected_baseline_sha256": ""}, {"expected_baseline_sha256": 0},
                  {"operation_id": None}, {"receipt": "../foreign.json"}, {"cutover_date": "2026-02-30"}):
        with pytest.raises(module.LifecycleError) as failure:
            module.admit_current_decision_v0(root, **{**request, **delta})
        assert failure.value.failure_id == "WI-DECISION-V0-ADMISSION-INPUT"
        assert not manifest.exists()
    missing = module.admit_current_decision_v0(root, policy_decision="2026-08-18-missing", cutover_date="2026-08-18")
    assert missing["state"] == "prepared" and missing["policy"]["sha256"] is None


@pytest.mark.parametrize("cause", ["late-member", "policy-bytes", "not-accepted", "wrong-binding", "missing-status", "same-day"])
def test_initial_v0_strict_stale_authority_and_historical_guards(tmp_path: Path, cause: str) -> None:
    module, root, captured, request = _initial_v0_public_fixture(tmp_path)
    policy = root / "work-items" / "decisions" / f"{request['policy_decision']}.md"
    if cause == "late-member":
        write(policy.parent / "2026-08-01-late.md", _legacy_v0_decision_record())
    elif cause == "policy-bytes":
        policy.write_bytes(policy.read_bytes() + b"Changed owner scope.\n")
    elif cause in ("not-accepted", "wrong-binding"):
        text = policy.read_text(encoding="utf-8").replace("- status: accepted", "- status: proposed") if cause == "not-accepted" else policy.read_text(encoding="utf-8").replace("- v0-cutover-date: 2026-08-18", "- v0-cutover-date: 2026-08-19")
        write(policy, text)
        request["expected_policy_sha256"] = hashlib.sha256(policy.read_bytes()).hexdigest().upper()
    elif cause == "missing-status":
        source = policy.parent / "2026-08-01-alpha.md"
        source.write_bytes(b"---\n---\nHistorical body.\n")
        recapture = module.admit_current_decision_v0(root)
        request["expected_baseline_sha256"] = recapture["baselineSha256"]
        write(policy, _accepted_v0_policy_record(request["policy_decision"], recapture["baselineSha256"]))
        request["expected_policy_sha256"] = hashlib.sha256(policy.read_bytes()).hexdigest().upper()
    else:
        request["cutover_date"] = "2026-08-01"
        write(policy, _accepted_v0_policy_record(request["policy_decision"], captured["baselineSha256"], cutover_date="2026-08-01"))
        request["expected_policy_sha256"] = hashlib.sha256(policy.read_bytes()).hexdigest().upper()
    with pytest.raises(module.LifecycleError):
        module.admit_current_decision_v0(root, **request)
    assert not (root / "work-items" / "decision-v0-compatibility.json").exists()
    assert not (root / request["receipt"]).exists()


@pytest.mark.parametrize("collision", ["manifest", "receipt"])
def test_initial_v0_create_only_foreign_collision_preserved(tmp_path: Path, monkeypatch, collision: str) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(tmp_path)
    original = module.LifecycleWriteTarget.promote_create
    foreign = None
    def appear(target, image):
        nonlocal foreign
        selected = target.leaf == (module.DECISION_V0_MANIFEST if collision == "manifest" else Path(request["receipt"]).name)
        if selected:
            foreign = target.path
            # Equal bytes still have a foreign identity and must not be replaced or deleted.
            foreign.write_bytes(base64.b64decode(image["data"]))
        return original(target, image)
    monkeypatch.setattr(module.LifecycleWriteTarget, "promote_create", appear)
    with pytest.raises(module.LifecycleError):
        module.admit_current_decision_v0(root, **request)
    assert foreign is not None and foreign.exists()
    pending = root / (request["receipt"] + ".pending")
    assert pending.exists()
    before = {path: path.read_bytes() for path in (root / "work-items", root / ".scratch") for path in path.rglob("*") if path.is_file()}
    monkeypatch.setattr(module.LifecycleWriteTarget, "promote_create", original)
    with pytest.raises(module.LifecycleError):
        module.admit_current_decision_v0(root, **request)
    assert all(path.read_bytes() == data for path, data in before.items())


def test_initial_v0_caught_pre_receipt_compensation_restores_absence(tmp_path: Path, monkeypatch) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(tmp_path)
    original = module.LifecycleWriteTarget.stage_create
    def fail_receipt(target, data):
        if target.leaf == Path(request["receipt"]).name:
            raise RuntimeError("synthetic receipt-stage failure")
        return original(target, data)
    monkeypatch.setattr(module.LifecycleWriteTarget, "stage_create", fail_receipt)
    with pytest.raises(RuntimeError, match="synthetic receipt-stage failure"):
        module.admit_current_decision_v0(root, **request)
    assert not (root / "work-items" / "decision-v0-compatibility.json").exists()
    assert not (root / (request["receipt"] + ".pending")).exists()
    assert not list(root.rglob("*.tmp"))


def _initial_v0_interrupt_child(root: Path, request: dict, point: str) -> None:
    code = '''import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location("initial_v0_child",sys.argv[1])
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
root=Path(sys.argv[2]);request=json.loads(sys.argv[3]);point=sys.argv[4]
original=m.LifecycleWriteTarget.promote_create
def pause(target,image):
    selected=(point=="pending" and target.leaf==Path(request["receipt"]+".pending").name) or (point=="manifest" and target.leaf==m.DECISION_V0_MANIFEST) or (point in ("receipt-stage","receipt") and target.leaf==Path(request["receipt"]).name)
    if selected and point=="receipt-stage":
        print("OWNED_INTERRUPT_READY",flush=True);sys.stdin.read()
    result=original(target,image)
    if selected and point!="receipt-stage":
        print("OWNED_INTERRUPT_READY",flush=True);sys.stdin.read()
    return result
m.LifecycleWriteTarget.promote_create=pause
sys.exit(m.main(["admit-current-decision-v0","--root",str(root),"--apply"]+[part for key,value in request.items() if key!="apply" for part in ("--"+key.replace("_","-"),str(value))]))
'''
    # Popen retains the creator's native process handle; no PID discovery or ancestry kill.
    child = subprocess.Popen([sys.executable, "-u", "-c", code, str(SCRIPT), str(root), json.dumps(request), point], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            marker = executor.submit(child.stdout.readline)
            try:
                assert marker.result(timeout=20).strip() == "OWNED_INTERRUPT_READY"
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=10)
        assert child.returncode != 0
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)


@pytest.mark.parametrize("point", ["pending", "manifest", "receipt-stage", "receipt"])
def test_initial_v0_abrupt_owned_process_death_fresh_public_reentry(tmp_path: Path, point: str) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(tmp_path)
    before = {path: path.read_bytes() for path in (root / "work-items").rglob("*") if path.is_file()}
    _initial_v0_interrupt_child(root, request, point)
    pending = root / (request["receipt"] + ".pending")
    assert pending.exists()
    assert (root / "work-items" / "decision-v0-compatibility.json").exists() == (point != "pending")
    receipt = root / request["receipt"]
    historical = receipt.read_bytes() if receipt.exists() else None
    resumed = run_cli(*_initial_v0_cli_args(root, request))
    assert resumed.returncode == 0, resumed.stdout
    result = json.loads(resumed.stdout)
    assert result["state"] == ("replayed" if point == "receipt" else "recovered")
    actual = json.loads(receipt.read_bytes())
    assert actual["settlement"] == ("initial" if point == "receipt" else "recovered")
    assert actual["readback"] == {"manifestVerified": True, "legacyBytesUnchanged": True, "policyUnchanged": True}
    if historical is not None:
        assert receipt.read_bytes() == historical
    assert all(path.read_bytes() == data for path, data in before.items())
    assert module._preflight_current_decision_v0(root)
    assert not pending.exists() and not list(root.rglob("*.tmp"))


@pytest.mark.parametrize("damage", ["request", "corrupt-pending", "lost-pending", "foreign-equal-manifest", "foreign-policy", "lost-receipt-stage"])
def test_initial_v0_interrupted_foreign_or_incomplete_state_preserved(tmp_path: Path, damage: str) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(tmp_path)
    _initial_v0_interrupt_child(root, request, "receipt-stage")
    pending = root / (request["receipt"] + ".pending")
    if damage == "request":
        request["operation_id"] = "wrong-operation"
    elif damage == "corrupt-pending":
        pending.write_bytes(b'{"schemaVersion":1,"schemaVersion":1}')
    elif damage == "lost-pending":
        pending.unlink()
    elif damage == "foreign-equal-manifest":
        manifest = root / "work-items" / "decision-v0-compatibility.json"
        other = manifest.with_suffix(".foreign")
        other.write_bytes(manifest.read_bytes())
        os.replace(other, manifest)
    elif damage == "foreign-policy":
        policy = root / "work-items" / "decisions" / f"{request['policy_decision']}.md"
        policy.write_bytes(policy.read_bytes() + b"Changed owner scope.\n")
    else:
        state = json.loads(pending.read_bytes())
        stage = next(row for row in state["outputs"] if row["path"] == request["receipt"])["ownedAfter"]["stagePath"]
        (root / stage).unlink()
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    resumed = run_cli(*_initial_v0_cli_args(root, request))
    assert resumed.returncode != 0 and "WI-DECISION-V0-ADMISSION-" in resumed.stdout
    assert all(path.exists() and path.read_bytes() == data for path, data in before.items())
    assert not (root / request["receipt"]).exists()


def test_initial_v0_empty_capture_never_admits_empty_manifest(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    empty = module.admit_current_decision_v0(root)
    assert empty == {"schemaVersion": 1, "state": "captured", "entries": [], "baselineSha256": None,
                     "policy": None, "cutoverDate": None, "manifest": None, "receipt": None}
    assert module._preflight_current_decision_v0(root) == {}
    with pytest.raises(module.LifecycleError) as failure:
        module.admit_current_decision_v0(root, policy_decision="2026-08-18-empty-policy", cutover_date="2026-08-18",
            expected_baseline_sha256="A" * 64, expected_policy_sha256="B" * 64, operation_id="empty", receipt=".scratch/empty.json", apply=True)
    assert failure.value.failure_id == "WI-DECISION-V0-ADMISSION-EMPTY"


def test_initial_v0_lost_manifest_stage_releases_only_bound_pending_then_refuses(tmp_path: Path) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(tmp_path)
    _initial_v0_interrupt_child(root, request, "pending")
    pending = root / (request["receipt"] + ".pending")
    record = json.loads(pending.read_bytes())
    stage = next(row for row in record["outputs"] if row["path"].startswith("work-items/"))["ownedAfter"]["stagePath"]
    (root / stage).unlink()
    with pytest.raises(module.LifecycleError) as failure:
        module.admit_current_decision_v0(root, **request)
    assert failure.value.failure_id == "WI-DECISION-V0-ADMISSION-RECOVERY-INCOMPLETE"
    assert not pending.exists() and not (root / "work-items" / "decision-v0-compatibility.json").exists()
    assert module.admit_current_decision_v0(root, **request)["state"] == "applied"


def test_initial_v0_replay_after_real_retirement_and_present_failure(tmp_path: Path) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(tmp_path, names=("terminal",), status="superseded")
    result = module.admit_current_decision_v0(root, **request)
    receipt = root / request["receipt"]
    receipt_before = receipt.read_bytes()
    source = root / "work-items" / "decisions" / "2026-08-01-terminal.md"
    instant = "2026-10-10T00:00:00Z"
    inventory = root / ".scratch" / "retirement-input.json"
    module.refresh_readme(root, allow_marker_bootstrap=True)
    write(inventory, json.dumps({"reference": "decision:2026-08-01-terminal", "expectedSourceSha256": hashlib.sha256(source.read_bytes()).hexdigest().upper(),
          "archivedAt": instant, "rationale": "Current synthetic owner confirms superseded historical bytes.",
          "evidence": "Synthetic exact source and current terminal status.", "incomingLinks": []}))
    archived = module.migrate_legacy(root, "decision:2026-08-01-terminal", incoming_links_inventory=inventory)
    assert archived.is_file() and not source.exists()
    manifest = root / "work-items" / "decision-v0-compatibility.json"
    assert json.loads(manifest.read_bytes())["schemaVersion"] == 2
    manifest_before = manifest.read_bytes()
    assert module.admit_current_decision_v0(root, **request)["state"] == "replayed"
    assert manifest.read_bytes() == manifest_before and receipt.read_bytes() == receipt_before
    # A real historical receipt cannot make a broken present reader pass.
    manifest.write_bytes(b"{}")
    with pytest.raises(module.LifecycleError) as failure:
        module.admit_current_decision_v0(root, **request)
    assert failure.value.failure_id == "WI-DECISION-V0-MANIFEST-INVALID"
    assert manifest.read_bytes() == b"{}" and receipt.read_bytes() == receipt_before


def test_initial_v0_public_producer_then_ordinary_audit_and_stale_readme(tmp_path: Path) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(tmp_path)
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    before = readme.read_bytes()
    with pytest.raises(module.LifecycleError) as original:
        module.audit(root)
    assert original.value.failure_id == "WI-DECISION-V0-MANIFEST-MISSING"
    module.admit_current_decision_v0(root, **request)
    module.audit_categories(root)
    module.audit(root)
    assert readme.read_bytes() == before
    readme.write_bytes(before.replace(module.README_END.encode(), b"independently stale derived board\n" + module.README_END.encode()))
    stale = readme.read_bytes()
    assert module.admit_current_decision_v0(root, **request)["state"] == "replayed"
    with pytest.raises(module.LifecycleError) as ordinary:
        module.audit(root)
    assert ordinary.value.failure_id == "WI-README-STALE"
    assert readme.read_bytes() == stale


@pytest.mark.parametrize("damage", ["pending-scalar", "replay-pending-scalar", "foreign-stage-bytes", "foreign-stage-identity", "pending-overcap", "receipt-overcap"])
def test_initial_v0_preservation_carrier_and_stage_states(tmp_path: Path, damage: str) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(tmp_path)
    pending = root / (request["receipt"] + ".pending")
    if damage == "replay-pending-scalar" or damage == "receipt-overcap":
        module.admit_current_decision_v0(root, **request)
    if damage.endswith("pending-scalar"):
        pending.write_bytes(b"null")
    elif damage.startswith("foreign-stage"):
        _initial_v0_interrupt_child(root, request, "pending")
        record = json.loads(pending.read_bytes())
        image = next(row for row in record["outputs"] if row["path"].startswith("work-items/"))["ownedAfter"]
        stage = root / image["stagePath"]
        if damage == "foreign-stage-bytes":
            stage.write_bytes(stage.read_bytes() + b"Changed unowned bytes.\n")
        else:
            replacement = stage.with_suffix(".replacement")
            replacement.write_bytes(stage.read_bytes())
            previous_identity = stage.stat().st_ino
            os.replace(replacement, stage)
            assert stage.stat().st_ino != previous_identity
    else:
        if damage == "pending-overcap":
            _initial_v0_interrupt_child(root, request, "manifest")
        carrier = pending if damage == "pending-overcap" else root / request["receipt"]
        carrier.write_bytes(b" " * (module._INITIAL_V0_MAX_BYTES + 1))
    before = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    with pytest.raises(module.LifecycleError) as refused:
        module.admit_current_decision_v0(root, **request)
    assert {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()} == before
    if damage.endswith("overcap"):
        assert refused.value.failure_id == "WI-LIFECYCLE-WRITE-BOUNDARY"
        assert isinstance(refused.value.__cause__, OSError)
    elif damage.endswith("pending-scalar"):
        assert refused.value.failure_id == "WI-DECISION-V0-ADMISSION-RECOVERY-INVALID"
    else:
        assert refused.value.failure_id == "WI-DECISION-V0-ADMISSION-RECOVERY-CONFLICT"


@pytest.mark.parametrize("fault", ["aggregate-cap", "native-identity", "stage-readback", "manifest-at-receipt-stage", "manifest-after-pending-update", "manifest-after-receipt-promotion"])
def test_initial_v0_owned_stage_lifetime_and_settlement(tmp_path: Path, monkeypatch, fault: str) -> None:
    module, root, _captured, request = _initial_v0_public_fixture(tmp_path)
    before = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    if fault == "aggregate-cap":
        source = root / "work-items" / "decisions" / "2026-08-01-alpha.md"
        source.write_bytes(b"---\nstatus: accepted\n---\n" + b"x" * (3200 * 1024) + b"\n")
        captured = module.admit_current_decision_v0(root)
        policy = root / "work-items" / "decisions" / f"{request['policy_decision']}.md"
        write(policy, _accepted_v0_policy_record(request["policy_decision"], captured["baselineSha256"]))
        request["expected_baseline_sha256"] = captured["baselineSha256"]
        request["expected_policy_sha256"] = hashlib.sha256(policy.read_bytes()).hexdigest().upper()
        before = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        with pytest.raises(module.LifecycleError) as refused:
            module.admit_current_decision_v0(root, **request)
        assert refused.value.failure_id == "WI-DECISION-V0-ADMISSION-RECOVERY-INVALID"
        assert {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()} == before
    elif fault in ("native-identity", "stage-readback"):
        original_open = module.LifecycleWriteTarget._file
        original_identity = module.LifecycleWriteTarget._identity
        original_image = module.LifecycleWriteTarget.owned_image
        original_close = module.LifecycleWriteTarget._close
        created, closed = [], []
        def capture(target, leaf, **kwargs):
            handle = original_open(target, leaf, **kwargs)
            if kwargs.get("create"):
                created.append((target, handle, leaf))
            return handle
        def fail_identity(target, handle):
            if fault == "native-identity" and any(owned == handle for _target, owned, _leaf in created):
                raise OSError("synthetic native stage identity acquisition failure")
            return original_identity(target, handle)
        def fail_readback(target, leaf=None, **kwargs):
            if fault == "stage-readback" and any(owned_target is target and owned_leaf == leaf for owned_target, _handle, owned_leaf in created):
                raise OSError("synthetic native stage readback failure")
            return original_image(target, leaf, **kwargs)
        def observe_close(target, handle):
            closed.append(handle)
            return original_close(target, handle)
        monkeypatch.setattr(module.LifecycleWriteTarget, "_file", capture)
        monkeypatch.setattr(module.LifecycleWriteTarget, "_identity", fail_identity)
        monkeypatch.setattr(module.LifecycleWriteTarget, "owned_image", fail_readback)
        monkeypatch.setattr(module.LifecycleWriteTarget, "_close", observe_close)
        try:
            with pytest.raises(OSError, match="synthetic native stage"):
                module.admit_current_decision_v0(root, **request)
            assert len(created) == 1
            assert all(handle in closed for _target, handle, _leaf in created)
            assert {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()} == before
        finally:
            # Harness release prevents a failed assertion from escaping its exact
            # creator handle; it cannot make a product lifetime assertion pass.
            for target, handle, _leaf in created:
                if handle not in closed:
                    original_close(target, handle)
    else:
        manifest = root / "work-items" / "decision-v0-compatibility.json"
        foreign_bytes, foreign_identity = None, None
        def replace_manifest():
            nonlocal foreign_bytes, foreign_identity
            old_identity = manifest.stat().st_ino
            foreign_bytes = manifest.read_bytes()
            replacement = manifest.with_suffix(".replacement")
            replacement.write_bytes(foreign_bytes)
            foreign_identity = replacement.stat().st_ino
            assert old_identity != foreign_identity
            os.replace(replacement, manifest)
        if fault == "manifest-at-receipt-stage":
            original = module.LifecycleWriteTarget.stage_create
            def drift(target, data):
                if target.path == root / request["receipt"]:
                    replace_manifest()
                return original(target, data)
            monkeypatch.setattr(module.LifecycleWriteTarget, "stage_create", drift)
        elif fault == "manifest-after-pending-update":
            original = module.LifecycleWriteTarget.publish
            def drift(target, data):
                result = original(target, data)
                if target.path == root / (request["receipt"] + ".pending"):
                    replace_manifest()
                return result
            monkeypatch.setattr(module.LifecycleWriteTarget, "publish", drift)
        else:
            original = module.LifecycleWriteTarget.promote_create
            def drift(target, image):
                result = original(target, image)
                if target.path == root / request["receipt"]:
                    replace_manifest()
                return result
            monkeypatch.setattr(module.LifecycleWriteTarget, "promote_create", drift)
        with pytest.raises(module.LifecycleError) as refused:
            module.admit_current_decision_v0(root, **request)
        assert refused.value.failure_id == "WI-DECISION-V0-ADMISSION-RECOVERY-CONFLICT"
        assert manifest.stat().st_ino == foreign_identity and manifest.read_bytes() == foreign_bytes
        assert (root / (request["receipt"] + ".pending")).exists()
        assert (root / request["receipt"]).exists() == (fault == "manifest-after-receipt-promotion")


def _write_decision_v0_manifest(
    root: Path,
    entries: list[dict[str, str]],
    *,
    policy_slug: str = "2026-08-18-current-decision-schema-versioned-read-compatibility",
    cutover_date: str = "2026-08-18",
) -> Path:
    ordered = sorted(entries, key=lambda row: row["path"])
    baseline = _decision_v0_baseline(ordered)
    write(
        root / "work-items" / "decisions" / f"{policy_slug}.md",
        _accepted_v0_policy_record(
            policy_slug,
            baseline,
            cutover_date=cutover_date,
        ),
    )
    target = root / "work-items" / "decision-v0-compatibility.json"
    write(
        target,
        json.dumps(
            {
                "schemaVersion": 1,
                "policyDecision": policy_slug,
                "cutoverDate": cutover_date,
                "baselineSha256": baseline,
                "entries": ordered,
            },
            indent=2,
        )
        + "\n",
    )
    return target


def test_migrate_legacy_v0_preserves_frozen_bytes_with_external_archive_evidence(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-superseded-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    source_bytes = _legacy_v0_decision_record(
        status="superseded", identity_line=f"id: {slug}"
    ).encode("utf-8")
    source.parent.mkdir(parents=True)
    source.write_bytes(source_bytes)
    digest = hashlib.sha256(source_bytes).hexdigest().upper()
    manifest = _write_decision_v0_manifest(
        root, [{"path": source.name, "sha256": digest, "state": "admitted"}]
    )
    policy = root / "work-items" / "decisions" / (
        "2026-08-18-current-decision-schema-versioned-read-compatibility.md"
    )
    policy_before = policy.read_bytes()
    baseline_before = json.loads(manifest.read_text(encoding="utf-8"))["baselineSha256"]
    archived_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}",
        "expectedSourceSha256": digest,
        "archivedAt": archived_at,
        "rationale": "Accepted successor supersedes this historical decision.",
        "evidence": "Synthetic successor relation and review receipt.",
        "incomingLinks": [],
    }))

    archived = module.migrate_legacy(
        root, f"decision:{slug}", incoming_links_inventory=inventory
    )

    assert archived == root / "work-items" / "decisions" / "archive" / archived_at[:7] / source.name
    assert archived.read_bytes() == source_bytes
    assert not source.exists()
    assert policy.read_bytes() == policy_before
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == 2
    assert payload["baselineSha256"] == baseline_before
    assert payload["entries"] == [{
        "path": source.name, "sha256": digest, "state": "retired",
        "archiveEvidence": {
            "archivePath": f"decisions/archive/{archived_at[:7]}/{source.name}",
            "archivedAt": archived_at,
            "rationale": "Accepted successor supersedes this historical decision.",
            "evidence": "Synthetic successor relation and review receipt.",
        },
    }]
    module.audit_categories(root)


def test_reopen_evidenced_archived_v0_uses_manifest_without_editing_archive(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-old-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded by successor.",
        "evidence": "Synthetic accepted review.", "incomingLinks": [],
    }))
    archived = module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
    assert module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory) == archived
    successor_slug = "2026-09-01-successor"
    successor_data = _current_decision_record(
        successor_slug, status="accepted", body=f"Reopens: {slug}\n"
    ).encode("utf-8")

    successor = module.reopen_category_record(
        root, f"decision:{slug}", successor_slug, successor_data
    )

    assert successor.read_bytes() == successor_data
    assert archived.read_bytes() == frozen


def test_migrate_legacy_v0_repairs_mutable_physical_link(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-linked-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    consumer = root / "work-items" / "bugs" / "consumer.md"
    original_link = f"../decisions/{source.name}"
    write(consumer, f"[historical decision]({original_link})\n")
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.",
        "incomingLinks": [{
            "consumer": "bugs/consumer.md", "kind": "physical", "value": original_link,
        }],
    }))

    archived = module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)

    assert archived.read_bytes() == frozen
    assert consumer.read_text(encoding="utf-8") == (
        f"[historical decision](../decisions/archive/{instant[:7]}/{source.name})\n"
    )


def test_migrate_legacy_v0_rolls_back_after_readme_failure(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-rollback-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    source_before = source.read_bytes()
    digest = hashlib.sha256(source_before).hexdigest().upper()
    manifest = _write_decision_v0_manifest(
        root, [{"path": source.name, "sha256": digest, "state": "admitted"}]
    )
    consumer = root / "work-items" / "bugs" / "consumer.md"
    original_link = f"../decisions/{source.name}"
    write(consumer, f"[historical decision]({original_link})\n")
    module.refresh_readme(root, allow_marker_bootstrap=True)
    before = (manifest.read_bytes(), consumer.read_bytes(), (root / "work-items" / "README.md").read_bytes())
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.",
        "incomingLinks": [{
            "consumer": "bugs/consumer.md", "kind": "physical", "value": original_link,
        }],
    }))
    with patch.object(module, "refresh_readme", side_effect=module.LifecycleError("WI-README-STALE", "injected")):
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)

    assert caught.exception.failure_id == "WI-README-STALE"
    assert source.read_bytes() == source_before
    assert not (root / "work-items" / "decisions" / "archive" / instant[:7] / source.name).exists()
    assert (manifest.read_bytes(), consumer.read_bytes(), (root / "work-items" / "README.md").read_bytes()) == before


def test_migrate_legacy_v0_rejects_missing_evidence_drift_and_v1_retirement(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-01-refused-v0"
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases = (
        ("missing-manifest", "WI-DECISION-V0-MANIFEST-MISSING"),
        ("source-drift", "WI-DECISION-V0-HASH-MISMATCH"),
        ("missing-evidence", "WI-DECISION-V0-ARCHIVE-EVIDENCE"),
        ("wrong-month", "WI-DECISION-V0-ARCHIVE-EVIDENCE"),
        ("old-retirement", "WI-DECISION-V0-MANIFEST-INVALID"),
    )
    for name, failure_id in cases:
        root = tmp_path / name
        source = root / "work-items" / "decisions" / f"{slug}.md"
        write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
        frozen = source.read_bytes()
        digest = hashlib.sha256(frozen).hexdigest().upper()
        entries = [{"path": source.name, "sha256": digest, "state": "admitted"}]
        if name == "old-retirement":
            entries.insert(0, {"path": "2026-07-01-retired.md", "sha256": "A" * 64, "state": "retired"})
        manifest = None if name == "missing-manifest" else _write_decision_v0_manifest(root, entries)
        if name == "source-drift":
            source.write_bytes(frozen + b"drift")
        before_source = source.read_bytes()
        before_manifest = manifest.read_bytes() if manifest else None
        inventory = root / "incoming.json"
        write(inventory, json.dumps({
            "reference": f"decision:{slug}", "expectedSourceSha256": digest,
            "archivedAt": "2026-13-01T00:00:00Z" if name == "wrong-month" else instant,
            "rationale": "Superseded.",
            "evidence": "" if name == "missing-evidence" else "Synthetic review.",
            "incomingLinks": [],
        }))
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
        assert caught.exception.failure_id == failure_id, name
        assert source.read_bytes() == before_source
        assert (manifest.read_bytes() if manifest else None) == before_manifest
        assert not (root / "work-items" / "decisions" / "archive").exists()


def test_migrate_legacy_v0_rejects_archived_physical_consumer_without_move(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-immutable-link-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    manifest = _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    consumer = root / "work-items" / "decisions" / "archive" / "2026-08" / "old-consumer.md"
    href = f"../../{source.name}"
    write(consumer, f"[frozen history]({href})\n")
    before = (manifest.read_bytes(), consumer.read_bytes())
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.",
        "incomingLinks": [{
            "consumer": "decisions/archive/2026-08/old-consumer.md",
            "kind": "physical", "value": href,
        }],
    }))
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
    assert caught.exception.failure_id == "WI-LEGACY-LINK-UNMAPPED"
    assert source.read_bytes() == frozen
    assert (manifest.read_bytes(), consumer.read_bytes()) == before


def test_migrate_legacy_v0_compensates_failures_after_move_and_manifest(
    tmp_path: Path,
) -> None:
    module = load_module()
    for stage in ("manifest", "link"):
        root = tmp_path / stage
        slug = f"2026-08-01-{stage}-failure-v0"
        source = root / "work-items" / "decisions" / f"{slug}.md"
        write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
        frozen = source.read_bytes()
        digest = hashlib.sha256(frozen).hexdigest().upper()
        manifest = _write_decision_v0_manifest(
            root, [{"path": source.name, "sha256": digest, "state": "admitted"}]
        )
        consumer = root / "work-items" / "bugs" / "consumer.md"
        href = f"../decisions/{source.name}"
        write(consumer, f"[history]({href})\n")
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme = root / "work-items" / "README.md"
        before = (manifest.read_bytes(), consumer.read_bytes(), readme.read_bytes())
        instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        inventory = root / "incoming.json"
        write(inventory, json.dumps({
            "reference": f"decision:{slug}", "expectedSourceSha256": digest,
            "archivedAt": instant, "rationale": "Superseded.",
            "evidence": "Synthetic review.",
            "incomingLinks": [{"consumer": "bugs/consumer.md", "kind": "physical", "value": href}],
        }))
        fail_path = manifest if stage == "manifest" else consumer
        original_atomic_write = module._atomic_write
        failed = False

        def fail_once(path, data):
            nonlocal failed
            if Path(path) == fail_path and not failed:
                failed = True
                raise OSError(f"injected {stage} failure")
            return original_atomic_write(path, data)

        with patch.object(module, "_atomic_write", side_effect=fail_once):
            with unittest.TestCase().assertRaises(OSError):
                module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
        assert failed
        assert source.read_bytes() == frozen
        assert not (root / "work-items" / "decisions" / "archive" / instant[:7] / source.name).exists()
        assert (manifest.read_bytes(), consumer.read_bytes(), readme.read_bytes()) == before


def test_migrate_legacy_v0_removes_only_new_empty_archive_parents_on_failure(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-parent-cleanup-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    manifest = _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    manifest_before = manifest.read_bytes()
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.", "incomingLinks": [],
    }))
    archive_root = root / "work-items" / "decisions" / "archive"
    archive_month_path = archive_root / instant[:7]
    original_mkdir = Path.mkdir

    def fail_after_month_creation(path, mode=0o777, parents=False, exist_ok=False):
        original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)
        if Path(path) == archive_month_path:
            raise OSError("injected interruption immediately after archive parent creation")

    with patch.object(Path, "mkdir", fail_after_month_creation):
        with unittest.TestCase().assertRaises(OSError):
            module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)

    assert source.read_bytes() == frozen
    assert manifest.read_bytes() == manifest_before
    assert not archive_month_path.exists()
    assert not archive_root.exists()


def test_migrate_legacy_v0_keeps_preexisting_empty_archive_parents_on_failure(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-existing-parent-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    manifest = _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    manifest_before = manifest.read_bytes()
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    archive_month_path = root / "work-items" / "decisions" / "archive" / instant[:7]
    archive_month_path.mkdir(parents=True)
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.", "incomingLinks": [],
    }))
    original_atomic_write = module._atomic_write
    failed = False

    def fail_manifest_once(path, data):
        nonlocal failed
        if Path(path) == manifest and not failed:
            failed = True
            raise OSError("injected manifest failure")
        return original_atomic_write(path, data)

    with patch.object(module, "_atomic_write", side_effect=fail_manifest_once):
        with unittest.TestCase().assertRaises(OSError):
            module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
    assert failed
    assert source.read_bytes() == frozen
    assert manifest.read_bytes() == manifest_before
    assert archive_month_path.is_dir()
    assert not any(archive_month_path.iterdir())


def test_decision_v0_v2_retirement_rejects_wrong_month_and_archive_hash(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-archive-bound-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()
    manifest = _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.", "incomingLinks": [],
    }))
    archived = module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
    frozen_manifest = manifest.read_bytes()
    payload = json.loads(frozen_manifest)
    payload["entries"][0]["archiveEvidence"]["archivePath"] = (
        f"decisions/archive/2000-01/{source.name}"
    )
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with unittest.TestCase().assertRaises(module.LifecycleError) as wrong_month:
        module.audit_categories(root)
    assert wrong_month.exception.failure_id == "WI-DECISION-V0-MANIFEST-INVALID"
    manifest.write_bytes(frozen_manifest)
    archived.write_bytes(archived.read_bytes() + b"drift")
    with unittest.TestCase().assertRaises(module.LifecycleError) as wrong_hash:
        module.audit_categories(root)
    assert wrong_hash.exception.failure_id == "WI-DECISION-V0-HASH-MISMATCH"


def _legacy_h1_decision_record(
    *,
    mode: str = "plain",
    status: str = "accepted",
    status_key: str = "status",
    extra_fields: tuple[tuple[str, str], ...] = (("owner", "architect"),),
    body: str = "Legacy H1 decision body.\n",
) -> str:
    fields = ((status_key, status), *extra_fields)
    if mode == "plain":
        prefix = "\n".join(f"{key}: {value}" for key, value in fields)
    elif mode == "bold":
        prefix = "\n".join(f"- **{key}:** {value}" for key, value in fields)
    else:
        raise AssertionError(f"unsupported test H1 mode: {mode}")
    return f"# Legacy H1 decision\n\n{prefix}\n\n{body}"


def _legacy_h1_list_decision_record(
    slug: str,
    *,
    status: str = "accepted",
    extra_fields: tuple[tuple[str, str], ...] = (
        ("work-item", "legacy-work-item"),
        ("owner", "architecture-reviewer"),
    ),
    body: str = "Legacy H1 list-metadata decision body.\n",
) -> str:
    fields = (("id", slug), ("status", status), *extra_fields)
    prefix = "\n".join(f"- {key}: {value}" for key, value in fields)
    return f"# Decision: Legacy list metadata\n\n{prefix}\n\n{body}"


def _accepted_h1_policy_record(
    slug: str,
    baseline_sha256: str,
    *,
    manifest_path: str = "work-items/decision-h1-compatibility.json",
    cutover_date: str = "2026-08-18",
) -> str:
    return _canonical_decision_record(slug).replace(
        "- status: proposed\n",
        "- status: accepted\n",
    ).replace(
        "- date: 2026-08-11\n",
        f"- date: {slug[:10]}\n",
    ).replace(
        "- supersedes: none\n",
        "- supersedes: 2026-08-18-current-decision-schema-versioned-read-compatibility\n",
    ).replace(
        "\n# Decision:",
        (
            f"- h1-manifest: {manifest_path}\n"
            f"- h1-baseline-sha256: {baseline_sha256}\n"
            f"- h1-cutover-date: {cutover_date}\n"
            "\n# Decision:"
        ),
    )


def _write_decision_h1_manifest(
    root: Path,
    entries: list[dict[str, str]],
    *,
    policy_slug: str = "2026-08-18-current-decision-schema-h1-read-compatibility",
    cutover_date: str = "2026-08-18",
) -> Path:
    ordered = sorted(entries, key=lambda row: row["path"])
    baseline = _decision_v0_baseline(ordered)
    write(
        root / "work-items" / "decisions" / f"{policy_slug}.md",
        _accepted_h1_policy_record(
            policy_slug,
            baseline,
            cutover_date=cutover_date,
        ),
    )
    target = root / "work-items" / "decision-h1-compatibility.json"
    write(
        target,
        json.dumps(
            {
                "schemaVersion": 1,
                "policyDecision": policy_slug,
                "cutoverDate": cutover_date,
                "baselineSha256": baseline,
                "entries": ordered,
            },
            indent=2,
        )
        + "\n",
    )
    return target


def test_decision_schema_rejects_noncanonical_current_records(tmp_path: Path) -> None:
    module = load_module()
    slug = "2026-08-11-schema-test"
    canonical = _canonical_decision_record(slug)
    cases = {
        "body-only-id": (
            canonical.replace(f"- id: {slug}\n", "").replace(
                "## Decision\n", f"## Decision\n- id: {slug}\n"
            ),
            "WI-DECISION-SCHEMA-INVALID",
        ),
        "proposer-is-not-decider": (
            canonical.replace("- decided-by: $architect\n", "- proposed-by: $architect\n"),
            "WI-DECISION-SCHEMA-INVALID",
        ),
        "duplicate-body-id": (
            canonical.replace("## Decision\n", f"## Decision\n- id: {slug}\n"),
            "WI-DECISION-FIELD-DUPLICATE",
        ),
        "wrong-id": (
            canonical.replace(f"- id: {slug}\n", "- id: 2026-08-11-other\n"),
            "WI-DECISION-IDENTITY-MISMATCH",
        ),
        "wrong-date": (
            canonical.replace("- date: 2026-08-11\n", "- date: 2026-08-10\n"),
            "WI-DECISION-IDENTITY-MISMATCH",
        ),
        "bare-leading-field": (
            canonical.replace("- context: schema-test\n", "context: schema-test\n"),
            "WI-DECISION-SCHEMA-INVALID",
        ),
        "decorated-leading-field": (
            canonical.replace(f"- id: {slug}\n", f"- **id**: {slug}\n"),
            "WI-DECISION-SCHEMA-INVALID",
        ),
        "empty-context": (
            canonical.replace("- context: schema-test\n", "- context:\n"),
            "WI-DECISION-SCHEMA-INVALID",
        ),
    }
    for name, (payload, failure_id) in cases.items():
        root = tmp_path / name
        write(root / "work-items" / "decisions" / f"{slug}.md", payload)
        try:
            module.audit_categories(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == failure_id, (name, exc.failure_id, str(exc))
        else:
            raise AssertionError(f"noncanonical current decision passed: {name}")


def test_decision_v1_list_keys_accept_ascii_case_variants_without_rewriting(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-11-ascii-case-keys"
    body = "# Decision: case fixture\n\nBody bytes stay exact.\n"
    canonical = _current_decision_record(slug, body=body).replace(
        "- superseded-by: none\n",
        "- superseded-by: none\n"
        "- terminal-at: 2026-08-11T12:00:00Z\n"
        "- rationale: keep terminal authority\n"
        "- evidence: preserve exact body\n"
        "- custom-field: Keep This Value\n",
    )
    variants = {
        "id": "ID",
        "status": "StAtUs",
        "date": "DATE",
        "decided-by": "Decided-By",
        "context": "CONTEXT",
        "supersedes": "SuperSedes",
        "superseded-by": "Superseded-By",
        "terminal-at": "TeRmInAl-At",
        "rationale": "Rationale",
        "evidence": "Evidence",
        "custom-field": "Custom-Field",
    }
    variant = canonical
    for old_name, new_name in variants.items():
        variant = variant.replace(f"- {old_name}:", f"- {new_name}:")

    canonical_record = module._parse_decision_record_text(canonical, slug)
    variant_record = module._parse_decision_record_text(variant, slug)
    assert dict(variant_record.fields) == dict(canonical_record.fields)
    assert variant_record.body_offset == canonical_record.body_offset
    assert variant.encode("utf-8")[variant_record.body_offset :] == canonical.encode(
        "utf-8"
    )[canonical_record.body_offset :]
    assert variant_record.fields["custom-field"] == "Keep This Value"
    terminal_variant = variant.replace(
        "- StAtUs: proposed\n", "- StAtUs: dropped\n"
    )
    assert module._validate_flat_terminal(
        module.CATEGORIES["decision"], terminal_variant.encode("utf-8")
    ) == "2026-08-11T12:00:00Z"

    root = tmp_path / "current"
    decision = root / "work-items" / "decisions" / f"{slug}.md"
    write(decision, variant)
    decision_before = decision.read_bytes()
    current_record = module._validate_current_decision_record(decision, slug)
    assert dict(current_record.fields) == dict(variant_record.fields)
    assert decision.read_bytes() == decision_before

    for malformed_key in ("id_name", "ïd", "id name", "id.name"):
        malformed = canonical.replace("- id:", f"- {malformed_key}:")
        with pytest.raises(module.LifecycleError) as caught:
            module._parse_decision_record_text(malformed, slug)
        assert caught.value.failure_id == "WI-DECISION-SCHEMA-INVALID"

    duplicate = canonical.replace(
        f"- id: {slug}\n", f"- id: {slug}\n- ID: {slug}\n"
    )
    with pytest.raises(module.LifecycleError) as duplicate_failure:
        module._parse_decision_record_text(duplicate, slug)
    assert duplicate_failure.value.failure_id == "WI-DECISION-FIELD-DUPLICATE"

    duplicate_body = canonical.replace(
        "# Decision: case fixture\n\n",
        f"# Decision: case fixture\n\n- DATE: {slug[:10]}\n\n",
    )
    with pytest.raises(module.LifecycleError) as body_duplicate_failure:
        module._parse_decision_record_text(duplicate_body, slug)
    assert body_duplicate_failure.value.failure_id == "WI-DECISION-FIELD-DUPLICATE"


def test_decision_v1_list_metadata_accepts_exact_h2_decision_body_heading(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-11-h2-body-heading"
    payload = _canonical_decision_record(slug).replace(
        f"# Decision: {slug}\n\n", ""
    )
    path = tmp_path / f"{slug}.md"
    write(path, payload)

    record = module._validate_current_decision_record(path, slug)

    assert record.format == "canonical-list-v1"
    assert record.body_offset == len(payload.split("## Decision\n", 1)[0].encode("utf-8"))


def test_decision_v1_first_heading_diagnostics_preserve_supported_formats_and_metadata_errors(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-11-first-heading-diagnostic"
    canonical = _canonical_decision_record(slug)

    h1_path = tmp_path / "h1" / f"{slug}.md"
    write(h1_path, canonical)
    assert module._validate_current_decision_record(h1_path, slug).format == "canonical-list-v1"

    h2_payload = canonical.replace(f"# Decision: {slug}\n\n", "")
    h2_path = tmp_path / "h2" / f"{slug}.md"
    write(h2_path, h2_payload)
    assert module._validate_current_decision_record(h2_path, slug).format == "canonical-list-v1"

    missing_metadata = canonical.replace("- context: schema-test\n", "")
    missing_metadata_path = tmp_path / "missing-metadata" / f"{slug}.md"
    write(missing_metadata_path, missing_metadata)
    with unittest.TestCase().assertRaises(module.LifecycleError) as metadata_caught:
        module._validate_current_decision_record(missing_metadata_path, slug)
    assert metadata_caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert str(metadata_caught.exception) == (
        f"decision:{slug} requires one non-empty leading 'context' field"
    )

    unsupported = canonical.replace(
        f"# Decision: {slug}", "## Acceptance gate"
    )
    unsupported_path = tmp_path / "unsupported" / f"{slug}.md"
    write(unsupported_path, unsupported)
    with unittest.TestCase().assertRaises(module.LifecycleError) as unsupported_caught:
        module._validate_current_decision_record(unsupported_path, slug)
    assert unsupported_caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert str(unsupported_caught.exception) == (
        f"decision:{slug} has unsupported first body heading at line 11: "
        "'## Acceptance gate'"
    )

    missing_heading = canonical.replace(
        f"# Decision: {slug}\n\n", "Decision title\n\n"
    ).replace("## Decision\n", "Decision body\n")
    missing_heading_path = tmp_path / "missing-heading" / f"{slug}.md"
    write(missing_heading_path, missing_heading)
    with unittest.TestCase().assertRaises(module.LifecycleError) as missing_heading_caught:
        module._validate_current_decision_record(missing_heading_path, slug)
    assert missing_heading_caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert str(missing_heading_caught.exception) == (
        f"decision:{slug} has no body heading"
    )

    long_heading = "## " + "x" * 300
    long_payload = canonical.replace(f"# Decision: {slug}", long_heading)
    long_path = tmp_path / "long-heading" / f"{slug}.md"
    write(long_path, long_payload)
    with unittest.TestCase().assertRaises(module.LifecycleError) as long_caught:
        module._validate_current_decision_record(long_path, slug)
    message = str(long_caught.exception)
    assert long_caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert len(message) < 300
    assert "x" * 200 not in message


def test_decision_v1_list_metadata_rejects_malformed_h2_body_headings(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-11-h2-body-heading"
    canonical = _canonical_decision_record(slug)
    cases = {
        "wrong-title": canonical.replace(f"# Decision: {slug}", "## Notes"),
        "nested-decision": canonical.replace(f"# Decision: {slug}", "### Decision"),
        "empty-heading": canonical.replace(f"# Decision: {slug}", "## "),
        "heading-before-required-metadata": canonical.replace(
            "- context: schema-test\n", "## Decision\n\n- context: schema-test\n"
        ),
    }

    for name, payload in cases.items():
        path = tmp_path / name / f"{slug}.md"
        write(path, payload)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._validate_current_decision_record(path, slug)
        assert caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID", name


def test_decision_schema_accepts_optional_multiline_and_legacy_archive(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-11-schema-test"
    write(
        tmp_path / "work-items" / "decisions" / f"{slug}.md",
        _canonical_decision_record(slug),
    )
    archived = (
        tmp_path
        / "work-items"
        / "decisions"
        / "archive"
        / "2026-08"
        / "legacy.md"
    )
    write(
        archived,
        "---\nstatus: dropped\n---\n\n# Decision: legacy\n\n"
        "Terminal-at: 2026-08-11T00:00:00Z\n"
        "Rationale: Historical bytes remain readable.\n"
        "Evidence: Synthetic archive fixture.\n",
    )

    assert module.audit_categories(tmp_path) == ()


def test_decision_v0_parser_accepts_closed_identity_matrix_and_preserves_v1(
    tmp_path: Path,
) -> None:
    module = load_module()
    cases = (
        (
            "2026-08-01-full-id",
            "id: 2026-08-01-full-id",
            {"id": "2026-08-01-full-id"},
        ),
        (
            "2026-08-02-undated-slug",
            "slug: undated-slug",
            {"slug": "undated-slug"},
        ),
        ("2026-08-03-no-identity", None, {}),
    )
    for slug, identity, expected_identity in cases:
        path = tmp_path / f"{slug}.md"
        write(
            path,
            _legacy_v0_decision_record(
                identity_line=identity,
                extra_header="owners:\n  - one\n  - two\n",
            ),
        )
        result = module._validate_current_decision_record(path, slug)
        assert result.format == "legacy-yaml-v0"
        assert result.raw_status == "accepted"
        assert result.admitted_current_status == "accepted"
        assert result.legacy_read_only is True
        assert result.fields["owners"] == ("one", "two")
        assert {key: result.fields[key] for key in expected_identity} == expected_identity
        assert "id" in result.fields if "id" in expected_identity else "id" not in result.fields
        assert "slug" in result.fields if "slug" in expected_identity else "slug" not in result.fields
        with unittest.TestCase().assertRaises(TypeError):
            result.fields["invented"] = "value"

    v1_slug = "2026-08-11-schema-test"
    v1_path = tmp_path / f"{v1_slug}.md"
    write(v1_path, _canonical_decision_record(v1_slug))
    v1 = module._validate_current_decision_record(v1_path, v1_slug)
    assert v1.format == "canonical-list-v1"
    assert v1.fields["id"] == v1_slug
    assert v1.raw_status == "proposed"
    assert v1.admitted_current_status == "proposed"
    assert v1.legacy_read_only is False


def test_decision_v0_parser_rejects_malformed_unknown_duplicate_and_identity(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-01-legacy"
    cases = {
        "unknown": ("## Decision\nstatus: accepted\n", "WI-DECISION-FORMAT-UNSUPPORTED"),
        "bom": ("\ufeff---\nstatus: accepted\n---\nbody\n", "WI-DECISION-FORMAT-UNSUPPORTED"),
        "missing-close": ("---\nstatus: accepted\nbody\n", "WI-DECISION-V0-SCHEMA-INVALID"),
        "blank-header": ("---\nstatus: accepted\n\n---\nbody\n", "WI-DECISION-V0-SCHEMA-INVALID"),
        "tab": ("---\nstatus:\taccepted\n---\nbody\n", "WI-DECISION-V0-SCHEMA-INVALID"),
        "nested": ("---\nstatus: accepted\n  child: value\n---\nbody\n", "WI-DECISION-V0-UNSUPPORTED-NESTING"),
        "empty-sequence": ("---\nstatus: accepted\nowners:\n  - \n---\nbody\n", "WI-DECISION-V0-UNSUPPORTED-NESTING"),
        "active-yaml": ("---\nstatus: &value accepted\n---\nbody\n", "WI-DECISION-V0-UNSUPPORTED-NESTING"),
        "duplicate": ("---\nstatus: accepted\nStatus: accepted\n---\nbody\n", "WI-DECISION-V0-FIELD-DUPLICATE"),
        "normalized-duplicate": ("---\nstatus: accepted\nowner name: one\nowner_name: two\n---\nbody\n", "WI-DECISION-V0-FIELD-DUPLICATE"),
        "wrong-id": ("---\nstatus: accepted\nid: 2026-08-01-other\n---\nbody\n", "WI-DECISION-IDENTITY-MISMATCH"),
        "dated-slug": (f"---\nstatus: accepted\nslug: {slug}\n---\nbody\n", "WI-DECISION-IDENTITY-MISMATCH"),
        "wrong-date": ("---\nstatus: accepted\ndate: 2026-08-02\n---\nbody\n", "WI-DECISION-DATE-MISMATCH"),
        "empty-body": ("---\nstatus: accepted\n---\n \n", "WI-DECISION-V0-SCHEMA-INVALID"),
    }
    for name, (payload, failure_id) in cases.items():
        path = tmp_path / name / f"{slug}.md"
        write(path, payload)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._validate_current_decision_record(path, slug)
        assert caught.exception.failure_id == failure_id, (name, caught.exception.failure_id)

    cutover_slug = "2026-08-18-new-v0"
    cutover = tmp_path / f"{cutover_slug}.md"
    write(cutover, _legacy_v0_decision_record())
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module._validate_current_decision_record(
            cutover,
            cutover_slug,
            v0_cutover_date="2026-08-18",
        )
    assert caught.exception.failure_id == "WI-DECISION-V0-CUTOVER-VIOLATION"


def test_decision_v0_manifest_admits_frozen_53_row_inventory_without_writes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    entries: list[dict[str, str]] = []
    identity_counts = {"id": 0, "slug": 0, "neither": 0}
    for index in range(53):
        day = 1 + index // 28
        slug = f"2026-07-{day:02d}-legacy-{index:02d}"
        if index < 2:
            identity = f"id: {slug}"
            identity_counts["id"] += 1
        elif index < 27:
            identity = f"slug: {slug[11:]}"
            identity_counts["slug"] += 1
        else:
            identity = None
            identity_counts["neither"] += 1
        path = root / "work-items" / "decisions" / f"{slug}.md"
        write(path, _legacy_v0_decision_record(identity_line=identity))
        entries.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                "state": "admitted",
            }
        )
    manifest = _write_decision_v0_manifest(root, entries)
    before = {
        path: path.read_bytes()
        for path in (root / "work-items" / "decisions").glob("*.md")
    }
    manifest_before = manifest.read_bytes()
    with patch.object(module, "_atomic_write") as atomic_write, patch.object(
        module.os,
        "replace",
    ) as replace_file:
        admitted = module.audit_categories(root)
    assert len(admitted) == 53
    assert identity_counts == {"id": 2, "slug": 25, "neither": 26}
    assert atomic_write.call_count == 0
    assert replace_file.call_count == 0
    assert manifest.read_bytes() == manifest_before
    assert all(path.read_bytes() == data for path, data in before.items())


def test_decision_v0_manifest_fail_closed_state_matrix(tmp_path: Path) -> None:
    module = load_module()

    def seeded(name: str, *, state: str = "admitted") -> tuple[Path, Path, Path]:
        root = tmp_path / name
        slug = "2026-08-01-legacy"
        decision = root / "work-items" / "decisions" / f"{slug}.md"
        write(decision, _legacy_v0_decision_record(identity_line=f"id: {slug}"))
        entry = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
            "state": state,
        }
        manifest = _write_decision_v0_manifest(root, [entry])
        return root, decision, manifest

    absent_root = tmp_path / "absent"
    write(
        absent_root / "work-items" / "decisions" / "2026-08-01-legacy.md",
        _legacy_v0_decision_record(),
    )
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(absent_root)
    assert caught.exception.failure_id == "WI-DECISION-V0-MANIFEST-MISSING"

    cases = [
        ("hash", "WI-DECISION-V0-HASH-MISMATCH", lambda _r, d, _m: d.write_text(d.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")),
        ("delete", "WI-DECISION-V0-MANIFEST-STALE", lambda _r, d, _m: d.unlink()),
        ("convert", "WI-DECISION-V0-MANIFEST-STALE", lambda _r, d, _m: d.write_text(_canonical_decision_record(d.stem), encoding="utf-8")),
        ("retired-reappear", "WI-DECISION-V0-RETIRED-REAPPEARED", lambda _r, _d, _m: None),
    ]
    for name, failure_id, mutate in cases:
        root, decision, manifest = seeded(
            name,
            state="retired" if name == "retired-reappear" else "admitted",
        )
        before_manifest = manifest.read_bytes()
        mutate(root, decision, manifest)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == failure_id, (name, caught.exception.failure_id)
        assert manifest.read_bytes() == before_manifest

    retired_root, retired_decision, retired_manifest = seeded("retired", state="retired")
    retired_decision.unlink()
    retired_before = retired_manifest.read_bytes()
    assert module.audit_categories(retired_root) == ()
    assert retired_manifest.read_bytes() == retired_before

    for name in ("new", "copy", "backdated"):
        root, decision, manifest = seeded(name)
        new_name = "2026-07-01-copy.md" if name == "backdated" else f"2026-08-02-{name}.md"
        shutil.copy2(decision, decision.parent / new_name)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == "WI-DECISION-V0-UNADMITTED", name


def test_decision_v0_manifest_rejects_invalid_shape_anchor_and_duplicate_json(
    tmp_path: Path,
) -> None:
    module = load_module()

    def seeded(name: str) -> tuple[Path, Path]:
        root = tmp_path / name
        decision = root / "work-items" / "decisions" / "2026-08-01-legacy.md"
        write(decision, _legacy_v0_decision_record())
        manifest = _write_decision_v0_manifest(
            root,
            [
                {
                    "path": decision.name,
                    "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
                    "state": "admitted",
                }
            ],
        )
        return root, manifest

    mutations = {
        "unknown-field": lambda payload: payload.update({"extra": True}),
        "schema": lambda payload: payload.update({"schemaVersion": 3}),
        "traversal": lambda payload: payload["entries"][0].update({"path": "../legacy.md"}),
        "lower-hash": lambda payload: payload["entries"][0].update({"sha256": payload["entries"][0]["sha256"].lower()}),
        "state": lambda payload: payload["entries"][0].update({"state": "pending"}),
        "duplicate-entry": lambda payload: payload["entries"].append(dict(payload["entries"][0])),
        "unsorted-entries": lambda payload: payload["entries"].append(
            {
                "path": "2026-07-01-earlier.md",
                "sha256": "A" * 64,
                "state": "retired",
            }
        ),
    }
    for name, mutate in mutations.items():
        root, manifest = seeded(name)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        mutate(payload)
        manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == "WI-DECISION-V0-MANIFEST-INVALID", (name, caught.exception.failure_id)

    root, manifest = seeded("duplicate-json")
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('"schemaVersion": 1,', '"schemaVersion": 1,\n  "schemaVersion": 1,'), encoding="utf-8")
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-V0-MANIFEST-INVALID"

    root, manifest = seeded("unaccepted-anchor")
    policy = root / "work-items" / "decisions" / "2026-08-18-current-decision-schema-versioned-read-compatibility.md"
    policy.write_text(policy.read_text(encoding="utf-8").replace("- status: accepted\n", "- status: proposed\n"), encoding="utf-8")
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-V0-MANIFEST-INVALID"


def test_decision_v0_manifest_is_repo_local_and_preflight_read_only(
    tmp_path: Path,
) -> None:
    module = load_module()
    for repo_name, slug in (("one", "2026-08-01-one"), ("two", "2026-08-02-two")):
        root = tmp_path / repo_name
        decision = root / "work-items" / "decisions" / f"{slug}.md"
        write(decision, _legacy_v0_decision_record(identity_line=f"id: {slug}"))
        manifest = _write_decision_v0_manifest(
            root,
            [
                {
                    "path": decision.name,
                    "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
                    "state": "admitted",
                }
            ],
        )
        policy = root / "work-items" / "decisions" / (
            "2026-08-18-current-decision-schema-versioned-read-compatibility.md"
        )
        protected = (decision, manifest, policy)
        before = {
            path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
            for path in protected
        }
        with patch.object(module, "_atomic_write", side_effect=AssertionError("V0 preflight wrote")):
            assert module.audit_categories(root) == (f"decisions/{slug}.md",)
        assert {
            path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
            for path in protected
        } == before
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "mcp-local-hub" not in source
    assert "F4AF62741FD4BEFC59AA3FEC95EDC88E995CD477B4551F53A2AFB403234A3A6F" not in source
    preflight_source = source.split("def _preflight_current_decision_v0", 1)[1].split("\ndef ", 1)[0]
    for mutation_token in ("write_text(", "write_bytes(", "os.replace(", ".unlink(", ".rename("):
        assert mutation_token not in preflight_source
    repository = Path(__file__).resolve().parents[1]
    for contract_path, no_fence_marker in (
        (repository / "docs" / "decisions.md", "NO `---` YAML fences"),
        (repository / "src.codex" / "skills" / "lead" / "SKILL.md", "no `---` fences"),
        (repository / "src.claude" / "skills" / "lead" / "SKILL.md", "no `---` fences"),
    ):
        contract = contract_path.read_text(encoding="utf-8")
        assert "list-item" in contract
        assert no_fence_marker in contract


def test_decision_h1_parser_accepts_closed_modes_and_opaque_body(tmp_path: Path) -> None:
    module = load_module()
    cases = (
        ("plain", "accepted (prefix authority)", "status", "accepted"),
        ("bold", "ACCEPTED 2026-07-01 — annotated", "status", "accepted"),
        ("bold", "proposed (deferred)", "Status", "proposed"),
    )
    for index, (mode, raw_status, status_key, admitted) in enumerate(cases):
        slug = f"2026-07-{index + 1:02d}-h1-{mode}"
        path = tmp_path / f"{slug}.md"
        body = "status: dropped\n\nBody metadata is opaque.\n"
        write(
            path,
            _legacy_h1_decision_record(
                mode=mode,
                status=raw_status,
                status_key=status_key,
                body=body,
            ),
        )
        result = module._validate_current_decision_record(path, slug)
        assert result.format == "legacy-markdown-h1-v0"
        assert result.raw_status == raw_status
        assert result.admitted_current_status == admitted
        assert result.legacy_read_only is True
        assert result.fields[status_key] == raw_status
        assert "id" not in result.fields and "slug" not in result.fields
        normalized = path.read_text(encoding="utf-8").encode("utf-8")
        assert normalized[result.body_offset :].decode("utf-8") == body
        with unittest.TestCase().assertRaises(TypeError):
            result.fields["invented"] = "value"

    cutover_slug = "2026-08-18-new-h1"
    cutover = tmp_path / f"{cutover_slug}.md"
    write(cutover, _legacy_h1_decision_record())
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module._validate_current_decision_record(
            cutover,
            cutover_slug,
            h1_cutover_date="2026-08-18",
        )
    assert caught.exception.failure_id == "WI-DECISION-H1-CUTOVER-VIOLATION"


def test_decision_h1_manifest_admits_exact_heading_list_metadata(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-07-18-external-owned-vcpkg-roots"
    decision = root / "work-items" / "decisions" / f"{slug}.md"
    body = "## Decision\n\nHistorical decision text remains opaque.\n"
    write(decision, _legacy_h1_list_decision_record(slug, body=body))
    decision_before = decision.read_bytes()
    manifest = _write_decision_h1_manifest(
        root,
        [
            {
                "path": decision.name,
                "sha256": hashlib.sha256(decision_before).hexdigest().upper(),
                "state": "admitted",
            }
        ],
    )
    manifest_before = manifest.read_bytes()

    assert module.audit_categories(root) == (f"decisions/{slug}.md",)
    record = module._preflight_current_decision_h1(root)[decision.name]

    assert record.format == "legacy-markdown-h1-v0"
    assert record.fields["id"] == slug
    assert record.fields["status"] == "accepted"
    assert record.raw_status == "accepted"
    assert record.admitted_current_status == "accepted"
    assert record.legacy_read_only is True
    normalized = decision.read_text(encoding="utf-8").encode("utf-8")
    assert normalized[record.body_offset :].decode("utf-8") == body
    assert decision.read_bytes() == decision_before
    assert manifest.read_bytes() == manifest_before

    variant_root = tmp_path / "ascii-case"
    variant_slug = "2026-07-19-external-owned-vcpkg-roots"
    variant = _legacy_h1_list_decision_record(variant_slug, body=body)
    for old_name, new_name in (
        ("id", "ID"),
        ("status", "STATUS"),
        ("work-item", "WORK-ITEM"),
        ("owner", "Owner"),
    ):
        variant = variant.replace(f"- {old_name}:", f"- {new_name}:")
    variant_decision = (
        variant_root
        / "work-items"
        / "decisions"
        / f"{variant_slug}.md"
    )
    write(variant_decision, variant)
    variant_before = variant_decision.read_bytes()
    variant_manifest = _write_decision_h1_manifest(
        variant_root,
        [
            {
                "path": variant_decision.name,
                "sha256": hashlib.sha256(variant_before).hexdigest().upper(),
                "state": "admitted",
            }
        ],
    )
    variant_manifest_before = variant_manifest.read_bytes()

    assert module.audit_categories(variant_root) == (
        f"decisions/{variant_slug}.md",
    )
    variant_record = module._preflight_current_decision_h1(variant_root)[
        variant_decision.name
    ]
    assert variant_record.fields["ID"] == variant_slug
    assert variant_record.fields["STATUS"] == "accepted"
    assert variant_record.fields["WORK-ITEM"] == "legacy-work-item"
    assert variant_record.fields["Owner"] == "architecture-reviewer"
    assert variant_decision.read_bytes() == variant_before
    assert variant_manifest.read_bytes() == variant_manifest_before


def test_decision_h1_list_metadata_requires_manifest_and_exact_identity_fields(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-07-18-external-owned-vcpkg-roots"
    canonical = _legacy_h1_list_decision_record(slug)

    unmanifested = tmp_path / "unmanifested"
    decision = unmanifested / "work-items" / "decisions" / f"{slug}.md"
    write(decision, canonical)
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(unmanifested)
    assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-MISSING"

    cases = {
        "missing-id": (
            canonical.replace(f"- id: {slug}\n", ""),
            "WI-DECISION-H1-SCHEMA-INVALID",
        ),
        "duplicate-id": (
            canonical.replace(f"- id: {slug}\n", f"- id: {slug}\n- id: {slug}\n"),
            "WI-DECISION-H1-FIELD-DUPLICATE",
        ),
        "wrong-id": (
            canonical.replace(f"- id: {slug}\n", "- id: 2026-07-18-wrong\n"),
            "WI-DECISION-IDENTITY-MISMATCH",
        ),
        "missing-status": (
            canonical.replace("- status: accepted\n", ""),
            "WI-DECISION-H1-STATUS-UNSUPPORTED",
        ),
        "duplicate-status": (
            canonical.replace(
                "- status: accepted\n",
                "- status: accepted\n- status: accepted\n",
            ),
            "WI-DECISION-H1-STATUS-UNSUPPORTED",
        ),
    }
    for name, (payload, failure_id) in cases.items():
        root = tmp_path / name
        current = root / "work-items" / "decisions" / f"{slug}.md"
        write(current, payload)
        before = current.read_bytes()
        manifest = _write_decision_h1_manifest(
            root,
            [
                {
                    "path": current.name,
                    "sha256": hashlib.sha256(before).hexdigest().upper(),
                    "state": "admitted",
                }
            ],
        )
        manifest_before = manifest.read_bytes()

        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)

        assert caught.exception.failure_id == failure_id, name
        assert current.read_bytes() == before, name
        assert manifest.read_bytes() == manifest_before, name


def test_decision_h1_parser_rejects_malformed_prefix_without_fallback(tmp_path: Path) -> None:
    module = load_module()
    slug = "2026-07-01-h1-invalid"
    cases = {
        "empty-title": ("# \n\nstatus: accepted\n\nbody\n", "WI-DECISION-FORMAT-UNSUPPORTED"),
        "missing-line-two": ("# Title\nstatus: accepted\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "empty-body": ("# Title\n\nstatus: accepted\n\n \n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "mixed-mode": ("# Title\n\nstatus: accepted\n- **owner:** one\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "tab": ("# Title\n\nstatus:\taccepted\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "indented": ("# Title\n\n status: accepted\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "malformed-bold": ("# Title\n\n- **status**: accepted\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "normalized-duplicate": ("# Title\n\nstatus: accepted\nowner name: one\nOwner_name: two\n\nbody\n", "WI-DECISION-H1-FIELD-DUPLICATE"),
        "duplicate-status": ("# Title\n\nstatus: accepted\nStatus: accepted\n\nbody\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "non-first-status": ("# Title\n\nowner: one\nstatus: accepted\n\nbody\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "unsupported-status": ("# Title\n\nstatus: dropped\n\nbody\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "punctuated-token": ("# Title\n\nstatus: accepted, maybe\n\nbody\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "body-only-status": ("# Title\n\nowner: one\n\nstatus: accepted\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "bom": ("\ufeff# Title\n\nstatus: accepted\n\nbody\n", "WI-DECISION-FORMAT-UNSUPPORTED"),
    }
    for name, (payload, failure_id) in cases.items():
        path = tmp_path / name / f"{slug}.md"
        write(path, payload)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._validate_current_decision_record(path, slug)
        assert caught.exception.failure_id == failure_id, (name, caught.exception.failure_id)

    invalid_utf8 = tmp_path / "invalid-utf8" / f"{slug}.md"
    invalid_utf8.parent.mkdir(parents=True)
    invalid_utf8.write_bytes(b"# Title\n\nstatus: accepted\n\nbody\xff\n")
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module._validate_current_decision_record(invalid_utf8, slug)
    assert caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"


def test_decision_h1_manifest_admits_13_rows_deterministically_without_writes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    entries: list[dict[str, str]] = []
    expected_statuses: dict[str, str] = {}
    decision_bytes: dict[Path, bytes] = {}
    for index in range(13):
        slug = f"2026-07-{index + 1:02d}-h1-{index:02d}"
        mode = "plain" if index < 7 else "bold"
        status = "proposed (deferred)" if index in {7, 8} else "accepted (frozen)"
        path = root / "work-items" / "decisions" / f"{slug}.md"
        write(
            path,
            _legacy_h1_decision_record(
                mode=mode,
                status=status,
                status_key="Status" if index == 12 else "status",
                body="status: dropped\n\nOpaque body.\n" if index == 6 else "Opaque body.\n",
            ),
        )
        entries.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                "state": "admitted",
            }
        )
        expected_statuses[path.name] = "proposed" if index in {7, 8} else "accepted"
        decision_bytes[path] = path.read_bytes()
    manifest = _write_decision_h1_manifest(root, entries)
    manifest_before = manifest.read_bytes()
    original_parse_fields = module._parse_fields

    def reject_h1_loose_scan(text: str) -> dict[str, str]:
        if text.startswith("# "):
            raise AssertionError("admitted H1 reached loose whole-document field scan")
        return original_parse_fields(text)

    with patch.object(module, "_parse_fields", side_effect=reject_h1_loose_scan), patch.object(
        module,
        "_atomic_write",
    ) as atomic_write, patch.object(module.os, "replace") as replace_file:
        observed = tuple(module.audit_categories(root) for _ in range(3))
    expected = tuple(f"decisions/{name}" for name in sorted(expected_statuses))
    assert observed == (expected, expected, expected)
    admitted = module._preflight_current_decision_h1(root)
    assert {name: row.admitted_current_status for name, row in admitted.items()} == expected_statuses
    assert atomic_write.call_count == 0 and replace_file.call_count == 0
    assert manifest.read_bytes() == manifest_before
    assert all(path.read_bytes() == payload for path, payload in decision_bytes.items())


def test_decision_h1_manifest_fail_closed_state_matrix(tmp_path: Path) -> None:
    module = load_module()

    def assert_read_only_failure(root: Path, failure_id: str) -> None:
        with patch.object(module, "_atomic_write") as atomic_write, patch.object(
            module.os,
            "replace",
        ) as replace_file, unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == failure_id, caught.exception.failure_id
        assert atomic_write.call_count == 0 and replace_file.call_count == 0

    def seeded(name: str, *, state: str = "admitted", slug: str = "2026-07-01-h1") -> tuple[Path, Path, Path]:
        root = tmp_path / name
        decision = root / "work-items" / "decisions" / f"{slug}.md"
        write(decision, _legacy_h1_decision_record())
        manifest = _write_decision_h1_manifest(
            root,
            [
                {
                    "path": decision.name,
                    "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
                    "state": state,
                }
            ],
        )
        return root, decision, manifest

    missing_root = tmp_path / "missing"
    write(
        missing_root / "work-items" / "decisions" / "2026-07-01-h1.md",
        _legacy_h1_decision_record(),
    )
    assert_read_only_failure(missing_root, "WI-DECISION-H1-MANIFEST-MISSING")

    cases = (
        ("hash", "admitted", "WI-DECISION-H1-HASH-MISMATCH", lambda decision: decision.write_text(decision.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")),
        ("delete", "admitted", "WI-DECISION-H1-MANIFEST-STALE", lambda decision: decision.unlink()),
        ("convert", "admitted", "WI-DECISION-H1-MANIFEST-STALE", lambda decision: decision.write_text(_canonical_decision_record(decision.stem), encoding="utf-8")),
        ("retired-reappear", "retired", "WI-DECISION-H1-RETIRED-REAPPEARED", lambda _decision: None),
    )
    for name, state, failure_id, mutate in cases:
        root, decision, manifest = seeded(name, state=state)
        manifest_before = manifest.read_bytes()
        mutate(decision)
        assert_read_only_failure(root, failure_id)
        assert manifest.read_bytes() == manifest_before

    retired_root, retired_decision, retired_manifest = seeded("retired", state="retired")
    retired_decision.unlink()
    retired_before = retired_manifest.read_bytes()
    assert module.audit_categories(retired_root) == ()
    assert retired_manifest.read_bytes() == retired_before

    for name, new_slug in (
        ("new", "2026-07-02-new"),
        ("copy", "2026-07-03-copy"),
        ("backdated", "2026-06-01-backdated"),
    ):
        root, decision, _manifest = seeded(name)
        shutil.copy2(decision, decision.parent / f"{new_slug}.md")
        assert_read_only_failure(root, "WI-DECISION-H1-UNADMITTED")

    cutover_root, _decision, _manifest = seeded(
        "cutover",
        slug="2026-08-18-cutover-h1",
    )
    assert_read_only_failure(cutover_root, "WI-DECISION-H1-CUTOVER-VIOLATION")


def test_decision_h1_manifest_rejects_invalid_shape_and_anchor(tmp_path: Path) -> None:
    module = load_module()

    def seeded(name: str) -> tuple[Path, Path]:
        root = tmp_path / name
        decision = root / "work-items" / "decisions" / "2026-07-01-h1.md"
        write(decision, _legacy_h1_decision_record())
        manifest = _write_decision_h1_manifest(
            root,
            [{"path": decision.name, "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(), "state": "admitted"}],
        )
        return root, manifest

    mutations = {
        "unknown-field": lambda payload: payload.update({"extra": True}),
        "schema": lambda payload: payload.update({"schemaVersion": 2}),
        "traversal": lambda payload: payload["entries"][0].update({"path": "../h1.md"}),
        "lower-hash": lambda payload: payload["entries"][0].update({"sha256": payload["entries"][0]["sha256"].lower()}),
        "state": lambda payload: payload["entries"][0].update({"state": "pending"}),
        "duplicate-entry": lambda payload: payload["entries"].append(dict(payload["entries"][0])),
        "unsorted-entries": lambda payload: payload["entries"].append(
            {"path": "2026-06-01-earlier.md", "sha256": "A" * 64, "state": "retired"}
        ),
    }
    for name, mutate in mutations.items():
        root, manifest = seeded(name)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        mutate(payload)
        manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-INVALID", name

    root, manifest = seeded("duplicate-json")
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            '"schemaVersion": 1,',
            '"schemaVersion": 1,\n  "schemaVersion": 1,',
        ),
        encoding="utf-8",
    )
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-INVALID"

    root, _manifest = seeded("unaccepted-anchor")
    policy = root / "work-items" / "decisions" / "2026-08-18-current-decision-schema-h1-read-compatibility.md"
    policy.write_text(
        policy.read_text(encoding="utf-8").replace("- status: accepted\n", "- status: proposed\n"),
        encoding="utf-8",
    )
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-INVALID"


def test_decision_h1_manifest_is_separate_generic_and_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "combined"
    v0_path = root / "work-items" / "decisions" / "2026-07-01-v0.md"
    h1_path = root / "work-items" / "decisions" / "2026-07-02-h1.md"
    write(v0_path, _legacy_v0_decision_record(identity_line=f"id: {v0_path.stem}"))
    write(h1_path, _legacy_h1_decision_record(mode="bold", status="PROPOSED later"))
    v0_manifest = _write_decision_v0_manifest(
        root,
        [{"path": v0_path.name, "sha256": hashlib.sha256(v0_path.read_bytes()).hexdigest().upper(), "state": "admitted"}],
    )
    h1_manifest = _write_decision_h1_manifest(
        root,
        [{"path": h1_path.name, "sha256": hashlib.sha256(h1_path.read_bytes()).hexdigest().upper(), "state": "admitted"}],
    )
    v0_before = v0_manifest.read_bytes()
    h1_before = h1_manifest.read_bytes()
    assert module.audit_categories(root) == (
        "decisions/2026-07-01-v0.md",
        "decisions/2026-07-02-h1.md",
    )
    assert v0_manifest.read_bytes() == v0_before
    assert h1_manifest.read_bytes() == h1_before

    payload = json.loads(h1_manifest.read_text(encoding="utf-8"))
    payload["entries"].append(dict(payload["entries"][0]))
    h1_manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-INVALID"
    assert v0_manifest.read_bytes() == v0_before

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert source.count("def _verify_current_decision_compatibility_manifest") == 1
    assert "2D873AB6EE1D6B026EEFD59879F538BA6DE8DBAB23C66646DD05FD7065D4137E" not in source
    assert "2026-06-16-hot-swap-zero-downtime-config" not in source
    assert not hasattr(module, "retire_decision_h1")
    h1_preflight = source.split("def _preflight_current_decision_h1", 1)[1].split("\ndef ", 1)[0]
    for mutation_token in ("write_text(", "write_bytes(", "os.replace(", ".unlink(", ".rename("):
        assert mutation_token not in h1_preflight


def test_decision_h1_failure_order_is_lexical_across_processes(tmp_path: Path) -> None:
    root = tmp_path / "ordered"
    entries: list[dict[str, str]] = []
    for slug, status in (
        ("2026-07-01-a-invalid", "dropped"),
        ("2026-07-02-z-invalid", "reverted"),
    ):
        path = root / "work-items" / "decisions" / f"{slug}.md"
        write(path, _legacy_h1_decision_record(status=status))
        entries.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                "state": "admitted",
            }
        )
    _write_decision_h1_manifest(root, entries)
    observed: list[str] = []
    for seed in ("1", "7", "41", "99"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "audit", "--root", str(root)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert process.returncode != 0
        assert "WI-DECISION-H1-STATUS-UNSUPPORTED" in process.stdout
        observed.append(process.stdout)
    assert all("2026-07-01-a-invalid" in output for output in observed)
    assert all("2026-07-02-z-invalid" not in output for output in observed)


class PartialMigrationRecoveryParserTests(unittest.TestCase):
    def _inventory_bytes(self, root: Path, *, suffix: str = "") -> bytes:
        work_items = (root / "work-items").resolve()
        return (
            "{"
            f'"digestAlgorithms":{{"directory":"sha256-tree-entries-v1","file":"sha256-file-bytes-v1"}},'
            f'"owner":"work-items-lifecycle-v1-migration",{suffix}'
            '"rows":[],"schemaVersion":1,'
            f'"workItemsRoot":{json.dumps(str(work_items))}'
            "}\n"
        ).encode("utf-8")

    def test_byte_parser_rejects_duplicate_json_keys(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self._inventory_bytes(
                root,
                suffix='"owner":"work-items-lifecycle-v1-migration",',
            )
            with self.assertRaises(module.LifecycleError) as caught:
                module._parse_migration_inventory_bytes(root, snapshot, strict_shape=True)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-CATEGORY-MIGRATION-INVENTORY",
            )

    def test_path_loader_delegates_exact_bytes_to_strict_parser(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory_path = root / "inventory.json"
            snapshot = self._inventory_bytes(root)
            inventory_path.write_bytes(snapshot)
            sentinel = {"parsed": True}
            with patch.object(
                module,
                "_parse_migration_inventory_bytes",
                return_value=sentinel,
            ) as parser:
                self.assertIs(
                    module._load_migration_inventory(root, inventory_path),
                    sentinel,
                )
            parser.assert_called_once_with(root, snapshot)

    def test_byte_parser_rejects_unknown_top_level_fields(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self._inventory_bytes(root).replace(
                b'"rows":[]',
                b'"unexpected":true,"rows":[]',
            )
            with self.assertRaises(module.LifecycleError) as caught:
                module._parse_migration_inventory_bytes(root, snapshot, strict_shape=True)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-CATEGORY-MIGRATION-INVENTORY",
            )


class LifecycleTransactionTests(unittest.TestCase):
    def _holder(self, root: Path, *, crash: bool = False) -> subprocess.Popen[str]:
        body = (
            "import importlib.util,os,sys;"
            "from pathlib import Path;"
            f"p=Path({str(SCRIPT)!r});"
            "s=importlib.util.spec_from_file_location('transaction_holder',p);"
            "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;"
            "s.loader.exec_module(m);"
            "t=m.LifecycleTransaction(Path(sys.argv[1]));t.__enter__();"
            "print('LOCKED',flush=True);"
            + ("os._exit(23)" if crash else "sys.stdin.readline();t.__exit__(None,None,None)")
        )
        return subprocess.Popen(
            [sys.executable, "-c", body, str(root)],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_live_owner_contention_fails_closed_and_releases_after_exit(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holder = self._holder(root)
            locked = holder.stdout.readline().strip()
            try:
                if locked == "LOCKED":
                    with self.assertRaises(module.LifecycleError) as caught:
                        with module.LifecycleTransaction(root):
                            self.fail("contending owner entered the transaction")
                    self.assertEqual(
                        caught.exception.failure_id,
                        "WI-LIFECYCLE-LOCK-HELD",
                    )
            finally:
                if holder.stdin and locked == "LOCKED":
                    holder.stdin.write("release\n")
                    holder.stdin.flush()
                stdout, stderr = holder.communicate(timeout=10)
                if holder.returncode == 0:
                    self.assertEqual(stderr, "")
            self.assertEqual(locked, "LOCKED", stderr)
            with module.LifecycleTransaction(root):
                pass

    def test_every_public_lifecycle_api_uses_the_common_transaction(self):
        module = load_module()
        expected = {
            "resolve_category",
            "work_item_dependency_state",
            "resolve_legacy_path",
            "collect_readme_entries",
            "render_readme_bytes",
            "refresh_readme",
            "reset_readme_static_guide",
            "check_readme",
            "create_candidate",
            "convert_legacy_candidate",
            "retire_legacy_backlog",
            "start_item",
            "update_status",
            "close_item",
            "reopen_item",
            "preflight_import_active_successor",
            "apply_import_active_successor",
            "audit_categories",
            "audit",
            "write_current_identity_normalization_inventory",
            "normalize_current_identity",
            "migrate_legacy_ledger_obligation",
            "revoke_legacy_ledger_obligation",
            "archive_with_successor",
            "supersede_current_bug",
            "archive_fixed_bug",
            "build_migration_inventory",
            "write_migration_inventory",
            "migrate_legacy",
            "terminalize_v1_inventory",
            "apply_migration_inventory",
            "recover_partial_migration_v1",
            "recover_transition",
            "admit_current_decision_v0",
            "verify_migration_inventory",
            "reopen_category_record",
            "run_trial",
        }
        self.assertEqual(set(module.LIFECYCLE_PUBLIC_APIS), expected)
        for name in sorted(expected):
            with self.subTest(name=name):
                self.assertTrue(
                    getattr(
                        getattr(module, name),
                        "__lifecycle_transaction_participant__",
                        False,
                    ),
                    name,
                )

    def test_process_crash_releases_native_lock(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holder = self._holder(root, crash=True)
            self.assertEqual(holder.stdout.readline().strip(), "LOCKED")
            stdout, stderr = holder.communicate(timeout=10)
            self.assertEqual(holder.returncode, 23, stdout + stderr)
            with module.LifecycleTransaction(root):
                pass


class PartialMigrationRecoveryBehaviorTests(unittest.TestCase):
    WORK_ITEM_ROWS = (
        (
            "work-item:2026-08-11-pr598-review-fix",
            "2026-08-11-pr598-review-fix",
            "2026-08-11T10:50:44Z",
        ),
        (
            "work-item:2026-08-11-pr600-review-fix",
            "2026-08-11-pr600-review-fix",
            "2026-08-11T10:53:49Z",
        ),
    )
    BUG_ROWS = (
        (
            "bug:2026-07-25-cleanup-aggressive-exe-extension-index-out-of-range-panic",
            "2026-07-25-cleanup-aggressive-exe-extension-index-out-of-range-panic",
        ),
        (
            "bug:2026-07-26-route-daemon-state-read-unhardened-parent-fallback-writes-hub-mcp-log",
            "2026-07-26-route-daemon-state-read-unhardened-parent-fallback-writes-hub-mcp-log",
        ),
    )

    def test_recovery_scratch_paths_reject_unreduced_reparse_participants(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repository"
            scratch = root / ".scratch"
            scratch.mkdir(parents=True)
            inventory = scratch / "inventory.json"
            inventory.write_bytes(b"{}\n")
            receipt_parent = scratch / "receipt-target"
            receipt_parent.mkdir()
            cases = []
            try:
                inventory_link = scratch / "inventory-link.json"
                os.symlink(inventory, inventory_link)
                cases.append((root, Path(".scratch/inventory-link.json"), "inventory"))

                receipt_parent_link = scratch / "receipt-parent-link"
                os.symlink(
                    receipt_parent,
                    receipt_parent_link,
                    target_is_directory=True,
                )
                cases.append(
                    (
                        root,
                        Path(".scratch/receipt-parent-link/receipt.json"),
                        "receipt",
                    )
                )

                root_link = base / "repository-link"
                os.symlink(root, root_link, target_is_directory=True)
                cases.append((root_link, Path(".scratch/inventory.json"), "inventory"))
            except OSError as exc:
                self.skipTest(f"target environment cannot create symlinks: {exc}")

            for recovery_root, candidate, label in cases:
                with self.subTest(candidate=candidate, label=label):
                    with self.assertRaises(module.LifecycleError) as caught:
                        module._partial_recovery_bound_scratch_file(
                            recovery_root,
                            candidate,
                            label=label,
                        )
                    self.assertEqual(
                        caught.exception.failure_id,
                        "WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
                    )

    def test_inventory_paths_reject_unreduced_root_and_target_parent_reparse(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_work_items = root / "real-work-items"
            real_work_items.mkdir()
            work_items_link = root / "work-items-link"
            real_parent = real_work_items / "real-archive-parent"
            real_parent.mkdir()
            target_parent_link = real_work_items / "target-parent-link"
            try:
                os.symlink(real_work_items, work_items_link, target_is_directory=True)
                os.symlink(real_parent, target_parent_link, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"target environment cannot create symlinks: {exc}")

            cases = (
                (work_items_link, "incident-target"),
                (real_work_items, "target-parent-link/incident-target"),
            )
            for work_items, relative in cases:
                with self.subTest(work_items=work_items, relative=relative):
                    with self.assertRaises(module.LifecycleError) as caught:
                        module._bound_inventory_path(work_items, relative)
                    self.assertEqual(
                        caught.exception.failure_id,
                        "WI-CATEGORY-MIGRATION-INVENTORY",
                    )

    def test_status_parent_reparse_swap_after_preflight_refuses_before_any_write(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            real_preflight = module._partial_recovery_preflight
            real_atomic_write = module._atomic_write
            attempted_writes = []

            def swap_after_preflight(recovery_root, inventory):
                plans = real_preflight(recovery_root, inventory)
                month = root / "work-items" / "archive" / "2026-08"
                moved = month.with_name("2026-08-real")
                month.rename(moved)
                try:
                    os.symlink(moved, month, target_is_directory=True)
                except OSError as exc:
                    moved.rename(month)
                    self.skipTest(
                        f"target environment cannot create a directory symlink: {exc}"
                    )
                return plans

            def recording_atomic_write(path, data):
                attempted_writes.append(Path(path))
                return real_atomic_write(path, data)

            try:
                with patch.object(
                    module,
                    "_partial_recovery_preflight",
                    side_effect=swap_after_preflight,
                ), patch.object(
                    module,
                    "_atomic_write",
                    side_effect=recording_atomic_write,
                ):
                    with self.assertRaises(module.LifecycleError):
                        self._run(module, root, fixture)
            finally:
                month = root / "work-items" / "archive" / "2026-08"
                if month.is_symlink():
                    month.unlink()
            self.assertEqual(attempted_writes, [])

    def _fixture(self, module, root: Path):
        work_items = root / "work-items"
        work_items.mkdir(parents=True)
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme = work_items / "README.md"
        expected_readme_sha256 = hashlib.sha256(readme.read_bytes()).hexdigest()
        rows = []
        unchanged = {}
        closures = {}
        targets = {}
        for index, (reference, slug) in enumerate(self.BUG_ROWS, start=1):
            target = work_items / "bugs" / "archive" / "2026-08" / f"{slug}.md"
            write(
                target,
                "status: fixed\n"
                "Terminal-at: 2026-08-17T18:25:44Z\n"
                f"Resolution: synthetic recovery fixture {index}\n"
                "Evidence: focused recovery test\n",
            )
            algorithm, digest = module._payload_digest(target)
            unchanged[reference] = digest
            rows.append(
                {
                    "admission": {
                        "negativeFixture": "bug_terminal_evidence_missing",
                        "reader": "mutate-work-item:_category_locations",
                        "result": "admitted",
                        "utcOwner": "bug:Terminal-at",
                        "validator": "mutate-work-item:_validate_flat_terminal",
                    },
                    "category": "bug",
                    "digestAlgorithm": algorithm,
                    "incomingLinks": {"references": [], "result": "clear"},
                    "inputSha256": digest,
                    "reference": reference,
                    "source": f"bugs/{slug}.md",
                    "target": f"bugs/archive/2026-08/{slug}.md",
                    "terminalInstant": "2026-08-17T18:25:44Z",
                }
            )
        for reference, slug, instant in self.WORK_ITEM_ROWS:
            target = work_items / "archive" / "2026-08" / slug
            status = quick_status().encode("utf-8")
            closure_bytes = marked_closure(instant).encode("utf-8")
            (target / "status.md").parent.mkdir(parents=True, exist_ok=True)
            (target / "status.md").write_bytes(status)
            (target / "closure.md").write_bytes(closure_bytes)
            algorithm, before_tree = module._payload_digest(target)
            after_status = module._terminalize_status(status)
            (target / "status.md").write_bytes(after_status)
            _after_algorithm, after_tree = module._payload_digest(target)
            (target / "status.md").write_bytes(status)
            targets[reference] = module.PartialRecoveryTarget(
                reference=reference,
                inventory_tree_preimage=before_tree,
                status_preimage=hashlib.sha256(status).hexdigest(),
                status_afterimage=hashlib.sha256(after_status).hexdigest(),
                projected_tree_afterimage=after_tree,
                closure_sha256=hashlib.sha256(closure_bytes).hexdigest(),
            )
            closures[reference] = closure_bytes
            rows.append(
                {
                    "admission": {
                        "negativeFixture": "work_item_terminal_evidence_missing",
                        "reader": "mutate-work-item:_category_locations",
                        "result": "admitted",
                        "utcOwner": "closure.md:Closed",
                        "validator": "mutate-work-item:_validate_closure",
                    },
                    "category": "work-item",
                    "digestAlgorithm": algorithm,
                    "incomingLinks": {"references": [], "result": "clear"},
                    "inputSha256": before_tree,
                    "reference": reference,
                    "source": f"active/{slug}",
                    "target": f"archive/2026-08/{slug}",
                    "terminalInstant": instant,
                }
            )
        inventory = {
            "digestAlgorithms": module.MIGRATION_DIGEST_ALGORITHMS,
            "owner": module.MIGRATION_OWNER,
            "rows": sorted(rows, key=lambda row: row["reference"]),
            "schemaVersion": module.MIGRATION_SCHEMA_VERSION,
            "workItemsRoot": str(work_items.resolve()),
        }
        inventory_bytes = (
            json.dumps(inventory, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        inventory_path = root / ".scratch" / "recovery-inventory.json"
        inventory_path.parent.mkdir(exist_ok=True)
        inventory_path.write_bytes(inventory_bytes)
        return {
            "inventory": inventory_path,
            "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
            "expected_readme_sha256": expected_readme_sha256,
            "receipt": root / ".scratch" / "recovery-receipt.json",
            "targets": targets,
            "unchanged": unchanged,
            "closures": closures,
            "status_preimages": {
                reference: target.status_preimage
                for reference, target in targets.items()
            },
        }

    def _run(self, module, root: Path, fixture: dict, **kwargs):
        with patch.multiple(
            module,
            PARTIAL_MIGRATION_RECOVERY_INVENTORY_SHA256=fixture[
                "inventory_sha256"
            ],
            PARTIAL_MIGRATION_RECOVERY_README_PREIMAGE_SHA256=fixture[
                "expected_readme_sha256"
            ],
            PARTIAL_MIGRATION_RECOVERY_TARGETS=fixture["targets"],
            PARTIAL_MIGRATION_RECOVERY_UNCHANGED_ROWS=fixture["unchanged"],
        ):
            return module.recover_partial_migration_v1(
                root,
                fixture["inventory"],
                expected_inventory_sha256=fixture["inventory_sha256"],
                expected_readme_sha256=fixture["expected_readme_sha256"],
                target_status_preimages=fixture["status_preimages"],
                receipt_path=fixture["receipt"],
                apply_admitted=True,
                render_readme=True,
                byte_check=True,
                **kwargs,
            )

    def test_exact_recovery_is_receipt_bound_and_idempotent(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            result = self._run(module, root, fixture)
            self.assertFalse(result.replay)
            self.assertEqual(result.audit, "PASS")
            self.assertEqual(
                hashlib.sha256(fixture["receipt"].read_bytes()).hexdigest().upper(),
                result.receipt_sha256,
            )
            receipt_payload = json.loads(fixture["receipt"].read_bytes())
            changed_rows = {
                row["reference"]: row
                for row in receipt_payload["rows"]
                if row["action"] == "terminalize-status"
            }
            self.assertEqual(set(changed_rows), set(fixture["targets"]))
            for reference, contract in fixture["targets"].items():
                self.assertEqual(
                    changed_rows[reference]["closureSha256"],
                    contract.closure_sha256.upper(),
                )
            self.assertEqual(
                {
                    row["action"]
                    for row in receipt_payload["rows"]
                    if row["reference"] in fixture["unchanged"]
                },
                {"none"},
            )
            for reference, contract in fixture["targets"].items():
                slug = reference.split(":", 1)[1]
                target = root / "work-items" / "archive" / "2026-08" / slug
                self.assertEqual(
                    hashlib.sha256((target / "status.md").read_bytes()).hexdigest(),
                    contract.status_afterimage,
                )
                self.assertEqual(
                    (target / "closure.md").read_bytes(),
                    fixture["closures"][reference],
                )
                self.assertFalse((root / "work-items" / "active" / slug).exists())
            self.assertEqual(
                (root / "work-items" / "README.md").read_bytes(),
                module.render_readme_bytes(root),
            )
            receipt_before = fixture["receipt"].read_bytes()
            with patch.object(
                module,
                "_atomic_write",
                wraps=module._atomic_write,
            ) as atomic_write:
                result = self._run(module, root, fixture)
            self.assertTrue(result.replay)
            atomic_write.assert_not_called()
            self.assertEqual(fixture["receipt"].read_bytes(), receipt_before)

    def test_failure_after_first_status_rolls_back_then_retry_succeeds(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            before = {
                reference: (
                    root
                    / "work-items"
                    / "archive"
                    / "2026-08"
                    / reference.split(":", 1)[1]
                    / "status.md"
                ).read_bytes()
                for reference in fixture["targets"]
            }
            with self.assertRaises(module.LifecycleError) as caught:
                self._run(
                    module,
                    root,
                    fixture,
                    inject_failure_at="after-status-1",
                )
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-TEST-FAILPOINT",
            )
            self.assertFalse(fixture["receipt"].exists())
            for reference, expected in before.items():
                status = (
                    root
                    / "work-items"
                    / "archive"
                    / "2026-08"
                    / reference.split(":", 1)[1]
                    / "status.md"
                )
                self.assertEqual(status.read_bytes(), expected)
            self.assertEqual(self._run(module, root, fixture).audit, "PASS")

    def test_crash_afterimage_is_reentered_without_rewriting_completed_target(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            reference = sorted(fixture["targets"])[0]
            contract = fixture["targets"][reference]
            status = (
                root
                / "work-items"
                / "archive"
                / "2026-08"
                / reference.split(":", 1)[1]
                / "status.md"
            )
            crash_afterimage = module._terminalize_status(status.read_bytes())
            self.assertEqual(
                hashlib.sha256(crash_afterimage).hexdigest(),
                contract.status_afterimage,
            )
            status.write_bytes(crash_afterimage)
            completed_before = status.read_bytes()
            result = self._run(module, root, fixture)
            self.assertFalse(result.replay)
            self.assertEqual(status.read_bytes(), completed_before)
            self.assertEqual(self._run(module, root, fixture).replay, True)

    def test_pending_recovery_refuses_preexisting_receipt(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            fixture["receipt"].write_bytes(b"not-an-authorized-receipt\n")
            with self.assertRaises(module.LifecycleError) as caught:
                self._run(module, root, fixture)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            )

    def test_incomplete_exact_prefix_pending_receipt_is_recreated_after_crash(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            self.assertEqual(self._run(module, root, fixture).audit, "PASS")
            exact_receipt = fixture["receipt"].read_bytes()
            fixture["receipt"].unlink()
            pending = fixture["receipt"].with_name(
                f".{fixture['receipt'].name}.pending-v1"
            )
            pending.write_bytes(exact_receipt[: len(exact_receipt) // 2])
            recovered = self._run(module, root, fixture)
            self.assertFalse(recovered.replay)
            self.assertEqual(fixture["receipt"].read_bytes(), exact_receipt)
            self.assertFalse(pending.exists())

    def test_receipt_settlement_fsyncs_parent_directory_before_success(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            fsync_modes = []
            real_fsync = module.os.fsync

            def recording_fsync(descriptor):
                fsync_modes.append(module.os.fstat(descriptor).st_mode)
                return real_fsync(descriptor)

            with patch.object(module.os, "fsync", side_effect=recording_fsync):
                self.assertTrue(
                    module._partial_recovery_settle_receipt(path, b"authorized\n")
                )
            self.assertTrue(
                any(stat.S_ISDIR(mode) for mode in fsync_modes),
                f"receipt parent directory was not fsynced: {fsync_modes!r}",
            )

    def test_receipt_directory_fsync_failure_cleans_own_link_and_retries(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            data = b"authorized\n"
            with patch.object(
                module,
                "_partial_recovery_fsync_directory",
                side_effect=module.LifecycleError(
                    "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CREATE-UNSUPPORTED",
                    "injected directory durability failure",
                ),
            ), self.assertRaises(module.LifecycleError):
                module._partial_recovery_settle_receipt(path, data)
            self.assertEqual(path.read_bytes(), data)
            self.assertFalse(path.with_name(f".{path.name}.pending-v1").exists())
            self.assertFalse(module._partial_recovery_settle_receipt(path, data))

    def test_late_receipt_conflict_cleanup_does_not_mask_primary(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            path = parent / "receipt.json"
            winner = parent / "winner.json"
            wanted = b"authorized\n"
            winner.write_bytes(wanted)
            real_directory_fsync = module._partial_recovery_fsync_directory

            def replace_after_fsync(directory_path):
                real_directory_fsync(directory_path)
                path.unlink()
                try:
                    os.symlink(winner, path)
                except OSError as exc:
                    self.skipTest(
                        f"target environment cannot create a symlink: {exc}"
                    )

            with patch.object(
                module,
                "_partial_recovery_fsync_directory",
                side_effect=replace_after_fsync,
            ), self.assertRaises(module.LifecycleError) as caught:
                module._partial_recovery_settle_receipt(path, wanted)

            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            )
            self.assertTrue(path.is_symlink())
            self.assertEqual(winner.read_bytes(), wanted)

    def test_exact_receipt_symlink_race_is_conflict_not_success(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            path = parent / "receipt.json"
            winner = parent / "winner.json"
            wanted = b"authorized\n"
            winner.write_bytes(wanted)

            def racing_link(_source, destination):
                try:
                    os.symlink(winner, destination)
                except OSError as exc:
                    self.skipTest(f"target environment cannot create a symlink: {exc}")
                raise FileExistsError(destination)

            with patch.object(module.os, "link", side_effect=racing_link):
                with self.assertRaises(module.LifecycleError) as caught:
                    module._partial_recovery_settle_receipt(path, wanted)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            )
            self.assertTrue(path.is_symlink())
            self.assertEqual(winner.read_bytes(), wanted)

    def test_closure_drift_refuses_before_status_write(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            reference = sorted(fixture["targets"])[0]
            slug = reference.split(":", 1)[1]
            status = root / "work-items" / "archive" / "2026-08" / slug / "status.md"
            closure_path = status.with_name("closure.md")
            before = status.read_bytes()
            closure_path.write_bytes(closure_path.read_bytes() + b"drift\n")
            with self.assertRaises(module.LifecycleError) as caught:
                self._run(module, root, fixture)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
            )
            self.assertEqual(status.read_bytes(), before)
            self.assertFalse(fixture["receipt"].exists())

    def test_same_bytes_closure_replacement_identity_refuses_before_status_write(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            before = {
                reference: (
                    root
                    / "work-items"
                    / "archive"
                    / "2026-08"
                    / reference.split(":", 1)[1]
                    / "status.md"
                ).read_bytes()
                for reference in fixture["targets"]
            }
            real_preflight = module._partial_recovery_preflight

            def replace_closure_identity(recovery_root, inventory):
                plans = real_preflight(recovery_root, inventory)
                closure = plans[0][0]["closure"]
                replacement = closure.with_name(".closure.identity-replacement")
                replacement.write_bytes(closure.read_bytes())
                os.replace(replacement, closure)
                return plans

            with patch.object(
                module,
                "_partial_recovery_preflight",
                side_effect=replace_closure_identity,
            ), self.assertRaises(module.LifecycleError) as caught:
                self._run(module, root, fixture)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
            )
            for reference, expected in before.items():
                status = (
                    root
                    / "work-items"
                    / "archive"
                    / "2026-08"
                    / reference.split(":", 1)[1]
                    / "status.md"
                )
                self.assertEqual(status.read_bytes(), expected)
            self.assertFalse(fixture["receipt"].exists())


class PartialMigrationRecoveryCliTests(unittest.TestCase):
    def _argv(self, root: Path) -> list[str]:
        return [
            "recover-partial-migration-v1",
            "--root",
            str(root),
            "--inventory",
            ".scratch/inventory.json",
            "--expected-inventory-sha256",
            "A" * 64,
            "--expected-readme-sha256",
            "B" * 64,
            "--target-status-preimage",
            "work-item:2026-08-11-pr598-review-fix=" + "C" * 64,
            "--target-status-preimage",
            "work-item:2026-08-11-pr600-review-fix=" + "D" * 64,
            "--receipt",
            ".scratch/recovery-receipt.json",
            "--apply-admitted",
            "--render-readme",
            "--byte-check",
        ]

    def test_parser_exposes_only_explicit_recovery_bindings(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            args = module.build_parser().parse_args(self._argv(Path(directory)))
        self.assertEqual(args.command, "recover-partial-migration-v1")
        self.assertEqual(len(args.target_status_preimage), 2)
        self.assertTrue(args.apply_admitted)
        self.assertTrue(args.render_readme)
        self.assertTrue(args.byte_check)

    def test_main_routes_exact_bindings_and_rejects_duplicate_target(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = self._argv(root)
            expected = module.PartialRecoveryResult("E" * 64, "PASS", False)
            with patch.object(
                module,
                "recover_partial_migration_v1",
                return_value=expected,
            ) as recovery, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(module.main(argv), 0)
            call_args, call_kwargs = recovery.call_args
            observer = call_kwargs.pop("diagnostic_observer")
            self.assertIs(type(observer), module.LifecycleDiagnosticObserver)
            self.assertEqual(call_args, (root, Path(".scratch/inventory.json")))
            self.assertEqual(
                call_kwargs,
                {
                    "expected_inventory_sha256": "A" * 64,
                    "expected_readme_sha256": "B" * 64,
                    "target_status_preimages": {
                        "work-item:2026-08-11-pr598-review-fix": "C" * 64,
                        "work-item:2026-08-11-pr600-review-fix": "D" * 64,
                    },
                    "receipt_path": Path(".scratch/recovery-receipt.json"),
                    "apply_admitted": True,
                    "render_readme": True,
                    "byte_check": True,
                },
            )
            self.assertEqual(
                output.getvalue(),
                "PARTIAL-MIGRATION-RECOVERY: PASS "
                + "receipt_sha256="
                + "E" * 64
                + " audit=PASS\n",
            )
            duplicate = argv + [
                "--target-status-preimage",
                "work-item:2026-08-11-pr598-review-fix=" + "F" * 64,
            ]
            with redirect_stdout(io.StringIO()) as error_output:
                self.assertEqual(module.main(duplicate), 1)
            self.assertIn(
                "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
                error_output.getvalue(),
            )

    def test_main_emits_exactly_one_committed_success_event(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            result = module.PartialRecoveryResult("E" * 64, "PASS", False)
            with patch.object(
                module,
                "recover_partial_migration_v1",
                return_value=result,
            ), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(module.main(self._argv(Path(directory))), 0)
            self.assertEqual(
                output.getvalue().splitlines(),
                [
                    "PARTIAL-MIGRATION-RECOVERY: PASS "
                    + "receipt_sha256="
                    + "E" * 64
                    + " audit=PASS"
                ],
            )

    def test_outcome_composer_preserves_primary_and_exact_cleanup_slots(self):
        module = load_module()
        primary = module.LifecycleError(
            "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            "primary receipt conflict",
        )
        composer = module.LifecycleOutcomeComposer()
        composer.capture_primary(primary)
        generic_phases = tuple(
            phase for phase in module.LIFECYCLE_CLEANUP_PHASES
            if phase not in module.LIFECYCLE_REPEATABLE_CLEANUP_PHASES
        )
        self.assertEqual(generic_phases, (
            "receipt-final", "receipt-pending", "rollback-parent-chain", "rollback-readme",
            "rollback-status:work-item:2026-08-11-pr600-review-fix",
            "rollback-status:work-item:2026-08-11-pr598-review-fix", "rollback-postcheck",
            "transaction-release", "transaction-file-close", "transaction-verification",
        ))
        for index, phase in enumerate(generic_phases, start=1):
            composer.record_cleanup(
                phase=phase,
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=f"resource-{index}",
                diagnostic=f"cleanup-{index}",
            )
        composer.set_rollback("incomplete")

        bundle = composer.finalize()

        self.assertIs(bundle.primary, primary)
        self.assertEqual(
            tuple(record.phase for record in bundle.cleanup_failures),
            generic_phases,
        )
        self.assertEqual(len(set(record.phase for record in bundle.cleanup_failures)), 10)
        self.assertEqual(bundle.rollback, "incomplete")
        with self.assertRaises(Exception):
            bundle.cleanup_failures += ()

        for index, phase in enumerate(module.LIFECYCLE_WRITE_CLEANUP_PHASES, start=1):
            composer.record_write_cleanup(
                phase=phase,
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=f"write-resource-{index}",
                diagnostic=f"write-cleanup-{index}",
            )
        composer.record_rollback_action(failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
            resource="work-items", diagnostic="actual failed rollback obligation")
        combined = composer.finalize()
        self.assertIs(combined.primary, primary)
        self.assertEqual(tuple(record.phase for record in combined.cleanup_failures),
                         module.LIFECYCLE_CLEANUP_PHASES)
        self.assertEqual(combined.rollback, "incomplete")
        with self.assertRaises(Exception):
            combined.cleanup_failures += ()

    def test_reusable_api_observer_preserves_control_flow_identity_and_zero_streams(self):
        module = load_module()
        primary = KeyboardInterrupt("operator cancellation")
        observer = module.LifecycleDiagnosticObserver()

        @module._lifecycle_participant
        def failing_api(root):
            composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
            composer.record_cleanup(
                phase="receipt-pending",
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=".scratch/.receipt.pending-v1",
                diagnostic="pending unlink failed",
            )
            raise primary

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    failing_api(
                        Path(directory),
                        diagnostic_observer=observer,
                    )

        self.assertIs(caught.exception, primary)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "")
        self.assertEqual(observer.state, "delivered")
        self.assertEqual(observer.snapshot.primaryKind, "control-flow")
        self.assertEqual(observer.snapshot.primaryType, "KeyboardInterrupt")
        self.assertEqual(observer.snapshot.topLevelKind, "control-flow-primary")
        self.assertEqual(
            tuple(record.phase for record in observer.snapshot.cleanupFailures),
            ("receipt-pending",),
        )

    def test_reusable_api_asyncio_cancelled_error_is_control_flow_and_same_object(self):
        module = load_module()
        primary = asyncio.CancelledError("cancelled")
        observer = module.LifecycleDiagnosticObserver()

        @module._lifecycle_participant
        def cancelled_api(root):
            composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
            composer.record_cleanup(
                phase="receipt-pending",
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=".scratch/.receipt.pending-v1",
                diagnostic="pending unlink failed",
            )
            raise primary

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                with self.assertRaises(asyncio.CancelledError) as caught:
                    cancelled_api(
                        Path(directory),
                        diagnostic_observer=observer,
                    )

        self.assertIs(caught.exception, primary)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "")
        self.assertEqual(observer.state, "delivered")
        self.assertEqual(observer.delivery_attempts, 1)
        self.assertEqual(observer.snapshot.primaryKind, "control-flow")
        self.assertEqual(observer.snapshot.primaryType, "CancelledError")
        self.assertEqual(observer.snapshot.topLevelKind, "control-flow-primary")
        self.assertEqual(
            tuple(record.phase for record in observer.snapshot.cleanupFailures),
            ("receipt-pending",),
        )

    def test_reusable_api_observer_rejection_is_one_shot_and_non_masking(self):
        module = load_module()
        primary = module.LifecycleError("WI-TEST-PRIMARY", "primary")
        observer = module.LifecycleDiagnosticObserver(_reject_delivery=True)

        @module._lifecycle_participant
        def failing_api(root):
            raise primary

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                with self.assertRaises(module.LifecycleError) as caught:
                    failing_api(
                        Path(directory),
                        diagnostic_observer=observer,
                    )

        self.assertIs(caught.exception, primary)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "")
        self.assertEqual(observer.state, "delivery-failed")
        self.assertIsNone(observer.snapshot)
        self.assertEqual(
            observer.delivery_failure.failure_id,
            "WI-LIFECYCLE-DIAGNOSTIC-DELIVERY",
        )
        self.assertEqual(observer.delivery_attempts, 1)

    def test_reusable_api_clean_candidate_returns_silently_after_release(self):
        module = load_module()
        observer = module.LifecycleDiagnosticObserver()
        result = module.PartialRecoveryResult("E" * 64, "PASS", False)

        @module._lifecycle_participant
        def successful_api(root):
            return module.PartialRecoveryCommittedCandidate(result)

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                actual = successful_api(
                    Path(directory),
                    diagnostic_observer=observer,
                )

        self.assertIs(actual, result)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "")
        self.assertEqual(observer.state, "not-needed")
        self.assertIsNone(observer.snapshot)

    def test_reusable_api_cleanup_only_promotes_earliest_slot_after_release(self):
        module = load_module()
        observer = module.LifecycleDiagnosticObserver()

        @module._lifecycle_participant
        def cleanup_only_api(root):
            composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
            composer.record_cleanup(
                phase="receipt-pending",
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=".scratch/.receipt.pending-v1",
                diagnostic="pending unlink failed",
            )
            return "proposed-success"

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(module.LifecycleError) as caught:
                cleanup_only_api(
                    Path(directory),
                    diagnostic_observer=observer,
                )

        self.assertEqual(
            caught.exception.failure_id,
            "WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
        )
        self.assertEqual(observer.snapshot.primaryKind, "none")
        self.assertEqual(observer.snapshot.topLevelKind, "cleanup-only")
        self.assertEqual(
            observer.snapshot.topLevelFailureId,
            "WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
        )

    def test_reusable_api_release_failure_preserves_existing_primary_identity(self):
        module = load_module()
        primary = module.LifecycleError("WI-TEST-PRIMARY", "primary")
        observer = module.LifecycleDiagnosticObserver()
        real_unlock = module.LifecycleTransaction._native_unlock

        def fail_after_unlock(transaction):
            real_unlock(transaction)
            raise OSError("injected release failure")

        @module._lifecycle_participant
        def failing_api(root):
            raise primary

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                module.LifecycleTransaction,
                "_native_unlock",
                fail_after_unlock,
            ), self.assertRaises(module.LifecycleError) as caught:
                failing_api(
                    Path(directory),
                    diagnostic_observer=observer,
                )

        self.assertIs(caught.exception, primary)
        self.assertEqual(
            tuple(record.phase for record in observer.snapshot.cleanupFailures),
            ("transaction-release",),
        )
        self.assertEqual(
            observer.snapshot.cleanupFailures[0].failureId,
            "WI-LIFECYCLE-LOCK-IDENTITY",
        )

    def test_reusable_api_rejects_subclassed_observer_before_lock_acquisition(self):
        module = load_module()

        class SubclassedObserver(module.LifecycleDiagnosticObserver):
            pass

        @module._lifecycle_participant
        def successful_api(root):
            return "unreachable"

        observer = SubclassedObserver()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, "LifecycleTransaction") as transaction:
                with self.assertRaises(TypeError):
                    successful_api(
                        Path(directory),
                        diagnostic_observer=observer,
                    )
            transaction.assert_not_called()
        self.assertEqual(observer.state, "empty")

    def test_cli_root_serializes_primary_cleanup_and_summary_exactly_once(self):
        module = load_module()

        @module._lifecycle_participant
        def failing_recovery(root, *args, **kwargs):
            composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
            composer.record_cleanup(
                phase="receipt-pending",
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=".scratch/.recovery-receipt.json.pending-v1",
                diagnostic="pending unlink failed",
            )
            raise module.LifecycleError(
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
                "primary receipt conflict",
            )

        expected_record = json.dumps(
            {
                "causeType": None,
                "diagnostic": "pending unlink failed",
                "failureId": "WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                "index": 1,
                "phase": "receipt-pending",
                "resource": ".scratch/.recovery-receipt.json.pending-v1",
                "total": 1,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                module,
                "recover_partial_migration_v1",
                failing_recovery,
            ), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(module.main(self._argv(Path(directory))), 1)

        self.assertEqual(
            output.getvalue().splitlines(),
            [
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT: "
                "primary receipt conflict",
                f"CLEANUP-FAILURE: {expected_record}",
                'CLEANUP-SUMMARY: {"count":1,"rollback":"not-needed"}',
            ],
        )

    def test_cli_root_preserves_control_flow_and_unexpected_identity_without_typed_line(self):
        module = load_module()
        for primary in (
            KeyboardInterrupt("operator cancellation"),
            RuntimeError("unexpected failure"),
        ):
            with self.subTest(primary=type(primary).__name__):

                @module._lifecycle_participant
                def failing_recovery(root, *args, **kwargs):
                    composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
                    composer.record_cleanup(
                        phase="receipt-pending",
                        failure_id=(
                            "WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED"
                        ),
                        resource=".scratch/.recovery-receipt.json.pending-v1",
                        diagnostic="pending unlink failed",
                    )
                    raise primary

                with tempfile.TemporaryDirectory() as directory:
                    with patch.object(
                        module,
                        "recover_partial_migration_v1",
                        failing_recovery,
                    ), redirect_stdout(io.StringIO()) as output:
                        with self.assertRaises(BaseException) as caught:
                            module.main(self._argv(Path(directory)))

                self.assertIs(caught.exception, primary)
                lines = output.getvalue().splitlines()
                self.assertEqual(len(lines), 2)
                self.assertTrue(lines[0].startswith("CLEANUP-FAILURE: "))
                self.assertEqual(
                    lines[1],
                    'CLEANUP-SUMMARY: {"count":1,"rollback":"not-needed"}',
                )
                self.assertNotIn("WI-TEST-PRIMARY", output.getvalue())


def test_ledger_location_intent_discovery_bounds_file_count_before_loading(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    transition_root = root / ".scratch" / "work-items-lifecycle-transitions"
    transition_root.mkdir(parents=True)
    for index in range(1025):
        (transition_root / f"intent-{index:04d}.json").write_text("{}", encoding="utf-8")
    loaded: list[Path] = []
    original = module._ledger_location_proof_object

    def track(path: Path, **kwargs):
        loaded.append(path)
        return original(path, **kwargs)

    with patch.object(module, "_ledger_location_proof_object", side_effect=track):
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._matching_ledger_location_intents(
                root, root, slug="target", logical_work_item="work-items/active/target"
            )

    assert caught.exception.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    assert "inventory limit" in str(caught.exception)
    assert loaded == []


def test_ledger_location_intent_discovery_bounds_each_file_before_full_read(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    transition_root = root / ".scratch" / "work-items-lifecycle-transitions"
    transition_root.mkdir(parents=True)
    oversized = transition_root / "oversized.json"
    oversized.write_bytes(b" " * (256 * 1024 + 1))
    observed_reads: list[Path] = []
    original_read_bytes = Path.read_bytes

    def track_read(path: Path) -> bytes:
        if path == oversized:
            observed_reads.append(path)
        return original_read_bytes(path)

    with patch.object(Path, "read_bytes", track_read):
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._matching_ledger_location_intents(
                root, root, slug="target", logical_work_item="work-items/active/target"
            )

    assert caught.exception.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    assert "byte limit" in str(caught.exception)
    assert observed_reads == []

def test_ledger_location_intent_discovery_bounds_cumulative_bytes_before_loading(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    transition_root = root / ".scratch" / "work-items-lifecycle-transitions"
    transition_root.mkdir(parents=True)
    payload = b"{}" + b" " * (256 * 1024 - 2)
    for index in range(33):
        (transition_root / f"intent-{index:02d}.json").write_bytes(payload)
    loaded: list[Path] = []
    original = module._ledger_location_proof_object

    def track(path: Path, **kwargs):
        loaded.append(path)
        return original(path, **kwargs)

    with patch.object(module, "_ledger_location_proof_object", side_effect=track):
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._matching_ledger_location_intents(
                root, root, slug="target", logical_work_item="work-items/active/target"
            )

    assert caught.exception.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    assert "cumulative byte limit" in str(caught.exception)
    assert loaded == []


class _UnittestAdapter(unittest.TestCase):
    """Run the module's pytest-style functions under the plan's unittest CLI."""


def _relocation_observation_fixture(tmp_path: Path):
    module = load_module()
    root = tmp_path / "repository"
    source = root / "current-owner"
    leaf = source / "nested" / "proof.bin"
    leaf.parent.mkdir(parents=True)
    leaf.write_bytes(b"original retained evidence")
    outside = root / "current-owner-lookalike" / "outside.bin"
    outside.parent.mkdir()
    outside.write_bytes(b"unaffected original proof")
    destination = root / "archive" / "moved-owner"
    destination.parent.mkdir()
    return module, root, source, destination, leaf, outside


def _directory_observation_stat(info, **changes):
    """Change selected stat fields while preserving every other captured field."""
    values = list(info)
    fields = ("st_mode", "st_ino", "st_dev", "st_nlink", "st_uid", "st_gid",
              "st_size", "st_atime", "st_mtime", "st_ctime")
    # The first seven tuple slots are named; tuple time slots are unnamed
    # and have separate public float/nanosecond attributes.
    tuple_fields = fields[:7]
    attributes = {name: getattr(info, name) for name in dir(info)
                  if name.startswith("st_") and name not in tuple_fields}
    for name, value in changes.items():
        if name not in tuple_fields:
            attributes[name] = value
        if name in fields:
            values[fields.index(name)] = value
    return os.stat_result(values, attributes)


@pytest.mark.parametrize("candidate_kind", ("exact", "exact-corrupt-at-entry", "minted-equivalent"))
def test_collection_admission_binds_before_failure_and_restoration(tmp_path, candidate_kind):
    module, root, source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    admitted = module._capture_owned_directory_snapshot(source, failure_id="TEST")
    candidate = replace(admitted) if candidate_kind == "minted-equivalent" else admitted
    cause = OSError("original native cause")
    first = module.LifecycleError("TEST-COLLECTION-LOCAL", "original local refusal")
    first.__cause__ = cause
    original_binding = candidate.capture_binding
    original_members = candidate.members
    with pytest.raises(module.LifecycleError) as final:
        with module.LifecycleTransaction(root) as transaction:
            transaction.observe_retained_inputs((admitted,))
            transaction._validator_reuse = object()
            if candidate_kind == "exact-corrupt-at-entry":
                object.__setattr__(candidate, "capture_binding", ())
            calls = []
            def refuse():
                calls.append(candidate)
                object.__setattr__(candidate, "capture_binding", ())
                object.__setattr__(candidate, "members", ())
                raise first
            try:
                with pytest.raises(module.LifecycleError) as caught:
                    transaction._verify_admitted_observation(candidate, refuse)
                assert caught.value is first and caught.value.__cause__ is cause
            finally:
                object.__setattr__(candidate, "capture_binding", original_binding)
                object.__setattr__(candidate, "members", original_members)
            assert calls == [candidate]
            failures = [value for kind, value in transaction.current_binding_evidence if kind == "integrity-failure"]
            assert failures[0][0] is admitted and failures[0][1] is first
            assert sum(row[1] is first for row in failures) == 1
            assert transaction._validator_reuse is None
            with pytest.raises(module.LifecycleError) as sticky:
                transaction.verify()
            assert sticky.value is first
    assert final.value is first and not transaction._locked and transaction._file is None


@pytest.mark.parametrize("invalid", ("empty-mint", "none-mint", "missing-mint", "different-parent", "different-metadata", "different-members", "unadmitted", "none-entry", "none-candidate"))
def test_collection_unadmitted_local_failure_never_poisoned_transaction(tmp_path, invalid):
    module, root, source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    admitted = module._capture_owned_directory_snapshot(source, failure_id="TEST")
    candidate = replace(admitted)
    if invalid == "empty-mint":
        candidate = replace(candidate, capture_binding=())
    elif invalid == "none-mint":
        candidate = replace(candidate, capture_binding=None)
    elif invalid == "missing-mint":
        object.__delattr__(candidate, "capture_binding")
    elif invalid == "different-parent":
        candidate = replace(candidate, parent_chain=module.CapturedPathParentChain(()))
    elif invalid == "different-metadata":
        candidate = replace(candidate, metadata=_directory_observation_stat(candidate.metadata, st_ino=0))
    elif invalid == "different-members":
        candidate = replace(candidate, members=())
    elif invalid == "none-candidate":
        candidate = None
    if invalid.startswith("different-"):
        object.__setattr__(candidate, "capture_binding", module._directory_capture_binding(candidate))
    with module.LifecycleTransaction(root) as transaction:
        if invalid not in ("unadmitted", "none-entry"):
            transaction.observe_retained_inputs((admitted,))
        elif invalid == "none-entry":
            transaction._retained_observations[source] = None
        before = transaction.current_binding_evidence
        reuse = transaction._validator_reuse = object()
        first = module.LifecycleError("TEST-LOCAL-ONLY", "port-local refusal")
        cause = OSError("port-local native cause")
        first.__cause__ = cause
        def refuse():
            # Post-failure equality cannot manufacture admission.
            if candidate is not None:
                for field in ("parent_chain", "metadata", "members", "capture_binding"):
                    object.__setattr__(candidate, field, getattr(admitted, field))
            raise first
        with pytest.raises(module.LifecycleError) as caught:
            transaction._verify_admitted_observation(candidate, refuse)
        assert caught.value is first and caught.value.__cause__ is cause
        assert transaction.current_binding_evidence is before
        assert transaction._source_admission_failure is None and transaction._validator_reuse is reuse
        if invalid == "none-entry":
            del transaction._retained_observations[source]
        transaction.verify()


def test_collection_genuine_empty_native_mint_and_file_qualification(tmp_path):
    module, root, _source, _destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    empty = root / "empty"; empty.mkdir()
    directory = module._capture_owned_directory_snapshot(empty, failure_id="TEST")
    file = module._capture_file_snapshot(leaf, failure_id="TEST")
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((directory, file))
        observed = []
        original = transaction._verify_integrity_constraint
        def track(constraint, verification):
            observed.append(constraint)
            return original(constraint, verification)
        transaction._verify_integrity_constraint = track
        transaction._verify_admitted_observation(replace(directory), lambda: None)
        transaction._verify_admitted_observation(replace(file), lambda: None)
        transaction._verify_admitted_observation(replace(file, require_single_link=True), lambda: None)
        assert observed == [directory, file]


def test_collection_guards_are_fresh_ordered_and_keep_local_failures(tmp_path, monkeypatch):
    module, _root, source, _destination, _leaf, outside = _relocation_observation_fixture(tmp_path)
    snapshots = tuple(module._capture_owned_directory_snapshot(path, failure_id="TEST")
                      for path in (source, outside.parent))
    events = []
    class Transaction:
        def verify(self, *, inverse=None):
            events.append(("global", inverse))
        def _verify_admitted_observation(self, snapshot, verification):
            events.append(("bind", snapshot.path))
            return verification()
    real = module._verify_owned_directory_snapshot
    def local(snapshot, failure_id):
        events.append(("native", snapshot.path))
        # The scheduling double has no native ownership; acquire the real proof standalone.
        native_token = module._CURRENT_LIFECYCLE_TRANSACTION.set(None)
        try:
            return real(snapshot, failure_id)
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(native_token)
    monkeypatch.setattr(module, "_verify_owned_directory_snapshot", local)
    token = module._CURRENT_LIFECYCLE_TRANSACTION.set(Transaction())
    try:
        for _ in range(2):
            module._verify_captured_directories(snapshots, "TEST", inverse="owned-inverse")
        expected = [("global", "owned-inverse")]
        for snapshot in snapshots:
            expected += [("bind", snapshot.path), ("native", snapshot.path)]
        expected += [("global", "owned-inverse")]
        assert events == expected * 2
        events.clear()
        module._verify_captured_directories((), "TEST")
        assert events == []
        with pytest.raises(AttributeError):
            module._verify_captured_directories((None,), "TEST")
        assert events == [("global", None)]
        events.clear()
        first = module.LifecycleError("TEST-LOCAL", "stop before successful postguard")
        def refuse(snapshot, failure_id):
            events.append(("refuse", snapshot.path))
            raise first
        monkeypatch.setattr(module, "_verify_owned_directory_snapshot", refuse)
        with pytest.raises(module.LifecycleError) as caught:
            module._verify_captured_directories(snapshots, "TEST")
        assert caught.value is first
        assert events == [("global", None), ("bind", snapshots[0].path), ("refuse", snapshots[0].path)]
    finally:
        module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    events.clear()
    monkeypatch.setattr(module, "_verify_owned_directory_snapshot", local)
    module._verify_captured_directories(snapshots, "TEST")
    assert events == [("native", snapshot.path) for snapshot in snapshots]


def test_collection_success_exit_refuses_persistent_midcollection_drift(tmp_path, monkeypatch):
    module, root, source, _destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    snapshots = tuple(module._capture_owned_directory_snapshot(path, failure_id="TEST")
                      for path in (source, outside.parent))
    retained = module._capture_file_snapshot(leaf, failure_id="TEST")
    first = None
    with pytest.raises(module.LifecycleError):
        with module.LifecycleTransaction(root) as transaction:
            transaction.observe_retained_inputs((retained,))
            token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            real = module._verify_owned_directory_snapshot
            checked = []
            def change_after_local(snapshot, failure_id, **kwargs):
                real(snapshot, failure_id, **kwargs)
                checked.append(snapshot.path)
                if snapshot is snapshots[0]:
                    leaf.write_bytes(b"changed retained evidence")
            try:
                with monkeypatch.context() as scoped:
                    scoped.setattr(module, "_verify_owned_directory_snapshot", change_after_local)
                    with pytest.raises(module.LifecycleError) as refused:
                        module._verify_captured_directories(snapshots, "TEST")
                first = refused.value
                assert checked == [snapshot.path for snapshot in snapshots]
            finally:
                module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
            leaf.write_bytes(retained.data)
            with pytest.raises(module.LifecycleError) as sticky:
                transaction.verify()
            assert sticky.value is first


def test_collection_local_admitted_refusal_is_sticky_through_real_boundary(tmp_path, monkeypatch):
    module, root, source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    admitted = module._capture_owned_directory_snapshot(source, failure_id="TEST")
    supplied = replace(admitted)
    first = module.LifecycleError("TEST-LOCAL", "actual collection local refusal")
    with pytest.raises(module.LifecycleError) as final:
        with module.LifecycleTransaction(root) as transaction:
            transaction.observe_retained_inputs((admitted,))
            token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            real = module._verify_owned_directory_snapshot
            calls = []
            def refuse_local(snapshot, failure_id, **kwargs):
                if failure_id == "TEST-LOCAL":
                    calls.append(snapshot)
                    object.__setattr__(snapshot, "capture_binding", ())
                    raise first
                return real(snapshot, failure_id, **kwargs)
            try:
                with monkeypatch.context() as scoped:
                    scoped.setattr(module, "_verify_owned_directory_snapshot", refuse_local)
                    with pytest.raises(module.LifecycleError) as caught:
                        module._verify_captured_directories((supplied,), "TEST-LOCAL")
                assert caught.value is first and calls == [supplied]
            finally:
                object.__setattr__(supplied, "capture_binding", admitted.capture_binding)
                module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
            assert transaction._retained_observations[source] is admitted
            with pytest.raises(module.LifecycleError) as sticky:
                transaction.verify()
            assert sticky.value is first
    assert final.value is first and not transaction._locked


def test_collection_global_route_keeps_minted_equivalent_and_rejects_unminted(tmp_path):
    module, root, source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    admitted = module._capture_owned_directory_snapshot(source, failure_id="TEST")
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((admitted,))
        transaction._verify_observation_map({source: replace(admitted)})
        before = transaction.current_binding_evidence
        transaction._validator_reuse = object()
        with pytest.raises(module.LifecycleError, match="not minted intact"):
            transaction._verify_observation_map({source: replace(admitted, capture_binding=())})
        assert transaction.current_binding_evidence is before
        assert transaction._validator_reuse is None and transaction._source_admission_failure is None
        transaction.verify()


def test_collection_midpoint_native_directory_replacement(tmp_path, monkeypatch):
    module, _root, source, _destination, _leaf, outside = _relocation_observation_fixture(tmp_path)
    snapshots = tuple(module._capture_owned_directory_snapshot(path, failure_id="TEST")
                      for path in (source, outside.parent))
    held = outside.parent.with_name("held-outside")
    real = module._verify_owned_directory_snapshot
    checked = []
    def replace_after_first(snapshot, failure_id):
        checked.append(snapshot)
        real(snapshot, failure_id)
        if snapshot is snapshots[0]:
            outside.parent.rename(held)
            outside.parent.mkdir()
    monkeypatch.setattr(module, "_verify_owned_directory_snapshot", replace_after_first)
    try:
        with pytest.raises(module.LifecycleError) as refused:
            module._verify_captured_directories(snapshots, "TEST-NATIVE-MIDPOINT")
        assert refused.value.failure_id == "TEST-NATIVE-MIDPOINT"
        assert checked == list(snapshots)
    finally:
        if held.exists():
            outside.parent.rmdir()
            held.rename(outside.parent)
    assert outside.read_bytes() == b"unaffected original proof"


def test_collection_primary_survives_discriminator_failure(tmp_path, monkeypatch):
    module, root, source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    admitted = module._capture_owned_directory_snapshot(source, failure_id="TEST")
    primary = module.LifecycleError("TEST-PRIMARY", "first acquired local refusal")
    cause = OSError("original native read cause"); primary.__cause__ = cause
    secondary = OSError("later failure-path discriminator refusal")
    with pytest.raises(module.LifecycleError) as final:
        with module.LifecycleTransaction(root) as transaction:
            transaction.observe_retained_inputs((admitted,))
            def discriminator(constraint):
                assert constraint is admitted
                raise secondary
            monkeypatch.setattr(transaction, "_failure_paths", discriminator)
            def refuse():
                raise primary
            with pytest.raises(module.LifecycleError) as caught:
                transaction._verify_admitted_observation(admitted, refuse)
            assert caught.value is primary and caught.value.__cause__ is cause
            failures = [value for kind, value in transaction.current_binding_evidence if kind == "integrity-failure"]
            assert [row[1] for row in failures] == [primary, secondary]
            assert all(row[0] is admitted for row in failures)
            with pytest.raises(module.LifecycleError) as sticky:
                transaction.verify()
            assert sticky.value is primary
    assert final.value is primary and not transaction._locked


def test_collection_noneligible_local_failure_stays_local(tmp_path):
    module, root, source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    admitted = module._capture_owned_directory_snapshot(source, failure_id="TEST")
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((admitted,))
        before = transaction.current_binding_evidence
        reuse = transaction._validator_reuse = object()
        first = RuntimeError("noneligible port-local failure")
        def refuse():
            raise first
        with pytest.raises(RuntimeError) as caught:
            transaction._verify_admitted_observation(admitted, refuse)
        assert caught.value is first and transaction.current_binding_evidence is before
        assert transaction._validator_reuse is reuse and transaction._source_admission_failure is None
        transaction.verify()


def _directory_observation_atime_change(module, snapshot):
    def changed(info):
        return _directory_observation_stat(info, st_atime=info.st_atime + 1,
                                           st_atime_ns=info.st_atime_ns + 1_000_000_000)
    current = replace(snapshot, metadata=changed(snapshot.metadata),
                      members=tuple((name, changed(info)) for name, info in snapshot.members))
    return replace(current, capture_binding=module._directory_capture_binding(current))


def test_retained_directory_observation_accepts_root_and_member_atime_only(tmp_path: Path) -> None:
    module, root, source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_owned_directory_snapshot(source, failure_id="TEST-PROOF")
    current = _directory_observation_atime_change(module, original)
    assert original.members and current != original
    assert current.metadata.st_atime_ns != original.metadata.st_atime_ns
    assert all(new.st_atime_ns != old.st_atime_ns
               for (_name, new), (_old_name, old) in zip(current.members, original.members))
    assert module._directory_capture_binding(current) == module._directory_capture_binding(original)
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((original,))
        observations = transaction._retained_observations
        transaction.observe_retained_inputs((current,))
        assert transaction._retained_observations is observations
        assert observations[source] is current
        assert current.metadata is not original.metadata and current.members is not original.members
        module._verify_owned_directory_snapshot(current, "TEST-PROOF")


def test_directory_effect_collection_uses_physical_observation_equivalence(tmp_path: Path, monkeypatch) -> None:
    module, root, _source, _destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_owned_directory_snapshot(leaf.parent, failure_id="TEST-PROOF")
    current = _directory_observation_atime_change(module, original)
    class CollectionReached(Exception):
        pass
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((original,))
        observations = transaction._retained_observations
        # Feed the collection's direct-binding representation branch only. Stop
        # before native/evidence verification; this is not effect admission.
        evidence = transaction._binding_evidence
        reached = []
        def stop_after_collection(values, **kwargs):
            reached.append(values)
            raise CollectionReached
        try:
            with monkeypatch.context() as scoped:
                scoped.setattr(transaction, "_verify_observation_map", stop_after_collection)
                transaction._binding_evidence = evidence + (("file", current),)
                with pytest.raises(CollectionReached):
                    transaction.prepare_owned_effect(object(), leaf, None)
                assert len(reached) == 1 and reached[0][original.path] is original
                drift = replace(current, metadata=_directory_observation_stat(
                    current.metadata, st_mtime_ns=current.metadata.st_mtime_ns + 1))
                transaction._binding_evidence = evidence + (("file", drift),)
                with pytest.raises(module.LifecycleError, match="directory representations disagree before effect") as caught:
                    transaction.prepare_owned_effect(object(), leaf, None)
                assert caught.value.failure_id == "WI-LIFECYCLE-EFFECT" and len(reached) == 1
                assert transaction._retained_observations is observations and observations[original.path] is original
                assert leaf.read_bytes() == b"original retained evidence"
        finally:
            transaction._binding_evidence = evidence


def test_retained_directory_observation_refuses_stable_membership_and_parent_drift(tmp_path: Path) -> None:
    module, root, source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_owned_directory_snapshot(source, failure_id="TEST-PROOF")
    name, member = original.members[0]
    participant, identity = original.parent_chain.participants[-1]
    variants = (
        replace(original, metadata=_directory_observation_stat(original.metadata, st_ino=original.metadata.st_ino + 1)),
        replace(original, metadata=_directory_observation_stat(original.metadata, st_mtime_ns=original.metadata.st_mtime_ns + 1)),
        replace(original, members=((name, _directory_observation_stat(member, st_ctime_ns=member.st_ctime_ns + 1)),)),
        replace(original, members=((name + "-changed", member),)),
        replace(original, members=()),
        replace(original, parent_chain=replace(original.parent_chain,
            participants=original.parent_chain.participants[:-1] + ((participant, (identity[0], identity[1] + 1)),))),
    )
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((original,))
        observations = transaction._retained_observations
        for current in variants:
            with pytest.raises(module.LifecycleError, match="retained-input observation changed during selection") as caught:
                transaction.observe_retained_inputs((current,))
            assert caught.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
            assert transaction._retained_observations is observations and observations[source] is original


def test_outcome_explicit_outward_preserves_original_and_actual_cleanup_occurrences():
    module = load_module()
    original = module.LifecycleError("ORIGINAL", "first substantive failure")
    outward = module.LifecycleError("WI-BUG-DISPOSITIONS-ROLLBACK", "existing domain aggregate")
    outward.__cause__ = original
    composer = module.LifecycleOutcomeComposer()
    with pytest.raises(ValueError):
        composer.designate_outward_failure(outward)
    composer.capture_primary(original)
    first, second, release = OSError(5, "inverse refused"), module.LifecycleError("DELETE", "delete refused"), OSError(6, "release refused")
    composer.record_rollback_action(failure_id="ROLLBACK", resource="first", diagnostic="inverse", cause=first)
    composer.record_rollback_action(failure_id=second.failure_id, resource="second", diagnostic="remove directory", cause=second)
    composer.record_write_cleanup(phase="write-target-release", failure_id="RELEASE", resource="handle", diagnostic="release", cause=release)
    composer.set_rollback("incomplete")
    composer.designate_outward_failure(outward)
    composer.capture_primary(second)
    bundle = composer.finalize()
    assert bundle.primary is original and bundle.outward_failure is outward
    assert module.LifecycleOutcomeComposer.top_level(bundle) is outward and outward.__cause__ is original
    assert [cause for _record, cause in composer.rollback_actions] == [first, second]
    assert "inverse: " in composer.rollback_message() and "delete refused" in composer.rollback_message()
    projection = module._lifecycle_diagnostic_bundle(bundle)
    assert projection.primaryFailureId == "ORIGINAL"
    assert projection.topLevelKind == "typed-outward" and projection.topLevelFailureId == outward.failure_id
    assert tuple(row.phase for row in projection.cleanupFailures) == ("write-target-release", "rollback-action")
    assert "occurrences=2" in projection.cleanupFailures[-1].diagnostic
    with pytest.raises(ValueError):
        composer.designate_outward_failure(module.LifecycleError("OTHER", "conflicting designation"))
    default = module.LifecycleOutcomeBundle(None, original, (), "not-needed")
    assert module.LifecycleOutcomeComposer.top_level(default) is original and default.outward_failure is None
    with pytest.raises(ValueError):
        composer.record_cleanup(phase="rollback-action", failure_id="WRONG", resource=None, diagnostic="wrong owner")


@pytest.mark.skipif(os.name != "nt", reason="actual native directory deletion refusal")
def test_close_native_cleanup_failure_keeps_original_and_existing_outward_aggregate(tmp_path, monkeypatch):
    module = load_module()
    root, slug, instant = tmp_path / "repo", "close-dual-native", "2026-10-08T00:00:00Z"
    seed_active(module, root, slug)
    write_empty_bug_dispositions(root, slug, instant)
    module.refresh_readme(root)
    active = root / "work-items/active" / slug
    status_before = (active / "status.md").read_bytes()
    readme_before = (root / "work-items/README.md").read_bytes()
    observer = module.LifecycleDiagnosticObserver()
    sentinel = module.LifecycleError("TEST-NATIVE-DELETE", "actual qualified deletion refused")
    native_delete = module.LifecycleWriteTarget._windows_delete
    owners = []
    def refuse(owner, handle):
        effect = owner._source_observation
        if effect is not None:
            assert effect.handle == handle and effect.source_owner is owner and effect.current_pair_is_bound()
            owners.append(owner)
            raise sentinel
        return native_delete(owner, handle)
    monkeypatch.setattr(module.LifecycleWriteTarget, "_windows_delete", refuse)
    with pytest.raises(module.LifecycleError) as failed:
        module.close_item(root, slug, closure(instant).encode(), instant,
            inject_readme_failure=True, diagnostic_observer=observer)
    assert failed.value.failure_id == "WI-BUG-DISPOSITIONS-ROLLBACK"
    assert failed.value.__cause__.failure_id == "WI-README-STALE"
    assert observer.snapshot.primaryFailureId == "WI-README-STALE"
    assert observer.snapshot.topLevelKind == "typed-outward"
    assert observer.snapshot.topLevelFailureId == failed.value.failure_id
    assert observer.snapshot.rollback == "incomplete"
    assert any(row.phase == "rollback-action" and row.failureId == sentinel.failure_id
               for row in observer.snapshot.cleanupFailures)
    assert owners and all(not owner._open and owner._source_observation is None for owner in owners)
    assert (active / "status.md").read_bytes() == status_before
    assert (root / "work-items/README.md").read_bytes() == readme_before


@pytest.mark.parametrize("rollback", [False, True])
def test_retirement_native_creator_stage_is_empty_and_released_after_settled_custody(tmp_path, monkeypatch, rollback):
    module = load_module()
    root, slug = tmp_path / "repo", "native-stage-release"
    source, before = _seed_legacy_backlog(root, slug, {"design.md": b"native creator custody\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    make = module.LifecycleWriteTarget.make_directories
    stages = []
    def capture(cls, path, transaction, **kwargs):
        result = make(path, transaction, **kwargs)
        if Path(path).parent == source.parent:
            assert len(kwargs["created"]) == 1
            record = kwargs["created"][0]
            assert record.locator == path and record.creator and record.creation_published
            assert record.finished and record.release_complete
            if os.name == "nt":
                assert record.native_result == 2
            stages.append(record)
        return result
    monkeypatch.setattr(module.LifecycleWriteTarget, "make_directories", classmethod(capture))
    if rollback:
        with pytest.raises(module.LifecycleError) as failed:
            module.retire_legacy_backlog(root, slug, b"Rejected.\n", "2026-08-01T00:00:00Z", inject_readme_failure=True)
        assert failed.value.failure_id == "WI-README-STALE"
        assert (source / "design.md").read_bytes() == before["design.md"]
    else:
        target = module.retire_legacy_backlog(root, slug, b"Rejected.\n", "2026-08-01T00:00:00Z")
        assert (target / "design.md").read_bytes() == before["design.md"] and not source.exists()
    assert len(stages) == 1 and not stages[0].locator.exists()


@pytest.mark.parametrize("mutation", ["foreign-member", "replacement"])
def test_retirement_stage_disposal_preserves_foreign_or_replaced_directory(tmp_path, monkeypatch, mutation):
    module = load_module()
    root, slug = tmp_path / "repo", "stage-foreign-disposal"
    source, before = _seed_legacy_backlog(root, slug, {"design.md": b"original committed payload\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    remove = module.LifecycleWriteTarget.remove_created_directory
    foreign = b"separately owned stage member\n"
    observed = {}
    def interfere(cls, record, transaction, **kwargs):
        if record.locator.parent == source.parent:
            assert record.creator and record.finished and record.release_complete
            observed["record"] = record
            if mutation == "replacement":
                preserved = record.locator.with_name(record.locator.name + ".preserved")
                record.locator.rename(preserved)
                record.locator.mkdir()
                observed["preserved"] = preserved
            member = record.locator / "foreign.bin"
            member.write_bytes(foreign)
            observed["member"] = member
            observed["identity"] = module._lifecycle_file_identity(member.lstat())
        return remove(record, transaction, **kwargs)
    monkeypatch.setattr(module.LifecycleWriteTarget, "remove_created_directory", classmethod(interfere))
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError):
        module.retire_legacy_backlog(root, slug, b"Rejected.\n", "2026-08-01T00:00:00Z", diagnostic_observer=observer)
    assert observed["member"].read_bytes() == foreign
    assert module._lifecycle_file_identity(observed["member"].lstat()) == observed["identity"]
    assert (root / "work-items/archive/2026-08" / slug / "design.md").read_bytes() == before["design.md"]
    assert any(row.phase == "rollback-action" for row in observer.snapshot.cleanupFailures)
    if mutation == "replacement":
        assert module._lifecycle_file_identity(observed["preserved"].lstat()) == observed["record"].identity
        assert module._lifecycle_file_identity(observed["record"].locator.lstat()) != observed["record"].identity


def test_retirement_occupied_restore_target_preserves_both_foreign_and_original_stage(tmp_path, monkeypatch):
    module = load_module()
    root, slug = tmp_path / "repo", "occupied-source-custody"
    source, before = _seed_legacy_backlog(root, slug, {"design.md": b"original retained stage payload\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    move = module.LifecycleTransaction.replace_directory
    stage, observed = [], {"hits": 0}
    foreign = b"foreign restoration target\n"
    def occupy(transaction, current, destination, *args, **kwargs):
        restoring_stage = bool(stage) and current == observed.get("archive") and destination == stage[0]
        if restoring_stage:
            inverse = kwargs["inverse"]
            assert transaction is observed["transaction"]
            assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is transaction and transaction._locked
            assert inverse.transaction is transaction and inverse.source == current and inverse.destination == destination
            assert not inverse.fulfilled and inverse.current_pair_is_bound()
        result = move(transaction, current, destination, *args, **kwargs)
        if current == source and not stage:
            assert kwargs.get("inverse") is None and destination.is_dir() and not source.exists()
            stage.append(destination)
            observed["transaction"] = transaction
        elif stage and current == stage[0] and kwargs.get("inverse") is None:
            observed["archive"] = destination
        if restoring_stage:
            assert inverse.fulfilled and inverse.current_pair_is_bound()
            assert not source.exists() and stage[0].is_dir()
            assert all((stage[0] / name).read_bytes() == body for name, body in before.items())
            observed["hits"] += 1
            assert observed["hits"] == 1
            source.mkdir()
            (source / "foreign.bin").write_bytes(foreign)
            observed["original"] = module._lifecycle_file_identity(stage[0].lstat())
            observed["foreign"] = module._lifecycle_file_identity(source.lstat())
        return result
    monkeypatch.setattr(module.LifecycleTransaction, "replace_directory", occupy)
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError) as failed:
        module.retire_legacy_backlog(root, slug, b"Rejected.\n", "2026-08-01T00:00:00Z",
            inject_readme_failure=True, diagnostic_observer=observer)
    assert observed["hits"] == 1
    assert failed.value.failure_id == "WI-README-STALE"
    assert (source / "foreign.bin").read_bytes() == foreign
    assert (stage[0] / "design.md").read_bytes() == before["design.md"]
    assert module._lifecycle_file_identity(source.lstat()) == observed["foreign"]
    assert module._lifecycle_file_identity(stage[0].lstat()) == observed["original"]
    assert observer.snapshot.rollback == "incomplete"


def test_retirement_existing_uuid_stage_is_never_adopted(tmp_path, monkeypatch):
    module = load_module()
    root, slug = tmp_path / "repo", "stage-collision"
    source, before = _seed_legacy_backlog(root, slug, {"design.md": b"original remains current\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    fixed = module.uuid.UUID(int=1234)
    collision = source.parent / f".{slug}.legacy-retire.{fixed.hex}"
    collision.mkdir()
    (collision / "foreign.bin").write_bytes(b"pre-existing stage candidate\n")
    identity = module._lifecycle_file_identity(collision.lstat())
    monkeypatch.setattr(module.uuid, "uuid4", lambda: fixed)
    with pytest.raises(module.LifecycleError) as failed:
        module.retire_legacy_backlog(root, slug, b"Rejected.\n", "2026-08-01T00:00:00Z")
    assert failed.value.failure_id == "WI-LEGACY-RETIREMENT-INVALID"
    assert module._lifecycle_file_identity(collision.lstat()) == identity
    assert (collision / "foreign.bin").read_bytes() == b"pre-existing stage candidate\n"
    assert (source / "design.md").read_bytes() == before["design.md"]


def test_absent_preimage_readme_restore_keeps_native_ownership_and_invalid_context_refusal(tmp_path):
    module = load_module()
    root = tmp_path / "repo"
    (root / "work-items").mkdir(parents=True)
    readme = root / "work-items/README.md"
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            module._restore_readme_snapshot(readme, None)
            assert not readme.exists()
            module._atomic_write(readme, b"owned README\n")
            module._restore_readme_snapshot(readme, None)
            assert not readme.exists() and readme not in transaction._retained_observations
            readme.write_bytes(b"foreign README\n")
            identity = module._lifecycle_file_identity(readme.lstat())
            with pytest.raises(module.LifecycleError):
                module._restore_readme_snapshot(readme, None)
            assert readme.read_bytes() == b"foreign README\n"
            assert module._lifecycle_file_identity(readme.lstat()) == identity
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
    try:
        with pytest.raises(module.LifecycleError):
            module._restore_readme_snapshot(readme, None)
        assert readme.read_bytes() == b"foreign README\n"
    finally:
        module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_retained_file_observation_keeps_content_identity_policy_and_kind_strict(tmp_path: Path) -> None:
    module, root, source, _destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF", require_single_link=True)
    directory = module._capture_owned_directory_snapshot(source, failure_id="TEST-PROOF")
    variants = (
        replace(original, data=b"X" + original.data[1:]),
        replace(original, length=original.length + 1),
        replace(original, identity=(original.identity[0], original.identity[1] + 1)),
        replace(original, parent_chain=module.CapturedPathParentChain(())),
        replace(directory, path=leaf),
    )
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((original,))
        observations = transaction._retained_observations
        for current in variants:
            with pytest.raises(module.LifecycleError, match="retained-input observation changed during selection"):
                transaction.observe_retained_inputs((current,))
            assert transaction._retained_observations is observations and observations[leaf] is original
        same = replace(original)
        transaction.observe_retained_inputs((same,))
        assert observations[leaf] is same
    unsupported = object()
    assert not module._captured_observations_equivalent(unsupported, unsupported)


@pytest.mark.parametrize("before, incoming", [(False, False), (False, True), (True, False), (True, True)])
def test_retained_file_qualification_joins_verified_boolean_directions(tmp_path, before, incoming):
    module, root, _source, _destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_file_snapshot(leaf, failure_id="TEST", require_single_link=before)
    current = replace(original, require_single_link=incoming)
    assert module._captured_observations_equivalent(original, current)
    assert (original == current) is (before == incoming)
    assert not module._captured_observations_equivalent(original, replace(current, path=outside))
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((original,))
        observations = transaction._retained_observations
        transaction.observe_retained_inputs((current,))
        retained = observations[leaf]
        assert transaction._retained_observations is observations
        assert retained.require_single_link is (before or incoming)
        module._verify_captured_file(retained, "TEST")
        transaction.verify()


@pytest.mark.parametrize("before, incoming", [(False, True), (True, False)])
def test_retained_file_qualification_checks_real_hardlink_in_both_mixed_directions(tmp_path, before, incoming):
    module, root, _source, _destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_file_snapshot(leaf, failure_id="TEST", require_single_link=before)
    link = outside.with_name("hardlink.bin")
    from contextlib import nullcontext
    transaction = module.LifecycleTransaction(root)
    final = pytest.raises(module.LifecycleError) if before else nullcontext()
    with final as outcome:
        with transaction:
            transaction.observe_retained_inputs((original,))
            os.link(leaf, link)
            try:
                weak = module._capture_file_snapshot(leaf, failure_id="TEST")
                assert weak.identity == original.identity and leaf.stat().st_nlink == 2
                current = replace(weak, require_single_link=incoming)
                assert module._captured_observations_equivalent(original, current)
                with pytest.raises(module.LifecycleError) as refused:
                    transaction.observe_retained_inputs((current,))
                assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
                assert transaction._retained_observations[leaf] is original
            finally:
                link.unlink()
            negatives = [value for kind, value in transaction.current_binding_evidence if kind == "integrity-failure"]
            assert bool(negatives) is before
    if before:
        assert outcome.value is refused.value
    assert transaction._file is None and not transaction._locked


def test_retained_file_qualification_refuses_missing_or_malformed_requirements(tmp_path):
    module, root, _source, _destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_file_snapshot(leaf, failure_id="TEST")
    missing = replace(original)
    object.__delattr__(missing, "require_single_link")
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs(())
        assert transaction._retained_observations == {}
        for current in (missing, *(replace(original, require_single_link=value) for value in (None, 0, "false"))):
            with pytest.raises(module.LifecycleError) as refused:
                transaction.observe_retained_inputs((current,))
            assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
            assert leaf not in transaction._retained_observations
        transaction.observe_retained_inputs((original,))
        with pytest.raises(module.LifecycleError):
            transaction.observe_retained_inputs((replace(original, require_single_link=None),))
        assert transaction._retained_observations[leaf] is original


def test_retained_file_qualification_verifier_refusal_keeps_previous_entry(tmp_path, monkeypatch):
    module, root, _source, _destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_file_snapshot(leaf, failure_id="TEST")
    first = module.LifecycleError("TEST-QUALIFICATION", "native verifier refused")
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((original,))
        verify = module._verify_captured_file
        with monkeypatch.context() as scoped:
            def refuse(snapshot, failure_id):
                assert snapshot.path == leaf
                if snapshot.require_single_link is True:
                    raise first
                return verify(snapshot, failure_id)
            scoped.setattr(module, "_verify_captured_file", refuse)
            with pytest.raises(module.LifecycleError) as refused:
                transaction.observe_retained_inputs((replace(original, require_single_link=True),))
            assert refused.value is first
            assert transaction._retained_observations[leaf] is original


def test_retained_file_qualification_missing_file_and_native_lock_proof_refuse(tmp_path, monkeypatch):
    module, root, _source, _destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_file_snapshot(leaf, failure_id="TEST")
    current = replace(original, require_single_link=True)
    held = leaf.with_name("held.bin")
    transaction = module.LifecycleTransaction(root)
    with pytest.raises(module.LifecycleError) as final:
        with transaction:
            transaction.observe_retained_inputs((original,))
            leaf.rename(held)
            try:
                with pytest.raises(module.LifecycleError):
                    transaction.observe_retained_inputs((current,))
                assert transaction._retained_observations[leaf] is original
            finally:
                held.rename(leaf)
            with monkeypatch.context() as scoped:
                scoped.setattr(transaction, "_identity", (0, 0))
                with pytest.raises(module.LifecycleError) as refused:
                    transaction.observe_retained_inputs((current,))
                assert refused.value.failure_id == "WI-LIFECYCLE-LOCK-IDENTITY"
                assert transaction._retained_observations[leaf] is original
            assert any(kind == "integrity-failure" for kind, _value in transaction.current_binding_evidence)
    assert final.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
    with pytest.raises(module.LifecycleError) as released:
        transaction.observe_retained_inputs((current,))
    assert released.value.failure_id == "WI-LIFECYCLE-LOCK-IDENTITY"
    assert transaction._retained_observations[leaf] is original


def test_retained_file_qualification_source_failure_is_sticky_and_clears_validator(tmp_path, monkeypatch):
    module, root, _source, _destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_file_snapshot(leaf, failure_id="TEST")
    first = module.LifecycleError("TEST-SOURCE", "selected source verification refused")
    with pytest.raises(module.LifecycleError) as final:
        with module.LifecycleTransaction(root) as transaction:
            transaction.observe_retained_inputs((original,))
            transaction._validator_reuse = object()
            verify = module._verify_captured_file
            def refuse(snapshot, failure_id):
                if snapshot.path == leaf and snapshot.require_single_link:
                    raise first
                return verify(snapshot, failure_id)
            monkeypatch.setattr(transaction, "_is_runtime_source", lambda path: path == leaf)
            monkeypatch.setattr(module, "_verify_captured_file", refuse)
            with pytest.raises(module.LifecycleError) as refused:
                transaction.observe_retained_inputs((replace(original, require_single_link=True),))
            assert refused.value is first
            assert transaction._retained_observations[leaf] is original
            assert transaction._source_admission_failure is first
            assert transaction._validator_reuse is None
            transaction.observe_retained_inputs((original,))
    assert final.value is first and not transaction._locked


def test_retained_file_qualification_strengthening_invalidates_prepared_effect(tmp_path):
    module, root, _source, _destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_file_snapshot(leaf, failure_id="TEST")
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            transaction.observe_retained_inputs((original,))
            with module.LifecycleWriteTarget(leaf, failure_id="TEST", _operation_owner=transaction) as owner:
                prepared = transaction.prepare_owned_effect(owner, None, leaf, data=original.data, replace_existing=True)
                assert prepared.current_pair_is_bound()
                transaction.observe_retained_inputs((replace(original, require_single_link=True),))
                assert not prepared.current_pair_is_bound()
                with pytest.raises(module.LifecycleError) as refused:
                    transaction.publish_owned_effect(prepared, native_identity=original.identity)
                assert refused.value.failure_id == "WI-LIFECYCLE-EFFECT"
            module._atomic_write(leaf, b"qualified next image")
            assert transaction._retained_observations[leaf].require_single_link is True
            transaction.verify()
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_retained_file_qualification_keeps_zero_byte_and_weak_hardlinked_files_valid(tmp_path):
    module, root, _source, _destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    leaf.write_bytes(b"")
    link = outside.with_name("weak-hardlink.bin")
    os.link(leaf, link)
    try:
        snapshot = module._capture_file_snapshot(leaf, failure_id="TEST")
        assert snapshot.data == b"" and snapshot.length == 0 and leaf.stat().st_nlink == 2
        with module.LifecycleTransaction(root) as transaction:
            transaction.observe_retained_inputs((snapshot, replace(snapshot)))
            assert transaction._retained_observations[leaf].require_single_link is False
            transaction.verify()
    finally:
        link.unlink()


@pytest.mark.parametrize("transport", ("direct", "participant"))
def test_transaction_failed_acquired_entry_keeps_primary_and_both_closer_failures(tmp_path: Path, monkeypatch, transport) -> None:
    module, root, _source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    primary = module.LifecycleError("TEST-ENTRY", "actual acquired entry receiving failure")
    events, transactions, exits, body = [], [], [], []
    native_lock, native_unlock = module.LifecycleTransaction._native_lock, module.LifecycleTransaction._native_unlock
    real_exit = module.LifecycleTransaction.__exit__
    class CloseFailure:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def close(self):
            events.append("close")
            self.stream.close()
            raise OSError("actual entry close secondary")
    def acquire(transaction):
        native_lock(transaction)
        transactions.append(transaction)
        transaction._file = CloseFailure(transaction._file)
    def fail_receiving(transaction, **kwargs):
        assert transaction._locked
        events.append("entry")
        raise primary
    def unlock(transaction):
        events.append("unlock")
        native_unlock(transaction)
        raise OSError("actual entry unlock secondary")
    def exit_once(transaction, *args):
        exits.append(transaction)
        return real_exit(transaction, *args)
    monkeypatch.setattr(module.LifecycleTransaction, "_native_lock", acquire)
    monkeypatch.setattr(module.LifecycleTransaction, "verify", fail_receiving)
    monkeypatch.setattr(module.LifecycleTransaction, "_native_unlock", unlock)
    monkeypatch.setattr(module.LifecycleTransaction, "__exit__", exit_once)
    observer = module.LifecycleDiagnosticObserver()
    def action(root):
        body.append(True)
    with pytest.raises(module.LifecycleError) as caught:
        if transport == "participant":
            module._lifecycle_participant(action)(root, diagnostic_observer=observer)
        else:
            with module.LifecycleTransaction(root):
                action(root)
    assert caught.value is primary and not body and not exits
    assert events == ["entry", "unlock", "close"]
    assert len(transactions) == 1 and not transactions[0]._locked and transactions[0]._file.closed
    if transport == "participant":
        assert tuple(row.phase for row in observer.snapshot.cleanupFailures) == ("transaction-release", "transaction-file-close")
        assert tuple(row.failureId for row in observer.snapshot.cleanupFailures) == ("WI-LIFECYCLE-LOCK-IDENTITY",) * 2
    else:
        assert any("actual entry unlock secondary" in note for note in primary.__notes__)
        assert any("actual entry close secondary" in note for note in primary.__notes__)


@pytest.mark.parametrize("acquisition", ("absent", "stream"))
def test_transaction_entry_settles_only_actual_acquisitions(tmp_path: Path, monkeypatch, acquisition) -> None:
    module, root, _source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    primary = module.LifecycleError("TEST-ENTRY", "actual entry acquisition refusal")
    events, transactions, body = [], [], []
    ensure = module.LifecycleTransaction._ensure_lock_file
    class ObservedStream:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def close(self):
            events.append("close")
            self.stream.close()
    def prepare(transaction):
        transactions.append(transaction)
        if acquisition == "absent":
            raise primary
        return ensure(transaction)
    def lock(transaction):
        assert not transaction._locked and transaction._file is not None
        transaction._file = ObservedStream(transaction._file)
        raise primary
    monkeypatch.setattr(module.LifecycleTransaction, "_ensure_lock_file", prepare)
    monkeypatch.setattr(module.LifecycleTransaction, "_native_lock", lock)
    monkeypatch.setattr(module.LifecycleTransaction, "_native_unlock", lambda transaction: events.append("unexpected-unlock"))
    observer = module.LifecycleDiagnosticObserver()
    @module._lifecycle_participant
    def action(root):
        body.append(True)
    with pytest.raises(module.LifecycleError) as caught:
        action(root, diagnostic_observer=observer)
    assert caught.value is primary and not body
    assert events == ([] if acquisition == "absent" else ["close"])
    assert transactions[0]._file is None and not transactions[0]._locked
    assert observer.snapshot.cleanupFailures == ()


@pytest.mark.parametrize("transport", ("direct", "participant"))
def test_transaction_exit_retains_verification_unlock_and_close_outcomes(tmp_path: Path, monkeypatch, transport) -> None:
    module, root, _source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    primary = module.LifecycleError("TEST-BODY", "actual body primary")
    verification = module.LifecycleError("TEST-VERIFY", "actual exit verification secondary")
    events, transactions = [], []
    native_unlock = module.LifecycleTransaction._native_unlock
    class CloseFailure:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def close(self):
            events.append("close")
            self.stream.close()
            raise OSError("actual exit close secondary")
    def unlock(transaction):
        events.append("unlock")
        native_unlock(transaction)
        raise OSError("actual exit unlock secondary")
    def fail_verification(**kwargs):
        events.append("verify")
        raise verification
    def action(root):
        transaction = module._CURRENT_LIFECYCLE_TRANSACTION.get() if transport == "participant" else transactions[0]
        if transport == "participant":
            transactions.append(transaction)
        transaction._file = CloseFailure(transaction._file)
        monkeypatch.setattr(transaction, "verify", fail_verification)
        raise primary
    monkeypatch.setattr(module.LifecycleTransaction, "_native_unlock", unlock)
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError) as caught:
        if transport == "participant":
            module._lifecycle_participant(action)(root, diagnostic_observer=observer)
        else:
            with module.LifecycleTransaction(root) as transaction:
                transactions.append(transaction)
                action(root)
    assert caught.value is primary
    assert events == ["verify", "unlock", "close"]
    assert not transactions[0]._locked and transactions[0]._file.closed
    if transport == "participant":
        rows = observer.snapshot.cleanupFailures
        assert tuple(row.phase for row in rows) == ("transaction-release", "transaction-file-close", "transaction-verification")
        assert tuple(row.failureId for row in rows) == ("WI-LIFECYCLE-LOCK-IDENTITY", "WI-LIFECYCLE-LOCK-IDENTITY", "TEST-VERIFY")
        assert rows[-1].resource is None
        assert all(row.causeType == "OSError" for row in rows[:2]) and rows[-1].causeType == "LifecycleError"
    else:
        assert all(any(word in note for note in primary.__notes__) for word in (
            "actual exit unlock secondary", "actual exit close secondary", "actual exit verification secondary"))


def test_transaction_cleanup_delivery_failure_keeps_acquired_outcomes_and_closers(tmp_path: Path, monkeypatch) -> None:
    module, root, _source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    primary = module.LifecycleError("TEST-BODY", "original before failed outcome delivery")
    events, phases = [], []
    record = module.LifecycleOutcomeComposer.record_cleanup
    unlock = module.LifecycleTransaction._native_unlock
    def release(transaction):
        unlock(transaction)
        events.append("unlock")
        raise OSError("real native unlock observation")
    def record_then_fail(composer, **kwargs):
        assert events == ["unlock"]
        phases.append(kwargs["phase"])
        if kwargs["phase"] == "transaction-release":
            raise RuntimeError("actual optional delivery failure")
        return record(composer, **kwargs)
    monkeypatch.setattr(module.LifecycleTransaction, "_native_unlock", release)
    monkeypatch.setattr(module.LifecycleOutcomeComposer, "record_cleanup", record_then_fail)
    @module._lifecycle_participant
    def action(root):
        transaction = module._CURRENT_LIFECYCLE_TRANSACTION.get()
        def verify(**kwargs):
            raise ValueError("actual untyped verification")
        monkeypatch.setattr(transaction, "verify", verify)
        raise primary
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError) as caught:
        action(root, diagnostic_observer=observer)
    assert caught.value is primary and events == ["unlock"]
    assert phases == ["transaction-release", "transaction-verification"]
    assert any("real native unlock observation" in note for note in primary.__notes__)
    assert any("actual untyped verification" in note for note in primary.__notes__)
    assert any("actual optional delivery failure" in note for note in primary.__notes__)
    assert tuple(row.phase for row in observer.snapshot.cleanupFailures) == ("transaction-verification",)
    assert observer.snapshot.cleanupFailures[0].failureId == "WI-LIFECYCLE-EFFECT"


def test_placement_receiving_precedes_fallible_readback_and_allows_verified_reuse(tmp_path: Path, monkeypatch) -> None:
    module, root, _source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    path = root / "placed.bin"
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            with module.LifecycleWriteTarget(path, failure_id="TEST-PLACEMENT") as writer:
                read = writer.read
                primary = module.LifecycleError("TEST-READBACK", "actual postplacement readback failure")
                def read_then_fail(**kwargs):
                    assert read(**kwargs) == b"placed"
                    record = writer._creations[-1]
                    assert record.phase == "final-placed" and not record.finished
                    raise primary
                with monkeypatch.context() as scoped:
                    scoped.setattr(writer, "read", read_then_fail)
                    with pytest.raises(module.LifecycleError) as caught:
                        writer.publish(b"placed")
                assert caught.value is primary
                record = writer._creations[-1]
                assert record.phase == "final-placed" and record.finished and record.release_complete
                assert record.raw_failure is primary and path.read_bytes() == b"placed"
                writer.publish(b"restored")
                assert path.read_bytes() == b"restored"
                writer.verify()
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_transaction_directory_move_preserves_exact_descendants_and_inverse(tmp_path: Path) -> None:
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    original = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF", require_single_link=True)
    separate = module._capture_file_snapshot(outside, failure_id="TEST-PROOF")
    directory_identity = source.stat().st_dev, source.stat().st_ino
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((original, separate))
        transaction.replace_directory(source, destination)
        moved = destination / "nested/proof.bin"
        relocated = transaction._retained_observations[moved]
        assert (relocated.identity, relocated.length, relocated.data, relocated.require_single_link) == (
            original.identity, original.length, original.data, original.require_single_link,
        )
        assert transaction._retained_observations[outside] is separate
        assert (destination.stat().st_dev, destination.stat().st_ino) == directory_identity
        transaction.replace_directory(destination, source)
        assert transaction._retained_observations[leaf] == original
        assert transaction._retained_observations[outside] is separate
        transaction.verify()


def test_transaction_directory_native_failure_keeps_observation_map(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    snapshot = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF")
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((snapshot,))
        before = transaction._retained_observations
        def failed_replace(*_args):
            raise PermissionError("injected native directory failure")
        monkeypatch.setattr(module.os, "rename" if module.os.name == "nt" else "replace", failed_replace)
        with pytest.raises(PermissionError, match="native directory failure"):
            transaction.replace_directory(source, destination)
        assert transaction._retained_observations is before
        assert source.is_dir() and not destination.exists()
        transaction.verify()


def test_transaction_postmove_proof_failure_compensates_before_return(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    snapshot = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF")
    separate = module._capture_file_snapshot(outside, failure_id="TEST-PROOF")
    identity = source.stat().st_dev, source.stat().st_ino
    with module.LifecycleTransaction(root) as transaction:
        # Acquire after the lock namespace exists: the selected originals must
        # include the direct parent AND the ancestor that represents its key.
        originals = tuple(module._capture_owned_directory_snapshot(path, failure_id="TEST-PROOF")
                          for path in (root, destination.parent))
        transaction.observe_retained_inputs((snapshot, separate, *originals))
        transaction._binding_evidence += (("membership", (destination.parent, ())),
                                         ("chain", originals[1].parent_chain))
        before = transaction._retained_observations
        evidence_before = transaction.current_binding_evidence
        keys_before = tuple(module._lifecycle_file_snapshot_key(value.metadata) for value in originals)
        bindings_before = tuple(value.capture_binding for value in originals)
        verify = transaction._verify_observation_map
        primary = module.LifecycleError("TEST-POST-MOVE", "injected postmove proof failure")
        rejected = []
        def fail_after_real_candidate_check(observations):
            verify(observations)
            if not rejected and destination / "nested/proof.bin" in observations:
                assert transaction._retained_observations is before
                assert transaction.current_binding_evidence is evidence_before
                changed_parent = observations[destination.parent]
                assert module._lifecycle_file_snapshot_key(changed_parent.metadata) != keys_before[1]
                ancestor = observations[root]
                assert module._lifecycle_file_snapshot_key(dict(ancestor.members)[destination.parent.name]) == (
                    module._lifecycle_file_snapshot_key(changed_parent.metadata))
                rejected.append(observations)
                raise primary
        monkeypatch.setattr(transaction, "_verify_observation_map", fail_after_real_candidate_check)
        with pytest.raises(module.LifecycleError, match="postmove proof failure") as caught:
            transaction.replace_directory(source, destination)
        assert caught.value is primary and len(rejected) == 1
        assert transaction._retained_observations is not before
        assert transaction.current_binding_evidence is not evidence_before
        assert transaction._retained_observations is not rejected[0]
        assert transaction._retained_observations[leaf] is snapshot
        assert transaction._retained_observations[outside] is separate
        assert tuple(module._lifecycle_file_snapshot_key(value.metadata) for value in originals) == keys_before
        assert tuple(value.capture_binding for value in originals) == bindings_before
        current_root = transaction._retained_observations[root]
        current_parent = transaction._retained_observations[destination.parent]
        assert module._lifecycle_file_snapshot_key(current_parent.metadata) != keys_before[1]
        assert module._lifecycle_file_snapshot_key(dict(current_root.members)[destination.parent.name]) == (
            module._lifecycle_file_snapshot_key(current_parent.metadata))
        assert set(name for name, _meta in current_parent.members) == set(name for name, _meta in originals[1].members)
        assert current_parent.capture_binding == module._directory_capture_binding(current_parent)
        assert current_root.capture_binding == module._directory_capture_binding(current_root)
        membership = next(value for kind, value in transaction.current_binding_evidence
                          if kind == "membership" and value[0] == destination.parent)
        assert membership[1] == tuple(name for name, _meta in current_parent.members)
        assert ("chain", current_parent.parent_chain) in transaction.current_binding_evidence
        assert (source.stat().st_dev, source.stat().st_ino) == identity
        assert not destination.exists() and leaf.read_bytes() == snapshot.data
        assert transaction._unsettled_relocations == ()
        transaction.verify()


def test_transaction_file_postmove_proof_failure_compensates_before_return(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    target = destination.parent / "moved-proof.bin"
    snapshot = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF", require_single_link=True)
    separate = module._capture_file_snapshot(outside, failure_id="TEST-PROOF")
    primary = module.LifecycleError("TEST-POST-MOVE", "injected file postmove proof failure")
    with module.LifecycleTransaction(root) as transaction:
        originals = tuple(module._capture_owned_directory_snapshot(path, failure_id="TEST-PROOF")
                          for path in (leaf.parent, source, root, destination.parent))
        transaction.observe_retained_inputs((snapshot, separate, *originals))
        transaction._binding_evidence += (("node", module._capture_structural_node(leaf, "TEST-PROOF")),)
        before = transaction._retained_observations
        evidence_before = transaction.current_binding_evidence
        verify = transaction._verify_observation_map
        rejected = []
        def fail_after_real_candidate_check(observations):
            verify(observations)
            if not rejected and target in observations:
                assert transaction._retained_observations is before
                assert transaction.current_binding_evidence is evidence_before
                assert observations[target].identity == snapshot.identity
                assert observations[target].data == snapshot.data
                assert observations[target].require_single_link
                rejected.append(observations)
                raise primary
        monkeypatch.setattr(transaction, "_verify_observation_map", fail_after_real_candidate_check)
        with pytest.raises(module.LifecycleError, match="file postmove proof failure") as caught:
            transaction.replace_directory(leaf, target, directory=False)
        assert caught.value is primary and len(rejected) == 1
        assert not target.exists() and leaf.read_bytes() == snapshot.data
        assert (leaf.stat().st_dev, leaf.stat().st_ino) == snapshot.identity
        assert transaction._retained_observations is not before
        assert transaction.current_binding_evidence is not evidence_before
        assert transaction.current_observation(snapshot) == snapshot
        assert transaction._retained_observations[outside] is separate
        assert before[leaf] is snapshot and snapshot.path == leaf
        assert transaction._unsettled_relocations == ()
        assert any(kind == "node" and value[0] == leaf for kind, value in transaction.current_binding_evidence)
        transaction.verify()


def test_transaction_compensation_refuses_restored_descendant_byte_drift(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    snapshot = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF")
    real_replace = (module.os.rename if module.os.name == "nt" else module.os.replace)
    primary = module.LifecycleError("TEST-POST-MOVE", "injected postmove proof failure")
    transaction = module.LifecycleTransaction(root)
    transaction.__enter__()
    transaction.observe_retained_inputs((snapshot,))
    before = transaction._retained_observations
    evidence_before = transaction.current_binding_evidence
    verify = transaction._verify_observation_map
    rejected = []
    reverse_checks = []
    def fail_after_real_candidate_check(observations):
        verify(observations)
        if not rejected and destination / "nested/proof.bin" in observations:
            rejected.append(observations)
            raise primary
    def replace_then_change_restored_leaf(old, new):
        real_replace(old, new)
        if Path(old) == destination and Path(new) == source:
            paths = (source, root, destination.parent)
            directories = tuple(module._capture_owned_directory_snapshot(path, failure_id="TEST-PROOF")
                                for path in paths)
            leaf.write_bytes(b"unowned changed retained evidence")
            current = tuple(module._capture_owned_directory_snapshot(path, failure_id="TEST-PROOF")
                            for path in paths)
            # A descendant payload write leaves these immediate directory
            # views intact; only the original retained file proof catches it.
            for original, observed in zip(directories, current):
                assert module._lifecycle_file_snapshot_key(original.metadata) == (
                    module._lifecycle_file_snapshot_key(observed.metadata))
                assert tuple((name, module._lifecycle_file_snapshot_key(meta)) for name, meta in original.members) == (
                    tuple((name, module._lifecycle_file_snapshot_key(meta)) for name, meta in observed.members))
            reverse_checks.append(current)
    monkeypatch.setattr(transaction, "_verify_observation_map", fail_after_real_candidate_check)
    monkeypatch.setattr(module.os, "rename" if module.os.name == "nt" else "replace", replace_then_change_restored_leaf)
    try:
        with pytest.raises(module.LifecycleError, match="postmove proof failure.*rollback failed.*identity or content changed") as caught:
            transaction.replace_directory(source, destination)
        assert caught.value.failure_id == "WI-LIFECYCLE-RELOCATION-ROLLBACK"
        assert caught.value.__cause__ is primary
        assert len(rejected) == len(reverse_checks) == 1
        assert transaction._retained_observations is before
        assert transaction.current_binding_evidence[:len(evidence_before)] == evidence_before
        assert len(transaction.current_binding_evidence) == len(evidence_before) + 1
        kind, (constraint, integrity_failure, failed_paths) = transaction.current_binding_evidence[-1]
        assert kind == "integrity-failure"
        assert constraint is snapshot
        assert integrity_failure.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
        assert "captured file path identity or content changed" in str(integrity_failure)
        assert failed_paths == (leaf,)
        assert transaction._retained_observations[leaf] is snapshot
        assert leaf.read_bytes() == b"unowned changed retained evidence"
        assert source.is_dir() and not destination.exists()
        assert len(transaction._unsettled_relocations) == 1
        with pytest.raises(module.LifecycleError) as sticky:
            transaction.verify()
        assert sticky.value is integrity_failure
    finally:
        with pytest.raises(module.LifecycleError):
            transaction.__exit__(None, None, None)


def test_transaction_directory_projection_refuses_unowned_sibling_metadata(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    snapshot = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF")
    real_replace = (module.os.rename if module.os.name == "nt" else module.os.replace)
    sibling = outside.parent
    transaction = module.LifecycleTransaction(root)
    transaction.__enter__()
    original_root = module._capture_owned_directory_snapshot(root, failure_id="TEST-PROOF")
    transaction.observe_retained_inputs((snapshot, original_root))
    before = transaction._retained_observations
    evidence_before = transaction.current_binding_evidence
    sibling_before = module._lifecycle_file_snapshot_key(dict(original_root.members)[sibling.name])
    def replace_then_change_sibling(old, new):
        real_replace(old, new)
        if Path(old) == source:
            (sibling / "unowned-entry.bin").write_bytes(b"foreign sibling namespace")
    monkeypatch.setattr(module.os, "rename" if module.os.name == "nt" else "replace", replace_then_change_sibling)
    try:
        with pytest.raises(module.LifecycleError, match="unrelated directory member changed.*rollback failed") as caught:
            transaction.replace_directory(source, destination)
        assert caught.value.failure_id == "WI-LIFECYCLE-RELOCATION-ROLLBACK"
        assert "unrelated directory member changed" in str(caught.value.__cause__)
        assert module._lifecycle_file_snapshot_key(sibling.stat()) != sibling_before
        assert (sibling / "unowned-entry.bin").read_bytes() == b"foreign sibling namespace"
        assert transaction._retained_observations is before
        assert transaction.current_binding_evidence is evidence_before
        assert len(transaction._unsettled_relocations) == 1
        assert not source.exists() and destination.is_dir()
    finally:
        with pytest.raises(module.LifecycleError):
            transaction.__exit__(None, None, None)


def test_transaction_relocation_does_not_recapture_replacement_leaf(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    snapshot = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF")
    real_replace = (module.os.rename if module.os.name == "nt" else module.os.replace)
    replacement = root / "same-bytes.bin"
    replacement.write_bytes(snapshot.data)
    replacement_identity = replacement.stat().st_dev, replacement.stat().st_ino
    directory_identity = source.stat().st_dev, source.stat().st_ino
    transaction = module.LifecycleTransaction(root)
    transaction.__enter__()
    transaction.observe_retained_inputs((snapshot,))
    before = transaction._retained_observations
    evidence_before = transaction.current_binding_evidence
    publish = transaction.publish_owned_effect
    publication_failures = []
    def publish_and_retain_failure(*args, **kwargs):
        try:
            return publish(*args, **kwargs)
        except BaseException as failure:
            publication_failures.append(failure)
            raise
    def replace_then_substitute(old, new):
        real_replace(old, new)
        if Path(old) == source:
            module.os.replace(replacement, destination / "nested/proof.bin")
    monkeypatch.setattr(module.os, "rename" if module.os.name == "nt" else "replace", replace_then_substitute)
    monkeypatch.setattr(transaction, "publish_owned_effect", publish_and_retain_failure)
    try:
        with pytest.raises(module.LifecycleError, match="rollback failed") as caught:
            transaction.replace_directory(source, destination)
        assert caught.value.failure_id == "WI-LIFECYCLE-RELOCATION-ROLLBACK"
        assert len(publication_failures) == 2
        assert caught.value.__cause__ is publication_failures[0]
        assert str(publication_failures[1]) in str(caught.value)
        assert transaction._retained_observations is before
        assert transaction.current_binding_evidence is evidence_before
        assert transaction._retained_observations[leaf] is snapshot
        moved_leaf = destination / "nested/proof.bin"
        assert not source.exists()
        assert (destination.stat().st_dev, destination.stat().st_ino) == directory_identity
        assert (moved_leaf.stat().st_dev, moved_leaf.stat().st_ino) == replacement_identity != snapshot.identity
        assert moved_leaf.read_bytes() == snapshot.data
        descriptor, = transaction._unsettled_relocations
        assert (descriptor.source, descriptor.destination, descriptor.identity) == (
            source, destination, directory_identity)
    finally:
        with pytest.raises(module.LifecycleError):
            transaction.__exit__(None, None, None)


def test_transaction_zero_observation_move_and_overlapping_refusal(tmp_path: Path) -> None:
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    identities = tuple(module._lifecycle_file_identity(path.lstat()) for path in (source, leaf.parent, leaf, outside))
    original_bytes, outside_bytes = leaf.read_bytes(), outside.read_bytes()
    with module.LifecycleTransaction(root) as transaction:
        admission = transaction._admission_evidence
        with pytest.raises(module.LifecycleError, match="overlaps"):
            transaction.replace_directory(source, source / "nested/new")
        assert transaction._retained_observations == {} and source.is_dir()
        transaction.replace_directory(source, destination)
        assert destination.is_dir() and not source.exists()
        assert set(transaction._retained_observations) == {destination}
        current = transaction._retained_observations[destination]
        assert isinstance(current, module.CapturedDirectorySnapshotV1) and current.path == destination
        assert module._lifecycle_file_identity(current.metadata) == identities[0]
        assert tuple((name, module._lifecycle_file_identity(info)) for name, info in current.members) == (("nested", identities[1]),)
        moved = destination / "nested/proof.bin"
        assert tuple(module._lifecycle_file_identity(path.lstat()) for path in (destination, moved.parent, moved, outside)) == identities
        assert moved.read_bytes() == original_bytes and outside.read_bytes() == outside_bytes
        assert transaction._admission_evidence is admission
        transaction.verify()


def test_transaction_unsafe_inverse_preserves_reappeared_source_and_primary(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    snapshot = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF")
    transaction = module.LifecycleTransaction(root)
    transaction.__enter__()
    transaction.observe_retained_inputs((snapshot,))
    original_directory = source.stat().st_dev, source.stat().st_ino
    verify = transaction._verify_observation_map
    def reappear_after_real_candidate_check(observations):
        verify(observations)
        if destination / "nested/proof.bin" in observations:
            source.mkdir()
            (source / "foreign.bin").write_bytes(b"reappeared unrelated bytes")
            raise module.LifecycleError("TEST-PRIMARY", "original postmove failure")
    monkeypatch.setattr(transaction, "_verify_observation_map", reappear_after_real_candidate_check)
    try:
        with pytest.raises(module.LifecycleError, match="relocation failed: original postmove failure; rollback failed") as failed:
            transaction.replace_directory(source, destination)
        assert isinstance(failed.value.__cause__, module.LifecycleError)
        assert failed.value.__cause__.failure_id == "TEST-PRIMARY"
        assert (source / "foreign.bin").read_bytes() == b"reappeared unrelated bytes"
        assert (destination.stat().st_dev, destination.stat().st_ino) == original_directory
        assert transaction._retained_observations[leaf] is snapshot
    finally:
        with pytest.raises(module.LifecycleError):
            transaction.__exit__(None, None, None)


def test_transaction_outside_drift_refuses_move_without_rebasing(tmp_path: Path) -> None:
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    snapshots = [module._capture_file_snapshot(p, failure_id="TEST-PROOF") for p in (leaf, outside)]
    transaction = module.LifecycleTransaction(root)
    transaction.__enter__()
    transaction.observe_retained_inputs(snapshots)
    before = transaction._retained_observations
    outside.write_bytes(b"outside changed bytes")
    try:
        with pytest.raises(module.LifecycleError):
            transaction.replace_directory(source, destination)
        assert transaction._retained_observations is before and source.is_dir() and not destination.exists()
    finally:
        with pytest.raises(module.LifecycleError):
            transaction.__exit__(None, None, None)


def test_transaction_substituted_directory_is_preserved_and_never_adopted(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    snapshot = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF")
    identity = source.stat().st_dev, source.stat().st_ino
    displaced = root / "displaced-original"
    real_replace = (module.os.rename if module.os.name == "nt" else module.os.replace)
    transaction = module.LifecycleTransaction(root)
    transaction.__enter__()
    transaction.observe_retained_inputs((snapshot,))
    def replace_then_substitute_directory(old, new):
        real_replace(old, new)
        if Path(old) == source:
            real_replace(destination, displaced)
            (destination / "nested").mkdir(parents=True)
            (destination / "nested/proof.bin").write_bytes(snapshot.data)
    monkeypatch.setattr(module.os, "rename" if module.os.name == "nt" else "replace", replace_then_substitute_directory)
    try:
        with pytest.raises(module.LifecycleError, match="original moved directory.*rollback failed"):
            transaction.replace_directory(source, destination)
        assert (displaced.stat().st_dev, displaced.stat().st_ino) == identity
        assert (destination / "nested/proof.bin").read_bytes() == snapshot.data
        assert transaction._retained_observations[leaf] is snapshot and not source.exists()
    finally:
        with pytest.raises(module.LifecycleError):
            transaction.__exit__(None, None, None)


def test_transaction_unsafe_destination_ancestor_refuses_before_native_move(tmp_path: Path) -> None:
    module, root, source, destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    snapshot = module._capture_file_snapshot(leaf, failure_id="TEST-PROOF")
    ordinary = root / "ordinary-archive"
    ordinary.mkdir()
    destination.parent.rmdir()
    destination.parent.symlink_to(ordinary, target_is_directory=True)
    with module.LifecycleTransaction(root) as transaction:
        transaction.observe_retained_inputs((snapshot,))
        before = transaction._retained_observations
        with pytest.raises(module.LifecycleError, match="unsafe"):
            transaction.replace_directory(source, destination)
        assert transaction._retained_observations is before
        assert source.is_dir() and leaf.read_bytes() == snapshot.data and not (ordinary / destination.name).exists()
        transaction.verify()


def test_unsettled_relocation_scope_is_component_bound_and_reentry_refuses(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, _leaf, outside = _relocation_observation_fixture(tmp_path)
    identity = source.stat().st_dev, source.stat().st_ino
    with module.LifecycleTransaction(root) as transaction:
        verify = transaction._verify_observation_map
        def fail_after_native_check(observations):
            verify(observations)
            if destination.exists() and not source.exists():
                source.mkdir()
                (source / "foreign.bin").write_bytes(b"foreign data")
                raise module.LifecycleError("TEST-PRIMARY", "unsettled native move")
        monkeypatch.setattr(transaction, "_verify_observation_map", fail_after_native_check)
        with pytest.raises(module.LifecycleError, match="rollback failed"):
            transaction.replace_directory(source, destination)
        descriptor, = transaction._unsettled_relocations
        assert (descriptor.source, descriptor.destination, descriptor.identity) == (source, destination, identity)
        with pytest.raises(AttributeError):
            descriptor.source = outside
        for path in (source, source / "child", destination, destination / "child", source.parent, destination.parent):
            assert transaction.cleanup_intersects_unsettled((path,))
        assert not transaction.cleanup_intersects_unsettled((outside,))
        assert not transaction.cleanup_intersects_unsettled(())
        assert transaction.cleanup_intersects_unsettled((outside, destination))
        assert transaction.cleanup_intersects_unsettled((source, outside))
        with pytest.raises(module.LifecycleError, match="intersects unsettled"):
            transaction.replace_directory(source, root / "new-target")
        assert (source / "foreign.bin").read_bytes() == b"foreign data" and destination.is_dir()
        # A proven unrelated file disposition is still allowed, not globally disabled.
        outside.unlink()
        assert not outside.exists()
    assert transaction._unsettled_relocations == (descriptor,)
    with pytest.raises(module.LifecycleError, match="held lifecycle transaction"):
        module._lifecycle_cleanup_intersects_unsettled(outside)


def test_unsettled_descriptor_survives_cleanup_diagnostic_exception(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    composer = module.LifecycleOutcomeComposer()
    token = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.set(composer)
    try:
        with module.LifecycleTransaction(root) as transaction:
            verify = transaction._verify_observation_map
            def fail_candidate(observations):
                verify(observations)
                if destination.exists() and not source.exists():
                    source.mkdir()
                    raise module.LifecycleError("TEST-PRIMARY", "original candidate failure")
            def fail_diagnostic(**_kwargs):
                raise ValueError("diagnostic recorder failed")
            monkeypatch.setattr(transaction, "_verify_observation_map", fail_candidate)
            monkeypatch.setattr(composer, "record_cleanup", fail_diagnostic)
            with pytest.raises(ValueError, match="diagnostic recorder"):
                transaction.replace_directory(source, destination)
            assert transaction.cleanup_intersects_unsettled((destination.parent,))
            assert composer.finalize().primary.failure_id == "TEST-PRIMARY"
    finally:
        module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.reset(token)


def test_caught_inverse_error_cannot_complete_unsettled_rollback(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    bundles = []
    strings = []
    transactions = []
    primary = module.LifecycleError("TEST-CALLER-PRIMARY", "primary before inverse")
    finalize = module.LifecycleOutcomeComposer.finalize
    def capture(self):
        bundle = finalize(self)
        bundles.append(bundle)
        return bundle
    monkeypatch.setattr(module.LifecycleOutcomeComposer, "finalize", capture)
    @module._lifecycle_participant
    def caller(root):
        transaction = module._CURRENT_LIFECYCLE_TRANSACTION.get()
        transactions.append(transaction)
        composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
        transaction.replace_directory(source, destination)
        composer.capture_primary(primary)
        verify = transaction._verify_observation_map
        def fail_inverse(observations):
            verify(observations)
            if source.exists() and not destination.exists():
                destination.mkdir()
                (destination / "foreign.bin").write_bytes(b"foreign inverse source")
                raise module.LifecycleError("TEST-INVERSE", "secondary inverse failure")
        monkeypatch.setattr(transaction, "_verify_observation_map", fail_inverse)
        try:
            transaction.replace_directory(destination, source)
        except module.LifecycleError as secondary:
            strings.append(str(secondary))
        composer.set_rollback("completed")
        return "caller bookkeeping completed"
    with pytest.raises(module.LifecycleError, match="primary before inverse") as caught:
        caller(root)
    assert caught.value is primary and bundles[-1].primary is primary
    assert strings == ["secondary inverse failure"]
    assert bundles[-1].rollback == "incomplete"
    assert tuple(row.phase for row in bundles[-1].cleanup_failures) == ("rollback-parent-chain", "transaction-verification")
    assert tuple(row.failure_id for row in bundles[-1].cleanup_failures) == ("WI-LIFECYCLE-RELOCATION-ROLLBACK", "WI-CATEGORY-MIGRATION-INVENTORY")
    assert transactions[-1]._file is None and not transactions[-1]._locked
    assert (source / "nested/proof.bin").read_bytes() == b"original retained evidence"
    assert (destination / "foreign.bin").read_bytes() == b"foreign inverse source"


def test_bound_relocation_authority_without_ambient_and_with_conflicting_context(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    if module.os.name != "nt":
        pytest.skip("held-source authority is the selected Windows contract")
    other_root = tmp_path / "other-repository"
    other_root.mkdir()
    release = module.LifecycleWriteTarget._release_handle
    probes = []
    with module.LifecycleTransaction(root) as transaction, module.LifecycleTransaction(other_root) as other:
        def receiving(owner, handle, primary=None):
            try:
                movement = transaction._active_relocation
                if movement is not None and owner is movement.source_owner and handle == movement.handle and not probes:
                    assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
                    assert not movement._creation_observation_active
                    identity = owner._identity(handle)
                    with pytest.raises(module.LifecycleError, match="no close authority"):
                        movement.target_owner._close(handle)
                    with pytest.raises(module.LifecycleError, match="no creator disposition authority"):
                        owner._windows_delete(handle)
                    token = module._CURRENT_LIFECYCLE_TRANSACTION.set(other)
                    try:
                        for action in (lambda: owner._assert_creation_settlement(),
                                       lambda: owner._borrow_directory(destination),
                                       lambda: owner._close(handle),
                                       lambda: owner._windows_delete(handle),
                                       lambda: movement.target_owner._windows_rename(handle, destination.name, replace=False)):
                            with pytest.raises(module.LifecycleError, match="operation context differs"):
                                action()
                        assert not transaction._unsettled_relocations
                        assert not other._unsettled_relocations
                        primary = module.LifecycleError("TEST-CONTEXT-PRIMARY", "primary before refused release")
                        release(owner, handle, primary)
                        assert any("write-target-release" in note for note in primary.__notes__)
                        assert len(transaction._unsettled_relocations) == 1
                        unsettled = transaction._unsettled_relocations[0]
                        assert (unsettled.source, unsettled.destination, unsettled.identity) == (source, destination, identity)
                        assert not other._unsettled_relocations
                        assert owner._identity(handle) == identity
                    finally:
                        module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
                    assert owner._identity(handle) == identity
                    assert module._lifecycle_file_identity(destination.lstat()) == identity
                    probes.append(identity)
            finally:
                release(owner, handle, primary)
        monkeypatch.setattr(module.LifecycleWriteTarget, "_release_handle", receiving)
        transaction.replace_directory(source, destination, expected_identity=module._lifecycle_file_identity(source.lstat()))
        assert len(probes) == 1
        assert transaction.cleanup_intersects_unsettled((source, destination))


@pytest.mark.parametrize("receiving", ["composer", "typed-error", "primary-note"])
def test_moved_handle_close_failure_reaches_unsettled_before_receiving(tmp_path: Path, monkeypatch, receiving) -> None:
    module, root, source, destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    if module.os.name != "nt":
        pytest.skip("actual moved handle close is the selected Windows contract")
    close = module.LifecycleWriteTarget._close
    retained = []
    primary = module.LifecycleError("TEST-CLOSE-PRIMARY", "real candidate primary")
    composer = module.LifecycleOutcomeComposer() if receiving == "composer" else None
    token = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.set(composer)
    try:
        with module.LifecycleTransaction(root) as transaction:
            def failed_close(owner, handle):
                movement = transaction._active_relocation
                if movement is not None and owner is movement.source_owner and handle == movement.handle and not retained:
                    retained.append((owner, handle, owner._identity(handle)))
                    raise OSError("injected actual native close refusal")
                return close(owner, handle)
            verify = transaction._verify_observation_map
            rejected = []
            def failed_candidate(observations, **kwargs):
                verify(observations, **kwargs)
                if receiving == "primary-note" and destination in observations and not rejected:
                    rejected.append(True)
                    raise primary
            with monkeypatch.context() as change:
                change.setattr(module.LifecycleWriteTarget, "_close", failed_close)
                change.setattr(transaction, "_verify_observation_map", failed_candidate)
                try:
                    if receiving == "typed-error":
                        with pytest.raises(module.LifecycleError, match="handle release.*native close refusal"):
                            transaction.replace_directory(source, destination, expected_identity=module._lifecycle_file_identity(source.lstat()))
                    elif receiving == "primary-note":
                        with pytest.raises(module.LifecycleError) as caught:
                            transaction.replace_directory(source, destination, expected_identity=module._lifecycle_file_identity(source.lstat()))
                        assert caught.value is primary
                        assert any("write-target-release" in note for note in primary.__notes__)
                    else:
                        transaction.replace_directory(source, destination, expected_identity=module._lifecycle_file_identity(source.lstat()))
                        assert composer.finalize().cleanup_failures
                    assert transaction.cleanup_intersects_unsettled((source, destination))
                    assert retained and retained[0][0]._identity(retained[0][1]) == retained[0][2]
                finally:
                    for owner, handle, _identity in retained:
                        close(owner, handle)
    finally:
        module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.reset(token)


def test_held_relocation_native_boundary_preserves_foreign_forward_and_inverse(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    if module.os.name != "nt":
        pytest.skip("held no-clobber primitive is Windows")
    rename = module.LifecycleWriteTarget._windows_rename
    foreign = b"foreign held-branch endpoint"
    entered = []
    foreign_identities = []
    foreign_directory_identities = []
    original_directory_identity = module._lifecycle_file_identity(source.lstat())
    original_nested_identity = module._lifecycle_file_identity(leaf.parent.lstat())
    original_leaf_identity = module._lifecycle_file_identity(leaf.lstat())
    with module.LifecycleTransaction(root) as transaction:
        def occupied(owner, handle, leaf, *, replace):
            movement = transaction._active_relocation
            if movement is not None and handle == movement.handle:
                assert movement.source_owner is not None and movement.target_owner is not None
                assert replace is False
                destination.mkdir()
                (destination / "foreign.bin").write_bytes(foreign)
                foreign_identities.append(module._lifecycle_file_identity((destination / "foreign.bin").lstat()))
                foreign_directory_identities.append(module._lifecycle_file_identity(destination.lstat()))
                entered.append("forward")
                try:
                    return rename(owner, handle, leaf, replace=replace)
                except OSError:
                    assert movement.source_owner._identity(handle) == original_directory_identity
                    raise
            return rename(owner, handle, leaf, replace=replace)
        with monkeypatch.context() as change:
            change.setattr(module.LifecycleWriteTarget, "_windows_rename", occupied)
            with pytest.raises(OSError):
                transaction.replace_directory(source, destination, expected_identity=module._lifecycle_file_identity(source.lstat()))
        assert (destination / "foreign.bin").read_bytes() == foreign
        assert module._lifecycle_file_identity((destination / "foreign.bin").lstat()) == foreign_identities[0]
        assert module._lifecycle_file_identity(destination.lstat()) == foreign_directory_identities[0]
        assert module._lifecycle_file_identity(source.lstat()) == original_directory_identity
        assert module._lifecycle_file_identity(leaf.parent.lstat()) == original_nested_identity
        assert module._lifecycle_file_identity(leaf.lstat()) == original_leaf_identity
        assert leaf.read_bytes() == b"original retained evidence"
        (destination / "foreign.bin").unlink(); destination.rmdir()
        verify = transaction._verify_observation_map
        rejected = []
        def reject_current(observations, **kwargs):
            verify(observations, **kwargs)
            if destination in observations and not rejected:
                rejected.append(True)
                raise module.LifecycleError("TEST-HELD-PRIMARY", "held forward proof failure")
        def occupied_inverse(owner, handle, leaf, *, replace):
            movement = transaction._active_relocation
            if movement is not None and handle == movement.handle and owner is movement.source_owner:
                source.mkdir()
                (source / "foreign.bin").write_bytes(foreign)
                foreign_identities.append(module._lifecycle_file_identity((source / "foreign.bin").lstat()))
                foreign_directory_identities.append(module._lifecycle_file_identity(source.lstat()))
                entered.append("inverse")
                try:
                    return rename(owner, handle, leaf, replace=replace)
                except OSError:
                    assert movement.source_owner._identity(handle) == original_directory_identity
                    raise
            return rename(owner, handle, leaf, replace=replace)
        with monkeypatch.context() as change:
            change.setattr(transaction, "_verify_observation_map", reject_current)
            change.setattr(module.LifecycleWriteTarget, "_windows_rename", occupied_inverse)
            with pytest.raises(module.LifecycleError, match="held forward proof failure.*rollback failed"):
                transaction.replace_directory(source, destination, expected_identity=module._lifecycle_file_identity(source.lstat()))
        assert entered == ["forward", "inverse"]
        assert (source / "foreign.bin").read_bytes() == foreign
        assert module._lifecycle_file_identity((source / "foreign.bin").lstat()) == foreign_identities[1]
        assert module._lifecycle_file_identity(source.lstat()) == foreign_directory_identities[1]
        moved = destination / leaf.relative_to(source)
        assert module._lifecycle_file_identity(destination.lstat()) == original_directory_identity
        assert module._lifecycle_file_identity(moved.parent.lstat()) == original_nested_identity
        assert module._lifecycle_file_identity(moved.lstat()) == original_leaf_identity
        assert moved.read_bytes() == b"original retained evidence"
        assert transaction.cleanup_intersects_unsettled((source, destination))


def test_transaction_native_boundary_refuses_foreign_forward_and_inverse(tmp_path: Path, monkeypatch) -> None:
    module, root, source, destination, leaf, _outside = _relocation_observation_fixture(tmp_path)
    real = module.os.rename if module.os.name == "nt" else module.os.replace
    if module.os.name != "nt":
        pytest.skip("selected atomic no-clobber boundary is Windows")
    foreign = b"foreign syscall-boundary bytes"
    def occupied_forward(old, new):
        destination.mkdir()
        (destination / "foreign.bin").write_bytes(foreign)
        return real(old, new)
    with module.LifecycleTransaction(root) as transaction:
        with monkeypatch.context() as change:
            change.setattr(module.os, "rename", occupied_forward)
            with pytest.raises(FileExistsError):
                transaction.replace_directory(source, destination)
        assert (destination / "foreign.bin").read_bytes() == foreign
        assert leaf.read_bytes() == b"original retained evidence"
        (destination / "foreign.bin").unlink(); destination.rmdir()
        verify = transaction._verify_observation_map
        failed = []
        primary = module.LifecycleError("TEST-BOUNDARY", "actual forward proof failure")
        def fail_candidate(observations, **kwargs):
            verify(observations, **kwargs)
            if destination in observations and not failed:
                failed.append(True)
                raise primary
        def occupied_inverse(old, new):
            if Path(old) == destination:
                source.mkdir()
                (source / "foreign.bin").write_bytes(foreign)
            return real(old, new)
        with monkeypatch.context() as change:
            change.setattr(transaction, "_verify_observation_map", fail_candidate)
            change.setattr(module.os, "rename", occupied_inverse)
            with pytest.raises(module.LifecycleError, match="actual forward proof failure.*rollback failed"):
                transaction.replace_directory(source, destination)
        assert (source / "foreign.bin").read_bytes() == foreign
        assert (destination / "nested/proof.bin").read_bytes() == b"original retained evidence"
        assert transaction.cleanup_intersects_unsettled((source, destination))


@pytest.mark.parametrize("transactional", [False, True])
def test_native_creation_directory_observation_borrows_target_ancestor_and_member(tmp_path: Path, monkeypatch, transactional) -> None:
    module, root, _source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    from contextlib import nullcontext
    created = root / "created" / "nested"
    with module.LifecycleTransaction(root) if transactional else nullcontext() as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction) if transactional else None
        try:
            with module.LifecycleWriteTarget(created / "leaf.bin", failure_id="TEST-BORROW") as creator:
                records = tuple(creator._creations)
                handles = tuple(record.handle for record in records)
                with monkeypatch.context() as observation:
                    retained = module.LifecycleWriteTarget._retain_directory
                    released = module.LifecycleWriteTarget._release_handle
                    def retain(reader, path, handle, **kwargs):
                        if reader is not creator:
                            assert handle not in handles
                        return retained(reader, path, handle, **kwargs)
                    def release(reader, handle, *args):
                        if reader is not creator:
                            assert handle not in handles
                        return released(reader, handle, *args)
                    observation.setattr(module.LifecycleWriteTarget, "_retain_directory", retain)
                    observation.setattr(module.LifecycleWriteTarget, "_release_handle", release)
                    for path in (created, created.parent, root):
                        snapshot = module._capture_owned_directory_snapshot(path, failure_id="TEST-BORROW", creation_owner=creator)
                        module._verify_owned_directory_snapshot(snapshot, "TEST-BORROW", creation_owner=creator)
                        assert snapshot.parent_chain.participants[-1][0] == path
                        assert snapshot.parent_chain.participants[-1][1] == (path.stat().st_dev, path.stat().st_ino)
                    assert not creator._creation_observation_active
                    for record in records:
                        assert creator._identity(record.handle) == record.identity
                        assert not record.release_attempted and not record.finished
                    creator.verify()
            assert all(record.release_complete and record.finished for record in records)
        finally:
            if transactional:
                module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    module._capture_owned_directory_snapshot(created, failure_id="TEST-BORROW")


def test_native_creation_directory_observation_refuses_invalid_lifetime_and_epoch(tmp_path: Path, monkeypatch) -> None:
    module, root, _source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    created = root / "created"
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            with module.LifecycleWriteTarget(created / "leaf.bin", failure_id="TEST-BORROW") as creator:
                record = creator._creations[-1]
                for field, invalid in (("seal", object()), ("owner", object()), ("release_attempted", True)):
                    original = getattr(record, field)
                    setattr(record, field, invalid)
                    try:
                        with pytest.raises(module.LifecycleError):
                            module._capture_owned_directory_snapshot(created, failure_id="TEST-BORROW", creation_owner=creator)
                        assert not creator._creation_observation_active
                    finally:
                        setattr(record, field, original)
                thread = creator._creation_thread
                creator._creation_thread = object()
                try:
                    with pytest.raises(module.LifecycleError, match="thread differs"):
                        module._capture_owned_directory_snapshot(created, failure_id="TEST-BORROW", creation_owner=creator)
                finally:
                    creator._creation_thread = thread
                evidence = transaction._binding_evidence
                scandir = module.os.scandir
                def change_epoch(path):
                    if path == created:
                        transaction._binding_evidence = evidence + (("absent", created / "epoch-marker"),)
                    return scandir(path)
                with monkeypatch.context() as change:
                    change.setattr(module.os, "scandir", change_epoch)
                    try:
                        with pytest.raises(module.LifecycleError, match="current operation changed"):
                            module._capture_owned_directory_snapshot(created, failure_id="TEST-BORROW", creation_owner=creator)
                    finally:
                        transaction._binding_evidence = evidence
                creator.verify()
            with pytest.raises(module.LifecycleError):
                module._capture_owned_directory_snapshot(created, failure_id="TEST-BORROW", creation_owner=creator)
            assert not creator._creation_observation_active
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_native_creation_directory_observation_refuses_in_place_current_selection(tmp_path: Path, monkeypatch) -> None:
    module, root, _source, _destination, _leaf, outside = _relocation_observation_fixture(tmp_path)
    selected = module._capture_file_snapshot(outside, failure_id="TEST-BORROW")
    created = root / "created"
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            with module.LifecycleWriteTarget(created / "leaf.bin", failure_id="TEST-BORROW") as creator:
                record = creator._creations[-1]
                current = transaction._retained_observations
                original_creator = current[created]
                scandir = module.os.scandir
                def select_during_capture(path):
                    if path == created:
                        transaction.observe_retained_inputs((selected,))
                    return scandir(path)
                with monkeypatch.context() as change:
                    change.setattr(module.os, "scandir", select_during_capture)
                    with pytest.raises(module.LifecycleError, match="current operation changed"):
                        module._capture_owned_directory_snapshot(created, failure_id="TEST-BORROW", creation_owner=creator)
                assert transaction._retained_observations is current
                assert current[created] is original_creator and current[outside] is selected
                assert not creator._creation_observation_active and not record.release_attempted
                assert creator._identity(record.handle) == record.identity
                # Selection before a fresh capture belongs to its actual current epoch.
                module._capture_owned_directory_snapshot(created, failure_id="TEST-BORROW", creation_owner=creator)
                creator.verify()
            assert record.release_complete and record.finished
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_native_creation_directory_observation_partial_failure_preserves_creator_custody(tmp_path: Path, monkeypatch) -> None:
    module, root, _source, _destination, _leaf, _outside = _relocation_observation_fixture(tmp_path)
    created = root / "created"
    with module.LifecycleWriteTarget(created / "leaf.bin", failure_id="TEST-BORROW") as creator:
        record = creator._creations[-1]
        scandir = module.os.scandir
        primary = RuntimeError("injected borrowed inventory failure")
        def fail_inventory(path):
            if path == created:
                for settle in (lambda: creator.__exit__(None, None, None),
                               lambda: creator._finish_creation(record, None, abort=True),
                               lambda: creator._release_creation(record, None),
                               lambda: creator._close(record.handle)):
                    with pytest.raises(module.LifecycleError, match="active observation"):
                        settle()
                with pytest.raises(module.LifecycleError, match="active observation"):
                    module._capture_owned_directory_snapshot(created, failure_id="TEST-BORROW", creation_owner=creator)
                assert not record.release_attempted and creator._open
                raise primary
            return scandir(path)
        with monkeypatch.context() as change:
            change.setattr(module.os, "scandir", fail_inventory)
            with pytest.raises(RuntimeError) as caught:
                module._capture_owned_directory_snapshot(created, failure_id="TEST-BORROW", creation_owner=creator)
        assert caught.value is primary
        assert not creator._creation_observation_active
        assert creator._identity(record.handle) == record.identity
        creator.verify()
    assert record.release_complete and record.finished


def _adapt_test(function):
    def method(self):
        with tempfile.TemporaryDirectory() as directory:
            # Use the existing public pytest runner for parameter/fixture binding.
            # Selecting one function expands its declared cases without a copied
            # argument matrix or a unittest-only fixture implementation.
            result = pytest.main([
                f"{Path(__file__).resolve()}::{function.__name__}",
                "--basetemp", directory, "-p", "no:cacheprovider", "-q",
            ])
            self.assertEqual(result, 0, f"pytest adapter failed: {function.__name__}")

    method.__name__ = function.__name__
    return method


for _name, _function in tuple(globals().items()):
    if _name.startswith("test_") and callable(_function):
        setattr(_UnittestAdapter, _name, _adapt_test(_function))


@pytest.mark.parametrize("version", [1, 2, 3])
def test_parent_park_preserves_fixed_and_open_bug_bytes_and_replays(tmp_path, version):
    module = load_module()
    root = tmp_path / "park"
    parent = "retained-parent"
    instant = "2026-10-08T00:00:00Z"
    retention = None
    if version == 3:
        _item, _retained, _pointer, _before, _pointer_before, retention = seed_retained_scratch_manifest(module, root, parent, instant)
    else:
        seed_active(module, root, parent)
    fixed = seed_context_bug(root, parent, "retained-fixed")
    opened = seed_context_bug(root, parent, "retained-open")
    fixed.write_bytes(fixed.read_bytes().replace(b"status: open", b"status: fixed"))
    if version == 2:
        fixed.write_bytes(fixed.read_bytes() + b"\nTerminal-at: 2026-10-01T00:00:00Z\nResolution: Prior fix.\nEvidence: Prior accepted proof.\n")
    before = {path: path.read_bytes() for path in (fixed, opened)}
    identities = {path: (path.stat().st_dev, path.stat().st_ino) for path in before}
    instant = "2026-10-08T00:00:00Z"
    rows = []
    for path in before:
        row = {"id": path.stem, "action": "preserve-current", "inputSha256": hashlib.sha256(before[path]).hexdigest(), "status": module._parse_fields(before[path].decode())["status"], "reason": "Retained under a separate owner.", "evidence": "Parent parking changes no bug bytes."}
        if version == 2:
            row.update(contextBefore=parent, contextAfter=parent)
        rows.append(row)
    manifest = write_bug_dispositions(root, parent, instant, rows)
    data = json.loads(manifest.read_bytes());data["schemaVersion"] = version
    if version == 3:
        data["evidenceRetention"] = retention["evidenceRetention"]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    request = root / "park-closure.md"
    request.write_text(closure(instant).replace("Outcome: Lifecycle transition completed.", "Outcome: PARK; bugs retained unchanged."), encoding="utf-8")
    command = ("close", "--root", str(root), "--slug", parent, "--closure-file", str(request), "--terminal-instant", instant)
    result = run_cli(*command)
    assert result.returncode == 0, result.stdout
    archived = root / "work-items" / "archive" / "2026-10" / parent
    assert module.resolve_category(root, f"work-item:{parent}") == archived.resolve()
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_bytes())
    assert receipt["schemaVersion"] == version
    for row in receipt["bugs"]:
        assert row["target"] is None and row["statusBefore"] == row["statusAfter"]
        assert row["beforeSha256"] == row["afterSha256"]
    assert hashlib.sha256((root / "work-items" / "README.md").read_bytes()).hexdigest() == receipt["readmeSha256"]
    for path in before:
        assert path.read_bytes() == before[path]
        assert (path.stat().st_dev, path.stat().st_ino) == identities[path]
    snapshot = tree_file_bytes(root)
    replay = run_cli(*command)
    assert replay.returncode == 0, replay.stdout
    assert tree_file_bytes(root) == snapshot


@pytest.mark.parametrize("parent_kind", ["canonical", "legacy"])
def test_fixed_bug_admin_accepts_archived_parent_and_repairs_mutable_link(tmp_path, parent_kind):
    module = load_module()
    root = tmp_path / "admin"
    parent = "parked-owner"
    instant = "2026-10-08T00:00:00Z"
    if parent_kind == "canonical":
        seed_active(module, root, parent)
        write_empty_bug_dispositions(root, parent, instant)
        archive_parent = module.close_item(root, parent, closure(instant).encode(), instant)
    else:
        archive_parent = root / "work-items" / "archive" / "2026-10" / parent
        write(archive_parent / "status.md", "status: closed\n")
        write(archive_parent / "closure.md", closure(instant))
        module.refresh_readme(root, allow_marker_bootstrap=True)
    bug = seed_context_bug(root, parent, "later-fixed")
    bug.write_bytes(bug.read_bytes().replace(b"status: open", b"status: fixed"))
    consumer = seed_context_bug(root, "other-owner", "mutable-consumer")
    consumer.write_bytes(consumer.read_bytes() + b"\nRelated: bug:later-fixed\n[physical](later-fixed.md#proof)\n")
    parent_before = tree_file_bytes(archive_parent)
    parent_identity = (archive_parent.stat().st_dev, archive_parent.stat().st_ino)
    command = ("archive-fixed-bug", "--root", str(root), "--slug", bug.stem, "--terminal-instant", instant, "--resolution", "Accepted synthetic fix.", "--evidence", "Synthetic current proof.", "--apply")
    result = run_cli(*command)
    assert result.returncode == 0, result.stdout
    target = root / "work-items" / "bugs" / "archive" / "2026-10" / bug.name
    receipt = json.loads(target.with_name(f"{bug.stem}.fixed-archive-receipt.json").read_bytes())
    assert not bug.exists() and target.exists()
    assert b"archive/2026-10/later-fixed.md#proof" in consumer.read_bytes()
    assert b"bug:later-fixed" in consumer.read_bytes()
    assert len(receipt["links"]) == 1
    assert tree_file_bytes(archive_parent) == parent_before
    assert (archive_parent.stat().st_dev, archive_parent.stat().st_ino) == parent_identity
    snapshot = tree_file_bytes(root)
    replay = run_cli(*command)
    assert replay.returncode == 0, replay.stdout
    assert tree_file_bytes(root) == snapshot


@pytest.mark.parametrize("case", ["legacy-id", "wrong-id", "duplicate-id", "duplicate-status", "duplicate-context", "duplicate-metadata", "physical-copy", "unknown-status", "terminalize-evidenced"])
def test_terminal_preservation_intact_record_boundary(tmp_path, case):
    module = load_module()
    root = tmp_path / case
    parent = "intact-owner"
    seed_active(module, root, parent)
    bug = seed_context_bug(root, parent, "selected-bug")
    original = bug.read_bytes().replace(b"status: open", b"status: fixed")
    if case == "legacy-id":
        original = original.replace(b"- id: selected-bug\n", b"")
    elif case == "wrong-id":
        original = original.replace(b"- id: selected-bug", b"- id: other-bug")
    elif case == "duplicate-id":
        original += b"- id: other-bug\n"
    elif case == "duplicate-status":
        original += b"- status: fixed\n"
    elif case == "duplicate-context":
        original += b"- context: intact-owner\n"
    elif case == "duplicate-metadata":
        original += b"Evidence: first\nEvidence: second\n"
    elif case == "unknown-status":
        original = original.replace(b"status: fixed", b"status: unrecognized")
    elif case == "terminalize-evidenced":
        original += b"Terminal-at: 2026-10-01T00:00:00Z\nResolution: Original fix.\nEvidence: Original proof.\n"
    bug.write_bytes(original)
    if case == "physical-copy":
        target = root / "work-items" / "bugs" / "archive" / "2026-09" / bug.name
        target.parent.mkdir(parents=True)
        target.write_bytes(original)
    instant = "2026-10-08T00:00:00Z"
    row = {"id": bug.stem, "action": "preserve-current", "inputSha256": hashlib.sha256(original).hexdigest(), "status": module._parse_fields(original.decode())["status"], "reason": "Retain only an intact record.", "evidence": "Owner boundary oracle."}
    if case == "terminalize-evidenced":
        row.pop("reason");row.update(action="terminalize", resolution="No repeated mutation.")
    write_bug_dispositions(root, parent, instant, [row])
    before = tree_file_bytes(root)
    if case == "legacy-id":
        archived = module.close_item(root, parent, closure(instant).encode(), instant)
        assert archived.is_dir() and bug.read_bytes() == original
    else:
        with pytest.raises(module.LifecycleError):
            module.close_item(root, parent, closure(instant).encode(), instant)
        assert tree_file_bytes(root) == before


@pytest.mark.parametrize("parent_kind", ["missing", "duplicate", "invalid-archive", "backlog"])
def test_fixed_bug_admin_parent_location_refusals_keep_originals(tmp_path, parent_kind):
    module = load_module()
    root = tmp_path / parent_kind
    parent = "bounded-parent"
    if parent_kind != "missing":
        archived = root / "work-items" / "archive" / "2026-10" / parent
        if parent_kind != "backlog":
            write(archived / "status.md", "status: closed\n")
            if parent_kind != "invalid-archive":
                write(archived / "closure.md", closure("2026-10-08T00:00:00Z"))
        else:
            write(root / "work-items" / "backlog" / f"{parent}.md", "status: candidate\nTask: Candidate only.\n")
        if parent_kind == "duplicate":
            write(root / "work-items" / "active" / parent / "status.md", quick_status())
    bug = seed_context_bug(root, parent, "bounded-fixed")
    bug.write_bytes(bug.read_bytes().replace(b"status: open", b"status: fixed"))
    module.resolve_category(root, f"bug:{bug.stem}")  # initialize the existing public owner before byte census
    before = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError):
        module.archive_fixed_bug(root, bug.stem, "2026-10-08T00:00:00Z", "Accepted fix.", "Accepted evidence.")
    assert tree_file_bytes(root) == before


def test_terminal_preservation_receipt_unknown_before_status_refuses_replay(tmp_path):
    module = load_module()
    root = tmp_path / "receipt"
    parent = "receipt-owner"
    seed_active(module, root, parent)
    bug = seed_context_bug(root, parent, "receipt-fixed")
    bug.write_bytes(bug.read_bytes().replace(b"status: open", b"status: fixed"))
    before = bug.read_bytes()
    instant = "2026-10-08T00:00:00Z"
    write_bug_dispositions(root, parent, instant, [{"id": bug.stem, "action": "preserve-current", "inputSha256": hashlib.sha256(before).hexdigest(), "status": "fixed", "reason": "Retain.", "evidence": "Accepted unchanged image."}])
    archived = module.close_item(root, parent, closure(instant).encode(), instant)
    receipt = archived / "bug-dispositions-receipt.json"
    payload = json.loads(receipt.read_bytes());payload["bugs"][0]["statusBefore"] = "unrecognized"
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    snapshot = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as refused:
        module.close_item(root, parent, closure(instant).encode(), instant)
    assert refused.value.failure_id == "WI-IMMUTABLE-ARCHIVE"
    assert tree_file_bytes(root) == snapshot and bug.read_bytes() == before


def test_successor_archive_preserves_terminal_bug_with_shared_owner(tmp_path):
    module = load_module()
    root = tmp_path / "successor"
    parent = "shared-preserve-owner"
    seed_active(module, root, parent)
    item = root / "work-items" / "active" / parent
    recorded = run_ledger(item, "append", "--run-id", "successor-synthetic-terminal", "--role", "qa-engineer", "--execution-role", "internal", "--status", "completed", "--gate", "none", "--scope", "synthetic successor input", "--started-at", "2026-10-08T00:00:00Z", "--updated-at", "2026-10-08T00:00:00Z")
    assert recorded.returncode == 0, recorded.stdout
    bug = seed_context_bug(root, parent, "successor-preserved-fixed")
    bug.write_bytes(bug.read_bytes().replace(b"status: open", b"status: fixed"))
    before = bug.read_bytes()
    instant = "2026-10-08T00:05:00Z"
    write_bug_dispositions(root, parent, instant, [{"id": bug.stem, "action": "preserve-current", "inputSha256": hashlib.sha256(before).hexdigest(), "status": "fixed", "reason": "Keep independent bug ownership.", "evidence": "Successor changes no bug bytes."}])
    module.refresh_readme(root)
    ledger_sha = hashlib.sha256((item / "agent-runs.jsonl").read_bytes()).hexdigest()
    readme_sha = hashlib.sha256((root / "work-items" / "README.md").read_bytes()).hexdigest()
    successor = b"Task: Resume independent work.\nContinues: shared-preserve-owner\nObligation-transfer: preserve-successor-operation\nNext action: Review the retained scope.\nupdated: 2026-10-08T00:05:00Z\n"
    transfer = json.dumps({"schemaVersion": 1, "sourceWorkItem": parent, "successorWorkItem": "ready-successor", "expectedSourceLedgerSha256": ledger_sha, "obligations": []}).encode()
    args = (root, parent, closure(instant).encode(), instant, "ready-successor", successor, "preserve-successor-operation", ledger_sha, readme_sha)
    receipt = module.archive_with_successor(*args, obligation_transfer_data=transfer)
    archived = root / receipt["archivePath"]
    bug_receipt = json.loads((archived / "bug-dispositions-receipt.json").read_bytes())
    assert bug_receipt["bugs"][0]["statusBefore"] == "fixed"
    assert bug_receipt["bugs"][0]["target"] is None and bug.read_bytes() == before
    snapshot = tree_file_bytes(root)
    assert module.archive_with_successor(*args, obligation_transfer_data=transfer) == receipt
    assert tree_file_bytes(root) == snapshot


def test_legacy_parent_archive_repairs_descendant_uris_and_compensates_conflict(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    root = tmp_path / "legacy-parent-links"
    parent = "legacy-parent"
    item = root / "work-items" / "active" / parent
    instant = "2026-10-08T15:00:00Z"
    write(item / "status.md", quick_status())
    write(item / "closure.md", closure(instant))
    write(item / "evidence.md", "Accepted legacy evidence.\n")
    evidence_before = (item / "evidence.md").read_bytes()
    consumer = seed_context_bug(root, "standalone", "legacy-consumer")
    before = consumer.read_bytes() + b"[evidence](../active/legacy-parent/evidence.md#case)\n[status](../active/legacy-parent/status.md)\n"
    consumer.write_bytes(before)
    inventory = root / "incoming.json"
    write(inventory, json.dumps({"reference": f"work-item:{parent}"}))
    module.refresh_readme(root, allow_marker_bootstrap=True)
    with pytest.raises(module.LifecycleError) as missing:
        module.migrate_legacy(root, f"work-item:{parent}", incoming_links_inventory=None)
    assert missing.value.failure_id == "WI-LEGACY-LINK-UNMAPPED"
    original_refresh = module.refresh_readme
    def fail_refresh(target):
        consumer.write_bytes(b"Concurrent author bytes.\n")
        raise module.LifecycleError("WI-README-STALE", "synthetic readback failure")
    monkeypatch.setattr(module, "refresh_readme", fail_refresh)
    with pytest.raises(module.LifecycleError) as conflict:
        module.migrate_legacy(root, f"work-item:{parent}", incoming_links_inventory=inventory)
    assert conflict.value.failure_id == "WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE"
    assert consumer.read_bytes() == b"Concurrent author bytes.\n" and item.is_dir()
    monkeypatch.setattr(module, "refresh_readme", original_refresh)
    consumer.write_bytes(before)
    archived = module.migrate_legacy(root, f"work-item:{parent}", incoming_links_inventory=inventory)
    assert consumer.read_bytes() == before.replace(b"../active/legacy-parent/", b"../archive/2026-10/legacy-parent/")
    assert (archived / "evidence.md").read_bytes() == evidence_before
    assert not (archived / "bug-dispositions-receipt.json").exists()
    assert module.migrate_legacy(root, f"work-item:{parent}", incoming_links_inventory=inventory) == archived


def _parent_successor_link_fixture(tmp_path: Path, *, opaque=False):
    spec = importlib.util.spec_from_file_location("parent_transition_fixtures", SCRIPT.parent.parent / "tests" / "test_legacy_obligation_migration.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    fixture = helpers.native_transfer_fixture(tmp_path)
    module, item = fixture["lifecycle"], fixture["item"]
    write(item / "evidence.md", "Original referenced evidence.\n")
    bug = seed_context_bug(tmp_path, "standalone", "parent-uri-consumer")
    before = bug.read_bytes() + f"[evidence](../active/{item.name}/evidence.md#case)\n[status](../active/{item.name}/status.md)\n[closure](../active/{item.name}/closure.md)\n".encode()
    bug.write_bytes(before)
    if opaque:
        bug.unlink()
        write(tmp_path / "work-items/active/side/status.md", quick_status())
        bug = tmp_path / "work-items/active/side/design.md"
        before = b"\xef\xbb\xbf\xc3\xa9\x97\r\n" + before.replace(b"../active/", b"../../active/") + b"\x81"
        bug.write_bytes(before)
    module.refresh_readme(tmp_path)
    fixture["readmeSha"] = hashlib.sha256((tmp_path / "work-items" / "README.md").read_bytes()).hexdigest()
    fixture.update(consumer=bug, consumerBefore=before, evidenceBefore=(item / "evidence.md").read_bytes())

    return fixture, helpers


def test_parent_successor_preserves_markerless_active_consumer_owner(
    tmp_path: Path,
) -> None:
    fixture, helpers = _parent_successor_link_fixture(tmp_path, opaque=True)
    module = fixture["lifecycle"]
    owner_status = tmp_path / "work-items/active/side/status.md"
    owner_status.write_bytes(b"status: blocked\n")
    module.refresh_readme(tmp_path)
    fixture["readmeSha"] = hashlib.sha256(
        (tmp_path / "work-items" / "README.md").read_bytes()
    ).hexdigest()

    helpers.run_transfer(fixture)

    expected = fixture["consumerBefore"].replace(
        f"../../active/{fixture['slug']}/".encode(),
        f"../../archive/2026-08/{fixture['slug']}/".encode(),
    )
    assert fixture["consumer"].read_bytes() == expected
    assert owner_status.read_bytes() == b"status: blocked\n"
    assert (tmp_path / "work-items/archive/2026-08" / fixture["slug"]).is_dir()


@pytest.mark.parametrize("opaque", (False, True))
def test_parent_successor_uri_restart_binds_original_targets_and_preserves_duty(tmp_path: Path, opaque: bool) -> None:
    fixture, helpers = _parent_successor_link_fixture(tmp_path, opaque=opaque)
    module = fixture["lifecycle"]
    with pytest.raises(module.LifecycleError):
        helpers.run_transfer(fixture, inject="T3")
    intent = module._transition_intent_path(tmp_path, fixture["operationId"])
    payload = json.loads(intent.read_bytes())
    evidence = next(row for row in payload["uriTargetBindings"]["rows"] if row["source"].endswith("/evidence.md"))
    assert evidence["beforeSha256"] == evidence["afterSha256"]
    closure_target = next(row for row in payload["uriTargetBindings"]["rows"] if row["source"].endswith("/closure.md"))
    assert closure_target["beforeSha256"] is None
    assert len(payload["uriConsumers"]["rows"]) == 1
    receipt = module._recover_transition(tmp_path, intent)
    archive = tmp_path / receipt["archivePath"]
    assert (archive / "agent-runs.jsonl").read_bytes() == fixture["ledgerBefore"]
    assert len(receipt["obligations"]) == 1 and not intent.exists()
    assert (archive / "evidence.md").read_bytes() == fixture["evidenceBefore"]
    expected = fixture["consumerBefore"].replace(f"../active/{fixture['slug']}/".encode(), f"../archive/2026-08/{fixture['slug']}/".encode())
    assert fixture["consumer"].read_bytes() == expected
    fixture["consumer"].write_bytes(expected + b"Later authoring.\n")
    assert helpers.run_transfer(fixture) == receipt
    assert fixture["consumer"].read_bytes().endswith(b"Later authoring.\n")


@pytest.mark.parametrize("phase", ["T1", "T3"])
def test_parent_successor_uri_target_drift_stops_before_recovery_effects(tmp_path: Path, phase: str) -> None:
    fixture, helpers = _parent_successor_link_fixture(tmp_path)
    module = fixture["lifecycle"]
    with pytest.raises(module.LifecycleError):
        helpers.run_transfer(fixture, inject=phase)
    intent = module._transition_intent_path(tmp_path, fixture["operationId"])
    payload = json.loads(intent.read_bytes())
    path = fixture["item"] if phase == "T1" else tmp_path / payload["archivePath"]
    (path / "evidence.md").write_bytes(b"Concurrent target evidence.\n")
    before = tree_file_bytes(tmp_path)
    with pytest.raises(module.LifecycleError) as refused:
        module._recover_transition(tmp_path, intent)
    assert refused.value.failure_id == ("WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE" if phase == "T1" else "WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE")
    assert tree_file_bytes(tmp_path) == before and intent.exists()


@pytest.mark.parametrize("missing", ["uriConsumers", "uriTargetBindings", "linkMaintenance", "target-row", "null-status"])
def test_parent_successor_uri_omission_cannot_downgrade_historical_profile(tmp_path: Path, missing: str) -> None:
    fixture, helpers = _parent_successor_link_fixture(tmp_path)
    module = fixture["lifecycle"]
    with pytest.raises(module.LifecycleError):
        helpers.run_transfer(fixture, inject="T0")
    intent = module._transition_intent_path(tmp_path, fixture["operationId"])
    payload = json.loads(intent.read_bytes())
    if missing == "null-status":
        payload["statusBefore"] = None
        next(row for row in payload["uriTargetBindings"]["rows"] if row["source"].endswith("/status.md"))["beforeSha256"] = None
    elif missing == "linkMaintenance":
        receipt = json.loads(module._unb64(payload["bugReceiptAfter"]))
        receipt.pop(missing)
        payload["bugReceiptAfter"] = module._b64(json.dumps(receipt).encode())
    elif missing == "target-row":
        payload["uriTargetBindings"]["rows"].pop()
    else:
        payload.pop(missing)
    intent.write_bytes(module._migration_receipt_bytes(payload))
    before = tree_file_bytes(tmp_path)
    with pytest.raises(module.LifecycleError):
        module._recover_transition(tmp_path, intent)
    assert tree_file_bytes(tmp_path) == before


def test_parent_successor_uri_intent_overflow_is_pre_effect(tmp_path: Path) -> None:
    fixture, helpers = _parent_successor_link_fixture(tmp_path)
    module = fixture["lifecycle"]
    consumer = fixture["consumer"]
    consumer.write_bytes(consumer.read_bytes() + b"Private synthetic body. " * 7000)
    module.refresh_readme(tmp_path)
    fixture["readmeSha"] = hashlib.sha256((tmp_path / "work-items" / "README.md").read_bytes()).hexdigest()
    before = tree_file_bytes(tmp_path)
    with pytest.raises(module.LifecycleError) as refused:
        helpers.run_transfer(fixture)
    assert refused.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    assert tree_file_bytes(tmp_path) == before
    assert not module._transition_intent_path(tmp_path, fixture["operationId"]).exists()


@pytest.mark.parametrize("phase", ["T1", "T4", "T6"])
def test_parent_successor_uri_owned_images_recover_at_distinct_boundaries(tmp_path: Path, phase: str) -> None:
    fixture, helpers = _parent_successor_link_fixture(tmp_path)
    module = fixture["lifecycle"]
    with pytest.raises(module.LifecycleError):
        helpers.run_transfer(fixture, inject=phase)
    intent = module._transition_intent_path(tmp_path, fixture["operationId"])
    outcome = module._recover_transition(tmp_path, intent)
    if phase == "T1":
        assert outcome is None and fixture["item"].is_dir()
        assert fixture["consumer"].read_bytes() == fixture["consumerBefore"]
        assert not (fixture["item"] / "closure.md").exists()
    else:
        assert outcome["status"] == "settled" and len(outcome["obligations"]) == 1
        assert b"../active/" not in fixture["consumer"].read_bytes()
    assert not intent.exists()


def test_parent_successor_recreated_uri_directory_refuses_restart(tmp_path: Path) -> None:
    fixture, helpers = _parent_successor_link_fixture(tmp_path)
    module, item = fixture["lifecycle"], fixture["item"]
    directory = item / "assets"
    directory.mkdir()
    fixture["consumer"].write_bytes(fixture["consumer"].read_bytes() + f"[assets](../active/{item.name}/assets)\n".encode())
    module.refresh_readme(tmp_path)
    fixture["readmeSha"] = hashlib.sha256((tmp_path / "work-items" / "README.md").read_bytes()).hexdigest()
    with pytest.raises(module.LifecycleError):
        helpers.run_transfer(fixture, inject="T3")
    intent = module._transition_intent_path(tmp_path, fixture["operationId"])
    payload = json.loads(intent.read_bytes())
    row = next(row for row in payload["uriTargetBindings"]["rows"] if row["kind"] == "directory")
    target = tmp_path / row["target"]
    target.rename(target.with_name("retained-original-assets"))
    target.mkdir()
    before = tree_file_bytes(tmp_path)
    with pytest.raises(module.LifecycleError) as refused:
        module._recover_transition(tmp_path, intent)
    assert refused.value.failure_id == "WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE"
    assert tree_file_bytes(tmp_path) == before and intent.exists()
    # A captured zero native identity is representable; parser does not replace it with unknown.
    row["identity"] = ["0", "0"]
    module._transition_parent_uri_images(tmp_path, payload)


@pytest.mark.parametrize("case", ["target-drift", "matching", "mismatched-caller", "mismatched-pending-caller", "no-intent-authoring"])
def test_parent_successor_public_replay_enforces_pending_t6_before_committed(tmp_path: Path, case: str) -> None:
    fixture, helpers = _parent_successor_link_fixture(tmp_path)
    module = fixture["lifecycle"]
    with pytest.raises(module.LifecycleError):
        helpers.run_transfer(fixture, inject="T3" if case == "mismatched-pending-caller" else "T6")
    intent = module._transition_intent_path(tmp_path, fixture["operationId"])
    archive = tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"]
    assert intent.exists()
    assert (archive / "lifecycle-transition-receipt.json").exists() == (case != "mismatched-pending-caller")
    if case == "no-intent-authoring":
        module._recover_transition(tmp_path, intent)
        assert not intent.exists()
    if case in {"target-drift", "no-intent-authoring"}:
        (archive / "evidence.md").write_bytes(b"Later referenced evidence authoring.\n")
    successor = fixture["successor"] + b"Mismatched request.\n" if case in {"mismatched-caller", "mismatched-pending-caller"} else fixture["successor"]
    for name, data in (("closure-input.md", fixture["closure"]), ("successor-input.md", successor), ("transfer-input.json", fixture["transfer"])):
        (tmp_path / name).write_bytes(data)
    before = tree_file_bytes(tmp_path)
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), "archive-with-successor", "--root", str(tmp_path),
        "--slug", fixture["slug"], "--closure-file", str(tmp_path / "closure-input.md"),
        "--terminal-instant", fixture["instant"], "--successor-slug", fixture["successorSlug"],
        "--successor-file", str(tmp_path / "successor-input.md"), "--operation-id", fixture["operationId"],
        "--expected-ledger-sha256", fixture["ledgerSha"], "--expected-readme-sha256", fixture["readmeSha"],
        "--obligation-transfer-file", str(tmp_path / "transfer-input.json")], capture_output=True, text=True, timeout=30)
    if case in {"target-drift", "mismatched-caller", "mismatched-pending-caller"}:
        assert result.returncode != 0 and "COMMITTED" not in result.stdout
        expected = "ROLLFORWARD-INDETERMINATE" if case == "target-drift" else "SETTLEMENT-MISMATCH"
        assert expected in result.stdout + result.stderr
        assert intent.exists() and tree_file_bytes(tmp_path) == before
    else:
        assert result.returncode == 0 and "WI-LIFECYCLE-TRANSITION-COMMITTED" in result.stdout
        assert not intent.exists()
        if case == "no-intent-authoring":
            assert tree_file_bytes(tmp_path) == before


def test_atomic_write_target_native_parent_effect_and_release(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    parent, outside = tmp_path / "ordinary", tmp_path / "outside"
    parent.mkdir(); outside.mkdir()
    path = parent / "target.bin"
    path.write_bytes(b"before")
    (outside / "sentinel").write_bytes(b"outside unchanged")
    original = module.LifecycleWriteTarget._file
    def inner_swap(target, leaf, *, create=False, delete=False):
        if create:
            try:
                parent.rename(tmp_path / "retained")
            except OSError:
                if os.name != "nt":
                    raise
                raise OSError("native pinned parent denied injected rename")
            parent.symlink_to(outside, target_is_directory=True)
        return original(target, leaf, create=create, delete=delete)
    monkeypatch.setattr(module.LifecycleWriteTarget, "_file", inner_swap)
    with pytest.raises(module.LifecycleError) as refused:
        module._atomic_write(path, b"after")
    assert refused.value.failure_id == "WI-LIFECYCLE-WRITE-BOUNDARY"
    assert sorted(p.name for p in outside.iterdir()) == ["sentinel"]
    assert (outside / "sentinel").read_bytes() == b"outside unchanged"
    retained = parent if os.name == "nt" else tmp_path / "retained"
    assert (retained / "target.bin").read_bytes() == b"before"
    assert sorted(p.name for p in retained.iterdir()) == ["target.bin"]
    monkeypatch.setattr(module.LifecycleWriteTarget, "_file", original)
    if os.name == "nt":
        parent.rename(tmp_path / "released")  # Actual handle release permits the ordinary move.


def test_atomic_write_target_kind_admission_keeps_large_replacement(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "large.bin"
    path.write_bytes(b"x" * (4 * 1024 * 1024 + 1))
    module._atomic_write(path, b"replacement")
    assert path.read_bytes() == b"replacement"


@pytest.mark.skipif(os.name != "nt", reason="Windows native handle receiving")
def test_atomic_write_native_partial_acquisition_releases_handles_and_temp(tmp_path: Path, monkeypatch) -> None:
    import ctypes
    module = load_module()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.GetProcessHandleCount.restype = ctypes.c_int
    def count():
        value = ctypes.c_ulong()
        assert kernel.GetProcessHandleCount(ctypes.c_void_p(-1), ctypes.byref(value))
        return value.value
    # Warm the loader and both actual native resource paths before baseline measurement.
    module._atomic_write(tmp_path / "warm.bin", b"warm")
    original_identity = module.LifecycleWriteTarget._identity
    before = count()
    monkeypatch.setattr(module.LifecycleWriteTarget, "_identity", lambda self, h: (_ for _ in ()).throw(OSError("identity probe")))
    with pytest.raises(module.LifecycleError):
        module._atomic_write(tmp_path / "failed.bin", b"no publication")
    assert count() == before and not (tmp_path / "failed.bin").exists()
    monkeypatch.setattr(module.LifecycleWriteTarget, "_identity", original_identity)
    original_check = module.LifecycleWriteTarget._windows_check
    def child_failure(target, handle, *, directory):
        if not directory:
            raise OSError("child attributes probe")
        return original_check(target, handle, directory=directory)
    monkeypatch.setattr(module.LifecycleWriteTarget, "_windows_check", child_failure)
    with pytest.raises(module.LifecycleError):
        module._atomic_write(tmp_path / "child-failed.bin", b"no publication")
    assert count() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["warm.bin"]


@pytest.mark.skipif(os.name != "nt", reason="Windows native read-only replacement signal")
def test_atomic_write_native_readonly_refusal_keeps_original_and_cleans_temp(tmp_path: Path) -> None:
    import stat
    module = load_module()
    path = tmp_path / "readonly.bin"
    path.write_bytes(b"original readonly bytes")
    path.chmod(stat.S_IREAD)
    try:
        with pytest.raises(module.LifecycleError) as refused:
            module._atomic_write(path, b"replacement")
        assert refused.value.failure_id == "WI-LIFECYCLE-WRITE-BOUNDARY"
        assert "rename" in str(refused.value)
        assert path.read_bytes() == b"original readonly bytes"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["readonly.bin"]
    finally:
        path.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_write_cleanup_composer_repeated_causes_bounded_projection_and_strict_old_slots() -> None:
    module = load_module()
    composer = module.LifecycleOutcomeComposer()
    first, second = OSError(5, "first-close-cause"), OSError(6, "second-close-cause")
    for index, cause in enumerate((first, second)):
        composer.record_write_cleanup(phase="write-target-release", failure_id="WI-LIFECYCLE-WRITE-BOUNDARY",
            resource=f"directory-{index}", diagnostic="close failed", cause=cause)
    bundle = composer.finalize()
    assert bundle == composer.finalize()
    assert len(bundle.cleanup_failures) == 1
    assert "occurrences=2" in bundle.cleanup_failures[0].diagnostic
    assert all(cause.strerror in bundle.cleanup_failures[0].diagnostic for cause in (first, second))
    assert composer._cleanup_occurrences["write-target-release"][0][1] is first
    assert module.LifecycleOutcomeComposer.top_level(bundle) is not None
    primary = module.LifecycleError("primary", "original primary")
    composer.capture_primary(primary)
    assert composer.top_level(composer.finalize()) is primary
    composer.record_cleanup(phase="transaction-release", failure_id="cleanup", resource=None, diagnostic="old slot")
    with pytest.raises(ValueError):
        composer.record_cleanup(phase="transaction-release", failure_id="cleanup", resource=None, diagnostic="duplicate")
    with pytest.raises(ValueError):
        composer.record_write_cleanup(phase="transaction-release", failure_id="cleanup", resource=None, diagnostic="wrong owner")
    for index in range(10):
        composer.record_write_cleanup(phase="write-temp-cleanup", failure_id="WI-LIFECYCLE-WRITE-BOUNDARY",
            resource=f"write-{index}", diagnostic="x" * 500, cause=OSError(f"cause-{index}"))
    output = next(row for row in composer.finalize().cleanup_failures if row.phase == "write-temp-cleanup")
    assert len(output.diagnostic) <= 512 and "occurrences=10" in output.diagnostic and "omitted-details=" in output.diagnostic
    assert len(composer._cleanup_occurrences["write-temp-cleanup"]) == 10


@pytest.mark.skipif(os.name != "nt", reason="native Windows write cleanup receiving")
def test_public_write_failure_preserves_primary_and_all_cleanup_attempts(tmp_path: Path, monkeypatch) -> None:
    import ctypes
    module = load_module()
    (tmp_path / "work-items").mkdir()
    module._atomic_write(tmp_path / "warm", b"warm")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.GetProcessHandleCount.restype = ctypes.c_int
    def handles():
        count = ctypes.c_ulong(); assert kernel.GetProcessHandleCount(ctypes.c_void_p(-1), ctypes.byref(count)); return count.value
    before = handles()
    original_close = module.LifecycleWriteTarget._close
    close_attempts = []
    def close_with_two_causes(target, handle):
        original_close(target, handle)  # Real native creator handle is settled before injecting its diagnostic fault.
        close_attempts.append(handle)
        if len(close_attempts) <= 2:
            raise OSError(5 + len(close_attempts), f"native-close-cause-{len(close_attempts)}")
    monkeypatch.setattr(module.LifecycleWriteTarget, "_write_handle", lambda self,h,data: (_ for _ in ()).throw(OSError("primary-write-cause")))
    monkeypatch.setattr(module.LifecycleWriteTarget, "_windows_delete", lambda self,h: (_ for _ in ()).throw(OSError("temp-cleanup-cause")))
    monkeypatch.setattr(module.LifecycleWriteTarget, "_close", close_with_two_causes)
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError) as refused:
        module.refresh_readme(tmp_path, allow_marker_bootstrap=True, diagnostic_observer=observer)
    assert "primary-write-cause" in str(refused.value)
    assert observer.state == "delivered" and observer.snapshot.primaryFailureId == refused.value.failure_id
    diagnostics = " ".join(row.diagnostic for row in observer.snapshot.cleanupFailures)
    assert "temp-cleanup-cause" in diagnostics and "native-close-cause-1" in diagnostics and "native-close-cause-2" in diagnostics
    assert handles() == before and len(close_attempts) > 2
    assert not (tmp_path / "work-items" / "README.md").exists()
    assert len(list((tmp_path / "work-items").glob(".*.tmp"))) == 1


@pytest.mark.skipif(os.name != "nt", reason="native cleanup-only repeated-write receiving")
def test_public_repeated_writes_keep_cleanup_only_failure_nonzero(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    original_close = module.LifecycleWriteTarget._close
    original_write = module.LifecycleWriteTarget._write_handle
    written = set()
    raised = set()
    def write_and_track(target, handle, data):
        original_write(target, handle, data)
        written.add(target.leaf)
    def close_and_report(target, handle):
        original_close(target, handle)
        if target.leaf in written and target.leaf not in raised:
            raised.add(target.leaf)
            raise OSError(f"cleanup-only-after-{target.leaf}")
    monkeypatch.setattr(module.LifecycleWriteTarget, "_write_handle", write_and_track)
    monkeypatch.setattr(module.LifecycleWriteTarget, "_close", close_and_report)
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError) as refused:
        module.create_candidate(tmp_path, "repeated-write", b"Task: Synthetic repeated writes.\nNext action: Inspect.\n", diagnostic_observer=observer)
    assert refused.value.failure_id == "WI-LIFECYCLE-WRITE-BOUNDARY"
    assert observer.snapshot.primaryKind == "none"
    cleanup = next(row for row in observer.snapshot.cleanupFailures if row.phase == "write-target-release")
    assert len(raised) >= 2 and f"occurrences={len(raised)}" in cleanup.diagnostic
    assert all(f"cleanup-only-after-{leaf}" in cleanup.diagnostic for leaf in raised)
    assert (tmp_path / "work-items" / "backlog" / "repeated-write.md").is_file()
    assert (tmp_path / "work-items" / "README.md").is_file()


def test_projection_apply_revoke_preserves_bound_repository_role(tmp_path: Path) -> None:
    fixture_path = ROOT / "tests" / "test_legacy_ledger_projection_writer.py"
    spec = importlib.util.spec_from_file_location("root_role_projection_fixture", fixture_path)
    support = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(support)
    case = support.LegacyLedgerProjectionWriterTests()
    module = load_module()
    root = tmp_path / "work-items"
    item, ledger_before, manifest = case._fixture(root)
    caller = root / "work-items"
    assert case._apply(module, root, manifest, dry_run=True)["dryRun"] is True
    applied = case._apply(module, caller, manifest)
    registry = caller / "legacy-ledger-projections.jsonl"
    with pytest.raises(module.LifecycleError) as mismatch:
        module.revoke_legacy_ledger_projection(caller, "projection-apply-001", "0" * 64, support.sha(registry.read_bytes()), "projection-revoke-bad", "2026-08-01T00:00:03Z")
    assert mismatch.value.failure_id == "WI-LEDGER-MIGRATION-TARGET-DIGEST"
    revoked = module.revoke_legacy_ledger_projection(caller, "projection-apply-001", applied["recordSha256"], support.sha(registry.read_bytes()), "projection-revoke-001", "2026-08-01T00:00:03Z")
    assert not revoked["replay"]
    replay = module.revoke_legacy_ledger_projection(caller, "projection-apply-001", applied["recordSha256"], support.sha(registry.read_bytes()), "projection-revoke-001", "2026-08-01T00:00:03Z")
    assert replay["replay"] and (item / "agent-runs.jsonl").read_bytes() == ledger_before
    assert not (tmp_path / ".scratch").exists()
    assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None


def test_partial_recovery_relative_inputs_preserve_bound_repository_role(tmp_path: Path) -> None:
    module = load_module()
    case = PartialMigrationRecoveryBehaviorTests()
    root = tmp_path / "work-items"
    caller = root / "work-items"
    @module._lifecycle_participant
    def build(bound_root):
        return case._fixture(module, bound_root)
    build = module._lifecycle_participant(build.__wrapped__, input_role="repository-root")
    fixture = build(root)
    fixture["inventory"] = fixture["inventory"].relative_to(root)
    fixture["receipt"] = fixture["receipt"].relative_to(root)
    result = case._run(module, caller, fixture)
    assert result.audit == "PASS" and not result.replay
    receipt = root / fixture["receipt"]
    before = receipt.read_bytes()
    assert case._run(module, caller, fixture).replay
    assert receipt.read_bytes() == before
    assert (caller / "README.md").read_bytes() == module.render_readme_bytes(caller)
    assert not (tmp_path / ".scratch").exists()
    assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None


def _selected_owner_fixture(root: Path, selected: str = "selected-target"):
    module = load_module()
    work_items = root / "work-items"
    def prepare(_root):
        seed_active(module, work_items, selected)
    module._lifecycle_participant(prepare, input_role="repository-root")(root)
    return module, work_items


@pytest.mark.parametrize("root_form", ("R", "W"))
def test_selected_close_ignores_different_neighbor_identity(tmp_path: Path, root_form: str) -> None:
    parent = tmp_path / "project"
    root = parent / "work-items"
    module, work_items = _selected_owner_fixture(root)
    seed_active(module, parent, "different-neighbor")
    neighbor = root / "active" / "different-neighbor"
    before = {path.relative_to(neighbor): (path.stat().st_dev, path.stat().st_ino, path.read_bytes())
              for path in neighbor.rglob("*") if path.is_file()}
    write_bug_dispositions(root, "selected-target", "2026-08-11T10:00:00Z", [])
    supplied = tmp_path / "closure.md"
    supplied.write_text(closure("2026-08-11T10:00:00Z"), encoding="utf-8")
    result = run_cli("close", "--root", str(root if root_form == "R" else work_items),
        "--slug", "selected-target", "--closure-file", str(supplied), "--terminal-instant", "2026-08-11T10:00:00Z")
    assert result.returncode == 0, result.stdout
    assert (work_items / "archive/2026-08/selected-target/bug-dispositions-receipt.json").is_file()
    assert not (work_items / "active/selected-target").exists()
    assert before == {path.relative_to(neighbor): (path.stat().st_dev, path.stat().st_ino, path.read_bytes())
                      for path in neighbor.rglob("*") if path.is_file()}


def test_declared_subject_direct_keyword_dual_invalid_and_absent(tmp_path: Path) -> None:
    parent = tmp_path / "project"
    root = parent / "work-items"
    module, work_items = _selected_owner_fixture(root, "dotted-task.md")
    seed_active(module, parent, "different-task")
    assert module.work_item_dependency_state(root=root, slug="dotted-task.md") == "open"
    assert module.work_item_dependency_state(root, "dotted-task.md") == "open"
    # A genuinely identical selected identity in both roots is ambiguous.
    seed_active(module, parent, "dotted-task.md")
    with pytest.raises(module.LifecycleError) as same_subject:
        module.work_item_dependency_state(root, "dotted-task.md")
    assert "acquisition ambiguous" in str(same_subject.value)
    # Same-root duplicate is domain DUAL, not root ambiguity.
    one = tmp_path / "single/work-items"
    own, ow = _selected_owner_fixture(one, "dual")
    write(ow / "backlog/dual.md", "status: candidate\n")
    with pytest.raises(own.LifecycleError) as dual:
        own.work_item_dependency_state(one, "dual")
    assert dual.value.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    invalid = ow / "active/invalid-known"
    invalid.mkdir()
    with pytest.raises((own.LifecycleError, FileNotFoundError)) as invalid_domain:
        own.close_item(one, "invalid-known", closure("2026-08-11T10:00:00Z").encode(), "2026-08-11T10:00:00Z")
    assert "acquisition" not in str(invalid_domain.value)
    with pytest.raises(own.LifecycleError) as missing:
        own.work_item_dependency_state(one, "missing-target")
    assert missing.value.failure_id == "WI-REFERENCE-MISSING"
    creation = tmp_path / "creation/work-items"
    creator, cw = _selected_owner_fixture(creation, "existing")
    creator.create_candidate(creation, "new-target", b"Task: New selected creation.\nNext action: Check.\nupdated: 2026-08-11T10:00:00Z\n")
    assert (cw / "backlog/new-target.md").is_file()
    with pytest.raises((own.LifecycleError, TypeError)):
        own.work_item_dependency_state(one, "")


def test_structural_archive_metadata_identity_and_currentness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "work-items"
    module, work_items = _selected_owner_fixture(root, "identity-task")
    archive = work_items / "archive"
    archive.mkdir()
    direct = archive / "ordinary-note.bin"
    direct.write_bytes(b"Direct metadata bytes.\n")
    dated = archive / "2026-10"
    dated.mkdir()
    month_file = dated / "metadata.bin"
    month_file.write_bytes(b"Month metadata bytes.\n")
    metadata = {direct, month_file}
    read_ids = {(p.stat().st_dev, p.stat().st_ino) for p in metadata}
    read_count = []
    original = module.os.fdopen
    class Observed:
        def __init__(self, stream, monitored): self.stream, self.monitored = stream, monitored
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def __getattr__(self, name): return getattr(self.stream, name)
        def read(self, *args):
            if self.monitored: read_count.append(1)
            return self.stream.read(*args)
    def observe(fd, *args, **kwargs):
        info = os.fstat(fd)
        return Observed(original(fd, *args, **kwargs), (info.st_dev, info.st_ino) in read_ids)
    with monkeypatch.context() as scoped:
        scoped.setattr(module.os, "fdopen", observe)
        for alias in (root, work_items):
            assert module.project_root_identity(alias)[:2] == (root, work_items)
        assert read_count == []
        full = module.archive_entity_inventory(root, input_role="repository-root")
        assert read_count and all(len(entity.snapshots) == 1 for entity in full.entities if entity.kind == "archive-metadata")
    for path in metadata:
        assert path.read_bytes() in (b"Direct metadata bytes.\n", b"Month metadata bytes.\n")
    with pytest.raises(module.LifecycleError):
        module.ArchiveEntity(direct, "archive-metadata", None, ())
    _r, _w, evidence = module.project_root_identity(root)
    direct.rename(archive / "held-old-metadata.bin")
    direct.write_bytes(b"Direct metadata bytes.\n")
    with pytest.raises(module.LifecycleError):
        module._verify_project_binding_evidence(evidence, "WI-README-STALE")
    module.refresh_readme(work_items)
    assert direct.read_bytes() == b"Direct metadata bytes.\n"
    full = module.archive_entity_inventory(root, input_role="repository-root")
    month_file.write_bytes(b"Changed month bytes.\n")
    with pytest.raises(module.LifecycleError): full.verify()


def test_selected_absence_and_parent_replacement_revalidate_under_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "project"
    root = parent / "work-items"
    module, work_items = _selected_owner_fixture(root, "target")
    seed_active(module, parent, "neighbor")
    original_enter = module.LifecycleTransaction.__enter__
    def competing_subject(transaction):
        (root / "active/target").mkdir()
        return original_enter(transaction)
    with monkeypatch.context() as scoped:
        scoped.setattr(module.LifecycleTransaction, "__enter__", competing_subject)
        with pytest.raises(module.LifecycleError) as appeared:
            module.work_item_dependency_state(root, "target")
    assert "absence changed" in str(appeared.value)
    assert (work_items / "active/target").is_dir()
    assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
    (root / "active/target").rmdir()
    evidence = []
    module._observe_project_path_at(root / "active/missing", "directory", evidence, "WI-README-STALE")
    (root / "active").rename(root / "held-active")
    (root / "active").mkdir()
    with pytest.raises(module.LifecycleError):
        module._verify_project_binding_evidence(tuple(evidence), "WI-README-STALE")


def test_native_target_whole_read_repeats_after_write(tmp_path: Path) -> None:
    module = load_module()
    assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
    assert module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get() is None
    path = tmp_path / "whole-read.bin"
    payload = b"0123456789ABCDEF"
    record = None
    with module.LifecycleWriteTarget(path, failure_id="WI-LIFECYCLE-WRITE-BOUNDARY") as target:
        primary = None
        try:
            record = target._new_creation(path, None, target._parent)
            handle = target._file(target.leaf, create=True, delete=True, _creation=record)
            record.identity = target._identity(handle)
            target._write_handle(handle, payload)
            assert target._read_handle(handle, len(payload)) == payload
            assert target._read_handle(handle, len(payload)) == payload
            assert target._identity(handle) == record.identity
            fresh = target._file(target.leaf)
            fresh_primary = None
            try:
                assert target._identity(fresh) == record.identity
                assert target._read_handle(fresh, len(payload)) == payload
            except BaseException as error:
                fresh_primary = error
                raise
            finally:
                target._release_handle(fresh, fresh_primary)
            assert target.read(maximum_bytes=len(payload)) == payload
        except BaseException as error:
            primary = error
            raise
        finally:
            if record is not None and not record.finished:
                target._finish_creation(record, primary, abort=True)
    assert record is not None and record.creator and record.finished
    assert record.deletion_accepted and record.release_complete and record.projection_complete
    assert record.phase == "disposed" and record.holder == "released" and not record.secondary
    assert not path.exists()


@pytest.mark.parametrize("payload,maximum,refused", (
    pytest.param(b"", 0, False, id="empty-zero"),
    pytest.param(b"x", 0, True, id="nonempty-zero"),
    pytest.param(b"0123456789ABCDEF", 15, True, id="over-bound-at-eof"),
))
def test_native_target_whole_read_envelope_at_eof(tmp_path: Path, payload: bytes, maximum: int, refused: bool) -> None:
    module = load_module()
    path = tmp_path / "bounded-read.bin"
    path.write_bytes(payload)
    with module.LifecycleWriteTarget(path, failure_id="WI-LIFECYCLE-WRITE-BOUNDARY") as target:
        handle = target._file(target.leaf)
        primary = None
        try:
            assert target._read_handle(handle, len(payload)) == payload
            if refused:
                with pytest.raises(OSError, match="admitted byte envelope"):
                    target._read_handle(handle, maximum)
            else:
                assert target._read_handle(handle, maximum) == b""
        except BaseException as error:
            primary = error
            raise
        finally:
            target._release_handle(handle, primary)
    assert path.read_bytes() == payload


@pytest.mark.parametrize("fault", ("seek", "read"))
def test_native_target_whole_read_failure_preserves_primary_and_release(tmp_path: Path, monkeypatch, fault: str) -> None:
    module = load_module()
    path = tmp_path / "failed-read.bin"
    payload = b"0123456789ABCDEF"
    path.write_bytes(payload)
    read_calls = []
    released = []
    with module.LifecycleWriteTarget(path, failure_id="WI-LIFECYCLE-WRITE-BOUNDARY") as target:
        original_close = module.LifecycleWriteTarget._close
        def close_then_report(owner, handle):
            original_close(owner, handle)
            released.append(handle)
            raise OSError("secondary-release-cause")
        with monkeypatch.context() as scoped:
            scoped.setattr(module.LifecycleWriteTarget, "_close", close_then_report)
            if os.name == "nt":
                c, _w, kernel, _nt, _types = target._native
                if fault == "seek":
                    def fail_seek(*args):
                        c.set_last_error(5)
                        return 0
                    scoped.setattr(kernel, "SetFilePointerEx", fail_seek)
                def fail_read(*args):
                    read_calls.append(1)
                    assert fault == "read", "read continued after failed positioning"
                    c.set_last_error(5)
                    return 0
                scoped.setattr(kernel, "ReadFile", fail_read)
            else:
                if fault == "seek":
                    def fail_seek(*args):
                        raise OSError(5, "positioning denied")
                    scoped.setattr(module.os, "lseek", fail_seek)
                def fail_read(*args):
                    read_calls.append(1)
                    assert fault == "read", "read continued after failed positioning"
                    raise OSError(5, "read denied")
                scoped.setattr(module.os, "read", fail_read)
            with pytest.raises(module.LifecycleError) as failure:
                target.read(maximum_bytes=len(payload))
            assert failure.value.failure_id == "WI-LIFECYCLE-WRITE-BOUNDARY"
            assert isinstance(failure.value.__cause__, OSError) and failure.value.__cause__.errno == 5
            expected_cause = "positioning" if fault == "seek" else "read"
            assert expected_cause in str(failure.value)
            assert any("secondary write-target-release: OSError" in note for note in failure.value.__notes__)
            assert read_calls == ([] if fault == "seek" else [1])
            assert len(released) == 1
    assert path.read_bytes() == payload



def test_owned_inverse_requires_actual_origin_epoch_actor_and_one_use(tmp_path):
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            prepared = transaction.prepare_owned_effect(transaction, source, destination, directory=True)
            for unsupported in (None, object(), prepared):
                with pytest.raises(module.LifecycleError, match="actual unused"):
                    transaction.qualify_owned_inverse(unsupported, operation="restore-move")
            transaction.replace_directory(source, destination)
            origin = next(value for kind, value in reversed(transaction.current_binding_evidence)
                          if kind == "owned-effect" and value.source == source)
            original_transaction = origin.transaction
            object.__setattr__(origin, "transaction", object())
            try:
                with pytest.raises(module.LifecycleError, match="actual unused"):
                    transaction.qualify_owned_inverse(origin, operation="restore-move")
            finally:
                object.__setattr__(origin, "transaction", original_transaction)
            actor = transaction._operation_owner
            transaction._operation_owner = object()
            with pytest.raises(module.LifecycleError, match="actual unused"):
                transaction.qualify_owned_inverse(origin, operation="restore-move")
            transaction._operation_owner = actor
            assert not any(kind == "integrity-failure" for kind, _value in transaction.current_binding_evidence)
            inverse = transaction.qualify_owned_inverse(origin, operation="restore-move")
            with pytest.raises(module.LifecycleError, match="actual unused"):
                transaction.qualify_owned_inverse(origin, operation="restore-move")
            transaction.replace_directory(destination, source, inverse=inverse)
            assert inverse.fulfilled and leaf.read_bytes() == b"original retained evidence"
            with pytest.raises(module.LifecycleError, match="already settled"):
                transaction.prepare_owned_effect(transaction, source, destination, directory=True, inverse=inverse)
            assert not any(kind == "integrity-failure" for kind, _value in transaction.current_binding_evidence)
            transaction.verify()
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_owned_inverse_selected_descendant_and_destination_conflicts_refuse(tmp_path):
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    transaction = module.LifecycleTransaction(root)
    with pytest.raises(module.LifecycleError):
        with transaction:
            token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            try:
                transaction.replace_directory(source, destination)
                origin = next(value for kind, value in reversed(transaction.current_binding_evidence)
                              if kind == "owned-effect" and value.source == source)
                selected = destination / leaf.relative_to(source)
                selected.write_bytes(b"foreign selected child")
                with pytest.raises(module.LifecycleError):
                    transaction.qualify_owned_inverse(origin, operation="restore-move")
                assert not source.exists() and selected.read_bytes() == b"foreign selected child"
            finally:
                module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_owned_inverse_conserves_foreign_parent_obligation_after_reversal(tmp_path):
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    outside = root / "actual-shared-parent-sibling.bin"
    outside.write_bytes(b"admitted shared parent sibling")
    original = outside.read_bytes()
    transaction = module.LifecycleTransaction(root)
    with pytest.raises(module.LifecycleError):
        with transaction:
            token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            try:
                transaction.observe_retained_inputs((module._capture_file_snapshot(outside, failure_id="TEST"),
                    module._capture_owned_directory_snapshot(root, failure_id="TEST")))
                transaction.replace_directory(source, destination)
                outside.write_bytes(b"foreign sibling")
                transaction.restore_owned_movement(destination, source)
                assert leaf.read_bytes() == b"original retained evidence" and outside.read_bytes() == b"foreign sibling"
                negatives = tuple(row for row in transaction.current_binding_evidence if row[0] == "integrity-failure")
                assert negatives
                outside.write_bytes(original)
                with pytest.raises(module.LifecycleError):
                    transaction.verify()
                with pytest.raises(module.LifecycleError):
                    module._atomic_write(outside, b"unauthorized forward")
                assert outside.read_bytes() == original
                assert all(any(current is row for current in transaction.current_binding_evidence) for row in negatives)
            finally:
                module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_owned_file_inverse_carries_relation_through_native_temporary_promotion(tmp_path):
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            module._atomic_write(outside, b"owned new body")
            transaction.restore_owned_file(outside, b"unaffected original proof")
            assert outside.read_bytes() == b"unaffected original proof"
            generated = outside.with_name("owned-generated.bin")
            module._atomic_write(generated, b"")
            transaction.restore_owned_file(generated, None)
            assert not generated.exists()
            transaction.verify()
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)



def test_owned_inverse_fresh_epoch_is_invalidated_by_retained_admission(tmp_path):
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            transaction.replace_directory(source, destination)
            origin = next(value for kind, value in reversed(transaction.current_binding_evidence)
                          if kind == "owned-effect" and value.source == source)
            inverse = transaction.qualify_owned_inverse(origin, operation="restore-move")
            transaction.observe_retained_inputs((module._capture_file_snapshot(outside, failure_id="TEST"),))
            assert not inverse.current_pair_is_bound()
            with pytest.raises(module.LifecycleError, match="origin or epoch"):
                transaction.replace_directory(destination, source, inverse=inverse)
            assert destination.is_dir() and not source.exists()
            assert not any(kind == "integrity-failure" for kind, _value in transaction.current_binding_evidence)
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


@pytest.mark.parametrize("conflict", ("occupied-destination", "parent-retarget"))
def test_owned_inverse_preserves_actual_destination_and_parent_conflicts(tmp_path, conflict):
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    with pytest.raises(module.LifecycleError):
        with module.LifecycleTransaction(root) as transaction:
            token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            try:
                transaction.replace_directory(source, destination)
                origin = next(value for kind, value in reversed(transaction.current_binding_evidence)
                              if kind == "owned-effect" and value.source == source)
                if conflict == "occupied-destination":
                    source.mkdir()
                    foreign = source / "foreign.txt"
                    foreign.write_bytes(b"foreign occupied destination")
                    owned = destination / leaf.relative_to(source)
                else:
                    displaced = root / "foreign-relocated-parent"
                    destination.parent.rename(displaced)
                    destination.parent.mkdir()
                    foreign = destination.parent / "foreign.txt"
                    foreign.write_bytes(b"foreign replacement parent")
                    owned = displaced / destination.name / leaf.relative_to(source)
                with pytest.raises(module.LifecycleError):
                    transaction.qualify_owned_inverse(origin, operation="restore-move")
                assert foreign.read_bytes().startswith(b"foreign")
                assert owned.read_bytes() == b"original retained evidence"
            finally:
                module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)


def test_owned_inverse_checks_runtime_source_independently_after_payload_drift(tmp_path, monkeypatch):
    module, runtime, alias, physical, root = _runtime_authority_fixture(tmp_path, monkeypatch, linked=False)
    leaf = root / "selected.txt"
    leaf.write_bytes(b"admitted original")
    outside = root / "unselected.txt"
    outside.write_bytes(b"admitted unrelated")
    transaction = module.LifecycleTransaction(root)
    with pytest.raises(module.LifecycleError):
        with transaction:
            token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            try:
                transaction.observe_retained_inputs((module._capture_file_snapshot(outside, failure_id="TEST"),))
                module._validator_module()
                module._atomic_write(leaf, b"owned postimage")
                outside.write_bytes(b"foreign payload mismatch first")
                source = runtime / "scripts/validate-work-item-state.py"
                source.write_bytes(source.read_bytes() + b"\n# synthetic source drift\n")
                with pytest.raises(module.LifecycleError) as caught:
                    transaction.restore_owned_file(leaf, b"admitted original")
                assert transaction._source_admission_failure is caught.value
                assert leaf.read_bytes() == b"owned postimage"
                assert outside.read_bytes() == b"foreign payload mismatch first"
            finally:
                module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)



def test_owned_file_inverse_native_refusal_settles_its_actual_temporary_creator(tmp_path, monkeypatch):
    module, root, source, destination, leaf, outside = _relocation_observation_fixture(tmp_path)
    records = []
    with module.LifecycleTransaction(root) as transaction:
        token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            module._atomic_write(outside, b"owned current body")
            create = module.LifecycleWriteTarget._new_creation
            rename = module.LifecycleWriteTarget._windows_rename
            sentinel = OSError("controlled inverse native promotion refusal")
            def capture(owner, *args, **kwargs):
                record = create(owner, *args, **kwargs)
                if owner._inverse is not None:
                    records.append(record)
                return record
            def refuse(owner, handle, leaf, **kwargs):
                if owner._inverse is not None:
                    raise sentinel
                return rename(owner, handle, leaf, **kwargs)
            with monkeypatch.context() as scoped:
                scoped.setattr(module.LifecycleWriteTarget, "_new_creation", capture)
                scoped.setattr(module.LifecycleWriteTarget, "_windows_rename", refuse)
                with pytest.raises(module.LifecycleError) as failed:
                    transaction.restore_owned_file(outside, b"unaffected original proof")
                assert failed.value.__cause__ is sentinel
            assert outside.read_bytes() == b"owned current body"
            assert records and all(record.finished and record.release_complete for record in records)
            assert all(not record.locator.exists() for record in records)
            assert not list(outside.parent.glob("*.tmp"))
            transaction.verify()
        finally:
            module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)



@pytest.mark.parametrize("producer", ("normalization-receipt", "v0-created-readme", "terminalization-receipt"))
def test_public_conditional_owned_output_removal_uses_actual_native_inverse(tmp_path, monkeypatch, producer):
    root = tmp_path / "repo"
    hits = []
    if producer == "normalization-receipt":
        module, work_items, _old, new, source, _lineage, _physical, inventory, output = _identity_normalization_fixture(root)
        before = {path: path.read_bytes() for path in work_items.rglob("*") if path.is_file()}
        replay = module._normalization_replay
        def fail_after_real_receipt(*args, **kwargs):
            assert replay(*args, **kwargs) is True
            assert output.exists()
            raise RuntimeError("controlled failure after native normalization receipt publication")
        monkeypatch.setattr(module, "_normalization_replay", fail_after_real_receipt)
        invoke = lambda: module.normalize_current_identity(
            root, "decision", source.relative_to(root).as_posix(), new, inventory, output)
        expected_failure = "WI-IDENTITY-NORMALIZE-ROLLBACK"
    elif producer == "v0-created-readme":
        module = load_module()
        slug, instant = "2026-08-01-native-readme-inverse", "2026-08-01T00:00:00Z"
        source = root / "work-items/decisions" / (slug + ".md")
        write(source, _legacy_v0_decision_record(status="superseded", identity_line="id: " + slug))
        digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()
        _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
        inventory = root / "incoming.json"
        write(inventory, json.dumps({"reference": "decision:" + slug, "expectedSourceSha256": digest,
            "archivedAt": instant, "rationale": "Superseded.", "evidence": "Synthetic native custody.", "incomingLinks": []}))
        work_items, output = root / "work-items", root / "work-items/README.md"
        assert not output.exists()
        before = {path: path.read_bytes() for path in work_items.rglob("*") if path.is_file()}
        refresh = module.refresh_readme
        def fail_after_real_refresh(*args, **kwargs):
            refresh(*args, **kwargs)
            assert output.exists()
            raise module.LifecycleError("WI-README-STALE", "controlled failure after native README publication")
        monkeypatch.setattr(module, "refresh_readme", fail_after_real_refresh)
        invoke = lambda: module.migrate_legacy(root, "decision:" + slug, incoming_links_inventory=inventory)
        expected_failure = "WI-README-STALE"
    else:
        module = load_module()
        work_items = root / "work-items"
        source = work_items / "bugs/owned-terminal-output.md"
        source.parent.mkdir(parents=True)
        source.write_bytes(_pre_v1_terminal_record("fixed", source.stem))
        inventory, output = root / ".scratch/inventory.json", root / ".scratch/receipt.json"
        _denied_terminalization_inventory(work_items, inventory)
        before = {path: path.read_bytes() for path in work_items.rglob("*") if path.is_file()}
        publish = module._atomic_write
        def fail_after_real_receipt(path, data, **kwargs):
            result = publish(path, data, **kwargs)
            if path == output:
                assert output.exists()
                raise OSError("controlled failure after native terminalization receipt publication")
            return result
        monkeypatch.setattr(module, "_atomic_write", fail_after_real_receipt)
        invoke = lambda: module.terminalize_v1_inventory(root, inventory,
            terminal_at="2026-08-01T00:00:00Z", authorization_marker="operator-authorized-v1-terminalization", receipt_path=output)
        expected_failure = "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    remove = module._remove_lifecycle_file
    def observe(path, *args, **kwargs):
        if path == output:
            transaction = module._CURRENT_LIFECYCLE_TRANSACTION.get()
            inverse = kwargs["inverse"]
            assert transaction is inverse.transaction and transaction._locked and inverse.current_pair_is_bound()
            assert inverse.source == output and inverse.destination is None and not inverse.fulfilled
            creator = inverse.inverse_origin.creator
            assert creator.creator and creator.acquired and creator.release_complete
            assert creator.native_result == (2 if module.os.name == "nt" else "exclusive-open")
        result = remove(path, *args, **kwargs)
        if path == output:
            assert inverse.fulfilled and not output.exists()
            assert output not in transaction._retained_observations
            assert ("absent", output) in transaction.current_binding_evidence
            hits.append(inverse)
        return result
    monkeypatch.setattr(module, "_remove_lifecycle_file", observe)
    with pytest.raises(module.LifecycleError) as failed:
        invoke()
    assert failed.value.failure_id == expected_failure
    assert len(hits) == 1 and not output.exists()
    assert {path: path.read_bytes() for path in work_items.rglob("*") if path.is_file()} == before
    assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
    assert module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get() is None


# Root-admitted unchanged independent QA A-D assertions, ported to this existing test owner.
def _r5_correction_error(e):
    return {"kind":type(e).__name__,"failureId":getattr(e,"failure_id",None),"message":str(e)}

def _r5_correction_attempt(call):
    try:return {"returned":True,"value":str(call())},None
    except BaseException as e:return {"returned":False,"error":_r5_correction_error(e)},e

def _r5_correction_native(module,p):
    s=p.lstat();return {"identity":module._lifecycle_file_identity(s),"size":s.st_size,"mtimeNs":s.st_mtime_ns,"ctimeNs":s.st_ctime_ns,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}

def _r5_correction_negative(tx):
    return [{"failure":_r5_correction_error(value[1]),"paths":[str(p.relative_to(tx.repository_root)) for p in value[2]]} for kind,value in tx.current_binding_evidence if kind=="integrity-failure"]

def _r5_correction_retain(name,rows):
    # Original QA assertions; the existing ProcessRunner retains actual stdout.
    print(json.dumps({"probe": name, "actual": rows}, default=str), flush=True)


def test_after_qualification_selected_refusal_cannot_become_clean_after_foreign_byte_reversal(tmp_path):
    module,root,source,destination,leaf,outside=_relocation_observation_fixture(tmp_path)
    tx=module.LifecycleTransaction(root);tx.__enter__();token=module._CURRENT_LIFECYCLE_TRANSACTION.set(tx)
    rows={"source":str(module.__file__)}
    first=None
    try:
        original=outside.read_bytes();post=b"owned current postimage"
        module._atomic_write(outside,post)
        origin=next(value for kind,value in reversed(tx.current_binding_evidence) if kind=="owned-effect" and value.destination==outside)
        inverse=tx.qualify_owned_inverse(origin,operation="restore-file")
        assert inverse.current_pair_is_bound() and inverse.inverse_origin is origin
        rows['positiveQualified']=True;rows['retainedKindsBefore']={str(p.relative_to(root)):type(v).__name__ for p,v in tx._retained_observations.items()}
        rows['nativePostimage']=_r5_correction_native(module,outside);map_ref=tx._retained_observations
        outside.write_bytes(b"foreign selected mutation")
        rows['foreignSelected']=_r5_correction_native(module,outside)
        rows['nativeInverseAttempt'],first=_r5_correction_attempt(lambda:module._atomic_write(outside,original,inverse=inverse))
        rows['negativeAfterAcquiredRefusal']=_r5_correction_negative(tx)
        rows['inverseFulfilledAfterRefusal']=inverse.fulfilled
        outside.write_bytes(post)
        rows['foreignReversed']=_r5_correction_native(module,outside)
        rows['sameRetainedMapAfterReversal']=tx._retained_observations is map_ref
        rows['negativeAfterForeignReversal']=_r5_correction_negative(tx)
        rows['defaultVerify'],_= _r5_correction_attempt(tx.verify)
        new=root/'post-refusal-forward.bin'
        rows['newForward'],_= _r5_correction_attempt(lambda:module._atomic_write(new,b"new forward after acquired selected failure"))
        rows['newForwardExists']=new.exists()
        rows['negativeAfterNewForward']=_r5_correction_negative(tx)
    finally:
        module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
        rows['finalTransactionExit'],_= _r5_correction_attempt(lambda:tx.__exit__(None,None,None))
        rows['transactionSettled']=tx._file is None and not tx._locked
        rows['contextCleared']=module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
        _r5_correction_retain('late-selected-refusal-observation.json',rows)
    assert first is not None and getattr(first,'failure_id',None)=='WI-LIFECYCLE-EFFECT',rows
    assert rows['nativePostimage']['identity']==rows['foreignReversed']['identity']
    assert rows['nativePostimage']['sha256']==rows['foreignReversed']['sha256']
    assert rows['negativeAfterAcquiredRefusal'] and rows['negativeAfterForeignReversal'],rows
    assert not rows['defaultVerify']['returned'] and not rows['newForward']['returned'] and not rows['newForwardExists'],rows
    assert not rows['finalTransactionExit']['returned'],rows
    assert rows['transactionSettled'] and rows['contextCleared'],rows

def test_known_present_owned_file_cannot_become_clean_through_absence_noop_and_same_identity_return(tmp_path):
    module,root,source,destination,leaf,outside=_relocation_observation_fixture(tmp_path)
    tx=module.LifecycleTransaction(root);tx.__enter__();token=module._CURRENT_LIFECYCLE_TRANSACTION.set(tx)
    rows={"source":str(module.__file__)}
    try:
        absent=root/'valid-never-retained.bin'
        assert absent not in tx._retained_observations and not absent.exists()
        rows['validUnretainedAbsence'],_= _r5_correction_attempt(lambda:tx.restore_owned_file(absent,None))
        assert rows['validUnretainedAbsence']['returned']
        owned=outside.parent/'owned-created.bin';held=outside.parent/'foreign-moved-owned.bin'
        module._atomic_write(owned,b"actual owned created body")
        current=tx._retained_observations[owned]
        origin=next(value for kind,value in reversed(tx.current_binding_evidence) if kind=="owned-effect" and value.destination==owned)
        assert origin.before.get(owned) is None and origin.native_after.identity==current.identity
        assert origin.creator.creator and origin.creator.acquired and origin.creator.release_complete
        rows['nativeOwnedBefore']=_r5_correction_native(module,owned);rows['actualCreator']={'acquired':origin.creator.acquired,'released':origin.creator.release_complete,'nativeResult':origin.creator.native_result}
        rows['retainedKindsBefore']={str(p.relative_to(root)):type(v).__name__ for p,v in tx._retained_observations.items()}
        owned.rename(held)
        assert not owned.exists() and module._lifecycle_file_identity(held.lstat())==current.identity
        rows['admittedCaptureStillPresent']=tx._retained_observations[owned] is current
        rows['absenceCompensation'],_=_r5_correction_attempt(lambda:tx.restore_owned_file(owned,None))
        rows['negativeAfterAbsence']=_r5_correction_negative(tx)
        assert held.exists() and not owned.exists()
        held.rename(owned)
        rows['sameIdentityReturned']=_r5_correction_native(module,owned)
        rows['negativeAfterIdentityReturn']=_r5_correction_negative(tx)
        rows['defaultVerify'],_=_r5_correction_attempt(tx.verify)
        new=root/'post-absence-forward.bin'
        rows['newForward'],_=_r5_correction_attempt(lambda:module._atomic_write(new,b"new forward after known missing owned file"))
        rows['newForwardExists']=new.exists()
        rows['negativeAfterNewForward']=_r5_correction_negative(tx)
    finally:
        module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
        rows['finalTransactionExit'],_=_r5_correction_attempt(lambda:tx.__exit__(None,None,None))
        rows['transactionSettled']=tx._file is None and not tx._locked
        rows['contextCleared']=module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
        _r5_correction_retain('known-present-absence-observation.json',rows)
    assert rows['nativeOwnedBefore']['identity']==rows['sameIdentityReturned']['identity']
    assert rows['nativeOwnedBefore']['sha256']==rows['sameIdentityReturned']['sha256']
    assert not rows['absenceCompensation']['returned'] and rows['negativeAfterAbsence'],rows
    assert rows['negativeAfterIdentityReturn'] and not rows['defaultVerify']['returned'],rows
    assert not rows['newForward']['returned'] and not rows['newForwardExists'] and not rows['finalTransactionExit']['returned'],rows
    assert rows['transactionSettled'] and rows['contextCleared'],rows


def test_actual_parent_mode_change_requires_strict_inverse_qualification(tmp_path):
    import stat
    module,root,source,destination,leaf,outside=_relocation_observation_fixture(tmp_path)
    tx=module.LifecycleTransaction(root);tx.__enter__();token=module._CURRENT_LIFECYCLE_TRANSACTION.set(tx)
    parent=outside.parent; original_mode=parent.stat().st_mode
    rows={"source":str(module.__file__),"originalMode":original_mode,"actualParentIdentity":module._lifecycle_file_identity(parent.lstat())}
    changed=False; meaningful=False
    try:
        module._atomic_write(outside,b"owned current body for mode discriminator")
        origin=tx._owned_file_origin(outside,b"unaffected original proof")
        rows['parentRetainedAsMapRow']=parent in tx._retained_observations
        assert not rows['parentRetainedAsMapRow']
        rows['originParentMode']=origin.directories[parent].metadata.st_mode
        rows['originParentIdentity']=module._lifecycle_file_identity(origin.directories[parent].metadata)
        mode_attempt,mode_error=_r5_correction_attempt(lambda:os.chmod(parent,original_mode & ~stat.S_IWRITE))
        rows['actualChmod']=mode_attempt
        changed=mode_error is None
        rows['currentMode']=parent.stat().st_mode
        rows['currentParentIdentity']=module._lifecycle_file_identity(parent.lstat())
        meaningful=rows['currentMode'] != rows['originParentMode']
        rows['actualModeFieldChanged']=meaningful
        if meaningful:
            rows['qualification'],_=_r5_correction_attempt(lambda:tx.qualify_owned_inverse(origin,operation="restore-file"))
            rows['negativeAfterQualification']=_r5_correction_negative(tx)
            rows['defaultVerify'],_=_r5_correction_attempt(tx.verify)
        else:
            rows['runtimeStatus']='UNVERIFIED: Windows chmod did not change the st_mode field required by the accepted parent proof'
    finally:
        if changed:
            rows['restoreActualParentMode'],_=_r5_correction_attempt(lambda:os.chmod(parent,original_mode))
        module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
        rows['finalTransactionExit'],_=_r5_correction_attempt(lambda:tx.__exit__(None,None,None))
        rows['transactionSettled']=tx._file is None and not tx._locked
        rows['contextCleared']=module._CURRENT_LIFECYCLE_TRANSACTION.get() is None
        _r5_correction_retain('parent-mode-observation.json',rows)
    if not meaningful:
        pytest.skip(rows['runtimeStatus'])
    assert rows['originParentIdentity']==rows['currentParentIdentity']
    assert not rows['qualification']['returned'],rows
    assert rows['negativeAfterQualification'] and not rows['defaultVerify']['returned'],rows
    assert not rows['finalTransactionExit']['returned'],rows
    assert rows['transactionSettled'] and rows['contextCleared'],rows


def test_conversion_foreign_target_refusal_does_not_skip_disjoint_original_directory_inverse(tmp_path,monkeypatch):
    import dataclasses
    module=load_module();root=tmp_path/"repo";slug="qa-conversion-independent-inverse"
    source,before=_seed_legacy_backlog(root,slug,{"brief.md":b"preserve rollback source\n","notes/design.md":b"preserve recursive rollback source\n"})
    source_id=module._lifecycle_file_identity(source.lstat())
    leaf_ids={n:module._lifecycle_file_identity((source/n).lstat()) for n in before}
    module.refresh_readme(root,allow_marker_bootstrap=True);readme=root/"work-items/README.md";readme_before=readme.read_bytes()
    target=source.with_suffix('.md');held=root/'foreign-moved-owned-candidate.md';foreign=b"QA DISTINCT FOREIGN TARGET: preserve identity and bytes\n"
    move=module.LifecycleTransaction.replace_directory;restore=module.LifecycleTransaction.restore_owned_movement
    rows={'injectionCount':0,'sourceInverseCalls':[]};stages=[];transactions=[]
    def capture_forward(tx,current,destination,*args,**kwargs):
        result=move(tx,current,destination,*args,**kwargs)
        if current==source:
            assert destination.is_dir() and not source.exists()
            stages.append(destination);transactions.append(tx)
            assert module._lifecycle_file_identity(destination.lstat())==source_id
        if destination==target and kwargs.get('directory') is False and kwargs.get('inverse') is None:
            assert len(stages)==1 and module._CURRENT_LIFECYCLE_TRANSACTION.get() is tx and tx._locked
            assert target.is_file()
            rows['ownedCandidateIdentityBefore']=module._lifecycle_file_identity(target.lstat())
            rows['ownedCandidateSha256']=hashlib.sha256(target.read_bytes()).hexdigest()
            target.rename(held);target.write_bytes(foreign)
            rows['foreignIdentityBefore']=module._lifecycle_file_identity(target.lstat())
            assert rows['foreignIdentityBefore']!=rows['ownedCandidateIdentityBefore']
            rows['injectionCount']+=1;assert rows['injectionCount']==1
        return result
    def observe_inverse(tx,current,destination):
        if stages and current==stages[0] and destination==source:
            rows['sourceInverseCalls'].append({'sameHeldTransaction':module._CURRENT_LIFECYCLE_TRANSACTION.get() is tx,'source':str(current.relative_to(root)),'destination':str(destination.relative_to(root))})
        return restore(tx,current,destination)
    monkeypatch.setattr(module.LifecycleTransaction,'replace_directory',capture_forward)
    monkeypatch.setattr(module.LifecycleTransaction,'restore_owned_movement',observe_inverse)
    observer=module.LifecycleDiagnosticObserver();caught=None
    try:
        module.convert_legacy_candidate(root,slug,b"status: candidate\nTask: candidate\nNext action: verify\n",inject_readme_failure=True,diagnostic_observer=observer)
    except BaseException as e:caught=e
    rows['raised']={'kind':type(caught).__name__,'failureId':getattr(caught,'failure_id',None),'message':str(caught)}
    rows['diagnostic']=dataclasses.asdict(observer.snapshot) if observer.snapshot else None
    rows['actualStage']=str(stages[0].relative_to(root)) if stages else None
    rows['foreignTargetPreserved']=target.is_file() and target.read_bytes()==foreign
    rows['foreignIdentityAfter']=module._lifecycle_file_identity(target.lstat()) if target.exists() else None
    rows['movedOwnedCandidatePreserved']=held.exists() and hashlib.sha256(held.read_bytes()).hexdigest()==rows.get('ownedCandidateSha256')
    rows['movedOwnedCandidateIdentity']=module._lifecycle_file_identity(held.lstat()) if held.exists() else None
    rows['originalSourceRestored']=source.is_dir() and all((source/n).read_bytes()==b for n,b in before.items())
    rows['stagedOriginalPreserved']=bool(stages) and stages[0].is_dir() and all((stages[0]/n).read_bytes()==b for n,b in before.items())
    selected=source if source.exists() else (stages[0] if stages else None)
    rows['selectedOriginalIdentity']=module._lifecycle_file_identity(selected.lstat()) if selected and selected.exists() else None
    rows['selectedOriginalLeafIdentities']={n:module._lifecycle_file_identity((selected/n).lstat()) for n in before} if selected and selected.exists() else {}
    rows['readmeExact']=readme.read_bytes()==readme_before
    rows['negativeObligations']=[{'failureId':getattr(v[1],'failure_id',None),'paths':[str(p.relative_to(root)) for p in v[2]]} for tx in transactions for kind,v in tx.current_binding_evidence if kind=='integrity-failure']
    rows['transactionSettled']=bool(transactions) and all(tx._file is None and not tx._locked for tx in transactions)
    rows['contextsCleared']=module._CURRENT_LIFECYCLE_TRANSACTION.get() is None and module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get() is None
    print(json.dumps(rows,default=str))
    assert rows['injectionCount']==1 and rows['foreignTargetPreserved'] and rows['movedOwnedCandidatePreserved'],rows
    assert rows['foreignIdentityBefore']==rows['foreignIdentityAfter']
    assert rows['ownedCandidateIdentityBefore']==rows['movedOwnedCandidateIdentity']
    assert rows['selectedOriginalIdentity']==source_id and rows['selectedOriginalLeafIdentities']==leaf_ids
    assert getattr(caught,'failure_id',None)=='WI-README-STALE' and observer.snapshot.primaryFailureId=='WI-README-STALE',rows
    assert observer.snapshot.rollback=='incomplete' and observer.snapshot.cleanupFailures,rows
    assert rows['sourceInverseCalls'] and rows['originalSourceRestored'],rows
    assert rows['readmeExact'] and rows['transactionSettled'] and rows['contextsCleared'],rows



def test_conversion_selected_destination_conflict_preserves_original_stage_and_foreign_state(tmp_path, monkeypatch):
    module = load_module()
    root, slug = tmp_path / "repo", "conversion-selected-destination-conflict"
    source, original = _seed_legacy_backlog(root, slug, {
        "brief.md": b"original custody must remain staged\n", "nested/evidence.bin": b"exact nested original\n"})
    original_identity = module._lifecycle_file_identity(source.lstat())
    leaf_identities = {name: module._lifecycle_file_identity((source / name).lstat()) for name in original}
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items/README.md"
    readme_before = readme.read_bytes()
    target, held = source.with_suffix(".md"), root / "foreign-moved-owned-candidate.md"
    foreign_target, foreign_source = b"distinct foreign candidate target\n", b"distinct occupied source destination\n"
    move, restore = module.LifecycleTransaction.replace_directory, module.LifecycleTransaction.restore_owned_movement
    observed, stages, calls = {"hits": 0}, [], []
    def substitute(transaction, current, destination, *args, **kwargs):
        result = move(transaction, current, destination, *args, **kwargs)
        if current == source:
            stages.append(destination)
        if destination == target and kwargs.get("inverse") is None:
            assert len(stages) == 1 and transaction._locked
            assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is transaction
            target.rename(held)
            target.write_bytes(foreign_target)
            source.mkdir()
            (source / "foreign.bin").write_bytes(foreign_source)
            observed.update(hits=observed["hits"] + 1,
                target_identity=module._lifecycle_file_identity(target.lstat()),
                source_identity=module._lifecycle_file_identity(source.lstat()), transaction=transaction)
        return result
    def observe_restore(transaction, current, destination):
        if stages and current == stages[0] and destination == source:
            calls.append(transaction)
        return restore(transaction, current, destination)
    monkeypatch.setattr(module.LifecycleTransaction, "replace_directory", substitute)
    monkeypatch.setattr(module.LifecycleTransaction, "restore_owned_movement", observe_restore)
    observer = module.LifecycleDiagnosticObserver()
    with pytest.raises(module.LifecycleError) as failure:
        module.convert_legacy_candidate(root, slug,
            b"status: candidate\nTask: candidate\nNext action: verify\n", inject_readme_failure=True,
            diagnostic_observer=observer)
    assert observed["hits"] == 1 and len(calls) == 1
    assert failure.value.failure_id == observer.snapshot.primaryFailureId == "WI-README-STALE"
    assert observer.snapshot.rollback == "incomplete"
    assert (source / "foreign.bin").read_bytes() == foreign_source and target.read_bytes() == foreign_target
    assert module._lifecycle_file_identity(source.lstat()) == observed["source_identity"]
    assert module._lifecycle_file_identity(target.lstat()) == observed["target_identity"]
    assert module._lifecycle_file_identity(stages[0].lstat()) == original_identity
    assert {name: (stages[0] / name).read_bytes() for name in original} == original
    assert {name: module._lifecycle_file_identity((stages[0] / name).lstat()) for name in original} == leaf_identities
    assert held.is_file() and readme.read_bytes() == readme_before
    negatives = [value for kind, value in observed["transaction"].current_binding_evidence if kind == "integrity-failure"]
    assert any(source in value[2] for value in negatives)
    assert any(row.phase == "rollback-action" and "restore staged original source" in row.diagnostic
               for row in observer.snapshot.cleanupFailures)
    assert not observed["transaction"]._locked and observed["transaction"]._file is None
    assert module._CURRENT_LIFECYCLE_TRANSACTION.get() is None and module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get() is None



def test_owned_retirement_recheck_conserves_late_selected_failure_before_native_entry(tmp_path):
    module, root, _source, _destination, _leaf, outside = _relocation_observation_fixture(tmp_path)
    path = outside.with_name("created-for-retirement-recheck.bin")
    body = b"actual owned retirement body"
    transaction = module.LifecycleTransaction(root)
    transaction.__enter__()
    token = module._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
    rows = {}
    try:
        module._atomic_write(path, body)
        identity = module._lifecycle_file_identity(path.lstat())
        origin = transaction._owned_file_origin(path, None)
        inverse = transaction.qualify_owned_inverse(origin, operation="remove-created")
        path.write_bytes(b"foreign same-ID body before native retirement entry")
        rows["removal"], failure = _r5_correction_attempt(lambda: module._remove_lifecycle_file(
            path, failure_id="TEST-RETAINED-RETIREMENT", inverse=inverse))
        assert isinstance(failure, module.LifecycleError)
        rows["negativeAfterRefusal"] = _r5_correction_negative(transaction)
        path.write_bytes(body)
        assert module._lifecycle_file_identity(path.lstat()) == identity
        rows["verifyAfterSameIdentityByteReturn"], _ = _r5_correction_attempt(transaction.verify)
        forward = root / "forbidden-post-retirement-forward.bin"
        rows["newForward"], _ = _r5_correction_attempt(lambda: module._atomic_write(forward, b"must refuse"))
        rows["newForwardExists"] = forward.exists()
    finally:
        module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
        rows["finalExit"], _ = _r5_correction_attempt(lambda: transaction.__exit__(None, None, None))
        rows["settled"] = transaction._file is None and not transaction._locked
        _r5_correction_retain("retirement-entry-conservation", rows)
    assert rows["negativeAfterRefusal"] and not rows["verifyAfterSameIdentityByteReturn"]["returned"]
    assert not rows["newForward"]["returned"] and not rows["newForwardExists"]
    assert not rows["finalExit"]["returned"] and rows["settled"]


# Three unchanged independent E/F/G semantic oracles; diagnostics use existing stdout ownership.
def _r6_phase_negative(tx):
    return [{"error": _r5_correction_error(value[1]),
             "paths": [str(path.relative_to(tx.repository_root)) for path in value[2]]}
            for kind, value in tx.current_binding_evidence if kind == "integrity-failure"]

def _r6_phase_native(m,p):
    s=p.lstat();return {'id':m._lifecycle_file_identity(s),'mode':s.st_mode,'size':s.st_size,'mtimeNs':s.st_mtime_ns,'ctimeNs':s.st_ctime_ns,'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None}
def _r6_phase_persist(n,row):
    _r5_correction_retain(n, row)

def _r6_phase_finish(m,tx,token,row,name):
    m._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    row['finalExit'],_=_r5_correction_attempt(lambda:tx.__exit__(None,None,None));row['settled']=tx._file is None and not tx._locked;row['contextCleared']=m._CURRENT_LIFECYCLE_TRANSACTION.get() is None;_r6_phase_persist(name,row)

def test_inverse_destination_parent_failure_survives_same_parent_return(tmp_path):
    m,root,source,destination,leaf,outside=_relocation_observation_fixture(tmp_path)
    left=root/'left-original-parent';left.mkdir();source.rename(left/source.name);source=left/source.name;leaf=source/'nested/proof.bin';held=root/'foreign-held-original-parent'
    tx=m.LifecycleTransaction(root);tx.__enter__();token=m._CURRENT_LIFECYCLE_TRANSACTION.set(tx);row={'actualModule':m.__file__}
    try:
        tx.replace_directory(source,destination)
        origin=next(v for k,v in reversed(tx.current_binding_evidence) if k=='owned-effect' and v.source==source)
        row['actualCompletedForward']=origin.native_after is not None;row['parentBefore']=_r6_phase_native(m,left)
        row['retainedKindsBefore']={str(p.relative_to(root)):type(v).__name__ for p,v in tx._retained_observations.items()}
        left.rename(held);row['destinationAbsentAfterParentMove']=not source.exists();row['sameParentAside']=_r6_phase_native(m,held)
        row['qualification'],failure=_r5_correction_attempt(lambda:tx.qualify_owned_inverse(origin,operation='restore-move'))
        row['negativeAfterAcquiredFailure']=_r6_phase_negative(tx)
        held.rename(left);row['parentReturned']=_r6_phase_native(m,left);row['negativeAfterSameParentReturn']=_r6_phase_negative(tx)
        row['defaultVerify'],_=_r5_correction_attempt(tx.verify)
        new=root/'forbidden-after-parent-return.bin';row['newForward'],_=_r5_correction_attempt(lambda:m._atomic_write(new,b'forward after acquired destination-parent refusal'));row['newForwardExists']=new.exists()
        row['originalSelectedBytesIntact']=(destination/'nested/proof.bin').read_bytes()==b'original retained evidence'
    finally:_r6_phase_finish(m,tx,token,row,'inverse-destination-parent-observation.json')
    assert failure is not None,row
    assert row['parentBefore']['id']==row['sameParentAside']['id']==row['parentReturned']['id']
    assert row['negativeAfterAcquiredFailure'] and row['negativeAfterSameParentReturn'],row
    assert not row['defaultVerify']['returned'] and not row['newForward']['returned'] and not row['newForwardExists'],row
    assert not row['finalExit']['returned'] and row['settled'] and row['contextCleared'],row

def test_actual_late_native_owned_image_refusal_survives_same_identity_byte_return(tmp_path,monkeypatch):
    m,root,source,destination,leaf,outside=_relocation_observation_fixture(tmp_path)
    path=outside.with_name('actual-late-owned-image.bin');body=b'actual current native image';tx=m.LifecycleTransaction(root);tx.__enter__();token=m._CURRENT_LIFECYCLE_TRANSACTION.set(tx);row={'actualModule':m.__file__,'injectionCount':0};owners=[]
    try:
        m._atomic_write(path,body);origin=tx._owned_file_origin(path,None);inverse=tx.qualify_owned_inverse(origin,operation='remove-created');row['nativeBefore']=_r6_phase_native(m,path)
        acquire=m.LifecycleWriteTarget._acquire_existing_parents;image=m.LifecycleWriteTarget.owned_image
        def mutate_after_real_parent_acquire(owner,*args,**kwargs):
            result=acquire(owner,*args,**kwargs)
            if owner.path==path and owner._inverse is inverse:
                assert m._CURRENT_LIFECYCLE_TRANSACTION.get() is tx and tx._locked and owner._open
                assert row['injectionCount']==0
                owners.append(owner);path.write_bytes(b'X'*len(body));row['injectionCount']+=1;row['nativeMutated']=_r6_phase_native(m,path)
            return result
        def observe_real_image(owner,*args,**kwargs):
            result=image(owner,*args,**kwargs)
            if owner.path==path and owner._inverse is inverse:
                row['actualNativeImage']={'identity':result['identity'],'sha256':result['sha256'],'bodyHex':m._unb64(result['data']).hex()} if result else None
            return result
        with monkeypatch.context() as scoped:
            scoped.setattr(m.LifecycleWriteTarget,'_acquire_existing_parents',mutate_after_real_parent_acquire);scoped.setattr(m.LifecycleWriteTarget,'owned_image',observe_real_image)
            row['removal'],failure=_r5_correction_attempt(lambda:m._remove_lifecycle_file(path,failure_id='QA-LATE-OWNED-IMAGE',inverse=inverse))
        row['negativeAfterAcquiredFailure']=_r6_phase_negative(tx);row['ownerClosedAfterFailure']=[not o._open and not o._directories for o in owners]
        row['pathStillPresent']=path.exists();path.write_bytes(body);row['nativeReturned']=_r6_phase_native(m,path);row['negativeAfterByteReturn']=_r6_phase_negative(tx)
        row['defaultVerify'],_=_r5_correction_attempt(tx.verify)
        new=root/'forbidden-after-native-image.bin';row['newForward'],_=_r5_correction_attempt(lambda:m._atomic_write(new,b'new forward after actual native image mismatch'));row['newForwardExists']=new.exists()
    finally:_r6_phase_finish(m,tx,token,row,'late-native-owned-image-observation.json')
    assert row['injectionCount']==1 and failure is not None and str(failure)=='owned retirement native image changed',row
    assert row['nativeBefore']['id']==row['nativeMutated']['id']==row['nativeReturned']['id']
    assert row['actualNativeImage']['bodyHex']==(b'X'*len(body)).hex(),row
    assert row['ownerClosedAfterFailure']==[True] and row['pathStillPresent'],row
    assert row['negativeAfterAcquiredFailure'] and row['negativeAfterByteReturn'],row
    assert not row['defaultVerify']['returned'] and not row['newForward']['returned'] and not row['newForwardExists'] and not row['finalExit']['returned'],row
    assert row['settled'] and row['contextCleared'],row

def test_consumed_inverse_refuses_invalid_repeat_without_minting_physical_failure(tmp_path):
    m,root,source,destination,leaf,outside=_relocation_observation_fixture(tmp_path)
    tx=m.LifecycleTransaction(root);tx.__enter__();token=m._CURRENT_LIFECYCLE_TRANSACTION.set(tx);row={'actualModule':m.__file__}
    try:
        original=outside.read_bytes();m._atomic_write(outside,b'actual owned postimage')
        origin=tx._owned_file_origin(outside,original);inverse=tx.qualify_owned_inverse(origin,operation='restore-file');m._atomic_write(outside,original,inverse=inverse)
        assert inverse.fulfilled and inverse.current_pair_is_bound();row['actuallyFulfilled']=True;row['currentBeforeInvalidRequest']=_r6_phase_native(m,outside)
        outside.write_bytes(b'foreign drift before invalid consumed request')
        row['invalidRepeat'],failure=_r5_correction_attempt(lambda:m._atomic_write(outside,original,inverse=inverse))
        row['negativeAfterInvalidRequest']=_r6_phase_negative(tx);row['fulfilledRemains']=inverse.fulfilled
        outside.write_bytes(original);row['sameObjectReturned']=_r6_phase_native(m,outside)
        row['defaultVerify'],_=_r5_correction_attempt(tx.verify)
        new=root/'valid-forward-after-api-refusal.bin';row['newForward'],_=_r5_correction_attempt(lambda:m._atomic_write(new,b'valid forward after invalid request only'));row['newForwardExists']=new.exists()
    finally:_r6_phase_finish(m,tx,token,row,'consumed-proof-invalid-request-observation.json')
    assert failure is not None and row['fulfilledRemains'],row
    assert row['currentBeforeInvalidRequest']['id']==row['sameObjectReturned']['id']
    assert row['negativeAfterInvalidRequest']==[],row
    assert row['defaultVerify']['returned'] and row['newForward']['returned'] and row['newForwardExists'],row
    assert row['finalExit']['returned'] and row['settled'] and row['contextCleared'],row


def test_lifecycle_outcome_composer_readiness_uses_raw_cleanup_state() -> None:
    module = load_module()
    clean = module.LifecycleOutcomeComposer()
    assert clean.has_cleanup_failures() is False

    single_slot = module.LifecycleOutcomeComposer()
    phase = next(
        phase for phase in module.LIFECYCLE_CLEANUP_PHASES
        if phase not in module.LIFECYCLE_REPEATABLE_CLEANUP_PHASES
    )
    single_slot.record_cleanup(
        phase=phase, failure_id="TEST-CLEANUP", resource="intent",
        diagnostic="recorded cleanup failure",
    )
    assert single_slot.has_cleanup_failures() is True

    occurrences = module.LifecycleOutcomeComposer()
    occurrences.record_write_cleanup(
        phase="write-target-release", failure_id="TEST-CLEANUP",
        resource="intent", diagnostic="recorded release failure",
        cause=OSError("owned image release fault"),
    )
    assert occurrences.has_cleanup_failures() is True


def test_successor_retirement_binding_rejects_missing_mismatched_and_unheld_composer(tmp_path: Path) -> None:
    module = load_module()
    with pytest.raises(module.LifecycleError, match="current lifecycle outcome composer") as missing:
        module._recover_successor_import.__wrapped__(
            tmp_path, tmp_path / "missing-intent.json", {"operationId": "front-missing-composer"},
        )
    assert missing.value.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"

    target_path = tmp_path / "uncreated-intent.json"
    target = module.LifecycleWriteTarget(target_path, failure_id="TEST-RETIREMENT")
    with pytest.raises(module.LifecycleError, match="outcome composer differs"):
        target.remove_owned(target_path.name, {}, outcome_composer=object())

    current = module.LifecycleOutcomeComposer()
    other = module.LifecycleOutcomeComposer()
    token = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.set(current)
    try:
        with pytest.raises(module.LifecycleError, match="outcome composer differs"):
            target.remove_owned(target_path.name, {}, outcome_composer=other)
        with pytest.raises(module.LifecycleError, match="current held lifecycle owner"):
            target.remove_owned(target_path.name, {}, outcome_composer=current)
    finally:
        module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.reset(token)
    assert not target_path.exists()


def test_unbound_native_owned_removal_preserves_none_result(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "ordinary-intent.json"
    payload = b"ordinary unbound removal\n"
    path.write_bytes(payload)
    with module.LifecycleWriteTarget(path, failure_id="TEST-ORDINARY-REMOVAL") as owner:
        image = owner.owned_image(path.name, maximum_bytes=len(payload))
        result = owner.remove_owned(path.name, image)
    assert result is None
    assert not path.exists()


def test_clean_successor_terminal_removal_returns_true(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    operation = "front-clean-readiness"
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"], fixture["dispositions"], operation,
    )
    with pytest.raises(module.LifecycleError):
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation, plan["digest"],
            inject_failure_at="after-receipt-publish",
        )
    intent_path = module._transition_intent_path(root, operation)
    assert intent_path.is_file()
    retired = []
    original_remove = module.LifecycleWriteTarget.remove_owned

    def capture_removal(owner, leaf, image, *, outcome_composer=None):
        if outcome_composer is None:
            result = original_remove(owner, leaf, image)
        else:
            result = original_remove(owner, leaf, image, outcome_composer=outcome_composer)
        if owner.path == intent_path:
            retired.append((outcome_composer, result))
        return result

    monkeypatch.setattr(module.LifecycleWriteTarget, "remove_owned", capture_removal)
    module.recover_transition(root, operation)
    assert len(retired) == 1 and type(retired[0][0]) is module.LifecycleOutcomeComposer
    assert retired[0][1] is True
    assert not intent_path.exists()


def test_successor_terminal_removal_defers_after_owned_image_release_failure(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    operation = "front-image-release-readiness"
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"], fixture["dispositions"], operation,
    )
    with pytest.raises(module.LifecycleError):
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation, plan["digest"],
            inject_failure_at="after-receipt-publish",
        )
    intent_path = module._transition_intent_path(root, operation)
    intent_before = intent_path.read_bytes()
    work_items_before = tree_file_bytes(root / "work-items")
    stage_root = root / ".scratch" / "work-items-lifecycle-successor-imports" / operation
    injected = []
    retired = []
    intent_effects = []
    native_owners = []
    original_close = module.LifecycleWriteTarget._close
    original_remove = module.LifecycleWriteTarget.remove_owned
    original_publish = module.LifecycleWriteTarget._publish_effect

    def close_then_report(owner, handle):
        original_close(owner, handle)
        if owner.path == intent_path and not injected:
            injected.append(handle)
            raise OSError("owned intent image released with a reported failure")

    def capture_removal(owner, leaf, image, *, outcome_composer=None):
        result = original_remove(owner, leaf, image, outcome_composer=outcome_composer)
        if owner.path == intent_path:
            native_owners.append(owner)
            retired.append((outcome_composer, result))
        return result

    def capture_publication(owner, prepared, identity):
        if (prepared is not None and prepared.source == intent_path and prepared.destination is None):
            intent_effects.append(prepared)
        return original_publish(owner, prepared, identity)

    with monkeypatch.context() as scoped:
        scoped.setattr(module.LifecycleWriteTarget, "_close", close_then_report)
        scoped.setattr(module.LifecycleWriteTarget, "remove_owned", capture_removal)
        scoped.setattr(module.LifecycleWriteTarget, "_publish_effect", capture_publication)
        with pytest.raises(module.LifecycleError) as failed:
            module.recover_transition(root, operation)

    assert injected and len(injected) == 1
    assert failed.value.failure_id == "WI-LIFECYCLE-WRITE-BOUNDARY"
    assert "occurrences=1" in str(failed.value)
    assert "owned intent image released with a reported failure" in str(failed.value)
    assert len(retired) == 1 and type(retired[0][0]) is module.LifecycleOutcomeComposer
    assert retired[0][1] is False
    assert intent_effects == []
    assert intent_path.read_bytes() == intent_before
    assert tree_file_bytes(root / "work-items") == work_items_before
    assert not stage_root.exists()
    assert len(native_owners) == 1 and not native_owners[0]._open
    assert native_owners[0]._directories == [] and native_owners[0]._parent is None
