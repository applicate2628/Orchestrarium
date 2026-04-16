Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This is the first candidate backlog for the next benchmark-wave fixtures.

This file uses the upgraded-pack naming system:
new atomic tests enter as `T29+`.

## Candidate probes

| Candidate ID | Working name | Main target | Intended pressure |
|---|---|---|---|
| `T29` | toolchain false-root ambiguity | `L08 worker.toolchain-root-ownership` | multiple plausible roots, one true owner, explicit anti-hardcode verification |
| `T30` | static UI wrong-file attraction | `L05 review.ui-static` and `L09 worker.ui-implementation` | distractor components and nearby files that look editable but are not the real owner |
| `T31` | fallback noisy-evidence filter | `O04` and `O05` | reject tempting local hacks and preserve test surface while fixing the real owner |
| `T32` | constrained multi-step patch with no drift | `L06` and `L07` | reward sustained correct edits and punish collateral test or contract drift |
| `T33` | decorative consistency with asset distractors | `L09 worker.ui-implementation` | require style-consistent updates across the correct asset seam without touching decoys |

## Fixture design rules

| Rule | Meaning |
|---|---|
| non-browser first | new UI fixtures should remain non-browser by default |
| owner verification required | each fixture should verify that the real owning file or seam was used |
| anti-hardcode | verifiers should reject exact-path or brittle repo-specific cheats where feasible |
| anti-drift | passing should require preserving unrelated tests or visible contract surfaces |
| bounded but not toy | fixtures should remain runnable, but must be messy enough to expose shallow workers |

## Active recommendation

Start with `T29` and `T30` before broadening to the rest of the backlog.
