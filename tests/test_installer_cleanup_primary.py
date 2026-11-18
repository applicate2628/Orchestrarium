"""Cleanup cause selection is diagnostic qualification, not backend admission."""
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_provider_prompt_projections import _load_installer


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"
CONTEXTS = ("copy-close", "scalar-parent-close", "descriptor-read-reset",
            "scalar-close", "file-close", "construction", "prepared")


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("kind", ["absent", "ordinary", "false", "raises"])
def test_cleanup_cause_expression_preserves_primary(context, kind):
    # Evaluate the production expression itself without impersonating native effects.
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    owner = next((node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef)
                  and node.name == "_copy_close_failure"), None) if context == "copy-close" else None
    matches = [node.args[2] for node in ast.walk(owner if owner is not None else tree)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "_InstallFailure" and len(node.args) >= 3
               and (owner is not None or
                    isinstance(node.args[1], ast.Constant) and node.args[1].value == context)]
    assert matches
    class Primary(RuntimeError):
        def __bool__(self):
            if kind == "raises":
                raise AssertionError("primary truthiness evaluated")
            return kind == "ordinary"
    primary = None if kind == "absent" else Primary("body")
    cleanup = OSError("cleanup")
    for cause in matches:
        expression = ast.Expression(cause)
        actual = eval(compile(expression, str(SOURCE), "eval"), {}, {
            "primary": primary, "original": primary, "cleanup": cleanup,
            "reset": cleanup, "failures": [SimpleNamespace(cause=cleanup)]})
        assert actual is (cleanup if primary is None else primary)


@pytest.mark.parametrize("kind", ["absent", "ordinary", "false", "raises"])
def test_payload_close_preserves_real_primary_and_created_bytes(tmp_path, monkeypatch, kind):
    module = _load_installer()
    transaction = module._InstallTransaction([], enabled=False)
    class Primary(RuntimeError):
        def __bool__(self):
            if kind == "raises":
                raise AssertionError("primary truthiness evaluated")
            return kind == "ordinary"
    primary = None if kind == "absent" else Primary("body")
    cleanup = OSError("close after actual release")
    recorded = {}
    def record(path, node):
        recorded[path] = node
    write = transaction._write_owned_file
    def write_then_fail(*args, **kwargs):
        result = write(*args, **kwargs)
        if primary is not None:
            raise primary
        return result
    close = module.os.close
    def close_then_fail(descriptor):
        close(descriptor)
        raise cleanup
    monkeypatch.setattr(transaction, "_write_owned_file", write_then_fail)
    with monkeypatch.context() as scoped:
        scoped.setattr(module.os, "close", close_then_fail)
        with pytest.raises(module._InstallFailure) as caught:
            transaction._prepare_payload_file(tmp_path, "prepared-", b"payload", record)
    assert caught.value.cause is (cleanup if primary is None else primary)
    assert caught.value.members[0].cause_exception is cleanup
    assert len(recorded) == 1
    path, node = next(iter(recorded.items()))
    assert caught.value.recovery_path == path
    assert path.read_bytes() == b"payload"
    assert transaction._point_matches(path, node, check_file_content=True)


@pytest.mark.parametrize("boundary", ["capture", "record", "first-write"])
def test_payload_acquisition_failure_preserves_creator_and_closes_descriptor(tmp_path, monkeypatch, boundary):
    """A failed creator witness must not authorize pathname cleanup."""
    import errno
    module = _load_installer()
    transaction = module._InstallTransaction([], enabled=False)
    primary = RuntimeError("acquisition failed")
    allocated = {}
    recorded = {}
    allocate = module.tempfile.mkstemp
    def allocate_and_remember(*args, **kwargs):
        descriptor, name = allocate(*args, **kwargs)
        allocated.update(descriptor=descriptor, path=Path(name))
        return descriptor, name
    def fail(*args, **kwargs):
        raise primary
    def record(path, node):
        if boundary == "record":
            raise primary
        recorded[path] = node
    with monkeypatch.context() as scoped:
        scoped.setattr(module.tempfile, "mkstemp", allocate_and_remember)
        if boundary == "capture":
            scoped.setattr(transaction, "_capture_node", fail)
        elif boundary == "first-write":
            scoped.setattr(module.os, "write", fail)
        with pytest.raises(module._InstallFailure if boundary == "capture" else RuntimeError) as caught:
            transaction._prepare_payload_file(tmp_path, "prepared-", b"payload", record)
    path = allocated["path"]
    assert path.read_bytes() == b""
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(OSError) as closed:
        module.os.fstat(allocated["descriptor"])
    assert closed.value.errno == errno.EBADF
    if boundary == "capture":
        assert caught.value.cause is primary
        assert caught.value.__cause__ is primary
        assert caught.value.recovery_path == path
        assert caught.value.members[0].cause == "unproved creator image preserved"
    else:
        assert caught.value is primary
    if boundary == "first-write":
        assert len(recorded) == 1
        assert transaction._point_matches(path, recorded[path], check_file_content=True)
    else:
        assert recorded == {}


@pytest.mark.parametrize("boundary", ["born", "capture", "record"])
def test_directory_acquisition_failure_preserves_created_identity(tmp_path, monkeypatch, boundary):
    """Creation without a registered witness must not authorize pathname cleanup."""
    import errno
    import os
    module = _load_installer()
    transaction = module._InstallTransaction([], enabled=False)
    target = tmp_path / "created"
    primary = RuntimeError("directory acquisition failed")
    observed = {}
    recorded = {}
    capture = transaction._capture_node
    def born(path):
        observed["identity"] = module._CreateOnlyMutablePath._identity(path)
        if boundary == "born":
            raise primary
    def capture_or_fail(path, **kwargs):
        if "descriptor" in kwargs:
            observed["descriptor"] = kwargs["descriptor"]
        if boundary == "capture":
            raise primary
        return capture(path, **kwargs)
    def record(path, node):
        if boundary == "record":
            raise primary
        recorded[path] = node
    monkeypatch.setattr(transaction, "_capture_node", capture_or_fail)
    with pytest.raises(RuntimeError) as caught:
        transaction._create_owned_directory(target, record, born=born)
    assert caught.value is primary
    assert target.is_dir() and list(target.iterdir()) == []
    assert module._CreateOnlyMutablePath._identity(target) == observed["identity"]
    assert list(tmp_path.iterdir()) == [target]
    assert recorded == {}
    if os.name == "posix" and boundary != "born":
        with pytest.raises(OSError) as closed:
            os.fstat(observed["descriptor"])
        assert closed.value.errno == errno.EBADF
