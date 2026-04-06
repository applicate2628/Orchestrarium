# Workflow Strategy Comparison

This reference compares the main workflow, review, and control strategies that matter to this repository.

Use it together with:
- [subagent-operating-model.md](subagent-operating-model.md)
- [operating-model-diagram.md](operating-model-diagram.md)
- [operating-model.md](../agents/contracts/operating-model.md)

## 1. Strategy families

| Family | Main question | Typical examples |
|---|---|---|
| Structural gate | Do we need independent approval at all? | `builder / blocker separation`, `maker / checker`, `single-owner self-approval` |
| Reviewer mode | How should an independent reviewer inspect the artifact? | `Claim-Verify`, `Adversarial`, `Claim-Verify + Adversarial` |
| Workflow protection | How do we prevent chaos before review even starts? | `fact-first routing`, `risk-owner routing`, `rolling loop`, `re-intake`, `integration ownership`, `change isolation` |
| Automation support | What can be checked without human judgment? | `single-owner + automated gates`, CI, linters, tests, static analysis |

## 2. Current repository defaults

| Concern | Default protection in this repository | Notes |
|---|---|---|
| Roadmap vs delivery ownership | `Roadmap / Intake loop` | `product-manager` owns admission; `lead` owns execution |
| Missing evidence | `Fact-first routing` | Use factual roles before interpretive ones |
| Critical domain risk | `Risk-owner routing` | Give the risk its own owner and artifact |
| Self-approval bias | `Builder / blocker separation` | Builder and blocking reviewer stay separate |
| Known bounded review risk | `Claim-Verify` | Default when the risk surface is understood |
| Novel or externally exposed review risk | `Adversarial` | Default when blind spots matter more than speed |
| Critical change with both execution and blind-spot risk | `Claim-Verify + Adversarial` | Run in sequence, preserving reviewer independence |
| Scope or priority drift | `Re-intake` | Route back to `product-manager` |
| Multi-phase landing | `Integration ownership` | Name one owner before QA |
| Stop-and-wait churn | `Rolling loop` | `PASS` advances, `REVISE` stays local for up to 2 consecutive cycles on the same role and artifact, `BLOCKED` stays rare |
| Broad unnecessary diff | `Change isolation` | Keep approved seams, blast radius, and nearby smoke coverage explicit |

## 3. Structural and review strategies

| Strategy | Type | What it separates | Best at | Weak at | Cost | Use when | Repository status |
|---|---|---|---|---|---|---|---|
| `Single-owner self-approval` | structural baseline | nothing | tiny low-risk changes | blind spots, self-approval bias, hidden risks | very low | only for trivial work | not the default |
| `Single-owner + automated gates` | automation-supported baseline | builder vs automated checks | syntax, tests, static issues, contract regressions | architecture, UX, product intent, unknown unknowns | low | low-risk changes with strong automation | used as support, not as sole strategy |
| `Pair / co-builder` | collaborative build mode | two builders vs one | fast exploration and shared implementation context | weak independence, shared anchoring | medium | rapid exploration, not final governance | not a core pattern |
| `Maker / checker` | lightweight independent gate | builder vs checker | clear execution errors against known criteria | deep design blind spots | medium | bounded work that still needs a second set of eyes | partially overlaps with our reviewer lanes |
| `Builder / blocker separation` | structural gate | builder vs independent blocker | self-approval bias, risk-domain independence | weak if the blocker is over-anchored to builder reasoning | medium to high | any change where the risk can independently fail the result | core |
| `Claim-Verify` | reviewer mode | builder claims vs independent verification | bounded risks, known surfaces, execution fidelity | unknown unknowns and unmodeled threats | medium | the builder can state falsifiable guarantees | core |
| `Adversarial` | reviewer mode | builder reasoning vs hostile review | blind spots, novel failure modes, external exposure | routine bounded defects, speed-sensitive reviews | high | missed unknowns are more dangerous than missed execution bugs | core |
| `Claim-Verify + Adversarial` | combined review | first verify, then attack | critical work that needs both execution checking and blind-spot hunting | time and coordination cost | very high | critical changes with serious downside | supported when justified |
| `Spec-first + compliance review` | design-control mode | spec vs implementation | API/schema fidelity, predictable execution against stable contracts | weak if the spec itself is wrong | medium to high | contracts and interfaces are the main risk | used in parts of the design/plan flow |
| `Audit sampling` | governance mode | full stream vs sampled review | throughput in high-volume flows | misses problems by design | low to medium | bulk operations where full review is too expensive | not a core pattern |

## 4. Change classification matrix

Use this before choosing a workflow path. It tells you how risky the change is and what gates it should force.

| Change class | Forced routing / gates | Example |
|---|---|---|
| `cosmetic` | Usually QA only; no extra specialist lane by default | wording, formatting, comments, local refactors with no observable behavior change |
| `additive` | Normal delivery loop; QA required; add a specialist lane only if a new risk owner appears. The lead may use a fast lane only when the change stays within one module or clearly bounded seam, introduces no new risk owner, and leaves existing contracts and shared abstractions unchanged | new code or docs that extend behavior without changing existing contracts or defaults |
| `behavioral` | Route through factual/design owner first if evidence is thin; QA required; add an independent reviewer when contracts, flow, or failure modes matter | runtime behavior, validation, error handling, or user-facing flow changes |
| `breaking-or-cross-cutting` | Architect and usually planner; re-review affected downstream artifacts; integration owner when multiple phases or specialists land together; reviewer lanes as needed | contract, migration, seam, dependency direction, rollout/rollback, or multi-boundary changes |

## 5. Workflow protection strategies

Embedded repository defaults are shown in **bold**.

| Strategy | Main purpose | Best at preventing | Escalate when | Repository status |
|---|---|---|---|---|
| **`Roadmap / Intake loop`** | keep roadmap ownership upstream of delivery | priority drift, implicit admission, delivery owning roadmap questions | admission into delivery is still not explicit | **core** |
| **`Delivery loop`** | move approved work through one staged execution path | lifecycle mixing and ad hoc routing | a critical risk or independent reviewer must be inserted | **core** |
| **`Fact-first routing`** | gather evidence before interpretation | opinion noise, speculative design, false certainty | interpretive roles are being asked to guess | **core** |
| **`Risk-owner routing`** | make one risk explicitly owned | security/performance/reliability/UX drift inside generic implementation | a risk can independently fail the result | **core** |
| **`Rolling loop`** | keep work moving without stop-and-wait churn | idle handoff latency and over-escalation of small corrections | work is stalling between accepted artifacts | **core** |
| **`Re-intake`** | send changed work back to roadmap ownership | quiet scope renegotiation inside delivery | the admitted item itself has changed | **core** |
| **`Integration ownership`** | ensure one coherent result before QA | “each phase passed, but the whole system is not integrated” | multiple implementation phases or specialists must land together | **core** |
| **`Change isolation`** | constrain blast radius and protect seams | unrelated-module churn, accidental cross-cutting edits, hidden dependency reversal | a local feature needs broad structural edits | **core** |
| **`Human / CI gate`** | add explicit external approval before publication | silent promotion of AI-accepted work into push/merge/release | team policy requires human or CI approval | **core** |
| **`Consultant advisory`** | add a non-blocking second opinion without mutating the main pipeline | premature commitment on ambiguity or cross-cutting tradeoffs | facts are assembled but route choice is still ambiguous | **supported, optional** |
| **`Parallel read lanes`** | accelerate independent evidence gathering | serial read-only bottlenecks | scopes overlap or synthesis cost outweighs speed | **supported** |
| `Parallel write lanes` | accelerate disjoint implementation work | unnecessary serial implementation when boundaries are already frozen | write scopes overlap or contracts are still moving | conditional only |

## 6. Quick selection guide

| If the situation is... | Start with... | Then add... |
|---|---|---|
| We do not know enough yet | `Fact-first routing` | `Risk-owner routing` if a critical domain risk appears |
| We know the task but a domain risk can sink it | `Risk-owner routing` | `Builder / blocker separation` if the risk needs independent approval |
| The risk is known and bounded | `Claim-Verify` | `Adversarial` only if the downside of a missed blind spot is high |
| The risk is novel, exposed, or poorly modeled | `Adversarial` | `Claim-Verify` first if execution fidelity is also critical |
| The change is clearly local and additive | `Additive fast lane` | re-classify to the normal delivery loop if the surface widens or a new risk owner appears |
| The item itself has changed | `Re-intake` | a fresh delivery loop after re-admission |
| The work spans multiple implementation phases | `Integration ownership` | QA and reviewer gates after one integrated artifact exists |
| The diff is getting too broad for a local change | `Change isolation` | re-route to `architect`, `planner`, or `architecture-reviewer` as needed |

## 7. Selection heuristics

- Use `Claim-Verify` when the reviewer should check whether the builder actually delivered what was promised.
- Use `Adversarial` when the reviewer should look for what the builder may never have modeled.
- Use `Builder / blocker separation` when self-approval would make the result untrustworthy.
- Use `Fact-first routing` whenever the next real question is factual rather than interpretive.
- Use `Re-intake` when the admitted item has changed, not just the current artifact.
- Use `Integration ownership` when QA would otherwise receive partially assembled work.
- Treat `change isolation` as a first-class protection, not as an implementation detail.
