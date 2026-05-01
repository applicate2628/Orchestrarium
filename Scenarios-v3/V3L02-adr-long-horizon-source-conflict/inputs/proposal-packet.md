Date: 2026-04-29
Source id: `SRC-PROPOSAL`
Authority: proposal only

# Proposal Packet

The migration proposal lists four options:

| Option | Name | Summary |
|---|---|---|
| `A` | global entitlement bus | replace PlanBridge event ownership with a central bus |
| `B` | boundary-owned compatibility adapter | keep PlanBridge as owner and emit v1 plus v2 through one compatibility adapter |
| `C` | consumer-side shims | ask each consumer to convert missing fields locally |
| `D` | direct schema switch | replace `PlanEnvelopeV1` with `PlanEnvelopeV2` immediately |

Proposal preference:

- The proposal author prefers Option A for long-term platform consolidation.

Proposal caveat:

- The proposal did not include the 2026-04-30 runtime trace or the latest downstream tests.
