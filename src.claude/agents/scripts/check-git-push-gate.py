#!/usr/bin/env python3
"""Git-push publication gate (PreToolUse, BLOCKING) — structural backstop for
the human-review-before-push rule.

WHAT THIS DENIES: a real non-dry `git push` without applicable genuine-user
publication authority and one fresh gate-owned canonical range scan for the
exact pending push. The gate derives the only scanner
producer as one held gate plus a fixed seven-module closure (`hook_common.py`, the
machine-path classifier, the POSIX process-group helper, the Windows Job helper,
`check-publication-safety.py`, the reviewed-publication policy owner, and the
linked-runtime-subroot helper), captures policy through those held bytes, executes
the complete closure with its current trusted interpreter, and binds the exactly
correlated typed result to remote, destination, source, current HEAD, and receipt
tip. Scanner-
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

Generic publication also receives the genuine original approval and its exact
reviewed source/root/endpoint/destination. Neutral steering cannot expire or
widen that pending operation. Its derived selector index is not authority:
original user/subject records and subsequent actual controls are requalified.
The PR provider oracle remains separate. Command-visible redirects and
payload-expanding options remain prohibited.

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
     Incomplete analysis with no effective publication record or malformed-minus-C
     candidate returns ABSTAIN, preserving uncertainty without vetoing ordinary
     work. Abstention certifies neither exact effects nor publication authority;
     it supplies no dry-run, human-approval, grant, or scan credit. The analysis
     dialect does not establish the actual interpreter. Positive candidates
     continue through the existing publication checks even under uncertainty.
  5. Every exact direct push proving a standalone positive long `--dry-run`,
     with no negation, ambiguous option role, or conservative candidate → exit 0.
  6. Missing, unreadable, invalid, or unstable required history denies with
     `PRG-TRANSCRIPT-UNAVAILABLE`. Reduce the complete stable JSONL history in
     forward order, binding both bounded-read passes to its opened descriptor's
     initial byte size. Complete history alone supplies no publication authority;
     active grants still enter the unchanged strict route.
  7. Current and recovered generic input enter the same original-control
     receiving owner. Genuine user approval must identify the actually reviewed
     immutable operation. Structured input retains its actual Q/A correlation;
     explicit plain user scope needs neither a question nor an independent
     packet. Neutral steering preserves pending O; changed scope, actual
     revocation/fulfillment or unresolved effects cannot inherit it. Original
     occurrence and whole-answer validation remain P's owner. Reports, index
     labels, questions and assistant/tool/file text cannot supply approval.
  8. Derive the latest exact PR grant/revoke/malformed state from the complete
     bounded readable transcript. A malformed reserved signal denies. An
     active grant runs only the strict PR route: fresh GitHub PR/Git identity
     binding plus one fresh unused non-empty range receipt bound to
     remote, full destination, and local HEAD tip. Every active-route failure
     denies without generic fallback.
  9. Exact pending generic consent must additionally pass the unchanged closed
     command/root/executable binding and one NEW gate-owned nonempty complete
     version-3 graph scan. Currentness is checked again before allowing the
     pending tool. Diagnostic transcript scans cannot authorize. Consuming the
     scan does not mean Git executed or fulfilled the human's operation.
  10. Otherwise — including when the decision path raises an uncaught exception (see
     the "A CRASH WHILE DECIDING" note above and `evaluate_push`'s own
     docstring; 2026-07-26 hardening) — emit a structured `permissionDecision:
     "deny"` payload with exact compliance instructions. Always exit 0 (the
     decision is carried by the stdout payload, not the exit code).

WHAT THE GENERIC NON-PR ROUTE STILL DOES NOT COVER (disclosed, not silently assumed away):
  - UNMARKED COPIED PROSE. Formal quotation/data contributes neither generic
    signal, but unmarked prose is byte-identical to direct prose. The public
    fixed marker and existing instruction vocabulary cannot infer intent.
    A copied denial's code-wrapped marker is excluded while independently
    unquoted push prose can still request the mandatory scan completion.
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
import binascii
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
import types
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Callable, NamedTuple
from urllib.parse import quote, unquote_to_bytes, urlsplit

from hook_common import (
    CURRENT_TURN_BYTE_CAP,
    HISTORY_STATUS_ABSENT,
    HISTORY_STATUS_FOUND,
    HISTORY_STATUS_IDENTITY_DRIFT,
    HISTORY_STATUS_INVALID,
    HISTORY_STATUS_LIMIT,
    HISTORY_STATUS_RESOURCE_UNAVAILABLE,
    HISTORY_STATUS_UNREADABLE,
    NO_OBSERVED_FAILURE,
    STATUS_FOUND,
    extract_model_shell_command_occurrences,
    extract_model_tool_calls_with_ids,
    extract_tool_outputs_with_ids,
    extract_native_control_calls,
    extract_native_control_results,
    extract_native_command_observation,
    hold_native_history_source,
    NativeHistoryIdentity,
    NativeHistorySourceError,
    extract_text,
    is_assistant_message,
    is_user_message,
    parse_envelope,
    read_transcript_history,
    read_stdin_utf8,
    scan_current_turn_boundary,
)


from git_push_gate_preflight import (
    PreflightResult,
    TranscriptDiagnostic,
    WorkdirDiagnostic,
    validate_preflight_result,
    validate_transcript_diagnostic,
    validate_workdir_diagnostic,
    build_preflight_from_stdin,
    ShellParseResult,
    absolute_literal_root_context,
    PrRouteDenied,
    resolve_command_dialect,
    parse_transcript_command,
    parse_native_argument_vector,
    project_scan_range_binding,
    extract_publication_user_reply,
    is_simple_pr_approval,
    normalize_publication_approval_text,
    parse_publication_pr_grant,
    publication_reply_has_push_instruction,
    classify_generic_push,
    PublicationUserReply,
)


# Genuine-user signals never replace original-scope/lifetime receiving or the
# mandatory command, binding and fresh authoritative-scan checks.
# User-side only by design: assistant prose can be steered by injected content
# (see the consultant continuation-prompt untrusted-data rule). Neither this
# marker nor [skip-bugfix-discipline] gains authority from the model's own reply.

PR_URL_REGEX = re.compile(
    r"^(?P<url>https://github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?)/"
    r"(?P<repo>[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?)/pull/"
    r"(?P<number>[1-9][0-9]*))$"
)
PR_BINDING_SIDECAR_SUFFIX = ".pr-publication-binding-v1.json"
PR_BINDING_LOCK_SUFFIX = ".lock"
PR_BINDING_SIDECAR_BYTE_CAP = 8192
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


class SimplePrIntent(NamedTuple):
    record: int
    sha256: str
    prior_scoped_grant: ActivePrGrant | None


class PrBindingState(NamedTuple):
    anchor_record: int
    anchor_sha256: str
    state: str
    repository_identity: tuple[int, int]
    remote: str
    head_ref: str
    pr_url: str | None
    pr_id: str | None
    head_repository_id: str | None


class PreparedPrPush(NamedTuple):
    literal: LiteralPushCommand
    repository_workdir: str
    git_exe: str


class VerifiedPrOracle(NamedTuple):
    target: PushTarget
    local_head: str
    pr_id: str
    head_repository_id: str


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


@dataclass(frozen=True)
class GenericPublicationSubject:
    """Reviewed scope, distinct from the invocation's technical HEAD."""

    root: str
    root_identity: tuple[int, int]
    repository_identity: tuple[int, int]
    worktree_identity: tuple[int, int]
    remote: str
    remote_identity: str
    destination: str
    object_format: str
    source_oid: str


@dataclass(frozen=True)
class GenericApprovalSelection:
    """Locators for semantic receiving; no field authenticates itself."""

    review_call_id: str | None
    review_record: int | None
    user_record: int
    question_call_id: str | None = None
    question_index: int | None = None


@dataclass(frozen=True)
class OriginalGenericApproval:
    subject: GenericPublicationSubject
    selection: GenericApprovalSelection
    user_sha256: str
    packet_sha256: str | None
    producer_kind: str
    history_sha256: str
    source_identity: NativeHistoryIdentity | None = None


@dataclass(frozen=True)
class GenericRecordEvidence:
    """Restrictive locators into actual native records, never approval flags."""

    role: str
    record: int
    record_sha256: str
    component: str
    call_id: str | None = None
    index: int | None = None
    span: tuple[int, int] | None = None


@dataclass(frozen=True)
class GenericSourceField:
    """One logical coordinate located in an actual evidence component."""

    field: str
    evidence_index: int
    span: tuple[int, int] | None = None


@dataclass(frozen=True)
class _OriginalLogicalScope:
    root: str
    repository: str
    remote: str
    remote_identity: str
    destination: str
    source_oid: str
    review_statement: str


@dataclass(frozen=True)
class _ReceivedGenericSource:
    """Source facts before current invocation or cache scope is compared."""

    scope: _OriginalLogicalScope
    selection: GenericApprovalSelection
    user_sha256: str
    packet_sha256: str | None
    producer_kind: str
    history_sha256: str


class _OriginalScopeInputError(PrRouteDenied):
    def __init__(self, coordinate: str):
        super().__init__("PGG-CONSENT-ASSOCIATION")
        self.coordinate = coordinate


@dataclass(frozen=True)
class GenericUserScopeSelection:
    """Root's semantic locators into an actual explicit plain user record.

    Spans use Python Unicode-string offsets. They identify original user data,
    not new SDK fields, an authored user frame, or a serialized permission.
    Root owns the meaning of the actual completed-review statement. Receiving
    below independently reads the genuine record and every selected value.
    """

    user_record: int
    root: str
    repository: str
    remote: str
    remote_identity: str
    destination: str
    source_oid: str
    review_statement: str
    spans: tuple[tuple[str, int, int], ...] = ()
    question_call_id: str | None = None
    question_index: int | None = None
    evidence: tuple[GenericRecordEvidence, ...] = ()
    source_fields: tuple[GenericSourceField, ...] = ()


@dataclass(frozen=True)
class GenericConsentResult:
    """Derived receiving outcome. Even pending is not publication permission."""

    state: str
    approval: OriginalGenericApproval | None
    detail: str
    direct_selection: GenericUserScopeSelection | None = None


@dataclass(frozen=True)
class _GenericControlCut:
    selection: GenericApprovalSelection | None
    intent_record: int
    intent_state: str
    pr_record: int
    commands: tuple[tuple[int, object], ...]
    opaque_calls: tuple[tuple[int, str], ...]
    model_publications: tuple[tuple[int, str, str | None], ...]
    invalid_command_records: tuple[tuple[int, object], ...]
    history_sha256: str
    history_status: str
    max_approval_record_bytes: int
    record_count: int
    execution_record: int = 0
    pr_state: str = "absent"
    pr_grant: object = None
    pr_reducer: object = None


@dataclass(frozen=True)
class GenericConsentIndex:
    """Restrictive materialization; its labels and digest are not authority."""

    user_record: int
    user_sha256: str
    source_identity: tuple[int, int]
    subject: GenericPublicationSubject
    spans: tuple[tuple[str, int, int], ...]
    question_call_id: str | None
    question_index: int | None
    history_sha256: str
    history_records: int
    evidence: tuple[GenericRecordEvidence, ...] = ()
    repository: str = ""
    review_statement: str = ""
    source_fields: tuple[GenericSourceField, ...] = ()


@dataclass(frozen=True)
class PreparedGenericPublication:
    repository_workdir: str
    git_exe: str
    binding: PushScanBinding
    subject: GenericPublicationSubject
    source_operand: str

    def requalify_binding(self) -> PushScanBinding:
        """Re-resolve this original invocation before discarding technical pins."""
        if type(self.source_operand) is not str or not self.source_operand:
            raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
        current = _resolve_generic_scan_binding(
            self.binding.remote, self.binding.destination, self.source_operand,
            self.repository_workdir, self.git_exe,
        )
        if current != self.binding:
            raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
        return current


def publication_review_packet(subject: GenericPublicationSubject) -> str:
    """Scope context for the existing review packet, never a consent record."""
    value = {
        "kind": "publication-review-v1",
        "subject": {
            "root": subject.root,
            "rootIdentity": list(subject.root_identity),
            "repositoryIdentity": list(subject.repository_identity),
            "worktreeIdentity": list(subject.worktree_identity),
            "remote": subject.remote,
            "remoteIdentity": subject.remote_identity,
            "destination": subject.destination,
            "objectFormat": subject.object_format,
            "sourceOid": subject.source_oid,
        },
    }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    _review_packet_subject(encoded)
    return encoded


def publication_review_reference(packet: str) -> str:
    return "[publication-review:" + hashlib.sha256(packet.encode("utf-8")).hexdigest() + "]"


def _review_packet_subject(packet: str) -> GenericPublicationSubject:
    value = _strict_json(packet, dict, "PGG-CONSENT-ASSOCIATION")
    if set(value) != {"kind", "subject"} or value["kind"] != "publication-review-v1":
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    subject = value["subject"]
    fields = {
        "root", "rootIdentity", "repositoryIdentity", "worktreeIdentity", "remote",
        "remoteIdentity", "destination", "objectFormat", "sourceOid",
    }
    if not isinstance(subject, dict) or set(subject) != fields:
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    for key in ("rootIdentity", "repositoryIdentity", "worktreeIdentity"):
        identity = subject[key]
        if not isinstance(identity, list) or len(identity) != 2 or any(type(n) is not int or n < 0 for n in identity):
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    if any(type(subject[key]) is not str or not subject[key] for key in fields - {"rootIdentity", "repositoryIdentity", "worktreeIdentity"}):
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    width = {"sha1": 40, "sha256": 64}.get(subject["objectFormat"])
    endpoint = urlsplit(subject["remoteIdentity"])
    if (
        width is None or re.fullmatch(r"[0-9a-f]{" + str(width) + r"}", subject["sourceOid"]) is None
        or not Path(subject["root"]).is_absolute()
        or not subject["destination"].startswith("refs/heads/")
        or not REMOTE_NAME_REGEX.fullmatch(subject["remote"])
        or endpoint.username is not None or endpoint.password is not None
    ):
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    return GenericPublicationSubject(
        subject["root"], tuple(subject["rootIdentity"]), tuple(subject["repositoryIdentity"]), tuple(subject["worktreeIdentity"]),
        subject["remote"], subject["remoteIdentity"], subject["destination"],
        subject["objectFormat"], subject["sourceOid"],
    )


def _receive_generic_original_association(
    transcript_path: str,
    selection: GenericApprovalSelection,
) -> OriginalGenericApproval:
    """Receive original records from HC; caller locators never grant consent."""
    calls: dict[str, tuple[int, object]] = {}
    review: tuple[int, tuple[str, ...]] | None = None
    approval: tuple[object, bytes] | None = None
    visible_review: list[tuple[int, str]] = []
    position = 0
    record_digests: dict[int, str] = {}
    digest = hashlib.sha256()

    def consume(entry: dict, raw: bytes) -> None:
        nonlocal position, review, approval
        position += 1
        digest.update(raw)
        if position in {selection.review_record, selection.user_record}:
            record_digests[position] = hashlib.sha256(raw).hexdigest()
        for call in extract_native_control_calls(entry):
            if call.call_id in {selection.review_call_id, selection.question_call_id}:
                if call.call_id in calls:
                    raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                calls[call.call_id] = position, call
                record_digests[position] = hashlib.sha256(raw).hexdigest()
        for result in extract_native_control_results(entry):
            if result.call_id == selection.review_call_id:
                if review is not None or position != selection.review_record:
                    raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                review = position, result.text_blocks
        if position == selection.user_record:
            if not is_user_message(entry):
                raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
            approval = extract_publication_user_reply(entry), raw
        if selection.review_record < position < selection.user_record and is_assistant_message(entry):
            visible_review.append((position, extract_text(entry)))

    _entries, status = read_transcript_history(
        transcript_path, byte_cap=None, record_cap=None, line_byte_cap=None,
        on_record=consume,
    )
    if status == HISTORY_STATUS_IDENTITY_DRIFT:
        raise PrRouteDenied("PGG-CONSENT-IDENTITY-DRIFT")
    if status != HISTORY_STATUS_FOUND:
        raise PrRouteDenied("PGG-CONSENT-HISTORY")
    if review is None or approval is None or selection.review_call_id not in calls:
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    review_position, blocks = review
    if not calls[selection.review_call_id][0] < review_position < selection.user_record:
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    packets: list[tuple[str, GenericPublicationSubject]] = []
    for block in blocks:
        try:
            subject = _review_packet_subject(block)
        except PrRouteDenied:
            continue
        packets.append((block, subject))
    if len(packets) != 1:
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    packet, subject = packets[0]
    reference = publication_review_reference(packet)
    reply, raw_user = approval
    action, _ = reply.publication_action()
    if action != "generic" and not publication_reply_has_push_instruction(reply):
        raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
    if reply.kind == "structured-answer":
        if selection.question_call_id not in calls or type(selection.question_index) is not int:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        question_position, question = calls[selection.question_call_id]
        if not review_position < question_position < selection.user_record or question.input_kind != "json":
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        if question.tool_name not in {"request_user_input_async", "functions.request_user_input_async"}:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        arguments = _strict_json(question.input_text, dict, "PGG-CONSENT-ASSOCIATION")
        questions = arguments.get("questions")
        index = selection.question_index
        if not isinstance(questions, list) or not 0 <= index < len(questions):
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        original = questions[index]
        if not isinstance(original, dict) or not isinstance(original.get("title"), str):
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        matched = []
        for item in reply.structured_items:
            locator = _strict_json(item.question_item_id, list, "PGG-CONSENT-ASSOCIATION")
            if locator == [question.tool_name, question.call_id, index]:
                matched.append(item)
        if len(matched) != 1 or matched[0].question != original["title"] or reference not in original["title"]:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        selected_answer = PublicationUserReply("plain", (matched[0].answer,))
        if selected_answer.publication_action()[0] != "generic" and not publication_reply_has_push_instruction(selected_answer):
            raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
    elif reply.kind == "plain":
        if selection.question_call_id is not None or selection.question_index is not None:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        if not any(review_position < pos < selection.user_record and reference in text for pos, text in visible_review):
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    else:
        raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
    review_evidence = GenericRecordEvidence("scope", review_position, record_digests[review_position], "result-text", selection.review_call_id, blocks.index(packet))
    selected = GenericUserScopeSelection(
        selection.user_record, subject.root, subject.remote_identity, subject.remote,
        subject.remote_identity, subject.destination, subject.source_oid, packet,
        question_call_id=selection.question_call_id, question_index=selection.question_index,
        evidence=(
            GenericRecordEvidence("approval", selection.user_record, hashlib.sha256(raw_user).hexdigest(), "answer" if reply.kind == "structured-answer" else "user-text", selection.question_call_id, selection.question_index),
            review_evidence,
            replace(review_evidence, role="completed-review"),
            GenericRecordEvidence("association", question_position, record_digests[question_position], "question", selection.question_call_id, selection.question_index)
            if reply.kind == "structured-answer" else replace(review_evidence, role="association"),
        ),
    )
    received = _receive_selected_generic_association(transcript_path, selected, subject)
    if received.history_sha256 != digest.hexdigest():
        raise PrRouteDenied("PGG-CONSENT-IDENTITY-DRIFT")
    return replace(received, packet_sha256=hashlib.sha256(packet.encode("utf-8")).hexdigest())


def _generic_control_cut(
    transcript_path: str, *, collect_lifecycle: bool = True,
    preflight: PreflightResult | None = None,
) -> _GenericControlCut:
    """Reduce the same selected finite source; there is no durable grant store."""
    calls: dict[str, int] = {}
    reviews: dict[str, tuple[str, int]] = {}
    questions: dict[str, tuple[int, object]] = {}
    visible: set[str] = set()
    commands: list[tuple[int, object]] = []
    opaque: list[tuple[int, str]] = []
    model_publications: list[tuple[int, str, str | None]] = []
    invalid_commands: list[tuple[int, object]] = []
    transcript_cwd: str | None = None
    selection: GenericApprovalSelection | None = None
    intent_record = pr_record = execution_record = position = 0
    pr_reducer = _PrGrantReducer(preflight) if preflight is not None else None
    intent_state = "no-intent"
    max_approval_record_bytes = 0
    digest = hashlib.sha256()
    reference_pattern = re.compile(r"\[publication-review:([0-9a-f]{64})\]")

    def consume(entry: dict, raw: bytes) -> None:
        nonlocal position, selection, intent_record, intent_state, pr_record, execution_record, transcript_cwd, max_approval_record_bytes
        if pr_reducer is not None:
            pr_reducer.consume(entry, raw)
        position += 1
        digest.update(raw)
        payload = entry.get("payload")
        if entry.get("type") in {"session_meta", "turn_context"} and isinstance(payload, dict):
            value = payload.get("cwd")
            transcript_cwd = value if isinstance(value, str) else None
        current_calls = {call.call_id: call for call in extract_native_control_calls(entry)}
        for call in current_calls.values():
            calls[call.call_id] = position
            if call.tool_name in {"request_user_input_async", "functions.request_user_input_async"}:
                questions[call.call_id] = position, call
            elif collect_lifecycle and call.input_kind == "raw" and call.tool_name.rsplit(".", 1)[-1] == "exec":
                opaque.append((position, call.call_id))
        for result in extract_native_control_results(entry):
            if result.call_id not in calls or calls[result.call_id] >= position:
                continue
            for block in result.text_blocks:
                # Do not interpret unrelated tool bodies as review packets.
                if not block.startswith('{"kind":"publication-review-v1",'):
                    continue
                try:
                    _review_packet_subject(block)
                except PrRouteDenied:
                    continue
                packet_digest = hashlib.sha256(block.encode("utf-8")).hexdigest()
                if packet_digest in reviews and reviews[packet_digest] != (result.call_id, position):
                    raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                reviews[packet_digest] = result.call_id, position
        command = extract_native_command_observation(entry) if collect_lifecycle else None
        if command is not None:
            commands.append((position, command))
        elif collect_lifecycle:
            params = entry.get("params") if entry.get("method") in {"item/started", "item/completed"} else None
            item = params.get("item") if isinstance(params, dict) else None
            payload = entry.get("payload") if entry.get("type") == "event_msg" else None
            core_item = payload.get("item") if isinstance(payload, dict) and payload.get("type") in {"item_started", "item_completed"} else None
            if (isinstance(item, dict) and item.get("type") == "commandExecution") or (isinstance(core_item, dict) and core_item.get("type") == "CommandExecution"):
                native_item = core_item if isinstance(core_item, dict) else item
                raw_command = native_item.get("command")
                raw_cwd = native_item.get("cwd")
                invalid_commands.append((position, {
                    "item_id": native_item.get("id"), "command": raw_command,
                    "cwd": raw_cwd, "core": isinstance(core_item, dict),
                }))
        for occurrence in extract_model_shell_command_occurrences(entry) if collect_lifecycle else ():
            parsed = parse_transcript_command(
                occurrence.command_text, occurrence.tool_name, occurrence.call_id, 0,
            )
            if not parsed.effective_publications.records:
                continue
            context = absolute_literal_root_context(parsed)
            selected_root = context[1] if context is not None else transcript_cwd
            call = current_calls.get(occurrence.call_id)
            if context is None and call is not None and call.input_kind == "json":
                try:
                    arguments = _strict_json(call.input_text, dict, "PGG-CONSENT-ASSOCIATION")
                except PrRouteDenied:
                    arguments = {}
                if isinstance(arguments.get("workdir"), str):
                    selected_root = arguments["workdir"]
            model_publications.append((position, occurrence.call_id, selected_root))
        if is_assistant_message(entry):
            visible.update(reference_pattern.findall(extract_text(entry)))
        if not is_user_message(entry):
            return
        reply = extract_publication_user_reply(entry)
        if reply.kind == "plain" and not any(reply.answers):
            return
        action, _ = reply.publication_action()
        if publication_reply_has_push_instruction(reply):
            execution_record = position
        if action == "generic" or publication_reply_has_push_instruction(reply):
            max_approval_record_bytes = max(max_approval_record_bytes, len(raw))
        if action in {"simple", "targeted", "malformed", "revoked"}:
            pr_record = position
        if action in {"malformed", "revoked"}:
            intent_state = "revoked" if action == "revoked" else "corrupt"
            intent_record, selection = position, None
        elif action == "generic" or publication_reply_has_push_instruction(reply):
            chosen: list[GenericApprovalSelection] = []
            if reply.kind == "structured-answer":
                for item in reply.structured_items:
                    selected_answer = PublicationUserReply("plain", (item.answer,))
                    if selected_answer.publication_action()[0] != "generic" and not publication_reply_has_push_instruction(selected_answer):
                        continue
                    try:
                        locator = _strict_json(item.question_item_id, list, "PGG-CONSENT-ASSOCIATION")
                    except PrRouteDenied:
                        continue
                    if len(locator) != 3 or type(locator[2]) is not int or not isinstance(locator[1], str):
                        continue
                    found = questions.get(locator[1])
                    if found is None:
                        continue
                    question_position, question = found
                    if locator[0] != question.tool_name or question.input_kind != "json":
                        continue
                    try:
                        arguments = _strict_json(question.input_text, dict, "PGG-CONSENT-ASSOCIATION")
                    except PrRouteDenied:
                        continue
                    originals = arguments.get("questions")
                    index = locator[2]
                    if not isinstance(originals, list) or not 0 <= index < len(originals):
                        continue
                    original = originals[index]
                    if not isinstance(original, dict) or original.get("title") != item.question:
                        continue
                    for reference in reference_pattern.findall(item.question):
                        review = reviews.get(reference)
                        if review is not None and review[1] < question_position < position:
                            chosen.append(GenericApprovalSelection(review[0], review[1], position, question.call_id, index))
            elif reply.kind == "plain":
                for reference in visible:
                    review = reviews.get(reference)
                    if review is not None and review[1] < position:
                        chosen.append(GenericApprovalSelection(review[0], review[1], position))
            if len(chosen) == 1:
                selection, intent_record, intent_state = chosen[0], position, "candidate"
            elif action == "generic":
                selection, intent_record, intent_state = None, position, "insufficient"
            # A bare request to execute does not change the authority domain.
            # A genuinely new generic approval above still supersedes old PR
            # authority even when its original association is insufficient.
        visible.clear()

    _entries, status = read_transcript_history(
        transcript_path, byte_cap=None, record_cap=None, line_byte_cap=None,
        on_record=consume,
    )
    pr_state, pr_grant = (pr_reducer.state, pr_reducer.grant) if pr_reducer is not None and status == HISTORY_STATUS_FOUND else ("absent", None)
    return _GenericControlCut(
        selection, intent_record, intent_state, pr_record, tuple(commands),
        tuple(opaque), tuple(model_publications), tuple(invalid_commands), digest.hexdigest(), status,
        max_approval_record_bytes, position, execution_record, pr_state, pr_grant, pr_reducer,
    )


def _parse_native_command(command: object) -> ShellParseResult:
    if command.argv:
        return parse_native_argument_vector(command.argv, "native-command:" + command.item_id, 0)
    return parse_transcript_command(command.command, "exec_command", "native-command:" + command.item_id, 0)


def _native_literal_leaf(parsed: ShellParseResult, subject: GenericPublicationSubject) -> ShellParseResult | None:
    """Only the grammar owner's exact child of an actually qualified wrapper."""
    while parsed.children:
        if parsed.status != "SCG-PARSED" or parsed.candidates or len(parsed.commands) != 1 or len(parsed.children) != 1 or len(parsed.wrapper_projections) != 1:
            return None
        projection = parsed.wrapper_projections[0]
        if projection.terminal_state != "EXACT_CHILD" or projection.child_input is None:
            return None
        wrapper = parsed.commands[0].executable
        if not Path(wrapper).is_absolute():
            return None
        resolved = _resolve_executable(Path(wrapper).name, subject.root)
        if resolved is None:
            return None
        try:
            _bind_literal_executable_identity(wrapper, resolved, "PGG-CONSENT-EXECUTABLE")
        except PrRouteDenied:
            return None
        parsed = parsed.children[0]
    return parsed


def _native_git_arguments(
    command: object, subject: GenericPublicationSubject, parsed: ShellParseResult | None,
) -> tuple[str, ...] | None:
    if parsed is None:
        return None
    publication = parsed.strict_projection.status == "canonical"
    if publication:
        argv = parsed.strict_projection.argv
    else:
        # Native argv and read-only queries reuse the exact literal record;
        # neither is reserialized into a shell or made a live push grammar.
        if (
            parsed.status != "SCG-PARSED" or len(parsed.commands) != 1
            or parsed.candidates or parsed.children or parsed.wrapper_projections
            or parsed.normalizations or parsed.lexical.operations
            or parsed.lexical.removed_spans
        ):
            return None
        record = parsed.commands[0]
        if (
            record.confidence != "exact" or record.normalization_state != "literal"
            or record.environment_assignments or record.control_keywords
            or any(not token.literalized for token in record.token_records)
        ):
            return None
        argv = record.tokens
    if not argv or not Path(argv[0]).is_absolute():
        return None
    git = _resolve_executable("git", subject.root)
    if git is None:
        return None
    try:
        _bind_literal_executable_identity(argv[0], git, "PGG-CONSENT-EXECUTABLE")
    except PrRouteDenied:
        return None
    selected_root = argv[2] if len(argv) > 2 and argv[1] == "-C" else command.cwd
    if _same_publication_root(selected_root, subject) is not True:
        return None
    result = tuple(argv[3:]) if len(argv) > 2 and argv[1] == "-C" else tuple(argv[1:])
    queries = {
        ("remote", "get-url", "--push", "--all", subject.remote),
        ("ls-remote", "--heads", subject.remote, subject.destination),
    }
    native_push = parsed.identity.input_kind == "DIRECT_ARGV" and result[:1] == ("push",)
    return result if publication or native_push or result in queries or _native_remote_mutation(result, subject) else None


def _same_publication_root(value: object, subject: GenericPublicationSubject) -> bool | None:
    if type(value) is not str or not value or not Path(value).is_absolute():
        return None
    try:
        observed = Path(value).stat()
    except OSError:
        return None
    return (observed.st_dev, observed.st_ino) == subject.root_identity


def _native_remote_mutation(args: tuple[str, ...], subject: GenericPublicationSubject) -> bool:
    if len(args) >= 3 and args[0] == "remote" and args[1] in {"set-url", "add", "remove", "rm", "rename"} and args[2] == subject.remote:
        return True
    if args[:1] != ("config",):
        return False
    key = "remote." + subject.remote + "."
    selected_keys = [index for index, word in enumerate(args) if word.startswith(key)]
    return any(index < len(args) - 1 or any(word in {"--unset", "--unset-all", "--add", "--replace-all"} for word in args[1:index]) for index in selected_keys)


def _native_operation_relevance(command: object, subject: GenericPublicationSubject) -> str:
    """Qualify relation to O before applying thread/outcome predicates."""
    parsed = _parse_native_command(command)
    publications = parsed.effective_publications.records
    if publications:
        possible = False
        for record in publications:
            push = record.push
            literal = push.command
            root = command.cwd
            options = push.git_global_options
            if len(options) == 2 and options[0] == "-C":
                root = options[1]
            elif options:
                possible = True
                continue
            relation = _same_publication_root(root, subject)
            if relation is False:
                continue
            if relation is None or len(push.positionals) != 2:
                possible = True
                continue
            remote, refspec = push.positionals
            destination = refspec.split(":", 1)[-1]
            destination = destination if destination.startswith("refs/") else "refs/heads/" + destination
            if remote != subject.remote or destination != subject.destination:
                continue
            return "selected"
        return "possible" if possible else "unrelated"
    # Only exact native query/mutation operands can affect a selected remote
    # preimage. Unrelated reads and opaque carrier names are not global vetoes.
    leaf = _native_literal_leaf(parsed, subject)
    if leaf is None or leaf.status != "SCG-PARSED" or leaf.candidates or len(leaf.commands) != 1:
        return "unrelated"
    tokens = leaf.commands[0].tokens
    if not tokens or Path(tokens[0]).name.casefold() not in {"git", "git.exe"}:
        return "unrelated"
    root = tokens[2] if len(tokens) > 2 and tokens[1] == "-C" else command.cwd
    args = tuple(tokens[3:]) if len(tokens) > 2 and tokens[1] == "-C" else tuple(tokens[1:])
    relation = _same_publication_root(root, subject)
    if relation is False:
        return "unrelated"
    queries = {("remote", "get-url", "--push", "--all", subject.remote),
               ("ls-remote", "--heads", subject.remote, subject.destination)}
    mutation = _native_remote_mutation(args, subject)
    if args in queries or mutation:
        return "mutation" if mutation else "observation" if relation is True else "possible"
    return "unrelated"


def _generic_operation_state(
    approval: OriginalGenericApproval,
    cut: _GenericControlCut,
    preflight: PreflightResult,
) -> tuple[str, str]:
    """Actual typed native lifecycle, independently of scan consumption."""
    subject = approval.subject
    selected = []
    for position, command in cut.commands:
        if position <= approval.selection.user_record:
            continue
        relevance = _native_operation_relevance(command, subject)
        if relevance != "unrelated":
            selected.append((position, command, relevance))
    for position, partial in cut.invalid_command_records:
        if position <= approval.selection.user_record:
            continue
        raw = partial.get("command")
        if partial.get("core") and isinstance(raw, list) and raw and all(type(word) is str for word in raw):
            parsed = parse_native_argument_vector(tuple(raw), "partial-native:" + str(position), 0)
        elif not partial.get("core") and type(raw) is str:
            parsed = parse_transcript_command(raw, "exec_command", "partial-native:" + str(position), 0)
        else:
            parsed = None
        matching_model = any(approval.selection.user_record < pos and call_id == partial.get("item_id") and (_same_publication_root(root, subject) is not False) for pos, call_id, root in cut.model_publications)
        if matching_model or (parsed is not None and parsed.effective_publications.records and _same_publication_root(partial.get("cwd"), subject) is not False):
            return "unresolved", "native-selected-command-shape"
    if selected and not preflight.native_session_id:
        return "unresolved", "native-command-thread-correlation"
    latest: dict[str, tuple[int, object, str]] = {}
    for position, command, relevance in selected:
        if command.thread_id != preflight.native_session_id:
            return "unresolved", "native-command-thread-correlation"
        if command.source == "unifiedExecInteraction":
            return "unresolved", "native-selected-continuation-parent-unavailable"
        previous = latest.get(command.item_id)
        if previous is not None:
            old = previous[1]
            if (old.command, old.argv, old.cwd, old.thread_id, old.turn_id, old.source) != (
                command.command, command.argv, command.cwd, command.thread_id, command.turn_id, command.source,
            ) or old.completed:
                return "corrupt", "native-command-correlation"
        latest[command.item_id] = position, command, relevance
    endpoint: tuple[int, str] | None = None
    targets: list[tuple[int, object]] = []
    for position, command, relevance in sorted(latest.values(), key=lambda row: row[0]):
        if relevance == "possible":
            return "unresolved", "native-selected-operation"
        if relevance == "mutation":
            mutation_args = _native_git_arguments(command, subject, _native_literal_leaf(_parse_native_command(command), subject))
            if mutation_args is None or not command.completed or command.status != "completed" or command.exit_code != 0:
                return "unresolved", "native-selected-remote-mutation"
            endpoint = None
            continue
        if position <= approval.selection.user_record:
            continue
        original_parse = _parse_native_command(command)
        parsed = _native_literal_leaf(original_parse, subject)
        argv = _native_git_arguments(command, subject, parsed)
        if argv is None:
            return "unresolved", "actual-target-command-shape"
        if argv == ("remote", "get-url", "--push", "--all", subject.remote):
            if command.completed and command.status == "completed" and command.exit_code == 0 and command.output is not None:
                values = command.output.splitlines()
                endpoint = (position, values[0]) if len(values) == 1 else None
            continue
        if command.argv:
            # The actual -C root was qualified above. Classify the remaining
            # native argument vector with the same grammar, without shell text.
            parsed = parse_native_argument_vector((parsed.commands[0].executable, *argv), "native-command:" + command.item_id, 0)
        decision = classify_generic_push(parsed)
        if decision.status == "PGG-ADMISSIBLE" and decision.binding is not None:
            remote, destination, source = decision.binding
            if (remote, destination) != (subject.remote, subject.destination):
                continue
            if command.item_id == preflight.tool_use_id and not command.completed:
                continue
            if not command.completed or command.status != "completed" or command.exit_code != 0:
                return "unresolved", "actual-target-outcome"
            if source != subject.source_oid:
                return "unresolved", "actual-target-immutable-source"
            if endpoint is None or endpoint[1] != subject.remote_identity:
                return "unresolved", "actual-target-remote-identity"
            targets.append((position, command))
            continue
        if argv == ("ls-remote", "--heads", subject.remote, subject.destination) and targets:
            if command.completed and command.status == "completed" and command.exit_code == 0 and command.output is not None:
                expected = subject.source_oid + "\t" + subject.destination
                if endpoint is not None and endpoint[1] == subject.remote_identity and command.output.splitlines() == [expected] and position > targets[-1][0]:
                    return "fulfilled", "actual-target-and-destination-readback"
        elif parsed.effective_publications.records:
            return "unresolved", "actual-target-command-shape"
    if targets:
        return "unresolved", "actual-destination-readback"
    for position, call_id, root in cut.model_publications:
        if position <= approval.selection.user_record:
            continue
        if _same_publication_root(root, subject) is False:
            continue
        if call_id == preflight.tool_use_id and call_id not in latest:
            continue
        if call_id not in latest:
            return "unresolved", "actual-target-result-unavailable"
    # Opaque names alone establish neither a publication attempt nor no effect.
    # Actual possibly matching model/native publications above remain held.
    return "pending", "exact-original-operation"


def _normalize_original_logical_scope(values: dict[str, str]) -> _OriginalLogicalScope:
    """Normalize only actual supplied source values; never fill from HEAD/cache."""
    if set(values) != _GENERIC_SCOPE_FIELDS:
        missing = sorted(_GENERIC_SCOPE_FIELDS - set(values))
        raise _OriginalScopeInputError(missing[0] if missing else "scope-fields")
    if any(type(value) is not str or not value for value in values.values()):
        raise _OriginalScopeInputError("scope-value")
    root = _normalize_repository_workdir(values["root"], subject="authorization", source="authorization-context")
    endpoint = values["remote_identity"]
    repository = _repo_identity_from_url(endpoint)
    if values["repository"] not in {endpoint, repository}:
        raise _OriginalScopeInputError("repository")
    repository = repository or endpoint
    destination = values["destination"]
    if not destination.startswith("refs/"):
        destination = "refs/heads/" + destination
    oid = values["source_oid"]
    parsed_endpoint = urlsplit(endpoint)
    if not REMOTE_NAME_REGEX.fullmatch(values["remote"]):
        raise _OriginalScopeInputError("remote")
    if parsed_endpoint.username is not None or parsed_endpoint.password is not None:
        raise _OriginalScopeInputError("remote_identity")
    if not destination.startswith("refs/heads/"):
        raise _OriginalScopeInputError("destination")
    if re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", oid) is None:
        raise _OriginalScopeInputError("source_oid")
    if not values["review_statement"].strip():
        raise _OriginalScopeInputError("review_statement")
    return _OriginalLogicalScope(root, repository, values["remote"], endpoint,
        destination, oid.lower(), values["review_statement"])


def _original_scope_source_values(selected, components) -> dict[str, str]:
    fields = selected.source_fields
    if fields:
        if any(not isinstance(value, GenericSourceField) for value in fields) or len(fields) != len(_GENERIC_SCOPE_FIELDS) or {value.field for value in fields} != _GENERIC_SCOPE_FIELDS:
            raise _OriginalScopeInputError("scope-fields")
        values = {}
        for value in fields:
            if type(value.evidence_index) is not int or not 0 <= value.evidence_index < len(components):
                raise _OriginalScopeInputError(value.field)
            evidence, text = components[value.evidence_index]
            needed_role = "completed-review" if value.field == "review_statement" else "scope"
            if evidence.role != needed_role:
                raise _OriginalScopeInputError(value.field)
            if value.span is not None:
                if type(value.span) is not tuple or len(value.span) != 2 or any(type(n) is not int for n in value.span) or not 0 <= value.span[0] < value.span[1] <= len(text):
                    raise _OriginalScopeInputError(value.field)
                text = text[value.span[0]:value.span[1]]
            values[value.field] = text
        return values
    # An actual complete packet is one fitting source adapter. It is decoded
    # before expected fields are consulted; general/narrative input uses the
    # finite source field/component selectors above, not another user protocol.
    packets = []
    for evidence, text in components:
        if evidence.role != "scope":
            continue
        try:
            packet = _review_packet_subject(text)
        except PrRouteDenied:
            continue
        packets.append((packet, text))
    if not packets or len({value[0] for value in packets}) != 1:
        raise _OriginalScopeInputError("scope-fields")
    packet, raw = packets[0]
    if not any(evidence.role == "completed-review" and text == raw for evidence, text in components):
        raise _OriginalScopeInputError("review_statement")
    return {"root": packet.root, "repository": packet.remote_identity,
            "remote": packet.remote, "remote_identity": packet.remote_identity,
            "destination": packet.destination, "source_oid": packet.source_oid,
            "review_statement": raw}


def _qualify_original_source_scope(source: _ReceivedGenericSource, current_subject: GenericPublicationSubject) -> OriginalGenericApproval:
    scope = source.scope
    # Only the source-derived root can use this operation's existing qualified
    # native context. Current invocation/HEAD is never a missing scope filler.
    if _same_publication_root(scope.root, current_subject) is not True:
        raise _OriginalScopeInputError("root-native-context")
    subject = GenericPublicationSubject(scope.root, current_subject.root_identity,
        current_subject.repository_identity, current_subject.worktree_identity,
        scope.remote, scope.remote_identity, scope.destination,
        {40: "sha1", 64: "sha256"}[len(scope.source_oid)], scope.source_oid)
    publication_review_packet(subject)
    return OriginalGenericApproval(subject, source.selection, source.user_sha256,
        source.packet_sha256, source.producer_kind, source.history_sha256)


def _receive_selected_generic_source(
    transcript_path: str,
    selected: GenericUserScopeSelection,
) -> _ReceivedGenericSource:
    """Receive Root's semantic selection over actual applicable components.

    Neither locators nor normalized values authenticate themselves. Original
    raw records, genuine user disposition, selected Q/A correlation and actual
    review/scope ordering are independently acquired every time. Root owns the
    interpretation linking those components; no packet or answer-only text
    format is imposed on that interpretation.
    """
    if type(selected.user_record) is not int or selected.user_record <= 0:
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    evidence = selected.evidence
    if any(not isinstance(value, GenericRecordEvidence) for value in evidence) or len(set(evidence)) != len(evidence):
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    wanted = {value.record for value in evidence} | {selected.user_record}
    call_ids = {value.call_id for value in evidence if value.call_id is not None}
    if selected.question_call_id is not None:
        call_ids.add(selected.question_call_id)
    records: dict[int, tuple[dict, bytes]] = {}
    calls: dict[str, tuple[int, object]] = {}
    digest = hashlib.sha256()
    position = 0

    def consume(entry: dict, raw: bytes) -> None:
        nonlocal position
        position += 1
        digest.update(raw)
        if position in wanted:
            records[position] = entry, raw
        for call in extract_native_control_calls(entry):
            if call.call_id in call_ids:
                if call.call_id in calls:
                    raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                calls[call.call_id] = position, call

    _entries, status = read_transcript_history(
        transcript_path, byte_cap=None, record_cap=None, line_byte_cap=None, on_record=consume,
    )
    if status == HISTORY_STATUS_IDENTITY_DRIFT:
        raise PrRouteDenied("PGG-CONSENT-IDENTITY-DRIFT")
    if status != HISTORY_STATUS_FOUND or selected.user_record not in records:
        raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
    user_entry, raw_user = records[selected.user_record]
    if not is_user_message(user_entry):
        raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
    reply = extract_publication_user_reply(user_entry)
    action, _ = reply.publication_action()
    if action in {"revoked", "malformed"} or (action != "generic" and not publication_reply_has_push_instruction(reply)):
        raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
    answer = None
    question_position = None
    question_text = None
    if reply.kind == "plain":
        if len(reply.answers) != 1 or (selected.question_call_id, selected.question_index) != (None, None):
            raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
        approval_text = reply.answers[0]
    elif reply.kind == "structured-answer":
        if selected.question_call_id not in calls or type(selected.question_index) is not int:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        question_position, question = calls[selected.question_call_id]
        if question_position >= selected.user_record or question.input_kind != "json" or question.tool_name not in {"request_user_input_async", "functions.request_user_input_async"}:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        questions = _strict_json(question.input_text, dict, "PGG-CONSENT-ASSOCIATION").get("questions")
        index = selected.question_index
        if not isinstance(questions, list) or not 0 <= index < len(questions):
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        matched = [item for item in reply.structured_items if _strict_json(item.question_item_id, list, "PGG-CONSENT-ASSOCIATION") == [question.tool_name, question.call_id, index]]
        if len(matched) != 1:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        answer = matched[0]
        original = questions[index]
        # Match the actual indexed producer component to the received native
        # question. Do not guess a universal historical title/key spelling.
        originals = [original] if type(original) is str else list(original.values()) if isinstance(original, dict) else []
        if sum(type(value) is str and value == answer.question for value in originals) != 1:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        selected_answer = PublicationUserReply("plain", (answer.answer,))
        if selected_answer.publication_action()[0] != "generic" and not publication_reply_has_push_instruction(selected_answer):
            raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
        approval_text, question_text = answer.answer, answer.question
    else:
        raise PrRouteDenied("PGG-CONSENT-PROVENANCE")

    fields = {"root": selected.root, "repository": selected.repository, "remote": selected.remote,
              "remote_identity": selected.remote_identity, "destination": selected.destination,
              "source_oid": selected.source_oid, "review_statement": selected.review_statement}
    if any(type(value) is not str or not value for value in fields.values()):
        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
    source_values = {}
    if not evidence:
        # Existing one-user-record adapter extracts actual values first.
        if len(selected.spans) != len(fields) or {row[0] for row in selected.spans} != set(fields):
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        for key, start, end in selected.spans:
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(approval_text):
                raise _OriginalScopeInputError(key)
            source_values[key] = approval_text[start:end]
    else:
        roles: dict[str, list[tuple[GenericRecordEvidence, str]]] = {}
        components = []
        for value in evidence:
            if value.role not in {"approval", "scope", "completed-review", "association"} or type(value.record) is not int or value.record <= 0 or value.record > selected.user_record or value.record not in records:
                raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
            entry, raw = records[value.record]
            if type(value.record_sha256) is not str or hashlib.sha256(raw).hexdigest() != value.record_sha256:
                raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
            if value.component == "user-text":
                if not is_user_message(entry) or extract_publication_user_reply(entry).kind != "plain" or value.call_id is not None or value.index is not None:
                    raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
                component = extract_publication_user_reply(entry).answers[0]
            elif value.component == "answer":
                if value.record != selected.user_record or answer is None or (value.call_id, value.index) != (selected.question_call_id, selected.question_index):
                    raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                component = answer.answer
            elif value.component in {"question", "call-input"}:
                if value.call_id not in calls or calls[value.call_id][0] != value.record:
                    raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                if value.component == "question":
                    if question_text is None or value.record != question_position or (value.call_id, value.index) != (selected.question_call_id, selected.question_index):
                        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                    component = question_text
                else:
                    if value.index is not None:
                        raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                    component = calls[value.call_id][1].input_text
            elif value.component == "result-text":
                matches = [result for result in extract_native_control_results(entry) if result.call_id == value.call_id]
                if value.call_id not in calls or calls[value.call_id][0] >= value.record or len(matches) != 1 or type(value.index) is not int or not 0 <= value.index < len(matches[0].text_blocks):
                    raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                component = matches[0].text_blocks[value.index]
            else:
                raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
            if value.span is not None:
                if type(value.span) is not tuple or len(value.span) != 2 or any(type(n) is not int for n in value.span) or not 0 <= value.span[0] < value.span[1] <= len(component):
                    raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
                component = component[value.span[0]:value.span[1]]
            if not component:
                raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
            roles.setdefault(value.role, []).append((value, component))
            components.append((value, component))
        if set(roles) != {"approval", "scope", "completed-review", "association"}:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        if any(value.record != selected.user_record or value.component not in {"answer", "user-text"} for value, _ in roles["approval"]):
            raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
        if question_position is not None and not any(value.record == question_position and value.component == "question" for value, _ in roles["association"]):
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        # Applicable user/answer components may supply scope and a statement
        # that review was completed. Only genuinely future source records are
        # excluded above; Q-before-answer correlation remains mandatory.
        source_values = _original_scope_source_values(selected, components)
    actual_scope = _normalize_original_logical_scope(source_values)
    expected_scope = _normalize_original_logical_scope(fields)
    if actual_scope != expected_scope:
        coordinate = next(name for name in sorted(_GENERIC_SCOPE_FIELDS) if getattr(actual_scope, name) != getattr(expected_scope, name))
        raise _OriginalScopeInputError(coordinate)
    review = min((value for value in evidence if value.role == "completed-review"), key=lambda value: value.record, default=None)
    return _ReceivedGenericSource(actual_scope, GenericApprovalSelection(
        review.call_id if review is not None else None,
        review.record if review is not None and review.record != selected.user_record else None,
        selected.user_record, selected.question_call_id, selected.question_index,
    ), hashlib.sha256(raw_user).hexdigest(), None, reply.kind, digest.hexdigest())


def _receive_selected_generic_association(
    transcript_path: str, selected: GenericUserScopeSelection, current_subject: GenericPublicationSubject,
) -> OriginalGenericApproval:
    return _qualify_original_source_scope(_receive_selected_generic_source(transcript_path, selected), current_subject)


def _receive_direct_user_scope(
    transcript_path: str, selected: GenericUserScopeSelection, current_subject: GenericPublicationSubject,
) -> OriginalGenericApproval:
    return _receive_selected_generic_association(transcript_path, selected, current_subject)


_GENERIC_INDEX_SUFFIX = ".generic-publication-index-v1.json"
_GENERIC_SCOPE_FIELDS = frozenset({
    "root", "repository", "remote", "remote_identity", "destination",
    "source_oid", "review_statement",
})


def _generic_index_path(transcript_path: str) -> Path:
    # Same selected native-source/binding owner; the PR v1 leaf is untouched.
    original = _binding_sidecar_path(transcript_path)
    return original.with_name(original.name[:-len(PR_BINDING_SIDECAR_SUFFIX)] + _GENERIC_INDEX_SUFFIX)


def _generic_evidence_payload(value: GenericRecordEvidence) -> dict:
    return {"role": value.role, "record": value.record, "sha256": value.record_sha256,
            "component": value.component, "callId": value.call_id, "index": value.index,
            "span": list(value.span) if value.span is not None else None}


def _decode_generic_evidence(value: object) -> GenericRecordEvidence:
    if not isinstance(value, dict) or set(value) != {"role", "record", "sha256", "component", "callId", "index", "span"}:
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    if value["role"] not in {"approval", "scope", "completed-review", "association"} or type(value["record"]) is not int or value["record"] <= 0 or type(value["sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None:
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    if value["component"] not in {"user-text", "answer", "question", "call-input", "result-text"}:
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    if value["callId"] is not None and (type(value["callId"]) is not str or not value["callId"]):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    if value["index"] is not None and (type(value["index"]) is not int or value["index"] < 0):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    span = value["span"]
    if span is not None and (not isinstance(span, list) or len(span) != 2 or any(type(n) is not int for n in span) or not 0 <= span[0] < span[1]):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    return GenericRecordEvidence(value["role"], value["record"], value["sha256"], value["component"], value["callId"], value["index"], tuple(span) if span is not None else None)


def _generic_source_field_payload(value: GenericSourceField) -> dict:
    return {"field": value.field, "evidenceIndex": value.evidence_index,
            "span": list(value.span) if value.span is not None else None}


def _decode_generic_source_field(value: object) -> GenericSourceField:
    if not isinstance(value, dict) or set(value) != {"field", "evidenceIndex", "span"} or value["field"] not in _GENERIC_SCOPE_FIELDS or type(value["evidenceIndex"]) is not int or value["evidenceIndex"] < 0:
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    span = value["span"]
    if span is not None and (not isinstance(span, list) or len(span) != 2 or any(type(n) is not int for n in span) or not 0 <= span[0] < span[1]):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    return GenericSourceField(value["field"], value["evidenceIndex"], tuple(span) if span is not None else None)


def _generic_index_payload(value: GenericConsentIndex) -> dict:
    return {
        "v": 1, "kind": "generic-derived-selection",
        "anchor": {"record": value.user_record, "sha256": value.user_sha256},
        "sourceIdentity": list(value.source_identity),
        "subject": json.loads(publication_review_packet(value.subject))["subject"],
        "spans": [list(row) for row in value.spans],
        "questionCallId": value.question_call_id, "questionIndex": value.question_index,
        "history": {"records": value.history_records, "sha256": value.history_sha256},
        "evidence": [_generic_evidence_payload(item) for item in value.evidence],
        "association": {"repository": value.repository, "reviewStatement": value.review_statement},
        "sourceFields": [_generic_source_field_payload(item) for item in value.source_fields],
    }


def _decode_generic_index(raw: bytes) -> GenericConsentIndex:
    value = _strict_json(raw.decode("utf-8", errors="strict"), dict, "PGG-CONSENT-CORRUPT")
    allowed = {"v", "kind", "anchor", "sourceIdentity", "subject", "spans", "questionCallId", "questionIndex", "history", "evidence", "association"}
    if set(value) not in (allowed, allowed | {"sourceFields"}) or type(value["v"]) is not int or value["v"] != 1 or value["kind"] != "generic-derived-selection":
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    anchor, history = value["anchor"], value["history"]
    if not isinstance(anchor, dict) or set(anchor) != {"record", "sha256"} or not isinstance(history, dict) or set(history) != {"records", "sha256"}:
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    if type(anchor["record"]) is not int or anchor["record"] <= 0 or type(history["records"]) is not int or history["records"] < anchor["record"]:
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    if any(type(item) is not str or re.fullmatch(r"[0-9a-f]{64}", item) is None for item in (anchor["sha256"], history["sha256"])):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    identity = value["sourceIdentity"]
    if not isinstance(identity, list) or len(identity) != 2 or any(type(n) is not int or n < 0 for n in identity):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    evidence_rows, association = value["evidence"], value["association"]
    if not isinstance(evidence_rows, list) or not isinstance(association, dict) or set(association) != {"repository", "reviewStatement"} or any(type(n) is not str for n in association.values()):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    evidence = tuple(_decode_generic_evidence(row) for row in evidence_rows)
    source_rows = value.get("sourceFields", [])
    if not isinstance(source_rows, list):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    source_fields = tuple(_decode_generic_source_field(row) for row in source_rows)
    if source_fields and (len(source_fields) != len(_GENERIC_SCOPE_FIELDS) or {row.field for row in source_fields} != _GENERIC_SCOPE_FIELDS):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    if len(set(evidence)) != len(evidence):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    spans = value["spans"]
    if not isinstance(spans, list) or (not evidence and len(spans) != len(_GENERIC_SCOPE_FIELDS)):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    for row in spans:
        if not isinstance(row, list) or len(row) != 3 or row[0] not in _GENERIC_SCOPE_FIELDS or any(type(n) is not int for n in row[1:]) or not 0 <= row[1] < row[2]:
            raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    if not evidence and {row[0] for row in spans} != _GENERIC_SCOPE_FIELDS:
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    call_id, index = value["questionCallId"], value["questionIndex"]
    if (call_id, index) != (None, None) and (type(call_id) is not str or not call_id or type(index) is not int or index < 0):
        raise PrRouteDenied("PGG-CONSENT-CORRUPT")
    subject = _review_packet_subject(json.dumps({"kind": "publication-review-v1", "subject": value["subject"]}))
    return GenericConsentIndex(
        anchor["record"], anchor["sha256"], tuple(identity), subject,
        tuple(tuple(row) for row in spans), call_id, index,
        history["sha256"], history["records"], evidence,
        association["repository"], association["reviewStatement"], source_fields,
    )


def _generic_index_capacity(
    cut: _GenericControlCut, subject: GenericPublicationSubject,
    source_metadata: os.stat_result,
) -> int:
    """Worst valid encoding from acquired inputs, not a new input-size limit.

    Six variable string slots can each refer to source user data, with at most
    six ASCII escape bytes per Unicode character. Seventeen locator integers
    are bounded by actual acquired record/text lengths. Native identity/schema
    bytes are included exactly. The PR v1 resource bound remains unchanged.
    """
    skeleton = GenericConsentIndex(
        1, "0" * 64, (source_metadata.st_dev, source_metadata.st_ino), subject,
        tuple((key, 0, 1) for key in sorted(_GENERIC_SCOPE_FIELDS)),
        None, None, "0" * 64, max(cut.record_count, 1),
    )
    fixed = len(json.dumps(_generic_index_payload(skeleton), ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
    digits = len(str(max(source_metadata.st_size, cut.record_count, cut.max_approval_record_bytes, 1)))
    # A distinct locator is one of four roles over an actual component and
    # an optional Unicode span. At most B components and (B+1)^2 spans exist
    # in B acquired bytes. Exact duplicates are redundant, not another input.
    # The ceiling is input-derived; reads allocate only observed-size+1.
    size = max(source_metadata.st_size, 1)
    locator_fixed = len(json.dumps(_generic_evidence_payload(GenericRecordEvidence("completed-review", 1, "0" * 64, "result-text", "", 0, (0, 1))), separators=(",", ":")))
    locator_bound = locator_fixed + 6 * size + 4 * digits
    field_fixed = len(json.dumps(_generic_source_field_payload(GenericSourceField("review_statement", 0, (0, 1))), separators=(",", ":")))
    # Seven logical coordinates, each with one component index (bounded by
    # actual distinct evidence count) and two source-character offsets.
    field_bound = len(_GENERIC_SCOPE_FIELDS) * (field_fixed + 5 * digits)
    return fixed + 6 * 6 * cut.max_approval_record_bytes + 17 * digits + 4 * size * (size + 1) ** 2 * locator_bound + 12 * size + field_bound


def _read_generic_index(
    transcript_path: str, cut: _GenericControlCut, subject: GenericPublicationSubject,
) -> GenericConsentIndex | None:
    return _read_native_binding_state(
        _generic_index_path(transcript_path),
        byte_cap=_generic_index_capacity(cut, subject, Path(transcript_path).stat()),
        decode_document=_decode_generic_index,
    )


def _selection_from_generic_index(
    transcript_path: str, value: GenericConsentIndex,
) -> tuple[GenericUserScopeSelection, str]:
    source = Path(transcript_path)
    metadata = source.stat()
    # The persisted inode is an acquisition observation, not perpetual
    # authority. The current operation holds and requalifies its actual source.
    observed_identity = (metadata.st_dev, metadata.st_ino)
    position = 0
    user: tuple[PublicationUserReply, bytes] | None = None
    prefix = hashlib.sha256()
    complete = hashlib.sha256()

    def consume(entry: dict, raw: bytes) -> None:
        nonlocal position, user
        position += 1
        complete.update(raw)
        if position <= value.history_records:
            prefix.update(raw)
        if position == value.user_record and is_user_message(entry):
            user = extract_publication_user_reply(entry), raw

    _entries, status = read_transcript_history(
        transcript_path, byte_cap=None, record_cap=None, line_byte_cap=None,
        on_record=consume,
    )
    if status == HISTORY_STATUS_IDENTITY_DRIFT:
        raise PrRouteDenied("PGG-CONSENT-IDENTITY-DRIFT")
    metadata = source.stat()
    if status != HISTORY_STATUS_FOUND or user is None or position < value.history_records or prefix.hexdigest() != value.history_sha256 or (metadata.st_dev, metadata.st_ino) != observed_identity:
        raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
    reply, raw = user
    if hashlib.sha256(raw).hexdigest() != value.user_sha256:
        raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
    if value.question_call_id is None:
        if reply.kind != "plain" or len(reply.answers) != 1:
            raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
        text = reply.answers[0]
    else:
        if reply.kind != "structured-answer":
            raise PrRouteDenied("PGG-CONSENT-PROVENANCE")
        matches = []
        for item in reply.structured_items:
            locator = _strict_json(item.question_item_id, list, "PGG-CONSENT-ASSOCIATION")
            if len(locator) == 3 and locator[1:] == [value.question_call_id, value.question_index]:
                matches.append(item)
        if len(matches) != 1:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        text = matches[0].answer
    if value.evidence:
        return GenericUserScopeSelection(
            value.user_record, value.subject.root, value.repository,
            value.subject.remote, value.subject.remote_identity,
            value.subject.destination, value.subject.source_oid, value.review_statement,
            question_call_id=value.question_call_id, question_index=value.question_index,
            evidence=value.evidence, source_fields=value.source_fields,
        ), complete.hexdigest()
    values = {}
    for key, start, end in value.spans:
        if not 0 <= start < end <= len(text):
            raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
        values[key] = text[start:end]
    return GenericUserScopeSelection(
        value.user_record, spans=value.spans, question_call_id=value.question_call_id,
        question_index=value.question_index, **values,
    ), complete.hexdigest()


def _receive_generic_publication_consent_once(
    preflight: PreflightResult,
    current_subject: GenericPublicationSubject,
    *,
    direct_selection: GenericUserScopeSelection | None = None,
) -> GenericConsentResult:
    """One common exact-scope receiving path; no cached label can authorize."""
    cut = _generic_control_cut(preflight.transcript_path)
    if cut.history_status != HISTORY_STATUS_FOUND:
        detail = "selected-history-drift" if cut.history_status == HISTORY_STATUS_IDENTITY_DRIFT else "selected-history-unavailable"
        return GenericConsentResult("corrupt", None, detail)
    materialized: GenericConsentIndex | None = None
    if cut.intent_state in {"revoked", "corrupt"}:
        return GenericConsentResult(cut.intent_state, None, "later-genuine-publication-control")
    if direct_selection is None and cut.intent_state != "candidate":
        try:
            materialized = _read_generic_index(preflight.transcript_path, cut, current_subject)
            if direct_selection is None and materialized is not None:
                direct_selection, observed_digest = _selection_from_generic_index(
                    preflight.transcript_path, materialized,
                )
                if observed_digest != cut.history_sha256:
                    return GenericConsentResult("corrupt", None, "selected-history-drift")
        except PrRouteDenied as exc:
            return GenericConsentResult("corrupt", None, exc.failure_id)
        except OSError:
            return GenericConsentResult("corrupt", None, "selected-source-unavailable")
    if direct_selection is None and (cut.intent_state != "candidate" or cut.selection is None):
        return GenericConsentResult(cut.intent_state, None, "original-reviewed-association")
    if direct_selection is not None and (
        cut.intent_state in {"revoked", "corrupt"}
        or cut.intent_record > direct_selection.user_record
    ):
        return GenericConsentResult(cut.intent_state, None, "later-genuine-publication-control")
    authority_record = direct_selection.user_record if direct_selection is not None else cut.intent_record
    if cut.pr_record > authority_record:
        return GenericConsentResult("superseded", None, "later-publication-intent")
    try:
        original = (
            _receive_direct_user_scope(preflight.transcript_path, direct_selection, current_subject)
            if direct_selection is not None
            else _receive_generic_original_association(preflight.transcript_path, cut.selection)
        )
    except PrRouteDenied as exc:
        detail = "original-source-coordinate:" + exc.coordinate if isinstance(exc, _OriginalScopeInputError) else exc.failure_id
        return GenericConsentResult("insufficient", None, detail)
    if original.history_sha256 != cut.history_sha256:
        return GenericConsentResult("corrupt", None, "selected-history-drift")
    if materialized is not None and materialized.user_record == original.selection.user_record:
        if materialized.user_sha256 != original.user_sha256:
            return GenericConsentResult("corrupt", None, "materialized-anchor-differs")
        if materialized.subject != original.subject:
            return GenericConsentResult("insufficient", original, "materialized-native-scope-differs")
    if original.subject != current_subject:
        return GenericConsentResult("insufficient", original, "selected-operation-differs")
    state, detail = _generic_operation_state(original, cut, preflight)
    return GenericConsentResult(state, original, detail, direct_selection)


def receive_generic_publication_consent(
    preflight: PreflightResult,
    current_subject: GenericPublicationSubject,
    *,
    direct_selection: GenericUserScopeSelection | None = None,
) -> GenericConsentResult:
    try:
        with hold_native_history_source(preflight.transcript_path) as source:
            # A frontier/content drift may be reread once within this same
            # source association; replacement never rebaselines the operation.
            result = _receive_generic_publication_consent_once(
                preflight, current_subject, direct_selection=direct_selection,
            )
            source.assert_current()
            if result.detail in {"selected-history-drift", "PGG-CONSENT-IDENTITY-DRIFT"}:
                result = _receive_generic_publication_consent_once(
                    preflight, current_subject, direct_selection=direct_selection,
                )
            source.assert_current()
            if result.approval is not None:
                result = replace(result, approval=replace(result.approval, source_identity=source.identity))
            return result
    except NativeHistorySourceError:
        return GenericConsentResult("corrupt", None, "selected-source-association")


def materialize_generic_publication_consent(
    preflight: PreflightResult,
    selection: GenericUserScopeSelection,
) -> GenericConsentResult:
    """Finite Root receiving, not a grant-file writer or a publication action."""
    try:
        with hold_native_history_source(preflight.transcript_path) as held_source:
            prepared = _prepare_generic_publication(preflight)
            result = receive_generic_publication_consent(
                preflight, prepared.subject, direct_selection=selection,
            )
            if result.state != "pending" or result.approval is None:
                return result
            if result.approval.source_identity != held_source.identity:
                return GenericConsentResult("corrupt", None, "selected-source-association")
            cut = _generic_control_cut(preflight.transcript_path, collect_lifecycle=False)
            if cut.history_status != HISTORY_STATUS_FOUND or cut.history_sha256 != result.approval.history_sha256:
                return GenericConsentResult("corrupt", None, "selected-history-drift")
            source = Path(preflight.transcript_path).stat()
            value = GenericConsentIndex(
                selection.user_record, result.approval.user_sha256, (source.st_dev, source.st_ino),
                result.approval.subject, selection.spans, selection.question_call_id,
                selection.question_index, cut.history_sha256, cut.record_count,
                selection.evidence, selection.repository if selection.evidence else "",
                selection.review_statement if selection.evidence else "", selection.source_fields,
            )
            capacity = _generic_index_capacity(cut, prepared.subject, source)
            path = _generic_index_path(preflight.transcript_path)

            def read_state(selected_path: Path) -> GenericConsentIndex | None:
                return _read_native_binding_state(
                    selected_path, byte_cap=capacity, decode_document=_decode_generic_index,
                )

            expected = read_state(path)
            _write_native_binding_state(
                path, value, expected=expected, read_state=read_state,
                encode_state=_generic_index_payload, byte_cap=capacity,
            )
            return receive_generic_publication_consent(preflight, prepared.subject, direct_selection=selection)

    except NativeHistorySourceError:
        return GenericConsentResult("corrupt", None, "selected-source-association")


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
    role_paths: tuple[tuple[str, str], ...]


SOURCE_ROLE_ORDER = (
    "gate", "hook_common", "classifier", "posix_helper", "windows_job",
    "scanner", "publication_review_policy", "linked_runtime_subroots",
)


SOURCE_LAYOUTS = (
    SourceLayout(
        "universal", ("scripts", "universal-hooks", "scripts", "check-git-push-gate.py"), 2,
        (
            ("gate", "universal-hooks/scripts/check-git-push-gate.py"),
            ("hook_common", "universal-hooks/scripts/hook_common.py"),
            ("classifier", "universal-hooks/hooks/check-machine-local-path.py"),
            ("posix_helper", "process_supervision/posix_process_group.py"),
            ("windows_job", "process_supervision/windows_job.py"),
            ("scanner", "universal-hooks/scripts/check-publication-safety.py"),
            ("publication_review_policy", "universal-hooks/scripts/publication_review_policy.py"),
            ("linked_runtime_subroots", "linked_runtime_subroots.py"),
        ),
    ),
    SourceLayout(
        "codex-source", ("src.codex", "skills", "lead", "scripts", "check-git-push-gate.py"), 4,
        (
            ("gate", "src.codex/skills/lead/scripts/check-git-push-gate.py"),
            ("hook_common", "src.codex/skills/lead/scripts/hook_common.py"),
            ("classifier", "src.codex/skills/lead/hooks/check-machine-local-path.py"),
            ("posix_helper", "scripts/process_supervision/posix_process_group.py"),
            ("windows_job", "scripts/process_supervision/windows_job.py"),
            ("scanner", "src.codex/skills/lead/scripts/check-publication-safety.py"),
            ("publication_review_policy", "src.codex/skills/lead/scripts/publication_review_policy.py"),
            ("linked_runtime_subroots", "scripts/linked_runtime_subroots.py"),
        ),
    ),
    SourceLayout(
        "claude-source", ("src.claude", "agents", "scripts", "check-git-push-gate.py"), 3,
        (
            ("gate", "src.claude/agents/scripts/check-git-push-gate.py"),
            ("hook_common", "src.claude/agents/scripts/hook_common.py"),
            ("classifier", "src.claude/agents/hooks/check-machine-local-path.py"),
            ("posix_helper", "scripts/process_supervision/posix_process_group.py"),
            ("windows_job", "scripts/process_supervision/windows_job.py"),
            ("scanner", "src.claude/agents/scripts/check-publication-safety.py"),
            ("publication_review_policy", "src.claude/agents/scripts/publication_review_policy.py"),
            ("linked_runtime_subroots", "scripts/linked_runtime_subroots.py"),
        ),
    ),
    SourceLayout(
        "component", ("scripts", "check-git-push-gate.py"), 1,
        (
            ("gate", "scripts/check-git-push-gate.py"),
            ("hook_common", "scripts/hook_common.py"),
            ("classifier", "hooks/check-machine-local-path.py"),
            ("posix_helper", "scripts/process_supervision/posix_process_group.py"),
            ("windows_job", "scripts/process_supervision/windows_job.py"),
            ("scanner", "scripts/check-publication-safety.py"),
            ("publication_review_policy", "scripts/publication_review_policy.py"),
            ("linked_runtime_subroots", "scripts/linked_runtime_subroots.py"),
        ),
    ),
)


@dataclass(frozen=True)
class PathComponentIdentity:
    root_relative_name: str
    kind: str
    identity: tuple[int, ...]


@dataclass(frozen=True)
class RootLocatorIdentity:
    logical_gate: str
    logical_root: str
    kind: str
    locator_identity: tuple[int, ...]
    raw_target: str | None
    physical_root: str
    physical_root_identity: tuple[int, ...]
    physical_gate: str
    gate_identity: tuple[int, ...]


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
    root_locator: RootLocatorIdentity


@dataclass(frozen=True)
class CapturedReviewModules:
    policy_module: object
    linked_module: object
    registered: tuple[tuple[str, object], ...]


@dataclass(frozen=True)
class CapturedReviewPayload:
    modules: CapturedReviewModules
    snapshot: object
    snapshot_id: str
    repository_observation: object
    repository: object | None
    origin_is_outside_repository: bool
    payload_bytes: bytes
    payload_sha256: str

    @property
    def policy_module(self) -> object:
        return self.modules.policy_module

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", self.snapshot_id) is None:
            raise ValueError("review-snapshot-id")
        if type(self.payload_bytes) is not bytes:
            raise ValueError("review-payload-bytes")
        if hashlib.sha256(self.payload_bytes).hexdigest() != self.payload_sha256:
            raise ValueError("review-payload-digest")


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
    captured_review: CapturedReviewPayload | None = None
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
            "captured_review",
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
        *,
        finalize_review: Callable[
            ["QualifiedPublicationEvidence"], tuple[dict, list[list[str]]]
        ] | None = None,
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
            review_finalization = None
            review_used_list = None
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
                if parsed.kind not in ("valid-v3", "qualified-v3") or parsed.receipt is None:
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
                    or (self.binding.route != "generic" and self.binding.source_oid != self.binding.head_oid)
                ):
                    mismatch = "PGG-RANGE-TIP-BINDING" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
                    raise PrRouteDenied(mismatch)
                if parsed.kind == "qualified-v3":
                    qualification = parsed.qualification
                    captured_review = self.captured_review
                    if (
                        execution.stderr
                        or qualification is None
                        or captured_review is None
                        or not captured_review.origin_is_outside_repository
                        or qualification.policy_snapshot_id != captured_review.snapshot_id
                        or not callable(finalize_review)
                    ):
                        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
                    finalized = finalize_review(qualification)
                    if type(finalized) is not tuple or len(finalized) != 2:
                        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
                    review_finalization, review_used_list = finalized
                    finalization_keys = {
                        "inputSnapshotId", "usedList", "currentSnapshotId",
                        "repositorySha256", "status", "reason", "resourcesSettled",
                    }
                    if (
                        type(review_finalization) is not dict
                        or set(review_finalization) != finalization_keys
                        or review_finalization.get("inputSnapshotId") != captured_review.snapshot_id
                        or type(review_used_list) is not list
                        or any(
                            type(row) is not list
                            or len(row) != 2
                            or type(row[0]) is not str
                            or type(row[1]) is not str
                            for row in review_used_list
                        )
                        or review_finalization.get("usedList") != review_used_list
                        or review_finalization.get("status") != "valid"
                        or review_finalization.get("reason") != "none"
                        or review_finalization.get("resourcesSettled") is not True
                    ):
                        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
                if time.monotonic() > float(self.authorization_deadline):
                    raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
            except BaseException:
                self.state = PendingState.FAILED
                raise
            self.consumption_id = secrets.token_hex(16)
            self.state = PendingState.CONSUMED
            return ConsumedAuthoritativeEvidence(
                self.invocation_id, self.binding, parsed, self.consumption_id, execution,
                review_finalization,
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


class QualifiedPublicationEvidence(NamedTuple):
    policy_snapshot_id: str
    used_decisions_b64: str
    applied: int
    applied_set: str
    examined: int | None = None


class PublicationSafetyObservation(NamedTuple):
    kind: str
    receipt: RangeReceiptV3 | None
    qualification: QualifiedPublicationEvidence | None = None


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
    review_finalization: dict | None = None


AuthoritativeScanObservation = ConsumedAuthoritativeEvidence









# P owns publication-specific original-occurrence qualification for BOTH
# generic consent and explicit instructions. Raw answers/event digests and
# this policy's chronology, binding and scan completion remain unchanged.
# Explicit quote/code/tagged-JSON syntax is data; plain inline markers retain
# their existing placement and exact whole-token display compatibility.

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
SCAN_QUALIFIED_STAGED_REGEX = re.compile(
    r"\Apublication-safety: qualified \(staged, "
    r"examined=(?P<examined>0|[1-9][0-9]*), "
    r"policy-snapshot=(?P<policy_snapshot>[0-9a-f]{64}), "
    r"used-decisions=(?P<used_decisions>[A-Za-z0-9+/]+={0,2}), "
    r"applied=(?P<applied>[1-9][0-9]*), "
    r"applied-set=(?P<applied_set>[0-9a-f]{64}), "
    r"unresolved=0, evaluation=complete\)\n\Z"
)
SCAN_QUALIFIED_RANGE_V3_REGEX = re.compile(
    r"\Apublication-safety: qualified \(range, receipt=v3, "
    r"commits=(?P<commits>[1-9][0-9]*), "
    r"commit-set=(?P<commit_set>[0-9a-f]{64}), messages=complete, "
    r"objects=(?P<objects>[1-9][0-9]*), "
    r"object-set=(?P<object_set>[0-9a-f]{64}), "
    r"blobs=(?P<blobs>0|[1-9][0-9]*), "
    r"blob-set=(?P<blob_set>[0-9a-f]{64}), "
    r"blob-bytes=(?P<blob_bytes>0|[1-9][0-9]*), "
    r"text=(?P<text>0|[1-9][0-9]*), "
    r"binary=(?P<binary>0|[1-9][0-9]*), "
    r"subjects=(?P<subjects>0|[1-9][0-9]*), "
    r"subject-set=(?P<subject_set>[0-9a-f]{64}), "
    r"paths=(?P<paths>0|[1-9][0-9]*), "
    r"path-set=(?P<path_set>[0-9a-f]{64}), history=complete, "
    r"remote=(?P<remote>[A-Za-z0-9._~%-]+), "
    r"dst=(?P<dst>[A-Za-z0-9._~%-]+), "
    r"src=(?P<src>[A-Za-z0-9._~%-]+), "
    rf"tip=(?P<tip>{_LOWERCASE_OID_PATTERN}), "
    r"policy-snapshot=(?P<policy_snapshot>[0-9a-f]{64}), "
    r"used-decisions=(?P<used_decisions>[A-Za-z0-9+/]+={0,2}), "
    r"applied=(?P<applied>[1-9][0-9]*), "
    r"applied-set=(?P<applied_set>[0-9a-f]{64}), "
    r"unresolved=0, evaluation=complete\)\n\Z"
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


def _valid_used_decisions_b64(value: str) -> bool:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        return False
    return bool(decoded) and base64.b64encode(decoded).decode("ascii") == value


def parse_publication_safety_observation(text: str) -> PublicationSafetyObservation:
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        return PublicationSafetyObservation("malformed", None)
    if "publication-safety: qualified" in text:
        staged = SCAN_QUALIFIED_STAGED_REGEX.fullmatch(text)
        if staged is not None:
            used_decisions = staged.group("used_decisions")
            examined = int(staged.group("examined"))
            if examined == 0 or not _valid_used_decisions_b64(used_decisions):
                return PublicationSafetyObservation("malformed", None)
            return PublicationSafetyObservation(
                "qualified-staged", None,
                QualifiedPublicationEvidence(
                    staged.group("policy_snapshot"), used_decisions,
                    int(staged.group("applied")), staged.group("applied_set"),
                    examined,
                ),
            )

        qualified = SCAN_QUALIFIED_RANGE_V3_REGEX.fullmatch(text)
        if qualified is None:
            return PublicationSafetyObservation("malformed", None)
        used_decisions = qualified.group("used_decisions")
        if not _valid_used_decisions_b64(used_decisions):
            return PublicationSafetyObservation("malformed", None)
        # Route the shared V3 graph/count/selection invariants through the
        # existing parser. The qualified spelling changes disposition evidence,
        # not the range receipt or its graph contract.
        v3_text = (
            "publication-safety: clean (range, receipt=v3, "
            f"commits={qualified.group('commits')}, "
            f"commit-set={qualified.group('commit_set')}, messages=complete, "
            f"objects={qualified.group('objects')}, "
            f"object-set={qualified.group('object_set')}, "
            f"blobs={qualified.group('blobs')}, "
            f"blob-set={qualified.group('blob_set')}, "
            f"blob-bytes={qualified.group('blob_bytes')}, "
            f"text={qualified.group('text')}, "
            f"binary={qualified.group('binary')}, "
            f"subjects={qualified.group('subjects')}, "
            f"subject-set={qualified.group('subject_set')}, "
            f"paths={qualified.group('paths')}, "
            f"path-set={qualified.group('path_set')}, history=complete, "
            f"remote={qualified.group('remote')}, "
            f"dst={qualified.group('dst')}, "
            f"src={qualified.group('src')}, "
            f"tip={qualified.group('tip')})\n"
        )
        parsed_v3 = parse_publication_safety_observation(v3_text)
        if parsed_v3.kind != "valid-v3" or parsed_v3.receipt is None:
            return PublicationSafetyObservation("malformed", None)
        if parsed_v3.receipt.text <= 0 or parsed_v3.receipt.blob_bytes <= 0:
            return PublicationSafetyObservation("malformed", None)
        return PublicationSafetyObservation(
            "qualified-v3", parsed_v3.receipt,
            QualifiedPublicationEvidence(
                qualified.group("policy_snapshot"), used_decisions,
                int(qualified.group("applied")), qualified.group("applied_set"),
            ),
        )

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
    parsed = parse_publication_pr_grant(text)
    if parsed is None:
        return None
    return ActivePrGrant(parsed.url, parsed.owner, parsed.repo, parsed.number)


def _canonicalize_numeric_pr_grant(
    number: int, authorization_workdir: str, *, preflight: PreflightResult
) -> ActivePrGrant:
    repository_workdir = _normalize_repository_workdir(
        authorization_workdir, subject="authorization", source="authorization-context",
    )
    _prepare_selected_repository_workdir(
        absolute_literal_root_context(preflight.parsed)
        if preflight.parsed is not None else None,
        preflight.repository_workdir,
        preflight.repository_workdir_source,
    )
    git_exe = _resolve_executable("git", repository_workdir)
    gh_exe = _resolve_executable("gh", repository_workdir)
    if git_exe is None or gh_exe is None:
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    repository_workdir = _prove_repository_root(
        repository_workdir, git_exe, subject="authorization", source="authorization-context",
    )
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
    if _prove_repository_root(
        repository_workdir, git_exe, subject="authorization", source="authorization-context",
    ) != repository_workdir:
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    return ActivePrGrant(match.group("url"), owner, repo, number)


@dataclass(slots=True)
class _PrGrantReducer:
    """Reduce genuine-user PR grant state in original transcript order."""

    preflight: PreflightResult
    state: str = "absent"
    grant: ActivePrGrant | SimplePrIntent | None = None
    transcript_workdir: str | None = None
    record_position: int = 0
    last_genuine_user_position: int = -1
    pending_numeric: tuple[ActivePrGrant, str | None, int] | None = None
    prior_scoped_grant: ActivePrGrant | None = None

    def consume(self, entry: dict, raw_record: bytes | None = None) -> None:
        position = self.record_position
        self.record_position += 1
        payload = entry.get("payload")
        if entry.get("type") in ("session_meta", "turn_context"):
            raw_context = payload.get("cwd") if isinstance(payload, dict) else None
            self.transcript_workdir = (
                raw_context if type(raw_context) is str and raw_context else None
            )
        if not is_user_message(entry):
            return
        reply = extract_publication_user_reply(entry)
        action, text = reply.publication_action()
        if action == "malformed":
            self.state, self.grant, self.pending_numeric = "malformed", None, None
            return
        if reply.kind != "structured-answer" and not any(reply.answers):
            return
        normalized = normalize_publication_approval_text(text)

        if self.pending_numeric is not None and self.pending_numeric[1] is None:
            self.state, self.grant, self.pending_numeric = "malformed", None, None
        self.last_genuine_user_position = position

        if action == "revoked":
            self.state, self.grant, self.pending_numeric = "revoked", None, None
            self.prior_scoped_grant = None
            return
        if is_simple_pr_approval(normalized):
            digest = hashlib.sha256(raw_record).hexdigest() if raw_record else ""
            self.state = "simple"
            self.grant = SimplePrIntent(position + 1, digest, self.prior_scoped_grant)
            self.pending_numeric = None
            return
        parsed_grant = _parse_pr_grant(normalized)
        if parsed_grant is not None:
            if parsed_grant.owner:
                self.state, self.grant = "active", parsed_grant
                self.prior_scoped_grant = parsed_grant
                self.pending_numeric = None
                return
            direct_context = entry.get("cwd")
            if direct_context is not None and (
                type(direct_context) is not str or not direct_context
            ):
                self.state, self.grant, self.pending_numeric = "malformed", None, None
                return
            contexts = {
                value
                for value in (direct_context, self.transcript_workdir)
                if value is not None
            }
            if len(contexts) > 1:
                self.state, self.grant, self.pending_numeric = "malformed", None, None
                return
            authorization_workdir = next(iter(contexts), None)
            self.state, self.grant = "active", None
            self.pending_numeric = (parsed_grant, authorization_workdir, position)
            return

    def finish(self) -> tuple[str, ActivePrGrant | SimplePrIntent | None]:
        if self.pending_numeric is None:
            return self.state, self.grant
        parsed_grant, authorization_workdir, position = self.pending_numeric
        if authorization_workdir is None:
            if position != self.last_genuine_user_position:
                self.state, self.grant, self.pending_numeric = "malformed", None, None
                return self.state, self.grant
            if (
                type(self.preflight.repository_workdir) is not str
                or not self.preflight.repository_workdir
            ):
                self.state, self.grant, self.pending_numeric = "malformed", None, None
                return self.state, self.grant
            authorization_workdir = self.preflight.repository_workdir
        self.grant = _canonicalize_numeric_pr_grant(
            parsed_grant.number, authorization_workdir, preflight=self.preflight
        )
        self.state, self.pending_numeric = "active", None
        return self.state, self.grant


def _stream_stable_pr_grant(
    preflight: PreflightResult,
) -> tuple[str, ActivePrGrant | SimplePrIntent | None, str]:
    """Reduce the shared owner's complete, finite, identity-stable history."""

    transcript_path = preflight.transcript_path
    if not transcript_path:
        return "absent", None, HISTORY_STATUS_ABSENT
    reducer = _PrGrantReducer(preflight)
    try:
        _unused_entries, status = read_transcript_history(
            transcript_path,
            byte_cap=None,
            record_cap=None,
            line_byte_cap=None,
            on_record=reducer.consume,
        )
    except PrRouteDenied:
        raise
    except Exception:
        return "absent", None, HISTORY_STATUS_UNREADABLE
    if status != HISTORY_STATUS_FOUND:
        return "absent", None, status
    state, grant = reducer.finish()
    return state, grant, HISTORY_STATUS_FOUND


def _recover_stable_pr_grant(
    preflight: PreflightResult,
) -> tuple[str, ActivePrGrant | SimplePrIntent | None, str]:
    """Retry only one complete reread after a discarded identity-drift snapshot."""
    state, grant, status = _stream_stable_pr_grant(preflight)
    if status == HISTORY_STATUS_IDENTITY_DRIFT:
        return _stream_stable_pr_grant(preflight)
    return state, grant, status


def _binding_sidecar_path(transcript_path: str) -> Path:
    if type(transcript_path) is not str or not transcript_path:
        raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE")
    transcript = Path(transcript_path)
    try:
        if not transcript.is_file():
            raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE")
    except OSError:
        raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE") from None
    return Path(str(transcript) + PR_BINDING_SIDECAR_SUFFIX)


def _repository_identity(repository_workdir: str) -> tuple[int, int]:
    try:
        observed = os.stat(repository_workdir, follow_symlinks=False)
    except OSError:
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=WorkdirDiagnostic(
            "repository-identity", "stat-failed", "repository", "derived-repository", "string",
        )) from None
    return observed.st_dev, observed.st_ino


def _binding_payload(state: PrBindingState) -> dict:
    return {
        "v": 1,
        "anchor": {
            "record": state.anchor_record,
            "sha256": state.anchor_sha256,
        },
        "state": state.state,
        "repositoryIdentity": list(state.repository_identity),
        "remote": state.remote,
        "headRef": state.head_ref,
        "prUrl": state.pr_url,
        "prId": state.pr_id,
        "headRepositoryId": state.head_repository_id,
    }


def _validate_binding_payload(value: object) -> PrBindingState:
    expected = {
        "v", "anchor", "state", "repositoryIdentity", "remote", "headRef",
        "prUrl", "prId", "headRepositoryId",
    }
    if not isinstance(value, dict) or set(value) != expected or value.get("v") != 1:
        raise PrRouteDenied("PRG-AUTH-MALFORMED")
    anchor = value.get("anchor")
    identity = value.get("repositoryIdentity")
    if (
        not isinstance(anchor, dict)
        or set(anchor) != {"record", "sha256"}
        or type(anchor.get("record")) is not int
        or anchor["record"] <= 0
        or not isinstance(anchor.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", anchor["sha256"]) is None
        or not isinstance(identity, list)
        or len(identity) != 2
        or any(type(item) is not int or item < 0 for item in identity)
        or value.get("state") not in {"pending", "bound", "revoked"}
        or not isinstance(value.get("remote"), str)
        or REMOTE_NAME_REGEX.fullmatch(value["remote"]) is None
        or not isinstance(value.get("headRef"), str)
        or not _portable_pr_head_ref(value["headRef"])
    ):
        raise PrRouteDenied("PRG-AUTH-MALFORMED")
    pr_values = (value.get("prUrl"), value.get("prId"), value.get("headRepositoryId"))
    if value["state"] == "pending":
        if pr_values != (None, None, None):
            raise PrRouteDenied("PRG-AUTH-MALFORMED")
    elif value["state"] == "bound" and any(
        not isinstance(item, str) or not item for item in pr_values
    ):
        raise PrRouteDenied("PRG-AUTH-MALFORMED")
    elif value["state"] == "revoked" and pr_values != (None, None, None) and any(
        not isinstance(item, str) or not item for item in pr_values
    ):
        raise PrRouteDenied("PRG-AUTH-MALFORMED")
    if value["state"] == "bound" or (
        value["state"] == "revoked" and pr_values != (None, None, None)
    ):
        if (
            PR_URL_REGEX.fullmatch(value["prUrl"]) is None
            or NODE_ID_REGEX.fullmatch(value["prId"]) is None
            or NODE_ID_REGEX.fullmatch(value["headRepositoryId"]) is None
        ):
            raise PrRouteDenied("PRG-AUTH-MALFORMED")
    return PrBindingState(
        anchor["record"], anchor["sha256"], value["state"], tuple(identity),
        value["remote"], value["headRef"], *pr_values,
    )


def _read_native_binding_state(
    path: Path, *, byte_cap: int, decode_document: Callable[[bytes], object],
) -> object | None:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise PrRouteDenied("PRG-AUTH-MALFORMED") from None
    if (
        not stat.S_ISREG(observed.st_mode)
        or stat.S_ISLNK(observed.st_mode)
        or observed.st_nlink != 1
        or observed.st_size > byte_cap
        or bool(
            getattr(observed, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    ):
        raise PrRouteDenied("PRG-AUTH-MALFORMED")
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            identity_fields = ("st_dev", "st_ino", "st_mode", "st_nlink")
            if tuple(getattr(opened, name) for name in identity_fields) != tuple(
                getattr(observed, name) for name in identity_fields
            ):
                raise PrRouteDenied("PRG-AUTH-MALFORMED")
            read_size = min(byte_cap + 1, observed.st_size + 1)
            raw = stream.read(read_size)
            after_read = os.fstat(stream.fileno())
            stream.seek(0)
            verified = stream.read(read_size)
            after_verify = os.fstat(stream.fileno())
        if len(raw) > byte_cap:
            raise PrRouteDenied("PRG-AUTH-MALFORMED")
        current = path.lstat()
        stable_fields = (
            "st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
            "st_mtime_ns", "st_ctime_ns",
        )
        opened_fields = tuple(getattr(opened, name) for name in stable_fields)
        if (
            opened_fields
            != tuple(getattr(after_read, name) for name in stable_fields)
            or opened_fields
            != tuple(getattr(after_verify, name) for name in stable_fields)
            or tuple(getattr(observed, name) for name in stable_fields)
            != tuple(getattr(current, name) for name in stable_fields)
            or raw != verified
            or len(raw) != opened.st_size
        ):
            raise PrRouteDenied("PRG-AUTH-MALFORMED")
        value = decode_document(raw)
    except PrRouteDenied:
        raise
    except Exception:
        raise PrRouteDenied("PRG-AUTH-MALFORMED") from None
    return value


def _decode_pr_binding_document(raw: bytes) -> PrBindingState:
    return _validate_binding_payload(json.loads(raw.decode("utf-8", errors="strict")))


def _read_binding_state(path: Path) -> PrBindingState | None:
    return _read_native_binding_state(
        path, byte_cap=PR_BINDING_SIDECAR_BYTE_CAP,
        decode_document=_decode_pr_binding_document,
    )


def _binding_lock_path(path: Path) -> Path:
    return path.with_name(path.name + PR_BINDING_LOCK_SUFFIX)


def _binding_file_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_nlink


def _unlink_owned_binding_file(
    path: Path, identity: tuple[int, int, int, int]
) -> bool:
    try:
        current = path.lstat()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    if (
        _binding_file_identity(current) != identity
        or not stat.S_ISREG(current.st_mode)
        or stat.S_ISLNK(current.st_mode)
        or current.st_nlink != 1
        or bool(
            getattr(current, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    ):
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def _acquire_binding_write_lock(path: Path) -> tuple[int, Path, tuple[int, int, int, int]]:
    lock_path = _binding_lock_path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except FileExistsError:
        raise PrRouteDenied("PRG-BINDING-DRIFT") from None
    except Exception:
        raise PrRouteDenied("PRG-INTERNAL") from None
    identity: tuple[int, int, int, int] | None = None
    try:
        metadata = os.fstat(descriptor)
        identity = _binding_file_identity(metadata)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or bool(
                getattr(metadata, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            )
        ):
            raise PrRouteDenied("PRG-BINDING-DRIFT")
        return descriptor, lock_path, identity
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        if identity is not None:
            _unlink_owned_binding_file(lock_path, identity)
        raise


def _release_binding_write_lock(
    descriptor: int,
    lock_path: Path,
    identity: tuple[int, int, int, int],
    *,
    preserve_primary: bool,
) -> None:
    failure_id: str | None = None
    try:
        os.close(descriptor)
    except OSError:
        failure_id = "PRG-INTERNAL"
    if not _unlink_owned_binding_file(lock_path, identity):
        failure_id = failure_id or "PRG-BINDING-DRIFT"
    if failure_id is not None and not preserve_primary:
        raise PrRouteDenied(failure_id)


def _write_native_binding_state(
    path: Path, state: object, *, expected: object | None,
    read_state: Callable[[Path], object | None],
    encode_state: Callable[[object], dict], byte_cap: int,
) -> None:
    payload = json.dumps(
        encode_state(state), ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    if len(payload) > byte_cap:
        raise PrRouteDenied("PRG-INTERNAL")
    lock_fd, lock_path, lock_identity = _acquire_binding_write_lock(path)
    target = path if expected is None else path.with_name(
        path.name + ".tmp-" + secrets.token_hex(8)
    )
    write_fd: int | None = None
    target_identity: tuple[int, int, int, int] | None = None
    committed = False
    primary = True
    try:
        if read_state(path) != expected:
            raise PrRouteDenied("PRG-BINDING-DRIFT")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            write_fd = os.open(target, flags, 0o600)
            target_metadata = os.fstat(write_fd)
            target_identity = _binding_file_identity(target_metadata)
            if (
                not stat.S_ISREG(target_metadata.st_mode)
                or target_metadata.st_nlink != 1
                or bool(
                    getattr(target_metadata, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                )
            ):
                raise OSError("sidecar staging file is not owned and ordinary")
            offset = 0
            while offset < len(payload):
                written = os.write(write_fd, payload[offset:])
                if written <= 0:
                    raise OSError("short sidecar write")
                offset += written
            os.fsync(write_fd)
            os.close(write_fd)
            write_fd = None
            if expected is not None:
                if read_state(path) != expected:
                    raise PrRouteDenied("PRG-BINDING-DRIFT")
                os.replace(target, path)
                committed = True
            if read_state(path) != state:
                raise PrRouteDenied("PRG-BINDING-DRIFT")
            committed = True
        except FileExistsError:
            raise PrRouteDenied("PRG-BINDING-DRIFT") from None
        except PrRouteDenied:
            raise
        except Exception:
            raise PrRouteDenied("PRG-INTERNAL") from None
        primary = False
    finally:
        if write_fd is not None:
            try:
                os.close(write_fd)
            except OSError:
                pass
        if not committed and target_identity is not None:
            _unlink_owned_binding_file(target, target_identity)
        _release_binding_write_lock(
            lock_fd, lock_path, lock_identity, preserve_primary=primary
        )


def _write_binding_state(
    path: Path, state: PrBindingState, *, expected: PrBindingState | None,
) -> None:
    _write_native_binding_state(
        path, state, expected=expected, read_state=_read_binding_state,
        encode_state=_binding_payload, byte_cap=PR_BINDING_SIDECAR_BYTE_CAP,
    )


def _same_binding_anchor(state: PrBindingState, intent: SimplePrIntent) -> bool:
    return (
        state.anchor_record == intent.record
        and state.anchor_sha256 == intent.sha256
    )


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


def _bind_literal_executable_identity(
    literal_executable: str, resolved_git: str, failure_id: str,
) -> None:
    try:
        executable_path = Path(literal_executable).resolve(strict=True)
        resolved_path = Path(resolved_git).resolve(strict=True)
        same_identity = executable_path.is_file() and resolved_path.is_file() and os.path.samefile(
            executable_path, resolved_path
        )
    except Exception:
        same_identity = False
    if not same_identity:
        raise PrRouteDenied(failure_id)


def _bind_pr_literal_executable(
    literal: LiteralPushCommand, resolved_git: str
) -> LiteralPushCommand:
    _bind_literal_executable_identity(
        literal.executable, resolved_git, "PRG-COMMAND-SHAPE"
    )
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
    output_lock = threading.Lock()
    reader_failures: list[BaseException] = []

    def drain(stream, destination: bytearray) -> None:
        try:
            while not overflow.is_set():
                chunk = stream.read(8192)
                if not chunk:
                    return
                with output_lock:
                    if len(destination) + len(chunk) > PROCESS_OUTPUT_BYTE_CAP:
                        overflow.set()
                        return
                    destination.extend(chunk)
        except BaseException as exc:
            with output_lock:
                reader_failures.append(exc)
            overflow.set()

    started: list[threading.Thread] = []
    primary_failure: BaseException | None = None
    primary_traceback = None
    cleanup_failures: list[BaseException] = []
    failed = False
    if process.stdout is None or process.stderr is None:
        primary_failure = RuntimeError("process output pipe unavailable")
        primary_traceback = primary_failure.__traceback__
        readers = ()
        failed = True
    else:
        readers = (
            threading.Thread(target=drain, args=(process.stdout, stdout), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, stderr), daemon=True),
        )
    deadline = time.monotonic() + max(0.0, timeout)
    try:
        for reader in readers:
            reader.start()
            started.append(reader)
        while process.poll() is None:
            if overflow.is_set() or time.monotonic() >= deadline:
                failed = True
                break
            time.sleep(0.01)
    except BaseException as exc:
        primary_failure = exc
        primary_traceback = exc.__traceback__
        failed = True

    termination_attempted = False
    termination_succeeded = False

    def request_termination() -> bool:
        nonlocal termination_attempted, termination_succeeded
        if termination_attempted:
            return termination_succeeded
        termination_attempted = True
        try:
            if process.poll() is not None:
                termination_succeeded = True
                return True
            process.kill()
            termination_succeeded = True
            return True
        except ProcessLookupError:
            termination_succeeded = True
            return True
        except BaseException as exc:
            cleanup_failures.append(exc)
            try:
                termination_succeeded = process.poll() is not None
            except BaseException as observe_exc:
                cleanup_failures.append(observe_exc)
                termination_succeeded = False
            return termination_succeeded

    def wait_for_owned_child() -> None:
        nonlocal failed, primary_failure, primary_traceback
        if termination_attempted and not termination_succeeded:
            return
        try:
            if termination_attempted:
                process.wait()
            else:
                process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            failed = True
            if request_termination():
                try:
                    process.wait()
                except BaseException as exc:
                    cleanup_failures.append(exc)
        except BaseException as exc:
            if primary_failure is None:
                primary_failure = exc
                primary_traceback = exc.__traceback__
            if request_termination():
                try:
                    process.wait()
                except BaseException as cleanup_exc:
                    cleanup_failures.append(cleanup_exc)
            else:
                cleanup_failures.append(exc)

    if failed or overflow.is_set():
        request_termination()
    wait_for_owned_child()

    for reader in started:
        try:
            reader.join(timeout=1.0)
        except BaseException as exc:
            if primary_failure is None:
                primary_failure = exc
                primary_traceback = exc.__traceback__
            cleanup_failures.append(exc)

    live_readers: list[threading.Thread] = []
    for reader in started:
        try:
            if reader.is_alive():
                live_readers.append(reader)
        except BaseException as exc:
            if primary_failure is None:
                primary_failure = exc
                primary_traceback = exc.__traceback__
            cleanup_failures.append(exc)

    if live_readers:
        failed = True
        for stream in (process.stdout, process.stderr):
            if stream is None:
                continue
            try:
                if not stream.closed:
                    stream.close()
            except BaseException as exc:
                cleanup_failures.append(exc)
        for reader in live_readers:
            try:
                reader.join(timeout=1.0)
            except BaseException as exc:
                if primary_failure is None:
                    primary_failure = exc
                    primary_traceback = exc.__traceback__
                cleanup_failures.append(exc)

    for stream in (process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            if not stream.closed:
                stream.close()
        except BaseException as exc:
            cleanup_failures.append(exc)

    unsettled = False
    try:
        unsettled = (
            process.returncode is None
            or any(reader.is_alive() for reader in started)
            or any(stream is not None and not stream.closed for stream in (
                process.stdout, process.stderr
            ))
        )
    except BaseException as exc:
        cleanup_failures.append(exc)
        unsettled = True

    if unsettled:
        cleanup_failures.append(RuntimeError("process resources remain unsettled"))

    def retain_outcome(error: BaseException) -> None:
        outcome = {
            "returncode": process.returncode,
            "stdout": bytes(stdout),
            "stderr": bytes(stderr),
            "complete": False,
            "resourcesSettled": not unsettled,
        }
        try:
            setattr(error, "publication_gate_process_outcome", outcome)
            if unsettled:
                setattr(error, "publication_gate_owned_process", process)
                setattr(error, "publication_gate_owned_readers", tuple(started))
                setattr(error, "publication_gate_owned_streams", (process.stdout, process.stderr))
        except BaseException as capture_failure:
            raise error from capture_failure

    if primary_failure is not None:
        retain_outcome(primary_failure)
        if cleanup_failures:
            raise primary_failure.with_traceback(primary_traceback) from cleanup_failures[0]
        raise primary_failure.with_traceback(primary_traceback)
    if cleanup_failures:
        failure = RuntimeError("process cleanup failed")
        retain_outcome(failure)
        raise failure from cleanup_failures[0]
    if unsettled:
        raise RuntimeError("process resources remain unsettled")
    if failed or overflow.is_set() or reader_failures:
        return None
    return ProcessResult(process.returncode, bytes(stdout), bytes(stderr))


_SCAN_BOOTSTRAP = r'''import base64,builtins,hashlib,json,re,sys,types
def no_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError("duplicate payload member")
        result[key]=value
    return result
def exact_object(value, keys, label):
    if type(value) is not dict or set(value)!=set(keys):
        raise ValueError(label)
    return value
bundle=json.loads(sys.stdin.buffer.read().decode("ascii"),object_pairs_hook=no_duplicates)
exact_object(bundle,("payloadVersion","sources","review"),"payload shape")
if type(bundle["payloadVersion"]) is not int or bundle["payloadVersion"]!=1:
    raise ValueError("payload version")
roles=("hook_common","classifier","posix_helper","windows_job","scanner","publication_review_policy","linked_runtime_subroots")
encoded_sources=exact_object(bundle["sources"],roles,"source roles")
sources={}
for key,value in encoded_sources.items():
    if type(value) is not str: raise ValueError("source encoding")
    raw=base64.b64decode(value,validate=True)
    if base64.b64encode(raw).decode("ascii")!=value: raise ValueError("source encoding")
    sources[key]=raw
review=exact_object(bundle["review"],("schemaVersion","repositoryObservation","snapshot","snapshotId"),"review shape")
if type(review["schemaVersion"]) is not int or review["schemaVersion"]!=1:
    raise ValueError("review version")
if type(review["snapshotId"]) is not str or re.fullmatch(r"[0-9a-f]{64}",review["snapshotId"]) is None:
    raise ValueError("snapshot id")
snapshot=exact_object(review["snapshot"],("schemaVersion","status","origin","rawBase64","rawSha256","diagnostic"),"snapshot shape")
if type(snapshot["schemaVersion"]) is not int or snapshot["schemaVersion"]!=1:
    raise ValueError("snapshot version")
if snapshot["status"]=="captured":
    if snapshot["origin"] is None or type(snapshot["rawBase64"]) is not str or type(snapshot["rawSha256"]) is not str or snapshot["diagnostic"]!="none":
        raise ValueError("captured snapshot shape")
    raw_policy=base64.b64decode(snapshot["rawBase64"],validate=True)
    if base64.b64encode(raw_policy).decode("ascii")!=snapshot["rawBase64"] or hashlib.sha256(raw_policy).hexdigest()!=snapshot["rawSha256"]:
        raise ValueError("captured snapshot bytes")
elif snapshot["status"] in ("absent","unavailable"):
    if snapshot["rawBase64"] is not None or snapshot["rawSha256"] is not None or snapshot["diagnostic"] in (None,"none"):
        raise ValueError("uncaptured snapshot shape")
else:
    raise ValueError("snapshot status")
observation=exact_object(review["repositoryObservation"],("status","repository","diagnostic"),"repository observation shape")
if observation["status"]=="captured":
    repo=exact_object(observation["repository"],("kind","objectFormat","commonGit","worktreeGit","worktreeRoot"),"repository shape")
    for name in ("commonGit","worktreeGit","worktreeRoot"):
        exact_object(repo[name],("pathEncoding","pathBase64","device","inode"),"native directory shape")
    if observation["diagnostic"]!="none": raise ValueError("repository observation diagnostic")
elif observation["status"] in ("not-requested","unavailable"):
    if observation["repository"] is not None: raise ValueError("unobserved repository")
    expected_diagnostic="not-needed" if observation["status"]=="not-requested" else "metadata-unavailable"
    if observation["diagnostic"]!=expected_diagnostic and not (observation["status"]=="unavailable" and observation["diagnostic"]=="unprovable-native-identity"):
        raise ValueError("repository observation diagnostic")
else:
    raise ValueError("repository observation status")
allowed=set(sys.stdlib_module_names)|{"hook_common","_orchestrarium_publication_review_policy_v1","_orchestrarium_linked_runtime_subroots_v1"}
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
posix_helper_name="_orchestrarium_posix_process_group_v1"
posix_helper=types.ModuleType(posix_helper_name)
posix_helper.__file__="<closure>/process_supervision/posix_process_group.py"
sys.modules[posix_helper_name]=posix_helper
exec(compile(sources["posix_helper"],posix_helper.__file__,"exec"),posix_helper.__dict__,posix_helper.__dict__)
windows_job_name="_orchestrarium_windows_job_v1"
windows_job=types.ModuleType(windows_job_name)
windows_job.__file__="<closure>/process_supervision/windows_job.py"
sys.modules[windows_job_name]=windows_job
exec(compile(sources["windows_job"],windows_job.__file__,"exec"),windows_job.__dict__,windows_job.__dict__)
linked_name="_orchestrarium_linked_runtime_subroots_v1"
linked=types.ModuleType(linked_name)
linked.__file__="<closure>/linked_runtime_subroots.py"
sys.modules[linked_name]=linked
exec(compile(sources["linked_runtime_subroots"],linked.__file__,"exec"),linked.__dict__,linked.__dict__)
policy_name="_orchestrarium_publication_review_policy_v1"
policy=types.ModuleType(policy_name)
policy.__file__="<closure>/publication_review_policy.py"
sys.modules[policy_name]=policy
exec(compile(sources["publication_review_policy"],policy.__file__,"exec"),policy.__dict__,policy.__dict__)
if sys.modules.get(linked_name) is not linked or linked.__name__!=linked_name or linked.__file__!="<closure>/linked_runtime_subroots.py":
    raise RuntimeError("linked module identity")
if sys.modules.get(policy_name) is not policy or policy.__name__!=policy_name or policy.__file__!="<closure>/publication_review_policy.py" or getattr(policy,"POLICY_MODULE_CONTRACT_ID",None)!="orchestrarium.publication-review-policy.module.v1":
    raise RuntimeError("policy module identity")
if getattr(policy,"POLICY_MODULE_KEY",None)!=policy_name or getattr(policy,"POLICY_INJECTION_KEY",None)!="__injected_review_policy_module__":
    raise RuntimeError("policy injection contract")
if policy.H("orchestrarium.publication-review.snapshot.v1",snapshot)!=review["snapshotId"]:
    raise RuntimeError("snapshot id")
if len(sys.argv)<3 or sys.argv[1]!="--gate-git-executable":
    raise RuntimeError("git executable contract")
git_executable=sys.argv[2]
scanner_path="<closure>/check-publication-safety.py"
scanner={"__name__":"__main__","__file__":scanner_path,"__package__":None,"__cached__":None,"__injected_find_machine_paths__":finder,"__injected_git_executable__":git_executable,"__injected_posix_process_group_module__":posix_helper,"__injected_windows_job_module__":windows_job,"__injected_review_policy_snapshot__":snapshot,"__injected_review_repository_observation__":observation,"__injected_review_execution__":"gate-captured-v1"}
scanner[policy.POLICY_INJECTION_KEY]=policy
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


def _close_owned_descriptors(fds: list[int]) -> tuple[tuple[int, BaseException], ...]:
    failures: list[tuple[int, BaseException]] = []
    for fd in reversed(tuple(dict.fromkeys(fds))):
        try:
            os.close(fd)
        except BaseException as exc:
            failures.append((fd, exc))
        else:
            while fd in fds:
                fds.remove(fd)
    return tuple(failures)


def _raise_capture_primary(
    primary: BaseException,
    traceback,
    cleanup_failures: tuple[tuple[int, BaseException], ...],
) -> None:
    if cleanup_failures:
        try:
            setattr(primary, "publication_gate_descriptor_cleanup_failures", cleanup_failures)
        except BaseException as retain_error:
            cleanup_failures = (*cleanup_failures, (-1, retain_error))
        raise primary.with_traceback(traceback) from cleanup_failures[0][1]
    raise primary.with_traceback(traceback)


def _open_owned_descriptor(open_descriptor: Callable[[], int], owned_fds: list[int] | None) -> int:
    descriptor: int | None = None
    try:
        descriptor = open_descriptor()
        if owned_fds is not None and descriptor not in owned_fds:
            owned_fds.append(descriptor)
        return descriptor
    except BaseException as primary:
        traceback = primary.__traceback__
        failures: tuple[tuple[int, BaseException], ...] = ()
        if descriptor is not None and (
            owned_fds is None or descriptor not in owned_fds
        ):
            failures = _close_owned_descriptors([descriptor])
        _raise_capture_primary(primary, traceback, failures)


def _open_windows_path(
    path: Path, *, directory: bool, owned_fds: list[int] | None = None,
) -> int:
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
    invalid = ctypes.c_void_p(-1).value
    handle = None
    descriptor: int | None = None
    native_handle_owned = False
    transfer_in_progress = False
    try:
        handle = create_file(str(path), desired_access, share_mode, None, 3, flags, None)
        if handle in (None, invalid):
            raise OSError(ctypes.get_last_error(), "CreateFileW")
        native_handle_owned = True
        transfer_in_progress = True
        descriptor = msvcrt.open_osfhandle(
            int(handle), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        transfer_in_progress = False
        native_handle_owned = False
        if owned_fds is not None:
            owned_fds.append(descriptor)
        return descriptor
    except BaseException as primary:
        traceback = primary.__traceback__
        cleanup_failures: list[tuple[int, BaseException]] = []
        if descriptor is not None and (
            owned_fds is None or descriptor not in owned_fds
        ):
            cleanup_failures.extend(_close_owned_descriptors([descriptor]))
        if transfer_in_progress and handle not in (None, invalid):
            try:
                setattr(primary, "publication_gate_native_handle_outcome", {
                    "handle": int(handle),
                    "ownership": "uncertain-during-crt-transfer",
                    "closeAttempted": False,
                })
            except BaseException as retain_error:
                cleanup_failures.append((int(handle), retain_error))
        elif native_handle_owned:
            try:
                closed = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
                if not closed:
                    cleanup_failures.append((int(handle), OSError(
                        ctypes.get_last_error(), "CloseHandle"
                    )))
            except BaseException as cleanup_error:
                cleanup_failures.append((int(handle), cleanup_error))
        _raise_capture_primary(primary, traceback, tuple(cleanup_failures))


def _open_windows_source(path: Path, *, owned_fds: list[int] | None = None) -> int:
    return _open_windows_path(path, directory=False, owned_fds=owned_fds)


def _capture_directory(
    path: Path, *, owned_fds: list[int] | None = None,
) -> tuple[int, tuple[int, ...]]:
    path_identity = _directory_generation(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if os.name == "posix":
        nofollow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if nofollow is None or directory_flag is None:
            raise ValueError("directory-open-unavailable")
        flags |= nofollow | directory_flag
    fd = _open_owned_descriptor(
        lambda: (
            _open_windows_path(path, directory=True, owned_fds=owned_fds)
            if os.name == "nt"
            else os.open(path, flags)
        ),
        owned_fds,
    )
    try:
        opened_identity = _directory_identity(os.fstat(fd))
        if opened_identity != path_identity:
            raise ValueError("directory-open-identity")
        return fd, opened_identity
    except BaseException as primary:
        traceback = primary.__traceback__
        failures = (
            () if owned_fds is not None and fd in owned_fds
            else _close_owned_descriptors([fd])
        )
        _raise_capture_primary(primary, traceback, failures)


def _capture_source_node(
    path: Path, role: str, *, owned_fds: list[int] | None = None,
) -> tuple[int, SourceNode]:
    path_identity = _regular_identity(path, single_link=True)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if os.name == "posix":
        if nofollow is None:
            raise ValueError("nofollow-unavailable")
        flags |= nofollow
    fd = _open_owned_descriptor(
        lambda: (
            _open_windows_source(path, owned_fds=owned_fds)
            if os.name == "nt"
            else os.open(path, flags)
        ),
        owned_fds,
    )
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
    except BaseException as primary:
        traceback = primary.__traceback__
        failures = (
            () if owned_fds is not None and fd in owned_fds
            else _close_owned_descriptors([fd])
        )
        _raise_capture_primary(primary, traceback, failures)


def _capture_interpreter_handle(
    identity: InterpreterIdentity,
    *, owned_fds: list[int] | None = None,
) -> int:
    path = Path(identity.absolute_resolved_path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if os.name == "posix":
        if nofollow is None:
            raise ValueError("nofollow-unavailable")
        flags |= nofollow
    fd = _open_owned_descriptor(
        lambda: (
            _open_windows_source(path, owned_fds=owned_fds)
            if os.name == "nt"
            else os.open(path, flags)
        ),
        owned_fds,
    )
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
    except BaseException as primary:
        traceback = primary.__traceback__
        failures = (
            () if owned_fds is not None and fd in owned_fds
            else _close_owned_descriptors([fd])
        )
        _raise_capture_primary(primary, traceback, failures)


def _layout_for_gate(gate: Path) -> tuple[SourceLayout, Path]:
    parts = gate.parts
    # Source packs overlap the generic component suffix. Pick the longest
    # declared exact suffix, and refuse ties instead of resolving by table order.
    matches = tuple(
        layout for layout in SOURCE_LAYOUTS
        if len(parts) >= len(layout.gate_suffix)
        and tuple(parts[-len(layout.gate_suffix):]) == layout.gate_suffix
    )
    if not matches:
        raise ValueError("layout")
    longest = max(len(layout.gate_suffix) for layout in matches)
    selected = tuple(layout for layout in matches if len(layout.gate_suffix) == longest)
    if len(selected) != 1:
        raise ValueError("layout-ambiguous")
    layout = selected[0]
    trust_root = gate.parent
    for _index in range(layout.trust_root_up):
        trust_root = trust_root.parent
    return layout, trust_root


def _observe_root_locator(
    gate: Path, layout: SourceLayout, logical_root: Path,
) -> RootLocatorIdentity:
    value = os.lstat(logical_root)
    raw_target = None
    if _is_link_or_reparse(value):
        tag = int(getattr(value, "st_reparse_tag", 0))
        if os.name == "nt":
            if tag == stat.IO_REPARSE_TAG_SYMLINK:
                kind = "symlink"
            elif tag == stat.IO_REPARSE_TAG_MOUNT_POINT:
                kind = "junction"
            else:
                raise ValueError("root-locator-kind")
        elif stat.S_ISLNK(value.st_mode):
            kind = "symlink"
        else:
            raise ValueError("root-locator-kind")
        raw_target = os.readlink(logical_root)
    else:
        _directory_identity(value)
        kind = "directory"
    # Only the selected root is resolved. Fixed descendants are acquired with
    # the ordinary/no-follow owners, so in-component links remain observable.
    physical_root = logical_root.resolve(strict=True)
    physical_gate = physical_root / layout.role_paths[0][1]
    root_identity = _directory_generation(physical_root)
    if _directory_identity(os.stat(logical_root)) != root_identity:
        raise ValueError("root-terminal-identity")
    gate_identity = _regular_identity(gate, single_link=True)
    if _regular_identity(physical_gate, single_link=True) != gate_identity:
        raise ValueError("logical-gate-identity")
    return RootLocatorIdentity(
        str(gate), str(logical_root), kind, _stat_identity(value), raw_target,
        str(physical_root), root_identity, str(physical_gate), gate_identity,
    )


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
    trust_root: Path, paths: tuple[Path, ...], *, owned_fds: list[int] | None = None,
) -> tuple[tuple[int, ...], tuple[PathComponentIdentity, ...]]:
    fds = owned_fds if owned_fds is not None else []
    components: list[PathComponentIdentity] = []
    by_name: dict[str, int] = {}
    try:
        for name, path in _component_paths(trust_root, paths):
            if name == "." or os.name != "posix":
                fd, identity = _capture_directory(path, owned_fds=fds)
            else:
                parent_name, _separator, basename = name.rpartition("/")
                parent_fd = by_name[parent_name or "."]
                expected_identity = _directory_generation(path)
                flags = (
                    os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NOFOLLOW") | getattr(os, "O_DIRECTORY")
                )
                fd = _open_owned_descriptor(
                    lambda: os.open(basename, flags, dir_fd=parent_fd), fds
                )
                identity = _directory_identity(os.fstat(fd))
                named_identity = _directory_identity(os.stat(
                    basename, dir_fd=parent_fd, follow_symlinks=False
                ))
                if identity != expected_identity or named_identity != identity:
                    raise ValueError("directory-open-identity")
            by_name[name] = fd
            components.append(PathComponentIdentity(name, "directory", identity))
        return tuple(fds), tuple(components)
    except BaseException as primary:
        if owned_fds is not None:
            raise
        traceback = primary.__traceback__
        cleanup_failures = _close_owned_descriptors(fds)
        _raise_capture_primary(primary, traceback, cleanup_failures)


def _capture_source_closure() -> tuple[tuple[int, ...], CanonicalSourceClosure]:
    gate = Path(os.path.abspath(__file__))
    layout, logical_root = _layout_for_gate(gate)
    locator = _observe_root_locator(gate, layout, logical_root)
    trust_root_path = Path(locator.physical_root)
    paths = tuple((role, trust_root_path / name) for role, name in layout.role_paths)
    fds: list[int] = []
    nodes: list[SourceNode] = []
    try:
        component_paths = tuple(path for _role, path in paths)
        component_fds, components = _capture_path_components(
            trust_root_path, component_paths, owned_fds=fds
        )
        for role, path in paths:
            fd, node = _capture_source_node(path, role, owned_fds=fds)
            nodes.append(node)
        bootstrap_digest = hashlib.sha256(_SCAN_BOOTSTRAP.encode("utf-8")).hexdigest()
        interpreter_identity = _interpreter_identity()
        _capture_interpreter_handle(interpreter_identity, owned_fds=fds)
        if (
            components[0].identity != locator.physical_root_identity
            or nodes[0].file_identity != locator.gate_identity
            or _observe_root_locator(gate, layout, logical_root) != locator
        ):
            raise ValueError("root-locator-capture-drift")
        digest_owner = hashlib.sha256(b"publication-safety-closure-v3\0")
        digest_owner.update(layout.name.encode("ascii") + b"\0")
        digest_owner.update(json.dumps(
            (layout.role_paths, tuple(getattr(locator, name) for name in locator.__dataclass_fields__)),
            ensure_ascii=True, separators=(",", ":"),
        ).encode("ascii"))
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
            gate_identity, bootstrap_digest, interpreter_identity, locator,
        )
    except BaseException as primary:
        traceback = primary.__traceback__
        cleanup_failures = _close_owned_descriptors(fds)
        _raise_capture_primary(primary, traceback, cleanup_failures)


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
    layout, logical_root = _layout_for_gate(gate)
    if layout != before.layout:
        raise ValueError("layout-drift")
    locator = _observe_root_locator(gate, layout, logical_root)
    if locator != before.root_locator:
        raise ValueError("root-locator-drift")
    trust_root_path = Path(locator.physical_root)
    paths = tuple(trust_root_path / name for _role, name in layout.role_paths)
    if (
        tuple(node.role for node in before.nodes) != tuple(role for role, _name in layout.role_paths)
        or tuple(node.expected_path for node in before.nodes) != tuple(map(str, paths))
        or before.trust_root != before.components[0]
        or before.trust_root.identity != locator.physical_root_identity
        or before.gate_identity != locator.gate_identity
    ):
        raise ValueError("component-relation-drift")
    current_component_paths = _component_paths(
        trust_root_path, paths
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
    if _observe_root_locator(gate, layout, logical_root) != locator:
        raise ValueError("root-locator-recheck-drift")
    return before


def _closure_payload(
    closure: CanonicalSourceClosure,
    review_document: object,
    canonical_bytes: object,
) -> bytes:
    if tuple(node.role for node in closure.nodes) != SOURCE_ROLE_ORDER:
        raise ValueError("source-role-closure")
    if type(review_document) is not dict or set(review_document) != {
        "schemaVersion", "repositoryObservation", "snapshot", "snapshotId",
    }:
        raise ValueError("review-payload-shape")
    if type(review_document.get("schemaVersion")) is not int or review_document["schemaVersion"] != 1:
        raise ValueError("review-payload-version")
    if re.fullmatch(r"[0-9a-f]{64}", review_document.get("snapshotId", "")) is None:
        raise ValueError("review-snapshot-id")
    snapshot = review_document.get("snapshot")
    if type(snapshot) is not dict or set(snapshot) != {
        "schemaVersion", "status", "origin", "rawBase64", "rawSha256", "diagnostic",
    }:
        raise ValueError("review-snapshot-shape")
    repository_observation = review_document.get("repositoryObservation")
    if type(repository_observation) is not dict or set(repository_observation) != {
        "status", "repository", "diagnostic",
    }:
        raise ValueError("review-repository-observation-shape")
    sources = {
        node.role: base64.b64encode(node.source).decode("ascii")
        for node in closure.nodes if node.role != "gate"
    }
    if len(sources) != 7 or tuple(sources) != SOURCE_ROLE_ORDER[1:]:
        raise ValueError("source-role-cardinality")
    encoder = canonical_bytes
    if not callable(encoder):
        raise ValueError("policy-canonical-encoder")
    payload = encoder({
        "payloadVersion": 1,
        "sources": sources,
        "review": review_document,
    })
    if type(payload) is not bytes or not payload.isascii():
        raise ValueError("canonical-payload-bytes")
    return payload


REPOSITORY_QUERY_ORDER = ("topLevel", "commonGit", "worktreeGit", "objectFormat")
REPOSITORY_QUERY_SUFFIXES = {
    "topLevel": ("--show-toplevel",),
    "commonGit": ("--path-format=absolute", "--git-common-dir"),
    "worktreeGit": ("--absolute-git-dir",),
    "objectFormat": ("--show-object-format",),
}


def _capture_repository_observation(
    policy_module: object,
    selected_root: Path,
    git_executable: str,
) -> dict:
    plan = policy_module.repository_query_plan(selected_root)
    if (
        type(plan) is not policy_module.RepositoryQueryPlanV1
        or plan.root != selected_root
    ):
        raise ValueError("repository-query-plan")
    queries = plan.queries
    if type(queries) is not tuple or len(queries) != len(REPOSITORY_QUERY_ORDER):
        raise ValueError("repository-query-cardinality")
    prefix = ("--no-optional-locks", "-C", str(selected_root), "rev-parse")
    results = []
    deadline = time.monotonic() + ORACLE_TIMEOUT_SECONDS
    for index, (query, key) in enumerate(zip(queries, REPOSITORY_QUERY_ORDER)):
        expected_args = (*prefix, *REPOSITORY_QUERY_SUFFIXES[key])
        if (
            type(query) is not policy_module.RepositoryQueryV1
            or query.key != key
            or type(query.git_args) is not tuple
            or query.git_args != expected_args
        ):
            raise ValueError("repository-query-contract")
        timeout = max(0.0, deadline - time.monotonic())
        try:
            outcome = _run_process(
                [git_executable, *query.git_args], timeout, str(plan.root)
            )
        except BaseException as primary:
            process_outcome = getattr(
                primary, "publication_gate_process_outcome", None
            )
            if type(process_outcome) is dict and set(process_outcome) == {
                "returncode", "stdout", "stderr", "complete", "resourcesSettled",
            }:
                failure_kind = (
                    "unsettled"
                    if process_outcome["resourcesSettled"] is not True
                    else "cancelled"
                    if isinstance(primary, KeyboardInterrupt)
                    else "execution-error"
                )
                results.append(policy_module.RepositoryQueryResultV1(
                    key, query.git_args, process_outcome["returncode"],
                    process_outcome["stdout"], process_outcome["stderr"],
                    False, process_outcome["resourcesSettled"], failure_kind,
                ))
            try:
                setattr(primary, "publication_review_query_plan", plan)
                setattr(primary, "publication_review_query_results", tuple(results))
                setattr(primary, "publication_review_query_index", index)
            except BaseException as capture_failure:
                raise primary from capture_failure
            raise
        if outcome is None:
            result = policy_module.RepositoryQueryResultV1(
                key, query.git_args, None, None, None,
                False, True, "none-result",
            )
        else:
            if (
                type(outcome) is not ProcessResult
                or type(outcome.returncode) is not int
                or type(outcome.stdout) is not bytes
                or type(outcome.stderr) is not bytes
            ):
                raise ValueError("repository-query-outcome")
            result = policy_module.RepositoryQueryResultV1(
                key, query.git_args, outcome.returncode, outcome.stdout,
                outcome.stderr, True, True,
                None if outcome.returncode == 0 else "execution-error",
            )
        results.append(result)
    observation = policy_module.repository_from_query_results(plan, tuple(results))
    if type(observation) is not dict or set(observation) != {
        "status", "repository", "diagnostic",
    }:
        raise ValueError("repository-observation")
    return observation


def _capture_review_payload(
    modules: CapturedReviewModules,
    closure: CanonicalSourceClosure,
    selected_root: Path,
    git_executable: str,
) -> CapturedReviewPayload:
    policy_module = modules.policy_module
    if (
        sys.modules.get("_orchestrarium_publication_review_policy_v1")
        is not policy_module
        or getattr(policy_module, "POLICY_MODULE_CONTRACT_ID", None)
        != "orchestrarium.publication-review-policy.module.v1"
    ):
        raise ValueError("policy-module-identity")
    origin = policy_module.resolve_trusted_origin()
    policy_read = policy_module.read_policy_snapshot(origin, selected_root)
    if type(policy_read) is not policy_module.PolicyReadV1:
        raise ValueError("policy-read-result")
    snapshot = policy_read.snapshot
    snapshot_id = policy_read.snapshot_id
    if (
        type(snapshot) is not dict
        or type(policy_read.usable_records) is not tuple
        or type(policy_read.issues) is not tuple
        or policy_module.H(
            "orchestrarium.publication-review.snapshot.v1", snapshot
        ) != snapshot_id
    ):
        raise ValueError("policy-snapshot-result")

    if policy_read.usable_records:
        repository_observation = _capture_repository_observation(
            policy_module, selected_root, git_executable
        )
    else:
        repository_observation = {
            "status": "not-requested",
            "repository": None,
            "diagnostic": "not-needed",
        }
    repository = repository_observation["repository"]
    origin_is_outside = False
    if repository_observation["status"] == "captured":
        origin_is_outside = policy_module.origin_is_outside_repository(
            snapshot, repository
        )
        if type(origin_is_outside) is not bool:
            raise ValueError("policy-origin-exclusion")

    review_document = {
        "schemaVersion": 1,
        "repositoryObservation": repository_observation,
        "snapshot": snapshot,
        "snapshotId": snapshot_id,
    }
    payload = _closure_payload(closure, review_document, policy_module.C)
    return CapturedReviewPayload(
        modules, snapshot, snapshot_id, repository_observation, repository,
        origin_is_outside, payload, hashlib.sha256(payload).hexdigest(),
    )


def _decode_used_decisions(
    policy_module: object,
    encoded: str,
    failure_id: str,
) -> list[list[str]]:
    try:
        raw = base64.b64decode(encoded, validate=True)
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise ValueError("used-list base64")
        value = _strict_json(raw.decode("ascii", errors="strict"), list, failure_id)
    except PrRouteDenied:
        raise
    except Exception:
        raise PrRouteDenied(failure_id) from None
    if (
        type(value) is not list
        or not value
        or any(
            type(row) is not list
            or len(row) != 2
            or type(row[0]) is not str
            or type(row[1]) is not str
            for row in value
        )
    ):
        raise PrRouteDenied(failure_id)
    if policy_module.C(value) != raw:
        raise PrRouteDenied(failure_id)
    return value


def _verify_used_review_currentness(
    captured_review: CapturedReviewPayload,
    qualification: QualifiedPublicationEvidence,
    repository_workdir: str,
    git_executable: str,
    failure_id: str,
) -> tuple[dict, list[list[str]]]:
    policy_module = captured_review.policy_module
    if (
        captured_review.repository is None
        or not captured_review.origin_is_outside_repository
        or qualification.policy_snapshot_id != captured_review.snapshot_id
    ):
        raise PrRouteDenied(failure_id)
    used_list = _decode_used_decisions(
        policy_module, qualification.used_decisions_b64, failure_id
    )
    fresh_observation = _capture_repository_observation(
        policy_module, Path(repository_workdir), git_executable
    )
    if fresh_observation["status"] != "captured":
        raise PrRouteDenied(failure_id)
    fresh_repository = fresh_observation["repository"]
    if not policy_module.origin_is_outside_repository(
        captured_review.snapshot, fresh_repository
    ):
        raise PrRouteDenied(failure_id)
    finalization = policy_module.verify_used(
        captured_review.snapshot, fresh_repository, used_list
    )
    finalization_keys = {
        "inputSnapshotId", "usedList", "currentSnapshotId", "repositorySha256",
        "status", "reason", "resourcesSettled",
    }
    if (
        type(finalization) is not dict
        or set(finalization) != finalization_keys
        or finalization["inputSnapshotId"] != captured_review.snapshot_id
        or finalization["usedList"] != used_list
        or type(finalization["currentSnapshotId"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", finalization["currentSnapshotId"]) is None
        or finalization["repositorySha256"]
        != policy_module.H(
            "orchestrarium.publication-review.repository.v1",
            captured_review.repository,
        )
        or finalization["status"] != "valid"
        or finalization["reason"] != "none"
        or finalization["resourcesSettled"] is not True
    ):
        raise PrRouteDenied(failure_id)
    return finalization, used_list


def _release_captured_review_modules(modules: CapturedReviewModules) -> None:
    failures = []
    for name, module in reversed(modules.registered):
        if sys.modules.get(name) is not module:
            failures.append(name)
            continue
        del sys.modules[name]
    if failures:
        raise ValueError("captured-module-settlement")


def _load_captured_review_modules(
    closure: CanonicalSourceClosure,
) -> CapturedReviewModules:
    if tuple(node.role for node in closure.nodes) != SOURCE_ROLE_ORDER:
        raise ValueError("source-role-closure")
    source_by_role = {node.role: node.source for node in closure.nodes}
    if set(source_by_role) != set(SOURCE_ROLE_ORDER):
        raise ValueError("source-role-cardinality")
    linked_name = "_orchestrarium_linked_runtime_subroots_v1"
    policy_name = "_orchestrarium_publication_review_policy_v1"
    if linked_name in sys.modules or policy_name in sys.modules:
        raise ValueError("captured-module-slot")
    registered: list[tuple[str, object]] = []
    try:
        linked = types.ModuleType(linked_name)
        linked.__file__ = "<closure>/linked_runtime_subroots.py"
        sys.modules[linked_name] = linked
        registered.append((linked_name, linked))
        exec(
            compile(source_by_role["linked_runtime_subroots"], linked.__file__, "exec"),
            linked.__dict__, linked.__dict__,
        )
        if sys.modules.get(linked_name) is not linked:
            raise ValueError("linked-module-identity")

        policy = types.ModuleType(policy_name)
        policy.__file__ = "<closure>/publication_review_policy.py"
        sys.modules[policy_name] = policy
        registered.append((policy_name, policy))
        exec(
            compile(source_by_role["publication_review_policy"], policy.__file__, "exec"),
            policy.__dict__, policy.__dict__,
        )
        if (
            sys.modules.get(policy_name) is not policy
            or getattr(policy, "POLICY_MODULE_CONTRACT_ID", None)
            != "orchestrarium.publication-review-policy.module.v1"
            or getattr(policy, "POLICY_MODULE_KEY", None) != policy_name
            or getattr(policy, "POLICY_INJECTION_KEY", None)
            != "__injected_review_policy_module__"
        ):
            raise ValueError("policy-module-identity")
        return CapturedReviewModules(policy, linked, tuple(registered))
    except BaseException as primary:
        if registered:
            try:
                _release_captured_review_modules(
                    CapturedReviewModules(
                        sys.modules.get(policy_name),
                        sys.modules.get(linked_name),
                        tuple(registered),
                    )
                )
            except BaseException as cleanup:
                raise primary from cleanup
        raise


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
            and type(self.child_identity) is int
            and self.child_identity > 0
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
    name: str = "worker"


class ChildSupervisor:
    """Single immediate owner for a launched scanner child and its workers."""

    def __init__(
        self, process=None, *, attempt_seconds: float = SCAN_SETTLEMENT_ATTEMPT_SECONDS,
    ) -> None:
        self.process = None
        self.supervisor_id = f"supervisor:{id(self)}"
        self.child_identity: int | None = None
        self.workers: list[_OwnedWorker] = []
        self._attempt_seconds = attempt_seconds
        self._attempts_used = 0
        self._operation_errors: list[str] = []
        self._operation_failures: list[tuple[str, BaseException]] = []
        self._settlement: GateSettlement | None = None
        if process is not None:
            self.adopt_process(process)

    def _record_operation_failure(self, name: str, failure: BaseException) -> None:
        self._operation_errors.append(name)
        self._operation_failures.append((name, failure))

    def adopt_process(self, process) -> None:
        if self.process is not None:
            raise RuntimeError("child supervisor already owns a process")
        self.process = process
        self.child_identity = int(process.pid)

    def start_worker(self, worker: threading.Thread, *, name: str = "worker") -> None:
        owned = _OwnedWorker(worker, "starting", name)
        self.workers.append(owned)
        try:
            worker.start()
            owned.start = "started"
        except BaseException as exc:
            self._record_operation_failure("worker-start", exc)
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
        if self.process is None:
            return GateSettlement(GateSettlementState.FAILED_UNSETTLED, None, False)
        if self._attempts_used >= SCAN_SETTLEMENT_MAX_ENTRIES:
            return self._settlement or GateSettlement(
                GateSettlementState.FAILED_UNSETTLED, None, False
            )
        self._attempts_used += 1
        deadline = time.monotonic() + self._attempt_seconds
        process = self.process
        return_code: int | None = None
        try:
            return_code = process.poll()
        except BaseException as exc:
            self._record_operation_failure("poll", exc)
        if return_code is None:
            try:
                process.terminate()
            except BaseException as exc:
                self._record_operation_failure("terminate", exc)
            try:
                return_code = process.wait(timeout=self._remaining(deadline))
            except BaseException as exc:
                self._record_operation_failure("wait", exc)
                try:
                    return_code = process.poll()
                except BaseException as poll_exc:
                    self._record_operation_failure("post-wait-poll", poll_exc)
            if return_code is None:
                try:
                    process.kill()
                except BaseException as exc:
                    self._record_operation_failure("kill", exc)
                try:
                    return_code = process.wait(timeout=self._remaining(deadline))
                except BaseException as exc:
                    self._record_operation_failure("kill-wait", exc)
        try:
            observed_return_code = process.poll()
            if observed_return_code is not None:
                return_code = observed_return_code
        except BaseException as exc:
            self._record_operation_failure("final-poll", exc)

        worker_rows: list[GateWorkerObservation] = []
        worker_terminals: dict[str, list[str]] = {}
        for owned in self.workers:
            worker = owned.worker
            terminal = "unobserved"
            if owned.start == "not-started":
                terminal = "not-started"
            elif owned.start in {"starting", "started"}:
                try:
                    alive = worker.is_alive()
                except BaseException as exc:
                    self._record_operation_failure("worker-observe", exc)
                    alive = None
                if alive is True:
                    try:
                        worker.join(timeout=self._remaining(deadline))
                    except BaseException as exc:
                        self._record_operation_failure("worker-join", exc)
                    try:
                        alive = worker.is_alive()
                    except BaseException as exc:
                        self._record_operation_failure("worker-observe", exc)
                        alive = None
                if alive is True:
                    terminal = "live"
                elif alive is False:
                    if owned.start == "started":
                        terminal = "joined"
                    else:
                        try:
                            if worker.ident is None and worker.native_id is None:
                                terminal = "unobserved"
                            else:
                                terminal = "joined"
                        except BaseException as exc:
                            self._record_operation_failure("worker-identity", exc)
                            terminal = "unobserved"
                elif owned.start == "starting":
                    terminal = "unobserved"
            worker_terminals.setdefault(owned.name, []).append(terminal)
            worker_rows.append(GateWorkerObservation(id(worker), owned.start, terminal, time.monotonic()))

        process_reaped = return_code is not None
        workers_terminal = all(
            row.terminal in {"not-started", "joined"} for row in worker_rows
        )
        stream_rows: list[GateTransportObservation] = []
        stream_values: list[tuple[str, object | None]] = []
        for name in ("stdin", "stdout", "stderr"):
            try:
                stream_values.append((name, getattr(process, name)))
            except BaseException as exc:
                self._record_operation_failure(name + "-observe", exc)
                stream_values.append((name, None))
        can_close_streams = process_reaped and workers_terminal
        for name, stream in stream_values:
            if stream is None:
                # A missing standard pipe is an actual observation, not an
                # unowned participant invented by the supervisor.
                stream_rows.append(GateTransportObservation(
                    name, "absent", True, None, time.monotonic()
                ))
                continue
            try:
                already_closed = bool(stream.closed)
            except BaseException as exc:
                already_closed = False
                self._record_operation_failure(name + "-observe", exc)
            if already_closed:
                stream_rows.append(GateTransportObservation(
                    name, "owned", True, None, time.monotonic()
                ))
                continue
            if not can_close_streams:
                reason = "process-unreaped" if not process_reaped else "worker-unsettled"
                stream_rows.append(GateTransportObservation(
                    name, "owned", False, reason, time.monotonic()
                ))
                continue
            try:
                stream.close()
            except BaseException as exc:
                self._record_operation_failure(name + "-close", exc)
            try:
                closed = bool(stream.closed)
            except BaseException as exc:
                closed = False
                self._record_operation_failure(name + "-observe", exc)
            stream_rows.append(GateTransportObservation(
                name, "owned", closed, None if closed else name + "-close",
                time.monotonic(),
            ))

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
    captured_review = pending.captured_review
    if (
        captured_review is None
        or type(payload) is not bytes
        or payload != captured_review.payload_bytes
        or hashlib.sha256(payload).hexdigest() != captured_review.payload_sha256
    ):
        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
    supervisor = ChildSupervisor()
    process = None
    launched: LaunchedScanInvocation | None = None
    settlement: GateSettlement | None = None
    output = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()
    output_lock = threading.Lock()
    reader_failures: list[BaseException] = []
    feeder_failures: list[BaseException] = []
    bounded = False
    primary_failure: BaseException | None = None
    primary_traceback = None
    settlement_failures: list[BaseException] = []

    def retain_child_outcome(primary: BaseException) -> None:
        actual_streams = []
        if process is not None:
            for name in ("stdin", "stdout", "stderr"):
                try:
                    actual_streams.append(getattr(process, name, None))
                except BaseException as exc:
                    settlement_failures.append(exc)
                    actual_streams.append(None)
        actual_workers = tuple(
            {"name": owned.name, "start": owned.start, "worker": owned.worker}
            for owned in supervisor.workers
        )
        try:
            actual_return_code = None if process is None else process.returncode
        except BaseException as exc:
            settlement_failures.append(exc)
            actual_return_code = None
        outcome = {
            "childIdentity": supervisor.child_identity,
            "returnCode": actual_return_code,
            "stdout": bytes(output["stdout"]),
            "stderr": bytes(output["stderr"]),
            "boundedCompletion": bounded,
            "settlement": settlement,
            "readerFailures": tuple(reader_failures),
            "feederFailures": tuple(feeder_failures),
            "settlementFailures": tuple(settlement_failures),
            "operationFailures": tuple(supervisor._operation_failures),
            "workers": actual_workers,
            "streams": tuple(actual_streams),
            "process": process,
            "supervisor": supervisor,
        }
        try:
            setattr(primary, "publication_gate_child_outcome", outcome)
        except BaseException as retain_error:
            settlement_failures.append(retain_error)
            outcome["settlementFailures"] = tuple(settlement_failures)
            try:
                setattr(primary, "publication_gate_child_outcome", outcome)
            except BaseException:
                pass

    def drain(name: str, stream) -> None:
        try:
            while not overflow.is_set():
                chunk = stream.read(8192)
                if not chunk:
                    return
                with output_lock:
                    total = len(output["stdout"]) + len(output["stderr"])
                    if total + len(chunk) > SCAN_OUTPUT_BYTE_CAP:
                        overflow.set()
                        return
                    output[name].extend(chunk)
        except BaseException as exc:
            reader_failures.append(exc)
            overflow.set()

    def feed() -> None:
        try:
            assert process.stdin is not None
            process.stdin.write(payload)
            process.stdin.close()
        except BaseException as exc:
            feeder_failures.append(exc)

    try:
        process = subprocess.Popen(
            list(pending.exact_argv), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False,
            cwd=repository_workdir,
        )
        supervisor.adopt_process(process)
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
        if process.stdout is None or process.stderr is None or process.stdin is None:
            raise RuntimeError("scanner child pipe unavailable")
        workers = (
            ("stdin", lambda: threading.Thread(target=feed)),
            ("stdout", lambda: threading.Thread(target=drain, args=("stdout", process.stdout))),
            ("stderr", lambda: threading.Thread(target=drain, args=("stderr", process.stderr))),
        )
        for name, construct in workers:
            worker = construct()
            supervisor.start_worker(worker, name=name)
        deadline = time.monotonic() + SCAN_TIMEOUT_SECONDS
        while True:
            return_code = process.poll()
            if return_code is not None:
                bounded = not overflow.is_set()
                break
            if overflow.is_set() or time.monotonic() >= deadline:
                break
            time.sleep(0.01)
    except BaseException as exc:
        primary_failure = exc
        primary_traceback = exc.__traceback__
    finally:
        if process is not None:
            if supervisor.process is None:
                try:
                    # The Popen object has already been acquired by this
                    # invocation. If the first adoption was interrupted, bind
                    # that exact object back to the same owner before any
                    # settlement attempt; do not rely on a successful return
                    # from the interrupted handoff.
                    supervisor.process = process
                    supervisor.child_identity = int(process.pid)
                except BaseException as exc:
                    settlement_failures.append(exc)
            if supervisor.process is process and supervisor.child_identity is None:
                try:
                    supervisor.child_identity = int(process.pid)
                except BaseException as exc:
                    settlement_failures.append(exc)
            try:
                with pending._transition_lock:
                    if pending.state is PendingState.CHILD_OWNED:
                        pending.state = PendingState.SETTLING
            except BaseException as exc:
                settlement_failures.append(exc)
            for _index in range(SCAN_SETTLEMENT_MAX_ENTRIES):
                try:
                    settlement = supervisor.settle()
                except BaseException as exc:
                    settlement_failures.append(exc)
                    continue
                if settlement.complete:
                    break
            try:
                with pending._transition_lock:
                    pending.settlement = settlement
                    if pending.state in {PendingState.CHILD_OWNED, PendingState.SETTLING}:
                        pending.state = (
                            PendingState.SETTLED
                            if (
                                primary_failure is None
                                and not reader_failures
                                and not feeder_failures
                                and not settlement_failures
                                and isinstance(settlement, GateSettlement)
                                and settlement.complete
                                and settlement.execution_eligible
                                and bounded
                                and not overflow.is_set()
                            )
                            else PendingState.FAILED
                        )
            except BaseException as exc:
                settlement_failures.append(exc)
                try:
                    with pending._transition_lock:
                        pending.state = PendingState.FAILED
                except BaseException as state_error:
                    settlement_failures.append(state_error)
        else:
            try:
                with pending._transition_lock:
                    if pending.state is PendingState.PREPARED:
                        pending.state = PendingState.FAILED
            except BaseException as exc:
                settlement_failures.append(exc)

    if process is None:
        if primary_failure is not None:
            if isinstance(primary_failure, OSError):
                raise PrRouteDenied(prefix + "-SCAN-EXECUTION") from primary_failure
            raise primary_failure.with_traceback(primary_traceback)
        raise PrRouteDenied(prefix + "-SCAN-EXECUTION")

    if primary_failure is None and reader_failures:
        primary_failure = reader_failures[0]
        primary_traceback = primary_failure.__traceback__
    if primary_failure is None and feeder_failures:
        primary_failure = feeder_failures[0]
        primary_traceback = primary_failure.__traceback__
    if primary_failure is None and settlement_failures:
        primary_failure = settlement_failures[0]
        primary_traceback = primary_failure.__traceback__

    if primary_failure is None and (
        not isinstance(settlement, GateSettlement)
        or not settlement.complete
        or not settlement.execution_eligible
    ):
        primary_failure = PrRouteDenied(prefix + "-SCAN-EXECUTION")
        primary_traceback = primary_failure.__traceback__
    if primary_failure is not None:
        retain_child_outcome(primary_failure)
        try:
            setattr(primary_failure, "publication_gate_child_settlement_failures", tuple(settlement_failures))
        except BaseException:
            pass
        if isinstance(primary_failure, PrRouteDenied):
            raise primary_failure.with_traceback(primary_traceback)
        if isinstance(primary_failure, Exception):
            raise PrRouteDenied(prefix + "-SCAN-EXECUTION") from primary_failure
        raise primary_failure.with_traceback(primary_traceback)
    if launched is None or not isinstance(settlement, GateSettlement):
        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")

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
    modules: CapturedReviewModules | None = None
    primary_failure: BaseException | None = None
    try:
        try:
            fds, closure_before = _capture_source_closure()
            interpreter_before = _interpreter_identity()
            if closure_before.interpreter_identity != interpreter_before:
                raise ValueError("interpreter-capture")
            modules = _load_captured_review_modules(closure_before)
            captured_review = _capture_review_payload(
                modules, closure_before, Path(repository_workdir), git_exe
            )
        except PrRouteDenied:
            raise
        except Exception as exc:
            if hasattr(exc, "publication_review_query_results"):
                raise PrRouteDenied(prefix + "-SCAN-EXECUTION") from exc
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
            interpreter_before, argv, object(), captured_review,
        )
        launched, records = _run_snapshot_child(
            pending, captured_review.payload_bytes, repository_workdir
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

        def finalize_review(
            qualification: QualifiedPublicationEvidence,
        ) -> tuple[dict, list[list[str]]]:
            return _verify_used_review_currentness(
                captured_review,
                qualification,
                repository_workdir,
                git_exe,
                prefix + "-SCAN-REFUSAL",
            )

        return pending.correlate_and_consume_once(
            launched, records, closure_after, interpreter_after,
            binding_after, freshness_tick,
            finalize_review=finalize_review,
        )
    except BaseException as exc:
        primary_failure = exc
        raise
    finally:
        cleanup_failures: list[BaseException] = []
        if modules is not None:
            try:
                _release_captured_review_modules(modules)
            except BaseException as exc:
                cleanup_failures.append(exc)
        for fd in fds:
            try:
                os.close(fd)
            except BaseException as exc:
                cleanup_failures.append(exc)
        if cleanup_failures:
            if primary_failure is not None:
                try:
                    setattr(
                        primary_failure,
                        "publication_gate_finalization_cleanup_failures",
                        tuple(cleanup_failures),
                    )
                except BaseException:
                    pass
                raise primary_failure from cleanup_failures[0]
            failure = PrRouteDenied(prefix + "-SCAN-PROVENANCE")
            try:
                setattr(
                    failure,
                    "publication_gate_finalization_cleanup_failures",
                    tuple(cleanup_failures),
                )
            except BaseException:
                pass
            raise failure from cleanup_failures[0]


def _run_text(
    argv: list[str],
    deadline: float,
    failure_id: str,
    repository_workdir: str,
    *,
    accepted_codes: tuple[int, ...] = (0,),
    workdir_diagnostic: WorkdirDiagnostic | None = None,
) -> tuple[int, str]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PrRouteDenied(failure_id, workdir_diagnostic=(
            workdir_diagnostic._replace(check="deadline") if workdir_diagnostic else None
        ))
    result = _run_process(argv, remaining, repository_workdir)
    if result is None or result.returncode not in accepted_codes:
        raise PrRouteDenied(failure_id, workdir_diagnostic=(
            workdir_diagnostic._replace(check="process-result") if workdir_diagnostic else None
        ))
    try:
        return result.returncode, result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise PrRouteDenied(failure_id, workdir_diagnostic=(
            workdir_diagnostic._replace(check="decode") if workdir_diagnostic else None
        )) from None


def _normalize_repository_workdir(
    repository_workdir: str, *, subject: str = "invocation", source: str = "unacquired",
) -> str:
    stage = {
        "authorization": "authorization-normalization", "literal": "literal-normalization",
    }.get(subject, "invocation-qualification")
    diagnostic = WorkdirDiagnostic.from_value(stage, "non-string", subject, source, repository_workdir)
    if type(repository_workdir) is not str or not repository_workdir:
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(
            check="non-string" if type(repository_workdir) is not str else "empty",
        ))
    check = "resolve-failed"
    try:
        candidate = Path(repository_workdir)
        if not candidate.is_absolute():
            raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="relative"))
        selected = candidate.resolve(strict=True)
        if not selected.is_dir():
            raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="not-directory"))
        if os.path.normcase(str(selected)) != os.path.normcase(repository_workdir):
            raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="canonical-mismatch"))
        # Case folding may make a reparse alias look like the selected root.
        # Require every lexical component to remain an ordinary directory.
        check = "ordinary-directory"
        for count in range(1, len(candidate.parts) + 1):
            _directory_generation(Path(*candidate.parts[:count]))
    except (OSError, RuntimeError, ValueError):
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check=check)) from None
    return str(selected)


def _prepare_selected_repository_workdir(
    literal_context: tuple[str, str] | None,
    repository_workdir: str,
    repository_workdir_source: str,
) -> str | None:
    """Qualify the selected E and preserve only P-proved literal absence."""
    source = repository_workdir_source if (
        type(repository_workdir_source) is str and repository_workdir_source in {"tool", "envelope"}
    ) else "unacquired"
    diagnostic = WorkdirDiagnostic.from_value(
        "invocation-qualification", "selected-types", "invocation", source, repository_workdir,
    )
    if (
        type(repository_workdir) is not str
        or type(repository_workdir_source) is not str
    ):
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic)
    if literal_context is not None and (
        type(literal_context) is not tuple
        or len(literal_context) != 2
        or any(type(value) is not str for value in literal_context)
        or any(not value or "\x00" in value for value in literal_context)
        or not Path(literal_context[0]).is_absolute()
        or not Path(literal_context[1]).is_absolute()
    ):
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=WorkdirDiagnostic.from_value(
            "invocation-qualification", "literal-context", "literal", "literal", literal_context,
        ))
    if repository_workdir_source in {"tool", "envelope"}:
        return _normalize_repository_workdir(repository_workdir, source=repository_workdir_source)
    if (
        repository_workdir_source == ""
        and repository_workdir == ""
        and literal_context is not None
    ):
        return None
    raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="selection-source"))


def _prove_repository_root(
    repository_workdir: str, git_exe: str, *, subject: str = "repository", source: str = "derived-repository",
) -> str:
    selected = Path(repository_workdir)
    diagnostic = WorkdirDiagnostic(
        "repository-root-proof", "root-output", subject, source, "string",
    )
    _, top_text = _run_text(
        [git_exe, "rev-parse", "--show-toplevel"],
        time.monotonic() + PROCESS_TIMEOUT_SECONDS,
        "PRG-WORKDIR-INVALID",
        repository_workdir,
        workdir_diagnostic=diagnostic,
    )
    rows = top_text.splitlines()
    if len(rows) != 1:
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic)
    try:
        top = Path(rows[0]).resolve(strict=True)
    except (OSError, RuntimeError):
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="resolve-failed")) from None
    if top != selected:
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="root-mismatch"))
    return repository_workdir


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
) -> VerifiedPrOracle:
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
    base_record = _strict_json(base_repo_text, dict, "PRG-PR-UNAVAILABLE")
    base_repo_id, base_default = _repo_record(base_record, f"{owner}/{repo}", "PRG-BINDING-DRIFT")
    if (
        base_repo_id == head_repo_id
        and head_name == base_record["nameWithOwner"]
        and base_record["url"] == f"https://github.com/{head_name}"
    ):
        # One fresh, validated same-repository observation serves both roles.
        head_record = base_record
    else:
        _, head_repo_text = _run_text(
            [gh_exe, "repo", "view", head_name, "--json", repo_fields],
            deadline,
            "PRG-PR-UNAVAILABLE",
            repository_workdir,
        )
        head_record = _strict_json(head_repo_text, dict, "PRG-PR-UNAVAILABLE")
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
    return VerifiedPrOracle(
        target, local_head_rows[0].lower(), pr_id, head_repo_id
    )


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
    dialect: str,
    parsed: ShellParseResult,
    repository_workdir: str,
    repository_workdir_source: str,
) -> bool:
    try:
        try:
            prepared = _prepare_pr_push(
                dialect, parsed, repository_workdir,
                repository_workdir_source,
            )
        except PrRouteDenied as exc:
            if exc.failure_id == "PRG-COMMAND-SHAPE":
                _raise_command_shape("legacy", dialect, parsed, "legacy-strict")
            raise
        try:
            verified = _verify_pr_oracle(
                grant, prepared.literal, prepared.repository_workdir
            )
        except PrRouteDenied as exc:
            if exc.failure_id == "PRG-COMMAND-SHAPE":
                _raise_command_shape("legacy", dialect, parsed, "oracle")
            raise
        binding = PushScanBinding(
            "strict", verified.target.remote, verified.target.destination,
            verified.local_head, verified.local_head,
        )
        _run_authoritative_scan(
            binding, prepared.repository_workdir, prepared.git_exe
        )
        return True
    except PrRouteDenied:
        raise
    except Exception:
        raise PrRouteDenied("PRG-INTERNAL") from None


def _prepare_pr_push(
    dialect: str,
    parsed: ShellParseResult,
    repository_workdir: str,
    repository_workdir_source: str,
) -> PreparedPrPush:
    effective = parsed.effective_publications
    if (
        parsed.strict_projection.status != "canonical"
        or len(effective.records) != 1
        or effective.records[0].kind != "DIRECT"
    ):
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    dialect = _pr_command_dialect(dialect)
    literal = _parse_pr_literal_shape(parsed, dialect)
    literal_context = absolute_literal_root_context(parsed)
    selected_workdir = _prepare_selected_repository_workdir(
        literal_context, repository_workdir, repository_workdir_source
    )
    repository_workdir = _select_pr_repository_workdir(
        literal.repository_root, literal_context, selected_workdir, repository_workdir_source,
    )
    git_exe = _resolve_executable("git", repository_workdir)
    if git_exe is None:
        raise PrRouteDenied("PRG-REMOTE-MISMATCH")
    literal = _bind_pr_literal_executable(literal, git_exe)
    repository_workdir = _prove_repository_root(repository_workdir, git_exe)
    return PreparedPrPush(literal, repository_workdir, git_exe)


def _select_pr_repository_workdir(
    literal_root: str | None,
    literal_context: tuple[str, str] | None,
    selected_workdir: str | None,
    repository_workdir_source: str,
) -> str:
    """Resolve the PR routes' root agreement after their own grammar checks."""
    if literal_root is None:
        if selected_workdir is None:
            raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=WorkdirDiagnostic(
                "invocation-qualification", "missing", "invocation", "absent", "missing",
            ))
        return selected_workdir
    command_root = _normalize_repository_workdir(literal_root, subject="literal", source="literal")
    if literal_context is None:
        if repository_workdir_source == "tool":
            if selected_workdir != command_root:
                raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=WorkdirDiagnostic(
                    "literal-agreement", "root-mismatch", "invocation", "tool", "string",
                ))
        elif repository_workdir_source != "envelope":
            raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=WorkdirDiagnostic(
                "literal-agreement", "selection-source", "invocation", "unacquired", "string",
            ))
    return command_root


def _raise_command_shape(
    route: str,
    dialect: str,
    parsed: ShellParseResult,
    stage: str,
) -> None:
    effective = parsed.effective_publications
    direct = (
        len(effective.records) == 1
        and effective.records[0].kind == "DIRECT"
    )
    safe_dialect = dialect if dialect in {"powershell", "posix", "unsupported"} else "other"
    strict = parsed.strict_projection.status
    if strict not in {"canonical", "noncanonical"}:
        strict = "other"
    allowed_stages = {
        "projection", "command-context", "git-global", "target",
        "executable", "dialect", "root", "oracle", "legacy-strict",
    }
    safe_stage = stage if stage in allowed_stages else "projection"
    error = PrRouteDenied("PRG-COMMAND-SHAPE")
    error.command_shape_diagnostic = (
        route if route in {"simple", "legacy"} else "legacy",
        safe_dialect,
        "true" if direct else "false",
        strict,
        safe_stage,
    )
    raise error


def _prepare_simple_pr_push(
    dialect: str,
    parsed: ShellParseResult,
    repository_workdir: str,
    repository_workdir_source: str,
) -> PreparedPrPush:
    effective = parsed.effective_publications
    if (
        parsed.dialect != dialect
        or dialect not in {"posix", "powershell"}
        or not effective.exact_complete
        or len(effective.records) != 1
        or effective.records[0].kind != "DIRECT"
        or len(parsed.commands) != 1
        or len(parsed.pushes) != 1
        or parsed.normalizations
    ):
        _raise_command_shape("simple", dialect, parsed, "projection")
    push = effective.records[0].push
    command = push.command
    if (
        push is not parsed.pushes[0]
        or not push.only_direct_push
        or not push.only_executable_command
        or push.shell_context not in {"top-level", "call-operator"}
        or command.control_keywords
        or (
            command.boundary_before != "start"
            and not (
                push.shell_context == "call-operator"
                and command.boundary_before == "&"
            )
        )
        or (
            command.boundary_after != "end"
            and not command.trailing_linebreak_only
        )
        or push.environment_assignments
        or push.option_status != "GPO-PARSED"
        or push.push_options
        or push.dry_run
        or len(push.positionals) != 2
        or push.repository_context not in {"ambient", "redirected"}
    ):
        _raise_command_shape("simple", dialect, parsed, "command-context")
    global_options = tuple(push.git_global_options)
    literal_context = absolute_literal_root_context(parsed)
    selected_workdir = _prepare_selected_repository_workdir(
        literal_context, repository_workdir, repository_workdir_source
    )
    if global_options:
        if len(global_options) != 2 or global_options[0] != "-C":
            _raise_command_shape("simple", dialect, parsed, "git-global")
        literal_root = global_options[1]
    else:
        if push.repository_context != "ambient":
            _raise_command_shape("simple", dialect, parsed, "command-context")
        literal_root = None
    repository_workdir = _select_pr_repository_workdir(
        literal_root, literal_context, selected_workdir, repository_workdir_source,
    )
    remote, refspec = push.positionals
    if not REMOTE_NAME_REGEX.fullmatch(remote):
        _raise_command_shape("simple", dialect, parsed, "target")
    prefix = "HEAD:refs/heads/"
    if not refspec.startswith(prefix):
        _raise_command_shape("simple", dialect, parsed, "target")
    head_ref = refspec[len(prefix):]
    if not _portable_pr_head_ref(head_ref):
        _raise_command_shape("simple", dialect, parsed, "target")
    git_exe = _resolve_executable("git", repository_workdir)
    if git_exe is None:
        raise PrRouteDenied("PRG-REMOTE-MISMATCH")
    raw_executable = command.executable
    if Path(raw_executable).is_absolute():
        literal_executable = raw_executable
    elif Path(raw_executable).name == raw_executable and raw_executable.casefold() in {
        "git", "git.exe",
    }:
        literal_executable = git_exe
    else:
        _raise_command_shape("simple", dialect, parsed, "executable")
    prepared_dialect = dialect
    literal = LiteralPushCommand(
        prepared_dialect, literal_executable, remote, refspec,
        PushTarget(remote, f"refs/heads/{head_ref}", head_ref),
        repository_workdir if global_options else None,
    )
    try:
        literal = _bind_pr_literal_executable(literal, git_exe)
    except PrRouteDenied as exc:
        if exc.failure_id == "PRG-COMMAND-SHAPE":
            _raise_command_shape("simple", dialect, parsed, "executable")
        raise
    try:
        repository_workdir = _prove_repository_root(repository_workdir, git_exe)
    except PrRouteDenied as exc:
        if exc.failure_id == "PRG-COMMAND-SHAPE":
            _raise_command_shape("simple", dialect, parsed, "root")
        raise
    return PreparedPrPush(literal, repository_workdir, git_exe)


def _discover_unique_open_pr(
    prepared: PreparedPrPush,
) -> tuple[ActivePrGrant, str, str]:
    gh_exe = _resolve_executable("gh", prepared.repository_workdir)
    if gh_exe is None:
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    _, text = _run_text(
        [
            gh_exe, "pr", "list", "--state", "open", "--head",
            prepared.literal.target.head_ref, "--limit", "2", "--json",
            "id,number,url,headRefName,headRepository",
        ],
        time.monotonic() + ORACLE_TIMEOUT_SECONDS,
        "PRG-PR-UNAVAILABLE",
        prepared.repository_workdir,
    )
    rows = _strict_json(text, list, "PRG-PR-UNAVAILABLE")
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    row = rows[0]
    match = (
        PR_URL_REGEX.fullmatch(row.get("url"))
        if isinstance(row.get("url"), str) else None
    )
    head_repository = row.get("headRepository")
    if (
        match is None
        or row.get("number") != int(match.group("number"))
        or row.get("headRefName") != prepared.literal.target.head_ref
        or not isinstance(row.get("id"), str)
        or NODE_ID_REGEX.fullmatch(row["id"]) is None
        or not isinstance(head_repository, dict)
        or not isinstance(head_repository.get("id"), str)
        or NODE_ID_REGEX.fullmatch(head_repository["id"]) is None
    ):
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    return (
        ActivePrGrant(
            match.group("url"), match.group("owner"), match.group("repo"),
            int(match.group("number")),
        ),
        row["id"],
        head_repository["id"],
    )


def _evaluate_simple_pr_route(
    intent: SimplePrIntent,
    current_marker: bool,
    preflight: PreflightResult,
) -> bool:
    if not intent.sha256:
        raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE")
    prepared = _prepare_simple_pr_push(
        preflight.dialect, preflight.parsed,
        preflight.repository_workdir, preflight.repository_workdir_source,
    )
    identity = _repository_identity(prepared.repository_workdir)
    sidecar_path = _binding_sidecar_path(preflight.transcript_path)
    existing = _read_binding_state(sidecar_path)
    pending = PrBindingState(
        intent.record, intent.sha256, "pending", identity,
        prepared.literal.remote, prepared.literal.target.head_ref,
        None, None, None,
    )
    verified: VerifiedPrOracle | None = None
    if existing is None and not current_marker:
        grant = intent.prior_scoped_grant
        if grant is None:
            raise PrRouteDenied("PRG-AUTH-MALFORMED")
        try:
            verified = _verify_pr_oracle(
                grant, prepared.literal, prepared.repository_workdir
            )
        except PrRouteDenied as exc:
            if exc.failure_id == "PRG-COMMAND-SHAPE":
                _raise_command_shape(
                    "simple", preflight.dialect, preflight.parsed, "oracle"
                )
            raise
        existing = PrBindingState(
            intent.record, intent.sha256, "bound", identity,
            prepared.literal.remote, prepared.literal.target.head_ref,
            grant.url, verified.pr_id, verified.head_repository_id,
        )
        _write_binding_state(sidecar_path, existing, expected=None)
    elif existing is None:
        _write_binding_state(sidecar_path, pending, expected=None)
        existing = pending
    elif not _same_binding_anchor(existing, intent):
        if not current_marker:
            raise PrRouteDenied("PRG-BINDING-DRIFT")
        _write_binding_state(sidecar_path, pending, expected=existing)
        existing = pending
    if (
        existing.repository_identity != identity
        or existing.remote != prepared.literal.remote
        or existing.head_ref != prepared.literal.target.head_ref
    ):
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    if existing.state == "revoked":
        raise PrRouteDenied("PRG-AUTH-MALFORMED")
    if verified is not None:
        pass
    elif existing.state == "pending":
        if not current_marker:
            raise PrRouteDenied("PRG-BINDING-DRIFT")
        grant, pr_id, head_repository_id = _discover_unique_open_pr(prepared)
        try:
            verified = _verify_pr_oracle(
                grant, prepared.literal, prepared.repository_workdir
            )
        except PrRouteDenied as exc:
            if exc.failure_id == "PRG-COMMAND-SHAPE":
                _raise_command_shape(
                    "simple", preflight.dialect, preflight.parsed, "oracle"
                )
            raise
        if (
            verified.pr_id != pr_id
            or verified.head_repository_id != head_repository_id
        ):
            raise PrRouteDenied("PRG-BINDING-DRIFT")
        bound = PrBindingState(
            intent.record, intent.sha256, "bound", identity,
            prepared.literal.remote, prepared.literal.target.head_ref,
            grant.url, pr_id, head_repository_id,
        )
        _write_binding_state(sidecar_path, bound, expected=existing)
        existing = bound
    else:
        match = PR_URL_REGEX.fullmatch(existing.pr_url or "")
        if match is None:
            raise PrRouteDenied("PRG-AUTH-MALFORMED")
        grant = ActivePrGrant(
            match.group("url"), match.group("owner"), match.group("repo"),
            int(match.group("number")),
        )
        try:
            verified = _verify_pr_oracle(
                grant, prepared.literal, prepared.repository_workdir
            )
        except PrRouteDenied as exc:
            if exc.failure_id == "PRG-COMMAND-SHAPE":
                _raise_command_shape(
                    "simple", preflight.dialect, preflight.parsed, "oracle"
                )
            raise
        if (
            verified.pr_id != existing.pr_id
            or verified.head_repository_id != existing.head_repository_id
        ):
            raise PrRouteDenied("PRG-BINDING-DRIFT")
    binding = PushScanBinding(
        "strict", verified.target.remote, verified.target.destination,
        verified.local_head, verified.local_head,
    )
    _run_authoritative_scan(binding, prepared.repository_workdir, prepared.git_exe)
    return True


def _revoke_simple_binding(transcript_path: str) -> None:
    path = _binding_sidecar_path(transcript_path)
    existing = _read_binding_state(path)
    if existing is None or existing.state == "revoked":
        return
    _write_binding_state(
        path, existing._replace(state="revoked"), expected=existing
    )




def _capture_generic_publication_subject(
    binding: PushScanBinding, repository_workdir: str, git_exe: str,
) -> GenericPublicationSubject:
    """Capture existing native repository observations and the effective endpoint."""
    fds: tuple[int, ...] = ()
    modules: CapturedReviewModules | None = None
    primary: BaseException | None = None
    try:
        fds, closure = _capture_source_closure()
        modules = _load_captured_review_modules(closure)
        observed = _capture_repository_observation(
            modules.policy_module, Path(repository_workdir), git_exe,
        )
        if observed["status"] != "captured":
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
        repository = observed["repository"]
        _, endpoints = _run_text(
            [git_exe, "remote", "get-url", "--push", "--all", binding.remote],
            time.monotonic() + ORACLE_TIMEOUT_SECONDS,
            "PGG-CONSENT-ASSOCIATION", repository_workdir,
        )
        rows = endpoints.splitlines()
        if len(rows) != 1 or not rows[0]:
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")

        def identity(key: str) -> tuple[int, int]:
            value = repository[key]
            return int(value["device"]), int(value["inode"])

        result = GenericPublicationSubject(
            repository_workdir, identity("worktreeRoot"), identity("commonGit"),
            identity("worktreeGit"), binding.remote, rows[0], binding.destination,
            repository["objectFormat"], binding.source_oid,
        )
        publication_review_packet(result)  # Validate before exposing scope data.
        return result
    except BaseException as exc:
        primary = exc
        raise
    finally:
        failures: list[BaseException] = []
        if modules is not None:
            try:
                _release_captured_review_modules(modules)
            except BaseException as exc:
                failures.append(exc)
        for fd in fds:
            try:
                os.close(fd)
            except BaseException as exc:
                failures.append(exc)
        if failures:
            if primary is not None:
                raise primary from failures[0]
            raise PrRouteDenied("PGG-CONSENT-ASSOCIATION") from failures[0]


def _prepare_generic_publication(preflight: PreflightResult) -> PreparedGenericPublication:
    """Preserve the existing command/root/executable/current-source qualification."""
    grammar = preflight.generic_decision
    if grammar.status != "PGG-ADMISSIBLE" or grammar.binding is None:
        raise PrRouteDenied(grammar.status)
    remote, destination, source = grammar.binding
    literal_context = (
        absolute_literal_root_context(preflight.parsed)
        if preflight.parsed is not None else None
    )
    selected_workdir = preflight.repository_workdir
    selected_source = preflight.repository_workdir_source
    generic_push_path = (
        preflight.reason_id == "PFP-CONSENT-GENERIC"
        or (
            preflight.reason_id == "PFP-HEAVY"
            and preflight.push_instruction is True
        )
    )
    selected_workdir = _prepare_selected_repository_workdir(
        literal_context, selected_workdir, selected_source
    )
    if selected_workdir is None and not generic_push_path:
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=WorkdirDiagnostic(
            "invocation-qualification", "missing", "invocation", "absent", "missing",
        ))

    literal_executable = None
    if literal_context is not None:
        literal_executable, raw_repository_root = literal_context
        repository_workdir = _normalize_repository_workdir(raw_repository_root, subject="literal", source="literal")
    else:
        if selected_workdir is None:
            raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=WorkdirDiagnostic(
                "invocation-qualification", "missing", "invocation", "absent", "missing",
            ))
        repository_workdir = selected_workdir

    git_exe = _resolve_executable("git", repository_workdir)
    if git_exe is None:
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=WorkdirDiagnostic(
            "executable-resolution", "executable-missing", "executable", "derived-repository", "null",
        ))
    if literal_executable is not None:
        _bind_literal_executable_identity(
            literal_executable, git_exe, "PGG-EXECUTABLE-MISMATCH"
        )
    repository_workdir = _prove_repository_root(repository_workdir, git_exe)
    binding = _resolve_generic_scan_binding(
        remote, destination, source, repository_workdir, git_exe
    )
    subject = _capture_generic_publication_subject(binding, repository_workdir, git_exe)
    return PreparedGenericPublication(repository_workdir, git_exe, binding, subject, source)


def _complete_generic_publication(
    preflight: PreflightResult,
    consent: GenericConsentResult | None = None,
    prepared: PreparedGenericPublication | None = None,
) -> bool:
    """Every generic allow requires actual original receiving plus a NEW scan."""
    try:
        with hold_native_history_source(preflight.transcript_path) as held_source:
            if not isinstance(consent, GenericConsentResult) or consent.state != "pending" or consent.approval is None:
                raise PrRouteDenied("PGG-CONSENT-ASSOCIATION")
            if consent.approval.source_identity != held_source.identity:
                raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
            prepared = prepared or _prepare_generic_publication(preflight)
            before = _capture_generic_publication_subject(
                prepared.requalify_binding(), prepared.repository_workdir, prepared.git_exe,
            )
            if before != prepared.subject:
                raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
            current = receive_generic_publication_consent(
                preflight, before, direct_selection=consent.direct_selection,
            )
            if current != consent or current.state != "pending":
                raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
            _run_authoritative_scan(prepared.binding, prepared.repository_workdir, prepared.git_exe)
            held_source.assert_current()
            after = _capture_generic_publication_subject(
                prepared.requalify_binding(),
                prepared.repository_workdir, prepared.git_exe,
            )
            if after != prepared.subject:
                raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
            received_after = receive_generic_publication_consent(
                preflight, after, direct_selection=consent.direct_selection,
            )
            if (
                received_after.state != "pending" or received_after.approval is None
                or received_after.approval.subject != consent.approval.subject
                or received_after.approval.selection != consent.approval.selection
                or received_after.approval.user_sha256 != consent.approval.user_sha256
                or received_after.approval.source_identity != held_source.identity
            ):
                raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
            return True

    except NativeHistorySourceError:
        raise PrRouteDenied("PGG-CONSENT-CURRENTNESS") from None


def _select_publication_intent(cut: _GenericControlCut, actual_source: _ReceivedGenericSource | None = None) -> str:
    generic_record = cut.intent_record
    if actual_source is not None:
        generic_record = max(generic_record, actual_source.selection.user_record)
    if generic_record > cut.pr_record and (cut.intent_state != "no-intent" or actual_source is not None):
        return "generic"
    if cut.pr_state in {"active", "simple", "revoked", "malformed"}:
        return "pr"
    if cut.intent_record or cut.execution_record:
        return "generic"
    return "none"


def _evaluate_held_publication(preflight: PreflightResult, direct_selection: GenericUserScopeSelection | None, held_source) -> bool:
    """Evaluate only transcript history, PR, scan, receipt and deny policy."""
    validate_preflight_result(preflight)
    generic_cut = _generic_control_cut(preflight.transcript_path, collect_lifecycle=False, preflight=preflight)
    if generic_cut.history_status == HISTORY_STATUS_IDENTITY_DRIFT:
        generic_cut = _generic_control_cut(preflight.transcript_path, collect_lifecycle=False, preflight=preflight)
    if generic_cut.history_status != HISTORY_STATUS_FOUND:
        diagnostic = _with_transcript_read_status(
            preflight.transcript_diagnostic, generic_cut.history_status, "not-run",
        )
        raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE", diagnostic)
    actual_source = None
    if direct_selection is not None:
        actual_source = _receive_selected_generic_source(preflight.transcript_path, direct_selection)
        held_source.assert_current()
        if actual_source.history_sha256 != generic_cut.history_sha256:
            # Requalify one current cut in this SAME held source, not a new
            # namespace. Actual later controls still participate in the choice.
            generic_cut = _generic_control_cut(preflight.transcript_path, collect_lifecycle=False, preflight=preflight)
            actual_source = _receive_selected_generic_source(preflight.transcript_path, direct_selection)
            held_source.assert_current()
            if generic_cut.history_status != HISTORY_STATUS_FOUND or actual_source.history_sha256 != generic_cut.history_sha256:
                raise PrRouteDenied("PGG-CONSENT-CURRENTNESS")
    domain = _select_publication_intent(generic_cut, actual_source)
    if domain == "generic":
        prepared = _prepare_generic_publication(preflight)
        selected = direct_selection if actual_source is not None and actual_source.selection.user_record >= max(generic_cut.intent_record, generic_cut.pr_record) else None
        consent = receive_generic_publication_consent(preflight, prepared.subject, direct_selection=selected)
        if consent.state != "pending":
            raise PrRouteDenied("PGG-CONSENT-" + consent.state.upper())
        return _complete_generic_publication(preflight, consent, prepared)
    if domain != "pr":
        return False
    pr_state, pr_grant = generic_cut.pr_reducer.finish() if generic_cut.pr_reducer is not None else (generic_cut.pr_state, generic_cut.pr_grant)
    if pr_state == "malformed":
        raise PrRouteDenied("PRG-AUTH-MALFORMED")
    if pr_state == "revoked":
        _revoke_simple_binding(preflight.transcript_path)
        return False
    if pr_state == "active" and pr_grant is not None:
        return _evaluate_active_pr_route(
            pr_grant, preflight.dialect, preflight.parsed,
            preflight.repository_workdir, preflight.repository_workdir_source,
        )
    if pr_state == "simple" and isinstance(pr_grant, SimplePrIntent):
        return _evaluate_simple_pr_route(
            pr_grant, preflight.simple_pr_approval, preflight
        )
    return False

def evaluate_heavy(preflight: PreflightResult, *, direct_selection: GenericUserScopeSelection | None = None) -> bool:
    """One held source/domain/state owner; optional actual Root source locators.

    Native entry supplies None. Call-local A is source input, never a success
    flag or cached authority; it is rereceived through the common owner. A
    native source-neutral no-marker generic-after-PR case lacks this port and
    is not inferred from cache/prose or relabelled as native Functional PASS.
    """
    validate_preflight_result(preflight)
    try:
        with hold_native_history_source(preflight.transcript_path) as held_source:
            return _evaluate_held_publication(preflight, direct_selection, held_source)
    except NativeHistorySourceError:
        diagnostic = _with_transcript_read_status(preflight.transcript_diagnostic, HISTORY_STATUS_UNREADABLE, "not-run")
        raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE", diagnostic) from None


_TRANSCRIPT_FAILURE_IDS = frozenset((
    "PRG-TRANSCRIPT-UNAVAILABLE",
))


def _with_transcript_read_status(
    diagnostic: TranscriptDiagnostic | None,
    history: str,
    recovery: str,
) -> TranscriptDiagnostic | None:
    if diagnostic is None:
        return None
    return validate_transcript_diagnostic(
        diagnostic._replace(history=history, recovery=recovery)
    )


def _denial_scope(failure_id: str) -> str:
    if failure_id.startswith("PGG-CONSENT-"):
        return "Generic publication consent unavailable"
    if failure_id == "PGG-PARSE-UNCERTAIN":
        return "Command parsing incomplete"
    if failure_id in _TRANSCRIPT_FAILURE_IDS:
        return "Publication denied"
    if failure_id.startswith("PGG-"):
        return "Generic scan-derived publication denied"
    return "PR-scoped publication denied"


def _format_transcript_diagnostic(diagnostic: TranscriptDiagnostic) -> str:
    checked = validate_transcript_diagnostic(diagnostic)
    return (
        "Transcript diagnostics: "
        f"envelope={checked.envelope}; current-turn={checked.current_turn}; "
        f"history={checked.history}; recovery={checked.recovery}."
    )


def _format_command_shape_diagnostic(value: object) -> str:
    if (
        not isinstance(value, tuple)
        or len(value) != 5
        or value[0] not in {"simple", "legacy"}
        or value[1] not in {"powershell", "posix", "unsupported", "other"}
        or value[2] not in {"true", "false"}
        or value[3] not in {"canonical", "noncanonical", "other"}
        or value[4] not in {
            "projection", "command-context", "git-global", "target",
            "executable", "dialect", "root", "oracle", "legacy-strict",
        }
    ):
        return ""
    return (
        "Command diagnostics: "
        f"route={value[0]}; dialect={value[1]}; direct={value[2]}; "
        f"strict={value[3]}; stage={value[4]}."
    )


def _format_gate_denial(failure_id: str) -> str:
    if failure_id not in SCAN_DENIAL_REASONS:
        failure_id = "PRG-INTERNAL"
    remediation = SCAN_DENIAL_REASONS.get(
        failure_id,
        "Retry only after the publication gate can complete its checks normally.",
    )
    scope = _denial_scope(failure_id)
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
    if result.outcome == "ABSTAIN" and result.continuation == "NONE":
        return 0

    failure_id: str | None = result.failure_id
    transcript_diagnostic = result.transcript_diagnostic
    workdir_diagnostic = result.workdir_diagnostic
    command_shape_diagnostic = None
    if result.continuation == "EVALUATE_HEAVY":
        try:
            if evaluate_heavy(result):
                return 0
        except PrRouteDenied as exc:
            failure_id = exc.failure_id
            transcript_diagnostic = exc.transcript_diagnostic
            workdir_diagnostic = exc.workdir_diagnostic
            command_shape_diagnostic = getattr(
                exc, "command_shape_diagnostic", None
            )
        except Exception:
            pass

    # Deny. PR-route failures intentionally expose only a stable identifier
    # and safe remediation; subprocess output, command text, paths, remotes,
    # and exception details never enter this payload.
    pr_reasons = {
        **SCAN_DENIAL_REASONS,
        "PRG-AUTH-MALFORMED": "Use the exact version-1 PR approval or revocation line in a genuine user message.",
        "PRG-TRANSCRIPT-UNAVAILABLE": "Retry from a readable current session transcript; summaries cannot authorize publication.",
        "PRG-COMMAND-SHAPE": "Use one solitary direct `git push <remote> HEAD:refs/heads/<head>` or `git -C <absolute-root> push <remote> HEAD:refs/heads/<head>` for a simple bound grant; existing Version 1 grants retain the exact absolute Git literal requirement.",
        "PRG-PR-UNAVAILABLE": "Restore authenticated GitHub state access, then retry so the pull request can be checked afresh.",
        "PRG-PR-STATE": "The pull request is not open; obtain a new grant only for an open pull request.",
        "PRG-BINDING-DRIFT": "Refresh the pull-request binding and retry with a current exact grant if needed.",
        "PRG-DESTINATION-UNSAFE": "Choose the current approved non-default pull-request head branch.",
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
        "PGG-PARSE-UNCERTAIN": "Provide the exact command and tool_name from the tool envelope, plus syntax/dialect metadata, so command parsing can be diagnosed.",
        "PGG-REPOSITORY-REDIRECT": "Use the ambient repository without command-local repository redirection.",
        "PGG-ENV-PREFIX": "Run the push without an environment-assignment prefix.",
        "PGG-GIT-GLOBAL-OPTION": "Run the push without Git global options before the push subcommand.",
        "PGG-EXECUTABLE-MISMATCH": "Use the same absolute Git executable in the command and the gate's selected executable for the explicit repository root.",
        "PGG-PUSH-OPTION": "Use only the documented output-only push options with scan-derived credit.",
        "PGG-REMOTE-CARDINALITY": "Name exactly one remote and one refspec.",
        "PGG-REFSPEC-CARDINALITY": "Name exactly one remote and one refspec.",
        "PGG-DESTINATION-SHAPE": "Use a refspec with a non-empty destination.",
        "PGG-RANGE-BINDING": "Correct the remote and destination binding, then retry the same push.",
        "PGG-RANGE-TIP-BINDING": "Keep the approved immutable source distinct from technical HEAD; satisfy the existing scan binding without changing human scope.",
        "PGG-CONSENT-ASSOCIATION": "Receive the actual original user and applicable reviewed-subject association; do not substitute a report, current HEAD or another approval marker.",
        "PGG-CONSENT-PROVENANCE": "Receive the applicable genuine user record and original structured Q/A when required; non-user data cannot authorize.",
        "PGG-CONSENT-HISTORY": "Resolve the selected original-control source and complete relevant later cut through its existing owner.",
        "PGG-CONSENT-CURRENTNESS": "Reconcile the changed original-control/binding inputs; retain genuinely pending authority without reusing a scan.",
        "PGG-CONSENT-CORRUPT": "Resolve the corrupt or contradictory selected control/index through its existing owner; a new marker cannot repair it.",
        "PGG-CONSENT-INSUFFICIENT": "Receive the specific missing original association or lifecycle evidence for the already approved operation; do not request its approval again.",
        "PGG-CONSENT-REVOKED": "Obey the genuine revocation; this original anchor cannot authorize another publication.",
        "PGG-CONSENT-FULFILLED": "The exact intent is fulfilled; an old index or destination reset cannot revive it.",
        "PGG-CONSENT-UNRESOLVED": "Settle the actual correlated target/effect at the existing execution owner; scan completion, Declined or missing output cannot rearm authority.",
        "PGG-CONSENT-SUPERSEDED": "Receive the actually selected later publication intent without downgrading an older scoped approval.",
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
            scope = _denial_scope(failure_id)
            reason = f"{failure_id}: {scope}. {remediation}"
            if failure_id == "PRG-WORKDIR-INVALID" and workdir_diagnostic is not None:
                try:
                    diagnostic = validate_workdir_diagnostic(workdir_diagnostic)
                except (TypeError, ValueError):
                    diagnostic = None
                if diagnostic is not None:
                    reason += (
                        f" Workdir diagnostics: stage={diagnostic.stage}; check={diagnostic.check}; "
                        f"subject={diagnostic.subject}; source={diagnostic.source}; "
                        f"value-kind={diagnostic.value_kind}."
                    )
            if (
                failure_id in _TRANSCRIPT_FAILURE_IDS
                and transcript_diagnostic is not None
            ):
                reason += " " + _format_transcript_diagnostic(
                    transcript_diagnostic
                )
            if failure_id == "PRG-COMMAND-SHAPE":
                detail = _format_command_shape_diagnostic(
                    command_shape_diagnostic
                )
                if detail:
                    reason += " " + detail
    else:
        reason = (
        "Git-push publication gate: this Bash command runs `git push` (an "
        "irreversible publication), but applicable exact pending user consent "
        "and a new gate-owned canonical range scan have not been received.\n\n"
        "Publication requires human review PLUS a leak-check of the content "
        "being published (Publication safety governance).\n\n"
        "  (a) If the user has NOT actually reviewed and approved this exact "
        "push, STOP, report readiness to push, and ask the user to approve. "
        "A genuine `[approve-publication]` input is not an unconditional bypass.\n\n"
        "  (b) If this exact unchanged operation is already approved, receive "
        "its original genuine control, reviewed scope and later state through "
        "the existing owner; do not request the same permission again. Neutral "
        "steering does not expire approval. Every attempt still requires one "
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
