# Orchestrarium Model Routing Version 2

## Contents

1. [Scope](#1-scope)
2. [Model and effort dimensions](#2-model-and-effort-dimensions)
3. [Default routes](#3-default-routes)
4. [Resolution modes](#4-resolution-modes)
5. [Complete-route economics](#5-complete-route-economics)
6. [Safety and independence](#6-safety-and-independence)
7. [Migration](#7-migration)
8. [Command-line use](#8-command-line-use)
9. [Terms and abbreviations](#9-terms-and-abbreviations)

## 1. Scope

Version 2 is a parallel model-routing contract. It does not rewrite the
Version 1 role policy, native role Tom's Obvious Minimal Language (TOML)
bindings, or installer ownership receipts.

Its source surfaces are:

- `shared/model-catalog.v2.json`;
- `shared/role-routing-policy.v2.json`;
- `scripts/model_routing/resolve_v2.py`.

The resolver is pure policy. It validates versioned inputs and returns a
nonauthorizing decision. It never launches a provider, mutates configuration,
or grants acceptance, merge, security, or publication authority.

## 2. Model and effort dimensions

### 2.1 Execution class

```text
mechanical -> Luna
general    -> Terra, Sol, Astra
```

Luna is not part of the general capability order. Its existing Orchestrarium
corridor remains a zero-decision-authority mechanical executor.

### 2.2 General capability

```text
balanced < frontier < apex
Terra       Sol        Astra
```

### 2.3 Exact model-effort profiles

A profile is the exact pair `model + reasoning effort`.

| Model | Admitted efforts |
|---|---|
| Luna | `none`, `low`, `medium`, `high`, `xhigh`, `max` |
| Terra | `none`, `low`, `medium`, `high`, `xhigh`, `max` |
| Sol | `none`, `low`, `medium`, `high`, `xhigh`, `max` |
| Astra | `low`, `medium`, `high`, `xhigh`, `max` |

Effort is model-local. Sol `xhigh` is not assumed to dominate Astra `medium`.
For Astra, the task policy owns the baseline effort:

- deep mathematics, connected science, cross-system synthesis, and critical
  design start at `medium`;
- critical recovery starts at `high`;
- a downshift requires `migration-evaluation` or `measured-sufficient`;
- `high` above a `medium` baseline requires `medium-objective-failure` or
  `measured-high-gain`;
- `xhigh` requires `high-objective-failure`, `high-contradictory`, or
  `measured-xhigh-gain`;
- `max` requires explicit human approval;
- `none` is invalid for Astra.

## 3. Default routes

| Task class | Default profile |
|---|---|
| Mechanical read/write | Luna `high` |
| Routine exploration, planning, review, or engineering | Role-compatible Terra/Sol profile |
| Routine science | Sol `high` |
| Mathematical research | Astra `medium` |
| Connected scientific workflow | Astra `medium` |
| Cross-system synthesis | Astra `medium` |
| Critical design | Astra `medium` |
| Critical security | Sol `xhigh` |
| Recovery | Sol `high` |
| Critical recovery | Astra `high` |

The policy rejects `max` as an automatic default. Critical-security Astra use
is never an automatic default and requires a separate safety approval.

## 4. Resolution modes

### 4.1 `policy-default`

Selects the exact task default. Missing or unknown model availability fails
closed. There is no implicit fallback.

### 4.2 `explicit`

Accepts one exact profile or a migration alias. The route must remain inside
the role's allowed profile corridor and satisfy the task's capability and
effort floors. Astra requires task-compatible route evidence, and nondefault
Astra effort is checked independently.

### 4.3 `optimize`

Requires one estimate for every currently available comparison profile admitted
by task and role policy. The objective and required evidence are explicit:

| Objective | Required evidence | Primary metric |
|---|---|---|
| `api-cost` | `measured-api-cost-to-pass` | Expected OpenAI Application Programming Interface cost |
| `tokens` | `measured-route-efficiency` | Expected total tokens |
| `steps` | `measured-route-efficiency` | Expected coordination steps |
| `latency` | `measured-route-efficiency` | Expected route wall time |

Missing, extra, malformed, future-dated, or incomparable estimates fail closed.
Each estimated call is bound to a known task, eligible role, role-admitted
profile, and an available model. The primary call is also bound to the exact
requested task and role.

## 5. Complete-route economics

Each route estimate includes:

- one exact primary call;
- every support, retry, and independent-review call;
- uncached input, cached input, cache-write, and output tokens;
- tool cost;
- actual route wall time and aggregate call time;
- coordination steps and rework cycles;
- attempted and accepted results on one comparison corpus;
- the quality-floor result.

Prices use integer nanodollars per token on the declared
`openai-api-standard` channel. For every call independently:

<a id="equation-1"></a>
\[
C_{\mathrm{call}}
=
C_{\mathrm{uncached}}
+C_{\mathrm{cached}}
+C_{\mathrm{cache\ write}}
+C_{\mathrm{output}}
+C_{\mathrm{tools}}.
\tag{1}
\]

The catalog's long-context input/cache and output multipliers apply separately
to each call whose prompt exceeds the recorded threshold. They are not applied
to the sum of several smaller calls.

For any route metric \(M\), expected consumption per accepted result is:

<a id="equation-2"></a>
\[
E[M_{\mathrm{accepted}}]
=
M_{\mathrm{route}}
\frac{N_{\mathrm{attempted}}}{N_{\mathrm{accepted}}}.
\tag{2}
\]

The resolver retains [equation (2)](#equation-2) as an exact rational number for:

- OpenAI API cost;
- total tokens;
- model calls;
- retry calls;
- rework cycles;
- coordination steps;
- wall time.

Hard admission gates and the quality floor run before optimization. The chosen
objective is the first ordering key; the remaining metrics and stable profile
identifier are deterministic tie-breaks. Therefore Astra `medium` may win on
tokens, steps, or latency when one stronger route replaces repeated Sol calls,
while `api-cost` may retain Sol when its complete accepted route remains cheaper.

The pricing snapshot has an explicit review date. Resolution after that date
fails with `E_MODEL_V2_PRICING_STALE` instead of silently using obsolete rates.

## 6. Safety and independence

- Automatic Astra fan-out is limited to one primary instance.
- Critical-security Astra use requires explicit critical-capability approval.
- `max` effort requires explicit human approval.
- Required independent reviewer-role execution is structural and cannot be
  removed by optimization.
- Provider independence is reported separately: Sol and Astra share the
  `openai` evidence-independence group and do not count as two independent
  provider families.
- The resolver always returns `fallback: none` and remains nonauthorizing.

## 7. Migration

Version 1 aliases preserve their old meaning:

```text
apex-max       -> sol-max
pinned-top-pro -> sol-xhigh
```

The old `apex-max` was Sol `max`; it must not silently become Astra. Astra is
selected only by an explicit Astra profile, a Version 2 task default, or a
complete measured comparison.

## 8. Command-line use

Write one exact request document and pass its path:

```bash
python scripts/model_routing/resolve_v2.py --request request.json
```

Minimal policy-default request:

```json
{
  "schemaVersion": 2,
  "mode": "policy-default",
  "taskClass": "mathematical-research",
  "role": "algorithm-scientist",
  "availability": {
    "terra": "available",
    "sol": "available",
    "astra": "available"
  },
  "requestedProfile": null,
  "routeEvidence": null,
  "effortEvidence": null,
  "allowMaxEffort": false,
  "allowCriticalAstra": false,
  "requestedFanout": 1,
  "objective": null,
  "routeEstimates": null,
  "asOf": "2026-09-04"
}
```

The process exits `0` only for `selected` and `2` for a typed denial or
unavailable route.

## 9. Terms and abbreviations

- **API — Application Programming Interface:** programmatic model access.
- **Astra:** GPT-6 Astra, the apex general-purpose model.
- **Effort:** model-local reasoning-effort setting.
- **Expected metric to acceptance:** complete-route resource use adjusted by
  the measured accepted-result rate.
- **Fallback:** alternate route after the requested route cannot run.
- **QA — Quality Assurance:** independent verification outside model selection.
- **TOML — Tom's Obvious Minimal Language:** native Codex role configuration.
