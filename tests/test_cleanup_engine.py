"""Tests for the read-only `.scratch/` valuables watchdog.

REFRAME (2026-07-17): this file previously exercised the sweep/quarantine/
restore/purge/`.hold` mutation engine (v1-v20 of the janitor). That whole
engine was deleted from `scripts/maintenance/cleanup.py` -- see
`work-items/active/2026-07-16-cleanup-routine/design-watchdog-reframe.md` for
the locked design.

PREDICATE REDESIGN (2026-07-17, adversarial-review follow-up): the first cut
gated purely on age (>7 days); live-tree evidence on this repository's own
`.scratch/` showed that gate had near-zero precision (58 of 59 sampled
flagged files were byte-identical to an existing git blob -- recoverable, not
actually at risk). The PRIMARY predicate is now git-content-uniqueness (a
file is a candidate only if `git cat-file --batch-check` reports its
`git hash-object` blob SHA as MISSING from the repository's object
database), with the junk denylist and non-empty filter as SECONDARY filters,
and age demoted to a severity/sort key. When git is unavailable for the scan
(no repository, no git executable, or any git call fails), the engine falls
back to the original age-gated behavior. This file covers: the primary
git-uniqueness predicate, the fail-open fallback (forced deterministically
via monkeypatch, not by hoping the test host's ambient temp directory is
git-free), junk-denylist correctness (secondary filter), the non-empty
filter, self-exclusion, junction/reparse-point safety, and a hard
zero-mutation guarantee covering both predicate paths and the git object
store itself.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "maintenance" / "cleanup.py"
SPEC = importlib.util.spec_from_file_location("cleanup_engine", ENGINE)
assert SPEC is not None and SPEC.loader is not None
cleanup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cleanup
SPEC.loader.exec_module(cleanup)

NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)

# The CLI path (`cleanup.main`) has no way to receive the frozen `NOW` above
# except through its `--now` clock-injection seam (see
# work-items/bugs/2026-07-26-cleanup-cli-path-has-no-now-seam-so-age-tests-are-time-bombs.md).
# Every CLI-path test below must append this to its argv, or its age-dependent
# assertions measure against the real wall clock instead of the frozen NOW.
NOW_ARGV = ["--now", NOW.isoformat()]


def write_file(root: Path, relative: str, *, age_days: float, text: str = "data") -> Path:
    """Write a file under `root` with an mtime `age_days` before NOW."""
    path = root / Path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    timestamp = (NOW - timedelta(days=age_days)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


def paths(valuables: list[dict]) -> list[str]:
    return [item["path"] for item in valuables]


def _snapshot(root: Path) -> dict[str, tuple[float, int, str]]:
    """A deterministic fingerprint of every entry under `root`: mtime, size,
    and a content hash for files (directories get a sentinel hash). Symlinks
    are recorded by their link target, never followed, so a scan that
    silently redirected through one would still show up as changed."""

    snapshot: dict[str, tuple[float, int, str]] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in list(dirnames) + filenames:
            full = Path(dirpath) / name
            relative = full.relative_to(root).as_posix()
            try:
                if full.is_symlink():
                    target = os.readlink(full)
                    snapshot[relative] = (0.0, -1, f"symlink:{target}")
                    continue
                info = full.stat()
                if full.is_dir():
                    snapshot[relative] = (info.st_mtime, -2, "dir")
                else:
                    digest = hashlib.sha256(full.read_bytes()).hexdigest()
                    snapshot[relative] = (info.st_mtime, info.st_size, digest)
            except OSError as exc:  # pragma: no cover - snapshot must not itself fail silently
                raise AssertionError(f"could not snapshot {full}: {exc}")
    return snapshot


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result


def _init_repo(root: Path) -> None:
    _run_git(["init", "-q", "."], root)
    _run_git(["config", "user.email", "t@t"], root)
    _run_git(["config", "user.name", "t"], root)


def _commit_file(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _run_git(["add", relative], root)
    _run_git(["commit", "-q", "-m", "seed"], root)


def _create_junction(link: Path, target: Path) -> bool:
    """Create an NTFS directory junction without needing elevation. Uses
    PowerShell's `New-Item -ItemType Junction` (robust to forward-slash paths
    on any Python build, unlike `cmd /c mklink /J`). Returns False (never
    raises) when unsupported -- non-Windows, no PowerShell, or the call
    fails -- so the caller can skip cleanly."""

    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "New-Item", "-ItemType", "Junction", "-Path", str(link), "-Target", str(target),
            ],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and os.path.isjunction(link)


@pytest.fixture
def no_git(monkeypatch):
    """Force the FAIL-OPEN fallback path deterministically, regardless of
    whether the test host's ambient temp directory happens to sit inside an
    unrelated git repository."""
    monkeypatch.setattr(cleanup, "_find_git_root", lambda start: None)


# ---------------------------------------------------------------------------
# Primary predicate: git-content-uniqueness
# ---------------------------------------------------------------------------


def test_content_matching_an_existing_git_blob_is_not_flagged(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "tracked.md", "shared content, never changes")
    # Never itself committed, but byte-identical to the committed blob.
    write_file(tmp_path, ".scratch/copy.md", age_days=30, text="shared content, never changes")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


def test_content_with_no_matching_blob_is_flagged_even_when_brand_new(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "tracked.md", "some tracked content")
    # Deliberately very fresh (well under the old 7-day gate) to prove age is
    # no longer a filter under the primary predicate.
    write_file(tmp_path, ".scratch/unique.md", age_days=0.01, text="genuinely unique, never committed")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["unique.md"]


def test_uniqueness_predicate_needs_no_prior_commit(tmp_path: Path):
    _init_repo(tmp_path)  # repo exists, but nothing committed anywhere
    write_file(tmp_path, ".scratch/unique.md", age_days=1, text="unique content")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["unique.md"]


def test_junk_denylist_still_excludes_unique_content(tmp_path: Path):
    _init_repo(tmp_path)
    write_file(tmp_path, ".scratch/unique.log", age_days=1, text="unique but junk extension")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


def test_empty_unique_file_is_still_never_flagged(tmp_path: Path):
    _init_repo(tmp_path)
    write_file(tmp_path, ".scratch/empty.md", age_days=1, text="")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


def test_git_mode_results_are_sorted_newest_first(tmp_path: Path):
    _init_repo(tmp_path)
    write_file(tmp_path, ".scratch/older.md", age_days=10, text="unique older content")
    write_file(tmp_path, ".scratch/newer.md", age_days=1, text="unique newer content")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["newer.md", "older.md"]


# ---------------------------------------------------------------------------
# Fail-open fallback (forced deterministically via the `no_git` fixture)
# ---------------------------------------------------------------------------


def test_fallback_gates_on_age_when_not_in_a_git_repository(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/old.md", age_days=30, text="anything")
    write_file(tmp_path, ".scratch/young.md", age_days=1, text="anything else")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["old.md"]


def test_fallback_age_exactly_at_threshold_is_not_flagged(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/edge.md", age_days=7.0)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


def test_fallback_age_just_under_threshold_is_not_flagged(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/edge.md", age_days=6.99)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


def test_fallback_age_just_over_threshold_is_flagged(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/edge.md", age_days=7.01)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["edge.md"]


def test_fallback_age_days_is_configurable(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/edge.md", age_days=2.5)

    short = cleanup.scan_valuables(tmp_path / ".scratch", fallback_age_days=2, now=NOW)
    long = cleanup.scan_valuables(tmp_path / ".scratch", fallback_age_days=3, now=NOW)

    assert paths(short) == ["edge.md"]
    assert long == []


def test_fallback_results_sorted_newest_first_ties_broken_by_path(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/zeta.md", age_days=8)
    write_file(tmp_path, ".scratch/alpha.md", age_days=8)
    write_file(tmp_path, ".scratch/newest.md", age_days=7.5)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["newest.md", "alpha.md", "zeta.md"]


def test_no_git_executable_falls_back_to_age_gate(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cleanup.shutil, "which", lambda _name: None)
    write_file(tmp_path, ".scratch/old.md", age_days=30, text="anything")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["old.md"]


def test_failed_git_hash_object_call_falls_back_to_age_gate(tmp_path: Path, monkeypatch):
    _init_repo(tmp_path)
    write_file(tmp_path, ".scratch/old.md", age_days=30, text="anything")

    monkeypatch.setattr(cleanup, "_hash_object_batch", lambda git_root, files: None)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["old.md"]


def test_failed_git_cat_file_call_falls_back_to_age_gate(tmp_path: Path, monkeypatch):
    _init_repo(tmp_path)
    write_file(tmp_path, ".scratch/old.md", age_days=30, text="anything")

    monkeypatch.setattr(cleanup, "inspect_git_object_set", lambda git_root, shas: None)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["old.md"]


# ---------------------------------------------------------------------------
# Junk-denylist correctness (secondary filter -- forced into fallback mode so
# classification is decided purely by the denylist, not by ambient git state)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extension", [".tmp", ".log", ".out", ".err", ".swp", ".swo"])
def test_denylisted_extensions_are_never_flagged(no_git, tmp_path: Path, extension: str):
    write_file(tmp_path, f".scratch/noise{extension}", age_days=30)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


@pytest.mark.parametrize("basename", ["Thumbs.db", "thumbs.db", ".DS_Store", ".ds_store"])
def test_denylisted_basenames_are_never_flagged(no_git, tmp_path: Path, basename: str):
    write_file(tmp_path, f".scratch/{basename}", age_days=30)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


@pytest.mark.parametrize(
    "dirname",
    ["__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", "dist", "build"],
)
def test_denylisted_directories_are_pruned_when_a_direct_child_of_scratch(
    no_git, tmp_path: Path, dirname: str
):
    write_file(tmp_path, f".scratch/{dirname}/important-looking.md", age_days=30)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


@pytest.mark.parametrize("dirname", ["build", "dist", ".cache"])
def test_ambiguous_directory_name_nested_deeper_is_not_pruned(no_git, tmp_path: Path, dirname: str):
    # These AMBIGUOUS names could coincidentally name a hand-authored folder,
    # so they are NOT a direct child of `.scratch/` here (two levels down)
    # and the directory-pruning rule must not hide this file.
    write_file(tmp_path, f".scratch/plans/{dirname}/notes.md", age_days=30)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == [f"plans/{dirname}/notes.md"]


@pytest.mark.parametrize(
    "dirname", ["__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache"]
)
def test_unambiguous_cache_directory_is_pruned_at_any_depth(no_git, tmp_path: Path, dirname: str):
    # Regression: a prior direct-child-only version of this rule leaked
    # hundreds of nested cache-directory files (measured: 332 .pyc files
    # under nested __pycache__/, 572 total under nested junk dirs, on this
    # repository's own live .scratch/). These names are UNAMBIGUOUS --
    # nothing hand-authored ever lives inside one -- so they must be pruned
    # regardless of nesting depth.
    write_file(
        tmp_path,
        f".scratch/reviews/some-snapshot/tests/{dirname}/compiled.pyc",
        age_days=30,
    )

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


@pytest.mark.parametrize("dirname", ["codex-prompts", "claude-prompts"])
@pytest.mark.parametrize(
    "suffix",
    [".md", ".out", ".err", ".stdout", ".stderr", ".stdout.txt", ".stderr.txt", ".last.txt", ".events.txt"],
)
def test_prompt_capture_shapes_are_excluded_under_their_directory(
    no_git, tmp_path: Path, dirname: str, suffix: str
):
    write_file(tmp_path, f".scratch/{dirname}/task-abc{suffix}", age_days=30)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


def test_markdown_outside_prompt_capture_directory_is_not_a_blanket_exclusion(no_git, tmp_path: Path):
    # The prompt-capture rule must NOT become "all .md is junk": a hand-authored
    # note elsewhere in .scratch/ is exactly what this watchdog protects.
    write_file(tmp_path, ".scratch/notes/important-plan.md", age_days=30)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["notes/important-plan.md"]


def test_self_report_basename_never_flags_itself(no_git, tmp_path: Path):
    write_file(
        tmp_path,
        f".scratch/{cleanup.DEFAULT_JUNK_DENYLIST.self_report_basename}",
        age_days=30,
    )

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


def test_denylist_is_configurable_not_hardcoded(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/data.custom", age_days=30)
    custom = cleanup.JunkDenylist(extensions=frozenset({".custom"}))

    default_result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)
    custom_result = cleanup.scan_valuables(tmp_path / ".scratch", denylist=custom, now=NOW)

    assert paths(default_result) == ["data.custom"]
    assert custom_result == []


# ---------------------------------------------------------------------------
# Non-empty filter
# ---------------------------------------------------------------------------


def test_empty_old_file_is_never_flagged(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/empty.md", age_days=30, text="")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


def test_nonempty_old_file_is_flagged(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/data.md", age_days=30, text="valuable content")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["data.md"]
    assert result[0]["size"] == len("valuable content")


# ---------------------------------------------------------------------------
# Baseline behavior / result shape / walker safety
# ---------------------------------------------------------------------------


def test_missing_scratch_dir_returns_empty_list(tmp_path: Path):
    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []


def test_result_entries_have_the_documented_shape(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/data.md", age_days=10, text="hello")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert len(result) == 1
    entry = result[0]
    assert set(entry) == {"path", "age_days", "size"}
    assert isinstance(entry["path"], str)
    assert isinstance(entry["age_days"], float)
    assert isinstance(entry["size"], int)
    assert entry["age_days"] == pytest.approx(10.0, abs=0.01)
    assert entry["size"] == 5


def test_nested_valuable_uses_scratch_relative_posix_path(no_git, tmp_path: Path):
    write_file(tmp_path, ".scratch/deep/nested/dir/data.md", age_days=30)

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert paths(result) == ["deep/nested/dir/data.md"]


def test_symlink_is_never_followed_or_flagged(no_git, tmp_path: Path):
    outside = write_file(tmp_path, "outside/target.md", age_days=100)
    link = tmp_path / ".scratch" / "link.md"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this host")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []
    assert outside.exists()


def test_junction_is_never_followed_or_flagged(no_git, tmp_path: Path):
    """Windows-specific regression: `entry.is_symlink()` alone returns False
    for an NTFS directory junction, so a walker relying on it alone would
    descend into the junction and enumerate files entirely outside
    `.scratch/`. `_is_link_or_reparse` must catch this too."""

    outside_target = write_file(tmp_path, "outside/target.md", age_days=100)
    junction = tmp_path / ".scratch" / "junction-dir"
    junction.parent.mkdir(parents=True, exist_ok=True)
    if not _create_junction(junction, outside_target.parent):
        pytest.skip("junction creation is unavailable on this host")

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    assert result == []
    assert outside_target.exists()


# ---------------------------------------------------------------------------
# Zero-mutation guarantee (both predicate paths, including the git object store)
# ---------------------------------------------------------------------------


def test_scan_never_mutates_the_tree_in_fallback_mode(no_git, tmp_path: Path):
    """Snapshot a nontrivial mixed tree, run the scan (twice, including once
    via the CLI), and assert the tree is byte-identical afterwards -- the
    scan must not create, modify, or delete anything, including its own
    directory listing order or mtimes."""

    write_file(tmp_path, ".scratch/valuable/plan.md", age_days=30, text="keep me")
    write_file(tmp_path, ".scratch/valuable/fresh.md", age_days=1, text="too young")
    write_file(tmp_path, ".scratch/noise.tmp", age_days=30)
    write_file(tmp_path, ".scratch/noise.log", age_days=30)
    write_file(tmp_path, ".scratch/__pycache__/cached.pyc", age_days=30)
    write_file(tmp_path, ".scratch/codex-prompts/run1.md", age_days=30)
    write_file(tmp_path, ".scratch/codex-prompts/run1.out", age_days=30)
    write_file(tmp_path, ".scratch/empty.md", age_days=30, text="")
    outside = write_file(tmp_path, "outside/target.md", age_days=100)
    link = tmp_path / ".scratch" / "link.md"
    try:
        link.symlink_to(outside)
        has_symlink = True
    except (OSError, NotImplementedError):
        has_symlink = False

    before = _snapshot(tmp_path)

    result_one = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)
    assert paths(result_one) == ["valuable/plan.md"]

    result_two = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)
    assert result_two == result_one

    exit_code = cleanup.main(["--root", str(tmp_path), *NOW_ARGV])
    assert exit_code == 0

    after = _snapshot(tmp_path)
    assert after == before, "scan_valuables (or main()) mutated the tree"
    if has_symlink:
        assert link.is_symlink()


def test_scan_never_mutates_the_tree_or_git_object_store_in_git_mode(tmp_path: Path):
    """The git-uniqueness path runs two git subprocesses; both must be
    provably read-only, including the `.git/objects` store itself (a
    `git hash-object -w` or any write there would be a real, if subtle,
    mutation this module must never perform)."""

    _init_repo(tmp_path)
    _commit_file(tmp_path, "tracked.md", "tracked content")
    write_file(tmp_path, ".scratch/unique.md", age_days=1, text="unique content, never committed")
    write_file(tmp_path, ".scratch/recoverable.md", age_days=1, text="tracked content")

    before = _snapshot(tmp_path)
    objects_before = sorted(
        str(p.relative_to(tmp_path)) for p in (tmp_path / ".git" / "objects").rglob("*") if p.is_file()
    )

    result = cleanup.scan_valuables(tmp_path / ".scratch", now=NOW)

    exit_code = cleanup.main(["--root", str(tmp_path), *NOW_ARGV])
    assert exit_code == 0

    after = _snapshot(tmp_path)
    objects_after = sorted(
        str(p.relative_to(tmp_path)) for p in (tmp_path / ".git" / "objects").rglob("*") if p.is_file()
    )
    # Mutation checks FIRST: if a future change ever writes to the object
    # store (e.g. a stray `-w`), this must surface as the specific "wrote to
    # git object store" failure, not get masked by a generic wrong-result
    # assertion failing first.
    assert objects_after == objects_before, "scan_valuables (or main()) wrote to the git object store"
    assert after == before, "scan_valuables (or main()) mutated the working tree"
    assert paths(result) == ["unique.md"]


def test_json_cli_also_never_mutates_the_tree(no_git, tmp_path: Path, capsys):
    write_file(tmp_path, ".scratch/data.md", age_days=30, text="valuable")
    before = _snapshot(tmp_path)

    exit_code = cleanup.main(["--root", str(tmp_path), "--json", *NOW_ARGV])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert paths(payload["valuables"]) == ["data.md"]
    assert _snapshot(tmp_path) == before


# ---------------------------------------------------------------------------
# CLI report surface (debugging only -- never the "automatic" mechanism)
# ---------------------------------------------------------------------------


def test_cli_report_lists_valuables_and_returns_zero(no_git, tmp_path: Path, capsys):
    write_file(tmp_path, ".scratch/data.md", age_days=30, text="valuable")

    exit_code = cleanup.main(["--root", str(tmp_path), *NOW_ARGV])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "data.md" in captured.out
    assert "watchdog" in captured.out


def test_cli_report_lists_longest_lingering_first(no_git, tmp_path: Path, capsys):
    # The operator's stated risk is data that has lingered LONG, not the
    # current session's own recent churn -- the report must lead with the
    # OLDEST candidate, not the newest.
    write_file(tmp_path, ".scratch/newest.md", age_days=8, text="new")
    write_file(tmp_path, ".scratch/oldest.md", age_days=90, text="old")

    exit_code = cleanup.main(["--root", str(tmp_path), *NOW_ARGV])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "longest-lingering first" in captured.out
    oldest_index = captured.out.index("oldest.md")
    newest_index = captured.out.index("newest.md")
    assert oldest_index < newest_index, "longest-lingering (oldest) entry must print first"


def test_cli_report_says_none_found_when_scratch_is_clean(no_git, tmp_path: Path, capsys):
    write_file(tmp_path, ".scratch/fresh.md", age_days=1)

    exit_code = cleanup.main(["--root", str(tmp_path), *NOW_ARGV])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "no valuables" in captured.out


def test_cli_fallback_age_days_flag_overrides_default_threshold(no_git, tmp_path: Path, capsys):
    write_file(tmp_path, ".scratch/data.md", age_days=3)

    exit_code = cleanup.main(
        ["--root", str(tmp_path), "--fallback-age-days", "2", "--json", *NOW_ARGV]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert paths(payload["valuables"]) == ["data.md"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
