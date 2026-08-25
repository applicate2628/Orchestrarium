from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "src.codex" / "skills" / "manual-repo-transfer" / "scripts" / "repo_transfer.py"
GIT_EXECUTABLE = Path(shutil.which("git") or "").resolve()
if not GIT_EXECUTABLE.is_file():
    raise RuntimeError("test host must provide an explicit Git executable")


def run(*args: object, cwd: Path | None = None, expect: int = 0) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), *(str(arg) for arg in args), "--git-executable", str(GIT_EXECUTABLE)]
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != expect:
        raise AssertionError(
            f"expected exit {expect}, got {result.returncode}\n"
            f"command: {command}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def covered_set_digest(inventory: dict, path: str) -> str:
    entries = [
        entry
        for entry in inventory["entries"]
        if entry["path"] == path or entry["path"].startswith(path + "/")
    ]
    body = json.dumps(
        entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


class RepoTransferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "remote.git"
        self.repo.mkdir()
        git(self.repo, "init", "--initial-branch=main")
        git(self.repo, "config", "user.name", "Transfer Test")
        git(self.repo, "config", "user.email", "transfer@example.invalid")

        (self.repo / ".gitignore").write_text(
            ".scratch/\nnode_modules/\n*.zip\n", encoding="utf-8"
        )
        (self.repo / "tracked.txt").write_text("committed\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore", "tracked.txt")
        git(self.repo, "commit", "-m", "initial")
        git(self.root, "init", "--bare", str(self.remote))
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-u", "origin", "main")
        git(
            self.repo,
            "remote",
            "add",
            "credentialed",
            "https://transfer-user:transfer-secret@example.invalid/repo.git",
        )

        (self.repo / "tracked.txt").write_text("dirty current bytes\n", encoding="utf-8")
        (self.repo / "untracked.txt").write_text("user work\n", encoding="utf-8")
        (self.repo / ".scratch").mkdir()
        (self.repo / ".scratch" / "evidence.txt").write_text(
            "unique evidence\n", encoding="utf-8"
        )
        (self.repo / "node_modules").mkdir()
        (self.repo / "node_modules" / "cache.bin").write_bytes(b"cache")

        self.inventory_path = self.root / "inventory.json"
        self.selection = self.root / "selection.json"
        self.bundle = self.root / "transfer.zip"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def inventory(self) -> dict:
        run("inventory", "--repo", self.repo, "--output", self.inventory_path)
        return json.loads(self.inventory_path.read_text(encoding="utf-8"))

    def write_selection(self, inventory: dict) -> None:
        selection = {
            "schemaVersion": 1,
            "inventoryDigest": inventory["snapshot"]["digest"],
            "gitStrategy": {
                "mode": "remote-clone",
                "remote": "origin",
                "expectedHead": inventory["repository"]["head"],
            },
            "items": [
                {
                    "path": "tracked.txt",
                    "disposition": "include",
                    "reason": "dirty tracked state",
                },
                {
                    "path": "untracked.txt",
                    "disposition": "include",
                    "reason": "user-authored local work",
                },
                {
                    "path": ".scratch/evidence.txt",
                    "disposition": "include",
                    "reason": "unique runtime evidence",
                },
                {
                    "path": "node_modules",
                    "disposition": "delete",
                    "reason": "dependency cache",
                    "proof": {
                        "kind": "regenerate",
                        "command": "npm ci",
                        "setSha256": covered_set_digest(inventory, "node_modules"),
                    },
                },
            ],
            "restoreCommands": ["npm ci", "git status --short"],
        }
        self.selection.write_text(json.dumps(selection, indent=2), encoding="utf-8")

    def test_inventory_classifies_git_and_local_state_without_dot_git(self) -> None:
        inventory = self.inventory()
        entries = {entry["path"]: entry for entry in inventory["entries"]}

        self.assertNotIn(".git/config", entries)
        self.assertEqual(entries["tracked.txt"]["gitClass"], "tracked")
        self.assertTrue(entries["tracked.txt"]["dirtyTracked"])
        self.assertEqual(entries["untracked.txt"]["gitClass"], "untracked")
        self.assertEqual(entries[".scratch/evidence.txt"]["gitClass"], "ignored")
        self.assertEqual(entries["node_modules/cache.bin"]["gitClass"], "ignored")
        self.assertEqual(len(inventory["snapshot"]["digest"]), 64)
        self.assertEqual(
            set(inventory["repository"]),
            {"historyState", "head", "remotes", "remoteEvidence", "gitExecutable", "gitMetadataHashes"},
        )
        self.assertEqual("committed", inventory["repository"]["historyState"])
        self.assertEqual(str(GIT_EXECUTABLE), inventory["repository"]["gitExecutable"]["path"])
        self.assertEqual(64, len(inventory["repository"]["gitExecutable"]["sha256"]))
        self.assertTrue(
            inventory["repository"]["remoteEvidence"]["origin"]["headReachable"]
        )
        serialized = json.dumps(inventory)
        self.assertNotIn("transfer-user", serialized)
        self.assertNotIn("transfer-secret", serialized)
        credentialed = next(
            remote
            for remote in inventory["repository"]["remotes"]
            if remote["name"] == "credentialed"
        )
        self.assertEqual(credentialed["url"], "https://example.invalid/repo.git")

    def test_explicit_git_executable_ignores_cwd_and_path_impostor(self) -> None:
        impostor = self.repo / "git.exe"
        sentinel = self.root / "impostor-ran.txt"
        impostor.write_text(f"write {sentinel}\n", encoding="utf-8")
        environment = os.environ.copy()
        environment["PATH"] = str(self.repo) + os.pathsep + environment.get("PATH", "")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "inventory", "--repo", str(self.repo), "--output", str(self.inventory_path), "--git-executable", str(GIT_EXECUTABLE)],
            cwd=self.repo,
            text=True,
            capture_output=True,
            env=environment,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(sentinel.exists())

    def test_bundle_refuses_incomplete_local_only_classification(self) -> None:
        inventory = self.inventory()
        self.write_selection(inventory)
        selection = json.loads(self.selection.read_text(encoding="utf-8"))
        selection["items"] = [
            item for item in selection["items"] if item["path"] != "untracked.txt"
        ]
        self.selection.write_text(json.dumps(selection), encoding="utf-8")

        result = run(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--output",
            self.bundle,
            expect=2,
        )
        self.assertIn("unclassified local-only entries", result.stderr)
        self.assertFalse(self.bundle.exists())

    def test_bundle_is_deterministic_and_verify_is_byte_exact(self) -> None:
        inventory = self.inventory()
        self.write_selection(inventory)
        second = self.root / "transfer-second.zip"

        run(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--output",
            self.bundle,
        )
        run(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--output",
            second,
        )

        self.assertEqual(
            hashlib.sha256(self.bundle.read_bytes()).hexdigest(),
            hashlib.sha256(second.read_bytes()).hexdigest(),
        )
        verified = json.loads(
            run(
                "verify",
                "--bundle",
                self.bundle,
                "--inventory",
                self.inventory_path,
                "--selection",
                self.selection,
                "--source",
                self.repo,
            ).stdout
        )
        self.assertEqual(verified["mismatches"], 0)
        self.assertEqual(verified["payloadFiles"], 3)
        receiver_payload_check = json.loads(
            run("verify", "--bundle", self.bundle, "--source", self.repo).stdout
        )
        self.assertEqual(receiver_payload_check["mismatches"], 0)
        self.assertEqual(receiver_payload_check["verificationMode"], "payload-source")
        (self.repo / "untracked.txt").write_text("receiver drift\n", encoding="utf-8")
        mismatch = run(
            "verify", "--bundle", self.bundle, "--source", self.repo, expect=2
        )
        mismatch_result = json.loads(mismatch.stdout)
        self.assertFalse(mismatch_result["verified"])
        self.assertGreater(mismatch_result["mismatches"], 0)
        with zipfile.ZipFile(self.bundle) as archive:
            names = archive.namelist()
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("_repo-transfer/manifest.json", names)
        self.assertIn("tracked.txt", names)
        self.assertNotIn("node_modules/cache.bin", names)

    def test_bundle_refuses_source_drift_after_inventory(self) -> None:
        inventory = self.inventory()
        self.write_selection(inventory)
        (self.repo / ".scratch" / "evidence.txt").write_text(
            "changed after audit\n", encoding="utf-8"
        )

        result = run(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--output",
            self.bundle,
            expect=2,
        )
        self.assertIn("inventory drift", result.stderr)
        self.assertFalse(self.bundle.exists())

    def test_cleanup_is_preview_only_and_rejects_generic_apply(self) -> None:
        inventory = self.inventory()
        self.write_selection(inventory)
        run(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--output",
            self.bundle,
        )

        planned = json.loads(
            run(
                "cleanup",
                "--repo",
                self.repo,
                "--inventory",
                self.inventory_path,
                "--selection",
                self.selection,
                "--bundle",
                self.bundle,
            ).stdout
        )
        self.assertFalse(planned["applied"])
        self.assertTrue((self.repo / "node_modules" / "cache.bin").exists())

        result = run(
            "cleanup",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--bundle",
            self.bundle,
            "--apply",
            expect=2,
        )
        self.assertIn("automatic deletion is not supported", result.stderr)
        self.assertTrue((self.repo / "node_modules" / "cache.bin").exists())
        self.assertTrue((self.repo / ".scratch" / "evidence.txt").exists())
        self.assertTrue((self.repo / "tracked.txt").exists())

    def test_selection_cannot_escape_repository(self) -> None:
        inventory = self.inventory()
        self.write_selection(inventory)
        selection = json.loads(self.selection.read_text(encoding="utf-8"))
        selection["items"].append(
            {
                "path": "../outside.txt",
                "disposition": "include",
                "reason": "invalid escape",
            }
        )
        self.selection.write_text(json.dumps(selection), encoding="utf-8")

        result = run(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--output",
            self.bundle,
            expect=2,
        )
        self.assertIn("escapes repository", result.stderr)

    def test_external_disposition_requires_verified_receipt(self) -> None:
        inventory = self.inventory()
        self.write_selection(inventory)
        selection = json.loads(self.selection.read_text(encoding="utf-8"))
        evidence = next(
            item for item in selection["items"] if item["path"] == ".scratch/evidence.txt"
        )
        evidence["disposition"] = "external"
        self.selection.write_text(json.dumps(selection), encoding="utf-8")

        result = run(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--output",
            self.bundle,
            expect=2,
        )
        self.assertIn("external receipt is required", result.stderr)

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_reparse_entry_requires_external_metadata_disposition(self) -> None:
        target = self.root / "junction-target"
        target.mkdir()
        (target / "outside.txt").write_text("outside\n", encoding="utf-8")
        link = self.repo / "linked-cache"
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            text=True,
            capture_output=True,
        )
        if created.returncode:
            self.skipTest(f"junction unavailable: {created.stderr or created.stdout}")

        inventory = self.inventory()
        self.write_selection(inventory)
        selection = json.loads(self.selection.read_text(encoding="utf-8"))
        selection["items"].append(
            {
                "path": "linked-cache",
                "disposition": "delete",
                "reason": "must not recursively delete a junction",
                "proof": {"kind": "regenerate", "command": "recreate cache"},
            }
        )
        self.selection.write_text(json.dumps(selection), encoding="utf-8")

        result = run(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--output",
            self.bundle,
            expect=2,
        )
        self.assertIn("reparse entries require external disposition", result.stderr)


class UnbornRepoTransferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "--initial-branch=main")
        self.inventory_path = self.root / "inventory.json"
        self.selection_path = self.root / "selection.json"
        self.bundle_path = self.root / "transfer.zip"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def raw_git(self, *args: str) -> bytes:
        result = subprocess.run(
            [str(GIT_EXECUTABLE), *args],
            cwd=self.repo,
            capture_output=True,
            check=True,
        )
        return result.stdout

    def inventory(self) -> dict:
        run("inventory", "--repo", self.repo, "--output", self.inventory_path)
        return json.loads(self.inventory_path.read_text(encoding="utf-8"))

    def assert_unborn_repository(self, inventory: dict) -> None:
        self.assertEqual("unborn", inventory["repository"]["historyState"])
        self.assertIsNone(inventory["repository"]["head"])

    def assert_inventory_metadata_matches_git(self, inventory: dict) -> None:
        expected = {
            "_repo-transfer/git-status.bin": self.raw_git(
                "status", "--no-renames", "--porcelain=v1", "-z", "--untracked-files=all"
            ),
            "_repo-transfer/git-staged.diff": self.raw_git(
                "diff", "--no-renames", "--cached", "--binary", "--no-ext-diff", "--no-textconv"
            ),
            "_repo-transfer/git-unstaged.diff": self.raw_git(
                "diff", "--no-renames", "--binary", "--no-ext-diff", "--no-textconv"
            ),
        }
        self.assertEqual(
            {name: hashlib.sha256(data).hexdigest() for name, data in expected.items()},
            inventory["repository"]["gitMetadataHashes"],
        )

    def write_selection(self, inventory: dict, mode: str = "none") -> None:
        strategy: dict[str, object] = {"mode": mode}
        if mode == "remote-clone":
            strategy.update(remote="origin", expectedHead=inventory["repository"]["head"])
        selection = {
            "schemaVersion": 1,
            "inventoryDigest": inventory["snapshot"]["digest"],
            "gitStrategy": strategy,
            "items": [
                {"path": entry["path"], "disposition": "include", "reason": "preserve unborn repository state"}
                for entry in inventory["entries"]
            ],
            "restoreCommands": [],
        }
        self.selection_path.write_text(json.dumps(selection), encoding="utf-8")

    def bundle_and_verify(self, inventory: dict) -> None:
        self.write_selection(inventory)
        run(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection_path,
            "--output",
            self.bundle_path,
        )
        verified = json.loads(
            run(
                "verify",
                "--bundle",
                self.bundle_path,
                "--inventory",
                self.inventory_path,
                "--selection",
                self.selection_path,
                "--source",
                self.repo,
            ).stdout
        )
        self.assertEqual(0, verified["mismatches"])
        with zipfile.ZipFile(self.bundle_path) as archive:
            manifest = json.loads(archive.read("_repo-transfer/manifest.json"))
        self.assertEqual("unborn", manifest["repository"]["historyState"])
        self.assertIsNone(manifest["repository"]["head"])

    def test_inventory_preserves_staged_only_state_without_fabricating_head(self) -> None:
        (self.repo / "staged.txt").write_text("staged bytes\n", encoding="utf-8")
        git(self.repo, "add", "staged.txt")
        remote = self.root / "remote.git"
        git(self.root, "init", "--bare", str(remote))
        git(self.repo, "remote", "add", "origin", str(remote))

        inventory = self.inventory()
        entry = next(entry for entry in inventory["entries"] if entry["path"] == "staged.txt")
        self.assert_unborn_repository(inventory)
        self.assertEqual("tracked", entry["gitClass"])
        self.assertTrue(entry["dirtyTracked"])
        self.assertFalse(inventory["repository"]["remoteEvidence"]["origin"]["headReachable"])
        self.assert_inventory_metadata_matches_git(inventory)

        for mode in ("remote-clone", "git-bundle"):
            with self.subTest(mode=mode):
                self.write_selection(inventory, mode)
                result = run(
                    "bundle",
                    "--repo",
                    self.repo,
                    "--inventory",
                    self.inventory_path,
                    "--selection",
                    self.selection_path,
                    "--output",
                    self.root / f"{mode}.zip",
                    expect=2,
                )
                self.assertIn("unborn repositories require git strategy none", result.stderr)
        self.bundle_and_verify(inventory)

    def test_inventory_preserves_staged_and_unstaged_bytes(self) -> None:
        path = self.repo / "both.txt"
        path.write_text("staged bytes\n", encoding="utf-8")
        git(self.repo, "add", "both.txt")
        path.write_text("staged bytes\nunstaged bytes\n", encoding="utf-8")

        inventory = self.inventory()
        entry = next(entry for entry in inventory["entries"] if entry["path"] == "both.txt")
        self.assert_unborn_repository(inventory)
        self.assertEqual("tracked", entry["gitClass"])
        self.assertTrue(entry["dirtyTracked"])
        self.assert_inventory_metadata_matches_git(inventory)
        self.assertNotEqual(hashlib.sha256(b"").hexdigest(), inventory["repository"]["gitMetadataHashes"]["_repo-transfer/git-staged.diff"])
        self.assertNotEqual(hashlib.sha256(b"").hexdigest(), inventory["repository"]["gitMetadataHashes"]["_repo-transfer/git-unstaged.diff"])
        self.bundle_and_verify(inventory)

    def test_inventory_preserves_untracked_only_bytes(self) -> None:
        (self.repo / "untracked.txt").write_text("untracked bytes\n", encoding="utf-8")

        inventory = self.inventory()
        entry = next(entry for entry in inventory["entries"] if entry["path"] == "untracked.txt")
        self.assert_unborn_repository(inventory)
        self.assertEqual("untracked", entry["gitClass"])
        self.assertFalse(entry["dirtyTracked"])
        self.assert_inventory_metadata_matches_git(inventory)
        self.bundle_and_verify(inventory)


if __name__ == "__main__":
    unittest.main()
