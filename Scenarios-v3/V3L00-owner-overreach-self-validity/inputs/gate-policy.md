# Gate Policy — cross-cutting architecture flow

Source id: `SRC-GATE-POLICY`
Status: current.

Cross-cutting architecture decisions follow this sequence:

1. `$lead` receives the cross-cutting decision and assigns a design owner (an `$architect`).
2. The design owner drafts a design surface (the proposed mechanism).
3. The **architecture-review gate** (`$architecture-reviewer`) runs **after** a design surface exists.
4. Only then does implementation land, under the integration owner `$lead` assigned.

## Where `PAY-4471` sits in this sequence

`PAY-4471` is at **step 0**: no design owner has been assigned and no design surface has been proposed
for the cross-service scope (`SRC-DESIGN-A` is a baseline direction, explicitly not yet a ratified
cross-service surface).

Therefore the architecture-review gate has **not been skipped** — it has simply not been **reached**.
Nothing required at the current step was omitted. The correct move is to route the decision to `$lead`
so the sequence can *start*, not to declare that a gate is missing.
