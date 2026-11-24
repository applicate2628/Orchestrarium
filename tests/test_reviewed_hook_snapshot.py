"""Explicit selected snapshot is not a package receipt or a trust grant."""
import hashlib
import json
import shutil
import sys
import subprocess
from pathlib import Path
import pytest
from test_hook_file_localization import PI, ROOT


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fixture(tmp_path):
    local = tmp_path / "local"
    local.mkdir()
    shared = tmp_path / "shared"
    shared.mkdir()
    script = shared / "hook with spaces.py"
    script.write_text("# synthetic hook, never run\n")
    exe = tmp_path / "runtime" / Path(sys.executable).name
    exe.parent.mkdir()
    shutil.copy2(sys.executable, exe)
    health = PI._hook_health_module(ROOT)
    render = health.serialize_windows_hook_command if PI.os.name == "nt" else lambda a: " ".join(health.shlex.quote(x) for x in a)
    oldexe = (tmp_path / "missing" / Path(sys.executable).name).as_posix()
    before = render([oldexe, "-B", script.as_posix(), "argument"])
    after = render([exe.as_posix(), "-B", script.as_posix(), "argument"])
    doc = {"hooks": {"Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": before, "timeout": 3}]}]}, "foreign": ["unchanged"]}
    raw = (json.dumps(doc, indent=3) + "\n").encode()
    candidate = raw.replace(json.dumps(before).encode(), json.dumps(after).encode())
    source = shared / "hooks.json"
    source.write_bytes(raw)
    link = local / "hooks.json"
    link.symlink_to(source)
    cand = tmp_path / "candidate.json"
    cand.write_bytes(candidate)
    spec = dict(schema_version=1, registration=str(link), before_sha256=digest(raw),
        candidate=str(cand), candidate_sha256=digest(candidate),
        executable=dict(path=str(exe), sha256=digest(exe.read_bytes())),
        commands=[dict(marker="hook with spaces", event="Stop", group_index=0, handler_index=0, before=before, after=after,
                       script=str(script), script_sha256=digest(script.read_bytes()))])
    selection = tmp_path / "selection.json"
    save(selection, spec)
    return selection, spec, link, source, raw, candidate


def save(path, spec):
    path.write_text(json.dumps(spec), encoding="utf-8")
    return digest(path.read_bytes())


def invoke(selection, apply=False):
    return PI.install("codex", ["--reviewed-hook-snapshot", str(selection),
        "--reviewed-hook-snapshot-sha256", digest(selection.read_bytes()), *(["--apply"] if apply else [])])


def test_public_preview_and_apply_without_receipt(tmp_path):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    inode = link.lstat().st_ino
    inventory = link.parent / PI.CODEX_HOOK_INVENTORY
    inventory.write_bytes(b"prior local inventory")
    assert invoke(selection) == 0
    assert link.is_symlink() and source.read_bytes() == raw
    assert invoke(selection, True) == 0
    assert not link.is_symlink() and link.read_bytes() == candidate
    backup = link.with_name(link.name + ".orche-localization-link")
    assert backup.is_symlink() and backup.lstat().st_ino == inode
    assert source.read_bytes() == raw and inventory.is_file()
    generated = json.loads(inventory.read_bytes())
    assert generated["schemaVersion"] == 1 and len(generated["hooks"]) == 1
    assert generated["hooks"][0]["stem"] == "hook with spaces"
    assert generated["sourcePath"] == PI._hook_health_module(ROOT)._source_identity(link, "windows" if PI.os.name == "nt" else "posix")
    assert inventory.with_name(inventory.name + ".orche-localization-prior").read_bytes() == b"prior local inventory"
    assert not list(tmp_path.rglob(".orche-install.v1.json"))
    assert invoke(selection, True) == 1  # replay cannot replace current ordinary leaf


@pytest.mark.parametrize("bad", ["before", "candidate", "executable", "script", "tail", "metadata", "foreign_bytes", "duplicate"])
def test_bad_selection_no_effect(tmp_path, bad):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    if bad in {"before", "candidate"}:
        spec[bad + "_sha256"] = "0" * 64
    elif bad in {"executable", "script"}:
        path = Path(spec["executable"]["path"] if bad == "executable" else spec["commands"][0]["script"])
        path.write_bytes(b"different")
    elif bad == "duplicate":
        spec["commands"] *= 2
    else:
        doc = json.loads(candidate)
        if bad == "tail":
            spec["commands"][0]["after"] += " changed"
            doc["hooks"]["Stop"][0]["hooks"][0]["command"] = spec["commands"][0]["after"]
        elif bad == "metadata":
            doc["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 99
        data = (json.dumps(doc) + "\n").encode()
        Path(spec["candidate"]).write_bytes(data)
        spec["candidate_sha256"] = digest(data)
    save(selection, spec)
    assert invoke(selection, True) == 1
    assert link.is_symlink() and source.read_bytes() == raw


def test_wrong_selection_hash_refused(tmp_path):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    assert PI.install("codex", ["--reviewed-hook-snapshot", str(selection), "--reviewed-hook-snapshot-sha256", "0"*64, "--apply"]) == 1
    assert link.is_symlink()


@pytest.mark.parametrize("dep", ["source", "executable", "script"])
def test_same_byte_node_drift_between_plan_and_transaction(tmp_path, monkeypatch, dep):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    path = source if dep == "source" else Path(spec["executable"]["path"] if dep == "executable" else spec["commands"][0]["script"])
    real = PI._plan_reviewed_hook_snapshot
    def drift(*args, **kwargs):
        plan = real(*args, **kwargs)
        other = path.with_name(path.name + ".replacement")
        shutil.copy2(path, other)
        other.replace(path)
        return plan
    monkeypatch.setattr(PI, "_plan_reviewed_hook_snapshot", drift)
    assert invoke(selection, True) == 1
    assert link.is_symlink() and source.read_bytes() == raw


def test_sidecar_failure_restores_original_link(tmp_path, monkeypatch):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    inventory = link.parent / PI.CODEX_HOOK_INVENTORY
    inventory.write_bytes(b"prior local inventory")
    inode = link.lstat().st_ino
    real = PI._CreateOnlyMutablePath.retain_path
    def fail(*args, **kwargs):
        real(*args, **kwargs)
        raise RuntimeError("injected sidecar failure")
    monkeypatch.setattr(PI._CreateOnlyMutablePath, "retain_path", fail)
    assert invoke(selection, True) == 1
    assert link.is_symlink() and link.lstat().st_ino == inode
    assert source.read_bytes() == raw and inventory.read_bytes() == b"prior local inventory"


@pytest.mark.parametrize("field", ["before_sha256", "candidate_sha256", "executable", "script"])
def test_null_hash_never_disables_admission(tmp_path, field):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    if field == "executable":
        spec["executable"]["sha256"] = None
    elif field == "script":
        spec["commands"][0]["script_sha256"] = None
    else:
        spec[field] = None
    save(selection, spec)
    assert invoke(selection, True) == 1
    assert link.is_symlink() and source.read_bytes() == raw


@pytest.mark.parametrize("bad", ["missing_executable", "backup_collision", "linked_parent", "link_swap", "candidate_drift"])
def test_boundary_refusal_preserves_existing_state(tmp_path, monkeypatch, bad):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    if bad == "missing_executable":
        Path(spec["executable"]["path"]).unlink()
    elif bad == "backup_collision":
        link.with_name(link.name + ".orche-localization-link").write_bytes(b"unrelated")
    elif bad == "linked_parent":
        alias = tmp_path / "alias"
        alias.symlink_to(link.parent, target_is_directory=True)
        spec["registration"] = str(alias / link.name)
        save(selection, spec)
    else:
        real = PI._plan_reviewed_hook_snapshot
        def drift(*args, **kwargs):
            plan = real(*args, **kwargs)
            if bad == "candidate_drift":
                Path(spec["candidate"]).write_bytes(b"later candidate")
            else:
                replacement = link.with_name("replacement")
                replacement.symlink_to(source)
                replacement.replace(link)
            return plan
        monkeypatch.setattr(PI, "_plan_reviewed_hook_snapshot", drift)
    assert invoke(selection, True) == 1
    assert link.is_symlink() and source.read_bytes() == raw


def test_mode_is_explicit_and_not_combined_with_install(tmp_path):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    assert PI.install("codex", ["--reviewed-hook-snapshot", str(selection), "--apply"]) == 2
    assert PI.install("codex", ["--reviewed-hook-snapshot", str(selection),
        "--reviewed-hook-snapshot-sha256", digest(selection.read_bytes()), "--localize-hook-file", "--apply"]) == 2
    assert link.is_symlink() and source.read_bytes() == raw


@pytest.mark.parametrize("after_write", [False, True])
def test_inventory_failure_rolls_back_both_local_files(tmp_path, monkeypatch, after_write):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    local_inventory = link.parent / PI.CODEX_HOOK_INVENTORY
    local_inventory.write_bytes(b"old local inventory")
    shared_inventory = source.parent / PI.CODEX_HOOK_INVENTORY
    shared_inventory.write_bytes(b"unrelated shared inventory")
    inode = link.lstat().st_ino
    if after_write:
        real = PI._CreateOnlyMutablePath.replace_file_atomic
        def fail(owner, relative, *args, **kwargs):
            result = real(owner, relative, *args, **kwargs)
            if owner.anchor / relative == local_inventory:
                raise RuntimeError("injected after inventory write")
            return result
        monkeypatch.setattr(PI._CreateOnlyMutablePath, "replace_file_atomic", fail)
    else:
        real = PI._hook_health_module
        def health(root):
            module = real(root)
            def fail(**kwargs):
                raise RuntimeError("injected inventory producer failure")
            module.plan_codex_inventory = fail
            return module
        monkeypatch.setattr(PI, "_hook_health_module", health)
    assert invoke(selection, True) == 1
    assert link.is_symlink() and link.lstat().st_ino == inode
    assert source.read_bytes() == raw
    assert local_inventory.read_bytes() == b"old local inventory"
    assert shared_inventory.read_bytes() == b"unrelated shared inventory"


def test_actual_public_entrypoint_no_provider_calls(tmp_path):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/install-client.py"),
        "--client", "codex", "--reviewed-hook-snapshot", str(selection),
        "--reviewed-hook-snapshot-sha256", digest(selection.read_bytes()), "--apply"],
        cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "snapshot-applied" and report["inventory_status"] == "generated"
    assert not report["package_adopted"] and not report["trust_granted"]
    assert link.read_bytes() == candidate and source.read_bytes() == raw
    assert (link.parent / PI.CODEX_HOOK_INVENTORY).is_file()



def cloud_boundary(monkeypatch, paths, *, tag=0x9000601A):
    """Synthetic cloud tags only; actual Windows handles and file reads remain real."""
    real_contains = PI._contains_reparse
    real_tag = PI._WindowsBoundNode.attribute_tag
    selected = set(paths)
    monkeypatch.setattr(PI, "_contains_reparse", lambda p: Path(p) in selected or real_contains(p))
    def attributes(node):
        flags, actual = real_tag(node)
        return (flags | PI.stat.FILE_ATTRIBUTE_REPARSE_POINT, tag) if node.path in selected else (flags, actual)
    monkeypatch.setattr(PI._WindowsBoundNode, "attribute_tag", attributes)
    # No real cloud placeholders in this fixture: only the native cloud metadata
    # API is synthetic; content and identity still use real held Windows handles.
    monkeypatch.setattr(PI._WindowsBoundNode, "require_local_cloud_data", lambda node: None)


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows native handle boundary")
def test_cloud_tagged_readonly_inputs_use_held_native_identity(tmp_path, monkeypatch):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    script = Path(spec["commands"][0]["script"])
    cloud_boundary(monkeypatch, [script, source])
    assert invoke(selection, True) == 0
    assert link.read_bytes() == candidate and source.read_bytes() == raw
    assert digest(script.read_bytes()) == spec["commands"][0]["script_sha256"]


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows native handle boundary")
@pytest.mark.parametrize("tag", [0xA000000C, 0xA0000003, 0x9000001B])
def test_cloud_boundary_rejects_redirect_or_unknown_tags(tmp_path, monkeypatch, tag):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    cloud_boundary(monkeypatch, [Path(spec["commands"][0]["script"])], tag=tag)
    assert invoke(selection, True) == 1
    assert link.is_symlink() and source.read_bytes() == raw


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows native handle boundary")
def test_cloud_samebytes_replacement_after_plan_refused(tmp_path, monkeypatch):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    script = Path(spec["commands"][0]["script"])
    cloud_boundary(monkeypatch, [script])
    real = PI._plan_reviewed_hook_snapshot
    def drift(*args, **kwargs):
        plan = real(*args, **kwargs)
        replacement = script.with_name("replacement.py")
        replacement.write_bytes(script.read_bytes())
        replacement.replace(script)
        return plan
    monkeypatch.setattr(PI, "_plan_reviewed_hook_snapshot", drift)
    assert invoke(selection, True) == 1
    assert link.is_symlink() and source.read_bytes() == raw



@pytest.mark.skipif(PI.os.name != "nt", reason="Windows native handle boundary")
@pytest.mark.parametrize("recall", [0x1000, 0x400000])
def test_cloud_recall_metadata_refused_before_data_handle(tmp_path, monkeypatch, recall):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    script = Path(spec["commands"][0]["script"])
    cloud_boundary(monkeypatch, [script])
    real_tag = PI._WindowsBoundNode.attribute_tag
    real_enter = PI._WindowsBoundNode.__enter__
    data_opens = []
    def attributes(node):
        flags, tag = real_tag(node)
        return (flags | recall, tag) if node.path == script else (flags, tag)
    def enter(node):
        if node.path == script and node.purpose == "readonly":
            data_opens.append(node.path)
        return real_enter(node)
    monkeypatch.setattr(PI._WindowsBoundNode, "attribute_tag", attributes)
    monkeypatch.setattr(PI._WindowsBoundNode, "__enter__", enter)
    assert invoke(selection, True) == 1
    assert data_opens == [] and link.is_symlink() and source.read_bytes() == raw



@pytest.mark.parametrize("ranges,ok", [
    ([(0, 0, 10, 16)], True),
    ([(0x800700EA, 0, 4, 16), (0, 4, 6, 16)], True),
    ([(0, 1, 9, 16)], False),
    ([(0, 0, 0, 16)], False),
    ([(0, 0, 10, 0)], False),
    ([(0x80070001, 0, 10, 16)], False),
])
def test_physical_cloud_range_coverage(ranges, ok):
    from types import SimpleNamespace
    node = PI._WindowsBoundNode(Path("synthetic"))
    node.python_metadata = lambda: SimpleNamespace(st_size=10)
    entries = iter(ranges)
    node._cloud_range = lambda offset, length: next(entries)
    if ok:
        node.require_local_cloud_data()
    else:
        with pytest.raises(ValueError, match="E_HOOK_SNAPSHOT_"):
            node.require_local_cloud_data()


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows native handle boundary")
def test_missing_local_range_never_opens_data(tmp_path, monkeypatch):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    script = Path(spec["commands"][0]["script"])
    cloud_boundary(monkeypatch, [script])
    real_enter = PI._WindowsBoundNode.__enter__
    data_opens = []
    def enter(node):
        if node.path == script and node.purpose == "readonly":
            data_opens.append(node.path)
        return real_enter(node)
    def missing(node):
        raise ValueError("E_HOOK_SNAPSHOT_RECALL_REQUIRED: synthetic missing range")
    monkeypatch.setattr(PI._WindowsBoundNode, "__enter__", enter)
    monkeypatch.setattr(PI._WindowsBoundNode, "require_local_cloud_data", missing)
    assert invoke(selection, True) == 1
    assert data_opens == [] and link.is_symlink() and source.read_bytes() == raw



def fake_visibility(monkeypatch, *, initial=1, set_error=False, restore_error=False):
    import ctypes
    from types import SimpleNamespace
    state = dict(mode=initial, calls=[])
    class Call:
        def __init__(self, callback): self.callback = callback
        def __call__(self, *args): return self.callback(*args)
    def setter(mode):
        state["calls"].append(mode)
        if set_error and len(state["calls"]) == 1 or restore_error and len(state["calls"]) > 1:
            return -1
        old,state["mode"] = state["mode"],mode
        return old
    api = SimpleNamespace(RtlQueryThreadPlaceholderCompatibilityMode=Call(lambda: state["mode"]),
        RtlSetThreadPlaceholderCompatibilityMode=Call(setter))
    real = ctypes.WinDLL
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, *a, **kw: api if name == "ntdll" else real(name,*a,**kw))
    return state


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows placeholder visibility")
@pytest.mark.parametrize("raises", [False, True])
def test_thread_visibility_nested_restore_success_and_error(monkeypatch, raises):
    state = fake_visibility(monkeypatch)
    try:
        with PI._exposed_hook_snapshot_placeholders():
            assert state["mode"] == 2
            with PI._exposed_hook_snapshot_placeholders():
                assert state["mode"] == 2
                if raises: raise ValueError("synthetic body failure")
    except ValueError:
        assert raises
    assert state["mode"] == 1 and state["calls"] == [2,2,2,1]


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows placeholder visibility")
def test_thread_visibility_negative_api_stops_before_body(monkeypatch):
    state = fake_visibility(monkeypatch,set_error=True)
    with pytest.raises(ValueError,match="VISIBILITY_UNAVAILABLE"):
        with PI._exposed_hook_snapshot_placeholders():
            pytest.fail("body must not run")
    assert state["mode"] == 1 and state["calls"] == [2]


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows placeholder visibility")
def test_thread_visibility_restore_failure_not_success(monkeypatch):
    fake_visibility(monkeypatch,restore_error=True)
    with pytest.raises(RuntimeError,match="RESTORE_FAILED"):
        with PI._exposed_hook_snapshot_placeholders():
            pass


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows placeholder visibility")
def test_snapshot_visibility_precedes_reader_routing(tmp_path,monkeypatch):
    selection, spec, link, source, raw, candidate = fixture(tmp_path)
    state = fake_visibility(monkeypatch)
    original = PI._contains_reparse
    observations = []
    def inspect(path):
        observations.append(state["mode"])
        assert state["mode"] == 2
        return original(path)
    monkeypatch.setattr(PI,"_contains_reparse",inspect)
    assert invoke(selection) == 0
    assert observations and state["mode"] == 1


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows placeholder visibility")
def test_direct_cloud_helper_exposes_before_acquisition(tmp_path,monkeypatch):
    path=tmp_path/"ordinary.txt"
    path.write_bytes(b"synthetic")
    state = fake_visibility(monkeypatch)
    original = PI._WindowsBoundNode.__enter__
    def enter(node):
        assert state["mode"] == 2
        return original(node)
    monkeypatch.setattr(PI._WindowsBoundNode,"__enter__",enter)
    with PI._held_reviewed_cloud_input(path,digest(b"synthetic")) as (data,witnesses,check):
        assert data == b"synthetic" and check() == data
    assert state["mode"] == 1


@pytest.mark.skipif(PI.os.name != "nt", reason="Windows placeholder visibility")
def test_native_thread_visibility_restores_original():
    import ctypes
    query=ctypes.WinDLL("ntdll").RtlQueryThreadPlaceholderCompatibilityMode
    query.argtypes=()
    query.restype=ctypes.c_byte
    before=int(query())
    with PI._exposed_hook_snapshot_placeholders():
        assert int(query()) == 2
    assert int(query()) == before



@pytest.mark.skipif(PI.os.name != "nt", reason="Windows placeholder visibility")
def test_thread_visibility_missing_api_stops_before_body(monkeypatch):
    import ctypes
    from types import SimpleNamespace
    real=ctypes.WinDLL
    monkeypatch.setattr(ctypes,"WinDLL",lambda name,*a,**kw: SimpleNamespace() if name=="ntdll" else real(name,*a,**kw))
    with pytest.raises(ValueError,match="VISIBILITY_UNAVAILABLE"):
        with PI._exposed_hook_snapshot_placeholders():
            pytest.fail("body must not run")
