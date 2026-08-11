"""Python runtime-profile, reclaim, and direct-hook contract tests."""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts/install-hypothesis-hook.py"
PRODUCTION_INSTALLER_PATH = ROOT / "scripts/production_installer.py"
INFORMATIONAL_REMINDER_HOOK_STEMS = frozenset(
    {
        "agents-mode-reminder",
        "check-scratch-valuables",
        "mcp-usage-reminder",
        "turn-anchor-reminder",
    }
)
CWD_SCANNING_HOOK_STEMS = frozenset({"check-scratch-valuables"})
CANONICAL_TRUST_GUIDANCE = (
    "After reinstall, start interactive `codex` — not `codex exec` — and choose **Trust all and continue** for all 12 affected entries.",
    "Do not press Esc and do not choose **`Continue without trusting`**, because all hooks and guards remain installed but inactive.",
    "`codex exec` silently skips untrusted hook entries instead of showing the trust prompt, so interactive `codex` must run first.",
    "The trust modal does not time out and the operator must review all 12 entries before making the explicit choice.",
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
def _provider_source_root(platform: str) -> Path:
    return ROOT / (
        "src.codex/skills/lead" if platform == "codex" else "src.claude/agents"
    )


def _owned_python_targets(platform: str) -> tuple[Path, ...]:
    return tuple(
        script
        for _marker, script, _event, _matcher in PRODUCTION_INSTALLER._hook_specs(
            platform, _provider_source_root(platform)
        )
    )


@pytest.mark.parametrize(("platform", "expected_count"), (("codex", 12), ("claude", 13)))
def test_hook_specs_membership_is_owned_by_universal_manifest(
    platform: str, expected_count: int
) -> None:
    manifest = PRODUCTION_INSTALLER._universal_hook_manifest_module()
    stems = tuple(
        marker
        for marker, _script, _event, _matcher in PRODUCTION_INSTALLER._hook_specs(
            platform, _provider_source_root(platform)
        )
    )
    assert len(stems) == expected_count
    assert set(stems) == manifest.registered_hook_stems(platform)


def test_hook_specs_follow_manifest_membership_and_fail_closed_on_missing_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        PRODUCTION_INSTALLER,
        "_universal_hook_manifest_module",
        lambda: SimpleNamespace(
            registered_hook_stems=lambda _platform: frozenset({"mcp-usage-reminder"})
        ),
    )
    specs = PRODUCTION_INSTALLER._hook_specs("codex", _provider_source_root("codex"))
    assert [marker for marker, *_rest in specs] == ["mcp-usage-reminder"]

    monkeypatch.setattr(
        PRODUCTION_INSTALLER,
        "_universal_hook_manifest_module",
        lambda: SimpleNamespace(
            registered_hook_stems=lambda _platform: frozenset({"missing-owner"})
        ),
    )
    with pytest.raises(RuntimeError, match="metadata is missing"):
        PRODUCTION_INSTALLER._hook_specs("codex", _provider_source_root("codex"))


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
    reclaim = source.index('"reclaim"')
    assert preflight < sync < register < verify < reclaim
    assert '"--codex-trust-mode"' in source and '"report"' in source
    assert "owned_canonical_identities" in source
    assert "write_codex_inventory" in source
    assert "post-reclaim installed hook verification failed" in source


def test_hook_health_runtime_and_inventory_are_codex_only() -> None:
    assert "check-hook-health.py" not in PRODUCTION_INSTALLER.RUNTIME_HELPERS
    assert PRODUCTION_INSTALLER.CODEX_RUNTIME_HELPERS == ("check-hook-health.py",)
    source = inspect.getsource(PRODUCTION_INSTALLER.install)
    assert 'if provider == "codex":' in source
    assert "CODEX_RUNTIME_HELPERS" in source
    assert "codex-hook-inventory.json" not in " ".join(PRODUCTION_INSTALLER.RUNTIME_HELPERS)


def test_installer_derives_touched_identities_from_before_after_hooks_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registration = tmp_path / ".codex" / "hooks.json"
    registration.parent.mkdir()
    registration.write_text('{"hooks":{}}\n', encoding="utf-8")
    installed_root = tmp_path / ".agents" / "skills" / "lead"
    specs = PRODUCTION_INSTALLER._hook_specs("codex", installed_root)
    before = {"unchanged-complete-identity", "matcher-old-complete-identity"}
    after = {"unchanged-complete-identity", "matcher-new-complete-identity"}

    class FakeHealth:
        calls = 0
        generated = False
        @classmethod
        def resolve_codex_command(cls, _value):
            return [str(Path(sys.executable).resolve())]
        @classmethod
        def _manifest_stems(cls, _root, _platform):
            return {marker for marker, *_rest in specs}
        @classmethod
        def owned_canonical_identities(cls, **_kwargs):
            cls.calls += 1
            return before if cls.calls == 1 else after
        @classmethod
        def write_codex_inventory(cls, **_kwargs):
            cls.generated = True

    invocations: list[list[str]] = []
    monkeypatch.setattr(PRODUCTION_INSTALLER, "_hook_health_module", lambda _root: FakeHealth)
    monkeypatch.setattr(
        PRODUCTION_INSTALLER,
        "_run",
        lambda arguments, _cwd, **_kwargs: invocations.append(arguments)
        or SimpleNamespace(returncode=0),
    )
    PRODUCTION_INSTALLER._install_hooks(
        ROOT, "codex", registration, installed_root, "target"
    )
    health_calls = [call for call in invocations if "--codex-trust-mode" in call]
    assert len(health_calls) == 2
    for call in health_calls:
        touched = [call[index + 1] for index, token in enumerate(call) if token == "--touched-identity"]
        assert touched == ["matcher-new-complete-identity"]
    assert FakeHealth.generated



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
    target = HELPER.resolve_hook_target(str(source), "windows", platform)
    assert Path(target.executable) == Path(sys.executable).resolve()
    assert len(target.args) == 1
    assert Path(target.args[0]) == source.resolve()
    assert target.args[0].endswith(".py")


@pytest.mark.parametrize("platform", ("codex", "claude"))
def test_registered_hook_inventory_has_python_as_sole_owner(platform: str) -> None:
    targets = _owned_python_targets(platform)
    assert targets
    assert all(target.suffix == ".py" and target.is_file() for target in targets)
    assert all(not target.with_suffix(".sh").exists() for target in targets)


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
