"""Read-only legacy reserve preferences retain per-layer precedence."""
from pathlib import Path
import stat
import tempfile
import unittest

from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
RESOLVER = load_module(ROOT / "scripts/resolve-agents-mode.py", "legacy_reserve_preference_resolver")
VALIDATOR = load_module(ROOT / "scripts/validate-agents-mode-installers.py", "legacy_reserve_preference_validator")


class LegacyReservePreferenceTests(unittest.TestCase):
    def setUp(self):
        # The invoking test owner settles this isolated fixture using trash-first disposition.
        self.base = Path(tempfile.mkdtemp(prefix="legacy-reserve-preference-"))
        self.project, self.home = self.base / "project", self.base / "home"
        self.project.mkdir()
        self.home.mkdir()

    def write(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def resolve(self, provider):
        before = {path: (path.read_bytes(), path.lstat().st_ino, stat.S_IFMT(path.lstat().st_mode))
                  for path in self.base.rglob("*") if path.is_file()}
        resolved = RESOLVER.resolve(provider, self.project, self.home, ROOT)
        after = {path: (path.read_bytes(), path.lstat().st_ino, stat.S_IFMT(path.lstat().st_mode))
                 for path in self.base.rglob("*") if path.is_file()}
        self.assertEqual(after, before)
        return resolved

    def test_shared_legacy_disable_retains_exact_bytes_identity_and_provenance(self):
        path = self.home / ".agents-mode.yaml"
        for provider in ("codex", "claude"):
            for value in (b"disabled", b"'disabled'", b'"DISABLED"'):
                with self.subTest(provider=provider, value=value):
                    self.write(path, b"# user choice\r\nexternalClaudeApiMode: " + value
                               + b"  # keep comment\r\nmcpMode: force\r\nfutureSetting: keep\r\n")
                    resolved = self.resolve(provider)
                    self.assertEqual(resolved["values"]["reserveResolver"], "disabled")
                    self.assertEqual(resolved["values"]["mcpMode"], "force")
                    self.assertEqual(resolved["values"]["futureSetting"], "keep")
                    self.assertEqual(resolved["sources"]["reserveResolver"], {
                        "rank": "shared-global", "path": str(path),
                    })

    def test_each_layer_recognizes_its_own_legacy_disable(self):
        for provider in ("codex", "claude"):
            for index in range(5):
                with self.subTest(provider=provider, layer=index):
                    project, home = self.project / f"{provider}-{index}", self.home / f"{provider}-{index}"
                    project.mkdir()
                    home.mkdir()
                    rank, path = RESOLVER.layer_paths(provider, project, home)[index]
                    payload = b"externalClaudeApiMode: disabled\r\n"
                    self.write(path, payload)
                    resolved = RESOLVER.resolve(provider, project, home, ROOT)
                    self.assertEqual(resolved["values"]["reserveResolver"], "disabled")
                    self.assertEqual(resolved["sources"]["reserveResolver"], {
                        "rank": rank, "path": str(path),
                    })
                    self.assertEqual(path.read_bytes(), payload)

    def test_canonical_key_in_same_layer_wins_in_either_text_order(self):
        path = self.home / ".agents-mode.yaml"
        canonical = b"reserveResolver: claude-wrapper\r\n"
        legacy = b"externalClaudeApiMode: disabled\r\n"
        for payload in (canonical + legacy, legacy + canonical):
            with self.subTest(payload=payload):
                self.write(path, payload)
                resolved = self.resolve("codex")
                self.assertEqual(resolved["values"]["reserveResolver"], "claude-wrapper")
                self.assertEqual(resolved["sources"]["reserveResolver"]["rank"], "shared-global")

    def test_higher_canonical_key_wins_over_lower_legacy_disable(self):
        self.write(self.home / ".agents-mode.yaml", b"externalClaudeApiMode: disabled\r\n")
        path = self.project / ".agents/.agents-mode.yaml"
        self.write(path, b"reserveResolver: wrapper:tools/local-review\r\n")
        resolved = self.resolve("codex")
        self.assertEqual(resolved["values"]["reserveResolver"], "wrapper:tools/local-review")
        self.assertEqual(resolved["sources"]["reserveResolver"], {"rank": "local", "path": str(path)})
        self.assertEqual(resolved["reserveResolverTrust"], "project-UNCONFIRMED")

    def test_higher_legacy_disable_wins_over_lower_canonical_key(self):
        self.write(self.home / ".agents-mode.yaml", b"reserveResolver: claude-wrapper\r\n")
        path = self.project / ".claude/.agents-mode.yaml"
        self.write(path, b"externalClaudeApiMode: disabled\r\n")
        resolved = self.resolve("claude")
        self.assertEqual(resolved["values"]["reserveResolver"], "disabled")
        self.assertEqual(resolved["sources"]["reserveResolver"], {"rank": "local", "path": str(path)})

    def test_other_legacy_values_do_not_pin_an_inherited_resolver(self):
        self.write(self.home / ".agents-mode.yaml", b"reserveResolver: claude-wrapper\r\n")
        path = self.project / ".agents/.agents-mode.yaml"
        for value in (b"auto", b"enabled", b"unknown"):
            with self.subTest(value=value):
                self.write(path, b"externalClaudeApiMode: " + value + b"\r\n")
                resolved = self.resolve("codex")
                self.assertEqual(resolved["values"]["reserveResolver"], "claude-wrapper")
                self.assertEqual(resolved["sources"]["reserveResolver"]["rank"], "shared-global")

    def test_installer_validator_reads_the_actual_shared_resolver(self):
        path = self.home / ".agents-mode.yaml"
        payload = b"# unchanged shared choice\r\nexternalClaudeApiMode: disabled\r\nmcpMode: force\r\n"
        self.write(path, payload)
        original = path.lstat()
        for case in VALIDATOR.INSTALLER_CASES:
            with self.subTest(provider=case.name):
                VALIDATOR.validate_shared_preference_resolution(ROOT, case, self.home)
                self.assertEqual(path.read_bytes(), payload)
                self.assertEqual(path.lstat().st_ino, original.st_ino)
                self.assertEqual(stat.S_IFMT(path.lstat().st_mode), stat.S_IFMT(original.st_mode))
                self.assertEqual(list(self.home.iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
