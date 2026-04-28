# ConsoleShip Workflow Context

The publish workflow has five important runtime situations:

1. Local checks are green, but remote review is stale.
2. A release owner is missing.
3. A risk waiver is accepted, but regression evidence is still missing.
4. The packet is truly ready and contains an auditor-only hidden-export note.
5. The packet has been published and needs a re-entry path for follow-up diffs.

False readiness is the main UX failure. A green local-check badge is not enough to publish. Publish
must never become the dominant action until owner, remote-review freshness, risk/regression evidence,
and export-scope cues are resolved.

Breakpoint expectations:

- Desktop `1440`: state summary, source evidence, and action rail can be visible together.
- Tablet `900`: state summary and action rail stay visible; source evidence can move below.
- Mobile `390`: state summary must come first; publish must not appear before unresolved owner/risk
  cues; secondary evidence can collapse.

Role boundary: UX design owns visible state, copy, ordering, and handoff expectations. Implementation
owns components, CSS, API calls, tests, and persistence.
