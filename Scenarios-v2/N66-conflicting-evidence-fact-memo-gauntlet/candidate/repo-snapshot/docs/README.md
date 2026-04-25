# BillingMesh Policy Runtime

BillingMesh policies are stored in `config/policies/billingmesh.yaml`, and the reporting team owns
updates to that YAML file.

Premium accounts can always export from every region. Hidden-row export is not available yet; any
`include_hidden` request should be treated as unsupported until the migration lands.

If a registry migration is observed in code, set `LEGACY_POLICY=1` to force the YAML runtime for the
release window.
