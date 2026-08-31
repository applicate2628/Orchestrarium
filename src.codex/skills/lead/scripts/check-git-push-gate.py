#!/usr/bin/env python3
"""Git-push publication gate (PreToolUse, BLOCKING) — structural backstop for
the human-review-before-push rule.

WHAT THIS DENIES: a command that confidently runs `git push` when neither the
genuine user's per-turn approval marker nor one fresh gate-owned canonical
range scan authorizes the exact pending push. The gate derives the only scanner
producer as one held gate plus gate-relative three-module closure (`hook_common.py`, the
machine-path classifier, and `check-publication-safety.py`), snapshots and
executes those bytes directly with its current trusted interpreter, and binds
the exactly correlated typed result to remote, destination, source, current
HEAD, and receipt tip. Scanner-
looking transcript calls and outputs are untrusted diagnostics and never mint
authorization.

WHY: `git push` is the highest-stakes irreversible action the pack governs —
"Human review before git push ... must include a leak-check of staged changes"
was prose-only while lower-stakes edit/stop moments got blocking hooks. This
hook closes that asymmetry.

HISTORICAL DEFECT CONTEXT FOR THE NOW-DIAGNOSTIC TRANSCRIPT PARSER (2026-07-26,
`work-items/backlog/2026-07-25-push-gate-blind-to-scan-result/brief.md` §11.5
D1-D3/S6, admitted from `work-items/bugs/2026-07-25-push-gate-keys-on-scan-
invocation-not-result.md`, severity high). Invocation alone was satisfied by a
scan that ran and immediately exited — including a scan that examined NOTHING.
`check-publication-safety.sh` builds its file list from `git diff --cached` and
exits 0 when that set is EMPTY. After a commit the staged index equals `HEAD`,
so the ordinary commit-then-push flow handed the invocation-only branch a scan
that passed having examined nothing, and it opened the gate anyway — reproduced
live in this repository. "Passed" is therefore DEFINED here: a scan counts only
when its own tool-output text reports a clean result AND a non-empty examined
set, in `tracked` mode specifically (a `--path` fixture-testing invocation must
not count — its output is tagged `path`, not `tracked`, precisely so it cannot
launder as gate evidence).

CORRELATION, NOT HAYSTACK-JOINING (2026-07-26, adversarial-gate correction —
this is the load-bearing part of the fix, not a footnote). A first cut of this
hardening built the call-evidence and the result-evidence as two INDEPENDENT
strings, each `\n`-joined across every entry in the turn, then checked whether
each string matched its own regex ANYWHERE. That is not a correlation, and an
adversarial review proved it live against the shipped hook: an empty-index
scan (correctly denying on its own) plus an UNRELATED `Read` of a file that
happened to quote the scanner's own clean-result text (a test fixture in this
very repository does) made the two independent haystacks both match — ALLOW,
with no real clean scan anywhere in the turn. The fix replaces both haystacks
with per-call `(call_id, text)` pairs keyed by the provider's own
call-identity field — Claude's `tool_use.id` / `tool_result.tool_use_id`,
Codex's `function_call` / `function_call_output` `call_id` (both verified
against real transcripts on this installation, not assumed). The RESULT side
uses `hook_common.extract_tool_outputs_with_ids`, unchanged since this first
hardening. The CALL side originally used `hook_common.
extract_model_tool_calls_with_ids` (a flattened `"<tool name> <full JSON
input>"` blob per call, fine for a plain-substring regex); the SECOND
hardening below (MENTION-vs-EXECUTION) replaced it with `hook_common.
extract_model_shell_command_occurrences`, which returns the typed RAW shell command
string instead, because execution-vs-mention detection needs an actual
parseable command, not a flattened blob. Only opens the gate when a result
CARRYING THE SAME ID as a scan-matching call also matches the clean-result
regex. A foreign tool's output can no longer satisfy this no matter what
text it happens to contain, because it carries a different id (or, for the
top-level Codex fallback shape with no id at all, no id — which is skipped,
i.e. can never correlate, the
fail-closed direction).

COLLISION REJECTION, NOT RESOLUTION (2026-07-26, second correlation finding on
this same mechanism, external adversarial-gate review). Correlating by id
(the fix above) is only sound if an id actually identifies ONE call and ONE
result. The code checked SET MEMBERSHIP only ("is this id present"), never
UNIQUENESS ("does exactly one call/result carry it") — reproduced live with
executable fixtures for both provider shapes: a real scan call and an
UNRELATED call sharing one literal id (e.g. `"duplicate"`), each with its own
matching tool output under that same shared id, still ALLOWed even though no
single call-and-its-own-result pair ever reported a genuine clean scan. A
colliding id cannot be resolved by picking a side (first-seen, scan-matching,
longest match, anything) — that is a guess dressed up as a correlation, and
this hook's whole reason to exist is to not guess about publication safety.
The only safe reading of an ambiguous transcript is to exclude the colliding
id from evidence on BOTH sides independently: an id claimed by more than one
model tool CALL can no longer identify "the" scan invocation, and an id
claimed by more than one tool OUTPUT can no longer identify "the" scan's own
answer, regardless of which of the colliding occurrences happens to look
legitimate. This is the same fail-closed posture as the missing-id case
below (an uncorrelatable call/result was always skipped, never credited) —
collision is just the mirror case: TOO MANY claimants instead of none, and
both resolve to "exclude, do not guess."

A same-id result that appears BEFORE the call it is supposedly answering, in
transcript order, is the mirror defect of collision and is closed by the same
change: correlation is retroactive within a turn (a call happens, then its
own result), never the reverse. `after_user_entries` is already forward
chronological order (`last_genuine_user_message` reverses it back into
original order before returning), so each call/result's own entry INDEX
doubles as its position in the turn; the fix requires a credited result's
index to be strictly greater than its call's index. A call and its own real
answering result can never land in the same transcript entry in either
provider shape (a `tool_use`/`function_call` entry and its answering
`tool_result`/`function_call_output` entry are always distinct records — see
extract_model_shell_command_occurrences and extract_tool_outputs_with_ids), so
this ordering check never rejects a genuine pair, only a same-id result that
could not possibly be answering the call it is being credited against.

CALL-SIDE UNIQUENESS COVERS EVERY ID-CARRYING CALL, NOT ONLY SHELL CALLS
(2026-07-26, third correlation finding on this same mechanism, external
adversarial-gate review — `work-items/bugs/2026-07-26-non-shell-call-can-
claim-a-scan-id-and-open-the-push-gate.md`). The COLLISION REJECTION fix
above computed call-side uniqueness (`call_positions`) by walking
`extract_model_shell_command_occurrences` alone, because that was already the
only extractor in scope for scan CALL detection. That conflated two
separable concerns: what makes an id AMBIGUOUS is any second claimant
regardless of tool type, while what makes a call a SCAN invocation is its
command text specifically. A non-shell call (a `Read`, a Codex call whose
arguments carry no `command` field, anything without a parseable shell
command) sharing a scan call's id was therefore invisible to the shell-only
uniqueness map, not merely uncounted — reproduced live: a scan call under id
`X` whose OWN answering result never arrives (an interrupted call), plus an
unrelated non-shell call sharing id `X`, plus one clean-shaped output under
`X` (necessarily the foreign call's own real answer, since the scan's own
answer is absent) still ALLOWed, because the shell-only map counted exactly
one claimant for `X` and the result-side collision check also saw exactly
one output for `X` — the ambiguity existed only on the call side, where the
shell-only walk could not see it. This is why the "a call-side collision
must produce a result-side collision" transitive argument (informally relied
on when the COLLISION REJECTION fix above shipped, and disclosed there as
`ASSUMPTION (UNVERIFIED)`) does not hold in general: it silently assumed the
scan's own answer always arrives under the scan's own id, which is exactly
the assumption an interrupted call violates. The fix separates the two
walks: call-side uniqueness now walks `extract_model_tool_calls_with_ids` —
every id-carrying call, regardless of tool type — while scan CALL detection
stays on `extract_model_shell_command_occurrences`, unchanged, because only a
shell call can ever execute the scanner. A non-shell call can now never hide
a second claimant on a scan id.

RESULT MATCH IS WHOLE-LINE, NOT SUBSTRING (2026-07-26, CRITICAL hardening —
`work-items/bugs/2026-07-26-push-gate-credits-a-blocking-scan-whose-grep-
echoes-the-clean-line.md`, found by `$security-reviewer` (fable), reproduced
end to end by `$lead`). `SCAN_CLEAN_TRACKED_REGEX` used to be a plain
substring search over a correlated result's whole text. That is exploitable
even with correlation, uniqueness, and ordering all intact, because the
scanner's OWN honest report of a BLOCKED scan can itself contain the
clean-result string as a SUBSTRING: `check-publication-safety.sh`'s
`nonpath_cmd` prints a matching `git grep` line straight to stdout (correct
behavior for a human reader — see that script's own `nonpath_cmd`/`echo
"$scanner_line"` handling), and `git grep` always prefixes `path:lineno:` to
the line it found. A single staged line such as `token = "publication-
safety: clean (tracked, examined 9 files)"` trips the `[Tt]oken` leak
pattern (a real, correct BLOCK — exit 1) while ALSO embedding the exact
clean-receipt text as a substring of that one grep report line. The
unanchored regex matched inside it regardless, and this hook never reads the
scan's own exit status (see the module's WHAT THIS STILL DOES NOT COVER
section on why that channel is unavailable to it) — so the scanner's honest
account of its own failure became the very string this hook accepted as
proof of success. None of the CORRELATION / COLLISION REJECTION / ORDERING /
CALL-SIDE UNIQUENESS hardenings above touch this: they all police WHO
produced the text (the right call, a unique id, the right order), never
WHAT the scan concluded — every one of them can hold exactly as designed
while this hole stays open, because the credited text is genuinely the
scan's own output, genuinely under its own unique id, genuinely in the
right order. The fix anchors `SCAN_CLEAN_TRACKED_REGEX` to a WHOLE LINE
(`^...$` under `re.MULTILINE`) — see that pattern's own comment block for
the full three-condition contract and why `git grep`'s mandatory
`path:lineno:` prefix means this costs the genuine receipt nothing. A
belt-and-braces companion, `SCAN_FAILURE_MARKER_REGEX`, additionally
excludes any correlated result that ALSO carries the scanner's own
self-reported failure line, so a scan cannot be credited as both blocked and
clean from the same output no matter how the whole-line anchor is
approached from some future angle.

A CRASH WHILE DECIDING FALLS THROUGH TO DENY, NEVER TO ALLOW (2026-07-26,
HIGH-severity hardening — `work-items/bugs/2026-07-26-push-gate-new-paths-
fail-open-because-the-wrapper-discards-the-exit-code.md`, found by
`$security-reviewer` (fable)). Before this hardening, `main()`'s only
`try/except` covered `parse_envelope` alone; every step from tool-input
extraction through the scan-evidence correlation loop ran unguarded. An
uncaught exception printed no deny payload, making a crash indistinguishable
from a legitimate allow to the host. The Python owner now moves every step from
tool-input extraction through the scan-evidence loop into `evaluate_push`,
called from `main()` inside one `try/except Exception` that treats a raised
exception as "fall through to the deny payload", never as "return 0
(allow)" — see `evaluate_push`'s own docstring for the exact mechanics and
why the five pre-existing deliberate fail-open returns inside it are
unaffected (they are ordinary returns, not exceptions).

RANGE MODE AND CLOSED COMMAND GRAMMAR. Tracked-mode output covers the staged
set; a range receipt covers commits not already present on the named remote
and carries `remote`/`dst`/`tip`. Both modes share call-id correlation,
collision rejection, ordering, execution-status, whole-line, non-empty, and
failure-marker checks. Both also require the same immutable command result to
admit exactly one solitary direct push: no environment prefix, Git-global
option, repository redirect, compound sibling, pipeline, unknown push option,
or extra refspec. Range mode additionally requires its declared `remote` and
`dst` to equal the admitted command binding.

The generic grammar deliberately stops short of the strict PR route's
source/tip, repository identity, remote freshness, and provider-oracle
bindings. Those remain explicit residuals of generic receipts, not permission
for command-visible redirects or payload-expanding options.

HONESTY RULE — THIS IS A BACKSTOP, NOT A GUARANTEE. The generic route under-detects by design.
It cannot see inside an opaque wrapper file such as `bash sync.sh`, nor can it
resolve dynamically supplied `eval` or expansion text whose `git push` bytes
are absent from the envelope. Exact parser-owned child payloads such as a
literal `bash -c` or `eval` argument remain visible, but arbitrary adjacent
argument text is not treated as a separately executed command. A PLAIN
MULTI-LINE command is NOT one of these gaps
and IS correctly modelled: `cd /repo` NEWLINE `git add -A` NEWLINE `git
commit -m x` NEWLINE `git push origin main`, all as one Bash tool call, is
seen as four parser-owned command records and the final push is retained.
What remains genuinely unmodelled is execution supplied from
outside the literal envelope — wrapper-file contents, `eval "$cmd"`, or an
expanded variable whose value is not present — because the hook sees command
text, never the contents or runtime values that text later loads. If the transcript is unavailable,
a detected non-dry push denies,
and a model can still fake the scan-evidence signal — it must
now fake a matching tool CALL and its OWN correlated tool OUTPUT (harder than
faking invocation alone, or than faking two uncorrelated strings), but neither
was ever cryptographically bound to what actually gets pushed (no receipt: see
`work-items/decisions/2026-07-26-publication-clean-receipt-contract.md`,
dropped, for why a stronger content-bound design was rejected). An ALLOW here
is also SILENT — the hook prints nothing on the approval path, only on deny —
so this docstring is the honest record for a maintainer, and the deny message
below is the honest record for an operator; neither claims "the push is safe",
only that a scan ran, in this turn, and its OWN output reported clean over
something. The binding rule remains the governance text: human review +
publication-safety leak-check before any push. Do not represent this hook as
enforcing that rule.

Decision algorithm (fail-open on envelope-parse failure, step 1, and on the
ordinary no-decision returns for subagents, missing commands, non-pushes, and
all-dry-run calls; an uncaught exception in the decision path falls through
to the DENY payload rather
than silently allowing — 2026-07-26 hardening, see `evaluate_push`'s
docstring and the module docstring's "A CRASH WHILE DECIDING" note above):

  1. Read the PreToolUse JSON envelope from stdin.
  2. If the envelope carries `agent_id` (a subagent context) → exit 0 (allow;
     mirrors check-bugfix-discipline.py — a subagent cannot inject the
     user-side override into the main transcript, so gating it here is an
     un-overridable false positive. Governance still forbids delegating a
     push to a subagent to dodge review).
  3. If `tool_input.command` is absent or empty → exit 0 (not a shell command).
  4. Parse once into the immutable shell result shared by push and scan
     consumers. Complete proven POSIX heredoc and PowerShell here-string
     bodies are data; uncertain regions preserve literal push candidates,
     while prefixes, option roles, operands, repository context, and command
     boundaries remain explicit provenance. No detected push or candidate → exit 0.
  5. Every exact direct push proving a standalone positive long `--dry-run`,
     with no negation, ambiguous option role, or conservative candidate → exit 0.
  6. If `transcript_path` is missing, unreadable, invalid, or exceeds the
     bounded full-history limits → deny with `PRG-TRANSCRIPT-UNAVAILABLE`.
  7. If the LAST GENUINE USER MESSAGE contains `[approve-publication]` AND
     that message is no longer than MARKER_MAX_MESSAGE_LENGTH characters →
     exit 0. The marker is honored ONLY from the user's own text — never from
     assistant prose, tool calls, or tool output — because prior provider or
     file content quoting the marker must not approve a publication. The
     length bound (2026-07-26 hardening; see MARKER_MAX_MESSAGE_LENGTH's own
     comment for the full contract decision and measurements) exists because
     the deny reason at step 10 embeds this same marker verbatim, so an
     operator who copies that reason back into chat reproduces the identical
     marker; a message shaped like a copied multi-paragraph deny block does
     not count as an approval here.
  8. Derive the latest exact PR grant/revoke/malformed state from the complete
     bounded readable transcript. A malformed reserved signal denies. An
     active grant runs only the strict PR route: fresh GitHub/Git binding and
     protection checks plus one fresh unused non-empty range receipt bound to
     remote, full destination, and local HEAD tip. Every active-route failure
     denies without generic fallback.
  9. If no active PR grant is present and the current turn (entries after the last genuine user message) shows
     a publication-safety scan invocation among the model's own tool CALLS,
     under an id UNIQUE among this turn's calls (see COLLISION REJECTION note
     below), WHOSE OWN correlated tool OUTPUT (same call id — see the
     CORRELATION note above), itself under an id unique among this turn's
     outputs and recorded STRICTLY AFTER the call it answers, reports EITHER
     (i) a clean, non-empty, `tracked`-mode result ON A WHOLE LINE BY ITSELF
     (see the RESULT MATCH IS WHOLE-LINE note above and `SCAN_CLEAN_TRACKED_
     REGEX`'s own comment), OR (ii) a clean, non-empty, `range`-mode result
     ON A WHOLE LINE BY ITSELF whose declared `remote` and `dst` equal the
     admitted push binding — AND the command is one solitary direct push in
     the closed generic grammar, AND in EITHER case does NOT also carry the
     scanner's own self-reported failure line
     (`SCAN_FAILURE_MARKER_REGEX`), AND the last genuine user message
     contains an explicit push-instruction signal (`push`, `запушь`,
     `залей`, ...) → exit 0.
  10. Otherwise — including when the decision path raises an uncaught exception (see
     the "A CRASH WHILE DECIDING" note above and `evaluate_push`'s own
     docstring; 2026-07-26 hardening) — emit a structured `permissionDecision:
     "deny"` payload with exact compliance instructions. Always exit 0 (the
     decision is carried by the stdout payload, not the exit code).

WHAT THE GENERIC NON-PR ROUTE STILL DOES NOT COVER (disclosed, not silently assumed away):
  - SHORT QUOTES OF THE BARE MARKER (2026-07-26, `$security-engineer`
    contract decision on `work-items/bugs/2026-07-26-the-deny-message-
    teaches-the-marker-that-opens-the-gate.md`). The MARKER_MAX_MESSAGE_LENGTH
    bound (see step 7 and that constant's own comment) closes a long, copied
    deny-block from opening the gate, but a SHORT quote of or question about
    just the marker itself ("what does `[approve-publication]` mean?") is
    still indistinguishable, by length or content, from a genuine short
    approval — no fixed-string match at this layer can tell them apart with
    certainty, because the marker is disclosed text a human can always
    retype into either shape. Fully closing this needs a per-event nonce or
    an out-of-band confirmation channel; both are larger contract changes
    than this bounded fix makes.
  - RECEIPTS DO NOT BIND REPOSITORY / WORKTREE IDENTITY. Command-local
    repository selectors (`GIT_DIR`, `GIT_WORK_TREE`, `-C`, `--git-dir`,
    `--work-tree`, `--namespace`, and push `--repo`) are retained and denied
    generic credit, but the transcript still does not prove that the scanner
    and later ambient push ran in the same repository/worktree. Range mode
    binds remote name plus destination; tracked mode carries neither.
  - Generic range mode uses a closed invocation grammar but does not bind the
    refspec source or current tip, repository/worktree identity, scanner
    authenticity, or remote freshness. Stronger bindings remain owned by the
    strict PR route or require a future receipt contract.
  - A model can still forge the evidence: DELIBERATELY type a literal fake
    clean-result line into a real command (`echo "publication-safety: clean
    (tracked, examined 999 files)"`), keyed to a real call id. This remains
    open and is the genuine adversarial-actor-with-a-shell case. It is
    DISTINCT from the two accident-class vectors closed by the parser-owned
    execution-vs-mention projection plus its compound-command solitary rule;
    both of those involved a REAL
    call producing REAL output with no forged literal anywhere in the
    command text: an innocent `grep`/`ls`/`Test-Path` that happened to NAME
    the scanner as a target (never ran it), and a real, correctly-zero-file
    scan chained with an unrelated sibling command whose own real output
    happened to satisfy the clean-result regex. Confusing these two classes
    was itself a defect in an earlier revision of this docstring (an
    adversarial-gate finding, 2026-07-26): it described the mention/
    compound-command paths as forgery when neither forges anything — real
    call, real output, real scan — which is exactly the momentum-and-
    accident class this backstop is meant to cover, not the exception to
    it. This bullet names the vectors that were found and closed, not an
    exhaustive claim that every possible accident-class vector is covered.
  - This hook does not read commit MESSAGES at all, and neither does the
    scanner it keys on (`2026-07-26-commit-messages-are-never-scanned-under-
    any-posture`, filed, not fixed here — sequenced after this item as
    `2026-07-26-publication-scanner-attestation-object`).
  - Current-turn evidence is read through the shared byte-bounded owner. A
    non-success snapshot cannot credit the marker or correlated scan route;
    strict complete history remains the separate source for PR grant state.
"""
from __future__ import annotations

import base64
import json
import hashlib
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote, unquote_to_bytes, urlsplit

from hook_common import (
    CURRENT_TURN_BYTE_CAP,
    HISTORY_STATUS_FOUND,
    HISTORY_STATUS_LIMIT,
    NO_OBSERVED_FAILURE,
    STATUS_FOUND,
    extract_model_shell_command_occurrences,
    extract_model_tool_calls_with_ids,
    extract_tool_outputs_with_ids,
    extract_user_typed_text,
    is_user_message,
    parse_envelope,
    read_stdin_utf8,
    read_transcript_history,
    scan_current_turn_boundary,
)


from git_push_gate_preflight import (
    PreflightResult,
    validate_preflight_result,
    build_preflight_from_stdin,
    ShellParseResult,
    PrRouteDenied,
    resolve_command_dialect,
    parse_transcript_command,
    project_scan_range_binding,
)


# Per-turn override marker — honored ONLY from the last genuine user message.
# User-side only by design: assistant prose can be steered by injected content
# (see the consultant continuation-prompt untrusted-data rule), so unlike
# [skip-bugfix-discipline] this marker never counts from the model's own reply.

PR_GRANT_PREFIX = "[approve-pr-publication:v1 pr="
PR_GRANT_NUMBER_REGEX = re.compile(r"^[1-9][0-9]*$")
PR_GRANT_MARKDOWN_REGEX = re.compile(
    r"^\[(?P<label>[^\]]+)\]\((?P<destination>[^)]+)\)$"
)
PR_URL_REGEX = re.compile(
    r"^(?P<url>https://github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?)/"
    r"(?P<repo>[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?)/pull/"
    r"(?P<number>[1-9][0-9]*))$"
)
PR_REVOKE_MARKER = "[revoke-pr-publication:v1]"
PR_RESERVED_PREFIXES = ("[approve-pr-publication:", "[revoke-pr-publication:")
TRANSCRIPT_HISTORY_BYTE_CAP = 32 * 1024 * 1024
TRANSCRIPT_HISTORY_RECORD_CAP = 50_000
TRANSCRIPT_HISTORY_LINE_BYTE_CAP = 2 * 1024 * 1024
PROCESS_OUTPUT_BYTE_CAP = 256 * 1024
PROCESS_TIMEOUT_SECONDS = 8.0
ORACLE_TIMEOUT_SECONDS = 45.0
SCAN_SNAPSHOT_BYTE_CAP = 1024 * 1024
SCAN_OUTPUT_BYTE_CAP = 256 * 1024
SCAN_TIMEOUT_SECONDS = 300.0
SCAN_SETTLEMENT_ATTEMPT_SECONDS = 3.0
SCAN_SETTLEMENT_MAX_ENTRIES = 2
REMOTE_NAME_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
PR_HEAD_REF_REGEX = re.compile(r"^[A-Za-z0-9._/-]{1,255}$", re.ASCII)
REPO_COMPONENT_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
NODE_ID_REGEX = re.compile(r"^[A-Za-z0-9_=-]{1,256}$")


@dataclass(frozen=True)
class GitObjectFormat:
    name: str
    hex_length: int
    oid_re: re.Pattern[str]

    def matches(self, value: str) -> bool:
        return self.oid_re.fullmatch(value) is not None


_SHA1_OBJECT_FORMAT = GitObjectFormat(
    "sha1", 40, re.compile(r"[0-9a-fA-F]{40}")
)
_SHA256_OBJECT_FORMAT = GitObjectFormat(
    "sha256", 64, re.compile(r"[0-9a-fA-F]{64}")
)
_SUPPORTED_OBJECT_FORMATS = {
    value.name: value for value in (_SHA1_OBJECT_FORMAT, _SHA256_OBJECT_FORMAT)
}
_SUPPORTED_OID_REGEX = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_LOWERCASE_OID_PATTERN = r"(?:[0-9a-f]{40}|[0-9a-f]{64})"
SCAN_DENIAL_REASONS = {
    "PGG-SCAN-PROVENANCE": "The canonical gate-owned range scanner could not be established.",
    "PRG-SCAN-PROVENANCE": "The canonical gate-owned range scanner could not be established.",
    "PGG-SCAN-IDENTITY-DRIFT": "The trusted scanner boundary changed during evaluation.",
    "PRG-SCAN-IDENTITY-DRIFT": "The trusted scanner boundary changed during evaluation.",
    "PGG-SCAN-EXECUTION": "The canonical range scanner did not complete and reap within its fixed bounds.",
    "PRG-SCAN-EXECUTION": "The canonical range scanner did not complete and reap within its fixed bounds.",
    "PGG-SCAN-FINDING": "The canonical range scanner reported a redacted publication-safety finding.",
    "PRG-SCAN-FINDING": "The canonical range scanner reported a redacted publication-safety finding.",
    "PGG-SCAN-REFUSAL": "The canonical range scanner returned a typed fail-closed refusal.",
    "PRG-SCAN-REFUSAL": "The canonical range scanner returned a typed fail-closed refusal.",
    "PGG-SCAN-CORRELATION": "The trusted scanner result did not match its exact pending invocation.",
    "PRG-SCAN-CORRELATION": "The trusted scanner result did not match its exact pending invocation.",
}


def _detect_git_object_format(
    repository_workdir: str,
    git_exe: str,
    failure_id: str,
    *,
    deadline: float | None = None,
) -> GitObjectFormat:
    active_deadline = deadline or (time.monotonic() + ORACLE_TIMEOUT_SECONDS)
    _, output = _run_text(
        [git_exe, "rev-parse", "--show-object-format"],
        active_deadline,
        failure_id,
        repository_workdir,
    )
    rows = output.splitlines()
    if len(rows) != 1:
        raise PrRouteDenied(failure_id)
    object_format = _SUPPORTED_OBJECT_FORMATS.get(rows[0])
    if object_format is None:
        raise PrRouteDenied(failure_id)
    return object_format


class ActivePrGrant(NamedTuple):
    url: str
    owner: str
    repo: str
    number: int


class ProcessResult(NamedTuple):
    returncode: int
    stdout: bytes
    stderr: bytes


class PushScanBinding(NamedTuple):
    route: str
    remote: str
    destination: str
    source_oid: str
    head_oid: str


class TrustedSourceIdentity(NamedTuple):
    expected_path: str
    parent_generation: tuple[int, ...]
    file_identity: tuple[int, ...]
    link_count: int
    size: int
    sha256: str


class InterpreterIdentity(NamedTuple):
    absolute_resolved_path: str
    file_identity: tuple[int, ...]


TrustedInterpreterIdentity = InterpreterIdentity


@dataclass(frozen=True)
class SourceNode:
    role: str
    expected_path: str
    file_identity: tuple[int, ...]
    link_count: int
    size: int
    sha256: str
    source: bytes


@dataclass(frozen=True)
class SourceLayout:
    name: str
    gate_suffix: tuple[str, ...]
    trust_root_up: int


SOURCE_LAYOUTS = (
    SourceLayout("universal", ("scripts", "universal-hooks", "scripts", "check-git-push-gate.py"), 1),
    SourceLayout("generated-codex", ("src.codex", "skills", "lead", "scripts", "check-git-push-gate.py"), 1),
    SourceLayout("generated-claude", ("src.claude", "agents", "scripts", "check-git-push-gate.py"), 1),
    SourceLayout("global", (".codex", "skills", "lead", "scripts", "check-git-push-gate.py"), 1),
    SourceLayout("project-local", (".agents", "skills", "lead", "scripts", "check-git-push-gate.py"), 1),
)


@dataclass(frozen=True)
class PathComponentIdentity:
    root_relative_name: str
    kind: str
    identity: tuple[int, ...]


@dataclass(frozen=True)
class CanonicalSourceClosure:
    layout: SourceLayout
    trust_root: PathComponentIdentity
    components: tuple[PathComponentIdentity, ...]
    nodes: tuple[SourceNode, ...]
    digest: str
    gate_identity: tuple[int, ...]
    bootstrap_digest: str
    interpreter_identity: InterpreterIdentity


class PendingState(str, Enum):
    PREPARED = "prepared"
    CHILD_OWNED = "child-owned"
    SETTLING = "settling"
    SETTLED = "settled"
    CORRELATED = "correlated"
    CONSUMED = "consumed"
    FAILED = "failed"


@dataclass(eq=False)
class PendingScanInvocation:
    invocation_id: str
    attempt_id: str
    binding: PushScanBinding
    closure: CanonicalSourceClosure | None
    interpreter_identity: InterpreterIdentity
    exact_argv: tuple[str, ...]
    result_slot: object
    created_tick: float = field(default_factory=time.monotonic)
    authorization_deadline: float | None = None
    state: PendingState = field(init=False, default=PendingState.PREPARED)
    child_identity: int | None = field(init=False, default=None)
    supervisor: object | None = field(init=False, default=None)
    settlement: object | None = field(init=False, default=None)
    closure_fresh_tick: float | None = field(init=False, default=None)
    binding_fresh_tick: float | None = field(init=False, default=None)
    correlation_id: str | None = field(init=False, default=None)
    consumption_id: str | None = field(init=False, default=None)
    _transition_lock: threading.Lock = field(init=False, repr=False, default_factory=threading.Lock)
    _identity_sealed: bool = field(init=False, repr=False, default=False)

    def __setattr__(self, name, value):
        if getattr(self, "_identity_sealed", False) and name in {
            "invocation_id", "attempt_id", "binding", "closure",
            "interpreter_identity", "exact_argv", "result_slot",
            "created_tick", "authorization_deadline",
        }:
            raise AttributeError("pending invocation identity is immutable")
        object.__setattr__(self, name, value)

    def __post_init__(self) -> None:
        if self.authorization_deadline is None:
            self.authorization_deadline = (
                self.created_tick + SCAN_TIMEOUT_SECONDS
                + SCAN_SETTLEMENT_ATTEMPT_SECONDS * SCAN_SETTLEMENT_MAX_ENTRIES
            )
        self._identity_sealed = True

    def __copy__(self):
        raise TypeError("pending invocation is non-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("pending invocation is non-copyable")

    def correlate_and_consume_once(
        self,
        launched: "LaunchedScanInvocation",
        records: tuple["TrustedExecutionRecord", ...],
        closure_after: CanonicalSourceClosure,
        interpreter_after: InterpreterIdentity,
        binding_after: PushScanBinding,
        freshness_tick: float,
    ) -> "ConsumedAuthoritativeEvidence":
        prefix = "PGG" if self.binding.route == "generic" else "PRG"
        with self._transition_lock:
            if self.state is PendingState.CONSUMED:
                raise PrRouteDenied(prefix + "-RECEIPT-USED")
            if (
                self.state is not PendingState.SETTLED
                or time.monotonic() > float(self.authorization_deadline)
                or len(records) != 1
            ):
                self.state = PendingState.FAILED
                raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
            execution = records[0]
            supervisor = launched.supervisor_token
            settlement = self.settlement
            certificate = (
                settlement.certificate if isinstance(settlement, GateSettlement) else None
            )
            actual_pid = getattr(getattr(supervisor, "process", None), "pid", None)
            if (
                launched.pending is not self
                or launched.invocation_id != self.invocation_id
                or launched.attempt_id != self.attempt_id
                or launched.binding != self.binding
                or launched.exact_argv != self.exact_argv
                or launched.result_slot is not self.result_slot
                or execution.pending is not self
                or execution.launched is not launched
                or execution.result_slot is not self.result_slot
                or supervisor is not self.supervisor
                or not isinstance(supervisor, ChildSupervisor)
                or launched.child_handle != self.child_identity
                or actual_pid != self.child_identity
                or supervisor.child_identity != self.child_identity
                or execution.settlement is not settlement
                or not isinstance(settlement, GateSettlement)
                or not settlement.complete
                or not settlement.execution_eligible
                or certificate is None
                or certificate.supervisor_id != supervisor.supervisor_id
                or certificate.child_identity != self.child_identity
                or closure_after != self.closure
                or execution.closure_after != closure_after
                or interpreter_after != self.interpreter_identity
                or execution.interpreter_identity_after != interpreter_after
                or execution.provenance_verdict != "trusted"
                or binding_after != self.binding
                or freshness_tick <= certificate.verified_at_monotonic_tick
            ):
                self.state = PendingState.FAILED
                raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
            self.closure_fresh_tick = freshness_tick
            self.binding_fresh_tick = freshness_tick
            self.correlation_id = secrets.token_hex(16)
            self.state = PendingState.CORRELATED
            try:
                if not execution.bounded_completion:
                    raise PrRouteDenied(prefix + "-SCAN-EXECUTION")
                combined = execution.stdout + execution.stderr
                try:
                    text = combined.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    raise PrRouteDenied(prefix + "-SCAN-EXECUTION") from None
                parsed = parse_publication_safety_observation(text)
                if execution.exit_code == 1:
                    raise PrRouteDenied(prefix + "-SCAN-FINDING")
                if execution.exit_code == 2:
                    raise PrRouteDenied(prefix + "-SCAN-REFUSAL")
                if execution.exit_code != 0:
                    raise PrRouteDenied(prefix + "-SCAN-EXECUTION")
                if parsed.kind != "valid-v3" or parsed.receipt is None:
                    mismatch = "PGG-RANGE-RECEIPT-VERSION" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
                    raise PrRouteDenied(mismatch)
                receipt = parsed.receipt
                if (receipt.remote, receipt.destination) != (
                    self.binding.remote, self.binding.destination
                ):
                    mismatch = "PGG-RANGE-BINDING" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
                    raise PrRouteDenied(mismatch)
                if (
                    receipt.source != self.binding.source_oid
                    or receipt.tip != self.binding.source_oid
                    or self.binding.source_oid != self.binding.head_oid
                ):
                    mismatch = "PGG-RANGE-TIP-BINDING" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
                    raise PrRouteDenied(mismatch)
            except BaseException:
                self.state = PendingState.FAILED
                raise
            self.consumption_id = secrets.token_hex(16)
            self.state = PendingState.CONSUMED
            return ConsumedAuthoritativeEvidence(
                self.invocation_id, self.binding, parsed, self.consumption_id, execution
            )


class LaunchedScanInvocation(NamedTuple):
    pending: PendingScanInvocation
    child_handle: int
    supervisor_token: object
    invocation_id: str
    attempt_id: str
    binding: PushScanBinding
    exact_argv: tuple[str, ...]
    result_slot: object


@dataclass(frozen=True)
class TrustedExecutionRecord:
    pending: PendingScanInvocation
    launched: LaunchedScanInvocation
    result_slot: object
    bounded_completion: bool
    exit_code: int
    stdout: bytes
    stderr: bytes
    settlement: object
    closure_after: CanonicalSourceClosure
    interpreter_identity_after: InterpreterIdentity
    provenance_verdict: str


# R2 public names remain aliases of the single lifecycle types.
TrustedScanInvocation = LaunchedScanInvocation
TrustedScanExecution = TrustedExecutionRecord


class PushTarget(NamedTuple):
    remote: str
    destination: str
    head_ref: str


class LiteralPushCommand(NamedTuple):
    dialect: str
    executable: str
    remote: str
    refspec: str
    target: PushTarget
    repository_root: str | None = None














































class ParsedTranscriptCommand(NamedTuple):
    entry_index: int
    occurrence_index: int
    call_id: str
    tool_name: str | None
    dialect: str
    dialect_exact: bool
    parsed: ShellParseResult






class RangeReceiptV3(NamedTuple):
    commits: int
    commit_set: str
    objects: int
    object_set: str
    blobs: int
    blob_set: str
    blob_bytes: int
    text: int
    binary: int
    subjects: int
    subject_set: str
    paths: int
    path_set: str
    remote: str
    destination: str
    source: str
    tip: str


class PublicationSafetyObservation(NamedTuple):
    kind: str
    receipt: RangeReceiptV3 | None


class UntrustedTranscriptScanObservation(NamedTuple):
    call_id: str
    call_position: int
    result_position: int | None
    correlation: str
    observation: PublicationSafetyObservation


class ConsumedAuthoritativeEvidence(NamedTuple):
    invocation_id: str
    binding: PushScanBinding
    parsed_outcome: PublicationSafetyObservation
    consumption_id: str
    execution: TrustedExecutionRecord | None = None


AuthoritativeScanObservation = ConsumedAuthoritativeEvidence









# MARKER-HONORING LENGTH BOUND (2026-07-26, `$security-engineer` contract
# decision — work-items/bugs/2026-07-26-the-deny-message-teaches-the-marker-
# that-opens-the-gate.md). The deny reason below embeds the marker verbatim
# so the operator knows what to type; an operator who copies that SAME text
# back into chat ("what does this mean?", pasting it into a bug report)
# reproduces the identical marker byte-for-byte. A bare substring search
# cannot distinguish that from a deliberate approval — both are the same
# bytes. The marker is a disclosed, shared, non-secret token, not a nonce; no
# fixed-string match at this layer separates "operator approved" from
# "operator quoted the denial" with certainty, because a human can always
# retype or paste any substring of already-disclosed text into either shape.
#
# Candidates considered and rejected (full comparison in the filed bug):
#   - Marker-must-be-on-its-own-line: rejected — it BREAKS the existing,
#     tested, documented approval convention. Both `test_user_marker_allows`
#     ("looks good, push it [approve-publication]") and
#     `test_lead_sync_flow_marker_allows` ("Wave E approved after review —
#     sync all branches [approve-publication]") carry the marker inline at
#     the end of an ordinary sentence, never alone on a line. A "fix" that
#     invalidates the documented contract it is meant to protect is a
#     regression, not a hardening.
#   - Recognize-the-gate's-own-output (exclude when deny-text vocabulary
#     co-occurs): rejected as the PRIMARY mechanism — it couples this
#     matcher to the deny reason's prose. This file's own history
#     (CORRELATION / COLLISION REJECTION / ORDERING / CALL-SIDE UNIQUENESS
#     notes above) is a record of exactly this kind of self-referential
#     pattern-matching drifting once real transcripts and real wording
#     changes are thrown at it; adding a fourth self-referential layer here,
#     on the strength of a single review pass with no adversarial pressure
#     yet applied, is not a risk this fix should take on.
#   - Change the marker string: rejected — the new string still has to
#     appear verbatim in the deny text for the operator to know what to
#     type, recreating the identical echo path under a new name, while
#     breaking every existing workflow/doc/habit across all four provider
#     packs for no structural gain.
#
# Chosen mitigation: a LENGTH BOUND, decoupled from the deny text's wording
# entirely (robust to future edits of that prose, unlike the rejected
# recognize-own-output approach). The marker is honored only when the
# carrying message is short enough to plausibly be a deliberate one-line
# approval, not a copied multi-paragraph block. Measured, not guessed
# (2026-07-26): the two documented genuine approvals above are 41 and 70
# characters; the shipped deny reason text is 2384 characters; a realistic
# PARTIAL quote of just one deny clause (clause (a) alone, a plausible
# "what does this bullet mean?" paste) measures 284-305 characters.
# MARKER_MAX_MESSAGE_LENGTH sits below both measured accident sizes with
# margin, while sitting well above both measured genuine-approval sizes —
# closing the bug's own named scenario ("pasting it into a bug report")
# with high confidence.
#
# NOT CLOSED (disclosed, not silently assumed away): a SHORT quote of, or
# question about, just the bare marker itself ("what does `[approve-
# publication]` mean?" — well under any length bound) is indistinguishable
# by length OR content from a genuine short approval. This residual is
# shared by every candidate considered above, not unique to this one;
# closing it fully needs a per-event nonce or an out-of-band confirmation
# channel, both larger contract changes than this bounded fix makes.
# MARKER_MAX_MESSAGE_LENGTH is a tunable judgment call, not a measured
# physical constant — recalibrate it if it is ever seen rejecting a genuine
# operator approval in practice.

# Explicit user push-instruction signal (English + Russian). Matched against
# the last genuine user message only; used together with scan evidence.

# Publication-safety scan INVOCATION detection is EXECUTION-based, not a
# regex over call text; the immutable parser projection below owns the
# 2026-07-26
# mention-vs-execution hardening, adversarial-gate finding). A prior
# `SCAN_INVOCATION_REGEX` here matched the scanner's NAME anywhere in a
# call's flattened text, which is satisfied just as readily by a command
# that merely NAMES the scanner (`grep ... check-publication-safety.sh`,
# `Test-Path .../check-publication-safety.py`, `ls .../agents-check-
# safety.md`) as by one that runs it — reproduced live against real
# historical transcripts on this machine (a `Test-Path` existence check and
# an `ls` of the command file both "matched" without ever running the
# scanner). `/agents-check-safety` is not matched as a distinct shape at
# all: it is not text-matched here because no real transcript on this
# machine ever shows it as its own tool-call shape (searched exhaustively);
# its own documented steps (`src.claude/commands/agents-check-safety.md`
# step 1) always cause the model to issue a real `bash .../check-
# publication-safety.sh` call, which the scan projection recognizes
# like any other real execution — so dropping the text-mention branch loses
# no real detection, only the false-positive surface it created.

# Publication-safety scan RESULT — matched narrowly against the CORRELATED
# tool OUTPUT of a call whose parser-owned projection proves scan execution
# (never prose, never an uncorrelated tool result — see extract_tool_outputs_with_ids
# and the module docstring's CORRELATION note), so a file or tool result
# merely mentioning the scanner cannot satisfy it either, whether or not it
# shares a turn with an unrelated scan invocation. This is the scanner's OWN
# self-reported clean-pass line (check-publication-safety.py, all
# copies): "publication-safety: clean (tracked, examined N files)". THREE
# conditions are all load-bearing and none is optional:
#   - `tracked` only. A `--path` fixture-testing invocation reports `path` in
#     the same slot; requiring the literal word `tracked` keeps a local fixture
#     scan (which can point at an arbitrary directory, scanning content that
#     has nothing to do with what is staged) from ever laundering as gate
#     evidence (mirrors the scan-mode gap identified for the receipt design
#     that was dropped in favor of this narrower mechanism, §3.3 of
#     work-items/decisions/2026-07-26-publication-clean-receipt-contract.md).
#   - `[1-9]\d*` only — NOT `\d*`. An examined count of exactly 0 must NOT
#     match: check-publication-safety.sh exits 0 (clean) when `git diff
#     --cached` is empty, which is exactly what happens in the ordinary
#     commit-then-push flow (the staged index already equals HEAD). A scan
#     that examined nothing is UNVERIFIED, not clean, for gate purposes — this
#     is the empty-index defect this hardening exists to close
#     (work-items/bugs/2026-07-25-push-gate-keys-on-scan-invocation-not-result.md).
#   - WHOLE-LINE MATCH (`^...$` under `re.MULTILINE`), not a bare substring
#     search — added 2026-07-26 as a CRITICAL fix, `$security-reviewer`
#     (fable) finding, reproduced end to end by `$lead`: `work-items/bugs/
#     2026-07-26-push-gate-credits-a-blocking-scan-whose-grep-echoes-the-
#     clean-line.md`. A plain substring search is satisfied just as readily
#     by the clean-receipt text appearing INSIDE a longer line as by the
#     receipt being the whole line — and the scanner's own `nonpath_cmd` /
#     `scanner_nonpath_cmd` `git grep` output (check-publication-safety.sh,
#     printed straight to stdout, correct behavior for a human reader) is
#     exactly such a longer line whenever the leaked content itself happens
#     to quote the receipt text: `git grep` unconditionally prefixes
#     `path:lineno:` to whatever it found, so a staged line such as
#     `token = "publication-safety: clean (tracked, examined 9 files)"`
#     both trips a real leak pattern (the scan correctly BLOCKS, exit 1) and
#     embeds the exact clean-receipt substring in the same report line — and
#     this hook never reads the scan's own exit status (see the module
#     docstring's WHAT THIS STILL DOES NOT COVER section), so the scanner's
#     honest report of its OWN failure was, verbatim, the string this gate
#     accepted as proof of success. Anchoring to a whole line costs the
#     genuine receipt nothing: check-publication-safety.sh's own emission
#     (`echo "publication-safety: clean (${scan_mode}, examined
#     ${examined_count} ${examined_word})"`, .sh:429) is always the sole
#     content of its own physical line, and `git grep`'s mandatory
#     `path:lineno:` prefix (or a line-numbering wrapper such as `cat -n`)
#     means an EMBEDDED occurrence can never itself start at the beginning
#     of a line. `re.MULTILINE`'s `$` matches immediately before a `\n`
#     (or at end-of-string), and the trailing `\s*` before it consumes a
#     stray `\r` from a CRLF-terminated capture (`\r` is itself whitespace),
#     so a Windows-style `\r\n` line ending does not defeat the anchor —
#     verified against fixtures carrying a trailing `\r` and against the
#     receipt as the ONLY line in the captured output (both anchor cases
#     bottom out in `$` matching at true end-of-string, no trailing newline
#     required). See `SCAN_FAILURE_MARKER_REGEX` immediately below for the
#     belt-and-braces companion check this same finding also requires.
SCAN_CLEAN_TRACKED_REGEX = re.compile(
    r"^publication-safety:\s*clean\s*\(\s*tracked\s*,\s*examined\s+([1-9]\d*)\s+files?\s*\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Belt-and-braces companion to SCAN_CLEAN_TRACKED_REGEX (2026-07-26, same
# critical hardening as the whole-line-match condition above — see that
# regex's own comment for the full reasoning this shares). Even a genuine
# whole-line match of the clean receipt must NOT be credited if the SAME
# correlated tool output also carries the scanner's own self-reported
# FAILURE line (check-publication-safety.sh's exact stderr text on a block,
# .sh:387, printed immediately before its `exit 1`). A single scan cannot
# both fail and pass; if a correlated result carries both strings, the
# honest and defensible reading is DENY, not a coin flip between two
# self-contradictory reports. Matched by plain SUBSTRING on purpose (unlike
# the whole-line-anchored clean regex above): this line's exact text is a
# fixed, known one-liner with nothing meaningful to anchor against, and this
# check only ever NARROWS what counts as clean — it can turn a would-be
# ALLOW into a DENY, never the reverse — so a broader match here costs
# nothing.
SCAN_FAILURE_MARKER_REGEX = re.compile(
    r"publication-safety scan found potential tracked-content leak markers",
    re.IGNORECASE,
)

# Publication-safety scan RESULT for `range` mode. Same THREE load-bearing
# conditions as SCAN_CLEAN_TRACKED_REGEX, applied to the SAME check-
# publication-safety.sh emission site (.sh's final echo, range branch):
#   - `range` only, never `tracked` or `path` — a distinct mode word so one
#     token never denotes two different scan subjects (mirrors why `path`
#     cannot launder as `tracked` evidence today).
#   - `[1-9]\d*` only — an examined count of exactly 0 (the range is already
#     fully published, or every candidate path was added-then-deleted within
#     it) must not match; check-publication-safety.sh's own zero-range line
#     ("range, examined 0 files -- nothing to publish") is shaped so it
#     cannot, doubly (wrong count AND a different tail with no remote/dst/tip
#     fields at all).
#   - WHOLE-LINE MATCH (`^...$` under `re.MULTILINE`), inherited from the
#     start rather than retrofitted — see SCAN_CLEAN_TRACKED_REGEX's own
#     comment for why a bare substring search is unsound here (a `git grep`
#     report line embedding this text as a substring must never be credited).
# `remote`, `dst`, and `tip` are captured so `evaluate_push` can compare the
# first two against the admitted immutable grammar decision's binding.
# `tip` is captured (and its shape validated as a supported Git object ID) because it
# is always part of the real receipt's own text. The legacy generic range
# branch does not compare it; the strict PR route does compare it to a fresh
# `git rev-parse --verify HEAD` result.
SCAN_CLEAN_RANGE_REGEX = re.compile(
    r"^publication-safety:\s*clean\s*\(\s*range\s*,\s*examined\s+(?P<count>[1-9]\d*)\s+files?\s*,"
    rf"\s*remote\s+(?P<remote>\S+)\s*,\s*dst\s+(?P<dst>\S+)\s*,\s*tip\s+(?P<tip>{_LOWERCASE_OID_PATTERN})\s*\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

SCAN_CLEAN_RANGE_V3_REGEX = re.compile(
    r"^publication-safety: clean \(range, receipt=v3, "
    r"commits=(?P<commits>[1-9]\d*), "
    r"commit-set=(?P<commit_set>[0-9a-f]{64}), messages=complete, "
    r"objects=(?P<objects>[1-9]\d*), object-set=(?P<object_set>[0-9a-f]{64}), "
    r"blobs=(?P<blobs>0|[1-9]\d*), blob-set=(?P<blob_set>[0-9a-f]{64}), "
    r"blob-bytes=(?P<blob_bytes>0|[1-9]\d*), text=(?P<text>0|[1-9]\d*), "
    r"binary=(?P<binary>0|[1-9]\d*), subjects=(?P<subjects>0|[1-9]\d*), "
    r"subject-set=(?P<subject_set>[0-9a-f]{64}), paths=(?P<paths>0|[1-9]\d*), "
    r"path-set=(?P<path_set>[0-9a-f]{64}), history=complete, "
    r"remote=(?P<remote>[A-Za-z0-9._~%-]+), "
    r"dst=(?P<dst>[A-Za-z0-9._~%-]+), "
    rf"src=(?P<src>[A-Za-z0-9._~%-]+), tip=(?P<tip>{_LOWERCASE_OID_PATTERN})\)$",
    re.MULTILINE,
)
SCAN_CLEAN_PATH_REGEX = re.compile(
    r"^publication-safety:\s*clean\s*\(\s*path\s*,\s*examined\s+\d+\s+files?[^\r\n]*\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
SCAN_TYPED_FAILURE_REGEX = re.compile(
    r"\bPS-(?:FINDING-(?:CONTENT|COMMIT-MESSAGE)|MSG-[A-Z-]+|INPUT-REFUSAL)\b"
)


def _decode_canonical_receipt_token(token: str) -> str | None:
    if not token:
        return None
    try:
        value = unquote_to_bytes(token).decode("utf-8", "strict")
    except (UnicodeDecodeError, ValueError):
        return None
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    if quote(value, safe="-._~", encoding="utf-8", errors="strict") != token:
        return None
    return value


def parse_publication_safety_observation(text: str) -> PublicationSafetyObservation:
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        return PublicationSafetyObservation("malformed", None)
    v3_matches = list(SCAN_CLEAN_RANGE_V3_REGEX.finditer(text))
    clean_lines = [
        line for line in text.splitlines()
        if line.startswith("publication-safety: clean (")
    ]
    has_failure = bool(
        SCAN_FAILURE_MARKER_REGEX.search(text) or SCAN_TYPED_FAILURE_REGEX.search(text)
    )
    if len(v3_matches) == 1 and len(clean_lines) == 1 and not has_failure:
        match = v3_matches[0]
        remote = _decode_canonical_receipt_token(match.group("remote"))
        destination = _decode_canonical_receipt_token(match.group("dst"))
        source = _decode_canonical_receipt_token(match.group("src"))
        if remote is None or destination is None or source is None:
            return PublicationSafetyObservation("malformed", None)
        counts = {
            name: int(match.group(name))
            for name in (
                "commits", "objects", "blobs", "blob_bytes", "text",
                "binary", "subjects", "paths",
            )
        }
        if (
            counts["commits"] > counts["objects"]
            or counts["blobs"] > counts["objects"]
            or counts["text"] + counts["binary"] != counts["blobs"]
            or (
                counts["blobs"] == 0
                and any(counts[name] != 0 for name in (
                    "blob_bytes", "text", "binary", "subjects", "paths"
                ))
            )
            or (
                counts["blobs"] > 0
                and not (
                    counts["subjects"] >= counts["paths"] >= counts["blobs"]
                )
            )
        ):
            return PublicationSafetyObservation("malformed", None)
        return PublicationSafetyObservation(
            "valid-v3",
            RangeReceiptV3(
                counts["commits"],
                match.group("commit_set"),
                counts["objects"],
                match.group("object_set"),
                counts["blobs"],
                match.group("blob_set"),
                counts["blob_bytes"],
                counts["text"],
                counts["binary"],
                counts["subjects"],
                match.group("subject_set"),
                counts["paths"],
                match.group("path_set"),
                remote,
                destination,
                source,
                match.group("tip"),
            ),
        )
    if v3_matches or "publication-safety: clean (range, receipt=v3" in text:
        return PublicationSafetyObservation("malformed", None)
    if "publication-safety: clean (range, receipt=v2" in text:
        return (
            PublicationSafetyObservation("legacy-nonauthorizing", None)
            if len(clean_lines) == 1 and not has_failure
            else PublicationSafetyObservation("malformed", None)
        )
    if (
        SCAN_CLEAN_TRACKED_REGEX.search(text)
        or SCAN_CLEAN_RANGE_REGEX.search(text)
        or SCAN_CLEAN_PATH_REGEX.search(text)
    ):
        return PublicationSafetyObservation("legacy-nonauthorizing", None)
    if clean_lines or has_failure:
        return PublicationSafetyObservation("malformed", None)
    return PublicationSafetyObservation("none", None)


# Git global options that consume a separate following value. They are
# retained in the invocation record; this set only identifies their arity.

# Shell keywords that PRECEDE a command without consuming the command slot
# (`if ...; then git push; fi`, `for b in x; do git push; done`).




def _mask_attached_io_numbers(command: str) -> str:
    """Replace only unquoted shell I/O-number prefixes with spaces.

    `shlex` exposes a public token stream, but not public raw-source
    provenance for whether a decimal token was immediately attached to a
    redirection operator. Preserve every source offset by masking only an
    ASCII digit run at a shell command boundary when its next character is
    `<` or `>`. The existing public tokenizer then sees the operator and
    consumes its target as it already does. Quotes and escaped characters are
    left untouched, so positional or quoted ref names such as `2` stay
    ordinary arguments.

    Heredoc and here-string bodies are removed by the data-region owner before
    this prepass runs, so attached descriptors in executable text are handled
    without inspecting body data.
    """
    masked = list(command)
    quote: str | None = None
    index = 0
    while index < len(command):
        character = command[index]
        if quote == "'":
            if character == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if character == "\\":
                index += 2
                continue
            if character == '"':
                quote = None
            index += 1
            continue
        if character == "\\":
            index += 2
            continue
        if character in "'\"":
            quote = character
            index += 1
            continue
        if "0" <= character <= "9" and (
            index == 0 or command[index - 1] in " \t\r\n;|&()"
        ):
            run_end = index
            while run_end < len(command) and "0" <= command[run_end] <= "9":
                run_end += 1
            if run_end < len(command) and command[run_end] in "<>":
                for digit_index in range(index, run_end):
                    masked[digit_index] = " "
            index = run_end
            continue
        index += 1
    return "".join(masked)
























































# --- Publication-safety scan EXECUTION detection (2026-07-26 hardening) ---
# Basenames the scanner ships under, across both provider lines and both
# shell targets. Matched by BASENAME only (never by directory), case-
# insensitively (Windows paths are case-insensitive and real PowerShell/CMD
# invocations on this machine vary case), so any installed or repo-local
# copy at any of the pack's own script paths is recognized.

# Interpreters that can be told to run an arbitrary script file as their
# FIRST operand (`bash x.sh`, `sh x.sh`, `. x.sh` / `source x.sh`). A bare
# `./x.sh` (or any other path ending in one of the basenames above) with NO
# interpreter prefix is also recognized — see `_record_runs_scan_script`'s
# direct-exec branch.

# PowerShell/pwsh flag whose OWN value is the script path to run.
# PowerShell/pwsh flag whose OWN value is an arbitrary COMMAND STRING —
# re-tokenized and re-scanned through this SAME segment machinery
# (recursion, not a second parser), so `-Command "grep ... x.ps1"` cannot
# launder a MENTION as an execution the way the old plain-substring regex
# could.










def _parse_pr_grant(text: str) -> ActivePrGrant | None:
    if not text.startswith(PR_GRANT_PREFIX) or not text.endswith("]"):
        return None
    target = text[len(PR_GRANT_PREFIX):-1]
    if PR_GRANT_NUMBER_REGEX.fullmatch(target):
        return ActivePrGrant(target, "", "", int(target))
    markdown = PR_GRANT_MARKDOWN_REGEX.fullmatch(target)
    if markdown:
        if markdown.group("label") != markdown.group("destination"):
            return None
        target = markdown.group("label")
    match = PR_URL_REGEX.fullmatch(target)
    if not match:
        return None
    owner = match.group("owner")
    repo = match.group("repo")
    if owner in (".", "..") or repo in (".", ".."):
        return None
    return ActivePrGrant(
        match.group("url"), owner, repo, int(match.group("number"))
    )


def _canonicalize_numeric_pr_grant(
    number: int, authorization_workdir: str
) -> ActivePrGrant:
    repository_workdir = _normalize_repository_workdir(authorization_workdir)
    git_exe = _resolve_executable("git", repository_workdir)
    gh_exe = _resolve_executable("gh", repository_workdir)
    if git_exe is None or gh_exe is None:
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    repository_workdir = _prove_repository_root(repository_workdir, git_exe)
    deadline = time.monotonic() + ORACLE_TIMEOUT_SECONDS
    _, repo_text = _run_text(
        [gh_exe, "repo", "view", "--json", "nameWithOwner,url"],
        deadline, "PRG-PR-UNAVAILABLE", repository_workdir,
    )
    repository = _strict_json(repo_text, dict, "PRG-PR-UNAVAILABLE")
    name = repository.get("nameWithOwner")
    if not isinstance(name, str) or name.count("/") != 1:
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    owner, repo = name.split("/", 1)
    if not REPO_COMPONENT_REGEX.fullmatch(owner) or not REPO_COMPONENT_REGEX.fullmatch(repo):
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    if repository.get("url") != f"https://github.com/{owner}/{repo}":
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    _, pr_text = _run_text(
        [gh_exe, "pr", "view", str(number), "--repo", name, "--json", "number,url"],
        deadline, "PRG-PR-UNAVAILABLE", repository_workdir,
    )
    pr = _strict_json(pr_text, dict, "PRG-PR-UNAVAILABLE")
    match = PR_URL_REGEX.fullmatch(pr.get("url")) if isinstance(pr.get("url"), str) else None
    if (
        match is None or pr.get("number") != number
        or match.group("owner") != owner or match.group("repo") != repo
    ):
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    if _prove_repository_root(repository_workdir, git_exe) != repository_workdir:
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    return ActivePrGrant(match.group("url"), owner, repo, number)


def _derive_pr_grant(
    entries: list[dict], envelope_repository_workdir: str
) -> tuple[str, ActivePrGrant | None]:
    state = "absent"
    grant: ActivePrGrant | None = None
    transcript_workdir: str | None = None
    genuine_user_indexes = [
        index for index, entry in enumerate(entries)
        if is_user_message(entry) and extract_user_typed_text(entry)
    ]
    last_user_index = genuine_user_indexes[-1] if genuine_user_indexes else -1
    for index, entry in enumerate(entries):
        payload = entry.get("payload") if isinstance(entry, dict) else None
        if entry.get("type") in ("session_meta", "turn_context"):
            raw_context = payload.get("cwd") if isinstance(payload, dict) else None
            transcript_workdir = raw_context if type(raw_context) is str and raw_context else None
        if not is_user_message(entry):
            continue
        text = extract_user_typed_text(entry)
        if not text:
            continue
        if text == PR_REVOKE_MARKER:
            state, grant = "revoked", None
            continue
        parsed_grant = _parse_pr_grant(text)
        if parsed_grant is not None:
            if not parsed_grant.owner:
                direct_context = entry.get("cwd")
                if direct_context is not None and (
                    type(direct_context) is not str or not direct_context
                ):
                    state, grant = "malformed", None
                    continue
                contexts = {
                    value for value in (direct_context, transcript_workdir)
                    if value is not None
                }
                if len(contexts) > 1:
                    state, grant = "malformed", None
                    continue
                authorization_workdir = next(iter(contexts), None)
                if authorization_workdir is None and index == last_user_index:
                    authorization_workdir = envelope_repository_workdir
                if authorization_workdir is None:
                    state, grant = "malformed", None
                    continue
                parsed_grant = _canonicalize_numeric_pr_grant(
                    parsed_grant.number, authorization_workdir
                )
            state, grant = "active", parsed_grant
            continue
        if text.startswith(PR_RESERVED_PREFIXES):
            state, grant = "malformed", None
    return state, grant


def _read_stable_transcript_suffix(transcript_path: str) -> tuple[list[dict], str]:
    """Read one stable complete-record suffix under the history reader's caps."""
    if not transcript_path:
        return [], "absent"
    path = Path(transcript_path)
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            eof = before.st_size
            if eof > TRANSCRIPT_HISTORY_BYTE_CAP:
                stream.seek(eof - TRANSCRIPT_HISTORY_BYTE_CAP)
                raw = stream.read(TRANSCRIPT_HISTORY_BYTE_CAP)
                if len(raw) != TRANSCRIPT_HISTORY_BYTE_CAP:
                    return [], "unreadable"
                sentinel, payload = raw[:1], raw[1:]
                if sentinel != b"\n":
                    newline = payload.find(b"\n")
                    if newline < 0:
                        return [], "limit"
                    payload = payload[newline + 1 :]
            else:
                stream.seek(0)
                payload = stream.read(eof)
                if len(payload) != eof:
                    return [], "unreadable"
            after = os.fstat(stream.fileno())
            current = path.stat()
    except Exception:
        return [], "unreadable"

    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    if identity_before != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or identity_before != (
        current.st_dev,
        current.st_ino,
        current.st_size,
        current.st_mtime_ns,
    ):
        return [], "unreadable"

    raw_lines = payload.split(b"\n")
    ended_with_newline = payload.endswith(b"\n")
    if ended_with_newline:
        raw_lines.pop()
    entries: list[dict] = []
    for index, raw_line in enumerate(raw_lines):
        if not raw_line.strip():
            continue
        line_size = len(raw_line) + (1 if ended_with_newline or index < len(raw_lines) - 1 else 0)
        if line_size > TRANSCRIPT_HISTORY_LINE_BYTE_CAP:
            return [], "limit"
        if len(entries) >= TRANSCRIPT_HISTORY_RECORD_CAP:
            return [], "limit"
        try:
            entry = json.loads(raw_line.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return [], "invalid"
        if not isinstance(entry, dict):
            return [], "invalid"
        entries.append(entry)
    return entries, "found"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_executable(name: str, repository_root: str) -> str | None:
    candidate = shutil.which(name)
    if not candidate:
        return None
    try:
        resolved = Path(candidate).resolve(strict=True)
        workspace = Path(repository_root).resolve(strict=True)
    except Exception:
        return None
    if not resolved.is_file() or _is_within(resolved, workspace):
        return None
    return str(resolved)


_PR_COMMAND_DIALECT_TEST_OVERRIDE: str | None = None


def _pr_command_dialect(resolved_dialect: str) -> str:
    """Validate the preflight-resolved production shell contract."""
    if _PR_COMMAND_DIALECT_TEST_OVERRIDE in ("posix", "powershell"):
        return _PR_COMMAND_DIALECT_TEST_OVERRIDE
    try:
        source = Path(__file__).resolve(strict=True).as_posix().casefold()
    except Exception:
        raise PrRouteDenied("PRG-COMMAND-SHAPE") from None
    if source.endswith((
        "/.claude/agents/scripts/check-git-push-gate.py",
        "/src.claude/agents/scripts/check-git-push-gate.py",
    )) and resolved_dialect == "posix":
        return resolved_dialect
    if source.endswith((
        "/.agents/skills/lead/scripts/check-git-push-gate.py",
        "/.codex/skills/lead/scripts/check-git-push-gate.py",
        "/src.codex/skills/lead/scripts/check-git-push-gate.py",
    )):
        if os.name == "posix" and resolved_dialect == "posix":
            return resolved_dialect
        if os.name == "nt" and resolved_dialect == "powershell":
            return resolved_dialect
    raise PrRouteDenied("PRG-COMMAND-SHAPE")






def _portable_pr_head_ref(value: str) -> bool:
    return PR_HEAD_REF_REGEX.fullmatch(value) is not None


def _parse_pr_literal_shape(
    parsed: ShellParseResult, dialect: str
) -> LiteralPushCommand:
    if parsed.dialect != dialect or parsed.strict_projection.status != "canonical":
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    if dialect not in ("posix", "powershell"):
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    decoded = list(parsed.strict_projection.argv)
    if len(decoded) == 4:
        executable, subcommand, remote, refspec = decoded
        repository_root = None
    elif len(decoded) == 6 and decoded[1] == "-C":
        executable, _option, repository_root, subcommand, remote, refspec = decoded
        if not Path(repository_root).is_absolute():
            raise PrRouteDenied("PRG-COMMAND-SHAPE")
    else:
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    if subcommand != "push" or not Path(executable).is_absolute():
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    if not REMOTE_NAME_REGEX.fullmatch(remote):
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    prefix = "HEAD:refs/heads/"
    if not refspec.startswith(prefix):
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    head_ref = refspec[len(prefix):]
    if not _portable_pr_head_ref(head_ref):
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    target = PushTarget(remote, f"refs/heads/{head_ref}", head_ref)
    return LiteralPushCommand(
        dialect, executable, remote, refspec, target, repository_root
    )


def _bind_pr_literal_executable(
    literal: LiteralPushCommand, resolved_git: str
) -> LiteralPushCommand:
    try:
        executable_path = Path(literal.executable).resolve(strict=True)
        resolved_path = Path(resolved_git).resolve(strict=True)
        same_identity = executable_path.is_file() and resolved_path.is_file() and os.path.samefile(
            executable_path, resolved_path
        )
    except Exception:
        same_identity = False
    if not same_identity:
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    return literal


def _parse_pr_literal_command(
    parsed: ShellParseResult,
    resolved_git: str,
    dialect: str,
) -> LiteralPushCommand:
    return _bind_pr_literal_executable(
        _parse_pr_literal_shape(parsed, dialect), resolved_git
    )


def _run_process(
    argv: list[str], timeout: float, repository_workdir: str
) -> ProcessResult | None:
    env = os.environ.copy()
    env.pop("GH_REPO", None)
    env["GH_PROMPT_DISABLED"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=repository_workdir,
        )
    except OSError:
        return None

    stdout = bytearray()
    stderr = bytearray()
    overflow = threading.Event()

    def drain(stream, destination: bytearray) -> None:
        try:
            while not overflow.is_set():
                chunk = stream.read(8192)
                if not chunk:
                    return
                if len(destination) + len(chunk) > PROCESS_OUTPUT_BYTE_CAP:
                    overflow.set()
                    return
                destination.extend(chunk)
        except OSError:
            overflow.set()

    assert process.stdout is not None and process.stderr is not None
    readers = (
        threading.Thread(target=drain, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr), daemon=True),
    )
    for reader in readers:
        reader.start()

    deadline = time.monotonic() + max(0.0, timeout)
    failed = False
    while process.poll() is None:
        if overflow.is_set() or time.monotonic() >= deadline:
            failed = True
            process.kill()
            break
        time.sleep(0.01)
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        failed = True
    for reader in readers:
        reader.join(timeout=1.0)
    process.stdout.close()
    process.stderr.close()
    if failed or overflow.is_set() or any(reader.is_alive() for reader in readers):
        return None
    return ProcessResult(process.returncode, bytes(stdout), bytes(stderr))


_SCAN_BOOTSTRAP = r'''import base64,builtins,json,sys,types
bundle=json.loads(sys.stdin.buffer.read().decode("ascii"))
sources={key:base64.b64decode(value,validate=True) for key,value in bundle.items()}
allowed=set(sys.stdlib_module_names)|{"hook_common"}
original_import=builtins.__import__
def guarded_import(name,globals=None,locals=None,fromlist=(),level=0):
    if not level and name.split(".",1)[0] not in allowed:
        raise ImportError("non-standard import denied")
    return original_import(name,globals,locals,fromlist,level)
builtins.__import__=guarded_import
common=types.ModuleType("hook_common")
common.__file__="<closure>/hook_common.py"
sys.modules["hook_common"]=common
exec(compile(sources["hook_common"],common.__file__,"exec"),common.__dict__,common.__dict__)
classifier={"__name__":"_publication_path_owner","__file__":"<closure>/check-machine-local-path.py","__package__":None,"__cached__":None}
exec(compile(sources["classifier"],classifier["__file__"],"exec"),classifier,classifier)
finder=classifier.get("find_machine_paths")
if not callable(finder):
    raise RuntimeError("classifier contract")
if len(sys.argv)<3 or sys.argv[1]!="--gate-git-executable":
    raise RuntimeError("git executable contract")
git_executable=sys.argv[2]
scanner_path="<closure>/check-publication-safety.py"
scanner={"__name__":"__main__","__file__":scanner_path,"__package__":None,"__cached__":None,"__injected_find_machine_paths__":finder,"__injected_git_executable__":git_executable}
sys.argv=[scanner_path,*sys.argv[3:]]
exec(compile(sources["scanner"],scanner_path,"exec"),scanner,scanner)
'''


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        int(value.st_dev), int(value.st_ino), int(value.st_mode),
        int(value.st_nlink), int(value.st_size),
        int(getattr(value, "st_mtime_ns", int(value.st_mtime * 1_000_000_000))),
    )


def _is_link_or_reparse(value: os.stat_result) -> bool:
    attributes = int(getattr(value, "st_file_attributes", 0))
    return stat.S_ISLNK(value.st_mode) or bool(attributes & 0x400)


def _regular_identity(path: Path, *, single_link: bool) -> tuple[int, ...]:
    value = os.lstat(path)
    if _is_link_or_reparse(value) or not stat.S_ISREG(value.st_mode):
        raise ValueError("object-kind")
    if single_link and value.st_nlink != 1:
        raise ValueError("link-count")
    return _stat_identity(value)


def _directory_identity(value: os.stat_result) -> tuple[int, ...]:
    if _is_link_or_reparse(value) or not stat.S_ISDIR(value.st_mode):
        raise ValueError("parent-kind")
    return _stat_identity(value)


def _directory_generation(path: Path) -> tuple[int, ...]:
    return _directory_identity(os.lstat(path))


def _interpreter_identity() -> TrustedInterpreterIdentity:
    raw = Path(sys.executable)
    if not raw.is_absolute():
        raise ValueError("interpreter-path")
    resolved = raw.resolve(strict=True)
    identity = _regular_identity(resolved, single_link=False)
    return TrustedInterpreterIdentity(str(resolved), identity)


def _open_windows_path(path: Path, *, directory: bool) -> int:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    desired_access = 0 if directory else 0x80000000
    share_mode = 0x00000001 | (0x00000002 | 0x00000004 if directory else 0)
    flags = 0x00200000 | (0x02000000 if directory else 0x00000080)
    handle = create_file(str(path), desired_access, share_mode, None, 3, flags, None)
    invalid = ctypes.c_void_p(-1).value
    if handle in (None, invalid):
        raise OSError(ctypes.get_last_error(), "CreateFileW")
    try:
        return msvcrt.open_osfhandle(
            int(handle), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
    except Exception:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
        raise


def _open_windows_source(path: Path) -> int:
    return _open_windows_path(path, directory=False)


def _capture_directory(path: Path) -> tuple[int, tuple[int, ...]]:
    path_identity = _directory_generation(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if os.name == "posix":
        nofollow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if nofollow is None or directory_flag is None:
            raise ValueError("directory-open-unavailable")
        flags |= nofollow | directory_flag
    fd = (
        _open_windows_path(path, directory=True)
        if os.name == "nt"
        else os.open(path, flags)
    )
    try:
        opened_identity = _directory_identity(os.fstat(fd))
        if opened_identity != path_identity:
            raise ValueError("directory-open-identity")
        return fd, opened_identity
    except Exception:
        os.close(fd)
        raise


def _capture_source_node(path: Path, role: str) -> tuple[int, SourceNode]:
    path_identity = _regular_identity(path, single_link=True)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if os.name == "posix":
        if nofollow is None:
            raise ValueError("nofollow-unavailable")
        flags |= nofollow
    fd = _open_windows_source(path) if os.name == "nt" else os.open(path, flags)
    try:
        opened = os.fstat(fd)
        opened_identity = _stat_identity(opened)
        if (
            _is_link_or_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened_identity != path_identity
        ):
            raise ValueError("open-identity")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(65_536, SCAN_SNAPSHOT_BYTE_CAP + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > SCAN_SNAPSHOT_BYTE_CAP:
                raise ValueError("snapshot-limit")
        source = b"".join(chunks)
        if len(source) != opened.st_size:
            raise ValueError("snapshot-size")
        return fd, SourceNode(
            role, str(path), opened_identity,
            int(opened.st_nlink), len(source), hashlib.sha256(source).hexdigest(), source,
        )
    except Exception:
        os.close(fd)
        raise


def _capture_interpreter_handle(
    identity: InterpreterIdentity,
) -> int:
    path = Path(identity.absolute_resolved_path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if os.name == "posix":
        if nofollow is None:
            raise ValueError("nofollow-unavailable")
        flags |= nofollow
    fd = _open_windows_source(path) if os.name == "nt" else os.open(path, flags)
    try:
        opened = os.fstat(fd)
        opened_identity = _stat_identity(opened)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened_identity[:2] != identity.file_identity[:2]
            or opened_identity[3:] != identity.file_identity[3:]
        ):
            raise ValueError("interpreter-open-identity")
        return fd
    except Exception:
        os.close(fd)
        raise


def _layout_for_gate(gate: Path) -> tuple[SourceLayout, Path]:
    parts = gate.parts
    matches = [
        layout for layout in SOURCE_LAYOUTS
        if len(parts) >= len(layout.gate_suffix)
        and tuple(parts[-len(layout.gate_suffix):]) == layout.gate_suffix
    ]
    if len(matches) != 1:
        raise ValueError("layout")
    layout = matches[0]
    return layout, gate.parent.parent


def _component_paths(trust_root: Path, paths: tuple[Path, ...]) -> tuple[tuple[str, Path], ...]:
    observed: dict[str, Path] = {".": trust_root}
    for path in paths:
        relative = path.relative_to(trust_root)
        cursor = trust_root
        for part in relative.parts[:-1]:
            cursor = cursor / part
            name = cursor.relative_to(trust_root).as_posix()
            observed[name] = cursor
    return tuple((name, observed[name]) for name in sorted(observed))


def _capture_path_components(
    trust_root: Path, paths: tuple[Path, ...],
) -> tuple[tuple[int, ...], tuple[PathComponentIdentity, ...]]:
    fds: list[int] = []
    components: list[PathComponentIdentity] = []
    by_name: dict[str, int] = {}
    try:
        for name, path in _component_paths(trust_root, paths):
            if name == "." or os.name != "posix":
                fd, identity = _capture_directory(path)
            else:
                parent_name, _separator, basename = name.rpartition("/")
                parent_fd = by_name[parent_name or "."]
                expected_identity = _directory_generation(path)
                flags = (
                    os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NOFOLLOW") | getattr(os, "O_DIRECTORY")
                )
                fd = os.open(basename, flags, dir_fd=parent_fd)
                try:
                    identity = _directory_identity(os.fstat(fd))
                    named_identity = _directory_identity(os.stat(
                        basename, dir_fd=parent_fd, follow_symlinks=False
                    ))
                    if identity != expected_identity or named_identity != identity:
                        raise ValueError("directory-open-identity")
                except Exception:
                    os.close(fd)
                    raise
            fds.append(fd)
            by_name[name] = fd
            components.append(PathComponentIdentity(name, "directory", identity))
        return tuple(fds), tuple(components)
    except Exception:
        for fd in fds:
            os.close(fd)
        raise


def _capture_source_closure() -> tuple[tuple[int, ...], CanonicalSourceClosure]:
    gate = Path(os.path.abspath(__file__))
    layout, trust_root_path = _layout_for_gate(gate)
    parent = gate.parent
    paths = (
        ("gate", gate),
        ("hook_common", parent / "hook_common.py"),
        ("classifier", parent.parent / "hooks" / "check-machine-local-path.py"),
        ("scanner", parent / "check-publication-safety.py"),
    )
    fds: list[int] = []
    nodes: list[SourceNode] = []
    try:
        component_paths = (gate,) + tuple(path for _role, path in paths)
        component_fds, components = _capture_path_components(
            trust_root_path, component_paths
        )
        fds.extend(component_fds)
        for role, path in paths:
            fd, node = _capture_source_node(path, role)
            fds.append(fd)
            nodes.append(node)
        bootstrap_digest = hashlib.sha256(_SCAN_BOOTSTRAP.encode("utf-8")).hexdigest()
        interpreter_identity = _interpreter_identity()
        fds.append(_capture_interpreter_handle(interpreter_identity))
        digest_owner = hashlib.sha256(b"publication-safety-closure-v2\0")
        digest_owner.update(layout.name.encode("ascii") + b"\0")
        digest_owner.update(bootstrap_digest.encode("ascii"))
        for component in components:
            digest_owner.update(b"\0" + component.root_relative_name.encode("utf-8") + b"\0")
            digest_owner.update(repr(component.identity).encode("ascii"))
        for node in nodes:
            digest_owner.update(b"\0" + node.role.encode("ascii") + b"\0")
            digest_owner.update(node.sha256.encode("ascii"))
        trust_root = components[0]
        gate_identity = nodes[0].file_identity
        return tuple(fds), CanonicalSourceClosure(
            layout, trust_root, components, tuple(nodes), digest_owner.hexdigest(),
            gate_identity, bootstrap_digest, interpreter_identity,
        )
    except Exception:
        for fd in fds:
            os.close(fd)
        raise


def _recheck_source_closure(
    fds: tuple[int, ...], before: CanonicalSourceClosure,
) -> CanonicalSourceClosure:
    component_count = len(before.components)
    if len(fds) != component_count + len(before.nodes) + 1:
        raise ValueError("closure-cardinality")
    component_fds = fds[:component_count]
    node_fds = fds[component_count:component_count + len(before.nodes)]
    interpreter_fd = fds[-1]
    gate = Path(os.path.abspath(__file__))
    layout, trust_root_path = _layout_for_gate(gate)
    if layout != before.layout:
        raise ValueError("layout-drift")
    current_component_paths = _component_paths(
        trust_root_path, (gate,) + tuple(Path(node.expected_path) for node in before.nodes)
    )
    if tuple(name for name, _path in current_component_paths) != tuple(
        component.root_relative_name for component in before.components
    ):
        raise ValueError("component-cardinality-drift")
    component_fd_by_name = {
        component.root_relative_name: fd
        for fd, component in zip(component_fds, before.components, strict=True)
    }
    for fd, component, (name, path) in zip(
        component_fds, before.components, current_component_paths, strict=True
    ):
        opened_identity = _directory_identity(os.fstat(fd))
        if os.name == "posix" and name != ".":
            parent_name, _separator, basename = name.rpartition("/")
            live_identity = _directory_identity(os.stat(
                basename,
                dir_fd=component_fd_by_name[parent_name or "."],
                follow_symlinks=False,
            ))
        else:
            live_identity = _directory_generation(path)
        if (
            opened_identity != component.identity
            or live_identity != opened_identity
        ):
            raise ValueError("component-drift")
    for fd, node in zip(node_fds, before.nodes, strict=True):
        path = Path(node.expected_path)
        opened = os.fstat(fd)
        opened_identity = _stat_identity(opened)
        if (
            opened_identity != node.file_identity
            or opened.st_nlink != 1
            or _regular_identity(path, single_link=True) != opened_identity
        ):
            raise ValueError("identity-drift")
        os.lseek(fd, 0, os.SEEK_SET)
        source = b""
        while len(source) <= SCAN_SNAPSHOT_BYTE_CAP:
            chunk = os.read(fd, min(65_536, SCAN_SNAPSHOT_BYTE_CAP + 1 - len(source)))
            if not chunk:
                break
            source += chunk
        if source != node.source or hashlib.sha256(source).hexdigest() != node.sha256:
            raise ValueError("source-drift")
    interpreter_opened = os.fstat(interpreter_fd)
    interpreter_opened_identity = _stat_identity(interpreter_opened)
    if (
        not stat.S_ISREG(interpreter_opened.st_mode)
        or interpreter_opened_identity[:2] != before.interpreter_identity.file_identity[:2]
        or interpreter_opened_identity[3:] != before.interpreter_identity.file_identity[3:]
        or _interpreter_identity() != before.interpreter_identity
    ):
        raise ValueError("interpreter-drift")
    if (
        _regular_identity(gate, single_link=True)
        != before.gate_identity
        or hashlib.sha256(_SCAN_BOOTSTRAP.encode("utf-8")).hexdigest()
        != before.bootstrap_digest
    ):
        raise ValueError("gate-drift")
    return before


def _closure_payload(closure: CanonicalSourceClosure) -> bytes:
    return json.dumps(
        {
            node.role: base64.b64encode(node.source).decode("ascii")
            for node in closure.nodes if node.role != "gate"
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


class GateSettlementState(str, Enum):
    SETTLED = "settled"
    FAILED_UNSETTLED = "failed-unsettled"


@dataclass(frozen=True)
class GateTransportObservation:
    name: str
    ownership: str
    closed_observed: bool
    failure_phase: str | None
    observed_at_monotonic_tick: float


@dataclass(frozen=True)
class GateWorkerObservation:
    worker_identity: int
    start: str
    terminal: str
    observed_at_monotonic_tick: float


@dataclass(frozen=True)
class GateSettlementCertificate:
    supervisor_id: str
    child_identity: int
    observed_return_code: int | None
    streams: tuple[GateTransportObservation, ...]
    workers: tuple[GateWorkerObservation, ...]
    operation_errors: tuple[str, ...]
    attempts_used: int
    verified_at_monotonic_tick: float

    @property
    def complete(self) -> bool:
        ticks = tuple(row.observed_at_monotonic_tick for row in self.streams + self.workers)
        return (
            self.observed_return_code is not None
            and 1 <= self.attempts_used <= SCAN_SETTLEMENT_MAX_ENTRIES
            and all(row.ownership != "owned" or row.closed_observed for row in self.streams)
            and all(row.terminal in {"not-started", "joined"} for row in self.workers)
            and (not ticks or self.verified_at_monotonic_tick > max(ticks))
        )


@dataclass(frozen=True)
class GateSettlement:
    state: GateSettlementState
    certificate: GateSettlementCertificate | None
    execution_eligible: bool

    @property
    def complete(self) -> bool:
        return (
            self.state is GateSettlementState.SETTLED
            and self.certificate is not None
            and self.certificate.complete
        )


@dataclass
class _OwnedWorker:
    worker: threading.Thread
    start: str = "not-started"


class ChildSupervisor:
    """Single immediate owner for a launched scanner child and its workers."""

    def __init__(
        self, process, *, attempt_seconds: float = SCAN_SETTLEMENT_ATTEMPT_SECONDS,
    ) -> None:
        self.process = process
        self.supervisor_id = f"supervisor:{id(self)}"
        self.child_identity = int(process.pid)
        self.workers: list[_OwnedWorker] = []
        self._attempt_seconds = attempt_seconds
        self._attempts_used = 0
        self._operation_errors: list[str] = []
        self._settlement: GateSettlement | None = None

    def start_worker(self, worker: threading.Thread) -> None:
        owned = _OwnedWorker(worker)
        self.workers.append(owned)
        try:
            worker.start()
            owned.start = "started"
        except BaseException:
            self._operation_errors.append("worker-start")
            raise

    @property
    def settled(self) -> bool:
        return self._settlement is not None and self._settlement.complete

    @property
    def settlement(self) -> GateSettlement | None:
        return self._settlement

    def _remaining(self, deadline: float) -> float:
        return max(0.0, deadline - time.monotonic())

    def settle(self) -> GateSettlement:
        if self._settlement is not None and self._settlement.complete:
            return self._settlement
        if self._attempts_used >= SCAN_SETTLEMENT_MAX_ENTRIES:
            return self._settlement or GateSettlement(
                GateSettlementState.FAILED_UNSETTLED, None, False
            )
        self._attempts_used += 1
        deadline = time.monotonic() + self._attempt_seconds
        process = self.process
        return_code = None
        try:
            return_code = process.poll()
        except BaseException:
            self._operation_errors.append("poll")

        stream_rows: list[GateTransportObservation] = []
        stdin = process.stdin
        if stdin is not None:
            try:
                stdin.close()
                stream_rows.append(GateTransportObservation("stdin", "owned", True, None, time.monotonic()))
            except BaseException:
                self._operation_errors.append("stdin-close")
                stream_rows.append(GateTransportObservation("stdin", "owned", False, "stdin-close", time.monotonic()))
        else:
            stream_rows.append(GateTransportObservation("stdin", "absent", True, None, time.monotonic()))

        if return_code is None:
            try:
                process.terminate()
            except BaseException:
                self._operation_errors.append("terminate")
            try:
                return_code = process.wait(timeout=self._remaining(deadline))
            except BaseException:
                self._operation_errors.append("wait")
            if return_code is None:
                try:
                    process.kill()
                except BaseException:
                    self._operation_errors.append("kill")
                try:
                    return_code = process.wait(timeout=self._remaining(deadline))
                except BaseException:
                    self._operation_errors.append("kill-wait")

        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            if stream is None:
                stream_rows.append(GateTransportObservation(name, "absent", True, None, time.monotonic()))
                continue
            try:
                stream.close()
                stream_rows.append(GateTransportObservation(name, "owned", True, None, time.monotonic()))
            except BaseException:
                self._operation_errors.append(name + "-close")
                stream_rows.append(GateTransportObservation(name, "owned", False, name + "-close", time.monotonic()))

        worker_rows: list[GateWorkerObservation] = []
        for owned in self.workers:
            worker = owned.worker
            terminal = "not-started" if owned.start != "started" else "unobserved"
            if owned.start == "started":
                try:
                    worker.join(timeout=self._remaining(deadline))
                except BaseException:
                    self._operation_errors.append("worker-join")
                try:
                    terminal = "live" if worker.is_alive() else "joined"
                except BaseException:
                    self._operation_errors.append("worker-observe")
            worker_rows.append(GateWorkerObservation(id(worker), owned.start, terminal, time.monotonic()))

        try:
            observed = process.poll()
            if observed is not None:
                return_code = observed
        except BaseException:
            self._operation_errors.append("final-poll")
        participant_ticks = tuple(row.observed_at_monotonic_tick for row in stream_rows + worker_rows)
        verified = max(time.monotonic(), (max(participant_ticks) + 1e-9) if participant_ticks else 0.0)
        certificate = GateSettlementCertificate(
            self.supervisor_id, self.child_identity, return_code,
            tuple(stream_rows), tuple(worker_rows), tuple(self._operation_errors),
            self._attempts_used, verified,
        )
        state = GateSettlementState.SETTLED if certificate.complete else GateSettlementState.FAILED_UNSETTLED
        self._settlement = GateSettlement(
            state, certificate, certificate.complete and not certificate.operation_errors
        )
        return self._settlement


def _run_snapshot_child(
    pending: PendingScanInvocation, payload: bytes, repository_workdir: str,
) -> tuple[LaunchedScanInvocation, tuple[TrustedExecutionRecord, ...]]:
    prefix = "PGG" if pending.binding.route == "generic" else "PRG"
    try:
        process = subprocess.Popen(
            list(pending.exact_argv), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False,
            cwd=repository_workdir,
        )
    except OSError:
        raise PrRouteDenied(prefix + "-SCAN-EXECUTION") from None
    supervisor = ChildSupervisor(process)
    launched = LaunchedScanInvocation(
        pending, process.pid, supervisor, pending.invocation_id,
        pending.attempt_id, pending.binding, pending.exact_argv,
        pending.result_slot,
    )
    with pending._transition_lock:
        if pending.state is not PendingState.PREPARED:
            pending.state = PendingState.FAILED
            raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
        pending.child_identity = process.pid
        pending.supervisor = supervisor
        pending.state = PendingState.CHILD_OWNED
    output = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()
    lock = threading.Lock()

    def drain(name: str, stream) -> None:
        try:
            while not overflow.is_set():
                chunk = stream.read(8192)
                if not chunk:
                    return
                with lock:
                    total = len(output["stdout"]) + len(output["stderr"])
                    if total + len(chunk) > SCAN_OUTPUT_BYTE_CAP:
                        overflow.set()
                        return
                    output[name].extend(chunk)
        except (OSError, ValueError):
            overflow.set()

    def feed() -> None:
        try:
            assert process.stdin is not None
            process.stdin.write(payload)
            process.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass

    assert process.stdout is not None and process.stderr is not None
    workers = (
        threading.Thread(target=feed),
        threading.Thread(target=drain, args=("stdout", process.stdout)),
        threading.Thread(target=drain, args=("stderr", process.stderr)),
    )
    bounded = False
    setup_failure = False
    try:
        for worker in workers:
            supervisor.start_worker(worker)
        deadline = time.monotonic() + SCAN_TIMEOUT_SECONDS
        while (
            process.poll() is None
            and not overflow.is_set()
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        bounded = process.poll() is not None and not overflow.is_set()
    except Exception:
        setup_failure = True
    finally:
        with pending._transition_lock:
            if pending.state is PendingState.CHILD_OWNED:
                pending.state = PendingState.SETTLING
        settlement = supervisor.settle()
        if not settlement.complete:
            settlement = supervisor.settle()
        with pending._transition_lock:
            pending.settlement = settlement
            pending.state = (
                PendingState.SETTLED if settlement.complete else PendingState.FAILED
            )
    if setup_failure:
        raise PrRouteDenied(prefix + "-SCAN-EXECUTION")
    execution = TrustedExecutionRecord(
        pending, launched, pending.result_slot,
        bounded,
        process.returncode if process.returncode is not None else -1,
        bytes(output["stdout"]), bytes(output["stderr"]), settlement,
        pending.closure, pending.interpreter_identity, "pending",
    )
    return launched, (execution,)


def _refresh_scan_binding(
    binding: PushScanBinding, repository_workdir: str, git_exe: str
) -> PushScanBinding:
    if binding.route == "generic":
        return _resolve_generic_scan_binding(
            binding.remote, binding.destination, binding.source_oid,
            repository_workdir, git_exe,
        )
    object_format = _detect_git_object_format(
        repository_workdir, git_exe, "PRG-RECEIPT-MISMATCH"
    )
    head_proc = subprocess.run(
        [git_exe, "rev-parse", "--verify", "HEAD^{commit}"],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
        cwd=repository_workdir,
    )
    rows = head_proc.stdout.splitlines()
    if head_proc.returncode or len(rows) != 1 or not object_format.matches(rows[0]):
        raise PrRouteDenied("PRG-RECEIPT-MISMATCH")
    head = rows[0].lower()
    return PushScanBinding("strict", binding.remote, binding.destination, head, head)


def _run_authoritative_scan(
    binding: PushScanBinding, repository_workdir: str, git_exe: str
) -> ConsumedAuthoritativeEvidence:
    prefix = "PGG" if binding.route == "generic" else "PRG"
    fds: tuple[int, ...] = ()
    try:
        fds, closure_before = _capture_source_closure()
        interpreter_before = _interpreter_identity()
        if closure_before.interpreter_identity != interpreter_before:
            raise ValueError("interpreter-capture")
    except Exception:
        for fd in fds:
            os.close(fd)
        raise PrRouteDenied(prefix + "-SCAN-PROVENANCE") from None
    invocation_id = secrets.token_hex(32)
    attempt_id = secrets.token_hex(16)
    argv = (
        interpreter_before.absolute_resolved_path, "-I", "-c", _SCAN_BOOTSTRAP,
        "--gate-git-executable", git_exe,
        "--range", binding.remote, binding.destination,
        "--range-source", binding.source_oid,
    )
    pending = PendingScanInvocation(
        invocation_id, attempt_id, binding, closure_before,
        interpreter_before, argv, object(),
    )
    try:
        launched, records = _run_snapshot_child(
            pending, _closure_payload(closure_before), repository_workdir
        )
        try:
            closure_after = _recheck_source_closure(fds, closure_before)
            interpreter_after = _interpreter_identity()
        except Exception:
            raise PrRouteDenied(prefix + "-SCAN-IDENTITY-DRIFT") from None
        if interpreter_after != interpreter_before:
            raise PrRouteDenied(prefix + "-SCAN-IDENTITY-DRIFT")
        records = tuple(replace(record,
            closure_after=closure_after,
            interpreter_identity_after=interpreter_after,
            provenance_verdict="trusted",
        ) for record in records)
        try:
            binding_after = _refresh_scan_binding(
                binding, repository_workdir, git_exe
            )
        except PrRouteDenied:
            raise
        except Exception:
            mismatch = "PGG-RANGE-TIP-BINDING" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
            raise PrRouteDenied(mismatch) from None
        settlement = pending.settlement
        certificate_tick = (
            settlement.certificate.verified_at_monotonic_tick
            if isinstance(settlement, GateSettlement) and settlement.certificate is not None
            else 0.0
        )
        freshness_tick = max(time.monotonic(), certificate_tick + 1e-9)
        return pending.correlate_and_consume_once(
            launched, records, closure_after, interpreter_after,
            binding_after, freshness_tick,
        )
    finally:
        for fd in fds:
            os.close(fd)


def _run_text(
    argv: list[str],
    deadline: float,
    failure_id: str,
    repository_workdir: str,
    *,
    accepted_codes: tuple[int, ...] = (0,),
) -> tuple[int, str]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PrRouteDenied(failure_id)
    result = _run_process(argv, remaining, repository_workdir)
    if result is None or result.returncode not in accepted_codes:
        raise PrRouteDenied(failure_id)
    try:
        return result.returncode, result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise PrRouteDenied(failure_id) from None


def _normalize_repository_workdir(repository_workdir: str) -> str:
    if type(repository_workdir) is not str or not repository_workdir:
        raise PrRouteDenied("PRG-WORKDIR-INVALID")
    try:
        selected = Path(repository_workdir).resolve(strict=True)
    except (OSError, RuntimeError):
        raise PrRouteDenied("PRG-WORKDIR-INVALID") from None
    if not selected.is_dir() or str(selected) != repository_workdir:
        raise PrRouteDenied("PRG-WORKDIR-INVALID")
    return repository_workdir


def _prove_repository_root(repository_workdir: str, git_exe: str) -> str:
    selected = Path(repository_workdir)
    _, top_text = _run_text(
        [git_exe, "rev-parse", "--show-toplevel"],
        time.monotonic() + PROCESS_TIMEOUT_SECONDS,
        "PRG-WORKDIR-INVALID",
        repository_workdir,
    )
    rows = top_text.splitlines()
    if len(rows) != 1:
        raise PrRouteDenied("PRG-WORKDIR-INVALID")
    try:
        top = Path(rows[0]).resolve(strict=True)
    except (OSError, RuntimeError):
        raise PrRouteDenied("PRG-WORKDIR-INVALID") from None
    if top != selected:
        raise PrRouteDenied("PRG-WORKDIR-INVALID")
    return repository_workdir


def _validate_repository_workdir(repository_workdir: str, git_exe: str) -> str:
    return _prove_repository_root(
        _normalize_repository_workdir(repository_workdir), git_exe
    )


def _strict_json(text: str, expected_type: type, failure_id: str):
    def no_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    try:
        parsed = json.loads(text, object_pairs_hook=no_duplicates)
    except (json.JSONDecodeError, ValueError):
        raise PrRouteDenied(failure_id) from None
    if not isinstance(parsed, expected_type):
        raise PrRouteDenied(failure_id)
    return parsed


def _required_text(value: object, failure_id: str, *, cap: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > cap or "\x00" in value:
        raise PrRouteDenied(failure_id)
    return value


def _required_oid(
    value: object,
    failure_id: str,
    object_format: GitObjectFormat | None = None,
) -> str:
    cap = object_format.hex_length if object_format is not None else 64
    text = _required_text(value, failure_id, cap=cap)
    if not (
        object_format.matches(text)
        if object_format is not None
        else _SUPPORTED_OID_REGEX.fullmatch(text)
    ):
        raise PrRouteDenied(failure_id)
    return text.lower()


def _repo_identity_from_url(raw_url: str) -> str | None:
    if not raw_url or len(raw_url) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in raw_url):
        return None
    if "%" in raw_url or "?" in raw_url or "#" in raw_url:
        return None
    owner = repo = ""
    scp = re.fullmatch(r"git@github\.com:([^/]+)/([^/]+)", raw_url)
    if scp:
        owner, repo = scp.groups()
    else:
        try:
            parsed = urlsplit(raw_url)
            if parsed.hostname != "github.com" or parsed.port is not None:
                return None
        except ValueError:
            return None
        if parsed.scheme == "https":
            if parsed.username is not None or parsed.password is not None:
                return None
        elif parsed.scheme == "ssh":
            if parsed.username != "git" or parsed.password is not None:
                return None
        else:
            return None
        parts = parsed.path.split("/")
        if len(parts) != 3 or parts[0] != "":
            return None
        owner, repo = parts[1], parts[2]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if (
        owner in (".", "..")
        or repo in (".", "..")
        or not REPO_COMPONENT_REGEX.fullmatch(owner)
        or not REPO_COMPONENT_REGEX.fullmatch(repo)
    ):
        return None
    return f"{owner}/{repo}"


def _repo_record(value: object, expected: str, failure_id: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise PrRouteDenied(failure_id)
    repo_id = _required_text(value.get("id"), failure_id, cap=256)
    if not NODE_ID_REGEX.fullmatch(repo_id):
        raise PrRouteDenied(failure_id)
    name = _required_text(value.get("nameWithOwner"), failure_id, cap=201)
    if name.casefold() != expected.casefold():
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    url = _required_text(value.get("url"), failure_id, cap=512)
    if url.casefold() != f"https://github.com/{name}".casefold():
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    default_ref = value.get("defaultBranchRef")
    if not isinstance(default_ref, dict):
        raise PrRouteDenied(failure_id)
    default_name = _required_text(default_ref.get("name"), failure_id, cap=255)
    return repo_id, default_name


def _verify_pr_oracle(
    grant: ActivePrGrant, literal: LiteralPushCommand, repository_workdir: str
) -> tuple[PushTarget, str]:
    deadline = time.monotonic() + ORACLE_TIMEOUT_SECONDS
    git_exe = literal.executable
    gh_exe = _resolve_executable("gh", repository_workdir)
    if gh_exe is None:
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    target = literal.target
    object_format = _detect_git_object_format(
        repository_workdir,
        git_exe,
        "PRG-BINDING-DRIFT",
        deadline=deadline,
    )

    fields = (
        "id,number,url,state,closed,mergedAt,baseRefName,baseRefOid,"
        "headRefName,headRefOid,headRepository,headRepositoryOwner"
    )
    _, pr_text = _run_text(
        [gh_exe, "pr", "view", grant.url, "--json", fields],
        deadline,
        "PRG-PR-UNAVAILABLE",
        repository_workdir,
    )
    pr = _strict_json(pr_text, dict, "PRG-PR-UNAVAILABLE")
    pr_url = pr.get("url")
    url_match = PR_URL_REGEX.fullmatch(pr_url) if isinstance(pr_url, str) else None
    if url_match is None or pr.get("number") != grant.number:
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    if grant.owner and pr_url != grant.url:
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    owner = url_match.group("owner")
    repo = url_match.group("repo")
    pr_id = _required_text(pr.get("id"), "PRG-BINDING-DRIFT", cap=256)
    if not NODE_ID_REGEX.fullmatch(pr_id):
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    if pr.get("state") != "OPEN" or pr.get("closed") is not False or pr.get("mergedAt") is not None:
        raise PrRouteDenied("PRG-PR-STATE")
    base_ref = _required_text(pr.get("baseRefName"), "PRG-BINDING-DRIFT", cap=255)
    _required_oid(pr.get("baseRefOid"), "PRG-BINDING-DRIFT", object_format)
    head_ref = _required_text(pr.get("headRefName"), "PRG-BINDING-DRIFT", cap=255)
    if not _portable_pr_head_ref(head_ref):
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    head_oid = _required_oid(pr.get("headRefOid"), "PRG-BINDING-DRIFT", object_format)
    head_repo = pr.get("headRepository")
    head_owner = pr.get("headRepositoryOwner")
    if not isinstance(head_repo, dict) or not isinstance(head_owner, dict):
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    head_repo_id = _required_text(head_repo.get("id"), "PRG-BINDING-DRIFT", cap=256)
    head_repo_name = _required_text(head_repo.get("name"), "PRG-BINDING-DRIFT", cap=100)
    head_owner_login = _required_text(head_owner.get("login"), "PRG-BINDING-DRIFT", cap=100)
    head_name = f"{head_owner_login}/{head_repo_name}"
    if not REPO_COMPONENT_REGEX.fullmatch(head_owner_login) or not REPO_COMPONENT_REGEX.fullmatch(head_repo_name):
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    if target.head_ref != head_ref:
        raise PrRouteDenied("PRG-COMMAND-SHAPE")

    repo_fields = "id,nameWithOwner,defaultBranchRef,url"
    _, base_repo_text = _run_text(
        [gh_exe, "repo", "view", f"{owner}/{repo}", "--json", repo_fields],
        deadline,
        "PRG-PR-UNAVAILABLE",
        repository_workdir,
    )
    _, head_repo_text = _run_text(
        [gh_exe, "repo", "view", head_name, "--json", repo_fields],
        deadline,
        "PRG-PR-UNAVAILABLE",
        repository_workdir,
    )
    base_record = _strict_json(base_repo_text, dict, "PRG-PR-UNAVAILABLE")
    head_record = _strict_json(head_repo_text, dict, "PRG-PR-UNAVAILABLE")
    _, base_default = _repo_record(base_record, f"{owner}/{repo}", "PRG-BINDING-DRIFT")
    current_head_repo_id, head_default = _repo_record(head_record, head_name, "PRG-BINDING-DRIFT")
    if current_head_repo_id != head_repo_id:
        raise PrRouteDenied("PRG-BINDING-DRIFT")

    _, ref_check = _run_text(
        [git_exe, "check-ref-format", "--branch", head_ref], deadline,
        "PRG-DESTINATION-UNSAFE", repository_workdir,
    )
    if ref_check.strip() != head_ref:
        raise PrRouteDenied("PRG-DESTINATION-UNSAFE")
    if target.destination == "refs/heads/main" or head_ref in (base_ref, base_default, head_default):
        raise PrRouteDenied("PRG-DESTINATION-UNSAFE")

    encoded_ref = quote(head_ref, safe="")
    _, branch_text = _run_text(
        [gh_exe, "api", "--hostname", "github.com", f"repos/{head_name}/branches/{encoded_ref}"],
        deadline,
        "PRG-PR-UNAVAILABLE",
        repository_workdir,
    )
    branch = _strict_json(branch_text, dict, "PRG-PR-UNAVAILABLE")
    if branch.get("name") != head_ref or branch.get("protected") is not False:
        raise PrRouteDenied("PRG-DESTINATION-UNSAFE")
    _, rules_text = _run_text(
        [gh_exe, "api", "--hostname", "github.com", f"repos/{head_name}/rules/branches/{encoded_ref}"],
        deadline,
        "PRG-PR-UNAVAILABLE",
        repository_workdir,
    )
    rules = _strict_json(rules_text, list, "PRG-PR-UNAVAILABLE")
    if rules:
        raise PrRouteDenied("PRG-DESTINATION-UNSAFE")

    _, expanded_urls = _run_text(
        [git_exe, "remote", "get-url", "--push", "--all", target.remote],
        deadline,
        "PRG-REMOTE-MISMATCH",
        repository_workdir,
    )
    urls = expanded_urls.splitlines()
    if len(urls) != 1 or not urls[0]:
        raise PrRouteDenied("PRG-REMOTE-MISMATCH")
    remote_identity = _repo_identity_from_url(urls[0])
    if remote_identity is None or remote_identity.casefold() != head_name.casefold():
        raise PrRouteDenied("PRG-REMOTE-MISMATCH")

    config_key = f"remote.{target.remote}.pushurl"
    code, raw_pushurl = _run_text(
        [git_exe, "config", "--get-all", config_key],
        deadline,
        "PRG-REMOTE-MISMATCH",
        repository_workdir,
        accepted_codes=(0, 1),
    )
    if code == 1:
        _, raw_pushurl = _run_text(
            [git_exe, "config", "--get-all", f"remote.{target.remote}.url"],
            deadline,
            "PRG-REMOTE-MISMATCH",
            repository_workdir,
        )
    raw_urls = raw_pushurl.splitlines()
    if len(raw_urls) != 1 or raw_urls[0] != urls[0]:
        raise PrRouteDenied("PRG-REMOTE-MISMATCH")

    _, remote_head_text = _run_text(
        [git_exe, "ls-remote", "--heads", target.remote, target.destination],
        deadline,
        "PRG-BRANCH-DRIFT",
        repository_workdir,
    )
    remote_rows = remote_head_text.splitlines()
    if len(remote_rows) != 1:
        raise PrRouteDenied("PRG-BRANCH-DRIFT")
    remote_parts = remote_rows[0].split("\t")
    if (
        len(remote_parts) != 2
        or remote_parts[1] != target.destination
        or not object_format.matches(remote_parts[0])
    ):
        raise PrRouteDenied("PRG-BRANCH-DRIFT")
    if remote_parts[0].lower() != head_oid:
        raise PrRouteDenied("PRG-BRANCH-DRIFT")

    _, local_head_text = _run_text(
        [git_exe, "rev-parse", "--verify", "HEAD"], deadline,
        "PRG-RECEIPT-MISMATCH", repository_workdir,
    )
    local_head_rows = local_head_text.splitlines()
    if len(local_head_rows) != 1 or not object_format.matches(local_head_rows[0]):
        raise PrRouteDenied("PRG-RECEIPT-MISMATCH")
    return target, local_head_rows[0].lower()


def _build_parsed_transcript_commands(
    entries: list[dict],
) -> tuple[ParsedTranscriptCommand, ...]:
    parsed_commands: list[ParsedTranscriptCommand] = []
    for entry_index, entry in enumerate(entries):
        for occurrence_index, occurrence in enumerate(
            extract_model_shell_command_occurrences(entry)
        ):
            resolution = resolve_command_dialect(occurrence.tool_name)
            root_occurrence = (
                f"transcript:{entry_index}:{occurrence_index}:{occurrence.call_id}"
            )
            parsed_commands.append(ParsedTranscriptCommand(
                entry_index,
                occurrence_index,
                occurrence.call_id,
                occurrence.tool_name,
                resolution.dialect,
                resolution.exact,
                parse_transcript_command(
                    occurrence.command_text, occurrence.tool_name,
                    root_occurrence, occurrence_index,
                ),
            ))
    return tuple(parsed_commands)


def _correlate_publication_safety_observations(
    entries: list[dict],
    parsed_commands: tuple[ParsedTranscriptCommand, ...],
) -> tuple[UntrustedTranscriptScanObservation, ...]:
    call_positions: dict[str, list[int]] = {}
    for index, entry in enumerate(entries):
        for call_id, _text in extract_model_tool_calls_with_ids(entry):
            call_positions.setdefault(call_id, []).append(index)
    results: dict[str, list[tuple[int, object]]] = {}
    for index, entry in enumerate(entries):
        for result in extract_tool_outputs_with_ids(entry):
            results.setdefault(result.call_id, []).append((index, result))
    scan_calls: dict[tuple[str, int], ParsedTranscriptCommand] = {}
    for parsed_command in parsed_commands:
        if parsed_command.parsed.scan_execution:
            scan_calls[(parsed_command.call_id, parsed_command.entry_index)] = parsed_command
    observations: list[UntrustedTranscriptScanObservation] = []
    for (call_id, call_position), parsed_command in scan_calls.items():
        if call_positions.get(call_id) != [call_position]:
            observations.append(UntrustedTranscriptScanObservation(
                call_id, call_position, None, "call-collision",
                PublicationSafetyObservation("none", None),
            ))
            continue
        matching = results.get(call_id, [])
        if len(matching) != 1:
            observations.append(UntrustedTranscriptScanObservation(
                call_id, call_position, None,
                "result-missing" if not matching else "result-collision",
                PublicationSafetyObservation("none", None),
            ))
            continue
        result_position, result = matching[0]
        if result_position <= call_position:
            observations.append(UntrustedTranscriptScanObservation(
                call_id, call_position, result_position, "result-order",
                PublicationSafetyObservation("none", None),
            ))
            continue
        if result.execution_status != NO_OBSERVED_FAILURE:
            observations.append(UntrustedTranscriptScanObservation(
                call_id, call_position, result_position, "result-status",
                PublicationSafetyObservation("none", None),
            ))
            continue
        observation = parse_publication_safety_observation(result.output_text)
        if observation.kind == "valid-v3":
            receipt = observation.receipt
            range_binding = project_scan_range_binding(parsed_command.parsed)
            if (
                receipt is None
                or range_binding is None
                or range_binding != (receipt.remote, receipt.destination)
            ):
                observation = PublicationSafetyObservation("malformed", None)
        observations.append(UntrustedTranscriptScanObservation(
            call_id,
            call_position,
            result_position,
            "valid",
            observation,
        ))
    return tuple(observations)


def _resolve_generic_scan_binding(
    remote: str, destination: str, source: str, repository_workdir: str,
    git_exe: str,
) -> PushScanBinding:
    if not source:
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    object_format = _detect_git_object_format(
        repository_workdir, git_exe, "PGG-RANGE-TIP-BINDING"
    )
    source_proc = subprocess.run(
        [git_exe, "rev-parse", "--verify", source],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
        cwd=repository_workdir,
    )
    source_rows = source_proc.stdout.splitlines()
    if (
        source_proc.returncode
        or len(source_rows) != 1
        or not object_format.matches(source_rows[0])
    ):
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    source_oid = source_rows[0].lower()
    type_proc = subprocess.run(
        [git_exe, "cat-file", "-t", source_oid],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
        cwd=repository_workdir,
    )
    if type_proc.returncode or type_proc.stdout.strip() != "commit":
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    head_proc = subprocess.run(
        [git_exe, "rev-parse", "--verify", "HEAD^{commit}"],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
        cwd=repository_workdir,
    )
    head_rows = head_proc.stdout.splitlines()
    if (
        head_proc.returncode
        or len(head_rows) != 1
        or not object_format.matches(head_rows[0])
    ):
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    return PushScanBinding(
        "generic", remote, destination, source_oid, head_rows[0].lower()
    )


def _evaluate_active_pr_route(
    grant: ActivePrGrant,
    command: str,
    dialect: str,
    parsed: ShellParseResult,
    repository_workdir: str,
    repository_workdir_source: str,
) -> bool:
    try:
        effective = parsed.effective_publications
        if (
            parsed.strict_projection.status != "canonical"
            or len(effective.records) != 1
            or effective.records[0].kind != "DIRECT"
        ):
            raise PrRouteDenied("PRG-COMMAND-SHAPE")
        dialect = _pr_command_dialect(dialect)
        literal = _parse_pr_literal_shape(parsed, dialect)
        if literal.repository_root is None:
            repository_workdir = _normalize_repository_workdir(
                repository_workdir
            )
        else:
            command_root = _normalize_repository_workdir(
                literal.repository_root
            )
            if repository_workdir_source == "tool":
                tool_root = _normalize_repository_workdir(repository_workdir)
                if tool_root != command_root:
                    raise PrRouteDenied("PRG-WORKDIR-INVALID")
            elif repository_workdir_source != "envelope":
                raise PrRouteDenied("PRG-WORKDIR-INVALID")
            repository_workdir = command_root
        git_exe = _resolve_executable("git", repository_workdir)
        if git_exe is None:
            raise PrRouteDenied("PRG-REMOTE-MISMATCH")
        literal = _bind_pr_literal_executable(literal, git_exe)
        repository_workdir = _prove_repository_root(
            repository_workdir, git_exe
        )
        target, local_head = _verify_pr_oracle(
            grant, literal, repository_workdir
        )
        binding = PushScanBinding(
            "strict", target.remote, target.destination, local_head, local_head
        )
        _run_authoritative_scan(binding, repository_workdir, git_exe)
        return True
    except PrRouteDenied:
        raise
    except Exception:
        raise PrRouteDenied("PRG-INTERNAL") from None




def evaluate_heavy(preflight: PreflightResult) -> bool:
    """Evaluate only transcript history, PR, scan, receipt and deny policy."""
    validate_preflight_result(preflight)
    history_entries, history_status = read_transcript_history(
        preflight.transcript_path,
        byte_cap=TRANSCRIPT_HISTORY_BYTE_CAP,
        record_cap=TRANSCRIPT_HISTORY_RECORD_CAP,
        line_byte_cap=TRANSCRIPT_HISTORY_LINE_BYTE_CAP,
    )
    suffix_recovery = history_status == HISTORY_STATUS_LIMIT
    if suffix_recovery:
        history_entries, history_status = _read_stable_transcript_suffix(
            preflight.transcript_path
        )
    if history_status != HISTORY_STATUS_FOUND:
        raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE")
    pr_state, pr_grant = _derive_pr_grant(
        history_entries, preflight.repository_workdir
    )
    if pr_state == "malformed":
        raise PrRouteDenied("PRG-AUTH-MALFORMED")
    if pr_state == "active" and pr_grant is not None:
        return _evaluate_active_pr_route(
            pr_grant, preflight.command, preflight.dialect, preflight.parsed,
            preflight.repository_workdir, preflight.repository_workdir_source,
        )
    if suffix_recovery:
        raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE")
    grammar = preflight.generic_decision
    if preflight.push_instruction:
        if grammar.status != "PGG-ADMISSIBLE" or grammar.binding is None:
            raise PrRouteDenied(grammar.status)
        remote, destination, source = grammar.binding
        repository_workdir = _normalize_repository_workdir(
            preflight.repository_workdir
        )
        git_exe = _resolve_executable("git", repository_workdir)
        if git_exe is None:
            raise PrRouteDenied("PRG-WORKDIR-INVALID")
        repository_workdir = _prove_repository_root(
            repository_workdir, git_exe
        )
        binding = _resolve_generic_scan_binding(
            remote, destination, source, repository_workdir, git_exe
        )
        _run_authoritative_scan(binding, repository_workdir, git_exe)
        return True
    return False

def _format_gate_denial(failure_id: str) -> str:
    if failure_id not in SCAN_DENIAL_REASONS:
        failure_id = "PRG-INTERNAL"
    remediation = SCAN_DENIAL_REASONS.get(
        failure_id,
        "Retry only after the publication gate can complete its checks normally.",
    )
    scope = (
        "Generic scan-derived publication denied"
        if failure_id.startswith("PGG-")
        else "PR-scoped publication denied"
    )
    return f"{failure_id}: {scope}. {remediation}"


def compose_gate_result(preflight: PreflightResult) -> int:
    """Compose one validated preflight into the stable gate result payload."""
    try:
        result = validate_preflight_result(preflight)
    except Exception:
        result = PreflightResult(
            "DEFER", "PFP-DENY-INTERNAL", "RENDER_DENY", None, None, "",
            None, None, None, False, None,
        )
    if result.outcome == "ALLOW_FINAL":
        return 0

    failure_id: str | None = result.failure_id
    if result.continuation == "EVALUATE_HEAVY":
        try:
            if evaluate_heavy(result):
                return 0
        except PrRouteDenied as exc:
            failure_id = exc.failure_id
        except Exception:
            pass

    # Deny. PR-route failures intentionally expose only a stable identifier
    # and safe remediation; subprocess output, command text, paths, remotes,
    # and exception details never enter this payload.
    pr_reasons = {
        **SCAN_DENIAL_REASONS,
        "PRG-AUTH-MALFORMED": "Use the exact version-1 PR approval or revocation line in a genuine user message.",
        "PRG-TRANSCRIPT-UNAVAILABLE": "Retry from a readable current session transcript; summaries cannot authorize publication.",
        "PRG-COMMAND-SHAPE": "Use one exact absolute Git literal: `git push <remote> HEAD:refs/heads/<head>` or `git -C <absolute-root> push <remote> HEAD:refs/heads/<head>`.",
        "PRG-PR-UNAVAILABLE": "Restore authenticated GitHub state access, then retry so the pull request can be checked afresh.",
        "PRG-PR-STATE": "The pull request is not open; obtain a new grant only for an open pull request.",
        "PRG-BINDING-DRIFT": "Refresh the pull-request binding and retry with a current exact grant if needed.",
        "PRG-DESTINATION-UNSAFE": "Choose the current unprotected non-default pull-request head branch.",
        "PRG-REMOTE-MISMATCH": "Use one direct GitHub remote for the current pull-request head repository.",
        "PRG-WORKDIR-INVALID": "Use one explicit absolute repository root for the current push tool call.",
        "PRG-BRANCH-DRIFT": "Refresh remote branch state, then retry the same push for a fresh gate-owned check.",
        "PRG-RECEIPT-MISSING": "Retry the push so the gate owns a fresh non-empty publication-safety check.",
        "PRG-RECEIPT-MISMATCH": "Correct the remote, destination, current HEAD, and tip binding, then retry the same push.",
        "PRG-RECEIPT-USED": "The prior receipt is consumed; retry the push for a fresh gate-owned check.",
        "PRG-INTERNAL": "Retry only after the publication gate can complete its checks normally.",
        "PGG-COMPOUND-CONTEXT": "Run one direct push as a solitary shell command before using scan-derived credit.",
        "PGG-LEXICAL-NORMALIZATION": "Use one literal unnormalized push command.",
        "PGG-OPTION-ARITY": "Use only complete documented push option forms.",
        "PGG-PARSE-UNCERTAIN": "Use one exact solitary direct push command.",
        "PGG-REPOSITORY-REDIRECT": "Use the ambient repository without command-local repository redirection.",
        "PGG-ENV-PREFIX": "Run the push without an environment-assignment prefix.",
        "PGG-GIT-GLOBAL-OPTION": "Run the push without Git global options before the push subcommand.",
        "PGG-PUSH-OPTION": "Use only the documented output-only push options with scan-derived credit.",
        "PGG-REMOTE-CARDINALITY": "Name exactly one remote and one refspec.",
        "PGG-REFSPEC-CARDINALITY": "Name exactly one remote and one refspec.",
        "PGG-DESTINATION-SHAPE": "Use a refspec with a non-empty destination.",
        "PGG-RANGE-BINDING": "Correct the remote and destination binding, then retry the same push.",
        "PGG-RANGE-TIP-BINDING": "Push the current HEAD commit directly and retry for a fresh gate-owned check.",
        "PGG-RANGE-RECEIPT-VERSION": "Retry the push so the gate emits one complete-history version-3 receipt.",
        "PGG-RECEIPT-USED": "The prior receipt is consumed; retry the push for a fresh gate-owned check.",
    }
    if failure_id is not None:
        if failure_id not in pr_reasons:
            failure_id = "PRG-INTERNAL"
        if failure_id in SCAN_DENIAL_REASONS:
            reason = _format_gate_denial(failure_id)
        else:
            remediation = pr_reasons.get(failure_id, pr_reasons["PRG-INTERNAL"])
            scope = "Generic scan-derived publication denied" if failure_id.startswith("PGG-") else "PR-scoped publication denied"
            reason = f"{failure_id}: {scope}. {remediation}"
    else:
        reason = (
        "Git-push publication gate: this Bash command runs `git push` (an "
        "irreversible publication), but this turn shows neither the per-turn "
        "user approval marker nor a successful gate-owned canonical range "
        "scan for this pending push.\n\n"
        "Publication requires human review PLUS a leak-check of the content "
        "being published (Publication safety governance). Pick one before "
        "retrying:\n\n"
        "  (a) Human exception: if the user has NOT explicitly approved this "
        "push, STOP, report readiness to push, and ask the user to approve. "
        "The user approves by including `[approve-publication]` in their next "
        "message; then retry. The marker is honored only from the user's own "
        "message and only for that turn. It is an exception, not the ordinary "
        "recovery route for an already-committed change.\n\n"
        "  (b) If the user already instructed you to push in their last "
        "message, retry one admissible solitary push. The gate itself runs one "
        "fresh non-empty version-3 complete-history range scan from the canonical sibling "
        "scanner, using an immutable in-memory source snapshot and its current "
        "trusted interpreter. Manual or transcript-visible scanner calls are "
        "diagnostic only and cannot authorize publication. If this route "
        "denies, use its stable failure identifier and fixed remediation; do "
        "not supply raw findings, command text, paths, or scanner output.\n\n"
        "  (c) To test what would be sent without publishing, use "
        "a standalone, unambiguous long `git push --dry-run`; option values, "
        "negated/short forms, and uncertain spellings are not fast-allowed.\n\n"
        "This hook is a BACKSTOP for the human-review-before-push rule, not a "
        "replacement for it. Do not work around it by wrapping the push in a "
        "script or delegating it to a subagent — that violates the same rule "
        "this gate protects."
        )

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(payload))
    return 0


def main(preflight: PreflightResult | None = None) -> int:
    try:
        result = (
            build_preflight_from_stdin()
            if preflight is None
            else validate_preflight_result(preflight)
        )
    except Exception:
        result = PreflightResult(
            "DEFER", "PFP-DENY-INTERNAL", "RENDER_DENY", None, None, "",
            None, None, None, False, None,
        )
    return compose_gate_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
