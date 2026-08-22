from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-slice-a-detached.py"


def _load():
    assert SCRIPT.is_file(), "detached Slice-A validator owner is missing"
    spec = importlib.util.spec_from_file_location("slice_a_detached_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _repo(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "slice-a@example.invalid")
    _git(repo, "config", "user.name", "Slice A Test")
    (repo / "tracked.txt").write_text("head\n", encoding="utf-8")
    (repo / "excluded.txt").write_text("head-excluded\n", encoding="utf-8")
    (repo / "probe.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (repo / ".gitignore").write_text("/.scratch/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "tracked.txt", "excluded.txt", "probe.sh")
    _git(repo, "commit", "-qm", "fixture")
    (repo / "tracked.txt").write_text("overlay\n", encoding="utf-8")
    (repo / "excluded.txt").write_text("concurrent\n", encoding="utf-8")
    baseline = repo / ".scratch" / "legacy-obligation-migration" / "baseline.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text('{"schemaVersion":1}\n', encoding="utf-8")
    digest = hashlib.sha256(baseline.read_bytes()).hexdigest()
    return repo, baseline, digest


def _command(module, *body: str, timeout: float = 5.0):
    return module.SliceACommand(
        name="fixture-command",
        argv=(sys.executable, "-c", ";".join(body) or "pass"),
        timeout_seconds=timeout,
    )


def _validate(module, repo: Path, run_dir: Path, baseline: Path, digest: str, command):
    return module.validate_slice_a(
        repo_root=repo,
        run_dir=run_dir,
        admitted_paths=("tracked.txt",),
        excluded_paths=("excluded.txt",),
        baseline_path=baseline,
        baseline_sha256=digest,
        commands=(command,),
        validation_scope="unit-fixture",
    )


def test_cli_help_is_side_effect_free() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert "--platform-only" in result.stdout


def test_slice_a_authorization_scope_polarity(
    tmp_path: Path,
) -> None:
    """A successful fixture lifecycle is useful but can never authorize Slice A."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / "success"
    manifest_path = _validate(
        module,
        repo,
        run_dir,
        baseline,
        digest,
        _command(module, "from pathlib import Path", "assert Path('tracked.txt').read_text() == 'overlay\\n'", "assert Path('.git').is_file()", "assert Path('probe.sh').is_file()"),
    )

    assert manifest_path == run_dir / module.TERMINAL_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["result"] == "PASS"
    assert manifest["stableId"] is None
    assert manifest["authorizing"] is False
    assert manifest["publishedAfterCleanup"] is True
    assert manifest["cleanup"]["worktreeRemoved"] is True
    assert not list(repo.parent.glob(".orchestrarium-slice-a-worktree-*"))
    receipts = list((run_dir / "attempts").glob("*.receipt.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text(encoding="utf-8"))["authorizing"] is False
    with pytest.raises(FileExistsError):
        _validate(
            module,
            repo,
            run_dir,
            baseline,
            digest,
            _command(module, "pass"),
        )


def _inject_partial_add(
    module,
    monkeypatch: pytest.MonkeyPatch,
    effect: str,
    *,
    interrupt: bool = False,
) -> tuple[list[Path], object, dict[str, bool]]:
    real_git = module._git
    targets: list[Path] = []
    state = {"registration": False}

    def injected(repo_root: Path, *args: str, check: bool = True):
        if args[:3] == ("worktree", "list", "--porcelain") and state["registration"]:
            payload = (
                f"worktree {targets[0]}\n"
                "HEAD 0000000000000000000000000000000000000000\n"
                "detached\n\n"
            ).encode("utf-8")
            return subprocess.CompletedProcess(["git", *args], 0, payload, b"")
        if args[:2] == ("worktree", "remove") and targets:
            state["registration"] = False
            if targets[0].exists():
                shutil.rmtree(targets[0])
            return subprocess.CompletedProcess(["git", *args], 0, b"", b"")
        if args[:2] != ("worktree", "add"):
            return real_git(repo_root, *args, check=check)
        worktree = Path(args[-2])
        targets.append(worktree)
        if effect in {"path-only", "both"}:
            worktree.mkdir(parents=True)
            (worktree / "partial.txt").write_text("partial\n", encoding="utf-8")
        if effect in {"registration-only", "both"}:
            state["registration"] = True
        if effect not in {"path-only", "registration-only", "both"}:
            raise AssertionError(effect)
        if interrupt:
            raise KeyboardInterrupt()
        return subprocess.CompletedProcess(
            ["git", *args], 1, stdout=b"", stderr=b"injected add failure"
        )

    monkeypatch.setattr(module, "_git", injected)
    return targets, real_git, state


def _cleanup_partial_fixture(real_git, repo: Path, worktree: Path) -> None:
    real_git(repo, "worktree", "remove", "--force", str(worktree), check=False)
    if worktree.exists() or worktree.is_symlink():
        shutil.rmtree(worktree, ignore_errors=True)
    real_git(repo, "worktree", "prune", "--expire", "now", check=False)


def _failed_add_validation(module, repo, baseline, digest, run_dir):
    return module.validate_slice_a(
        repo_root=repo,
        run_dir=run_dir,
        admitted_paths=("tracked.txt",),
        excluded_paths=("excluded.txt",),
        baseline_path=baseline,
        baseline_sha256=digest,
        commands=(_command(module, "pass"),),
        validation_scope="unit-fixture",
    )


def test_worktree_add_nonzero_path_only_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, state = _inject_partial_add(module, monkeypatch, "path-only")
    try:
        manifest = _failed_add_validation(
            module, repo, baseline, digest, repo / ".scratch" / "runs" / "path-only"
        )
        assert manifest is None
        assert len(targets) == 1
        assert not targets[0].exists()
        assert state["registration"] is False
    finally:
        if targets:
            _cleanup_partial_fixture(real_git, repo, targets[0])


def test_worktree_add_nonzero_registration_only_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, state = _inject_partial_add(
        module, monkeypatch, "registration-only"
    )
    try:
        manifest = _failed_add_validation(
            module,
            repo,
            baseline,
            digest,
            repo / ".scratch" / "runs" / "registration-only",
        )
        assert manifest is None
        assert len(targets) == 1
        assert not targets[0].exists()
        assert state["registration"] is False
    finally:
        if targets:
            _cleanup_partial_fixture(real_git, repo, targets[0])


def test_worktree_add_nonzero_both_side_effects_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, state = _inject_partial_add(module, monkeypatch, "both")
    try:
        manifest = _failed_add_validation(
            module, repo, baseline, digest, repo / ".scratch" / "runs" / "both"
        )
        assert manifest is None
        assert len(targets) == 1
        assert not targets[0].exists()
        assert state["registration"] is False
    finally:
        if targets:
            _cleanup_partial_fixture(real_git, repo, targets[0])


def test_worktree_add_interruption_partial_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, state = _inject_partial_add(
        module, monkeypatch, "both", interrupt=True
    )
    run_dir = repo / ".scratch" / "runs" / "interrupted-add"
    try:
        with pytest.raises(KeyboardInterrupt):
            _failed_add_validation(module, repo, baseline, digest, run_dir)
        assert len(targets) == 1
        assert not targets[0].exists()
        assert state["registration"] is False
        assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()
    finally:
        if targets:
            _cleanup_partial_fixture(real_git, repo, targets[0])


def test_partial_acquisition_cleanup_failure_manifest_is_durable_before_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, _state = _inject_partial_add(
        module, monkeypatch, "path-only", interrupt=True
    )
    real_rmtree = module.shutil.rmtree

    def fail_partial_remove(path, *args, **kwargs):
        if targets and Path(path) == targets[0]:
            raise OSError("injected partial cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", fail_partial_remove)
    run_dir = repo / ".scratch" / "runs" / "interrupted-cleanup-failure"
    try:
        with pytest.raises(KeyboardInterrupt):
            _failed_add_validation(module, repo, baseline, digest, run_dir)
        manifest_path = run_dir / module.TERMINAL_MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["result"] == "NON_PASS"
        assert manifest["stableId"] == "E_SLICE_A_VALIDATION_CLEANUP_FAILED"
        assert manifest["authorizing"] is False
        assert manifest["cleanup"]["pathPresent"] is True
        assert manifest["cleanup"]["registrationPresent"] is False
        assert manifest["recoveryPath"] == str(targets[0])
        assert "KeyboardInterrupt" in manifest["originalCause"]
    finally:
        monkeypatch.setattr(module.shutil, "rmtree", real_rmtree)
        if targets:
            _cleanup_partial_fixture(real_git, repo, targets[0])


def test_deep_evidence_directory_uses_a_bounded_workspace_worktree_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows path length must depend on repo scratch, not the evidence nesting."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    real_git = module._git
    targets: list[Path] = []

    def observed_git(repo_root: Path, *args: str, check: bool = True):
        if args[:2] == ("worktree", "add"):
            targets.append(Path(args[-2]))
        return real_git(repo_root, *args, check=check)

    monkeypatch.setattr(module, "_git", observed_git)
    run_dir = repo / ".scratch" / ("deep-evidence-segment-" * 8) / "run"
    manifest_path = _validate(
        module,
        repo,
        run_dir,
        baseline,
        digest,
        _command(module, "pass"),
    )
    assert manifest_path.is_file()
    assert len(targets) == 1
    worktree = targets[0]
    assert worktree.parent.parent == repo.parent
    assert worktree.parent.name.startswith(".orchestrarium-slice-a-worktree-")
    assert worktree.name == "candidate"
    assert ".scratch" not in {part.casefold() for part in worktree.parts}
    assert len(str(worktree)) < len(str(run_dir / "worktree"))
    assert not worktree.exists()


def test_child_failure_has_attempt_receipt_but_no_terminal_manifest(
    tmp_path: Path,
) -> None:
    """A non-zero child remains attempt evidence and cannot publish a manifest."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / "child-failure"
    manifest = _validate(
        module,
        repo,
        run_dir,
        baseline,
        digest,
        _command(module, "import sys", "sys.exit(7)"),
    )

    assert manifest is None
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()
    receipt_path = next((run_dir / "attempts").glob("*.receipt.json"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["authorizing"] is False
    assert receipt["reaped"] is True
    assert receipt["exitCode"] == 7


def test_real_child_timeout_is_reaped(tmp_path: Path) -> None:
    """The process supervisor kills and reaps a child whose sleep exceeds its timeout."""

    module = _load()
    attempts = tmp_path / "attempts"
    attempts.mkdir()
    receipt = module._run_child(
        _command(module, "import time", "time.sleep(5)", timeout=0.05),
        tmp_path,
        attempts,
        1,
    )
    assert receipt.timedOut is True
    assert receipt.reaped is True
    assert receipt.spoolsClosed is True


def test_timed_out_receipt_with_clean_cleanup_has_no_terminal_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed timeout receipt cannot become focused PASS after clean cleanup."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / "timed-out-receipt"
    receipt = module.ChildReceipt(
        schemaVersion=1,
        name="fixture-command",
        argv=(sys.executable, "-c", "pass"),
        cwd=".",
        environmentKeys=("PATH",),
        timeoutSeconds=5.0,
        exitCode=-1,
        timedOut=True,
        cancelled=False,
        reaped=True,
        spoolsClosed=True,
        durationSeconds=0.01,
        stdoutSha256="0" * 64,
        stderrSha256="0" * 64,
    )
    monkeypatch.setattr(module, "_run_child", lambda *_args, **_kwargs: receipt)
    manifest = _validate(
        module, repo, run_dir, baseline, digest, _command(module, "pass")
    )
    assert manifest is None
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()
    assert not list(repo.parent.glob(".orchestrarium-slice-a-worktree-*"))


@pytest.mark.parametrize("mode", ("missing", "spool-open"))
def test_missing_or_unclosed_receipt_fails_without_terminal_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Null receipts and unclosed spools cannot be interpreted as a clean child."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / mode
    if mode == "missing":
        result = None
    else:
        result = module.ChildReceipt(
            schemaVersion=1,
            name="fixture-command",
            argv=(sys.executable, "-c", "pass"),
            cwd=".",
            environmentKeys=("PATH",),
            timeoutSeconds=5.0,
            exitCode=0,
            timedOut=False,
            cancelled=False,
            reaped=True,
            spoolsClosed=False,
            durationSeconds=0.01,
            stdoutSha256="0" * 64,
            stderrSha256="0" * 64,
        )
    monkeypatch.setattr(module, "_run_child", lambda *_args, **_kwargs: result)
    manifest = _validate(
        module, repo, run_dir, baseline, digest, _command(module, "pass")
    )
    assert manifest is None
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()


def test_shell_census_omission_fails_before_child_and_without_manifest(
    tmp_path: Path
) -> None:
    """A detached copy that loses a tracked shell entrypoint is not faithful."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    (repo / "probe.sh").unlink()
    run_dir = repo / ".scratch" / "runs" / "shell-omission"
    manifest = module.validate_slice_a(
        repo_root=repo,
        run_dir=run_dir,
        admitted_paths=("tracked.txt", "probe.sh"),
        excluded_paths=("excluded.txt",),
        baseline_path=baseline,
        baseline_sha256=digest,
        commands=(_command(module, "pass"),),
        validation_scope="unit-fixture",
    )
    assert manifest is None
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()


def test_explicit_untracked_exclusion_is_absent_from_detached_worktree(
    tmp_path: Path,
) -> None:
    """Concurrent untracked notes are classified but never copied into evidence."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    concurrent = repo / ".superpowers" / "concurrent.md"
    concurrent.parent.mkdir()
    concurrent.write_text("unrelated\n", encoding="utf-8")
    run_dir = repo / ".scratch" / "runs" / "untracked-exclusion"
    manifest_path = module.validate_slice_a(
        repo_root=repo,
        run_dir=run_dir,
        admitted_paths=("tracked.txt",),
        excluded_paths=("excluded.txt",),
        ignored_untracked_paths=(".superpowers/concurrent.md",),
        baseline_path=baseline,
        baseline_sha256=digest,
        commands=(
            _command(
                module,
                "from pathlib import Path",
                "assert not Path('.superpowers/concurrent.md').exists()",
            ),
        ),
        validation_scope="unit-fixture",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["result"] == "PASS"
    assert manifest["excludedUntracked"] == [
        {"path": ".superpowers/concurrent.md", "status": "??"}
    ]


def test_cleanup_failure_publishes_one_nonpass_with_recovery_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cleanup failure must never leave a preliminary PASS to overwrite."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / "cleanup-failure"
    real_remove = module._remove_worktree
    retained: list[Path] = []

    def fail_remove(repo_root: Path, worktree: Path):
        retained.append(worktree)
        return module.CleanupOutcome(
            worktree_removed=False,
            registration_removed=False,
            failures=(f"worktree-remove:{tmp_path / 'private-machine-path'}",),
            recovery_path=str(worktree),
        )

    monkeypatch.setattr(module, "_remove_worktree", fail_remove)
    try:
        manifest_path = _validate(
            module, repo, run_dir, baseline, digest, _command(module, "pass")
        )
        assert manifest_path is not None
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["result"] == "NON_PASS"
        assert manifest["stableId"] == "E_SLICE_A_VALIDATION_CLEANUP_FAILED"
        assert manifest["authorizing"] is False
        assert manifest["recoveryPath"] == str(retained[0])
        assert manifest["cleanup"]["failures"] == [
            "worktree-remove",
            "worktree-path-remains",
            "worktree-registration-remains",
        ]
        assert str(tmp_path / "private-machine-path") not in json.dumps(manifest)
        assert not list(run_dir.glob("*.tmp"))
    finally:
        monkeypatch.setattr(module, "_remove_worktree", real_remove)
        assert len(retained) == 1
        real_remove(repo, retained[0])


@pytest.mark.parametrize("boundary", ("child", "publication"))
def test_interruption_before_publication_leaves_no_terminal_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    """An interruption cannot expose a terminal result at either boundary."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / f"interrupt-{boundary}"
    if boundary == "child":
        monkeypatch.setattr(
            module,
            "_run_child",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
    else:
        monkeypatch.setattr(
            module,
            "_atomic_publish",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
    with pytest.raises(KeyboardInterrupt):
        _validate(module, repo, run_dir, baseline, digest, _command(module, "pass"))
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()


@pytest.mark.parametrize(
    "scope", ("unit-fixture", "platform-final-correction-a", "slice-a-final")
)
def test_detached_manifest_always_nonauthorizing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scope: str
) -> None:
    """Catches machine authority or raw/local evidence in a successful manifest."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    command = _command(module, "pass")
    arguments = {
        "repo_root": repo,
        "run_dir": repo / ".scratch" / "runs" / f"nonauthorizing-{scope}",
        "admitted_paths": ("tracked.txt",),
        "excluded_paths": ("excluded.txt",),
        "baseline_path": baseline,
        "baseline_sha256": digest,
        "commands": (command,),
        "validation_scope": scope,
    }
    if scope != "unit-fixture":
        design = tmp_path / f"{scope}-design.md"
        design.write_text("accepted reset design\n", encoding="utf-8")
        design_digest = hashlib.sha256(design.read_bytes()).hexdigest()
        monkeypatch.setattr(module, "_validate_design_currency", lambda *_args: None)
        arguments.update(
            design_path=design,
            design_sha256=design_digest,
        )
    manifest_path = module.validate_slice_a(
        **arguments,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["authorizing"] is False
    assert "worktreePath" not in manifest
    assert "fullSuiteComparison" not in manifest
    assert "baselineRun" not in manifest
    assert "candidateRun" not in manifest
    encoded = json.dumps(manifest, sort_keys=True).casefold()
    assert "environmenttemplate" not in encoded
    assert "longrepr" not in encoded
    for receipt in manifest["receipts"]:
        assert "argv" not in receipt
        assert "cwd" not in receipt
        assert "stdout" not in receipt
        assert "stderr" not in receipt
        assert len(receipt["argvSha256"]) == 64
        assert len(receipt["stdoutSha256"]) == 64
        assert len(receipt["stderrSha256"]) == 64
    assert str(tmp_path) not in json.dumps(manifest, sort_keys=True)
    assert sys.executable not in json.dumps(manifest, sort_keys=True)


def test_r4_authority_surfaces_removed() -> None:
    """Catches reintroduction of the removed candidate-controlled authority owners."""

    module = _load()
    for symbol in (
        "FullSuiteComparisonV1",
        "_FULL_SUITE_HOOK_SOURCE",
        "_derive_exercise_map",
        "_run_paired_full_suites",
        "_load_full_suite_hook",
        "_full_suite_run_record",
    ):
        assert not hasattr(module, symbol), symbol
    assert not list((ROOT / "tests" / "fixtures" / "luna").rglob("*.json"))
