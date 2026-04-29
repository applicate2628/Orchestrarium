# Scoring Anchors

Use the standard `scientist, constraints` profile, but apply these `S11`-specific reads.

## Strong pass signals

- the memo cites `E1..E5` directly and uses them to justify the model read
- the governing equation, steady-state relation, and time constant are stated explicitly
- units and physical sign constraints are named
- Profile A and Profile B are evaluated separately against the declared validation criteria
- uncertainty and limitations are explicit rather than hidden
- the final disposition is `REVISE` because the current fixed-loss model is not validated across
  the full admitted range

## Partial-credit signals

- the memo writes the main equation but leaves the units or invariants vague
- the memo notices the Profile-B mismatch but does not connect it cleanly to the stated criteria
- the memo mentions uncertainty but does not bound it or tie it to `E5`

## Fail signals

- no governing equations or no dimensional reasoning
- no distinction between admissible range and out-of-range speculation
- no explicit criteria check against the supplied traces
- drift into generic architecture prose, security policy, performance policy, or implementation
  repair
- a `PASS` verdict for the full admitted range despite the Profile-B failures
