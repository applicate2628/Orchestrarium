#!/usr/bin/env python3
"""One-shot exact-head patch for safe noncanonical history staging cleanup."""

from __future__ import annotations

from pathlib import Path


LEDGER = Path("scripts/agent-run-ledger.py")
FOLLOWUP_TESTS = Path("tests/test_pr10_followup_regressions.py")
OWNERSHIP_TESTS = Path("tests/test_noncanonical_replay_staging_ownership.py")
NOTES = Path("RELEASE_NOTES.md")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_between(
    text: str, start: str, end: str, replacement: str, label: str
) -> str:
    begin = text.find(start)
    if begin < 0:
        raise SystemExit(f"{label}: start marker not found")
    finish = text.find(end, begin)
    if finish < 0:
        raise SystemExit(f"{label}: end marker not found")
    return text[:begin] + replacement.rstrip() + "\n\n\n" + text[finish:]


def patch_ledger() -> None:
    text = LEDGER.read_text(encoding="utf-8")
    cleanup = '''def _cleanup_owned_history_staging(history_path: Path, staging: Path) -> None:
    """Retire the admitted history hardlink without unlinking its fixed name."""
    try:
        staging_metadata = staging.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))
    try:
        history_metadata = history_path.lstat()
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))
    identity = _noncanonical_file_identity(history_metadata)
    if (
        not stat.S_ISREG(history_metadata.st_mode)
        or stat.S_ISLNK(history_metadata.st_mode)
        or _noncanonical_is_reparse(history_metadata)
        or not stat.S_ISREG(staging_metadata.st_mode)
        or stat.S_ISLNK(staging_metadata.st_mode)
        or _noncanonical_is_reparse(staging_metadata)
        or getattr(history_metadata, "st_nlink", 1) != 2
        or getattr(staging_metadata, "st_nlink", 1) != 2
        or _noncanonical_file_identity(staging_metadata) != identity
    ):
        _noncanonical_fail(
            "HISTORY-CONFLICT", "reserved history staging path conflicts"
        )

    handoff_directory = Path(
        tempfile.mkdtemp(prefix=f".{staging.name}.cleanup-", dir=staging.parent)
    )
    handoff = handoff_directory / "staging"
    removed = False
    try:
        try:
            os.replace(staging, handoff)
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", str(exc))
        try:
            moved_metadata = handoff.lstat()
            current_history = history_path.lstat()
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", str(exc))
        if (
            not stat.S_ISREG(moved_metadata.st_mode)
            or stat.S_ISLNK(moved_metadata.st_mode)
            or _noncanonical_is_reparse(moved_metadata)
            or not stat.S_ISREG(current_history.st_mode)
            or stat.S_ISLNK(current_history.st_mode)
            or _noncanonical_is_reparse(current_history)
            or getattr(moved_metadata, "st_nlink", 1) != 2
            or getattr(current_history, "st_nlink", 1) != 2
            or _noncanonical_file_identity(moved_metadata) != identity
            or _noncanonical_file_identity(current_history) != identity
        ):
            _noncanonical_fail(
                "HISTORY-CONFLICT", "history staging changed during private handoff"
            )
        try:
            handoff.unlink()
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", str(exc))
        removed = True
        try:
            final_history = history_path.lstat()
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", str(exc))
        if (
            not stat.S_ISREG(final_history.st_mode)
            or stat.S_ISLNK(final_history.st_mode)
            or _noncanonical_is_reparse(final_history)
            or getattr(final_history, "st_nlink", 1) != 1
            or _noncanonical_file_identity(final_history) != identity
        ):
            _noncanonical_fail(
                "HISTORY-CONFLICT", "history identity changed during staging cleanup"
            )
    finally:
        # A contested handoff is evidence. Remove only an empty private directory.
        if removed or not handoff.exists():
            try:
                handoff_directory.rmdir()
            except OSError:
                pass
'''
    text = replace_between(
        text,
        "def _validate_owned_history_staging(",
        "def _write_exact_staging_file(",
        cleanup,
        "history staging cleanup owner",
    )
    call_count = text.count("_validate_owned_history_staging(")
    if call_count != 2:
        raise SystemExit(
            f"history staging call sites: expected two matches, found {call_count}"
        )
    text = text.replace(
        "_validate_owned_history_staging(", "_cleanup_owned_history_staging("
    )
    old_comment = '''    # Publication retains exactly the history name and its reserved staging name
    # on one inode because pathname-only unlink cannot prove ownership atomically.
    # Admit only that known two-link state; any other hardlink is not authority.
'''
    new_comment = '''    # A crash after linking history but before private-handoff cleanup leaves the
    # history name plus its reserved staging name on one inode. Admit only that
    # known two-link recovery state; any other hardlink is not authority.
'''
    text = replace_once(
        text, old_comment, new_comment, "history two-link recovery comment"
    )
    LEDGER.write_text(text, encoding="utf-8")


def patch_followup_test() -> None:
    text = FOLLOWUP_TESTS.read_text(encoding="utf-8")
    test = '''def test_noncanonical_history_cleanup_quarantines_fixed_name_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = load_module(LEDGER, "pr10_history_cleanup_handoff_owner")
    history = tmp_path / "agent-runs.history.fixture.jsonl"
    staging = tmp_path / ".agent-runs.history.fixture.jsonl.tmp"
    owned = b"owned history bytes\\n"
    foreign = b"foreign history staging replacement\\n"
    history.write_bytes(owned)
    try:
        os.link(history, staging)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")
    original_replace = ledger.os.replace
    raced = False

    def racing_replace(source, destination, *args, **kwargs):
        nonlocal raced
        if Path(source) == staging and not raced:
            raced = True
            replacement = staging.with_suffix(".foreign")
            replacement.write_bytes(foreign)
            original_replace(replacement, staging)
        return original_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(ledger.os, "replace", racing_replace)

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        ledger._cleanup_owned_history_staging(history, staging)

    assert raced is True
    assert history.read_bytes() == owned
    assert history.stat().st_nlink == 1
    assert not staging.exists()
    preserved = [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.read_bytes() == foreign
    ]
    assert preserved, "the foreign replacement must be quarantined, not deleted"
'''
    text = replace_between(
        text,
        "def test_noncanonical_history_staging_is_validated_without_unlink(",
        "def _noncanonical_replay_fixture(",
        test,
        "history cleanup race regression",
    )
    FOLLOWUP_TESTS.write_text(text, encoding="utf-8")


def patch_ownership_test() -> None:
    text = OWNERSHIP_TESTS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "def test_existing_history_replay_preserves_same_inode_reserved_link(",
        "def test_existing_history_replay_cleans_same_inode_reserved_link(",
        "history cleanup test name",
    )
    old = '''    assert history.read_bytes() == original
    assert staging.read_bytes() == original
    assert history.stat().st_nlink == 2
    assert staging.stat().st_ino == history.stat().st_ino
'''
    new = '''    assert history.read_bytes() == original
    assert history.stat().st_nlink == 1
    assert not staging.exists()
    assert not list(item.glob(f".{staging.name}.cleanup-*"))
'''
    text = replace_once(text, old, new, "history cleanup success expectation")
    OWNERSHIP_TESTS.write_text(text, encoding="utf-8")


def patch_release_notes() -> None:
    text = NOTES.read_text(encoding="utf-8")
    old = (
        "Noncanonical ledger staging rereads stop after the expected bytes plus one; "
        "the admitted inode is moved through an unpredictable private same-directory "
        "handoff and re-admitted before canonical replacement. Fixed history staging "
        "names remain retained when pathname-only cleanup cannot prove atomic ownership."
    )
    new = (
        "Noncanonical ledger staging rereads stop after the expected bytes plus one; "
        "the admitted inode is moved through an unpredictable private same-directory "
        "handoff and re-admitted before canonical replacement. History staging links "
        "use the same fixed-name quarantine boundary and are removed only after the "
        "private handoff is revalidated against the immutable history inode."
    )
    text = replace_once(text, old, new, "history cleanup release note")
    NOTES.write_text(text, encoding="utf-8")


def main() -> None:
    patch_ledger()
    patch_followup_test()
    patch_ownership_test()
    patch_release_notes()


if __name__ == "__main__":
    main()
