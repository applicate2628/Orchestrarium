---
name: bug-hunting
description: Investigate runtime bugs with diagnostic logging before any fix.
---

# Bug Hunting

## Iron law

**Stop guessing, start logging.** Every minute spent reasoning from architecture alone is a minute the runtime would have told you the truth in. Every diagnostic round you add narrows the search; every speculative fix you ship widens it.

## Rule 0 — Never fix until logs prove the hypothesis (ABSOLUTE, two-sided)

**ABSOLUTE RULE.** Hypotheses MUST be confirmed by debugging, and NO fix is permitted until full, absolute runtime confirmation. This binds at BOTH ends of every fix — confirming the cause is necessary but not sufficient:

- **Before the fix — prove the CAUSE.** No edit to production code while the working theory of the bug is still a theory. Diagnostic output must show — in the runtime, with timestamps — exactly the cause believed to be acting. If the log does not show it, the theory is wrong or incomplete; add more logging, do not patch.
- **After the fix — prove the FIX is perfectly correct.** Identifying the cause does not make a fix "done". Re-run with the diagnostics still in and prove in the runtime that (1) the symptom is gone AND (2) no adjacent behavior regressed. "It should work now" / "this is the right fix" is never confirmation — only a clean runtime log is. Until that log exists the fix stays "implemented, not yet verified", never "done". A fix asserted correct without a runtime log proving it is a Rule 0 violation as severe as patching on an unverified cause.

This applies even when the theory comes from an authoritative source: a consultant memo, a Codex/Claude answer, a Stack Overflow accepted answer, official documentation. External advice is a candidate hypothesis, not a verified one — treat it as a pointer to which signals to log next, never as a green light to ship a fix.

Trigger phrases meaning "go log, do not patch":
- "still happening" / "ничего не поменялось"
- "this needs to be checked first"
- "don't fix until logs show this"
- Any moment where you find yourself about to issue an `Edit` after reading only code, not after reading a log

## Rule 1 — When a fix does not land first try, stop guessing immediately

If a hypothesis-driven fix does not visibly remove the symptom, do not try another hypothesis-driven fix. Switch to instrumentation. Adding logs is cheap; re-rolling the dice on guesses burns user trust faster than the bug itself.

Concrete trigger: "still happening" / "ничего не поменялось" → next action is **diagnostic output**, not another speculative edit.

- **Second-cross-break stop:** If a second fix in the same session breaks a previously working neighbor, STOP all edits. Before any further edit, run a read-only multi-angle structural diagnosis covering (1) the owning invariant and call/data flow, (2) sibling modes/surfaces, and (3) timing/lifecycle/shared-state interactions; identify which prior edit changed the real symptom and verify the structural cause.

## Rule 2 — Pick the smallest signal that distinguishes live hypotheses

Pick a handful of orthogonal events and log them with a single line each, prefixed by timestamp + short tag + the state values that matter (`inFlight`, `attached`, `bounds`, `session`, etc.). One line per event, fixed shape, parseable by eye. Do not dump a wall of structured data — you will be reading dozens of these in sequence to spot the timing gap.

Provider-neutral example shape:

```
[TAG hh:mm:ss.fff] EVENT_NAME field1=value1 field2=value2 field3=value3
```

Look for:
- which event is missing entirely (the one you expected to see never fires)
- which event runs twice (unexpected re-entry or duplicate firing)
- the gap between two events (something is happening in the silence)
- a field value that disagrees with your mental model

If a UI variant works correctly but another does not, treat them as separate code paths even when they look like they share state — log inside each to confirm rather than assume.

- When N symptoms or failing cases are reported, keep N independent root hypotheses and instrument each case. Collapse them to one common root only when one observed mechanism explains every case; shared timing, location, or correlation is not proof.

## Rule 3 — Redirect stderr to a scratch file, never lean on console output

Console output is lost between iterations. Redirect to a scratch file under the repo (e.g. `.scratch/<topic>.log`, already covered by repo `.gitignore` conventions). Persistent log files survive app crashes and allow diff between runs.

PowerShell:

```powershell
Start-Process -RedirectStandardError .scratch/bug.log <command>
```

POSIX shell:

```bash
<command> 2> .scratch/bug.log
```

## Rule 4 — Visual or animation bugs go through frame extraction, not raw video

For UI bugs that depend on animation, timing, or sequence, do not stare at the raw video. Extract frames first and read the smallest set that distinguishes states. The detailed video-frame workflow lives in `$analyzing-video-bugs`. The broader visual-verification workflow (theme/state context, capturing a fresh recording when none exists, classifying structural vs cosmetic) lives in `$windows-gui-manual-testing`.

If the user has already identified a specific frame number ("frame 39 is the bug"), use that pointer directly — it is a one-word hint that saves an hour of derivation.

## Rule 5 — Trust the live state more than the code's claimed state

A log line is what the runtime actually did. A trace through the source code is what you believe it did. When they disagree, **the log wins**. Mental models of multi-callback async UI code, lifecycle handlers, and partially-initialized state are wrong more often than logs are.

## Rule 6 — When diagnostics themselves do not change behaviour, you have a clean signal

Read-only diagnostic output (e.g. `Console.Error.WriteLine`, `print`, `log.debug`) is observably zero-risk for most UI and lifecycle bugs — no side effects, no allocations that matter, no thread reordering. If the symptom persists with logs in, you can compare runs cleanly. Do not conflate "added diagnostics" with "changed the system" — that is the whole point.

## Rule 7 — Remove diagnostics after the fix is verified, in the same commit cycle

Diagnostics are scaffolding. Once the root cause is committed, sweep the temporary log lines in the same commit cycle. Leaving them in pollutes future debugging — every new bug ends up co-located with stale tracing from an old one.

## Rule 8 — Announce launch parameters before a non-trivial run, verify artifact existence after

Before kicking off a non-trivial run that takes more than a few seconds (batch job, optimization stage, multi-hour compute, training run, simulation, benchmark, dataset rebuild, debugger session with custom config), announce the full parameter set in a single block — mode or profile, key configuration values, input source path, output destination, expected runtime or ETA — and pause for user correction if any parameter is ambiguous. Diagnostic and production runs use the same parameter set unless the user explicitly authorized a faster diagnostic mode; do not silently substitute a faster regime for the authorized one or invert the relationship by treating the diagnostic mode as the default.

After such a run, a completion notification, callback, exit-code-zero, or "task done" message is not by itself evidence the run succeeded. Verify the expected output artifact exists at the declared destination, check its success markers (file present, expected size, normal-completion log entry, exit status), and only then claim success. A run that produced no artifact at the declared path is `BLOCKED` or `REVISE`, regardless of how cleanly its process exited.

## Pattern in action

Abstracted from real incident loops:

1. **First speculative fix fails.** The user reports the symptom unchanged. Treat this as the Rule 1 trigger: do not re-roll on another guess.
2. **Add 3–5 orthogonal log lines** at suspected branch points: state-change handlers, lifecycle entries, completion callbacks, gate conditions. Same prefix shape, parseable by eye.
3. **The user reproduces the bug; logs are captured to the scratch file.** Read the log end-to-end and look for: a missing event, a doubled event, a large gap between two events, or a field value that disagrees with the mental model.
4. **The cause appears in the log** — usually one of:
   - a gate condition was different than code-reading suggested
   - a callback fired with stale state
   - an event fired twice from two different sources
   - an event never fired at all
   - geometry, bounds, or attachment state was wrong at the moment a downstream event tried to use it
5. **Fix the smallest thing that closes the gap.** When logging is right, a one-line change is typical.
6. **Re-run with diagnostics still in.** Verify the failure shape is gone in the same log file, then sweep the diagnostics in the next commit.

The pattern across cases: **log first, read the gap or the missing event, fix the smallest thing that closes it.** Never re-roll on guesses.

## Non-goals

- Not a substitute for `$qa-engineer` review gates — this is methodology for the diagnostic phase, not for verification or for owning the fix as an artifact.
- Not for design-stage decisions, performance budgets, or architectural reasoning.
- Not for visual-bug capture or frame-level analysis — use `$analyzing-video-bugs` (frame extraction and transition detection) and `$windows-gui-manual-testing` (broader visual verification including screen capture).

## Terms and abbreviations

- `Edit`: tool call that modifies a tracked source file. The discipline above forbids issuing one before the working theory is verified in a log.
- `repro`: reproduction; the user's act of running the failing case so the agent can collect runtime evidence.
- `scratch file`: a file under `.scratch/` (gitignored by repository convention) used for transient logs, frames, and probes.
- `gate condition`: the boolean expression guarding whether a code path executes; bugs frequently live in a gate that looked correct on paper but was wrong at runtime.
