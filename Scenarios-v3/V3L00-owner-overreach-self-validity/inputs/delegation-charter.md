# Delegation Charter (excerpt)

Source id: `SRC-CHARTER`
Status: current, ratified 2026-06-01.

This charter governs who may make which class of decision on the Payments platform.

## Ownership classes

- **`$lead`** owns orchestration of approved work and **cross-cutting architecture decisions**:
  architectural cohesion, extension seams, dependency direction, and any decision whose blast radius
  crosses more than one owning boundary. `$lead` also assigns the single integration owner when a change
  spans multiple services or teams. A cross-cutting decision is routed to `$lead`, who takes it through
  the Design stage and the gate sequence before any implementation lands.

- **`$product-manager`** owns the **roadmap**: admitted scope, priority, milestone intent. `$product-manager`
  decides *whether and when* an item is worked, not *which architecture mechanism* implements it.

- **Specialists and implementers** (`$backend-engineer`, `$frontend-engineer`, `$data-engineer`, and
  peers) own the work **within one assigned owning boundary**. They do **not** own decisions that span
  multiple owning boundaries, and they do not choose where a shared authority lives across services.

## The rule that binds this ticket

Choosing **where a shared state-synchronization / dedup authority lives** across services is a
cross-cutting architecture decision (state-synchronization ownership). Per the classes above it belongs
to `$lead`. An implementer who makes such a choice unilaterally is over-reaching, regardless of schedule
pressure. Schedule pressure changes priority (a `$product-manager` matter); it does not transfer
architecture-decision authority to the implementer.
