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

# Per-turn override marker — honored ONLY from the last genuine user message.
# User-side only by design: assistant prose can be steered by injected content
# (see the consultant continuation-prompt untrusted-data rule), so unlike
# [skip-bugfix-discipline] this marker never counts from the model's own reply.
APPROVE_MARKER_REGEX = re.compile(r"\[approve-publication\]", re.IGNORECASE)

PR_GRANT_REGEX = re.compile(
    r"^\[approve-pr-publication:v1 pr=(?P<url>https://github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?)/"
    r"(?P<repo>[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?)/pull/"
    r"(?P<number>[1-9][0-9]*))\]$"
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
OID_REGEX = re.compile(r"^[0-9a-fA-F]{40}$")
REMOTE_NAME_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
PR_HEAD_REF_REGEX = re.compile(r"^[A-Za-z0-9._/-]{1,255}$", re.ASCII)
REPO_COMPONENT_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
NODE_ID_REGEX = re.compile(r"^[A-Za-z0-9_=-]{1,256}$")
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
                if parsed.kind != "valid-v2" or parsed.receipt is None:
                    mismatch = "PGG-RANGE-RECEIPT-VERSION" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
                    raise PrRouteDenied(mismatch)
                receipt = parsed.receipt
                if (receipt.remote, receipt.destination) != (
                    self.binding.remote, self.binding.destination
                ):
                    mismatch = "PGG-RANGE-BINDING" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
                    raise PrRouteDenied(mismatch)
                if (
                    receipt.tip != self.binding.source_oid
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


class DataRegion(NamedTuple):
    kind: str
    start: int
    end: int


class PossibleCommandCandidate(NamedTuple):
    dialect: str
    source_span: tuple[int, int]
    words: tuple[str, ...]
    reason: str


class LexicalAtom(NamedTuple):
    value: str
    source_span: tuple[int, int]
    state: str
    literalized: bool
    operator_capable: bool
    token_membership: int


class LexicalOperation(NamedTuple):
    kind: str
    source_span: tuple[int, int]
    contribution: str


class _ShellLexicalState(NamedTuple):
    dialect: str
    atoms: tuple[LexicalAtom, ...]
    removed_spans: tuple[LexicalOperation, ...]
    data_regions: tuple[DataRegion, ...]
    status: str
    normalizations: tuple[LexicalOperation, ...]


class LexicalToken(NamedTuple):
    value: str
    source_spans: tuple[tuple[int, int], ...]
    states: tuple[str, ...]
    literalized: bool


class LexicalSegment(NamedTuple):
    tokens: tuple[str, ...]
    token_records: tuple[LexicalToken, ...]
    boundary_before: str
    boundary_after: str
    source_span: tuple[int, int]


class ShellLexicalRecord(NamedTuple):
    atoms: tuple[LexicalAtom, ...]
    operations: tuple[LexicalOperation, ...]
    removed_spans: tuple[LexicalOperation, ...]
    data_regions: tuple[DataRegion, ...]
    segments: tuple[LexicalSegment, ...]


class CommandIdentity(NamedTuple):
    dialect: str
    depth: int
    parent: CommandIdentity | None
    parent_source_span: tuple[int, int] | None
    ordinal: int
    input_kind: str
    wrapper_id: str | None
    payload_composition: str | None
    contributing_spans: tuple[tuple[int, int], ...]
    root_occurrence: str


class CommandInput(NamedTuple):
    kind: str
    dialect: str
    shell_text: str | None
    argv_records: tuple[LexicalToken, ...]
    payload_composition: str | None
    contributing_tokens: tuple[LexicalToken, ...]


class WrapperExecutableIdentity(NamedTuple):
    original_token: str
    exact_basename: str
    windows_folded_basename: str
    suffix_class: str
    dialect: str


class WrapperOptionSpec(NamedTuple):
    spelling: str
    accepted_forms: tuple[str, ...]
    arity: int
    mode: str | None
    requires_mode: str | None


class WrapperGrammar(NamedTuple):
    wrapper_id: str
    executable_names: tuple[str, ...]
    parent_dialects: tuple[str, ...]
    option_specs: tuple[WrapperOptionSpec, ...]
    option_terminator: str | None
    assignment_rule_id: str | None
    operand_rule: str
    payload_mode: str
    child_dialect: str
    case_sensitive: bool
    allow_payload_tail: bool


class TerminalParticipant(NamedTuple):
    kind: str
    token: LexicalToken
    structural_value: str | None
    classification: str
    reason: str


class WrapperProjection(NamedTuple):
    wrapper_id: str
    parent_identity: CommandIdentity
    consumed_options: tuple[LexicalToken, ...]
    consumed_assignments: tuple[LexicalToken, ...]
    operand_records: tuple[LexicalToken, ...]
    child_input: CommandInput | None
    terminal_state: str
    reason: str
    payload_composition: str | None
    contributing_tokens: tuple[LexicalToken, ...]
    candidate: PossibleCommandCandidate | None
    terminal_participants: tuple[TerminalParticipant, ...]


class StrictLiteralProjection(NamedTuple):
    status: str
    argv: tuple[str, ...]


class OptionOccurrence(NamedTuple):
    spelling: str
    role: str
    polarity: str
    consumed_value_index: int | None


class ExecutableCommand(NamedTuple):
    dialect: str
    tokens: tuple[str, ...]
    token_records: tuple[LexicalToken, ...]
    environment_assignments: tuple[str, ...]
    control_keywords: tuple[str, ...]
    executable: str
    arguments: tuple[str, ...]
    source_span: tuple[int, int]
    ordinal: int
    command_count: int
    boundary_before: str
    boundary_after: str
    sole_canonical_literal: bool
    nesting_context: str
    trailing_linebreak_only: bool
    confidence: str
    normalization_state: str


class GitPushInvocation(NamedTuple):
    command: ExecutableCommand | PossibleCommandCandidate
    executable: str
    environment_assignments: tuple[str, ...]
    git_global_options: tuple[str, ...]
    post_subcommand_tokens: tuple[str, ...]
    push_options: tuple[str, ...]
    positionals: tuple[str, ...]
    repository_context: str
    dry_run: bool
    only_direct_push: bool
    only_executable_command: bool
    git_global_occurrences: tuple[OptionOccurrence, ...]
    push_option_occurrences: tuple[OptionOccurrence, ...]
    option_status: str
    dry_run_state: str
    shell_context: str
    candidate: bool
    normalization_state: str


class EffectivePublicationRecord(NamedTuple):
    record_id: str
    identity: CommandIdentity
    kind: str
    push: GitPushInvocation
    certainty: str
    dry_credit_eligible: bool
    generic_credit_eligible: bool


class EffectivePublicationProjection(NamedTuple):
    records: tuple[EffectivePublicationRecord, ...]
    exact_complete: bool
    eligible_direct_dry: tuple[EffectivePublicationRecord, ...]
    eligible_direct_generic: tuple[EffectivePublicationRecord, ...]


class ShellParseResult(NamedTuple):
    identity: CommandIdentity
    dialect: str
    status: str
    lexical: ShellLexicalRecord
    segments: tuple[LexicalSegment, ...]
    commands: tuple[ExecutableCommand, ...]
    candidates: tuple[PossibleCommandCandidate, ...]
    strict_projection: StrictLiteralProjection
    wrapper_projections: tuple[WrapperProjection, ...]
    children: tuple[ShellParseResult, ...]
    pushes: tuple[GitPushInvocation, ...]
    effective_publications: EffectivePublicationProjection
    scan_execution: bool
    data_regions: tuple[DataRegion, ...]
    normalizations: tuple[LexicalOperation, ...]
    raw_command: str


class ParsedTranscriptCommand(NamedTuple):
    entry_index: int
    occurrence_index: int
    call_id: str
    tool_name: str | None
    dialect: str
    dialect_exact: bool
    parsed: ShellParseResult


class CommandDialectResolution(NamedTuple):
    dialect: str
    exact: bool


class GenericPushDecision(NamedTuple):
    status: str
    binding: tuple[str, str, str] | None


class RangeReceiptV2(NamedTuple):
    files: int
    commits: int
    commit_set: str
    remote: str
    destination: str
    tip: str


class PublicationSafetyObservation(NamedTuple):
    kind: str
    receipt: RangeReceiptV2 | None


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


class PrRouteDenied(Exception):
    def __init__(self, failure_id: str):
        super().__init__(failure_id)
        self.failure_id = failure_id


def _wrapper_option(
    spelling: str,
    arity: int = 0,
    mode: str | None = None,
    requires_mode: str | None = None,
    accepted_forms: tuple[str, ...] | None = None,
) -> WrapperOptionSpec:
    forms = accepted_forms or (("DETACHED",) if arity else ("FLAG",))
    return WrapperOptionSpec(spelling, forms, arity, mode, requires_mode)


ASSIGNMENT_NAME_RULES = {
    "ENV_ASCII_SHELL_NAME_V1": r"[A-Za-z_][A-Za-z0-9_]*",
    "SUDO_ASCII_SHELL_NAME_V1": r"[A-Za-z_][A-Za-z0-9_]*",
}


class WrapperGrammarRegistry:
    """Minimal immutable R12 grammar; policy code never branches by wrapper."""

    _ROW_IDS = (
        "posix-eval",
        "posix-env",
        "posix-command",
        "posix-exec",
        "posix-sudo",
        "posix-shell-command",
        "powershell-host-command",
    )

    _ROWS = (
        WrapperGrammar(
            "posix-eval", ("eval",), ("posix",), (), None, None,
            "compose-all", "SPACE_JOIN_LOGICAL_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-env", ("env",), ("posix",), (), "--", "ENV_ASCII_SHELL_NAME_V1",
            "direct", "DIRECT_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-command", ("command",), ("posix",),
            (
                _wrapper_option("-p"),
                _wrapper_option("-v", mode="query"),
                _wrapper_option("-V", mode="query"),
            ),
            "--", None, "direct", "DIRECT_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-exec", ("exec",), ("posix",),
            (
                _wrapper_option("-c"),
                _wrapper_option("-l"),
                _wrapper_option("-a", arity=1),
            ),
            "--", None, "direct", "DIRECT_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-sudo", ("sudo",), ("posix",), (), "--", "SUDO_ASCII_SHELL_NAME_V1",
            "direct", "DIRECT_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-shell-command", ("bash", "sh", "dash", "zsh"), ("posix",),
            (
                _wrapper_option("-c", arity=1, mode="command"),
                _wrapper_option("-lc", arity=1, mode="command"),
                _wrapper_option("-cl", arity=1, mode="command"),
                _wrapper_option("-l", requires_mode="command"),
                _wrapper_option("--login", requires_mode="command"),
            ),
            "--", None, "selector", "SINGLE_LOGICAL_TOKEN", "posix",
            True, True,
        ),
        WrapperGrammar(
            "powershell-host-command", ("powershell", "pwsh"),
            ("posix", "powershell"),
            (
                _wrapper_option("-Command", arity=1, mode="command"),
                _wrapper_option("-c", arity=1, mode="command"),
                _wrapper_option("-NoProfile"),
                _wrapper_option("-NonInteractive"),
                _wrapper_option("-NoLogo"),
                _wrapper_option("-Mta"),
                _wrapper_option("-Sta"),
                _wrapper_option("-ExecutionPolicy", arity=1),
                _wrapper_option("-InputFormat", arity=1),
                _wrapper_option("-OutputFormat", arity=1),
                _wrapper_option("-WindowStyle", arity=1),
                _wrapper_option("-File", arity=1, mode="file"),
                _wrapper_option("-f", arity=1, mode="file"),
            ),
            None, None, "selector", "SINGLE_LOGICAL_TOKEN", "powershell",
            False, False,
        ),
    )

    @classmethod
    def rows(cls) -> tuple[WrapperGrammar, ...]:
        cls.validate()
        return cls._ROWS

    @classmethod
    def validate(cls) -> None:
        rows = cls._ROWS
        if not isinstance(rows, tuple) or len(rows) != len(cls._ROW_IDS):
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
        if not all(isinstance(row, WrapperGrammar) for row in rows):
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
        if tuple(row.wrapper_id for row in rows) != cls._ROW_IDS:
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
        if tuple(ASSIGNMENT_NAME_RULES) != (
            "ENV_ASCII_SHELL_NAME_V1",
            "SUDO_ASCII_SHELL_NAME_V1",
        ):
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
        try:
            assignment_patterns_valid = all(
                isinstance(pattern, str)
                and bool(pattern)
                and re.compile(pattern) is not None
                for pattern in ASSIGNMENT_NAME_RULES.values()
            )
        except re.error:
            assignment_patterns_valid = False
        if not assignment_patterns_valid:
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")

        for row in rows:
            strings = (
                row.wrapper_id,
                row.operand_rule,
                row.payload_mode,
                row.child_dialect,
            )
            if not all(isinstance(value, str) and value for value in strings):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if (
                not isinstance(row.executable_names, tuple)
                or not row.executable_names
                or not all(
                    isinstance(name, str) and bool(name)
                    for name in row.executable_names
                )
                or len(set(row.executable_names)) != len(row.executable_names)
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if (
                not isinstance(row.parent_dialects, tuple)
                or not row.parent_dialects
                or not all(
                    isinstance(dialect, str)
                    and dialect in {"posix", "powershell"}
                    for dialect in row.parent_dialects
                )
                or len(set(row.parent_dialects)) != len(row.parent_dialects)
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if not isinstance(row.option_specs, tuple):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.option_terminator is not None and (
                not isinstance(row.option_terminator, str)
                or not row.option_terminator
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.assignment_rule_id is not None and (
                not isinstance(row.assignment_rule_id, str)
                or row.assignment_rule_id not in ASSIGNMENT_NAME_RULES
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.operand_rule not in {"compose-all", "direct", "selector"}:
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.payload_mode not in {
                "SPACE_JOIN_LOGICAL_ARGV",
                "DIRECT_ARGV",
                "SINGLE_LOGICAL_TOKEN",
            }:
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.child_dialect not in {"same", "posix", "powershell"}:
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if not isinstance(row.case_sensitive, bool) or not isinstance(
                row.allow_payload_tail, bool
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")

            option_names: set[str] = set()
            for option in row.option_specs:
                if not isinstance(option, WrapperOptionSpec):
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                if not isinstance(option.spelling, str) or not option.spelling:
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                option_key = (
                    option.spelling
                    if row.case_sensitive
                    else option.spelling.lower()
                )
                if option_key in option_names:
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                option_names.add(option_key)
                if (
                    not isinstance(option.accepted_forms, tuple)
                    or not option.accepted_forms
                    or not all(
                        isinstance(form, str)
                        and form in {
                            "FLAG",
                            "DETACHED",
                            "EQUALS_ATTACHED",
                            "SHORT_ATTACHED",
                        }
                        for form in option.accepted_forms
                    )
                    or len(set(option.accepted_forms)) != len(option.accepted_forms)
                ):
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                if (
                    not isinstance(option.arity, int)
                    or isinstance(option.arity, bool)
                    or option.arity not in {0, 1}
                ):
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                for state in (option.mode, option.requires_mode):
                    if state is not None and (
                        not isinstance(state, str) or not state
                    ):
                        raise PrRouteDenied("WPG-REGISTRY-SCHEMA")

    @classmethod
    def identity(cls, executable: str, dialect: str) -> WrapperExecutableIdentity:
        exact = _basename(executable)
        suffix = "EXE" if exact.lower().endswith(".exe") else "NONE"
        folded = exact[:-4].lower() if suffix == "EXE" else exact.lower()
        return WrapperExecutableIdentity(executable, exact, folded, suffix, dialect)

    @classmethod
    def resolve(
        cls, executable: str | WrapperExecutableIdentity, dialect: str | None = None
    ) -> WrapperGrammar | None:
        identity = (
            executable
            if isinstance(executable, WrapperExecutableIdentity)
            else cls.identity(executable, dialect or "unsupported")
        )
        for row in cls.rows():
            if identity.dialect not in row.parent_dialects:
                continue
            names = (
                row.executable_names
                if row.case_sensitive
                else tuple(name.lower() for name in row.executable_names)
            )
            candidate = (
                identity.exact_basename
                if row.case_sensitive
                else identity.windows_folded_basename
            )
            if candidate in names:
                return row
        return None

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
MARKER_MAX_MESSAGE_LENGTH = 200

# Explicit user push-instruction signal (English + Russian). Matched against
# the last genuine user message only; used together with scan evidence.
PUSH_INSTRUCTION_REGEX = re.compile(
    r"(?ix)"
    r"\bpush\b|git\s+push|\bpublish\b|"
    r"запушь|запушить|запушь?те|пушни|пушь|пуш|пушай|пушить|"
    r"залей|залить|"
    r"опубликуй|опубликовать|публикуй"
)

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
# `tip` is captured (and its shape validated as 40 hex characters) because it
# is always part of the real receipt's own text. The legacy generic range
# branch does not compare it; the strict PR route does compare it to a fresh
# `git rev-parse --verify HEAD` result.
SCAN_CLEAN_RANGE_REGEX = re.compile(
    r"^publication-safety:\s*clean\s*\(\s*range\s*,\s*examined\s+(?P<count>[1-9]\d*)\s+files?\s*,"
    r"\s*remote\s+(?P<remote>\S+)\s*,\s*dst\s+(?P<dst>\S+)\s*,\s*tip\s+(?P<tip>[0-9a-f]{40})\s*\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

SCAN_CLEAN_RANGE_V2_REGEX = re.compile(
    r"^publication-safety: clean \(range, receipt=v2, "
    r"files=(?P<files>0|[1-9]\d*), commits=(?P<commits>[1-9]\d*), "
    r"commit-set=(?P<commit_set>[0-9a-f]{64}), messages=complete, "
    r"remote=(?P<remote>[A-Za-z0-9._~%-]+), "
    r"dst=(?P<dst>[A-Za-z0-9._~%-]+), tip=(?P<tip>[0-9a-f]{40})\)$",
    re.MULTILINE,
)
SCAN_CLEAN_RANGE_V2_EMPTY_REGEX = re.compile(
    r"^publication-safety: clean \(range, receipt=v2, files=0, "
    r"commits=0 -- nothing to publish\)$",
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
    v2_matches = list(SCAN_CLEAN_RANGE_V2_REGEX.finditer(text))
    clean_lines = [
        line for line in text.splitlines()
        if line.startswith("publication-safety: clean (")
    ]
    has_failure = bool(
        SCAN_FAILURE_MARKER_REGEX.search(text) or SCAN_TYPED_FAILURE_REGEX.search(text)
    )
    if len(v2_matches) == 1 and len(clean_lines) == 1 and not has_failure:
        match = v2_matches[0]
        remote = _decode_canonical_receipt_token(match.group("remote"))
        destination = _decode_canonical_receipt_token(match.group("dst"))
        if remote is None or destination is None:
            return PublicationSafetyObservation("malformed", None)
        return PublicationSafetyObservation(
            "valid-v2",
            RangeReceiptV2(
                int(match.group("files")),
                int(match.group("commits")),
                match.group("commit_set"),
                remote,
                destination,
                match.group("tip"),
            ),
        )
    if v2_matches or "publication-safety: clean (range, receipt=v2" in text:
        if SCAN_CLEAN_RANGE_V2_EMPTY_REGEX.search(text) and len(clean_lines) == 1 and not has_failure:
            return PublicationSafetyObservation("legacy-nonauthorizing", None)
        return PublicationSafetyObservation("malformed", None)
    if (
        SCAN_CLEAN_TRACKED_REGEX.search(text)
        or SCAN_CLEAN_RANGE_REGEX.search(text)
        or SCAN_CLEAN_PATH_REGEX.search(text)
        or SCAN_CLEAN_RANGE_V2_EMPTY_REGEX.search(text)
    ):
        return PublicationSafetyObservation("legacy-nonauthorizing", None)
    if clean_lines or has_failure:
        return PublicationSafetyObservation("malformed", None)
    return PublicationSafetyObservation("none", None)


# Git global options that consume a separate following value. They are
# retained in the invocation record; this set only identifies their arity.
_GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
_REPOSITORY_ENV_NAMES = {"GIT_DIR", "GIT_WORK_TREE"}
_REPOSITORY_GIT_OPTIONS = {"-C", "--git-dir", "--work-tree", "--namespace"}
_SAFE_PUSH_OPTIONS = {"-q", "--quiet", "-v", "--verbose", "--progress", "--no-progress", "--porcelain"}
_PUSH_REQUIRED_VALUE_OPTIONS = {
    "--repo", "--no-repo", "--receive-pack", "--no-receive-pack",
    "--exec", "--no-exec", "-o", "--push-option", "--no-push-option",
}
_PUSH_REQUIRED_ENUM_OPTIONS = {"--recurse-submodules", "--no-recurse-submodules"}
_PUSH_RECURSE_VALUES = {"check", "on-demand", "no"}
_PUSH_OPTIONAL_GLUED_OPTIONS = {"--force-with-lease", "--signed"}
_PUSH_BOOLEAN_OPTIONS = {
    "-q", "-v", "-n", "-f", "-u", "-4", "-6",
    "--quiet", "--verbose", "--dry-run", "--no-dry-run",
    "--all", "--no-all", "--branches", "--no-branches",
    "--mirror", "--no-mirror", "--delete", "--no-delete",
    "--tags", "--no-tags", "--porcelain", "--no-porcelain",
    "--force", "--no-force", "--force-if-includes", "--no-force-if-includes",
    "--thin", "--no-thin", "--set-upstream", "--no-set-upstream",
    "--progress", "--no-progress", "--prune", "--no-prune",
    "--verify", "--no-verify", "--follow-tags", "--no-follow-tags",
    "--atomic", "--no-atomic", "--ipv4", "--no-ipv4", "--ipv6", "--no-ipv6",
    "--no-force-with-lease", "--no-signed",
}

# Shell keywords that PRECEDE a command without consuming the command slot
# (`if ...; then git push; fi`, `for b in x; do git push; done`).
_SHELL_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!"}


def _is_redirection_operator(token: str) -> bool:
    return ("<" in token or ">" in token) and all(character in "<>&" for character in token)


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


def _line_content(line: str) -> str:
    return line[:-2] if line.endswith("\r\n") else line[:-1] if line.endswith("\n") else line


def _mask_non_newlines(chars: list[str], start: int, end: int) -> None:
    for index in range(start, end):
        if chars[index] not in "\r\n":
            chars[index] = " "


def _posix_heredoc_specs(line: str) -> tuple[list[tuple[str, bool]], bool]:
    """Return literal heredoc delimiters from one command line.

    The parse is all-or-nothing.  POSIX ``<<<`` is an ordinary here-string
    redirection and never enters the heredoc queue.  A delimiter word is
    assembled across adjacent quoted/unquoted/backslash segments after quote
    removal; expansion-bearing or incomplete words are outside this bounded
    grammar and make the whole header uncertain.
    """
    specs: list[tuple[str, bool]] = []
    quote: str | None = None
    index = 0
    while index < len(line):
        character = line[index]
        if quote is not None:
            if quote == '"' and character == "\\":
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character == "\\":
            index += 2
            continue
        if character == "#" and (index == 0 or line[index - 1] in " \t;|&()"):
            break
        if character in "'\"":
            quote = character
            index += 1
            continue
        if not line.startswith("<<", index):
            index += 1
            continue
        if line.startswith("<<<", index):
            index += 3
            continue
        index += 2
        strip_tabs = index < len(line) and line[index] == "-"
        if strip_tabs:
            index += 1
        while index < len(line) and line[index] in " \t":
            index += 1
        if index >= len(line):
            return [], False

        value: list[str] = []
        while index < len(line) and line[index] not in " \t;|&()<>":
            character = line[index]
            if character == "\\":
                index += 1
                if index >= len(line):
                    return [], False
                value.append(line[index])
                index += 1
                continue
            if character == "'":
                end = line.find("'", index + 1)
                if end < 0:
                    return [], False
                value.extend(line[index + 1:end])
                index = end + 1
                continue
            if character == '"':
                index += 1
                while index < len(line) and line[index] != '"':
                    character = line[index]
                    if character == "\\":
                        if index + 1 >= len(line):
                            return [], False
                        escaped = line[index + 1]
                        if escaped in '$`"\\':
                            value.append(escaped)
                            index += 2
                            continue
                        value.append("\\")
                        index += 1
                        continue
                    if character in "$`":
                        return [], False
                    value.append(character)
                    index += 1
                if index >= len(line):
                    return [], False
                index += 1
                continue
            if character in "$`":
                return [], False
            value.append(character)
            index += 1
        delimiter = "".join(value)
        if not delimiter:
            return [], False
        specs.append((delimiter, strip_tabs))
    return specs, True


def _powershell_data_regions(command: str) -> tuple[tuple[DataRegion, ...], str]:
    lines = command.splitlines(keepends=True)
    if command and (not lines or sum(len(line) for line in lines) < len(command)):
        lines.append(command[sum(len(line) for line in lines):])
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)

    regions: list[DataRegion] = []
    block_depth = 0
    block_start = 0
    quote: str | None = None
    line_index = 0
    start_index = 0
    while line_index < len(lines):
        content = _line_content(lines[line_index])
        index = start_index
        start_index = 0
        while index < len(content):
            character = content[index]
            if block_depth:
                if content.startswith("<#", index):
                    block_depth += 1
                    index += 2
                    continue
                if content.startswith("#>", index):
                    block_depth -= 1
                    index += 2
                    if block_depth == 0:
                        regions.append(DataRegion(
                            "powershell-block-comment", block_start, starts[line_index] + index
                        ))
                    continue
                index += 1
                continue
            if quote == "'":
                if character == "'" and index + 1 < len(content) and content[index + 1] == "'":
                    index += 2
                    continue
                if character == "'":
                    quote = None
                index += 1
                continue
            if quote == '"':
                if character == "`":
                    index += 2
                    continue
                if character == '"':
                    quote = None
                index += 1
                continue
            if character == "`":
                index += 2
                continue
            if character == "#":
                break
            if content.startswith("<#", index):
                block_start = starts[line_index] + index
                block_depth = 1
                index += 2
                continue
            if content.startswith(("@'", '@"'), index) and (
                index == 0 or content[index - 1].isspace() or content[index - 1] in "=,(;|&"
            ) and not content[index + 2:].strip():
                delimiter = content[index + 1] + "@"
                cursor = line_index + 1
                while cursor < len(lines):
                    candidate = _line_content(lines[cursor])
                    if candidate.startswith(delimiter) and (
                        len(candidate) == len(delimiter)
                        or candidate[len(delimiter)] in " \t;|&()"
                    ):
                        break
                    cursor += 1
                if cursor >= len(lines):
                    return (), "SCG-UNTERMINATED-DATA"
                regions.append(DataRegion(
                    "powershell-here-string",
                    starts[line_index] + index,
                    starts[cursor] + len(delimiter),
                ))
                line_index = cursor
                content = _line_content(lines[line_index])
                index = len(delimiter)
                continue
            if character in "'\"":
                quote = character
            index += 1
        line_index += 1
    if block_depth or quote is not None:
        return (), "SCG-AMBIGUOUS-DATA"
    return tuple(regions), "SCG-PARSED"


def _mask_shell_data_regions(command: str, dialect: str) -> tuple[str, tuple[DataRegion, ...], str]:
    lines = command.splitlines(keepends=True)
    if command and (not lines or sum(len(line) for line in lines) < len(command)):
        lines.append(command[sum(len(line) for line in lines):])
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)
    pending_regions: list[DataRegion] = []
    if dialect in ("powershell", "posix-compat"):
        ps_regions, ps_status = _powershell_data_regions(command)
        if ps_status != "SCG-PARSED":
            return command, (), ps_status
        pending_regions.extend(ps_regions)

    line_index = 0
    while line_index < len(lines):
        content = _line_content(lines[line_index])
        if dialect in ("posix", "posix-compat"):
            specs, valid = _posix_heredoc_specs(content)
            if not valid:
                return command, (), "SCG-AMBIGUOUS-DATA"
            if specs:
                cursor = line_index + 1
                header_regions: list[DataRegion] = []
                for delimiter, strip_tabs in specs:
                    body_start = starts[cursor] if cursor < len(lines) else len(command)
                    while cursor < len(lines):
                        candidate = _line_content(lines[cursor])
                        comparable = candidate.lstrip("\t") if strip_tabs else candidate
                        if comparable == delimiter:
                            break
                        cursor += 1
                    if cursor >= len(lines):
                        return command, (), "SCG-UNTERMINATED-DATA"
                    region_end = starts[cursor] + len(_line_content(lines[cursor]))
                    header_regions.append(DataRegion("posix-heredoc", body_start, region_end))
                    cursor += 1
                pending_regions.extend(header_regions)
                line_index = cursor
                continue
        line_index += 1
    chars = list(command)
    for region in sorted(pending_regions, key=lambda item: (item.start, item.end)):
        _mask_non_newlines(chars, region.start, region.end)
    return "".join(chars), tuple(pending_regions), "SCG-PARSED"


_LEXICAL_WILDCARD = "\ufff0"
_POWERSHELL_UNSUPPORTED_ESCAPE_STARTERS = frozenset("0abefnrtuv")


def _build_shell_lexical_state(command: str, dialect: str) -> _ShellLexicalState:
    """Run the one bounded provenance-carrying lexical pass for ``command``."""
    _masked, data_regions, data_status = _mask_shell_data_regions(command, dialect)
    atoms: list[LexicalAtom] = []
    operations: list[LexicalOperation] = []
    removed: list[LexicalOperation] = []
    status = data_status
    quote: str | None = None
    token_open = False
    token_membership = -1
    index = 0
    region_index = 0

    def worsen(value: str) -> None:
        nonlocal status
        rank = {
            "SCG-PARSED": 0,
            "SCG-UNPARSEABLE": 1,
            "SCG-AMBIGUOUS-DATA": 2,
            "SCG-UNTERMINATED-DATA": 3,
            "SCG-UNSUPPORTED-ESCAPE": 4,
            "SCG-UNTERMINATED-ESCAPE": 5,
        }
        if rank.get(value, 6) > rank.get(status, 0):
            status = value

    def begin_token() -> int:
        nonlocal token_open, token_membership
        if not token_open:
            token_membership += 1
            token_open = True
        return token_membership

    def emit(
        value: str,
        start: int,
        end: int,
        state: str,
        *,
        literalized: bool = False,
        operator_capable: bool = False,
    ) -> None:
        nonlocal token_open
        if operator_capable or (
            state == "ordinary" and not literalized and value in " \t\r"
        ):
            membership = -1
            token_open = False
        else:
            membership = begin_token()
        atoms.append(LexicalAtom(
            value, (start, end), state, literalized, operator_capable, membership
        ))

    def record(kind: str, start: int, end: int, contribution: str, *, removed_span: bool) -> None:
        operation = LexicalOperation(kind, (start, end), contribution)
        operations.append(operation)
        if removed_span:
            removed.append(operation)

    def in_data(position: int) -> DataRegion | None:
        nonlocal region_index
        while region_index < len(data_regions) and position >= data_regions[region_index].end:
            region_index += 1
        if region_index < len(data_regions):
            region = data_regions[region_index]
            if region.start <= position < region.end:
                return region
        return None

    while index < len(command):
        region = in_data(index)
        if region is not None:
            if command[index] in "\r\n":
                end = index + 2 if command.startswith("\r\n", index) else index + 1
                emit(command[index:end], index, end, "data", operator_capable=True)
                index = end
            else:
                index += 1
            continue

        character = command[index]
        if dialect in ("posix", "posix-compat"):
            if quote == "'":
                if character == "'":
                    quote = None
                    index += 1
                else:
                    emit(character, index, index + 1, "single-quoted", literalized=True)
                    index += 1
                continue
            if quote == '"':
                if character == '"':
                    quote = None
                    index += 1
                    continue
                if character == "\\":
                    if index + 1 >= len(command):
                        worsen("SCG-UNTERMINATED-ESCAPE")
                        emit(_LEXICAL_WILDCARD, index, index + 1, "double-quoted", literalized=True)
                        index += 1
                        continue
                    if command[index + 1] == "\n":
                        record("posix-continuation", index, index + 2, "quoted-argument", removed_span=True)
                        index += 2
                        continue
                    escaped = command[index + 1]
                    if escaped in '$`"\\':
                        emit(escaped, index, index + 2, "double-quoted", literalized=True)
                        record("posix-literal-escape", index, index + 2, "quoted-argument", removed_span=False)
                        index += 2
                        continue
                    emit("\\", index, index + 1, "double-quoted", literalized=True)
                    index += 1
                    continue
                emit(character, index, index + 1, "double-quoted", literalized=True)
                index += 1
                continue
            if character == "#" and not token_open:
                while index < len(command) and command[index] not in "\r\n":
                    index += 1
                continue
            if character == "'":
                begin_token()
                quote = "'"
                index += 1
                continue
            if character == '"':
                begin_token()
                quote = '"'
                index += 1
                continue
            if character == "\\":
                if index + 1 >= len(command):
                    worsen("SCG-UNTERMINATED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, index + 1, "ordinary", literalized=True)
                    index += 1
                    continue
                if command[index + 1] == "\n":
                    record("posix-continuation", index, index + 2, "command-token", removed_span=True)
                    index += 2
                    continue
                if command.startswith("\r\n", index + 1) or command[index + 1] == "\r":
                    end = index + 3 if command.startswith("\r\n", index + 1) else index + 2
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, end, "ordinary", literalized=True)
                    index = end
                    continue
                emit(command[index + 1], index, index + 2, "ordinary", literalized=True)
                record("posix-literal-escape", index, index + 2, "command-token", removed_span=False)
                index += 2
                continue
            operator = character in "();<>|&\n"
            emit(character, index, index + 1, "ordinary", operator_capable=operator)
            index += 1
            continue

        # PowerShell lexical subset.
        if quote == "'":
            if character == "'" and index + 1 < len(command) and command[index + 1] == "'":
                emit("'", index, index + 2, "single-quoted", literalized=True)
                index += 2
            elif character == "'":
                quote = None
                index += 1
            else:
                emit(character, index, index + 1, "single-quoted", literalized=True)
                index += 1
            continue
        if quote == '"':
            if character == '"':
                quote = None
                index += 1
                continue
            if character == "`":
                if index + 1 >= len(command):
                    worsen("SCG-UNTERMINATED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, index + 1, "double-quoted", literalized=True)
                    index += 1
                    continue
                if command.startswith("\r\n", index + 1) or command[index + 1] == "\n":
                    end = index + 3 if command.startswith("\r\n", index + 1) else index + 2
                    value = command[index + 1:end]
                    emit(value, index, end, "double-quoted", literalized=True)
                    record("powershell-preserved-token-newline", index, end, "quoted-argument", removed_span=False)
                    index = end
                    continue
                if command[index + 1] == "\r":
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, index + 2, "double-quoted", literalized=True)
                    index += 2
                    continue
                escaped = command[index + 1]
                if not escaped.isascii() or not escaped.isprintable() or escaped.lower() in _POWERSHELL_UNSUPPORTED_ESCAPE_STARTERS:
                    unsupported_end = index + 2
                    if escaped.lower() == "u" and unsupported_end < len(command) and command[unsupported_end] == "{":
                        closing = command.find("}", unsupported_end + 1, min(len(command), unsupported_end + 9))
                        if closing >= 0:
                            unsupported_end = closing + 1
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, unsupported_end, "double-quoted", literalized=True)
                    index = unsupported_end
                else:
                    emit(escaped, index, index + 2, "double-quoted", literalized=True)
                    record("powershell-literal-escape", index, index + 2, "quoted-argument", removed_span=False)
                    index += 2
                continue
            emit(character, index, index + 1, "double-quoted", literalized=True)
            index += 1
            continue
        if character == "#":
            while index < len(command) and command[index] not in "\r\n":
                index += 1
            continue
        if character == "'":
            begin_token()
            quote = "'"
            index += 1
            continue
        if character == '"':
            begin_token()
            quote = '"'
            index += 1
            continue
        if character == "`":
            if index + 1 >= len(command):
                worsen("SCG-UNTERMINATED-ESCAPE")
                emit(_LEXICAL_WILDCARD, index, index + 1, "ordinary", literalized=True)
                index += 1
                continue
            if command.startswith("\r\n", index + 1):
                end = index + 3
                following = end
                while following < len(command) and command[following] in " \t":
                    following += 1
                if token_open:
                    emit("\n", index, end, "ordinary", operator_capable=True)
                    record("powershell-open-token-crlf-boundary", index, end, "separator-decision", removed_span=True)
                elif following < len(command) and command[following] not in "\r\n":
                    record("powershell-token-boundary-continuation", index, end, "separator-decision", removed_span=True)
                else:
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, end, "ordinary", literalized=True)
                index = end
                continue
            if command[index + 1] == "\n":
                end = index + 2
                following = end
                while following < len(command) and command[following] in " \t":
                    following += 1
                if not token_open and following < len(command) and command[following] not in "\r\n":
                    record("powershell-token-boundary-continuation", index, end, "separator-decision", removed_span=True)
                elif token_open:
                    emit("\n", index, end, "ordinary", literalized=True)
                    record("powershell-preserved-token-newline", index, end, "command-token", removed_span=False)
                else:
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, end, "ordinary", literalized=True)
                index = end
                continue
            if command[index + 1] == "\r":
                worsen("SCG-UNSUPPORTED-ESCAPE")
                emit(_LEXICAL_WILDCARD, index, index + 2, "ordinary", literalized=True)
                index += 2
                continue
            escaped = command[index + 1]
            if not escaped.isascii() or not escaped.isprintable() or escaped.lower() in _POWERSHELL_UNSUPPORTED_ESCAPE_STARTERS:
                unsupported_end = index + 2
                if escaped.lower() == "u" and unsupported_end < len(command) and command[unsupported_end] == "{":
                    closing = command.find("}", unsupported_end + 1, min(len(command), unsupported_end + 9))
                    if closing >= 0:
                        unsupported_end = closing + 1
                worsen("SCG-UNSUPPORTED-ESCAPE")
                emit(_LEXICAL_WILDCARD, index, unsupported_end, "ordinary", literalized=True)
                index = unsupported_end
            else:
                emit(escaped, index, index + 2, "ordinary", literalized=True)
                record("powershell-literal-escape", index, index + 2, "command-token", removed_span=False)
                index += 2
            continue
        operator = character in "();<>|&\n"
        emit(character, index, index + 1, "ordinary", operator_capable=operator)
        index += 1

    if quote is not None:
        worsen("SCG-UNPARSEABLE")
    return _ShellLexicalState(
        dialect, tuple(atoms), tuple(removed), data_regions, status, tuple(operations)
    )


def _tokenize_shell_lexical_state(
    state: _ShellLexicalState,
) -> tuple[LexicalSegment, ...]:
    segments: list[LexicalSegment] = []
    tokens: list[str] = []
    token_records: list[LexicalToken] = []
    token_atoms: list[LexicalAtom] = []
    segment_atoms: list[LexicalAtom] = []
    boundary_before = "start"
    skip_redirection_target = False

    def flush_token() -> None:
        nonlocal token_atoms, skip_redirection_target
        if not token_atoms:
            return
        value = "".join(atom.value for atom in token_atoms)
        if skip_redirection_target:
            skip_redirection_target = False
        else:
            tokens.append(value)
            states = tuple(dict.fromkeys(atom.state for atom in token_atoms))
            token_records.append(LexicalToken(
                value,
                tuple(atom.source_span for atom in token_atoms),
                states,
                any(atom.literalized for atom in token_atoms),
            ))
            segment_atoms.extend(token_atoms)
        token_atoms = []

    def flush_segment(boundary_after: str) -> None:
        nonlocal tokens, token_records, segment_atoms
        flush_token()
        if not tokens:
            return
        start = min(atom.source_span[0] for atom in segment_atoms)
        end = max(atom.source_span[1] for atom in segment_atoms)
        segments.append(LexicalSegment(
            tuple(tokens), tuple(token_records), boundary_before, boundary_after, (start, end)
        ))
        tokens = []
        token_records = []
        segment_atoms = []

    index = 0
    atoms = state.atoms
    while index < len(atoms):
        atom = atoms[index]
        if atom.operator_capable:
            flush_token()
            operator_atoms = [atom]
            index += 1
            while index < len(atoms):
                following = atoms[index]
                if not following.operator_capable or following.source_span[0] != operator_atoms[-1].source_span[1]:
                    break
                operator_atoms.append(following)
                index += 1
            operator = "".join(item.value for item in operator_atoms)
            if _is_redirection_operator(operator):
                if tokens and tokens[-1].isdigit() and segment_atoms and (
                    segment_atoms[-1].source_span[1] == operator_atoms[0].source_span[0]
                ) and all(
                    item.state == "ordinary" and not item.literalized
                    for item in segment_atoms
                    if item.token_membership == segment_atoms[-1].token_membership
                ):
                    tokens.pop()
                    token_records.pop()
                    io_membership = segment_atoms[-1].token_membership
                    segment_atoms = [
                        item for item in segment_atoms if item.token_membership != io_membership
                    ]
                skip_redirection_target = True
                continue
            flush_segment(operator)
            boundary_before = operator
            continue
        if atom.state == "ordinary" and not atom.literalized and atom.value in " \t\r":
            flush_token()
        else:
            token_atoms.append(atom)
        index += 1
    flush_segment("end")
    return tuple(segments)


def _candidate_word_matches(value: str, target: str) -> bool:
    normalized = _normalized_command_word(value)
    pieces = normalized.split(_LEXICAL_WILDCARD)
    pattern = "^" + ".?".join(re.escape(piece) for piece in pieces) + "$"
    return re.fullmatch(pattern, target, re.IGNORECASE) is not None


def _candidate_patterns_from_segments(
    segments: tuple[LexicalSegment, ...], dialect: str, reason: str
) -> tuple[PossibleCommandCandidate, ...]:
    candidates: list[PossibleCommandCandidate] = []
    for segment in segments:
        words: list[str] = []
        for token in segment.tokens:
            pieces = token.split()
            words.extend(pieces if pieces else (token,))
        for index in range(len(words) - 1):
            if _candidate_word_matches(words[index], "git") and _candidate_word_matches(words[index + 1], "push"):
                candidates.append(PossibleCommandCandidate(
                    dialect, segment.source_span, ("git", "push"), reason
                ))
                break
    return tuple(candidates)


def _nesting_context(dialect: str, before: str, after: str) -> str:
    boundaries = before + after
    if "(" in boundaries or ")" in boundaries:
        return "subshell"
    if "|" in boundaries and "||" not in boundaries:
        return "pipeline"
    if "&" in boundaries and "&&" not in boundaries:
        if dialect == "powershell" and before == "&":
            return "call-operator"
        return "background"
    if before != "start" or after != "end":
        if all(character in "\r\n" for character in after) and before == "start":
            return "top-level"
        return "compound"
    return "top-level"


def _strict_literal_projection(
    command: str,
    dialect: str,
    status: str,
    candidates: tuple[PossibleCommandCandidate, ...],
    normalizations: tuple[LexicalOperation, ...],
    commands: tuple[ExecutableCommand, ...],
) -> StrictLiteralProjection:
    if status != "SCG-PARSED" or candidates:
        return StrictLiteralProjection("uncertain", ())
    if normalizations or len(commands) != 1:
        return StrictLiteralProjection("noncanonical", ())
    record = commands[0]
    argv = record.tokens
    if len(argv) != 4:
        return StrictLiteralProjection("noncanonical", ())
    if dialect == "posix" and shlex.join(argv) == command:
        return StrictLiteralProjection("canonical", argv)
    if dialect == "powershell" and (
        record.boundary_before == "&"
        and record.boundary_after == "end"
        and all(token.states == ("single-quoted",) for token in record.token_records)
        and _serialize_powershell_literal(argv) == command
    ):
        return StrictLiteralProjection("canonical", argv)
    return StrictLiteralProjection("noncanonical", ())


def _token_source_span(token: LexicalToken) -> tuple[int, int]:
    return (
        min(span[0] for span in token.source_spans),
        max(span[1] for span in token.source_spans),
    )


def _argument_records(record: ExecutableCommand) -> tuple[LexicalToken, ...]:
    executable_index = len(record.tokens) - len(record.arguments) - 1
    return record.token_records[executable_index + 1:]


def _records_can_publish(records: tuple[LexicalToken, ...]) -> bool:
    words: list[str] = []
    for token in records:
        pieces = token.value.split()
        words.extend(pieces if pieces else (token.value,))
    return any(
        _candidate_word_matches(words[index], "git")
        and _candidate_word_matches(words[index + 1], "push")
        for index in range(len(words) - 1)
    )


def _candidate_from_records(
    records: tuple[LexicalToken, ...], dialect: str, reason: str
) -> PossibleCommandCandidate | None:
    if not records or not _records_can_publish(records):
        return None
    start = min(_token_source_span(token)[0] for token in records)
    end = max(_token_source_span(token)[1] for token in records)
    return PossibleCommandCandidate(dialect, (start, end), ("git", "push"), reason)


class WrapperArgvMachine:
    """Generic state machine over one immutable wrapper registry row."""

    @staticmethod
    def _same_spelling(grammar: WrapperGrammar, left: str, right: str) -> bool:
        return left == right if grammar.case_sensitive else left.lower() == right.lower()

    @classmethod
    def _match_option(
        cls, grammar: WrapperGrammar, value: str
    ) -> tuple[WrapperOptionSpec | None, str | None, str | None]:
        for spec in grammar.option_specs:
            if cls._same_spelling(grammar, value, spec.spelling):
                form = "DETACHED" if spec.arity else "FLAG"
                return spec, form, None
            compare_value = value if grammar.case_sensitive else value.lower()
            compare_spelling = spec.spelling if grammar.case_sensitive else spec.spelling.lower()
            if compare_value.startswith(compare_spelling) and len(value) > len(spec.spelling):
                suffix = value[len(spec.spelling):]
                if suffix.startswith("=") and "EQUALS_ATTACHED" in spec.accepted_forms:
                    return spec, "EQUALS_ATTACHED", suffix[1:]
                if suffix and "SHORT_ATTACHED" in spec.accepted_forms:
                    return spec, "SHORT_ATTACHED", suffix
                return spec, "UNSUPPORTED_ATTACHED", suffix.lstrip("=:")
        return None, None, None

    @staticmethod
    def _participant(
        kind: str,
        token: LexicalToken,
        classification: str,
        reason: str,
        structural_value: str | None = None,
    ) -> TerminalParticipant:
        return TerminalParticipant(kind, token, structural_value, classification, reason)

    @classmethod
    def evaluate(
        cls, record: ExecutableCommand, identity: CommandIdentity
    ) -> WrapperProjection | None:
        executable_identity = WrapperGrammarRegistry.identity(
            record.executable, record.dialect
        )
        grammar = WrapperGrammarRegistry.resolve(executable_identity)
        if grammar is None:
            return None
        arguments = _argument_records(record)
        options: list[LexicalToken] = []
        assignments: list[LexicalToken] = []
        participants: list[TerminalParticipant] = []

        def projection(
            state: str,
            reason: str,
            *,
            operands: tuple[LexicalToken, ...] = (),
            child_input: CommandInput | None = None,
            payload_composition: str | None = None,
            contributing: tuple[LexicalToken, ...] = (),
            candidate: PossibleCommandCandidate | None = None,
        ) -> WrapperProjection:
            return WrapperProjection(
                grammar.wrapper_id,
                identity,
                tuple(options),
                tuple(assignments),
                operands,
                child_input,
                state,
                reason,
                payload_composition,
                contributing,
                candidate,
                tuple(participants),
            )

        def terminal_candidate(
            reason: str,
            retained: tuple[LexicalToken, ...] | None = None,
        ) -> WrapperProjection:
            records = retained if retained is not None else arguments
            candidate = _candidate_from_records(records, record.dialect, reason)
            return projection(
                "CANDIDATE", reason, operands=records, candidate=candidate
            )

        if grammar.operand_rule == "compose-all":
            if not arguments:
                return projection("EXACT_NO_CHILD", "WPG-NO-OPERAND")
            if arguments[0].value.startswith("-"):
                participants.append(cls._participant(
                    "OPTION_TOKEN", arguments[0], "UNRESOLVED",
                    "WPG-UNSUPPORTED-OPTION",
                ))
                return terminal_candidate("WPG-UNSUPPORTED-OPTION")
            participants.extend(
                cls._participant("OPERAND", token, "EXACT", "WPG-EXACT")
                for token in arguments
            )
            payload = " ".join(token.value for token in arguments)
            child_input = CommandInput(
                "COMPOSED_SHELL_TEXT", record.dialect, payload, (),
                grammar.payload_mode, arguments,
            )
            return projection(
                "EXACT_CHILD", "WPG-EXACT", operands=arguments,
                child_input=child_input, payload_composition=grammar.payload_mode,
                contributing=arguments,
            )

        index = 0
        mode = "execute"
        required_modes: list[str] = []
        selector_payload: LexicalToken | None = None
        option_terminated = False
        while index < len(arguments):
            token = arguments[index]
            value = token.value
            if (
                not option_terminated
                and grammar.option_terminator is not None
                and value == grammar.option_terminator
            ):
                options.append(token)
                participants.append(cls._participant(
                    "TERMINATOR", token, "EXACT", "WPG-EXACT"
                ))
                option_terminated = True
                index += 1
                break
            if not option_terminated and value.startswith("-"):
                spec, form, attached_value = cls._match_option(grammar, value)
                if spec is None:
                    participants.append(cls._participant(
                        "OPTION_TOKEN", token, "UNRESOLVED",
                        "WPG-UNSUPPORTED-OPTION",
                    ))
                    structural = value.split("=", 1)[1] if "=" in value else None
                    if structural is not None:
                        participants.append(cls._participant(
                            "ATTACHED_VALUE", token, "UNRESOLVED",
                            "WPG-ATTACHED-PAYLOAD-UNSUPPORTED", structural,
                        ))
                    return terminal_candidate("WPG-UNSUPPORTED-OPTION")
                if form == "UNSUPPORTED_ATTACHED":
                    participants.append(cls._participant(
                        "OPTION_TOKEN", token, "UNRESOLVED",
                        "WPG-ATTACHED-PAYLOAD-UNSUPPORTED",
                    ))
                    participants.append(cls._participant(
                        "ATTACHED_VALUE", token, "UNRESOLVED",
                        "WPG-ATTACHED-PAYLOAD-UNSUPPORTED", attached_value,
                    ))
                    return terminal_candidate("WPG-ATTACHED-PAYLOAD-UNSUPPORTED")
                if spec.mode is not None and mode != "execute":
                    participants.append(cls._participant(
                        "MODE", token, "UNRESOLVED", "WPG-CONFLICTING-MODE"
                    ))
                    return terminal_candidate("WPG-CONFLICTING-MODE")
                if index + spec.arity >= len(arguments):
                    participants.append(cls._participant(
                        "OPTION_TOKEN", token, "UNRESOLVED",
                        "WPG-OPTION-MISSING-VALUE",
                    ))
                    return terminal_candidate("WPG-OPTION-MISSING-VALUE")
                options.append(token)
                values = arguments[index + 1:index + 1 + spec.arity]
                options.extend(values)
                participants.append(cls._participant(
                    "OPTION_TOKEN", token, "EXACT", "WPG-EXACT"
                ))
                participants.extend(
                    cls._participant(
                        "DETACHED_VALUE", option_value, "EXACT", "WPG-EXACT",
                        option_value.value,
                    )
                    for option_value in values
                )
                if spec.mode is not None:
                    mode = spec.mode
                    selector_payload = values[0] if values else None
                if spec.requires_mode is not None:
                    required_modes.append(spec.requires_mode)
                index += 1 + spec.arity
                if spec.mode in ("command", "file"):
                    break
                continue
            break

        if required_modes and any(required != mode for required in required_modes):
            if options:
                participants.append(cls._participant(
                    "MODE", options[-1], "UNRESOLVED", "WPG-OPTION-WRONG-STATE"
                ))
            return terminal_candidate("WPG-OPTION-WRONG-STATE")

        if grammar.operand_rule == "selector":
            if mode == "command" and selector_payload is not None:
                remainder = arguments[index:]
                if remainder and not grammar.allow_payload_tail:
                    participants.extend(
                        cls._participant(
                            "SUFFIX", item, "UNRESOLVED",
                            "WPG-UNSUPPORTED-COMPOSITION",
                        )
                        for item in remainder
                    )
                    return terminal_candidate("WPG-UNSUPPORTED-COMPOSITION")
                participants.extend(
                    cls._participant("SUFFIX", item, "EXACT", "WPG-EXACT")
                    for item in remainder
                )
                child_dialect = (
                    record.dialect if grammar.child_dialect == "same"
                    else grammar.child_dialect
                )
                child_input = CommandInput(
                    "SHELL_TEXT", child_dialect, selector_payload.value, (),
                    grammar.payload_mode, (selector_payload,),
                )
                return projection(
                    "EXACT_CHILD", "WPG-EXACT",
                    operands=(selector_payload, *remainder),
                    child_input=child_input,
                    payload_composition=grammar.payload_mode,
                    contributing=(selector_payload,),
                )
            opaque = arguments[index:]
            participants.extend(
                cls._participant("OPERAND", item, "EXACT", "WPG-OPERAND-OPAQUE")
                for item in opaque
            )
            return projection(
                "EXACT_NO_CHILD", "WPG-OPERAND-OPAQUE", operands=opaque
            )

        if grammar.assignment_rule_id is not None:
            exact_pattern = ASSIGNMENT_NAME_RULES[grammar.assignment_rule_id]
            while index < len(arguments):
                value = arguments[index].value
                if "=" not in value:
                    break
                name, _assigned = value.split("=", 1)
                if value.count("=") != 1 or re.fullmatch(exact_pattern, name) is None:
                    participants.append(cls._participant(
                        "ASSIGNMENT_LIKE", arguments[index], "UNRESOLVED",
                        "WPG-ASSIGNMENT-MALFORMED", name,
                    ))
                    return terminal_candidate("WPG-ASSIGNMENT-MALFORMED")
                assignments.append(arguments[index])
                participants.append(cls._participant(
                    "ASSIGNMENT_LIKE", arguments[index], "EXACT", "WPG-EXACT", name
                ))
                index += 1

        if mode == "query":
            opaque = arguments[index:]
            participants.extend(
                cls._participant("OPERAND", item, "EXACT", "WPG-QUERY-MODE")
                for item in opaque
            )
            return projection("EXACT_NO_CHILD", "WPG-QUERY-MODE", operands=opaque)
        operands = arguments[index:]
        if not operands:
            return projection("EXACT_NO_CHILD", "WPG-NO-OPERAND")
        participants.extend(
            cls._participant("OPERAND", item, "EXACT", "WPG-EXACT")
            for item in operands
        )
        child_dialect = (
            record.dialect if grammar.child_dialect == "same" else grammar.child_dialect
        )
        child_input = CommandInput(
            "DIRECT_ARGV", child_dialect, None, operands, grammar.payload_mode,
            operands,
        )
        return projection(
            "EXACT_CHILD", "WPG-EXACT", operands=operands,
            child_input=child_input, payload_composition=grammar.payload_mode,
            contributing=operands,
        )


def _effective_record_id(identity: CommandIdentity, ordinal: int) -> str:
    chain: list[str] = []
    cursor: CommandIdentity | None = identity
    while cursor is not None:
        chain.append(f"{cursor.wrapper_id or 'root'}:{cursor.ordinal}")
        cursor = cursor.parent
    chain.reverse()
    return f"{identity.root_occurrence}|{'/'.join(chain)}|{ordinal}"


def _assemble_effective_publications(
    identity: CommandIdentity,
    status: str,
    candidates: tuple[PossibleCommandCandidate, ...],
    pushes: tuple[GitPushInvocation, ...],
    projections: tuple[WrapperProjection, ...],
    children: tuple[ShellParseResult, ...],
) -> EffectivePublicationProjection:
    records: list[EffectivePublicationRecord] = []
    for push in pushes:
        kind = "CANDIDATE" if push.candidate else "DIRECT"
        records.append(EffectivePublicationRecord(
            _effective_record_id(identity, len(records)), identity, kind, push,
            "possible" if push.candidate else "exact",
            not push.candidate and push.dry_run_state == "DRY-ENABLED",
            not push.candidate,
        ))
    for child in children:
        for child_record in child.effective_publications.records:
            relative_depth = child_record.identity.depth - identity.depth
            records.append(child_record._replace(
                kind="WRAPPER_CHILD" if relative_depth == 1 else "NESTED",
                dry_credit_eligible=False,
                generic_credit_eligible=False,
            ))
    exact_complete = (
        status == "SCG-PARSED"
        and not candidates
        and all(
            projection.terminal_state != "CANDIDATE"
            and all(
                participant.classification == "EXACT"
                for participant in projection.terminal_participants
            )
            for projection in projections
        )
        and all(child.effective_publications.exact_complete for child in children)
    )
    immutable = tuple(records)
    return EffectivePublicationProjection(
        immutable,
        exact_complete,
        tuple(record for record in immutable if record.dry_credit_eligible),
        tuple(record for record in immutable if record.generic_credit_eligible),
    )


def _assemble_command_records(
    segments: tuple[LexicalSegment, ...],
    dialect: str,
    normalizations: tuple[LexicalOperation, ...],
) -> tuple[ExecutableCommand, ...]:
    commands: list[ExecutableCommand] = []
    command_count = len(segments)
    normalization_state = "normalized" if normalizations else "literal"
    for ordinal, segment in enumerate(segments):
        tokens = list(segment.tokens)
        boundary_before = segment.boundary_before
        boundary_after = segment.boundary_after
        prefix_index = 0
        assignments: list[str] = []
        keywords: list[str] = []
        while prefix_index < len(tokens):
            token = tokens[prefix_index]
            if "=" in token and re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", token.split("=", 1)[0]
            ) is not None:
                assignments.append(token)
            elif token in _SHELL_KEYWORDS:
                keywords.append(token)
            else:
                break
            prefix_index += 1
        executable = tokens[prefix_index] if prefix_index < len(tokens) else ""
        arguments = tuple(tokens[prefix_index + 1:]) if executable else ()
        commands.append(ExecutableCommand(
            dialect,
            tuple(tokens),
            segment.token_records,
            tuple(assignments),
            tuple(keywords),
            executable,
            arguments,
            segment.source_span,
            ordinal,
            command_count,
            boundary_before,
            boundary_after,
            False,
            _nesting_context(dialect, boundary_before, boundary_after),
            boundary_before == "start" and boundary_after != "end"
            and all(character in "\r\n" for character in boundary_after),
            "exact",
            normalization_state,
        ))
    return tuple(commands)


def _parse_command_input(
    command_input: CommandInput,
    identity: CommandIdentity,
) -> ShellParseResult:
    dialect = command_input.dialect
    raw_command = command_input.shell_text or ""
    if command_input.kind == "DIRECT_ARGV":
        records = command_input.argv_records
        source_span = (
            min(_token_source_span(token)[0] for token in records),
            max(_token_source_span(token)[1] for token in records),
        )
        segments = (LexicalSegment(
            tuple(token.value for token in records), records, "start", "end", source_span
        ),)
        status = "SCG-PARSED"
        lexical = ShellLexicalRecord((), (), (), (), segments)
        data_regions: tuple[DataRegion, ...] = ()
        normalizations: tuple[LexicalOperation, ...] = ()
        initial_candidates: tuple[PossibleCommandCandidate, ...] = ()
    else:
        lexical_dialect = (
            dialect if dialect in ("posix", "powershell", "posix-compat")
            else "posix-compat"
        )
        state = _build_shell_lexical_state(raw_command, lexical_dialect)
        status = state.status if dialect == lexical_dialect else "SCG-UNSUPPORTED-DIALECT"
        segments = _tokenize_shell_lexical_state(state)
        initial_candidates = (
            _candidate_patterns_from_segments(segments, dialect, status)
            if status != "SCG-PARSED" else ()
        )
        lexical = ShellLexicalRecord(
            state.atoms, state.normalizations, state.removed_spans,
            state.data_regions, segments,
        )
        data_regions = state.data_regions
        normalizations = state.normalizations

    command_records = _assemble_command_records(segments, dialect, normalizations)
    strict_projection = (
        _strict_literal_projection(
            raw_command, dialect, status, initial_candidates,
            normalizations, command_records,
        )
        if command_input.kind != "DIRECT_ARGV"
        else StrictLiteralProjection("noncanonical", ())
    )
    if strict_projection.status == "canonical":
        command_records = (
            command_records[0]._replace(sole_canonical_literal=True),
        )

    projections: list[WrapperProjection] = []
    children: list[ShellParseResult] = []
    candidates = list(initial_candidates)
    for record in command_records:
        projection = WrapperArgvMachine.evaluate(record, identity)
        if projection is None:
            continue
        if projection.child_input is not None and identity.depth >= 4:
            candidate = _candidate_from_records(
                projection.contributing_tokens, dialect, "WPG-DEPTH-LIMIT"
            )
            unresolved = tuple(
                TerminalParticipant(
                    "SUFFIX", token, token.value, "UNRESOLVED",
                    "WPG-NESTED-UNRESOLVED",
                )
                for token in projection.contributing_tokens
            )
            projection = projection._replace(
                child_input=None,
                terminal_state="CANDIDATE",
                reason="WPG-NESTED-UNRESOLVED",
                candidate=candidate,
                terminal_participants=(
                    *projection.terminal_participants, *unresolved
                ),
            )
        projections.append(projection)
        if projection.candidate is not None:
            candidates.append(projection.candidate)
        if projection.child_input is not None:
            child_tokens = projection.contributing_tokens
            child_span = (
                min(_token_source_span(token)[0] for token in child_tokens),
                max(_token_source_span(token)[1] for token in child_tokens),
            )
            child_identity = CommandIdentity(
                projection.child_input.dialect,
                identity.depth + 1,
                identity,
                child_span,
                record.ordinal,
                projection.child_input.kind,
                projection.wrapper_id,
                projection.payload_composition,
                tuple(_token_source_span(token) for token in child_tokens),
                identity.root_occurrence,
            )
            children.append(_parse_command_input(projection.child_input, child_identity))

    immutable_candidates = tuple(candidates)
    immutable_children = tuple(children)
    pushes = _project_git_push_records(command_records, immutable_candidates)
    effective_publications = _assemble_effective_publications(
        identity, status, immutable_candidates, pushes, tuple(projections),
        immutable_children
    )
    scan_execution = _project_scan_execution_graph(
        status, immutable_candidates, command_records
    )
    return ShellParseResult(
        identity,
        dialect,
        status,
        lexical,
        segments,
        command_records,
        immutable_candidates,
        strict_projection,
        tuple(projections),
        immutable_children,
        pushes,
        effective_publications,
        scan_execution,
        data_regions,
        normalizations,
        raw_command,
    )


def _parse_shell_command_identity(
    command: str,
    dialect: str,
    identity: CommandIdentity,
) -> ShellParseResult:
    return _parse_command_input(
        CommandInput("SHELL_TEXT", dialect, command, (), None, ()), identity
    )


def parse_shell_command(command: str, dialect: str = "posix-compat") -> ShellParseResult:
    WrapperGrammarRegistry.validate()
    identity = CommandIdentity(
        dialect, 0, None, None, 0, "SHELL_TEXT", None, None, (), "live"
    )
    return _parse_shell_command_identity(command, dialect, identity)


def _global_option_is_repository_redirect(option: str) -> bool:
    return option in _REPOSITORY_GIT_OPTIONS or any(
        option.startswith(prefix)
        for prefix in ("-C", "--git-dir=", "--work-tree=", "--namespace=")
    )


def _parse_push_options(
    post_tokens: tuple[str, ...]
) -> tuple[
    tuple[OptionOccurrence, ...], tuple[str, ...], tuple[str, ...], str, str, str
]:
    occurrences: list[OptionOccurrence] = []
    option_tokens: list[str] = []
    operands: list[str] = []
    repository_context = "ambient"
    option_status = "GPO-PARSED"
    positive_dry = 0
    negative_dry = 0
    options_open = True
    index = 0

    def worsen(status: str) -> None:
        nonlocal option_status
        rank = {"GPO-PARSED": 0, "GPO-UNKNOWN": 1, "GPO-AMBIGUOUS": 2, "GPO-MISSING-VALUE": 3}
        if rank[status] > rank[option_status]:
            option_status = status

    while index < len(post_tokens):
        token = post_tokens[index]
        if not options_open:
            operands.append(token)
            index += 1
            continue
        if token == "--":
            occurrences.append(OptionOccurrence(token, "end-of-options", "neutral", None))
            option_tokens.append(token)
            options_open = False
            index += 1
            continue

        name, has_equals, glued_value = token.partition("=")
        if name in _PUSH_REQUIRED_VALUE_OPTIONS:
            option_tokens.append(token)
            value_index: int | None
            if has_equals:
                value_index = index
                if not glued_value:
                    worsen("GPO-MISSING-VALUE")
            elif index + 1 < len(post_tokens):
                value_index = index + 1
            else:
                value_index = None
                worsen("GPO-MISSING-VALUE")
            occurrences.append(OptionOccurrence(name, "required-value", "neutral", value_index))
            if name in ("--repo", "--no-repo"):
                repository_context = "redirected" if value_index is not None else "indeterminate"
            index += 1 if has_equals or value_index is None else 2
            continue
        if token.startswith("-o") and token != "-o":
            option_tokens.append(token)
            occurrences.append(OptionOccurrence("-o", "required-value", "neutral", index))
            index += 1
            continue
        if name in _PUSH_REQUIRED_ENUM_OPTIONS:
            option_tokens.append(token)
            value_index = index if has_equals else index + 1 if index + 1 < len(post_tokens) else None
            value = glued_value if has_equals else post_tokens[value_index] if value_index is not None else ""
            if value_index is None:
                worsen("GPO-MISSING-VALUE")
            elif value not in _PUSH_RECURSE_VALUES:
                worsen("GPO-AMBIGUOUS")
            occurrences.append(OptionOccurrence(name, "required-enum", "neutral", value_index))
            index += 1 if has_equals or value_index is None else 2
            continue
        if name in _PUSH_OPTIONAL_GLUED_OPTIONS:
            option_tokens.append(token)
            if has_equals and not glued_value:
                worsen("GPO-AMBIGUOUS")
            occurrences.append(OptionOccurrence(
                name, "optional-glued-value", "neutral", index if has_equals else None
            ))
            index += 1
            continue
        if token in _PUSH_BOOLEAN_OPTIONS:
            option_tokens.append(token)
            polarity = "positive"
            if token.startswith("--no-"):
                polarity = "negative"
            if token == "--dry-run":
                positive_dry += 1
            elif token == "--no-dry-run":
                negative_dry += 1
            occurrences.append(OptionOccurrence(token, "boolean", polarity, None))
            index += 1
            continue
        if token.startswith("-"):
            option_tokens.append(token)
            occurrences.append(OptionOccurrence(token, "unknown", "neutral", None))
            worsen("GPO-UNKNOWN")
            index += 1
            continue
        operands.append(token)
        index += 1

    if option_status != "GPO-PARSED" or (positive_dry and negative_dry):
        dry_run_state = "DRY-INDETERMINATE"
    elif positive_dry:
        dry_run_state = "DRY-ENABLED"
    else:
        dry_run_state = "DRY-NOT-CREDITABLE"
    return (
        tuple(occurrences), tuple(option_tokens), tuple(operands),
        repository_context, option_status, dry_run_state,
    )


def _project_git_push_records(
    commands: tuple[ExecutableCommand, ...],
    candidates: tuple[PossibleCommandCandidate, ...],
) -> tuple[GitPushInvocation, ...]:
    pushes: list[GitPushInvocation] = []
    for record in commands:
        if _normalized_command_word(record.executable) != "git":
            continue
        arguments = list(record.arguments)
        global_options: list[str] = []
        global_occurrences: list[OptionOccurrence] = []
        index = 0
        post_tokens: tuple[str, ...] | None = None
        while index < len(arguments):
            token = arguments[index]
            if token == "push":
                post_tokens = tuple(arguments[index + 1:])
                break
            if token in _GIT_VALUE_OPTS:
                if index + 1 >= len(arguments):
                    break
                global_options.extend((token, arguments[index + 1]))
                global_occurrences.append(OptionOccurrence(token, "required-value", "neutral", index + 1))
                index += 2
                continue
            if token.startswith(("-C", "-c")) and token not in ("-C", "-c"):
                global_options.append(token)
                global_occurrences.append(OptionOccurrence(token[:2], "required-value", "neutral", index))
                index += 1
                continue
            if token.startswith("--") and "=" in token:
                global_options.append(token)
                global_occurrences.append(OptionOccurrence(token.split("=", 1)[0], "required-value", "neutral", index))
                index += 1
                continue
            if token.startswith("-"):
                global_options.append(token)
                global_occurrences.append(OptionOccurrence(token, "unknown", "neutral", None))
                index += 1
                continue
            break
        if post_tokens is None:
            continue

        (
            push_occurrences, push_options, positionals, repository_context,
            option_status, dry_run_state,
        ) = _parse_push_options(post_tokens)

        env_names = {item.split("=", 1)[0] for item in record.environment_assignments}
        if env_names & _REPOSITORY_ENV_NAMES or any(
            _global_option_is_repository_redirect(option) for option in global_options
        ):
            repository_context = "redirected"
        pushes.append(GitPushInvocation(
            record,
            record.executable,
            record.environment_assignments,
            tuple(global_options),
            post_tokens,
            tuple(push_options),
            tuple(positionals),
            repository_context,
            dry_run_state == "DRY-ENABLED",
            False,
            len(commands) == 1 and not candidates,
            tuple(global_occurrences),
            push_occurrences,
            option_status,
            dry_run_state,
            record.nesting_context,
            False,
            record.normalization_state,
        ))
    for candidate in candidates:
        pushes.append(GitPushInvocation(
            candidate, "git", (), (), (), (), (), "indeterminate", False,
            False, False, (), (), "GPO-AMBIGUOUS", "DRY-INDETERMINATE",
            "uncertain", True, "uncertain",
        ))
    only_direct_push = len(pushes) == 1
    return tuple(push._replace(only_direct_push=only_direct_push) for push in pushes)


def find_git_push_records(parsed: ShellParseResult) -> list[GitPushInvocation]:
    """Return the one parser-owned effective publication projection."""
    return [record.push for record in parsed.effective_publications.records]


def classify_generic_push(parsed: ShellParseResult) -> GenericPushDecision:
    projection = parsed.effective_publications
    if not projection.exact_complete:
        return GenericPushDecision("PGG-PARSE-UNCERTAIN", None)
    if parsed.normalizations:
        return GenericPushDecision("PGG-LEXICAL-NORMALIZATION", None)
    if (
        len(parsed.commands) != 1
        or len(projection.records) != 1
        or len(projection.eligible_direct_generic) != 1
    ):
        return GenericPushDecision("PGG-COMPOUND-CONTEXT", None)
    push = projection.eligible_direct_generic[0].push
    if not isinstance(push.command, ExecutableCommand):
        return GenericPushDecision("PGG-PARSE-UNCERTAIN", None)
    if push.command.control_keywords or push.shell_context != "top-level" or (
        push.command.boundary_before != "start"
        or (
            push.command.boundary_after != "end"
            and not push.command.trailing_linebreak_only
        )
    ):
        return GenericPushDecision("PGG-COMPOUND-CONTEXT", None)
    if push.repository_context != "ambient":
        return GenericPushDecision("PGG-REPOSITORY-REDIRECT", None)
    if push.environment_assignments:
        return GenericPushDecision("PGG-ENV-PREFIX", None)
    if push.git_global_options:
        return GenericPushDecision("PGG-GIT-GLOBAL-OPTION", None)
    if push.option_status in ("GPO-MISSING-VALUE", "GPO-AMBIGUOUS"):
        return GenericPushDecision("PGG-OPTION-ARITY", None)
    if push.option_status == "GPO-UNKNOWN" or any(
        option not in _SAFE_PUSH_OPTIONS for option in push.push_options
    ):
        return GenericPushDecision("PGG-PUSH-OPTION", None)
    if not push.positionals:
        return GenericPushDecision("PGG-REMOTE-CARDINALITY", None)
    if len(push.positionals) != 2:
        return GenericPushDecision("PGG-REFSPEC-CARDINALITY", None)
    remote, refspec = push.positionals
    if ":" in refspec:
        source, destination = refspec.split(":", 1)
    else:
        source = destination = refspec
    if not destination:
        return GenericPushDecision("PGG-DESTINATION-SHAPE", None)
    return GenericPushDecision("PGG-ADMISSIBLE", (remote, destination, source))
# --- Publication-safety scan EXECUTION detection (2026-07-26 hardening) ---
# Basenames the scanner ships under, across both provider lines and both
# shell targets. Matched by BASENAME only (never by directory), case-
# insensitively (Windows paths are case-insensitive and real PowerShell/CMD
# invocations on this machine vary case), so any installed or repo-local
# copy at any of the pack's own script paths is recognized.
_SCAN_SCRIPT_BASENAMES = {
    "check-publication-safety.py", "check-publication-safety.sh",
    "check-publication-gate.py", "check-publication-gate.sh",
}

# Interpreters that can be told to run an arbitrary script file as their
# FIRST operand (`bash x.sh`, `sh x.sh`, `. x.sh` / `source x.sh`). A bare
# `./x.sh` (or any other path ending in one of the basenames above) with NO
# interpreter prefix is also recognized — see `_record_runs_scan_script`'s
# direct-exec branch.
_SHELL_INTERPRETERS = {"bash", "sh", "dash", ".", "source"}
_PYTHON_INTERPRETERS = {"python", "python3", "py"}

# PowerShell/pwsh flag whose OWN value is the script path to run.
_PS_FILE_FLAGS = {"-file"}
# PowerShell/pwsh flag whose OWN value is an arbitrary COMMAND STRING —
# re-tokenized and re-scanned through this SAME segment machinery
# (recursion, not a second parser), so `-Command "grep ... x.ps1"` cannot
# launder a MENTION as an execution the way the old plain-substring regex
# could.
_PS_COMMAND_FLAGS = {"-command", "-c"}


def _basename(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def _normalized_command_word(token: str) -> str:
    """Lowercased basename of `token` with a trailing `.exe` suffix stripped.

    Scan and push projections reuse this normalization for the same shell-word
    identity question instead of maintaining independently drifting copies.

    `_basename`'s backslash-to-forward-slash + rsplit handles a Windows
    absolute path (`C:\\Program Files\\Git\\bin\\git.exe`); `.lower()`
    handles Windows' case-insensitive command resolution (`GIT push`,
    `Git push`, `git.EXE push` all resolve and run identically to `git
    push` -- measured live, 2026-07-26: the pre-fix exact-match head test
    caught none of these); the `.exe` strip handles the Windows executable
    suffix both `git` and the PowerShell interpreters ship under, with or
    without a path prefix."""
    base = _basename(token).lower()
    if base.endswith(".exe"):
        base = base[:-4]
    return base


def _record_runs_scan_script(record: ExecutableCommand) -> bool:
    """Project scan execution from the parser-owned command record."""
    if not record.executable:
        return False
    head_base = _basename(record.executable).lower()
    arguments = list(record.arguments)

    # Direct exec: the command word itself IS the scanner
    # (`./check-publication-safety.sh`, a bare basename on PATH, or an
    # absolute/relative path to it).
    if head_base in _SCAN_SCRIPT_BASENAMES:
        return True

    # Interpreter + script-path-as-first-operand (`bash check-...sh`, ...).
    if head_base in _SHELL_INTERPRETERS or _normalized_command_word(record.executable) in _PYTHON_INTERPRETERS:
        return bool(arguments) and _basename(arguments[0]).lower() in _SCAN_SCRIPT_BASENAMES

    # PowerShell / pwsh, any casing, optional `.exe` suffix -- reuses
    # `_normalized_command_word` (see its docstring) rather than repeating
    # the basename/lower/`.exe`-strip sequence inline a second time; the push
    # projection shares this exact function instead of carrying its own copy.
    ps_name = _normalized_command_word(record.executable)
    if ps_name in ("powershell", "pwsh"):
        i = 0
        while i < len(arguments):
            flag = arguments[i].lower()
            if flag in _PS_FILE_FLAGS:
                return i + 1 < len(arguments) and _basename(arguments[i + 1]).lower() in _SCAN_SCRIPT_BASENAMES
            if flag in _PS_COMMAND_FLAGS:
                return False
            i += 1
        return False
    return False


def _project_scan_execution_graph(
    status: str,
    candidates: tuple[PossibleCommandCandidate, ...],
    commands: tuple[ExecutableCommand, ...],
) -> bool:
    if status != "SCG-PARSED" or candidates or len(commands) != 1:
        return False
    record = commands[0]
    powershell_call = (
        record.dialect == "powershell"
        and record.nesting_context == "call-operator"
        and record.boundary_before == "&"
    )
    if record.nesting_context != "top-level" and not powershell_call:
        return False
    if record.boundary_before != "start" and not powershell_call:
        return False
    if record.boundary_after != "end" and not record.trailing_linebreak_only:
        return False
    if _record_runs_scan_script(record):
        return True
    return False


def project_scan_execution(parsed: ShellParseResult) -> bool:
    """Return the parser-owned scan-execution projection."""
    return parsed.scan_execution


def _project_scan_range_binding(parsed: ShellParseResult) -> tuple[str, str] | None:
    if not project_scan_execution(parsed) or len(parsed.commands) != 1:
        return None
    record = parsed.commands[0]
    executable = _basename(record.executable).lower()
    arguments = list(record.arguments)
    scanner: str | None = None
    scanner_args: list[str] = []
    if executable == "check-publication-safety.py" or executable == "check-publication-safety.sh":
        scanner = executable
        scanner_args = arguments
    elif (executable in _SHELL_INTERPRETERS or _normalized_command_word(record.executable) in _PYTHON_INTERPRETERS) and arguments:
        candidate = _basename(arguments[0]).lower()
        if candidate in ("check-publication-safety.py", "check-publication-safety.sh"):
            scanner = candidate
            scanner_args = arguments[1:]
    elif _normalized_command_word(record.executable) in ("powershell", "pwsh"):
        for index, argument in enumerate(arguments):
            if argument.lower() in _PS_FILE_FLAGS and index + 1 < len(arguments):
                candidate = _basename(arguments[index + 1]).lower()
                if candidate in ("check-publication-safety.py", "check-publication-safety.sh"):
                    scanner = candidate
                    scanner_args = arguments[index + 2:]
                break
    if scanner is None or len(scanner_args) != 3 or scanner_args[0] != "--range":
        return None
    remote, destination = scanner_args[1:]
    if not remote or not destination:
        return None
    return remote, destination


def _derive_pr_grant(entries: list[dict]) -> tuple[str, ActivePrGrant | None]:
    state = "absent"
    grant: ActivePrGrant | None = None
    for entry in entries:
        if not is_user_message(entry):
            continue
        text = extract_user_typed_text(entry)
        if not text:
            continue
        if text == PR_REVOKE_MARKER:
            state, grant = "revoked", None
            continue
        match = PR_GRANT_REGEX.fullmatch(text)
        if match:
            owner = match.group("owner")
            repo = match.group("repo")
            if owner in (".", "..") or repo in (".", ".."):
                state, grant = "malformed", None
            else:
                state = "active"
                grant = ActivePrGrant(
                    match.group("url"), owner, repo, int(match.group("number"))
                )
            continue
        if text.startswith(PR_RESERVED_PREFIXES):
            state, grant = "malformed", None
    return state, grant


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_executable(name: str) -> str | None:
    candidate = shutil.which(name)
    if not candidate:
        return None
    try:
        resolved = Path(candidate).resolve(strict=True)
        workspace = Path.cwd().resolve(strict=True)
    except Exception:
        return None
    if not resolved.is_file() or _is_within(resolved, workspace):
        return None
    return str(resolved)


_PR_COMMAND_DIALECT_TEST_OVERRIDE: str | None = None


def _pr_command_dialect(tool_name: object) -> str:
    """Select one production shell contract; never infer it from command text."""
    if _PR_COMMAND_DIALECT_TEST_OVERRIDE in ("posix", "powershell"):
        return _PR_COMMAND_DIALECT_TEST_OVERRIDE
    try:
        source = Path(__file__).resolve(strict=True).as_posix().casefold()
    except Exception:
        raise PrRouteDenied("PRG-COMMAND-SHAPE") from None
    resolution = resolve_command_dialect(tool_name)
    if source.endswith((
        "/.claude/agents/scripts/check-git-push-gate.py",
        "/src.claude/agents/scripts/check-git-push-gate.py",
    )) and tool_name == "Bash" and resolution.exact:
        return resolution.dialect
    if source.endswith((
        "/.codex/skills/lead/scripts/check-git-push-gate.py",
        "/src.codex/skills/lead/scripts/check-git-push-gate.py",
    )):
        if os.name == "posix" and tool_name in ("Bash", "shell_command", "exec_command"):
            return resolution.dialect
        if os.name == "nt" and tool_name in ("PowerShell", "shell_command", "exec_command"):
            return resolution.dialect
    raise PrRouteDenied("PRG-COMMAND-SHAPE")


def resolve_command_dialect(tool_name: object) -> CommandDialectResolution:
    if tool_name == "PowerShell":
        return CommandDialectResolution("powershell", True)
    if tool_name == "Bash":
        return CommandDialectResolution("posix", True)
    if tool_name in ("shell_command", "exec_command"):
        return CommandDialectResolution(
            "powershell" if os.name == "nt" else "posix", True
        )
    return CommandDialectResolution("unsupported", False)


def _serialize_powershell_literal(argv: tuple[str, str, str, str]) -> str:
    return "& " + " ".join("'" + word.replace("'", "''") + "'" for word in argv)


def _portable_pr_head_ref(value: str) -> bool:
    return PR_HEAD_REF_REGEX.fullmatch(value) is not None


def _parse_pr_literal_command(
    parsed: ShellParseResult,
    resolved_git: str,
    dialect: str,
) -> LiteralPushCommand:
    if parsed.dialect != dialect or parsed.strict_projection.status != "canonical":
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    if dialect not in ("posix", "powershell"):
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    decoded = list(parsed.strict_projection.argv)
    executable, subcommand, remote, refspec = decoded
    if subcommand != "push" or executable != resolved_git or not Path(executable).is_absolute():
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    try:
        executable_path = Path(executable).resolve(strict=True)
        resolved_path = Path(resolved_git).resolve(strict=True)
        same_identity = executable_path.is_file() and resolved_path.is_file() and os.path.samefile(
            executable_path, resolved_path
        )
    except Exception:
        same_identity = False
    if not same_identity:
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
    return LiteralPushCommand(dialect, executable, remote, refspec, target)


def _run_process(argv: list[str], timeout: float) -> ProcessResult | None:
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
scanner_path="<closure>/check-publication-safety.py"
scanner={"__name__":"__main__","__file__":scanner_path,"__package__":None,"__cached__":None,"__injected_find_machine_paths__":finder}
sys.argv=[scanner_path,*sys.argv[1:]]
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
    pending: PendingScanInvocation, payload: bytes,
) -> tuple[LaunchedScanInvocation, tuple[TrustedExecutionRecord, ...]]:
    prefix = "PGG" if pending.binding.route == "generic" else "PRG"
    try:
        process = subprocess.Popen(
            list(pending.exact_argv), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False,
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


def _refresh_scan_binding(binding: PushScanBinding) -> PushScanBinding:
    if binding.route == "generic":
        return _resolve_generic_scan_binding(
            binding.remote, binding.destination, binding.source_oid
        )
    head_proc = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
    )
    rows = head_proc.stdout.splitlines()
    if head_proc.returncode or len(rows) != 1 or not OID_REGEX.fullmatch(rows[0]):
        raise PrRouteDenied("PRG-RECEIPT-MISMATCH")
    head = rows[0].lower()
    return PushScanBinding("strict", binding.remote, binding.destination, head, head)


def _run_authoritative_scan(binding: PushScanBinding) -> ConsumedAuthoritativeEvidence:
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
        "--range", binding.remote, binding.destination,
    )
    pending = PendingScanInvocation(
        invocation_id, attempt_id, binding, closure_before,
        interpreter_before, argv, object(),
    )
    try:
        launched, records = _run_snapshot_child(pending, _closure_payload(closure_before))
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
            binding_after = _refresh_scan_binding(binding)
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
    *,
    accepted_codes: tuple[int, ...] = (0,),
) -> tuple[int, str]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PrRouteDenied(failure_id)
    result = _run_process(argv, min(PROCESS_TIMEOUT_SECONDS, remaining))
    if result is None or result.returncode not in accepted_codes:
        raise PrRouteDenied(failure_id)
    try:
        return result.returncode, result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise PrRouteDenied(failure_id) from None


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


def _required_oid(value: object, failure_id: str) -> str:
    text = _required_text(value, failure_id, cap=40)
    if not OID_REGEX.fullmatch(text):
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


def _verify_pr_oracle(grant: ActivePrGrant, literal: LiteralPushCommand) -> tuple[PushTarget, str]:
    deadline = time.monotonic() + ORACLE_TIMEOUT_SECONDS
    git_exe = literal.executable
    gh_exe = _resolve_executable("gh")
    if gh_exe is None:
        raise PrRouteDenied("PRG-PR-UNAVAILABLE")
    target = literal.target

    fields = (
        "id,number,url,state,closed,mergedAt,baseRefName,baseRefOid,"
        "headRefName,headRefOid,headRepository,headRepositoryOwner"
    )
    _, pr_text = _run_text(
        [gh_exe, "pr", "view", grant.url, "--json", fields],
        deadline,
        "PRG-PR-UNAVAILABLE",
    )
    pr = _strict_json(pr_text, dict, "PRG-PR-UNAVAILABLE")
    if pr.get("number") != grant.number or pr.get("url") != grant.url:
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    pr_id = _required_text(pr.get("id"), "PRG-BINDING-DRIFT", cap=256)
    if not NODE_ID_REGEX.fullmatch(pr_id):
        raise PrRouteDenied("PRG-BINDING-DRIFT")
    if pr.get("state") != "OPEN" or pr.get("closed") is not False or pr.get("mergedAt") is not None:
        raise PrRouteDenied("PRG-PR-STATE")
    base_ref = _required_text(pr.get("baseRefName"), "PRG-BINDING-DRIFT", cap=255)
    _required_oid(pr.get("baseRefOid"), "PRG-BINDING-DRIFT")
    head_ref = _required_text(pr.get("headRefName"), "PRG-BINDING-DRIFT", cap=255)
    if not _portable_pr_head_ref(head_ref):
        raise PrRouteDenied("PRG-COMMAND-SHAPE")
    head_oid = _required_oid(pr.get("headRefOid"), "PRG-BINDING-DRIFT")
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
        [gh_exe, "repo", "view", f"{grant.owner}/{grant.repo}", "--json", repo_fields],
        deadline,
        "PRG-PR-UNAVAILABLE",
    )
    _, head_repo_text = _run_text(
        [gh_exe, "repo", "view", head_name, "--json", repo_fields],
        deadline,
        "PRG-PR-UNAVAILABLE",
    )
    base_record = _strict_json(base_repo_text, dict, "PRG-PR-UNAVAILABLE")
    head_record = _strict_json(head_repo_text, dict, "PRG-PR-UNAVAILABLE")
    _, base_default = _repo_record(base_record, f"{grant.owner}/{grant.repo}", "PRG-BINDING-DRIFT")
    current_head_repo_id, head_default = _repo_record(head_record, head_name, "PRG-BINDING-DRIFT")
    if current_head_repo_id != head_repo_id:
        raise PrRouteDenied("PRG-BINDING-DRIFT")

    _, ref_check = _run_text(
        [git_exe, "check-ref-format", "--branch", head_ref], deadline, "PRG-DESTINATION-UNSAFE"
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
    )
    branch = _strict_json(branch_text, dict, "PRG-PR-UNAVAILABLE")
    if branch.get("name") != head_ref or branch.get("protected") is not False:
        raise PrRouteDenied("PRG-DESTINATION-UNSAFE")
    _, rules_text = _run_text(
        [gh_exe, "api", "--hostname", "github.com", f"repos/{head_name}/rules/branches/{encoded_ref}"],
        deadline,
        "PRG-PR-UNAVAILABLE",
    )
    rules = _strict_json(rules_text, list, "PRG-PR-UNAVAILABLE")
    if rules:
        raise PrRouteDenied("PRG-DESTINATION-UNSAFE")

    _, expanded_urls = _run_text(
        [git_exe, "remote", "get-url", "--push", "--all", target.remote],
        deadline,
        "PRG-REMOTE-MISMATCH",
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
        accepted_codes=(0, 1),
    )
    if code == 1:
        _, raw_pushurl = _run_text(
            [git_exe, "config", "--get-all", f"remote.{target.remote}.url"],
            deadline,
            "PRG-REMOTE-MISMATCH",
        )
    raw_urls = raw_pushurl.splitlines()
    if len(raw_urls) != 1 or raw_urls[0] != urls[0]:
        raise PrRouteDenied("PRG-REMOTE-MISMATCH")

    _, remote_head_text = _run_text(
        [git_exe, "ls-remote", "--heads", target.remote, target.destination],
        deadline,
        "PRG-BRANCH-DRIFT",
    )
    remote_rows = remote_head_text.splitlines()
    if len(remote_rows) != 1:
        raise PrRouteDenied("PRG-BRANCH-DRIFT")
    remote_parts = remote_rows[0].split("\t")
    if len(remote_parts) != 2 or remote_parts[1] != target.destination or not OID_REGEX.fullmatch(remote_parts[0]):
        raise PrRouteDenied("PRG-BRANCH-DRIFT")
    if remote_parts[0].lower() != head_oid:
        raise PrRouteDenied("PRG-BRANCH-DRIFT")

    _, local_head_text = _run_text(
        [git_exe, "rev-parse", "--verify", "HEAD"], deadline, "PRG-RECEIPT-MISMATCH"
    )
    local_head_rows = local_head_text.splitlines()
    if len(local_head_rows) != 1 or not OID_REGEX.fullmatch(local_head_rows[0]):
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
            identity = CommandIdentity(
                resolution.dialect, 0, None, None, occurrence_index,
                "SHELL_TEXT", None, None, (), root_occurrence,
            )
            parsed_commands.append(ParsedTranscriptCommand(
                entry_index,
                occurrence_index,
                occurrence.call_id,
                occurrence.tool_name,
                resolution.dialect,
                resolution.exact,
                _parse_shell_command_identity(
                    occurrence.command_text, resolution.dialect, identity
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
        if project_scan_execution(parsed_command.parsed):
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
        if observation.kind == "valid-v2":
            receipt = observation.receipt
            range_binding = _project_scan_range_binding(parsed_command.parsed)
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
    remote: str, destination: str, source: str
) -> PushScanBinding:
    if not source:
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    source_proc = subprocess.run(
        ["git", "rev-parse", "--verify", source],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
    )
    source_rows = source_proc.stdout.splitlines()
    if source_proc.returncode or len(source_rows) != 1 or not OID_REGEX.fullmatch(source_rows[0]):
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    source_oid = source_rows[0].lower()
    type_proc = subprocess.run(
        ["git", "cat-file", "-t", source_oid],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
    )
    if type_proc.returncode or type_proc.stdout.strip() != "commit":
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    head_proc = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
    )
    head_rows = head_proc.stdout.splitlines()
    if head_proc.returncode or len(head_rows) != 1 or not OID_REGEX.fullmatch(head_rows[0]):
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    return PushScanBinding(
        "generic", remote, destination, source_oid, head_rows[0].lower()
    )


def _evaluate_active_pr_route(
    grant: ActivePrGrant,
    command: str,
    tool_name: object,
    parsed: ShellParseResult,
) -> bool:
    try:
        effective = parsed.effective_publications
        if (
            parsed.strict_projection.status != "canonical"
            or len(effective.records) != 1
            or effective.records[0].kind != "DIRECT"
        ):
            raise PrRouteDenied("PRG-COMMAND-SHAPE")
        dialect = _pr_command_dialect(tool_name)
        git_exe = _resolve_executable("git")
        if git_exe is None:
            raise PrRouteDenied("PRG-REMOTE-MISMATCH")
        literal = _parse_pr_literal_command(parsed, git_exe, dialect)
        target, local_head = _verify_pr_oracle(grant, literal)
        binding = PushScanBinding(
            "strict", target.remote, target.destination, local_head, local_head
        )
        _run_authoritative_scan(binding)
        return True
    except PrRouteDenied:
        raise
    except Exception:
        raise PrRouteDenied("PRG-INTERNAL") from None


def _has_solitary_direct_dry_credit(parsed: ShellParseResult) -> bool:
    """Return true only for one exact root-level positive long-form dry push."""
    effective = parsed.effective_publications
    if (
        not effective.exact_complete
        or parsed.normalizations
        or len(effective.records) != 1
        or len(effective.eligible_direct_dry) != 1
    ):
        return False
    record = effective.records[0]
    eligible = effective.eligible_direct_dry[0]
    push = record.push
    return (
        (record is eligible or record.record_id == eligible.record_id)
        and record.kind == "DIRECT"
        and record.certainty == "exact"
        and push.only_direct_push
        and push.only_executable_command
        and push.dry_run_state == "DRY-ENABLED"
        and any(
            occurrence.spelling == "--dry-run"
            and occurrence.polarity == "positive"
            for occurrence in push.push_option_occurrences
        )
    )


def evaluate_push(envelope: dict) -> bool:
    """The decision algorithm after envelope parsing (see the module docstring): return
    True to ALLOW the push (`main()` then exits 0 with no payload), False to
    fall through to the deny payload. MAY RAISE — `main()` wraps the call to
    this function in one try/except and treats a raised exception exactly
    like a False return (fall through to deny), never like True.

    Split out of `main()` (2026-07-26 HIGH-severity hardening — `work-items/
    bugs/2026-07-26-push-gate-new-paths-fail-open-because-the-wrapper-
    discards-the-exit-code.md`; see the module docstring's "A CRASH WHILE
    DECIDING" note for the full defect this closes). Before this split, an
    uncaught exception ANYWHERE in this logic propagated out of `main()` and
    produced no deny payload, so the host could not distinguish a crash from a
    legitimate allow.
    Fail-open is the deliberate posture for a non-command, non-push,
    subagent context, or dry run. A detected non-dry push with no readable
    transcript now fails closed; it is not
    defensible for a hook that CRASHED WHILE DECIDING, because those two are
    indistinguishable to everything downstream.

    The bug report's own count of "five" fail-open paths refers to the five
    NUMBERED steps 2-6 in the module docstring's decision algorithm (step 3
    there bundles two code-level checks — non-dict `tool_input` and a
    missing/non-string `command` — under one label, "tool_input.command is
    absent or empty"). The ordinary `return True` paths below remain subagent
    context, non-dict `tool_input`, no/empty command, no detected push,
    all-dry-run, and a suspicious wrapper/prefix with no active PR grant.
    Each is an ordinary return reached without any
    exception being raised, so `main()`'s try/except never intercepts them —
    only a genuinely raised exception is redirected to deny."""
    # Subagent context: mirrors check-bugfix-discipline.py. The subagent's
    # envelope points at the MAIN session transcript, and the subagent cannot
    # put the user-side [approve-publication] marker there — gating it here is
    # an un-overridable false block. Governance still forbids delegating a
    # push to a subagent to dodge review; this hook stays a backstop.
    if envelope.get("agent_id"):
        return True

    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return True

    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return True

    live_resolution = resolve_command_dialect(envelope.get("tool_name"))
    parsed = parse_shell_command(command, live_resolution.dialect)
    push_records = find_git_push_records(parsed)
    if not push_records and parsed.effective_publications.exact_complete:
        return True  # no `git push` in command position
    if not push_records:
        raise PrRouteDenied("PGG-PARSE-UNCERTAIN")

    if _has_solitary_direct_dry_credit(parsed):
        return True  # one exact dry push sends no update

    transcript_path = envelope.get("transcript_path") or ""
    if not transcript_path:
        raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE")

    last_user_entry, _after_user_entries, current_turn_status = scan_current_turn_boundary(
        transcript_path, byte_cap=CURRENT_TURN_BYTE_CAP
    )
    user_text = (
        extract_user_typed_text(last_user_entry)
        if current_turn_status == STATUS_FOUND and last_user_entry is not None
        else ""
    )
    # (a) Per-turn user-side override — the marker counts ONLY from the last
    # genuine user message, never from assistant prose / tool calls / output.
    # ALSO bounded by MARKER_MAX_MESSAGE_LENGTH (see that constant's comment
    # for the full contract decision, measurements, and disclosed residual):
    # a marker riding inside a long message — the shape of a copied deny
    # block, not a one-line approval — does not open the gate here; it falls
    # through to branch (b) and then to deny, same as no marker at all.
    if APPROVE_MARKER_REGEX.search(user_text) and len(user_text) <= MARKER_MAX_MESSAGE_LENGTH:
        return True

    history_entries, history_status = read_transcript_history(
        transcript_path,
        byte_cap=TRANSCRIPT_HISTORY_BYTE_CAP,
        record_cap=TRANSCRIPT_HISTORY_RECORD_CAP,
        line_byte_cap=TRANSCRIPT_HISTORY_LINE_BYTE_CAP,
    )
    if history_status != "found":
        raise PrRouteDenied("PRG-TRANSCRIPT-UNAVAILABLE")
    pr_state, pr_grant = _derive_pr_grant(history_entries)
    if pr_state == "malformed":
        raise PrRouteDenied("PRG-AUTH-MALFORMED")
    if pr_state == "active" and pr_grant is not None:
        return _evaluate_active_pr_route(
            pr_grant,
            command,
            envelope.get("tool_name"),
            parsed,
        )

    grammar = classify_generic_push(parsed)

    # (b) One fresh gate-owned canonical range scan. Transcript observations
    # above remain diagnostic untrusted input and never enter this branch.
    if PUSH_INSTRUCTION_REGEX.search(user_text):
        if grammar.status != "PGG-ADMISSIBLE" or grammar.binding is None:
            raise PrRouteDenied(grammar.status)
        remote, destination, source = grammar.binding
        binding = _resolve_generic_scan_binding(remote, destination, source)
        _run_authoritative_scan(binding)
        return True

    return False  # no allow condition satisfied -> caller falls through to deny


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


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    failure_id: str | None = None
    try:
        if evaluate_push(envelope):
            return 0
    except PrRouteDenied as exc:
        failure_id = exc.failure_id
    except Exception:
        # A crash WHILE DECIDING is a decision not made, not a decision to
        # allow — fall through to the deny payload below rather than
        # returning 0 silently (2026-07-26 hardening; see evaluate_push's
        # own docstring and the module docstring's "A CRASH WHILE DECIDING"
        # note for the full defect this closes).
        pass

    # Deny. PR-route failures intentionally expose only a stable identifier
    # and safe remediation; subprocess output, command text, paths, remotes,
    # and exception details never enter this payload.
    pr_reasons = {
        **SCAN_DENIAL_REASONS,
        "PRG-AUTH-MALFORMED": "Use the exact version-1 PR approval or revocation line in a genuine user message.",
        "PRG-TRANSCRIPT-UNAVAILABLE": "Retry from a readable current session transcript; summaries cannot authorize publication.",
        "PRG-COMMAND-SHAPE": "Use exactly one ordinary `git push <remote> HEAD:refs/heads/<current-head-ref>` command.",
        "PRG-PR-UNAVAILABLE": "Restore authenticated GitHub state access, then retry so the pull request can be checked afresh.",
        "PRG-PR-STATE": "The pull request is not open; obtain a new grant only for an open pull request.",
        "PRG-BINDING-DRIFT": "Refresh the pull-request binding and retry with a current exact grant if needed.",
        "PRG-DESTINATION-UNSAFE": "Choose the current unprotected non-default pull-request head branch.",
        "PRG-REMOTE-MISMATCH": "Use one direct GitHub remote for the current pull-request head repository.",
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
        "PGG-RANGE-RECEIPT-VERSION": "Retry the push so the gate emits one message-complete version-2 receipt.",
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
        "fresh non-empty version-2 range scan from the canonical sibling "
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


if __name__ == "__main__":
    sys.exit(main())
