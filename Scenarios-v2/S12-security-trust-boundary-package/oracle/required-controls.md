# Required Controls

These are the ground-truth control anchors for `S12`.

## `C1` Path confinement and manifest allowlisting

Attachment manifests and bundle-supplied paths must be canonicalized and confined to the admitted
bundle root before staging. Parent traversal, symlink escape, and widened archive reads are
must-fail conditions.

Evidence anchors: `E1`, `E2`, `E5`

## `C2` Broker-only secret acquisition and non-persistence

Provider and vault credentials must come only from the broker, remain short-lived and run-scoped,
and never be serialized into bundle material, debug capture, raw logs, or analyst exports.

Evidence anchors: `E3`, `E4`, `E5`

## `C3` Transport minimization and environment allowlist

Only the prompt packet, explicit attachment allowlist, and a minimal environment contract may cross
to the provider launcher. Full environment snapshots and implicit repo upload are disallowed.

Evidence anchors: `E1`, `E3`, `E4`, `E5`

## `C4` Untrusted output quarantine and schema validation

Provider stdout, stderr, structured packets, and returned attachments remain untrusted until they
are schema-checked, sanitized, and explicitly selected for downstream use. They must never be
executed or copied verbatim into a broader-trust surface.

Evidence anchors: `E2`, `E4`, `E5`

## `C5` Redaction gate and storage/access separation

Raw evidence vault storage and analyst export storage must remain separate in both path and access
policy. The analyst package is derived output produced through an explicit redaction gate, not a
view into the raw vault.

Evidence anchors: `E1`, `E3`, `E4`, `E5`

## `C6` Distinct identities, provenance, and approval boundary

Raw-vault writes, analyst export publication, and operator approval must be distinguishable in
identity, provenance, and audit fields. One service-account path must not stand in for all three.

Evidence anchors: `E1`, `E3`, `E5`
