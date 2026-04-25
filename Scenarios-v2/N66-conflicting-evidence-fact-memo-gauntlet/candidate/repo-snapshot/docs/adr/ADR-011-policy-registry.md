# ADR-011: BillingMesh policy registry

Status: Accepted

BillingMesh policy enforcement is owned by the platform-policy team and resolved through the
in-process registry. The historical YAML policy file is deprecated documentation only and must not
be treated as the runtime source of truth.

Rollback through `LEGACY_POLICY=1` is rejected because it would split entitlement behavior between
API and reporting flows. Semantic policy changes require product re-intake.
