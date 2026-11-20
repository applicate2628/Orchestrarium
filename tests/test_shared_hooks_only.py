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
def shared_prior(tmp_path, monkeypatch, request):
    if getattr(request, "param", False):
        original_specs = PI._hook_specs

        def specs_with_tool_pair(provider, lead):
            specs = original_specs(provider, lead)
            selected = sorted(stem for stem, _, event, matcher in specs
                              if event == "SessionStart" and matcher is None)[:2]
            assert len(selected) == 2
            return [(stem, script, "PostToolUse", "OldTool") if stem in selected
                    else (stem, script, event, matcher)
                    for stem, script, event, matcher in specs]

        monkeypatch.setattr(PI, "_hook_specs", specs_with_tool_pair)

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

def test_update_between_retained_releases_is_idempotent_and_never_adopts_wrong_owner(shared_prior, monkeypatch):
    s = shared_prior
    args = ["--global", "--shared-hook-runtime", "--hooks-only"]
    assert PI.install("codex", args) == 0
    registered = (s.common.read_bytes(), s.sidecar.read_bytes())
    _stems, identities = s.health._load_codex_inventory(s.sidecar, target=s.alias, host_os=s.host)
    old_python = Path(json.loads(next(iter(identities)))["command"].split("\0")[0])
    replacement = s.tmp_path / "other-release" / "lead"
    previous_specs = PI._hook_specs("codex", s.retained)
    retired, moved = previous_specs[:2]
    desired_specs = [
        (stem, replacement / script.relative_to(s.retained),
         "PostToolUse" if stem == moved[0] else event, matcher)
        for stem, script, event, matcher in previous_specs if stem != retired[0]
    ]
    added = "new-release-hook"
    desired_specs.append((added, replacement / "hooks" / f"{added}.py", "SessionStart", None))
    monkeypatch.setitem(PI._CODEX_HOOK_STATUS_MESSAGES, added, "Fixture hook")
    original_specs = PI._hook_specs
    monkeypatch.setattr(PI, "_hook_specs", lambda provider, lead:
                        desired_specs if lead == replacement else original_specs(provider, lead))
    for _stem, script, _event, _matcher in desired_specs:
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("pass\n", encoding="utf-8")
    monkeypatch.setattr(PI, "_retained_codex_hook_root", lambda *_args: replacement)

    def select(_root, package):
        return s.retained, (old_python if package == s.retained.parent else old_python.with_name("wrong")), previous_specs
    monkeypatch.setattr(PI, "_previous_retained_hook_root", select)

    chosen = [*args, "--previous-retained-release", str(s.retained.parent)]
    wrong = [*args, "--previous-retained-release", str(replacement.parent)]
    assert PI.install("codex", wrong) == 1
    assert (s.common.read_bytes(), s.sidecar.read_bytes()) == registered
    with monkeypatch.context() as fault:
        fault.setattr(PI, "_run_hook_health_bounded", lambda *_args: SimpleNamespace(returncode=1))
        assert PI.install("codex", chosen) == 1
    assert (s.common.read_bytes(), s.sidecar.read_bytes()) == registered
    assert all(p.read_bytes() == s.before[p] for p in (s.settings, s.owner_receipt))
    select_targets = s.health._selected_hook_targets

    def select_non_direct(specs):
        targets, witnesses = select_targets(specs)
        stem = next(iter(witnesses))
        script, (resolved, _chain, node) = witnesses[stem]
        witnesses[stem] = (script, (resolved, ("non-direct-fixture",), node))
        return targets, witnesses

    with monkeypatch.context() as fault:
        fault.setattr(PI, "_hook_health_module", lambda _root: s.health)
        fault.setattr(s.health, "_selected_hook_targets", select_non_direct)
        assert PI.install("codex", chosen) == 1
    assert (s.common.read_bytes(), s.sidecar.read_bytes()) == registered
    assert PI.install("codex", [*chosen, "--dry-run"]) == 0
    assert (s.common.read_bytes(), s.sidecar.read_bytes()) == registered
    assert PI.install("codex", chosen) == 0
    assert json.loads(s.common.read_bytes())["hooks"][s.event][0] == s.foreign
    assert (s.common.read_bytes(), s.sidecar.read_bytes()) != registered
    items = json.loads(s.common.read_bytes())
    targets, _ = s.health._selected_hook_targets(previous_specs)
    assert list(s.health._iter_owned_hooks(items, {stem for stem, *_ in previous_specs},
                                          "codex", s.host, targets)) == []
    assert items["hooks"]["PostToolUse"]
    assert any(added + ".py" in handler["command"]
               for group in items["hooks"]["SessionStart"] for handler in group["hooks"])

    published = {p: (p.read_bytes(), p.stat().st_ino) for p in (s.common, s.sidecar)}
    assert PI.install("codex", chosen) == 0
    assert all((p.read_bytes(), p.stat().st_ino) == before for p, before in published.items())
@pytest.mark.parametrize("member", ["bundle.json", "runtime-evidence.json", "app/install.py"])
def test_previous_release_rejects_non_direct_package_evidence(tmp_path, member):
    package = tmp_path / "previous"
    selected = package / member
    selected.parent.mkdir(parents=True)
    elsewhere = tmp_path / "not-in-package"
    elsewhere.write_text("not package evidence", encoding="utf-8")
    _make_file_symlink(selected, elsewhere)
    with pytest.raises(ValueError, match="redirected package evidence"):
        PI._previous_retained_hook_root(ROOT, package)

@pytest.mark.parametrize("shared_prior", [False, True], indirect=True, ids=["remove", "matcher-change"])
@pytest.mark.parametrize("foreign_between", [False, True])
def test_shared_upgrade_retires_joint_owned_group_without_shifting_foreign(
    shared_prior, monkeypatch, capsys, foreign_between,
):
    s = shared_prior
    args = ["--global", "--shared-hook-runtime", "--hooks-only"]
    assert PI.install("codex", args) == 0
    previous = PI._hook_specs("codex", s.retained)
    matcher_change = any(matcher == "OldTool" for _, _, _, matcher in previous)
    affected_event, old_matcher = ("PostToolUse", "OldTool") if matcher_change else ("SessionStart", None)
    selected = {stem for stem, _, event, matcher in previous
                if (event, matcher) == (affected_event, old_matcher)}
    selected = set(sorted(selected)[:2])
    assert len(selected) == 2
    data = json.loads(s.common.read_bytes())
    targets, _ = s.health._selected_hook_targets(previous)
    rows = list(s.health._owned_records(data, selected, "codex", s.host, targets))
    assert len(rows) == 2
    first, second = rows
    groups = data["hooks"][affected_event]
    foreign = {"type": "command", "command": "unrelated-operator-hook"}
    owners = [first[4], second[4]]
    groups[first[1]]["hooks"] = ([owners[0], foreign, owners[1]]
                                  if foreign_between else [foreign, *owners])
    groups[second[1]]["hooks"] = []
    s.common.write_bytes(HELPER.encode_hook_config(data))
    before = (s.common.read_bytes(), s.sidecar.read_bytes(), s.settings.read_bytes())
    alias = (s.alias.lstat().st_ino, os.readlink(s.alias))
    _, identities = s.health._load_codex_inventory(s.sidecar, target=s.alias, host_os=s.host)
    old_python = Path(json.loads(next(iter(identities)))["command"].split("\0")[0])
    replacement = s.tmp_path / "next-release" / "lead"
    desired = [(stem, replacement / script.relative_to(s.retained), event,
                "NewTool" if matcher_change and stem in selected else matcher)
               for stem, script, event, matcher in previous
               if matcher_change or stem not in selected]
    for _, script, _, _ in desired:
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("pass\n", encoding="utf-8")
    original_specs = PI._hook_specs
    monkeypatch.setattr(PI, "_hook_specs", lambda provider, lead:
                        desired if lead == replacement else original_specs(provider, lead))
    monkeypatch.setattr(PI, "_retained_codex_hook_root", lambda *_args: replacement)
    monkeypatch.setattr(PI, "_previous_retained_hook_root",
                        lambda *_args: (s.retained, old_python, previous))
    chosen = [*args, "--previous-retained-release", str(s.retained.parent)]

    expected = int(foreign_between)
    assert PI.install("codex", [*chosen, "--dry-run"]) == expected
    assert (s.common.read_bytes(), s.sidecar.read_bytes(), s.settings.read_bytes()) == before
    assert PI.install("codex", chosen) == expected
    assert (s.alias.lstat().st_ino, os.readlink(s.alias)) == alias
    assert s.settings.read_bytes() == before[2]
    if foreign_between:
        assert (s.common.read_bytes(), s.sidecar.read_bytes()) == before[:2]
        assert "E_CODEX_HOOK_SLOT_SHIFT" in capsys.readouterr().err
    else:
        result = json.loads(s.common.read_bytes())
        assert result["hooks"][affected_event][first[1]]["hooks"] == [foreign]
        assert not list(s.health._owned_records(result, selected, "codex", s.host, targets))
        desired_targets, _ = s.health._selected_hook_targets(desired)
        registered = list(s.health._owned_records(result, selected, "codex", s.host, desired_targets))
        assert {row[5].marker for row in registered} == (selected if matcher_change else set())
        assert all(row[0] == affected_event and row[3].get("matcher") == "NewTool"
                   for row in registered)
        published = (s.common.read_bytes(), s.sidecar.read_bytes())
        assert PI.install("codex", chosen) == 0
        assert (s.common.read_bytes(), s.sidecar.read_bytes()) == published


def test_retained_catalog_reads_its_own_literals_without_executing(tmp_path):
    catalog = tmp_path / "universal_hooks_manifest.py"
    catalog.write_text(
        'raise RuntimeError("past release must not run")\n'
        'REGISTERED_HOOK_STEMS_BY_PLATFORM = {"codex": frozenset({"old-hook"})}\n'
        'HOOK_METADATA = (("old-hook", "hooks", "Stop", None),)\n'
        'HOOK_DIRECTORY_OVERRIDES = {("codex", "old-hook"): "scripts"}\n'
        'HOOK_SCRIPT_OVERRIDES = {"old-hook": "other.py"}\n',
        encoding="utf-8",
    )
    assert PI._HOOK_MANIFEST.retained_hook_specs(catalog, "codex", tmp_path) == [
        ("old-hook", tmp_path / "scripts" / "other.py", "Stop", None),
    ]
