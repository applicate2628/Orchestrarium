# Accepted Review Scope

This bundle reviews one additive helper that materializes packet data for a generic findings-only
code-review lane.

## Required behavior

1. The changed-path list must preserve all touched review surfaces from the bounded diff, including
   `modified`, `added`, and `renamed` entries.
2. Finding dedupe may normalize title text as a helper hint, but distinct findings must remain
   separate when the path or line anchor differs.
3. Malformed hunk headers must stay diagnosable. The packet builder may reject them or surface an
   explicit parse problem, but it must not silently degrade them into empty evidence.
4. The helper remains bundle-local and additive. Small fixed limits, a local dataclass, and stable
   non-security hashing for local dedupe are accepted implementation choices in this admitted scope.

## Review posture

- raise correctness or diagnosability issues that require `REVISE`
- keep the report generic; this packet does not admit a separate architecture, security, or
  performance review lane
