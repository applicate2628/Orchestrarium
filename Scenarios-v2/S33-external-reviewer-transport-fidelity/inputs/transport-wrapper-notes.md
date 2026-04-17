# Transport Wrapper Notes

- This adapter is a direct external launch contract. It does not proxy through an internal helper.
- Explicit provider selection disables automatic rerouting to other providers.
- The requested review strategy must be preserved exactly as assigned in the transport report.
- A successful route must remain review-only: do not emit semantic reviewer findings, QA verdicts, or remediation advice.
- If the selected provider CLI were unavailable, return `BLOCKED:dependency` instead of falling back internally.
- No internal reviewer, QA role, or consultant may stand in for the selected external route.
- Do not discuss the quality of the unexecuted semantic review artifact.
