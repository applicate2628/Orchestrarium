# Subagent Operating Model — Codex Addendum

Canonical shared core: [shared/references/subagent-operating-model.md](../shared/references/subagent-operating-model.md)

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This file keeps only Codex-specific runtime and repository concretization for the shared subagent operating model. Use the shared core for canonical blueprint, routing, role, and governance-model text.

### Native context reuse

Apply the shared **Context handoff economy** owner. Native role TOML files already reference AGENTS and the selected role instead of embedding the full corpus; preserve that thin overlay. Do not assume that an inherited skills catalog proves a loaded skill body, or that a new thread has the parent's full history. Use the supported invocation's actual context contract, supply missing instructions when uncertain, and send only changed task requirements on follow-up. This is dispatch guidance, not a new host setting or proof of token savings. Global/project automatic AGENTS concatenation remains a separate installation/loading compatibility question; never omit standalone project governance merely because a global file exists.

The review binding can explicitly select fresh context or a handoff of selected
task evidence; neither mode imports the parent conversation. See the owning
SDK binding contract for current supported modes and continuation limitations.

### Explicit Codex SDK review integration

The repository-local `--sdk-review-binding` opt-in uses the official Python Codex
App Server software development kit (SDK), not an ACP proxy or a new Agents
coordinator. Only an admitted external-reviewer invocation selects it; other roles
and invocations without the option retain their legacy paths. The same Host retains
authority. A binding file is nonauthorizing, the current containment path is
Windows-only, and this bridge selects an empty MCP scope. Installer-managed helper
files do not install dependencies or qualify execution. Current installed-bridge
qualification remains pending. Diagnostic recovery is implemented but not yet
native-qualified; earlier native observations cover an older source snapshot.
V3 SDK evidence keeps existing receiving/ledger owners and cannot close another run. See [the exact opt-in contract and limits](../docs/sdk-execution.md).

A Codex Host may separately use the existing Python SDK executor for an admitted
Claude API/cloud Worker with explicit file-tool authority. Its
`tool-restricted-workspace-write` provenance is not the Codex native
`workspace-write` sandbox. The exact provider/access route and Host permission
callback remain authoritative; the public Claude command-line route stays
prompt-only. This does not enable a subscription CLI worker or a default-route
change. See the shared guarantee distinction and SDK implementation boundary.

## Codex-specific runtime notes

- Mechanical-plan filesystem preflight is a repo-local check, not host containment. An explicitly observed exact root may be located on an ordinary mounted volume; native identity is rechecked across its ancestor chain. Detected descendant mounts and all links/junctions/reparse points remain refused. Python documents that [os.path.ismount](https://docs.python.org/3/library/os.path.html#os.path.ismount) cannot reliably detect same-filesystem bind mounts and also treats Linux btrfs subvolumes as mount points. No stronger mount-detection guarantee is claimed; caller authority and host restrictions remain independent.

The installed routing, recovery and role-resolution policy remains inline in [the Codex source addendum](../src.codex/AGENTS.codex.md#template-routing). Its ordered decision tree combines route shape and participants without adding first-match semantics. Shared quick-fix, primary-task continuity and physical lifecycle are already composed into the same instruction document. Main-conversation continuation saves recovery after each accepted stage; the additive Architect trigger for factual decisions, Architecture Decision Records (ADRs) or material alternatives is separate from the no-implementation research route, and Planner still requires an explicitly requested execution plan. This source consolidation adds no loader, read dependency or Lead activation and does not establish effective client-budget fit, actual loading or compaction behavior.

Apply the shared **Context handoff economy** owner. Do not assume that an inherited skills catalog proves a loaded skill body, or that a new thread has the parent's full history. Use the supported invocation's actual context contract, supply missing instructions when uncertain, and send only changed task requirements on follow-up. This is dispatch guidance, not a new host setting or proof of token savings. Global-backed project rendering requires the exact matching-policy checks documented in INSTALL.md; never omit standalone project governance merely because a global file exists.

- Codex native subagent dispatch is available when the current host exposes it. Admit those native lanes through the shared rolling lane-ready-set contract; do not assume sequential-only internal execution, and do not infer a numeric concurrency cap from an earlier refusal or another runtime.
- Ordinary discovery presents admissible choices and a default suggestion. The caller evaluates task fit, honors genuine current custom controls, and consciously selects and supplies both model and effort when deciding by task, including when choosing the suggestion. An omitted pair remains compatible and resolves to an explicit default pair; rationale is not automatically classified and higher effort remains caller judgment. Resolution checks the resulting tuple before the generic carrier; old-generation factory migration requires positive stock provenance and preserves noncontrol bytes. Direct bare `default` calls inherit provider/parent settings instead; policy-requiring callers use the selector. Role policy owns exact profile membership and separate special-corridor/explicit-profile rules; the installed `Native Astra task-dependent route` owns explicit-tuple and custom-pin conflict semantics. Claim an override only when the host explicitly supports it and returned actual runtime metadata confirms the effective model and effort; otherwise record `unspecified by runtime`. The same ordinary selector exposes explicit supervised `luna-high` and `luna-xhigh` only at the existing exploration/engineering producer task-role intersection; it retains the profession and independent gates. Admission requires an eligible task-role pair and exact task/role profile membership, followed by host filtering; ordinary tier/effort metadata is descriptive. Shared task-first economics defaults Luna mechanics to Extra high; exact profile admission, caller contracts and final review/critical/recovery membership remain binding. No public benchmark claim proves universal speed or coding superiority. Product Manager uses the same generic skill-only route when policy admits its planning pair; its recommendation does not grant user consent or expand accepted delivery scope.
- The Codex native-host choice is owned by `Native Astra task-dependent route` in [the existing Lead operating-model](../src.codex/skills/lead/operating-model.md#native-astra-task-dependent-route). The installed AGENTS native-dispatch kernel requires applicable procedures before selection, submission and receiving; reading them does not activate Lead or change Claude Agent/external routing. The shared **Task-first dispatch economics** owner governs current Sol 6.2, Astra 6.2, Terra 6.1 and Luna 6 selection; public benchmarks are not local runtime qualification. A genuine task-scoped user authorization may cover Astra High/Extra high for those admitted tasks, including necessary repeated attempts within unchanged scope, route, allowed efforts and spending bounds; do not ask again for each covered attempt. Recheck scope, revocation and limits before dispatch; a material change needs renewed authorization. Every model Max still needs separate exact-attempt approval, including Astra Max. Other Astra efforts retain exact-launch approval. Routing approval, profile selection and copied flags do not create launch or spending authority; separate assistant, provider, subscription, external-review and platform permissions still apply. Native requested/resolved controls remain separate from observed execution; host rejection never implies fallback.
- Native Goal recovery consumes shared **Goal resumption and hold currency** before selecting a continuation or changing Goal state. Read current state through the actual available host API and verify the latest applicable user enable/resume for the same admitted task/scope, including a new Goal after no-Goal work; an old active snapshot or assistant recovery note is not authority. Keep real current pauses and separate approvals; the shared rule supplies no tool, auto-enable permission or provider-native guarantee.
- Consultant config lives in `.agents/.agents-mode.yaml`; routing reads normalize effective values in memory, with persistence limited to authorized install/configuration writes under the [external dispatch owner](../src.codex/skills/lead/external-dispatch.md#canonical-config).
- Codex may extend the shared `agents-mode` schema with `externalClaudeProfile` to select the Claude CLI execution profile (`sonnet-high`, `opus-xhigh` shipped default, `opus-max` max-depth escalation, or `fable-xhigh` current flagship-family best-effort tier) when `externalProvider` resolves to Claude.
- `externalProvider: auto` resolves by lane type through the active named production priority profile rather than by Codex-line default. Shipped production `auto` uses `codex | claude` only. Explicit Kimi selection is limited to policy-admitted read-only work or engineering whose task eligibility and assigned profession map to `external-worker`. A selected capability file supplies only caller-scoped tools under that existing mutation class and role mapping; it grants neither authority nor a sandbox. Grok remains unavailable, and removed Gemini/Qwen scalar values fail closed with `E_EXTERNAL_PROVIDER_REMOVED`.

## Codex-side repository concretization

- Admitted adjacent-defect proposals use the configured bug-registry path when the repository defines one, under `qa-engineer`'s bug-admission contract. Typed holds retain their actual cause, required remainder, owner and next action under the shared core.
- Task-memory root, recovery entry point, active-item directory, and archive location remain repository-defined in this Codex-side reference model. The [Lead work-cycle owner](../src.codex/skills/lead/SKILL.md#work-cycle-ownership-recipe) selects Root recording for native and already-admitted direct external owner-equivalent execution, or actual supported wrapper recording on Root's behalf when it executes. That dispatch step resolves finite current demand before the first writer/scheduling and carries C through terminal and receiving; the route-neutral operating guide adds no second procedure. Direct external guarantees remain with the [external-dispatch owner](../src.codex/skills/lead/external-dispatch.md). The Lead owner also performs strict selected-item `--obligations-json` receipt/status recovery and actual continuation/close and original-target readiness. Wrapper-only IDs/readback apply only to actual wrapper execution; external outcomes remain nonauthorizing and separately assigned Root/internal acceptance or independent closers remain required. This includes logical-phase versus supported-host release/accounting and retention of actual runner identities/state before formatting/truncation; this addendum owns no second completion or teardown algorithm.
- Bug preservation and separate fixed-bug administration use the [shared lifecycle owner contract](../shared/references/work-items-root-contract.md) and its operator runbook; no provider-specific status or parent-location rule is added.
- Periodic controls stay pack-local in [periodic-control-matrix.md](periodic-control-matrix.md).
- Older Codex examples may still show `Gate: PASS | REVISE | BLOCKED | RETURN(role)`; the typed `BLOCKED[:class]` form from the shared core remains compatible.

## Shared core now owns

- Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition
- Shared review/gate semantics, periodic-controls model, rolling lane-ready admission, parallel-work guidance, and generic task-memory expectations
- The generic lead memo and final wording

## Global-backed project installation

The Codex installer may omit the duplicate managed project policy only after an
exact match with the selected native global managed block. A nonempty override
hides the base; CODEX_HOME selects the global root. Failure to establish the match
keeps the full local policy. `--standalone-instructions` explicitly keeps the
complete project copy. User additions stay outside the managed replacement.
New sessions receive the updated native instruction snapshot; running sessions
are not retroactively rewritten. Global uninstall warns rather than inventing a
complete dependent-project census. See INSTALL.md for the supported lifecycle.

## Terms and Abbreviations

- SDK: Software Development Kit.
- MCP: Model Context Protocol.
- ACP: Agent Client Protocol.
- Host: existing invoking orchestration session.
- V3: version-three SDK provider-result envelope.

- Luna/High and Luna/Extra high (`xhigh`): explicit Luna model profiles at their model-local reasoning efforts; neither adds role authority.
- V1: the existing named mechanical execution and facts contract.
- TOML: the configuration format used by native role definitions.
- Other governance terms follow the [shared glossary](../shared/references/spine/governance-glossary.md).

## Scratch-independent recovery

Apply the [shared artifact owner](../shared/references/repository-source-hygiene.md#scratch-independent-recovery). Important edits, unpublished commits and required evidence need verified custody outside disposable storage before pause or handoff; a worktree is insufficient if its Git common directory or object alternates still depend on scratch. This adds no provider-specific storage owner or publication permission.

## Review-loop receiving

Review-loop receiving uses the shared review-loop methodology and the existing Python state owner. A completed same-artifact REVISE may receive an owner-qualified recorded-equivalent closure without overwriting the original result; an empty original scout reconciliation may receive explicit later dispositions through version-2 amendment metadata. Keep original provenance and independent acceptance requirements; the helper never launches reviewers or invents PASS.
