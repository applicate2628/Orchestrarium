"""Real local path checks; hook checks are not atomic native tool containment."""
from pathlib import Path
import os
import pytest
import test_sdk_claude as base
from sdk_execution import runtime
from sdk_execution.claude import authorize_claude_workspace_tool as authorize


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    (tmp_path / "runtime").mkdir()
    monkeypatch.setattr(runtime, "_worker_authority_roots", lambda provider="claude": (tmp_path / "authority",))
    req = base.request(role="backend-engineer", result_kind="task", cwd=str(root), write_workspace=str(root))
    selection = base.claude_selection(tmp_path, executable=str(tmp_path / "runtime" / "claude.exe"))
    pin = runtime.validate_worker_custody(req, selection)
    def call(name, args, **kwargs):
        return authorize(req, selection, name, args, expected_identity=pin, **kwargs)
    return root, call


def test_files_and_new_parent_write(case):
    root, call = case
    file = root / "file.py"
    file.write_text("old")
    call("Read", {"file_path": str(file), "offset": 1, "limit": 3})
    call("Edit", {"file_path": str(file), "old_string": "old", "new_string": "new", "replace_all": False})
    call("Write", {"file_path": str(root / "new" / "nested" / "file.py"), "content": "new"})
    assert not (root / "new").exists()


@pytest.mark.parametrize("control", [".git", ".agents", ".codex", ".claude"])
def test_project_control_readable_not_writable(case, control):
    root, call = case
    folder = root / control
    folder.mkdir()
    file = folder / "context"
    file.write_text("context")
    call("Read", {"file_path": str(file)})
    call("Glob", {"pattern": "**/*"})
    call("Grep", {"pattern": "context", "path": str(root), "-i": True})
    with pytest.raises(ValueError, match="protected"):
        call("Write", {"file_path": str(file), "content": "new"})


def test_confidential_paths_denied_for_all_reads(case):
    root, call = case
    file = root / "credential-context"
    file.write_text("fixture")
    for name, args in [("Read", {"file_path": str(file)}), ("Glob", {"pattern": "**/*"}), ("Grep", {"pattern": "x"})]:
        with pytest.raises(ValueError, match="protected"):
            call(name, args, protected_paths=(file,))


def test_hardlink_write_denied_but_read_admitted(case, tmp_path):
    root, call = case
    source = tmp_path / "original"
    source.write_text("x")
    alias = root / "alias"
    os.link(source, alias)
    call("Read", {"file_path": str(alias)})
    with pytest.raises(ValueError, match="alias"):
        call("Write", {"file_path": str(alias), "content": "new"})


@pytest.mark.parametrize("suffix", ["../escape", "file:stream", "NUL", "trailing.", "trailing ", "CONIN$", "CONOUT$", "COM\u00b9", "LPT\u00b2", "file*name"])
def test_unsafe_windows_paths(case, suffix):
    if os.name != "nt" and suffix != "../escape":
        pytest.skip("Windows alias semantics")
    root, call = case
    with pytest.raises(ValueError):
        call("Write", {"file_path": str(root / suffix), "content": "x"})


@pytest.mark.parametrize("args", [{"pattern": "../*"}, {"pattern": "/outside/*"}, {"pattern": "x", "path": "../outside"}])
def test_search_escape_refused(case, args):
    root, call = case
    with pytest.raises(ValueError):
        call("Glob", args)


def test_narrow_relative_search_and_typed_flags(case):
    root, call = case
    (root / "src").mkdir()
    (root / "src" / "x.py").write_text("x")
    call("Glob", {"path": "src", "pattern": "**/*.py"})
    call("Grep", {"path": "src", "pattern": "x", "glob": "*.py", "multiline": True, "head_limit": 0})
    with pytest.raises(ValueError, match="arguments"):
        call("Grep", {"pattern": "x", "command": "anything"})


def test_symlink_search_refused(case, tmp_path):
    root, call = case
    target = tmp_path / "outside"
    target.mkdir()
    try:
        (root / "link").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    with pytest.raises(ValueError):
        call("Glob", {"pattern": "**/*"})


@pytest.mark.skipif(os.name != "nt", reason="Windows junction coverage")
def test_junction_search_refused_without_symlink_privilege(case, tmp_path):
    import subprocess
    root, call = case
    target = tmp_path / "junction-target"
    target.mkdir()
    link = root / "junction"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    assert result.returncode == 0
    with pytest.raises(ValueError):
        call("Glob", {"pattern": "**/*"})


@pytest.mark.skipif(os.name != "nt", reason="Windows compatibility naming")
def test_reserved_names_supported_python_fallback(case, monkeypatch):
    import sdk_execution.runtime as adapter
    native_reserved = adapter.ntpath.isreserved
    class LegacyWindowsPath(adapter.PureWindowsPath):
        def is_reserved(self):
            return native_reserved(str(self))
    monkeypatch.setattr(adapter, "PureWindowsPath", LegacyWindowsPath)
    monkeypatch.delattr(adapter.ntpath, "isreserved", raising=False)
    root, call = case
    for name in ("CONIN$", "CONOUT$", "COM\u00b9", "LPT\u00b2", "wild*name"):
        with pytest.raises(ValueError):
            call("Write", {"file_path": str(root / name), "content": "x"})


@pytest.mark.parametrize("pattern", ["~/**", "~user/**", "{../outside,src}/**", ".{.,src}/**", "{/outside,src}/**", "@(../outside)"])
def test_path_producing_glob_expansion_refused(case, pattern):
    _, call = case
    with pytest.raises(ValueError):
        call("Glob", {"pattern": pattern})


def test_safe_extension_brace_search(case):
    root, call = case
    (root / "x.py").write_text("x")
    call("Glob", {"pattern": "**/*.{py,js}"})


@pytest.mark.parametrize("raw", ["~", "~/nested", "~user"])
def test_native_home_expansion_alias_refused(case, raw):
    root, call = case
    (root / "~" / "nested").mkdir(parents=True)
    (root / "~user").mkdir()
    for name in ("Glob", "Grep"):
        with pytest.raises(ValueError, match="file_tool_path_alias"):
            call(name, {"pattern": "*", "path": raw})
    # A canonical absolute path names the literal directory without expansion.
    call("Glob", {"pattern": "*", "path": str(root / "~")})
