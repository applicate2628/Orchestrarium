#!/usr/bin/env python3
"""One-shot exact-head patch driver for PR #10 follow-up review findings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


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


def patch_provider() -> None:
    path = Path("scripts/provider_prompt.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''            normalized_option = option.lstrip("-/").casefold() if option else ""
            carrier = None
            if normalized_option in {"header", "h"}:
                carrier = add_header_argument
            elif normalized_option in {"env", "e"}:
                carrier = add_env_argument
''',
        '''            words = option_words(option) if option else ()
            carrier = None
            if words and words[-1] in {"header", "headers"} and "file" not in words:
                carrier = add_header_argument
            elif words in {
                ("e",),
                ("env",),
                ("environment",),
                ("env", "var"),
                ("environment", "variable"),
                ("set", "env"),
            }:
                carrier = add_env_argument
''',
        "provider carrier aliases",
    )

    text = replace_once(
        text,
        '''            elif inline_value is not None and "://" in inline_value:
                add_url_credentials(inline_value)
            elif option is None and "://" in argument:
                add_url_credentials(argument)
            index += 1
''',
        '''            elif inline_value is not None and "://" in inline_value:
                add_url_credentials(inline_value)
            elif option is None:
                name, separator, value = argument.partition("=")
                if separator and re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]*", name, re.ASCII
                ):
                    add_env_value(name, value)
                elif "://" in argument:
                    add_url_credentials(argument)
            index += 1
''',
        "provider bare environment assignment",
    )

    helper = '''def _kimi_capability_write_exclusion(descriptor: int):
    """Exclude Windows writers before capability metadata or bytes are sampled."""
    from contextlib import nullcontext

    if os.name != "nt":
        return nullcontext()

    import ctypes
    import msvcrt
    from ctypes import wintypes

    class Overlapped(ctypes.Structure):
        _fields_ = (
            ("Internal", ctypes.c_size_t),
            ("InternalHigh", ctypes.c_size_t),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        )

    class WindowsFileLock:
        def __init__(self) -> None:
            self.overlapped = Overlapped()
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self.handle = wintypes.HANDLE(msvcrt.get_osfhandle(descriptor))
            self.length = PROMPT_SNAPSHOT_MAX_BYTES + 1
            self.lock_file_ex = self.kernel32.LockFileEx
            self.lock_file_ex.argtypes = (
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(Overlapped),
            )
            self.lock_file_ex.restype = wintypes.BOOL
            self.unlock_file_ex = self.kernel32.UnlockFileEx
            self.unlock_file_ex.argtypes = (
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(Overlapped),
            )
            self.unlock_file_ex.restype = wintypes.BOOL

        def __enter__(self):
            flags = 0x00000002 | 0x00000001
            if not self.lock_file_ex(
                self.handle,
                flags,
                0,
                self.length & 0xFFFFFFFF,
                self.length >> 32,
                ctypes.byref(self.overlapped),
            ):
                raise OSError(
                    ctypes.get_last_error(),
                    "unable to exclude capability-file writers",
                )
            return self

        def __exit__(self, exc_type, _exc, _traceback):
            unlocked = self.unlock_file_ex(
                self.handle,
                0,
                self.length & 0xFFFFFFFF,
                self.length >> 32,
                ctypes.byref(self.overlapped),
            )
            if not unlocked and exc_type is None:
                raise OSError(
                    ctypes.get_last_error(),
                    "unable to release capability-file writer exclusion",
                )
            return False

    return WindowsFileLock()
'''
    text = replace_once(
        text,
        '''    return tuple(result)


def read_kimi_capability_selection(path: Path) -> KimiCapabilitySelectionV1:
''',
        '''    return tuple(result)


''' + helper + '''


def read_kimi_capability_selection(path: Path) -> KimiCapabilitySelectionV1:
''',
        "provider capability exclusion helper",
    )

    old_read = '''        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_mode) != (
                before.st_dev,
                before.st_ino,
                before.st_mode,
            ):
                raise ValueError("identity")
            raw = stream.read(PROMPT_SNAPSHOT_MAX_BYTES + 1)
            after_read = os.fstat(stream.fileno())
            stream.seek(0)
            confirmed_raw = stream.read(PROMPT_SNAPSHOT_MAX_BYTES + 1)
            after_confirmation = os.fstat(stream.fileno())
        validate_no_reparse_components(candidate)
        after_path = candidate.lstat()
        stable_fields = (
            "st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns"
        )
        # Windows pathname and descriptor ctime have different semantics.
        # Compare each interface with its own earlier observation.
        if (
            tuple(getattr(opened, name) for name in stable_fields)
            != tuple(getattr(after_read, name) for name in stable_fields)
            or tuple(getattr(opened, name) for name in stable_fields)
            != tuple(getattr(after_confirmation, name) for name in stable_fields)
            or tuple(getattr(before, name) for name in stable_fields)
            != tuple(getattr(after_path, name) for name in stable_fields)
            or raw != confirmed_raw
            or len(raw) != opened.st_size
            or len(raw) > PROMPT_SNAPSHOT_MAX_BYTES
        ):
            raise ValueError("snapshot changed or exceeded size limit")
'''
    new_read = '''        with os.fdopen(descriptor, "rb") as stream:
            with _kimi_capability_write_exclusion(stream.fileno()):
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino, opened.st_mode) != (
                    before.st_dev,
                    before.st_ino,
                    before.st_mode,
                ):
                    raise ValueError("identity")
                raw = stream.read(PROMPT_SNAPSHOT_MAX_BYTES + 1)
                after_read = os.fstat(stream.fileno())
                stream.seek(0)
                confirmed_raw = stream.read(PROMPT_SNAPSHOT_MAX_BYTES + 1)
                after_confirmation = os.fstat(stream.fileno())
                validate_no_reparse_components(candidate)
                after_path = candidate.lstat()
                stable_fields = (
                    "st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns"
                )
                # Windows pathname and descriptor ctime have different semantics.
                # Compare each interface with its own earlier observation.
                if (
                    tuple(getattr(opened, name) for name in stable_fields)
                    != tuple(getattr(after_read, name) for name in stable_fields)
                    or tuple(getattr(opened, name) for name in stable_fields)
                    != tuple(getattr(after_confirmation, name) for name in stable_fields)
                    or tuple(getattr(before, name) for name in stable_fields)
                    != tuple(getattr(after_path, name) for name in stable_fields)
                    or raw != confirmed_raw
                    or len(raw) != opened.st_size
                    or len(raw) > PROMPT_SNAPSHOT_MAX_BYTES
                ):
                    raise ValueError("snapshot changed or exceeded size limit")
'''
    text = replace_once(
        text, old_read, new_read, "provider capability read exclusion scope"
    )
    path.write_text(text, encoding="utf-8")


def patch_ledger() -> None:
    path = Path("scripts/agent-run-ledger.py")
    text = path.read_text(encoding="utf-8")

    history_validator = '''def _validate_owned_history_staging(history_path: Path, staging: Path) -> None:
    """Validate the known two-link publication state without racy deletion."""
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
    if (
        not stat.S_ISREG(history_metadata.st_mode)
        or stat.S_ISLNK(history_metadata.st_mode)
        or _noncanonical_is_reparse(history_metadata)
        or not stat.S_ISREG(staging_metadata.st_mode)
        or stat.S_ISLNK(staging_metadata.st_mode)
        or _noncanonical_is_reparse(staging_metadata)
        or getattr(history_metadata, "st_nlink", 1) != 2
        or getattr(staging_metadata, "st_nlink", 1) != 2
        or (history_metadata.st_dev, history_metadata.st_ino)
        != (staging_metadata.st_dev, staging_metadata.st_ino)
    ):
        _noncanonical_fail(
            "HISTORY-CONFLICT", "reserved history staging path conflicts"
        )
'''
    text = replace_between(
        text,
        "def _cleanup_owned_history_staging(",
        "def _write_exact_staging_file(",
        history_validator,
        "ledger history staging retention",
    )
    text = text.replace(
        "_cleanup_owned_history_staging(", "_validate_owned_history_staging("
    )

    verified_replace = '''def _replace_exact_staging_file(
    path: Path,
    destination: Path,
    expected: bytes,
    identity: tuple[int, int, int, int],
) -> None:
    """Re-admit the exact bounded candidate immediately before replacement."""
    descriptor, opened = _noncanonical_open_ordinary(path, writable=False)
    try:
        if (
            _noncanonical_file_identity(opened) != identity
            or getattr(opened, "st_nlink", 1) != 1
        ):
            _noncanonical_fail(
                "HISTORY-CONFLICT",
                f"staging descriptor identity changed: {path.name}",
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
        current = path.lstat()
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
            f"staging path changed before publication: {path.name}",
        )
    os.replace(path, destination)
'''
    text = replace_between(
        text,
        "def _cleanup_exact_staging_file(",
        "def _publish_noncanonical_history_blob(",
        verified_replace,
        "ledger verified replacement owner",
    )

    text = replace_once(
        text,
        '''        os.replace(candidate, ledger_path)
        replaced = True
        if inject_failure == "post-ledger-replace-readback":
''',
        '''        _replace_exact_staging_file(
            candidate, ledger_path, marker_bytes, staging_identity
        )
        replaced = True
        if inject_failure == "post-ledger-replace-readback":
''',
        "ledger apply replacement",
    )
    text = replace_once(
        text,
        '''        os.replace(candidate, ledger_path)
        replaced = True
        if inject_failure == "post-ledger-replace-readback":
''',
        '''        _replace_exact_staging_file(
            candidate, ledger_path, original, staging_identity
        )
        replaced = True
        if inject_failure == "post-ledger-replace-readback":
''',
        "ledger rollback replacement",
    )

    cleanup_block = '''    finally:
        if not replaced and staging_identity is not None:
            _cleanup_exact_staging_file(candidate, staging_identity)
'''
    count = text.count(cleanup_block)
    if count != 2:
        raise SystemExit(
            f"ledger preserved-candidate cleanup: expected two matches, found {count}"
        )
    text = text.replace(cleanup_block, "")
    text = text.replace(
        "# A crash after os.link() but before staging cleanup leaves exactly the\n"
        "    # history name plus its owned staging name on the same inode. Admit only that\n"
        "    # known two-link crash state; an arbitrary external hardlink is not authority.\n",
        "# Publication retains exactly the history name and its reserved staging name\n"
        "    # on one inode because pathname-only unlink cannot prove ownership atomically.\n"
        "    # Admit only that known two-link state; any other hardlink is not authority.\n",
    )
    path.write_text(text, encoding="utf-8")


def patch_followup_tests() -> None:
    path = Path("tests/test_pr10_followup_regressions.py")
    text = path.read_text(encoding="utf-8")

    exact_cleanup_test = '''def test_noncanonical_failed_apply_retains_owned_candidate_without_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, item, expected_sha256, original, marker_bytes = _noncanonical_replay_fixture(
        tmp_path, "pr10_failed_apply_retention_owner"
    )
    canonical = item / "agent-runs.jsonl"
    canonical.write_bytes(original)
    candidate = item / "agent-runs.jsonl.tmp"
    monkeypatch.setattr(
        ledger, "_validate_noncanonical_marker_candidate", lambda *_args: None
    )
    original_unlink = ledger.Path.unlink

    def forbid_candidate_unlink(path: Path, *args, **kwargs):
        if Path(path) == candidate:
            raise AssertionError("fixed candidate must not be pathname-unlinked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(ledger.Path, "unlink", forbid_candidate_unlink)

    completed, _history = ledger._command_apply_noncanonical_history(
        item,
        expected_sha256,
        "linked-ledger-replay",
        "2026-09-10T12:00:00Z",
        ledger.load_validator(),
        "pre-ledger-replace",
    )

    assert completed is False
    assert candidate.read_bytes() == marker_bytes
'''
    text = replace_between(
        text,
        "def test_noncanonical_cleanup_never_unlinks_a_swapped_candidate(",
        "def test_noncanonical_history_cleanup_never_unlinks_a_swapped_name(",
        exact_cleanup_test,
        "follow-up exact cleanup regression",
    )

    history_cleanup_test = '''def test_noncanonical_history_staging_is_validated_without_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = load_module(LEDGER, "pr10_history_cleanup_preservation_owner")
    history = tmp_path / "agent-runs.history.fixture.jsonl"
    staging = tmp_path / ".agent-runs.history.fixture.jsonl.tmp"
    owned = b"owned history bytes\\n"
    history.write_bytes(owned)
    try:
        os.link(history, staging)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")
    original_unlink = ledger.Path.unlink

    def forbid_staging_unlink(path: Path, *args, **kwargs):
        if Path(path) == staging:
            raise AssertionError("history staging must not be pathname-unlinked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(ledger.Path, "unlink", forbid_staging_unlink)

    ledger._validate_owned_history_staging(history, staging)

    assert history.read_bytes() == owned
    assert staging.read_bytes() == owned
    assert history.stat().st_ino == staging.stat().st_ino
'''
    text = replace_between(
        text,
        "def test_noncanonical_history_cleanup_never_unlinks_a_swapped_name(",
        "def _noncanonical_replay_fixture(",
        history_cleanup_test,
        "follow-up history cleanup regression",
    )

    publication_start = text.find(
        '@pytest.mark.parametrize("operation", ("apply", "rollback"))\n'
        "def test_noncanonical_publish_never_commits_a_swapped_candidate("
    )
    if publication_start < 0:
        raise SystemExit("follow-up publication regression: start marker not found")
    publication_test = '''@pytest.mark.parametrize("operation", ("apply", "rollback"))
def test_noncanonical_publish_never_commits_a_swapped_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    ledger, item, expected_sha256, original, marker_bytes = _noncanonical_replay_fixture(
        tmp_path, f"pr10_publish_swap_{operation}_owner"
    )
    canonical = item / "agent-runs.jsonl"
    initial = original if operation == "apply" else marker_bytes
    canonical.write_bytes(initial)
    candidate = item / "agent-runs.jsonl.tmp"
    foreign = b"foreign candidate published at replace boundary\\n"
    original_write = ledger._write_exact_staging_file
    raced = False

    def write_then_swap(path: Path, expected: bytes):
        nonlocal raced
        identity = original_write(path, expected)
        if path == candidate and not raced:
            raced = True
            replacement = candidate.with_suffix(".foreign")
            replacement.write_bytes(foreign)
            os.replace(replacement, candidate)
        return identity

    monkeypatch.setattr(ledger, "_write_exact_staging_file", write_then_swap)
    monkeypatch.setattr(
        ledger, "_validate_noncanonical_marker_candidate", lambda *_args: None
    )
    command = (
        ledger._command_apply_noncanonical_history
        if operation == "apply"
        else ledger._command_rollback_noncanonical_history
    )

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        command(
            item,
            expected_sha256,
            "linked-ledger-replay",
            "2026-09-10T12:00:00Z",
            ledger.load_validator(),
            None,
        )

    assert raced is True
    assert canonical.read_bytes() == initial
'''
    text = text[:publication_start] + publication_test
    path.write_text(text, encoding="utf-8")


def patch_existing_tests() -> None:
    path = Path("tests/test_noncanonical_replay_staging_ownership.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "def test_existing_history_replay_cleans_only_same_inode_crash_link(",
        "def test_existing_history_replay_preserves_same_inode_reserved_link(",
        "history staging test name",
    )
    text = replace_once(
        text,
        '''    assert history.read_bytes() == original
    assert history.stat().st_nlink == 1
    assert not staging.exists()
''',
        '''    assert history.read_bytes() == original
    assert staging.read_bytes() == original
    assert history.stat().st_nlink == 2
    assert staging.stat().st_ino == history.stat().st_ino
''',
        "history staging ownership expectation",
    )
    path.write_text(text, encoding="utf-8")


def patch_release_notes_and_projection() -> None:
    notes_path = Path("RELEASE_NOTES.md")
    notes = notes_path.read_text(encoding="utf-8")
    notes = replace_once(
        notes,
        "Capability files must yield the same bounded byte image twice, so an in-place same-metadata rewrite is refused.",
        "Capability files exclude Windows writers before the first metadata or byte sample and must then yield the same bounded byte image twice, so an in-place same-metadata rewrite is refused.",
        "capability release note",
    )
    notes = replace_once(
        notes,
        "structured `--header`/`-H` and `--env`/`-e` carriers, colon or equals credential options, separated compound credential options,",
        "structured header aliases and `--env`/`-e` carriers, bare environment assignments, colon or equals credential options, separated compound credential options,",
        "credential-carrier release note",
    )
    notes = replace_once(
        notes,
        "Noncanonical ledger staging rereads stop after the expected bytes plus one, and failure cleanup removes only the exact single-link staging identity admitted by the operation.",
        "Noncanonical ledger staging rereads stop after the expected bytes plus one, is re-admitted immediately before replacement, and fixed recovery or history staging names are retained when pathname-only cleanup cannot prove atomic ownership.",
        "ledger publication release note",
    )
    notes_path.write_text(notes, encoding="utf-8")

    provider = Path("scripts/provider_prompt.py")
    manifest_path = Path("shared/provider-prompt-projections.v1.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["provider_prompt.py"]["sha256"] = hashlib.sha256(
        provider.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    patch_provider()
    patch_ledger()
    patch_followup_tests()
    patch_existing_tests()
    patch_release_notes_and_projection()


if __name__ == "__main__":
    main()
