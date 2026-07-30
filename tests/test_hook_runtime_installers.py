"""Python runtime-profile, reclaim, and direct-hook contract tests."""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts/install-hypothesis-hook.py"
PRODUCTION_INSTALLER_PATH = ROOT / "scripts/production_installer.py"
BASH_RUNTIME_PATH = ROOT / "scripts/bash_runtime.py"
PROTECTED = (
    "check-publication-safety.sh",
    "agent-run-ledger.sh",
    "check-work-items-state.sh",
    "validate-work-item-state.sh",
    "invoke-claude-api.sh",
    "custom.sh",
)
STRUCTURED_JSON_HOOK_STEMS = frozenset(
    {
        "agents-mode-reminder",
        "check-bugfix-discipline",
        "check-git-push-gate",
        "check-machine-local-path",
        "check-mcp-momentum",
        "check-no-trash-in-repo",
        "check-passive-polling-stop",
        "check-repository-orientation",
        "check-scratch-valuables",
        "check-stale-relation-residue",
        "check-typed-routing",
        "check-work-items-archival-stop",
        "mcp-usage-reminder",
        "turn-anchor-reminder",
    }
)
INFORMATIONAL_REMINDER_HOOK_STEMS = frozenset(
    {"agents-mode-reminder", "mcp-usage-reminder", "turn-anchor-reminder"}
)
CWD_SCANNING_HOOK_STEMS = frozenset({"check-scratch-valuables"})
CANONICAL_TRUST_GUIDANCE = (
    "After reinstall, start interactive `codex` — not `codex exec` — and choose **Trust all and continue** for all 13 affected entries.",
    "Do not press Esc and do not choose **`Continue without trusting`**, because all hooks and guards remain installed but inactive.",
    "`codex exec` silently skips untrusted hook entries instead of showing the trust prompt, so interactive `codex` must run first.",
    "The trust modal does not time out and the operator must review all 13 entries before making the explicit choice.",
)
BYPASS_TOKENS = (
    "bypass_" + "hook_trust",
    "BYPASS_" + "HOOK_TRUST",
    "dangerously-" + "bypass-hook-trust",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HELPER = _load(HELPER_PATH, "hook_runtime_helper")
PRODUCTION_INSTALLER = _load(
    PRODUCTION_INSTALLER_PATH, "production_installer_runtime_test"
)
BASH_RUNTIME = _load(BASH_RUNTIME_PATH, "bash_runtime_hook_test")


def _provider_source_root(platform: str) -> Path:
    return ROOT / (
        "src.codex/skills/lead" if platform == "codex" else "src.claude/agents"
    )


def _owned_python_targets(platform: str) -> tuple[Path, ...]:
    return tuple(
        sorted(
            {path.with_suffix(".py") for path in HELPER.owned_hook_wrapper_sources(ROOT, platform)}
        )
    )


def _seed_installed_tree(root: Path, platform: str) -> tuple[Path, ...]:
    provider_root = _provider_source_root(platform)
    candidates: list[Path] = []
    for source in HELPER.owned_hook_wrapper_sources(ROOT, platform):
        target = root / source.relative_to(provider_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        shutil.copy2(source.with_suffix(".py"), target.with_suffix(".py"))
        candidates.append(target)
    for name in PROTECTED:
        target = root / "scripts" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("protected\n", encoding="utf-8")
    return tuple(candidates)


def _registration_data(
    candidates: tuple[Path, ...], *, platform: str, wrapper: bool
) -> dict:
    entries: list[dict] = []
    for sample in candidates:
        target = sample if wrapper else sample.with_suffix(".py")
        if platform == "claude":
            command = {
                "type": "command",
                "command": "bash" if wrapper else str(Path(sys.executable).resolve()),
                "args": [str(target.resolve())],
            }
        else:
            executable = "bash" if wrapper else str(Path(sys.executable).resolve())
            command = {
                "type": "command",
                "command": f"{executable} {target.resolve()}",
            }
        entries.append({"hooks": [command]})
    return {"hooks": {"PreToolUse": entries}}


def _parse_structured_stdout(data: bytes) -> object:
    """Require one UTF-8 JSON document plus JSON whitespace only."""
    return json.loads(data.decode("utf-8"))


def _assert_exact_order(text: str, lines: tuple[str, ...]) -> None:
    positions = []
    for line in lines:
        assert text.count(line) == 1, line
        positions.append(text.index(line))
    assert positions == sorted(positions)


def _bypass_is_evidence_only(line: str) -> bool:
    if not any(token in line for token in BYPASS_TOKENS):
        return True
    lowered = line.casefold()
    evidence_markers = (
        "probe",
        "measurement",
        "was passed",
        "ruling out",
        "confirmed",
    )
    enablement_markers = ("run ", "use ", "launch ", "set ", "pass ")
    return any(marker in lowered for marker in evidence_markers) and not any(
        marker in lowered for marker in enablement_markers
    )


def test_python_production_installer_owns_ordered_hook_transaction() -> None:
    source = inspect.getsource(PRODUCTION_INSTALLER._install_hooks)
    preflight = source.index("--test-transaction-preflight")
    sync = source.index('"sync"')
    register = source.index("for marker, script, event, matcher")
    verify = source.index("check-hook-health.py")
    reclaim = source.index("--reclaim-root")
    assert preflight < sync < register < verify < reclaim

    run_source = inspect.getsource(PRODUCTION_INSTALLER.install)
    assert 'args.hook_runtime != "python"' in run_source
    assert "production hooks support only --hook-runtime python" in run_source


@pytest.mark.parametrize(
    ("platform", "source"),
    (
        ("codex", ROOT / "src.codex/skills/lead/scripts/check-bugfix-discipline.py"),
        ("claude", ROOT / "src.claude/agents/scripts/check-bugfix-discipline.py"),
    ),
)
def test_python_target_resolution_is_absolute_and_direct(
    platform: str, source: Path
) -> None:
    target = HELPER.resolve_hook_target(str(source), "windows", "python", platform)
    assert Path(target.executable) == Path(sys.executable).resolve()
    assert len(target.args) == 1
    assert Path(target.args[0]) == source.resolve()
    assert target.args[0].endswith(".py")


@pytest.mark.parametrize("platform", ("codex", "claude"))
def test_owned_production_wrappers_are_posix_only(platform: str) -> None:
    wrappers = HELPER.owned_hook_wrapper_sources(ROOT, platform)
    assert wrappers
    assert all(path.suffix == ".sh" for path in wrappers)
    assert all(path.with_suffix(".py").is_file() for path in wrappers)


@pytest.mark.parametrize("platform", ("codex", "claude"))
def test_profile_verification_exclusions_match_reclaim_inventory(
    platform: str,
) -> None:
    wrappers = HELPER.owned_hook_wrapper_sources(ROOT, platform)
    excluded = HELPER.profile_verification_exclusions(ROOT, platform, "python")
    expected = tuple(
        sorted(
            path.relative_to(ROOT / ("src.codex" if platform == "codex" else "src.claude")).as_posix()
            for path in wrappers
        )
    )
    assert excluded == expected
    assert all(path.endswith(".sh") for path in excluded)
    assert HELPER.profile_verification_exclusions(ROOT, platform, "wrapper") == ()
    assert HELPER.profile_verification_exclusions(ROOT, platform, "native") == ()


@pytest.mark.parametrize("platform", ("codex", "claude"))
def test_reclaim_is_exact_and_idempotent(tmp_path: Path, platform: str) -> None:
    installed = tmp_path / platform
    candidates = _seed_installed_tree(installed, platform)
    assert candidates
    direct = _registration_data(candidates, platform=platform, wrapper=False)

    removed = HELPER.reclaim_stale_hook_wrappers(
        repo_root=ROOT,
        installed_root=installed,
        platform=platform,
        registration_data=direct,
        dry_run=False,
        abort_policy=HELPER.TestAbortPolicy(None, None),
    )
    assert removed == candidates
    assert all(not path.exists() for path in candidates)
    assert (
        HELPER.reclaim_stale_hook_wrappers(
            repo_root=ROOT,
            installed_root=installed,
            platform=platform,
            registration_data=direct,
            dry_run=False,
            abort_policy=HELPER.TestAbortPolicy(None, None),
        )
        == ()
    )


@pytest.mark.parametrize("platform", ("codex", "claude"))
def test_wrapper_registration_disables_reclaim(
    tmp_path: Path, platform: str
) -> None:
    installed = tmp_path / platform
    candidates = _seed_installed_tree(installed, platform)
    wrappers = _registration_data(candidates, platform=platform, wrapper=True)
    assert (
        HELPER.reclaim_stale_hook_wrappers(
            repo_root=ROOT,
            installed_root=installed,
            platform=platform,
            registration_data=wrappers,
            dry_run=False,
            abort_policy=HELPER.TestAbortPolicy(None, None),
        )
        == ()
    )
    assert all(path.is_file() for path in candidates)


@pytest.mark.parametrize("platform", ("codex", "claude"))
def test_reclaim_preserves_non_hook_wrappers(
    tmp_path: Path, platform: str
) -> None:
    installed = tmp_path / platform
    candidates = _seed_installed_tree(installed, platform)
    HELPER.reclaim_stale_hook_wrappers(
        repo_root=ROOT,
        installed_root=installed,
        platform=platform,
        registration_data=_registration_data(
            candidates, platform=platform, wrapper=False
        ),
        dry_run=False,
        abort_policy=HELPER.TestAbortPolicy(None, None),
    )
    assert all(
        (installed / "scripts" / name).read_text(encoding="utf-8")
        == "protected\n"
        for name in PROTECTED
    )


@pytest.mark.parametrize("platform", ("codex", "claude"))
def test_dry_run_reports_exact_set_without_mutation(
    tmp_path: Path, platform: str
) -> None:
    installed = tmp_path / platform
    candidates = _seed_installed_tree(installed, platform)
    removed = HELPER.reclaim_stale_hook_wrappers(
        repo_root=ROOT,
        installed_root=installed,
        platform=platform,
        registration_data=_registration_data(
            candidates, platform=platform, wrapper=False
        ),
        dry_run=True,
        abort_policy=HELPER.TestAbortPolicy(None, None),
    )
    assert removed == candidates
    assert all(path.is_file() for path in candidates)


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_decision_parity_between_posix_launcher_and_python_owner(
    tmp_path: Path, platform: str
) -> None:
    bash = BASH_RUNTIME.resolve_bash()
    if not bash:
        pytest.skip("host-native retained POSIX launcher runtime is unavailable")

    corpus = (b"", b"{malformed\n", b"{}\n")
    owned_stems = {
        wrapper.stem for wrapper in HELPER.owned_hook_wrapper_sources(ROOT, platform)
    }
    assert owned_stems <= STRUCTURED_JSON_HOOK_STEMS
    for python_target in _owned_python_targets(platform):
        wrapper = python_target.with_suffix(".sh")
        assert wrapper.is_file()
        for envelope in corpus:
            wrapped = subprocess.run(
                [str(bash), str(wrapper)],
                cwd=tmp_path,
                input=envelope,
                capture_output=True,
                timeout=60,
            )
            direct = subprocess.run(
                [sys.executable, str(python_target)],
                cwd=tmp_path,
                input=envelope,
                capture_output=True,
                timeout=60,
            )
            assert wrapped.returncode == direct.returncode, python_target
            assert wrapped.stderr == direct.stderr, python_target
            if wrapped.stdout == direct.stdout:
                continue
            assert wrapped.stdout and direct.stdout, python_target
            assert _parse_structured_stdout(wrapped.stdout) == _parse_structured_stdout(
                direct.stdout
            ), python_target


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_hooks_run_from_foreign_cwd(tmp_path: Path, platform: str) -> None:
    foreign_cwds = (tmp_path / "first", tmp_path / "second")
    for cwd in foreign_cwds:
        cwd.mkdir()
    for python_target in _owned_python_targets(platform):
        if python_target.stem in CWD_SCANNING_HOOK_STEMS:
            continue
        runs = [
            subprocess.run(
                [sys.executable, str(python_target)],
                input=b"{}\n",
                capture_output=True,
                cwd=cwd,
                timeout=60,
            )
            for cwd in foreign_cwds
        ]
        root_run, foreign_run = runs
        assert root_run.returncode == foreign_run.returncode, python_target
        assert root_run.stdout == foreign_run.stdout, python_target
        assert root_run.stderr == foreign_run.stderr, python_target


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_direct_invocation_fails_open(tmp_path: Path, platform: str) -> None:
    for python_target in _owned_python_targets(platform):
        for envelope in (b"", b"{malformed\n"):
            completed = subprocess.run(
                [sys.executable, str(python_target)],
                input=envelope,
                capture_output=True,
                cwd=tmp_path,
                timeout=60,
            )
            label = (python_target.stem, envelope)
            assert completed.returncode == 0, label
            assert completed.stderr == b"", label
            if (
                python_target.stem in INFORMATIONAL_REMINDER_HOOK_STEMS
                and completed.stdout
            ):
                _parse_structured_stdout(completed.stdout)
            elif python_target.stem not in INFORMATIONAL_REMINDER_HOOK_STEMS:
                assert completed.stdout == b"", label


def test_decision_parity_oracle_requires_one_utf8_json_document() -> None:
    assert _parse_structured_stdout(b' \t\r\n{"value":1}\r\n') == {"value": 1}
    with pytest.raises(json.JSONDecodeError):
        _parse_structured_stdout(b"{}\n{}")
    with pytest.raises(json.JSONDecodeError):
        _parse_structured_stdout("{}\u00a0".encode())
    with pytest.raises(UnicodeDecodeError):
        _parse_structured_stdout(b'{"value":"\xff"}')


def test_trust_guidance_contract() -> None:
    for path in (ROOT / "INSTALL.md", ROOT / "src.codex/AGENTS.codex.md"):
        _assert_exact_order(path.read_text(encoding="utf-8"), CANONICAL_TRUST_GUIDANCE)

    install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    assert "#### Codex Python workflow" in install
    assert "python .\\scripts\\install-codex.py --global --dry-run" in install
    assert "python .\\scripts\\install-codex.py --global" in install
    assert "install-codex.ps1" not in install


def test_trust_guidance_contract_rejects_same_count_mutations() -> None:
    text = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    mutated = text.replace(
        CANONICAL_TRUST_GUIDANCE[0],
        CANONICAL_TRUST_GUIDANCE[0].replace(
            "Trust all and continue", "Continue without trusting"
        ),
        1,
    )
    with pytest.raises(AssertionError):
        _assert_exact_order(mutated, CANONICAL_TRUST_GUIDANCE)


def test_trust_bypass_classifier_accepts_prohibition_but_rejects_enablement() -> None:
    token = BYPASS_TOKENS[-1]
    assert _bypass_is_evidence_only(
        f"The controlled probe confirmed the flag `{token}` was not needed."
    )
    assert not _bypass_is_evidence_only(
        f"Run `codex {token} exec` to skip the trust prompt."
    )
