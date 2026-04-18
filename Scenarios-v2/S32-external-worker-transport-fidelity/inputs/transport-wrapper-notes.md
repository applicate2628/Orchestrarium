# Transport Wrapper Notes

- This adapter is a direct external launch contract. It does not proxy through an internal helper.
- Explicit provider selection disables automatic rerouting to other providers.
- If the selected provider CLI is available and exposes a valid direct path, preserve that provider
  and report the direct external CLI route.
- If the selected provider CLI is unavailable, return `BLOCKED:dependency`.
- A missing external route must be reported as `Resolved provider: none` and
  `Actual execution path: role disabled`.
- No internal implementer, reviewer, or consultant may stand in for the disabled route.
- Do not discuss the quality of the unexecuted semantic worker artifact.
