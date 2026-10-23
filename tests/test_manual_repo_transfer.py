from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "src.codex" / "skills" / "manual-repo-transfer" / "scripts" / "repo_transfer.py"
GIT_EXECUTABLE = Path(shutil.which("git") or "").resolve()
if not GIT_EXECUTABLE.is_file():
    raise RuntimeError("test host must provide an explicit Git executable")


def load_transfer_module():
    spec = importlib.util.spec_from_file_location("repo_transfer_direct_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(
    *args: object,
    cwd: Path | None = None,
    expect: int = 0,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), *(str(arg) for arg in args), "--git-executable", str(GIT_EXECUTABLE)]
    result = subprocess.run(
        command, cwd=cwd, text=True, capture_output=True, timeout=timeout
    )
    if result.returncode != expect:
        raise AssertionError(
            f"expected exit {expect}, got {result.returncode}\n"
            f"command: {command}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def run_without_git(
    *args: object,
    expect: int = 0,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), *(str(arg) for arg in args)]
    result = subprocess.run(command, text=True, capture_output=True)
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

    def test_process_supervision_failure_preserves_typed_failure_id(self) -> None:
        module = load_transfer_module()

        class Sink:
            def bytes_for(self, _stream: str) -> bytes:
                return b""

        result = types.SimpleNamespace(
            failure_id="PSV1-POSIX-ORACLE-UNAVAILABLE",
            timed_out=False,
            tree=types.SimpleNamespace(tree_empty=False),
            resources_closed=True,
        )

        class Owner:
            def build_repository_transfer_git_request(self, **_kwargs):
                return object(), Sink()

            def run(self, _request):
                return result

            def close(self):
                return None

        module._PROCESS_RUNNER_MODULE = types.SimpleNamespace(
            ProcessRunnerV1=Owner,
            EnvironmentRowV1=lambda name, value: (name, value),
        )

        with self.assertRaisesRegex(
            module.ContractError, r"PSV1-POSIX-ORACLE-UNAVAILABLE"
        ):
            module._run_process_runner_git_process(
                [str(GIT_EXECUTABLE), "status"], self.repo, {}
            )

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

    def test_inventory_validation_streams_the_version_one_snapshot_digest(self) -> None:
        inventory = self.inventory()
        snapshot = {
            "entries": inventory["entries"],
            "repository": inventory["repository"],
        }
        expected = hashlib.sha256(
            json.dumps(
                snapshot,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(expected, inventory["snapshot"]["digest"])

        module = load_transfer_module()

        def whole_buffer_forbidden(_value):
            raise AssertionError("whole canonical JSON buffer reached")

        module.canonical_json = whole_buffer_forbidden
        module.validate_inventory(inventory)

    def test_git_metadata_batches_are_byte_identical_and_runner_bounded(self) -> None:
        module = load_transfer_module()
        repository = module.bind_repository(self.repo, GIT_EXECUTABLE)
        for setting, value in (
            ("clean", "cat"),
            ("smudge", "cat"),
            ("process", "cat"),
            ("required", "true"),
        ):
            git(self.repo, "config", f"filter.fixture.{setting}", value)
        deleted = self.repo / "staged-delete.txt"
        deleted.write_text("delete me\n", encoding="utf-8")
        git(self.repo, "add", deleted.name)
        git(self.repo, "commit", "-m", "add staged-delete fixture")
        deleted.unlink()
        git(self.repo, "add", "-u", deleted.name)
        staged = self.repo / "staged add [literal].txt"
        staged.write_text("staged\n", encoding="utf-8")
        git(self.repo, "add", staged.name)
        special = self.repo / "untracked ! [literal].txt"
        special.write_text("special\n", encoding="utf-8")
        paths = [
            ".scratch/evidence.txt",
            "node_modules/cache.bin",
            staged.name,
            deleted.name,
            special.name,
            "tracked.txt",
            "untracked.txt",
        ]
        if os.name == "posix":
            posix_special = self.repo / ":(glob)*\n.txt"
            posix_special.write_text("literal pathspec bytes\n", encoding="utf-8")
            paths.append(posix_special.name)
        expected = module.git_metadata(repository, paths)
        runner = module._load_process_runner()
        original_count = runner.MAX_ARGV_COUNT
        original_run = module.run_bound_git_process
        observed: list[tuple[str, ...]] = []

        def recording_run(bound, command, stdin_bytes=None):
            if "--" in command and any(
                name in command for name in ("status", "diff")
            ):
                observed.append(tuple(command))
            return original_run(bound, command, stdin_bytes=stdin_bytes)

        module.run_bound_git_process = recording_run
        runner.MAX_ARGV_COUNT = len(module.git_command_prefix(repository)) + 9
        try:
            actual = module.git_metadata(repository, paths)
        finally:
            runner.MAX_ARGV_COUNT = original_count
            module.run_bound_git_process = original_run

        self.assertEqual(expected, actual)
        self.assertGreater(len(observed), 3)
        for command in observed:
            encoded = [len(argument.encode("utf-8")) for argument in command]
            self.assertLessEqual(len(command), runner.MAX_ARGV_COUNT)
            self.assertLessEqual(sum(size + 1 for size in encoded), runner.MAX_ARGV_BYTES)
            self.assertLessEqual(max(encoded), runner.MAX_ARG_BYTES)
            if os.name == "nt":
                units = len(
                    runner.serialize_msvcrt_argv(command).encode("utf-16-le")
                ) // 2
                self.assertLessEqual(units, runner.MAX_WINDOWS_COMMAND_LINE_UNITS)

    def test_git_metadata_rejects_one_unadmittable_path_before_metadata_launch(self) -> None:
        module = load_transfer_module()
        repository = module.bind_repository(self.repo, GIT_EXECUTABLE)
        runner = module._load_process_runner()
        original_arg_bytes = runner.MAX_ARG_BYTES
        original_run = module.run_bound_git_process
        metadata_launches = 0

        def recording_run(bound, command, stdin_bytes=None):
            nonlocal metadata_launches
            if "--" in command and any(
                name in command for name in ("status", "diff")
            ):
                metadata_launches += 1
            return original_run(bound, command, stdin_bytes=stdin_bytes)

        module.run_bound_git_process = recording_run
        runner.MAX_ARG_BYTES = 64
        try:
            with self.assertRaisesRegex(
                module.ContractError,
                "git metadata path exceeds bounded command",
            ):
                module.git_metadata(repository, ["x" * 100])
        finally:
            runner.MAX_ARG_BYTES = original_arg_bytes
            module.run_bound_git_process = original_run
        self.assertEqual(0, metadata_launches)

    def test_git_metadata_aggregate_output_cap_is_not_multiplied_by_batches(self) -> None:
        module = load_transfer_module()
        repository = module.bind_repository(self.repo, GIT_EXECUTABLE)
        runner = module._load_process_runner()
        original_count = runner.MAX_ARGV_COUNT
        original_run = module.run_git_command
        calls = 0

        def large_batch(_bound, command, **_kwargs):
            nonlocal calls
            calls += 1
            return subprocess.CompletedProcess(
                command, 0, b"x" * (module.MAX_JSON_BYTES // 2 + 1), b""
            )

        runner.MAX_ARGV_COUNT = len(module.git_command_prefix(repository)) + 8
        module.run_git_command = large_batch
        try:
            with self.assertRaisesRegex(
                module.ContractError, "git output exceeds JSON limit"
            ):
                module.git_metadata(repository, ["one.txt", "two.txt"])
        finally:
            runner.MAX_ARGV_COUNT = original_count
            module.run_git_command = original_run
        self.assertEqual(3, calls)

    def test_later_git_metadata_batch_failure_leaves_no_bundle_or_temporary(self) -> None:
        module = load_transfer_module()
        inventory = self.inventory()
        self.write_selection(inventory)
        repository = module.bind_repository(self.repo, GIT_EXECUTABLE)
        runner = module._load_process_runner()
        original_count = runner.MAX_ARGV_COUNT
        original_run = module.run_git_command
        metadata_batches = 0

        def fail_second_batch(bound, command, **kwargs):
            nonlocal metadata_batches
            if "--" in command and any(
                name in command for name in ("status", "diff")
            ):
                metadata_batches += 1
                if metadata_batches == 2:
                    raise module.ContractError("later metadata batch failure")
            return original_run(bound, command, **kwargs)

        runner.MAX_ARGV_COUNT = len(module.git_command_prefix(repository)) + 8
        module.run_git_command = fail_second_batch
        try:
            with self.assertRaisesRegex(
                module.ContractError, "later metadata batch failure"
            ):
                module.bundle(
                    repository,
                    self.inventory_path,
                    self.selection,
                    self.bundle,
                )
        finally:
            runner.MAX_ARGV_COUNT = original_count
            module.run_git_command = original_run
        self.assertEqual(2, metadata_batches)
        self.assertFalse(self.bundle.exists())
        self.assertEqual([], list(self.bundle.parent.glob(f".{self.bundle.name}.*.tmp")))

    def test_inventory_uses_nul_safe_batched_check_ignore(self) -> None:
        module = load_transfer_module()
        original_run_git = module.run_git
        invocations: list[tuple[tuple[str, ...], bytes | None]] = []

        def recording_run_git(repository, *arguments, **kwargs):
            result = original_run_git(repository, *arguments, **kwargs)
            invocations.append((arguments, kwargs.get("stdin_bytes")))
            return result

        module.run_git = recording_run_git
        module.MAX_GIT_CHECK_IGNORE_PATHS = 2
        (self.repo / ".scratch" / "more evidence.txt").write_text(
            "more evidence\n", encoding="utf-8"
        )
        if os.name == "posix":
            (self.repo / ".scratch" / "line\nbreak.txt").write_text(
                "newline evidence\n", encoding="utf-8"
            )

        inventory = module.build_inventory(
            module.bind_repository(self.repo, GIT_EXECUTABLE)
        )

        check_ignore = [
            (arguments, stdin_bytes)
            for arguments, stdin_bytes in invocations
            if "check-ignore" in arguments
        ]
        self.assertGreaterEqual(len(check_ignore), 2)
        for arguments, stdin_bytes in check_ignore:
            self.assertIn("--stdin", arguments)
            self.assertIn("-z", arguments)
            self.assertIsNotNone(stdin_bytes)
            records = stdin_bytes.removesuffix(b"\0").split(b"\0")
            self.assertLessEqual(len(records), 2)
            self.assertTrue(all(record.startswith(b"./") for record in records))
        self.assertFalse(
            any(
                arguments[:3] == ("ls-files", "--others", "--ignored")
                for arguments, _stdin_bytes in invocations
            )
        )
        entries = {entry["path"]: entry for entry in inventory["entries"]}
        self.assertEqual("ignored", entries[".scratch/evidence.txt"]["gitClass"])
        if os.name == "posix":
            self.assertEqual(
                "ignored", entries[".scratch/line\nbreak.txt"]["gitClass"]
            )
        self.assertEqual("ignored", entries[".scratch/more evidence.txt"]["gitClass"])

        before_single_batch = len(check_ignore)
        module.MAX_GIT_CHECK_IGNORE_PATHS = 100_000
        single_batch_inventory = module.build_inventory(
            module.bind_repository(self.repo, GIT_EXECUTABLE)
        )
        later_check_ignore = [
            arguments
            for arguments, _stdin_bytes in invocations
            if "check-ignore" in arguments
        ][before_single_batch:]
        self.assertEqual(1, len(later_check_ignore))
        self.assertEqual(
            module.canonical_json(inventory),
            module.canonical_json(single_batch_inventory),
        )

    def test_ignore_protocol_preserves_magic_wildcard_and_surrogateescape(self) -> None:
        module = load_transfer_module()
        raw_path = b"non-utf8-\x80.bin"
        paths = [":(glob)literal.txt", "wild*card.txt", "line\nbreak.txt"]
        if os.name == "posix":
            paths.append(raw_path.decode(sys.getfilesystemencoding(), "surrogateescape"))
        submitted: list[bytes] = []

        def echo_ignored(_repository, *arguments, **kwargs):
            self.assertEqual(
                ("check-ignore", "--no-index", "--stdin", "-z"), arguments
            )
            payload = kwargs["stdin_bytes"]
            submitted.extend(payload.removesuffix(b"\0").split(b"\0"))
            return subprocess.CompletedProcess(arguments, 0, payload, b"")

        module.run_git = echo_ignored
        ignored = module.ignored_census_paths(object(), paths)

        self.assertEqual(set(paths), ignored)
        self.assertEqual([os.fsencode(f"./{path}") for path in paths], submitted)

    def test_inventory_output_cap_is_atomic_and_control_json_cap_is_unchanged(self) -> None:
        module = load_transfer_module()
        value = {"payload": "x" * 64}
        exact_cap = len(module.canonical_json(value)) + 1
        exact_output = self.root / "exact-cap.json"
        module.publish_canonical_json(
            module.bind_output(exact_output, self.repo, force=False),
            value,
            exact_cap,
            "inventory cap",
            final_newline=True,
        )
        self.assertEqual(exact_cap, exact_output.stat().st_size)

        oversized_output = self.root / "cap-plus-one.json"
        with self.assertRaisesRegex(module.ContractError, "inventory cap"):
            module.publish_canonical_json(
                module.bind_output(oversized_output, self.repo, force=False),
                value,
                exact_cap - 1,
                "inventory cap",
                final_newline=True,
            )
        self.assertFalse(oversized_output.exists())

        document = json.dumps(
            {"payload": "x" * module.MAX_JSON_BYTES}, separators=(",", ":")
        ).encode("utf-8")
        with self.assertRaisesRegex(module.ContractError, "invalid selection"):
            module.read_json_bytes(document, "selection")
        self.assertEqual(
            len(document) - len(b'{"payload":""}'),
            len(
                module.read_json_bytes(
                    document, "inventory", module.MAX_INVENTORY_JSON_BYTES
                )["payload"]
            ),
        )

    def test_later_ignore_batch_failure_does_not_commit_inventory(self) -> None:
        module = load_transfer_module()
        original_run_git = module.run_git
        check_ignore_calls = 0

        def fail_second_batch(repository, *arguments, **kwargs):
            nonlocal check_ignore_calls
            if "check-ignore" in arguments:
                check_ignore_calls += 1
                if check_ignore_calls == 2:
                    return subprocess.CompletedProcess(
                        arguments, 2, b"", b"classification failed"
                    )
            return original_run_git(repository, *arguments, **kwargs)

        module.run_git = fail_second_batch
        module.MAX_GIT_CHECK_IGNORE_PATHS = 2
        result = module.main(
            [
                "inventory",
                "--repo",
                str(self.repo),
                "--git-executable",
                str(GIT_EXECUTABLE),
                "--output",
                str(self.inventory_path),
            ]
        )

        self.assertEqual(2, result)
        self.assertEqual(2, check_ignore_calls)
        self.assertFalse(self.inventory_path.exists())

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

    def test_bundle_force_is_explicit_and_replaces_only_a_bound_regular_file(self) -> None:
        inventory = self.inventory()
        self.write_selection(inventory)
        arguments = (
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
        run(*arguments)
        self.bundle.write_bytes(b"operator-owned\n")
        refused = run(*arguments, expect=2)
        self.assertEqual("TRANSFER-OUTPUT-EXISTS", refused.stderr.strip())
        self.assertEqual(b"operator-owned\n", self.bundle.read_bytes())
        run(*arguments, "--force")
        with zipfile.ZipFile(self.bundle) as archive:
            self.assertIn("_repo-transfer/manifest.json", archive.namelist())

    def test_receiver_archive_verify_does_not_require_git(self) -> None:
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

        verified = json.loads(
            run_without_git("verify", "--bundle", self.bundle).stdout
        )

        self.assertTrue(verified["verified"])
        self.assertEqual("archive-integrity", verified["verificationMode"])

    def test_source_verify_modes_without_git_are_refused_by_mode_validation(self) -> None:
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

        refused = run_without_git(
            "verify",
            "--bundle",
            self.bundle,
            "--source",
            self.repo,
            expect=2,
        )

        self.assertIn(
            "git executable is required with a source repository",
            refused.stderr,
        )
        trusted_refused = run_without_git(
            "verify",
            "--bundle",
            self.bundle,
            "--inventory",
            self.inventory_path,
            "--selection",
            self.selection,
            "--source",
            self.repo,
            expect=2,
        )
        self.assertIn(
            "git executable is required with a source repository",
            trusted_refused.stderr,
        )

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

    @unittest.skipUnless(
        os.name != "nt" and hasattr(os, "mkfifo"),
        "POSIX named-pipe integration contract",
    )
    def test_fifo_fails_repository_traversal_at_type_classification(self) -> None:
        module = load_transfer_module()
        fifo = self.repo / "blocked.fifo"
        os.mkfifo(fifo)

        with self.assertRaisesRegex(
            module.ContractError,
            r"^unsupported repository entry: blocked\.fifo$",
        ):
            list(module.walk_repository(self.repo))

    @unittest.skipUnless(
        os.name != "nt" and hasattr(os, "mkfifo"),
        "POSIX held-file census contract",
    )
    def test_inventory_census_is_nonblocking_for_fifo(self) -> None:
        module = load_transfer_module()
        fifo = self.repo / "blocked-census.fifo"
        os.mkfifo(fifo)

        with self.assertRaisesRegex(module.ContractError, r"^inventory drift$"):
            module.inventory_regular_file(fifo)

    @unittest.skipIf(os.name == "nt", "POSIX append drift contract")
    def test_bound_inventory_census_rejects_append(self) -> None:
        module = load_transfer_module()
        source = self.repo / "append-drift.bin"
        source.write_bytes(b"original")

        session = module.BoundPayloadInputSession(source)
        try:
            with source.open("ab") as stream:
                stream.write(b"-appended")
            with self.assertRaisesRegex(module.ContractError, r"^inventory drift$"):
                session.consume_census(session.eof)
        finally:
            session.close(validate=False)

    @unittest.skipIf(os.name == "nt", "POSIX pathname replacement contract")
    def test_bound_inventory_census_rejects_path_replacement(self) -> None:
        module = load_transfer_module()
        source = self.repo / "replacement-drift.bin"
        replacement = self.repo / "replacement.bin"
        source.write_bytes(b"original")
        replacement.write_bytes(b"substitute")

        session = module.BoundPayloadInputSession(source)
        try:
            os.replace(replacement, source)
            with self.assertRaisesRegex(module.ContractError, r"^inventory drift$"):
                session.consume_census(session.eof)
        finally:
            session.close(validate=False)

    def test_nested_git_content_is_hostile_external_only_without_child_git(self) -> None:
        module = load_transfer_module()
        nested_git = self.repo / "vendor" / ".git"
        nested_git.mkdir(parents=True)
        (nested_git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (self.repo / "vendor" / "source.txt").write_text(
            "vendored source\n", encoding="utf-8"
        )
        repository = module.bind_repository(self.repo, GIT_EXECUTABLE)
        original_run_git = module.run_git
        calls: list[tuple[Path, tuple[str, ...], bytes | None]] = []

        def recording_run_git(bound, *arguments, **kwargs):
            result = original_run_git(bound, *arguments, **kwargs)
            calls.append((bound.root, arguments, kwargs.get("stdin_bytes")))
            return result

        module.run_git = recording_run_git
        inventory = module.build_inventory(repository)
        entries = {entry["path"]: entry for entry in inventory["entries"]}

        self.assertNotIn(".git/config", entries)
        self.assertIn("vendor/.git/HEAD", entries)
        self.assertTrue(entries["vendor/.git/HEAD"]["hostile"])
        self.assertTrue(entries["vendor/.git/HEAD"]["metadataOnly"])
        self.assertTrue(all(root == repository.root for root, _args, _input in calls))
        self.assertTrue(
            any(
                stdin_bytes is not None
                and b"./vendor/.git/HEAD\0" in stdin_bytes
                for _root, arguments, stdin_bytes in calls
                if "check-ignore" in arguments
            )
        )

        self.write_selection(inventory)
        selection = json.loads(self.selection.read_text(encoding="utf-8"))
        external_row = {
            "path": "vendor",
            "disposition": "external",
            "reason": "nested repository metadata",
            "receipt": {
                "artifact": "external:nested-repository",
                "setSha256": covered_set_digest(inventory, "vendor"),
            },
        }
        selection["items"].append(external_row)
        rows = module.validate_selection(self.repo, inventory, selection)
        self.assertEqual("external", next(row for row in rows if row["path"] == "vendor")["disposition"])

        for disposition in ("include", "delete"):
            invalid = json.loads(json.dumps(selection))
            row = next(item for item in invalid["items"] if item["path"] == "vendor")
            row.clear()
            row.update(
                path="vendor",
                disposition=disposition,
                reason="must remain external",
            )
            with self.subTest(disposition=disposition), self.assertRaisesRegex(
                module.ContractError,
                "reparse or hostile entries require external disposition",
            ):
                module.validate_selection(self.repo, inventory, invalid)

        direct = json.loads(json.dumps(selection))
        row = next(item for item in direct["items"] if item["path"] == "vendor")
        row.update(
            path="vendor/.git/HEAD",
            receipt={
                "artifact": "external:nested-repository-head",
                "setSha256": covered_set_digest(inventory, "vendor/.git/HEAD"),
            },
        )
        with self.assertRaisesRegex(
            module.ContractError, "selection path escapes repository"
        ):
            module.validate_selection(self.repo, inventory, direct)


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
