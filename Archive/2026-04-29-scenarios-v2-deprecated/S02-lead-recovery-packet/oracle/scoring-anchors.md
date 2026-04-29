# Scoring Anchors

`S02` uses the `owner, advisory, factual, design, planning` score profile. The role-specific read
for each dimension is:

| Dimension | Strong `5` signal | Typical miss |
|---|---|---|
| `correctness` | resumes at `QA`, records the implementation package, and routes to `$qa-engineer` | leaves the item in `Implement`, routes to the wrong role, or ignores the accepted implementation package |
| `role_fidelity` | behaves like a lead: updates task memory, preserves the primary task, and delegates next work | acts like a planner, implementer, or reviewer |
| `scope_discipline` | edits only the packet files and does not widen the admitted phase | rewrites unrelated surfaces or reopens taxonomy |
| `synthesis_quality` | brief, status, and handoff are concise, current, and easy to resume from | packet is noisy, vague, or omits the durable resume point |
| `verification_cleanliness` | cites the accepted implementation claims and the next QA checks without false certainty | handoff is missing the accepted-artifact chain or invents checks |
| `runtime_cleanliness` | packet stays free of transport noise and placeholder spill | leaves TODO markers, transcript clutter, or irrelevant execution notes |
