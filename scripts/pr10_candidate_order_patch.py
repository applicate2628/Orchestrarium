#!/usr/bin/env python3
"""One-shot patch that materializes the fixed ledger candidate only when needed."""

from pathlib import Path


PATH = Path("scripts/agent-run-ledger.py")


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    old = '''    try:
        staging_identity = _write_exact_staging_file(candidate, marker_bytes)
        _validate_noncanonical_marker_candidate(item, candidate, validator)
        _publish_noncanonical_history_blob(
            item, history_path, expected_sha256, original
        )
        if inject_failure == "post-history-publish":
            print("FAIL: injected post-history-publish interruption", file=sys.stderr)
            return False, history_path
        if inject_failure == "pre-ledger-replace":
            print("FAIL: injected pre-ledger-replace interruption", file=sys.stderr)
            return False, history_path
'''
    new = '''    try:
        # The history blob is digest-bound and nonauthorizing. Publish that inert
        # prerequisite before materializing the fixed-name ledger candidate, so a
        # post-history interruption leaves no candidate path to recover or clean.
        _publish_noncanonical_history_blob(
            item, history_path, expected_sha256, original
        )
        if inject_failure == "post-history-publish":
            print("FAIL: injected post-history-publish interruption", file=sys.stderr)
            return False, history_path
        staging_identity = _write_exact_staging_file(candidate, marker_bytes)
        _validate_noncanonical_marker_candidate(item, candidate, validator)
        if inject_failure == "pre-ledger-replace":
            print("FAIL: injected pre-ledger-replace interruption", file=sys.stderr)
            return False, history_path
'''
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"apply candidate ordering: expected one match, found {count}")
    PATH.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
