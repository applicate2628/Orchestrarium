from __future__ import annotations

"""Regression tests for the accepted transfer-tool security contract.

The tests use only temporary repositories and the public command-line
interface.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "src.codex" / "skills" / "manual-repo-transfer" / "scripts" / "repo_transfer.py"
TRANSFER_ROOT = "_repo-transfer"
MANIFEST = f"{TRANSFER_ROOT}/manifest.json"
GIT_EXECUTABLE = Path(shutil.which("git") or "").resolve()
if not GIT_EXECUTABLE.is_file():
    raise RuntimeError("test host must provide an explicit Git executable")


def load_transfer_module():
    spec = importlib.util.spec_from_file_location("repo_transfer_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    if completed.returncode:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.stdout.strip()


def run_cli(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *(str(arg) for arg in args), "--git-executable", str(GIT_EXECUTABLE)],
        text=True,
        capture_output=True,
    )


def path_covers(parent: str, child: str) -> bool:
    return child == parent or child.startswith(parent + "/")


class IoBoundaryTests(unittest.TestCase):
    def test_inventory_json_budget_includes_final_newline_and_refuses_overage_before_output(self) -> None:
        module = load_transfer_module()
        inventory = {"entries": [{"path": "entry"}]}
        encoded = module.canonical_json(inventory)
        with tempfile.TemporaryDirectory(prefix="repo-transfer-inventory-frame-") as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            output = Path(temp) / "inventory.json"
            stderr = io.StringIO()
            with (
                mock.patch.object(module, "MAX_JSON_BYTES", len(encoded) + 1),
                mock.patch.object(module, "bind_repository", return_value=module.BoundRepository(root, GIT_EXECUTABLE, "0" * 64)),
                mock.patch.object(module, "build_inventory", return_value=inventory),
                contextlib.redirect_stderr(stderr),
            ):
                self.assertEqual(0, module.main(["inventory", "--repo", str(root), "--git-executable", str(GIT_EXECUTABLE), "--output", str(output)]))
            self.assertEqual(encoded + b"\n", output.read_bytes())
            output.unlink()
            stderr = io.StringIO()
            with (
                mock.patch.object(module, "MAX_JSON_BYTES", len(encoded)),
                mock.patch.object(module, "bind_repository", return_value=module.BoundRepository(root, GIT_EXECUTABLE, "0" * 64)),
                mock.patch.object(module, "build_inventory", return_value=inventory),
                contextlib.redirect_stderr(stderr),
            ):
                self.assertEqual(2, module.main(["inventory", "--repo", str(root), "--git-executable", str(GIT_EXECUTABLE), "--output", str(output)]))
            self.assertIn("inventory output exceeds JSON limit", stderr.getvalue())
            self.assertFalse(output.exists())

    def test_nfkc_hostile_path_segments_are_rejected_directly_and_in_archives(self) -> None:
        module = load_transfer_module()
        for path in ("\uff0e", "\uff0e\uff0e", "safe\uff0fescape", "safe\uff3cescape"):
            with self.subTest(path=path):
                self.assertIsNotNone(module.portable_path_issue(path))
                self.assertEqual(path, module.selection_path(Path("unused"), path))
        with tempfile.TemporaryDirectory(prefix="repo-transfer-nfkc-archive-") as temp:
            bundle_path = Path(temp) / "hostile.zip"
            with zipfile.ZipFile(bundle_path, "w") as archive:
                archive.writestr("safe\uff0fescape", b"payload")
            result = run_cli("verify", "--bundle", bundle_path)
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("unsafe archive entry", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_standard_and_zip64_central_directory_limits_fail_before_zipfile_open(self) -> None:
        module = load_transfer_module()
        with tempfile.TemporaryDirectory(prefix="repo-transfer-zip-preflight-") as temp:
            root = Path(temp)
            standard = root / "standard.zip"
            with zipfile.ZipFile(standard, "w") as archive:
                archive.writestr(MANIFEST, b"{}")
            base_bytes = bytearray(standard.read_bytes())
            standard_bytes = bytearray(base_bytes)
            eocd = standard_bytes.rfind(b"PK\x05\x06")
            self.assertNotEqual(-1, eocd)
            struct.pack_into("<I", standard_bytes, eocd + 12, module.MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES + 1)
            standard.write_bytes(standard_bytes)

            zip64 = root / "zip64.zip"
            raw = bytearray(standard.read_bytes())
            struct.pack_into("<I", raw, eocd + 12, 0)
            central_offset = struct.unpack_from("<I", raw, eocd + 16)[0]
            zip64_eocd = struct.pack(
                "<4sQ2H2I4Q",
                b"PK\x06\x06",
                44,
                45,
                45,
                0,
                0,
                1,
                1,
                module.MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES + 1,
                central_offset,
            )
            locator = struct.pack("<4sIQI", b"PK\x06\x07", 0, eocd, 1)
            for offset, value in ((8, 0xFFFF), (10, 0xFFFF)):
                struct.pack_into("<H", raw, eocd + offset, value)
            for offset in (12, 16):
                struct.pack_into("<I", raw, eocd + offset, 0xFFFFFFFF)
            zip64.write_bytes(raw[:eocd] + zip64_eocd + locator + raw[eocd:])

            zip64_with_classic_fields = root / "zip64-with-classic-fields.zip"
            raw = bytearray(base_bytes)
            eocd = raw.rfind(b"PK\x05\x06")
            central_offset = struct.unpack_from("<I", raw, eocd + 16)[0]
            zip64_eocd = struct.pack(
                "<4sQ2H2I4Q",
                b"PK\x06\x06",
                44,
                45,
                45,
                0,
                0,
                1,
                1,
                module.MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES + 1,
                central_offset,
            )
            locator = struct.pack("<4sIQI", b"PK\x06\x07", 0, eocd, 1)
            zip64_with_classic_fields.write_bytes(raw[:eocd] + zip64_eocd + locator + raw[eocd:])

            malformed_zip64_locator = root / "malformed-zip64-locator.zip"
            raw = bytearray(base_bytes)
            eocd = raw.rfind(b"PK\x05\x06")
            locator = struct.pack("<4sIQI", b"PK\x06\x07", 0, 0, 2)
            malformed_zip64_locator.write_bytes(raw[:eocd] + locator + raw[eocd:])

            for bundle_path, message in (
                (standard, "archive resource limit"),
                (zip64, "archive resource limit"),
                (zip64_with_classic_fields, "archive resource limit"),
                (malformed_zip64_locator, "invalid bundle"),
            ):
                with self.subTest(bundle=bundle_path.name), mock.patch.object(
                    module.zipfile,
                    "ZipFile",
                    side_effect=AssertionError("ZipFile must not open before preflight"),
                ):
                    with self.assertRaisesRegex(module.ContractError, message):
                        module.verify(bundle_path, None, None, None)

    def test_bounded_subprocess_refuses_cap_plus_one_without_subprocess_run_capture(self) -> None:
        module = load_transfer_module()
        command = [
            sys.executable,
            "-B",
            "-c",
            "import sys; sys.stdout.buffer.write(b'x' * 65)",
        ]
        with mock.patch.object(module, "MAX_JSON_BYTES", 64), mock.patch.object(
            module.subprocess,
            "run",
            side_effect=AssertionError("subprocess.run capture is forbidden"),
        ):
            with self.assertRaisesRegex(module.ContractError, "git output exceeds JSON limit"):
                module.run_bounded_process(command, None, {})

    def test_bounded_subprocess_reaps_timed_out_child_as_contract_error(self) -> None:
        module = load_transfer_module()
        spawned: list[subprocess.Popen[bytes]] = []
        original_popen = subprocess.Popen

        def remember_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            process = original_popen(*args, **kwargs)
            spawned.append(process)
            return process

        command = [sys.executable, "-B", "-c", "import time; time.sleep(1)"]
        with (
            mock.patch.object(module, "GIT_COMMAND_TIMEOUT_SECONDS", 0.01),
            mock.patch.object(module.subprocess, "Popen", side_effect=remember_popen),
        ):
            with self.assertRaisesRegex(module.ContractError, "git command timed out"):
                module.run_bounded_process(command, None, {})
        self.assertEqual(1, len(spawned))
        self.assertIsNotNone(spawned[0].poll())

    def test_inventory_producer_refuses_overlimit_before_publishing_output(self) -> None:
        module = load_transfer_module()
        with tempfile.TemporaryDirectory(prefix="repo-transfer-inventory-cap-") as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            output = Path(temp) / "inventory.json"
            inventory = {"entries": [{"path": f"entry-{index}"} for index in range(10)]}
            self.assertGreater(len(module.canonical_json(inventory)), 64)
            stderr = io.StringIO()
            with (
                mock.patch.object(module, "MAX_JSON_BYTES", 64),
                mock.patch.object(module, "bind_repository", return_value=module.BoundRepository(root, GIT_EXECUTABLE, "0" * 64)),
                mock.patch.object(module, "build_inventory", return_value=inventory),
                contextlib.redirect_stderr(stderr),
            ):
                result = module.main(["inventory", "--repo", str(root), "--git-executable", str(GIT_EXECUTABLE), "--output", str(output)])
            self.assertEqual(2, result)
            self.assertIn("inventory output exceeds JSON limit", stderr.getvalue())
            self.assertFalse(output.exists())

    def test_trusted_verify_uses_one_zipfile_instance_for_all_archive_reads(self) -> None:
        module = load_transfer_module()
        with tempfile.TemporaryDirectory(prefix="repo-transfer-trusted-zip-") as temp:
            root = Path(temp)
            bundle_path = root / "transfer.zip"
            git_evidence = {"path": str(GIT_EXECUTABLE), "sha256": "0" * 64}
            inventory = {"snapshot": {"digest": "0" * 64}, "repository": {"head": "head", "gitExecutable": git_evidence}, "entries": []}
            selection = {"schemaVersion": module.SCHEMA_VERSION, "items": []}
            metadata = {name: b"" for name in module.METADATA_NAMES}
            manifest = {
                "schemaVersion": module.SCHEMA_VERSION,
                "inventoryDigest": inventory["snapshot"]["digest"],
                "selectionDigest": module.sha256_bytes(module.canonical_json(selection)),
                "repository": {"head": inventory["repository"]["head"], "gitExecutable": git_evidence},
                "payload": [],
                "metadata": [
                    {"path": name, "size": 0, "sha256": module.sha256_bytes(data)}
                    for name, data in metadata.items()
                ],
                "deletions": [],
            }
            with zipfile.ZipFile(bundle_path, "w") as archive:
                for name, data in metadata.items():
                    archive.writestr(name, data)
                archive.writestr(MANIFEST, module.canonical_json(manifest))
            with (
                mock.patch.object(module, "bind_repository", return_value=module.BoundRepository(root, GIT_EXECUTABLE, "0" * 64)),
                mock.patch.object(module, "load_validated_snapshot", return_value=(root, inventory, selection, [])),
                mock.patch.object(module.zipfile, "ZipFile", wraps=zipfile.ZipFile) as open_archive,
            ):
                verified = module.verify(bundle_path, Path("inventory.json"), Path("selection.json"), root, GIT_EXECUTABLE)
            self.assertTrue(verified["verified"])
            self.assertEqual(1, open_archive.call_count)

    def test_unsupported_zip_compression_is_a_contract_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="repo-transfer-unsupported-zip-") as temp:
            bundle_path = Path(temp) / "unsupported.zip"
            with zipfile.ZipFile(bundle_path, "w") as archive:
                archive.writestr(MANIFEST, b"{}")
            raw = bytearray(bundle_path.read_bytes())
            for signature, offset in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
                position = raw.find(signature)
                self.assertNotEqual(-1, position)
                struct.pack_into("<H", raw, position + offset, 99)
            bundle_path.write_bytes(raw)
            result = run_cli("verify", "--bundle", bundle_path)
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("invalid internal manifest", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


class SecurityContractTests(unittest.TestCase):
    """Regression tests for the accepted defensive transfer contract."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="repo-transfer-security-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "origin.git"
        self.repo.mkdir()
        git(self.repo, "init", "--initial-branch=main")
        git(self.repo, "config", "user.name", "Security QA")
        git(self.repo, "config", "user.email", "security-qa@example.invalid")
        (self.repo / ".gitignore").write_text(".scratch/\ncache/\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        (self.repo / "secret.txt").write_text("secret before edit\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore", "tracked.txt", "secret.txt")
        git(self.repo, "commit", "-m", "base")
        git(self.root, "init", "--bare", str(self.remote))
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-u", "origin", "main")
        (self.repo / "secret.txt").write_text("TOP-SECRET-CHANGED-BYTES\n", encoding="utf-8")
        git(self.repo, "add", "secret.txt")
        (self.repo / "work.txt").write_text("local work\n", encoding="utf-8")
        (self.repo / ".scratch").mkdir()
        (self.repo / ".scratch" / "evidence.txt").write_text("evidence\n", encoding="utf-8")
        (self.repo / "cache").mkdir()
        (self.repo / "cache" / "cache.bin").write_bytes(b"cache")
        self.inventory_path = self.root / "inventory.json"
        self.selection_path = self.root / "selection.json"
        self.bundle_path = self.root / "transfer.zip"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def inventory(self) -> dict:
        result = run_cli("inventory", "--repo", self.repo, "--output", self.inventory_path)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(self.inventory_path.read_text(encoding="utf-8"))

    def exact_set_sha256(self, inventory: dict, selection_path: str) -> str:
        entries = [
            entry for entry in inventory["entries"] if path_covers(selection_path, entry["path"])
        ]
        return sha256(canonical_json(entries))

    def selection(
        self,
        inventory: dict,
        *,
        remote: str = "origin",
        items: list[dict] | None = None,
        strategy: str = "remote-clone",
    ) -> dict:
        if items is None:
            items = [
                {"path": "work.txt", "disposition": "include", "reason": "local work"},
                {"path": ".scratch/evidence.txt", "disposition": "include", "reason": "evidence"},
                {
                    "path": "secret.txt",
                    "disposition": "external",
                    "reason": "restricted dirty tracked data",
                    "receipt": {
                        "artifact": "vault:secret",
                        "setSha256": self.exact_set_sha256(inventory, "secret.txt"),
                    },
                },
                {
                    "path": "cache",
                    "disposition": "delete",
                    "reason": "rebuildable cache",
                    "proof": {
                        "kind": "regenerate",
                        "command": "rebuild-cache",
                        "setSha256": self.exact_set_sha256(inventory, "cache"),
                    },
                },
            ]
        return {
            "schemaVersion": 1,
            "inventoryDigest": inventory["snapshot"]["digest"],
            "gitStrategy": {
                "mode": strategy,
                "remote": remote,
                "expectedHead": inventory["repository"]["head"],
            },
            "items": items,
            "restoreCommands": [],
        }

    def write_selection(self, selection: dict) -> None:
        self.selection_path.write_text(json.dumps(selection), encoding="utf-8")

    def assert_contract_error(self, result: subprocess.CompletedProcess[str], message: str) -> None:
        self.assertEqual(2, result.returncode, f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn(message, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def bundle(self) -> subprocess.CompletedProcess[str]:
        return run_cli(
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

    def test_selection_rows_never_overlap_in_either_direction(self) -> None:
        inventory = self.inventory()
        receipt = {"artifact": "vault:secret", "setSha256": self.exact_set_sha256(inventory, ".scratch/secret.txt")}
        for items in (
            [
                {"path": ".scratch", "disposition": "include", "reason": "parent"},
                {"path": ".scratch/evidence.txt", "disposition": "external", "reason": "child", "receipt": receipt},
                {"path": "work.txt", "disposition": "include", "reason": "work"},
                {"path": "secret.txt", "disposition": "external", "reason": "secret", "receipt": {"artifact": "vault", "setSha256": self.exact_set_sha256(inventory, "secret.txt")}},
                {"path": "cache", "disposition": "delete", "reason": "cache", "proof": {"kind": "regenerate", "command": "rebuild", "setSha256": self.exact_set_sha256(inventory, "cache")}},
            ],
            [
                {"path": ".scratch", "disposition": "external", "reason": "parent", "receipt": {"artifact": "vault", "setSha256": self.exact_set_sha256(inventory, ".scratch")}},
                {"path": ".scratch/evidence.txt", "disposition": "include", "reason": "child"},
                {"path": "work.txt", "disposition": "include", "reason": "work"},
                {"path": "secret.txt", "disposition": "external", "reason": "secret", "receipt": {"artifact": "vault", "setSha256": self.exact_set_sha256(inventory, "secret.txt")}},
                {"path": "cache", "disposition": "delete", "reason": "cache", "proof": {"kind": "regenerate", "command": "rebuild", "setSha256": self.exact_set_sha256(inventory, "cache")}},
            ],
        ):
            with self.subTest(items=items[:2]):
                self.write_selection(self.selection(inventory, items=items))
                self.assert_contract_error(self.bundle(), "selection rows overlap")

    def test_internal_archive_namespace_requires_external_disposition(self) -> None:
        module = load_transfer_module()
        for path in ("_repo-transfer", "_repo-transfer/x", "_repo-transfer/git-status.bin"):
            with self.subTest(path=path):
                entry = {
                    "path": path,
                    "entryType": "file",
                    "gitClass": "untracked",
                    "dirtyTracked": False,
                    "size": 1,
                    "sha256": sha256(b"x"),
                }
                repository = {
                    "head": "0" * 40,
                    "remotes": [],
                    "remoteEvidence": {},
                    "gitMetadataHashes": {},
                }
                inventory = {
                    "schemaVersion": 1,
                    "repository": repository,
                    "entries": [entry],
                    "snapshot": {
                        "digest": sha256(
                            canonical_json({"entries": [entry], "repository": repository})
                        )
                    },
                }
                receipt = {
                    "artifact": "vault:reserved-namespace",
                    "setSha256": sha256(canonical_json([entry])),
                }
                external = {
                    "schemaVersion": 1,
                    "inventoryDigest": inventory["snapshot"]["digest"],
                    "gitStrategy": {"mode": "none"},
                    "items": [
                        {
                            "path": path,
                            "disposition": "external",
                            "reason": "reserved helper namespace",
                            "receipt": receipt,
                        }
                    ],
                }
                rows = module.validate_selection(self.repo, inventory, external)
                self.assertEqual("external", rows[0]["disposition"])
                for disposition in ("include", "delete"):
                    invalid = json.loads(json.dumps(external))
                    invalid["items"][0]["disposition"] = disposition
                    invalid["items"][0].pop("receipt", None)
                    if disposition == "delete":
                        invalid["items"][0]["proof"] = {
                            "kind": "regenerate",
                            "command": "rebuild",
                            "setSha256": receipt["setSha256"],
                        }
                    with self.assertRaisesRegex(
                        module.ContractError,
                        "internal archive namespace requires external disposition",
                    ):
                        module.validate_selection(self.repo, inventory, invalid)

    def test_hostile_inventory_identity_is_nameable_only_as_external(self) -> None:
        module = load_transfer_module()
        entry = {
            "path": "wild?.txt",
            "entryType": "file",
            "gitClass": "ignored",
            "dirtyTracked": False,
            "size": 1,
            "sha256": sha256(b"x"),
            "metadataOnly": True,
            "hostile": True,
        }
        repository = {
            "head": "0" * 40,
            "remotes": [],
            "remoteEvidence": {},
            "gitMetadataHashes": {},
        }
        inventory = {
            "schemaVersion": 1,
            "repository": repository,
            "entries": [entry],
            "snapshot": {
                "digest": sha256(
                    canonical_json({"entries": [entry], "repository": repository})
                )
            },
        }
        receipt = {
            "artifact": "vault:hostile-name",
            "setSha256": sha256(canonical_json([entry])),
        }
        external = {
            "schemaVersion": 1,
            "inventoryDigest": inventory["snapshot"]["digest"],
            "gitStrategy": {"mode": "none"},
            "items": [
                {
                    "path": "wild?.txt",
                    "disposition": "external",
                    "reason": "portable external storage",
                    "receipt": receipt,
                }
            ],
        }
        rows = module.validate_selection(self.repo, inventory, external)
        self.assertEqual("external", rows[0]["disposition"])
        for disposition in ("include", "delete"):
            with self.subTest(disposition=disposition):
                invalid = json.loads(json.dumps(external))
                invalid["items"][0]["disposition"] = disposition
                invalid["items"][0].pop("receipt", None)
                if disposition == "delete":
                    invalid["items"][0]["proof"] = {
                        "kind": "regenerate",
                        "command": "rebuild",
                        "setSha256": receipt["setSha256"],
                    }
                with self.assertRaisesRegex(
                    module.ContractError, "reparse or hostile entries require external disposition"
                ):
                    module.validate_selection(self.repo, inventory, invalid)

    def test_windows_device_names_with_extensions_and_superscripts_are_hostile(self) -> None:
        module = load_transfer_module()
        for name in (
            "CON.txt",
            "conin$",
            "CONIN$.txt",
            "ConOut$.log",
            "ＣＯＮＯＵＴ$.txt",
            "NUL.tar.gz",
            "COM¹",
            "COM².log",
            "COM³.txt",
            "LPT¹",
            "LPT².log",
            "LPT³.txt",
        ):
            with self.subTest(name=name):
                self.assertIsNotNone(module.portable_path_issue(name))
        for name in ("CONSOLE.txt", "CONINBOX.txt", "CONOUTLET.log", "COM10.txt", "LPT10.log"):
            with self.subTest(name=name):
                self.assertIsNone(module.portable_path_issue(name))

    def test_git_executable_rejects_ambient_and_untrusted_locations(self) -> None:
        module = load_transfer_module()
        missing = self.root / "missing-git.exe"
        in_repository = self.repo / "git.exe"
        in_repository.write_text("impostor\n", encoding="utf-8")
        with self.assertRaisesRegex(module.ContractError, "absolute"):
            module.bind_repository(self.repo, Path("git"))
        with self.assertRaisesRegex(module.ContractError, "ordinary file"):
            module.bind_repository(self.repo, missing)
        with self.assertRaisesRegex(module.ContractError, "outside the repository"):
            module.bind_repository(self.repo, in_repository)
        with mock.patch.object(module, "is_reparse_point", side_effect=lambda path: path == GIT_EXECUTABLE):
            with self.assertRaisesRegex(module.ContractError, "reparse point"):
                module.bind_repository(self.repo, GIT_EXECUTABLE)

    def test_external_receipt_binds_exact_covered_entry_set(self) -> None:
        inventory = self.inventory()
        valid = self.selection(inventory)
        self.write_selection(valid)
        self.assertEqual(0, self.bundle().returncode, "a correct external receipt must be accepted")
        for replacement in (None, "0" * 64):
            with self.subTest(replacement=replacement):
                invalid = self.selection(inventory)
                receipt = invalid["items"][2]["receipt"]
                if replacement is None:
                    del receipt["setSha256"]
                else:
                    receipt["setSha256"] = replacement
                self.write_selection(invalid)
                self.assert_contract_error(self.bundle(), "external receipt setSha256")

    def test_delete_proof_binds_exact_covered_entry_set(self) -> None:
        inventory = self.inventory()
        items = [
            {"path": "work.txt", "disposition": "include", "reason": "work"},
            {"path": ".scratch/evidence.txt", "disposition": "include", "reason": "evidence"},
            {"path": "secret.txt", "disposition": "include", "reason": "ordinary test data"},
            {"path": "cache", "disposition": "delete", "reason": "cache", "proof": {"kind": "regenerate", "command": "rebuild"}},
        ]
        for replacement in (None, "f" * 64):
            with self.subTest(replacement=replacement):
                invalid = self.selection(inventory, items=json.loads(json.dumps(items)))
                proof = invalid["items"][-1]["proof"]
                if replacement is not None:
                    proof["setSha256"] = replacement
                self.write_selection(invalid)
                self.assert_contract_error(self.bundle(), "delete proof setSha256")

    def test_remote_clone_requires_the_named_remote_tracking_evidence(self) -> None:
        inventory = self.inventory()
        remote_b = self.root / "remote-b.git"
        git(self.root, "init", "--bare", str(remote_b))
        git(self.repo, "remote", "add", "b", str(remote_b))
        git(self.repo, "push", "b", "main")
        git(self.repo, "remote", "add", "a", str(self.root / "empty-a.git"))
        git(self.root, "init", "--bare", str(self.root / "empty-a.git"))
        # Refresh inventory after remotes are added: only b has a tracking ref for HEAD.
        inventory = self.inventory()
        for name in ("does-not-exist", "a"):
            with self.subTest(remote=name):
                self.write_selection(self.selection(inventory, remote=name))
                self.assert_contract_error(self.bundle(), "selected remote has no HEAD tracking evidence")

    def test_snapshot_binds_sanitized_remote_evidence_and_git_metadata(self) -> None:
        inventory = self.inventory()
        self.assertIn("remoteEvidence", inventory["repository"])
        self.assertIn("origin", inventory["repository"]["remoteEvidence"])
        self.assertNotIn(str(self.remote), canonical_json(inventory).decode("utf-8"))
        self.write_selection(self.selection(inventory))
        result = self.bundle()
        self.assertEqual(0, result.returncode, result.stderr)
        # Only the Git index changes: no worktree file is modified.
        git(self.repo, "reset", "HEAD", "secret.txt")
        result = run_cli(
            "verify", "--bundle", self.bundle_path, "--inventory", self.inventory_path,
            "--selection", self.selection_path, "--source", self.repo,
        )
        self.assert_contract_error(result, "metadata snapshot mismatch")
        cleanup = run_cli(
            "cleanup", "--repo", self.repo, "--inventory", self.inventory_path,
            "--selection", self.selection_path, "--bundle", self.bundle_path,
        )
        self.assert_contract_error(cleanup, "metadata snapshot mismatch")

    def test_archive_metadata_excludes_external_dirty_tracked_paths_and_dot_git(self) -> None:
        inventory = self.inventory()
        self.assertFalse(any(entry["path"] == ".git" or entry["path"].startswith(".git/") for entry in inventory["entries"]))
        self.write_selection(self.selection(inventory))
        self.assertEqual(0, self.bundle().returncode)
        with zipfile.ZipFile(self.bundle_path) as archive:
            names = archive.namelist()
            metadata = b"".join(archive.read(name) for name in names if name.startswith(f"{TRANSFER_ROOT}/git-"))
        self.assertNotIn(b"secret.txt", metadata)
        self.assertNotIn(b"TOP-SECRET-CHANGED-BYTES", metadata)
        self.assertFalse(any("secret.txt" in name for name in names))

    def test_empty_include_set_produces_empty_git_metadata(self) -> None:
        inventory = self.inventory()
        items = []
        for path in ("work.txt", ".scratch/evidence.txt", "secret.txt"):
            items.append(
                {
                    "path": path,
                    "disposition": "external",
                    "reason": "restricted or separately preserved",
                    "receipt": {
                        "artifact": f"vault:{path}",
                        "setSha256": self.exact_set_sha256(inventory, path),
                    },
                }
            )
        items.append(
            {
                "path": "cache",
                "disposition": "delete",
                "reason": "rebuildable cache",
                "proof": {
                    "kind": "regenerate",
                    "command": "rebuild",
                    "setSha256": self.exact_set_sha256(inventory, "cache"),
                },
            }
        )
        self.write_selection(self.selection(inventory, items=items))
        self.assertEqual(0, self.bundle().returncode)
        with zipfile.ZipFile(self.bundle_path) as archive:
            names = archive.namelist()
            metadata = [
                archive.read(name)
                for name in names
                if name.startswith(f"{TRANSFER_ROOT}/git-")
            ]
        self.assertTrue(metadata)
        self.assertTrue(all(value == b"" for value in metadata))
        self.assertFalse(any("secret.txt" in name for name in names))

    def test_tracked_deletion_is_inventoried_and_preserved_in_metadata(self) -> None:
        repo = self.root / "tracked-deletion-repo"
        repo.mkdir()
        git(repo, "init", "--initial-branch=main")
        git(repo, "config", "user.name", "Deletion QA")
        git(repo, "config", "user.email", "deletion@example.invalid")
        (repo / "deleted.txt").write_text("remove me\n", encoding="utf-8")
        git(repo, "add", "deleted.txt")
        git(repo, "commit", "-m", "base")
        (repo / "deleted.txt").unlink()
        inventory_path = self.root / "deletion-inventory.json"
        selection_path = self.root / "deletion-selection.json"
        bundle_path = self.root / "deletion-transfer.zip"
        result = run_cli("inventory", "--repo", repo, "--output", inventory_path)
        self.assertEqual(0, result.returncode, result.stderr)
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        deleted = next(entry for entry in inventory["entries"] if entry["path"] == "deleted.txt")
        self.assertEqual("deleted", deleted["entryType"])
        self.assertTrue(deleted["dirtyTracked"])
        selection = {
            "schemaVersion": 1,
            "inventoryDigest": inventory["snapshot"]["digest"],
            "gitStrategy": {"mode": "none"},
            "items": [
                {
                    "path": "deleted.txt",
                    "disposition": "include",
                    "reason": "preserve tracked deletion state",
                }
            ],
            "restoreCommands": [],
        }
        selection_path.write_text(json.dumps(selection), encoding="utf-8")
        result = run_cli(
            "bundle",
            "--repo",
            repo,
            "--inventory",
            inventory_path,
            "--selection",
            selection_path,
            "--output",
            bundle_path,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        with zipfile.ZipFile(bundle_path) as archive:
            self.assertNotIn("deleted.txt", archive.namelist())
            metadata = b"".join(
                archive.read(name)
                for name in archive.namelist()
                if name.startswith(f"{TRANSFER_ROOT}/git-")
            )
        self.assertIn(b"deleted.txt", metadata)

    def test_staged_tracked_deletion_is_inventoried_and_bound_into_receiver_check(self) -> None:
        repo = self.root / "staged-deletion-repo"
        repo.mkdir()
        git(repo, "init", "--initial-branch=main")
        git(repo, "config", "user.name", "Deletion QA")
        git(repo, "config", "user.email", "deletion@example.invalid")
        (repo / "deleted.txt").write_text("remove me\n", encoding="utf-8")
        git(repo, "add", "deleted.txt")
        git(repo, "commit", "-m", "base")
        git(repo, "rm", "deleted.txt")
        inventory_path = self.root / "staged-deletion-inventory.json"
        selection_path = self.root / "staged-deletion-selection.json"
        bundle_path = self.root / "staged-deletion-transfer.zip"
        self.assertEqual(0, run_cli("inventory", "--repo", repo, "--output", inventory_path).returncode)
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        deleted = next(entry for entry in inventory["entries"] if entry["path"] == "deleted.txt")
        self.assertEqual("deleted", deleted["entryType"])
        selection_path.write_text(json.dumps({
            "schemaVersion": 1,
            "inventoryDigest": inventory["snapshot"]["digest"],
            "gitStrategy": {"mode": "none"},
            "items": [{"path": "deleted.txt", "disposition": "include", "reason": "preserve staged deletion"}],
            "restoreCommands": [],
        }), encoding="utf-8")
        bundle = run_cli("bundle", "--repo", repo, "--inventory", inventory_path, "--selection", selection_path, "--output", bundle_path)
        self.assertEqual(0, bundle.returncode, bundle.stderr)
        absent = run_cli("verify", "--bundle", bundle_path, "--source", repo)
        self.assertEqual(0, absent.returncode, absent.stderr)
        (repo / "deleted.txt").write_text("resurrected\n", encoding="utf-8")
        present = run_cli("verify", "--bundle", bundle_path, "--source", repo)
        self.assertEqual(2, present.returncode, present.stderr)
        self.assertEqual(1, json.loads(present.stdout)["mismatches"])

    def test_assume_unchanged_and_skip_worktree_files_are_conservatively_local_state(self) -> None:
        for path, flag in (("assume.txt", "--assume-unchanged"), ("skip.txt", "--skip-worktree")):
            with self.subTest(flag=flag):
                (self.repo / path).write_text("base\n", encoding="utf-8")
                git(self.repo, "add", path)
                git(self.repo, "commit", "-m", f"add {path}")
                git(self.repo, "update-index", flag, path)
                (self.repo / path).write_text(f"physical {flag}\n", encoding="utf-8")
                inventory = self.inventory()
                entry = next(item for item in inventory["entries"] if item["path"] == path)
                self.assertTrue(entry["dirtyTracked"])
                self.assertEqual(sha256((self.repo / path).read_bytes()), entry["sha256"])

    def test_cleanup_keeps_a_real_selection_snapshot_when_the_file_is_replaced(self) -> None:
        inventory = self.inventory()
        original = self.selection(inventory)
        replacement = self.selection(inventory)
        replacement["items"][-1] = {
            "path": "cache",
            "disposition": "delete",
            "reason": "replacement selection",
            "proof": {
                "kind": "regenerate",
                "command": "different-rebuild",
                "setSha256": self.exact_set_sha256(inventory, "cache"),
            },
        }
        self.write_selection(original)
        self.assertEqual(0, self.bundle().returncode)
        replacement_path = self.root / "replacement-selection.json"
        replacement_path.write_text(json.dumps(replacement), encoding="utf-8")
        module = load_transfer_module()
        repository = module.bind_repository(self.repo, GIT_EXECUTABLE)
        root, snapshot_inventory, snapshot_selection, rows = module.load_validated_snapshot(
            repository, self.inventory_path, self.selection_path, "metadata snapshot mismatch"
        )
        os.replace(replacement_path, self.selection_path)
        preview = module.cleanup_preview_from_snapshot(
            self.bundle_path, repository, snapshot_inventory, snapshot_selection, rows
        )
        self.assertEqual(["cache"], preview["deletions"])
        self.assertEqual(sha256(canonical_json(original)), preview["selectionDigest"])
        self.assertEqual(inventory["snapshot"]["digest"], preview["inventoryDigest"])
        self.assertEqual([{"path": "cache", "kind": "regenerate", "setSha256": self.exact_set_sha256(inventory, "cache")}], preview["deletionProofs"])

    def test_git_external_helpers_never_execute(self) -> None:
        marker = self.root / "helper-ran.txt"
        probe = self.root / "probe.cmd"
        probe.write_text("@echo off\necho helper-ran>\"%~1\"\n", encoding="utf-8")
        # The command is deliberately harmless; arguments make it valid for both
        # external-diff and fsmonitor invocation shapes.
        command = f'"{probe}" "{marker}"'
        git(self.repo, "config", "diff.external", command)
        git(self.repo, "config", "core.fsmonitor", command)
        self.inventory()
        self.assertFalse(marker.exists(), "inventory must disable Git helper execution")

    def test_git_clean_filter_never_executes_during_inventory(self) -> None:
        repo = self.root / "filter-repo"
        repo.mkdir()
        git(repo, "init", "--initial-branch=main")
        git(repo, "config", "user.name", "Filter QA")
        git(repo, "config", "user.email", "filter-qa@example.invalid")
        (repo / "filtered.txt").write_text("base\n", encoding="utf-8")
        git(repo, "add", "filtered.txt")
        git(repo, "commit", "-m", "base")
        (repo / ".gitattributes").write_text(
            "filtered.txt filter=transfer-probe\n", encoding="utf-8"
        )
        git(repo, "add", ".gitattributes")
        git(repo, "commit", "-m", "attributes")
        marker = self.root / "clean-filter-ran.txt"
        probe = self.root / "clean_filter_probe.py"
        probe.write_text(
            "import pathlib,sys\n"
            "pathlib.Path(sys.argv[1]).write_text('ran', encoding='utf-8')\n"
            "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
            encoding="utf-8",
        )
        filter_command = subprocess.list2cmdline(
            [sys.executable, str(probe), str(marker)]
        )
        git(repo, "config", "filter.transfer-probe.clean", filter_command)
        (repo / "filtered.txt").write_text("dirty\n", encoding="utf-8")
        marker.unlink(missing_ok=True)
        output = self.root / "filter-inventory.json"
        result = run_cli("inventory", "--repo", repo, "--output", output)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(marker.exists(), "inventory must disable Git clean filters")

    def test_included_dotted_git_clean_filter_never_executes(self) -> None:
        repo = self.root / "included-filter-repo"
        repo.mkdir()
        git(repo, "init", "--initial-branch=main")
        git(repo, "config", "user.name", "Included Filter QA")
        git(repo, "config", "user.email", "included-filter@example.invalid")
        (repo / "filtered.txt").write_text("base\n", encoding="utf-8")
        git(repo, "add", "filtered.txt")
        git(repo, "commit", "-m", "base")
        (repo / ".gitattributes").write_text(
            "filtered.txt filter=transfer.probe\n", encoding="utf-8"
        )
        git(repo, "add", ".gitattributes")
        git(repo, "commit", "-m", "attributes")
        marker = self.root / "included-clean-filter-ran.txt"
        probe = self.root / "included_clean_filter_probe.cmd"
        probe.write_text(
            "@echo off\n"
            "echo ran>\"%~1\"\n"
            "more\n",
            encoding="utf-8",
        )
        command = f'"{probe.as_posix()}" "{marker.as_posix()}"'
        included_config = self.root / "included-filter.config"
        git(
            repo,
            "config",
            "--file",
            str(included_config),
            "filter.transfer.probe.clean",
            command,
        )
        git(
            repo,
            "config",
            "--file",
            str(included_config),
            "filter.transfer.probe.required",
            "true",
        )
        git(repo, "config", "include.path", str(included_config))
        (repo / "filtered.txt").write_text("dirty\n", encoding="utf-8")
        marker.unlink(missing_ok=True)
        output = self.root / "included-filter-inventory.json"
        result = run_cli("inventory", "--repo", repo, "--output", output)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(marker.exists(), "inventory must disable included dotted filters")

    def test_worktree_scoped_git_clean_filter_never_executes(self) -> None:
        repo = self.root / "worktree-filter-repo"
        repo.mkdir()
        git(repo, "init", "--initial-branch=main")
        git(repo, "config", "user.name", "Worktree Filter QA")
        git(repo, "config", "user.email", "worktree-filter@example.invalid")
        (repo / "filtered.txt").write_text("base\n", encoding="utf-8")
        git(repo, "add", "filtered.txt")
        git(repo, "commit", "-m", "base")
        (repo / ".gitattributes").write_text(
            "filtered.txt filter=transfer.worktree\n", encoding="utf-8"
        )
        git(repo, "add", ".gitattributes")
        git(repo, "commit", "-m", "attributes")
        marker = self.root / "worktree-clean-filter-ran.txt"
        probe = self.root / "worktree_clean_filter_probe.cmd"
        probe.write_text(
            "@echo off\n"
            "echo ran>\"%~1\"\n"
            "more\n",
            encoding="utf-8",
        )
        command = f'"{probe.as_posix()}" "{marker.as_posix()}"'
        git(repo, "config", "extensions.worktreeConfig", "true")
        git(repo, "config", "--worktree", "filter.transfer.worktree.clean", command)
        git(repo, "config", "--worktree", "filter.transfer.worktree.required", "true")
        (repo / "filtered.txt").write_text("dirty\n", encoding="utf-8")
        marker.unlink(missing_ok=True)
        output = self.root / "worktree-filter-inventory.json"
        result = run_cli("inventory", "--repo", repo, "--output", output)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(marker.exists(), "inventory must disable worktree filters")

    @unittest.skipUnless(os.name == "nt", "Windows junction metadata contract")
    def test_reparse_inventory_binds_link_target_metadata(self) -> None:
        target = self.root / "junction-target"
        target.mkdir()
        link = self.repo / "linked-evidence"
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            text=True,
            capture_output=True,
        )
        if created.returncode:
            self.skipTest(f"junction unavailable: {created.stderr or created.stdout}")
        inventory = self.inventory()
        entry = next(item for item in inventory["entries"] if item["path"] == "linked-evidence")
        self.assertEqual("reparse", entry["entryType"])
        self.assertTrue(entry["metadataOnly"])
        self.assertTrue(entry["linkTarget"])
        items = self.selection(inventory)["items"]
        items.append(
            {
                "path": "linked-evidence",
                "disposition": "external",
                "reason": "link metadata uses separate storage",
                "receipt": {
                    "artifact": "vault:linked-evidence",
                    "setSha256": self.exact_set_sha256(inventory, "linked-evidence"),
                },
            }
        )
        self.write_selection(self.selection(inventory, items=items))
        self.assertEqual(0, self.bundle().returncode)

    def write_forged_bundle(self, path: Path, entries: dict[str, bytes], *, attributes: dict[str, int] | None = None) -> None:
        manifest = {
            "schemaVersion": 1,
            "inventoryDigest": "0" * 64,
            "selectionDigest": "0" * 64,
            "repository": {
                "head": "0" * 40,
                "gitExecutable": {"path": str(GIT_EXECUTABLE), "sha256": sha256(GIT_EXECUTABLE.read_bytes())},
            },
            "payload": [
                {"path": name, "size": len(data), "sha256": sha256(data)}
                for name, data in entries.items()
            ],
            "metadata": [],
            "deletions": [],
        }
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                info = zipfile.ZipInfo(name)
                if attributes and name in attributes:
                    info.external_attr = attributes[name]
                    info.create_system = 3
                archive.writestr(info, data)
            archive.writestr(MANIFEST, canonical_json(manifest))

    def rewrite_bundle_manifest(self, source: Path, destination: Path, mutate) -> None:
        with zipfile.ZipFile(source) as archive:
            content = {name: archive.read(name) for name in archive.namelist()}
        manifest = json.loads(content[MANIFEST].decode("utf-8"))
        mutate(manifest)
        content[MANIFEST] = canonical_json(manifest)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in content.items():
                archive.writestr(name, data)

    def make_directory_link(self, link: Path, target: Path) -> None:
        if os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], text=True, capture_output=True)
            if result.returncode:
                self.skipTest(result.stderr or result.stdout)
        else:
            os.symlink(target, link, target_is_directory=True)

    def test_trusted_verify_and_cleanup_reject_self_consistent_empty_forgery(self) -> None:
        inventory = self.inventory()
        items = [
            {"path": "work.txt", "disposition": "include", "reason": "work"},
            {"path": ".scratch/evidence.txt", "disposition": "include", "reason": "evidence"},
            {"path": "secret.txt", "disposition": "include", "reason": "data"},
            {"path": "cache", "disposition": "delete", "reason": "cache", "proof": {"kind": "regenerate", "command": "rebuild", "setSha256": self.exact_set_sha256(inventory, "cache")}},
        ]
        selection = self.selection(inventory, items=items)
        self.write_selection(selection)
        forged = self.root / "forged.zip"
        self.write_forged_bundle(forged, {})
        trusted = run_cli("verify", "--bundle", forged, "--inventory", self.inventory_path, "--selection", self.selection_path, "--source", self.repo)
        self.assert_contract_error(trusted, "invalid manifest entry category")
        cleanup = run_cli("cleanup", "--repo", self.repo, "--inventory", self.inventory_path, "--selection", self.selection_path, "--bundle", forged)
        self.assert_contract_error(cleanup, "invalid manifest entry category")

    def test_payload_rows_cannot_be_relabelled_as_metadata(self) -> None:
        inventory = self.inventory()
        self.write_selection(self.selection(inventory))
        self.assertEqual(0, self.bundle().returncode)
        rewritten = self.root / "category-drift.zip"
        with zipfile.ZipFile(self.bundle_path) as source:
            content = {name: source.read(name) for name in source.namelist()}
        manifest = json.loads(content[MANIFEST].decode("utf-8"))
        self.assertTrue(manifest["payload"])
        manifest["metadata"].extend(manifest["payload"])
        manifest["payload"] = []
        content[MANIFEST] = canonical_json(manifest)
        with zipfile.ZipFile(rewritten, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in content.items():
                archive.writestr(name, data)
        trusted = run_cli(
            "verify",
            "--bundle",
            rewritten,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection_path,
            "--source",
            self.repo,
        )
        self.assert_contract_error(trusted, "invalid manifest entry category")
        payload_source = run_cli(
            "verify", "--bundle", rewritten, "--source", self.repo
        )
        self.assert_contract_error(payload_source, "invalid manifest entry category")

    def test_verify_rejects_unsafe_zip_member_types_and_portable_name_collisions(self) -> None:
        unsafe = [
            ("link", stat.S_IFLNK << 16),
            ("device", stat.S_IFCHR << 16),
            ("directory/", stat.S_IFDIR << 16),
            ("./file", 0),
            ("dir/", 0),
            ("CON", 0),
            ("trailing.", 0),
            ("trailing ", 0),
            ("wild?.txt", 0),
        ]
        for name, attr in unsafe:
            with self.subTest(name=name):
                bundle = self.root / (sha256(name.encode()) + ".zip")
                self.write_forged_bundle(bundle, {name: b"x"}, attributes={name: attr})
                self.assert_contract_error(run_cli("verify", "--bundle", bundle), "unsafe archive")
        for names in ({"A.txt": b"a", "a.txt": b"b"}, {"\u00e9.txt": b"a", "e\u0301.txt": b"b"}, {"a": b"a", "a/b": b"b"}):
            with self.subTest(names=tuple(names)):
                bundle = self.root / (sha256(canonical_json(sorted(names))) + ".zip")
                self.write_forged_bundle(bundle, names)
                self.assert_contract_error(run_cli("verify", "--bundle", bundle), "archive path collision")
        encrypted = self.root / "encrypted.zip"
        self.write_forged_bundle(encrypted, {"payload.txt": b"x"})
        data = bytearray(encrypted.read_bytes())
        for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            start = data.index(signature)
            flags = int.from_bytes(data[start + offset:start + offset + 2], "little") | 1
            data[start + offset:start + offset + 2] = flags.to_bytes(2, "little")
        encrypted.write_bytes(data)
        self.assert_contract_error(run_cli("verify", "--bundle", encrypted), "encrypted archive entry")

    def test_verify_rejects_archive_resource_bombs_before_reading_members(self) -> None:
        too_many = self.root / "too-many.zip"
        import struct
        central = b"".join(
            struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0, 0, 0, 0, 0, 0, 0, len(name), 0, 0, 0, 0, 0, 0) + name
            for name in (f"payload-{number:05d}".encode("ascii") for number in range(10_001))
        )
        too_many.write_bytes(central + struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 10_001, 10_001, len(central), 0, 0))
        self.assert_contract_error(run_cli("verify", "--bundle", too_many), "archive resource limit")
        compression_bomb = self.root / "compression-bomb.zip"
        with zipfile.ZipFile(compression_bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("payload.bin", b"\0" * (1024 * 1024))
            archive.writestr(MANIFEST, b"{}")
        self.assert_contract_error(run_cli("verify", "--bundle", compression_bomb), "archive resource limit")

    def test_malformed_nested_inventory_and_selection_shapes_are_contract_errors(self) -> None:
        inventory = self.inventory()
        selection = self.selection(inventory)
        cases = [
            ("entry-not-object", {**inventory, "entries": [None]}),
            ("entry-field-wrong-type", {**inventory, "entries": [{**inventory["entries"][0], "dirtyTracked": []}]}),
        ]
        for name, malformed_inventory in cases:
            with self.subTest(name=name):
                malformed_inventory["snapshot"] = {"digest": sha256(canonical_json({"entries": malformed_inventory["entries"], "repository": malformed_inventory["repository"]}))}
                self.inventory_path.write_text(json.dumps(malformed_inventory), encoding="utf-8")
                malformed_selection = {**selection, "inventoryDigest": malformed_inventory["snapshot"]["digest"]}
                self.selection_path.write_text(json.dumps(malformed_selection), encoding="utf-8")
                result = run_cli("bundle", "--repo", self.repo, "--inventory", self.inventory_path, "--selection", self.selection_path, "--output", self.root / f"{name}.zip")
                self.assert_contract_error(result, "invalid inventory snapshot")
        inventory = self.inventory()
        malformed_selection = self.selection(inventory)
        malformed_selection["gitStrategy"] = {"mode": "remote-clone", "remote": "origin", "expectedHead": {"not": "a string"}}
        self.write_selection(malformed_selection)
        result = self.bundle()
        self.assert_contract_error(result, "invalid selection")

    def test_unborn_inventory_requires_safe_history_contract_and_none_strategy(self) -> None:
        module = load_transfer_module()
        entry = {
            "path": "work.txt",
            "entryType": "file",
            "gitClass": "untracked",
            "dirtyTracked": False,
            "size": 4,
            "sha256": sha256(b"work"),
        }
        repository = {
            "historyState": "unborn",
            "head": None,
            "remotes": [],
            "remoteEvidence": {},
            "gitExecutable": {"path": str(GIT_EXECUTABLE), "sha256": sha256(GIT_EXECUTABLE.read_bytes())},
            "gitMetadataHashes": {},
        }
        inventory = {"schemaVersion": 1, "repository": repository, "entries": [entry]}
        inventory["snapshot"] = {"digest": sha256(canonical_json({"entries": [entry], "repository": repository}))}
        module.validate_inventory(inventory)
        base_selection = {
            "schemaVersion": 1,
            "inventoryDigest": inventory["snapshot"]["digest"],
            "items": [{"path": "work.txt", "disposition": "include", "reason": "local work"}],
        }
        valid = {**base_selection, "gitStrategy": {"mode": "none"}}
        self.assertEqual("work.txt", module.validate_selection(self.repo, inventory, valid)[0]["path"])
        for strategy in (
            {"mode": "git-bundle"},
            {"mode": "remote-clone", "remote": "origin", "expectedHead": None},
        ):
            with self.subTest(strategy=strategy):
                with self.assertRaisesRegex(module.ContractError, "unborn repositories require git strategy none"):
                    module.validate_selection(self.repo, inventory, {**base_selection, "gitStrategy": strategy})

        delete_selection = {
            **base_selection,
            "gitStrategy": {"mode": "none"},
            "items": [{
                "path": "work.txt",
                "disposition": "delete",
                "reason": "invalid history claim",
                "proof": {"kind": "git-recoverable", "setSha256": sha256(canonical_json([entry]))},
            }],
        }
        with self.assertRaisesRegex(module.ContractError, "unborn repository has no verified Git history"):
            module.validate_selection(self.repo, inventory, delete_selection)

        for history_state, head in (("committed", None), ("unborn", "0" * 40), ("unknown", None), (None, "0" * 40)):
            with self.subTest(history_state=history_state, head=head):
                malformed_repository = {**repository, "historyState": history_state, "head": head}
                malformed = {**inventory, "repository": malformed_repository}
                malformed["snapshot"] = {"digest": sha256(canonical_json({"entries": [entry], "repository": malformed_repository}))}
                with self.assertRaisesRegex(module.ContractError, "invalid inventory snapshot"):
                    module.validate_inventory(malformed)

    def test_portable_identity_reserves_mixed_case_and_nfkc_equivalent_git_paths(self) -> None:
        module = load_transfer_module()
        for path in (".GIT/config", ".\uff27\uff29\uff34/config"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(module.ContractError, "selection path escapes repository"):
                    module.selection_path(self.repo, path)
        for path in ("_REPO-TRANSFER/cache", "_\uff32\uff25\uff30\uff2f\uff0d\uff34\uff32\uff21\uff2e\uff33\uff26\uff25\uff32/cache"):
            with self.subTest(path=path):
                inventory = {
                    "schemaVersion": 1,
                    "repository": {"head": "0" * 40, "remotes": [], "remoteEvidence": {}, "gitMetadataHashes": {}},
                    "entries": [{"path": path, "entryType": "file", "gitClass": "untracked", "dirtyTracked": False, "size": 1, "sha256": sha256(b"x")}],
                }
                inventory["snapshot"] = {"digest": sha256(canonical_json({"entries": inventory["entries"], "repository": inventory["repository"]}))}
                selection = {"schemaVersion": 1, "inventoryDigest": inventory["snapshot"]["digest"], "gitStrategy": {"mode": "none"}, "items": [{"path": path, "disposition": "include", "reason": "must reject portable reserved namespace"}]}
                with self.assertRaisesRegex(module.ContractError, "internal archive namespace"):
                    module.validate_selection(self.repo, inventory, selection)

    def test_cleanup_is_permanently_preview_only(self) -> None:
        inventory = self.inventory()
        items = [
            {"path": "work.txt", "disposition": "include", "reason": "work"},
            {"path": ".scratch/evidence.txt", "disposition": "include", "reason": "evidence"},
            {"path": "secret.txt", "disposition": "include", "reason": "data"},
            {"path": "cache", "disposition": "delete", "reason": "cache", "proof": {"kind": "regenerate", "command": "rebuild", "setSha256": self.exact_set_sha256(inventory, "cache")}},
        ]
        self.write_selection(self.selection(inventory, items=items))
        self.assertEqual(0, self.bundle().returncode)
        preview = run_cli("cleanup", "--repo", self.repo, "--inventory", self.inventory_path, "--selection", self.selection_path, "--bundle", self.bundle_path)
        self.assertEqual(0, preview.returncode, preview.stderr)
        self.assertTrue((self.repo / "cache" / "cache.bin").exists())
        applied = run_cli("cleanup", "--repo", self.repo, "--inventory", self.inventory_path, "--selection", self.selection_path, "--bundle", self.bundle_path, "--apply")
        self.assert_contract_error(applied, "cleanup is preview-only")
        self.assertTrue((self.repo / "cache" / "cache.bin").exists())

    def test_cleanup_rechecks_delete_only_inventory_entries_before_preview(self) -> None:
        inventory = self.inventory()
        self.write_selection(self.selection(inventory))
        self.assertEqual(0, self.bundle().returncode)
        module = load_transfer_module()
        repository = module.bind_repository(self.repo, GIT_EXECUTABLE)
        root, snapshot_inventory, snapshot_selection, rows = module.load_validated_snapshot(
            repository, self.inventory_path, self.selection_path, "metadata snapshot mismatch"
        )
        (self.repo / "cache" / "cache.bin").write_bytes(b"changed after trusted snapshot")
        with self.assertRaisesRegex(module.ContractError, "metadata snapshot mismatch"):
            module.cleanup_preview_from_snapshot(
                self.bundle_path, repository, snapshot_inventory, snapshot_selection, rows
            )

    def test_cleanup_full_census_rejects_new_descendant_under_delete_selection(self) -> None:
        inventory = self.inventory()
        self.write_selection(self.selection(inventory))
        self.assertEqual(0, self.bundle().returncode)
        module = load_transfer_module()
        repository = module.bind_repository(self.repo, GIT_EXECUTABLE)
        root, snapshot_inventory, snapshot_selection, rows = module.load_validated_snapshot(
            repository, self.inventory_path, self.selection_path, "metadata snapshot mismatch"
        )
        (self.repo / "cache" / "new-after-snapshot.bin").write_bytes(b"new")
        with self.assertRaisesRegex(module.ContractError, "metadata snapshot mismatch"):
            module.cleanup_preview_from_snapshot(self.bundle_path, repository, snapshot_inventory, snapshot_selection, rows)

    def test_json_rejects_duplicate_keys_and_nonfinite_numeric_literals(self) -> None:
        inventory = self.inventory()
        valid = self.selection(inventory)
        documents = [
            json.dumps(valid)[:-1] + ',"inventoryDigest":"' + inventory["snapshot"]["digest"] + '"}',
            json.dumps(valid)[:-1] + ',"extra":1e999}',
            json.dumps(valid)[:-1] + ',"extra":Infinity}',
        ]
        for document in documents:
            with self.subTest(document=document[-24:]):
                self.selection_path.write_text(document, encoding="utf-8")
                self.assert_contract_error(self.bundle(), "invalid selection")

    def test_trusted_verify_binds_manifest_head_and_single_open_bundle_snapshot(self) -> None:
        inventory = self.inventory()
        self.write_selection(self.selection(inventory))
        self.assertEqual(0, self.bundle().returncode)
        head_drift = self.root / "head-drift.zip"
        self.rewrite_bundle_manifest(self.bundle_path, head_drift, lambda manifest: manifest["repository"].update(head="0" * 40))
        self.assert_contract_error(run_cli("verify", "--bundle", head_drift, "--inventory", self.inventory_path, "--selection", self.selection_path, "--source", self.repo), "bundle does not match trusted inventory")

    def test_v1_committed_inventory_and_manifest_without_history_state_remain_readable(self) -> None:
        module = load_transfer_module()
        inventory = self.inventory()
        inventory["repository"].pop("historyState")
        inventory["snapshot"] = {"digest": sha256(canonical_json({"entries": inventory["entries"], "repository": inventory["repository"]}))}
        module.validate_inventory(inventory)

        current = self.inventory()
        self.write_selection(self.selection(current))
        self.assertEqual(0, self.bundle().returncode)
        legacy_manifest = self.root / "legacy-v1-manifest.zip"
        self.rewrite_bundle_manifest(self.bundle_path, legacy_manifest, lambda manifest: manifest["repository"].pop("historyState"))
        result = run_cli("verify", "--bundle", legacy_manifest)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_portable_tree_rejects_selection_and_manifest_cross_category_conflicts(self) -> None:
        module = load_transfer_module()
        repository = {"head": "0" * 40, "remotes": [], "remoteEvidence": {}, "gitMetadataHashes": {}}
        entries = [
            {"path": "A", "entryType": "file", "gitClass": "untracked", "dirtyTracked": False, "size": 1, "sha256": sha256(b"a")},
            {"path": "a/child", "entryType": "file", "gitClass": "untracked", "dirtyTracked": False, "size": 1, "sha256": sha256(b"b")},
        ]
        inventory = {"schemaVersion": 1, "repository": repository, "entries": entries}
        inventory["snapshot"] = {"digest": sha256(canonical_json({"entries": entries, "repository": repository}))}
        selection = {"schemaVersion": 1, "inventoryDigest": inventory["snapshot"]["digest"], "gitStrategy": {"mode": "none"}, "items": [
            {"path": "A", "disposition": "include", "reason": "first"},
            {"path": "a/child", "disposition": "include", "reason": "second"},
        ]}
        with self.assertRaisesRegex(module.ContractError, "selection rows overlap"):
            module.validate_selection(self.repo, inventory, selection)
        inventory = self.inventory()
        self.write_selection(self.selection(inventory))
        self.assertEqual(0, self.bundle().returncode)
        for name, mutate in (
            ("payload-delete", lambda manifest: manifest.update(deletions=[{"path": "WORK.TXT/archive"}])),
            ("delete-delete", lambda manifest: manifest.update(deletions=[{"path": "gone"}, {"path": "GONE/item"}])),
            ("reserved", lambda manifest: manifest["payload"].__setitem__(0, {**manifest["payload"][0], "path": "_\uff32\uff25\uff30\uff2f\uff0d\uff34\uff32\uff21\uff2e\uff33\uff26\uff25\uff32/payload.txt"})),
        ):
            with self.subTest(name=name):
                forged = self.root / f"portable-{name}.zip"
                self.rewrite_bundle_manifest(self.bundle_path, forged, mutate)
                self.assert_contract_error(run_cli("verify", "--bundle", forged), "invalid manifest entry category")

    def test_internal_manifest_requires_all_typed_binding_fields(self) -> None:
        inventory = self.inventory()
        self.write_selection(self.selection(inventory))
        self.assertEqual(0, self.bundle().returncode)
        cases = [
            ("schema-bool", lambda manifest: manifest.update(schemaVersion=True)),
            ("inventory-missing", lambda manifest: manifest.pop("inventoryDigest")),
            ("selection-bool", lambda manifest: manifest.update(selectionDigest=True)),
            ("repository-not-object", lambda manifest: manifest.update(repository=[])),
            ("repository-head-bool", lambda manifest: manifest.update(repository={"head": True})),
            ("payload-not-list", lambda manifest: manifest.update(payload={})),
            ("metadata-not-list", lambda manifest: manifest.update(metadata={})),
            ("deletions-missing", lambda manifest: manifest.pop("deletions")),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                forged = self.root / f"manifest-{name}.zip"
                self.rewrite_bundle_manifest(self.bundle_path, forged, mutate)
                self.assert_contract_error(run_cli("verify", "--bundle", forged), "invalid internal manifest")

    def test_bundle_enforces_verifier_compression_ratio_before_writing_output(self) -> None:
        (self.repo / "work.txt").write_bytes(b"\0" * (1024 * 1024))
        inventory = self.inventory()
        self.write_selection(self.selection(inventory))
        result = self.bundle()
        self.assert_contract_error(result, "archive resource limit")
        self.assertFalse(self.bundle_path.exists())

    def test_receiver_rejects_reparse_ancestors_for_payload_and_deletion_paths(self) -> None:
        nested = self.repo / "nested"
        nested.mkdir()
        (nested / "payload.txt").write_text("payload\n", encoding="utf-8")
        inventory = self.inventory()
        items = self.selection(inventory)["items"]
        items.append({"path": "nested/payload.txt", "disposition": "include", "reason": "nested payload"})
        self.write_selection(self.selection(inventory, items=items))
        self.assertEqual(0, self.bundle().returncode)
        forged = self.root / "reparse-ancestors.zip"
        self.rewrite_bundle_manifest(self.bundle_path, forged, lambda manifest: manifest.update(deletions=[{"path": "gone/file.txt"}]))
        payload_target = self.root / "payload-target"
        payload_target.mkdir()
        (payload_target / "payload.txt").write_text("payload\n", encoding="utf-8")
        shutil.rmtree(nested)
        self.make_directory_link(nested, payload_target)
        gone_target = self.root / "gone-target"
        gone_target.mkdir()
        self.make_directory_link(self.repo / "gone", gone_target)
        result = run_cli("verify", "--bundle", forged, "--source", self.repo)
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual(2, json.loads(result.stdout)["mismatches"])

    def test_json_inputs_are_bounded_finite_and_shallow_contract_documents(self) -> None:
        inventory = self.inventory()
        valid = self.selection(inventory)
        nested: object = "end"
        for _ in range(80):
            nested = {"x": nested}
        cases = [
            ("nan", json.dumps(valid)[:-1] + ',"extra":NaN}'),
            ("oversized", json.dumps({**valid, "padding": "x" * (8 * 1024 * 1024 + 1)})),
            ("nested", json.dumps({**valid, "extra": nested})),
        ]
        for name, document in cases:
            with self.subTest(name=name):
                self.selection_path.write_text(document, encoding="utf-8")
                result = self.bundle()
                self.assert_contract_error(result, "invalid selection")

    def test_selected_metadata_suppresses_cross_category_rename_paths(self) -> None:
        (self.repo / "external-old.txt").write_text("rename me\n", encoding="utf-8")
        git(self.repo, "add", "external-old.txt")
        git(self.repo, "commit", "-m", "rename base")
        git(self.repo, "mv", "external-old.txt", "included-new.txt")
        inventory = self.inventory()
        items = self.selection(inventory)["items"]
        items.append({"path": "included-new.txt", "disposition": "include", "reason": "selected renamed content"})
        items.append({
            "path": "external-old.txt",
            "disposition": "external",
            "reason": "old name stays outside the archive",
            "receipt": {"artifact": "vault:old-name", "setSha256": self.exact_set_sha256(inventory, "external-old.txt")},
        })
        self.write_selection(self.selection(inventory, items=items, strategy="none"))
        result = self.bundle()
        self.assertEqual(0, result.returncode, result.stderr)
        with zipfile.ZipFile(self.bundle_path) as archive:
            metadata = b"".join(archive.read(name) for name in archive.namelist() if name.startswith(f"{TRANSFER_ROOT}/git-"))
        self.assertNotIn(b"external-old.txt", metadata)

    def test_all_remote_urls_are_sanitized(self) -> None:
        git(self.repo, "remote", "add", "http-auth", "https://user:token@example.invalid/repo.git?key=value#fragment")
        git(self.repo, "remote", "add", "ssh-auth", "ssh://git@ssh.example.invalid/org/repo.git")
        git(self.repo, "remote", "add", "scp-auth", "git@scp.example.invalid:org/repo.git")
        inventory = self.inventory()
        remotes = {entry["name"]: entry["url"] for entry in inventory["repository"]["remotes"]}
        self.assertEqual("https://example.invalid/repo.git", remotes["http-auth"])
        self.assertEqual("ssh://ssh.example.invalid/org/repo.git", remotes["ssh-auth"])
        self.assertEqual("ssh://scp.example.invalid/org/repo.git", remotes["scp-auth"])
        self.assertEqual("<local-path>", remotes["origin"])

    def test_unexpected_archive_and_path_errors_are_contract_errors(self) -> None:
        invalid = self.root / "not-a-zip.bin"
        invalid.write_bytes(b"not a zip")
        self.assert_contract_error(run_cli("verify", "--bundle", invalid), "invalid bundle")
        self.assert_contract_error(run_cli("verify", "--bundle", self.root), "invalid bundle")
        self.assert_contract_error(run_cli("inventory", "--repo", self.root / "missing", "--output", self.root / "out.json"), "not a git repository")
        bad_inventory = self.root / "bad-inventory.json"
        bad_selection = self.root / "bad-selection.json"
        bad_inventory.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "repository": {},
                    "entries": [],
                    "snapshot": 1,
                }
            ),
            encoding="utf-8",
        )
        bad_selection.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "inventoryDigest": "0" * 64,
                    "gitStrategy": {"mode": "none"},
                    "items": [],
                }
            ),
            encoding="utf-8",
        )
        malformed = run_cli(
            "bundle",
            "--repo",
            self.repo,
            "--inventory",
            bad_inventory,
            "--selection",
            bad_selection,
            "--output",
            self.root / "bad.zip",
        )
        self.assert_contract_error(malformed, "invalid inventory snapshot")


if __name__ == "__main__":
    unittest.main()
