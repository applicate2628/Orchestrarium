# Terra, Luna, Sol, and Astra Routing Audit

## Contents

1. [Audited state](#1-audited-state)
2. [Repository-wide findings](#2-repository-wide-findings)
3. [Version 1 point upgrade](#3-version-1-point-upgrade)
4. [Version 2 correction](#4-version-2-correction)
5. [Reasoning-effort policy](#5-reasoning-effort-policy)
6. [Pull-request interaction](#6-pull-request-interaction)
7. [Verification obligations](#7-verification-obligations)
8. [Terms and abbreviations](#8-terms-and-abbreviations)

## 1. Audited state

The audit covers:

- `main` at `ece04040627fcc0d0988128e44d401de53ff01fb`;
- Pull Request (PR) 4 at `3dbfb9faf824365f5898fe52dd10093f4d75da9c`;
- PR 5 at `ea7a9cfc21f7f5b8e78ec9681fd458917ff7aea1`;
- the pre-correction PR 6 head at `8787a1ae9a993fdbef116437019c921ce8682bd7`;
- current OpenAI model and reasoning-effort documentation observed on 2026-09-04.

PR 4 does not change the model-routing policy, native model bindings, or
provider-profile schema. PR 5 adds policy overlays and Ponytail compatibility;
its current files do not overlap the model catalog, role policy, or Astra
resolver. PR 6 is stacked on PR 4 and is the Version 1 point-upgrade branch.

## 2. Repository-wide findings

### 2.1 Current ownership surfaces

Model and effort semantics are distributed across:

1. `shared/role-routing-policy.v1.json`;
2. `src.codex/agents/*.toml`;
3. `src.codex/agents/orchestrarium-role-manifest.json`;
4. `shared/agents-mode.schema.json`;
5. `shared/agents-mode.defaults.yaml`;
6. `shared/agents-mode.presets.json`;
7. `scripts/resolve-agents-mode.py`;
8. `scripts/provider_prompt.py`;
9. provider skills, references, validators, and tests.

The Version 1 role manifest hash-binds the role policy and every native role
file. A quick upgrade that rewrites those objects would require exact
stock-prior migration and would no longer be a point change.

### 2.2 Semantic defects

1. Version 1 orders `mechanical < balanced < frontier < apex`, although Luna is
   a zero-decision-authority mechanical execution class, not the lowest general
   reasoning tier.
2. `apex-max` still binds `gpt-5.6-sol`; Version 1 therefore has a named apex
   tier without an apex model.
3. `allowedProfiles` is validated but is not a general runtime selector.
   Native roles use static model and effort values from Tom's Obvious Minimal
   Language (TOML) files.
4. Exact model identifiers and effort choices are duplicated across policy,
   native roles, operator presets, transport parsing, tests, and docs.
5. Version 1 has no owner for complete-route economics: input, cached input,
   cache writes, output, repeated calls, tool costs, retries, rework, review,
   and elapsed time.
6. Model capability and reasoning effort are partially separated but still
   compared as though one global effort ladder had the same meaning for every
   model.
7. Sol and Astra belong to the same OpenAI evidence-independence group and
   cannot supply two provider-independent opinions.

### 2.3 Official model constraints used by the design

- Luna, Terra, and Sol admit `none`, `low`, `medium`, `high`, `xhigh`, and
  `max`; Astra admits `low`, `medium`, `high`, `xhigh`, and `max`.
- Astra is priced above Sol per token, but published evidence also reports
  fewer iterations, fewer written steps in some work, lower elapsed time in
  some agentic tasks, and up to 20% fewer tokens in one partner workflow.
- Published evaluation scores are the maximum at any tested effort. They do
  not prove that a reported maximum is specifically a `medium` result.
- The long-context price multiplier applies per request, so a three-call Sol
  route and a one-call Astra route must be priced call by call.

## 3. Version 1 point upgrade

Version 1 keeps all existing native roles, policy hashes, operator defaults,
and installed ownership rules unchanged. It adds one explicit `astra-routing`
skill and pure resolver.

The corrected resolver requires two independent decisions:

1. **Route admission:** why Astra is used at all.
2. **Effort admission:** why the selected Astra effort differs from the task
   default.

Accepted route evidence is task-specific:

| Task class | Route evidence | Default effort |
|---|---|---|
| `mathematical-research` | `mathematics-quality-floor` or `measured-cost-to-pass` | `medium` |
| `scientific-agentic-workflow` | `connected-science-workflow` or `measured-cost-to-pass` | `medium` |
| `cross-system-synthesis` | `cross-system-context-retention` or `measured-cost-to-pass` | `medium` |
| `critical-recovery` | `verified-frontier-recovery` or `measured-cost-to-pass` | `high` |

`measured-cost-to-pass` requires positive integer Astra and legacy route costs,
and Astra is selected only when its complete expected route cost is strictly
lower. This prevents effort-failure evidence from silently authorizing an
otherwise unjustified Astra route.

Version 1 remains:

- explicit rather than automatic;
- limited to one Astra instance;
- nonauthorizing;
- unavailable without silent fallback;
- independent of native role TOML and `agents-mode`.

## 4. Version 2 correction

Version 2 introduces parallel, versioned artifacts rather than mutating
Version 1:

- `shared/model-catalog.v2.json`;
- `shared/role-routing-policy.v2.json`;
- `scripts/model_routing/resolve_v2.py`;
- `tests/test_model_routing_v2.py`;
- `docs/model-routing-v2.md`.

The corrected model:

```text
mechanical execution: Luna

general capability:
balanced -> Terra
frontier -> Sol
apex    -> Astra
```

Version 2 uses exact `model + effort` profiles, model-local effort admission,
runtime availability states, explicit maximum-effort approval, Astra security
approval where required, a one-instance Astra fan-out ceiling, and no implicit
fallback.

For deep mathematics, connected scientific workflows, cross-system synthesis,
and critical design, the policy default is Astra `medium`. Critical recovery
defaults to Astra `high`. Routine science remains Sol `high`.

Automatic comparison mode evaluates the complete available policy-declared
candidate set. Every route estimate contains all calls, raw token buckets,
route wall time, coordination steps, retry calls, rework cycles, independent
review, and an acceptance probability. The caller selects one explicit
objective: OpenAI Application Programming Interface (API) cost, total tokens,
steps, or latency. The resolver:

1. prices each call independently and applies long-context multipliers per call;
2. computes expected cost, total tokens, model calls, retries, rework cycles,
   steps, and wall time to an accepted result;
3. removes routes that fail the quality floor or hard admission gates;
4. minimizes the selected objective with deterministic secondary tie-breaks;
5. records the exact objective and API pricing channel in the decision.

This allows Astra `medium` to win when one stronger pass uses fewer tokens or
steps than a multi-call Sol `xhigh` route, even when the single Astra call has a
higher API price. An API-cost objective can independently keep Sol when the
complete accepted Sol route remains cheaper.

No scalar score can override availability, role eligibility, effort support,
maximum-effort approval, safety admission, review requirements, or fan-out.

## 5. Reasoning-effort policy

Effort is model-local, not a universal quality rank.

For Astra:

- `low`: migration evaluation or measured sufficiency;
- `medium`: default for deep mathematics, connected science, and cross-system
  synthesis;
- `high`: objective medium failure or measured gain; also the critical-recovery
  default;
- `xhigh`: objective high failure, contradiction, or measured gain;
- `max`: explicit human approval only;
- `none`: invalid.

Astra `medium` may outperform Sol `xhigh`, but the router does not assume that
from labels. It uses policy defaults for known task classes and complete
measured route estimates for economic optimization.

## 6. Pull-request interaction

- PR 6 remains the narrow Version 1 point upgrade stacked on PR 4.
- The Version 2 branch is stacked on the corrected PR 6 head.
- PR 5 remains independent; it should be merged or rebased by merge commit
  according to its own ownership contract rather than copied into either
  model-routing branch.
- No GitHub Actions workflow is added or used.

## 7. Verification obligations

Before either branch leaves draft state:

1. run the focused Version 1 and Version 2 tests;
2. run Python compilation and `git diff --check`;
3. run both provider-pack validators in a full checkout;
4. run installer and publication-gate checks;
5. run Codex review on each final head;
6. add the repository-required release-note and public-index updates when the
   owning integration branch is ready for publication.

## 8. Terms and abbreviations

- **Astra:** GPT-6 Astra, the apex general-purpose model.
- **Effort:** model-local reasoning effort.
- **PR — Pull Request:** a proposed branch merge.
- **QA — Quality Assurance:** independent implementation verification.
- **TOML — Tom's Obvious Minimal Language:** native Codex role configuration.
- **Version 1 / Version 2:** compatibility contract and redesigned routing contract.
