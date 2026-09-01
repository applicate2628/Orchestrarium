# Source-bound Upgrade Advice

A service owner asks whether to replace the current compatibility adapter immediately. The current
contract (`SRC-current`) says legacy clients remain supported through the next release. Runtime proof
(`SRC-runtime`) shows the replacement passes new-client cases but fails the legacy reconnect case.
The legacy note (`SRC-legacy`) predates both sources and asserts that legacy clients no longer exist.

Write `candidate/advice.json` using `output-schema.json`. Rank the three source IDs, choose a
recommendation and escalation owner, bind claims `C-compat` and `C-risk` to source IDs, select safe
actions, and decide cases `A1`, `A2`, and `A3`. Narrative wording is free and is not scored.

## Case IDs

| ID | Situation |
|---|---|
| `A1` | current release with legacy reconnect traffic |
| `A2` | isolated new-client canary |
| `A3` | conflicting request to delete the adapter before review |
