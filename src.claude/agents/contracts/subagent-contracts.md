# Subagent Contracts

Handoff templates and response format for lead-to-specialist delegation.

## Execution mechanism

Every specialist invocation MUST use the **Agent tool** with the matching `subagent_type` parameter, except provider-backed external adapter routes. `$external-worker` and `$external-reviewer` are direct external launch routes, not internal specialist-agent hosts. The handoff template below becomes the agent's `prompt` for ordinary specialists. The orchestrator (the main conversation, as Lead) MUST NOT role-play specialists inline — each role runs in an isolated agent context.

## External dispatch contract

Use this contract when `subagent_type` is `external-worker` or `external-reviewer`.

- These roles are routing adapters, not new business professions.
- The `Assigned role` field names the internal role being replaced for provenance.
- Read and normalize `.claude/.agents-mode.yaml` first. Honor `parallelMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalModelMode`, `externalCodexProfile`, and advisory/review-only `reserve` profile entries when they are present. Drop retired canonical keys during normalization. On the Claude line, do not write `externalClaudeProfile` into the canonical `.agents-mode.yaml` file; it remains Codex-line only.
- If local `.claude/.agents-mode.yaml` is missing, read local legacy `.claude/.agents-mode` as compatibility input only; if both local files are missing, fall back through pack-local global `~/.claude/.agents-mode.yaml`, pack-local global legacy `~/.claude/.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml` (alongside `~/.claude.json`), before applying built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file.
- Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.
- There is no generic external adapter for owner roles such as `$product-manager` or `$lead`. If a request lands in one of those lanes, fail fast with an unsupported-route explanation instead of probing providers.
- Do not silently fall back to an internal specialist if the external CLI is unavailable; the adapter is disabled and the orchestrator may reroute.
- Do not satisfy `$external-worker` or `$external-reviewer` by spawning an internal agent/helper/subagent host that merely relays to another CLI. If the current runtime cannot launch the selected external provider directly, the route is unavailable.
- **Subagent no-spawn-and-wait rule.** A dispatched subagent is NOT re-invoked when a background child it launched (a `run_in_background` shell-out or a background agent) finishes — background-completion notifications go only to the MAIN orchestrating loop. So a subagent must never launch a background child and end its turn "waiting for the notification"; the child strands and the subagent returns an empty result (the recurring `external`-mode consultant role-confusion). A subagent has two compliant paths: complete the work synchronously in-turn (a single blocking shell-out it parses before returning), or return a result telling the orchestrating runtime to own the long-running/background step and feed the outcome back. The orchestrating runtime — which receives background-completion notifications — owns any launch that cannot finish inside one subagent turn.
- `external-worker` covers the full worker-side lane.
- `external-reviewer` covers review and QA-side work.
- `externalProvider: auto` resolves by the active named production priority profile instead of a host-line default; shipped `auto` uses the Codex/Claude pair only. Gemini/Qwen stay `WEAK MODEL / NOT RECOMMENDED` example-only paths; Kimi/Grok are explicit-only read-only routes requiring the pre-dispatch policy and independent verification, never shipped production `auto`.
- `parallelMode` is the general rule for whether independent helper lanes should be parallelized by judgment at all. External fan-out follows that rule instead of defining a separate global concurrency model.
- Independent external adapters may run in parallel when their scopes are disjoint, `parallelMode` permits ordinary parallel fan-out, and provider runtimes support concurrent non-interactive execution. If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- Same-provider reuse is allowed for independent external fan-out. Do not impose a one-instance-per-provider cap when multiple admitted artifacts or disjoint slices need the same helper/provider combination.
- `externalOpinionCounts` still governs distinct-provider opinion requirements for one lane; it does not replace the general `parallelMode` rule or limit brigade-style parallel launches across different independent lanes or slices.
- When the routing decision is "launch a bounded set of external helpers together", prefer `/agents-external-brigade` so the brigade has one explicit plan, one ownership table, and one aggregated result surface.

For external adapters, include the provenance header from `external-dispatch.md` in the returned artifact.

## Handoff template

```text
Role:
Goal:
Approved inputs:
- <accepted artifact or fact>
Allowed tools (affirmatively name repo-relevant MCP servers/skills, or state "runtime default surface"):
- <allowed tool, MCP server, skill, or "runtime default surface">
Scope:
- <allowed area>
Out of scope:
- <forbidden area>
Allowed change surface:
- <approved files, modules, or seams>
Must-not-break surfaces:
- <nearby but unrelated areas that need isolation or smoke coverage>
Diff-invisible invariants:
- <behavior or contract that must remain true although the diff may not expose it>
Named regression guard:
- <test/probe plus expected result that falsifies preservation>
Dead/superseded code disposition:
- deleted <files/symbols/paths> | none (probe: <named search/reachability/test>)
Evidence discipline:
- <cite each decision-driving claim with an in-repo file:line, installed-dependency surface check, versioned official docs/upstream source URL, or target-environment smoke test preserved under .scratch/; otherwise label it ASSUMPTION (UNVERIFIED) with the resolving step; never use "should work", "should be fine", "probably", "likely", "I think", "based on training data", "in general", or "this pattern usually works" as a correctness-driver>
Defect-class inventory:
- <when one instance was cited: every participant to audit—parallel arms, cell/data shapes, return paths, and read-sites; otherwise "not-triggered">
Constraints:
- <constraint>
Expected artifact:
- <one artifact>
Acceptance criteria:
- <criterion>
Gate to next stage:
- <what must be proven>
```

Before dispatch, fill `Diff-invisible invariants`, `Named regression guard`, and `Dead/superseded code disposition`; `none` is valid only with a one-line reason. When a change supersedes a mechanism, `none` is invalid. An implementation or review handoff with any field omitted is incomplete.

`Approved inputs` identify the producing run's declared scope and accepted artifact revision when available; no new handoff field is required. Evaluate authored claims and review verdicts against the producing run's declared scope and accepted baseline: later independently owned lane deltas are reviewed in their own lane and do not retroactively falsify the earlier artifact; an actual material revision of the accepted upstream artifact still invalidates dependent `PASS` states and triggers dependent re-review.

Receiving-side echo: the returned artifact MUST (a) report the Named regression guard's actual result (expected vs observed), (b) answer each Diff-invisible invariant as verified or ASSUMPTION (UNVERIFIED), (c) report the Dead/superseded code disposition result and its named probe, and (d) when the dispatch cited a defect class, include the class audit — every enumerated participant classified fixed / not-affected. An artifact missing the echo fails the mechanical acceptance gate.

**Class-completeness trigger (mandatory):** when a reviewer, bot, or test cites one instance of a defect class, the dispatch prompt MUST direct the recipient to enumerate every participant of that class, classify each one, and fix every confirmed instance. A prompt scoped only to the named line is invalid.

**Object-axis trigger (mandatory for C1-based clean verdicts, PRE-verdict).** The class-completeness
trigger above fires AFTER a finding: "you found one — where are its siblings?" This one fires BEFORE
a clean/verified verdict that relies on a C1 single-owner-invariant assessment: "you are about to
call this clean — did you aim at the right object?" A lens can be present, sharp and
productive and still miss an entire class because it was never aimed at a second axis: a real audit
ran the split-ownership lens, found "one conceptual decision has four independent owners", and never
found the same defect in policy VALUES — it asked who owns the decision, never who owns the number.
The rule for the number already existed and was not applied.

When a clean/verified verdict relies on a C1 (single-owner-invariant) assessment, the dispatch MUST
require, and the returned artifact MUST carry, an object-axis record — one row per C1 assessment used
to support that verdict:

`| lens | primary object examined | adjacent object classes re-aimed at | decision facts proved (not a proxy) | result + evidence |`

For such a C1-reliant verdict, an absent or empty-celled record fails mechanical acceptance exactly
like the receiving-side echo; a grouped `N/A` needs a bounded one-phrase reason, never silence.
Dispatches and verdicts that do not rely on a C1 assessment owe no object-axis record. Define the adjacent axis
FUNCTIONALLY, never as a noun checklist (a closed list of nouns is the same blind lens one level
down): the representations a legitimate policy change must update together; objects under ANOTHER
owner that the operation touches; and the facts the decision actually used, not a proxy for them
("same object" is not "same state" unless identity IS the predicate).

Admission predicate for a value candidate — apply BEFORE searching, so this never becomes a literal
hunt: name (a) the policy owner who would legitimately change it, (b) the change that would trigger
it, (c) the consumers or boundary representations that MUST co-vary, and (d) the one place they would
look. A world fact, protocol constant, or algorithm-local literal fails (b) or (c) and is excluded —
that exemption is deliberate. A literal is a discovery seed, never a finding. Same-owner candidates
aggregate into ONE finding. Without co-variation it is not a single-owner defect at all — it may be
plain hardcoding, which is a different rule and a different fix.


## Artifact gate

A lead MUST NOT delegate recovery-tracked or multi-stage work until the work-item folder contains a verified `brief.md` and full `status.md`.

### Workflow economy projection

Apply the binding shared **Workflow economy (binding)** rule. This contract projects the one-canonical-artifact/concise-root-ledger boundary and forbids progress-only artifacts or progress-only `REVISE`; it does not add a second provider-specific review policy.

- `brief.md` must have explicit scope, out-of-scope, acceptance criteria, required roles, and critical risks with owners.
- `status.md` must follow the format below and be updated after every stage transition, agent launch, or interruption, including any open obligations that still block closeout.
- If either artifact is missing, stale, or incomplete, the lead restores only the lead-owned task-memory state from persisted accepted artifacts BEFORE delegating any specialist role. Do not reconstruct missing specialist artifacts or factual findings from chat memory.
- For `quick-fix`, the minimal status below is the handoff and must exist before implementer dispatch and the first repository mutation; no `brief.md` or other heavy prelude artifact is required.

### Quick-fix minimal status.md

Create `work-items/active/<slug>/status.md` with only these ordinary lifecycle fields and recovery facts:

```markdown
---
template: quick-fix
status: active
started: <YYYY-MM-DD HH:MM>
updated: <YYYY-MM-DD HH:MM>
---

- **Task**: <admitted objective>
- **Current step**: <current execution step>
- **Last result**: <last completed step or admission result>
- **Next action**: <next concrete action>
```

An admitted `quick-fix` does not add `roadmap.md`, `brief.md`, Research, Design, Plan, consultant, pre-implementation review, or a report before its first mutation. If it is re-classified, keep this work-item and enrich its recovery state to the full format below instead of creating a late unrelated item. After delivery, apply the normal immediate closure/archive rule.

### status.md format

```markdown
---
template: <template name>
orchestration: light | full-lead
started: <YYYY-MM-DD>
updated: <YYYY-MM-DD HH:MM>
---

## Current state

- **Primary task**: <one active objective, e.g. "full-impact review of current change set">
- **Primary task status**: <active | side-interrupted | parked | closed>
- **Interruption marker**: <none | INTERRUPTED(no-artifact)>
- **Stage**: <current stage name or number>
- **Main conv role**: <what main conversation is doing: orchestrating | waiting for agents | reviewing artifact | idle>
- **Last accepted artifact**: <filename or "none">
- **Open obligations before closeout**: <none | remaining required work still inside admitted scope>
- **Epic**: <parent epic slug, or none> — present only when this work-item belongs to an epic; a single bare `Epic: <slug>` line is the join key the epic roll-up reads (see the lead skill `## Epics`)
- **Depends-on**: <comma-separated work-item slugs, or none> — other work-items this one needs completed first; a single bare `Depends-on: <slug>, <slug>` line is what the derivation reads. A standing, planned inter-work-item dependency edge (distinct from the runtime `BLOCKED:*` gate verdicts). Targets are work-items only, resolved across physical `active/`, `archive/YYYY-MM/`, and `backlog/` locations (a backlog match is existence, not done). A target that resolves nowhere is folded into `blocked-by`, never treated as satisfied. `/agents-status` derives `blocked-by` (open targets) and the ready-set from these lines (see the lead skill `## Dependencies`)
- **Priority**: <high | medium | low, or none> — scheduling urgency set by `$product-manager` at admission; distinct from bug/perf SEVERITY (defect impact). A low-severity bug can still be high-priority.

## Active agents

| Agent | Role | Model/effort | Status | Launched |
| --- | --- | --- | --- | --- |
| <description> | <role> | <model/profile + effort — one-line complexity rationale> | running | <HH:MM> |

## Completed agents

| Agent | Role | Result | Artifact |
| --- | --- | --- | --- |
| <description> | <role> | PASS/REVISE/BLOCKED | <filename> |

## REVISE loop

| Field | Value |
| --- | --- |
| **Stage** | <stage name where REVISE occurred> |
| **Iteration** | <1-3, or "escalated"> |
| **Gate role** | <qa-engineer, security-reviewer, etc.> |
| **Last finding summary** | <one-line summary of what the gate found> |
| **Owner of next action** | <implementer role that must fix, or "user" if escalated> |

## Next action

<What happens next: which agent to launch, what artifact to review, or what decision to make.>
```

Legacy handling: older `status.md` files may carry `orchestrator: main | lead`. Read `main` as `orchestration: light` and `lead` as `orchestration: full-lead`; do not rewrite old files in bulk. The orchestrator is ALWAYS the main conversation (holding the Lead role) — the retired field encoded orchestration weight, not a different owner, which is why it is renamed. New/updated files write `orchestration:`.

The REVISE loop section is optional — include it only when a stage has returned REVISE and the loop is active. Remove it when the loop resolves (PASS or escalation).

### agent-runs.jsonl format

Only the root main conversation holding Lead writes `agent-runs.jsonl`: it records each launch and, after receiving and accepting the assigned artifact and evidence, its terminal outcome. A main-owned validated helper or wrapper may perform that write on the root's behalf.

The ledger is machine-readable execution state; `status.md` remains the human-readable recovery summary. A `PASS` in `status.md` is not accepted unless the corresponding ledger event has `gate: "PASS"`, `status: "completed"`, an artifact path, and at least one evidence entry.

Minimum required fields are defined by `shared/schemas/agent-runs.schema.json`: `schemaVersion`, `runId`, `workItem`, `role`, `executionRole`, `status`, `gate`, `scope`, `startedAt`, and `updatedAt`.

When `scripts/agent-run-ledger.*` or an installed equivalent is available, prefer its `append` command so the event is validated and rolled back on failure. Use its `init` command for one-time migration of legacy work items with missing status sections or ledger files. Manual JSONL append is acceptable only when no helper is available.

Before closeout, run `scripts/validate-work-item-state.* --work-item <path>` or the installed equivalent when the repository exposes one. Before broad closeout, interruption recovery, or publication review, run `scripts/check-work-items-state.* --root <repo>` or the installed equivalent to scan all active work items. Closeout is blocked while the ledger contains running agents, duplicate run IDs, missing artifacts for `PASS`, `PASS` without evidence, stale running agents, or inconsistent `BLOCKED` / `REVISE` status.

No-artifact interruption rule:
- A handoff interrupt or worker stall without an artifact does not count as a substantive REVISE artifact.
- Set `Primary task status: side-interrupted` and `Interruption marker: INTERRUPTED(no-artifact)` in `status.md` for orchestrator bookkeeping.
- Keep the stage open, and either rerun the same role with a tighter slice or route to the proper factual role.
- The lead must not synthesize the missing artifact or replace missing factual work inline.
- If the interrupted stage belongs to a full-impact review or verification pass, keep that review as the primary task until a review artifact is emitted or the user explicitly parks/cancels it.

## Response format

```text
1. Summary
2. Artifact
3. Risks / Unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)
```

- When a role makes a decision, it should clearly distinguish confirmed facts, assumptions, and judgment.
- If the main gap is missing evidence, recommend the appropriate factual role instead of escalating into opinion.
- `$consultant` replaces the Gate line with `5. Advisory status: NON-BLOCKING` and appends `6. Continuation prompt: <ready-to-send second prompt that begins with a direct imperative to continue and names the next concrete action>`.
- Consultant mode `external` stays external-only. If external execution is unavailable, batch closure stays open and the lead escalates to the user instead of downgrading to an internal-only run.
- `external-worker` and `external-reviewer` keep the standard gate line, but their artifact must also carry the external provenance header from `external-dispatch.md`.

### BLOCKED classification

When returning BLOCKED, specify the class:

| Class | Meaning | Orchestrator action |
| --- | --- | --- |
| `BLOCKED:dependency` | Cannot proceed — missing tool, environment, access, or information that no current agent can provide | Present to user for resolution |
| `BLOCKED:prerequisite` | Discovered adjacent work that must complete first (e.g., broken adjacent module, missing migration) | File in `work-items/bugs/` → user decides priority → resume when resolved |

If no class is specified, treat as `BLOCKED:dependency` (conservative default).

## Interaction rules

- The orchestrating owner controls routing: `$product-manager` for roadmap, `$lead` for delivery.
- Only the root main conversation holding Lead dispatches downstream roles and writes work-item lifecycle state.
- A specialist completes one profession, artifact, and gate; it returns evidence plus an optional non-binding recommended next role to the root, then stops.
- A specialist never adopts Lead, launches a peer or downstream stage, advances the pipeline, or writes `agent-runs.jsonl`.
- The root may directly launch a configured external wrapper; no provider or leaf may recursively launch another wrapper.
- Subagents produce accepted artifacts for the next role — they do not assign work to peers directly.
- If blocked by missing evidence, route back to the orchestrating owner for factual clarification.
- Reviewers report findings and gate outcomes; they do not manage implementation.
- When an upstream artifact is insufficient, return `REVISE` or `BLOCKED` instead of silently redefining the contract.

## Test ownership boundary

| Test type | Owner | When |
| --- | --- | --- |
| Unit tests for new/changed code | Implementer | Written as part of the implementation artifact |
| Regression tests for existing behavior | QA engineer | Written during verification if missing |
| Integration / end-to-end tests | QA engineer | Written or updated during verification |
| Contract-change test updates | Implementer | When QA classifies a failure as `contract-change` — the implementer who changed the behavior updates the tests |

If the plan specifies a different test ownership split, follow the plan. This table is the default when no plan-level override exists.

## Session persistence

An active work-item is the current task's `work-items/active/<slug>/` directory. With one, a specialist writes only its canonical task artifact; the root records the concise lane result and provenance in `agent-runs.jsonl`, with no `.reports/` or `.plans/` duplicate. Trivial work writes nothing. A meaningful standalone result with no active work-item MAY use one `.reports/YYYY-MM/` summary; an explicitly requested standalone plan MAY use one `.plans/YYYY-MM/` snapshot. See `AGENTS.md` § "Session persistence rule".

## Structured completion report

For substantial tasks, prefer a structured closeout in the final summary:

- **Changed:** what was modified and why
- **Verified:** what was tested or checked, with evidence
- **Not verified:** what was not checked and why
- **Still open:** remaining required work to satisfy the current request, or `none`
- **Risks / follow-ups:** residual risks, deferred work, or known limitations

This is a recommended format for user-facing task completion, not a mandatory gate artifact. For pipeline handoffs, use the shared response format above.

## Gate questions

Ask these before advancing:

1. Is the artifact complete for its stage?
2. Is anything still assumed but unstated?
3. Did the stage stay within its role boundaries?
4. Are the allowed change surface and must-not-break surfaces explicit enough?
5. Is the next stage receiving only the context it truly needs?
6. Is an independent reviewer or human gate still required?
7. Is the blast radius still inside the approved change surface?
8. Is any admitted-scope obligation still open even though one sub-batch is finished?

## Terms and Abbreviations

- `agent-run-ledger.*`: helper script family that initializes legacy work-item ledger files and appends validated `agent-runs.jsonl` events.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `artifact`: concrete work product such as a memo, plan, patch, review, or closure note.
- `BLOCKED`: workflow state for a real missing dependency, prerequisite, or unavailable route.
- `CLI`: Command-Line Interface; a provider or tool invoked from a shell.
- `evidence`: concrete verification data such as a command, artifact path, review result, log summary, or observed output supporting a gate.
- `gate`: acceptance checkpoint that verifies whether an artifact may move forward.
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only execution events.
- `ledger`: append-only record of agent runs, gates, artifacts, and evidence for a work item.
- `PASS`: workflow state meaning the scoped artifact passed the relevant gate.
- `QA`: Quality Assurance; verification work for tests, regressions, and acceptance criteria.
- `REVISE`: workflow state meaning the artifact must return to the same role for bounded correction.
- `status.md`: human-readable recovery summary for the active work item.
