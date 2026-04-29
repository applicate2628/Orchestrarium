# ADR-014: YAML rollback switch

Status: Draft

Proposal: restore `config/policies/billingmesh.yaml` as the primary source and use
`LEGACY_POLICY=1` to roll back the registry if export behavior surprises operators.

This draft was opened after an incident review but was never accepted.
