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
clean result over a NON-EMPTY tracked staged set, OR a NON-EMPTY published
commit range bound to the push's own remote and destination (`range` mode,
2026-07-27 — see the RANGE-MODE BRANCH (b) note below) — combined with an
explicit push instruction in the last genuine user message.

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
extraction through the scan-evidence correlation loop ran unguarded. Both
wrapper scripts (`check-git-push-gate.sh`, `check-git-push-gate.ps1`)
unconditionally exit 0 regardless of what the python helper does internally
— that is the deliberate fail-open contract for a hook that CANNOT decide
(missing transcript, malformed envelope, no command). It is NOT a defensible
outcome for a hook that CRASHED WHILE DECIDING: an uncaught exception in that
unguarded code printed nothing to stdout and exited non-zero, the wrapper
discarded that exit code and exited 0 anyway, so the model-facing result was
a SILENT ALLOW — indistinguishable from a legitimate pass to everything
downstream, the identical failure-indistinguishable-from-success shape this
same review batch kept finding elsewhere. The fix moves every step from
tool-input extraction through the scan-evidence loop into `evaluate_push`,
called from `main()` inside one `try/except Exception` that treats a raised
exception as "fall through to the deny payload", never as "return 0
(allow)" — see `evaluate_push`'s own docstring for the exact mechanics and
why the five pre-existing deliberate fail-open returns inside it are
unaffected (they are ordinary returns, not exceptions).

RANGE-MODE BRANCH (b) ADDED (2026-07-27, narrow scope — work-items/active/
2026-07-26-push-gate-range-receipt/, `$lead` disposition overriding a PARK
recommendation on new operator evidence: "меня задолбали сессии своими
[approve-publication]", demonstrated live in the same session — an explicit
plain-language push instruction denied anyway because branch (b) as shipped
was unreachable). `tracked` mode's subject is `git diff --cached`, which the
operator's own governance-prescribed workflow (commit early, review rounds,
push many turns later) leaves EMPTY by push time — the staged index already
equals HEAD, so a scan run there examines nothing and branch (b) is
STRUCTURALLY UNREACHABLE, routing every push onto the marker (a) — the one
branch that needs no leak-check at all. `check-publication-safety.sh --range
<remote> <dst>` scans a DIFFERENT subject: the commit set about to be
PUBLISHED, modelled as `<tip> --not --remotes=<remote>` (`tip` resolved as
the current HEAD at scan time), reading content from the COMMITTED BLOB at
`tip` — never the working tree, never the index. Its receipt names
`remote`/`dst`/`tip` (`SCAN_CLEAN_RANGE_REGEX`, whole-line anchored under
`re.MULTILINE` from the start, with the SAME `[1-9]\\d*` zero-examined armor
and the SAME `SCAN_FAILURE_MARKER_REGEX` exclusion `SCAN_CLEAN_TRACKED_
REGEX` already carries — see that regex's own comment for why each of those
three conditions is load-bearing), and this hook credits a range receipt
under the IDENTICAL call-id-correlation / collision-rejection / ordering
machinery as `tracked` — gated on one additional check `tracked` mode has
never needed: the receipt's declared `remote` and `dst` must equal every
detected `git push`'s own argv tokens (`_extract_push_remote_and_dst`).

NARROW BY DELIBERATE SCOPE CUT, NOT OVERSIGHT. The design this predicate is
drawn from (`work-items/active/2026-07-26-push-gate-range-receipt/design.md`,
revision 2, `$architecture-reviewer` PASS) specified a much larger grammar on
top of the same range-scanning idea: an exact-spelling argv allowlist (every
token after `push` individually admitted or denied), a literal-40-hex-SHA
refspec-source binding (the push's refspec source compared against the
receipt's `tip`, closing a TOCTOU window where a command mutates git state —
e.g. `git commit` — and pushes in the SAME call, before this hook ever
runs), and a pinned git-config gate (`push.followTags`, `remote.*.mirror`,
...). `$lead` cut ALL of that from this item after re-scoping to the
operator's actual, recurring pain — "every push falls to the marker" — which
none of that wider grammar removes; the SCANNER'S RANGE-COMPUTATION AND
RECEIPT ALONE do. See that work item's `status.md` "$lead disposition" for
the full reasoning. What this means concretely, stated as a residual rather
than left implicit: this predicate binds ONLY `remote` + `dst`. A command
that runs a git-state-mutating command and `git push` together in one call,
or that adds a flag the wider (unbuilt) grammar would deny (`--force`, a tag
refspec, `git -c push.followTags=true`, ...), CAN still be credited here as
long as `remote`/`dst` match — a SMALLER hole than every push falling to the
no-scan marker branch (today's actual, structural defect), but a real,
disclosed residual, not a hidden one. Closing it further is filed as
separate work, not silently promised here.

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

Decision algorithm (fail-open on envelope-parse failure, step 1, and on the
five deliberate no-decision returns in steps 2-6; an uncaught exception
anywhere in steps 2-8 now falls through to the DENY payload at step 9 rather
than silently allowing — 2026-07-26 hardening, see `evaluate_push`'s
docstring and the module docstring's "A CRASH WHILE DECIDING" note above):

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
  7. If the LAST GENUINE USER MESSAGE contains `[approve-publication]` AND
     that message is no longer than MARKER_MAX_MESSAGE_LENGTH characters →
     exit 0. The marker is honored ONLY from the user's own text — never from
     assistant prose, tool calls, or tool output — because prior provider or
     file content quoting the marker must not approve a publication. The
     length bound (2026-07-26 hardening; see MARKER_MAX_MESSAGE_LENGTH's own
     comment for the full contract decision and measurements) exists because
     the deny reason at step 9 embeds this same marker verbatim, so an
     operator who copies that reason back into chat reproduces the identical
     marker; a message shaped like a copied multi-paragraph deny block does
     not count as an approval here.
  8. If the current turn (entries after the last genuine user message) shows
     a publication-safety scan invocation among the model's own tool CALLS,
     under an id UNIQUE among this turn's calls (see COLLISION REJECTION note
     below), WHOSE OWN correlated tool OUTPUT (same call id — see the
     CORRELATION note above), itself under an id unique among this turn's
     outputs and recorded STRICTLY AFTER the call it answers, reports EITHER
     (i) a clean, non-empty, `tracked`-mode result ON A WHOLE LINE BY ITSELF
     (see the RESULT MATCH IS WHOLE-LINE note above and `SCAN_CLEAN_TRACKED_
     REGEX`'s own comment), OR (ii) a clean, non-empty, `range`-mode result
     ON A WHOLE LINE BY ITSELF whose declared `remote` and `dst` equal every
     detected `git push`'s own argv tokens (see the RANGE-MODE BRANCH (b)
     note above and `SCAN_CLEAN_RANGE_REGEX`'s own comment) — AND in EITHER
     case does NOT also carry the scanner's own self-reported failure line
     (`SCAN_FAILURE_MARKER_REGEX`), AND the last genuine user message
     contains an explicit push-instruction signal (`push`, `запушь`,
     `залей`, ...) → exit 0.
  9. Otherwise — including when steps 2-8 raise an uncaught exception (see
     the "A CRASH WHILE DECIDING" note above and `evaluate_push`'s own
     docstring; 2026-07-26 hardening) — emit a structured `permissionDecision:
     "deny"` payload with exact compliance instructions. Always exit 0 (the
     decision is carried by the stdout payload, not the exit code).

WHAT THIS STILL DOES NOT COVER (disclosed, not silently assumed away):
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
  - NO WORKTREE / REPOSITORY / DESTINATION BINDING FOR `tracked` MODE; A
    NARROWER GAP FOR `range` MODE (2026-07-26, adversarial-gate finding,
    high; refined 2026-07-27 when `range` mode's remote+dst binding shipped
    — see the RANGE-MODE BRANCH (b) note above). For `tracked`, the
    clean-result line still carries no repository, worktree, or destination
    identity at all — it is a plain string. This repository alone runs SIX
    live worktrees of itself and forward-commits through them. A scan
    invoked (and correlated) in one worktree's turn and a `git push` issued
    in a DIFFERENT worktree within the same turn are NOT distinguished by
    anything in this mechanism for `tracked` mode. For `range` mode, the
    DESTINATION (remote name + dst ref) IS bound to the push's own argv —
    but repository/worktree IDENTITY is still not: the gate cannot tell
    which repository or worktree the scan actually ran in, only that SOME
    scan somewhere reported a receipt naming this destination. Binding
    repository identity requires comparing the scan's and the push's own
    effective working directory (cwd / `-C` argument), which this hook does
    not currently capture or compare in EITHER mode. Treat this exactly as
    the multi-commit gap below: real, not hypothetical, explicitly not
    closed by this change.
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

# Publication-safety scan RESULT for `range` mode (2026-07-27 — see the
# module docstring's RANGE-MODE BRANCH (b) note for the full context and the
# narrow scope this predicate stays inside). Same THREE load-bearing
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
# first two against the push's own argv (`_extract_push_remote_and_dst`,
# below) — the receipt's binding mechanism this predicate exists to check.
# `tip` is captured (and its shape validated as 40 hex characters) because it
# is always part of the real receipt's own text, but this narrow-scope
# predicate does NOT compare it against anything — see the module docstring
# for why that binding was cut from this item's scope.
SCAN_CLEAN_RANGE_REGEX = re.compile(
    r"^publication-safety:\s*clean\s*\(\s*range\s*,\s*examined\s+(?P<count>[1-9]\d*)\s+files?\s*,"
    r"\s*remote\s+(?P<remote>\S+)\s*,\s*dst\s+(?P<dst>\S+)\s*,\s*tip\s+(?P<tip>[0-9a-f]{40})\s*\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_push_remote_and_dst(push_args: list[str]) -> tuple[str, str] | None:
    """Best-effort (remote, dst) extraction from ONE detected push's argument
    list (the token list `find_git_push_invocations` returns for that push,
    i.e. everything after `push` in its command segment) — used ONLY for the
    narrow `range`-mode binding (see the module docstring's RANGE-MODE
    BRANCH (b) note and SCAN_CLEAN_RANGE_REGEX's own comment). This is
    deliberately NOT the exact-spelling argv grammar the fuller design
    specified (that is out of scope for this item): it takes the first TWO
    tokens that do not start with `-` as (remote, dst_token) and IGNORES any
    further token, rather than admitting or denying the command shape.

    Two consequences of that leniency, both intentional:
      - A push carrying a trailing redirection artifact (e.g. the stray
        file-descriptor digit `iter_command_segments` can leave behind for
        `2>&1` — see that function's own docstring) does not lose range
        credit merely because the argv token list is one token longer than
        the two we need.
      - This function makes NO admissibility claim about the rest of the
        command (a force flag, `--follow-tags`, a third positional, ...) --
        it only extracts what it needs to compare, safely, because the
        caller falls through to the marker/deny path exactly as it does
        today when this returns None or when the comparison fails. Ignoring
        extra tokens never launders anything the comparison itself does not
        already gate.

    Splits a `<src>:<dst>` refspec on its FIRST `:` to recover the
    destination (a git ref name cannot itself contain `:`); a bare token with
    no colon (`git push origin claude`) is used as-is. Returns None when
    fewer than two positional tokens are present (a bare `git push` or
    `git push origin` alone) or when the extracted destination is empty (a
    delete refspec, `:dst`, or `+:dst`) -- either way, range credit is simply
    not attempted, and the marker/deny fallback is unaffected."""
    positionals = [tok for tok in push_args if not tok.startswith("-")]
    if len(positionals) < 2:
        return None
    remote, dst_token = positionals[0], positionals[1]
    dst = dst_token.split(":", 1)[1] if ":" in dst_token else dst_token
    if not dst:
        return None
    return remote, dst


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
        # Normalized comparison (2026-07-26 hardening) -- see
        # `_normalized_command_word`'s docstring. The prior exact-match test
        # (`head == "git" or head.endswith("/git")`) only ever caught a bare
        # lowercase `git` or a forward-slash path ending in `/git`; measured
        # live against the shipped detector, it missed `git.exe`, `git.EXE`,
        # an absolute Windows path ending in `git.exe`, and bare-word case
        # variants `GIT`/`Git` -- all of which resolve and run identically to
        # `git` on Windows. The root cause was the exact-match test itself,
        # not the `.exe` suffix specifically, so the fix normalizes the head
        # token the same way the scan-script detector already normalizes its
        # own command word, rather than special-casing `.exe` alone.
        if _normalized_command_word(segment[0]) != "git":
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


def _normalized_command_word(token: str) -> str:
    """Lowercased basename of `token` with a trailing `.exe` suffix stripped.

    This is the SAME normalization `_segment_runs_scan_script` already
    applied inline when recognizing the PowerShell/pwsh interpreter name
    (`ps_name`, below) -- extracted here so `find_git_push_invocations`'s
    git-head test REUSES it instead of growing a second, independently-
    drifting normalizer for the identical "what shell word is this really"
    question. Two normalizers for one concept is exactly the defect class
    this file's own scan-execution detector exists to avoid (see
    `iter_command_segments`'s docstring: "one tokenizer, two consumers ...
    two parsers for one shell-command concept is how the halves drift
    apart") -- this function applies that same discipline one layer down
    (2026-07-26 hardening, `git.exe`/`GIT`/`Git` head-detection gap,
    `work-items/bugs/2026-07-26-the-deny-message-teaches-the-marker-that-
    opens-the-gate.md` §"A second, smaller one from the same review").

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

    # PowerShell / pwsh, any casing, optional `.exe` suffix -- reuses
    # `_normalized_command_word` (see its docstring) rather than repeating
    # the basename/lower/`.exe`-strip sequence inline a second time; the
    # `find_git_push_invocations` git-head test below now shares this exact
    # function instead of carrying its own copy.
    ps_name = _normalized_command_word(segment[0])
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


def evaluate_push(envelope: dict) -> bool:
    """Steps 2-8 of the decision algorithm (see the module docstring): return
    True to ALLOW the push (`main()` then exits 0 with no payload), False to
    fall through to the deny payload. MAY RAISE — `main()` wraps the call to
    this function in one try/except and treats a raised exception exactly
    like a False return (fall through to deny), never like True.

    Split out of `main()` (2026-07-26 HIGH-severity hardening — `work-items/
    bugs/2026-07-26-push-gate-new-paths-fail-open-because-the-wrapper-
    discards-the-exit-code.md`; see the module docstring's "A CRASH WHILE
    DECIDING" note for the full defect this closes). Before this split, an
    uncaught exception ANYWHERE in this logic propagated out of `main()`
    entirely: both wrapper scripts (`check-git-push-gate.sh`,
    `check-git-push-gate.ps1`) unconditionally discard the python process's
    exit code and exit 0 regardless, so a crash meant nothing was ever
    printed to stdout — no deny payload, nothing — and the model-facing
    result was a SILENT ALLOW, indistinguishable from a legitimate pass.
    Fail-open is the deliberate, documented posture for a hook that CANNOT
    decide (a missing transcript, no command, a dry run); it is not
    defensible for a hook that CRASHED WHILE DECIDING, because those two are
    indistinguishable to everything downstream.

    The bug report's own count of "five" fail-open paths refers to the five
    NUMBERED steps 2-6 in the module docstring's decision algorithm (step 3
    there bundles two code-level checks — non-dict `tool_input` and a
    missing/non-string `command` — under one label, "tool_input.command is
    absent or empty"). Concretely, SIX `return True` statements below are
    UNCHANGED by this split: subagent context, non-dict `tool_input`, no/
    empty `command`, no `git push` found, every push is `--dry-run`, and a
    missing `transcript_path`. Each is an ordinary return reached without any
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

    pushes = find_git_push_invocations(command)
    if not pushes:
        return True  # no `git push` in command position

    if all("--dry-run" in args for args in pushes):
        return True  # every push is a dry run; nothing is sent

    transcript_path = envelope.get("transcript_path") or ""
    if not transcript_path:
        return True  # cannot determine turn state; fail open

    entries = read_transcript_tail(transcript_path, TRANSCRIPT_TAIL_LINES)
    last_user_entry, user_text, after_user_entries = last_genuine_user_message(entries)

    if last_user_entry is None:
        user_text = ""

    # (a) Per-turn user-side override — the marker counts ONLY from the last
    # genuine user message, never from assistant prose / tool calls / output.
    # ALSO bounded by MARKER_MAX_MESSAGE_LENGTH (see that constant's comment
    # for the full contract decision, measurements, and disclosed residual):
    # a marker riding inside a long message — the shape of a copied deny
    # block, not a one-line approval — does not open the gate here; it falls
    # through to branch (b) and then to deny, same as no marker at all.
    if APPROVE_MARKER_REGEX.search(user_text) and len(user_text) <= MARKER_MAX_MESSAGE_LENGTH:
        return True

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
            # RANGE-MODE binding (2026-07-27 — see the module docstring's
            # RANGE-MODE BRANCH (b) note). Maps a correlated result's OWN id
            # to the (remote, dst) its range receipt declared, so branch (b)
            # below can credit a `range`-mode clean receipt the SAME way it
            # already credits a `tracked`-mode one — same correlation,
            # collision-rejection, ordering, and failure-marker exclusion —
            # gated on the ADDITIONAL remote/dst comparison against argv that
            # `tracked` mode has never needed (it names no destination).
            clean_range_bindings: dict[str, tuple[str, str]] = {}
            for idx, entry in enumerate(after_user_entries):
                for result_id, result_text in extract_tool_outputs_with_ids(entry):
                    result_positions.setdefault(result_id, []).append(idx)
                    # WHOLE-LINE match AND no co-occurring scanner FAILURE
                    # line (2026-07-26 critical hardening — see
                    # SCAN_CLEAN_TRACKED_REGEX's and SCAN_FAILURE_MARKER_
                    # REGEX's own comments): a scan's honest report of its
                    # OWN block must never be credited as its own clean pass.
                    # The SAME exclusion applies to a range receipt, for the
                    # identical reason (2026-07-27) — checked ONCE, ahead of
                    # both mode-specific matches below, so neither can be
                    # credited from a result that also reports its own block.
                    if SCAN_FAILURE_MARKER_REGEX.search(result_text):
                        continue
                    if SCAN_CLEAN_TRACKED_REGEX.search(result_text):
                        clean_result_ids.add(result_id)
                    range_match = SCAN_CLEAN_RANGE_REGEX.search(result_text)
                    if range_match:
                        clean_range_bindings[result_id] = (
                            range_match.group("remote"),
                            range_match.group("dst"),
                        )

            # Every detected push in this command must extract to the SAME
            # (remote, dst) the range receipt declared — mirrors the existing
            # `all(... for args in pushes)` posture the `--dry-run` check
            # above already uses: an ambiguous or partially-unextractable
            # push list is never credited by range mode, it simply falls
            # through (the marker and `tracked`-mode evidence are still
            # available). `_extract_push_remote_and_dst` returning None for
            # ANY push makes range credit impossible for this command.
            push_bindings = [_extract_push_remote_and_dst(args) for args in pushes]
            range_binding_uniform = (
                all(binding is not None for binding in push_bindings)
                and len(set(push_bindings)) == 1
            )

            for call_id in unambiguous_scan_call_ids:
                positions = result_positions.get(call_id, [])
                # Mirror collision rule, result side: an id claimed by more
                # than one tool output cannot be trusted to be THIS call's
                # own answer either — exclude rather than pick one.
                if len(positions) != 1:
                    continue
                # ORDERING: the credited result must sit strictly AFTER the
                # call it is answering. A call and its own real answering
                # result can never share one transcript entry (see the
                # module docstring's COLLISION REJECTION note), so `>` never
                # rejects a genuine pair.
                if positions[0] <= call_positions[call_id][0]:
                    continue
                if call_id in clean_result_ids:
                    return True
                if (
                    range_binding_uniform
                    and call_id in clean_range_bindings
                    and clean_range_bindings[call_id] == push_bindings[0]
                ):
                    return True

    return False  # no allow condition satisfied -> caller falls through to deny


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    try:
        if evaluate_push(envelope):
            return 0
    except Exception:
        # A crash WHILE DECIDING is a decision not made, not a decision to
        # allow — fall through to the deny payload below rather than
        # returning 0 silently (2026-07-26 hardening; see evaluate_push's
        # own docstring and the module docstring's "A CRASH WHILE DECIDING"
        # note for the full defect this closes).
        pass

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
