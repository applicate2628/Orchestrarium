"""Initial file capture retains actionable, privacy-safe refusal context."""
from types import SimpleNamespace
from pathlib import Path
import io
import os
import stat
import pytest
from test_mutate_work_item import load_module


@pytest.mark.parametrize("fault,predicate", [
    ("limit", "capture-byte-limit-exceeded"),
    ("size", "capture-size-differs"),
    ("reread", "read-bytes-differ"),
    ("middle", "descriptor-stat-changed-after-read"),
    ("after", "descriptor-stat-changed-after-verification"),
    ("path", "path-stat-changed-during-read"),
    ("identity", "current-path-identity-differs"),
    ("symlink", "current-file-is-symlink"),
    ("links", "single-link-count-differs"),
    ("attributes", "current-file-is-reparse"),
    ("reparse", "captured-path-is-reparse"),
])
def test_initial_capture_names_first_refusal_without_content(tmp_path, monkeypatch, fault, predicate):
    module = load_module()
    path = tmp_path / "PRIVATE_PATH_SENTINEL"
    def info(**changes):
        values = dict(st_dev=1, st_ino=2, st_mode=stat.S_IFREG | 0o600,
                      st_nlink=1, st_size=4, st_mtime_ns=10, st_ctime_ns=20,
                      st_file_attributes=0)
        values.update(changes)
        return SimpleNamespace(**values)
    before, observed, middle, after, current = [info() for _ in range(5)]
    data, verified = b"DATA", b"DATA"
    if fault == "limit": data = verified = b"DATA!"
    if fault == "size": data = verified = b"DAT"
    if fault == "reread": verified = b"ELSE"
    if fault == "middle": middle.st_mtime_ns += 1
    if fault == "after": after.st_ctime_ns += 1
    if fault == "path": current.st_mtime_ns += 1
    if fault == "identity": observed.st_ino = current.st_ino = 3
    if fault == "symlink": observed.st_mode = current.st_mode = stat.S_IFLNK
    if fault == "links": observed.st_nlink = current.st_nlink = 2
    if fault == "attributes":
        monkeypatch.setattr(module.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024, raising=False)
        current.st_file_attributes = 1024

    class Reads(io.BytesIO):
        def __init__(self):
            super().__init__()
            self.values = iter((data, verified))
        def read(self, amount=-1): return next(self.values)
        def fileno(self): return 97
    stream = Reads()
    with monkeypatch.context() as patcher:
        patcher.setattr(module, "_capture_file_identity_prefix",
                            lambda *a, **k: (module.CapturedPathParentChain(()), observed, 97, before))
        patcher.setattr(module.os, "fdopen", lambda *a, **k: stream)
        samples = iter((middle, after))
        patcher.setattr(module.os, "fstat", lambda _fd: next(samples))
        patcher.setattr(module.Path, "lstat", lambda _path: current)
        patcher.setattr(module, "_lifecycle_path_has_reparse", lambda _path: fault == "reparse")
        with pytest.raises(module.LifecycleError) as refused:
            module._capture_file_snapshot(path, failure_id="WI-VALIDATOR-LOAD",
                                          maximum_bytes=4, require_single_link=True)
    assert stream.closed
    error = refused.value
    assert error.failure_id == "WI-VALIDATOR-LOAD"
    assert error.args == ("file snapshot changed during capture",)
    assert error.detail is not None
    detail = module._lifecycle_diagnostic_payload(error.detail)
    assert detail["predicate"] == predicate
    assert detail["stage"] == "snapshot-verify"
    assert detail["descriptorBeforeStat"] == ["1", "2", str(stat.S_IFREG | 0o600), "1", "4", "10", "20"]
    assert detail["firstReadBytes"] == len(data)
    assert detail["verifiedReadBytes"] == len(verified)
    assert "PRIVATE_PATH_SENTINEL" not in str(error)
    assert "DATA" not in str(error) and "ELSE" not in str(error)


def test_runtime_capture_failure_retains_controlled_source_slot(monkeypatch):
    module = load_module()
    failure = module.LifecycleError("WI-VALIDATOR-LOAD", "file snapshot changed during capture",
        detail=module.LifecycleDiagnosticDetail("file-snapshot", (("predicate", "read-bytes-differ"),)))
    monkeypatch.setattr(module, "_declared_runtime_source_authority", lambda: None)
    def refuse(*args, **kwargs): raise failure
    monkeypatch.setattr(module, "_capture_file_snapshot", refuse)
    with pytest.raises(module.LifecycleError) as caught:
        module._capture_runtime_source(Path("scripts/validate-work-item-state.py"),
                                       failure_id="WI-VALIDATOR-LOAD")
    assert caught.value is failure
    detail = module._lifecycle_diagnostic_payload(failure.detail)
    assert detail["kind"] == "runtime-source"
    assert detail["source"] == "scripts/validate-work-item-state.py"
    assert detail["stage"] == "file-capture"
    assert detail["entries"][0]["predicate"] == "read-bytes-differ"


def test_initial_capture_real_descriptor_is_closed_on_stat_refusal(tmp_path, monkeypatch):
    module = load_module()
    target = tmp_path / "private-native-source.bin"
    target.write_bytes(b"native source remains unchanged")
    actual_fstat = os.fstat
    descriptors = []
    calls = 0
    def changed_middle(fd):
        nonlocal calls
        calls += 1
        descriptors.append(fd)
        value = actual_fstat(fd)
        if calls == 2:
            fields = {name: getattr(value, name) for name in
                      ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
                       "st_mtime_ns", "st_ctime_ns")}
            fields["st_mtime_ns"] += 1
            return SimpleNamespace(**fields)
        return value
    with monkeypatch.context() as patcher:
        patcher.setattr(module.os, "fstat", changed_middle)
        with pytest.raises(module.LifecycleError) as refused:
            module._capture_file_snapshot(target, failure_id="WI-VALIDATOR-LOAD")
    detail = module._lifecycle_diagnostic_payload(refused.value.detail)
    assert detail["predicate"] == "descriptor-stat-changed-after-read"
    assert int(detail["descriptorMiddleStat"][5]) == int(detail["descriptorBeforeStat"][5]) + 1
    assert len(set(descriptors)) == 1
    with pytest.raises(OSError):
        actual_fstat(descriptors[0])
    assert target.read_bytes() == b"native source remains unchanged"


def test_cli_keeps_runtime_snapshot_detail(tmp_path, monkeypatch, capsys):
    module = load_module()
    detail = module.LifecycleDiagnosticDetail(
        "runtime-source", (("source", "shared/schemas/agent-runs.schema.json"),
                           ("stage", "file-capture")),
        (module.LifecycleDiagnosticDetail("file-snapshot",
            (("predicate", "read-bytes-differ"),)),))
    failure = module.LifecycleError("WI-VALIDATOR-LOAD", "file snapshot changed during capture",
                                    detail=detail)
    def refuse(*args, **kwargs): raise failure
    monkeypatch.setattr(module, "audit", refuse)
    assert module.main(["audit", "--root", str(tmp_path)]) == 1
    output = capsys.readouterr()
    assert "WI-VALIDATOR-LOAD" in output.out
    assert "shared/schemas/agent-runs.schema.json" in output.out
    assert "read-bytes-differ" in output.out
    assert not output.err
