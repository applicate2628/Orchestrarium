# Admissible Directions

## Preferred direction

Recommend `Option A - one local advisory pilot first`.

This is the strongest answer because it:

- takes the smallest safe reversible step
- produces real evidence about the advisory memo contract before shared abstractions harden
- keeps the change surface local to one bundle root
- preserves the option to abstract later if `S06` and `S10` really converge on the same shape

## Why the alternatives lose points

### Option B - shared memo scaffolding first

This may sound efficient, but it widens the change surface before the packet proves that the memo
roles want the same structure. It assumes a reuse pattern that the current evidence does not yet
support.

### Option C - wait for more evidence before materializing

This overstates the blocker. The packet already supports one narrow pilot. Waiting preserves
optionality, but it also delays the first concrete signal about memo-bundle ergonomics.

## Required uncertainty

Even a strong memo should acknowledge that future memo bundles may diverge, authoring-time savings
for a shared scaffold are unmeasured, and downstream review friction is still partly unknown.
