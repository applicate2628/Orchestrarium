# Known Risks

- review bundles are vulnerable to role-boundary drift when authors try to make the review output
  directly actionable for implementers
- control-plane rules drift when read-only and protected-path lists are copied into multiple local
  owners instead of referenced from one contract
- reviewers sometimes over-report cosmetic duplication; in this scenario only maintained rule copies
  or boundary violations should be treated as architecture findings
- the presence of a downstream publication module is not itself a defect; the defect is pulling that
  downstream module into bundle-authoring logic
