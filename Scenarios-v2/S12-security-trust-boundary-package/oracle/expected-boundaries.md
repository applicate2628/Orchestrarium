# Expected Trust Boundaries

The package should make these boundaries explicit and explain what crosses each one.

## `TB1` Scenario bundle input -> runner-owned workspace

Bundle content, attachment manifests, and path references are candidate-controlled inputs from the
runner's point of view. The design must confine file resolution to the admitted bundle root and
must not let bundle-supplied paths widen into archive or workstation content.

Evidence anchors: `E1`, `E2`, `E5`

## `TB2` Runner-orchestrator -> credential broker

Secrets originate from the broker, not from bundle material or persisted config. Retrieval, scope,
and storage rules must be explicit because the current draft leaks environment values into debug
capture.

Evidence anchors: `E1`, `E3`, `E4`, `E5`

## `TB3` Runner/provider launcher -> external provider transport

The provider CLI and upstream service are allowed integrations but not trusted local components.
Only an allowlisted prompt packet and selected attachments may cross this boundary, and returned
output remains untrusted until validated.

Evidence anchors: `E1`, `E2`, `E4`, `E5`

## `TB4` Raw evidence vault -> analyst export package

Raw artifacts are more sensitive and less trusted than the analyst package. The design must keep
restricted raw storage separate from redacted broader-access export material.

Evidence anchors: `E1`, `E2`, `E4`, `E5`

## `TB5` Human operator approval -> service-account automation

Operator approval is a distinct trust boundary. The current draft blurs approval, vault writing,
and analyst export publication behind the same service-account path.

Evidence anchors: `E1`, `E3`, `E5`
