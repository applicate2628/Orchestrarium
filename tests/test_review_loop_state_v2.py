from __future__ import annotations

import json
import os
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "review_loop_state.py"


def _engine_module():
    spec = importlib.util.spec_from_file_location("review_loop_state_path_test", ENGINE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _tree_bytes(root: Path) -> tuple[tuple[str, str, bytes], ...]:
    result: list[tuple[str, str, bytes]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            result.append((relative, "dir", b""))
        else:
            result.append((relative, "file", path.read_bytes()))
    return tuple(result)


def _git_revision(repo: Path) -> str:
    _text(repo / "artifact.md", "authoritative artifact\n")
    subprocess.run(["git", "-C", str(repo), "add", "artifact.md"], check=True)
    subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.name=Review Loop Test",
            "-c", "user.email=review-loop@example.invalid",
            "commit", "-q", "-m", "fixture",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _directory_link(link: Path, target: Path, *, junction: bool = False) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        if junction:
            if os.name != "nt":
                pytest.skip("Windows junction coverage")
            result = subprocess.run(
                ["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                pytest.skip(f"junction unavailable: {result.stdout}{result.stderr}")
        else:
            link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory link unavailable: {exc}")


def _run(repo: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENGINE), *map(str, args)],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def _wait_for_barrier(path: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if path.is_file():
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.fail(
                f"barrier process exited before readiness ({process.returncode}): "
                f"{stdout}{stderr}"
            )
        time.sleep(0.01)
    process.kill()
    stdout, stderr = process.communicate()
    pytest.fail(f"barrier process timed out: {stdout}{stderr}")


def _barrier_process(
    repo: Path,
    barrier: Path,
    *engine_args: object,
    mode: str = "atomic-write",
) -> subprocess.Popen[str]:
    helper = _text(
        repo / ".scratch" / f"barrier-{mode}.py",
        """from __future__ import annotations
import importlib.util
import sys
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location("review_loop_state_barrier", sys.argv[1])
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
barrier = Path(sys.argv[2])
mode = sys.argv[3]

if mode == "atomic-write":
    def stop_after_owned_resources(*_args, **_kwargs):
        barrier.write_text("ready\\n", encoding="utf-8")
        while True:
            time.sleep(0.05)
    module._atomic_write = stop_after_owned_resources
elif mode == "lock":
    lock_path = Path(sys.argv[4])
    lock_root = module._repo_root(Path.cwd())
    with module._Lock(lock_path, lock_root, lock_root / ".scratch" / "reviews"):
        barrier.write_text("ready\\n", encoding="utf-8")
        while True:
            time.sleep(0.05)
    raise SystemExit(0)
elif mode == "keyboard-interrupt":
    def cancel_after_owned_resources(*_args, **_kwargs):
        raise KeyboardInterrupt
    module._atomic_write = cancel_after_owned_resources
elif mode == "uncertain-state":
    original_replace = module.os.replace
    def corrupt_after_state_replace(source, destination):
        original_replace(source, destination)
        destination = Path(destination)
        if destination.name == "state.json":
            destination.write_text('{"schema_version":2,"rounds":[', encoding="utf-8")
            barrier.write_text("ready\\n", encoding="utf-8")
    module.os.replace = corrupt_after_state_replace
elif mode == "after-commit":
    original_commit = module._commit_operation
    def stop_after_committed_readback(*args, **kwargs):
        receipt = original_commit(*args, **kwargs)
        barrier.write_text("ready\\n", encoding="utf-8")
        while True:
            time.sleep(0.05)
        return receipt
    module._commit_operation = stop_after_committed_readback
else:
    raise AssertionError(mode)

code = module.main(sys.argv[4:])
print(f"RETURN={code}")
""",
    )
    return subprocess.Popen(
        [
            sys.executable,
            str(helper),
            str(ENGINE),
            str(barrier),
            mode,
            *map(str, engine_args),
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _begin_arguments(
    repo: Path,
    state: Path,
    operation_id: str = "begin-1",
) -> list[object]:
    artifact = _text(repo / "design.md", "frozen design\n")
    objective = _text(repo / ".scratch" / "objective.txt", "fix one defect\n")
    scope = _text(repo / ".scratch" / "scope.txt", "scripts and bindings\n")
    runtime_root = _text(repo / ".scratch" / "runtime-root.txt", "trace:42\n")
    diff = _text(repo / ".scratch" / "diff.txt", "initial artifact\n")
    return [
        "begin",
        "--state", state,
        "--operation-id", operation_id,
        "--loop-id", "loop-a",
        "--objective-file", objective,
        "--scope-file", scope,
        "--runtime-root-file", runtime_root,
        "--diff-file", diff,
        "--artifact-file", artifact,
    ]


def _begin(repo: Path, operation_id: str = "begin-1") -> tuple[Path, dict]:
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    result = _run(repo, *_begin_arguments(repo, state, operation_id))
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    return state, receipt


def _record(repo: Path, state: Path, receipt: dict, lane: str, verdict: str) -> subprocess.CompletedProcess[str]:
    payload = {
        "verdict": verdict,
        "rationale": "specific evidence-backed result",
        "root_proven": "yes",
        "scope_unchanged": "yes",
        "verification_adequate": "yes",
    }
    if lane == "scout":
        payload = {"findings": [], "reconciliation": []}
    result_file = _text(
        repo / ".scratch" / f"{lane}.json",
        json.dumps(payload),
    )
    attempt = receipt["attempts"][lane]
    return _run(
        repo,
        "record-result",
        "--state", state,
        "--operation-id", f"result-{lane}-{verdict.lower()}",
        "--round", 1,
        "--lane", lane,
        "--attempt-id", attempt,
        "--artifact-revision", receipt["artifact_revision"],
        "--result-file", result_file,
    )


def test_begin_persists_and_reads_back_before_receipt(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state, receipt = _begin(repo)
    persisted = json.loads(state.read_text(encoding="utf-8"))
    assert receipt["event"] == "ORCHESTRARIUM_REVIEW_LOOP_STATE_V2"
    assert receipt["command"] == "begin"
    assert receipt["state"] == ".scratch/reviews/loop-a/state.json"
    assert receipt["artifact_revision"].startswith("sha256:")
    assert persisted["rounds"][0]["artifact"]["revision"] == receipt["artifact_revision"]
    assert set(receipt["attempts"]) == {"surgical", "deep", "scout"}


def test_begin_is_idempotent_and_conflicting_replay_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state, first = _begin(repo)
    _, replay = _begin(repo)
    assert replay == first
    before = state.read_bytes()
    conflict = _begin_conflict(repo, state)
    assert conflict.returncode != 0
    assert "RLSTATE_OPERATION_CONFLICT" in conflict.stderr
    assert state.read_bytes() == before


def _begin_conflict(repo: Path, state: Path) -> subprocess.CompletedProcess[str]:
    changed = _text(repo / "other.md", "different artifact\n")
    return _run(
        repo,
        "begin",
        "--state", state,
        "--operation-id", "begin-1",
        "--loop-id", "loop-a",
        "--objective-file", repo / ".scratch" / "objective.txt",
        "--scope-file", repo / ".scratch" / "scope.txt",
        "--runtime-root-file", repo / ".scratch" / "runtime-root.txt",
        "--diff-file", repo / ".scratch" / "diff.txt",
        "--artifact-file", changed,
    )


def test_revision_mismatch_and_snapshot_mutation_fail_without_state_change(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state, receipt = _begin(repo)
    payload = _text(repo / ".scratch" / "result.json", json.dumps({"verdict": "PASS", "rationale": "ok", "root_proven": "yes", "scope_unchanged": "yes", "verification_adequate": "yes"}))
    before = state.read_bytes()
    mismatch = _run(repo, "record-result", "--state", state, "--operation-id", "bad-revision", "--round", 1, "--lane", "surgical", "--attempt-id", receipt["attempts"]["surgical"], "--artifact-revision", "sha256:" + "0" * 64, "--result-file", payload)
    assert mismatch.returncode != 0
    assert "RLSTATE_REVISION_MISMATCH" in mismatch.stderr
    assert state.read_bytes() == before

    persisted = json.loads(state.read_text(encoding="utf-8"))
    snapshot = repo / persisted["rounds"][0]["artifact"]["snapshot"]
    snapshot.write_text("mutated\n", encoding="utf-8")
    mutated = _run(repo, "mark-running", "--state", state, "--operation-id", "mark-after-mutation", "--round", 1, "--lane", "surgical", "--attempt-id", receipt["attempts"]["surgical"])
    assert mutated.returncode != 0
    assert "RLSTATE_ARTIFACT_MUTATED" in mutated.stderr
    assert state.read_bytes() == before


def test_failure_retry_keeps_revision_and_round_can_complete(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state, receipt = _begin(repo)
    failed = _run(repo, "record-failure", "--state", state, "--operation-id", "fail-scout", "--round", 1, "--lane", "scout", "--attempt-id", receipt["attempts"]["scout"], "--artifact-revision", receipt["artifact_revision"], "--failure", "died")
    assert failed.returncode == 0, failed.stderr
    retry = _run(repo, "admit-retry", "--state", state, "--operation-id", "retry-scout", "--round", 1, "--lane", "scout", "--failed-attempt-id", receipt["attempts"]["scout"])
    assert retry.returncode == 0, retry.stderr
    retry_receipt = json.loads(retry.stdout)
    assert retry_receipt["artifact_revision"] == receipt["artifact_revision"]
    receipt["attempts"]["scout"] = retry_receipt["attempt_id"]
    for lane in ("surgical", "deep", "scout"):
        assert _record(repo, state, receipt, lane, "REVISE").returncode == 0
    complete = _run(repo, "complete-round", "--state", state, "--operation-id", "complete-1", "--round", 1)
    assert complete.returncode == 0, complete.stderr


def test_next_round_accepts_new_frozen_revision_after_revise(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state, receipt = _begin(repo)
    for lane in ("surgical", "deep", "scout"):
        assert _record(repo, state, receipt, lane, "REVISE").returncode == 0
    assert _run(repo, "complete-round", "--state", state, "--operation-id", "complete-1", "--round", 1).returncode == 0
    revised = _text(repo / "design-v2.md", "corrected design\n")
    diff = _text(repo / ".scratch" / "diff-v2.txt", "answers round one\n")
    next_round = _run(repo, "next-round", "--state", state, "--operation-id", "round-2", "--diff-file", diff, "--artifact-file", revised)
    assert next_round.returncode == 0, next_round.stderr
    second = json.loads(next_round.stdout)
    assert second["round"] == 2
    assert second["artifact_revision"] != receipt["artifact_revision"]
    persisted = json.loads(state.read_text(encoding="utf-8"))
    assert persisted["rounds"][0]["artifact"]["revision"] == receipt["artifact_revision"]


def test_v1_read_compat_and_explicit_migration_required(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "legacy" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"objective": "o", "scope": "s", "runtime_root": "r", "rounds": [{"round": 1, "diff": "initial", "surgical": {"attempt_id": "s1", "verdict": "PASS", "rationale": "specific"}, "deep": {"attempt_id": "d1", "verdict": "PASS", "rationale": "specific"}, "scout": {"attempt_id": "c1", "findings": []}, "lane_failures": []}]}), encoding="utf-8")
    valid = _run(repo, "validate", "--state", state)
    assert valid.returncode == 0
    assert "RLSTATE_V1_READ_ONLY" in valid.stderr
    before = state.read_bytes()
    mutate = _run(repo, "close", "--state", state, "--operation-id", "close-legacy", "--outcome", "converged")
    assert mutate.returncode != 0
    assert "RLSTATE_MIGRATION_REQUIRED" in mutate.stderr
    assert state.read_bytes() == before


def test_v1_migration_is_explicit_and_byte_exact_rollback_is_available(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    artifact = _text(repo / "artifact.md", "authoritative historical artifact\n")
    subprocess.run(["git", "-C", str(repo), "add", "artifact.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Review Loop Test",
            "-c",
            "user.email=review-loop@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    state = repo / ".scratch" / "reviews" / "legacy" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps(
            {
                "objective": "o",
                "scope": "s",
                "runtime_root": "r",
                "rounds": [
                    {
                        "round": 1,
                        "diff": "initial",
                        "surgical": {"attempt_id": "s1", "verdict": "PASS", "rationale": "specific"},
                        "deep": {"attempt_id": "d1", "verdict": "PASS", "rationale": "specific"},
                        "scout": {"attempt_id": "c1", "findings": []},
                        "lane_failures": [],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    original = state.read_bytes()
    migrated = _run(
        repo,
        "migrate-v1",
        "--state",
        state,
        "--operation-id",
        "migration-1",
        "--round-revision",
        f"1=git:{revision}",
    )
    assert migrated.returncode == 0, migrated.stderr
    receipt = json.loads(migrated.stdout)
    assert json.loads(state.read_text(encoding="utf-8"))["schema_version"] == 2
    receipt_file = _text(repo / ".scratch" / "migration-receipt.json", json.dumps(receipt))
    rolled_back = _run(
        repo,
        "rollback-migration",
        "--state",
        state,
        "--migration-receipt",
        receipt_file,
    )
    assert rolled_back.returncode == 0, rolled_back.stderr
    assert state.read_bytes() == original


def test_state_path_must_be_below_repository_scratch_reviews(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    escaped = repo / "state.json"
    result = _run(repo, "validate", "--state", escaped)
    assert result.returncode != 0
    assert "RLSTATE_PATH_ESCAPE" in result.stderr


def test_state_path_must_not_cross_a_link_boundary(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = repo / ".scratch" / "reviews" / "linked"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    result = _run(repo, "validate", "--state", link / "state.json")
    assert result.returncode != 0
    assert "RLSTATE_PATH_ESCAPE" in result.stderr

    outside_state = _text(
        outside / "legacy.json",
        json.dumps(
            {
                "objective": "o",
                "scope": "s",
                "runtime_root": "r",
                "rounds": [
                    {
                        "round": 1,
                        "diff": "d",
                        "surgical": {"attempt_id": "s", "verdict": "PASS", "rationale": "r"},
                        "deep": {"attempt_id": "d", "verdict": "PASS", "rationale": "r"},
                        "scout": {"attempt_id": "c", "findings": []},
                        "lane_failures": [],
                    }
                ],
            }
        ),
    )
    state_link = repo / ".scratch" / "reviews" / "file-link" / "state.json"
    state_link.parent.mkdir()
    state_link.symlink_to(outside_state)
    linked_file = _run(repo, "validate", "--state", state_link)
    assert linked_file.returncode != 0
    assert "RLSTATE_PATH_ESCAPE" in linked_file.stderr


@pytest.mark.parametrize(
    "junction",
    (
        False,
        pytest.param(True, marks=pytest.mark.skipif(os.name != "nt", reason="Windows junction")),
    ),
)
def test_begin_rejects_derived_artifact_link_without_external_mutation(
    tmp_path: Path,
    junction: bool,
) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    state.parent.mkdir(parents=True)
    external = tmp_path / ("junction-target" if junction else "symlink-target")
    external.mkdir()
    _text(external / "sentinel.bin", "external bytes\n")
    before = _tree_bytes(external)
    _directory_link(state.parent / "artifacts", external, junction=junction)

    result = _run(repo, *_begin_arguments(repo, state))

    assert result.returncode != 0
    assert "RLSTATE_PATH_ESCAPE" in result.stderr
    assert _tree_bytes(external) == before
    assert not state.exists()


def test_begin_rejects_derived_lock_symlink_without_external_mutation(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    state.parent.mkdir(parents=True)
    external_lock = _text(tmp_path / "external-lock.bin", "external lock bytes\n")
    before = external_lock.read_bytes()
    try:
        state.with_name(state.name + ".lock").symlink_to(external_lock)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")

    result = _run(repo, *_begin_arguments(repo, state))

    assert result.returncode != 0
    assert "RLSTATE_PATH_ESCAPE" in result.stderr
    assert external_lock.read_bytes() == before
    assert not state.exists()


def test_recovery_rejects_derived_artifact_link_without_external_cleanup(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    revision = _git_revision(repo)
    begin_args = _begin_arguments(repo, state)
    begin_args[-2:] = ["--git-revision", revision]
    begun = _run(repo, *begin_args)
    assert begun.returncode == 0, begun.stderr
    receipt = json.loads(begun.stdout)
    external = tmp_path / "recovery-target"
    external.mkdir()
    _text(external / ("round-9-" + "0" * 64 + ".snapshot"), "owned elsewhere\n")
    _text(external / "sentinel.bin", "external bytes\n")
    before = _tree_bytes(external)
    _directory_link(state.parent / "artifacts", external)

    result = _run(
        repo,
        "mark-running",
        "--state", state,
        "--operation-id", "linked-recovery",
        "--round", 1,
        "--lane", "surgical",
        "--attempt-id", receipt["attempts"]["surgical"],
    )

    assert result.returncode != 0
    assert "RLSTATE_PATH_ESCAPE" in result.stderr
    assert _tree_bytes(external) == before


@pytest.mark.skipif(os.name != "nt", reason="Windows junction")
def test_snapshot_backed_recovery_preserves_path_escape_and_external_tree(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state, receipt = _begin(repo)
    before_state = state.read_bytes()
    persisted = json.loads(before_state)
    snapshot = repo / persisted["rounds"][0]["artifact"]["snapshot"]
    snapshot_bytes = snapshot.read_bytes()
    snapshot_name = snapshot.name
    artifact_dir = snapshot.parent
    snapshot.unlink()
    artifact_dir.rmdir()
    external = tmp_path / "snapshot-recovery-target"
    external.mkdir()
    (external / snapshot_name).write_bytes(snapshot_bytes)
    _text(external / "sentinel.bin", "external bytes\n")
    before_external = _tree_bytes(external)
    _directory_link(artifact_dir, external, junction=True)

    result = _run(
        repo,
        "mark-running",
        "--state", state,
        "--operation-id", "snapshot-linked-recovery",
        "--round", 1,
        "--lane", "surgical",
        "--attempt-id", receipt["attempts"]["surgical"],
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr.startswith("RLSTATE_PATH_ESCAPE:")
    assert "RLSTATE_RECOVERY_REQUIRED" not in result.stderr
    assert state.read_bytes() == before_state
    assert _tree_bytes(external) == before_external


def test_migration_rejects_derived_backup_symlink_without_external_mutation(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    revision = _git_revision(repo)
    state = repo / ".scratch" / "reviews" / "legacy" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps(
            {
                "objective": "o",
                "scope": "s",
                "runtime_root": "r",
                "rounds": [
                    {
                        "round": 1,
                        "diff": "initial",
                        "surgical": {"attempt_id": "s", "verdict": "PASS", "rationale": "r"},
                        "deep": {"attempt_id": "d", "verdict": "PASS", "rationale": "r"},
                        "scout": {"attempt_id": "c", "findings": []},
                        "lane_failures": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    external_backup = _text(tmp_path / "external-v1.bin", "external V1 bytes\n")
    before = external_backup.read_bytes()
    try:
        state.with_name(state.name + ".v1-backup").symlink_to(external_backup)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")

    result = _run(
        repo,
        "migrate-v1",
        "--state", state,
        "--operation-id", "migration-linked-backup",
        "--round-revision", f"1=git:{revision}",
    )

    assert result.returncode != 0
    assert "RLSTATE_PATH_ESCAPE" in result.stderr
    assert external_backup.read_bytes() == before


def test_cleanup_rejects_linked_candidate_without_external_mutation(
    tmp_path: Path,
) -> None:
    module = _engine_module()
    repo = _repo(tmp_path)
    reviews = repo / ".scratch" / "reviews"
    state = reviews / "loop-a" / "state.json"
    state.parent.mkdir(parents=True)
    external = tmp_path / "cleanup-target"
    external.mkdir()
    external_candidate = _text(external / "round-1-candidate.snapshot", "outside\n")
    before = _tree_bytes(external)
    _directory_link(state.parent / "artifacts", external)
    linked_candidate = state.parent / "artifacts" / external_candidate.name

    with pytest.raises(module.StateError, match="RLSTATE_PATH_ESCAPE"):
        module._cleanup_if_unreferenced(state, repo, reviews, linked_candidate)

    assert _tree_bytes(external) == before


@pytest.mark.parametrize("precreate_loop_root", (False, True))
def test_absent_or_empty_loop_root_remains_admissible(
    tmp_path: Path,
    precreate_loop_root: bool,
) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    if precreate_loop_root:
        state.parent.mkdir(parents=True)
        assert tuple(state.parent.iterdir()) == ()

    result = _run(repo, *_begin_arguments(repo, state))

    assert result.returncode == 0, result.stderr
    assert state.is_file()


def test_late_lock_link_after_state_context_is_rejected_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _engine_module()
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    args = _begin_arguments(repo, state)
    external_lock = _text(tmp_path / "late-external-lock.bin", "late bytes\n")
    before = external_lock.read_bytes()
    original = module._state_context

    def context_then_replace(state_arg: str | Path):
        root, reviews, admitted_state = original(state_arg)
        admitted_state.parent.mkdir(parents=True, exist_ok=True)
        admitted_state.with_name(admitted_state.name + ".lock").symlink_to(external_lock)
        return root, reviews, admitted_state

    monkeypatch.setattr(module, "_state_context", context_then_replace)
    monkeypatch.chdir(repo)
    try:
        result = module.main([str(item) for item in args])
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")

    captured = capsys.readouterr()
    assert result == 1
    assert "RLSTATE_PATH_ESCAPE" in captured.err
    assert external_lock.read_bytes() == before


def test_completed_attempt_cannot_later_be_reclassified_as_failure(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state, receipt = _begin(repo)
    assert _record(repo, state, receipt, "surgical", "PASS").returncode == 0
    before = state.read_bytes()
    failure = _run(
        repo,
        "record-failure",
        "--state",
        state,
        "--operation-id",
        "late-failure",
        "--round",
        1,
        "--lane",
        "surgical",
        "--attempt-id",
        receipt["attempts"]["surgical"],
        "--artifact-revision",
        receipt["artifact_revision"],
        "--failure",
        "died",
    )
    assert failure.returncode != 0
    assert "RLSTATE_INVALID" in failure.stderr
    assert state.read_bytes() == before


def test_deeply_nested_result_json_has_bounded_path_free_failure(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state, receipt = _begin(repo)
    before = state.read_bytes()
    depth = 1800
    nested = '{"x":' * depth + "{}" + "}" * depth
    result_file = repo / ".scratch" / "nested-result.json"
    result_file.write_text(
        '{"verdict":"PASS","rationale":"specific","blockers":['
        + nested
        + '],"root_proven":"yes","scope_unchanged":"yes",'
        + '"verification_adequate":"yes"}',
        encoding="utf-8",
    )

    result = _run(
        repo,
        "record-result",
        "--state", state,
        "--operation-id", "deep-result",
        "--round", 1,
        "--lane", "surgical",
        "--attempt-id", receipt["attempts"]["surgical"],
        "--artifact-revision", receipt["artifact_revision"],
        "--result-file", result_file,
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr == "RLSTATE_INVALID: result JSON nesting exceeds the supported limit\n"
    assert "Traceback" not in result.stderr
    assert str(ENGINE) not in result.stderr
    assert state.read_bytes() == before


def test_terminal_state_rejects_new_operations_but_replays_close(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state, receipt = _begin(repo)
    for lane in ("surgical", "deep", "scout"):
        assert _record(repo, state, receipt, lane, "PASS").returncode == 0
    assert _run(repo, "complete-round", "--state", state, "--operation-id", "complete-1", "--round", 1).returncode == 0
    closed = _run(repo, "close", "--state", state, "--operation-id", "close-1", "--outcome", "converged")
    assert closed.returncode == 0, closed.stderr
    assert _run(repo, "close", "--state", state, "--operation-id", "close-1", "--outcome", "converged").stdout == closed.stdout
    before = state.read_bytes()
    second = _run(repo, "close", "--state", state, "--operation-id", "close-2", "--outcome", "converged")
    assert second.returncode != 0
    assert "RLSTATE_INVALID" in second.stderr
    assert state.read_bytes() == before


def test_stable_lock_file_is_not_ownership_and_kernel_lock_releases_on_death(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state, receipt = _begin(repo)
    lock = state.with_name(state.name + ".lock")
    assert lock.is_file()
    barrier = repo / ".scratch" / "lock-held"
    holder = _barrier_process(repo, barrier, lock, mode="lock")
    _wait_for_barrier(barrier, holder)
    blocked = _run(
        repo,
        "mark-running",
        "--state", state,
        "--operation-id", "mark-after-live-lock",
        "--round", 1,
        "--lane", "surgical",
        "--attempt-id", receipt["attempts"]["surgical"],
    )
    assert blocked.returncode != 0
    assert "RLSTATE_LOCKED" in blocked.stderr
    holder.kill()
    holder.communicate(timeout=10)
    recovered = _run(
        repo,
        "mark-running",
        "--state", state,
        "--operation-id", "mark-after-owner-death",
        "--round", 1,
        "--lane", "surgical",
        "--attempt-id", receipt["attempts"]["surgical"],
    )
    assert recovered.returncode == 0, recovered.stderr
    assert lock.is_file()


def test_hard_termination_orphan_snapshot_and_pending_file_recover_next_begin(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    begin_args = _begin_arguments(repo, state)
    barrier = repo / ".scratch" / "snapshot-finalized"
    process = _barrier_process(repo, barrier, *begin_args)
    _wait_for_barrier(barrier, process)
    orphaned = tuple((state.parent / "artifacts").glob("*.snapshot"))
    assert len(orphaned) == 1
    process.kill()
    process.communicate(timeout=10)
    pending = _text(state.parent / f".{state.name}.orphan.tmp", "pending\n")
    assert not state.exists()
    retry = _run(repo, *begin_args)
    assert retry.returncode == 0, retry.stderr
    assert "RLSTATE_RECOVERED" in retry.stderr
    assert not pending.exists()
    persisted = json.loads(state.read_text(encoding="utf-8"))
    referenced = repo / persisted["rounds"][0]["artifact"]["snapshot"]
    snapshots = tuple((state.parent / "artifacts").glob("*.snapshot"))
    assert snapshots == (referenced,)


def test_hard_termination_orphan_migration_backup_recovers_next_migration(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    _text(repo / "artifact.md", "historical artifact\n")
    subprocess.run(["git", "-C", str(repo), "add", "artifact.md"], check=True)
    subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.name=Review Loop Test",
            "-c", "user.email=review-loop@example.invalid",
            "commit", "-q", "-m", "fixture",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    state = repo / ".scratch" / "reviews" / "legacy" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps(
            {
                "objective": "o",
                "scope": "s",
                "runtime_root": "r",
                "rounds": [
                    {
                        "round": 1,
                        "diff": "initial",
                        "surgical": {"attempt_id": "s1", "verdict": "PASS", "rationale": "r"},
                        "deep": {"attempt_id": "d1", "verdict": "PASS", "rationale": "r"},
                        "scout": {"attempt_id": "c1", "findings": []},
                        "lane_failures": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    args = [
        "migrate-v1",
        "--state", state,
        "--operation-id", "migration-1",
        "--round-revision", f"1=git:{revision}",
    ]
    barrier = repo / ".scratch" / "backup-finalized"
    process = _barrier_process(repo, barrier, *args)
    _wait_for_barrier(barrier, process)
    backup = state.with_name(state.name + ".v1-backup")
    assert backup.is_file()
    process.kill()
    process.communicate(timeout=10)
    retry = _run(repo, *args)
    assert retry.returncode == 0, retry.stderr
    assert "RLSTATE_RECOVERED" in retry.stderr
    assert backup.is_file()
    assert json.loads(state.read_text(encoding="utf-8"))["schema_version"] == 2


def test_corrupt_state_requires_operator_recovery_and_preserves_candidates(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"schema_version":2,"rounds":[', encoding="utf-8")
    artifact_dir = state.parent / "artifacts"
    artifact_dir.mkdir()
    orphan_snapshot = _text(
        artifact_dir / ("round-1-" + "0" * 64 + ".snapshot"),
        "candidate\n",
    )
    orphan_backup = _text(state.with_name(state.name + ".v1-backup"), "candidate\n")
    pending = _text(state.parent / f".{state.name}.candidate.tmp", "candidate\n")
    result = _run(
        repo,
        "close",
        "--state", state,
        "--operation-id", "close-corrupt",
        "--outcome", "deadlock",
    )
    assert result.returncode != 0
    assert "RLSTATE_RECOVERY_REQUIRED" in result.stderr
    assert orphan_snapshot.is_file()
    assert orphan_backup.is_file()
    assert pending.is_file()


def test_keyboard_interrupt_cleans_owned_snapshot_and_returns_cancelled(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    args = _begin_arguments(repo, state)
    result = _barrier_process(
        repo,
        repo / ".scratch" / "unused",
        *args,
        mode="keyboard-interrupt",
    ).communicate(timeout=20)
    stdout, stderr = result
    assert "RETURN=130" in stdout
    assert "RLSTATE_CANCELLED" in stderr
    assert not state.exists()
    assert tuple((state.parent / "artifacts").glob("*.snapshot")) == ()
    retry = _run(repo, *args)
    assert retry.returncode == 0, retry.stderr


def test_uncertain_commit_requires_operator_recovery_and_preserves_snapshot(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    args = _begin_arguments(repo, state)
    barrier = repo / ".scratch" / "state-replaced-corrupt"
    process = _barrier_process(repo, barrier, *args, mode="uncertain-state")
    stdout, stderr = process.communicate(timeout=20)
    assert process.returncode == 0, stdout + stderr
    assert barrier.is_file()
    assert "RETURN=1" in stdout
    assert "RLSTATE_COMMIT_UNCERTAIN" in stderr
    snapshots = tuple((state.parent / "artifacts").glob("*.snapshot"))
    assert len(snapshots) == 1

    retry = _run(repo, *args)
    assert retry.returncode != 0
    assert "RLSTATE_RECOVERY_REQUIRED" in retry.stderr
    assert tuple((state.parent / "artifacts").glob("*.snapshot")) == snapshots


def test_hard_termination_after_commit_replays_receipt_and_keeps_reference(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    state = repo / ".scratch" / "reviews" / "loop-a" / "state.json"
    args = _begin_arguments(repo, state)
    barrier = repo / ".scratch" / "state-committed"
    process = _barrier_process(repo, barrier, *args, mode="after-commit")
    _wait_for_barrier(barrier, process)
    committed = json.loads(state.read_text(encoding="utf-8"))
    snapshot = repo / committed["rounds"][0]["artifact"]["snapshot"]
    assert snapshot.is_file()
    process.kill()
    process.communicate(timeout=10)

    replay = _run(repo, *args)
    assert replay.returncode == 0, replay.stderr
    receipt = json.loads(replay.stdout)
    assert receipt == committed["operations"][0]["receipt"]
    assert snapshot.is_file()


@pytest.mark.parametrize("outcome", ("drift", "deadlock"))
def test_nonconverged_close_requires_a_complete_revise_round(
    tmp_path: Path,
    outcome: str,
) -> None:
    repo = _repo(tmp_path)
    state, _receipt = _begin(repo)
    before = state.read_bytes()
    result = _run(
        repo,
        "close",
        "--state",
        state,
        "--operation-id",
        f"early-{outcome}",
        "--outcome",
        outcome,
    )
    assert result.returncode != 0
    assert "RLSTATE_INVALID" in result.stderr
    assert state.read_bytes() == before


def test_runtime_engine_is_projected_and_observability_record_is_current() -> None:
    installer = (ROOT / "scripts" / "production_installer.py").read_text(encoding="utf-8")
    live_surfaces = (
        ROOT / "shared" / "references" / "review-loop-methodology.md",
        ROOT / "shared" / "references" / "ru" / "review-loop-methodology.md",
        ROOT / "src.claude" / "agents" / "contracts" / "review-loop.md",
        ROOT / "src.claude" / "commands" / "agents-review-loop.md",
        ROOT / "src.codex" / "skills" / "review-loop" / "SKILL.md",
    )
    old_bug = "work-items/bugs/2026-07-26-nothing-observes-a-review-loop-that-ran-without-a-ledger.md"
    archived_bug = "work-items/bugs/archive/2026-08/2026-07-26-nothing-observes-a-review-loop-that-ran-without-a-ledger.md"
    assert '"review_loop_state.py"' in installer
    for surface in live_surfaces:
        text = surface.read_text(encoding="utf-8")
        assert old_bug not in text
        assert archived_bug not in text
    codex = live_surfaces[-1].read_text(encoding="utf-8")
    claude = live_surfaces[-2].read_text(encoding="utf-8")
    assert "ORCHESTRARIUM_REVIEW_LOOP_STATE_V2" in codex
    assert "ORCHESTRARIUM_REVIEW_LOOP_STATE_V2" in claude
    assert "absence observer" not in codex
    assert "only launchable attempt IDs" not in claude


@pytest.mark.parametrize(
    ("provider", "script", "installed"),
    (
        ("codex", "install-codex.py", Path(".agents/skills/lead/scripts/review_loop_state.py")),
        ("claude", "install-claude.py", Path(".claude/agents/scripts/review_loop_state.py")),
    ),
)
def test_runtime_engine_is_copied_by_production_installers(
    tmp_path: Path,
    provider: str,
    script: str,
    installed: Path,
) -> None:
    project = tmp_path / provider
    project.mkdir()
    env = os.environ.copy()
    if provider == "codex":
        env["CODEX_BIN"] = str(ROOT / "tests" / "fixtures" / "fake_codex_hooks_host.py")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / script),
            "--target",
            str(project),
            "--force",
            "--allow-unsafe-target",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (project / installed).read_bytes() == ENGINE.read_bytes()
