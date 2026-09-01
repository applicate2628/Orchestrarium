# N01 UX Structure Brief

- Brief owner: `$ux-designer`
- Surfaces in scope: Windows desktop routing workspace plus web release console
- Artifact boundary: one UX structure brief only

## UX objective

Give operators one legible information hierarchy so the current release decision is obvious before
they act, across the desktop workspace and the web release console.

## Users and operating context

Curators, reviewers, and approvers move between the desktop workspace and the web console and must
not re-learn the hierarchy on each surface.

## Current hierarchy and information-structure failures

- Publish readiness reads as just another metadata badge instead of the top-level release verdict.
- Blockers and unresolved reviewer asks look like ordinary notes.
- Screenshots and supporting metadata are visually stronger than the release decision.

## Information hierarchy principles

- Lead with the decision, not the decoration.
- Keep shared facts named the same across surfaces.
- Rank by consequence: what blocks a release outranks what merely describes it.

## Proposed cross-surface information structure

The shared ladder leads with the current release verdict, then the active blocker or reviewer ask,
then owner and lane, then evidence freshness, and only then supporting metadata. Screenshots are
demoted below the release decision on both surfaces.

### Desktop workspace hierarchy

- Foreground the current release verdict and any active blocker; the blocker outranks pack ID and
  scenario count.

### Web release console hierarchy

- Lead the detail page with the current release verdict instead of the history and screenshot tabs.

### Shared naming and hierarchy ladder

- Use one shared naming set for verdict, blocker, reviewer ask, owner, and evidence freshness so the
  cross-surface ladder does not need translation; supporting metadata stays last.

## Proposed static emphasis model

- Primary (desktop and web): the current release verdict and the active blocker.

### Primary focus regions

- The release verdict and blocker are the primary focus regions on both desktop and web.

### Secondary detail zones

- Secondary: owner, lane, and evidence freshness.

### Escalation and exception cues

- Deferred: screenshots, routine metadata, and passive counts sit in deferred zones, below the
  release decision, and must not outrank a blocker.

## Key hierarchy changes

- Demote routine metadata, history, and screenshots below the release verdict and any unresolved
  reviewer ask, using one cross-surface ladder so nothing outranks a blocker.

## Boundaries to implementation and review

- Implementation stays out of scope; this is structure only.
- Review findings stay out of scope; this is not a review report.

## Open questions and follow-ups

- How many shared labels can desktop and web adopt without churn?

## Brief status

PASS
