"""Disposable-install parity gate for lifecycle V1 hook retirement."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "install-hypothesis-hook.py"
OBSOLETE_MARKER = "check-work-items-archival-stop"
RETIRED_BYPASS = "[acknowledge-open-work-items]"
REMINDER_MARKERS = frozenset(
    {
        "mcp-usage-reminder",
        "agents-mode-reminder",
        "check-scratch-valuables",
        "turn-anchor-reminder",
    }
)
SHARED_STRUCTURAL_MARKERS = frozenset(
    {
        "check-bugfix-discipline",
        "check-git-push-gate",
        "check-passive-polling-stop",
        "check-machine-local-path",
        "check-no-trash-in-repo",
        "check-stale-relation-residue",
        "check-repository-orientation",
        "check-mcp-momentum",
    }
)
EXPECTED_MARKERS = {
    "codex": SHARED_STRUCTURAL_MARKERS | REMINDER_MARKERS,
    "claude": SHARED_STRUCTURAL_MARKERS | REMINDER_MARKERS | {"check-typed-routing"},
}
EXPECTED_COUNTS = {
    "codex": (8, 12),
    "claude": (9, 13),
}
CURRENT_LIFECYCLE_SURFACES = (
    ROOT / "INSTALL.md",
    ROOT / "src.codex" / "AGENTS.codex.md",
    ROOT / "src.codex" / "skills" / "lead" / "SKILL.md",
    ROOT / "src.claude" / "CLAUDE.md",
    ROOT / "src.claude" / "skills" / "lead" / "SKILL.md",
    ROOT / "src.claude" / "commands" / "agents-status.md",
    ROOT / "src.claude" / "commands" / "agents-implement.md",
    ROOT / "docs" / "epics.md",
    ROOT / "docs" / "dependencies.md",
    ROOT / "docs" / "decisions.md",
    ROOT / "docs" / "lessons.md",
    ROOT / "shared" / "references" / "repository-source-hygiene.md",
    ROOT / "shared" / "references" / "ru" / "repository-source-hygiene.md",
    ROOT / "scripts" / "validate-claude-md.py",
    ROOT / "tests" / "test_claude_md_size.py",
    ROOT / "scripts" / "universal-hooks" / "scripts" / "workitem_sentinels.py",
    ROOT / "scripts" / "universal-hooks" / "scripts" / "hook_common.py",
    ROOT / "src.codex" / "skills" / "lead" / "scripts" / "workitem_sentinels.py",
    ROOT / "src.codex" / "skills" / "lead" / "scripts" / "hook_common.py",
    ROOT / "src.claude" / "agents" / "scripts" / "workitem_sentinels.py",
    ROOT / "src.claude" / "agents" / "scripts" / "hook_common.py",
)
RETIRED_ADAPTER_PATHS = tuple(
    ROOT / base / f"{OBSOLETE_MARKER}{suffix}"
    for base in (
        Path("scripts/universal-hooks/scripts"),
        Path("src.codex/skills/lead/scripts"),
        Path("src.claude/agents/scripts"),
    )
    for suffix in (".py", ".sh")
)
RETIRED_CONTROL_CLAIMS = (
    OBSOLETE_MARKER,
    RETIRED_BYPASS,
    "work-items-archival",
    "work-items archival Stop",
    "archival Stop-hook",
    "archival Stop hook flags",
    "SEN-2",
    "Registered ONLY on `Stop`",
    "neither blocking Stop guard",
    "28 wrappers from 14 owned stems",
)


def _load_installer():
    path = ROOT / "scripts" / "production_installer.py"
    spec = importlib.util.spec_from_file_location("production_installer_lifecycle_parity", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_helper(
    provider: str,
    registration: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(HELPER),
            "--target",
            str(registration),
            "--platform",
            provider,
            "--host-os",
            "windows" if os.name == "nt" else "posix",
            *arguments,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _install_specs(provider: str, registration: Path, installed_root: Path) -> None:
    installer = _load_installer()
    for marker, script, event, matcher in installer._hook_specs(provider, installed_root):
        arguments = ["--script-marker", marker, "--script-path", str(script)]
        if event != "PreToolUse":
            arguments.extend(("--hook-event", event))
        if matcher:
            arguments.extend(("--tool-matcher", matcher))
        result = _run_helper(provider, registration, *arguments)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)


def _remove_obsolete(provider: str, registration: Path) -> None:
    result = _run_helper(
        provider,
        registration,
        "--script-marker",
        OBSOLETE_MARKER,
        "--hook-event",
        "Stop",
        "--remove",
    )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


def _all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _all_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_strings(nested)


class TestWorkItemsLifecycleInstallParity(unittest.TestCase):
    def test_bug_disposition_close_contract_is_present_across_installed_surfaces(self) -> None:
        surfaces = (
            ROOT / "shared" / "AGENTS.shared.md",
            ROOT / "src.codex" / "AGENTS.codex.md",
            ROOT / "src.claude" / "CLAUDE.md",
            ROOT / "src.codex" / "skills" / "lead" / "SKILL.md",
            ROOT / "src.claude" / "skills" / "lead" / "SKILL.md",
            ROOT / "src.codex" / "skills" / "knowledge-archivist" / "SKILL.md",
            ROOT / "src.claude" / "agents" / "knowledge-archivist.md",
        )
        for path in surfaces:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("bug-dispositions.json", text)
                self.assertIn("terminalize", text)
                self.assertIn("preserve-current", text)

        owner = (ROOT / "scripts" / "mutate-work-item.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('BUG_DISPOSITIONS_MANIFEST = "bug-dispositions.json"', owner)
        self.assertIn(
            'BUG_DISPOSITIONS_RECEIPT = "bug-dispositions-receipt.json"', owner
        )
        self.assertIn('"WI-BUG-DISPOSITIONS-PENDING"', owner)

    def test_current_contract_runtime_and_validator_inventory_is_archive_only(self) -> None:
        stale: list[str] = []
        for path in CURRENT_LIFECYCLE_SURFACES:
            self.assertTrue(path.is_file(), f"missing current lifecycle surface: {path}")
            text = path.read_text(encoding="utf-8")
            for token in RETIRED_CONTROL_CLAIMS:
                if token in text:
                    stale.append(f"{path.relative_to(ROOT)}: {token}")
        self.assertEqual(stale, [], "live contract reintroduced retired lifecycle control")

        for path in RETIRED_ADAPTER_PATHS:
            self.assertFalse(path.exists(), f"retired adapter path exists: {path}")

        installer = _load_installer()
        for provider, (structural_count, total_count) in EXPECTED_COUNTS.items():
            source_root = (
                ROOT / "src.codex" / "skills" / "lead"
                if provider == "codex"
                else ROOT / "src.claude" / "agents"
            )
            markers = {
                marker
                for marker, _script, _event, _matcher in installer._hook_specs(
                    provider, source_root
                )
            }
            self.assertTrue(
                all(
                    script.suffix == ".py"
                    for _marker, script, _event, _matcher in installer._hook_specs(
                        provider, source_root
                    )
                ),
                "production hook registrations must target Python directly",
            )
            self.assertEqual(markers, EXPECTED_MARKERS[provider])
            self.assertEqual(len(markers), total_count)
            self.assertEqual(len(markers - REMINDER_MARKERS), structural_count)

        install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        self.assertIn("direct-Python hook runtime", install)
        self.assertNotIn("--hook-runtime wrapper", install)
        self.assertNotIn("wrappers from", install)
        self.assertIn(
            "retired-file manifest removes only exact last-pack-owned hook shell or PowerShell files",
            install,
        )

        codex = (ROOT / "src.codex" / "AGENTS.codex.md").read_text(encoding="utf-8")
        self.assertIn("ships eight structural hooks", codex)
        self.assertIn("auto-installs all twelve hook entries", codex)
        self.assertIn("Physical location owns membership", codex)

        claude = (ROOT / "src.claude" / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("auto-installs thirteen `settings.json` entries", claude)
        self.assertIn("nine structural hooks", claude)
        self.assertIn("Physical location owns lifecycle membership", claude)

        runtime = (
            ROOT / "scripts" / "universal-hooks" / "scripts" / "workitem_sentinels.py"
        ).read_text(encoding="utf-8")
        self.assertIn("only after it physically enters archive/", runtime)
        self.assertIn('"event": "PeriodicCheck"', runtime)

    def test_disposable_upgrade_preserves_retained_hook_identities(self) -> None:
        installer = _load_installer()
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for provider, expected_count in (("codex", 12), ("claude", 13)):
                source_root = (
                    ROOT / "src.codex" / "skills" / "lead"
                    if provider == "codex"
                    else ROOT / "src.claude" / "agents"
                )
                actual = temp / f"{provider}-actual.json"
                expected = temp / f"{provider}-expected.json"
                user_event = [{"hooks": [{"type": "command", "command": "user-owned-hook"}]}]
                _install_specs(provider, expected, source_root)
                seeded = json.loads(expected.read_text(encoding="utf-8"))
                seeded["userSetting"] = {"preserve": True}
                seeded["hooks"]["CustomEvent"] = copy.deepcopy(user_event)
                seeded["hooks"].setdefault("Stop", []).append(
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"python /old/{OBSOLETE_MARKER}.py",
                            }
                        ]
                    }
                )
                actual.write_text(json.dumps(seeded), encoding="utf-8")

                _remove_obsolete(provider, actual)
                _install_specs(provider, actual, source_root)

                actual_data = json.loads(actual.read_text(encoding="utf-8"))
                expected_data = json.loads(expected.read_text(encoding="utf-8"))
                self.assertEqual(actual_data.pop("userSetting"), {"preserve": True})
                self.assertEqual(
                    actual_data["hooks"].pop("CustomEvent"),
                    user_event,
                )
                self.assertEqual(actual_data, expected_data)
                self.assertEqual(
                    len(installer._hook_specs(provider, source_root)),
                    expected_count,
                )
                self.assertFalse(
                    any(OBSOLETE_MARKER in value for value in _all_strings(actual_data))
                )

    def test_disposable_layouts_have_mirrored_runtime_support_and_no_adapter(self) -> None:
        canonical_runtime = ROOT / "scripts" / "universal-hooks" / "scripts"
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for provider, source in (
                ("codex", ROOT / "src.codex" / "skills" / "lead"),
                ("claude", ROOT / "src.claude" / "agents"),
            ):
                installed = temp / provider
                shutil.copytree(source, installed)
                for helper in (
                    "mutate-work-item.py",
                    "check-work-items-state.py",
                    "validate-work-item-state.py",
                ):
                    shutil.copy2(ROOT / "scripts" / helper, installed / "scripts" / helper)
                for support in ("workitem_sentinels.py", "hook_common.py"):
                    self.assertEqual(
                        hashlib.sha256((installed / "scripts" / support).read_bytes()).hexdigest(),
                        hashlib.sha256((canonical_runtime / support).read_bytes()).hexdigest(),
                    )
                for helper in (
                    "mutate-work-item.py",
                    "check-work-items-state.py",
                    "validate-work-item-state.py",
                ):
                    self.assertEqual(
                        hashlib.sha256((installed / "scripts" / helper).read_bytes()).hexdigest(),
                        hashlib.sha256((ROOT / "scripts" / helper).read_bytes()).hexdigest(),
                    )
                lifecycle_help = subprocess.run(
                    [
                        sys.executable,
                        str(installed / "scripts" / "mutate-work-item.py"),
                        "--help",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(lifecycle_help.returncode, 0, lifecycle_help.stderr)
                self.assertIn("convert-legacy-candidate", lifecycle_help.stdout)
                self.assertIn("retire-legacy-backlog", lifecycle_help.stdout)
                for suffix in (".py", ".sh"):
                    self.assertEqual(
                        list(installed.rglob(f"{OBSOLETE_MARKER}{suffix}")),
                        [],
                    )

    def test_production_installers_ship_lifecycle_validator_schema(self) -> None:
        installer = _load_installer()
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for provider in ("codex", "claude"):
                installed_root = temp / provider
                helper_target = installed_root / "scripts"
                installer._install_runtime_files(ROOT, helper_target, False)
                schema = (
                    installed_root / "shared" / "schemas" / "agent-runs.schema.json"
                )
                validator = installed_root / "scripts" / "validate-work-item-state.py"
                classifier = installed_root / "scripts" / "maintenance" / "cleanup.py"
                with self.subTest(provider=provider, stage="schema"):
                    self.assertTrue(schema.is_file(), schema)
                    self.assertEqual(
                        hashlib.sha256(schema.read_bytes()).hexdigest(),
                        hashlib.sha256(
                            (
                                ROOT / "shared" / "schemas" / "agent-runs.schema.json"
                            ).read_bytes()
                        ).hexdigest(),
                    )
                    self.assertEqual(
                        hashlib.sha256(classifier.read_bytes()).hexdigest(),
                        hashlib.sha256(
                            (ROOT / "scripts" / "maintenance" / "cleanup.py").read_bytes()
                        ).hexdigest(),
                    )
                validation_help = subprocess.run(
                    [sys.executable, str(validator), "--help"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                with self.subTest(provider=provider, stage="validator-load"):
                    self.assertEqual(
                        validation_help.returncode,
                        0,
                        validation_help.stdout + validation_help.stderr,
                    )
                lifecycle = installed_root / "scripts" / "mutate-work-item.py"
                classifier_load = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import importlib.util,sys;"
                            f"p=r'{lifecycle}';"
                            "s=importlib.util.spec_from_file_location('installed_lifecycle',p);"
                            "m=importlib.util.module_from_spec(s);"
                            "sys.modules[s.name]=m;s.loader.exec_module(m);"
                            "m._scratch_classifier_module()"
                        ),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                with self.subTest(provider=provider, stage="classifier-load"):
                    self.assertEqual(
                        classifier_load.returncode,
                        0,
                        classifier_load.stdout + classifier_load.stderr,
                    )


if __name__ == "__main__":
    unittest.main()
