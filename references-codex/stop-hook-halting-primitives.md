# Stop-Hook Halting Primitives

Measured 2026-07-25 against `claude` 2.1.220 and `codex-cli` 0.145.0 (Codex source pinned and re-fetched
at tag `rust-v0.145.0`); extended 2026-07-26 with T-14 and T-20, two live Codex-line probes of whether a
`stopReason`/`systemMessage` payload actually reaches the operator. This file is the durable,
independently re-verifiable form of the finding; `work-items/active/2026-07-25-review-round-cap-
enforcement/model-review.md` and `design.md` §0.9/§4.4c are the session narrative and are not required to
re-check anything below.

## Current pack status (2026-07-29)

The r8 SEN-2 cut documented below remains the historical disposition of the rejected threshold/NOTICE-only
design; it no longer means SEN-2 is absent. Accepted decision
`2026-07-29-host-correlated-action-evidence-for-delivery-gates` reinstates SEN-2 as the registry's third,
stateless RESOLVE-tier sentinel for one exact opted-in Primary mutation action. Only a direct semantic
exact-target mutation plus a same-id explicit-success result earns credit; child/re-entry skips bound it to
one block per root user turn, and invalid input fails open. T-14/T-20 are unchanged: HALT remains absent,
and operator-directed NOTICE remains unreliable on Codex.

## The fact

At the `Stop` hook event, on **both** the Claude Code line and the Codex line, `decision: "block"` is a
**forced continuation**, not a halt: it makes the model produce another turn using `reason` as the
continuation content. The actual halting primitive is a different, universal field:
`{"continue": false, "stopReason": "..."}`. `continue: false` **takes precedence over
`decision: "block"`** on both lines — if any fired hook returns `continue: false`, the run stops even if
another fired hook in the same batch returned `decision: "block"`. On the Claude line, `stopReason` is
documented as shown to the **user** and explicitly **not shown to Claude** — an operator-only channel a
policed model cannot read, answer, or clear.

A third universal field, `systemMessage`, is documented the same way as `stopReason` (shown to the
**user**, never to the model) but is independent of both `continue` and `decision` — it never forces a
continuation and never halts by itself. Measured live (below): a bare `systemMessage` payload with no
other field costs **zero extra turns and zero extra hook fires** — the turn completes exactly as it
would with no hook output at all. It is the one primitive a hook author can reach for purely to notify
the operator without perturbing the run in either direction.

## Why this matters for a hook author

A `Stop` hook that wants to genuinely end a run — escalate to a human, refuse to let the model keep
going, break a churn loop — must emit `continue: false` (+ `stopReason`), not `decision: "block"`.
Emitting `decision: "block"` at `Stop` does the opposite of what "block" suggests: it hands the model a
new prompt built from `reason`, and the conversation continues. This pack's own shipped `Stop` hooks
(`check-passive-polling-stop`, `check-work-items-archival-stop`) currently emit `decision: "block"` by
design — that is a deliberate choice to keep the model in the loop for a bounded correction, not a
mechanism error — but any *new* `Stop` hook intended to force a hard stop must reach for `continue: false`
instead.

A hook that wants to surface information to the operator **without** blocking, forcing a continuation,
or costing a model turn — a soft warning, a "this condition still persists" escalation — should emit
`systemMessage` alone, **but see T-14/T-20 below first**: on the Codex line, measurement shows this
channel does not reach the operator either. `check-work-items-archival-stop.py`'s invariant registry
(`workitem_sentinels.py`) originally shipped a three-way split matching the three fields documented
above — `decision:"block"` (RESOLVE), `continue:false` + `stopReason` (HALT), `systemMessage` alone
(NOTICE) — but removed the HALT tier entirely at r7 (T-14: neither `stopReason` nor `systemMessage`
reached the operator inside a HALT payload on Codex, and `--json` mode emitted no hook-status event at
all) and, at r8, cut the one invariant (SEN-2, delivery drought) that depended on NOTICE reaching an
operator for its own release rationale, after T-20 additionally measured that a **bare** `systemMessage`
NOTICE — no `continue`, no `decision` — *also* does not reach the operator on Codex. The registry that
ships now emits exactly one tier that is genuinely cross-line: RESOLVE (`decision:"block"`), which is
model-directed and works identically on both lines. Every operator-directed output this pack emits (the
§4.4a `stop_hook_active` escalation NOTICE, the FM-1 sentinels-unavailable fallback NOTICE) is
Claude-line only, and there is no run-terminating tier shipped on either line. See T-14/T-20 below for the
measurements that drove this, and design.md §0.9/§4.4c for the design-level disposition.

## Measured, Claude line

Same one-word task (`Reply with exactly the word: PROBEOK`), same hook registration (a `Stop` hook
writing one JSON object to stdout and exiting 0), same model, same session shape:

| Stop-hook payload | `num_turns` | Hook fires | `terminal_reason` | assistant messages |
| --- | --- | --- | --- | --- |
| `{"continue": false, "stopReason": "..."}` | 1 | 1 | `stop_hook_prevented` | 1 |
| `{"decision": "block", "reason": "..."}` | 10 | 9 | `completed` | 18 |
| `{"systemMessage": "..."}` (no other field) | 1 | 1 | `completed` | 1 |

The `systemMessage`-alone row is the one to read carefully against the `decision:"block"` row above it:
both show `terminal_reason: completed` (neither is a runtime-level halt), but `systemMessage` alone costs
**one** hook fire and **one** assistant message where `decision:"block"` costs 9 and 18 — `completed`
means "the runtime did not forcibly stop the run," not "the payload had no effect." Preserved evidence
for this row: `/.scratch/2026-07-25-sentinel-design-probes/r4probe/sysmsg/out3.json` (the raw stream-json
result, `num_turns:1`, `terminal_reason:"completed"`, one assistant record containing exactly `PROBEOK`)
and the paired envelope `env_2013_22950.json` (`hook_event_name:"Stop"`, `stop_hook_active:false`),
captured from a `Stop` hook registered to emit `{"systemMessage": "..."}` and nothing else.

Verbatim, official Claude Code hooks reference (fetched raw this session,
`https://code.claude.com/docs/en/hooks`):

- Universal fields: *"like `continue` work across all events."*
- `continue`: *"If `false`, Claude stops processing entirely after the hook runs. Takes precedence over
  any event-specific decision fields"*
- `stopReason`: *"Message shown to the user when `continue` is `false`. Not shown to Claude"*
- `systemMessage`: listed as a universal-field row in the JSON output table, *"Warning message shown to
  the user"* — the same audience as `stopReason` (the user, never Claude) but with no dependency on
  `continue` and no event-specific counterpart to override.

## `stop_hook_active` is advisory metadata, not a runtime cap

Across the 9 `decision: "block"` hook fires in the measurement above, the envelope's
`stop_hook_active` flag read `False` on the first fire and `True` on the other 8 — and the run still
ran to `num_turns: 10`. `stop_hook_active` is metadata the runtime sets so **each hook can choose** to
honor it (stop re-triggering its own continuation once already re-triggered once); it is not an
enforced ceiling the runtime itself applies. A hook that never checks this flag inherits unbounded
turn amplification, not a 1-extra-turn cap. This pack's own `check-work-items-archival-stop.py` and
`check-passive-polling-stop.py` do check it and early-return when set — that is why they are safe — but
the safety is each hook's own property, not a property of the `Stop` event.

## Measured, Codex line (source + installed-binary evidence, plus a live T-14/T-20 probe below)

Codex's official hook documentation and its runtime source at the installed tag agree with the Claude
line and add one further wrinkle: on Codex, `continue: false` reaches further than `Stop` — it also
halts **mid-turn** at `PostToolUse`, an event where the turn has not yet finished.

- Official docs: on `Stop`, `decision: "block"` *"doesn't reject the turn. Instead, it tells Codex to
  continue and automatically creates a new continuation prompt that acts as a new user prompt, using
  your `reason` as that prompt text"*; and *"If any matching `Stop` hook returns `continue: false`, that
  takes precedence over continuation decisions."*
- Source, `codex-rs/hooks/src/events/stop.rs` at tag `rust-v0.145.0`:
  - `:247-250` — `if !parsed.universal.continue_processing { status = HookRunStatus::Stopped; should_stop = true; ... }`
  - `:263-274` — the `else if parsed.should_block` arm sets `HookRunStatus::Blocked` and a
    `continuation_prompt`, so on the *same* hook result `continue:false` is checked first and wins.
  - `:377-379` — aggregated across all fired hooks: `should_stop = results.iter().any(|r| r.should_stop)`;
    `should_block = !should_stop && results.iter().any(|r| r.should_block)` — any hook's stop suppresses
    every hook's continuation.
  - `:486-507` — the upstream unit test `continue_false_overrides_block_decision`. Literal input
    `{"continue":false,"stopReason":"done","decision":"block","reason":"keep going"}` asserts
    `should_stop: true` and `HookRunStatus::Stopped`.
- `codex-rs/hooks/src/events/post_tool_use.rs:213-217` — the same `continue:false` arm exists on
  `PostToolUse`, i.e. a genuine mid-turn stop (the turn is not yet finished at that event, unlike `Stop`).

`systemMessage` on the Codex line: official docs describe it as *"Surfaced as a warning in the UI or
event stream"* — a display-only field, structurally independent of the `should_stop`/`should_block`
aggregation cited above (neither `HookRunStatus` variant is driven by it). T-14/T-20 below supersede what
this session originally left as an open question: measured live, neither `stopReason` nor `systemMessage`
reached the operator, in either a HALT-shaped or a bare NOTICE-shaped payload.

**The 2026-07-25 attempt at a live Codex probe was inconclusive, not negative.** An isolated `CODEX_HOME`
smoke test timed out before a turn ran (0 hook fires, no stdout), because a fresh, never-trusted
`CODEX_HOME` blocks a hook from firing at all pending an interactive trust prompt — this is why the
conclusions in this section originally rested on three source-level angles (official docs, runtime source
at the pinned tag, the installed binary's own string table) rather than a live probe. T-14/T-20
(2026-07-26) resolved the blocker by adding `--dangerously-bypass-hook-trust` to the invocation, letting
the hook fire on a fresh `CODEX_HOME` without the interactive trust step, and obtained a genuine live
result.

### T-14 — HALT payload (`continue:false` + `stopReason` + `systemMessage`)

Measured: neither `stopReason` nor `systemMessage` reached the operator inside a HALT-shaped payload, and
`--json` mode emitted no hook-status event at all — the operator had no observable signal that a `Stop`
hook had fired, let alone what it said. This is the direct cause of r7's HALT-tier removal (design.md
§4.4c/§1.0): a run-terminating tier that is silent to the operator on one of its two lines is not merely
unattributed, it is undetectable, and this pack's three installed copies of the hook are byte-identical
(G-2) — the tier would be all-or-nothing across both lines regardless of which line the fired hook lives
on.

### T-20 — a BARE `systemMessage` NOTICE (no `continue`, no `decision`)

Measured: a `systemMessage`-only payload — the exact shape this pack's NOTICE tier emits — also did not
reach the operator on the Codex line. This is the direct cause of r8's SEN-2 cut (design.md §0.9): SEN-2
(delivery drought) was the one invariant whose entire release rationale depended on NOTICE reaching
*someone* (the operator — NOTICE is turn-free by design and therefore never reaches the model either);
T-20 showed it reaches nobody on Codex, on the same line the admitted incident happened on, and this
pack's byte-identical installed copies again make the gap all-or-nothing rather than fixable by
Codex-specific tuning.

**Confirmed genuine, not a false negative.** Three independent checks rule out "the probe itself was
broken and produced a null result that only looks like absence":

1. `--dangerously-bypass-hook-trust` was passed explicitly, ruling out the fresh-install hook-trust gate
   that produced the 2026-07-25 INCONCLUSIVE (not negative) attempt above.
2. The hook script's own `fired.log` side effect — a line appended on every invocation, independent of
   what the hook returns to the runtime — confirmed the hook process actually executed and reached the
   point where it emitted its payload. The null result is a **delivery** null, not an **execution** null.
3. Six separate executions across three distinct `CODEX_HOME` configurations each produced (a) the
   `fired.log` marker and (b) a saved envelope on disk, with zero exceptions — a consistent negative
   across independent configurations, not a one-off fluke.

The captured envelope also corroborates a second, unrelated design point: it carried
`"transcript_path": null` — the literal Codex `string | null` case that `workitem_sentinels.py`'s
tier-viability rule (design.md §4.4b) and this adapter's own guard (`if not isinstance(transcript_path,
str): transcript_path = ""` in `check-work-items-archival-stop.py`) exist to handle, observed in the wild
rather than only reasoned about from the documented type.

### Consequences for this pack's shipped hooks

- **RESOLVE is the only genuinely cross-line tier.** `decision:"block"` (SEN-0, SEN-1) works identically
  on both lines because it is read by the MODEL, not the operator — T-14/T-20 only measured the
  operator-facing fields (`stopReason`, `systemMessage`), which is exactly the channel every other tier
  depended on.
- **A persistent RESOLVE forces a fresh model continuation every user turn, forever — it does not go
  silent.** `stop_hook_active` is a WITHIN-turn flag: measured `False` on the first of nine envelope
  fires and `True` only on repeat fires inside that SAME turn's own forced-continuation processing —
  it resets at the first `Stop` fire of every new user turn. A RESOLVE-tier finding (SEN-0 or SEN-1)
  that still holds therefore re-fires to the model at the start of every subsequent turn, indefinitely,
  costing one continuation each time. The escalation to a turn-free NOTICE (this adapter's own §4.4a
  rule) only triggers in the narrower within-turn double-fire case — reasonable on the Claude line,
  where that NOTICE reaches the operator (measured turn-free, one hook fire; table above), but T-20
  shows the identical NOTICE reaches nobody on Codex even then. Net effect on Codex: a per-turn model
  tax with no operator signal at all, never a one-time notice that then falls silent.
- **FM-1 (the sentinels-unavailable fallback) is undeliverable on Codex, so the guard can vanish
  silently.** If `workitem_sentinels.py` fails to import for any reason, `check-work-items-archival-
  stop.py`'s `except Exception` fallback prints `{"systemMessage": SENTINELS_UNAVAILABLE_NOTICE}` and
  exits 0 — the one signal that would tell an operator the entire registry stopped working. On Claude
  this NOTICE reaches the operator; on Codex, per T-20, it reaches nobody. A Codex-line install can
  therefore lose this guard entirely, silently, with zero operator-visible signal — the pack's own
  fail-open-to-silence failure mode, on the same line the original incident happened on.

## Re-verification

Claude line (requires a throwaway Claude Code session with a `Stop` hook registered in `settings.json`
pointing at a script that writes the desired JSON to stdout and exits 0; compare `num_turns`,
`terminal_reason`, and hook-fire count in the resulting transcript for the three payloads above).

Codex line, source citations (no live Codex session required):

```bash
gh api repos/openai/codex/contents/codex-rs/hooks/src/events/stop.rs?ref=rust-v0.145.0 \
  -H "Accept: application/vnd.github.raw"
gh api repos/openai/codex/contents/codex-rs/hooks/src/events/post_tool_use.rs?ref=rust-v0.145.0 \
  -H "Accept: application/vnd.github.raw"
```

Confirm the installed Codex CLI version matches the pinned tag before trusting the source citations as
a statement about the currently-installed runtime:

```bash
codex --version   # expect: codex-cli 0.145.0
```

T-14/T-20 live re-verification (Codex line, requires a hook script that (a) appends to its own
`fired.log` on every invocation before doing anything else, so execution is provable independent of
delivery, and (b) writes the operator-facing payload under test to stdout and exits 0):

```bash
codex --dangerously-bypass-hook-trust exec --json ...   # bypasses the fresh-install hook-trust prompt
                                                          # that made the 2026-07-25 attempt inconclusive
```

Repeat across a fresh `CODEX_HOME` per run (at least 3, matching this session's evidence) and confirm,
for each of a HALT-shaped payload and a bare NOTICE-shaped payload: `fired.log` gained a line (proves
execution), a saved envelope exists (inspect its `transcript_path` field — `null` is the expected, not
anomalous, case per Codex's own `string | null` typing), and no operator-visible surface (`--json` event
stream, saved transcript, UI) shows the payload's `stopReason`/`systemMessage` text.

## Residuals

- **Resolved by T-14/T-20 (2026-07-26):** the two residuals this file previously carried here —
  whether `stopReason`/`systemMessage` reach the operator on the Codex line at all — are no longer open
  questions for the configuration actually tested (`--json`-mode `codex exec`, fresh `CODEX_HOME`,
  `--dangerously-bypass-hook-trust`): both fields reached nobody, confirmed genuine per the three checks
  above. The r7 HALT removal and the operator-channel premise behind the r8 SEN-2 cut do not need a
  human-output-mode result to hold: `--json` mode already establishes that this pack cannot rely on
  either channel reaching the operator in a configuration it must support. The accepted 2026-07-29
  decision supersedes SEN-2's absence by using model-facing RESOLVE and host-correlated mutation evidence,
  not either operator channel.
- Whether `codex exec` **human-output** mode (as opposed to `--json`) renders `reason`/`systemMessage`
  text differently is a narrower, lower-priority `ASSUMPTION (UNVERIFIED)` that remains genuinely open:
  the installed binary's `event_processor_with_human_output.rs` renders only `hook: <EventName> <Status>`
  to stderr in that mode (a fact, not re-tested by T-14/T-20), so the operator reliably learns *that* a
  hook fired even there, but whether the payload's own text is additionally shown is untested. This does
  not affect the design decisions above, which do not depend on it.
- This file does not calibrate what a `Stop`-hook turn/spend threshold should be, and does not restate
  the broader registry-design questions the source work-item explores; it documents the measured
  primitive facts (`continue:false`, `decision:"block"`, `systemMessage`, and T-14/T-20's operator-delivery
  results) and how to re-check them.

## Terms and Abbreviations

- **`continue: false`** — the universal hook-output field on both the Claude and Codex lines that stops
  the run and takes precedence over `decision: "block"`.
- **`decision: "block"`** — a hook-output field that, at the `Stop` event on both lines, *continues* the
  conversation with a new prompt instead of stopping it.
- **Envelope** — the JSON object a runtime writes to a hook's stdin describing the current event.
- **FM-1** — design.md's identifier for the sentinels-unavailable failure mode: `workitem_sentinels.py`
  fails to import and the adapter's fallback NOTICE is the only signal of the gap; undeliverable on Codex
  per T-20 (see "Consequences for this pack's shipped hooks" above).
- **Hook** — a script the runtime runs at a lifecycle event (`PreToolUse`, `Stop`, `PostToolUse`, …).
- **`HookRunStatus`** — Codex's per-hook-run outcome enum: `Stopped` (from `continue:false`), `Blocked`
  (from `decision:block`), `Failed`.
- **`systemMessage`** — a universal hook-output field on both lines, shown to the user/operator only
  (never to the model), independent of `continue`/`decision`; measured turn-free on the Claude line
  (`num_turns:1`, one hook fire, `terminal_reason:completed` — identical to no hook output at all), but
  measured (T-20) to reach nobody on the Codex line even as a bare payload.
- **`stopReason`** — the field paired with `continue:false`; on the Claude line it is shown to the human
  operator and explicitly not shown to the model; measured (T-14) to reach nobody on the Codex line.
- **`stop_hook_active`** — an envelope flag marking that the current turn was already re-triggered once
  by a `Stop` hook; advisory metadata each hook must check itself, not an enforced runtime cap.
- **T-14** — the 2026-07-26 live Codex-line probe of a HALT-shaped payload (`continue:false` +
  `stopReason` + `systemMessage`); measured that neither operator-facing field is delivered. Drove r7's
  HALT-tier removal.
- **T-20** — the 2026-07-26 live Codex-line probe of a bare `systemMessage` NOTICE payload; measured that
  it is also not delivered. Drove r8's SEN-2 cut.
- **Tag `rust-v0.145.0`** — the pinned Codex Rust-workspace release tag matching the installed
  `codex-cli 0.145.0` used for every source citation in this file.
