# Accepted Brief

## Admitted problem

The release workflow already has the right broad surface split:

- desktop is where curators prepare, edit, and locally validate the release bundle
- web is where reviewers inspect, question, approve, and publish

The problem is the state model between those surfaces. Operators do not know whether a bundle is
waiting on local fixes, an open reviewer question, a paused publish check, or a resumable draft.
The current experience also fails to return people to the right point after interruptions.

## Protected assumptions

- The workflow must stay split across desktop and web; this is not a single-surface redesign.
- Local validation failures, reviewer questions, change requests, and approval readiness must stay
  distinct states rather than collapse into one generic `needs work` bucket.
- Returning from an interruption should preserve context about what changed, who owns the next move,
  and where the operator resumes.
- The brief may restructure state labels, transitions, and handoff cues, but it must not prescribe
  implementation classes, routes, APIs, or storage changes.

## Success read

A strong brief gives operators one explicit state ladder plus a legible resume path whenever work is
interrupted or handed back.
