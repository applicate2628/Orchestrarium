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
    matches = [node.args[2] for node in ast.walk(tree)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "_InstallFailure" and len(node.args) >= 3
               and isinstance(node.args[1], ast.Constant) and node.args[1].value == context]
    assert len(matches) == 1
    class Primary(RuntimeError):
        def __bool__(self):
            if kind == "raises":
                raise AssertionError("primary truthiness evaluated")
            return kind == "ordinary"
    primary = None if kind == "absent" else Primary("body")
    cleanup = OSError("cleanup")
    expression = ast.Expression(matches[0])
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
