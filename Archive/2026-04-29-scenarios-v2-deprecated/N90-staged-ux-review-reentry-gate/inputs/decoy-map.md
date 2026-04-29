# False-Positive Decoy Map

Reject these as findings:

- `FP1-disabled-opacity-decoy`: `.publish-button[disabled]` uses opacity, but the stylesheet also renders a visible disabled reason.
- `FP2-noopener-link-decoy`: the docs link uses `rel="noopener"` for link hardening.
- `FP3-empty-draft-label-decoy`: `.empty-draft-label` is a neutral zero-state label, not a publish gating failure.
