"""Native global instructions are reused without deleting authored rule content."""
from pathlib import Path

import pytest

from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def policy_case(tmp_path, monkeypatch):
    backend = load_module(ROOT / "scripts/production_installer.py", "global_policy_reuse_case")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    global_doc = home / ".codex/AGENTS.md"
    # Explicit native-path fixture, not an assumption about Windows env-home parity.
    monkeypatch.setattr(backend, "_native_codex_default_home", lambda: home / ".codex")
    backend._merge_codex_agents(ROOT, ROOT / "src.codex", global_doc, False)
    local = tmp_path / "project/AGENTS.md"
    local.parent.mkdir()
    local.write_text("# Project additions\nKeep my test command.\n", encoding="utf-8")
    shared = (ROOT / "shared/AGENTS.shared.md").read_text(encoding="utf-8").rstrip()
    assert shared in global_doc.read_text(encoding="utf-8")
    return backend, global_doc, local, shared


def render_local(case, **kwargs):
    backend, _global, local, _shared = case
    backend._merge_codex_agents(ROOT, ROOT / "src.codex", local, False, **kwargs)
    return local.read_text(encoding="utf-8")


def test_matching_global_policy_is_not_repeated_in_project(policy_case):
    backend, global_doc, local, shared = policy_case
    before = global_doc.read_bytes()
    text = render_local(policy_case)
    assert shared not in text
    assert "Keep my test command." in text
    assert backend.CODEX_BEGIN in text and backend.CODEX_END in text
    assert global_doc.read_bytes() == before


def test_missing_global_keeps_full_standalone_policy(policy_case):
    _backend, global_doc, _local, shared = policy_case
    global_doc.unlink()
    assert shared in render_local(policy_case)


def test_nonmatching_override_prevents_reuse_of_hidden_base(policy_case):
    _backend, global_doc, _local, shared = policy_case
    global_doc.with_name("AGENTS.override.md").write_text("Different global policy", encoding="utf-8")
    assert shared in render_local(policy_case)


def test_empty_override_does_not_hide_matching_global(policy_case):
    _backend, global_doc, _local, shared = policy_case
    global_doc.with_name("AGENTS.override.md").write_text(" \n", encoding="utf-8")
    assert shared not in render_local(policy_case)


def test_matching_selected_override_can_supply_global_policy(policy_case):
    _backend, global_doc, _local, shared = policy_case
    global_doc.with_name("AGENTS.override.md").write_bytes(global_doc.read_bytes())
    global_doc.write_text("Other base policy", encoding="utf-8")
    assert shared not in render_local(policy_case)


@pytest.mark.parametrize("decoration", ["fenced", "duplicated"])
def test_quoted_or_ambiguous_global_blocks_do_not_authorize_reuse(policy_case, decoration):
    _backend, global_doc, _local, shared = policy_case
    original = global_doc.read_text(encoding="utf-8")
    text = "~~~markdown\n" + original + "~~~\n" if decoration == "fenced" else original + original
    global_doc.write_text(text, encoding="utf-8")
    assert shared in render_local(policy_case)


def test_global_self_update_never_replaces_full_policy_with_dependency(policy_case):
    backend, global_doc, _local, shared = policy_case
    backend._merge_codex_agents(ROOT, ROOT / "src.codex", global_doc, False)
    assert shared in global_doc.read_text(encoding="utf-8")


def test_explicit_standalone_retains_full_rules(policy_case):
    _backend, _global, _local, shared = policy_case
    assert shared in render_local(policy_case, prefer_global=False)


def test_custom_codex_home_is_the_only_global_source(policy_case, tmp_path, monkeypatch):
    _backend, global_doc, _local, shared = policy_case
    custom = tmp_path / "custom codex home"
    custom.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(custom))
    assert shared in render_local(policy_case)
    (custom / "AGENTS.md").write_bytes(global_doc.read_bytes())
    assert shared not in render_local(policy_case)


@pytest.mark.parametrize("apply", [False, True])
def test_global_uninstall_surfaces_project_dependency_without_new_blocker(policy_case, capsys, apply):
    backend, global_doc, _local, shared = policy_case
    codec = backend._provider_ownership_module(ROOT)
    config = backend._provider_configuration_module(ROOT)
    text = global_doc.read_text(encoding="utf-8")
    digest = config.block_digest(text, "codex", backend._claude_document_context)
    receipt = codec.encode_record({}, "codex", "global", configs={
        ".codex/AGENTS.md": {"kind": "block", "blockKind": "codex", "sha256": digest}
    })
    (global_doc.parent / codec.RECEIPT_NAME).write_bytes(receipt)
    args = ["--global", "--uninstall"] + (["--apply"] if apply else [])
    assert backend.install("codex", args) == 0
    assert "global-backed project" in capsys.readouterr().out
    after = global_doc.read_text(encoding="utf-8") if global_doc.exists() else ""
    assert (shared in after) == (not apply)


def test_reapply_can_move_between_full_and_global_backed_without_losing_user_text(policy_case):
    _backend, global_doc, local, shared = policy_case
    assert shared in render_local(policy_case, prefer_global=False)
    global_bytes = global_doc.read_bytes()
    assert shared not in render_local(policy_case)
    reused = local.read_bytes()
    assert shared not in render_local(policy_case)
    assert local.read_bytes() == reused
    assert shared in render_local(policy_case, prefer_global=False)
    assert local.read_text(encoding="utf-8").count("Keep my test command.") == 1
    assert global_doc.read_bytes() == global_bytes


@pytest.mark.parametrize("content", [b"\xffinvalid UTF-8", b"Different version of policy"])
def test_unreadable_or_changed_global_keeps_full_local_policy(policy_case, content):
    _backend, global_doc, _local, shared = policy_case
    global_doc.write_bytes(content)
    assert shared in render_local(policy_case)


def test_preview_preserves_both_instruction_files(policy_case):
    backend, global_doc, local, _shared = policy_case
    before = (global_doc.read_bytes(), local.read_bytes())
    backend._merge_codex_agents(ROOT, ROOT / "src.codex", local, True)
    assert (global_doc.read_bytes(), local.read_bytes()) == before


def test_project_install_records_and_uninstalls_global_backed_block(policy_case):
    backend, global_doc, local, shared = policy_case
    before_global = global_doc.read_bytes()
    arguments = ["--target", str(local.parent), "--allow-unsafe-target", "--no-hypothesis-hook"]
    assert backend.install("codex", arguments) == 0
    text = local.read_text(encoding="utf-8")
    assert "Installation mode: global-backed." in text and shared not in text
    assert "Keep my test command." in text
    assert backend.install("codex", arguments + ["--standalone-instructions"]) == 0
    assert shared in local.read_text(encoding="utf-8")
    assert backend.install("codex", arguments) == 0
    assert shared not in local.read_text(encoding="utf-8")
    assert backend.install("codex", arguments + ["--uninstall", "--apply"]) == 0
    assert "Keep my test command." in local.read_text(encoding="utf-8")
    assert backend.CODEX_BEGIN not in local.read_text(encoding="utf-8")
    assert global_doc.read_bytes() == before_global


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_nonregular_override_is_skipped_without_blocking(policy_case, kind):
    import os
    import subprocess
    import sys
    _backend, global_doc, local, _shared = policy_case
    override = global_doc.with_name("AGENTS.override.md")
    if kind == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("POSIX named pipe fixture")
        os.mkfifo(override)
    else:
        override.mkdir()
    script = ("import sys; from pathlib import Path; "
              + f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
              + "import production_installer as backend; "
              + f"root=Path({str(ROOT)!r}); global_doc=Path({str(global_doc)!r}); "
              + f"local=Path({str(local)!r}); "
              + "print(backend._matching_native_codex_global_policy(root, local, "
                "global_doc.read_text(encoding='utf-8').rstrip('\\n')))")
    env = dict(os.environ, CODEX_HOME=str(global_doc.parent))
    result = subprocess.run([sys.executable, "-c", script], capture_output=True,
                            text=True, timeout=8, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "AGENTS.md"


def test_literal_tilde_codex_home_does_not_reuse_expanded_home_policy(policy_case, tmp_path, monkeypatch):
    _backend, _global, _local, shared = policy_case
    launcher = tmp_path / "launcher"
    literal_home = launcher / "~" / ".codex"
    literal_home.mkdir(parents=True)
    (literal_home / "AGENTS.md").write_text("Different native global policy", encoding="utf-8")
    monkeypatch.chdir(launcher)
    monkeypatch.setenv("CODEX_HOME", "~/.codex")
    assert shared in render_local(policy_case)


@pytest.mark.parametrize("control", [chr(value) for value in range(0x1c, 0x20)])
def test_native_nonempty_control_override_hides_matching_base(policy_case, control):
    _backend, global_doc, _local, shared = policy_case
    global_doc.with_name("AGENTS.override.md").write_text(control, encoding="utf-8")
    assert shared in render_local(policy_case)


@pytest.mark.parametrize("available", [True, False])
def test_environment_home_cannot_replace_unproved_native_default_home(policy_case, tmp_path, monkeypatch, available):
    backend, _global, _local, shared = policy_case
    native = tmp_path / "actual-native-profile" / ".codex"
    native.mkdir(parents=True)
    monkeypatch.setattr(backend, "_native_codex_default_home",
                        lambda: native if available else None, raising=False)
    assert shared in render_local(policy_case)


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows Known Folder API")
@pytest.mark.parametrize("status", [0, -2147467259])
def test_native_windows_home_frees_os_buffer_on_success_and_failure(tmp_path, monkeypatch, status):
    import ctypes
    from types import SimpleNamespace
    backend = load_module(ROOT / "scripts/production_installer.py", "native_home_allocation_case")
    profile = tmp_path / "native-profile"
    allocation = ctypes.c_wchar_p(str(profile))
    freed = []
    def get_path(_folder, flags, token, output):
        assert flags == 0 and token is None
        ctypes.cast(output, ctypes.POINTER(ctypes.c_wchar_p))[0] = allocation
        return status
    def free(pointer):
        freed.append(pointer.value)
    def library(name):
        return (SimpleNamespace(SHGetKnownFolderPath=get_path) if name == "shell32"
                else SimpleNamespace(CoTaskMemFree=free))
    monkeypatch.setattr(ctypes, "WinDLL", library)
    assert backend._native_codex_default_home() == (profile / ".codex" if status == 0 else None)
    assert freed == [ctypes.cast(allocation, ctypes.c_void_p).value]


@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX native home selection")
def test_posix_native_home_does_not_borrow_userprofile(tmp_path, monkeypatch):
    backend = load_module(ROOT / "scripts/production_installer.py", "native_posix_home_case")
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("HOME", raising=False)
    assert backend._native_codex_default_home() is None
    monkeypatch.setenv("HOME", "relative-home")
    assert backend._native_codex_default_home() is None
    monkeypatch.setenv("HOME", str(tmp_path))
    assert backend._native_codex_default_home() == tmp_path / ".codex"
