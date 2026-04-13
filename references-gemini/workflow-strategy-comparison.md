# Workflow Strategy Comparison

This reference compares the main workflow, review, and control strategies that matter to this standalone Gemini branch.

Use it together with:

- [subagent-operating-model.md](subagent-operating-model.md)
- [operating-model-diagram.md](operating-model-diagram.md)
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) when `.gemini/.agents-mode.yaml` behavior matters

## Strategy families

| Family | Main question | Typical examples |
|---|---|---|
| Structural gate | Do we need independent approval at all? | `builder / blocker separation`, `maker / checker`, `single-owner self-approval` |
| Reviewer mode | How should an independent reviewer inspect the artifact? | `Claim-Verify`, `Adversarial`, `Claim-Verify + Adversarial` |
| Workflow protection | How do we prevent chaos before review even starts? | `fact-first routing`, `risk-owner routing`, `rolling loop`, `re-intake`, `integration ownership`, `change isolation` |
| Automation support | What can be checked without human judgment? | tests, linters, static analysis, structural validators |

## Current repository defaults

| Concern | Default protection in this repository | Notes |
|---|---|---|
| Roadmap vs delivery ownership | `Roadmap / Intake loop` | `product-manager` owns admission; `lead` owns execution |
| Missing evidence | `Fact-first routing` | Use factual roles before interpretive ones |
| Critical domain risk | `Risk-owner routing` | Give the risk its own owner and artifact |
| Self-approval bias | `Builder / blocker separation` | Builder and blocking reviewer stay separate |
| Scope or priority drift | `Re-intake` | Route back to `product-manager` |
| Multi-phase landing | `Integration ownership` | Name one owner before QA |
| Stop-and-wait churn | `Rolling loop` | `PASS` advances, `REVISE` stays local for up to 3 cycles, `BLOCKED` stays rare |
| Broad unnecessary diff | `Change isolation` | Keep approved seams and blast radius explicit |

## Change classification matrix

| Change class | Forced routing / gates | Example |
|---|---|---|
| `cosmetic` | Usually QA only | wording, formatting, comments |
| `additive` | Normal delivery loop; extra specialist lanes only if a new risk owner appears | new code or docs that extend behavior without changing contracts |
| `behavioral` | Route through factual or design owner first if evidence is thin; QA required | validation, error handling, runtime flow changes |
| `breaking-or-cross-cutting` | Architect and usually planner; re-review affected downstream artifacts | contract, seam, migration, or multi-boundary changes |

## Minimal selection guide

| Situation | Start with | Then add |
|---|---|---|
| We do not know enough yet | `Fact-first routing` | `Risk-owner routing` if a critical domain risk appears |
| The risk is known and bounded | `Claim-Verify` | `Adversarial` only if missed blind spots are expensive |
| The risk is novel or poorly modeled | `Adversarial` | `Claim-Verify` first if execution fidelity is also critical |
| The change is clearly local and additive | `Additive fast lane` | Re-classify if the surface widens or a new risk owner appears |
| The item itself has changed | `Re-intake` | A fresh delivery loop after re-admission |
