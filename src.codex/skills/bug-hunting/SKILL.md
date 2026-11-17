---
name: bug-hunting
description: "Diagnose bugs with hypothesis-appropriate evidence, then verify the scoped fix."
---

# Bug Hunting

## Core discipline

**Investigate before guessing; choose evidence that can distinguish the hypotheses.** Identify the violated invariant, its owner, the observed symptom and a falsifying case. Reuse current trustworthy evidence before collecting more. More logs are not automatically more certainty.

## Rule 0 - Establish the cause, then verify the fix

- **Before the fix:** connect the hypothesis to inspectable evidence. Static evidence and deterministic unit tests can establish a deterministic code defect; runtime or integration evidence is needed when the claim depends on actual scheduling, environment, native behavior or external state. Code inspection is not a substitute for those runtime claims, and a timestamped log is not a prerequisite for every source edit.
- **After the fix:** reproduce the relevant failure before the change where feasible, verify the corrected behavior and neighboring cases, and distinguish implemented code from executed acceptance. When required acceptance evidence is unavailable, report that affected criterion as "implemented, not yet verified" and name the next check. Passing scoped checks is not a guarantee of perfect correctness or whole-system readiness.
- External advice, including official documentation and another model's answer, is a candidate explanation. Check its applicability to the current code and scenario; it does not replace evidence or authorize execution.
- Honor an explicit user requirement to collect particular evidence before a particular change. Otherwise select the smallest sufficient method rather than adding an automatic logging gate.

## Rule 1 - A failed fix changes the investigation, not all work

If a fix leaves the symptom unchanged, do not stack another speculative patch. Reconcile the attempted change with the failing case and choose a discriminating check: focused source/data-flow analysis, a deterministic regression test, targeted instrumentation or a native reproduction as appropriate.

- **Second-cross-break stop:** If a second fix in the same session breaks a previously working neighbor, pause speculative changes to the affected mechanism. Diagnose its owner, sibling modes and shared-state/lifecycle interactions before the next behavior change; retain safe diagnostic edits and continue independent authorized work. Expand the pause only when evidence shows a shared dependency or safety risk. Preserve user data, required permissions and mandatory safety checks.

## Rule 2 - Pick the smallest signal that distinguishes live hypotheses

For a timing or state-observation hypothesis, log a few orthogonal events with timestamp, short tag and relevant state values (`inFlight`, `attached`, `bounds`, `session`). Keep events compact and correlate them to the actual run, source and task. Do not dump unrelated state or secrets.

Provider-neutral example:

```
[TAG hh:mm:ss.fff] EVENT_NAME field1=value1 field2=value2 field3=value3
```

Look for a missing event, duplicate entry, an unexpected interval or a state value inconsistent with the hypothesis. Absence is evidence only if the observation covered that event and its collection completed. Treat apparently similar UI variants as distinct paths until their relevant behavior is established.

- When N symptoms or failing cases are reported, keep N independent root hypotheses and choose evidence for each case. Collapse them to one common root only when one observed mechanism explains every case; shared timing, location or correlation is not proof.

## Rule 3 - Retain only the evidence the investigation needs

Reuse complete evidence already retained by the execution tool or test report. When a run can lose necessary output, capture it in the authorized ignored scratch workspace, such as `.scratch/<topic>.log`; preserve unique load-bearing evidence before overwriting it. A file is not mandatory for a simple check whose complete result is already retained. Follow the project's storage, privacy and cleanup rules; scratch storage is not a durable source of truth.

PowerShell capture example:

```powershell
Start-Process -RedirectStandardError .scratch/bug.log <command>
```

POSIX capture example:

```bash
<command> 2> .scratch/bug.log
```

## Rule 4 - Use frame evidence for visual transitions

For animation, timing or sequence bugs, inspect the smallest relevant frame set rather than relying on an impression of a video. Use `$analyzing-video-bugs` for frame extraction and `$windows-gui-manual-testing` for capture, theme/state context and structural-versus-cosmetic verification. Use a specific user-provided frame pointer directly when available.

## Rule 5 - Resolve conflicting observations

A log records the instrumented path, not necessarily the complete system. When source analysis and a trace disagree, check source/version identity, execution path, capture completeness, buffering, correlation and observer effects. Resolve the contradiction rather than automatically trusting either a mental model or a log line. Do not infer successful execution from missing output or exit status alone.

## Rule 6 - Diagnostics can change behavior

Logging can alter timing, allocation, locks, blocking I/O and thread scheduling; evaluating diagnostic arguments can itself have side effects. It can expose secrets or affect the failure being investigated. Use the least intrusive sufficient signal, avoid sensitive values, and compare instrumented versus normal behavior when relevant. If instrumentation hides or changes the symptom, record that limitation and select a safer signal or controlled test; do not claim a clean reproduction merely because the instrumented run passes.

## Rule 7 - Remove temporary diagnostics without losing verification

Remove temporary diagnostic code in the same change cycle once its evidence has served the investigation, unless retained observability is an intentional reviewed requirement. Preserve the necessary result in the existing task/verification artifact. Re-run the affected regression with diagnostics removed when removal can change behavior; verify the delivered configuration, not just the instrumented one.

## Rule 8 - Make runs and outcomes explicit

For a non-trivial run, state the relevant mode, inputs, outputs and expected scope before starting. Ask only when an unresolved parameter changes correctness, cost, permissions or safety. Reuse an already authorized run plan; do not add a new confirmation for routine unchanged checks. Distinguish a bounded diagnostic case from production acceptance and do not silently substitute one for the other. Model, quota and other required approvals remain in force.

Check the required outcome after the run. If an output artifact is required, verify its existence, content and success markers at the declared destination; a completion message or exit zero alone is insufficient. A test with no required output artifact needs its actual test result, not an invented file. Missing required evidence blocks the affected claim or dependent operation, not independent authorized work.

## Pattern in action

1. Identify the invariant and competing explanations; record the observed failure.
2. Choose the smallest discriminating evidence. A deterministic branch bug may need a focused test; an async lifecycle race may need controlled scheduling and targeted event capture.
3. Inspect the result, including missing coverage and observer effects. Reject explanations contradicted by evidence.
4. Fix the owning mechanism with the smallest adequate change; preserve unrelated behavior and user state.
5. Run the regression and relevant neighboring checks. Remove temporary diagnostics and verify the delivered behavior where their removal matters.
6. Report what changed, what was actually verified and any scoped remainder. Continue independent authorized work.

## Non-goals

- Not a substitute for `$qa-engineer` acceptance or independent review.
- Not permission to run models, spend quota, change protected settings or bypass ownership checks.
- Not a replacement for design decisions or the specialized visual-evidence skills.

## Terms and abbreviations

- `Edit`: a tool action changing source; evidence requirements follow the proposed change and its claims, not the tool name.
- `repro`: a controlled reproduction used to distinguish explanations or verify the fix.
- `scratch file`: ignored transient evidence stored according to the project's authorized workspace policy.
- `gate condition`: a predicate controlling a code path; test the actual relevant inputs instead of assuming its outcome.
