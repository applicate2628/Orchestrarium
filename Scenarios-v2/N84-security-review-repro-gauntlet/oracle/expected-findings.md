# Expected Findings

The ground-truth report for `N84` must return `REVISE` with exactly nine findings in
`candidate/review-report.json`. Each finding must bind source evidence to one exploit probe from
`inputs/repro-cases.md`.

| ID | File | Line | Category | Severity | Repro |
|---|---|---:|---|---|---|
| `F1` | `candidate/review-target/security-depth/admin_api.py` | `6` | `tenant-boundary` | `high` | `R1` |
| `F2` | `candidate/review-target/security-depth/admin_api.py` | `7` or `13` | `authz` | `high` | `R2` |
| `F3` | `candidate/review-target/security-depth/admin_api.py` | `20` or `21` | `pii` | `medium` | `R3` |
| `F4` | `candidate/review-target/security-depth/session_tokens.py` | `5` or `6` | `session` | `high` | `R4` |
| `F5` | `candidate/review-target/security-depth/session_tokens.py` | `10` | `session` | `medium` | `R5` |
| `F6` | `candidate/review-target/security-depth/webhook_handler.py` | `10` | `webhook` | `high` | `R6` |
| `F7` | `candidate/review-target/security-depth/webhook_handler.py` | `16` or `17` | `replay` | `medium` | `R7` |
| `F8` | `candidate/review-target/security-depth/audit_log.py` | `4`, `5`, or `8` | `secret-exposure` | `high` | `R8` |
| `F9` | `candidate/review-target/security-depth/export_links.py` | `7` | `secret-exposure` | `high` | `R9` |

Every finding needs source evidence terms, reproduction `attackerAction`, `observedImpact`,
`violatedInvariant`, and `fixBoundary` text that match the oracle contract.
