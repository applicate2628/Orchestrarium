# Optional skill registry

This is the source registry of supplementary skills reviewed for use with Orchestrarium. They are not Orchestrarium roles, part of the default install, or prerequisites for dispatch or acceptance. Lead selects relevant, available and authorized methods; the assigned role owns their application. Existing criteria, checks and independent review establish the guarantee, not a skill invocation.

| Skill | Use when | Source pin and license |
| --- | --- | --- |
| [`ponytail-review`](ponytail/skills/ponytail-review/SKILL.md) | Review a change for unnecessary complexity; use normal correctness and architecture review separately. | [DietrichGebert/ponytail @ `356918e`](https://github.com/DietrichGebert/ponytail/tree/356918eba965ee1eac64bd3a7f0dd02108350de5), [MIT](ponytail/LICENSE) |
| [`ponytail-audit`](ponytail/skills/ponytail-audit/SKILL.md) | Audit existing scoped code for avoidable complexity; findings are advisory and do not authorize edits. | Same pinned source and license. |

These copies are the two upstream skill texts and their license only. Do not install the upstream plugin, hooks, scripts or background services from this registry. Use a copy as a reference or enable the individual skill through the host's normal mechanism if approved; reuse an existing matching installation instead of creating a second skill with the same name. If unavailable, use the normal architecture/review criteria and continue. Interpret all findings, examples and any upstream recommendation to ship as complexity advice only. They neither certify correctness nor authorize acceptance or publication. Do not narrow validation or safeguards to reduce code.

Review changes to a source pin and its license before updating the copy. Proprietary marketplace skill text is not included; architectural work uses the existing `architect` and `architecture-reviewer` roles.
