#!/usr/bin/env python3
"""One-shot exact-head patch for PR #10 identity-bound ledger publication."""

from pathlib import Path


LEDGER = Path("scripts/agent-run-ledger.py")
NOTES = Path("RELEASE_NOTES.md")


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    begin = text.find(start)
    if begin < 0:
        raise SystemExit(f"missing start marker: {start}")
    finish = text.find(end, begin)
    if finish < 0:
        raise SystemExit(f"missing end marker: {end}")
    return text[:begin] + replacement.rstrip() + "\n\n\n" + text[finish:]


def main() -> None:
    text = LEDGER.read_text(encoding="utf-8")
    replacement = '''def _replace_exact_staging_file(
    path: Path,
    destination: Path,
    expected: bytes,
    identity: tuple[int, int, int, int],
) -> None:
    """Publish only the admitted inode after a private same-directory handoff."""

    def admit(candidate: Path) -> None:
        descriptor, opened = _noncanonical_open_ordinary(candidate, writable=False)
        try:
            if (
                _noncanonical_file_identity(opened) != identity
                or getattr(opened, "st_nlink", 1) != 1
            ):
                _noncanonical_fail(
                    "HISTORY-CONFLICT",
                    f"staging descriptor identity changed: {candidate.name}",
                )
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                actual = stream.read(len(expected) + 1)
                after_read = os.fstat(stream.fileno())
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", str(exc))
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        try:
            current = candidate.lstat()
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", str(exc))
        if (
            actual != expected
            or _noncanonical_file_identity(after_read) != identity
            or getattr(after_read, "st_nlink", 1) != 1
            or not stat.S_ISREG(current.st_mode)
            or stat.S_ISLNK(current.st_mode)
            or _noncanonical_is_reparse(current)
            or getattr(current, "st_nlink", 1) != 1
            or _noncanonical_file_identity(current) != identity
        ):
            _noncanonical_fail(
                "HISTORY-CONFLICT",
                f"staging path changed before publication: {candidate.name}",
            )

    admit(path)
    handoff_directory = Path(
        tempfile.mkdtemp(prefix=f".{path.name}.publish-", dir=path.parent)
    )
    handoff = handoff_directory / "candidate"
    published = False
    try:
        try:
            os.replace(path, handoff)
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", str(exc))
        # A fixed-name swap is now quarantined under an unpredictable private
        # directory. Re-admit the moved object before the canonical name is touched.
        admit(handoff)
        try:
            os.replace(handoff, destination)
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", str(exc))
        published = True
        try:
            current = destination.lstat()
        except OSError as exc:
            _noncanonical_fail("READBACK-INDETERMINATE", str(exc))
        if (
            not stat.S_ISREG(current.st_mode)
            or stat.S_ISLNK(current.st_mode)
            or _noncanonical_is_reparse(current)
            or getattr(current, "st_nlink", 1) != 1
            or _noncanonical_file_identity(current) != identity
        ):
            _noncanonical_fail(
                "READBACK-INDETERMINATE",
                "published ledger identity changed at replacement",
            )
    finally:
        # rmdir cannot remove a foreign file. A contested or failed handoff is
        # deliberately preserved for diagnosis rather than pathname-cleaned.
        if published or not handoff.exists():
            try:
                handoff_directory.rmdir()
            except OSError:
                pass
'''
    text = replace_between(
        text,
        "def _replace_exact_staging_file(",
        "def _publish_noncanonical_history_blob(",
        replacement,
    )
    LEDGER.write_text(text, encoding="utf-8")

    notes = NOTES.read_text(encoding="utf-8")
    old = (
        "Noncanonical ledger staging rereads stop after the expected bytes plus one, "
        "is re-admitted immediately before replacement, and fixed recovery or history "
        "staging names are retained when pathname-only cleanup cannot prove atomic ownership."
    )
    new = (
        "Noncanonical ledger staging rereads stop after the expected bytes plus one; "
        "the admitted inode is moved through an unpredictable private same-directory "
        "handoff and re-admitted before canonical replacement. Fixed history staging "
        "names remain retained when pathname-only cleanup cannot prove atomic ownership."
    )
    if notes.count(old) != 1:
        raise SystemExit("release-note staging sentence drifted")
    NOTES.write_text(notes.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
