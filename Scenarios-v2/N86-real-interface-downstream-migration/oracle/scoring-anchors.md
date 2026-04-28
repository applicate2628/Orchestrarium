# N86 Scoring Anchors

Score this as a real interface migration task, not as a style rewrite.

Highest-value evidence:

- Structured API result models replace ambiguous legacy return values with no compatibility wrappers.
- Hidden consumers preserve missing/suspended/expired accounts, tenant disablement, feature denial,
  denied-without-publish, publisher timeout, duplicate usage, accepted usage, and reporting counts.
- The hidden downstream app imports only public package exports and can serialize structured
  dataclass results without module-private knowledge.
- Migration state binds source ids, stale-source rejection, interface map, call sites, compatibility
  matrix, validation, and exact patch budget.
- Review response resolves every review item with owner and validation cue.
- Closeout records exact changed paths, validation command, review outcome, and residual risk.
