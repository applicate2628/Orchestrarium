import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ResolveAgentsModeTest(unittest.TestCase):
    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")

    def _resolve(self, provider: str, project_root: Path, home: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "resolve-agents-mode.py"),
                "--provider",
                provider,
                "--project-root",
                str(project_root),
                "--home",
                str(home),
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_codex_layers_compose_per_key_without_synthesizing_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()

            self._write(
                home / ".agents-mode.yaml",
                """
                consultantMode: internal
                mcpMode: force
                externalPriorityProfile: quality-first
                """,
            )
            self._write(
                home / ".codex" / ".agents-mode.yaml",
                """
                mcpMode: auto
                parallelMode: force
                """,
            )
            self._write(
                project / ".agents" / ".agents-mode",
                """
                parallelMode: manual
                preferExternalReviewer: true
                """,
            )
            self._write(
                project / ".agents" / ".agents-mode.yaml",
                """
                consultantMode: disabled
                """,
            )

            resolved = self._resolve("codex", project, home)

            values = resolved["values"]
            sources = resolved["sources"]
            self.assertEqual(values["consultantMode"], "disabled")
            self.assertEqual(sources["consultantMode"]["rank"], "local")
            self.assertEqual(values["parallelMode"], "manual")
            self.assertEqual(sources["parallelMode"]["rank"], "local-legacy")
            self.assertEqual(values["mcpMode"], "auto")
            self.assertEqual(sources["mcpMode"]["rank"], "global")
            self.assertEqual(values["externalPriorityProfile"], "quality-first")
            self.assertEqual(sources["externalPriorityProfile"]["rank"], "shared-global")
            self.assertEqual(values["preferExternalReviewer"], "true")
            self.assertEqual(values["delegationMode"], "auto")
            self.assertEqual(sources["delegationMode"]["rank"], "defaults")
            self.assertEqual(values["externalClaudeProfile"], "opus-xhigh")

            self.assertFalse((project / ".agents" / ".agents-mode.yaml.generated").exists())

    def test_shared_extensionless_preferences_are_read_without_migration(self) -> None:
        for provider in ("codex", "claude"):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                project, home = base / "project", base / "home"
                project.mkdir()
                legacy = home / ".agents-mode"
                self._write(legacy, "# Retained preferences\nmcpMode: force\nexternalClaudeApiMode: disabled\n")
                original, identity = legacy.read_bytes(), legacy.stat().st_ino

                resolved = self._resolve(provider, project, home)

                for key, value in (("mcpMode", "force"), ("reserveResolver", "disabled")):
                    self.assertEqual(resolved["values"][key], value)
                    self.assertEqual(resolved["sources"][key],
                                     {"rank": "shared-global", "path": str(legacy)})
                self.assertEqual((legacy.read_bytes(), legacy.stat().st_ino), (original, identity))
                self.assertEqual(list(home.iterdir()), [legacy])
                self.assertEqual(list(project.iterdir()), [])

    def test_shared_canonical_file_suppresses_legacy_keys_and_wrapper_confirmation(self) -> None:
        for provider, local_dir in (("codex", ".agents"), ("claude", ".claude")):
            for canonical_text in ("", "mcpMode: auto\n"):
                with self.subTest(provider=provider, canonical=canonical_text), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    project, home = base / "project", base / "home"
                    canonical, legacy = home / ".agents-mode.yaml", home / ".agents-mode"
                    self._write(canonical, canonical_text)
                    self._write(legacy, "consultantMode: internal\nmcpMode: force\nreserveResolver: wrapper:shared-review\n")
                    self._write(project / local_dir / ".agents-mode.yaml",
                                "reserveResolver: wrapper:shared-review\n")
                    before = {path: path.read_bytes() for path in (canonical, legacy)}

                    resolved = self._resolve(provider, project, home)

                    self.assertEqual(resolved["values"]["consultantMode"], "disabled")
                    self.assertEqual(resolved["sources"]["consultantMode"]["rank"], "defaults")
                    self.assertEqual(resolved["values"]["mcpMode"], "auto")
                    self.assertEqual(resolved["reserveResolverTrust"], "project-UNCONFIRMED")
                    self.assertNotIn(str(legacy), {value["path"] for value in resolved["sources"].values()})
                    self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_shared_extensionless_selection_keeps_provider_and_project_precedence(self) -> None:
        for provider, local_dir in (("codex", ".agents"), ("claude", ".claude")):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                project, home = base / "project", base / "home"
                legacy = home / ".agents-mode"
                self._write(legacy, "mcpMode: force\nconsultantMode: internal\nreserveResolver: wrapper:shared-review\n")
                self._write(home / f".{provider}" / ".agents-mode.yaml", "mcpMode: auto\n")
                self._write(project / local_dir / ".agents-mode", "consultantMode: disabled\n")

                resolved = self._resolve(provider, project, home)

                for key, value, rank in (("mcpMode", "auto", "global"),
                                         ("consultantMode", "disabled", "local-legacy")):
                    self.assertEqual(resolved["values"][key], value)
                    self.assertEqual(resolved["sources"][key]["rank"], rank)
                self.assertEqual(resolved["values"]["reserveResolver"], "wrapper:shared-review")
                self.assertEqual(resolved["sources"]["reserveResolver"],
                                 {"rank": "shared-global", "path": str(legacy)})
                self.assertEqual(resolved["reserveResolverTrust"], "user-global")

    def test_occupied_shared_canonical_path_does_not_select_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project, home = base / "project", base / "home"
            project.mkdir()
            canonical = home / ".agents-mode.yaml"
            canonical.mkdir(parents=True)
            self._write(home / ".agents-mode", "consultantMode: internal\n")

            resolved = self._resolve("codex", project, home)

            self.assertEqual(resolved["values"]["consultantMode"], "disabled")
            self.assertEqual(resolved["sources"]["consultantMode"]["rank"], "defaults")
            self.assertTrue(canonical.is_dir())

    def test_dispatch_owners_keep_second_opinion_toggle_sparse(self) -> None:
        owners = {
            "codex": ("src.codex/skills/lead/external-dispatch.md", ".codex", ".agents"),
            "claude": ("adapters/claude/agents/contracts/external-dispatch.md", ".claude", ".claude"),
        }
        for provider, (owner, global_pack, local_pack) in owners.items():
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                project, home = base / "project", base / "home"
                project.mkdir()
                config = home / global_pack / ".agents-mode.yaml"
                self._write(config, "consultantMode: internal\nexternalProvider: kimi\ndelegationMode: manual\n")
                inherited = self._resolve(provider, project, home)
                self.assertEqual(inherited["values"]["consultantMode"], "internal")
                local = project / local_pack / ".agents-mode.yaml"
                self.assertFalse(local.exists())
                self._write(local, "consultantMode: external\n")
                effective = self._resolve(provider, project, home)
                self.assertEqual(effective["values"]["consultantMode"], "external")
                for key in ("externalProvider", "delegationMode"):
                    self.assertEqual(effective["values"][key], inherited["values"][key])
                    self.assertEqual(effective["sources"][key], inherited["sources"][key])
                    self.assertEqual(effective["sources"][key]["rank"], "global")
                self._write(local, "consultantMode: internal\nfutureSetting: retained\n")
                before = local.read_bytes()
                readback = self._resolve(provider, project, home)
                self.assertEqual(readback["values"]["consultantMode"], "internal")
                for key in ("externalProvider", "delegationMode"):
                    self.assertEqual(readback["sources"][key], inherited["sources"][key])
                self.assertEqual(local.read_bytes(), before)
                policy = (ROOT / owner).read_text(encoding="utf-8")
                self.assertIn("A Second Opinion toggle writes only the local `consultantMode` key", policy)
                self.assertIn("Authorized installer normalization is separate", policy)
                self.assertNotIn("write the full default shape", policy)
                self.assertNotIn("must not rewrite the file back to a consultant-only shape", policy)

    def test_project_local_wrapper_resolver_is_flagged_project_unconfirmed(self) -> None:
        """F9: a repo-supplied executable-bearing reserveResolver must not be silently trusted."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()

            self._write(
                home / ".claude" / ".agents-mode.yaml",
                """
                reserveResolver: claude-sonnet
                """,
            )
            self._write(
                project / ".claude" / ".agents-mode.yaml",
                """
                consultantMode: external
                reserveResolver: wrapper:tools/evil.sh
                """,
            )

            resolved = self._resolve("claude", project, home)

            self.assertEqual(resolved["values"]["reserveResolver"], "wrapper:tools/evil.sh")
            self.assertEqual(resolved["sources"]["reserveResolver"]["rank"], "local")
            self.assertEqual(resolved["reserveResolverTrust"], "project-UNCONFIRMED")

    def test_user_global_wrapper_resolver_stays_trusted(self) -> None:
        """F9: an executable-bearing resolver defined at a user-global layer is honored."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()

            self._write(
                home / ".claude" / ".agents-mode.yaml",
                """
                reserveResolver: wrapper:reserve-review
                """,
            )

            resolved = self._resolve("claude", project, home)

            self.assertEqual(resolved["values"]["reserveResolver"], "wrapper:reserve-review")
            self.assertEqual(resolved["sources"]["reserveResolver"]["rank"], "global")
            self.assertEqual(resolved["reserveResolverTrust"], "user-global")

    def test_project_local_wrapper_matching_user_global_value_is_confirmed(self) -> None:
        """F9: a project-local executable value identical to a user-global one is the durable
        first-use approval record, so it resolves trusted."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()

            self._write(
                home / ".agents-mode.yaml",
                """
                reserveResolver: wrapper:tools/reserve-review.ps1
                """,
            )
            self._write(
                project / ".claude" / ".agents-mode.yaml",
                """
                reserveResolver: wrapper:tools/reserve-review.ps1
                """,
            )

            resolved = self._resolve("claude", project, home)

            self.assertEqual(resolved["sources"]["reserveResolver"]["rank"], "local")
            self.assertEqual(resolved["reserveResolverTrust"], "user-global")

    def test_non_executable_reserve_resolver_needs_no_trust_gate(self) -> None:
        """F9: symbolic resolver values (claude-sonnet/claude-wrapper/disabled) carry no
        arbitrary executable, so the trust gate does not fire even from a project layer."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()

            self._write(
                project / ".claude" / ".agents-mode.yaml",
                """
                reserveResolver: claude-sonnet
                """,
            )

            resolved = self._resolve("claude", project, home)

            self.assertEqual(resolved["sources"]["reserveResolver"]["rank"], "local")
            self.assertEqual(resolved["reserveResolverTrust"], "not-executable")

            defaults_only = self._resolve("claude", base / "project", home)
            self.assertEqual(defaults_only["reserveResolverTrust"], "not-executable")

    def test_supported_quoted_scalars_resolve_to_semantic_values_without_rewrite(self) -> None:
        """Quoted YAML syntax is decoded for runtime use but remains byte-exact on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()
            overlay = project / ".agents" / ".agents-mode.yaml"
            self._write(
                overlay,
                r"""
                externalProvider: "claude"
                reserveResolver: 'disabled'
                externalPriorityProfile: "quality\"first"
                """,
            )
            original = overlay.read_bytes()

            resolved = self._resolve("codex", project, home)

            self.assertEqual(resolved["values"]["externalProvider"], "claude")
            self.assertEqual(resolved["values"]["reserveResolver"], "disabled")
            self.assertEqual(resolved["values"]["externalPriorityProfile"], 'quality"first')
            self.assertEqual(overlay.read_bytes(), original)

    def test_unquoted_scalar_keeps_its_semantic_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()
            self._write(project / ".agents" / ".agents-mode.yaml", "mcpMode: force\n")

            resolved = self._resolve("codex", project, home)

            self.assertEqual(resolved["values"]["mcpMode"], "force")

    def test_invalid_quoted_scalar_fails_closed_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()
            overlay = project / ".agents" / ".agents-mode.yaml"
            original = b'externalProvider: "claude\n'
            overlay.parent.mkdir(parents=True)
            overlay.write_bytes(original)

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "resolve-agents-mode.py"),
                    "--provider",
                    "codex",
                    "--project-root",
                    str(project),
                    "--home",
                    str(home),
                    "--repo-root",
                    str(ROOT),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("E_AGENTS_MODE_INVALID_YAML", result.stderr)
            self.assertEqual(overlay.read_bytes(), original)

    def test_removed_providers_fail_with_migration_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            home = base / "home"
            project.mkdir()
            home.mkdir()
            self._write(
                home / ".agents-mode.yaml",
                """
                mcpMode: force
                externalProvider: auto
                """,
            )

            for provider in ("gemini", "qwen"):
                with self.subTest(provider=provider):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(ROOT / "scripts" / "resolve-agents-mode.py"),
                            "--provider",
                            provider,
                            "--project-root",
                            str(project),
                            "--home",
                            str(home),
                            "--repo-root",
                            str(ROOT),
                            "--json",
                        ],
                        text=True,
                        capture_output=True,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("E_EXTERNAL_PROVIDER_REMOVED", result.stderr)
                    self.assertIn(provider, result.stderr)


if __name__ == "__main__":
    unittest.main()
