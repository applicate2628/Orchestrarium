"""Installer runtime-profile, reclaim, and interruption-safety tests."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts" / "install-hypothesis-hook.py"
INSTALLERS = (
    ROOT / "scripts" / "install-claude.sh",
    ROOT / "scripts" / "install-claude.ps1",
    ROOT / "scripts" / "install-codex.sh",
    ROOT / "scripts" / "install-codex.ps1",
)
PROTECTED = (
    "check-publication-safety.ps1",
    "agent-run-ledger.ps1",
    "check-work-items-state.ps1",
    "validate-work-item-state.ps1",
    "invoke-claude-api.ps1",
    "my-thing.ps1",
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
# Informational hooks that emit their context regardless of stdin, including
# empty and malformed stdin. Silence is NOT their fail-open contract; exiting 0
# without a traceback is. agents-mode-reminder is additionally conditional on
# the resolved delegation mode, so its stdout is allowed to be empty too.
INFORMATIONAL_REMINDER_HOOK_STEMS = frozenset(
    {
        "agents-mode-reminder",
        "mcp-usage-reminder",
        "turn-anchor-reminder",
    }
)
# check-scratch-valuables deliberately scans the working tree it is launched
# in, so its output is cwd-dependent BY CONTRACT and cannot be held to the
# cwd-independence invariant. Verified: it is the only such owned hook.
CWD_SCANNING_HOOK_STEMS = frozenset({"check-scratch-valuables"})


def _load_helper():
    spec = importlib.util.spec_from_file_location("install_hypothesis_hook_runtime", HELPER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HELPER = _load_helper()


def _source_specs(platform: str) -> tuple[tuple[str, Path], ...]:
    if platform == "claude":
        return (
            ("scripts", ROOT / "src.claude" / "agents" / "scripts"),
            ("hooks", ROOT / "src.claude" / "agents" / "hooks"),
        )
    return (
        ("scripts", ROOT / "src.codex" / "skills" / "lead" / "scripts"),
        ("hooks", ROOT / "src.codex" / "skills" / "lead" / "hooks"),
    )


def _seed_installed_tree(root: Path, platform: str) -> tuple[Path, ...]:
    for subdir, source in _source_specs(platform):
        destination = root / subdir
        destination.mkdir(parents=True, exist_ok=True)
        for wrapper in (*source.glob("*.ps1"), *source.glob("*.sh")):
            if wrapper.with_suffix(".py").is_file():
                shutil.copy2(wrapper, destination / wrapper.name)
                shutil.copy2(wrapper.with_suffix(".py"), destination / wrapper.with_suffix(".py").name)
    for name in PROTECTED:
        (root / "scripts" / name).write_text("protected\n", encoding="utf-8")
    return HELPER.reclaimable_hook_wrappers(ROOT, root, platform)


def _registration_data(
    candidates: tuple[Path, ...], *, platform: str, wrapper: bool
) -> dict:
    stems = sorted({candidate.stem for candidate in candidates})
    entries = []
    for stem in stems:
        sample = next(candidate for candidate in candidates if candidate.stem == stem)
        if platform == "claude" and wrapper:
            command = {
                "type": "command",
                "command": "powershell.exe",
                "args": ["-File", str(sample.with_suffix(".ps1"))],
            }
        elif platform == "claude":
            command = {
                "type": "command",
                "command": sys.executable,
                "args": [str(sample.with_suffix(".py"))],
            }
        elif wrapper:
            command = {
                "type": "command",
                "command": (
                    "powershell.exe -NoProfile -ExecutionPolicy Bypass "
                    f"-File {sample.with_suffix('.ps1')}"
                ),
            }
        else:
            command = {
                "type": "command",
                "command": f"{sys.executable} {sample.with_suffix('.py')}",
            }
        entries.append({"hooks": [command]})
    return {"hooks": {"PreToolUse": entries}}


def _registered_script_paths(data: dict) -> tuple[Path, ...]:
    paths: list[Path] = []
    for entry in data["hooks"]["PreToolUse"]:
        hook = entry["hooks"][0]
        if "args" in hook:
            paths.append(Path(hook["args"][-1]))
        else:
            paths.append(Path(shlex.split(hook["command"], posix=False)[-1].strip("'\"")))
    return tuple(paths)


def test_all_four_installers_default_to_python_and_order_transaction() -> None:
    for installer in INSTALLERS:
        text = installer.read_text(encoding="utf-8")
        assert (
            'HOOK_RUNTIME="python"' in text
            or '[string]$HookRuntime = "python"' in text
        ), installer
        assert "--hook-runtime" in text
        sync = text.index("check-bugfix-discipline.py")
        register = text.index("Installing bugfix-discipline")
        verify = text.index("Verifying registered hook targets before reclaiming wrappers")
        reclaim = text.index("Reclaiming owned installed hook wrappers after verification")
        assert sync < register < verify < reclaim, installer


@pytest.mark.parametrize(
    ("platform", "expected_count"),
    (("claude", 28), ("codex", 26)),
)
def test_reclaim_is_exact_and_idempotent(
    tmp_path: Path, platform: str, expected_count: int
) -> None:
    installed = tmp_path / platform
    candidates = _seed_installed_tree(installed, platform)
    assert len(candidates) == expected_count
    direct = _registration_data(candidates, platform=platform, wrapper=False)

    removed = HELPER.reclaim_stale_hook_wrappers(
        repo_root=ROOT,
        installed_root=installed,
        platform=platform,
        registration_data=direct,
        dry_run=False,
        install_scope=HELPER.InstallScope.TARGET,
    )
    assert len(removed) == expected_count
    assert not any(path.exists() for path in removed)
    assert (
        HELPER.reclaim_stale_hook_wrappers(
            repo_root=ROOT,
            installed_root=installed,
            platform=platform,
            registration_data=direct,
            dry_run=False,
            install_scope=HELPER.InstallScope.TARGET,
        )
        == ()
    )


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_wrapper_profile_does_not_reclaim(tmp_path: Path, platform: str) -> None:
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
            install_scope=HELPER.InstallScope.TARGET,
        )
        == ()
    )
    assert all(path.is_file() for path in candidates)


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_reclaim_preserves_non_hook_wrappers(tmp_path: Path, platform: str) -> None:
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
        install_scope=HELPER.InstallScope.TARGET,
    )
    assert all((installed / "scripts" / name).read_text(encoding="utf-8") == "protected\n" for name in PROTECTED)


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_dry_run_reports_exact_set_without_mutation(tmp_path: Path, platform: str) -> None:
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
        install_scope=HELPER.InstallScope.TARGET,
    )
    assert removed == candidates
    assert all(path.is_file() for path in candidates)


@pytest.mark.parametrize(
    ("platform", "expected_count"),
    (("claude", 28), ("codex", 26)),
)
def test_profile_verification_exclusions_are_owned_by_reclaim_inventory(
    platform: str, expected_count: int
) -> None:
    excluded = HELPER.profile_verification_exclusions(ROOT, platform, "python")
    assert len(excluded) == expected_count
    assert all(path.endswith((".ps1", ".sh")) for path in excluded)
    assert len({Path(path).stem for path in excluded}) * 2 == expected_count
    assert HELPER.profile_verification_exclusions(ROOT, platform, "wrapper") == ()
    assert HELPER.profile_verification_exclusions(ROOT, platform, "native") == ()


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_decision_parity_across_runtimes(
    tmp_path: Path, platform: str
) -> None:
    """Thin wrappers and direct Python preserve payloads and verdicts."""
    wrapper_launchers: list[tuple[str, str]] = []
    bash = shutil.which("bash")
    if bash:
        wrapper_launchers.append((".sh", bash))
    if os.name == "nt":
        powershell = (
            shutil.which("pwsh.exe")
            or shutil.which("pwsh")
            or shutil.which("powershell.exe")
            or shutil.which("powershell")
        )
        if powershell:
            wrapper_launchers.append((".ps1", powershell))
    if not wrapper_launchers:
        pytest.skip("no retained wrapper runtime is available")

    corpus = (b"", b"{malformed\n", b"{}\n")
    owned_stems = {
        wrapper.stem for wrapper in HELPER.owned_hook_wrapper_sources(ROOT, platform)
    }
    assert owned_stems <= STRUCTURED_JSON_HOOK_STEMS
    for python_target in sorted(
        {
            wrapper.with_suffix(".py")
            for wrapper in HELPER.owned_hook_wrapper_sources(ROOT, platform)
        }
    ):
        direct_command = [sys.executable, str(python_target)]
        for wrapper_suffix, launcher in wrapper_launchers:
            wrapper = python_target.with_suffix(wrapper_suffix)
            assert wrapper.is_file()
            if wrapper_suffix == ".ps1":
                wrapper_command = [
                    launcher,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(wrapper),
                ]
            else:
                wrapper_command = [launcher, str(wrapper)]
            for envelope in corpus:
                wrapped = subprocess.run(
                    wrapper_command,
                    cwd=tmp_path,
                    input=envelope,
                    capture_output=True,
                    timeout=20,
                )
                direct = subprocess.run(
                    direct_command,
                    cwd=tmp_path,
                    input=envelope,
                    capture_output=True,
                    timeout=20,
                )
                assert wrapped.returncode == direct.returncode, python_target
                assert wrapped.stderr == direct.stderr, python_target
                stem = python_target.stem
                if stem not in STRUCTURED_JSON_HOOK_STEMS:
                    assert wrapped.stdout == direct.stdout, python_target
                    continue
                if wrapped.stdout == direct.stdout == b"":
                    continue
                assert wrapped.stdout and direct.stdout, python_target
                wrapped_payload = _parse_structured_stdout(wrapped.stdout)
                direct_payload = _parse_structured_stdout(direct.stdout)
                assert wrapped_payload == direct_payload, python_target
                canonical_wrapped = json.dumps(
                    wrapped_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                canonical_direct = json.dumps(
                    direct_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                assert canonical_wrapped == canonical_direct, python_target


def _parse_structured_stdout(data: bytes) -> object:
    """Require one UTF-8 JSON document plus JSON whitespace only."""
    return json.loads(data.decode("utf-8"))


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_hooks_run_from_foreign_cwd(tmp_path: Path, platform: str) -> None:
    """I2: unregistering the wrapper introduces no new cwd assumption.

    The wrapper never cd'd, so the direct target must keep seeing the host's
    cwd and must not depend on being launched from its own directory or from
    the repository root. Probed rather than assumed: every owned target except
    the working-tree scanner below is byte-identical across two cwds.
    """
    for python_target in sorted(
        {
            wrapper.with_suffix(".py")
            for wrapper in HELPER.owned_hook_wrapper_sources(ROOT, platform)
        }
    ):
        if python_target.stem in CWD_SCANNING_HOOK_STEMS:
            continue
        runs = []
        for cwd in (ROOT, tmp_path):
            runs.append(
                subprocess.run(
                    [sys.executable, str(python_target)],
                    input=b"{}\n",
                    capture_output=True,
                    cwd=cwd,
                    timeout=60,
                )
            )
        root_run, foreign_run = runs
        assert root_run.returncode == foreign_run.returncode, python_target
        assert root_run.stdout == foreign_run.stdout, python_target
        assert root_run.stderr == foreign_run.stderr, python_target


@pytest.mark.parametrize("platform", ("claude", "codex"))
def test_direct_invocation_fails_open(tmp_path: Path, platform: str) -> None:
    """I3: the fail-open contract survives losing the wrapper that asserted it.

    Empty and malformed stdin must never crash the host. That contract was
    only ever exercised through the .ps1/.sh wrappers, so unregistering them
    orphans it unless it is re-asserted against the target as registered.

    Universal part: exit 0 and no stderr for every owned hook. The stdout half
    splits by hook class -- decision/audit hooks stay silent, the informational
    reminders emit their context regardless of stdin (that is their contract,
    not a fail-open violation).
    """
    for python_target in sorted(
        {
            wrapper.with_suffix(".py")
            for wrapper in HELPER.owned_hook_wrapper_sources(ROOT, platform)
        }
    ):
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
            if python_target.stem in INFORMATIONAL_REMINDER_HOOK_STEMS:
                # Always-emit by contract; only require it stay well-formed.
                if completed.stdout:
                    _parse_structured_stdout(completed.stdout)
            else:
                assert completed.stdout == b"", label


def test_decision_parity_oracle_requires_one_utf8_json_document() -> None:
    assert _parse_structured_stdout(b' \t\r\n{"value":1}\r\n') == {"value": 1}
    with pytest.raises(json.JSONDecodeError):
        _parse_structured_stdout(b"{}\n{}")
    with pytest.raises(json.JSONDecodeError):
        _parse_structured_stdout("{}\u00a0".encode())
    with pytest.raises(UnicodeDecodeError):
        _parse_structured_stdout(b'{"value":"\xff"}')


@dataclass(frozen=True)
class MarkdownNode:
    path: str
    heading_chain: tuple[str, ...]
    block_kind: str
    info_string: str
    visible: bool
    ordinal: int
    normalized_content: str


@dataclass(frozen=True)
class GuidanceBlock:
    path: str
    heading_chain: tuple[str, ...]
    lines: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowBlock:
    path: str
    heading_chain: tuple[str, ...]
    info_string: str
    ordinal: int
    commands: tuple[str, ...]


@dataclass(frozen=True)
class ProvenanceBlock:
    path: str
    heading_chain: tuple[str, ...]
    block_kind: str
    info_string: str
    ordinal: int
    expected_token: str
    role: str
    content_sha256: str


class TrustGuidanceContract:
    """One structural owner for Codex trust guidance and bypass provenance.

    EVERY bypass token in this module is written as a concatenation, never as one
    literal. That is not style -- it is the only way this contract can police the
    file it lives in. `validate` scans every tracked text surface, and since this
    module became tracked it is one of them; a literal token anywhere below would
    be classified against its own rules and reported. Adjacent-literal
    concatenation is resolved at compile time, so every runtime value here is
    byte-identical to the unsplit form: the classifier, the allowlisted
    prohibition line and the synthetic fixtures all behave exactly as before, and
    only the bytes on disk differ. Do not "tidy" any of these back into a single
    literal -- doing so does not weaken the contract, it makes it fail.
    """

    TOKENS = (
        "bypass_" + "hook_trust",
        "BYPASS_" + "HOOK_TRUST",
        "dangerously-" + "bypass-hook-trust",
    )
    CANONICAL_GUIDANCE = (
        "After reinstall, start interactive `codex` — not `codex exec` — and choose **Trust all and continue** for all 13 affected entries.",
        "Do not press Esc and do not choose **`Continue without trusting`**, because all hooks and guards remain installed but inactive.",
        "`codex exec` silently skips untrusted hook entries instead of showing the trust prompt, so interactive `codex` must run first.",
        "The trust modal does not time out and the operator must review all 13 entries before making the explicit choice.",
    )
    GUIDANCE_BLOCKS = (
        GuidanceBlock(
            "INSTALL.md",
            (
                "Installation",
                "Post-install customization",
                "Structural enforcement hooks (auto-installed)",
                "Codex manual trust step",
            ),
            CANONICAL_GUIDANCE,
        ),
        GuidanceBlock(
            "src.codex/AGENTS.codex.md",
            (
                "Codex Platform Rules",
                "Bootstrap — verified premises plus edit/commit checkpoints",
                "Structural enforcement (auto-installed)",
                "Manual trust step required (Codex security model)",
            ),
            CANONICAL_GUIDANCE,
        ),
    )
    WORKFLOW_BLOCKS = (
        WorkflowBlock(
            "INSTALL.md",
            (
                "Installation",
                "Post-install customization",
                "Structural enforcement hooks (auto-installed)",
                "Codex PowerShell workflow",
            ),
            "powershell",
            0,
            (
                r".\scripts\install-codex.ps1 -Global -DryRun",
                r".\scripts\install-codex.ps1 -Global",
                "codex",
                "python scripts/check-hook-health.py --verify-fires",
            ),
        ),
        WorkflowBlock(
            "INSTALL.md",
            (
                "Installation",
                "Post-install customization",
                "Structural enforcement hooks (auto-installed)",
                "Codex Bash workflow",
            ),
            "bash",
            0,
            (
                "bash scripts/install-codex.sh --global --dry-run",
                "bash scripts/install-codex.sh --global",
                "codex",
                "python scripts/check-hook-health.py --verify-fires",
            ),
        ),
    )
    PROVENANCE_BLOCKS = (
        ProvenanceBlock(
            "RELEASE_NOTES.md",
            ("Release Notes", "2026-07-26", "Fixed"),
            "prose",
            "",
            1,
            "--" + "dangerously-" + "bypass-hook-trust",
            "release-history-summary",
            "9d771bb08cf169a069c47156da2f08eb2df578c8f8337d6e1aa08ee471710d38",
        ),
        ProvenanceBlock(
            "references-codex/stop-hook-halting-primitives.md",
            (
                "Stop-Hook Halting Primitives",
                "Measured, Codex line (source + installed-binary evidence, plus a live T-14/T-20 probe below)",
            ),
            "prose",
            "",
            29,
            "--" + "dangerously-" + "bypass-hook-trust",
            "historical-probe-description",
            "27a9b2d58844dcf8768a3c5ed98f33838515c2ddc3ce2cf1e373896b72a6a4c3",
        ),
        ProvenanceBlock(
            "references-codex/stop-hook-halting-primitives.md",
            (
                "Stop-Hook Halting Primitives",
                "Measured, Codex line (source + installed-binary evidence, plus a live T-14/T-20 probe below)",
                "T-20 — a BARE `systemMessage` NOTICE (no `continue`, no `decision`)",
            ),
            "prose",
            "",
            9,
            "--" + "dangerously-" + "bypass-hook-trust",
            "proof-control-item",
            "21e8ca8ab30a8ca64a845dd15af4ff91fa7409fe157f6ed5796da7dbf1d87caa",
        ),
        ProvenanceBlock(
            "references-codex/stop-hook-halting-primitives.md",
            ("Stop-Hook Halting Primitives", "Re-verification"),
            "fence",
            "bash",
            2,
            "--" + "dangerously-" + "bypass-hook-trust",
            "controlled-runnable-probe-command",
            "7f3d179d28fe1dc788053d8d289a777955b43244c2840141b2ea0d6a857a260b",
        ),
        ProvenanceBlock(
            "references-codex/stop-hook-halting-primitives.md",
            ("Stop-Hook Halting Primitives", "Residuals"),
            "prose",
            "",
            3,
            "--" + "dangerously-" + "bypass-hook-trust",
            "tested-configuration-residual",
            "d09a652b5a2525c6580edd93ea2044e060ff0530af5eb02872e72b863235f2d8",
        ),
        ProvenanceBlock(
            "references-codex/ru/stop-hook-halting-primitives.md",
            (
                "Останавливающие примитивы Stop-хука",
                "Измерено, линия Codex (доказательства из исходников и установленного бинарника, плюс живая проба T-14/T-20 ниже)",
            ),
            "prose",
            "",
            37,
            "--" + "dangerously-" + "bypass-hook-trust",
            "historical-probe-description-ru",
            "be8b0c84d2353b792366b51e8c4ae8ed3a1b4b3aa3ef23de255391b775c066cc",
        ),
        ProvenanceBlock(
            "references-codex/ru/stop-hook-halting-primitives.md",
            (
                "Останавливающие примитивы Stop-хука",
                "Измерено, линия Codex (доказательства из исходников и установленного бинарника, плюс живая проба T-14/T-20 ниже)",
                "T-20 — ГОЛЫЙ NOTICE `systemMessage` (без `continue`, без `decision`)",
            ),
            "prose",
            "",
            9,
            "--" + "dangerously-" + "bypass-hook-trust",
            "proof-control-item-ru",
            "92d23a6222a8c8ea327addb85ca457c03fb4d711039b078f39c7533bf353e153",
        ),
        ProvenanceBlock(
            "references-codex/ru/stop-hook-halting-primitives.md",
            ("Останавливающие примитивы Stop-хука", "Как перепроверить"),
            "fence",
            "bash",
            2,
            "--" + "dangerously-" + "bypass-hook-trust",
            "controlled-runnable-probe-command-ru",
            "bcf22b546c557becc7063d170513921748a090399acdf3186b94e749e8db6002",
        ),
        ProvenanceBlock(
            "references-codex/ru/stop-hook-halting-primitives.md",
            ("Останавливающие примитивы Stop-хука", "Остаточные пункты"),
            "prose",
            "",
            3,
            "--" + "dangerously-" + "bypass-hook-trust",
            "tested-configuration-residual-ru",
            "583f421c6a0b5791a8b74fc9ab51f4ec2fc422e4b1966c2c08ded476bf7090aa",
        ),
    )
    PROHIBITION_LINES = frozenset(
        {
            "Do not use `BYPASS_" + "HOOK_TRUST=1`; it disables the trust gate.",
        }
    )
    EXECUTABLE_FENCE_LANGUAGES = frozenset(
        {"bash", "sh", "shell", "powershell", "ps1", "cmd", "bat", "json", "toml", "yaml", "yml"}
    )

    @staticmethod
    def _normalized_line(text: str) -> str:
        return re.sub(r"[ \t\r\f\v]+", " ", text).strip()

    @classmethod
    def _normalized_block(cls, lines: list[str]) -> str:
        return "\n".join(cls._normalized_line(line) for line in lines).strip("\n")

    @staticmethod
    def _node_key(node: MarkdownNode) -> tuple[object, ...]:
        return (
            node.path,
            node.heading_chain,
            node.block_kind,
            node.info_string,
            node.ordinal,
        )

    @classmethod
    def _parse_markdown(cls, path: str, text: str) -> tuple[MarkdownNode, ...]:
        headings: list[str] = []
        ordinals: dict[tuple[tuple[str, ...], str], int] = {}
        nodes: list[MarkdownNode] = []
        fence_marker: str | None = None
        fence_info = ""
        fence_lines: list[str] = []
        fence_heading: tuple[str, ...] = ()
        comment_lines: list[str] | None = None
        comment_heading: tuple[str, ...] = ()

        def emit(
            heading_chain: tuple[str, ...],
            block_kind: str,
            info_string: str,
            visible: bool,
            content_lines: list[str],
        ) -> None:
            ordinal_key = (heading_chain, block_kind)
            ordinal = ordinals.get(ordinal_key, 0)
            ordinals[ordinal_key] = ordinal + 1
            nodes.append(
                MarkdownNode(
                    path,
                    heading_chain,
                    block_kind,
                    info_string,
                    visible,
                    ordinal,
                    cls._normalized_block(content_lines),
                )
            )

        for line_number, line in enumerate(text.splitlines(), start=1):
            if comment_lines is not None:
                comment_lines.append(line)
                if "-->" in line:
                    before, after = line.split("-->", 1)
                    if after.strip():
                        raise AssertionError(
                            f"{path}:{line_number}: content after HTML comment is ambiguous"
                        )
                    comment_lines[-1] = before + "-->"
                    emit(comment_heading, "html_comment", "", False, comment_lines)
                    comment_lines = None
                continue

            if fence_marker is not None:
                if line.strip() == fence_marker:
                    emit(fence_heading, "fence", fence_info, True, fence_lines)
                    fence_marker = None
                    fence_info = ""
                    fence_lines = []
                else:
                    fence_lines.append(line)
                continue

            if "<!--" in line:
                before, after = line.split("<!--", 1)
                if before.strip():
                    raise AssertionError(
                        f"{path}:{line_number}: inline HTML comment is ambiguous"
                    )
                comment_heading = tuple(headings)
                if "-->" in after:
                    body, suffix = after.split("-->", 1)
                    if suffix.strip():
                        raise AssertionError(
                            f"{path}:{line_number}: content after HTML comment is ambiguous"
                        )
                    emit(
                        comment_heading,
                        "html_comment",
                        "",
                        False,
                        ["<!--" + body + "-->"],
                    )
                else:
                    comment_lines = ["<!--" + after]
                continue

            heading = re.fullmatch(r"\s*(#{1,6})\s+(.+?)\s*", line)
            if heading:
                level = len(heading.group(1))
                headings[:] = headings[: level - 1]
                headings.append(heading.group(2))
                continue

            fence = re.fullmatch(r"\s*(`{3,}|~{3,})(.*)", line)
            if fence:
                fence_marker = fence.group(1)
                fence_info = fence.group(2).strip()
                fence_heading = tuple(headings)
                fence_lines = []
                continue

            if line.strip():
                emit(tuple(headings), "prose", "", True, [line])

        if comment_lines is not None:
            raise AssertionError(f"{path}: unterminated HTML comment")
        if fence_marker is not None:
            raise AssertionError(f"{path}: unterminated fenced block")
        return tuple(nodes)

    @classmethod
    def _parse_raw(cls, path: str, text: str) -> tuple[MarkdownNode, ...]:
        return tuple(
            MarkdownNode(path, (), "raw", "", True, ordinal, cls._normalized_line(line))
            for ordinal, line in enumerate(
                (line for line in text.splitlines() if line.strip())
            )
        )

    @classmethod
    def _parse_surfaces(
        cls, surfaces: dict[str, str]
    ) -> dict[str, tuple[MarkdownNode, ...]]:
        required_paths = {
            spec.path
            for spec in (*cls.GUIDANCE_BLOCKS, *cls.WORKFLOW_BLOCKS, *cls.PROVENANCE_BLOCKS)
        }
        required_paths.update(
            path
            for path, text in surfaces.items()
            if any(token in text for token in cls.TOKENS)
        )
        missing = sorted(required_paths - surfaces.keys())
        if missing:
            raise AssertionError("missing trust contract surfaces: " + ", ".join(missing))
        return {
            path: (
                cls._parse_markdown(path, surfaces[path])
                if Path(path).suffix.lower() == ".md"
                else cls._parse_raw(path, surfaces[path])
            )
            for path in sorted(required_paths)
        }

    @classmethod
    def token_inventory(cls, surfaces: dict[str, str]) -> dict[str, int]:
        """Telemetry only; never used to make the security verdict."""
        return {
            path: sum(text.count(token) for token in cls.TOKENS)
            for path, text in surfaces.items()
            if any(token in text for token in cls.TOKENS)
        }

    @classmethod
    def _is_actionable(cls, node: MarkdownNode) -> bool:
        lowered = node.normalized_content.lower()
        action_text = (
            re.sub(r"`[^`]*`", "", lowered)
            if node.block_kind == "prose"
            else lowered
        )
        token_expression = (
            r"(?:bypass_" + r"hook_trust|dangerously-" + r"bypass-hook-trust)"
        )
        assignment = re.search(
            rf"(?:^|[;#\s])(?:export|set)\s+[a-z_]*{token_expression}\s*[:=]",
            action_text,
        ) or re.search(
            rf"(?:\$env:)?[a-z_]*{token_expression}\s*[:=]",
            action_text,
        )
        command = re.search(
            r"\bcodex\s+--dangerously-" + r"bypass-hook-trust\b", action_text
        )
        executable_fence = (
            node.block_kind == "fence"
            and node.info_string.lower() in cls.EXECUTABLE_FENCE_LANGUAGES
        )
        return bool(assignment or command or (executable_fence and any(
            token.lower() in lowered for token in cls.TOKENS
        )))

    @classmethod
    def _classify_node_hit(cls, node: MarkdownNode) -> str:
        actionable = cls._is_actionable(node)
        provenance_keys = {
            (
                spec.path,
                spec.heading_chain,
                spec.block_kind,
                spec.info_string,
                spec.ordinal,
            )
            for spec in cls.PROVENANCE_BLOCKS
        }
        if cls._node_key(node) in provenance_keys:
            return "provenance"
        if actionable:
            return "enablement"
        if (
            node.visible
            and node.block_kind == "prose"
            and node.normalized_content in cls.PROHIBITION_LINES
        ):
            return "prohibition"
        return "unqualified"

    @classmethod
    def validate(cls, surfaces: dict[str, str]) -> None:
        parsed = cls._parse_surfaces(surfaces)
        errors: list[str] = []

        action_label = "**Trust all and continue**"
        for spec in cls.GUIDANCE_BLOCKS:
            nodes = tuple(
                node
                for node in parsed[spec.path]
                if node.heading_chain == spec.heading_chain
            )
            actual_lines = tuple(node.normalized_content for node in nodes)
            if (
                actual_lines != spec.lines
                or any(not node.visible or node.block_kind != "prose" for node in nodes)
            ):
                errors.append(
                    f"{spec.path}: exact visible trust block changed under "
                    + " > ".join(spec.heading_chain)
                )
            if surfaces[spec.path].count(action_label) != 1:
                errors.append(
                    f"{spec.path}: trust action label must occur exactly once"
                )

        for spec in cls.WORKFLOW_BLOCKS:
            owned_nodes = tuple(
                node
                for node in parsed[spec.path]
                if node.heading_chain == spec.heading_chain
            )
            owned_fences = tuple(
                node for node in owned_nodes if node.block_kind == "fence"
            )
            matching = tuple(
                node
                for node in owned_fences
                if node.block_kind == "fence"
                and node.info_string == spec.info_string
                and node.ordinal == spec.ordinal
            )
            if (
                len(owned_fences) != 1
                or len(matching) != 1
                or not matching[0].visible
                or any(
                    node.block_kind not in {"prose", "fence"}
                    for node in owned_nodes
                )
                or tuple(matching[0].normalized_content.splitlines()) != spec.commands
            ):
                errors.append(
                    f"{spec.path}: exact executable {spec.info_string} workflow changed under "
                    + " > ".join(spec.heading_chain)
                )

        provenance = {
            (
                spec.path,
                spec.heading_chain,
                spec.block_kind,
                spec.info_string,
                spec.ordinal,
            ): spec
            for spec in cls.PROVENANCE_BLOCKS
        }
        matched: set[tuple[object, ...]] = set()
        for path_nodes in parsed.values():
            for node in path_nodes:
                node_tokens = [
                    token
                    for token in cls.TOKENS
                    if token in node.normalized_content
                ]
                if not node_tokens:
                    continue
                key = cls._node_key(node)
                classification = cls._classify_node_hit(node)
                spec = provenance.get(key)
                if classification == "provenance" and spec is not None:
                    digest = hashlib.sha256(
                        node.normalized_content.encode("utf-8")
                    ).hexdigest()
                    if (
                        not node.visible
                        or node.normalized_content.count(spec.expected_token) != 1
                        or len(node_tokens) != 1
                        or digest != spec.content_sha256
                    ):
                        errors.append(
                            f"{node.path}: provenance block changed for role {spec.role}"
                        )
                    else:
                        matched.add(key)
                    continue
                if classification != "prohibition":
                    errors.append(
                        f"{node.path}: trust bypass {classification} at "
                        f"{node.block_kind}[{node.ordinal}] under "
                        + " > ".join(node.heading_chain)
                    )

        missing_provenance = sorted(
            spec.role for key, spec in provenance.items() if key not in matched
        )
        if missing_provenance:
            errors.append(
                "trust bypass provenance blocks missing or changed: "
                + ", ".join(missing_provenance)
            )
        if errors:
            raise AssertionError("\n".join(errors))


def _tracked_text_surfaces() -> dict[str, str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    surfaces: dict[str, str] = {}
    for raw_path in listed:
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8")
        path = ROOT / relative
        try:
            surfaces[relative.replace("\\", "/")] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return surfaces


def test_trust_guidance_contract() -> None:
    TrustGuidanceContract.validate(_tracked_text_surfaces())


def _replace_once(surfaces: dict[str, str], path: str, old: str, new: str) -> None:
    assert surfaces[path].count(old) == 1, (path, old)
    surfaces[path] = surfaces[path].replace(old, new, 1)


def _replace_first(surfaces: dict[str, str], path: str, old: str, new: str) -> None:
    assert old in surfaces[path], (path, old)
    surfaces[path] = surfaces[path].replace(old, new, 1)


def _move_bypass_command_outside_provenance(
    surfaces: dict[str, str],
) -> None:
    path = "references-codex/stop-hook-halting-primitives.md"
    lines = surfaces[path].splitlines()
    index = next(
        i
        for i, line in enumerate(lines)
        if "codex --" + "dangerously-" + "bypass-hook-trust" in line
    )
    command = lines.pop(index)
    lines.extend(
        [
            "",
            "## Operator command",
            "",
            "Evidence follows:",
            "",
            "```bash",
            command,
            "```",
        ]
    )
    surfaces[path] = "\n".join(lines) + "\n"


def _remove_bypass_history_qualifier(surfaces: dict[str, str]) -> None:
    path = "references-codex/stop-hook-halting-primitives.md"
    _replace_once(
        surfaces,
        path,
        "(2026-07-26) resolved the blocker by adding `--"
        + "dangerously-"
        + "bypass-hook-trust"
        + "` to the invocation",
        "Operators can add `--"
        + "dangerously-"
        + "bypass-hook-trust"
        + "` to the invocation",
    )


def _move_powershell_workflow_into_html_comment(
    surfaces: dict[str, str],
) -> None:
    workflow = "\n".join(
        (
            "```powershell",
            *TrustGuidanceContract.WORKFLOW_BLOCKS[0].commands,
            "```",
        )
    )
    _replace_once(
        surfaces,
        "INSTALL.md",
        workflow,
        "<!--\n" + workflow + "\n-->",
    )


def _replace_controlled_probe_with_mixed_action(
    surfaces: dict[str, str],
) -> None:
    _replace_once(
        surfaces,
        "references-codex/stop-hook-halting-primitives.md",
        "codex --" + "dangerously-" + "bypass-hook-trust" + " exec --json ...",
        "# Do not use this command; export " + "BYPASS_" + "HOOK_TRUST=1",
    )


def _negate_trust_choice(surfaces: dict[str, str], replacement: str) -> None:
    _replace_once(
        surfaces,
        "INSTALL.md",
        "and choose **Trust all and continue**",
        "and " + replacement + " **Trust all and continue**",
    )


def _trust_guidance_mutations() -> dict[str, Callable[[dict[str, str]], None]]:
    bypass_lower = "bypass_" + "hook_trust"
    bypass_upper = "BYPASS_" + "HOOK_TRUST"
    mutations: dict[str, Callable[[dict[str, str]], None]] = {
        "interactive-replaced-by-exec": lambda s: _replace_once(
            s,
            "INSTALL.md",
            "start interactive `codex` — not `codex exec`",
            "start `codex exec` — not interactive `codex`",
        ),
        "interactive-guidance-deleted": lambda s: _replace_once(
            s,
            "src.codex/AGENTS.codex.md",
            "start interactive `codex` — not `codex exec` — and ",
            "",
        ),
        "trust-choice-changed": lambda s: _replace_once(
            s,
            "INSTALL.md",
            "**Trust all and continue**",
            "**Review hooks and continue**",
        ),
        "affected-count-weakened": lambda s: _replace_once(
            s,
            "INSTALL.md",
            "all 13 affected entries",
            "some of the 13 affected entries",
        ),
        "decline-warning-negated": lambda s: _replace_once(
            s,
            "INSTALL.md",
            "Do not press Esc and do not choose",
            "Press Esc or choose",
        ),
        "exec-skip-inverted": lambda s: _replace_once(
            s,
            "INSTALL.md",
            "`codex exec` silently skips untrusted hook entries",
            "`codex exec` runs untrusted hook entries",
        ),
        "timeout-weakened": lambda s: _replace_once(
            s,
            "INSTALL.md",
            "trust modal does not time out",
            "trust modal may time out",
        ),
        "powershell-workflow-noop": lambda s: _replace_once(
            s,
            "INSTALL.md",
            ".\\scripts\\install-codex.ps1 -Global\ncodex",
            "Write-Output .\\scripts\\install-codex.ps1 -Global\ncodex",
        ),
        "bash-workflow-wrong-order": lambda s: _replace_once(
            s,
            "INSTALL.md",
            "bash scripts/install-codex.sh --global\ncodex",
            "codex\nbash scripts/install-codex.sh --global",
        ),
        "health-command-placeholder": lambda s: _replace_once(
            s,
            "INSTALL.md",
            (
                "bash scripts/install-codex.sh --global\n"
                "codex\n"
                "python scripts/check-hook-health.py --verify-fires"
            ),
            (
                "bash scripts/install-codex.sh --global\n"
                "codex\n"
                "Write-Output check hook health"
            ),
        ),
        "history-made-imperative": lambda s: _replace_once(
            s,
            "RELEASE_NOTES.md",
            "--" + "dangerously-" + "bypass-hook-trust",
            bypass_upper + "=1",
        ),
        "history-qualifier-removed": _remove_bypass_history_qualifier,
        "assignment-replaces-provenance-hit": lambda s: _replace_first(
            s,
            "references-codex/ru/stop-hook-halting-primitives.md",
            "--" + "dangerously-" + "bypass-hook-trust",
            bypass_lower + "=1",
        ),
        "command-moved-outside-provenance": _move_bypass_command_outside_provenance,
        "reviewer-workflow-moved-into-html-comment": (
            _move_powershell_workflow_into_html_comment
        ),
        "reviewer-mixed-prohibition-and-assignment": (
            _replace_controlled_probe_with_mixed_action
        ),
    }
    for name, phrase in (
        ("do-not", "do not choose"),
        ("never", "never choose"),
        ("must-not", "must not choose"),
        ("should-not", "should not choose"),
        ("cannot", "cannot choose"),
        ("cant", "can't choose"),
        ("dont", "don't choose"),
    ):
        mutations[f"positive-choice-negated-{name}-immediate"] = (
            lambda surfaces, replacement=phrase: _negate_trust_choice(
                surfaces, replacement
            )
        )
    for name, phrase in (
        ("do-not", "do not under any circumstances choose"),
        ("never", "never under any circumstances choose"),
        ("must-not", "must not under any circumstances choose"),
        ("should-not", "should not under any circumstances choose"),
        ("cannot", "cannot under any circumstances choose"),
        ("cant", "can't under any circumstances choose"),
        ("dont", "don't under any circumstances choose"),
    ):
        mutations[f"positive-choice-negated-{name}-intervening"] = (
            lambda surfaces, replacement=phrase: _negate_trust_choice(
                surfaces, replacement
            )
        )
    return mutations


@pytest.mark.parametrize("mutation_name", tuple(_trust_guidance_mutations()))
def test_trust_guidance_contract_rejects_same_count_mutations(
    mutation_name: str,
) -> None:
    original = _tracked_text_surfaces()
    mutated = dict(original)
    _trust_guidance_mutations()[mutation_name](mutated)
    assert TrustGuidanceContract.token_inventory(mutated) == (
        TrustGuidanceContract.token_inventory(original)
    )
    if mutation_name == "reviewer-workflow-moved-into-html-comment":
        for command in TrustGuidanceContract.WORKFLOW_BLOCKS[0].commands:
            assert mutated["INSTALL.md"].count(command) == original["INSTALL.md"].count(
                command
            )
    with pytest.raises(AssertionError):
        TrustGuidanceContract.validate(mutated)


def test_trust_bypass_classifier_accepts_prohibition_but_rejects_enablement() -> None:
    path = "docs/synthetic.md"
    token = "BYPASS_" + "HOOK_TRUST"
    prohibition = MarkdownNode(
        path,
        (),
        "prose",
        "",
        True,
        0,
        f"Do not use `{token}=1`; it disables the trust gate.",
    )
    enablement = MarkdownNode(path, (), "raw", "", True, 0, f"export {token}=1")
    mixed = MarkdownNode(
        path,
        (),
        "fence",
        "bash",
        True,
        0,
        f"# Do not use this command; export {token}=1",
    )
    assert TrustGuidanceContract._classify_node_hit(prohibition) == "prohibition"
    assert TrustGuidanceContract._classify_node_hit(enablement) == "enablement"
    assert TrustGuidanceContract._classify_node_hit(mixed) == "enablement"
