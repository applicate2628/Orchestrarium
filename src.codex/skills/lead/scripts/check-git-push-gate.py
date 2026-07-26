#!/usr/bin/env python3
"""Git-push publication gate (PreToolUse, BLOCKING) — structural backstop for
the human-review-before-push rule.

WHAT THIS DENIES: a Bash command that confidently runs `git push` in command
position, when the current turn shows neither (a) the per-turn user-side
override marker `[approve-publication]` in the LAST GENUINE USER MESSAGE, nor
(b) evidence that a publication-safety scan (`check-publication-safety` /
`check-publication-gate` / `agents-check-safety`) was invoked among the
model's own tool calls AND that SAME invocation's OWN tool OUTPUT this same
turn — correlated by call identity, never by mere co-occurrence — reported a
clean result over a NON-EMPTY tracked staged set — combined with an explicit
push instruction in the last genuine user message.

WHY: `git push` is the highest-stakes irreversible action the pack governs —
"Human review before git push ... must include a leak-check of staged changes"
was prose-only while lower-stakes edit/stop moments got blocking hooks. This
hook closes that asymmetry.

WHY BRANCH (b) KEYS ON RESULT, NOT JUST INVOCATION (2026-07-26 hardening,
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
extract_model_shell_commands_with_ids`, which returns the RAW shell command
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
extract_model_shell_commands_with_ids and extract_tool_outputs_with_ids), so
this ordering check never rejects a genuine pair, only a same-id result that
could not possibly be answering the call it is being credited against.

CALL-SIDE UNIQUENESS COVERS EVERY ID-CARRYING CALL, NOT ONLY SHELL CALLS
(2026-07-26, third correlation finding on this same mechanism, external
adversarial-gate review — `work-items/bugs/2026-07-26-non-shell-call-can-
claim-a-scan-id-and-open-the-push-gate.md`). The COLLISION REJECTION fix
above computed call-side uniqueness (`call_positions`) by walking
`extract_model_shell_commands_with_ids` alone, because that was already the
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
stays on `extract_model_shell_commands_with_ids`, unchanged, because only a
shell call can ever execute the scanner. A non-shell call can now never hide
a second claimant on a scan id.

HONESTY RULE — THIS IS A BACKSTOP, NOT A GUARANTEE. It under-detects by design
(a push wrapped in a script the hook only sees as `bash sync.sh`, `eval`,
command substitution, or another command-wrapper is not modelled — the hook
cannot see INSIDE a wrapper script's own contents, only the outer command
line that invokes it). A PLAIN MULTI-LINE command is NOT one of these gaps
and IS correctly modelled: `cd /repo` NEWLINE `git add -A` NEWLINE `git
commit -m x` NEWLINE `git push origin main`, all as one Bash tool call, is
seen as four separate commands and the `git push` on the last line is found
(a newline-treated-as-plain-whitespace defect that made this NOT true — the
canonical publish flow bypassed the gate entirely — was found
and fixed in the same 2026-07-26 hardening that added the solo-segment rule
below; see `iter_command_segments`'s NEWLINE-AS-SEPARATOR note and
`work-items/bugs/2026-07-26-push-gate-never-fires-on-a-multi-line-push-
command.md`). What remains genuinely unmodelled is a command word that
ITSELF hides `git push` from view — `bash sync.sh` where `sync.sh`'s own
file contents run `git push`, `eval "$cmd"`, command substitution
(`$(...)`), or piping through `xargs` — because the hook only ever sees the
literal text of the ONE command it was invoked with, never the contents of
a script file that command happens to run. The transcript may be
unavailable (then the hook fails open — see step 6's exact scope below),
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

Decision algorithm (fail-open everywhere on internal error):

  1. Read the PreToolUse JSON envelope from stdin.
  2. If the envelope carries `agent_id` (a subagent context) → exit 0 (allow;
     mirrors check-bugfix-discipline.py — a subagent cannot inject the
     user-side override into the main transcript, so gating it here is an
     un-overridable false positive. Governance still forbids delegating a
     push to a subagent to dodge review).
  3. If `tool_input.command` is absent or empty → exit 0 (not a shell command).
  4. Parse the command with the shared shell-aware command-position parser
     (shlex tokens, separators, env-assignment prefixes, git global options —
     the check-no-trash-in-repo.py technique). No `git push` in command
     position → exit 0. `git push` inside a quoted string is NOT a command.
  5. Every detected push carrying `--dry-run` → exit 0 (nothing is sent).
  6. If `transcript_path` is MISSING (absent/empty) → exit 0 (cannot determine;
     fail open). This is NARROWER than it sounds: a `transcript_path` that IS
     present but names an unreadable, non-existent, or unparseable file does
     NOT reach this exit — `read_transcript_tail` returns an empty entry list
     for it, which yields no genuine user message, which fails BOTH (a) and
     (b) below on their own merits, falling through to step 9 (DENY). Only a
     genuinely MISSING field fails open; an unreadable-but-present one denies.
  7. If the LAST GENUINE USER MESSAGE contains `[approve-publication]` →
     exit 0. The marker is honored ONLY from the user's own text — never from
     assistant prose, tool calls, or tool output — because prior provider or
     file content quoting the marker must not approve a publication.
  8. If the current turn (entries after the last genuine user message) shows
     a publication-safety scan invocation among the model's own tool CALLS,
     under an id UNIQUE among this turn's calls (see COLLISION REJECTION note
     below), WHOSE OWN correlated tool OUTPUT (same call id — see the
     CORRELATION note above), itself under an id unique among this turn's
     outputs and recorded STRICTLY AFTER the call it answers, reports a
     clean, non-empty, `tracked`-mode result, AND the last genuine user
     message contains an explicit push-instruction signal (`push`, `запушь`,
     `залей`, ...) → exit 0.
  9. Otherwise → emit a structured `permissionDecision: "deny"` payload with
     exact compliance instructions. Always exit 0 (the decision is carried by
     the stdout payload, not the exit code).

WHAT THIS STILL DOES NOT COVER (disclosed, not silently assumed away):
  - NO WORKTREE / REPOSITORY / DESTINATION BINDING (2026-07-26, adversarial-
    gate finding, high). The clean-result line carries no repository,
    worktree, or commit identity — it is a plain string. This repository
    alone runs SIX live worktrees of itself and forward-commits through them.
    A scan invoked (and correlated) in one worktree's turn and a `git push`
    issued in a DIFFERENT worktree within the same turn are NOT distinguished
    by anything in this mechanism — the gate cannot currently tell "the scan
    that ran was scanning the tree this push is publishing" from "a scan ran
    somewhere, on something, this turn." Binding requires comparing the
    scan's and the push's own effective working directory (cwd / `-C`
    argument), which this hook does not currently capture or compare. Treat
    this exactly as the multi-commit gap below: real, not hypothetical,
    explicitly not closed by this change.
  - Multi-commit pushes, force pushes, rebases, amends, and mirror/tag pushes
    all fall to the operator marker exactly as before — nothing here binds the
    scanned content to a specific commit object or destination ref.
  - A model can still forge the evidence: DELIBERATELY type a literal fake
    clean-result line into a real command (`echo "publication-safety: clean
    (tracked, examined 999 files)"`), keyed to a real call id. This remains
    open and is the genuine adversarial-actor-with-a-shell case. It is
    DISTINCT from the two accident-class vectors this same 2026-07-26
    hardening closed (execution-vs-mention detection, `find_scan_script_
    executions`, plus the compound-command solo-segment rule,
    `_command_is_solely_scan_execution`) — both of those involved a REAL
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
  - TRANSCRIPT_TAIL_LINES REACHABILITY (2026-07-26, adversarial-gate
    finding, pre-existing but now load-bearing since branch (b) is a real
    correlation check rather than a haystack join). Only the last
    TRANSCRIPT_TAIL_LINES entries of the transcript are read; a scan-and-
    result pair further back than that is invisible, so branch (b) is
    UNREACHABLE for that turn no matter how correctly the scan ran. Measured
    on this machine's own real transcripts, under the turn-boundary
    definition that mirrors this hook's own `last_genuine_user_message` (see
    TRANSCRIPT_TAIL_LINES' comment for the exact method and sample): ~38% of
    real turns exceed the window. This fails CLOSED (an unreachable
    branch (b) denies, it does not allow), which is the safe direction, but
    it is silent about WHY — an operator sees a bare deny and does not know
    whether their scan evidence was rejected or never seen at all. The deny
    message below now names this possibility explicitly rather than leaving
    it silent. Widening the window is a deliberate future decision (it costs
    read time on every push) and is intentionally NOT made here.
"""
from __future__ import annotations

import json
import re
import shlex
import sys

from hook_common import (
    extract_model_shell_commands_with_ids,
    extract_model_tool_calls_with_ids,
    extract_tool_outputs_with_ids,
    last_genuine_user_message,
    parse_envelope,
    read_stdin_utf8,
    read_transcript_tail,
)

# Per-turn override marker — honored ONLY from the last genuine user message.
# User-side only by design: assistant prose can be steered by injected content
# (see the consultant continuation-prompt untrusted-data rule), so unlike
# [skip-bugfix-discipline] this marker never counts from the model's own reply.
APPROVE_MARKER_REGEX = re.compile(r"\[approve-publication\]", re.IGNORECASE)

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
# regex over call text — see find_scan_script_executions below (2026-07-26
# mention-vs-execution hardening, adversarial-gate finding). A prior
# `SCAN_INVOCATION_REGEX` here matched the scanner's NAME anywhere in a
# call's flattened text, which is satisfied just as readily by a command
# that merely NAMES the scanner (`grep ... check-publication-safety.sh`,
# `Test-Path .../check-publication-safety.ps1`, `ls .../agents-check-
# safety.md`) as by one that runs it — reproduced live against real
# historical transcripts on this machine (a `Test-Path` existence check and
# an `ls` of the command file both "matched" without ever running the
# scanner). `/agents-check-safety` is not matched as a distinct shape at
# all: it is not text-matched here because no real transcript on this
# machine ever shows it as its own tool-call shape (searched exhaustively);
# its own documented steps (`src.claude/commands/agents-check-safety.md`
# step 1) always cause the model to issue a real `bash .../check-
# publication-safety.sh` call, which find_scan_script_executions recognizes
# like any other real execution — so dropping the text-mention branch loses
# no real detection, only the false-positive surface it created.

# Publication-safety scan RESULT — matched narrowly against the CORRELATED
# tool OUTPUT of a call that itself matched find_scan_script_executions
# (never prose, never an uncorrelated tool result — see extract_tool_outputs_with_ids
# and the module docstring's CORRELATION note), so a file or tool result
# merely mentioning the scanner cannot satisfy it either, whether or not it
# shares a turn with an unrelated scan invocation. This is the scanner's OWN
# self-reported clean-pass line (check-publication-safety.sh / .ps1, all
# copies): "publication-safety: clean (tracked, examined N files)". Two
# conditions are both load-bearing and
# neither is optional:
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
SCAN_CLEAN_TRACKED_REGEX = re.compile(
    r"publication-safety:\s*clean\s*\(\s*tracked\s*,\s*examined\s+([1-9]\d*)\s+files?\s*\)",
    re.IGNORECASE,
)

# How many transcript JSONL lines to read (same tail budget as the sibling
# bugfix-discipline hook). DISCLOSED REACHABILITY GAP (2026-07-26, adversarial-
# gate finding, pre-existing, amplified by this hardening making branch (b)
# real correlation work at all): a scan-and-result pair more than this many
# entries before the push is invisible to `read_transcript_tail`, so branch
# (b) becomes UNREACHABLE for that turn regardless of how correctly the scan
# ran, silently pushing the operator toward the `[approve-publication]`
# marker (the branch that needs no scan at all). Measured directly against
# this machine's own real session transcripts (477 main-session `.jsonl`
# files under `~/.claude/projects`, subagent sidechains excluded since a
# subagent context already exits at step 2 above; 2026-07-26). An initial
# pass used a partially-permissive turn-boundary definition and read ~14% of
# turns exceeding 100; re-measured under the boundary that actually MIRRORS
# this hook's own `last_genuine_user_message` (non-empty typed text, skipping
# meta/compact-summary entries — the same rule this hook itself uses to find
# where a turn starts): median turn length 66 entries, p90 385, ~38% of turns
# exceed 100. That figure is the one that describes this hook's real
# exposure, because it is measured the same way the hook itself measures a
# turn; the ~14% figure came from a looser boundary than what the hook
# actually applies and understates the gap — both figures are recorded here
# rather than silently discarding the superseded one. This fails closed here
# (the current, safe behavior), which is not the same as this branch being
# reliably reachable. Widening the window trades read-time cost on EVERY
# push (not measured here) against that reachability gap; this hardening
# deliberately does NOT pick a new number unilaterally — see the deny
# message's reachability note, WHAT THIS STILL DOES NOT COVER below, and
# work-items/bugs/2026-07-26-transcript-tail-lines-reachability-gap-needs-a-decision.md.
TRANSCRIPT_TAIL_LINES = 100

# `git` global options that consume a SEPARATE following token as their value;
# skipped together with their value when scanning for the subcommand (so
# `git -C /x push` is still seen as a push).
_GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}

# Shell keywords that PRECEDE a command without consuming the command slot
# (`if ...; then git push; fi`, `for b in x; do git push; done`).
_SHELL_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!"}


def iter_command_segments(command: str) -> list[list[str]] | None:
    """Tokenize `command` and split it into one raw token list per shell
    command in the pipeline — the SHARED first half of the shell-aware
    technique this hook uses for BOTH `git push` detection
    (find_git_push_invocations) and publication-safety-scan EXECUTION
    detection (find_scan_script_executions, 2026-07-26 mention-vs-execution
    hardening). One tokenizer, two consumers, on purpose: an earlier
    incarnation of this fix used this exact tokenizer for `git push` but a
    bare substring regex for the scanner side, which is exactly how the
    scanner side was fooled by a `grep` command that merely NAMED the
    scanner as a target path instead of running it (reproduced live,
    2026-07-26 adversarial-gate finding) — two parsers for one shell-command
    concept is how the halves drift apart, so there is only one here.

    Quotes are honored (`git push` or a scanner path inside a quoted string
    is data, not a command); command separators (`;`, `&&`, `||`, `|`, `&`,
    `(`, `)`, and an UNQUOTED NEWLINE) start a new segment; redirection
    targets (`>`, `>>`, `<`, `2>&1`, ...) are consumed and never appear in
    any segment (pure stream redirection is not a second command). Returns
    None on a tokenizer error (unbalanced quotes) — fail open, same as the
    original inline try/except. Each returned segment still has its own
    leading env-assignment prefix / shell keywords in place; callers that
    need the EFFECTIVE command word use `strip_command_prefix`.

    NEWLINE-AS-SEPARATOR (2026-07-26, adversarial-gate finding, root cause
    of TWO defects in the two consumers of this one function — fixed here
    once rather than in each consumer separately, which is the entire point
    of sharing one segmenter). `shlex(..., whitespace_split=True)` treats
    `\\n` as ordinary WHITESPACE by default (it is part of `self.whitespace`
    out of the box), never as a token of its own — so a multi-line Bash
    command (routine in this harness: the model routinely batches several
    commands into one tool call separated by real newlines, not `;`) was
    tokenized as if every line had been joined with a single space, with NO
    way to tell where one line ended and the next began. Two independent
    consumers broke on this, both reproduced live against these exact bytes
    before this fix:
      - `_command_is_solely_scan_execution`'s solo-segment rule (the
        compound-command hardening two revisions ago) never saw more than
        one segment for `bash check-publication-safety.sh` NEWLINE `grep -rn
        'examined' tests/`, so it credited the whole thing as a solitary
        scan execution — the exact compound-command defect that hardening
        exists to block, resurrected through a newline instead of `;`.
      - `find_git_push_invocations` never saw `git push` in command
        position for `cd /repo` NEWLINE `git add -A` NEWLINE `git commit -m
        x` NEWLINE `git push origin main` — the canonical multi-line
        publish sequence — because the whole four-line command collapsed
        into ONE segment whose first token is `cd`, so the segment is
        rejected outright and the `git push` tokens buried later in the
        same (wrongly-unified) segment are never reached. This is a
        PRE-EXISTING gap (confirmed present before this hardening even
        started), not a regression from the compound-command fix, but it
        shares the identical root cause and is fixed by the same change:
        `work-items/bugs/2026-07-26-push-gate-never-fires-on-a-multi-line-
        push-command.md`.
    Fixed by explicitly re-including `\\n` as a punctuation/separator
    character AND removing it from shlex's own whitespace set post-
    construction (adding it to `punctuation_chars` alone is not sufficient —
    shlex checks whitespace before punctuation, so a character present in
    BOTH is still swallowed as whitespace and never reaches the punctuation
    path; verified empirically against this exact shlex version before
    relying on it, not assumed from the docs). A newline INSIDE a quoted
    string (`echo "line1\\nline2"`) is untouched and stays literal data, not
    a separator — quote-tracking runs before whitespace/punctuation
    classification either way."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
        lexer.whitespace_split = True
        lexer.whitespace = " \t\r"  # exclude \n so it is emitted as its own token, not swallowed
        tokens = list(lexer)
    except ValueError:
        return None  # unbalanced quotes / unparseable -> fail open

    segments: list[list[str]] = []
    current: list[str] = []
    skip_redir_target = False
    for tok in tokens:
        if not tok:
            continue
        if skip_redir_target:
            skip_redir_target = False
            continue
        # A redirection operator (`>`, `>>`, `<`, `2>`, `&>`, ...) is not a
        # command separator; the next token is its target, not a command/arg.
        if ("<" in tok or ">" in tok) and all(c in "<>&" for c in tok):
            skip_redir_target = True
            continue
        # Command separators (including a bare, unquoted newline) -> the
        # next token starts a new segment.
        if all(c in ";|&()\n" for c in tok):
            if current:
                segments.append(current)
            current = []
            continue
        current.append(tok)
    if current:
        segments.append(current)
    return segments


def strip_command_prefix(segment: list[str]) -> list[str]:
    """Drop a leading env-assignment prefix (`FOO=bar`) and/or leading shell
    keywords (`if`, `then`, ...) from one command segment — the same
    command-slot-transparency rule `find_git_push_invocations` always
    applied, factored out so `find_scan_script_executions` gets it too
    without a second copy of the logic. Matches consecutively (`FOO=1 BAR=2
    if git push` all strip) exactly as the original inline loop did."""
    i = 0
    while i < len(segment):
        tok = segment[i]
        if "=" in tok and tok.split("=", 1)[0].isidentifier():
            i += 1
            continue
        if tok in _SHELL_KEYWORDS:
            i += 1
            continue
        break
    return segment[i:]


def find_git_push_invocations(command: str) -> list[list[str]]:
    """Return the argument-token list of each `git push` found in command position.

    Built on `iter_command_segments` (tokenize + split on separators/
    redirection — see that function's docstring for why it is shared with
    the scan-execution detector rather than duplicated) plus
    `strip_command_prefix` (env-assignment / leading shell keywords). Within
    each segment: the effective first token must be `git` (or end in
    `/git`), then walk remaining tokens skipping git global options (and the
    value of value-taking ones) to find the first non-option token — it
    must be `push`. Each detected push contributes the token list up to the
    end of its segment, so the caller can check for `--dry-run`. Constructs
    that hide `git` behind another command word (`bash sync.sh`, `eval`,
    `$(...)`, `xargs`, ...) are not modelled and under-detect — acceptable
    for a backstop that must fail open. A tokenizer error returns []
    (fail open), same as before."""
    segments = iter_command_segments(command)
    if segments is None:
        return []  # unparseable -> fail open

    pushes: list[list[str]] = []
    for raw_segment in segments:
        segment = strip_command_prefix(raw_segment)
        if not segment:
            continue
        head = segment[0]
        if not (head == "git" or head.endswith("/git")):
            continue  # not a git invocation in this segment
        current_args: list[str] | None = None  # collecting args of an active `git push`
        skip_value = False
        for tok in segment[1:]:
            if current_args is not None:
                current_args.append(tok)
                continue
            if skip_value:
                skip_value = False
                continue
            if tok in _GIT_VALUE_OPTS:
                skip_value = True
                continue
            if tok.startswith("-"):
                continue  # other git global option
            # first non-option token after `git` = the subcommand
            if tok == "push":
                current_args = []
                pushes.append(current_args)
            else:
                break  # a different git subcommand -> not our concern, rest of segment skipped
    return pushes


# --- Publication-safety scan EXECUTION detection (2026-07-26 hardening) ---
# Basenames the scanner ships under, across both provider lines and both
# shell targets. Matched by BASENAME only (never by directory), case-
# insensitively (Windows paths are case-insensitive and real PowerShell/CMD
# invocations on this machine vary case), so any installed or repo-local
# copy at any of the pack's own script paths is recognized.
_SCAN_SCRIPT_BASENAMES = {
    "check-publication-safety.sh", "check-publication-safety.ps1",
    "check-publication-gate.sh", "check-publication-gate.ps1",
}

# Interpreters that can be told to run an arbitrary script file as their
# FIRST operand (`bash x.sh`, `sh x.sh`, `. x.sh` / `source x.sh`). A bare
# `./x.sh` (or any other path ending in one of the basenames above) with NO
# interpreter prefix is also recognized — see `_segment_runs_scan_script`'s
# direct-exec branch.
_SHELL_INTERPRETERS = {"bash", "sh", "dash", ".", "source"}

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


def _segment_runs_scan_script(raw_segment: list[str]) -> bool:
    """True if this ONE command segment's own leading command word directly
    EXECUTES a publication-safety scan script — never merely names one as an
    argument to some OTHER command. A `grep`/`cat`/`ls`/`Test-Path`/
    `ParseFile` of the scanner's path is a MENTION, not an execution, and
    must return False (this is the distinction the prior plain-substring
    regex could not draw — reproduced live both synthetically and against
    real historical `Test-Path` / `ls` mentions on this machine, 2026-07-26)."""
    segment = strip_command_prefix(raw_segment)
    if not segment:
        return False
    head_base = _basename(segment[0]).lower()

    # Direct exec: the command word itself IS the scanner
    # (`./check-publication-safety.sh`, a bare basename on PATH, or an
    # absolute/relative path to it).
    if head_base in _SCAN_SCRIPT_BASENAMES:
        return True

    # Interpreter + script-path-as-first-operand (`bash check-...sh`, ...).
    if head_base in _SHELL_INTERPRETERS:
        return len(segment) > 1 and _basename(segment[1]).lower() in _SCAN_SCRIPT_BASENAMES

    # PowerShell / pwsh, any casing, optional `.exe` suffix.
    ps_name = head_base[:-4] if head_base.endswith(".exe") else head_base
    if ps_name in ("powershell", "pwsh"):
        i = 1
        while i < len(segment):
            flag = segment[i].lower()
            if flag in _PS_FILE_FLAGS:
                return i + 1 < len(segment) and _basename(segment[i + 1]).lower() in _SCAN_SCRIPT_BASENAMES
            if flag in _PS_COMMAND_FLAGS:
                if i + 1 >= len(segment):
                    return False
                # -Command's value is itself a command string — recurse
                # through the SAME tokenizer/segmenter, not a second parser.
                nested = " ".join(segment[i + 1:])
                return _command_is_solely_scan_execution(nested)
            i += 1
        return False
    return False


def _command_is_solely_scan_execution(command: str) -> bool:
    """True if `command` contains EXACTLY ONE shell command segment and that
    segment EXECUTES a publication-safety scan script. Deliberately rejects
    ANY additional chained/piped/backgrounded segment (`;`, `&&`, `||`, `|`,
    `&`) — even a benign-looking one (`| tail`, `; echo done`) — because of
    the 2026-07-26 adversarial-gate compound-command finding: a command that
    runs the REAL scanner ALONGSIDE a second, independently-invoked sibling
    command in the SAME tool call (`bash check-publication-safety.sh; grep
    -rn 'examined' tests/`) merges both commands' stdout into ONE
    correlated tool result, so a real, correctly-zero-file scan plus an
    unrelated sibling command's own real output can together satisfy the
    clean-result regex with no real clean scan of anything having occurred.
    There is no way to attribute which OUTPUT LINE came from which SEGMENT
    once the shell has merged them into one stdout stream, so the only
    sound rule is: credit an invocation as scan evidence ONLY when the scan
    is the single, solitary command in that call. Pure stream REDIRECTION
    (`2>&1`, `> file`) is NOT a second segment — `iter_command_segments`
    strips redirection targets, never splits on them — and remains allowed
    (`bash check-publication-safety.sh 2>&1 > out.txt` is still one
    segment). This is a disclosed, deliberate trade-off (a real scan piped
    through `| tail` no longer counts as gate evidence), not a silent
    regression — see the module docstring's WHAT THIS STILL DOES NOT COVER
    section — and it is the direction that fails safe: it makes the gate
    under-count real scans, never over-count a compound one."""
    segments = iter_command_segments(command)
    if not segments or len(segments) != 1:
        return False
    return _segment_runs_scan_script(segments[0])


def find_scan_script_executions(command: str) -> bool:
    """Public entry point: True if `command` is (solely) a real EXECUTION of
    a publication-safety scan script. Replaces a plain substring regex over
    a call's flattened text, which matched a MENTION exactly as readily as
    an execution. `/agents-check-safety` is intentionally not matched as its
    own shape here — see the comment above SCAN_CLEAN_TRACKED_REGEX's
    former neighbor for why: no real transcript on this machine ever shows
    it as a distinct tool-call shape, and its own documented steps always
    bottom out in a real `bash .../check-publication-safety.sh` call, which
    this function recognizes like any other real execution."""
    return _command_is_solely_scan_execution(command)


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    # Subagent context: mirrors check-bugfix-discipline.py. The subagent's
    # envelope points at the MAIN session transcript, and the subagent cannot
    # put the user-side [approve-publication] marker there — gating it here is
    # an un-overridable false block. Governance still forbids delegating a
    # push to a subagent to dodge review; this hook stays a backstop.
    if envelope.get("agent_id"):
        return 0

    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return 0

    pushes = find_git_push_invocations(command)
    if not pushes:
        return 0  # no `git push` in command position

    if all("--dry-run" in args for args in pushes):
        return 0  # every push is a dry run; nothing is sent

    transcript_path = envelope.get("transcript_path") or ""
    if not transcript_path:
        return 0  # cannot determine turn state; fail open

    entries = read_transcript_tail(transcript_path, TRANSCRIPT_TAIL_LINES)
    last_user_entry, user_text, after_user_entries = last_genuine_user_message(entries)

    if last_user_entry is None:
        user_text = ""

    # (a) Per-turn user-side override — the marker counts ONLY from the last
    # genuine user message, never from assistant prose / tool calls / output.
    if APPROVE_MARKER_REGEX.search(user_text):
        return 0

    # (b) Publication-safety scan EXECUTED this turn (find_scan_script_
    # executions — real execution, never a mere MENTION of the scanner's
    # name as some other command's argument; see that function's docstring
    # and the 2026-07-26 mention-vs-execution hardening) AND that SAME
    # invocation's OWN tool OUTPUT (correlated by the provider's own
    # call-identity field — never by mere co-occurrence anywhere in the
    # turn: see the module docstring's CORRELATION note) reports a clean
    # result over a non-empty `tracked` set, AND the user explicitly
    # instructed a push in their last message. Correlation is load-bearing:
    # an unrelated tool call (a Read, a Grep, anything) whose OWN output
    # happens to contain text shaped like the scanner's clean-result line
    # must NOT satisfy this — only the specific call that itself EXECUTED
    # the scanner gets to have its own answering output checked against
    # SCAN_CLEAN_TRACKED_REGEX.
    if PUSH_INSTRUCTION_REGEX.search(user_text):
        # COLLISION REJECTION (see the module docstring's COLLISION REJECTION
        # note): correlating by id is only sound while an id is unique. Track
        # every entry INDEX a call id / result id was seen at (not just
        # whether it was seen) so a same id claimed by more than one call, or
        # more than one output, can be detected and excluded — never
        # resolved by guessing which claimant is "the real one". The same
        # index doubles as ORDERING evidence: `after_user_entries` is forward
        # chronological, so a credited result must be found at a strictly
        # LATER index than the call it answers.
        #
        # CALL-SIDE UNIQUENESS COVERS EVERY ID-CARRYING CALL (see the module
        # docstring's CALL-SIDE UNIQUENESS COVERS EVERY ID-CARRYING CALL note):
        # `call_positions` is built from `extract_model_tool_calls_with_ids` --
        # ANY tool call with an id, not only shell calls -- because what makes
        # an id ambiguous is any second claimant regardless of tool type. Scan
        # CALL detection stays a SEPARATE walk over
        # `extract_model_shell_commands_with_ids`, because what makes a call a
        # scan invocation is its command text, and only a shell call can ever
        # execute the scanner.
        call_positions: dict[str, list[int]] = {}
        scan_call_ids: set[str] = set()
        for idx, entry in enumerate(after_user_entries):
            for call_id, _call_text in extract_model_tool_calls_with_ids(entry):
                call_positions.setdefault(call_id, []).append(idx)
            for call_id, command_text in extract_model_shell_commands_with_ids(entry):
                if find_scan_script_executions(command_text):
                    scan_call_ids.add(call_id)

        # A scan-matching id claimed by more than one call in this turn is
        # ambiguous — exclude it entirely rather than crediting either call.
        unambiguous_scan_call_ids = {
            call_id
            for call_id in scan_call_ids
            if len(call_positions.get(call_id, [])) == 1
        }

        if unambiguous_scan_call_ids:
            result_positions: dict[str, list[int]] = {}
            clean_result_ids: set[str] = set()
            for idx, entry in enumerate(after_user_entries):
                for result_id, result_text in extract_tool_outputs_with_ids(entry):
                    result_positions.setdefault(result_id, []).append(idx)
                    if SCAN_CLEAN_TRACKED_REGEX.search(result_text):
                        clean_result_ids.add(result_id)

            for call_id in unambiguous_scan_call_ids:
                positions = result_positions.get(call_id, [])
                # Mirror collision rule, result side: an id claimed by more
                # than one tool output cannot be trusted to be THIS call's
                # own answer either — exclude rather than pick one.
                if len(positions) != 1 or call_id not in clean_result_ids:
                    continue
                # ORDERING: the credited result must sit strictly AFTER the
                # call it is answering. A call and its own real answering
                # result can never share one transcript entry (see the
                # module docstring's COLLISION REJECTION note), so `>` never
                # rejects a genuine pair.
                if positions[0] > call_positions[call_id][0]:
                    return 0

    # Deny.
    reason = (
        "Git-push publication gate: this Bash command runs `git push` (an "
        "irreversible publication), but this turn shows neither the per-turn "
        "user approval marker nor a publication-safety scan that reported a "
        "clean result.\n\n"
        "Publication requires human review PLUS a leak-check of staged changes "
        "(Publication safety governance). Pick one before retrying:\n\n"
        "  (a) If the user has NOT explicitly approved this push: STOP, report "
        "readiness to push, and ask the user to approve. The user approves by "
        "including `[approve-publication]` in their next message; then retry. "
        "The marker is honored only from the user's own message and only for "
        "that turn.\n\n"
        "  (b) If the user already instructed you to push in their last "
        "message: run a publication-safety scan (check-publication-safety.sh, "
        "its .ps1 twin, check-publication-gate.sh/.ps1, or /agents-check-safety "
        "— ANY installed or repo-local copy counts; no specific path is "
        "required) YOURSELF, as your OWN tool call, in THIS turn. A scan the "
        "OPERATOR runs in their own terminal does not count — only a scan you "
        "invoke, in this turn, is visible to this gate. Run it ALONE: a "
        "standalone command with nothing chained or piped after it in the "
        "same call (`bash check-publication-safety.sh` — not `... ; grep ...` "
        "or `... | tail ...`) — this gate can no longer credit a scan that "
        "shares its call with any other command, because their output "
        "cannot be told apart afterward. The scan must also have something "
        "to examine: a scan that reports zero staged files does NOT satisfy "
        "this gate, even though it exits clean — that is what happens after "
        "you have already committed (the staged index then equals HEAD), "
        "and it means nothing was actually scanned. Stage the change first "
        "(or use marker (a) instead), then retry once the scan's own output "
        "reports a clean result over a NON-EMPTY set. If you already ran the "
        "scan correctly and this still denies, the scan-and-result pair may "
        "simply be too far back in this turn for the gate to see (only the "
        "most recent transcript entries are read) — re-run the scan closer "
        "to the push, or use marker (a).\n\n"
        "  (c) To test what would be sent without publishing, use "
        "`git push --dry-run` — it is always allowed.\n\n"
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
