# Version 1 routing: operator and integration guide

[Scope](#1-scope) · [Astra examples](#2-astra-examples) · [Worker handoff](#3-worker-handoff) · [Installation acceptance](#4-installation-acceptance) · [Terms](#5-terms)

## 1. Scope

These are **source-checkout examples** for two optional selectors, not a new
scheduler and not evidence of an installed-provider acceptance run. Run the
commands from the Orchestrarium checkout root. The examples invoke only a pure
selector and do not contact a provider or consume model quota.

The owning contracts are [Astra routing](../src.codex/skills/astra-routing/SKILL.md)
and [Lead worker routing](../src.codex/skills/lead-worker-routing/SKILL.md).
Use those contracts for supported fields and failure handling; this guide does
not introduce another ranking policy.

No example changes native roles, operator defaults, credentials, or admission.
The legacy `apex-max` profile retains its Sol binding; selecting Astra explicitly
does not migrate it. The legacy Terra-medium archivist is also unchanged.
Luna remains in its separate exact mechanical execution contract.

## 2. Astra examples

The inventory and evidence labels below are **synthetic** parser examples, not
observations of the reader's account. In real work the caller supplies verified
inventory and retains the underlying route and effort evidence. Never manufacture
those observations to turn an unavailable route into a selected one.

A mathematical task with admitted quality evidence starts at `medium`:

<!-- selector-example:quality-medium -->
```text
python src.codex/skills/astra-routing/scripts/resolve.py --task-class mathematical-research --available-model gpt-6-astra --route-evidence mathematics-quality-floor
```

Expected: exit `0`, `status = selected`, `effort = medium`, and
`requiresAdapterAdmission = true`. Both `executionAuthorized` and `authorizing`
remain false. This output is a candidate selection, not permission to launch.

For a complete-route cost comparison, one micro-US dollar is one millionth of a
US dollar. The following synthetic `1` and `2` amounts are deliberately not a
price estimate for real model work. The measured effort must match the selected
profile and both routes must share a task cohort and acceptance/accounting basis.

<!-- selector-example:measured-medium -->
```text
python src.codex/skills/astra-routing/scripts/resolve.py --task-class mathematical-research --available-model gpt-6-astra --route-evidence measured-cost-to-pass --astra-cost-microusd 1 --legacy-cost-microusd 2 --measured-effort medium
```

Expected: exit `0`, selected `medium`, with `costComparison.astraEffort = medium`.
The caller retains every model/effort pair in the comparison route and includes
failed attempts, repeated context, tools, independent review, and rework once.
Cash, subscription credits, and time are not silently interchangeable.

A measurement for medium cannot justify selecting high, even with separate
high-effort evidence:

<!-- selector-example:effort-mismatch -->
```text
python src.codex/skills/astra-routing/scripts/resolve.py --task-class mathematical-research --available-model gpt-6-astra --route-evidence measured-cost-to-pass --astra-cost-microusd 1 --legacy-cost-microusd 2 --measured-effort medium --effort high --effort-evidence measured-high-gain
```

Expected: exit `2`, `E_ASTRA_V1_ECONOMICS_EFFORT_MISMATCH`, no model launch flags.
Correct the evidence or selected profile; do not reinterpret denial as fallback.

The operator floor also cannot be bypassed with a downshift label:

<!-- selector-example:below-floor -->
```text
python src.codex/skills/astra-routing/scripts/resolve.py --task-class mathematical-research --available-model gpt-6-astra --route-evidence mathematics-quality-floor --effort low --effort-evidence migration-evaluation
```

Expected: exit `2`, `E_ASTRA_V1_EFFORT_BELOW_MINIMUM`, no launch flags.
Recovery may use medium only under its separately admitted downshift evidence;
maximum effort still needs explicit approval for that run. A measured gain may
justify starting higher without first paying for an unnecessary lower attempt.

## 3. Worker handoff

The general selector's only command-line entrypoint is
`src.codex/skills/lead-worker-routing/scripts/resolve.py --request-file <path>`;
`_resolver_base.py` is private, not a second entrypoint. Its request must bind
role, scope, capability, tools, mutation ceiling, artifact, gate, policy identity,
and the explicit candidate order.

A selected general candidate is not an Astra evidence check. When that candidate
is Astra, retain its separate route/effort decision and any required maximum-effort
approval before adapter admission. Do not confuse the worker request fingerprint
with a signature or authenticated evidence. Native workers remain host-bound.

The approved adapter revalidates actual model identity, supported effort, current
availability, executable, credentials, tools and sandbox before launch. It owns
file-based prompt delivery and the terminal receipt. A stronger author cannot
absorb its own independent reviewer. Unavailable Grok and policy-bound Kimi do
not acquire additional rights through this selector.

## 4. Installation acceptance

The existence of source directories does not establish a complete installation.
Registration must stay consistent across the common-skill index, applicable
**common-skill body pins**, and the source/installed surfaces for both providers.
Do not remove a pin check to suppress an orphan or missing-body warning.

Changes to a validator under the canonical Lead tree can change that tree's
identity. Review the exact **accepted-prior** transition and prove a stock
upgrade and a customized-tree refusal before declaring reinstall supported.
Do not synthesize a new tree digest or overwrite a customized installation.

In a complete checkout, verify the source, then disposable installed targets:

```text
python -m pytest -q tests
python src.codex/skills/lead/scripts/validate-skill-pack.py
python src.claude/agents/scripts/validate-skill-pack.py
python scripts/validate-agents-mode-installers.py --root .
python scripts/validate-provider-prompt-projections.py --help
python scripts/sync-universal-hooks.py --check
python scripts/check-publication-gate.py
```

The projection helper's `--help` only discovers its current invocation contract;
it is not a projection validation result. Perform the source and installed
checks required by that contract, plus clean install, exact reinstall, recognized
stock upgrade, customized-state preservation, and third-party hook/skill
coexistence. Native Windows runs remain separate evidence from Linux tests.
Do not normalize pinned source bytes merely to make an installer pass.

Keep release notes and root installation/overview links aligned with the actual
accepted surface. GitHub Actions and automatic bot triggers are not part of this
procedure. A source test or a schema-valid V2 example does not replace these gates.

## 5. Terms

**V1 — Version 1** is the current compatibility line. **Lead** is the accountable
orchestration owner. **Effort** is a model-local reasoning setting.
**CLI — Command-Line Interface** is a command-line entrypoint. **USD — United
States dollar** is the cost unit used by the Astra selector. **Pin** is an expected
content digest. **Accepted-prior** is a recognized exact prior stock payload,
not permission to overwrite arbitrary files. **Admission** is verified permission
to execute; **selection** only identifies a candidate. **Fallback** is an explicitly
permitted replacement route. **Terminal receipt** is execution-completion evidence.
