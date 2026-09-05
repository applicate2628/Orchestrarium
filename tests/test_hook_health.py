"""Read-only registration health checks for both provider schemas."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check-hook-health.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_hook_health_tests", CHECKER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


def _source_dirs(platform: str) -> tuple[Path, ...]:
    if platform == "claude":
        return (
            ROOT / "src.claude" / "agents" / "scripts",
            ROOT / "src.claude" / "agents" / "hooks",
        )
    return (
        ROOT / "src.codex" / "skills" / "lead" / "scripts",
        ROOT / "src.codex" / "skills" / "lead" / "hooks",
    )


def _target_for(platform: str, stem: str) -> Path:
    for directory in _source_dirs(platform):
        candidate = directory / f"{stem}.py"
        if candidate.is_file():
            return candidate
    raise AssertionError(f"missing Python target for {platform}:{stem}")


def _config(platform: str) -> dict:
    entries = []
    for stem in sorted(CHECKER._manifest_stems(ROOT, platform)):
        target = _target_for(platform, stem)
        if platform == "claude":
            hook = {
                "type": "command",
                "command": sys.executable,
                "args": [str(target)],
            }
        else:
            hook = {
                "type": "command",
                "command": " ".join(
                    shlex.quote(token) for token in (sys.executable, str(target))
                ),
            }
        entries.append({"hooks": [hook]})
    return {"hooks": {"PreToolUse": entries}}


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_registered_command_executes_every_owned_hook(
    tmp_path: Path, platform: str
) -> None:
    target = tmp_path / f"{platform}.json"
    target.write_text(json.dumps(_config(platform)), encoding="utf-8")
    messages = CHECKER.verify_config(
        target=target,
        platform=platform,
        host_os="posix",
        repo_root=ROOT,
        verify_fires=True,
    )
    expected = CHECKER._manifest_stems(ROOT, platform)
    assert len(messages) == len(expected)
    assert all(message.startswith(f"PASS {platform} ") for message in messages)


def _mcp_only_config() -> dict:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": sys.executable,
                            "args": [
                                str(
                                    ROOT
                                    / "src.claude"
                                    / "agents"
                                    / "scripts"
                                    / "check-mcp-momentum.py"
                                )
                            ],
                        }
                    ]
                }
            ]
        }
    }


def test_hook_health_uses_force_mode_and_requires_claude_deny_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "mcp-health.json"
    target.write_text(json.dumps(_mcp_only_config()), encoding="utf-8")
    monkeypatch.setattr(
        CHECKER, "_manifest_stems", lambda _root, _platform: {"check-mcp-momentum"}
    )
    real_run = subprocess.run
    observed: dict[str, object] = {}

    def capturing_run(*args, **kwargs):
        env = kwargs.get("env")
        observed["env"] = env
        if isinstance(env, dict):
            synthetic_home = Path(env["HOME"])
            observed["mcp_config_exists"] = (synthetic_home / ".claude.json").exists()
            observed["mode"] = (synthetic_home / ".agents-mode.yaml").read_text(
                encoding="utf-8"
            )
        completed = real_run(*args, **kwargs)
        observed["stdout"] = completed.stdout
        return completed

    monkeypatch.setattr(CHECKER.subprocess, "run", capturing_run)
    messages = CHECKER.verify_config(
        target=target,
        platform="claude",
        host_os="posix",
        repo_root=ROOT,
        verify_fires=True,
    )
    assert messages == ["PASS claude PreToolUse check-mcp-momentum"]
    assert "[MCP-FORCE-1]" in str(observed.get("stdout", ""))
    assert observed.get("mcp_config_exists") is False
    assert observed.get("mode") == "mcpMode: force\n"


def test_hook_health_rejects_silent_mcp_positive_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "silent-mcp-health.json"
    target.write_text(json.dumps(_mcp_only_config()), encoding="utf-8")
    monkeypatch.setattr(
        CHECKER, "_manifest_stems", lambda _root, _platform: {"check-mcp-momentum"}
    )
    monkeypatch.setattr(
        CHECKER.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    with pytest.raises(ValueError, match="check-mcp-momentum.*decision"):
        CHECKER.verify_config(
            target=target,
            platform="claude",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=True,
        )


def test_missing_executable_and_missing_target_are_distinct(tmp_path: Path) -> None:
    executable_config = _config("claude")
    executable_config["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = str(
        tmp_path / "missing-python"
    )
    executable_json = tmp_path / "missing-executable.json"
    executable_json.write_text(json.dumps(executable_config), encoding="utf-8")
    with pytest.raises(ValueError, match="registered executable is missing"):
        CHECKER.verify_config(
            target=executable_json,
            platform="claude",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
        )

    target_config = _config("claude")
    target_config["hooks"]["PreToolUse"][0]["hooks"][0]["args"] = [
        str(tmp_path / "agents-mode-reminder.py")
    ]
    target_json = tmp_path / "missing-target.json"
    target_json.write_text(json.dumps(target_config), encoding="utf-8")
    with pytest.raises(ValueError, match="registered target is missing"):
        CHECKER.verify_config(
            target=target_json,
            platform="claude",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
        )


def test_leftover_wrapper_warning_is_read_only(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(_config("claude")), encoding="utf-8")
    installed = tmp_path / "agents"
    wrapper = installed / "scripts" / "check-bugfix-discipline.ps1"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("wrapper\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(CHECKER_PATH),
            "--target",
            str(target),
            "--platform",
            "claude",
            "--host-os",
            "posix",
            "--repo-root",
            str(ROOT),
            "--installed-root",
            str(installed),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert f"WARN leftover hook wrapper: {wrapper}" in completed.stdout
    assert wrapper.read_text(encoding="utf-8") == "wrapper\n"


def test_hook_health_nonzero_names_failing_hook(tmp_path: Path) -> None:
    failing_stem = "agents-mode-reminder"
    installed_root = tmp_path / "agents"
    for source_dir in _source_dirs("claude"):
        shutil.copytree(source_dir, installed_root / source_dir.name)

    config = _config("claude")
    for entry in config["hooks"]["PreToolUse"]:
        for hook in entry["hooks"]:
            source_target = Path(hook["args"][0])
            hook["args"] = [
                str(installed_root / source_target.parent.name / source_target.name)
            ]

    installed_target = installed_root / "scripts" / f"{failing_stem}.py"
    installed_target.write_text(
        "import sys\n"
        'sys.stderr.write("deliberate installed hook failure\\n")\n'
        "raise SystemExit(37)\n",
        encoding="utf-8",
    )

    matching_hooks = [
        hook
        for entry in config["hooks"]["PreToolUse"]
        for hook in entry["hooks"]
        if Path(hook["args"][0]).stem == failing_stem
    ]
    assert len(matching_hooks) == 1
    matching_hooks[0]["args"] = [str(installed_target)]

    target = tmp_path / "settings.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(CHECKER_PATH),
            "--target",
            str(target),
            "--platform",
            "claude",
            "--host-os",
            "windows" if os.name == "nt" else "posix",
            "--repo-root",
            str(ROOT),
            "--verify-fires",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode != 0
    assert failing_stem in completed.stderr
    assert "deliberate installed hook failure" in completed.stderr


def test_foreign_entry_without_args_is_tolerated(tmp_path: Path) -> None:
    config = _config("claude")
    config["hooks"]["PreToolUse"].append(
        {"hooks": [{"type": "command", "command": "codegraph prompt-hook"}]}
    )
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    messages = CHECKER.verify_config(
        target=target,
        platform="claude",
        host_os="posix",
        repo_root=ROOT,
        verify_fires=False,
    )
    expected = CHECKER._manifest_stems(ROOT, "claude")
    assert len(messages) == len(expected)


def test_unparseable_entry_naming_owned_stem_fails_loudly(tmp_path: Path) -> None:
    stem = "check-bugfix-discipline"
    target_script = _target_for("claude", stem)
    config = _config("claude")
    config["hooks"]["PreToolUse"].append(
        {
            "hooks": [
                {
                    "type": "command",
                    "command": f'"{sys.executable}" "{target_script}"',
                }
            ]
        }
    )
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match=stem):
        CHECKER.verify_config(
            target=target,
            platform="claude",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
        )


def test_corrupted_args_on_owned_entry_names_the_stem(tmp_path: Path) -> None:
    stem = "check-bugfix-discipline"
    config = _config("claude")
    matching_hooks = [
        hook
        for entry in config["hooks"]["PreToolUse"]
        for hook in entry["hooks"]
        if Path(hook["args"][0]).stem == stem
    ]
    assert len(matching_hooks) == 1
    matching_hooks[0]["args"] = matching_hooks[0]["args"][0]
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match=stem) as excinfo:
        CHECKER.verify_config(
            target=target,
            platform="claude",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
        )
    assert "missing registered hooks" not in str(excinfo.value)


@pytest.mark.parametrize("pending_status", ("untrusted", "modified"))
def test_hook_health_report_allows_only_touched_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pending_status: str
) -> None:
    target = tmp_path / "hooks.json"
    target.write_text(json.dumps(_config("codex")), encoding="utf-8")
    rows = list(
        CHECKER._iter_owned_hooks(
            json.loads(target.read_text(encoding="utf-8")),
            CHECKER._manifest_stems(ROOT, "codex"),
            "codex",
            "posix",
        )
    )
    touched = CHECKER.canonical_identity(
        rows[0][0],
        rows[0][2],
        "posix",
        matcher=rows[0][3],
        source_path=target,
    )
    records = [
        {
            "eventName": event,
            "matcher": matcher,
            "handlerType": "command",
            "command": " ".join(shlex.quote(value) for value in argv),
            "currentHash": "sha256:fixture",
            "trustStatus": pending_status if index == 0 else "trusted",
            "enabled": True,
            "sourcePath": str(target.resolve()),
        }
        for index, (event, _stem, argv, matcher) in enumerate(rows)
    ]
    monkeypatch.setattr(CHECKER, "_codex_hooks_list", lambda **_kwargs: records)
    monkeypatch.setattr(
        CHECKER, "resolve_codex_command",
        lambda *_args: pytest.fail("injected inventory must not resolve a real host"),
    )
    messages = CHECKER.verify_config(
        target=target,
        platform="codex",
        host_os="posix",
        repo_root=ROOT,
        verify_fires=False,
        codex_trust_mode="report",
        touched_identities={touched},
    )
    assert any(message.startswith("PENDING_MANUAL_TRUST") for message in messages)
    with pytest.raises(
        ValueError, match=f"CODEX_HOOK_TRUST_{pending_status.upper()}"
    ):
        CHECKER.verify_config(
            target=target,
            platform="codex",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
            codex_trust_mode="require",
        )
    with pytest.raises(ValueError, match="CODEX_HOOK_TRUST_PREEXISTING_DRIFT"):
        CHECKER.verify_config(
            target=target,
            platform="codex",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
            codex_trust_mode="report",
        )


def _host_trust_fixture(target: Path) -> tuple[list[tuple], list[dict]]:
    target.write_text(json.dumps(_config("codex")), encoding="utf-8")
    rows = list(CHECKER._iter_owned_hooks(
        json.loads(target.read_text(encoding="utf-8")),
        CHECKER._manifest_stems(ROOT, "codex"), "codex", "posix",
    ))
    records = [{
        "eventName": event, "matcher": matcher, "handlerType": "command",
        "command": " ".join(shlex.quote(value) for value in argv),
        "sourcePath": str(target.resolve()), "enabled": True,
        "trustStatus": "trusted", "currentHash": "sha256:fixture",
    } for event, _stem, argv, matcher in rows]
    return rows, records


def _make_file_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=False)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")
    assert link.is_symlink()


def _make_directory_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows junction coverage")
    link.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item",
            "-ItemType",
            "Junction",
            "-Path",
            str(link),
            "-Target",
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not os.path.isjunction(link):
        pytest.skip(f"junction creation is unavailable: {result.stdout}{result.stderr}")


def test_complete_fingerprint_detects_matcher_only_upgrade(tmp_path: Path) -> None:
    target = tmp_path / "hooks.json"
    config = _config("codex")
    config["hooks"]["PreToolUse"][0]["matcher"] = "Bash"
    target.write_text(json.dumps(config), encoding="utf-8")
    before = CHECKER.owned_canonical_identities(
        target=target, platform="codex", host_os="posix", repo_root=ROOT
    )
    entry = config["hooks"]["PreToolUse"][0]
    entry["matcher"] += "|MatcherOnlyUpgrade"
    target.write_text(json.dumps(config), encoding="utf-8")
    after = CHECKER.owned_canonical_identities(
        target=target, platform="codex", host_os="posix", repo_root=ROOT
    )
    assert len(after - before) == len(before - after) == 1


@pytest.mark.parametrize(("field", "value", "discriminator"), (
    ("enabled", False, "CODEX_HOOK_TRUST_DISABLED"),
    ("currentHash", "", "CODEX_HOOK_LIST_MALFORMED"),
    ("sourcePath", "wrong-hooks.json", "CODEX_HOOK_LIST_SOURCE_MISMATCH"),
))
def test_require_rejects_disabled_empty_hash_or_wrong_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value, discriminator: str
) -> None:
    target = tmp_path / "hooks.json"
    _rows, records = _host_trust_fixture(target)
    records[0][field] = str(tmp_path / value) if field == "sourcePath" else value
    monkeypatch.setattr(CHECKER, "_codex_hooks_list", lambda **_kwargs: records)
    with pytest.raises(ValueError, match=discriminator):
        CHECKER.verify_config(
            target=target, platform="codex", host_os="posix", repo_root=ROOT,
            verify_fires=False, codex_trust_mode="require",
            codex_command=[str(Path(sys.executable).resolve())],
            codex_home=tmp_path / "codex-home", query_cwd=tmp_path,
        )


def test_require_rejects_wrong_host_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "hooks.json"
    _rows, records = _host_trust_fixture(target)
    records[0]["command"] += " --different-runtime"
    monkeypatch.setattr(CHECKER, "_codex_hooks_list", lambda **_kwargs: records)
    with pytest.raises(ValueError, match="CODEX_HOOK_LIST_MISSING"):
        CHECKER.verify_config(
            target=target, platform="codex", host_os="posix", repo_root=ROOT,
            verify_fires=False, codex_trust_mode="require",
            codex_command=[str(Path(sys.executable).resolve())],
            codex_home=tmp_path / "home", query_cwd=tmp_path,
        )


class _RecordingInput(io.BytesIO):
    def __init__(self, cancel: bool = False) -> None:
        super().__init__(); self.cancel = cancel
    def write(self, value: bytes) -> int:
        if self.cancel: raise KeyboardInterrupt
        return super().write(value)


class _FakeAppServer:
    def __init__(
        self,
        stdout: str,
        *,
        cancel: bool = False,
        terminate_timeout: bool = False,
        returncode: int | None = None,
    ) -> None:
        self.stdin = _RecordingInput(cancel); self.stdout = io.BytesIO(stdout.encode("utf-8"))
        self.stderr = io.BytesIO(b"credential-sentinel\n")
        self.returncode = returncode; self.terminate_timeout = terminate_timeout
        self.terminated = False; self.killed = False; self.wait_calls = 0
    def poll(self): return self.returncode
    def terminate(self): self.terminated = True
    def kill(self): self.killed = True
    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.terminate_timeout and not self.killed:
            raise subprocess.TimeoutExpired("codex", timeout)
        self.returncode = 0; return 0


@pytest.mark.parametrize(("stdout", "expected"), (
    ('{"id":1,"result":{}}\n{"id":2,"result":{"data":[]}}\n', None),
    ('{"id":1,"result":{}}\n{"id":2,"result":{"data":"wrong"}}\n', "MALFORMED"),
    ('{"id":1,"result":{}}\n', "UNAVAILABLE"),
))
def test_app_server_cleanup_success_malformed_and_list_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str, expected: str | None
) -> None:
    process = _FakeAppServer(stdout)
    monkeypatch.setattr(CHECKER.subprocess, "Popen", lambda *_a, **_kw: process)
    call = lambda: CHECKER._codex_hooks_list(
        codex_command=[str(Path(sys.executable).resolve())],
        codex_home=tmp_path / "home", query_cwd=tmp_path, timeout=0.01,
    )
    if expected:
        with pytest.raises(ValueError, match=expected): call()
    else: assert call() == []
    assert process.terminated
    assert process.stdin.closed and process.stdout.closed and process.stderr.closed


def test_app_server_cleanup_cancellation_and_terminate_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = '{"id":1,"result":{}}\n{"id":2,"result":{"data":[]}}\n'
    cancelled = _FakeAppServer(response, cancel=True)
    monkeypatch.setattr(CHECKER.subprocess, "Popen", lambda *_a, **_kw: cancelled)
    with pytest.raises(KeyboardInterrupt):
        CHECKER._codex_hooks_list(
            codex_command=[str(Path(sys.executable).resolve())],
            codex_home=tmp_path / "home", query_cwd=tmp_path,
        )
    assert cancelled.terminated and cancelled.stdin.closed and cancelled.stdout.closed and cancelled.stderr.closed
    timed = _FakeAppServer(response, terminate_timeout=True)
    monkeypatch.setattr(CHECKER.subprocess, "Popen", lambda *_a, **_kw: timed)
    assert CHECKER._codex_hooks_list(
        codex_command=[str(Path(sys.executable).resolve())],
        codex_home=tmp_path / "home", query_cwd=tmp_path,
    ) == []
    assert timed.terminated and timed.killed and timed.wait_calls == 2


def test_inventory_probe_uses_exact_scope_and_excludes_sentinels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = _FakeAppServer('{"id":1,"result":{}}\n{"id":2,"result":{"data":[]}}\n')
    captured = {}
    def fake_popen(arguments, **kwargs):
        captured["arguments"] = arguments; captured.update(kwargs); return process
    monkeypatch.setenv("OPENAI_API_KEY", "credential-sentinel")
    monkeypatch.setenv("PROMPT_SENTINEL", "prompt-sentinel")
    monkeypatch.setattr(CHECKER.subprocess, "Popen", fake_popen)
    command = [str(Path(sys.executable).resolve()), str(tmp_path / "codex-owner.py")]
    home = tmp_path / "selected-home"; cwd = tmp_path / "selected-cwd"; cwd.mkdir()
    assert CHECKER._codex_hooks_list(
        codex_command=command, codex_home=home, query_cwd=cwd
    ) == []
    assert captured["arguments"][:2] == command
    assert captured["cwd"] == cwd and captured["env"]["CODEX_HOME"] == str(home)
    serialized = json.dumps(captured, default=str)
    assert "credential-sentinel" not in serialized and "prompt-sentinel" not in serialized


def test_generated_inventory_is_read_only_and_detects_registration_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "hooks.json"
    rows, records = _host_trust_fixture(target)
    before = target.read_bytes()
    inventory = tmp_path / "codex-hook-inventory.json"
    specs = [
        (stem, Path(argv[-1]), event, matcher)
        for event, stem, argv, matcher in rows
    ]
    monkeypatch.setenv("OPENAI_API_KEY", "credential-sentinel")
    CHECKER.write_codex_inventory(
        target=target, specs=specs, inventory_path=inventory, host_os="posix"
    )
    assert target.read_bytes() == before
    assert "credential-sentinel" not in inventory.read_text(encoding="utf-8")
    monkeypatch.setattr(CHECKER, "_codex_hooks_list", lambda **_kwargs: records)
    CHECKER.verify_config(
        target=target, platform="codex", host_os="posix", repo_root=ROOT,
        verify_fires=False, inventory_path=inventory,
        codex_trust_mode="require",
        codex_command=[str(Path(sys.executable).resolve())],
        codex_home=tmp_path / "home", query_cwd=tmp_path,
    )
    config = json.loads(target.read_text(encoding="utf-8"))
    config["hooks"]["PreToolUse"][0]["matcher"] = "drift"
    target.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="drifted from generated inventory"):
        failure = CHECKER.verify_config(
            target=target, platform="codex", host_os="posix", repo_root=ROOT,
            verify_fires=False, inventory_path=inventory,
        )


def test_codex_hook_health_report_and_require_accept_file_symlink_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logical = tmp_path / "home" / ".codex" / "hooks.json"
    resolved = tmp_path / "shared" / "hooks.json"
    resolved.parent.mkdir()
    resolved.write_text('{}\n', encoding="utf-8")
    _make_file_symlink(logical, resolved)
    link_target = os.readlink(logical)
    rows, records = _host_trust_fixture(logical)
    specs = [
        (stem, Path(argv[-1]), event, matcher)
        for event, stem, argv, matcher in rows
    ]
    inventory = resolved.parent / CHECKER.INVENTORY_NAME

    assert CHECKER._codex_inventory_sidecar(logical) == inventory
    CHECKER.write_codex_inventory(
        target=logical,
        specs=specs,
        inventory_path=inventory,
        host_os="posix",
    )
    monkeypatch.setattr(CHECKER, "_codex_hooks_list", lambda **_kwargs: records)

    for mode in ("report", "require"):
        messages = CHECKER.verify_config(
            target=logical,
            platform="codex",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
            inventory_path=inventory,
            codex_trust_mode=mode,
            codex_command=[str(Path(sys.executable).resolve())],
            codex_home=logical.parent,
            query_cwd=tmp_path,
        )
        assert sum(
            message.startswith("PASS CODEX_HOOK_TRUST_TRUSTED")
            for message in messages
        ) == len(rows)

    assert logical.is_symlink()
    assert os.readlink(logical) == link_target
    assert resolved.is_file()
    assert inventory.is_file()
    assert not (logical.parent / CHECKER.INVENTORY_NAME).exists()


def test_codex_hook_health_accepts_file_symlink_referent_through_junction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logical = tmp_path / "home" / ".codex" / "hooks.json"
    real_root = tmp_path / "real-env"
    resolved = real_root / "Agents" / ".codex" / "hooks.json"
    resolved.parent.mkdir(parents=True)
    resolved.write_text('{}\n', encoding="utf-8")
    junction = tmp_path / "env"
    _make_directory_junction(junction, real_root)
    referent_through_junction = junction / "Agents" / ".codex" / "hooks.json"
    _make_file_symlink(logical, referent_through_junction)
    file_link_target = os.readlink(logical)
    rows, records = _host_trust_fixture(logical)
    inventory = resolved.parent / CHECKER.INVENTORY_NAME

    assert CHECKER._codex_inventory_sidecar(logical) == inventory
    CHECKER.write_codex_inventory(
        target=logical,
        specs=[
            (stem, Path(argv[-1]), event, matcher)
            for event, stem, argv, matcher in rows
        ],
        inventory_path=inventory,
        host_os="posix",
    )
    monkeypatch.setattr(CHECKER, "_codex_hooks_list", lambda **_kwargs: records)
    CHECKER.verify_config(
        target=logical,
        platform="codex",
        host_os="posix",
        repo_root=ROOT,
        verify_fires=False,
        inventory_path=inventory,
        codex_trust_mode="require",
        codex_command=[str(Path(sys.executable).resolve())],
        codex_home=logical.parent,
        query_cwd=tmp_path,
    )

    assert logical.is_symlink()
    assert os.readlink(logical) == file_link_target
    assert os.path.isjunction(junction)
    assert inventory.is_file()
    assert not (logical.parent / inventory.name).exists()


def test_codex_hook_junction_authority_rejects_retarget(tmp_path: Path) -> None:
    logical = tmp_path / "home" / ".codex" / "hooks.json"
    first_root = tmp_path / "first-env"
    first = first_root / "Agents" / ".codex" / "hooks.json"
    first.parent.mkdir(parents=True)
    first.write_text('{}\n', encoding="utf-8")
    inventory = first.parent / CHECKER.INVENTORY_NAME
    inventory.write_text('{}\n', encoding="utf-8")
    second_root = tmp_path / "second-env"
    second = second_root / "Agents" / ".codex" / "hooks.json"
    second.parent.mkdir(parents=True)
    second.write_text('{}\n', encoding="utf-8")
    junction = tmp_path / "env"
    _make_directory_junction(junction, first_root)
    _make_file_symlink(
        logical,
        junction / "Agents" / ".codex" / "hooks.json",
    )
    authority = CHECKER._inventory_authority(
        logical, inventory, for_write=False
    )

    junction.rmdir()
    _make_directory_junction(junction, second_root)

    with pytest.raises(ValueError, match="^E_HOOK_INVENTORY_TARGET_INVALID"):
        CHECKER._recheck_inventory_authority(authority, for_write=False)
    assert logical.is_symlink()
    assert os.path.isjunction(junction)
    assert first.is_file() and second.is_file()


@pytest.mark.parametrize("case", ("dangling", "cycle", "opaque"))
def test_codex_hook_junction_rejects_invalid_component_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    logical = tmp_path / "home" / ".codex" / "hooks.json"
    if case == "cycle":
        real_root = tmp_path / "cycle-root"
        real_root.mkdir()
        junction = real_root / "loop"
        _make_directory_junction(junction, real_root)
        _make_file_symlink(logical, junction / "loop" / "hooks.json")
    else:
        real_root = tmp_path / "real-env"
        resolved = real_root / "Agents" / ".codex" / "hooks.json"
        resolved.parent.mkdir(parents=True)
        resolved.write_text('{}\n', encoding="utf-8")
        junction = tmp_path / "env"
        _make_directory_junction(junction, real_root)
        _make_file_symlink(
            logical,
            junction / "Agents" / ".codex" / "hooks.json",
        )
        if case == "dangling":
            real_root.rename(tmp_path / "moved-env")
        else:
            monkeypatch.setattr(
                CHECKER.os.path,
                "isjunction",
                lambda _path: False,
            )

    with pytest.raises(ValueError, match="^E_HOOK_INVENTORY_TARGET_INVALID"):
        CHECKER._codex_inventory_sidecar(logical)


def test_codex_hook_symlink_authority_rejects_resolved_replacement_and_retarget(
    tmp_path: Path,
) -> None:
    logical = tmp_path / "home" / ".codex" / "hooks.json"
    first = tmp_path / "first" / "hooks.json"
    first.parent.mkdir()
    first.write_text('{}\n', encoding="utf-8")
    _make_file_symlink(logical, first)
    inventory = first.parent / CHECKER.INVENTORY_NAME
    inventory.write_text('{}\n', encoding="utf-8")
    initial = CHECKER._inventory_authority(logical, inventory, for_write=False)

    replacement = first.with_name("replacement.json")
    replacement.write_text('{}\n', encoding="utf-8")
    os.replace(replacement, first)
    with pytest.raises(ValueError, match="^E_HOOK_INVENTORY_TARGET_INVALID"):
        CHECKER._recheck_inventory_authority(initial, for_write=False)

    current = CHECKER._inventory_authority(logical, inventory, for_write=False)
    second = tmp_path / "second" / "hooks.json"
    second.parent.mkdir()
    second.write_text('{}\n', encoding="utf-8")
    logical.unlink()
    _make_file_symlink(logical, second)
    with pytest.raises(ValueError, match="^E_HOOK_INVENTORY_TARGET_INVALID"):
        CHECKER._recheck_inventory_authority(current, for_write=False)


@pytest.mark.parametrize("case", ("dangling", "directory", "loop"))
def test_codex_hook_symlink_rejects_invalid_final_target(
    tmp_path: Path, case: str
) -> None:
    logical = tmp_path / "home" / ".codex" / "hooks.json"
    if case == "dangling":
        _make_file_symlink(logical, tmp_path / "missing" / "hooks.json")
    elif case == "directory":
        directory = tmp_path / "directory"
        directory.mkdir()
        _make_file_symlink(logical, directory)
    else:
        other = tmp_path / "other.json"
        _make_file_symlink(logical, other)
        _make_file_symlink(other, logical)

    with pytest.raises(ValueError, match="^E_HOOK_INVENTORY_TARGET_INVALID"):
        CHECKER._codex_inventory_sidecar(logical)


def test_codex_hook_inventory_exact_parent_negative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F4: only the exact ordinary sibling of hooks.json can carry authority."""

    config_root = tmp_path / "codex-home"
    config_root.mkdir()
    target = config_root / "hooks.json"
    rows, records = _host_trust_fixture(target)
    specs = [
        (stem, Path(argv[-1]), event, matcher)
        for event, stem, argv, matcher in rows
    ]
    exact = target.parent / CHECKER.INVENTORY_NAME
    CHECKER.write_codex_inventory(
        target=target,
        specs=specs,
        inventory_path=exact,
        host_os="posix",
    )
    monkeypatch.setattr(CHECKER, "_codex_hooks_list", lambda **_kwargs: records)
    before_target = target.read_bytes()
    before_inventory = exact.read_bytes()

    CHECKER.verify_config(
        target=target,
        platform="codex",
        host_os="posix",
        repo_root=ROOT,
        verify_fires=False,
        inventory_path=exact,
        codex_trust_mode="require",
        codex_command=[str(Path(sys.executable).resolve())],
        codex_home=config_root,
        query_cwd=tmp_path,
    )

    outside = tmp_path / "outside" / CHECKER.INVENTORY_NAME
    outside.parent.mkdir()
    outside.write_bytes(before_inventory)
    alternate = target.parent / "alternate-inventory.json"
    alternate.write_bytes(before_inventory)
    for candidate in (outside, alternate):
        with pytest.raises(ValueError, match="^E_HOOK_INVENTORY_TARGET_INVALID"):
            CHECKER.verify_config(
                target=target,
                platform="codex",
                host_os="posix",
                repo_root=ROOT,
                verify_fires=False,
                inventory_path=candidate,
            )

    exact.unlink()
    try:
        exact.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")
    with pytest.raises(ValueError, match="^E_HOOK_INVENTORY_TARGET_INVALID"):
        CHECKER.verify_config(
            target=target,
            platform="codex",
            host_os="posix",
            repo_root=ROOT,
            verify_fires=False,
            inventory_path=exact,
        )
    assert target.read_bytes() == before_target
    assert outside.read_bytes() == before_inventory


def test_codex_inventory_writer_rejects_outside_parent_without_mutation(
    tmp_path: Path,
) -> None:
    """F4: the write branch applies the same exact-parent no-reparse authority."""

    target = tmp_path / "codex-home" / "hooks.json"
    target.parent.mkdir()
    rows, _records = _host_trust_fixture(target)
    outside = tmp_path / "outside" / CHECKER.INVENTORY_NAME
    outside.parent.mkdir()
    with pytest.raises(ValueError, match="^E_HOOK_INVENTORY_TARGET_INVALID"):
        CHECKER.write_codex_inventory(
            target=target,
            specs=[
                (stem, Path(argv[-1]), event, matcher)
                for event, stem, argv, matcher in rows
            ],
            inventory_path=outside,
            host_os="posix",
        )
    assert not outside.exists()


def test_codex_inventory_rejects_reparse_target_parent(
    tmp_path: Path,
) -> None:
    """F4: lexical target-parent identity cannot be supplied through a reparse."""

    actual = tmp_path / "actual-home"
    alias = tmp_path / "alias-home"
    actual.mkdir()
    try:
        alias.symlink_to(actual, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    target = alias / "hooks.json"
    rows, _records = _host_trust_fixture(target)
    inventory = alias / CHECKER.INVENTORY_NAME
    with pytest.raises(ValueError, match="^E_HOOK_INVENTORY_TARGET_INVALID"):
        CHECKER.write_codex_inventory(
            target=target,
            specs=[
                (stem, Path(argv[-1]), event, matcher)
                for event, stem, argv, matcher in rows
            ],
            inventory_path=inventory,
            host_os="posix",
        )


def test_post_reclaim_installed_helper_trusted_and_modified_smoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "codex-home" / "hooks.json"
    target.parent.mkdir()
    rows, records = _host_trust_fixture(target)
    installed_scripts = tmp_path / "codex-home" / "skills" / "lead" / "scripts"
    installed_scripts.mkdir(parents=True)
    installed_helper = installed_scripts / "check-hook-health.py"
    shutil.copy2(CHECKER_PATH, installed_helper)
    inventory = target.parent / "codex-hook-inventory.json"
    CHECKER.write_codex_inventory(
        target=target,
        specs=[(stem, Path(argv[-1]), event, matcher) for event, stem, argv, matcher in rows],
        inventory_path=inventory,
        host_os="posix",
    )
    assert not list(installed_scripts.glob("*.sh"))
    spec = importlib.util.spec_from_file_location("installed_hook_health_smoke", installed_helper)
    assert spec and spec.loader
    installed = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = installed
    spec.loader.exec_module(installed)
    monkeypatch.setattr(installed, "_codex_hooks_list", lambda **_kwargs: records)
    trusted = installed.verify_config(
        target=target, platform="codex", host_os="posix", repo_root=tmp_path,
        verify_fires=False, inventory_path=inventory, codex_trust_mode="require",
        codex_command=[str(Path(sys.executable).resolve())],
        codex_home=target.parent, query_cwd=tmp_path,
    )
    assert sum(message.startswith("PASS CODEX_HOOK_TRUST_TRUSTED") for message in trusted) == len(rows)
    touched = installed.canonical_identity(
        rows[0][0], rows[0][2], "posix", matcher=rows[0][3], source_path=target
    )
    records[0]["trustStatus"] = "modified"
    report = installed.verify_config(
        target=target, platform="codex", host_os="posix", repo_root=tmp_path,
        verify_fires=False, inventory_path=inventory, codex_trust_mode="report",
        touched_identities={touched}, codex_command=[str(Path(sys.executable).resolve())],
        codex_home=target.parent, query_cwd=tmp_path,
    )
    assert any(message.startswith("PENDING_MANUAL_TRUST") for message in report)


@pytest.mark.parametrize(
    "stdout",
    (
        '{"id":1,"error":{"code":-1,"message":"no"}}\n'
        '{"id":2,"result":{"data":[]}}\n',
        '{"id":1,"result":{}}\n'
        '{"id":2,"error":{"code":-1,"message":"no"}}\n',
        '{"id":1,"result":[]}\n',
    ),
)
def test_jsonrpc_error_and_malformed_envelopes_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    process = _FakeAppServer(stdout)
    monkeypatch.setattr(CHECKER.subprocess, "Popen", lambda *_a, **_kw: process)
    with pytest.raises(ValueError, match="PROTOCOL_ERROR|MALFORMED"):
        CHECKER._codex_hooks_list(
            codex_command=[str(Path(sys.executable).resolve())],
            codex_home=tmp_path / "home",
            query_cwd=tmp_path,
        )
    assert process.terminated
    assert process.stdin.closed and process.stdout.closed and process.stderr.closed


@pytest.mark.parametrize(
    "stdout",
    (
        "x" * (CHECKER.MAX_STDOUT_LINE_BYTES + 1),
        "".join('{"method":"notice"}\n' for _ in range(CHECKER.MAX_STDOUT_MESSAGES + 1)),
    ),
    ids=("oversized-line", "message-flood"),
)
def test_app_server_stdout_bounds_fail_closed_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    process = _FakeAppServer(stdout)
    monkeypatch.setattr(CHECKER.subprocess, "Popen", lambda *_a, **_kw: process)
    with pytest.raises(ValueError, match="CODEX_HOOK_LIST_BOUNDS"):
        CHECKER._codex_hooks_list(
            codex_command=[str(Path(sys.executable).resolve())],
            codex_home=tmp_path / "home",
            query_cwd=tmp_path,
            timeout=0.5,
        )
    assert process.terminated
    assert process.stdin.closed and process.stdout.closed and process.stderr.closed


def test_started_app_server_nonzero_exit_is_reaped_and_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = _FakeAppServer("", returncode=7)
    monkeypatch.setattr(CHECKER.subprocess, "Popen", lambda *_a, **_kw: process)
    with pytest.raises(ValueError, match="CODEX_HOOK_LIST_UNAVAILABLE"):
        CHECKER._codex_hooks_list(
            codex_command=[str(Path(sys.executable).resolve())],
            codex_home=tmp_path / "home",
            query_cwd=tmp_path,
        )
    assert process.wait_calls == 1
    assert process.stdin.closed and process.stdout.closed and process.stderr.closed


def test_hook_health_read_only_trust_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "hooks.json"
    _rows, records = _host_trust_fixture(target)
    config_before = target.read_bytes()
    host_before = json.dumps(records, sort_keys=True).encode("utf-8")
    monkeypatch.setattr(CHECKER, "_codex_hooks_list", lambda **_kwargs: records)
    CHECKER.verify_config(
        target=target,
        platform="codex",
        host_os="posix",
        repo_root=ROOT,
        verify_fires=False,
        codex_trust_mode="require",
        codex_command=[str(Path(sys.executable).resolve())],
        codex_home=tmp_path / "home",
        query_cwd=tmp_path,
    )
    assert target.read_bytes() == config_before
    assert json.dumps(records, sort_keys=True).encode("utf-8") == host_before


def test_installed_require_derives_target_sidecar_and_ignores_helper_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "codex-home" / "hooks.json"
    target.parent.mkdir()
    rows, records = _host_trust_fixture(target)
    scripts = target.parent / "skills" / "lead" / "scripts"
    scripts.mkdir(parents=True)
    helper = scripts / "check-hook-health.py"
    shutil.copy2(CHECKER_PATH, helper)
    inventory = target.parent / CHECKER.INVENTORY_NAME
    CHECKER.write_codex_inventory(
        target=target,
        specs=[(stem, Path(argv[-1]), event, matcher) for event, stem, argv, matcher in rows],
        inventory_path=inventory,
        host_os="posix",
    )
    stale_inventory = scripts / CHECKER.INVENTORY_NAME
    stale_inventory.write_text("stale", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("installed_inventory_default", helper)
    assert spec and spec.loader
    installed = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = installed
    spec.loader.exec_module(installed)
    monkeypatch.setattr(installed, "_codex_hooks_list", lambda **_kwargs: records)
    arguments = [
        str(helper),
        "--target", str(target),
        "--platform", "codex",
        "--host-os", "posix",
        "--codex-trust-mode", "require",
        "--codex-command-json", json.dumps([str(Path(sys.executable).resolve())]),
        "--codex-home", str(target.parent),
        "--query-cwd", str(tmp_path),
        "--repo-root", str(ROOT),
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    assert installed.main() == 0
    inventory.unlink()
    assert installed.main() == 1


def test_real_inventory_probe_still_requires_a_codex_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_BIN", str(tmp_path / "missing-codex"))
    with pytest.raises(ValueError, match="CODEX_HOOK_LIST_UNAVAILABLE"):
        CHECKER._codex_hooks_list(
            codex_command=None, codex_home=tmp_path, query_cwd=tmp_path,
        )
