"""Isolated shared hooks-only registration transaction. No native trust mutation."""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from _filesystem_fixture_support import _make_file_symlink
from test_hook_runtime_installers import HELPER, PRODUCTION_INSTALLER as PI, ROOT


@pytest.fixture
def shared_prior(tmp_path, monkeypatch):
    home = tmp_path / "operator-home"
    profile = home / ".codex"
    profile.mkdir(parents=True)
    sync = tmp_path / "shared"
    sync.mkdir()
    common = sync / "hooks.json"
    alias = profile / "hooks.json"
    owned_lead = home / ".agents/skills/lead"
    owned_lead.mkdir(parents=True)
    retained = tmp_path / "retained/lead"
    retained.mkdir(parents=True)
    health = PI._hook_health_module(ROOT)
    host = "windows" if os.name == "nt" else "posix"
    missing_python = str(tmp_path / ("python.exe" if host == "windows" else "python"))
    old_executable = Path(missing_python)
    old_executable.write_bytes(b"not invoked")
    old_executable.chmod(0o755)
    specs = PI._hook_specs("codex", owned_lead)
    # Keep a foreign first slot in the same event as a managed registration.
    event = specs[0][2]
    foreign = {"hooks": [{"type": "command", "command": "foreign-user-handler"}]}
    data = {"hooks": {event: [foreign]}}
    for stem, script, current_event, matcher in specs:
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("pass\n", encoding="utf-8")
        replacement = retained / script.relative_to(owned_lead)
        replacement.parent.mkdir(parents=True, exist_ok=True)
        replacement.write_text("pass\n", encoding="utf-8")
        old_target = HELPER.resolve_hook_target(str(script), host, "codex",
                                                python_executable=missing_python)
        data["hooks"].setdefault(current_event, []).append(
            HELPER.build_codex_entry(old_target, host, current_event, matcher,
                                     PI._CODEX_HOOK_STATUS_MESSAGES[stem])
        )
    old_executable.unlink()
    common.write_bytes(HELPER.encode_hook_config(data))
    _make_file_symlink(alias, common)
    owner_receipt = owned_lead.parent / PI._LEAD_RECEIPT_NAME
    owner_receipt.write_bytes(PI._lead_receipt_bytes(PI._tree_sha256(owned_lead)))
    settings = profile / "config.toml"
    settings.write_text("# User settings and native trust are out of scope.\n", encoding="utf-8")
    sidecar = sync / health.INVENTORY_NAME
    health.write_codex_inventory(target=alias, specs=specs, inventory_path=sidecar, host_os=host)
    calls = []
    monkeypatch.setattr(PI, "_retained_codex_hook_root", lambda *args: retained)
    monkeypatch.setattr(PI, "_resolve_global_home", lambda: home)
    monkeypatch.setattr(PI, "_run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))
    monkeypatch.setattr(health, "resolve_codex_command", lambda *_args: ["local-fixture"])
    def checker(args, _root, trusted):
        assert Path(args[0]) == trusted == ROOT / "scripts/check-hook-health.py"
        assert args[args.index("--codex-trust-mode") + 1] == "report"
        calls.append(args)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(PI, "_run_hook_health_bounded", checker)
    before = {p: p.read_bytes() for p in (common, sidecar, settings, owner_receipt)}
    return SimpleNamespace(**locals())


def test_scoped_preview_and_apply_preserve_foreign_profile_and_link(shared_prior):
    s = shared_prior
    args = ["--global", "--shared-hook-runtime", "--hooks-only"]
    assert PI.install("codex", [*args, "--dry-run"]) == 0
    assert not s.calls and all(p.read_bytes() == value for p, value in s.before.items())
    assert PI.install("codex", args) == 0
    assert len(s.calls) == 2
    assert json.loads(s.sidecar.read_bytes())["schemaVersion"] == 2
    assert json.loads(s.common.read_bytes())["hooks"][s.event][0] == s.foreign
    assert s.alias.is_symlink() and s.alias.resolve() == s.common
    assert all(p.read_bytes() == s.before[p] for p in (s.settings, s.owner_receipt))
    published = {p: (p.read_bytes(), p.stat().st_ino) for p in (s.common, s.sidecar)}
    assert PI.install("codex", args) == 0
    assert all((p.read_bytes(), p.stat().st_ino) == before for p, before in published.items())


def test_failed_postpublish_health_restores_both_files(shared_prior, monkeypatch):
    s = shared_prior
    def reject(*_args):
        assert json.loads(s.sidecar.read_bytes())["schemaVersion"] == 2
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(PI, "_run_hook_health_bounded", reject)
    assert PI.install("codex", ["--global", "--shared-hook-runtime", "--hooks-only"]) == 1
    assert s.alias.is_symlink() and s.alias.resolve() == s.common
    assert all(p.read_bytes() == value for p, value in s.before.items())


def test_scope_does_not_accept_drifted_receipt_or_pack_flags(shared_prior, monkeypatch):
    s = shared_prior
    selected = s.specs[0][1]
    selected.write_text("different\n", encoding="utf-8")
    args = ["--global", "--shared-hook-runtime", "--hooks-only"]
    assert PI.install("codex", args) == 1
    assert all(p.read_bytes() == value for p, value in s.before.items())
    monkeypatch.setattr(PI, "_target", lambda *_args: pytest.fail("target must not be reached"))
    assert PI.install("codex", [*args, "--force"]) == 1
    assert PI.install("codex", ["--hooks-only", "--uninstall", "--apply"]) == 1


def test_foreign_link_retarget_is_not_adopted(shared_prior, monkeypatch):
    s = shared_prior
    alternate = s.sync / "foreign-hooks.json"
    alternate.write_bytes(s.before[s.common])
    original = alternate.read_bytes()

    def swap_alias(_root, _installer, registration, _provider, _mode, stage):
        if stage == "sync":
            registration.unlink()
            _make_file_symlink(registration, alternate)

    monkeypatch.setattr(PI, "_checkpoint", swap_alias)
    assert PI.install("codex", ["--global", "--shared-hook-runtime", "--hooks-only"]) == 1
    assert s.alias.resolve() == alternate
    assert alternate.read_bytes() == original
    assert all(p.read_bytes() == value for p, value in s.before.items())
    assert not s.calls


def test_refuses_custom_predecessor_arguments_even_when_inventory_matches(shared_prior, capsys):
    s = shared_prior
    payload = json.loads(s.common.read_bytes())
    first_owned = payload["hooks"][s.specs[0][2]][1]["hooks"][0]
    first_owned["command"] += " --operator-defined"
    s.common.write_bytes(HELPER.encode_hook_config(payload))
    s.health.write_codex_inventory(
        target=s.alias, specs=s.specs, inventory_path=s.sidecar, host_os=s.host,
    )
    before = (s.common.read_bytes(), s.sidecar.read_bytes())
    args = ["--global", "--shared-hook-runtime", "--hooks-only"]
    assert PI.install("codex", [*args, "--dry-run"]) == 1
    assert PI.install("codex", args) == 1
    assert "E_SHARED_HOOK_RUNTIME" in capsys.readouterr().err
    assert (s.common.read_bytes(), s.sidecar.read_bytes()) == before
    assert not s.calls
