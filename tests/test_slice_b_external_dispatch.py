from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESOLVER_PATH = ROOT / "scripts" / "resolve-agents-mode.py"
sys.path.insert(0, str(ROOT / "scripts"))
import production_installer as installer  # noqa: E402


def _load_resolver():
    spec = importlib.util.spec_from_file_location(
        "slice_b_external_dispatch_resolver", RESOLVER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RESOLVER = _load_resolver()


def _install_dispatch_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pack: str,
    mode: str,
) -> tuple[Path, Path, Path, Path]:
    install_root = tmp_path / f"installed-{pack}-{mode}"
    install_root.mkdir()
    arguments = ["--force", "--no-hypothesis-hook"]
    if mode == "project":
        arguments.extend(["--target", str(install_root), "--allow-unsafe-target"])
        project_root = install_root
        home = tmp_path / f"clean-home-{pack}"
        home.mkdir()
    else:
        monkeypatch.setenv("USERPROFILE", str(install_root))
        monkeypatch.setenv("HOME", str(install_root))
        arguments.append("--global")
        project_root = tmp_path / f"clean-project-{pack}"
        project_root.mkdir()
        home = install_root

    assert installer.install(pack, arguments) == 0
    if pack == "codex":
        policy_root = install_root / ".agents" / "skills" / "lead"
    else:
        policy_root = install_root / ".claude" / "agents"
    resolver = policy_root / "scripts" / "resolve-agents-mode.py"
    return resolver, policy_root, project_root, home


def _run_installed_external_dispatch(
    resolver: Path,
    *,
    provider: str,
    task_class: str,
    role: str,
    project_root: Path,
    home: Path,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(resolver),
            "--provider",
            provider,
            "--project-root",
            str(project_root),
            "--home",
            str(home),
            "--resolve-external-dispatch",
            "--task-class",
            task_class,
            "--role",
            role,
            "--json",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _make_runtime_directory_link(logical: Path, backing: Path, kind: str) -> None:
    logical.parent.mkdir(parents=True, exist_ok=True)
    if kind == "symlink":
        logical.symlink_to(backing, target_is_directory=True)
        return
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(logical), str(backing)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        pytest.skip(f"directory junction unavailable: {result.stdout}{result.stderr}")


def _canonical_sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def test_legacy_resolution_unchanged_and_auto_excludes_new_providers() -> None:
    schema_path = ROOT / "shared" / "agents-mode.schema.json"
    defaults_path = ROOT / "shared" / "agents-mode.defaults.yaml"
    presets_path = ROOT / "shared" / "agents-mode.presets.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    scalar = {record["name"]: record for record in schema["scalarKeys"]}

    assert schema["productionAutoProviders"] == ["codex", "claude"]
    assert schema["exampleOnlyProviders"] == []
    assert schema["explicitOnlyProviders"] == ["kimi", "grok"]
    assert scalar["externalProvider"]["allowed"] == [
        "auto",
        "codex",
        "claude",
        "kimi",
        "grok",
    ]
    assert _canonical_sha(schema["priorityProfiles"]) == (
        "435c3646a5ff9c36bc5b4483d1a04ae7fb8f8ffde51dc5795e2c2918d22f7956"
    )
    assert hashlib.sha256(presets_path.read_bytes()).hexdigest() == (
        "221a9b4fef1cdc0bef6109dc0f4305a0344fb6b0553057ce80c628df65122077"
    )
    array_lines = "\n".join(
        line
        for line in defaults_path.read_text(encoding="utf-8").splitlines()
        if ": [" in line
    ).encode()
    assert hashlib.sha256(array_lines).hexdigest() == (
        "b44947bc07123e967c5a165a255dd23308ddd025c183ecb88cb0ec5c1f21d735"
    )
    assert "kimi" not in json.dumps(schema["priorityProfiles"])
    assert "grok" not in json.dumps(schema["priorityProfiles"])
    assert set(RESOLVER.PROVIDER_DIRS) == {"codex", "claude"}
    assert RESOLVER.REMOVED_EXTERNAL_PROVIDERS == {"gemini", "qwen"}


@pytest.mark.parametrize(
    ("provider", "expected_status", "execution_authorized"),
    (
        ("kimi", "external-authorized", True),
        ("grok", "unavailable", False),
    ),
)
@pytest.mark.parametrize(
    ("task_class", "role"),
    (
        ("exploration", "analyst"),
        ("planning", "planner"),
        ("review", "qa-engineer"),
    ),
)
def test_external_dispatch_projects_provider_execution_disposition(
    provider: str,
    expected_status: str,
    execution_authorized: bool,
    task_class: str,
    role: str,
) -> None:
    decision = RESOLVER.resolve_external_dispatch(
        provider, task_class, role, repo_root=ROOT
    )
    expected_native_effort = "unsupported" if provider == "kimi" else "high"
    expected_loss = (
        "no-native-effort-control"
        if provider == "kimi"
        else "none"
    )

    assert decision == {
        "schemaVersion": 1,
        "status": expected_status,
        "stableId": None,
        "provider": provider,
        "taskClass": task_class,
        "role": role,
        "requiredModelTier": "balanced",
        "requiredEffort": "high",
        "mutationClass": "read-only",
        "nativeEffort": expected_native_effort,
        "effortMappingLoss": expected_loss,
        "finalAuthorizingRole": False,
        "executionAuthorized": execution_authorized,
        "independentVerification": True,
        "fallback": "none",
    }


@pytest.mark.parametrize("provider", ("kimi", "grok"))
@pytest.mark.parametrize(
    ("task_class", "role"),
    (
        ("micro", "mechanical-scout"),
        ("mechanical-read", "mechanical-scout"),
        ("mechanical", "mechanical-worker"),
        ("engineering", "worker"),
        ("critical-design", "architect"),
        ("critical-security", "security-reviewer"),
        ("recovery", "worker"),
        ("review", "worker"),
        ("unknown", "analyst"),
    ),
)
def test_external_dispatch_denies_every_unadmitted_task_or_role(
    provider: str, task_class: str, role: str
) -> None:
    decision = RESOLVER.resolve_external_dispatch(
        provider, task_class, role, repo_root=ROOT
    )
    assert decision["status"] == "denied"
    assert decision["stableId"] == f"E_{provider.upper()}_DISPATCH_DENIED"
    assert decision["executionAuthorized"] is False
    assert decision["fallback"] == "none"


def test_external_dispatch_denies_unsupported_provider_and_native_is_unchanged() -> None:
    denied = RESOLVER.resolve_external_dispatch(
        "codex", "exploration", "analyst", repo_root=ROOT
    )
    assert denied["status"] == "denied"
    assert denied["stableId"] == "E_EXTERNAL_DISPATCH_DENIED"
    assert denied["executionAuthorized"] is False

    assert RESOLVER.resolve_role_dispatch(
        "mechanical-read", "mechanical-scout", "enabled", repo_root=ROOT
    ) == {
        "schemaVersion": 1,
        "status": "native-required",
        "stableId": None,
        "taskClass": "mechanical-read",
        "role": "mechanical-scout",
        "requestedProfile": "luna-high",
        "requestedModel": "gpt-5.6-luna",
        "requestedEffort": "high",
        "sandbox": "read-only",
        "fallback": "none",
        "executionContract": json.loads(
            (ROOT / "shared" / "role-routing-policy.v1.json").read_text(encoding="utf-8")
        )["mechanicalExecutionContract"],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("executionDisposition", "unsupported"),
        ("availability", "unknown"),
    ),
)
def test_external_dispatch_fails_closed_on_invalid_execution_realization(
    tmp_path: Path, field: str, value: str
) -> None:
    policy_root = tmp_path / "policy-root"
    policy_path = policy_root / "shared" / "role-routing-policy.v1.json"
    policy_path.parent.mkdir(parents=True)
    policy = json.loads(
        (ROOT / "shared" / "role-routing-policy.v1.json").read_text(encoding="utf-8")
    )
    policy["providerRealizations"]["kimi"][field] = value
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    decision = RESOLVER.resolve_external_dispatch(
        "kimi", "review", "qa-engineer", repo_root=policy_root
    )

    assert decision["status"] == "denied"
    assert decision["stableId"] == "E_KIMI_DISPATCH_DENIED"
    assert decision["executionAuthorized"] is False
    assert decision["independentVerification"] is False
    assert decision["fallback"] == "none"


@pytest.mark.parametrize("provider", ("kimi", "grok"))
@pytest.mark.parametrize("role", ("architecture-reviewer", "security-reviewer"))
def test_external_dispatch_rejects_policy_declared_final_authorizers(
    provider: str, role: str
) -> None:
    decision = RESOLVER.resolve_external_dispatch(
        provider, "review", role, repo_root=ROOT
    )

    assert decision["status"] == "denied"
    assert decision["stableId"] == f"E_{provider.upper()}_FINAL_OWNER_DENIED"
    assert decision["finalAuthorizingRole"] is True
    assert decision["executionAuthorized"] is False
    assert decision["fallback"] == "none"


@pytest.mark.parametrize(
    ("mode", "provider", "task_class", "role"),
    (
        ("project", "kimi", "exploration", "analyst"),
        ("global", "kimi", "exploration", "analyst"),
        ("project", "grok", "review", "qa-engineer"),
        ("global", "grok", "review", "qa-engineer"),
    ),
)
def test_installed_claude_external_dispatch_uses_its_own_policy_root_from_foreign_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    provider: str,
    task_class: str,
    role: str,
) -> None:
    resolver, policy_root, project_root, home = _install_dispatch_layout(
        tmp_path, monkeypatch, "claude", mode
    )
    assert resolver.read_bytes() == RESOLVER_PATH.read_bytes()
    assert resolver.parent.parent == policy_root
    assert (policy_root / "shared" / "role-routing-policy.v1.json").read_bytes() == (
        ROOT / "shared" / "role-routing-policy.v1.json"
    ).read_bytes()

    foreign = tmp_path / f"foreign-claude-{mode}-{provider}"
    foreign.joinpath("shared").mkdir(parents=True)
    foreign.joinpath("shared", "role-routing-policy.v1.json").write_text(
        '{"schemaVersion":0}\n', encoding="utf-8"
    )
    result = _run_installed_external_dispatch(
        resolver,
        provider=provider,
        task_class=task_class,
        role=role,
        project_root=project_root,
        home=home,
        cwd=foreign,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == RESOLVER.resolve_external_dispatch(
        provider, task_class, role, repo_root=ROOT
    )


@pytest.mark.parametrize("mode", ("project", "global"))
def test_installed_codex_external_dispatch_retains_policy_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    resolver, _policy_root, project_root, home = _install_dispatch_layout(
        tmp_path, monkeypatch, "codex", mode
    )
    foreign = tmp_path / f"foreign-codex-{mode}"
    foreign.mkdir()
    result = _run_installed_external_dispatch(
        resolver,
        provider="kimi",
        task_class="exploration",
        role="analyst",
        project_root=project_root,
        home=home,
        cwd=foreign,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == RESOLVER.resolve_external_dispatch(
        "kimi", "exploration", "analyst", repo_root=ROOT
    )


@pytest.mark.parametrize(
    "kind",
    ("ordinary", "symlink", "junction")
    if os.name == "nt"
    else ("ordinary", "symlink"),
)
def test_installed_global_codex_external_dispatch_accepts_declared_agents_root(
    tmp_path: Path,
    kind: str,
) -> None:
    home = tmp_path / f"home-{kind}"
    home.mkdir()
    project_root = tmp_path / f"project-{kind}"
    project_root.mkdir()
    logical_agents = home / ".agents"
    backing_agents = (
        logical_agents if kind == "ordinary" else tmp_path / f"backing-agents-{kind}"
    )
    policy_root = backing_agents / "skills" / "lead"
    scripts = policy_root / "scripts"
    shared = policy_root / "shared"
    scripts.mkdir(parents=True)
    shared.mkdir()
    scripts.joinpath("resolve-agents-mode.py").write_bytes(RESOLVER_PATH.read_bytes())
    scripts.joinpath("linked_runtime_subroots.py").write_bytes(
        (ROOT / "scripts" / "linked_runtime_subroots.py").read_bytes()
    )
    shared.joinpath("role-routing-policy.v1.json").write_bytes(
        (ROOT / "shared" / "role-routing-policy.v1.json").read_bytes()
    )
    if kind != "ordinary":
        redirect_agents = tmp_path / f"redirect-agents-{kind}"
        try:
            _make_runtime_directory_link(redirect_agents, backing_agents, kind)
            _make_runtime_directory_link(logical_agents, redirect_agents, kind)
        except OSError as exc:
            pytest.skip(f"directory {kind} unavailable: {exc}")
    resolver = logical_agents / "skills" / "lead" / "scripts" / "resolve-agents-mode.py"

    result = _run_installed_external_dispatch(
        resolver,
        provider="kimi",
        task_class="review",
        role="qa-engineer",
        project_root=project_root,
        home=home,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    decision = json.loads(result.stdout)
    assert decision["status"] == "external-authorized"
    assert decision["stableId"] is None
    assert decision["executionAuthorized"] is True
    assert decision["fallback"] == "none"


def test_installed_external_dispatch_rejects_absent_anchor(
    tmp_path: Path,
) -> None:
    policy_root = tmp_path / "standalone" / "agents"
    scripts = policy_root / "scripts"
    scripts.mkdir(parents=True)
    resolver = scripts / "resolve-agents-mode.py"
    resolver.write_bytes(RESOLVER_PATH.read_bytes())
    shared = policy_root / "shared"
    shared.mkdir()
    shared.joinpath("role-routing-policy.v1.json").write_bytes(
        (ROOT / "shared" / "role-routing-policy.v1.json").read_bytes()
    )
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    project_root.mkdir()
    home.mkdir()

    result = _run_installed_external_dispatch(
        resolver,
        provider="kimi",
        task_class="exploration",
        role="analyst",
        project_root=project_root,
        home=home,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    decision = json.loads(result.stdout)
    assert decision["status"] == "denied"
    assert decision["stableId"] == "E_KIMI_DISPATCH_DENIED"
    assert decision["fallback"] == "none"


def test_installed_claude_external_dispatch_rejects_ambiguous_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver, _policy_root, project_root, _home = _install_dispatch_layout(
        tmp_path, monkeypatch, "claude", "project"
    )
    result = _run_installed_external_dispatch(
        resolver,
        provider="kimi",
        task_class="exploration",
        role="analyst",
        project_root=project_root,
        home=project_root,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    decision = json.loads(result.stdout)
    assert decision["status"] == "denied"
    assert decision["stableId"] == "E_KIMI_DISPATCH_DENIED"
    assert decision["fallback"] == "none"


@pytest.mark.parametrize(
    "mutation",
    ("missing-policy", "malformed-policy", "linked-policy", "linked-resolver"),
)
def test_installed_claude_external_dispatch_fails_closed_on_invalid_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    resolver, policy_root, project_root, home = _install_dispatch_layout(
        tmp_path, monkeypatch, "claude", "project"
    )
    policy = policy_root / "shared" / "role-routing-policy.v1.json"
    if mutation == "missing-policy":
        policy.unlink()
    elif mutation == "malformed-policy":
        policy.write_text('{"schemaVersion":0}\n', encoding="utf-8")
    elif mutation == "linked-policy":
        target = tmp_path / "linked-policy.json"
        policy.replace(target)
        try:
            policy.symlink_to(target)
        except OSError as exc:
            pytest.skip(f"file symlink unavailable: {exc}")
    else:
        target = tmp_path / "linked-resolver.py"
        resolver.replace(target)
        try:
            resolver.symlink_to(target)
        except OSError as exc:
            pytest.skip(f"file symlink unavailable: {exc}")

    result = _run_installed_external_dispatch(
        resolver,
        provider="kimi",
        task_class="exploration",
        role="analyst",
        project_root=project_root,
        home=home,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    decision = json.loads(result.stdout)
    assert decision["status"] == "denied"
    assert decision["stableId"] == "E_KIMI_DISPATCH_DENIED"
    assert decision["fallback"] == "none"
