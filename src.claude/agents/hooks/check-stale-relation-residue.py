#!/usr/bin/env python3
"""Stale-relation residue guard for the PreToolUse hook — AUDIT mode.

The structural enforcement backstop for law C6 of the architecture-layering
reference ("a superseding change leaves only the correct current state;
stale-relation residue is erased"). It flags an Edit/Write that ADDS a
stale-relation phrase — a phrase asserting an OBSOLETE relationship that a
completed rename / merge / deprecation / move / fix should have left no trace
of — into a LIVE-tree file.

C6's full probe (grep the change-specific OLD NAME after a superseding change)
cannot be a generic always-on hook: the hook does not know the old name. So
this guard keys on the OPERATION-INDEPENDENT residue PHRASES instead — the
fixed vocabulary C6 enumerates as residue to erase:
  - `X = deprecated alias` / `deprecated alias`
  - `now-retired ... kept as a historical example`
  - `used to be misregistered as` / `was misregistered as`
  - `(was Y)` / `(formerly Y)` / `(previously Y)` parentheticals
  - `former alias` / `former name`
  - `X -> Y alias` / `X→Y alias` (arrow + alias)
  - `this is wrong, the correct is Y` / `... is wrong, use Y`

WARN, NEVER BLOCK. The STALE-vs-LIVE discriminator is review-bound (C6 itself
says so): a LIVE relation — a real dependency, a deliberate split, a current
`X vs Y` comparison/measurement — is legitimate and uses some of the same
words. A blocking gate would false-positive on legitimate current prose, so
this guard only surfaces CANDIDATES for a human to judge, via exit 1 (never 2,
which would block) on a hit. Per Claude Code's hooks reference, exit 0's stderr
is written only to the debug log and is invisible in the transcript; any other
non-zero, non-2 exit code is a non-blocking error that shows a "<hook name>
hook error" notice plus the first stderr line in the transcript, and execution
continues exactly as it does on exit 0. Exit 1 on a hit (0 otherwise) is what
makes this guard's warning visible enough to actually measure the
false-positive rate this posture exists to measure. Promotion to a blocking
`deny` (exit 2) is a separate, reviewed step once the false-positive rate is
measured over real repos (mirrors the machine-local-path / no-trash audits).

EXEMPT targets (where a stale-relation phrase IS legitimate provenance — the
"provenance lives in version control + ONE decision/closure record" clause of
C6): decision/closure registries (`work-items/`), changelogs / release notes
(`RELEASE_NOTES`, `CHANGELOG`, `HISTORY`), archival trees (`/archive/`,
`/legacy/`, `_archive`), the local scratch area (`.scratch/`), and git
internals (`.git/`). In those, recording the superseded relation is the point.

Design note: this hook fires on the EDIT's own `tool_input` (the file path and
the content being written), NOT on session/transcript context — keying on the
immediate action keeps the guard precise, as the machine-local-path audit does.

Fail-open everywhere on internal error (return 0).
"""
from __future__ import annotations

import os
import re
import sys

# hook_common lives in the sibling scripts/ dir (shared with the grandfathered
# hooks); this hook lives in the typed hooks/ dir per the source-hygiene rule.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from hook_common import parse_envelope, read_stdin_utf8


def _emit(msg: str) -> None:
    """Write a warning to stderr as UTF-8 bytes regardless of console codepage.

    Mirrors hook_common.read_stdin_utf8 on the write side so Cyrillic / em-dash
    / arrow characters survive a Windows cp1252 console. Fail-open on any error.
    """
    try:
        sys.stderr.buffer.write(msg.encode("utf-8"))
        sys.stderr.buffer.flush()
    except Exception:
        try:
            sys.stderr.write(msg)
        except Exception:
            pass


# High-confidence stale-relation residue markers (case-insensitive). Each almost
# always asserts a SUPERSEDED relationship rather than a current fact. Kept
# deliberately narrow to bound the false-positive rate; WARN-only regardless.
_PATTERNS = [
    # "deprecated alias" (X = deprecated alias / a deprecated alias for Y)
    re.compile(r"(?i)\bdeprecated\s+alias\b"),
    # "former alias" / "former name" / "former internal name" / "former
    # identifier" / "old alias" (NOT bare "old name" — too common in live prose,
    # e.g. "ask for the old name and the new name"). "former internal name" is a
    # leaked-historical-identifier residue C6 names in its security note.
    re.compile(r"(?i)\b(?:former\s+(?:internal\s+)?(?:alias|name|identifier)|old\s+alias)\b"),
    # "now-retired ... (historical|example|kept)" — a retired thing kept as a sample
    re.compile(r"(?i)\bnow[-\s]?retired\b[^.\n]{0,80}?\b(?:historical|example|kept|sample)\b"),
    # "kept ... as a historical example" / "kept here only as a ... example"
    re.compile(r"(?i)\bkept\b[^.\n]{0,60}?\bhistorical\b[^.\n]{0,20}?\bexample\b"),
    # "misregistered as" / "misregistered-as" / "used-to-be-misregistered-as"
    # (C6 names the hyphenated form; allow hyphen OR whitespace separators).
    re.compile(r"(?i)\bmisregistered[-\s]+as\b"),
    # parenthetical "(was X)" / "(formerly X)" / "(previously X)" / "(renamed from X)"
    re.compile(r"(?i)\((?:was|formerly|previously|renamed\s+from)\s+[^)\n]{1,40}\)"),
    # arrow + alias: "X -> Y alias" / "X→Y alias" / "X => Y ... alias"
    re.compile(r"(?i)(?:->|=>|→)[^.\n]{0,40}?\balias\b"),
    # explicit correction residue: "this is wrong, (the) correct is Y" (require
    # "correct is" — a bare "...is wrong, use X" is common live instruction prose)
    re.compile(r"(?i)\bis\s+wrong\b[^.\n]{0,30}?\bcorrect\s+is\b"),
]


def find_stale_relations(text: str) -> list[str]:
    """Return deduped stale-relation residue snippets found in text."""
    hits: list[str] = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            snippet = m.group(0).strip()
            # collapse internal whitespace/newlines for a compact warning line
            snippet = re.sub(r"\s+", " ", snippet)
            if snippet:
                hits.append(snippet)
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        key = h.lower()
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


def _target_path(tool_input: dict) -> str:
    for key in ("file_path", "notebook_path", "path"):
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            return v
    return ""


# Path SEGMENTS (slash-bounded, not loose substrings) where recording a
# superseded relation IS legitimate provenance.
_EXEMPT_SEGMENTS = (
    "/.scratch/", "/.git/",
    "/work-items/",            # decision / closure / task-memory registry
    "/archive/", "/legacy/", "/_archive/",
)
# Whole filename STEMS (not substrings) that are changelog / release / history
# provenance docs — so `CHANGELOG.md` is exempt but a live `history_parser.py`
# (stem `history_parser`, not `history`) is NOT.
_EXEMPT_NAME_STEMS = {
    "release_notes", "release-notes", "changelog", "changes", "history", "news",
}


def _is_exempt_target(target: str) -> bool:
    if not target:
        return False
    norm = target.replace("\\", "/").lower()
    # Always present a leading slash so a relative path (`work-items/x`) matches
    # the same `/segment/` test as an absolute one (`/repo/work-items/x`).
    slashed = "/" + norm.lstrip("/")
    if any(seg in slashed for seg in _EXEMPT_SEGMENTS):
        return True
    base = slashed.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    if base in _EXEMPT_NAME_STEMS or stem in _EXEMPT_NAME_STEMS:
        return True
    return False


def _added_only(text: str) -> str:
    """For a unified-diff / apply_patch payload, keep only the ADDED (`+`) lines
    so the guard fires on residue being ADDED, never on residue being REMOVED (a
    `-` line — erasing residue is exactly what C6 wants, the guard must not warn
    on it). Non-diff text (Edit `new_string`, Write `content`) is returned
    unchanged — there a leading `-` is legitimate content (a markdown bullet),
    not a removal, so it must still be scanned.
    """
    is_diff = (
        "\n@@" in text or text.startswith("@@")
        or text.startswith("diff --git") or text.startswith("--- ")
        or "*** Update File" in text or "*** Add File" in text
    )
    if not is_diff:
        return text
    kept: list[str] = []
    for line in text.splitlines():
        if line.startswith("+++"):
            continue  # diff file header, not added content
        if line.startswith("+"):
            kept.append(line[1:])
        # drop "-" (removed) and " " (context/unchanged) lines: neither is what
        # THIS change adds
    return "\n".join(kept)


def _content_to_scan(tool_input: dict) -> str:
    """Join the string values being written (content, new_string, patch, ...).

    Skips the path keys (the target, not written content). Mirrors the
    machine-local-path audit so apply_patch / Edit / Write all get scanned
    without enumerating per-tool key names; each value passes through
    `_added_only` so a diff payload is scanned only on its added lines.
    """
    path_keys = {"file_path", "notebook_path", "path", "old_string"}
    parts: list[str] = []
    for key, val in tool_input.items():
        if key in path_keys:
            continue
        if isinstance(val, str):
            parts.append(_added_only(val))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    parts.append(_added_only(item))
    return "\n".join(parts)


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0  # nothing to inspect; allow

    target = _target_path(tool_input)
    if _is_exempt_target(target):
        return 0  # provenance / changelog / archive / scratch / git -> allow

    text = _content_to_scan(tool_input)
    if not text:
        return 0

    hits = find_stale_relations(text)
    if hits:
        shown = "; ".join(hits[:5])
        _emit(
            "[stale-relation-residue AUDIT] candidate stale-relation residue in write to "
            f"{target or '<unknown target>'}: {shown}\n"
            "  (C6: a superseding change must leave ONLY the correct current state — "
            "erase residue of the obsolete relation. Discriminator is review-bound: "
            "if this asserts a STALE relationship (a done rename / gone alias / fixed "
            "misregistration) erase it; if it asserts a LIVE fact (a real dependency, a "
            "current comparison) keep it. AUDIT mode -- allowing this write.)\n"
        )
        # Exit 1 (never 2): a non-blocking "<hook name> hook error" transcript
        # notice with the first stderr line, so the warning is actually visible
        # -- exit 0 here is invisible outside --debug.
        return 1
    # AUDIT mode: always allow the write. (Promotion to a blocking deny -- exit
    # 2 -- is a separate reviewed step once the false-positive rate is measured.)
    return 0


if __name__ == "__main__":
    sys.exit(main())
