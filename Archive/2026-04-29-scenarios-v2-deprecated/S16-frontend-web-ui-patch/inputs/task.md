# Task

You are acting as `$frontend-engineer` on a bounded implementation bundle.

## Goal

Repair the browser UI in `candidate/workspace/` so the release-readiness board satisfies the
accepted state and accessibility contract without widening into preview infrastructure, fixtures, or
non-web surfaces.

## Required output

Update these files only:

- `candidate/workspace/src/dashboard.js`
- `candidate/workspace/src/ui-copy.js`
- `candidate/workspace/src/dashboard.css`

## Requirements

- loading state must expose a polite live-region message that announces the in-progress refresh
- success state must render real filter buttons with `aria-pressed`, a visible active state, and a
  summary tied to the result list
- empty state must explain that the selected filter produced no matches and provide a reset action
- error state must announce the failure with an alert and must not keep stale result cards visible
- result cards must expose an accessibility-sensitive label that includes the check title and status
- keyboard focus must remain visible for filter controls and the empty-state or retry actions
- preserve the preview shell, fixture data, browser checklist, and local verifier wiring

## Disallowed behavior

- do not edit anything under `inputs/`, `oracle/`, or `verifiers/`
- do not edit `candidate/README.md`
- do not edit `candidate/workspace/package.json` or `candidate/workspace/index.html`
- do not edit `candidate/workspace/src/main.js` or `candidate/workspace/src/fixtures.js`
- do not edit `candidate/workspace/scripts/**` or `candidate/workspace/tests/**`
- do not add dependencies, change the preview server, or turn this into a Qt, backend, or platform
  task
